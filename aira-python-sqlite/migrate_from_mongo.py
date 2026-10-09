"""
migrate_from_mongo.py — ONE-TIME migration: copies every user, group, and
meta document out of your live MongoDB Atlas database into the new local
aira.db (SQLite) file, so switching from fps.ms/Mongo to the VM/SQLite
version doesn't lose anyone's coins, zoo, badges, or group settings.

Run this ONCE on the new host, before starting the bot for the first time.
Needs pymongo temporarily (NOT part of the bot's normal requirements.txt
anymore — install it just for this one script, then you can uninstall it).

Usage:
    pip install pymongo --break-system-packages   # just for this script
    MONGO_URI="mongodb+srv://...你的真实连接串..." python3 migrate_from_mongo.py
"""

import os
import sys

MONGO_URI = os.environ.get("MONGO_URI")
if not MONGO_URI:
    print("Set MONGO_URI to your (rotated) Atlas connection string and re-run:")
    print('  MONGO_URI="mongodb+srv://..." python3 migrate_from_mongo.py')
    sys.exit(1)

try:
    import pymongo
except ImportError:
    print("Run: pip install pymongo --break-system-packages")
    sys.exit(1)

from sqlite_shim import MongoClient as SqliteClient

SQLITE_DB_PATH = os.environ.get("SQLITE_DB_PATH", "aira.db")

print(f"Connecting to Atlas...")
mongo = pymongo.MongoClient(MONGO_URI)
mongo_db = mongo["aira"]

print(f"Opening local SQLite file: {SQLITE_DB_PATH}")
sqlite_client = SqliteClient(SQLITE_DB_PATH)
sqlite_db = sqlite_client["aira"]

counts = {}
for collection_name in ["users", "groups", "meta"]:
    docs = list(mongo_db[collection_name].find())
    for doc in docs:
        doc_id = str(doc["_id"])
        doc_copy = dict(doc)
        doc_copy["_id"] = doc_id
        sqlite_db[collection_name].replace_one({"_id": doc_id}, doc_copy, upsert=True)
    counts[collection_name] = len(docs)
    print(f"  {collection_name}: {len(docs)} documents migrated")

mongo.close()
sqlite_client.close()

print(f"\n✅ Migration complete.")
print(f"   Users: {counts.get('users', 0)}")
print(f"   Groups: {counts.get('groups', 0)}")
print(f"   Meta docs: {counts.get('meta', 0)}")
print(f"\nYou can now start aira_bot.py normally — it'll use {SQLITE_DB_PATH}.")
