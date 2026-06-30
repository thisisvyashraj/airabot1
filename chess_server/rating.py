"""
FIDE-style Elo rating updates.

Expected score: E_A = 1 / (1 + 10^((R_B - R_A) / 400))
New rating:     R_A' = R_A + K * (S_A - E_A)

K-factor follows real FIDE bands:
  - K = 40 for players with fewer than 30 rated games (provisional)
  - K = 20 for players rated under 2400 (with 30+ games)
  - K = 10 for players rated 2400 or above
Rating floor of 100 (FIDE effectively floors near 1400, but we go lower so
brand-new accounts and the easiest bot levels stay meaningful).
"""

FLOOR = 100

# Virtual "rating" assigned to each of the 16 bot difficulty levels, used
# only to compute the human player's Elo change when playing the bot --
# the bot itself doesn't have a persistent rating that moves.
BOT_LEVEL_ELO = {
    1: 100,   2: 250,   3: 400,   4: 550,
    5: 700,   6: 850,   7: 1000,  8: 1150,
    9: 1320,  10: 1500, 11: 1700, 12: 1900,
    13: 2150, 14: 2400, 15: 2700, 16: 3200,
}


def k_factor(rating: int, games_played: int) -> int:
    if games_played < 30:
        return 40
    if rating < 2400:
        return 20
    return 10


def expected_score(rating_a: int, rating_b: int) -> float:
    return 1 / (1 + 10 ** ((rating_b - rating_a) / 400))


def apply_result(rating_doc: dict, opponent_rating: int, score: float) -> dict:
    """score: 1.0 win, 0.5 draw, 0.0 loss. Mutates and returns rating_doc."""
    r = rating_doc["rating"]
    k = k_factor(r, rating_doc.get("games_played", 0))
    e = expected_score(r, opponent_rating)
    new_r = round(r + k * (score - e))
    new_r = max(FLOOR, new_r)

    rating_doc["rating"] = new_r
    rating_doc["peak_rating"] = max(rating_doc.get("peak_rating", new_r), new_r)
    rating_doc["games_played"] = rating_doc.get("games_played", 0) + 1
    if score == 1.0:
        rating_doc["wins"] = rating_doc.get("wins", 0) + 1
    elif score == 0.0:
        rating_doc["losses"] = rating_doc.get("losses", 0) + 1
    else:
        rating_doc["draws"] = rating_doc.get("draws", 0) + 1
    rating_doc["last_delta"] = new_r - r
    return rating_doc


def update_pair(white_doc: dict, black_doc: dict, result: str):
    """result: 'white', 'black', or 'draw'. Updates both docs in place."""
    if result == "white":
        sw, sb = 1.0, 0.0
    elif result == "black":
        sw, sb = 0.0, 1.0
    else:
        sw, sb = 0.5, 0.5
    r_white, r_black = white_doc["rating"], black_doc["rating"]
    apply_result(white_doc, r_black, sw)
    apply_result(black_doc, r_white, sb)
