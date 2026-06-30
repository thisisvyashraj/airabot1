"""
Bot opponent move selection -- 16 difficulty levels (1 = ~100 Elo beginner,
16 = maximum engine strength).

Two backends:
  1. Real Stockfish, if a binary is available (set STOCKFISH_PATH env var,
     or have `stockfish` on PATH / installed via an apt buildpack). This
     uses Stockfish's own UCI_LimitStrength + UCI_Elo options to target
     levels 1-15 accurately, and runs at full strength (no limit, decent
     depth/time) for level 16 -- genuinely超-human play.
  2. A pure-Python fallback (no external binary needed -- works out of the
     box on any host) using minimax + alpha-beta pruning over a
     piece-square-table evaluation, with the search depth, "blunder"
     probability and eval noise tuned per level so strength scales
     smoothly from a beginner who hangs pieces up to a near-optimal
     shallow-search engine. This is what runs by default.
"""
import os
import time
import random
import chess
import asyncio

STOCKFISH_PATH = os.environ.get("STOCKFISH_PATH", "")

# depth = hard search depth, time_budget = wall-clock cap in seconds
# (iterative deepening stops early and returns the best move found so far
# once the budget runs out, so level 16 never hangs the server).
LEVELS = {
    #      depth  blunder_chance  noise(centipawns)  time_budget
    1:  dict(depth=1, blunder=0.55, noise=400, time_budget=0.2),
    2:  dict(depth=1, blunder=0.45, noise=350, time_budget=0.2),
    3:  dict(depth=1, blunder=0.35, noise=300, time_budget=0.3),
    4:  dict(depth=2, blunder=0.28, noise=260, time_budget=0.3),
    5:  dict(depth=2, blunder=0.22, noise=220, time_budget=0.4),
    6:  dict(depth=2, blunder=0.16, noise=180, time_budget=0.5),
    7:  dict(depth=2, blunder=0.10, noise=140, time_budget=0.6),
    8:  dict(depth=3, blunder=0.07, noise=110, time_budget=0.8),
    9:  dict(depth=3, blunder=0.05, noise=85,  time_budget=1.0),
    10: dict(depth=3, blunder=0.03, noise=60,  time_budget=1.2),
    11: dict(depth=3, blunder=0.02, noise=40,  time_budget=1.5),
    12: dict(depth=4, blunder=0.01, noise=25,  time_budget=2.0),
    13: dict(depth=4, blunder=0.0,  noise=15,  time_budget=2.5),
    14: dict(depth=4, blunder=0.0,  noise=8,   time_budget=3.0),
    15: dict(depth=5, blunder=0.0,  noise=0,   time_budget=3.5),
    16: dict(depth=5, blunder=0.0,  noise=0,   time_budget=4.0),
}

# Maps level -> approx UCI_Elo for real Stockfish (used only if available)
STOCKFISH_ELO = {
    1: 1320, 2: 1350, 3: 1400, 4: 1450, 5: 1550, 6: 1650, 7: 1750, 8: 1850,
    9: 1950, 10: 2100, 11: 2250, 12: 2450, 13: 2650, 14: 2850, 15: 3000,
    16: None,  # None = full strength, no limit
}

PIECE_VALUES = {
    chess.PAWN: 100, chess.KNIGHT: 320, chess.BISHOP: 330,
    chess.ROOK: 500, chess.QUEEN: 900, chess.KING: 0,
}

# Simplified piece-square tables (white's perspective; mirrored for black)
PAWN_PST = [
    0, 0, 0, 0, 0, 0, 0, 0,
    50, 50, 50, 50, 50, 50, 50, 50,
    10, 10, 20, 30, 30, 20, 10, 10,
    5, 5, 10, 25, 25, 10, 5, 5,
    0, 0, 0, 20, 20, 0, 0, 0,
    5, -5, -10, 0, 0, -10, -5, 5,
    5, 10, 10, -20, -20, 10, 10, 5,
    0, 0, 0, 0, 0, 0, 0, 0,
]
KNIGHT_PST = [
    -50, -40, -30, -30, -30, -30, -40, -50,
    -40, -20, 0, 0, 0, 0, -20, -40,
    -30, 0, 10, 15, 15, 10, 0, -30,
    -30, 5, 15, 20, 20, 15, 5, -30,
    -30, 0, 15, 20, 20, 15, 0, -30,
    -30, 5, 10, 15, 15, 10, 5, -30,
    -40, -20, 0, 5, 5, 0, -20, -40,
    -50, -40, -30, -30, -30, -30, -40, -50,
]
BISHOP_PST = [
    -20, -10, -10, -10, -10, -10, -10, -20,
    -10, 0, 0, 0, 0, 0, 0, -10,
    -10, 0, 5, 10, 10, 5, 0, -10,
    -10, 5, 5, 10, 10, 5, 5, -10,
    -10, 0, 10, 10, 10, 10, 0, -10,
    -10, 10, 10, 10, 10, 10, 10, -10,
    -10, 5, 0, 0, 0, 0, 5, -10,
    -20, -10, -10, -10, -10, -10, -10, -20,
]
ROOK_PST = [
    0, 0, 0, 0, 0, 0, 0, 0,
    5, 10, 10, 10, 10, 10, 10, 5,
    -5, 0, 0, 0, 0, 0, 0, -5,
    -5, 0, 0, 0, 0, 0, 0, -5,
    -5, 0, 0, 0, 0, 0, 0, -5,
    -5, 0, 0, 0, 0, 0, 0, -5,
    -5, 0, 0, 0, 0, 0, 0, -5,
    0, 0, 0, 5, 5, 0, 0, 0,
]
QUEEN_PST = [
    -20, -10, -10, -5, -5, -10, -10, -20,
    -10, 0, 0, 0, 0, 0, 0, -10,
    -10, 0, 5, 5, 5, 5, 0, -10,
    -5, 0, 5, 5, 5, 5, 0, -5,
    0, 0, 5, 5, 5, 5, 0, -5,
    -10, 5, 5, 5, 5, 5, 0, -10,
    -10, 0, 5, 0, 0, 0, 0, -10,
    -20, -10, -10, -5, -5, -10, -10, -20,
]
KING_PST = [
    -30, -40, -40, -50, -50, -40, -40, -30,
    -30, -40, -40, -50, -50, -40, -40, -30,
    -30, -40, -40, -50, -50, -40, -40, -30,
    -30, -40, -40, -50, -50, -40, -40, -30,
    -20, -30, -30, -40, -40, -30, -30, -20,
    -10, -20, -20, -20, -20, -20, -20, -10,
    20, 20, 0, 0, 0, 0, 20, 20,
    20, 30, 10, 0, 0, 10, 30, 20,
]
PST = {
    chess.PAWN: PAWN_PST, chess.KNIGHT: KNIGHT_PST, chess.BISHOP: BISHOP_PST,
    chess.ROOK: ROOK_PST, chess.QUEEN: QUEEN_PST, chess.KING: KING_PST,
}


def _square_index(square: int, color: bool) -> int:
    return square if color == chess.WHITE else chess.square_mirror(square)


def evaluate(board: chess.Board) -> int:
    """Static evaluation in centipawns, positive = good for white."""
    if board.is_checkmate():
        return -99999 if board.turn == chess.WHITE else 99999
    if board.is_stalemate() or board.is_insufficient_material() or \
       board.can_claim_threefold_repetition() or board.can_claim_fifty_moves():
        return 0

    score = 0
    for square, piece in board.piece_map().items():
        value = PIECE_VALUES[piece.piece_type] + PST[piece.piece_type][_square_index(square, piece.color)]
        score += value if piece.color == chess.WHITE else -value

    # small mobility bonus
    score += 3 * (len(list(board.legal_moves)) if board.turn == chess.WHITE else -len(list(board.legal_moves)))
    return score


class _TimeUp(Exception):
    pass


def _alphabeta(board: chess.Board, depth: int, alpha: int, beta: int, maximizing: bool, deadline: float) -> int:
    if time.monotonic() > deadline:
        raise _TimeUp()
    if depth == 0 or board.is_game_over():
        return evaluate(board)
    if maximizing:
        value = -10**9
        for move in board.legal_moves:
            board.push(move)
            try:
                value = max(value, _alphabeta(board, depth - 1, alpha, beta, False, deadline))
            finally:
                board.pop()
            alpha = max(alpha, value)
            if alpha >= beta:
                break
        return value
    else:
        value = 10**9
        for move in board.legal_moves:
            board.push(move)
            try:
                value = min(value, _alphabeta(board, depth - 1, alpha, beta, True, deadline))
            finally:
                board.pop()
            beta = min(beta, value)
            if alpha >= beta:
                break
        return value


def _search_at_depth(board: chess.Board, depth: int, maximizing: bool, deadline: float):
    """One full iterative-deepening pass. Raises _TimeUp if it runs out of time
    partway through -- caller keeps the previous (shallower) result in that case."""
    scored = []
    for move in board.legal_moves:
        board.push(move)
        try:
            val = _alphabeta(board, depth - 1, -10**9, 10**9, not maximizing, deadline)
        finally:
            board.pop()
        scored.append((val, move))
    scored.sort(key=lambda x: x[0], reverse=maximizing)
    return scored


def _best_move_internal(board: chess.Board, level: int) -> chess.Move:
    cfg = LEVELS[level]
    legal = list(board.legal_moves)
    if not legal:
        return None

    # Random blunder chance simulates a weak/inattentive player.
    if random.random() < cfg["blunder"]:
        return random.choice(legal)

    maximizing = board.turn == chess.WHITE
    deadline = time.monotonic() + cfg["time_budget"]
    best_scored = None
    try:
        for d in range(1, cfg["depth"] + 1):
            best_scored = _search_at_depth(board, d, maximizing, deadline)
    except _TimeUp:
        pass
    if not best_scored:
        return random.choice(legal)

    # add noise so lower levels don't always pick the objectively best move
    noisy = [(val + random.randint(-cfg["noise"], cfg["noise"]), mv) for val, mv in best_scored]
    noisy.sort(key=lambda x: x[0], reverse=maximizing)
    return noisy[0][1]


def _best_move_stockfish(board: chess.Board, level: int) -> chess.Move:
    import chess.engine
    elo = STOCKFISH_ELO[level]
    with chess.engine.SimpleEngine.popen_uci(STOCKFISH_PATH) as sf:
        if elo is not None:
            sf.configure({"UCI_LimitStrength": True, "UCI_Elo": elo})
        else:
            sf.configure({"UCI_LimitStrength": False})
        limit = chess.engine.Limit(time=0.5 if elo and elo < 2000 else 1.5)
        result = sf.play(board, limit)
        return result.move


async def get_bot_move(board: chess.Board, level: int) -> chess.Move:
    level = max(1, min(16, int(level)))
    # Add delay logic
    if level <= 5: delay = random.uniform(2.0, 7.0)
    elif level <= 10: delay = random.uniform(1.5, 3.0)
    else: delay = random.uniform(0.1, 1.5)
    await asyncio.sleep(delay)
    
    if STOCKFISH_PATH:
        try: return _best_move_stockfish(board, level)
        except Exception: pass
    return _best_move_internal(board, level)
