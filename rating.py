"""
chess_server/rating.py
Elo-style rating system modeled on how FIDE actually computes rating
changes:
  - K=40 for players with fewer than 30 rated games (new players move fast)
  - K=20 for players rated under 2400 with 30+ games
  - K=10 for players rated 2400 and above
  - expected score via the standard logistic curve:
        E_a = 1 / (1 + 10 ** ((R_b - R_a) / 400))
  - new_rating = old_rating + K * (actual_score - expected_score)

Bot opponents have a FIXED reference rating per difficulty level (see
engine.BOT_LEVELS) and are never themselves rated up/down -- exactly like
how FIDE doesn't re-rate a tournament's pairing software. Beating a higher
-rated bot nets you more rating than beating a low one, and losing to a low
-rated bot costs you more than losing to a strong one, same as it would
against a human of that rating.
"""
from datetime import datetime, timezone

DEFAULT_RATING = 1200


def k_factor(rating: int, games_played: int) -> int:
    if games_played < 30:
        return 40
    if rating >= 2400:
        return 10
    return 20


def expected_score(r_a: float, r_b: float) -> float:
    return 1 / (1 + 10 ** ((r_b - r_a) / 400))


def get_or_create_rating(collection, uid: int, name: str = None) -> dict:
    doc = collection.find_one({"_id": str(uid)})
    if doc:
        if name and doc.get("name") != name:
            collection.update_one({"_id": str(uid)}, {"$set": {"name": name}})
            doc["name"] = name
        return doc
    doc = {
        "_id": str(uid),
        "name": name or "Player",
        "rating": DEFAULT_RATING,
        "peak_rating": DEFAULT_RATING,
        "games": 0,
        "wins": 0,
        "losses": 0,
        "draws": 0,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    collection.insert_one(doc)
    return doc


def apply_result(collection, uid: int, my_rating: int, opp_rating: int, score: float) -> int:
    """score: 1 = win, 0.5 = draw, 0 = loss. Returns the new rating."""
    doc = get_or_create_rating(collection, uid)
    games = doc.get("games", 0)
    k = k_factor(my_rating, games)
    expected = expected_score(my_rating, opp_rating)
    new_rating = round(my_rating + k * (score - expected))

    update = {
        "rating": new_rating,
        "games": games + 1,
        "peak_rating": max(doc.get("peak_rating", DEFAULT_RATING), new_rating),
    }
    if score == 1:
        update["wins"] = doc.get("wins", 0) + 1
    elif score == 0:
        update["losses"] = doc.get("losses", 0) + 1
    else:
        update["draws"] = doc.get("draws", 0) + 1

    collection.update_one({"_id": str(uid)}, {"$set": update})
    return new_rating
