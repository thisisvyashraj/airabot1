"""
chess_server/server.py
Backend for Aira Chess.

Responsibilities:
  - Full chess rules (castling, en passant, promotion, check/checkmate,
    stalemate, threefold repetition, 50-move rule, insufficient material) --
    all delegated to python-chess, which is what actually makes "every real
    chess mechanic" correct instead of hand-rolled and buggy.
  - Bot opponent moves (engine.py), 16 difficulty levels.
  - FIDE-style Elo ratings (rating.py).
  - A websocket relay so two real people can play live, either via a shared
    room code/link or random matchmaking.

Run with:  uvicorn server:app --host 0.0.0.0 --port 8000
(see chess_server/README.md for the full setup walkthrough)
"""
import os
import random
import string
import asyncio
from datetime import datetime, timezone

import chess
import pymongo
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from engine import get_bot_move, BOT_LEVELS
from rating import get_or_create_rating, apply_result, DEFAULT_RATING

# ── Mongo (reuses the same Aira database, separate collection) ─────────────
MONGO_URI = os.environ.get("MONGO_URI", "")
_mongo_client = pymongo.MongoClient(MONGO_URI) if MONGO_URI else pymongo.MongoClient()
db = _mongo_client["aira"]
chess_ratings = db["chess_ratings"]

app = FastAPI(title="Aira Chess Server")
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"],
)

STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/")
async def root():
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))


# ══════════════════════════════════════════════════════════════════════════
#  In-memory game state
# ══════════════════════════════════════════════════════════════════════════
class Game:
    def __init__(self, game_id: str, time_control: int):
        self.id = game_id
        self.board = chess.Board()
        self.white = None   # {"uid":int,"name":str,"type":"human"} or {"level":int,"type":"bot","name":str}
        self.black = None
        self.time_control = time_control      # seconds per side; 0 = unlimited
        self.clocks = {"white": time_control, "black": time_control}
        self.last_move_ts = None
        self.status = "waiting"                # waiting / active / finished
        self.result = None                      # "1-0" / "0-1" / "1/2-1/2"
        self.reason = None
        self.moves = []                          # SAN list
        self.sockets = set()
        self.draw_offered_by = None
        self.created_at = datetime.now(timezone.utc)


GAMES: dict[str, Game] = {}
ROOMS: dict[str, str] = {}          # room_code -> game_id
QUEUE: list[dict] = []               # players still waiting for random matchmaking
MATCHED: dict[int, str] = {}         # uid -> game_id, consumed once by /api/queue/status


def _gen_id(n: int = 14) -> str:
    return "".join(random.choices(string.ascii_lowercase + string.digits, k=n))


def _gen_room_code() -> str:
    return "".join(random.choices(string.ascii_uppercase + string.digits, k=6))


# ══════════════════════════════════════════════════════════════════════════
#  Move application / game-over detection / clocks
# ══════════════════════════════════════════════════════════════════════════
def _apply_move(g: Game, move: chess.Move):
    now = datetime.now(timezone.utc)
    if g.time_control > 0 and g.last_move_ts:
        elapsed = (now - g.last_move_ts).total_seconds()
        mover = "white" if g.board.turn == chess.WHITE else "black"
        g.clocks[mover] = max(0.0, g.clocks[mover] - elapsed)
    san = g.board.san(move)
    g.board.push(move)
    g.moves.append(san)
    g.last_move_ts = now
    g.draw_offered_by = None
    _check_game_over(g)


def _check_game_over(g: Game):
    b = g.board
    if b.is_checkmate():
        g.status, g.reason = "finished", "checkmate"
        g.result = "0-1" if b.turn == chess.WHITE else "1-0"
    elif b.is_stalemate():
        g.status, g.result, g.reason = "finished", "1/2-1/2", "stalemate"
    elif b.is_insufficient_material():
        g.status, g.result, g.reason = "finished", "1/2-1/2", "insufficient material"
    elif b.can_claim_threefold_repetition():
        g.status, g.result, g.reason = "finished", "1/2-1/2", "threefold repetition"
    elif b.can_claim_fifty_moves():
        g.status, g.result, g.reason = "finished", "1/2-1/2", "fifty-move rule"
    elif b.is_seventyfive_moves() or b.is_fivefold_repetition():
        g.status, g.result, g.reason = "finished", "1/2-1/2", "draw"


async def _clock_sweep_loop():
    while True:
        await asyncio.sleep(1)
        for g in list(GAMES.values()):
            if g.status == "active" and g.time_control > 0 and g.last_move_ts:
                mover = "white" if g.board.turn == chess.WHITE else "black"
                elapsed = (datetime.now(timezone.utc) - g.last_move_ts).total_seconds()
                remaining = g.clocks[mover] - elapsed
                if remaining <= 0:
                    g.status = "finished"
                    g.reason = "timeout"
                    g.result = "0-1" if mover == "white" else "1-0"
                    await _broadcast_state(g)
                    await _finalize_game(g)


@app.on_event("startup")
async def _on_startup():
    asyncio.create_task(_clock_sweep_loop())


# ══════════════════════════════════════════════════════════════════════════
#  Bot move trigger
# ══════════════════════════════════════════════════════════════════════════
async def _maybe_bot_move(game_id: str):
    g = GAMES.get(game_id)
    if not g or g.status != "active":
        return
    side = g.white if g.board.turn == chess.WHITE else g.black
    if not side or side.get("type") != "bot":
        return
    await asyncio.sleep(random.uniform(0.4, 1.1))  # feels more natural than an instant move
    move = await get_bot_move(g.board, side["level"])
    if move is None:
        return
    _apply_move(g, move)
    await _broadcast_state(g)
    if g.status == "finished":
        await _finalize_game(g)


# ══════════════════════════════════════════════════════════════════════════
#  Rating finalization
# ══════════════════════════════════════════════════════════════════════════
async def _finalize_game(g: Game):
    if g.result == "1-0":
        w_score, b_score = 1.0, 0.0
    elif g.result == "0-1":
        w_score, b_score = 0.0, 1.0
    else:
        w_score, b_score = 0.5, 0.5

    white_human = g.white if g.white and g.white.get("type") == "human" else None
    black_human = g.black if g.black and g.black.get("type") == "human" else None

    if white_human and black_human:
        wr = get_or_create_rating(chess_ratings, white_human["uid"], white_human["name"])
        br = get_or_create_rating(chess_ratings, black_human["uid"], black_human["name"])
        apply_result(chess_ratings, white_human["uid"], wr["rating"], br["rating"], w_score)
        apply_result(chess_ratings, black_human["uid"], br["rating"], wr["rating"], b_score)
    elif white_human and g.black and g.black.get("type") == "bot":
        bot_rating = BOT_LEVELS.get(g.black["level"], BOT_LEVELS[1])["rating"]
        wr = get_or_create_rating(chess_ratings, white_human["uid"], white_human["name"])
        apply_result(chess_ratings, white_human["uid"], wr["rating"], bot_rating, w_score)
    elif black_human and g.white and g.white.get("type") == "bot":
        bot_rating = BOT_LEVELS.get(g.white["level"], BOT_LEVELS[1])["rating"]
        br = get_or_create_rating(chess_ratings, black_human["uid"], black_human["name"])
        apply_result(chess_ratings, black_human["uid"], br["rating"], bot_rating, b_score)


# ══════════════════════════════════════════════════════════════════════════
#  WebSocket state payload / broadcast
# ══════════════════════════════════════════════════════════════════════════
def _state_payload(g: Game) -> dict:
    mover = "white" if g.board.turn == chess.WHITE else "black"
    live_clocks = dict(g.clocks)
    if g.status == "active" and g.time_control > 0 and g.last_move_ts:
        elapsed = (datetime.now(timezone.utc) - g.last_move_ts).total_seconds()
        live_clocks[mover] = max(0.0, g.clocks[mover] - elapsed)
    return {
        "type": "state",
        "game_id": g.id,
        "fen": g.board.fen(),
        "turn": mover,
        "moves": g.moves,
        "white": g.white,
        "black": g.black,
        "time_control": g.time_control,
        "clocks": live_clocks,
        "status": g.status,
        "result": g.result,
        "reason": g.reason,
        "draw_offered_by": g.draw_offered_by,
        "in_check": g.board.is_check(),
    }


async def _broadcast_state(g: Game):
    payload = _state_payload(g)
    dead = []
    for ws in g.sockets:
        try:
            await ws.send_json(payload)
        except Exception:
            dead.append(ws)
    for d in dead:
        g.sockets.discard(d)


# ══════════════════════════════════════════════════════════════════════════
#  REST: create / join games
# ══════════════════════════════════════════════════════════════════════════
class VsBotReq(BaseModel):
    uid: int
    name: str
    color: str           # white / black / random
    time_control: int
    level: int


@app.post("/api/game/vsbot")
async def create_vsbot(req: VsBotReq):
    level = max(1, min(req.level, 16))
    color = req.color if req.color in ("white", "black") else random.choice(["white", "black"])
    game_id = _gen_id()
    g = Game(game_id, max(0, req.time_control))
    human = {"uid": req.uid, "name": req.name, "type": "human"}
    bot = {"level": level, "type": "bot", "name": f"Aira Bot · Lv{level} (~{BOT_LEVELS[level]['rating']})"}
    if color == "white":
        g.white, g.black = human, bot
    else:
        g.white, g.black = bot, human
    g.status = "active"
    g.last_move_ts = datetime.now(timezone.utc)
    GAMES[game_id] = g
    if g.white.get("type") == "bot":
        asyncio.create_task(_maybe_bot_move(game_id))
    return {"game_id": game_id}


class RoomCreateReq(BaseModel):
    uid: int
    name: str
    color: str
    time_control: int


@app.post("/api/room/create")
async def room_create(req: RoomCreateReq):
    color = req.color if req.color in ("white", "black") else random.choice(["white", "black"])
    game_id = _gen_id()
    room_code = _gen_room_code()
    g = Game(game_id, max(0, req.time_control))
    human = {"uid": req.uid, "name": req.name, "type": "human"}
    if color == "white":
        g.white = human
    else:
        g.black = human
    g.status = "waiting"
    GAMES[game_id] = g
    ROOMS[room_code] = game_id
    return {"game_id": game_id, "room_code": room_code}


class RoomJoinReq(BaseModel):
    room_code: str
    uid: int
    name: str


@app.post("/api/room/join")
async def room_join(req: RoomJoinReq):
    game_id = ROOMS.get(req.room_code.upper())
    if not game_id or game_id not in GAMES:
        raise HTTPException(404, "Room not found or expired")
    g = GAMES[game_id]
    if g.white and g.white.get("uid") == req.uid:
        return {"game_id": game_id}
    if g.black and g.black.get("uid") == req.uid:
        return {"game_id": game_id}
    if g.status != "waiting":
        raise HTTPException(400, "Room already full / game already started")
    human = {"uid": req.uid, "name": req.name, "type": "human"}
    if g.white is None:
        g.white = human
    elif g.black is None:
        g.black = human
    else:
        raise HTTPException(400, "Room full")
    g.status = "active"
    g.last_move_ts = datetime.now(timezone.utc)
    return {"game_id": game_id}


class QueueJoinReq(BaseModel):
    uid: int
    name: str
    color: str
    time_control: int


@app.post("/api/queue/join")
async def queue_join(req: QueueJoinReq):
    if req.uid in MATCHED:
        return {"game_id": MATCHED.pop(req.uid)}
    for w in QUEUE:
        if w["uid"] == req.uid:
            return {"queued": True}
    for idx, waiting in enumerate(QUEUE):
        if waiting["time_control"] != req.time_control:
            continue
        QUEUE.pop(idx)
        if req.color in ("white", "black"):
            a_color = req.color
        elif waiting["color"] in ("white", "black"):
            a_color = "white" if waiting["color"] == "black" else "black"
        else:
            a_color = random.choice(["white", "black"])
        game_id = _gen_id()
        g = Game(game_id, max(0, req.time_control))
        human_a = {"uid": req.uid, "name": req.name, "type": "human"}
        human_b = {"uid": waiting["uid"], "name": waiting["name"], "type": "human"}
        if a_color == "white":
            g.white, g.black = human_a, human_b
        else:
            g.white, g.black = human_b, human_a
        g.status = "active"
        g.last_move_ts = datetime.now(timezone.utc)
        GAMES[game_id] = g
        MATCHED[waiting["uid"]] = game_id
        return {"game_id": game_id}
    QUEUE.append({"uid": req.uid, "name": req.name, "color": req.color, "time_control": req.time_control})
    return {"queued": True}


@app.get("/api/queue/status/{uid}")
async def queue_status(uid: int):
    if uid in MATCHED:
        return {"matched": True, "game_id": MATCHED.pop(uid)}
    return {"matched": False}


@app.post("/api/queue/cancel")
async def queue_cancel(uid: int = Query(...)):
    global QUEUE
    QUEUE = [w for w in QUEUE if w["uid"] != uid]
    return {"ok": True}


@app.get("/api/game/{game_id}")
async def api_game_state(game_id: str):
    g = GAMES.get(game_id)
    if not g:
        raise HTTPException(404, "Game not found")
    return _state_payload(g)


# ══════════════════════════════════════════════════════════════════════════
#  REST: ratings / leaderboard
# ══════════════════════════════════════════════════════════════════════════
@app.get("/api/rating/{uid}")
async def api_rating(uid: int):
    doc = get_or_create_rating(chess_ratings, uid)
    return {
        "rating": doc.get("rating", DEFAULT_RATING),
        "peak_rating": doc.get("peak_rating", DEFAULT_RATING),
        "wins": doc.get("wins", 0),
        "losses": doc.get("losses", 0),
        "draws": doc.get("draws", 0),
    }


@app.get("/api/leaderboard")
async def api_leaderboard():
    rows = list(chess_ratings.find().sort("rating", -1).limit(50))
    return {"leaderboard": [
        {
            "name": r.get("name", "?"), "rating": r.get("rating", DEFAULT_RATING),
            "wins": r.get("wins", 0), "losses": r.get("losses", 0), "draws": r.get("draws", 0),
        }
        for r in rows
    ]}


@app.get("/api/health")
async def health():
    return {"ok": True, "active_games": len(GAMES), "queue": len(QUEUE)}


# ══════════════════════════════════════════════════════════════════════════
#  WebSocket: live game relay
# ══════════════════════════════════════════════════════════════════════════
@app.websocket("/ws/{game_id}")
async def ws_game(websocket: WebSocket, game_id: str):
    await websocket.accept()
    g = GAMES.get(game_id)
    if not g:
        await websocket.send_json({"type": "error", "message": "Game not found or expired"})
        await websocket.close()
        return
    g.sockets.add(websocket)
    try:
        await websocket.send_json(_state_payload(g))
        while True:
            msg = await websocket.receive_json()
            await _handle_ws_message(g, websocket, msg)
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        g.sockets.discard(websocket)


async def _handle_ws_message(g: Game, ws: WebSocket, msg: dict):
    mtype = msg.get("type")
    uid = msg.get("uid")

    if mtype == "ping":
        await ws.send_json(_state_payload(g))
        return

    if mtype == "move":
        if g.status != "active":
            await ws.send_json({"type": "error", "message": "Game is not active"}); return
        mover_color = chess.WHITE if g.board.turn == chess.WHITE else chess.BLACK
        side = g.white if mover_color == chess.WHITE else g.black
        if not side or side.get("type") != "human" or side.get("uid") != uid:
            await ws.send_json({"type": "error", "message": "Not your turn"}); return
        try:
            move = chess.Move.from_uci(msg["uci"])
        except Exception:
            await ws.send_json({"type": "error", "message": "Malformed move"}); return
        if move not in g.board.legal_moves:
            await ws.send_json({"type": "error", "message": "Illegal move"}); return
        _apply_move(g, move)
        await _broadcast_state(g)
        if g.status == "finished":
            await _finalize_game(g)
        else:
            asyncio.create_task(_maybe_bot_move(g.id))

    elif mtype == "resign":
        if g.status != "active":
            return
        if g.white and g.white.get("uid") == uid:
            side_color = "white"
        elif g.black and g.black.get("uid") == uid:
            side_color = "black"
        else:
            return
        g.status, g.reason = "finished", "resignation"
        g.result = "0-1" if side_color == "white" else "1-0"
        await _broadcast_state(g)
        await _finalize_game(g)

    elif mtype == "draw_offer":
        g.draw_offered_by = uid
        await _broadcast_state(g)

    elif mtype == "draw_accept":
        if g.draw_offered_by and g.draw_offered_by != uid and g.status == "active":
            g.status, g.result, g.reason = "finished", "1/2-1/2", "agreement"
            await _broadcast_state(g)
            await _finalize_game(g)

    elif mtype == "draw_decline":
        g.draw_offered_by = None
        await _broadcast_state(g)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="0.0.0.0", port=int(os.environ.get("PORT", 8000)), reload=False)
