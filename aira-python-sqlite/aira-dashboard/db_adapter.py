"""
db_adapter.py
──────────────
Talks to aira.db directly (no bot process involved) so the dashboard works
even while the bot is stopped.

ASSUMPTION - PLEASE VERIFY (see SETUP.md "Before you deploy"):
Your context doc describes the bot's Mongo-shim tables as a key/value style
table per collection:

    CREATE TABLE <collection> (_id TEXT PRIMARY KEY, doc TEXT)   -- doc = JSON blob

This file was written against that shape for three collections: "users",
"groups" and "meta". I did NOT have your real sqlite_shim.py, only
aira_bot.py, so I could not confirm groups/meta actually follow the same
pattern (only that they go through the same shim client aira_bot.py uses).

Call GET /api/schema-check (the dashboard does this automatically and shows
a banner) - verify_schema() below checks the real tables/columns and tells
you immediately if something doesn't match, instead of silently showing
empty data.

If your real schema differs, the only things you should need to change are:
  - TABLE_* constants below
  - the field names inside list_users / get_user / analytics_snapshot
    (marked with # FIELD ASSUMPTION comments)

Redeem codes: your bot's existing redeem handler may expect a specific table
/ code format that I have no record of. To stay safe, codes created here go
into their own dedicated table (REDEEM_TABLE, created if missing) rather than
guessing at your bot's existing one. If your bot already has a redeem-codes
table/command, point REDEEM_TABLE at it and adjust _redeem_doc() to match
its field names before relying on this in production.
"""
from __future__ import annotations

import json
import os
import re
import secrets
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator, Optional

DB_PATH = Path(os.environ.get("AIRA_DB_PATH", "aira.db"))

TABLE_USERS = "users"
TABLE_GROUPS = "groups"
TABLE_META = "meta"
REDEEM_TABLE = "dashboard_redeem_codes"

PAGE_SIZE = 25
CURRENCY_FIELDS = ("coins", "gems")

# FIELD ASSUMPTION → now confirmed against the real aira_bot.py you shared.
# The bot's actual _USER_DEFAULTS has: username, full_name, coins, gems,
# hunts, streak, best_streak, total_coins_ever, badges, weapon, pet, etc.
# It does NOT store any per-user timestamp anywhere (no joined_at, no
# last_seen/last_active field persisted to sqlite) — the only "last activity"
# concept in the whole bot is an in-memory, per-process dict that resets on
# every restart and isn't saved, so it's not something this dashboard can
# read from the database. Rather than show a column that will always be
# blank, "Last seen" has been replaced below with fields that actually
# exist: hunts and best streak.
FIELD_USERNAME = "username"
FIELD_NAME = "full_name"
FIELD_JOINED_AT = None   # does not exist in this bot's schema — see note above
FIELD_LAST_SEEN = None   # does not exist in this bot's schema — see note above
FIELD_BROADCAST_OPTOUT = "broadcast_optout"  # also doesn't exist yet; harmless no-op until/unless you add it


@contextmanager
def _conn() -> Iterator[sqlite3.Connection]:
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    try:
        yield con
        con.commit()
    finally:
        con.close()


def _table_exists(con: sqlite3.Connection, name: str) -> bool:
    row = con.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (name,)
    ).fetchone()
    return row is not None


def _ensure_redeem_table(con: sqlite3.Connection) -> None:
    con.execute(
        f"CREATE TABLE IF NOT EXISTS {REDEEM_TABLE} ("
        f"code TEXT PRIMARY KEY, amount INTEGER, currency TEXT, "
        f"created_at REAL, redeemed_by TEXT, redeemed_at REAL)"
    )


# ─── generic doc access (mirrors the bot's own get/upsert shape) ────────

def get_doc(table: str, doc_id: str) -> Optional[dict]:
    with _conn() as con:
        if not _table_exists(con, table):
            return None
        row = con.execute(f"SELECT doc FROM {table} WHERE _id = ?", (doc_id,)).fetchone()
        if row is None:
            return None
        return json.loads(row["doc"])


def upsert_doc(table: str, doc_id: str, doc: dict) -> None:
    with _conn() as con:
        con.execute(
            f"INSERT INTO {table} (_id, doc) VALUES (?, ?) "
            f"ON CONFLICT(_id) DO UPDATE SET doc = excluded.doc",
            (doc_id, json.dumps(doc)),
        )


def delete_doc(table: str, doc_id: str) -> bool:
    with _conn() as con:
        cur = con.execute(f"DELETE FROM {table} WHERE _id = ?", (doc_id,))
        return cur.rowcount > 0


# ─── users ───────────────────────────────────────────────────────────────

def get_user(uid: str) -> Optional[dict]:
    doc = get_doc(TABLE_USERS, uid)
    if doc is None:
        return None
    return {"_id": uid, **doc}


def list_users(search: str = "", page: int = 1) -> dict:
    with _conn() as con:
        if not _table_exists(con, TABLE_USERS):
            return {"users": [], "total": 0, "page": page, "pages": 0}
        rows = con.execute(f"SELECT _id, doc FROM {TABLE_USERS}").fetchall()

    users = []
    needle = search.strip().lower()
    for row in rows:
        doc = json.loads(row["doc"])
        uid = row["_id"]
        username = str(doc.get(FIELD_USERNAME, "") or "")
        name = str(doc.get(FIELD_NAME, "") or "")
        if needle and needle not in uid.lower() and needle not in username.lower() and needle not in name.lower():
            continue
        users.append({
            "_id": uid,
            "username": username,
            "name": name,
            "coins": doc.get("coins", 0),
            "gems": doc.get("gems", 0),
            "hunts": doc.get("hunts", 0),
            "best_streak": doc.get("best_streak", 0),
            "total_coins_ever": doc.get("total_coins_ever", 0),
            "badges": doc.get("badges") or [],
        })

    users.sort(key=lambda u: (u["total_coins_ever"] or 0), reverse=True)
    total = len(users)
    pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
    page = min(max(1, page), pages)
    start = (page - 1) * PAGE_SIZE
    return {"users": users[start:start + PAGE_SIZE], "total": total, "page": page, "pages": pages}


def adjust_currency(uid: str, field: str, delta: int) -> dict:
    if field not in CURRENCY_FIELDS:
        raise ValueError(f"Unknown currency field '{field}', expected one of {CURRENCY_FIELDS}")
    doc = get_doc(TABLE_USERS, uid)
    if doc is None:
        raise KeyError(f"No such user '{uid}'")
    current = int(doc.get(field, 0) or 0)
    doc[field] = max(0, current + int(delta))
    upsert_doc(TABLE_USERS, uid, doc)
    return doc


# Fields that represent a timed cooldown/lock and are safe to clear from the
# admin panel — confirmed present in the bot's real _USER_DEFAULTS.
RESETTABLE_COOLDOWN_FIELDS = (
    "hunt_cooldown", "daily_claimed", "auto_hunt_expiry", "owo_boost_expiry",
    "half_cooldown_expiry", "cheap_autohunt_expiry", "shield_expiry", "pray_expires",
)


def reset_cooldowns(uid: str) -> dict:
    doc = get_doc(TABLE_USERS, uid)
    if doc is None:
        raise KeyError(f"No such user '{uid}'")
    for field in RESETTABLE_COOLDOWN_FIELDS:
        if field in doc:
            doc[field] = None
    upsert_doc(TABLE_USERS, uid, doc)
    return doc


def grant_badge(uid: str, badge: str) -> dict:
    doc = get_doc(TABLE_USERS, uid)
    if doc is None:
        raise KeyError(f"No such user '{uid}'")
    badges = doc.get("badges") or []
    if badge not in badges:
        badges.append(badge)
    doc["badges"] = badges
    upsert_doc(TABLE_USERS, uid, doc)
    return doc


# ─── analytics ───────────────────────────────────────────────────────────

def analytics_snapshot() -> dict:
    now = time.time()

    with _conn() as con:
        users_rows = con.execute(f"SELECT doc FROM {TABLE_USERS}").fetchall() if _table_exists(con, TABLE_USERS) else []
        groups_rows = con.execute(f"SELECT doc FROM {TABLE_GROUPS}").fetchall() if _table_exists(con, TABLE_GROUPS) else []

    total_coins = total_gems = total_hunts = total_coins_ever = 0
    users_with_pet = users_with_streak = 0
    top_streak = 0
    for row in users_rows:
        doc = json.loads(row["doc"])
        total_coins += int(doc.get("coins", 0) or 0)
        total_gems += int(doc.get("gems", 0) or 0)
        total_hunts += int(doc.get("hunts", 0) or 0)
        total_coins_ever += int(doc.get("total_coins_ever", 0) or 0)
        if doc.get("pet"):
            users_with_pet += 1
        streak = int(doc.get("best_streak", 0) or 0)
        if streak > 0:
            users_with_streak += 1
        top_streak = max(top_streak, streak)

    return {
        "total_users": len(users_rows),
        "total_groups": len(groups_rows),
        "total_coins": total_coins,
        "total_gems": total_gems,
        "total_hunts": total_hunts,
        "total_coins_ever": total_coins_ever,
        "users_with_pet": users_with_pet,
        "users_with_streak": users_with_streak,
        "top_streak": top_streak,
        "generated_at": now,
        "note": (
            "This bot doesn't store a per-user join date or last-active timestamp "
            "anywhere in the database (confirmed against the real _USER_DEFAULTS in "
            "aira_bot.py), so 'new users today' / 'active today' can't be computed "
            "honestly — these metrics use fields that do exist instead."
        ),
    }


def broadcast_targets() -> list[int]:
    targets: list[int] = []
    with _conn() as con:
        if _table_exists(con, TABLE_USERS):
            for row in con.execute(f"SELECT _id, doc FROM {TABLE_USERS}").fetchall():
                doc = json.loads(row["doc"])
                if doc.get(FIELD_BROADCAST_OPTOUT):
                    continue
                # The bot's user doc has no separate chat_id field — the row's
                # own _id (the sqlite-shim key) IS the Telegram chat id.
                try:
                    targets.append(int(row["_id"]))
                except (TypeError, ValueError):
                    continue
        if _table_exists(con, TABLE_GROUPS):
            for row in con.execute(f"SELECT _id FROM {TABLE_GROUPS}").fetchall():
                try:
                    targets.append(int(row["_id"]))
                except (TypeError, ValueError):
                    continue
    return targets


# ─── redeem codes ────────────────────────────────────────────────────────

def _generate_code() -> str:
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # no 0/O/1/I ambiguity
    chunk = lambda: "".join(secrets.choice(alphabet) for _ in range(4))
    return f"AIRA-{chunk()}-{chunk()}"


def create_redeem_codes(count: int, amount: int, currency: str = "gems") -> list[str]:
    if count < 1 or count > 500:
        raise ValueError("count must be between 1 and 500")
    if amount < 1:
        raise ValueError("amount must be positive")
    if currency not in CURRENCY_FIELDS:
        raise ValueError(f"currency must be one of {CURRENCY_FIELDS}")

    codes = []
    with _conn() as con:
        _ensure_redeem_table(con)
        for _ in range(count):
            for _attempt in range(5):
                code = _generate_code()
                try:
                    con.execute(
                        f"INSERT INTO {REDEEM_TABLE} (code, amount, currency, created_at, redeemed_by, redeemed_at) "
                        f"VALUES (?, ?, ?, ?, NULL, NULL)",
                        (code, amount, currency, time.time()),
                    )
                    codes.append(code)
                    break
                except sqlite3.IntegrityError:
                    continue
    return codes


def list_redeem_codes() -> list[dict]:
    with _conn() as con:
        _ensure_redeem_table(con)
        rows = con.execute(
            f"SELECT code, amount, currency, created_at, redeemed_by, redeemed_at "
            f"FROM {REDEEM_TABLE} ORDER BY created_at DESC"
        ).fetchall()
    return [dict(row) for row in rows]


def revoke_redeem_code(code: str) -> bool:
    with _conn() as con:
        _ensure_redeem_table(con)
        cur = con.execute(f"DELETE FROM {REDEEM_TABLE} WHERE code = ?", (code,))
        return cur.rowcount > 0


# ─── schema self-check ───────────────────────────────────────────────────

def verify_schema() -> list[str]:
    problems: list[str] = []
    if not DB_PATH.exists():
        return [f"Database file not found at {DB_PATH} - check AIRA_DB_PATH."]

    with _conn() as con:
        for table in (TABLE_USERS, TABLE_GROUPS, TABLE_META):
            if not _table_exists(con, table):
                problems.append(f"Table '{table}' not found - dashboard expected it to exist.")
                continue
            cols = {r["name"] for r in con.execute(f"PRAGMA table_info({table})")}
            missing = {"_id", "doc"} - cols
            if missing:
                problems.append(
                    f"Table '{table}' is missing column(s) {sorted(missing)} - "
                    f"dashboard assumes a (_id TEXT, doc TEXT JSON) shape."
                )

        if _table_exists(con, TABLE_USERS):
            sample = con.execute(f"SELECT doc FROM {TABLE_USERS} LIMIT 25").fetchall()
            if sample:
                seen_currency = any(
                    any(k in json.loads(r["doc"]) for k in CURRENCY_FIELDS) for r in sample
                )
                if not seen_currency:
                    problems.append(
                        "No user docs sampled contain a 'coins' or 'gems' field - "
                        "double check CURRENCY_FIELDS in db_adapter.py matches your bot."
                    )
    return problems
