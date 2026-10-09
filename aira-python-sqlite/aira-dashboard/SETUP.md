# Aira Godmode Dashboard — setup

## Before you deploy (read this first)

This was built against the schema your context doc *describes* for the bot's
sqlite/Mongo-shim tables — `_id TEXT PRIMARY KEY, doc TEXT` (a JSON blob) for
`users`, and the assumption that `groups` / `meta` follow the same shape
since they go through the same shim client. **I did not have your real
`sqlite_shim.py` or `aira_bot.py`, only the exported chat transcript** — so
this is a best-effort rebuild of what was described, not code copied from
your original files.

The dashboard checks itself: open it and look at the top of any page. If the
real tables don't match, a red banner lists exactly what's wrong instead of
silently showing empty data. If you see that banner, the only files you
should need to touch are the `TABLE_*` / `FIELD_*` constants at the top of
`db_adapter.py` — everything else (auth, routes, UI) is independent of the
exact schema.

**Redeem codes** are the biggest unknown: if your bot already has its own
redeem-code table or command, point `REDEEM_TABLE` in `db_adapter.py` at it
and adjust the field names — otherwise codes created here live in their own
table and your bot's existing `/redeem` handler (if any) won't recognize
them yet.

**Owner commands** are auto-detected by scanning your bot's `.py` files for
command handlers near an owner/admin ID check — this is a starting point to
verify, not a guaranteed-complete list. For something reliable, create
`owner_commands.json` next to your bot code:
```json
[
  {"name": "/broadcast", "usage": "/broadcast <text>", "description": "Send a message to every user."}
]
```

## 1. Install

```bash
cd /home/azureuser/aira-bot/aira-python-sqlite
mkdir -p aira-dashboard && cd aira-dashboard
# copy dashboard_server.py, auth.py, db_adapter.py, bot_ops.py, templates/, static/,
# dashboard_config.json, requirements.txt here
python3 -m venv venv
./venv/bin/pip install -r requirements.txt
```

## 2. Environment

Reuse the bot's own `.env` (for `BOT_TOKEN`), plus a few dashboard-specific
vars. Either export these in the systemd unit (see below, already set up
for the default paths) or add them to the `.env`:

| Variable | Default | Purpose |
|---|---|---|
| `AIRA_BOT_DIR` | current dir | Bot's folder — file browser is sandboxed to this |
| `AIRA_DB_PATH` | `aira.db` | Path to the bot's sqlite database |
| `AIRA_SERVICE_NAME` | `aira-bot` | systemd unit name the dashboard controls |
| `BOT_TOKEN` | — | Same Telegram token the bot uses, needed for Announce |
| `AIRA_DASHBOARD_CONFIG` | `dashboard_config.json` | Where the two accounts + password hashes live |
| `AIRA_AUTO_RESTART` | `1` | Set to `0` to stop the bot auto-restarting after a user-data edit |

## 3. Passwordless sudo (only for bot control, nothing else)

The dashboard needs to run `systemctl start/stop/restart` on the bot's unit
without a password prompt. Grant **exactly that**, nothing wider:

```bash
sudo visudo -f /etc/sudoers.d/aira-dashboard
```
```
azureuser ALL=(root) NOPASSWD: /usr/bin/systemctl start aira-bot, /usr/bin/systemctl stop aira-bot, /usr/bin/systemctl restart aira-bot
```
Confirm the real path to `systemctl` with `which systemctl` first — some
distros put it at `/bin/systemctl` instead. Don't use a wildcard like
`systemctl *` here; it would let the dashboard user run *any* systemctl
command as root, not just start/stop/restart on this one unit.

Log tailing uses `journalctl -u aira-bot` — if that needs elevated
permissions on your VM, either add the dashboard's user to the `systemd-journal`
group (`sudo usermod -aG systemd-journal azureuser`, then log out/in) instead
of touching sudoers again.

## 4. Getting a permanent public URL (not Vercel — here's why, and what to do instead)

**Vercel cannot host this.** Vercel runs your code as stateless serverless
functions with no persistent filesystem and no way to `sudo systemctl` or
open a local SQLite file on your Azure VM. Every button on this dashboard —
start/stop/restart, the file editor, the terminal — only works because the
dashboard process runs *on the same VM* as the bot. There's no version of
this that works as "frontend on Vercel talking to your VM" without turning
that VM's admin API into something reachable from the whole internet, which
is a much bigger, riskier rebuild than what you asked for. So: this stays on
the VM, and we get you a permanent public link to *that*.

Two real options, in order of how much you get for the setup effort:

### Option A — Cloudflare Tunnel + Cloudflare Access (recommended if you own or can buy a domain)

This gives you a real permanent URL (e.g. `dashboard.yourdomain.com`) and,
critically, puts Cloudflare's own login wall (email one-time-code, or Google
sign-in) **in front of** the dashboard's own login page. So getting in
requires passing two independent locks, not one — this matters a lot now
that there's a real terminal behind it.

1. **Get a domain on Cloudflare** (any registrar is fine — add the domain
   to your Cloudflare account and let it manage DNS; this can be a $1–10/yr
   domain, it doesn't need to be fancy).
2. **Install `cloudflared` on the VM:**
   ```bash
   curl -L --output cloudflared.deb https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-arm64.deb
   sudo dpkg -i cloudflared.deb
   ```
   (arm64 because your VM is aarch64 — see the top of this doc.)
3. **Log in and create a named (permanent) tunnel:**
   ```bash
   cloudflared tunnel login
   cloudflared tunnel create aira-dashboard
   ```
   This prints a tunnel ID and writes credentials to `~/.cloudflared/`.
4. **Point a DNS record at it:**
   ```bash
   cloudflared tunnel route dns aira-dashboard dashboard.yourdomain.com
   ```
5. **Create `~/.cloudflared/config.yml`:**
   ```yaml
   tunnel: aira-dashboard
   credentials-file: /home/azureuser/.cloudflared/<tunnel-id>.json
   ingress:
     - hostname: dashboard.yourdomain.com
       service: http://127.0.0.1:8420
     - service: http_status:404
   ```
6. **Run it as a service so it survives reboots:**
   ```bash
   sudo cloudflared service install
   sudo systemctl enable --now cloudflared
   ```
7. **Add the login wall — Cloudflare Zero Trust → Access → Applications →
   Add an application → Self-hosted.** Point it at `dashboard.yourdomain.com`,
   and add a policy that only allows specific email addresses (yours and
   Moonlight's) via one-time email code. Now `dashboard.yourdomain.com` asks
   for an email code *before* it ever shows the dashboard's own login page.
8. **Done** — `https://dashboard.yourdomain.com` is now a permanent link
   you can open from anywhere, gated by two separate logins.

### Option B — Tailscale Funnel (no domain needed, good if you just want it working today)

Tailscale gives you a permanent HTTPS URL under `*.ts.net` without owning a
domain. The trade-off: Funnel does **not** add its own login wall in front —
anyone with the link reaches the dashboard's own login page directly. Use
this if getting a domain feels like overkill, but treat the two dashboard
passwords as the *only* thing standing between the internet and a shell, and
make sure they're the strong ones from section 6, not the originals.

```bash
curl -fsSL https://tailscale.com/install.sh | sh
sudo tailscale up
sudo tailscale funnel 8420
```
Tailscale prints your permanent public URL (something like
`https://<machine-name>.<your-tailnet>.ts.net`). It stays the same across
reboots as long as the service is running (`tailscale funnel` runs as a
background daemon once enabled — check `sudo tailscale funnel status`).

### If you don't need it public at all

The SSH tunnel from the original section 4 (`ssh -L 8420:localhost:8420 ...`)
is still the safest option and needs none of the above — use it if "share a
public link" turns out to matter less than "always have access myself."

## 5. Run it

Manually, to check it boots:
```bash
./venv/bin/uvicorn dashboard_server:app --host 127.0.0.1 --port 8420
```

As a service — copy `aira-dashboard.service` to `/etc/systemd/system/`,
edit the paths inside if yours differ, then:
```bash
sudo systemctl daemon-reload
sudo systemctl enable --now aira-dashboard
```

## 6. First login — and the passwords have already been changed

`dashboard_config.json` in this zip no longer ships with `iluvss`/`himani` —
those were flagged as weak, dictionary-word passwords in your own context
doc even before this had a terminal attached, and a terminal makes that risk
real rather than theoretical. The two accounts now use random, generated
passwords baked in as proper PBKDF2 hashes:

| Account | Username | Password |
|---|---|---|
| Yash | `vyash` | `eoNL-2cYO-3xQk` |
| Moonlight | `moonlight` | `TBxw-KFAz-oOHd` |

Log in, answer the Ghevar oath, and — since you now have a real shell in
Settings' shadow — consider rotating these again yourself once you're in,
just so no one who ever saw this chat log has them. The ghevar oath name
mapping (Yash / Mooniiiiee) is unchanged.

## 7. The terminal — read this before you expose the dashboard publicly

The new Terminal tab is a full, unrestricted shell (WebSocket + pty) running
as whatever OS user the dashboard process runs as — not sandboxed to the bot
folder, not limited to a command allowlist. It's gated behind the same
session cookie as everything else, has a 15-minute idle timeout
(`AIRA_TERMINAL_IDLE_TIMEOUT` env var to change it), and every open/close is
written to `terminal_audit.log` next to the bot's own files.

If you go with **Option A** above, the Cloudflare Access wall covers this.
If you go with **Option B** or the dashboard is otherwise reachable without
a second login layer, treat the two dashboard passwords with the same care
you'd give an SSH key — because functionally, that's what they now are.

## What I could not verify (be aware before relying on this)

- **Schema shape** for `users`/`groups`/`meta` — protected by the schema
  banner, but the banner only catches things I thought to check for.
- **Analytics fields** (`joined_at`, `last_seen`) — if your bot's user docs
  use different key names, "new today" / "active today" will read 0 even
  with real users. Adjust the `FIELD_*` constants in `db_adapter.py`.
- **Redeem code format** your bot's own handler (if one exists) expects —
  see the "Redeem codes" note above.
- **Owner command list** — auto-detected, not authoritative.
- End-to-end request flow (login → verify → dashboard → each API route) was
  exercised against a small seeded fake database and the file
  browser/editor was tested with a scratch file, all in this sandbox — not
  against your real `aira.db` or your real bot process, since neither was
  available here.
