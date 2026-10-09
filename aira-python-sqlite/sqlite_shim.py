"""
sqlite_shim.py — a drop-in replacement for the small slice of pymongo's API
that aira_bot.py actually uses, backed by a local SQLite file instead of a
network round-trip to MongoDB Atlas.

Why this exists: aira_bot.py's Mongo usage is confined to one connection
line (`pymongo.MongoClient(MONGO_URI)`) and a consistent set of call
patterns across ~70 call sites: `find_one`, `replace_one` (upsert),
`find` (with `$gt`-style filters, `.sort()`, `.limit()`, and an ignored
projection arg), `update_one` (with `$set`/`$addToSet`), and one
`bulk_write([ReplaceOne(...), ...])` call. This module implements exactly
that surface — nothing more — so the other ~8,000 lines of aira_bot.py
don't need to change at all.

Each Mongo "collection" becomes one SQLite table, storing one JSON blob
per document (keyed by _id) — the same flexible, schema-less shape Mongo
gave the original code, just without a network hop.

Usage in aira_bot.py (see MIGRATION.md for the exact 3-line diff):
    from sqlite_shim import ReplaceOne, MongoClient
    ...
    client = MongoClient(SQLITE_DB_PATH)   # instead of pymongo.MongoClient(MONGO_URI)
"""

import json
import sqlite3
import threading
from typing import Any, Dict, Iterable, List, Optional


def _matches(doc: Dict[str, Any], filt: Dict[str, Any]) -> bool:
    """Minimal Mongo-style filter matching: exact-match fields, plus
    $gt/$gte/$lt/$lte/$ne/$in operator dicts — the only operators
    aira_bot.py's queries actually use."""
    for key, want in filt.items():
        have = doc.get(key)
        if isinstance(want, dict):
            for op, opval in want.items():
                if op == "$gt" and not (have is not None and have > opval):
                    return False
                elif op == "$gte" and not (have is not None and have >= opval):
                    return False
                elif op == "$lt" and not (have is not None and have < opval):
                    return False
                elif op == "$lte" and not (have is not None and have <= opval):
                    return False
                elif op == "$ne" and have == opval:
                    return False
                elif op == "$in" and have not in opval:
                    return False
                elif op not in ("$gt", "$gte", "$lt", "$lte", "$ne", "$in"):
                    return False  # unsupported operator — fail closed rather than silently mismatch
        else:
            if have != want:
                return False
    return True


class ReplaceOne:
    """Matches pymongo.ReplaceOne's constructor signature — used by the one
    bulk_write() call site in save_data()."""

    def __init__(self, filter: Dict[str, Any], replacement: Dict[str, Any], upsert: bool = False):
        self.filter = filter
        self.replacement = replacement
        self.upsert = upsert


class Cursor:
    """Just enough of pymongo's chainable cursor for .sort()/.limit()/iteration."""

    def __init__(self, docs: List[Dict[str, Any]]):
        self._docs = docs

    def sort(self, field: str, direction: int = 1) -> "Cursor":
        self._docs.sort(key=lambda d: (d.get(field) is None, d.get(field, 0)), reverse=(direction == -1))
        return self

    def limit(self, n: int) -> "Cursor":
        self._docs = self._docs[:n]
        return self

    def __iter__(self):
        return iter(self._docs)

    def __len__(self):
        return len(self._docs)


class ShimCollection:
    def __init__(self, conn: sqlite3.Connection, lock: threading.Lock, name: str):
        self.conn = conn
        self.lock = lock
        self.name = name
        with self.lock:
            self.conn.execute(f'CREATE TABLE IF NOT EXISTS "{name}" (_id TEXT PRIMARY KEY, doc TEXT NOT NULL)')
            self.conn.commit()

    def _all_docs(self) -> Iterable[Dict[str, Any]]:
        cur = self.conn.execute(f'SELECT _id, doc FROM "{self.name}"')
        for _id, doc_json in cur.fetchall():
            doc = json.loads(doc_json)
            doc["_id"] = _id
            yield doc

    def find_one(self, filt: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        filt = filt or {}
        if "_id" in filt and len(filt) == 1:
            cur = self.conn.execute(f'SELECT doc FROM "{self.name}" WHERE _id = ?', (str(filt["_id"]),))
            row = cur.fetchone()
            if row is None:
                return None
            doc = json.loads(row[0])
            doc["_id"] = str(filt["_id"])
            return doc
        for doc in self._all_docs():
            if _matches(doc, filt):
                return doc
        return None

    def find(self, filt: Optional[Dict[str, Any]] = None, projection: Optional[Dict[str, Any]] = None) -> Cursor:
        # projection is accepted (aira_bot.py passes one at a few call sites)
        # but intentionally ignored — returning extra fields is harmless
        # since callers only read the fields they asked to project.
        filt = filt or {}
        docs = [d for d in self._all_docs() if _matches(d, filt)]
        return Cursor(docs)

    def replace_one(self, filt: Dict[str, Any], replacement: Dict[str, Any], upsert: bool = False) -> None:
        _id = str(filt.get("_id", replacement.get("_id")))
        doc = dict(replacement)
        doc["_id"] = _id
        with self.lock:
            self.conn.execute(
                f'INSERT INTO "{self.name}" (_id, doc) VALUES (?, ?) '
                f"ON CONFLICT(_id) DO UPDATE SET doc = excluded.doc",
                (_id, json.dumps(doc)),
            )
            self.conn.commit()

    def update_one(self, filt: Dict[str, Any], update: Dict[str, Any], upsert: bool = False) -> None:
        existing = self.find_one(filt) or {"_id": str(filt.get("_id", ""))}
        if "$set" in update:
            existing.update(update["$set"])
        if "$addToSet" in update:
            for field, value in update["$addToSet"].items():
                arr = existing.get(field, [])
                if value not in arr:
                    arr.append(value)
                existing[field] = arr
        if "$inc" in update:
            for field, value in update["$inc"].items():
                existing[field] = existing.get(field, 0) + value
        if "$unset" in update:
            for field in update["$unset"]:
                existing.pop(field, None)
        if "$pull" in update:
            for field, value in update["$pull"].items():
                existing[field] = [x for x in existing.get(field, []) if x != value]
        self.replace_one(filt, existing, upsert=True)

    def bulk_write(self, ops: List[ReplaceOne], ordered: bool = False) -> None:
        if not ops:
            return
        rows = []
        for op in ops:
            _id = str(op.filter.get("_id", op.replacement.get("_id")))
            doc = dict(op.replacement)
            doc["_id"] = _id
            rows.append((_id, json.dumps(doc)))
        with self.lock:
            # executemany + a single commit, instead of one commit per row
            # (the fix for save_data() doing thousands of individual disk
            # fsyncs on every call — this does exactly one).
            self.conn.executemany(
                f'INSERT INTO "{self.name}" (_id, doc) VALUES (?, ?) '
                f"ON CONFLICT(_id) DO UPDATE SET doc = excluded.doc",
                rows,
            )
            self.conn.commit()

    def count_documents(self, filt: Optional[Dict[str, Any]] = None) -> int:
        return len(list(self.find(filt)))


class ShimDatabase:
    def __init__(self, conn: sqlite3.Connection, lock: threading.Lock):
        self.conn = conn
        self.lock = lock
        self._collections: Dict[str, ShimCollection] = {}

    def __getitem__(self, name: str) -> ShimCollection:
        if name not in self._collections:
            self._collections[name] = ShimCollection(self.conn, self.lock, name)
        return self._collections[name]


class MongoClient:
    """Drop-in for pymongo.MongoClient — takes a SQLite file path instead
    of a mongodb:// URI. `client["aira"]` returns the same ShimDatabase
    regardless of the name passed, since it's all one local file."""

    def __init__(self, sqlite_path: str = "aira.db"):
        self.conn = sqlite3.connect(sqlite_path, check_same_thread=False)
        self.conn.execute("PRAGMA journal_mode = WAL;")
        self.conn.execute("PRAGMA synchronous = NORMAL;")
        self.conn.execute("PRAGMA wal_autocheckpoint = 500;")
        self.conn.execute("PRAGMA busy_timeout = 5000;")
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA synchronous=NORMAL")  # safe with WAL; only a real DB engine crash mid-write risks losing the last transaction, not a normal bot crash/restart
        self.lock = threading.Lock()
        self._db = ShimDatabase(self.conn, self.lock)

    def __getitem__(self, _name: str) -> ShimDatabase:
        return self._db

    def close(self):
        self.conn.close()


