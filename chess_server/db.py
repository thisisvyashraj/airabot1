"""
Mongo persistence for the chess service.
Reuses the SAME MongoDB cluster/URI as the main bot (MONGO_URI env var),
just adds new collections inside the existing "aira" database so you don't
need a second database: chess_ratings, chess_games, chess_rooms, chess_queue.
"""
import os
import time
import secrets
import string
import pymongo

MONGO_URI = os.environ.get("MONGO_URI", "")

_client = None
_db = None


def get_db():
    global _client, _db
    if _db is None:
        _client = pymongo.MongoClient(MONGO_URI)
        _db = _client["aira"]
        _db["chess_ratings"].create_index("uid", unique=True)
        _db["chess_games"].create_index("game_id", unique=True)
        _db["chess_rooms"].create_index("room_code", unique=True)
    return _db


# ── Ratings ──────────────────────────────────────────────────────────────
DEFAULT_RATING = 1200


def get_rating_doc(uid: int, name: str = None):
    db = get_db()
    doc = db["chess_ratings"].find_one({"uid": uid})
    if doc is None:
        doc = {
            "uid": uid, "name": name or str(uid), "rating": DEFAULT_RATING,
            "peak_rating": DEFAULT_RATING, "wins": 0, "losses": 0, "draws": 0,
            "games_played": 0, "updated_at": time.time(),
        }
        db["chess_ratings"].insert_one(doc)
    elif name and doc.get("name") != name:
        db["chess_ratings"].update_one({"uid": uid}, {"$set": {"name": name}})
        doc["name"] = name
    return doc


def save_rating_doc(doc: dict):
    db = get_db()
    db["chess_ratings"].update_one({"uid": doc["uid"]}, {"$set": doc}, upsert=True)


def get_leaderboard(limit: int = 10):
    db = get_db()
    return list(db["chess_ratings"].find().sort("rating", -1).limit(limit))


# ── Games ────────────────────────────────────────────────────────────────
def new_game_id() -> str:
    return secrets.token_urlsafe(9)


def new_room_code() -> str:
    alphabet = string.ascii_uppercase + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(6))


def save_game(game: dict):
    db = get_db()
    db["chess_games"].update_one({"game_id": game["game_id"]}, {"$set": game}, upsert=True)


def load_game(game_id: str):
    db = get_db()
    return db["chess_games"].find_one({"game_id": game_id})


def save_room(room: dict):
    db = get_db()
    db["chess_rooms"].update_one({"room_code": room["room_code"]}, {"$set": room}, upsert=True)


def load_room(room_code: str):
    db = get_db()
    return db["chess_rooms"].find_one({"room_code": room_code})
