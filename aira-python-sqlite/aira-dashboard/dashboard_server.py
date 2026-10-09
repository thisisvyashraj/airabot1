"""
dashboard_server.py
────────────────────
Run with:
    ./venv/bin/uvicorn dashboard_server:app --host 127.0.0.1 --port 8420

Then reach it either via `ssh -L 8420:localhost:8420 azureuser@<VM_IP>` and
open http://localhost:8420, or put it behind a systemd unit + your existing
Cloudflare tunnel setup if you want it reachable directly (see SETUP.md for
why an SSH tunnel is the safer default).

Env vars it reads (put these in the SAME .env the bot uses, or export them
in the dashboard's own systemd unit):
    AIRA_BOT_DIR          - path to the bot's folder (default: current dir)
    AIRA_DB_PATH          - path to aira.db (default: aira.db)
    AIRA_SERVICE_NAME     - systemd unit name (default: aira-bot)
    BOT_TOKEN             - same Telegram bot token the bot uses (for Announce)
    AIRA_DASHBOARD_CONFIG - path to the accounts file (default: dashboard_config.json)
    AIRA_AUTO_RESTART     - "0" to disable auto-restart-after-user-edit (default: on)
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

import asyncio
import json as _json

from fastapi import FastAPI, Request, Response, Depends, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

import auth
import bot_ops
import db_adapter
import terminal_ops

BASE_DIR = Path(__file__).parent
AUTO_RESTART = os.environ.get("AIRA_AUTO_RESTART", "1") != "0"

app = FastAPI(title="Aira Godmode Dashboard")
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=BASE_DIR / "templates")

SESSION_COOKIE = "aira_session"
PENDING_COOKIE = "aira_pending"


# ─── auth dependencies ──────────────────────────────────────────────────

def get_session(request: Request) -> Optional[dict]:
    return auth.get_session(request.cookies.get(SESSION_COOKIE))


def require_session(request: Request) -> dict:
    session = get_session(request)
    if not session:
        raise HTTPException(status_code=401, detail="Not logged in")
    return session


def require_csrf(request: Request, session: dict = Depends(require_session)) -> dict:
    header = request.headers.get("X-CSRF-Token")
    token = request.cookies.get(SESSION_COOKIE)
    if not auth.check_csrf(token, header):
        raise HTTPException(status_code=403, detail="Bad or missing CSRF token")
    return session


# ─── auth routes ────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
def root(request: Request):
    if get_session(request):
        return RedirectResponse("/dashboard")
    return RedirectResponse("/login")


@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    if get_session(request):
        return RedirectResponse("/dashboard")
    return templates.TemplateResponse(request, "login.html", {"error": None})


@app.post("/login", response_class=HTMLResponse)
async def login_form(request: Request):
    form = await request.form()
    username = (form.get("username") or "").strip()
    password = form.get("password") or ""
    if not auth.check_credentials(username, password):
        return templates.TemplateResponse(
            request,
            "login.html",
            {"error": "Wrong username or password. Try again."},
            status_code=401,
        )
    pending_token = auth.create_pending(username)
    resp = RedirectResponse("/verify", status_code=303)
    resp.set_cookie(PENDING_COOKIE, pending_token, httponly=True, samesite="strict", max_age=auth.PENDING_TTL)
    return resp


@app.get("/verify", response_class=HTMLResponse)
def verify_page(request: Request):
    token = request.cookies.get(PENDING_COOKIE)
    username = auth.peek_pending(token)
    if not username:
        return RedirectResponse("/login")
    oath_name = auth.verify_name_for(username)
    return templates.TemplateResponse(request, "verify.html", {"oath_name": oath_name})


@app.post("/verify")
async def verify_submit(request: Request):
    form = await request.form()
    answer = form.get("answer")
    token = request.cookies.get(PENDING_COOKIE)
    username = auth.pop_pending(token)
    resp = RedirectResponse("/login", status_code=303)
    resp.delete_cookie(PENDING_COOKIE)
    if not username or answer != "yes":
        return templates.TemplateResponse(
            request,
            "login.html",
            {"error": "Ghevar knows a liar when it sees one. Log in again."},
            status_code=401,
        )
    session_token, _csrf = auth.create_session(username)
    resp = RedirectResponse("/dashboard", status_code=303)
    resp.delete_cookie(PENDING_COOKIE)
    resp.set_cookie(SESSION_COOKIE, session_token, httponly=True, samesite="strict", max_age=auth.SESSION_TTL)
    return resp


@app.post("/logout")
def logout(request: Request, response: Response):
    auth.destroy_session(request.cookies.get(SESSION_COOKIE))
    resp = JSONResponse({"ok": True})
    resp.delete_cookie(SESSION_COOKIE)
    return resp


@app.get("/dashboard", response_class=HTMLResponse)
def dashboard_page(request: Request, session: dict = Depends(require_session)):
    display_name = auth.display_name_for(session["username"])
    return templates.TemplateResponse(
        request,
        "dashboard.html",
        {"display_name": display_name, "csrf": session["csrf"]},
    )


# ─── schema check ────────────────────────────────────────────────────────

@app.get("/api/schema-check")
def api_schema_check(session: dict = Depends(require_session)):
    return {"problems": db_adapter.verify_schema()}


# ─── bot control ─────────────────────────────────────────────────────────

@app.get("/api/status")
def api_status(session: dict = Depends(require_session)):
    return bot_ops.bot_status()


@app.post("/api/bot/{action}")
def api_bot_action(action: str, session: dict = Depends(require_csrf)):
    if action not in ("start", "stop", "restart"):
        raise HTTPException(400, "Unsupported action")
    fn = {"start": bot_ops.start_bot, "stop": bot_ops.stop_bot, "restart": bot_ops.restart_bot}[action]
    return fn()


@app.get("/api/logs")
def api_logs(session: dict = Depends(require_session)):
    return {"logs": bot_ops.tail_logs(300)}


# ─── users ───────────────────────────────────────────────────────────────

@app.get("/api/users")
def api_users(search: str = "", page: int = 1, session: dict = Depends(require_session)):
    return db_adapter.list_users(search=search, page=max(1, page))


@app.get("/api/users/{uid}")
def api_user_detail(uid: str, session: dict = Depends(require_session)):
    user = db_adapter.get_user(uid)
    if user is None:
        raise HTTPException(404, "No such user")
    return user


class CurrencyAdjust(BaseModel):
    field: str
    delta: int


@app.post("/api/users/{uid}/currency")
def api_user_currency(uid: str, body: CurrencyAdjust, session: dict = Depends(require_csrf)):
    try:
        doc = db_adapter.adjust_currency(uid, body.field, body.delta)
    except (KeyError, ValueError) as e:
        raise HTTPException(400, str(e))
    if AUTO_RESTART:
        bot_ops.restart_bot()
    return {"ok": True, "new_value": doc.get(body.field)}


@app.post("/api/users/{uid}/reset-cooldowns")
def api_user_reset_cooldowns(uid: str, session: dict = Depends(require_csrf)):
    try:
        db_adapter.reset_cooldowns(uid)
    except KeyError as e:
        raise HTTPException(404, str(e))
    if AUTO_RESTART:
        bot_ops.restart_bot()
    return {"ok": True}


class BadgeGrant(BaseModel):
    badge: str


@app.post("/api/users/{uid}/badge")
def api_user_grant_badge(uid: str, body: BadgeGrant, session: dict = Depends(require_csrf)):
    badge = body.badge.strip()
    if not badge:
        raise HTTPException(400, "Badge name can't be empty")
    try:
        doc = db_adapter.grant_badge(uid, badge)
    except KeyError as e:
        raise HTTPException(404, str(e))
    if AUTO_RESTART:
        bot_ops.restart_bot()
    return {"ok": True, "badges": doc.get("badges")}


class RawUserEdit(BaseModel):
    doc: dict


@app.post("/api/users/{uid}/raw")
def api_user_raw(uid: str, body: RawUserEdit, session: dict = Depends(require_csrf)):
    existing = db_adapter.get_doc("users", uid)
    if existing is None:
        raise HTTPException(404, "No such user")
    new_doc = dict(body.doc)
    new_doc.pop("_id", None)
    db_adapter.upsert_doc("users", uid, new_doc)
    if AUTO_RESTART:
        bot_ops.restart_bot()
    return {"ok": True}


@app.delete("/api/users/{uid}")
def api_user_delete(uid: str, session: dict = Depends(require_csrf)):
    ok = db_adapter.delete_doc("users", uid)
    if not ok:
        raise HTTPException(404, "No such user")
    if AUTO_RESTART:
        bot_ops.restart_bot()
    return {"ok": True}


# ─── analytics ─────────────────────────────────────────────────────────

@app.get("/api/analytics")
def api_analytics(session: dict = Depends(require_session)):
    return db_adapter.analytics_snapshot()


# ─── announce ────────────────────────────────────────────────────────────

@app.get("/api/announce/targets")
def api_announce_targets(session: dict = Depends(require_session)):
    return {"count": len(db_adapter.broadcast_targets())}


class AnnounceBody(BaseModel):
    text: str


@app.post("/api/announce")
def api_announce(body: AnnounceBody, session: dict = Depends(require_csrf)):
    if not body.text.strip():
        raise HTTPException(400, "Empty message")
    targets = db_adapter.broadcast_targets()
    if not targets:
        raise HTTPException(400, "No known users or groups yet")
    return bot_ops.broadcast(body.text, targets)


# ─── redeem codes ────────────────────────────────────────────────────────

class RedeemCreate(BaseModel):
    count: int
    amount: int
    currency: str = "gems"


@app.post("/api/redeem/create")
def api_redeem_create(body: RedeemCreate, session: dict = Depends(require_csrf)):
    try:
        codes = db_adapter.create_redeem_codes(body.count, body.amount, body.currency)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return {"codes": codes}


@app.get("/api/redeem/list")
def api_redeem_list(session: dict = Depends(require_session)):
    return {"codes": db_adapter.list_redeem_codes()}


@app.delete("/api/redeem/{code}")
def api_redeem_delete(code: str, session: dict = Depends(require_csrf)):
    ok = db_adapter.revoke_redeem_code(code)
    if not ok:
        raise HTTPException(404, "Code not found")
    return {"ok": True}


# ─── files ───────────────────────────────────────────────────────────────

@app.get("/api/files")
def api_files_list(path: str = "", session: dict = Depends(require_session)):
    try:
        return {"entries": bot_ops.list_dir(path)}
    except (bot_ops.PathEscape, NotADirectoryError) as e:
        raise HTTPException(400, str(e))


@app.get("/api/files/content")
def api_files_content(path: str, session: dict = Depends(require_session)):
    try:
        return bot_ops.read_file(path)
    except (bot_ops.PathEscape, FileNotFoundError) as e:
        raise HTTPException(400, str(e))


class FileSave(BaseModel):
    path: str
    content: str


@app.post("/api/files/save")
def api_files_save(body: FileSave, session: dict = Depends(require_csrf)):
    try:
        return bot_ops.write_file(body.path, body.content)
    except (bot_ops.PathEscape, FileNotFoundError, PermissionError) as e:
        raise HTTPException(400, str(e))


@app.get("/api/files/download")
def api_files_download(path: str, session: dict = Depends(require_session)):
    try:
        real_path = bot_ops.download_path(path)
    except bot_ops.PathEscape as e:
        raise HTTPException(400, str(e))
    if not real_path.is_file():
        raise HTTPException(404, "Not found")
    return FileResponse(real_path, filename=real_path.name)


# ─── owner commands reference ───────────────────────────────────────────

@app.get("/api/owner-commands")
def api_owner_commands(session: dict = Depends(require_session)):
    try:
        return {"commands": bot_ops.owner_commands()}
    except Exception as e:
        # Belt-and-suspenders: owner_commands() already guards per-file, but
        # this endpoint should never 500 the whole page over a best-effort
        # scan - degrade to an empty list with a visible reason instead.
        return {"commands": [], "error": f"Scan failed: {e}"}


# ─── settings ────────────────────────────────────────────────────────────

class PasswordChange(BaseModel):
    current_password: str
    new_password: str


@app.post("/api/settings/password")
def api_change_password(body: PasswordChange, session: dict = Depends(require_csrf)):
    username = session["username"]
    if not auth.check_credentials(username, body.current_password):
        raise HTTPException(400, "Current password is wrong")
    if len(body.new_password) < 6:
        raise HTTPException(400, "New password should be at least 6 characters")
    auth.set_password(username, body.new_password)
    return {"ok": True}


@app.get("/api/me")
def api_me(session: dict = Depends(require_session)):
    return {"username": session["username"], "display_name": auth.display_name_for(session["username"])}


# ─── terminal (WebSocket) ────────────────────────────────────────────────
# This is a full, unrestricted shell on the box the dashboard runs on -
# equivalent in power to SSH. It is gated by the same session cookie as
# everything else, but nothing about the shell itself is sandboxed once
# you're in. See terminal_ops.py and SETUP.md's "Terminal" section before
# exposing this dashboard anywhere but localhost/SSH-tunnel/behind
# Cloudflare Access.

@app.websocket("/ws/terminal")
async def ws_terminal(websocket: WebSocket):
    session = auth.get_session(websocket.cookies.get(SESSION_COOKIE))
    if not session:
        await websocket.close(code=4401)  # policy violation / unauthorized
        return

    await websocket.accept()
    pty_session = terminal_ops.PtySession(username=session["username"])

    async def send_bytes(data: bytes):
        await websocket.send_bytes(data)

    pump_task = asyncio.create_task(terminal_ops.pump_pty_to_websocket(pty_session, send_bytes))

    try:
        while True:
            if pump_task.done():
                break
            try:
                message = await asyncio.wait_for(websocket.receive(), timeout=1.0)
            except asyncio.TimeoutError:
                continue
            if message.get("type") == "websocket.disconnect":
                break
            if "text" in message and message["text"] is not None:
                try:
                    control = _json.loads(message["text"])
                except ValueError:
                    continue
                if control.get("type") == "resize":
                    pty_session.resize(int(control.get("cols", 80)), int(control.get("rows", 24)))
                elif control.get("type") == "input":
                    pty_session.write(control.get("data", "").encode())
            elif "bytes" in message and message["bytes"] is not None:
                pty_session.write(message["bytes"])
    except WebSocketDisconnect:
        pass
    finally:
        pump_task.cancel()
        pty_session.close()
        try:
            await websocket.close()
        except RuntimeError:
            pass  # already closed
