"""
auth.py
────────
Everything about "who is allowed in".

Design:
  - Exactly two accounts, loaded from a small JSON file (AIRA_DASHBOARD_CONFIG,
    default dashboard_config.json) so passwords are never hardcoded in source
    and can be changed from Settings without touching code.
  - Passwords are stored as PBKDF2-SHA256 hashes with a per-user salt, never
    in plaintext.
  - Login is two steps: password check -> short-lived "pending" cookie ->
    the sarcastic Ghevar verification page -> real session cookie.
  - Sessions and pending tokens live in memory (a dict). That's fine for a
    single-process dashboard used by two people; it also means restarting
    the dashboard logs everyone out, which is an acceptable trade for
    simplicity here.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import time
from pathlib import Path
from typing import Optional

CONFIG_PATH = Path(os.environ.get("AIRA_DASHBOARD_CONFIG", "dashboard_config.json"))

PENDING_TTL = 5 * 60        # 5 minutes to answer the Ghevar question
SESSION_TTL = 12 * 60 * 60  # 12 hour session

# in-memory stores
_sessions: dict[str, dict] = {}   # session_token -> {username, csrf, expires}
_pending: dict[str, dict] = {}    # pending_token -> {username, expires}

PBKDF2_ITERATIONS = 200_000


# ─── config file ─────────────────────────────────────────────────────────

def _default_config() -> dict:
    """Used only if no config file exists yet - seeds it with the two
    accounts from the original brief, then the file becomes the source
    of truth."""
    return {
        "users": {
            "vyash": {
                "display_name": "Yash",
                "verify_name": "Yash",
                **_hash_password("iluvss"),
            },
            "moonlight": {
                "display_name": "Moonlight",
                "verify_name": "Mooniiiiee",
                **_hash_password("himani"),
            },
        }
    }


def _load_config() -> dict:
    if not CONFIG_PATH.exists():
        cfg = _default_config()
        _save_config(cfg)
        return cfg
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_config(cfg: dict) -> None:
    tmp = CONFIG_PATH.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)
    tmp.replace(CONFIG_PATH)


def _hash_password(password: str) -> dict:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), PBKDF2_ITERATIONS).hex()
    return {"salt": salt, "hash": digest}


def _verify_password(password: str, salt: str, expected_hash: str) -> bool:
    candidate = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), PBKDF2_ITERATIONS).hex()
    return hmac.compare_digest(candidate, expected_hash)


# ─── credentials ─────────────────────────────────────────────────────────

def check_credentials(username: str, password: str) -> bool:
    cfg = _load_config()
    user = cfg.get("users", {}).get(username)
    if not user:
        return False
    return _verify_password(password, user["salt"], user["hash"])


def display_name_for(username: str) -> str:
    cfg = _load_config()
    user = cfg.get("users", {}).get(username, {})
    return user.get("display_name", username)


def verify_name_for(username: str) -> str:
    """The name used in the 'Ghevar ki kasam khao ki tum ___ ho' question."""
    cfg = _load_config()
    user = cfg.get("users", {}).get(username, {})
    return user.get("verify_name", username)


def set_password(username: str, new_password: str) -> None:
    cfg = _load_config()
    if username not in cfg.get("users", {}):
        raise KeyError(username)
    cfg["users"][username].update(_hash_password(new_password))
    _save_config(cfg)


# ─── pending (post-password, pre-verification) ──────────────────────────

def create_pending(username: str) -> str:
    token = secrets.token_urlsafe(24)
    _pending[token] = {"username": username, "expires": time.time() + PENDING_TTL}
    _sweep(_pending)
    return token


def peek_pending(token: Optional[str]) -> Optional[str]:
    if not token:
        return None
    entry = _pending.get(token)
    if not entry or entry["expires"] < time.time():
        _pending.pop(token, None)
        return None
    return entry["username"]


def pop_pending(token: Optional[str]) -> Optional[str]:
    username = peek_pending(token)
    if token:
        _pending.pop(token, None)
    return username


# ─── sessions ────────────────────────────────────────────────────────────

def create_session(username: str) -> tuple[str, str]:
    token = secrets.token_urlsafe(32)
    csrf = secrets.token_urlsafe(24)
    _sessions[token] = {"username": username, "csrf": csrf, "expires": time.time() + SESSION_TTL}
    _sweep(_sessions)
    return token, csrf


def get_session(token: Optional[str]) -> Optional[dict]:
    if not token:
        return None
    entry = _sessions.get(token)
    if not entry or entry["expires"] < time.time():
        _sessions.pop(token, None)
        return None
    return entry


def destroy_session(token: Optional[str]) -> None:
    if token:
        _sessions.pop(token, None)


def check_csrf(session_token: Optional[str], header_value: Optional[str]) -> bool:
    if not session_token or not header_value:
        return False
    entry = _sessions.get(session_token)
    if not entry:
        return False
    return hmac.compare_digest(entry["csrf"], header_value)


def _sweep(store: dict) -> None:
    """Drop expired entries so these dicts don't grow forever."""
    now = time.time()
    dead = [k for k, v in store.items() if v["expires"] < now]
    for k in dead:
        store.pop(k, None)
