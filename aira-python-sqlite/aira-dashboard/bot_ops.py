"""
bot_ops.py
───────────
Everything that touches the OS or the network on the bot's behalf:
systemctl control, log tailing, a sandboxed file browser/editor, Telegram
broadcast, and best-effort owner-command discovery.

Passwordless sudo:
  This process runs as a normal user and shells out to `sudo systemctl`.
  See SETUP.md for the exact /etc/sudoers.d rule that allows ONLY
  `systemctl {start,stop,restart,status} <service>` for this user without a
  password prompt - do not widen that rule.
"""
from __future__ import annotations

import os
import py_compile
import shutil
import subprocess
import time
from pathlib import Path
from typing import Optional

BOT_DIR = Path(os.environ.get("AIRA_BOT_DIR", ".")).resolve()
SERVICE_NAME = os.environ.get("AIRA_SERVICE_NAME", "aira-bot")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")

TELEGRAM_API = "https://api.telegram.org"
BACKUP_DIR = BOT_DIR / ".dashboard_backups"

# File types the code editor will open/save. Anything else is browse+download only.
EDITABLE_EXTENSIONS = {".py", ".txt", ".md", ".json", ".env", ".cfg", ".ini", ".yaml", ".yml"}
MAX_READ_BYTES = 2_000_000  # 2 MB guard so the editor never chokes on a huge file


class PathEscape(Exception):
    """Raised when a requested path would resolve outside BOT_DIR."""


def _safe_path(rel_path: str) -> Path:
    rel_path = rel_path or ""
    candidate = (BOT_DIR / rel_path).resolve()
    if BOT_DIR not in candidate.parents and candidate != BOT_DIR:
        raise PathEscape(f"'{rel_path}' is outside the bot directory")
    return candidate


# ─── systemctl control ───────────────────────────────────────────────────

def _systemctl(action: str) -> dict:
    try:
        result = subprocess.run(
            ["sudo", "-n", "systemctl", action, SERVICE_NAME],
            capture_output=True, text=True, timeout=20,
        )
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": f"systemctl {action} timed out"}
    ok = result.returncode == 0
    return {"ok": ok, "stdout": result.stdout.strip(), "stderr": result.stderr.strip()}


def start_bot() -> dict:
    return _systemctl("start")


def stop_bot() -> dict:
    return _systemctl("stop")


def restart_bot() -> dict:
    return _systemctl("restart")


def bot_status() -> dict:
    try:
        result = subprocess.run(
            ["systemctl", "show", SERVICE_NAME, "--property=ActiveState,SubState,ExecMainStartTimestamp,ExecMainPID"],
            capture_output=True, text=True, timeout=10,
        )
    except subprocess.TimeoutExpired:
        return {"active": "unknown", "detail": "status check timed out"}
    props = dict(line.split("=", 1) for line in result.stdout.strip().splitlines() if "=" in line)
    return {
        "active": props.get("ActiveState", "unknown"),
        "sub_state": props.get("SubState", "unknown"),
        "since": props.get("ExecMainStartTimestamp", ""),
        "pid": props.get("ExecMainPID", ""),
        "raw_error": result.stderr.strip() or None,
    }


def tail_logs(lines: int = 300) -> str:
    try:
        result = subprocess.run(
            ["journalctl", "-u", SERVICE_NAME, "-n", str(lines), "--no-pager"],
            capture_output=True, text=True, timeout=10,
        )
    except subprocess.TimeoutExpired:
        return "(log fetch timed out)"
    if result.returncode != 0:
        return result.stderr.strip() or "(no logs available - check journald permissions)"
    return result.stdout


# ─── file browser / editor ──────────────────────────────────────────────

def list_dir(rel_path: str) -> list[dict]:
    target = _safe_path(rel_path)
    if not target.exists():
        raise NotADirectoryError(f"'{rel_path}' does not exist")
    if not target.is_dir():
        raise NotADirectoryError(f"'{rel_path}' is not a directory")
    entries = []
    for child in sorted(target.iterdir(), key=lambda p: (p.is_file(), p.name.lower())):
        if child.name == "__pycache__" or (child.name.startswith(".") and child.name != ".env"):
            continue  # hide dotfiles / our own backup dir / pycache, except .env which admins need
        stat = child.stat()
        entries.append({
            "name": child.name,
            "path": str(child.relative_to(BOT_DIR)),
            "is_dir": child.is_dir(),
            "size": stat.st_size if child.is_file() else None,
            "modified": stat.st_mtime,
            "editable": child.suffix.lower() in EDITABLE_EXTENSIONS or child.name.lower() == ".env",
        })
    return entries


def read_file(rel_path: str) -> dict:
    target = _safe_path(rel_path)
    if not target.is_file():
        raise FileNotFoundError(f"'{rel_path}' not found")
    if target.stat().st_size > MAX_READ_BYTES:
        raise FileNotFoundError(f"'{rel_path}' is too large to open in the editor (>2MB) - use download instead")
    try:
        content = target.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        raise FileNotFoundError(f"'{rel_path}' is not a text file")
    return {"path": rel_path, "content": content}


def write_file(rel_path: str, content: str) -> dict:
    target = _safe_path(rel_path)
    if not target.exists():
        raise FileNotFoundError(f"'{rel_path}' not found - creating new files isn't supported yet")

    # Safety net: if it's a .py file, back it up and compile-check the new
    # content BEFORE overwriting, so a bad edit never bricks the bot.
    if target.suffix == ".py":
        try:
            py_compile.compile(str(target), doraise=False)  # noop, just ensures module cache dir exists
        except Exception:
            pass
        tmp_check = target.with_suffix(".dashboard_check.py")
        tmp_check.write_text(content, encoding="utf-8")
        try:
            py_compile.compile(str(tmp_check), doraise=True)
        except py_compile.PyCompileError as e:
            tmp_check.unlink(missing_ok=True)
            raise PermissionError(f"Not saved - new content doesn't compile: {e.msg}")
        finally:
            tmp_check.unlink(missing_ok=True)

    BACKUP_DIR.mkdir(exist_ok=True)
    backup_name = f"{target.name}.{int(time.time())}.bak"
    shutil.copy2(target, BACKUP_DIR / backup_name)

    target.write_text(content, encoding="utf-8")
    return {"ok": True, "backup": str(BACKUP_DIR / backup_name)}


def download_path(rel_path: str) -> Path:
    return _safe_path(rel_path)


# ─── broadcast ───────────────────────────────────────────────────────────

def broadcast(text: str, targets: list[int]) -> dict:
    if not BOT_TOKEN:
        return {"ok": False, "error": "BOT_TOKEN is not set - can't reach the Telegram API"}

    import httpx  # imported lazily so the rest of the dashboard works without it installed

    sent = failed = 0
    errors: list[str] = []
    url = f"{TELEGRAM_API}/bot{BOT_TOKEN}/sendMessage"
    with httpx.Client(timeout=10) as client:
        for i, chat_id in enumerate(targets):
            try:
                resp = client.post(url, json={"chat_id": chat_id, "text": text})
                if resp.status_code == 200 and resp.json().get("ok"):
                    sent += 1
                else:
                    failed += 1
                    errors.append(f"{chat_id}: {resp.text[:120]}")
            except Exception as e:
                failed += 1
                errors.append(f"{chat_id}: {e}")
            if i % 25 == 24:
                time.sleep(1)  # stay well under Telegram's rate limits on big broadcasts
    return {"ok": True, "sent": sent, "failed": failed, "errors": errors[:20]}


# ─── owner-command discovery (best effort - verify manually) ───────────

def owner_commands() -> list[dict]:
    """
    Tries two sources, in order:
      1. owner_commands.json next to the bot code, if you maintain one -
         treated as the source of truth.
      2. A best-effort text scan of the bot's .py files for command
         definitions that look owner/admin-gated. This is NOT guaranteed
         complete or accurate - it's a starting point for you to confirm,
         not an authoritative list.
    """
    curated = BOT_DIR / "owner_commands.json"
    if curated.exists():
        import json
        try:
            return json.loads(curated.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass

    found: list[dict] = []
    owner_hints = ("owner_id", "OWNER_ID", "is_owner", "ADMIN_ID", "admin_id")
    try:
        py_files = sorted(BOT_DIR.glob("*.py"))
    except OSError:
        py_files = []
    for py_file in py_files:
        try:
            lines = py_file.read_text(encoding="utf-8", errors="ignore").splitlines()
            for i, line in enumerate(lines):
                stripped = line.strip()
                if stripped.startswith(("@bot.command", "@dp.message", "@bot.on_message", "def cmd_", "async def cmd_")):
                    window = "\n".join(lines[max(0, i - 2):i + 6])
                    if any(hint in window for hint in owner_hints):
                        found.append({
                            "file": py_file.name,
                            "line": i + 1,
                            "snippet": stripped[:120],
                            "note": "Auto-detected from an owner/admin ID check nearby - verify manually.",
                        })
        except Exception:
            # A single unreadable/oddly-encoded file should never take down
            # the whole scan - skip it and keep going.
            continue
    if not found:
        found.append({
            "file": None, "line": None, "snippet": None,
            "note": (
                "No owner-gated commands auto-detected. Create owner_commands.json "
                "next to the bot code (a list of {\"name\":, \"usage\":, \"description\":} "
                "objects) to show a curated list here instead."
            ),
        })
    return found
