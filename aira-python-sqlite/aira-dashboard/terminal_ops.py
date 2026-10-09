"""
terminal_ops.py
────────────────
A real interactive shell, backed by a pty, reachable from the dashboard
over a WebSocket. This is the most powerful thing in the whole app —
it is NOT scoped to the bot directory, NOT limited to a command allowlist,
and runs as whatever OS user the dashboard process runs as. Treat access
to it as equivalent to SSH access to the box.

Because of that, dashboard_server.py:
  - requires a valid session cookie before the WebSocket handshake is
    even accepted (same session system as everything else)
  - enforces an idle timeout, closing the socket if nothing is typed
    for TERMINAL_IDLE_TIMEOUT seconds
  - writes a line to terminal_audit.log every time a session opens or
    closes (who, when, how long) - not a full keystroke log, but enough
    to answer "was this used, and by whom" after the fact

This module only does the OS-level pty plumbing. It knows nothing about
HTTP/WebSocket framing - that lives in dashboard_server.py.
"""
from __future__ import annotations

import asyncio
import fcntl
import os
import pty
import struct
import termios
import time
from pathlib import Path
from typing import Optional

BOT_DIR = Path(os.environ.get("AIRA_BOT_DIR", ".")).resolve()
AUDIT_LOG = BOT_DIR / "terminal_audit.log"
TERMINAL_IDLE_TIMEOUT = int(os.environ.get("AIRA_TERMINAL_IDLE_TIMEOUT", "900"))  # 15 min
SHELL = os.environ.get("SHELL", "/bin/bash")


def _log(line: str) -> None:
    try:
        with open(AUDIT_LOG, "a", encoding="utf-8") as f:
            f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {line}\n")
    except OSError:
        pass  # audit logging must never crash the terminal itself


class PtySession:
    """One live shell process + its pty file descriptor."""

    def __init__(self, username: str, cols: int = 80, rows: int = 24):
        self.username = username
        self.opened_at = time.time()
        self.last_activity = time.time()
        pid, fd = pty.fork()
        if pid == 0:
            # Child: become the shell, in the bot's own directory so
            # relative paths (venv, .env, aira.db) behave the way the
            # person expects from an SSH session.
            os.chdir(str(BOT_DIR))
            os.environ["TERM"] = "xterm-256color"
            os.execvp(SHELL, [SHELL, "-l"])
            os._exit(1)  # pragma: no cover - only reached if exec fails
        self.pid = pid
        self.fd = fd
        self.resize(cols, rows)
        os.set_blocking(self.fd, False)
        _log(f"OPEN user={username} pid={pid}")

    def resize(self, cols: int, rows: int) -> None:
        try:
            winsize = struct.pack("HHHH", rows, cols, 0, 0)
            fcntl.ioctl(self.fd, termios.TIOCSWINSZ, winsize)
        except OSError:
            pass

    def write(self, data: bytes) -> None:
        self.last_activity = time.time()
        try:
            os.write(self.fd, data)
        except OSError:
            pass

    def read(self, max_bytes: int = 65536) -> Optional[bytes]:
        try:
            return os.read(self.fd, max_bytes)
        except BlockingIOError:
            return b""
        except OSError:
            return None  # pty closed / process exited

    def idle_seconds(self) -> float:
        return time.time() - self.last_activity

    def close(self) -> None:
        duration = int(time.time() - self.opened_at)
        _log(f"CLOSE user={self.username} pid={self.pid} duration_s={duration}")
        try:
            os.close(self.fd)
        except OSError:
            pass
        try:
            os.kill(self.pid, 9)
            os.waitpid(self.pid, 0)
        except (OSError, ChildProcessError):
            pass


async def pump_pty_to_websocket(session: PtySession, send_bytes) -> None:
    """Forward pty output to the websocket as it arrives, using the event
    loop's own fd-readiness notification (the pty master fd is a normal
    selectable fd) rather than polling, until the process dies or the
    session goes idle too long. Runs as its own asyncio task."""
    loop = asyncio.get_event_loop()
    queue: asyncio.Queue = asyncio.Queue()

    def _on_readable():
        data = session.read()
        queue.put_nowait(data)  # None means the pty/process is gone

    loop.add_reader(session.fd, _on_readable)
    try:
        while True:
            try:
                data = await asyncio.wait_for(queue.get(), timeout=5.0)
            except asyncio.TimeoutError:
                if session.idle_seconds() > TERMINAL_IDLE_TIMEOUT:
                    _log(f"TIMEOUT user={session.username} pid={session.pid}")
                    break
                continue
            if data is None:
                break  # shell exited
            if data:
                await send_bytes(data)
    finally:
        try:
            loop.remove_reader(session.fd)
        except (ValueError, OSError):
            pass
