"""
Professional Elo System with Acceleration.
Uses an aggressive K-factor for new players to find their true rating
quickly, then stabilizes.
"""

FLOOR = 100
PLACEMENT_GAMES = 5  # Rating is "Provisional" until 5 games

BOT_LEVEL_ELO = {
    1: 200,   2: 400,   3: 600,   4: 800,
    5: 1000,  6: 1200,  7: 1400,  8: 1550,
    9: 1700,  10: 1850, 11: 2000, 12: 2150,
    13: 2300, 14: 2500, 15: 2700, 16: 3000,
}

def k_factor(rating: int, games_played: int) -> int:
    """Dynamic K-factor: Higher for new players, lower for veterans."""
    if games_played < PLACEMENT_GAMES:
        return 80   # Accelerated placement (Very fast movement)
    if games_played < 20:
        return 40   # Provisional (Moderate adjustment)
    if rating < 2000:
        return 20   # Standard
    return 10       # Expert stabilization

def expected_score(rating_a: int, rating_b: int) -> float:
    return 1 / (1 + 10 ** ((rating_b - rating_a) / 400))

def apply_result(rating_doc: dict, opponent_rating: int, score: float) -> dict:
    r = rating_doc["rating"]
    games = rating_doc.get("games_played", 0)
    
    # Calculate Rating change
    k = k_factor(r, games)
    e = expected_score(r, opponent_rating)
    delta = round(k * (score - e))
    
    # Finalize rating
    new_r = max(FLOOR, r + delta)
    
    # Update Document
    rating_doc["rating"] = new_r
    rating_doc["peak_rating"] = max(rating_doc.get("peak_rating", new_r), new_r)
    rating_doc["games_played"] = games + 1
    
    # Track stats
    if score == 1.0: rating_doc["wins"] = rating_doc.get("wins", 0) + 1
    elif score == 0.0: rating_doc["losses"] = rating_doc.get("losses", 0) + 1
    else: rating_doc["draws"] = rating_doc.get("draws", 0) + 1
    
    rating_doc["last_delta"] = delta
    rating_doc["provisional"] = games + 1 < PLACEMENT_GAMES
    
    return rating_doc

def update_pair(white_doc: dict, black_doc: dict, result: str):
    # Determine scores
    if result == "white": sw, sb = 1.0, 0.0
    elif result == "black": sw, sb = 0.0, 1.0
    else: sw, sb = 0.5, 0.5
    
    # Apply Elo change
    apply_result(white_doc, black_doc["rating"], sw)
    apply_result(black_doc, white_doc["rating"], sb)
