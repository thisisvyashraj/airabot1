"""
chess_server/engine.py
Bot opponent move generation for 16 difficulty levels.

If STOCKFISH_PATH points to a real Stockfish binary, that's used for actual
strong play (recommended for levels 10+). If it's not set/found, this falls
back to a small built-in alpha-beta search so the bot still works out of the
box -- just not at grandmaster strength on the hardest levels.

Honest note: no engine -- including real Stockfish -- is actually rated
"5000". The strongest engines today land around ~3600-3700 on computer
rating lists. Level 16 here is tuned to be "as strong as this service can
make it" (full-depth Stockfish if you have it installed), and its rating
label below is what's used for the Elo math, not a literal claim.
"""
import os
import random
import asyncio
import chess

try:
    import chess.engine
    HAS_CHESS_ENGINE = True
except ImportError:
    HAS_CHESS_ENGINE = False

STOCKFISH_PATH = os.environ.get("STOCKFISH_PATH", "")

# level -> (approx rating used for Elo math, search depth, stockfish "Skill
# Level" 0-20, chance per move the bot plays a deliberately weaker move)
BOT_LEVELS = {
    1:  {"rating": 150,  "depth": 1, "skill": 0,  "blunder": 0.40},
    2:  {"rating": 350,  "depth": 1, "skill": 2,  "blunder": 0.32},
    3:  {"rating": 550,  "depth": 2, "skill": 4,  "blunder": 0.25},
    4:  {"rating": 750,  "depth": 2, "skill": 6,  "blunder": 0.20},
    5:  {"rating": 950,  "depth": 2, "skill": 8,  "blunder": 0.15},
    6:  {"rating": 1150, "depth": 3, "skill": 9,  "blunder": 0.11},
    7:  {"rating": 1350, "depth": 3, "skill": 10, "blunder": 0.08},
    8:  {"rating": 1550, "depth": 3, "skill": 11, "blunder": 0.06},
    9:  {"rating": 1750, "depth": 4, "skill": 12, "blunder": 0.045},
    10: {"rating": 1950, "depth": 4, "skill": 14, "blunder": 0.03},
    11: {"rating": 2150, "depth": 4, "skill": 15, "blunder": 0.02},
    12: {"rating": 2350, "depth": 4, "skill": 17, "blunder": 0.012},
    13: {"rating": 2550, "depth": 4, "skill": 18, "blunder": 0.006},
    14: {"rating": 2750, "depth": 4, "skill": 19, "blunder": 0.0},
    15: {"rating": 3000, "depth": 4, "skill": 20, "blunder": 0.0},
    16: {"rating": 3300, "depth": 4, "skill": 20, "blunder": 0.0},
}
# NOTE on depth: these depths are deliberately conservative for the pure
# python fallback engine below -- a naive alpha-beta search in Python gets
# very slow much past depth 4. When STOCKFISH_PATH is configured, Stockfish
# is given a time budget instead (scaled by level) and easily outplays this
# fallback at every level, especially 10+.

PIECE_VALUES = {
    chess.PAWN: 100, chess.KNIGHT: 320, chess.BISHOP: 330,
    chess.ROOK: 500, chess.QUEEN: 900, chess.KING: 0,
}

CENTER_SQUARES = [chess.D4, chess.D5, chess.E4, chess.E5]

_engine_lock = asyncio.Lock()
_engine = None
_engine_unavailable = False


async def _get_stockfish():
    """Lazily start a single shared Stockfish process, if configured."""
    global _engine, _engine_unavailable
    if _engine_unavailable or not STOCKFISH_PATH or not HAS_CHESS_ENGINE:
        return None
    if _engine is not None:
        return _engine
    async with _engine_lock:
        if _engine is not None:
            return _engine
        if not os.path.exists(STOCKFISH_PATH):
            _engine_unavailable = True
            return None
        try:
            _transport, _engine = await chess.engine.popen_uci(STOCKFISH_PATH)
            return _engine
        except Exception:
            _engine_unavailable = True
            return None


def _evaluate(board: chess.Board) -> int:
    """Simple material + mobility + center-control eval, from White's POV."""
    if board.is_checkmate():
        # side to move is checkmated -> bad for side to move
        return -99999 if board.turn == chess.WHITE else 99999
    if board.is_stalemate() or board.is_insufficient_material():
        return 0

    score = 0
    for piece_type, value in PIECE_VALUES.items():
        score += len(board.pieces(piece_type, chess.WHITE)) * value
        score -= len(board.pieces(piece_type, chess.BLACK)) * value

    for sq in CENTER_SQUARES:
        piece = board.piece_at(sq)
        if piece:
            score += 10 if piece.color == chess.WHITE else -10

    # mobility (small weight, mainly a tie-breaker)
    mobility = len(list(board.legal_moves))
    score += mobility if board.turn == chess.WHITE else -mobility

    return score


def _order_moves(board: chess.Board, moves):
    # captures and checks first -> much better alpha-beta pruning
    def key(m):
        score = 0
        if board.is_capture(m):
            score += 10
        if board.gives_check(m):
            score += 5
        return score
    return sorted(moves, key=key, reverse=True)


def _alphabeta(board: chess.Board, depth: int, alpha: float, beta: float, maximizing: bool) -> float:
    if depth == 0 or board.is_game_over():
        return _evaluate(board)
    moves = _order_moves(board, list(board.legal_moves))
    if maximizing:
        value = float("-inf")
        for m in moves:
            board.push(m)
            value = max(value, _alphabeta(board, depth - 1, alpha, beta, False))
            board.pop()
            alpha = max(alpha, value)
            if alpha >= beta:
                break
        return value
    else:
        value = float("inf")
        for m in moves:
            board.push(m)
            value = min(value, _alphabeta(board, depth - 1, alpha, beta, True))
            board.pop()
            beta = min(beta, value)
            if beta <= alpha:
                break
        return value


def _internal_best_move(board: chess.Board, cfg: dict):
    moves = list(board.legal_moves)
    if not moves:
        return None
    maximizing = board.turn == chess.WHITE
    depth = max(1, min(cfg["depth"], 4))  # hard safety cap, see note above

    scored = []
    for m in moves:
        board.push(m)
        val = _alphabeta(board, depth - 1, float("-inf"), float("inf"), not maximizing)
        board.pop()
        scored.append((val, m))
    scored.sort(key=lambda x: x[0], reverse=maximizing)

    blunder = cfg.get("blunder", 0)
    if blunder > 0 and random.random() < blunder:
        if blunder > 0.25 or len(scored) <= 2:
            return random.choice(moves)
        pool = scored[1:min(4, len(scored))]
        return random.choice(pool)[1]
    return scored[0][1]


async def get_bot_move(board: chess.Board, level: int) -> "chess.Move | None":
    """Return the bot's chosen move for the given board/level."""
    cfg = BOT_LEVELS.get(level, BOT_LEVELS[1])
    if board.is_game_over():
        return None

    engine = await _get_stockfish()
    if engine is not None:
        try:
            await engine.configure({"Skill Level": cfg["skill"]})
            think_time = 0.15 + cfg["skill"] * 0.05
            limit = chess.engine.Limit(time=think_time)
            result = await engine.play(board, limit)
            if result.move:
                return result.move
        except Exception:
            pass  # fall through to internal engine

    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _internal_best_move, board, cfg)
