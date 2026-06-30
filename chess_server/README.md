# Aira Chess Service

This is the backend the `/chess` flow in `aira_bot.py` already talks to
(it was wired up to call `CHESS_SERVER_URL` but that service never existed
until now). It provides:

- Full legal chess rules via `python-chess` (castling, en passant,
  promotion, checkmate, stalemate, threefold repetition, 50-move rule,
  insufficient material).
- A bot opponent with 16 difficulty levels (minimax + alpha-beta with
  tuned depth/blunder-rate/noise per level; auto-uses real Stockfish
  instead if you set `STOCKFISH_PATH`).
- Real 2-player multiplayer: room codes (share a link or `/chessjoin CODE`)
  and random matchmaking, synced live over WebSocket.
- FIDE-style Elo ratings (K=40 under 30 games, K=20 under 2400, K=10 above;
  standard expected-score formula) and a `/api/leaderboard`.
- The actual board web app (`static/`) that opens inside Telegram's
  WebApp button — click-to-move, clocks, promotion picker, resign/draw.

## 1. Add it to your repo

Copy this whole `chess_server/` folder into the root of your existing repo
(next to `aira_bot.py`).

## 2. Add 3 lines to your existing `requirements.txt`

```
fastapi==0.115.0
uvicorn[standard]==0.32.0
chess==1.11.2
```

(`uvicorn[standard]` pulls in `websockets`, which the live board sync needs.)

## 3. Add 1 line to your existing `Procfile`

```
web: cd chess_server && uvicorn main:app --host 0.0.0.0 --port $PORT
```

Your `Procfile` will then have two process types: `worker` (the Telegram
bot, unchanged) and `web` (this chess service) — both in the *same app*,
which means they share the same public URL.

## 4. Deploy, then set 2 env vars on the bot

Once deployed, your app has one public URL (e.g.
`https://your-app.herokuapp.com` or whatever your host gives you). Set:

```
CHESS_SERVER_URL=https://your-app-url
CHESS_WEBAPP_URL=https://your-app-url
```

Both point at the **same** URL — this one service serves both the JSON
API (`/api/...`) and the board webapp (`/`) together. Then scale up the
`web` process type (on Heroku: `heroku ps:scale web=1`) alongside your
existing `worker`.

No env var changes are needed for `MONGO_URI` — `chess_server/db.py` reads
the exact same `MONGO_URI` your bot already uses, and just adds new
collections (`chess_ratings`, `chess_games`, `chess_rooms`) inside the same
`aira` database.

## Notes on the bot strength scale

Level 1 plays close to random (~100 Elo) and level 16 runs a ~4-second
alpha-beta search with no noise (strong club/expert-level play, roughly
2000-2400 Elo against the internal evaluator). True "stronger than any
human" play requires a real engine binary — if you set `STOCKFISH_PATH` to
a Stockfish executable on the host, levels automatically switch to real
Stockfish with `UCI_LimitStrength`/`UCI_Elo` for levels 1-15 and full
strength for level 16, which genuinely does exceed human (including
super-GM) level. Without Stockfish installed, the built-in fallback above
is what runs — still fully legal, fully playable chess at every level.

## Notes on matchmaking persistence

The random-matchmaking queue lives in memory (a Python list), not Mongo —
simplest reliable option for a single web process. If the dyno restarts,
anyone still waiting in queue just needs to run `/chess` → Random Opponent
again. Active games and ratings are always persisted in Mongo regardless.
