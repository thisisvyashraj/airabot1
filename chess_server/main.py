"""
Aira Chess Service
═══════════════════
Standalone FastAPI service providing: full chess rules (via python-chess),
vs-bot games (16 difficulty levels), real 2-player multiplayer (room code
or random matchmaking), live sync over WebSocket, FIDE-style Elo ratings,
and a leaderboard. Also serves the web board UI used inside Telegram's
WebApp button.

Run locally:   uvicorn main:app --reload --port 8000
Run in prod:   uvicorn main:app --host 0.0.0.0 --port $PORT   (see Procfile)
"""
import time
import random
import asyncio
from typing import Optional

import chess
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel

import db
import engine
import rating

app = FastAPI(title="Aira Chess Service")

# in-memory matchmaking queue + websocket registry (per-process; fine for a
# single web dyno, which is the normal setup for this bot)
_queue: list[dict] = []
_sockets: dict[str, list[WebSocket]] = {}


# ── Models ───────────────────────────────────────────────────────────────
class VsBotReq(BaseModel):
    uid: int; name: str; color: str = "random"; time_control: int = 0; level: int = 1

class RoomCreateReq(BaseModel):
    uid: int; name: str; color: str = "random"; time_control: int = 0

class RoomJoinReq(BaseModel):
    room_code: str; uid: int; name: str

class QueueJoinReq(BaseModel):
    uid: int; name: str; color: str = "random"; time_control: int = 0

class MoveReq(BaseModel):
    uid: int; uci: str; promotion: Optional[str] = None

class UidReq(BaseModel):
    uid: int


# ── Helpers ──────────────────────────────────────────────────────────────
def _new_game(white_uid, white_name, black_uid, black_name, time_control, mode="pvp", bot_level=None):
    game = {
        "game_id": db.new_game_id(),
        "mode": mode,
        "white_uid": white_uid, "white_name": white_name,
        "black_uid": black_uid, "black_name": black_name,
        "fen": chess.STARTING_FEN,
        "moves": [],  # list of uci strings, for move history / replay
        "time_control": time_control,
        "white_clock": time_control or None,
        "black_clock": time_control or None,
        "last_move_at": time.time(),
        "status": "active",
        "result": None,            # "white" | "black" | "draw"
        "result_reason": None,
        "bot_level": bot_level,
        "draw_offered_by": None,
        "created_at": time.time(),
    }
    db.save_game(game)
    return game


def _public_state(game: dict) -> dict:
    board = chess.Board(game["fen"])
    white_clock, black_clock = _live_clocks(game)
    return {
        "game_id": game["game_id"], "mode": game["mode"],
        "fen": game["fen"], "turn": "white" if board.turn == chess.WHITE else "black",
        "white_name": game["white_name"], "black_name": game["black_name"],
        "white_uid": game["white_uid"], "black_uid": game["black_uid"],
        "time_control": game["time_control"],
        "white_clock": white_clock, "black_clock": black_clock,
        "status": game["status"], "result": game["result"], "result_reason": game["result_reason"],
        "in_check": board.is_check(), "bot_level": game.get("bot_level"),
        "draw_offered_by": game.get("draw_offered_by"),
        "moves": game["moves"],
        "legal_moves": [m.uci() for m in board.legal_moves] if game["status"] == "active" else [],
    }


def _live_clocks(game: dict):
    """Clocks aren't ticked server-side every second -- we compute remaining
    time lazily from last_move_at, so no background scheduler is needed."""
    if not game["time_control"]:
        return None, None
    board = chess.Board(game["fen"])
    elapsed = time.time() - game["last_move_at"] if game["status"] == "active" else 0
    wc, bc = game["white_clock"], game["black_clock"]
    if game["status"] == "active":
        if board.turn == chess.WHITE:
            wc = max(0, wc - elapsed)
        else:
            bc = max(0, bc - elapsed)
    return round(wc, 1), round(bc, 1)


def _check_timeout(game: dict) -> bool:
    """Returns True if a flag fell and the game was just ended."""
    if not game["time_control"] or game["status"] != "active":
        return False
    wc, bc = _live_clocks(game)
    if wc <= 0:
        _finish_game(game, "black", "timeout")
        return True
    if bc <= 0:
        _finish_game(game, "white", "timeout")
        return True
    return False


def _finish_game(game: dict, result: str, reason: str):
    game["status"] = "finished"
    game["result"] = result
    game["result_reason"] = reason
    _apply_rating(game)
    db.save_game(game)


def _apply_rating(game: dict):
    """Updates Elo for both real human players. For vs-bot games only the
    human's rating moves (the bot uses a fixed virtual rating per level)."""
    if game["mode"] == "bot":
        human_uid = game["white_uid"] if game["white_uid"] else game["black_uid"]
        human_color = "white" if game["white_uid"] else "black"
        human_doc = db.get_rating_doc(human_uid, game["white_name"] if human_color == "white" else game["black_name"])
        bot_elo = rating.BOT_LEVEL_ELO.get(game.get("bot_level", 1), 1200)
        if game["result"] == "draw":
            score = 0.5
        elif game["result"] == human_color:
            score = 1.0
        else:
            score = 0.0
        rating.apply_result(human_doc, bot_elo, score)
        db.save_rating_doc(human_doc)
    else:
        white_doc = db.get_rating_doc(game["white_uid"], game["white_name"])
        black_doc = db.get_rating_doc(game["black_uid"], game["black_name"])
        rating.update_pair(white_doc, black_doc, game["result"])
        db.save_rating_doc(white_doc)
        db.save_rating_doc(black_doc)


async def _broadcast(game_id: str, payload: dict):
    for ws in list(_sockets.get(game_id, [])):
        try:
            await ws.send_json(payload)
        except Exception:
            pass


def _game_over_result(board: chess.Board):
    if board.is_checkmate():
        return ("black" if board.turn == chess.WHITE else "white"), "checkmate"
    if board.is_stalemate():
        return "draw", "stalemate"
    if board.is_insufficient_material():
        return "draw", "insufficient material"
    if board.can_claim_threefold_repetition():
        return "draw", "threefold repetition"
    if board.can_claim_fifty_moves():
        return "draw", "50-move rule"
    return None, None


# ── REST: game creation (these 4 are what aira_bot.py already calls) ─────
@app.post("/api/game/vsbot")
async def create_vs_bot(req: VsBotReq):
    color = req.color
    if color == "random":
        color = random.choice(["white", "black"])
    if color == "white":
        game = _new_game(req.uid, req.name, None, "Aira Bot", req.time_control, mode="bot", bot_level=req.level)
    else:
        game = _new_game(None, "Aira Bot", req.uid, req.name, req.time_control, mode="bot", bot_level=req.level)
        # bot plays white and moves first
        board = chess.Board()
        mv = engine.get_bot_move(board, req.level)
        board.push(mv)
        game["fen"] = board.fen()
        game["moves"].append(mv.uci())
        game["last_move_at"] = time.time()
        db.save_game(game)
    return {"game_id": game["game_id"]}


@app.post("/api/room/create")
async def room_create(req: RoomCreateReq):
    room_code = db.new_room_code()
    color = req.color
    if color == "random":
        color = random.choice(["white", "black"])
    if color == "white":
        game = _new_game(req.uid, req.name, None, None, req.time_control, mode="pvp")
    else:
        game = _new_game(None, None, req.uid, req.name, req.time_control, mode="pvp")
    game["status"] = "waiting"
    db.save_game(game)
    db.save_room({"room_code": room_code, "game_id": game["game_id"], "creator_uid": req.uid, "status": "waiting"})
    return {"game_id": game["game_id"], "room_code": room_code}


@app.post("/api/room/join")
async def room_join(req: RoomJoinReq):
    room = db.load_room(req.room_code.upper())
    if not room:
        raise HTTPException(404, "Room not found")
    game = db.load_game(room["game_id"])
    if not game or game["status"] != "waiting":
        raise HTTPException(400, "Room is no longer joinable")
    if game["white_uid"] is None:
        game["white_uid"], game["white_name"] = req.uid, req.name
    else:
        game["black_uid"], game["black_name"] = req.uid, req.name
    game["status"] = "active"
    game["last_move_at"] = time.time()
    db.save_game(game)
    room["status"] = "matched"
    db.save_room(room)
    return {"game_id": game["game_id"]}


@app.post("/api/queue/join")
async def queue_join(req: QueueJoinReq):
    # try to find a waiting opponent with the same time control
    for i, entry in enumerate(_queue):
        if entry["time_control"] == req.time_control and entry["uid"] != req.uid:
            _queue.pop(i)
            colors = ["white", "black"]
            random.shuffle(colors)
            p1_color, p2_color = colors
            if p1_color == "white":
                game = _new_game(entry["uid"], entry["name"], req.uid, req.name, req.time_control)
            else:
                game = _new_game(req.uid, req.name, entry["uid"], entry["name"], req.time_control)
            entry["matched_game_id"] = game["game_id"]
            return {"queued": False, "game_id": game["game_id"]}
    _queue.append({"uid": req.uid, "name": req.name, "color": req.color,
                    "time_control": req.time_control, "matched_game_id": None, "joined_at": time.time()})
    return {"queued": True}


@app.get("/api/queue/status/{uid}")
async def queue_status(uid: int):
    for entry in _queue:
        if entry["uid"] == uid and entry.get("matched_game_id"):
            return {"matched": True, "game_id": entry["matched_game_id"]}
    return {"matched": False}


# ── REST: ratings / leaderboard (also already called by aira_bot.py) ─────
@app.get("/api/rating/{uid}")
async def get_rating(uid: int):
    doc = db.get_rating_doc(uid)
    return {k: doc.get(k) for k in ("rating", "peak_rating", "wins", "losses", "draws", "games_played")}


@app.get("/api/leaderboard")
async def leaderboard():
    rows = db.get_leaderboard(10)
    return {"leaderboard": [
        {"name": r.get("name"), "rating": r.get("rating"), "wins": r.get("wins", 0),
         "losses": r.get("losses", 0), "draws": r.get("draws", 0)} for r in rows
    ]}


# ── REST: in-game actions (used by the webapp board UI) ───────────────────
@app.get("/api/game/{game_id}/state")
async def game_state(game_id: str):
    game = db.load_game(game_id)
    if not game:
        raise HTTPException(404, "Game not found")
    _check_timeout(game)
    return _public_state(game)


@app.post("/api/game/{game_id}/move")
async def game_move(game_id: str, req: MoveReq):
    game = db.load_game(game_id)
    if not game:
        raise HTTPException(404, "Game not found")
    if game["status"] != "active":
        raise HTTPException(400, "Game is not active")
    if _check_timeout(game):
        await _broadcast(game_id, {"type": "state", "state": _public_state(game)})
        raise HTTPException(400, "Time's up")

    board = chess.Board(game["fen"])
    is_white_turn = board.turn == chess.WHITE
    mover_uid = game["white_uid"] if is_white_turn else game["black_uid"]
    if req.uid != mover_uid:
        raise HTTPException(403, "Not your move")

    try:
        move = chess.Move.from_uci(req.uci + (req.promotion or ""))
    except Exception:
        raise HTTPException(400, "Bad move format")
    if move not in board.legal_moves:
        raise HTTPException(400, "Illegal move")

    # update clock for the player who just moved
    if game["time_control"]:
        elapsed = time.time() - game["last_move_at"]
        if is_white_turn:
            game["white_clock"] = max(0, game["white_clock"] - elapsed)
        else:
            game["black_clock"] = max(0, game["black_clock"] - elapsed)

    board.push(move)
    game["fen"] = board.fen()
    game["moves"].append(move.uci())
    game["last_move_at"] = time.time()
    game["draw_offered_by"] = None

    result, reason = _game_over_result(board)
    if result:
        _finish_game(game, result, reason)
    else:
        db.save_game(game)

        if game["mode"] == "bot" and game["status"] == "active":
            bot_move = engine.get_bot_move(board, game["bot_level"])
            if bot_move:
                board.push(bot_move)
                game["fen"] = board.fen()
                game["moves"].append(bot_move.uci())
                game["last_move_at"] = time.time()
                result, reason = _game_over_result(board)
                if result:
                    _finish_game(game, result, reason)
                else:
                    db.save_game(game)

    state = _public_state(game)
    await _broadcast(game_id, {"type": "state", "state": state})
    return state


@app.post("/api/game/{game_id}/resign")
async def game_resign(game_id: str, req: UidReq):
    game = db.load_game(game_id)
    if not game or game["status"] != "active":
        raise HTTPException(400, "Game not active")
    winner = "black" if req.uid == game["white_uid"] else "white"
    _finish_game(game, winner, "resignation")
    state = _public_state(game)
    await _broadcast(game_id, {"type": "state", "state": state})
    return state


@app.post("/api/game/{game_id}/draw/offer")
async def draw_offer(game_id: str, req: UidReq):
    game = db.load_game(game_id)
    if not game or game["status"] != "active":
        raise HTTPException(400, "Game not active")
    game["draw_offered_by"] = req.uid
    db.save_game(game)
    await _broadcast(game_id, {"type": "draw_offered", "uid": req.uid})
    return {"ok": True}


@app.post("/api/game/{game_id}/draw/respond")
async def draw_respond(game_id: str, req: UidReq, accept: bool = False):
    game = db.load_game(game_id)
    if not game or game["status"] != "active":
        raise HTTPException(400, "Game not active")
    if accept:
        _finish_game(game, "draw", "agreement")
    else:
        game["draw_offered_by"] = None
        db.save_game(game)
    state = _public_state(game)
    await _broadcast(game_id, {"type": "state", "state": state})
    return state


# ── WebSocket: push state updates to both players live ────────────────────
@app.websocket("/ws/{game_id}")
async def ws_endpoint(websocket: WebSocket, game_id: str):
    await websocket.accept()
    _sockets.setdefault(game_id, []).append(websocket)
    try:
        game = db.load_game(game_id)
        if game:
            await websocket.send_json({"type": "state", "state": _public_state(game)})
        while True:
            await websocket.receive_text()  # client only needs to receive; ignore pings
    except WebSocketDisconnect:
        pass
    finally:
        _sockets[game_id] = [s for s in _sockets.get(game_id, []) if s is not websocket]


# ── Static webapp (the actual board UI opened by Telegram's WebApp button) ─
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
async def root():
    return FileResponse("static/index.html")
