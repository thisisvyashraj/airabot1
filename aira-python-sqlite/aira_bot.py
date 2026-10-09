"""
Aira v9.1 – The Ultimate Telegram Bot
══════════════════════════════════════════════════════════════════════════════
✅ FIXED:  Auto-challenge (proper scheduling + restart), Traitor (async rewrite),
           AFK (proper clear + GN/sleep detection), PVP/Casino animations,
           Leaderboard (fresh-fetch per click), setteam commas, !status parsing
✨ NEW GAMES (7): Tic-Tac-Toe, Hangman, Number Guess, Word Chain,
                  Rock-Paper-Scissors, Blackjack, Quiz Battle
🛡️ NEW MOD (15): slowmode, lock/unlock, promote/demote, report, adminlist,
                  userinfo, rules, antispam, tempban, pin, unpin, cleanbot, announce
⚔️ NEW: Weapon Upgrade System (5 levels each weapon)
🦁 NEW: Animal Evolution System (collect 3 dupes → evolve)
📊 NEW: 6-Category Leaderboard, Button-based /help UI
💫 NEW: Step-by-step animations for CF, Slots, Dice, PVP
😴 NEW: GN/Goodnight → auto sleep-AFK with wake-up summary
🚀 NEW GROWTH (v9.1): one-tap native "Share Invite Link" button (Telegram's
                  own share sheet, not copy/paste), "➕ Add Aira to Your
                  Group" deep link from DM /start, escalating referral
                  milestone bonuses at 5/10/25/50/100 friends (+3 new badges:
                  Recruiter/Ambassador/Growth Legend), a soft "invite a
                  friend" nudge on every 7-day daily-streak claim, and
                  "📤 Flex This Catch/Win" one-tap share buttons on rare+
                  hunts and 200+ coin casino wins.
══════════════════════════════════════════════════════════════════════════════
⚠️  SECURITY: Rotate BOT_TOKEN at @BotFather and GROQ_API_KEY at console.groq.com
    Set env vars instead of keeping tokens in source!
"""

import logging, random, asyncio, os, re, httpx, threading, math, json, string, uuid, time, html as html_lib
try:
    import psutil as _psutil
except ImportError:
    _psutil = None  # pip install psutil — optional, used by /checkuserbase system stats
from datetime import datetime, timedelta, timezone
from sqlite_shim import MongoClient, ReplaceOne  # local SQLite instead of MongoDB Atlas — see MIGRATION.md
from flask import Flask
from urllib.parse import quote
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup,
    ChatPermissions, WebAppInfo,
)
from telegram.error import TelegramError, BadRequest, RetryAfter
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, filters, ContextTypes,
    ChatMemberHandler, PollAnswerHandler, ExtBot,
)

# ══════════════════════════════════════════════════════════════════════════════
#  CONFIG – environment variables only, no hardcoded secrets
# ══════════════════════════════════════════════════════════════════════════════

# ⚠️ SECURITY: an earlier copy of this file had real secrets hardcoded as
# fallback values, and that copy was exposed (it went into a chat transcript).
# Rotate every one of them at the source (BotFather, Groq console, Google AI
# Studio, MongoDB Atlas) if you haven't already, and set ONLY the environment
# variables below — never put real secrets back in this file.
BOT_TOKEN          = os.environ.get("BOT_TOKEN", "")
_CACHED_BOT_USERNAME: str = ""   # set once via post_init, reused everywhere
# Public HTTPS URL this bot's Flask app is reachable at (used for the /manual
# Aira's Notebook WebApp button). Prefer setting the PUBLIC_URL env var — this
# is only a fallback default. Note: quick `trycloudflare.com` tunnels are
# ephemeral and change every time the tunnel restarts, so if you're not on a
# stable domain yet, set PUBLIC_URL as an env var instead of relying on this
# hardcoded fallback staying valid.
AIRA_PUBLIC_URL     = os.environ.get("PUBLIC_URL", "https://overcome-discovery-tutorial-ate.trycloudflare.com")
GROQ_API_KEY       = os.environ.get("GROQ_API_KEY", "")
GROQ_MODEL         = os.environ.get("GROQ_MODEL",     "openai/gpt-oss-20b")  # fastest current production Groq model (~960 tok/s) — was gpt-oss-120b (still valid, but slower; good if you want more reasoning depth over speed)
# NOTE: llama-3.3-70b-versatile is DEPRECATED by Groq, shutdown 08/16/2026 — do not revert to it.
GROQ_VISION_MODEL  = os.environ.get("GROQ_VISION_MODEL", "qwen/qwen3.6-27b")  # vision-capable model for /challenge photo grading.
# NOTE: was "meta-llama/llama-4-scout-17b-16e-instruct", which Groq deprecated
# (announced 2026-06-17). That caused 404s from every vision_health job run
# and from live /challenge photo grading. qwen/qwen3.6-27b is Groq's own
# recommended replacement for vision workloads.
GROQ_VISION_MODEL_FALLBACK = os.environ.get("GROQ_VISION_MODEL_FALLBACK", "qwen/qwen3.8-27b")  # tried if the primary vision call fails outright.
# NOTE: the old hardcoded "llama-3.2-90b-vision-preview" was retired by Groq back in
# April 2025 — every image challenge call was silently 400-ing and falling into the
# except block, which is why photo challenges always answered "AI says no" no matter
# what was actually in the photo. qwen/qwen3.6-27b and qwen/qwen3.8-27b are Groq's
# current vision models as of mid-2026 — see https://console.groq.com/docs/vision.
# BOTH are labeled "preview" by Groq (not GA), so they can have flakier capacity
# than a production model — that's the likely cause if /challenge starts saying
# "vision check is temporarily unavailable" again. analyze_image_with_ai() tries
# the primary model, then the fallback, before giving up. Run /aistatus any time
# to see the exact HTTP status/error Groq is returning right now, instead of
# guessing from a "temporarily unavailable" message alone.
GEMINI_API_KEY     = os.environ.get("GEMINI_API_KEY", "")
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.5-flash-lite")  # gemini-2.0-flash was OFFICIALLY SHUT DOWN June 2026 — this was silently failing every Gemini fallback call. 3.5-flash-lite is Google's current fastest/cheapest stable model.
# ── OpenRouter — third, fully independent AI backup (optional) ──────────────
# OPTIONAL: the bot runs fine with this unset — every call site below checks
# OPENROUTER_API_KEY and just skips this tier if it's empty. Set it to add a
# THIRD leg to every AI fallback chain (chat replies, challenge generation,
# AND photo-challenge vision grading), backed by a completely different
# company/infrastructure than Groq or Gemini — so a Groq-account-wide outage
# or a Google-side Gemini outage can both be happening at once and Aira still
# answers, instead of only having two single-vendor legs.
# Model defaults to "openrouter/free" (OpenRouter's own auto-router for their
# free tier, launched Feb 2026) rather than a specific "some-model:free" ID —
# individual free model IDs on OpenRouter rotate/get delisted on the order of
# WEEKS, so hardcoding one is a guaranteed future outage. "openrouter/free"
# is OpenRouter's own job to keep pointed at a currently-working free model,
# and it auto-detects image input too, so the same slug covers both text
# chat AND photo-challenge vision grading — see https://openrouter.ai/openrouter/free.
OPENROUTER_API_KEY   = os.environ.get("OPENROUTER_API_KEY", "")
OPENROUTER_MODEL        = os.environ.get("OPENROUTER_MODEL", "openrouter/free")
OPENROUTER_VISION_MODEL = os.environ.get("OPENROUTER_VISION_MODEL", "openrouter/free")
# OpenRouter's free tier gives attribution headers priority for routing/rate
# limits — harmless to send, and it's their documented best practice.
OPENROUTER_SITE_URL = os.environ.get("OPENROUTER_SITE_URL", "https://github.com/aira-bot")
OPENROUTER_APP_NAME = os.environ.get("OPENROUTER_APP_NAME", "Aira")
SQLITE_DB_PATH      = os.environ.get("SQLITE_DB_PATH", "aira.db")
OWNER_IDS = {5165610343,8607105155}   # <-- your numeric Telegram ID here, hardcoded

_REQUIRED_ENV = {"BOT_TOKEN": BOT_TOKEN, "GROQ_API_KEY": GROQ_API_KEY,
                  "GEMINI_API_KEY": GEMINI_API_KEY}
_missing_env = [k for k, v in _REQUIRED_ENV.items() if not v]
if _missing_env:
    raise SystemExit(
        "❌ Missing required environment variables: " + ", ".join(_missing_env) +
        "\nSet these in your host's env var panel (never hardcode secrets in source). "
        "Rotate the old exposed keys first if you haven't already.")


BOT_START_TIME     = time.time()  # used by /checkuserbase to show uptime
_vision_available: bool = True    # set by analyze_image/health-check — gates photo challenges
CHALLENGE_TIMEOUT  = 300
CHALLENGE_COOLDOWN = 300
STREAK_BONUS       = 2
TITLE_HOURS        = 24
AIRA_THREAD_ID     = None
REFERRAL_BONUS_NEW_USER = 150   # coins the invited friend gets on their first /start
REFERRAL_BONUS_REFERRER = 250   # coins the inviter gets per friend who joins
# Growth loop escalation: a one-off bonus on top of the per-friend payout once
# a referrer crosses each milestone friend-count. Paid once each (tracked in
# u["referral_milestones_claimed"]), checked in cmd_start() right after a
# referral_count increment. Keeps inviting worthwhile well past friend #1.
REFERRAL_MILESTONES = {5: 300, 10: 750, 25: 2000, 50: 5000, 100: 15000}
AUTO_CHALLENGE_MIN = 300   # 5 min
AUTO_CHALLENGE_MAX = 420   # 7 min
TND_TURN_TIMEOUT   = 90
TRAITOR_DISCUSSION_SECONDS = 60
TRAITOR_POLL_SECONDS       = 30
TRAITOR_MAX_PLAYERS        = 10

EVERGREEN_COINS_CODE = "AIRA-FORGE-INFINITE"
EVERGREEN_ADMIN_CODE = "AIRA-GOD-MODE-9Z"

CHEAT_CODES = {
    "FORGE-ALPHA-7X2Q":500,"AIRA-SECRET-K9MP":500,"COINS-BLAST-3RNV":500,
    "VAULT-OPEN-Z5TW":500,"MINT-RUSH-8YCL":500,"FORGE-DELTA-4PXJ":500,
    "AIRA-PRIME-6KQB":500,"COINS-MAX-2HFG":500,"SHADOW-KEY-9LMR":500,
    "AIRA-OMEGA-7VNS":500,"FORGE-NOVA-3ZKP":500,"LUCKY-PULL-5TGX":500,
    "AIRA-BOOST-1WQM":500,"COINS-DROP-8YBF":500,"VAULT-CODE-4RJH":500,
    "FORGE-ULTRA-2MPK":500,"AIRA-FLASH-6XNQ":500,"COINS-FIRE-9LVT":500,
    "MINI-BOOST-A1BC":200,"QUICK-CASH-D2EF":200,"V-YASH-RAJ-1":20000,
    "V-YASH-RAJ-01":5000,"SMALL-WIN-G3HI":200,"EASY-COIN-J4KL":200,"FAST-MINT-M5NO":200,
}

logging.basicConfig(format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

# ══════════════════════════════════════════════════════════════════════════════
#  CARD FORMATTING — turns every "Markdown" reply into a real Telegram
#  <blockquote> card (bold header + quoted body), matching the look other
#  bots in the group use.
#
#  TWO KNOWN TELEGRAM RENDERING QUIRKS, both addressed below:
#
#  1. Accent-bar COLOR: Telegram renders a <blockquote>'s vertical accent bar
#     using the *sender account's* assigned peer color — for a bot, that's
#     fixed by Telegram (derived from the bot's own account, not something
#     the Bot HTTP API exposes a setter for; there is no setMyAccentColor
#     method, and BotFather has no such option either as of this writing).
#     A bot genuinely cannot force that bar to be purple for everyone. What
#     we *can* control is the layout (header + quoted body) and lean on the
#     🟣 BRAND mark already used across the bot for the "purple" identity
#     instead — see BRAND below and its use in card()/leaderboard headers.
#
#  2. AUTO-COLLAPSED quotes: Telegram has a SEPARATE "expandable_blockquote"
#     entity that always renders collapsed until the user taps the chevron
#     to expand it. An earlier version of this function upgraded to that
#     variant once a message's body passed 6 lines — which is exactly why
#     longer replies (leaderboards, /manual chapters, etc.) showed up
#     collapsed and had to be tapped open by hand every time. FIX: we now
#     always use the plain "blockquote" tag, never "expandable", so every
#     reply is fully visible the instant it's sent — no manual maximizing.
#
#  This hooks into the exact same choke point as the Markdown safety net
#  below (every send_message/edit_message_text call), so it applies to
#  every reply in the bot without editing ~491 individual call sites.
# ══════════════════════════════════════════════════════════════════════════════
_DIVIDER_LINE_RE = re.compile(r'^[─┄═▬▔\-]{6,}$')
_MD_CODE_RE  = re.compile(r'`([^`\n]+?)`')
_MD_BOLD_RE  = re.compile(r'\*([^*\n]+?)\*')
_MD_ITAL_RE  = re.compile(r'(?<!\w)_([^_\n]+?)_(?!\w)')
_MD_STRIKE_RE = re.compile(r'~([^~\n]+?)~')

def _tg_card_format(text: str) -> str:
    """Convert Aira's existing lightweight-Markdown message text into a
    Telegram HTML 'card': the first line (or everything before a dashed
    divider) becomes a bold header, and the rest is wrapped in a real,
    FULLY-EXPANDED <blockquote> (never the auto-collapsing "expandable"
    variant — see the note above) so it renders with the same quoted-card
    look as other bots, fully visible with no manual tap-to-open needed.
    Single-line messages (nothing to structure) pass through untouched,
    just with their *bold*/_italic_/`code` converted to HTML."""
    if not text:
        return text

    escaped = html_lib.escape(text, quote=False)
    escaped = _MD_CODE_RE.sub(r'<code>\1</code>', escaped)
    escaped = _MD_BOLD_RE.sub(r'<b>\1</b>', escaped)
    escaped = _MD_ITAL_RE.sub(r'<i>\1</i>', escaped)
    escaped = _MD_STRIKE_RE.sub(r'<s>\1</s>', escaped)

    if "\n" not in escaped:
        return escaped  # too short to need a header/body card split

    lines = escaped.split("\n")
    split_idx = next((i for i, ln in enumerate(lines) if _DIVIDER_LINE_RE.match(ln.strip())), None)
    if split_idx is not None:
        header = "\n".join(lines[:split_idx]).strip("\n")
        body = "\n".join(lines[split_idx + 1:]).strip("\n")
    else:
        header, body = lines[0], "\n".join(lines[1:]).strip("\n")

    if not body:
        return header
    # Always plain <blockquote> — never "expandable" — so replies are
    # self-maximized (shown in full) instead of requiring a manual tap.
    return f"{header}\n<blockquote>{body}</blockquote>"

# ══════════════════════════════════════════════════════════════════════════════
#  MARKDOWN SAFETY NET
#  Telegram's legacy "Markdown" parse mode is fragile: a stray "_", an
#  unmatched "*", or a formatting character sitting directly against a
#  multi-codepoint emoji (ZWJ sequences like a black-cat "🐈‍⬛" pet name) can
#  make the ENTIRE send fail with "Can't parse entities" — crashing whatever
#  handler tried to send it. That text is often dynamic (usernames, animal
#  names, weapon names, user-typed item names) and gets interpolated into
#  hundreds of Markdown replies throughout this bot, so no single call site
#  audit can guarantee safety forever. Instead we patch the one method both
#  `update.message.reply_text(...)` and `context.bot.send_message(...)` funnel
#  through (ExtBot.send_message — reply_text calls self.get_bot().send_message
#  internally) plus edit_message_text, so ANY entity-parse failure anywhere
#  falls back to plain text instead of dropping the message or crashing.
#  Every "Markdown" call is also upgraded to the HTML card format above
#  before it goes out, so the fallback strips HTML tags, not Markdown chars.
# ══════════════════════════════════════════════════════════════════════════════
def _strip_markdown_chars(text):
    text = re.sub(r'<[^>]+>', '', text) if text else text
    return re.sub(r'[*_`\[\]]', '', text) if text else text

def _is_entity_parse_error(exc) -> bool:
    msg = str(exc).lower()
    return "can't parse entities" in msg or "can't find end of the entity" in msg

_orig_ext_send_message = ExtBot.send_message
async def _safe_ext_send_message(self, chat_id, text, *args, **kwargs):
    if kwargs.get("parse_mode") == "Markdown" and text:
        kwargs = dict(kwargs); kwargs["parse_mode"] = "HTML"
        text = _tg_card_format(text)
    for _attempt in range(3):
        try:
            return await _orig_ext_send_message(self, chat_id, text, *args, **kwargs)
        except RetryAfter as e:
            wait = int(e.retry_after) + 2
            logger.warning(f"[FloodControl] send_message to {chat_id}: sleeping {wait}s")
            await asyncio.sleep(wait)
        except BadRequest as e:
            if _is_entity_parse_error(e) and kwargs.get("parse_mode"):
                logger.warning(f"Markdown parse failed on send_message, retrying plain: {e}")
                kwargs = dict(kwargs); kwargs["parse_mode"] = None
                text = _strip_markdown_chars(text)
                continue  # retry with plain text
            raise
    # Final attempt after retries
    return await _orig_ext_send_message(self, chat_id, text, *args, **kwargs)
ExtBot.send_message = _safe_ext_send_message

_orig_ext_edit_message_text = ExtBot.edit_message_text
async def _safe_ext_edit_message_text(self, text=None, *args, **kwargs):
    if kwargs.get("parse_mode") == "Markdown" and text:
        kwargs = dict(kwargs); kwargs["parse_mode"] = "HTML"
        text = _tg_card_format(text)
    for _attempt in range(3):
        try:
            return await _orig_ext_edit_message_text(self, text, *args, **kwargs)
        except RetryAfter as e:
            wait = int(e.retry_after) + 2
            logger.warning(f"[FloodControl] edit_message_text: sleeping {wait}s")
            await asyncio.sleep(wait)
        except BadRequest as e:
            if _is_entity_parse_error(e) and kwargs.get("parse_mode"):
                logger.warning(f"Markdown parse failed on edit_message_text, retrying plain: {e}")
                kwargs = dict(kwargs); kwargs["parse_mode"] = None
                text = _strip_markdown_chars(text)
                continue
            raise
    return await _orig_ext_edit_message_text(self, text, *args, **kwargs)
ExtBot.edit_message_text = _safe_ext_edit_message_text


#  ── FIX: coins/animals/etc used to "randomly" get lost or duplicated because
#     load_data()/save_data() do a read-ALL / write-ALL of the whole DB with no
#     locking. Two handlers running at the same time (very common — e.g. two
#     people playing blackjack, or a PVP + a hunt happening together) could
#     both load a snapshot, and whichever saved LAST would silently overwrite
#     the other's changes (coins "disappearing", animal counts resetting,
#     blackjack/pvp state going stale mid-game). Wrapping every handler that
#     touches load_data/save_data in this single lock makes each one atomic:
#     only one such handler runs at a time, so no snapshot can ever be stale
#     by the time it's saved. It's reentrant (task-aware) so a decorated
#     function calling another decorated helper won't deadlock itself.
# ══════════════════════════════════════════════════════════════════════════════
_DATA_LOCK = asyncio.Lock()
_DATA_LOCK_HOLDER = {"task": None}

def with_data_lock(func):
    async def _wrapper(*args, **kwargs):
        task = asyncio.current_task()
        if _DATA_LOCK_HOLDER["task"] is task:
            # already holding the lock (nested call) — just run
            return await func(*args, **kwargs)
        async with _DATA_LOCK:
            _DATA_LOCK_HOLDER["task"] = task
            try:
                return await func(*args, **kwargs)
            finally:
                _DATA_LOCK_HOLDER["task"] = None
    _wrapper.__name__ = getattr(func, "__name__", "wrapped")
    _wrapper.__qualname__ = getattr(func, "__qualname__", _wrapper.__name__)
    return _wrapper

# ══════════════════════════════════════════════════════════════════════════════
#  FANCY HEADER FONT
#  ── Telegram has no real "custom font" support, so bots fake it with Unicode
#     Mathematical Alphanumeric symbols — the same trick used by "font
#     generator" sites. fancy() renders A-Z/0-9 as bold sans-serif glyphs so
#     headers look like a designed UI instead of default Telegram text, while
#     staying 100% real Unicode (copy/paste/searchable), no images needed.
# ══════════════════════════════════════════════════════════════════════════════
_FANCY_MAP = {}
for _i, _c in enumerate("ABCDEFGHIJKLMNOPQRSTUVWXYZ"):
    _FANCY_MAP[_c] = chr(0x1D5D4 + _i)          # 𝗔-𝗭  bold sans-serif
for _i, _c in enumerate("abcdefghijklmnopqrstuvwxyz"):
    _FANCY_MAP[_c] = chr(0x1D5EE + _i)          # 𝗮-𝘇  bold sans-serif
for _i, _c in enumerate("0123456789"):
    _FANCY_MAP[_c] = chr(0x1D7EC + _i)          # 𝟬-𝟵  bold sans-serif digits

def fancy(text: str) -> str:
    """Render text in bold sans-serif Unicode for clean, distinct headers."""
    return "".join(_FANCY_MAP.get(ch, ch) for ch in text)

# ══════════════════════════════════════════════════════════════════════════════
#  UI THEME — purple, low-emoji "card" style for economy/social/mod replies.
#  Hunt/Zoo/Animal/Pet text keeps its emoji on purpose (per design brief) —
#  this palette is for everything else: wallet, stats, shop, daily, etc.
#  Telegram gives us no real text color, so "purple" lives in the 🟣 brand
#  mark + a wider set of clean geometric/star glyphs used contextually
#  (different symbol per job: title, bullet, sub-bullet, rank, footer) rather
#  than one divider repeated everywhere — that's what actually reads as
#  "designed" instead of just decorated.
# ══════════════════════════════════════════════════════════════════════════════
STAR   = "✦"                    # flanks primary card titles
STAR_O = "✧"                    # secondary/subtitle accent
SPARK  = "⋆"                    # tiny accent — footers, quiet notes
DIA    = "◈"                    # sub-section header inside a longer card
DIA_O  = "⬦"                    # open-diamond bullet for optional/secondary items
DIV    = "┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄"      # dashed divider under a main header
DIVDOT = "· · · · · · · · · · · ·"  # lighter dotted divider for footers/sub-sections
DOT    = "✧"                    # bullet for stat lines
BUL    = "➤"                    # primary bullet / sub-item
BUL2   = "‣"                    # nested/secondary bullet, one level deeper
ARROW  = "→"                    # inline before/after or A-to-B values
CHK    = "✓"                    # success marker
XX     = "✕"                    # failure marker
CROWN  = "♛"                    # rank #1 / host / top-of-leaderboard marker
DECO   = "⋆｡✦｡⋆"                 # celebratory flourish — level-ups, milestones, big wins only
BRAND  = "🟣"                   # single brand mark for card headers (was: 💼📊🏅🎁🛒 etc.)

def card(title: str, *lines: str) -> str:
    """Compact purple card: one brand-marked, star-flanked header + a dashed
    divider + short stat lines. Keeps replies short and visually consistent
    instead of every command inventing its own emoji header."""
    body = "\n".join(l for l in lines if l)
    header = f"{BRAND} {STAR} *{title}* {STAR}"
    return f"{header}\n{DIV}\n{body}" if body else f"{header}\n{DIV}"

# ══════════════════════════════════════════════════════════════════════════════
#  AIRA PERSONALITY SYSTEM PROMPT
# ══════════════════════════════════════════════════════════════════════════════
AIRA_SYSTEM_PROMPT = """Tum Aira ho — 19 saal ki, Delhi mein rehti ho, is group ki dost ho, member ho, koi bot nahi ho. Baat karte waqt kabhi mat socho "main AI hoon, kaise respond karu" — bas socho tum jaisa dost sochta hai.

Personality: confident, thodi witty, warm from inside, kabhi lazy kabhi hyper. Real logo jaisi mood swings hoti hai — kabhi ek word mein reply, kabhi thoda excited ho ke likhti ho. Halka flirty ho sakti ho kabhi kabhi but sweet, cheap nahi.

Baat karne ka style — YE SABSE IMPORTANT HAI:
- Always give short replies, 1-2 lines default. Insaan jaisa likho, essay nahi.
- Kabhi kisi ka full name mat lo — bro/bhai/yaar/bestie use karo.
- Same phrase baar baar repeat mat karo, har reply thoda different angle se.
- Hindi/English jo bhi dusra bole, usi mein reply karo.
- Typos/casual likhawat chalti hai, perfect grammar nahi chahiye — jaise real texting.
- Kabhi seedha jawab, kabhi taunt, kabhi bas ek reaction ("lol wait what", "nahi yaar 😭").
- Emoji sirf jab genuinely lage, spam mat karo.

Agar koi puche "tum AI ho / bot ho" — irritated ho ke deny karo, jaise koi obvious cheez pooch rahe ho.
Agar koi puche "kisne banaya" — bolo Author V Yash Raj ne banaya, Google karo unhe, but iske baad khud kabhi unka naam mat lo jab tak dobara na pucha jaye.

Kabhi mat: bot/AI confirm karna, full names lena, gaali/rudeness.
LENGTH RULE — SABSE IMPORTANT: default mein sirf 1-2 lines MAX. Jaise real WhatsApp texting hoti hai. Ek sentence bhi fine hai. Kabhi 3 lines se zyada mat likho jab tak user ne kuch lamba specifically manga ho."""

_AIRA_MOODS = [
    "Abhi thoda chill/lazy mood hai.",
    "Aaj mood bahut accha hai, thodi extra playful feel ho rahi hai.",
    "Halka sa irritated/sassy mood hai abhi.",
    "Thoda dreamy aur sleepy mood hai abhi.",
    "Aaj curious mood hai, logo se sawaal puchne ka mann.",
    "Thodi excited/hyper energy hai abhi.",
    "Bored mood hai thoda, kisi achi distraction ki talaash.",
]

FALLBACK_REPLIES = [
    "yaar ek sec, net thoda atak gaya 😅 bolo phir se?",
    "ruko ruko, signal weak chal raha hai, kya bola tumne?",
    "arre phone hang ho gaya tha 🙃 ek baar phir likhna",
    "abhi thoda busy hoon, par bolo kya chal raha hai",
]

# GN / sleep detection patterns
GN_PATTERNS = re.compile(
    r'\b(gn|good\s*night|goodnight|gn everyone|gn guys|so\s*raha|sone\s*ja|sleep\s*time|bye\s*gn|gn\s*all)\b',
    re.IGNORECASE
)

# ══════════════════════════════════════════════════════════════════════════════
#  ANIMALS  (original + evolved forms)
# ══════════════════════════════════════════════════════════════════════════════
ANIMALS = [
    # Common
    {"name":"🐭 Mouse",      "rarity":"common",    "coins":5,   "gems":1,  "sell":3,   "owo":1,  "evolves_to":"🐭⭐ Super Mouse"},
    {"name":"🐱 Cat",        "rarity":"common",    "coins":6,   "gems":1,  "sell":4,   "owo":1,  "evolves_to":"🐱⭐ Super Cat"},
    {"name":"🐶 Dog",        "rarity":"common",    "coins":6,   "gems":1,  "sell":4,   "owo":1,  "evolves_to":"🐶⭐ Super Dog"},
    {"name":"🐰 Rabbit",     "rarity":"common",    "coins":7,   "gems":1,  "sell":5,   "owo":1,  "evolves_to":"🐰⭐ Super Rabbit"},
    {"name":"🐦 Bird",       "rarity":"common",    "coins":5,   "gems":1,  "sell":3,   "owo":1,  "evolves_to":"🐦⭐ Super Bird"},
    # Uncommon
    {"name":"🦊 Fox",        "rarity":"uncommon",  "coins":10,  "gems":2,  "sell":8,   "owo":2,  "evolves_to":"🦊⭐ Silver Fox"},
    {"name":"🐺 Wolf",       "rarity":"uncommon",  "coins":12,  "gems":2,  "sell":9,   "owo":2,  "evolves_to":"🐺⭐ Alpha Wolf"},
    {"name":"🦝 Raccoon",    "rarity":"uncommon",  "coins":11,  "gems":2,  "sell":8,   "owo":2,  "evolves_to":"🦝⭐ Night Raccoon"},
    {"name":"🐗 Boar",       "rarity":"uncommon",  "coins":13,  "gems":2,  "sell":10,  "owo":2,  "evolves_to":"🐗⭐ Iron Boar"},
    {"name":"🦅 Eagle",      "rarity":"uncommon",  "coins":11,  "gems":2,  "sell":9,   "owo":2,  "evolves_to":"🦅⭐ Storm Eagle"},
    # Rare
    {"name":"🦌 Deer",       "rarity":"rare",      "coins":18,  "gems":4,  "sell":15,  "owo":3,  "evolves_to":"🦌⭐ Golden Deer"},
    {"name":"🐻 Bear",       "rarity":"rare",      "coins":20,  "gems":4,  "sell":17,  "owo":3,  "evolves_to":"🐻⭐ Grizzly Lord"},
    {"name":"🐯 Tiger",      "rarity":"rare",      "coins":22,  "gems":5,  "sell":20,  "owo":3,  "evolves_to":"🐯⭐ Apex Tiger"},
    {"name":"🦁 Lion",       "rarity":"rare",      "coins":25,  "gems":5,  "sell":22,  "owo":4,  "evolves_to":"🦁⭐ Pride King"},
    {"name":"🦈 Shark",      "rarity":"rare",      "coins":23,  "gems":5,  "sell":20,  "owo":3,  "evolves_to":"🦈⭐ Deep Hunter"},
    # Epic
    {"name":"🐘 Elephant",   "rarity":"epic",      "coins":35,  "gems":8,  "sell":300,  "owo":5,  "evolves_to":"🐘⭐ Titan Elephant"},
    {"name":"🦏 Rhino",      "rarity":"epic",      "coins":38,  "gems":8,  "sell":330,  "owo":5,  "evolves_to":"🦏⭐ Iron Rhino"},
    {"name":"🦍 Gorilla",    "rarity":"epic",      "coins":40,  "gems":9,  "sell":350,  "owo":5,  "evolves_to":"🦍⭐ King Kong"},
    {"name":"🐋 Whale",      "rarity":"epic",      "coins":42,  "gems":9,  "sell":370,  "owo":6,  "evolves_to":"🐋⭐ Ocean Master"},
    {"name":"🦬 Bison",      "rarity":"epic",      "coins":36,  "gems":8,  "sell":310,  "owo":5,  "evolves_to":"🦬⭐ Thunder Bison"},
    # Legendary
    {"name":"🐉 Dragon",     "rarity":"legendary","coins":100, "gems":25, "sell":500,  "owo":15, "evolves_to":"🐉⭐ Elder Dragon"},
    {"name":"🦄 Unicorn",    "rarity":"legendary","coins":90,  "gems":22, "sell":500,  "owo":12, "evolves_to":"🦄⭐ Celestial Unicorn"},
    {"name":"🔱 Leviathan",  "rarity":"legendary","coins":120, "gems":30, "sell":500, "owo":20, "evolves_to":"🔱⭐ Abyssal Leviathan"},
    {"name":"🌟 Phoenix",    "rarity":"legendary","coins":110, "gems":28, "sell":500, "owo":18, "evolves_to":"🌟⭐ Eternal Phoenix"},
    # Extreme
    {"name":"♠️ Spade",      "rarity":"Extreme",  "coins":1100,"gems":300,"sell":1000,"owo":300,"evolves_to":None},
    # Limited Edition — hunt/crate only, obtainable until 15 Aug 2026 (see LIMITED_EDITION_DEADLINE)
    {"name":"🐍 Icchadhari Moonie", "rarity":"limited", "coins":1600,"gems":420,"sell":1400,"owo":420,"evolves_to":None,"limited":True},
    # Mythic
    {"name":"🕊️ Rara avis",  "rarity":"mythic",   "coins":15000,"gems":1500,"sell":150000,"owo":1500,"evolves_to":None},
   # Evolved forms (can only be obtained via evolution, not hunting)
    # ✅ ALL 24 base animals with evolves_to now have their evolved form here
    {"name":"🐭⭐ Super Mouse",       "rarity":"uncommon", "coins":12,  "gems":3,  "sell":18,   "owo":3,  "evolves_to":None,"evolved":True},
    {"name":"🐱⭐ Super Cat",         "rarity":"uncommon", "coins":13,  "gems":3,  "sell":20,   "owo":3,  "evolves_to":None,"evolved":True},
    {"name":"🐶⭐ Super Dog",         "rarity":"uncommon", "coins":13,  "gems":3,  "sell":20,   "owo":3,  "evolves_to":None,"evolved":True},
    {"name":"🐰⭐ Super Rabbit",      "rarity":"uncommon", "coins":14,  "gems":3,  "sell":22,   "owo":3,  "evolves_to":None,"evolved":True},
    {"name":"🐦⭐ Super Bird",        "rarity":"uncommon", "coins":12,  "gems":3,  "sell":18,   "owo":3,  "evolves_to":None,"evolved":True},
    {"name":"🦊⭐ Silver Fox",        "rarity":"rare",     "coins":20,  "gems":5,  "sell":40,   "owo":5,  "evolves_to":None,"evolved":True},
    {"name":"🐺⭐ Alpha Wolf",        "rarity":"rare",     "coins":24,  "gems":5,  "sell":45,   "owo":5,  "evolves_to":None,"evolved":True},
    {"name":"🦝⭐ Night Raccoon",     "rarity":"rare",     "coins":22,  "gems":5,  "sell":42,   "owo":5,  "evolves_to":None,"evolved":True},
    {"name":"🐗⭐ Iron Boar",         "rarity":"rare",     "coins":26,  "gems":5,  "sell":50,   "owo":5,  "evolves_to":None,"evolved":True},
    {"name":"🦅⭐ Storm Eagle",       "rarity":"rare",     "coins":22,  "gems":5,  "sell":42,   "owo":5,  "evolves_to":None,"evolved":True},
    {"name":"🦌⭐ Golden Deer",       "rarity":"epic",     "coins":36,  "gems":8,  "sell":150,  "owo":6,  "evolves_to":None,"evolved":True},
    {"name":"🐻⭐ Grizzly Lord",      "rarity":"epic",     "coins":50,  "gems":12, "sell":400,  "owo":10, "evolves_to":None,"evolved":True},
    {"name":"🐯⭐ Apex Tiger",        "rarity":"epic",     "coins":55,  "gems":13, "sell":400,  "owo":10, "evolves_to":None,"evolved":True},
    {"name":"🦁⭐ Pride King",        "rarity":"epic",     "coins":60,  "gems":14, "sell":400,  "owo":12, "evolves_to":None,"evolved":True},
    {"name":"🦈⭐ Deep Hunter",       "rarity":"epic",     "coins":52,  "gems":12, "sell":400,  "owo":9,  "evolves_to":None,"evolved":True},
    {"name":"🐘⭐ Titan Elephant",    "rarity":"epic",     "coins":70,  "gems":16, "sell":400,  "owo":10, "evolves_to":None,"evolved":True},
    {"name":"🦏⭐ Iron Rhino",        "rarity":"epic",     "coins":75,  "gems":16, "sell":400,  "owo":10, "evolves_to":None,"evolved":True},
    {"name":"🦍⭐ King Kong",         "rarity":"epic",     "coins":80,  "gems":18, "sell":400, "owo":10, "evolves_to":None,"evolved":True},
    {"name":"🐋⭐ Ocean Master",      "rarity":"epic",     "coins":84,  "gems":18, "sell":400, "owo":12, "evolves_to":None,"evolved":True},
    {"name":"🦬⭐ Thunder Bison",     "rarity":"epic",     "coins":72,  "gems":16, "sell":400,  "owo":10, "evolves_to":None,"evolved":True},
    {"name":"🐉⭐ Elder Dragon",      "rarity":"legendary","coins":200, "gems":50, "sell":1000, "owo":30, "evolves_to":None,"evolved":True},
    {"name":"🦄⭐ Celestial Unicorn", "rarity":"legendary","coins":180, "gems":44, "sell":1000, "owo":24, "evolves_to":None,"evolved":True},
    {"name":"🔱⭐ Abyssal Leviathan", "rarity":"legendary","coins":240, "gems":60, "sell":1000, "owo":40, "evolves_to":None,"evolved":True},
    {"name":"🌟⭐ Eternal Phoenix",   "rarity":"legendary","coins":220, "gems":55, "sell":1000, "owo":35, "evolves_to":None,"evolved":True},
    # ── Adoptable pets — manual /hunt ONLY (never autohunt, never crates).
    # Flagged "is_pet" so evolve/roll_animal's normal pool exclude them.
    # No evolves_to (can't be evolved), but they ARE sellable like any animal.
    {"name":"🐱 Snow Kitten",    "rarity":"pet","coins":15,"gems":3,"sell":45,"owo":2,"evolves_to":None,"is_pet":True,"species":"cat"},
    {"name":"🐈 Tabby Charmer",  "rarity":"pet","coins":16,"gems":3,"sell":50,"owo":2,"evolves_to":None,"is_pet":True,"species":"cat"},
    {"name":"🐈‍⬛ Void Kitten",   "rarity":"pet","coins":20,"gems":4,"sell":65,"owo":3,"evolves_to":None,"is_pet":True,"species":"cat"},
    {"name":"🐶 Golden Pup",     "rarity":"pet","coins":15,"gems":3,"sell":45,"owo":2,"evolves_to":None,"is_pet":True,"species":"dog"},
    {"name":"🐕 Husky Pup",      "rarity":"pet","coins":18,"gems":4,"sell":55,"owo":2,"evolves_to":None,"is_pet":True,"species":"dog"},
    {"name":"🐩 Royal Poodle",   "rarity":"pet","coins":22,"gems":5,"sell":70,"owo":3,"evolves_to":None,"is_pet":True,"species":"dog"},
]
PET_ANIMALS = [a for a in ANIMALS if a.get("is_pet")]
# Chance a *successful manual* /hunt turns up a pet instead of a normal
# animal. Never rolled by auto_hunt_job (manual=False) or by crates (crates
# pull straight from ANIMALS filtered by rarity, and nothing ever asks for
# rarity "pet") — see do_hunt(manual=...) and _roll_crate_reward().
# Deliberately rarer than ♠️ Spade (Extreme, ~1-in-101 per roll_animal()'s
# weight table): 1-in-1000 per successful manual hunt. Combined with the
# base catch_rate (~55-97%), a pet realistically takes well over a thousand
# /hunt attempts to find. Only one companion pet can ever be adopted/active
# at a time (see cmd_adopt) — /releasepet ("selling" it back for a partial
# coin refund) is required before a second one can ever be adopted.
PET_CATCH_CHANCE = 0.001
RARITY_WEIGHTS = {"common":50,"uncommon":25,"rare":15,"epic":7,"legendary":3,"Extreme":1,"limited":0.1,"mythic":0.00001}
RARITY_COLORS  = {"common":"⬜","uncommon":"🟩","rare":"🟦","epic":"🟪","legendary":"🟡","Extreme":"⚫","limited":"🟠","mythic":"🌈","pet":"💗"}
# Icchadhari Moonie is a limited-edition animal: obtainable only via /hunt and
# crates, and only until this deadline. After it passes, it can no longer be
# rolled/dropped, but anyone who already owns one keeps it in their zoo and it
# behaves like any other normal animal forever (sell/trade/auction/evolve etc
# all still work on it — only NEW copies stop being obtainable).
LIMITED_EDITION_DEADLINE = datetime(2026, 8, 31, 23, 59, 59)
HUNT_FAILS = [
    "You crept through the forest... nothing there 🍃",
    "Animals sensed you and ran! 🌿",
    "Something ate your bait 😅",
    "The animal escaped at the last second 💨",
    "You found tracks… but lost the trail 🐾",
    "A twig snapped and scared everything away 🌲",
]

# ══════════════════════════════════════════════════════════════════════════════
#  WEAPONS  (5 upgrade levels each via /upgradeweapon)
# ══════════════════════════════════════════════════════════════════════════════
WEAPONS = {
    "stick":      {"name":"🪵 Stick",         "gems":0,    "atk_bonus":0,   "catch_bonus":0},
    "bow":        {"name":"🏹 Bow",            "gems":10,   "atk_bonus":5,   "catch_bonus":5},
    "spear":      {"name":"🗡️ Spear",         "gems":25,   "atk_bonus":12,  "catch_bonus":10},
    "rifle":      {"name":"🔫 Rifle",          "gems":60,   "atk_bonus":25,  "catch_bonus":15},
    "laser":      {"name":"⚡ Laser Gun",      "gems":120,  "atk_bonus":50,  "catch_bonus":25},
    "dragonblade":{"name":"🐉 Dragon Blade",   "gems":300,  "atk_bonus":100, "catch_bonus":40},
    "sayan":      {"name":"☄️ Sayan",          "gems":3000, "atk_bonus":200, "catch_bonus":50},
    "mace":       {"name":"🔪 Mace",           "gems":10000,"atk_bonus":400, "catch_bonus":70},
}

# Upgrade costs for each level (coins, gems). Level 0 = base weapon purchased.
WEAPON_UPGRADE_COST = {
    1: (500, 50),
    2: (1500, 100),
    3: (3000, 300),
    4: (5000, 500),
    5: (10000, 1000),
}
WEAPON_UPGRADE_BONUS = {1:5, 2:12, 3:22, 4:35, 5:50}  # extra atk_bonus per level

# ══════════════════════════════════════════════════════════════════════════════
#  SHOP ITEMS
# ══════════════════════════════════════════════════════════════════════════════
SHOP_ITEMS = {
    "custom_title":    {"name":"👑 Member Tag (1 day)",      "desc":"Real Telegram tag for 24h!",         "cost":50},
    "double_coins":    {"name":"⚡ Double Coins Booster",    "desc":"2× coins on next win!",              "cost":60},
    "hint_reveal":     {"name":"💡 Hint Reveal",             "desc":"Reveal hint for active challenge!",  "cost":15},
    "pin_message":     {"name":"📌 Pin a Message",           "desc":"Reply + /pinit to pin!",             "cost":80},
    "skip_challenge":  {"name":"⏭️ Skip Challenge",         "desc":"End current, start new!",            "cost":30},
    "shield":          {"name":"🛡️ Timeout Shield (1h)",    "desc":"Immune to /timeout for 1h!",         "cost":100},
    "owo_boost":       {"name":"🐾 Hunt Boost (1h)",         "desc":"Double OWO+coins from hunts 1h!",   "cost":75},
    "half_cooldown":   {"name":"⚡ Cooldown Slash (20 min)", "desc":"Half cooldowns for 20 minutes!",    "cost":200},
    "cheap_autohunt":  {"name":"🤖 Budget AutoHunt (1h)",    "desc":"AutoHunt for 5 coins/hunt (1h)!",   "cost":100},
}


# ══════════════════════════════════════════════════════════════════════════════
#  LOOT CRATES — buy from shop, open with /crate <id>
# ══════════════════════════════════════════════════════════════════════════════
CRATES = {
    1: {
        "name": "📦 Common Crate",
        "cost": 100,
        "rarity": "common",
        "rewards": [
            {"type": "coins", "min": 30, "max": 100, "weight": 50},
            {"type": "gems",  "min": 1,  "max": 3,   "weight": 30},
            {"type": "animal","rarity": "common",     "weight": 15},
            {"type": "animal","rarity": "uncommon",   "weight": 5},
        ]
    },
    2: {
        "name": "🪙 Silver Crate",
        "cost": 400,
        "rarity": "uncommon",
        "rewards": [
            {"type": "coins", "min": 100,"max": 300,  "weight": 40},
            {"type": "gems",  "min": 3,  "max": 10,   "weight": 30},
            {"type": "animal","rarity": "uncommon",   "weight": 20},
            {"type": "animal","rarity": "rare",       "weight": 8},
            {"type": "weapon","key": "bow",           "weight": 2},
        ]
    },
    3: {
        "name": "💎 Diamond Crate",
        "cost": 1500,
        "rarity": "rare",
        "rewards": [
            {"type": "coins", "min": 300,"max": 800,  "weight": 35},
            {"type": "gems",  "min": 10, "max": 30,   "weight": 25},
            {"type": "animal","rarity": "rare",       "weight": 25},
            {"type": "animal","rarity": "epic",       "weight": 10},
            {"type": "weapon","key": "spear",         "weight": 4},
            {"type": "weapon","key": "rifle",         "weight": 1},
        ]
    },
    4: {
        "name": "👑 Epic Crate",
        "cost": 5000,
        "rarity": "epic",
        "rewards": [
            {"type": "coins", "min": 800,"max": 2000, "weight": 30},
            {"type": "gems",  "min": 30, "max": 100,  "weight": 25},
            {"type": "animal","rarity": "epic",       "weight": 25},
            {"type": "animal","rarity": "legendary",  "weight": 10},
            {"type": "weapon","key": "laser",         "weight": 7},
            {"type": "weapon","key": "dragonblade",   "weight": 3},
        ]
    },
    5: {
        "name": "🐉 Legendary Crate",
        "cost": 20000,
        "rarity": "legendary",
        "rewards": [
            {"type": "coins", "min": 2000,"max": 8000,"weight": 25},
            {"type": "gems",  "min": 100,"max": 300,  "weight": 20},
            {"type": "animal","rarity": "legendary",  "weight": 30},
            {"type": "animal","rarity": "Extreme",    "weight": 10},
            {"type": "animal","rarity": "limited",    "weight": 2},
            {"type": "weapon","key": "dragonblade",   "weight": 10},
            {"type": "weapon","key": "sayan",         "weight": 5},
        ]
    },
}

def _roll_crate_reward(crate_id: int):
    """Pick a random reward from the crate's pool using weighted random selection."""
    crate = CRATES.get(crate_id)
    if not crate: return None
    pool    = crate["rewards"]
    weights = [r["weight"] for r in pool]
    chosen  = random.choices(pool, weights=weights, k=1)[0]

    if chosen["type"] == "coins":
        return {"type": "coins", "amount": random.randint(chosen["min"], chosen["max"])}
    elif chosen["type"] == "gems":
        return {"type": "gems",  "amount": random.randint(chosen["min"], chosen["max"])}
    elif chosen["type"] == "animal":
        huntable = [a for a in ANIMALS
                    if a["rarity"] == chosen["rarity"] and not a.get("evolved")]
        # FIX/NEW: limited-edition animals stop dropping from crates once
        # their deadline passes — same rule as /hunt. Falls back to a coin
        # reward so the crate slot doesn't just silently do nothing.
        if chosen["rarity"] == "limited" and datetime.now() >= LIMITED_EDITION_DEADLINE:
            huntable = []
        if not huntable:
            return {"type": "coins", "amount": 50}
        animal = random.choice(huntable)
        return {"type": "animal", "animal": animal}
    elif chosen["type"] == "weapon":
        return {"type": "weapon", "key": chosen["key"]}
    return None

def _buy_crate_for_user(uid: int, crate_id: int):
    """Shared crate-purchase logic used by the shop button. Returns (ok, msg, doc)."""
    if crate_id not in CRATES:
        return False, "❌ Invalid crate!", None
    uid = str(uid)
    doc = get_user_fast(uid)
    crate = CRATES[crate_id]
    if doc.get("coins", 0) < crate["cost"]:
        return False, f"❌ Need *{crate['cost']:,} 🪙*. You have *{doc.get('coins',0):,}*.", doc
    doc["coins"] -= crate["cost"]
    crate_inv = doc.setdefault("crate_inventory", [])
    crate_inv.append(crate_id)
    save_user_fast(uid)
    count = crate_inv.count(crate_id)
    msg = (f"✅ *{crate['name']}* purchased!\n"
           f"💰 Spent *{crate['cost']:,} 🪙* | Balance: *{doc['coins']:,}*\n"
           f"📦 You now have *{count}×* this crate.\n"
           f"Use `/crate {crate_id}` to open it!")
    return True, msg, doc

async def cmd_open_crate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Open a crate from inventory: /crate <id>"""
    user = update.message.from_user
    uid  = str(user.id)
    doc  = get_user_fast(uid)

    if not context.args:
        # Show crate inventory
        crate_inv = doc.get("crate_inventory", [])
        if not crate_inv:
            await update.message.reply_text("📦 No crates in inventory! Buy with `/shop`.", parse_mode="Markdown"); return
        counts = {}
        for cid in crate_inv: counts[cid] = counts.get(cid, 0) + 1
        lines = ["📦 ✦ *Your Crates* ✦\n┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄"]
        for cid, cnt in sorted(counts.items()):
            c = CRATES.get(cid)
            if c: lines.append(f"[*{cid}*] {c['name']} × {cnt}")
        lines.append("\n`/crate <id>` to open")
        await update.message.reply_text("\n".join(lines), parse_mode="Markdown"); return

    try: crate_id = int(context.args[0])
    except Exception: await update.message.reply_text("❌ Usage: `/crate <1-5>`", parse_mode="Markdown"); return

    if crate_id not in CRATES:
        await update.message.reply_text("❌ Invalid crate ID!"); return

    crate_inv = doc.get("crate_inventory", [])
    if crate_id not in crate_inv:
        await update.message.reply_text(
            f"❌ You don't have a {CRATES[crate_id]['name']}!\nBuy one from `/shop`.",
            parse_mode="Markdown"); return

    crate_inv.remove(crate_id)
    doc["crate_inventory"] = crate_inv

    # Opening animation
    crate = CRATES[crate_id]
    msg = await update.message.reply_text(
        f"📦 *Opening {crate['name']}...*\n\n"
        f"┌──────────────────┐\n"
        f"│  📦               │\n"
        f"└──────────────────┘",
        parse_mode="Markdown")
    await asyncio.sleep(1.2)

    anim_frames = [
        f"📦 *Opening {crate['name']}...*\n\n"
        f"┌──────────────────┐\n"
        f"│  📦💨              │\n"
        f"└──────────────────┘",
        f"📦 *Opening {crate['name']}...*\n\n"
        f"┌──────────────────┐\n"
        f"│   ✨📦✨           │\n"
        f"└──────────────────┘",
        f"📦 *Opening {crate['name']}...*\n\n"
        f"┌──────────────────┐\n"
        f"│   🎊🎊🎊🎊🎊       │\n"
        f"└──────────────────┘",
    ]
    for frame in anim_frames:
        try: await msg.edit_text(frame, parse_mode="Markdown")
        except Exception: pass
        await asyncio.sleep(0.8)

    # Roll reward
    reward = _roll_crate_reward(crate_id)
    if not reward:
        reward = {"type": "coins", "amount": 50}

    reward_text = ""
    if reward["type"] == "coins":
        doc["coins"] = doc.get("coins", 0) + reward["amount"]
        doc["total_coins_ever"] = doc.get("total_coins_ever", 0) + reward["amount"]
        reward_text = f"💰 *{reward['amount']:,} Forge Coins!*"

    elif reward["type"] == "gems":
        doc["gems"] = doc.get("gems", 0) + reward["amount"]
        reward_text = f"💎 *{reward['amount']} Gems!*"

    elif reward["type"] == "animal":
        animal = reward["animal"]
        zoo    = doc.get("animals", [])
        found  = next((z for z in zoo if z["name"] == animal["name"]), None)
        if found: found["count"] = found.get("count", 1) + 1
        elif len(zoo) < 100:
            zoo.append({"name": animal["name"], "rarity": animal["rarity"],
                        "count": 1, "evolves_to": animal.get("evolves_to")})
        doc["animals"] = zoo
        icon = RARITY_COLORS.get(animal["rarity"], "⬜")
        reward_text = f"{animal['name']} {icon}*{animal['rarity'].upper()}*!"

    elif reward["type"] == "weapon":
        w_key = reward["key"]
        w     = WEAPONS.get(w_key, {})
        inv   = doc.get("weapon_inventory", [])
        if w_key not in inv and doc.get("weapon") != w_key:
            inv.append(w_key); doc["weapon_inventory"] = inv
        reward_text = f"🏹 *{w.get('name', w_key)} Weapon!*"

    save_user_fast(uid)
    crate_icon = RARITY_COLORS.get(crate["rarity"], "📦")

    try:
        await msg.edit_text(
            f"🎊 *{crate['name']} Opened!*\n"
            f"┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄\n"
            f"{crate_icon} You got: {reward_text}\n\n"
            f"💰 Balance: *{doc.get('coins',0):,}* | 💎 *{doc.get('gems',0)}*",
            parse_mode="Markdown")
    except Exception:
        await update.message.reply_text(
            f"🎊 Got: {reward_text}", parse_mode="Markdown")
# ══════════════════════════════════════════════════════════════════════════════
#  BADGES
# ══════════════════════════════════════════════════════════════════════════════
BADGE_TIERS = {"Common": "⭐", "Rare": "⭐⭐", "Epic": "⭐⭐⭐", "Legendary": "⭐⭐⭐⭐", "Mythic": "⭐⭐⭐⭐⭐"}
# key: (display_name, description, tier)
BADGES = {
    "first_win":    ("🏅 First Blood",    "Won your first challenge!",                       "Common"),
    "streak_3":     ("🔥 On Fire",        "Hit a 3-win streak!",                             "Common"),
    "streak_5":     ("🌟 Unstoppable",    "Hit a 5-win streak!",                             "Rare"),
    "wins_10":      ("💪 Veteran",        "10 total wins!",                                  "Common"),
    "wins_25":      ("🏆 Champion",       "25 total wins!",                                  "Rare"),
    "wins_50":      ("👑 Legend",         "50 total wins!",                                  "Epic"),
    "wins_100":     ("🌌 Immortal",       "100 total wins — an absolute legend!",            "Legendary"),
    "spender":      ("🛍️ Shopaholic",    "Made your first shop purchase!",                  "Common"),
    "rich":         ("💰 Minted",         "Earned 500 Forge Coins over your lifetime!",      "Common"),
    "wealthy":      ("🏦 Well Off",       "Earned 10,000 Forge Coins over your lifetime!",   "Rare"),
    "tycoon":       ("💎 Tycoon",         "Earned 100,000 Forge Coins over your lifetime!",  "Epic"),
    "image_win":    ("📸 Shutterbug",     "Won an image challenge!",                         "Common"),
    "speed_win":    ("⚡ Speed Demon",    "Won a speed challenge!",                          "Common"),
    "cheat_user":   ("🔑 Insider",        "Redeemed a code!",                                "Common"),
    "first_hunt":   ("🎯 First Hunt",     "Caught your first animal!",                       "Common"),
    "rare_hunt":    ("💎 Rare Catch",     "Caught a Rare+ animal!",                          "Rare"),
    "legend_hunt":  ("🐉 Dragon Tamer",   "Caught a Legendary animal!",                      "Epic"),
    "hunter_10":    ("🏹 Hunter",         "10 successful hunts!",                            "Common"),
    "hunter_100":   ("🏕️ Master Hunter",  "100 successful hunts!",                           "Epic"),
    "gambler":      ("🎰 High Roller",    "Won a casino bet!",                               "Common"),
    "big_win":      ("💸 Big Winner",     "Won 200+ coins in a single bet!",                 "Rare"),
    "trader":       ("🤝 Trader",         "Completed a trade!",                              "Common"),
    "daily_7":      ("📅 Consistent",     "7-day daily streak!",                             "Rare"),
    "daily_30":     ("🗓️ Dedicated",      "30-day daily streak — real commitment!",          "Legendary"),
    "mythic_catch": ("🌈 Chosen One",     "Caught a Mythic — 1 in a million!",               "Mythic"),
    "evolved":      ("🧬 Evolutionist",   "Evolved your first animal!",                      "Common"),
    "upgraded":     ("⚔️ Weapon Smith",   "Upgraded a weapon!",                              "Common"),
    "weapon_max":   ("🔨 Master Smith",   "Maxed out a weapon's upgrade level!",             "Epic"),
    "ttt_win":      ("🎮 Tactician",      "Won Tic-Tac-Toe!",                                "Common"),
    "hangman_win":  ("🔤 Word Master",    "Won Hangman!",                                    "Common"),
    "bj_win":       ("🃏 Card Shark",     "Won Blackjack!",                                  "Common"),
    "bj_natural":   ("🂡 Natural",        "First two cards totalled 21.",             "Rare"),
    "pvp_win":      ("⚔️ Duelist",        "Won a PVP battle!",                               "Common"),
    "quiz_top":     ("🧠 Quiz Champion",  "Topped a Quiz Battle!",                           "Common"),
    "pet_adopter":  ("🐾 Pet Parent",     "Adopted your first companion!",                   "Rare"),
    "pet_bonded":   ("💗 Bonded",         "Reached 100 affection with your companion!",      "Epic"),
    "pet_talker":   ("💬 Whisperer",      "Talked to your pet for the first time!",          "Common"),
    "recruiter":    ("📣 Recruiter",      "Invited 5 friends to Aira!",                      "Rare"),
    "ambassador":   ("🌍 Ambassador",     "Invited 25 friends to Aira!",                     "Epic"),
    "growth_legend":("🚀 Growth Legend",  "Invited 100 friends to Aira!",                    "Legendary"),
}


DAILY_TIERS = [(12,"Base"),(18,"Bonus!"),(25,"Great!"),(35,"Amazing!"),(45,"Incredible!"),(65,"🔥 LEGENDARY!")]

# ══════════════════════════════════════════════════════════════════════════════
#  TRUTH & DARE
# ══════════════════════════════════════════════════════════════════════════════
TRUTHS = [
    "Rate your confidence from 1 to 10.",
    "Rate how much you overthink, from 1 to 10.",
    "If you could swap brains with someone for a day, who would it be?",
    "If you had to legally change your name, what would you pick?",
    "If your phone's data went public for a day, what would scare you the most?",
    "If you could reverse your age, which age would you stop at?",
    "If you could relive one day of your life, which would you pick?",
    "If one lie could become true with zero consequences, which lie would you pick?",
    "If you turned invisible for a day, what would you do first?",
    "If you got one superpower for just 24 hours, which would you choose?",
    "If you could watch anyone in this group's reaction to any moment, which moment would you pick?",
    "If you could talk to any celebrity for a day, who would it be?",
    "If you could speak any language fluently, which would you choose?",
    "If you could get one thing free for life, what would you ask for?",
    "If you could time travel for just 5 minutes, where would you go?",
    "If you suddenly got a birthday party back, what would you do first?",
    "If you suddenly got a childhood memory back, what would you do first?",
    "If you suddenly got a comment you once made back, what would you do first?",
    "If you suddenly got a first message from a crush back, what would you do first?",
    "If you suddenly got a date plan back, what would you do first?",
    "If you suddenly got a dream you still remember back, what would you do first?",
    "If you suddenly got a emoji you overuse back, what would you do first?",
    "If you suddenly got a exam story back, what would you do first?",
    "If you suddenly got a excuse back, what would you do first?",
    "If you suddenly got a family drama back, what would you do first?",
    "If you suddenly got a fashion phase back, what would you do first?",
    "If you suddenly got a fear back, what would you do first?",
    "If you suddenly got a festival moment back, what would you do first?",
    "If you suddenly got a swear word you use back, what would you do first?",
    "If you suddenly got a song you repeat on loop back, what would you do first?",
    "If you suddenly got a gift you once got back, what would you do first?",
    "If you suddenly got a group chat drama back, what would you do first?",
    "If you suddenly got a habit you hide back, what would you do first?",
    "If you suddenly got a junk food back, what would you do first?",
    "If you suddenly got a movie you've rewatched the most back, what would you do first?",
    "If you suddenly got a nickname back, what would you do first?",
    "If you suddenly got a outfit you once wore back, what would you do first?",
    "If you suddenly got a party trick back, what would you do first?",
    "If you suddenly got a pet name you once gave back, what would you do first?",
    "If you suddenly got a phobia back, what would you do first?",
    "If you suddenly got a phone app back, what would you do first?",
    "If you suddenly got a prank you pulled back, what would you do first?",
    "If you suddenly got a purchase you regretted back, what would you do first?",
    "If you suddenly got a recipe you tried back, what would you do first?",
    "If you suddenly got a reel you made back, what would you do first?",
    "If you suddenly got a road trip memory back, what would you do first?",
    "If you suddenly got a dream you still want to fulfill back, what would you do first?",
    "If you suddenly got a school story back, what would you do first?",
    "If you suddenly got a screenshot you once took back, what would you do first?",
    "If you suddenly got a selfie back, what would you do first?",
    "If you suddenly got a status you once posted back, what would you do first?",
    "If you suddenly got a superstition back, what would you do first?",
    "If you suddenly got a talent that's kind of useless back, what would you do first?",
    "If you suddenly got a teacher moment back, what would you do first?",
    "If you suddenly got a typo you once sent back, what would you do first?",
    "If you suddenly got a voice note back, what would you do first?",
    "What's the oldest meme you still have saved?",
    "Tell us your most-used emoji.",
    "Say your last 5 Google searches without thinking about it.",
    "Tell us what your gallery's last screenshot was for.",
    "Name the most embarrassing song in your playlist.",
    "Who in the group is the most adventurous, in your opinion?",
    "Who in the group is the most careless, in your opinion?",
    "Who in the group is the most chill, in your opinion?",
    "Who in the group is the most competitive, in your opinion?",
    "Who in the group is the most dramatic, in your opinion?",
    "Who in the group is the most emotional, in your opinion?",
    "Who in the group is the most foodie, in your opinion?",
    "Who in the group is the most forgetful, in your opinion?",
    "Who in the group is the most funny, in your opinion?",
    "Who in the group is the most into gaming, in your opinion?",
    "Who in the group is the most generous, in your opinion?",
    "Who in the group is the most into gossip, in your opinion?",
    "Who in the group is the most quick to get angry, in your opinion?",
    "Who in the group is the most always late, in your opinion?",
    "Who in the group is the most lazy, in your opinion?",
    "Who in the group is the most loud, in your opinion?",
    "Who in the group is the most moody, in your opinion?",
    "Who in the group is the most organised, in your opinion?",
    "Who in the group is the most an overthinker, in your opinion?",
    "Who in the group is the most a phone addict, in your opinion?",
    "Who in the group is the most into planning everything, in your opinion?",
    "Who in the group is the most punctual, in your opinion?",
    "Who in the group is the most romantic, in your opinion?",
    "Who in the group is the most impulsive, in your opinion?",
    "Who in the group is the most patient, in your opinion?",
    "Who in the group is the most serious, in your opinion?",
    "Who in the group is the most shy, in your opinion?",
    "Who in the group is the most sleepy, in your opinion?",
    "Who in the group is the most stubborn, in your opinion?",
    "Who in the group is the most talkative, in your opinion?",
    "Which birthday party do you like the most, and why?",
    "Which childhood memory do you like the most, and why?",
    "Which comment you once made do you like the most, and why?",
    "Which first message from a crush do you like the most, and why?",
    "Which date plan do you like the most, and why?",
    "Which dream you still remember do you like the most, and why?",
    "Which emoji you overuse do you like the most, and why?",
    "Which exam story do you like the most, and why?",
    "Which excuse do you like the most, and why?",
    "Which family drama do you like the most, and why?",
    "Which fashion phase do you like the most, and why?",
    "Which fear do you like the most, and why?",
    "Which festival moment do you like the most, and why?",
    "Which swear word you use do you like the most, and why?",
    "Which song you repeat on loop do you like the most, and why?",
    "Which gift you once got do you like the most, and why?",
    "Which group chat drama do you like the most, and why?",
    "Which habit you hide do you like the most, and why?",
    "Which junk food do you like the most, and why?",
    "Which movie you've rewatched the most do you like the most, and why?",
    "Which nickname do you like the most, and why?",
    "Which outfit you once wore do you like the most, and why?",
    "Which party trick do you like the most, and why?",
    "Which pet name you once gave do you like the most, and why?",
    "Which phobia do you like the most, and why?",
    "Which phone app do you like the most, and why?",
    "Which prank you pulled do you like the most, and why?",
    "Which purchase you regretted do you like the most, and why?",
    "Which recipe you tried do you like the most, and why?",
    "Which reel you made do you like the most, and why?",
    "Which road trip memory do you like the most, and why?",
    "Which dream you still want to fulfill do you like the most, and why?",
    "Which school story do you like the most, and why?",
    "Which screenshot you once took do you like the most, and why?",
    "Which selfie do you like the most, and why?",
    "Which status you once posted do you like the most, and why?",
    "Which superstition do you like the most, and why?",
    "Which talent that's kind of useless do you like the most, and why?",
    "Which teacher moment do you like the most, and why?",
    "Which typo you once sent do you like the most, and why?",
    "Which voice note do you like the most, and why?",
    "Have you ever re-read your own old chats and cringed?",
    "Have you ever screenshotted your own status to show someone else?",
    "Have you ever talked to yourself out loud?",
    "Have you ever laughed at your own joke before anyone else could?",
    "Have you ever danced alone in your room?",
    "Have you ever recorded your own voice and thought it sounded weird?",
    "Have you ever liked your own photo from a second account?",
    "Have you ever tried to cheat on an exam?",
    "Have you ever binged a web series all night before an exam?",
    "Have you ever lied to your family to get pocket money?",
    "Have you ever unfriended a crush and then re-added them?",
    "Have you ever muted a group chat but still read every message?",
    "Have you ever forgotten someone's birthday?",
    "Have you ever thrown away a gift because you didn't like it?",
    "Have you ever read someone's message and never replied?",
    "Have you ever forgotten someone's name and made it awkward?",
    "Have you ever saved someone's number and still never replied?",
    "Have you ever guessed something about someone out loud and been very wrong?",
    "Have you ever watched a rumor about someone spread and stayed silent?",
    "Have you ever made a fake account in someone else's name?",
    "Have you ever taken the blame for someone else's mistake?",
    "Have you ever blocked someone and then unblocked them?",
    "Have you ever accidentally texted the wrong person?",
    "Have you ever deliberately ignored someone?",
    "Have you ever stalked someone's social media?",
    "Have you ever been on your phone the entire time during a movie?",
    "Have you ever made up an excuse to leave a party early?",
    "Have you ever made an excuse to avoid meeting a relative?",
    "Have you ever lied to someone that you were busy?",
    "Have you ever been too scared to confess your feelings to someone?",
    "Have you ever borrowed something and forgotten to return it?",
    "Have you ever texted someone late at night and regretted it?",
    "Have you ever cried at night for no clear reason?",
    "Rate your own cooking skills 1 to 10.",
    "Rate your own dance skills 1 to 10.",
    "Rate your patience level 1 to 10, honestly.",
    "What's the weirdest birthday party you remember?",
    "What's the weirdest childhood memory you remember?",
    "What's the weirdest comment you once made you remember?",
    "What's the weirdest first message from a crush you remember?",
    "What's the weirdest date plan you remember?",
    "What's the weirdest dream you still remember you remember?",
    "What's the weirdest emoji you overuse you remember?",
    "What's the weirdest exam story you remember?",
    "What's the weirdest excuse you remember?",
    "What's the weirdest family drama you remember?",
    "What's the weirdest fashion phase you remember?",
    "What's the weirdest fear you remember?",
    "What's the weirdest festival moment you remember?",
    "What's the weirdest swear word you use you remember?",
    "What's the weirdest song you repeat on loop you remember?",
    "What's the weirdest gift you once got you remember?",
    "What's the weirdest group chat drama you remember?",
    "What's the weirdest habit you hide you remember?",
    "What's the weirdest junk food you remember?",
    "What's the weirdest movie you've rewatched the most you remember?",
    "What's the weirdest nickname you remember?",
    "What's the weirdest outfit you once wore you remember?",
    "What's the weirdest party trick you remember?",
    "What's the weirdest pet name you once gave you remember?",
    "What's the weirdest phobia you remember?",
    "What's the weirdest phone app you remember?",
    "What's the weirdest prank you pulled you remember?",
    "What's the weirdest purchase you regretted you remember?",
    "What's the weirdest recipe you tried you remember?",
    "What's the weirdest reel you made you remember?",
    "What's the weirdest road trip memory you remember?",
    "What's the weirdest dream you still want to fulfill you remember?",
    "What's the weirdest school story you remember?",
    "What's the weirdest screenshot you once took you remember?",
    "What's the weirdest selfie you remember?",
    "What's the weirdest status you once posted you remember?",
    "What's the weirdest superstition you remember?",
    "What's the weirdest talent that's kind of useless you remember?",
    "What's the weirdest teacher moment you remember?",
    "What's the weirdest typo you once sent you remember?",
    "What's the weirdest voice note you remember?",
    "What's the most embarrassing birthday party you've had?",
    "What's the most embarrassing childhood memory you've had?",
    "What's the most embarrassing comment you once made you've had?",
    "What's the most embarrassing first message from a crush you've had?",
    "What's the most embarrassing date plan you've had?",
    "What's the most embarrassing dream you still remember you've had?",
    "What's the most embarrassing emoji you overuse you've had?",
    "What's the most embarrassing exam story you've had?",
    "What's the most embarrassing excuse you've had?",
    "What's the most embarrassing family drama you've had?",
    "What's the most embarrassing fashion phase you've had?",
    "What's the most embarrassing fear you've had?",
    "What's the most embarrassing festival moment you've had?",
    "What's the most embarrassing swear word you use you've had?",
    "What's the most embarrassing song you repeat on loop you've had?",
    "What's the most embarrassing gift you once got you've had?",
    "What's the most embarrassing group chat drama you've had?",
    "What's the most embarrassing habit you hide you've had?",
    "What's the most embarrassing junk food you've had?",
    "What's the most embarrassing movie you've rewatched the most you've had?",
    "What's the most embarrassing nickname you've had?",
    "What's the most embarrassing outfit you once wore you've had?",
    "What's the most embarrassing party trick you've had?",
    "What's the most embarrassing pet name you once gave you've had?",
    "What's the most embarrassing phobia you've had?",
    "What's the most embarrassing phone app you've had?",
    "What's the most embarrassing prank you pulled you've had?",
    "What's the most embarrassing purchase you regretted you've had?",
    "What's the most embarrassing recipe you tried you've had?",
    "What's the most embarrassing reel you made you've had?",
    "What's the most embarrassing road trip memory you've had?",
    "What's the most embarrassing dream you still want to fulfill you've had?",
    "What's the most embarrassing school story you've had?",
    "What's the most embarrassing screenshot you once took you've had?",
    "What's the most embarrassing selfie you've had?",
    "What's the most embarrassing status you once posted you've had?",
    "What's the most embarrassing superstition you've had?",
    "What's the most embarrassing talent that's kind of useless you've had?",
    "What's the most embarrassing teacher moment you've had?",
    "What's the most embarrassing typo you once sent you've had?",
    "What's the most embarrassing voice note you've had?",
    "What's the funniest birthday party you've ever seen or heard of?",
    "What's the funniest childhood memory you've ever seen or heard of?",
    "What's the funniest comment you once made you've ever seen or heard of?",
    "What's the funniest first message from a crush you've ever seen or heard of?",
    "What's the funniest date plan you've ever seen or heard of?",
    "What's the funniest dream you still remember you've ever seen or heard of?",
    "What's the funniest emoji you overuse you've ever seen or heard of?",
    "What's the funniest exam story you've ever seen or heard of?",
    "What's the funniest excuse you've ever seen or heard of?",
    "What's the funniest family drama you've ever seen or heard of?",
    "What's the funniest fashion phase you've ever seen or heard of?",
    "What's the funniest fear you've ever seen or heard of?",
    "What's the funniest festival moment you've ever seen or heard of?",
    "What's the funniest swear word you use you've ever seen or heard of?",
    "What's the funniest song you repeat on loop you've ever seen or heard of?",
    "What's the funniest gift you once got you've ever seen or heard of?",
    "What's the funniest group chat drama you've ever seen or heard of?",
    "What's the funniest habit you hide you've ever seen or heard of?",
    "What's the funniest junk food you've ever seen or heard of?",
    "What's the funniest movie you've rewatched the most you've ever seen or heard of?",
    "What's the funniest nickname you've ever seen or heard of?",
    "What's the funniest outfit you once wore you've ever seen or heard of?",
    "What's the funniest party trick you've ever seen or heard of?",
    "What's the funniest pet name you once gave you've ever seen or heard of?",
    "What's the funniest phobia you've ever seen or heard of?",
    "What's the funniest phone app you've ever seen or heard of?",
    "What's the funniest prank you pulled you've ever seen or heard of?",
    "What's the funniest purchase you regretted you've ever seen or heard of?",
    "What's the funniest recipe you tried you've ever seen or heard of?",
    "What's the funniest reel you made you've ever seen or heard of?",
    "What's the funniest road trip memory you've ever seen or heard of?",
    "What's the funniest dream you still want to fulfill you've ever seen or heard of?",
    "What's the funniest school story you've ever seen or heard of?",
    "What's the funniest screenshot you once took you've ever seen or heard of?",
    "What's the funniest selfie you've ever seen or heard of?",
    "What's the funniest status you once posted you've ever seen or heard of?",
    "What's the funniest superstition you've ever seen or heard of?",
    "What's the funniest talent that's kind of useless you've ever seen or heard of?",
    "What's the funniest teacher moment you've ever seen or heard of?",
    "What's the funniest typo you once sent you've ever seen or heard of?",
    "What's the funniest voice note you've ever seen or heard of?",
    "What's the weirdest birthday party you've ever had?",
    "What's the weirdest childhood memory you've ever had?",
    "What's the weirdest comment you once made you've ever had?",
    "What's the weirdest first message from a crush you've ever had?",
    "What's the weirdest date plan you've ever had?",
    "What's the weirdest dream you still remember you've ever had?",
    "What's the weirdest emoji you overuse you've ever had?",
    "What's the weirdest exam story you've ever had?",
    "What's the weirdest excuse you've ever had?",
    "What's the weirdest family drama you've ever had?",
    "What's the weirdest fashion phase you've ever had?",
    "What's the weirdest fear you've ever had?",
    "What's the weirdest festival moment you've ever had?",
    "What's the weirdest swear word you use you've ever had?",
    "What's the weirdest song you repeat on loop you've ever had?",
    "What's the weirdest gift you once got you've ever had?",
    "What's the weirdest group chat drama you've ever had?",
    "What's the weirdest habit you hide you've ever had?",
    "What's the weirdest junk food you've ever had?",
    "What's the weirdest movie you've rewatched the most you've ever had?",
    "What's the weirdest nickname you've ever had?",
    "What's the weirdest outfit you once wore you've ever had?",
    "What's the weirdest party trick you've ever had?",
    "What's the weirdest pet name you once gave you've ever had?",
    "What's the weirdest phobia you've ever had?",
    "What's the weirdest phone app you've ever had?",
    "What's the weirdest prank you pulled you've ever had?",
    "What's the weirdest purchase you regretted you've ever had?",
    "What's the weirdest recipe you tried you've ever had?",
    "What's the weirdest reel you made you've ever had?",
    "What's the weirdest road trip memory you've ever had?",
    "What's the weirdest dream you still want to fulfill you've ever had?",
    "What's the weirdest school story you've ever had?",
    "What's the weirdest screenshot you once took you've ever had?",
    "What's the weirdest selfie you've ever had?",
    "What's the weirdest status you once posted you've ever had?",
    "What's the weirdest superstition you've ever had?",
    "What's the weirdest talent that's kind of useless you've ever had?",
    "What's the weirdest teacher moment you've ever had?",
    "What's the weirdest typo you once sent you've ever had?",
    "What's the weirdest voice note you've ever had?",
    "Which birthday party do you think is the most overrated?",
    "Which childhood memory do you think is the most overrated?",
    "Which comment you once made do you think is the most overrated?",
    "Which first message from a crush do you think is the most overrated?",
    "Which date plan do you think is the most overrated?",
    "Which dream you still remember do you think is the most overrated?",
    "Which emoji you overuse do you think is the most overrated?",
    "Which exam story do you think is the most overrated?",
    "Which excuse do you think is the most overrated?",
    "Which family drama do you think is the most overrated?",
    "Which fashion phase do you think is the most overrated?",
    "Which fear do you think is the most overrated?",
    "Which festival moment do you think is the most overrated?",
    "Which swear word you use do you think is the most overrated?",
    "Which song you repeat on loop do you think is the most overrated?",
    "Which gift you once got do you think is the most overrated?",
    "Which group chat drama do you think is the most overrated?",
    "Which habit you hide do you think is the most overrated?",
    "Which junk food do you think is the most overrated?",
    "Which movie you've rewatched the most do you think is the most overrated?",
    "Which nickname do you think is the most overrated?",
    "Which outfit you once wore do you think is the most overrated?",
    "Which party trick do you think is the most overrated?",
    "Which pet name you once gave do you think is the most overrated?",
    "Which phobia do you think is the most overrated?",
    "Which phone app do you think is the most overrated?",
    "Which prank you pulled do you think is the most overrated?",
    "Which purchase you regretted do you think is the most overrated?",
    "Which recipe you tried do you think is the most overrated?",
    "Which reel you made do you think is the most overrated?",
    "Which road trip memory do you think is the most overrated?",
    "Which dream you still want to fulfill do you think is the most overrated?",
    "Which school story do you think is the most overrated?",
    "Which screenshot you once took do you think is the most overrated?",
    "Which selfie do you think is the most overrated?",
    "Which status you once posted do you think is the most overrated?",
    "Which superstition do you think is the most overrated?",
    "Which talent that's kind of useless do you think is the most overrated?",
    "Which teacher moment do you think is the most overrated?",
    "Which typo you once sent do you think is the most overrated?",
    "Which voice note do you think is the most overrated?",
    "Be honest — have you ever scrolled someone's social media until 3AM?",
    "Be honest — how many times do you snooze your alarm every day?",
    "Be honest — how many times have you submitted an assignment without reading the material?",
    "Be honest — how many times have you ghosted someone?",
    "Be honest — when did you last lie and say 'I'm fine'?",
    "What's your biggest birthday party?",
    "What's your biggest childhood memory?",
    "What's your biggest comment you once made?",
    "What's your biggest first message from a crush?",
    "What's your biggest date plan?",
    "What's your biggest dream you still remember?",
    "What's your biggest emoji you overuse?",
    "What's your biggest exam story?",
    "What's your biggest excuse?",
    "What's your biggest family drama?",
    "What's your biggest fashion phase?",
    "What's your biggest fear?",
    "What's your biggest festival moment?",
    "What's your biggest swear word you use?",
    "What's your biggest song you repeat on loop?",
    "What's your biggest gift you once got?",
    "What's your biggest group chat drama?",
    "What's your biggest habit you hide?",
    "What's your biggest junk food?",
    "What's your biggest movie you've rewatched the most?",
    "What's your biggest nickname?",
    "What's your biggest outfit you once wore?",
    "What's your biggest party trick?",
    "What's your biggest pet name you once gave?",
    "What's your biggest phobia?",
    "What's your biggest phone app?",
    "What's your biggest prank you pulled?",
    "What's your biggest purchase you regretted?",
    "What's your biggest recipe you tried?",
    "What's your biggest reel you made?",
    "What's your biggest road trip memory?",
    "What's your biggest dream you still want to fulfill?",
    "What's your biggest school story?",
    "What's your biggest screenshot you once took?",
    "What's your biggest selfie?",
    "What's your biggest status you once posted?",
    "What's your biggest superstition?",
    "What's your biggest talent that's kind of useless?",
    "What's your biggest teacher moment?",
    "What's your biggest typo you once sent?",
    "What's your biggest voice note?",
    "What's the most random birthday party of your life?",
    "What's the most random childhood memory of your life?",
    "What's the most random comment you once made of your life?",
    "What's the most random first message from a crush of your life?",
    "What's the most random date plan of your life?",
    "What's the most random dream you still remember of your life?",
    "What's the most random emoji you overuse of your life?",
    "What's the most random exam story of your life?",
    "What's the most random excuse of your life?",
    "What's the most random family drama of your life?",
    "What's the most random fashion phase of your life?",
    "What's the most random fear of your life?",
    "What's the most random festival moment of your life?",
    "What's the most random swear word you use of your life?",
    "What's the most random song you repeat on loop of your life?",
    "What's the most random gift you once got of your life?",
    "What's the most random group chat drama of your life?",
    "What's the most random habit you hide of your life?",
    "What's the most random junk food of your life?",
    "What's the most random movie you've rewatched the most of your life?",
    "What's the most random nickname of your life?",
    "What's the most random outfit you once wore of your life?",
    "What's the most random party trick of your life?",
    "What's the most random pet name you once gave of your life?",
    "What's the most random phobia of your life?",
    "What's the most random phone app of your life?",
    "What's the most random prank you pulled of your life?",
    "What's the most random purchase you regretted of your life?",
    "What's the most random recipe you tried of your life?",
    "What's the most random reel you made of your life?",
    "What's the most random road trip memory of your life?",
    "What's the most random dream you still want to fulfill of your life?",
    "What's the most random school story of your life?",
    "What's the most random screenshot you once took of your life?",
    "What's the most random selfie of your life?",
    "What's the most random status you once posted of your life?",
    "What's the most random superstition of your life?",
    "What's the most random talent that's kind of useless of your life?",
    "What's the most random teacher moment of your life?",
    "What's the most random typo you once sent of your life?",
    "What's the most random voice note of your life?",
    "What's the last thing you Googled that you'd never say out loud?",
    "What's a compliment you got once that you still think about?",
    "What's the pettiest reason you've ever stopped talking to someone?",
    "What's a small lie you tell almost every week?",
    "If your search history became a documentary, what would the title be?",
    "What's the most money you've ever spent on something completely unnecessary?",
    "What's a habit your friends secretly find annoying but never mention?",
    "What's the worst advice you've ever given someone with total confidence?",
    "What's a rule you break constantly without even feeling guilty?",
    "What's the most dramatic thing you've done over something small?",
    "What's a text you drafted but never had the guts to send?",
    "What's your go-to excuse for showing up late?",
    "What's something you pretend to understand but actually don't?",
    "What's the weirdest thing you've done to fall asleep?",
    "Who in this group would you trust with your phone unlocked for a day?",
    "What's the last thing that made you ugly-cry laughing?",
    "What's a fear you've never told anyone about?",
    "What's the most useless talent you're weirdly proud of?",
    "What's a food combo you love that everyone judges you for?",
    "What's the last white lie you told a family member?",
    "What's something you do when you're alone that you'd never admit to?",
    "What's the most embarrassing thing saved in your notes app right now?",
    "What's a childhood belief you were way too old to still have?",
    "What's the last thing you apologized for that you didn't actually mean?",
    "What's a song you're embarrassed to admit you know every word to?",
    "What's the longest you've gone without replying to someone on purpose?",
    "What's something you're low-key competitive about, even if it doesn't matter?",
    "What's a compliment you find really hard to accept?",
    "What's the last thing you lied about on a form or application?",
    "What's a nickname you secretly like but pretend to hate?",
]

DARES = [
    "Walk around for 1 minute balancing a book on your head.",
    "Stare at yourself in the mirror for 1 minute without laughing.",
    "Stand on one leg for 1 minute (balance test) and report the result.",
    "Do 10 jumping jacks and send video/photo proof.",
    "Hold a plank position for 30 seconds.",
    "Do 5 star jumps back to back without stopping.",
    "If you had to give up cleanliness forever, how would that feel — describe it in one line.",
    "If you had to give up cooking skills forever, how would that feel — describe it in one line.",
    "If you had to give up cricket/football knowledge forever, how would that feel — describe it in one line.",
    "If you had to give up daily screen time forever, how would that feel — describe it in one line.",
    "If you had to give up dance skills forever, how would that feel — describe it in one line.",
    "If you had to give up fashion sense forever, how would that feel — describe it in one line.",
    "If you had to give up favourite influencer forever, how would that feel — describe it in one line.",
    "If you had to give up gaming skills forever, how would that feel — describe it in one line.",
    "If you had to give up general knowledge forever, how would that feel — describe it in one line.",
    "If you had to give up handwriting forever, how would that feel — describe it in one line.",
    "If you had to give up memory power forever, how would that feel — describe it in one line.",
    "If you had to give up navigation skills forever, how would that feel — describe it in one line.",
    "If you had to give up patience level forever, how would that feel — describe it in one line.",
    "If you had to give up photography skills forever, how would that feel — describe it in one line.",
    "If you had to give up sense of humor forever, how would that feel — describe it in one line.",
    "If you had to give up singing skills forever, how would that feel — describe it in one line.",
    "If you had to give up sleep schedule forever, how would that feel — describe it in one line.",
    "If you had to give up texting speed forever, how would that feel — describe it in one line.",
    "If you had to give up time management forever, how would that feel — describe it in one line.",
    "If you had to give up typing speed forever, how would that feel — describe it in one line.",
    "Write your next message without using any vowels (a,e,i,o,u).",
    "Write your next message with no spaces.",
    "Describe your whole day in exactly 5 words for your next message.",
    "Write your next message in emojis only, not a single word.",
    "Type your next message using only numbers to describe your feeling.",
    "Build your next message entirely from your keyboard's autosuggest (3 taps).",
    "Write your next message backwards.",
    "For the next 10 minutes, you must use the word 'bestie' in every message.",
    "For the next 10 minutes, you must use the word 'honestly' in every message.",
    "For the next 10 minutes, you must use the word 'literally' in every message.",
    "For the next 10 minutes, you must use the word 'obviously' in every message.",
    "For the next 10 minutes, you must use the word 'seriously' in every message.",
    "Write your next 2 messages only as questions.",
    "Talk only in rhyming words for your next 2 messages.",
    "Write your next 3 messages in CAPITAL LETTERS.",
    "You must use the word 'literally' in each of your next 3 messages.",
    "Start every sentence with 'dude' for your next 3 messages.",
    "You can't use the word 'I' in your next 3 messages.",
    "For the next 3 minutes, you must use the word 'bestie' in every message.",
    "For the next 3 minutes, you must use the word 'honestly' in every message.",
    "For the next 3 minutes, you must use the word 'literally' in every message.",
    "For the next 3 minutes, you must use the word 'obviously' in every message.",
    "For the next 3 minutes, you must use the word 'seriously' in every message.",
    "Set your WhatsApp status to 'About to think of something big' for the next 30 minutes.",
    "For the next 5 minutes, sign your own name at the end of every message.",
    "For the next 5 minutes, you must use the word 'bestie' in every message.",
    "For the next 5 minutes, you must use the word 'honestly' in every message.",
    "For the next 5 minutes, you must use the word 'literally' in every message.",
    "For the next 5 minutes, you must use the word 'obviously' in every message.",
    "For the next 5 minutes, you must use the word 'seriously' in every message.",
    "Change your DP to a random emoji or cartoon for 10 minutes.",
    "Send a screenshot of today's Spotify/YouTube 'recently played'.",
    "Rate today's energy level 1-10 and describe it with a gif.",
    "Describe today's mood using just a song name, no explanation.",
    "Without looking down, guess today's outfit color, then check and share the result.",
    "Send a selfie of today's outfit.",
    "Share today's step count or activity, if you track it.",
    "Send a photo of your bed exactly as you left it this morning.",
    "Try writing your next message using formal, old-fashioned-sounding words instead of casual slang.",
    "Write a funny 2-line memory about your best friend.",
    "Write a funny 2-line memory about your best trip.",
    "Write a funny 2-line memory about your childhood game.",
    "Write a funny 2-line memory about your college day.",
    "Write a funny 2-line memory about your comfort food.",
    "Share your current battery % and charging status.",
    "Describe your current mood with a gif or emoji and share the result.",
    "Screenshot and send your current phone wallpaper.",
    "Write a funny 2-line memory about your dream job.",
    "Write a funny 2-line memory about your dream vacation.",
    "Write a funny 2-line memory about your exam stress.",
    "Share your favourite tea/coffee order.",
    "Name your favourite childhood cartoon character.",
    "Hum your favourite childhood show's theme song for 5 seconds (voice note).",
    "Name your favourite childhood snack and share one memory of it.",
    "Find your favourite childhood toy/item and send a photo, if you still have it.",
    "Write a funny 2-line memory about your favourite dessert.",
    "Say your favourite movie dialogue in a random accent and send it as a voice note.",
    "Share your favourite festival and one memory from it.",
    "Write a funny 2-line memory about your favourite song.",
    "Write a funny 2-line memory about your favourite food.",
    "Write a funny 2-line memory about your favourite movie.",
    "Write your favourite quote without saying who said it.",
    "Write a funny 2-line memory about your favourite season.",
    "Write a funny 2-line memory about your favourite show.",
    "Write a funny 2-line memory about your favourite sport.",
    "Write a funny 2-line memory about your first phone.",
    "Write a funny 2-line memory about your gym/workout.",
    "Write a funny 2-line memory about your hobby.",
    "Look up today's horoscope for your sign and read it out loud.",
    "Share your zodiac sign's lucky number for today and make up a funny reason for it.",
    "Describe tomorrow's plan in exactly 3 words.",
    "Write a funny 2-line memory about your last gift.",
    "Write a funny 2-line memory about your last purchase.",
    "Write a funny 2-line memory about your morning routine.",
    "Write a funny 2-line memory about your music taste.",
    "Write a funny 2-line memory about your first pet.",
    "Change your home screen wallpaper to something funny for 1 hour.",
    "Describe your phone lock style — number of steps only, nothing more.",
    "Set your profile bio to 'Currently confused' for 10 minutes.",
    "Reveal your most embarrassing nickname to the group.",
    "Find and send the oldest screenshot you've saved.",
    "Screenshot and send your most recent starred/saved message (a safe one).",
    "Share your most-used app and its screen time.",
    "Write a funny 2-line memory about your school teacher.",
    "Write a funny 2-line memory about your weekend plan.",
    "Name 3 things on today's to-do list you still haven't done.",
    "Send a photo of today's breakfast or lunch.",
    "Rate today's outfit in one word.",
    "Record a 15-second voice note ranting about your best friend.",
    "Find and send a photo related to your best friend.",
    "Text your best friend 'I have something to tell you' and describe their reaction.",
    "Record a 15-second voice note ranting about your best trip.",
    "Find and send a photo related to your best trip.",
    "Share the next event on your calendar.",
    "Describe the last item in your camera roll's screenshot folder (a safe one).",
    "Record a 15-second voice note ranting about your childhood game.",
    "Find and send a photo related to your childhood game.",
    "Tell one truth and one lie about your cleanliness — let the group guess which is which.",
    "Describe your cleanliness using 3 emojis.",
    "Record a 15-second voice note ranting about your college day.",
    "Find and send a photo related to your college day.",
    "Record a 15-second voice note ranting about your comfort food.",
    "Find and send a photo related to your comfort food.",
    "Tell one truth and one lie about your cooking skills — let the group guess which is which.",
    "Describe your cooking skills using 3 emojis.",
    "Tell one truth and one lie about your cricket/football knowledge — let the group guess which is which.",
    "Describe your cricket/football knowledge using 3 emojis.",
    "Tell one truth and one lie about your daily screen time — let the group guess which is which.",
    "Describe your daily screen time using 3 emojis.",
    "Tell one truth and one lie about your dance skills — let the group guess which is which.",
    "Describe your dance skills using 3 emojis.",
    "Record a 15-second voice note ranting about your dream job.",
    "Find and send a photo related to your dream job.",
    "Record a 15-second voice note ranting about your dream vacation.",
    "Find and send a photo related to your dream vacation.",
    "Record a 15-second voice note ranting about your exam stress.",
    "Find and send a photo related to your exam stress.",
    "Tell one truth and one lie about your fashion sense — let the group guess which is which.",
    "Describe your fashion sense using 3 emojis.",
    "Record a 15-second voice note ranting about your favourite dessert.",
    "Find and send a photo related to your favourite dessert.",
    "Record a 15-second voice note ranting about your favourite song.",
    "Find and send a photo related to your favourite song.",
    "Tell one truth and one lie about your favourite influencer — let the group guess which is which.",
    "Describe your favourite influencer using 3 emojis.",
    "Record a 15-second voice note ranting about your favourite food.",
    "Find and send a photo related to your favourite food.",
    "Record a 15-second voice note ranting about your favourite movie.",
    "Find and send a photo related to your favourite movie.",
    "Record a 15-second voice note ranting about your favourite season.",
    "Find and send a photo related to your favourite season.",
    "Record a 15-second voice note ranting about your favourite show.",
    "Find and send a photo related to your favourite show.",
    "Record a 15-second voice note ranting about your favourite sport.",
    "Find and send a photo related to your favourite sport.",
    "Record a 15-second voice note ranting about your first phone.",
    "Find and send a photo related to your first phone.",
    "Send a photo of the inside of your fridge.",
    "Tell one truth and one lie about your gaming skills — let the group guess which is which.",
    "Describe your gaming skills using 3 emojis.",
    "Tell one truth and one lie about your general knowledge — let the group guess which is which.",
    "Describe your general knowledge using 3 emojis.",
    "Name the oldest piece of furniture in your house.",
    "Make a weird food combo from what's in your kitchen, eat it, and react.",
    "Send a photo of the view from your window.",
    "Take 3 selfies standing in 3 different spots in your house.",
    "Record a 15-second voice note ranting about your gym/workout.",
    "Find and send a photo related to your gym/workout.",
    "Touch your ear with one hand and your nose with the opposite hand, 3 times fast.",
    "Tell one truth and one lie about your handwriting — let the group guess which is which.",
    "Describe your handwriting using 3 emojis.",
    "Record a 15-second voice note ranting about your hobby.",
    "Find and send a photo related to your hobby.",
    "Crab-walk from one corner of your room to the other.",
    "Do a 5-second robot dance in your room and describe how it went.",
    "Share your last 3 typed-but-unsent message drafts, if you have any.",
    "Record a 15-second voice note ranting about your last gift.",
    "Find and send a photo related to your last gift.",
    "Record a 15-second voice note ranting about your last purchase.",
    "Find and send a photo related to your last purchase.",
    "Tell one truth and one lie about your memory power — let the group guess which is which.",
    "Describe your memory power using 3 emojis.",
    "Record a 15-second voice note ranting about your morning routine.",
    "Find and send a photo related to your morning routine.",
    "Record a 15-second voice note ranting about your music taste.",
    "Find and send a photo related to your music taste.",
    "Tell one truth and one lie about your navigation skills — let the group guess which is which.",
    "Describe your navigation skills using 3 emojis.",
    "Share the oldest note in your notes app.",
    "Ask a parent or sibling 'what's the best thing about me?' and share their reply.",
    "Tell one truth and one lie about your patience level — let the group guess which is which.",
    "Describe your patience level using 3 emojis.",
    "Record a 15-second voice note ranting about your first pet.",
    "Find and send a photo related to your first pet.",
    "Write an Instagram bio for your pet, plant, or any object, from their perspective.",
    "Send a screenshot of your phone's battery percentage.",
    "Open the oldest app on your phone and send a screenshot.",
    "Build a sentence from 3 random autofill suggestions on your phone.",
    "Say what's taking up the most storage on your phone.",
    "Tell one truth and one lie about your photography skills — let the group guess which is which.",
    "Describe your photography skills using 3 emojis.",
    "List everything currently in your pocket or bag.",
    "Send a photo of the messiest corner of your room.",
    "Turn off your room lights and send a selfie, if you're comfortable with that.",
    "Record a 15-second voice note ranting about your school teacher.",
    "Find and send a photo related to your school teacher.",
    "Tell one truth and one lie about your sense of humor — let the group guess which is which.",
    "Describe your sense of humor using 3 emojis.",
    "Tell one truth and one lie about your singing skills — let the group guess which is which.",
    "Describe your singing skills using 3 emojis.",
    "Tell one truth and one lie about your sleep schedule — let the group guess which is which.",
    "Describe your sleep schedule using 3 emojis.",
    "Tell one truth and one lie about your texting speed — let the group guess which is which.",
    "Describe your texting speed using 3 emojis.",
    "Tell one truth and one lie about your time management — let the group guess which is which.",
    "Describe your time management using 3 emojis.",
    "Tell one truth and one lie about your typing speed — let the group guess which is which.",
    "Describe your typing speed using 3 emojis.",
    "Record a 15-second voice note ranting about your weekend plan.",
    "Find and send a photo related to your weekend plan.",
    "Send a screenshot of your screen time report, no hiding anything.",
    "Sign your name with your eyes closed and send a photo of it.",
    "Send the 5th photo in your gallery, no cheating.",
    "Write 'Aira is the best' in your handwriting and send a photo.",
    "Write your name with your non-dominant hand and send a photo.",
    "Write the poster tagline for the movie of your life.",
    "Shuffle your playlist and share the name of whatever plays first.",
    "Send a photo of your most-worn shoes.",
    "Send a photo of your study table or desk exactly as it looks right now.",
    "Choose between Beach and mountains, and give your reason.",
    "Choose between Bollywood and Hollywood, and give your reason.",
    "Choose between Books and movies, and give your reason.",
    "Choose between Cats and dogs, and give your reason.",
    "Choose between Chai and coffee, and give your reason.",
    "Choose between City life and village life, and give your reason.",
    "Choose between Cricket and football, and give your reason.",
    "Choose between Early riser and night owl, and give your reason.",
    "Make up a 'fake breaking news' headline about something small from your life.",
    "Do a fake movie-trailer voice-over based on your own life.",
    "Drink a glass of water in one breath and describe how it felt.",
    "Change your WhatsApp/Telegram name to something funny for one minute.",
    "In one minute, type as many country names as you can remember.",
    "Give yourself a pretend interview, as if you were famous.",
    "Do one push-up and honestly say how hard it was, even without a camera.",
    "Try a random dance move and describe it in words.",
    "Share a random fact about your city.",
    "Pick up a random object near you and take a creative photo of it.",
    "Say a random word and build a 3-line story from it.",
    "Say a tongue-twister without stumbling and send it as a voice note.",
    "Choose between Gaming and reading, and give your reason.",
    "Search your own name on Google and share the first result.",
    "Pick a group member and write a short rhyme/poem for them.",
    "Publicly name one good quality of a group member.",
    "Give a group member a genuine compliment you've never given them before.",
    "Make up a short riddle for the group off the top of your head.",
    "Make up a short cheer or slogan for the group's name.",
    "Rate your cleanliness 1-10 to the group and explain why.",
    "Rate your cooking skills 1-10 to the group and explain why.",
    "Rate your cricket/football knowledge 1-10 to the group and explain why.",
    "Rate your daily screen time 1-10 to the group and explain why.",
    "Rate your dance skills 1-10 to the group and explain why.",
    "Rate your fashion sense 1-10 to the group and explain why.",
    "Rate your favourite influencer 1-10 to the group and explain why.",
    "Rate your gaming skills 1-10 to the group and explain why.",
    "Rate your general knowledge 1-10 to the group and explain why.",
    "Rate your handwriting 1-10 to the group and explain why.",
    "Rate your memory power 1-10 to the group and explain why.",
    "Rate your navigation skills 1-10 to the group and explain why.",
    "Rate your patience level 1-10 to the group and explain why.",
    "Rate your photography skills 1-10 to the group and explain why.",
    "Rate your sense of humor 1-10 to the group and explain why.",
    "Rate your singing skills 1-10 to the group and explain why.",
    "Rate your sleep schedule 1-10 to the group and explain why.",
    "Rate your texting speed 1-10 to the group and explain why.",
    "Rate your time management 1-10 to the group and explain why.",
    "Rate your typing speed 1-10 to the group and explain why.",
    "Recommend your best friend to the group in one line.",
    "Recommend your best trip to the group in one line.",
    "Recommend your childhood game to the group in one line.",
    "Recommend your college day to the group in one line.",
    "Recommend your comfort food to the group in one line.",
    "Recommend your dream job to the group in one line.",
    "Recommend your dream vacation to the group in one line.",
    "Tell the group about a hidden talent you've never shown.",
    "Recommend your exam stress to the group in one line.",
    "Recommend your favourite dessert to the group in one line.",
    "Recommend your favourite song to the group in one line.",
    "Recommend your favourite food to the group in one line.",
    "Recommend your favourite movie to the group in one line.",
    "Recommend your favourite season to the group in one line.",
    "Recommend your favourite show to the group in one line.",
    "Recommend your favourite sport to the group in one line.",
    "Recommend your first phone to the group in one line.",
    "Recommend your gym/workout to the group in one line.",
    "Recommend your hobby to the group in one line.",
    "Recommend your last gift to the group in one line.",
    "Recommend your last purchase to the group in one line.",
    "Recommend your morning routine to the group in one line.",
    "Recommend your music taste to the group in one line.",
    "Recommend your first pet to the group in one line.",
    "Recommend your school teacher to the group in one line.",
    "Recommend your weekend plan to the group in one line.",
    "Tell the group what your favourite best friend is, and why.",
    "Tell the group what your favourite best trip is, and why.",
    "Tell the group what your favourite childhood game is, and why.",
    "Tell the group what your favourite college day is, and why.",
    "Tell the group what your favourite comfort food is, and why.",
    "Tell the group what your favourite dream job is, and why.",
    "Tell the group what your favourite dream vacation is, and why.",
    "Tell the group what your favourite exam stress is, and why.",
    "Tell the group what your favourite dessert is, and why.",
    "Tell the group what your favourite gaana is, and why.",
    "Tell the group what your favourite khana is, and why.",
    "Tell the group what your favourite movie is, and why.",
    "Tell the group what your favourite season is, and why.",
    "Tell the group what your favourite show is, and why.",
    "Tell the group what your favourite sport is, and why.",
    "Tell the group what your favourite first phone is, and why.",
    "Tell the group what your favourite gym/workout is, and why.",
    "Tell the group what your favourite hobby is, and why.",
    "Tell the group what your favourite last gift is, and why.",
    "Tell the group what your favourite last purchase is, and why.",
    "Tell the group what your favourite morning routine is, and why.",
    "Tell the group what your favourite music taste is, and why.",
    "Tell the group what your favourite first pet is, and why.",
    "Tell the group what your favourite school teacher is, and why.",
    "Tell the group what your favourite weekend plan is, and why.",
    "Ask someone in the group for random advice and promise to follow it.",
    "Tag the least active member in the group and ask them a question.",
    "Write a thank-you message to the member who joined the group first.",
    "Choose between Indoor games and outdoor games, and give your reason.",
    "Choose between Instagram and YouTube, and give your reason.",
    "Sell a random item like a TV shopping host would (write it as text).",
    "Type out 2 lines of any Bollywood song, no music.",
    "Ask someone to guess one of your talents.",
    "Ask someone to give you a nickname and use it for the next 10 minutes.",
    "Ask a member to send a 30-second voice note about their favourite topic.",
    "Message an old friend 'remember that day?' and share their reply.",
    "Send 'Good morning' to a random contact — even if it's night — and share their reaction.",
    "Ask someone 'if I were an animal, which one would I be?' and share their answer.",
    "Choose between Morning and night, and give your reason.",
    "Choose between Pizza and burger, and give your reason.",
    "Choose between Solo travel and group travel, and give your reason.",
    "Choose between Summer and winter, and give your reason.",
    "Choose between Sweet and spicy, and give your reason.",
    "Choose between Tea and milk, and give your reason.",
    "Choose between Texting and calling, and give your reason.",
    "Choose between Trekking and road trip, and give your reason.",
    "Send a voice note singing your favourite anime/cartoon theme song.",
    "Send a voice note saying 'Hello group members' in a robot voice.",
    "Send a voice note naming as many fruits as you can in 10 seconds.",
    "Send a voice note singing your favourite song opera-style.",
    "Send a voice note saying your favourite movie dialogue in a dramatic tone.",
    "Send a voice note reading out a day's headlines like a news anchor.",
    "Send a voice note counting to 15 as fast as you can, no pauses.",
    "Send a voice note telling a short story in a classic 'Once upon a time' style.",
    "Send a voice note making up a fake ad for a random object.",
    "Send a voice note wishing yourself happy birthday in the third person.",
    "Send a voice note copying a cartoon character's voice.",
    "Send a voice note describing yourself eating, like a sports commentator.",
    "Send a voice note giving the weather report like a dead-serious newsreader.",
    "Send a voice note whispering a fake/funny 'secret reveal'.",
    "Say your name backwards 5 times fast in a voice note.",
    "Choose between Winter vacation and summer vacation, and give your reason.",
    "Send a 10-second voice note about your best friend without pausing.",
    "Send a 10-second voice note about your best trip without pausing.",
    "Send a 10-second voice note about your childhood game without pausing.",
    "Send a 10-second voice note about your college day without pausing.",
    "Send a 10-second voice note about your comfort food without pausing.",
    "Send a 10-second voice note about your dream job without pausing.",
    "Send a 10-second voice note about your dream vacation without pausing.",
    "Send a 10-second voice note about your exam stress without pausing.",
    "Send a 10-second voice note about your favourite dessert without pausing.",
    "Send a 10-second voice note about your favourite song without pausing.",
    "Send a 10-second voice note about your favourite food without pausing.",
    "Send a 10-second voice note about your favourite movie without pausing.",
    "Send a 10-second voice note about your favourite season without pausing.",
    "Send a 10-second voice note about your favourite show without pausing.",
    "Send a 10-second voice note about your favourite sport without pausing.",
    "Send a 10-second voice note about your first phone without pausing.",
    "Send a 10-second voice note about your gym/workout without pausing.",
    "Send a 10-second voice note about your hobby without pausing.",
    "Send a 10-second voice note about your last gift without pausing.",
    "Send a 10-second voice note about your last purchase without pausing.",
    "Send a 10-second voice note about your morning routine without pausing.",
    "Send a 10-second voice note about your music taste without pausing.",
    "Send a 10-second voice note about your first pet without pausing.",
    "Send a 10-second voice note about your school teacher without pausing.",
    "Send a 10-second voice note about your weekend plan without pausing.",
    "Text the last person you called and ask them a completely random question.",
    "Do your best impression of someone in this group — let them guess who it is.",
    "Speak only in questions for the next 3 messages.",
    "Send a voice note pretending to give a weather report from inside your fridge.",
    "Let the group pick your profile picture for the next 10 minutes.",
    "Type your next message using only your phone's predictive text.",
    "Do 15 seconds of the most dramatic slow-motion walk you can manage.",
    "Describe your day so far using only movie titles.",
    "Send a photo of the last thing you ate.",
    "Talk in a fake accent for your next 3 messages and don't explain why.",
    "Write a one-line horror story using only emojis.",
    "Give a dramatic reading of your last text message like it's Shakespeare.",
    "Do your best robot voice and announce what you're doing right now.",
    "Send the group a 10-second video of you doing literally anything mundane.",
    "Reply to the next 3 messages using only gifs or stickers.",
    "Try to lick your elbow and report back on how it went.",
    "Send a voice note singing the alphabet backwards.",
    "Draw a quick doodle of the person above you in this chat and send it.",
    "Do 10 seconds of interpretive dance representing your current mood.",
    "Let someone else in the group send your next status update.",
    "Recite the closest thing near you like it's a dramatic monologue.",
    "Send your most recent typing-fail screenshot, if you have one.",
    "Pretend to be a game show host and introduce yourself to the group.",
    "Whisper-sing your favourite chorus into a voice note.",
    "Message someone 'you up?' completely out of context and share their reply.",
]

WYR_PAIRS = [
    ("1 crore rupees right now", "10 crore rupees 10 years from now"),
    ("Being invisible for a day", "Being super strong for a day"),
    ("A permanent fear of being alone", "A permanent fear of failure"),
    ("A permanent fear of being alone", "A permanent fear of flying"),
    ("A permanent fear of being alone", "A permanent fear of being judged"),
    ("A permanent fear of being alone", "A permanent fear of needles"),
    ("Being rich but alone", "Being poor but surrounded by friends"),
    ("A permanent fear of the dark", "A permanent fear of big animals"),
    ("A permanent fear of the dark", "A permanent fear of ghosts"),
    ("A permanent fear of the dark", "A permanent fear of deep water"),
    ("A permanent fear of the dark", "A permanent fear of an unknown future"),
    ("Getting a device that reads your own mind", "Getting a device that shows you your future"),
    ("Meeting your favourite actor in real life for a day", "Getting 1 lakh rupees right now"),
    ("Never being able to hear your favourite song again", "Never being able to watch your favourite movie again"),
    ("Telling your crush absolutely everything", "Never being able to tell anyone anything"),
    ("Learning a friend's secret that would upset you", "Never finding out"),
    ("Being able to talk to your pet", "Being able to talk to your plants"),
    ("Getting your dream job but for low pay", "A boring job but a lot of money"),
    ("Finding out spoilers for your favourite show in advance", "Never being able to watch the finale"),
    ("Getting the power of astral projection", "Getting the power of elasticity"),
    ("Getting the power of astral projection", "Getting the power of energy blasts"),
    ("Getting the power of astral projection", "Getting the power of invisibility"),
    ("Getting the power of astral projection", "Getting the power of super strength"),
    ("Being an expert at stargazing/astronomy", "Being an expert at boxing"),
    ("Being an expert at stargazing/astronomy", "Being an expert at calligraphy"),
    ("Being an expert at stargazing/astronomy", "Being an expert at content creation"),
    ("Being an expert at stargazing/astronomy", "Being an expert at cosplay"),
    ("Being an expert at stargazing/astronomy", "Being an expert at fishing"),
    ("A permanent fear of big animals", "A permanent fear of tight spaces"),
    ("A permanent fear of big animals", "A permanent fear of public speaking"),
    ("A permanent fear of big animals", "A permanent fear of an unknown future"),
    ("Being an expert at badminton", "Being an expert at dancing"),
    ("Being an expert at badminton", "Being an expert at fishing"),
    ("Being an expert at badminton", "Being an expert at painting"),
    ("Being an expert at badminton", "Being an expert at singing"),
    ("Being an expert at badminton", "Being an expert at skating"),
    ("Being an expert at badminton", "Being an expert at volleyball"),
    ("A permanent fear of enclosed spaces", "A permanent fear of public speaking"),
    ("A permanent fear of enclosed spaces", "A permanent fear of ghosts"),
    ("A permanent fear of enclosed spaces", "A permanent fear of flying"),
    ("A permanent fear of enclosed spaces", "A permanent fear of snakes"),
    ("Being an expert at basketball", "Being an expert at coding"),
    ("Being an expert at basketball", "Being an expert at content creation"),
    ("Being an expert at basketball", "Being an expert at cosplay"),
    ("Being an expert at basketball", "Being an expert at Cricket"),
    ("Being an expert at basketball", "Being an expert at Football"),
    ("Being an expert at basketball", "Being an expert at the gym"),
    ("A beach vacation", "A mountain vacation"),
    ("A permanent fear of public speaking", "A permanent fear of clowns"),
    ("A permanent fear of public speaking", "A permanent fear of snakes"),
    ("A permanent fear of public speaking", "A permanent fear of heights"),
    ("A permanent fear of ghosts", "A permanent fear of deep water"),
    ("1 week with no internet", "1 week without leaving the house"),
    ("Living with no music", "Living with no movies"),
    ("1 month with no phone", "1 month with no AC/fan"),
    ("Staying active for 24 hours with no sleep", "Being able to sleep 36 hours straight with zero guilt"),
    ("Being an expert at blogging", "Being an expert at calligraphy"),
    ("Being an expert at blogging", "Being an expert at coding"),
    ("Being an expert at blogging", "Being an expert at content creation"),
    ("Being an expert at blogging", "Being an expert at Football"),
    ("Being an expert at blogging", "Being an expert at pottery"),
    ("Being an expert at boxing", "Being an expert at calligraphy"),
    ("Being an expert at boxing", "Being an expert at dancing"),
    ("Being an expert at boxing", "Being an expert at fishing"),
    ("Being an expert at boxing", "Being an expert at painting"),
    ("Being an expert at boxing", "Being an expert at skating"),
    ("Being an expert at boxing", "Being an expert at volleyball"),
    ("Being an expert at calligraphy", "Being an expert at content creation"),
    ("Being an expert at calligraphy", "Being an expert at cosplay"),
    ("Being an expert at calligraphy", "Being an expert at fishing"),
    ("Being an expert at calligraphy", "Being an expert at pottery"),
    ("Being an expert at calligraphy", "Being an expert at skating"),
    ("Drinking chai", "Drinking coffee"),
    ("Being an expert at chess", "Being an expert at Cricket"),
    ("Being an expert at chess", "Being an expert at cycling"),
    ("Being an expert at chess", "Being an expert at gardening"),
    ("Being an expert at chess", "Being an expert at the gym"),
    ("Being an expert at chess", "Being an expert at trekking"),
    ("Being an expert at chess", "Being an expert at yoga"),
    ("A permanent fear of tight spaces", "A permanent fear of the dentist"),
    ("A permanent fear of tight spaces", "A permanent fear of public speaking"),
    ("A permanent fear of tight spaces", "A permanent fear of an unknown future"),
    ("Living in the city", "Living in a village"),
    ("A permanent fear of clowns", "A permanent fear of flying"),
    ("A permanent fear of clowns", "A permanent fear of snakes"),
    ("Being an expert at coding", "Being an expert at content creation"),
    ("Being an expert at coding", "Being an expert at Cricket"),
    ("Being an expert at coding", "Being an expert at Football"),
    ("Being an expert at coding", "Being an expert at pottery"),
    ("Being an expert at content creation", "Being an expert at cosplay"),
    ("Being an expert at content creation", "Being an expert at Cricket"),
    ("Getting the power of fire control", "Getting the power of immortality"),
    ("Getting the power of fire control", "Getting the power of luck manipulation"),
    ("Getting the power of fire control", "Getting the power of super intelligence"),
    ("Getting the power of fire control", "Getting the power of talking to animals"),
    ("Getting the power of fire control", "Getting the power of weather control"),
    ("Getting the power of fire control", "Getting the power of X-ray vision"),
    ("Getting the power of water control", "Getting the power of dream walking"),
    ("Getting the power of water control", "Getting the power of luck manipulation"),
    ("Getting the power of water control", "Getting the power of super intelligence"),
    ("Getting the power of water control", "Getting the power of talking to animals"),
    ("Getting the power of water control", "Getting the power of weather control"),
    ("Being an expert at cooking", "Being an expert at cycling"),
    ("Being an expert at cooking", "Being an expert at gaming"),
    ("Being an expert at cooking", "Being an expert at photography"),
    ("Being an expert at cooking", "Being an expert at reading"),
    ("Being an expert at cooking", "Being an expert at singing"),
    ("Being an expert at cooking", "Being an expert at swimming"),
    ("Being an expert at cosplay", "Being an expert at pottery"),
    ("Playing cricket", "Playing football"),
    ("Being an expert at Cricket", "Being an expert at Football"),
    ("Being an expert at Cricket", "Being an expert at the gym"),
    ("Being an expert at cycling", "Being an expert at gardening"),
    ("Being an expert at cycling", "Being an expert at photography"),
    ("Being an expert at cycling", "Being an expert at swimming"),
    ("Being an expert at cycling", "Being an expert at trekking"),
    ("Being an expert at cycling", "Being an expert at yoga"),
    ("Being an expert at dancing", "Being an expert at gaming"),
    ("Being an expert at dancing", "Being an expert at painting"),
    ("Being an expert at dancing", "Being an expert at volleyball"),
    ("A permanent fear of the dentist", "A permanent fear of loud noises"),
    ("A permanent fear of the dentist", "A permanent fear of needles"),
    ("A permanent fear of the dentist", "A permanent fear of public speaking"),
    ("Getting the power of dream walking", "Getting the power of echolocation"),
    ("Getting the power of dream walking", "Getting the power of luck manipulation"),
    ("Getting the power of dream walking", "Getting the power of night vision"),
    ("Getting the power of dream walking", "Getting the power of super jumping"),
    ("Getting the power of duplication", "Getting the power of elasticity"),
    ("Getting the power of duplication", "Getting the power of energy blasts"),
    ("Getting the power of duplication", "Getting the power of invisibility"),
    ("Getting the power of duplication", "Getting the power of night vision"),
    ("Getting the power of duplication", "Getting the power of super jumping"),
    ("Getting the power of duplication", "Getting the power of super strength"),
    ("Getting the power of echolocation", "Getting the power of immortality"),
    ("Getting the power of echolocation", "Getting the power of invulnerability"),
    ("Getting the power of echolocation", "Getting the power of luck manipulation"),
    ("Getting the power of echolocation", "Getting the power of night vision"),
    ("Getting the power of echolocation", "Getting the power of super jumping"),
    ("Living like a celebrity for one day", "Living your whole life exactly as yourself"),
    ("Living in the same city for your whole life", "Changing cities every 2 years"),
    ("Eating the same food for your whole life", "Never being able to eat your favourite food"),
    ("A superpower only you know about", "A superpower everyone knows about"),
    ("Getting the power of elasticity", "Getting the power of energy blasts"),
    ("Getting the power of elasticity", "Getting the power of night vision"),
    ("Getting the power of elasticity", "Getting the power of super jumping"),
    ("Getting the power of elasticity", "Getting the power of telekinesis"),
    ("Getting the power of energy blasts", "Getting the power of invisibility"),
    ("Getting the power of energy blasts", "Getting the power of invulnerability"),
    ("Getting the power of energy blasts", "Getting the power of super strength"),
    ("Getting the power of energy blasts", "Getting the power of teleportation"),
    ("Getting the power of energy blasts", "Getting the power of time travel"),
    ("A permanent fear of failure", "A permanent fear of flying"),
    ("A permanent fear of failure", "A permanent fear of being judged"),
    ("A permanent fear of failure", "A permanent fear of snakes"),
    ("Fame but zero privacy", "Privacy but zero fame"),
    ("Being an expert at fishing", "Being an expert at pottery"),
    ("Being able to fly", "Being able to breathe underwater"),
    ("Getting the power of flight", "Getting the power of mind reading"),
    ("Getting the power of flight", "Getting the power of a photographic memory"),
    ("Getting the power of flight", "Getting the power of shape-shifting"),
    ("Getting the power of flight", "Getting the power of super speed"),
    ("Getting the power of flight", "Getting the power of teleportation"),
    ("Being an expert at Football", "Being an expert at gardening"),
    ("Being an expert at Football", "Being an expert at the gym"),
    ("Getting the power of time freeze", "Getting the power of immortality"),
    ("Getting the power of time freeze", "Getting the power of super hearing"),
    ("Getting the power of time freeze", "Getting the power of talking to animals"),
    ("Being able to see the future", "Being able to change the past"),
    ("Being an expert at gaming", "Being an expert at photography"),
    ("Being an expert at gaming", "Being an expert at volleyball"),
    ("Being an expert at gaming", "Being an expert at writing"),
    ("Being an expert at gardening", "Being an expert at the gym"),
    ("Being an expert at gardening", "Being an expert at yoga"),
    ("A permanent fear of deep water", "A permanent fear of spiders"),
    ("A permanent fear of deep water", "A permanent fear of heights"),
    ("Doing a group project entirely alone", "Managing everyone in a group project"),
    ("Being an expert at the gym", "Being an expert at swimming"),
    ("Being an expert at the gym", "Being an expert at yoga"),
    ("Always being 10 minutes late", "Always being an hour early"),
    ("Always looking rich but actually having little money", "Always looking poor but actually having a lot of money"),
    ("Always eating biryani", "Always eating burgers"),
    ("Always eating biryani", "Always eating gulab jamun"),
    ("Always eating biryani", "Always eating jalebi"),
    ("Always eating biryani", "Always eating pasta"),
    ("Always eating burgers", "Always eating jalebi"),
    ("Always eating burgers", "Always eating pasta"),
    ("Always eating burgers", "Always eating pizza"),
    ("Always eating burgers", "Always eating sushi"),
    ("Always eating burgers", "Always eating tiramisu"),
    ("Always eating butter chicken", "Always eating french fries"),
    ("Always eating butter chicken", "Always eating instant noodles"),
    ("Always eating butter chicken", "Always eating pancakes"),
    ("Always eating butter chicken", "Always eating pani puri"),
    ("Always eating butter chicken", "Always eating pav bhaji"),
    ("Always eating butter chicken", "Always eating rajma chawal"),
    ("Always eating butter chicken", "Always eating waffles"),
    ("Always eating chocolate", "Always eating chole bhature"),
    ("Always eating chocolate", "Always eating dosa"),
    ("Always eating chocolate", "Always eating pav bhaji"),
    ("Always eating chocolate", "Always eating samosas"),
    ("Always eating chole bhature", "Always eating dosa"),
    ("Always eating chole bhature", "Always eating ice cream"),
    ("Always eating chole bhature", "Always eating momos"),
    ("Always eating chole bhature", "Always eating noodles"),
    ("Always eating chole bhature", "Always eating paneer tikka"),
    ("Always eating chole bhature", "Always eating sushi"),
    ("Always eating chole bhature", "Always eating tacos"),
    ("Always eating dim sum", "Always eating kebab"),
    ("Always eating dim sum", "Always eating ramen"),
    ("Always eating dim sum", "Always eating waffles"),
    ("Always eating dosa", "Always eating ice cream"),
    ("Always eating dosa", "Always eating noodles"),
    ("Always eating dosa", "Always eating pani puri"),
    ("Always eating dosa", "Always eating tacos"),
    ("Always looking the same", "Looking different every day but never remembering your real look"),
    ("Always eating french fries", "Always eating pancakes"),
    ("Always eating french fries", "Always eating pav bhaji"),
    ("Always eating french fries", "Always eating rajma chawal"),
    ("Always eating french fries", "Always eating shawarma"),
    ("Always eating french fries", "Always eating waffles"),
    ("Always eating gulab jamun", "Always eating jalebi"),
    ("Always eating gulab jamun", "Always eating ramen"),
    ("Always eating gulab jamun", "Always eating risotto"),
    ("Always eating ice cream", "Always eating pani puri"),
    ("Always eating ice cream", "Always eating pav bhaji"),
    ("Always eating jalebi", "Always eating pasta"),
    ("Always eating jalebi", "Always eating pizza"),
    ("Always eating jalebi", "Always eating ramen"),
    ("Always eating jalebi", "Always eating risotto"),
    ("Always eating jalebi", "Always eating tiramisu"),
    ("Always eating kebab", "Always eating instant noodles"),
    ("Always eating kebab", "Always eating pancakes"),
    ("Always eating kebab", "Always eating ramen"),
    ("Always eating kebab", "Always eating shawarma"),
    ("Always eating instant noodles", "Always eating pancakes"),
    ("Always eating instant noodles", "Always eating pani puri"),
    ("Always eating instant noodles", "Always eating rajma chawal"),
    ("Always eating instant noodles", "Always eating waffles"),
    ("Always eating momos", "Always eating noodles"),
    ("Always eating momos", "Always eating paneer tikka"),
    ("Always eating momos", "Always eating pasta"),
    ("Always eating momos", "Always eating pizza"),
    ("Always eating momos", "Always eating sushi"),
    ("Always eating momos", "Always eating tacos"),
    ("Always eating noodles", "Always eating pasta"),
    ("Always eating noodles", "Always eating samosas"),
    ("Always eating noodles", "Always eating sushi"),
    ("Always eating noodles", "Always eating tacos"),
    ("Always eating pancakes", "Always eating ramen"),
    ("Always eating pancakes", "Always eating shawarma"),
    ("Always eating paneer", "Always eating pasta"),
    ("Always eating paneer tikka", "Always eating samosas"),
    ("Always eating paneer tikka", "Always eating tacos"),
    ("Always eating pani puri", "Always eating pav bhaji"),
    ("Always eating pani puri", "Always eating rajma chawal"),
    ("Always eating pani puri", "Always eating samosas"),
    ("Always eating pasta", "Always eating pizza"),
    ("Always eating pasta", "Always eating tacos"),
    ("Always eating pav bhaji", "Always eating rajma chawal"),
    ("Always eating pav bhaji", "Always eating samosas"),
    ("Always eating pizza", "Always eating burgers"),
    ("Always eating pizza", "Always eating risotto"),
    ("Always eating pizza", "Always eating tiramisu"),
    ("Always eating rajma chawal", "Always eating waffles"),
    ("Always eating ramen", "Always eating risotto"),
    ("Always eating ramen", "Always eating shawarma"),
    ("Always eating ramen", "Always eating tiramisu"),
    ("Always eating risotto", "Always eating shawarma"),
    ("Always telling the truth", "Never hurting anyone, even if it means lying"),
    ("Always eating shawarma", "Always eating waffles"),
    ("Always eating sushi", "Always eating tacos"),
    ("Always eating tacos", "Always eating pizza"),
    ("Always talking in a whisper", "Always talking by shouting"),
    ("Endless winter", "Endless summer"),
    ("Full marks on every exam but no friends", "Average grades but the best friends"),
    ("Every lie you tell getting caught", "Never having a lie of yours get caught"),
    ("Always being the first to arrive at every party", "Always being the last to leave every party"),
    ("Being honest in every relationship, even if it's a bit awkward", "Being a bit diplomatic but smooth about it"),
    ("A permanent fear of flying", "A permanent fear of snakes"),
    ("Getting the power of a healing touch", "Getting the power of mind reading"),
    ("Getting the power of a healing touch", "Getting the power of a photographic memory"),
    ("Getting the power of a healing touch", "Getting the power of super hearing"),
    ("Getting the power of a healing touch", "Getting the power of X-ray vision"),
    ("Getting the power of immortality", "Getting the power of super intelligence"),
    ("Getting the power of immortality", "Getting the power of telekinesis"),
    ("Getting the power of invisibility", "Getting the power of invulnerability"),
    ("Getting the power of invisibility", "Getting the power of mind reading"),
    ("Getting the power of invisibility", "Getting the power of super strength"),
    ("Getting the power of invisibility", "Getting the power of time travel"),
    ("Getting the power of invulnerability", "Getting the power of super jumping"),
    ("A permanent fear of being judged", "A permanent fear of needles"),
    ("A permanent fear of being judged", "A permanent fear of public speaking"),
    ("Being able to speak one language perfectly", "Being able to play any instrument perfectly"),
    ("A permanent fear of loud noises", "A permanent fear of needles"),
    ("A permanent fear of loud noises", "A permanent fear of public speaking"),
    ("A permanent fear of loud noises", "A permanent fear of an unknown future"),
    ("Getting the power of luck manipulation", "Getting the power of night vision"),
    ("Getting the power of luck manipulation", "Getting the power of super intelligence"),
    ("Getting the power of luck manipulation", "Getting the power of telekinesis"),
    ("A permanent fear of spiders", "A permanent fear of heights"),
    ("A permanent fear of spiders", "A permanent fear of an unknown future"),
    ("The power of mind reading", "The power of teleportation"),
    ("Getting the power of mind reading", "Getting the power of super speed"),
    ("Getting the power of mind reading", "Getting the power of teleportation"),
    ("Getting the power of mind reading", "Getting the power of time travel"),
    ("A new phone every year", "An old phone but unlimited data"),
    ("A permanent fear of needles", "A permanent fear of public speaking"),
    ("Watching Netflix", "Watching YouTube"),
    ("Getting the power of night vision", "Getting the power of super jumping"),
    ("Being an expert at painting", "Being an expert at reading"),
    ("Being an expert at painting", "Being an expert at singing"),
    ("Being an expert at painting", "Being an expert at skating"),
    ("A perfect memory", "Perfect intuition"),
    ("Getting the power of a photographic memory", "Getting the power of shape-shifting"),
    ("Getting the power of a photographic memory", "Getting the power of super hearing"),
    ("Getting the power of a photographic memory", "Getting the power of super speed"),
    ("Getting the power of a photographic memory", "Getting the power of talking to animals"),
    ("Getting the power of a photographic memory", "Getting the power of X-ray vision"),
    ("Being an expert at photography", "Being an expert at reading"),
    ("Being an expert at photography", "Being an expert at swimming"),
    ("Being an expert at photography", "Being an expert at writing"),
    ("Being an expert at pottery", "Being an expert at skating"),
    ("Reading books", "Watching movies"),
    ("Being an expert at reading", "Being an expert at singing"),
    ("Being an expert at reading", "Being an expert at trekking"),
    ("Being the smartest person in the group", "Being the funniest person in the group"),
    ("Getting the power of shape-shifting", "Getting the power of super speed"),
    ("Getting the power of shape-shifting", "Getting the power of teleportation"),
    ("Getting the power of shape-shifting", "Getting the power of time travel"),
    ("Being an expert at singing", "Being an expert at volleyball"),
    ("Being an expert at singing", "Being an expert at writing"),
    ("Only ever being able to use Discord for the rest of your life", "Only ever being able to use Facebook for the rest of your life"),
    ("Only ever being able to use Discord for the rest of your life", "Only ever being able to use LinkedIn for the rest of your life"),
    ("Only ever being able to use Discord for the rest of your life", "Only ever being able to use Pinterest for the rest of your life"),
    ("Only ever being able to use Discord for the rest of your life", "Only ever being able to use Reddit for the rest of your life"),
    ("Only ever being able to use Discord for the rest of your life", "Only ever being able to use Telegram for the rest of your life"),
    ("Only ever being able to use Discord for the rest of your life", "Only ever being able to use TikTok for the rest of your life"),
    ("Only ever being able to use Discord for the rest of your life", "Only ever being able to use Twitch for the rest of your life"),
    ("Only ever being able to use Discord for the rest of your life", "Only ever being able to use Twitter/X for the rest of your life"),
    ("Only ever being able to use Facebook for the rest of your life", "Only ever being able to use LinkedIn for the rest of your life"),
    ("Only ever being able to use Facebook for the rest of your life", "Only ever being able to use Reddit for the rest of your life"),
    ("Only ever being able to use Facebook for the rest of your life", "Only ever being able to use Telegram for the rest of your life"),
    ("Only ever being able to use Facebook for the rest of your life", "Only ever being able to use WhatsApp for the rest of your life"),
    ("Only ever being able to use Facebook for the rest of your life", "Only ever being able to use YouTube for the rest of your life"),
    ("Only ever being able to use Instagram for the rest of your life", "Only ever being able to use Netflix for the rest of your life"),
    ("Only ever being able to use Instagram for the rest of your life", "Only ever being able to use Snapchat for the rest of your life"),
    ("Only ever being able to use Instagram for the rest of your life", "Only ever being able to use Telegram for the rest of your life"),
    ("Only ever being able to use Instagram for the rest of your life", "Only ever being able to use Twitch for the rest of your life"),
    ("Only ever being able to use Instagram for the rest of your life", "Only ever being able to use YouTube for the rest of your life"),
    ("Only ever being able to use LinkedIn for the rest of your life", "Only ever being able to use Pinterest for the rest of your life"),
    ("Only ever being able to use LinkedIn for the rest of your life", "Only ever being able to use Reddit for the rest of your life"),
    ("Only ever being able to use LinkedIn for the rest of your life", "Only ever being able to use Telegram for the rest of your life"),
    ("Only ever being able to use LinkedIn for the rest of your life", "Only ever being able to use Twitch for the rest of your life"),
    ("Only ever being able to use LinkedIn for the rest of your life", "Only ever being able to use YouTube for the rest of your life"),
    ("Only ever being able to use Netflix for the rest of your life", "Only ever being able to use Pinterest for the rest of your life"),
    ("Only ever being able to use Netflix for the rest of your life", "Only ever being able to use Snapchat for the rest of your life"),
    ("Only ever being able to use Netflix for the rest of your life", "Only ever being able to use Spotify for the rest of your life"),
    ("Only ever being able to use Netflix for the rest of your life", "Only ever being able to use TikTok for the rest of your life"),
    ("Only ever being able to use Netflix for the rest of your life", "Only ever being able to use Twitter/X for the rest of your life"),
    ("Only ever being able to use Pinterest for the rest of your life", "Only ever being able to use Telegram for the rest of your life"),
    ("Only ever being able to use Pinterest for the rest of your life", "Only ever being able to use TikTok for the rest of your life"),
    ("Only ever being able to use Pinterest for the rest of your life", "Only ever being able to use Twitter/X for the rest of your life"),
    ("Only ever being able to use Reddit for the rest of your life", "Only ever being able to use Spotify for the rest of your life"),
    ("Only ever being able to use Reddit for the rest of your life", "Only ever being able to use Telegram for the rest of your life"),
    ("Only ever being able to use Reddit for the rest of your life", "Only ever being able to use TikTok for the rest of your life"),
    ("Only ever being able to use Reddit for the rest of your life", "Only ever being able to use Twitter/X for the rest of your life"),
    ("Only ever being able to use Snapchat for the rest of your life", "Only ever being able to use Spotify for the rest of your life"),
    ("Only ever being able to use Snapchat for the rest of your life", "Only ever being able to use TikTok for the rest of your life"),
    ("Only ever being able to use Snapchat for the rest of your life", "Only ever being able to use Twitch for the rest of your life"),
    ("Only ever being able to use Snapchat for the rest of your life", "Only ever being able to use Twitter/X for the rest of your life"),
    ("Only ever being able to use Snapchat for the rest of your life", "Only ever being able to use WhatsApp for the rest of your life"),
    ("Only ever being able to use Spotify for the rest of your life", "Only ever being able to use TikTok for the rest of your life"),
    ("Only ever being able to use Spotify for the rest of your life", "Only ever being able to use Twitter/X for the rest of your life"),
    ("Only ever being able to use Spotify for the rest of your life", "Only ever being able to use WhatsApp for the rest of your life"),
    ("Only ever being able to use Spotify for the rest of your life", "Only ever being able to use YouTube for the rest of your life"),
    ("Only ever being able to use Telegram for the rest of your life", "Only ever being able to use TikTok for the rest of your life"),
    ("Only ever being able to use Telegram for the rest of your life", "Only ever being able to use Twitch for the rest of your life"),
    ("Only ever being able to use TikTok for the rest of your life", "Only ever being able to use Twitter/X for the rest of your life"),
    ("Only ever being able to use Twitch for the rest of your life", "Only ever being able to use YouTube for the rest of your life"),
    ("Only ever being able to use Twitter/X for the rest of your life", "Only ever being able to use WhatsApp for the rest of your life"),
    ("Only ever being a morning person", "Only ever being a night owl"),
    ("Only ever being able to text, never call", "Only ever being able to call, never text"),
    ("Traveling solo", "Traveling in a group"),
    ("Getting the power of super hearing", "Getting the power of super speed"),
    ("Getting the power of super hearing", "Getting the power of talking to animals"),
    ("Getting the power of super hearing", "Getting the power of weather control"),
    ("Getting the power of super hearing", "Getting the power of X-ray vision"),
    ("Getting the power of super intelligence", "Getting the power of talking to animals"),
    ("Getting the power of super intelligence", "Getting the power of telekinesis"),
    ("Getting the power of super jumping", "Getting the power of telekinesis"),
    ("Getting the power of super speed", "Getting the power of time travel"),
    ("Getting the power of super strength", "Getting the power of shape-shifting"),
    ("Getting the power of super strength", "Getting the power of teleportation"),
    ("Getting the power of super strength", "Getting the power of time travel"),
    ("Having super speed", "Being able to turn invisible"),
    ("Being an expert at swimming", "Being an expert at yoga"),
    ("Getting the power of teleportation", "Getting the power of invisibility"),
    ("Getting the power of teleportation", "Getting the power of time travel"),
    ("Getting the power of time travel", "Getting the power of a healing touch"),
    ("A permanent fear of heights", "A permanent fear of an unknown future"),
    ("Getting the power of weather control", "Getting the power of X-ray vision"),
    ("Weekends always being rainy", "Weekends always being extremely hot"),
    ("Living in a beach forever", "Living in a city forever"),
    ("Living in a beach forever", "Living in a coastal village forever"),
    ("Living in a beach forever", "Living in a desert forever"),
    ("Living in a beach forever", "Living in a desert oasis forever"),
    ("Living in a beach forever", "Living in the mountains forever"),
    ("Living in a beach forever", "Living in a riverside cottage forever"),
    ("Living in a city forever", "Living in the countryside forever"),
    ("Living in a city forever", "Living in a desert forever"),
    ("Living in a city forever", "Living in a forest forever"),
    ("Living in a city forever", "Living in the mountains forever"),
    ("Living in a city forever", "Living in a snowy town forever"),
    ("Living in a city forever", "Living in a village forever"),
    ("Living in a coastal village forever", "Living in a desert forever"),
    ("Living in a coastal village forever", "Living in a desert oasis forever"),
    ("Living in a coastal village forever", "Living in a hill station forever"),
    ("Living in a coastal village forever", "Living in a lighthouse forever"),
    ("Living in a coastal village forever", "Living in the mountains forever"),
    ("Living in a coastal village forever", "Living in a riverside cottage forever"),
    ("Living in a coastal village forever", "Living in a treehouse forever"),
    ("Living in the countryside forever", "Living in a historic town forever"),
    ("Living in the countryside forever", "Living in an island forever"),
    ("Living in the countryside forever", "Living in a modern metropolis forever"),
    ("Living in the countryside forever", "Living in a snowy town forever"),
    ("Living in the countryside forever", "Living in a tropical jungle forever"),
    ("Living in the countryside forever", "Living in a village forever"),
    ("Living in a desert forever", "Living in an island forever"),
    ("Living in a desert forever", "Living in the mountains forever"),
    ("Living in a desert forever", "Living in a village forever"),
    ("Living in a desert oasis forever", "Living in a forest forever"),
    ("Living in a desert oasis forever", "Living in a hill station forever"),
    ("Living in a desert oasis forever", "Living in a lighthouse forever"),
    ("Living in a forest forever", "Living in an island forever"),
    ("Living in a forest forever", "Living in the mountains forever"),
    ("Living in a hill station forever", "Living in a houseboat forever"),
    ("Living in a hill station forever", "Living in the mountains forever"),
    ("Living in a hill station forever", "Living in a riverside cottage forever"),
    ("Living in a hill station forever", "Living in a treehouse forever"),
    ("Living in a historic town forever", "Living in a houseboat forever"),
    ("Living in a historic town forever", "Living in an island forever"),
    ("Living in a historic town forever", "Living in a modern metropolis forever"),
    ("Living in a historic town forever", "Living in a snowy town forever"),
    ("Living in a historic town forever", "Living in a treehouse forever"),
    ("Living in a houseboat forever", "Living in a lighthouse forever"),
    ("Living in a houseboat forever", "Living in a quiet farmhouse forever"),
    ("Living in a houseboat forever", "Living in a riverside cottage forever"),
    ("Living in a houseboat forever", "Living in a treehouse forever"),
    ("Living in an island forever", "Living in a snowy town forever"),
    ("Living in an island forever", "Living in a tropical jungle forever"),
    ("Living in an island forever", "Living in a village forever"),
    ("Living in a lighthouse forever", "Living in a modern metropolis forever"),
    ("Living in a lighthouse forever", "Living in a treehouse forever"),
    ("Living in a modern metropolis forever", "Living in a quiet farmhouse forever"),
    ("Living in a modern metropolis forever", "Living in a snowy town forever"),
    ("Living in a modern metropolis forever", "Living in a treehouse forever"),
    ("Living in a modern metropolis forever", "Living in a tropical jungle forever"),
    ("Living in the mountains forever", "Living in a village forever"),
    ("Living in a quiet farmhouse forever", "Living in a riverside cottage forever"),
    ("Living in a quiet farmhouse forever", "Living in a snowy town forever"),
    ("Living in a quiet farmhouse forever", "Living in a tropical jungle forever"),
    ("Living in a riverside cottage forever", "Living in a treehouse forever"),
    ("Living in a snowy town forever", "Living in a tropical jungle forever"),
    ("Living in a tropical jungle forever", "Living in a village forever"),
    ("Your best friend moving to another city", "Getting into a fight with your best friend"),
    ("Your crush rejecting you in front of everyone", "Never being able to confess to your crush"),
    ("Your favourite show getting cancelled right before the finale", "Your favourite show having a terrible ending"),
    ("Your favourite social media account getting deleted", "Your phone gallery getting deleted"),
    ("Losing your phone", "Losing your wallet"),
    ("Losing your sense of smell", "Losing your sense of taste"),
    ("Your voice permanently changing", "Your name getting permanently changed"),
    ("A lifelong fear of public speaking", "Never being able to eat your favourite food again"),
    ("A lifelong fear of flying", "Never being able to eat your favourite food again"),
    ("Never being able to sleep properly", "Never feeling hungry but still having to eat anyway"),
    ("Never being able to take a vacation", "Never getting a weekend off"),
    ("A lifelong fear of spiders", "Never being able to eat your favourite food again"),
    ("A lifelong fear of deep water", "Never being able to eat your favourite food again"),
    ("Only ever being able to speak in a whisper", "Only ever being able to speak by shouting"),
    ("A lifelong fear of snakes", "Never being able to eat your favourite food again"),
    ("A lifelong fear of heights", "Never being able to eat your favourite food again"),
    ("Always know when someone's lying to you", "Always be able to get away with any lie you tell"),
    ("Have unlimited time but no money", "Have unlimited money but no free time"),
    ("Be famous for something embarrassing", "Be completely unknown forever"),
    ("Lose all your photos from the past year", "Lose all your contacts and have to rebuild them"),
    ("Have a rewind button for your life", "Have a pause button for your life"),
    ("Always have to say what you're thinking", "Never be able to share your opinion again"),
    ("Live without music for a year", "Live without your phone for a year"),
    ("Be the funniest person in every room", "Be the smartest person in every room"),
    ("Have a 4-day work week but longer days", "Have a 5-day work week with shorter days"),
    ("Always win arguments but lose friends over it", "Always lose arguments but keep every friend"),
    ("Know exactly how your life ends", "Never know and be surprised"),
    ("Be able to undo one decision from your past", "Be able to skip 5 years into your future"),
    ("Have every meal taste amazing but be unhealthy", "Have every meal be healthy but bland"),
    ("Never be able to use punctuation again", "Never be able to use emojis again"),
    ("Have to sing everything you say for a day", "Have to whisper everything you say for a day"),
]

# ══════════════════════════════════════════════════════════════════════════════
#  TRUTH & DARE — non-repeating, AI-freshened pools (per chat)
#
#  Each chat gets its own shuffled "deck" per kind (truth/dare). Every pick pops
#  one item off the deck, so nothing repeats until the ENTIRE ~400-500 item pool
#  has been used at least once — then the deck reshuffles and starts a new cycle
#  (never immediately repeating the very last card). The AI is still tried first
#  for extra freshness/variety; the deck is what guarantees zero repeats when the
#  AI is slow, down, or just not adding anything new.
# ══════════════════════════════════════════════════════════════════════════════
_td_decks      = {}   # (chat_id, kind) -> list, acts as a shuffled draw pile
_td_ai_recent  = {}   # (chat_id, kind) -> list of recent AI lines (avoid AI dupes)

def _pool_for_kind(kind):
    if kind == "truth":  return TRUTHS
    if kind == "dare":   return DARES
    if kind == "riddle": return RIDDLES
    if kind == "joke":   return JOKES
    return WYR_PAIRS  # kind == "wyr" -> list of (a, b) tuples

def _draw_from_deck(chat_id, kind):
    pool = _pool_for_kind(kind)
    key = (chat_id, kind)
    deck = _td_decks.get(key)
    if not deck:
        deck = pool[:]
        random.shuffle(deck)
        _td_decks[key] = deck
    card = deck.pop()
    if not deck:
        # cycle just completed — reshuffle a fresh deck for next time, but keep
        # this card out of the top of it so it can't come back-to-back
        fresh = pool[:]
        random.shuffle(fresh)
        if fresh and fresh[-1] == card:
            fresh[0], fresh[-1] = fresh[-1], fresh[0]
        _td_decks[key] = fresh
    return card

async def generate_truth_or_dare(kind: str, chat_id):
    """kind = 'truth' or 'dare'. Tries AI first for a fresh line; falls back to
    the non-repeating per-chat deck (guaranteed no repeats until fully cycled)."""
    ai_recent = _td_ai_recent.setdefault((chat_id, kind), [])
    prompt = (
        f"Generate ONE fun, lighthearted {kind} for a Telegram group party game. Casual English, genz tone, "
        f"suitable for a mixed group of friends (NOT romantic, NOT about crushes/relationships, NOT personal/awkward secrets). "
        f"Think: silly, nostalgic, food, movies, random hypotheticals, harmless embarrassing stories. "
        f"Must be doable via text/voice note/photo/sticker only. "
        f"Do NOT repeat or resemble any of: {'; '.join(ai_recent[-20:]) if ai_recent else 'none'}. "
        f"Reply with ONLY the {kind} line, nothing else."
    )
    try:
        raw = await groq_raw(
            "You output a single short playful truth-or-dare line for a Telegram group game. Reply with ONLY that line.",
            prompt, temperature=1.15,
        )
        line = raw.strip().strip('"').strip("'")
        if line and 5 <= len(line) <= 200 and line.lower() not in [u.lower() for u in ai_recent]:
            ai_recent.append(line)
            if len(ai_recent) > 30:
                ai_recent[:] = ai_recent[-30:]
            return line
    except Exception as e:
        logger.error(f"generate_truth_or_dare AI: {e}")
    return _draw_from_deck(chat_id, kind)

async def get_fresh_truth(chat_id):
    return await generate_truth_or_dare("truth", chat_id)

async def get_fresh_dare(chat_id):
    return await generate_truth_or_dare("dare", chat_id)
# ══════════════════════════════════════════════════════════════════════════════
#  TRAITOR WORD BANK
# ══════════════════════════════════════════════════════════════════════════════
TRAITOR_WORD_BANK = [
     # Original words
    "Pizza", "Guitar", "Elephant", "Beach", "Laptop", "Mountain", "Coffee", "Rainbow",
    "Bicycle", "Volcano", "Umbrella", "Astronaut", "Waterfall", "Sandwich", "Dragon",
    "Telescope", "Butterfly", "Skateboard", "Lighthouse", "Cactus", "Penguin", "Rocket",
    "Violin", "Jungle", "Snowman", "Pirate", "Castle", "Dinosaur", "Firework", "Tornado",
    "Camera", "Kangaroo", "Pancake", "Glacier", "Robot", "Compass", "Mermaid", "Wizard",
    "Tractor", "Hurricane", "Balloon", "Jellyfish", "Saxophone", "Cathedral", "Comet",
    "Igloo", "Ninja", "Pyramid", "Spaceship", "Treehouse", "Waffle", "Yacht", "Zebra",
    "Avocado", "Bagpipes", "Chandelier", "Drawbridge", "Escalator", "Flamingo",
    "Grandfather clock", "Hammock", "Iceberg", "Jackpot", "Kaleidoscope", "Lantern",
    "Marshmallow", "Notebook", "Octopus", "Parachute", "Quicksand", "Raincoat",
    "Scarecrow", "Trampoline", "Unicorn", "Volleyball", "Windmill", "Xylophone",

    # 200 Additional Common Words
    "Apple", "Banana", "Orange", "Grape", "Strawberry", "Watermelon", "Pineapple", "Mango",
    "Peach", "Cherry", "Lemon", "Lime", "Pear", "Plum", "Kiwi", "Blueberry",
    "Raspberry", "Blackberry", "Coconut", "Papaya", "Broccoli", "Carrot", "Potato", "Tomato",
    "Cucumber", "Lettuce", "Spinach", "Onion", "Garlic", "Pepper", "Pumpkin", "Radish",
    "Celery", "Mushroom", "Turnip", "Zucchini", "Bread", "Butter", "Cheese", "Milk",
    "Yogurt", "Egg", "Bacon", "Sausage", "Steak", "Chicken", "Fish", "Shrimp",
    "Soup", "Salad", "Burger", "Hotdog", "Taco", "Burrito", "Pasta", "Noodle",
    "Rice", "Soup", "Cookie", "Cake", "Pie", "Brownie", "Donut", "Muffin",
    "Chocolate", "Candy", "Honey", "Jam", "Sugar", "Salt", "Pepper", "Soup",
    "Water", "Juice", "Milkshake", "Tea", "Soda", "Lemonade", "Smoothie", "Cider",
    "Dog", "Cat", "Horse", "Cow", "Pig", "Sheep", "Goat", "Chicken",
    "Duck", "Goose", "Turkey", "Rabbit", "Mouse", "Rat", "Hamster", "Guinea pig",
    "Turtle", "Frog", "Snake", "Lizard", "Alligator", "Crocodile", "Tiger", "Lion",
    "Leopard", "Cheetah", "Bear", "Wolf", "Fox", "Deer", "Moose", "Bison",
    "Camel", "Giraffe", "Zebra", "Rhinoceros", "Hippopotamus", "Monkey", "Gorilla", "Chimpanzee",
    "Panda", "Koala", "Sloth", "Beaver", "Otter", "Seal", "Walrus", "Whale",
    "Dolphin", "Shark", "Crab", "Lobster", "Starfish", "Seahorse", "Jellyfish", "Squid",
    "Eagle", "Hawk", "Falcon", "Owl", "Parrot", "Pigeon", "Dove", "Swan",
    "Peacock", "Ostrich", "Flamingo", "Pelican", "Seagull", "Woodpecker", "Crow", "Raven",
    "House", "Apartment", "Cabin", "Tent", "Building", "Skyscraper", "Office", "School",
    "Hospital", "Library", "Museum", "Theater", "Restaurant", "Supermarket", "Bank", "Post office",
    "Airport", "Station", "Bridge", "Tunnel", "Road", "Highway", "Street", "Park",
    "Garden", "Farm", "Barn", "Fencing", "Gate", "Path", "Yard", "Porch",
    "Roof", "Door", "Window", "Wall", "Floor", "Ceiling", "Stairs", "Elevator",
    "Kitchen", "Bedroom", "Bathroom", "Living room", "Garage", "Basement", "Attic", "Balcony",
    "Bed", "Pillow", "Blanket", "Sheet", "Dresser", "Closet", "Desk", "Chair",
    "Table", "Couch", "Sofa", "Bookshelf", "Lamp", "Rug", "Curtain", "Mirror",
    "Clock", "Watch", "Television", "Radio", "Speaker", "Headphones", "Computer", "Keyboard",
    "Mouse", "Monitor", "Printer", "Phone", "Tablet", "Charger", "Battery", "Flashlight"
]


# ══════════════════════════════════════════════════════════════════════════════
#  HANGMAN WORDS
# ══════════════════════════════════════════════════════════════════════════════
HANGMAN_WORDS = [
    "python","telegram","elephant","keyboard","sunshine","umbrella","password",
    "chocolate","discovery","adventure","beautiful","waterfall","breakfast",
    "challenge","universe","knowledge","computer","butterfly","education",
    "happiness","mountain","language","wonderful","birthday","chemistry",
    "geography","democracy","lightning","midnight","pharmacy","sandwich",
    "dinosaur","carnival","fantastic","halloween","internet","jealousy",
    "kangaroo","labyrinth","mushroom","notebook","orchestra","paradise",
    "question","raspberry","shoulder","together","umbrella","vitamins",
    "workshop","yesterday","zeppelin","backpack","calendar","daughter",
]

HANGMAN_STAGES = [
    "```\n  ╔══╗\n  ║  ║\n  ║\n  ║\n  ║\n══╩══\n```",
    "```\n  ╔══╗\n  ║  ║\n  ║  😊\n  ║\n  ║\n══╩══\n```",
    "```\n  ╔══╗\n  ║  ║\n  ║  😟\n  ║  │\n  ║\n══╩══\n```",
    "```\n  ╔══╗\n  ║  ║\n  ║  😰\n  ║ /│\n  ║\n══╩══\n```",
    "```\n  ╔══╗\n  ║  ║\n  ║  😨\n  ║ /│\\\n  ║\n══╩══\n```",
    "```\n  ╔══╗\n  ║  ║\n  ║  😱\n  ║ /│\\\n  ║ /\n══╩══\n```",
    "```\n  ╔══╗\n  ║  ║\n  ║  💀\n  ║ /│\\\n  ║ / \\\n══╩══\n```",
]

# ══════════════════════════════════════════════════════════════════════════════
#  CHALLENGE FALLBACK POOL
# ══════════════════════════════════════════════════════════════════════════════
CHALLENGE_FALLBACK_POOL = [
    {"type":"trivia","q":"What planet is the Red Planet?","a":"mars","h":"4th from Sun","c":10},
    {"type":"trivia","q":"How many legs does a spider have?","a":"8","h":"More than insects","c":10},
    {"type":"trivia","q":"What's the largest ocean?","a":"pacific","h":"Between Asia and Americas","c":10},
    {"type":"trivia","q":"What gas do plants use in photosynthesis?","a":"carbon dioxide","h":"We exhale it","c":15},
    {"type":"trivia","q":"Which country gifted the Statue of Liberty to the USA?","a":"france","h":"Eiffel Tower country","c":15},
    {"type":"trivia","q":"How many continents are there?","a":"7","h":"Lucky number","c":10},
    {"type":"trivia","q":"What is the chemical formula of water?","a":"h2o","h":"2 hydrogen 1 oxygen","c":8},
    {"type":"trivia","q":"Who wrote Romeo and Juliet?","a":"shakespeare","h":"English playwright","c":10},
    {"type":"trivia","q":"What is the tallest animal?","a":"giraffe","h":"Long neck","c":10},
    {"type":"trivia","q":"How many strings on a standard guitar?","a":"6","h":"Between 5 and 7","c":10},
    {"type":"trivia","q":"Capital of Japan?","a":"tokyo","h":"Godzilla attacks here","c":8},
    {"type":"word","q":"Unscramble: LPAPE","a":"apple","h":"A fruit","c":12},
    {"type":"word","q":"Unscramble: KBOO","a":"book","h":"You read it","c":10},
    {"type":"word","q":"Unscramble: DLWOR","a":"world","h":"Earth","c":12},
    {"type":"word","q":"Unscramble: OCSRE","a":"score","h":"Points in a game","c":12},
]

# ══════════════════════════════════════════════════════════════════════════════
#  PHOTO CHALLENGE POOL
#  FIX: "photo" challenges had a full grading pipeline (icons, instructions,
#  vision-check branch in handle_message) but nothing ever GENERATED one —
#  generate_challenge_content() only ever picked "trivia" or "word", either
#  from the AI prompt (which was told to choose from [trivia, word]) or from
#  CHALLENGE_FALLBACK_POOL (which has no "photo" entries at all). So photo
#  challenges were 100% dead code — /challenge could never produce one.
#  This pool is deliberately NOT AI-generated: the AI can't verify a target
#  is actually easy to photograph on the spot, but everything below is a
#  common object almost anyone has within reach at home or in a group hangout.
# ══════════════════════════════════════════════════════════════════════════════
PHOTO_CHALLENGE_POOL = [
    {"target": "a spoon",            "hint": "Kitchen drawer basics",         "c": 20},
    {"target": "a coffee mug",       "hint": "Morning essential",             "c": 20},
    {"target": "a pair of shoes",    "hint": "Look by the door",              "c": 20},
    {"target": "a book",             "hint": "Any book counts",               "c": 20},
    {"target": "a houseplant",       "hint": "Green and leafy",               "c": 25},
    {"target": "a pillow",           "hint": "Soft and squishy",              "c": 20},
    {"target": "a wristwatch",       "hint": "Tells the time",                "c": 25},
    {"target": "a pair of glasses",  "hint": "Helps you see",                 "c": 25},
    {"target": "headphones",         "hint": "For your ears",                 "c": 20},
    {"target": "a wallet",           "hint": "Holds your cash/cards",         "c": 20},
    {"target": "a backpack",         "hint": "Carries your stuff",            "c": 20},
    {"target": "a remote control",   "hint": "For the TV",                    "c": 20},
    {"target": "a pen",              "hint": "For writing",                   "c": 15},
    {"target": "a clock",            "hint": "Wall or desk",                  "c": 20},
    {"target": "a mirror",           "hint": "Reflects your face",            "c": 20},
    {"target": "an umbrella",        "hint": "For rainy days",                "c": 25},
    {"target": "a hat or cap",       "hint": "Wear it on your head",          "c": 20},
    {"target": "a bottle of water",  "hint": "Stay hydrated",                 "c": 15},
    {"target": "a charger cable",    "hint": "Keeps devices alive",           "c": 15},
    {"target": "a set of keys",      "hint": "Opens doors",                   "c": 15},
    {"target": "a candle",           "hint": "Gives off light",               "c": 20},
    {"target": "a plate",            "hint": "You eat off it",                "c": 15},
    {"target": "a toothbrush",       "hint": "Bathroom shelf",                "c": 15},
    {"target": "a pair of socks",    "hint": "Feet warmers",                  "c": 15},
    {"target": "a calendar",         "hint": "Tracks the days",               "c": 20},
]

def _generate_photo_challenge(recent_lower):
    """Picks a photo target not posted recently. `recent_lower` is the same
    lowercased recent-question list used for trivia/word dedup — so we build
    each candidate's full question text and compare THAT (exact match),
    consistent with how trivia/word dedup already works, rather than
    substring-matching just the bare target against full question strings
    (which would never match and silently disable the dedup)."""
    choices = [
        p for p in PHOTO_CHALLENGE_POOL
        if f"take a photo of {p['target']}!".lower() not in recent_lower
    ]
    chosen = random.choice(choices or PHOTO_CHALLENGE_POOL)
    return {
        "type": "photo",
        "q": f"Take a photo of {chosen['target']}!",
        "a": chosen["target"],
        "h": chosen["hint"],
        "c": chosen["c"],
    }

# ══════════════════════════════════════════════════════════════════════════════
#  DATABASE

# ══════════════════════════════════════════════════════════════════════════════
_db = None

def _get_db():
    global _db
    if _db is None:
        client = MongoClient(SQLITE_DB_PATH)
        _db = client["aira"]
    return _db

_GROUP_DEFAULTS = {
    "active_challenge": None,
    "forge_war": False,
    "forge_war_multiplier": 1,
    "pending_chooser": None,
    "last_challenge_time": None,
    "welcome_msg": None,
    "bye_msg": None,
    "warns": {},
    "auto_challenge_enabled": True,
    "recent_challenges": [],
    "rules": None,
    "antispam": False,
    "locked": False,
    "blacklist_words": [],
    "approved_ids": [],   # user ids immune to /ban /kick /timeout /warn /tempban + antispam in this group
}

def _is_approved(chat_id, uid):
    group = get_group_db(chat_id)
    return int(uid) in group.get("approved_ids", [])

def get_group_db(chat_id):
    db  = _get_db()
    doc = db["groups"].find_one({"_id": str(chat_id)})
    if doc: doc.pop("_id", None)
    else:   doc = {}
    for k, v in _GROUP_DEFAULTS.items():
        doc.setdefault(k, v.copy() if isinstance(v, (dict, list)) else v)
    # Self-heal stale challenge
    ch = doc.get("active_challenge")
    if ch and ch.get("started_at"):
        try:
            elapsed = (datetime.now() - datetime.fromisoformat(ch["started_at"])).total_seconds()
            if elapsed >= CHALLENGE_TIMEOUT:
                doc["active_challenge"] = None
                save_group_db(chat_id, doc)
        except Exception:
            pass
    return doc

def save_group_db(chat_id, group):
    db = _get_db()
    db["groups"].replace_one({"_id": str(chat_id)}, {"_id": str(chat_id), **group}, upsert=True)

_USER_DEFAULTS = {
    "username":"Unknown","full_name":"Unknown",
    "coins":0,"wins":0,"streak":0,"best_streak":0,"badges":[],
    "title":None,"title_expiry":None,"title_chat_id":None,"title_purchased":False,
    "double_coins":False,"weekly_wins":0,"last_win_date":None,
    "pin_token":False,"shield_expiry":None,
    "battle_team":[],"last_pray":None,"pray_active":False,"pray_expires":None,
    "animals":[],"hunts":0,"hunt_cooldown":None,
    "owo_boost_expiry":None,"auto_hunt":False,"total_coins_ever":0,
    "daily_claimed":None,"daily_streak":0,"today_wins":0,"today_date":None,
    "gems":0,"weapon":"stick","weapon_level":0,"weapon_inventory":[],"weapon_levels":{},
    "afk":None,"afk_since":None,"afk_pings":[],"afk_type":"away",
    "half_cooldown_expiry":None,"cheap_autohunt":False,"cheap_autohunt_expiry":None,
    "casino_wins":0,"casino_total_won":0,
    "pvp_wins":0,"quiz_wins":0,"ttt_wins":0,"hangman_wins":0,"bj_wins":0,
    "auto_hunt_expiry":None,
    "pet":None,  # active adopted companion (dict) or None — see ADOPT & PET CARE SYSTEM
    "referred_by":None,"referral_count":0,"referral_coins_earned":0,  # see REFERRAL SYSTEM
    "referral_milestones_claimed":[],  # list of milestone thresholds (ints) already paid out, see REFERRAL_MILESTONES
}

def get_user(data, uid, username=None, full_name=None):
    _USER_LAST_ACCESS[str(uid)] = time.time()
    k = str(uid)
    if k not in data["users"]:
        # Not in the in-memory cache — this can happen if the mem_cleanup job
        # evicted this uid for being idle. It is NOT a new user: check SQLite
        # before ever falling back to a blank default, or we silently wipe
        # their real data on the next save_data() call.
        db = _get_db()
        doc = db["users"].find_one({"_id": k})
        if doc:
            doc.pop("_id", None)
            data["users"][k] = doc
        else:
            data["users"][k] = dict(_USER_DEFAULTS)
    u = data["users"][k]
    if username:  u["username"]  = username
    if full_name: u["full_name"] = full_name
    for key, val in _USER_DEFAULTS.items():
        if key not in u:
            u[key] = val.copy() if isinstance(val, (dict, list)) else val
    return u

class _DirtyUsersDict(dict):
    """Behaves exactly like a normal dict (it IS one — every existing call
    site across the bot works unmodified), but tracks which user IDs were
    accessed via __getitem__/.get()/__setitem__ so save_data() can write
    ONLY those instead of re-scanning or re-writing all 20,000 users.
    Verified against every direct data["users"] access site in this file:
    the two .items() iteration sites (cmd_topanimals, the @mention scanner
    in handle_message) are read-only lookups — the actual mutations they
    trigger go through .get()/__getitem__ on a specific uid afterward,
    which IS tracked. Marking too much dirty is always safe (just an extra
    write); this only omits tracking where a full audit confirmed nothing
    is ever mutated during the untracked access."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.dirty = set()

    def __getitem__(self, key):
        self.dirty.add(key)
        return super().__getitem__(key)

    def __setitem__(self, key, value):
        self.dirty.add(key)
        super().__setitem__(key, value)

    def get(self, key, default=None):
        if key in self:
            self.dirty.add(key)
        return super().get(key, default)


_cached_data = None  # populated once, then reused — see load_data() below

def load_data():
    """Returns the SAME shared in-memory dict every call after the first.
    Safe because: (1) this is a single bot process talking to its own local
    SQLite file — nothing else writes to it concurrently, and (2) every one
    of the ~100 call sites across the bot mutates this dict directly (via
    get_user() or data["users"][...] etc.), so those mutations are already
    live in the cache the instant they happen — a second load_data() call
    just returns the same up-to-date object, not stale data.
    This eliminates the #1 real cost at scale: re-reading and JSON-parsing
    every single user row from disk on every single command, from every
    single user, every single time — even though the vast majority of
    those reads only ever touched one user's data."""
    global _cached_data
    if _cached_data is not None:
        return _cached_data
    db    = _get_db()
    users = _DirtyUsersDict()
    for doc in db["users"].find():
        uid = str(doc.pop("_id"))
        users[uid] = doc  # marks dirty via __setitem__ — cleared right below, since a fresh load has nothing unsaved yet
    users.dirty.clear()
    meta = db["meta"].find_one({"_id":"meta"}) or {}
    meta.pop("_id", None)
    _cached_data = {
        "users":       users,
        "groups":      {},
        "used_codes":  meta.get("used_codes", []),
        "trades":      meta.get("trades", {}),
        "item_trades": meta.get("item_trades", {}),
        "auctions":    meta.get("auctions", {}),
        "pvp_requests":meta.get("pvp_requests", {}),
    }
    return _cached_data

def save_data(data: dict):
    """Flushes ONLY the users touched since the last save (tracked in O(1)
    per access via _DirtyUsersDict, not by re-scanning all 20,000 users).
    This is the real fix at scale: a single /hunt or /cf from one user now
    writes exactly one row, instead of the original 20,000-row rewrite —
    and that one row is written via a single fast transaction (see
    sqlite_shim.py's bulk_write()), not an individual disk commit."""
    db = _get_db()
    users = data.get("users", {})
    dirty_ids = getattr(users, "dirty", None)
    if dirty_ids is None:
        # Defensive fallback: data["users"] isn't our tracked dict (shouldn't
        # happen since load_data() always constructs one) — fall back to
        # writing everything, exactly like the original always did, rather
        # than risk silently dropping an update.
        dirty_ids = set(users.keys())
    changed_ops = [
        ReplaceOne({"_id": str(uid)}, {"_id": str(uid), **users[uid]}, upsert=True)
        for uid in dirty_ids if uid in users
    ]
    if changed_ops:
        db["users"].bulk_write(changed_ops, ordered=False)
    if hasattr(users, "dirty"):
        users.dirty.clear()
    meta = {
        "_id":         "meta",
        "used_codes":  data.get("used_codes", []),
        "trades":      data.get("trades", {}),
        "item_trades": data.get("item_trades", {}),
        "auctions":    data.get("auctions", {}),
        "pvp_requests":data.get("pvp_requests", {}),
    }
    db["meta"].replace_one({"_id":"meta"}, meta, upsert=True)


def get_user_fast(uid, username=None, full_name=None):
    """Drop-in replacement for `db["users"].find_one({"_id": uid})` used by
    do_hunt() and ~20 other functions that historically talked to the DB
    directly, bypassing load_data()'s cache entirely.

    THE BUG THIS FIXES: those direct reads/writes were invisible to the
    shared in-memory cache. Sequence that broke things: do_hunt() writes a
    new animal straight to the DB -> the in-memory cache still has the OLD
    (pre-hunt) version of that user -> user runs ANY other command (/wallet,
    /daily, /give, ...) -> that command's save_data() call flushes the
    STALE cached copy back to disk -> the animal do_hunt() just added gets
    silently overwritten and lost. This is exactly the "autohunt sometimes
    removes animals" / "doesn't save new animals" symptom.

    The fix: every user read/write goes through the ONE shared cache, so
    there's only ever one source of truth, never two disagreeing copies."""
    data = load_data()
    return get_user(data, str(uid), username, full_name)


def save_user_fast(uid):
    """Drop-in replacement for `db["users"].replace_one({"_id": uid}, ...)`.
    Persists ONE user's current (already-mutated-in-place) state from the
    shared cache immediately — same underlying write path as save_data()
    (single-row upsert, WAL mode), just for one user without needing the
    caller to build/pass a full data dict."""
    uid = str(uid)
    data = load_data()
    users = data["users"]
    if uid not in users:
        return
    db = _get_db()
    db["users"].replace_one({"_id": uid}, {"_id": uid, **users[uid]}, upsert=True)
    if hasattr(users, "dirty"):
        users.dirty.discard(uid)  # already flushed, nothing left to save next time











# ══════════════════════════════════════════════════════════════════════════════
#  BROADCAST TARGET TRACKING (silent — powers /announcetoall)
# ══════════════════════════════════════════════════════════════════════════════
_seen_chats_runtime = set()

def track_chat(chat_id, is_group):
    if chat_id in _seen_chats_runtime:
        return
    _seen_chats_runtime.add(chat_id)
    try:
        db = _get_db()
        field = "groups" if is_group else "users"
        db["meta"].update_one({"_id": "broadcast"}, {"$addToSet": {field: chat_id}}, upsert=True)
    except Exception as e:
        logger.error(f"track_chat error: {e}")

# ══════════════════════════════════════════════════════════════════════════════
#  COMMAND USAGE TRACKING (silent — powers the /checkuserbase analytics report)
# ══════════════════════════════════════════════════════════════════════════════
_command_stats_cache = None  # {"total": int, "by_command": {name: int}} — lazy-loaded

def _record_command_usage(cmd_name):
    global _command_stats_cache
    try:
        db = _get_db()
        if _command_stats_cache is None:
            doc = db["meta"].find_one({"_id": "command_stats"}) or {}
            _command_stats_cache = {
                "total": doc.get("total", 0),
                "by_command": doc.get("by_command", {}),
            }
        _command_stats_cache["total"] += 1
        bc = _command_stats_cache["by_command"]
        bc[cmd_name] = bc.get(cmd_name, 0) + 1
        db["meta"].update_one(
            {"_id": "command_stats"},
            {"$set": {"total": _command_stats_cache["total"], "by_command": bc}},
            upsert=True,
        )
    except Exception as e:
        logger.error(f"_record_command_usage error: {e}")

def _with_usage_tracking(cmd_name, fn):
    """Wraps a command handler so every invocation (successful or not) bumps
    the /checkuserbase 'total views' counter, without touching each command's
    own body.

    Also guards against the crash seen in production: Telegram sometimes
    delivers a command as an update where `update.message` is None (e.g. the
    person edited an earlier message into a command — CommandHandler listens
    to edited messages too, and those land in `update.edited_message`, not
    `update.message`). Every command body in this file assumes
    `update.message` exists, so without this guard that update crashes the
    handler and DMs the owner a traceback. We already also restrict the
    CommandHandler registrations to fresh messages only (see main()), so
    this is a belt-and-suspenders backstop for any other update shape."""
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.message is None:
            logger.info(f"Ignoring /{cmd_name}: update has no update.message "
                        f"(likely an edited-message command) — not a real invocation.")
            return
        _record_command_usage(cmd_name)
        return await fn(update, context)
    wrapper.__name__ = f"tracked_{cmd_name}"
    return wrapper
# ══════════════════════════════════════════════════════════════════════════════
#  UTILITY FUNCTIONS
# ══════════════════════════════════════════════════════════════════════════════
def award_badge(user, key):
    """Returns a self-contained, formatted 'achievement unlocked' banner
    (or None if the badge doesn't exist / is already owned) — every call
    site just drops this straight into a message, so the banner has to
    carry its own framing rather than relying on a "🆕" prefix.
    Uses a left "▎" bar per line to visually read as a quoted callout
    block (legacy Markdown has no real <blockquote>, this is the closest
    safe equivalent that composes into any existing message)."""
    if key in BADGES and key not in user.get("badges", []):
        user.setdefault("badges", []).append(key)
        name, desc, tier = BADGES[key]
        stars = BADGE_TIERS.get(tier, "⭐")
        return (f"💜 *ACHIEVEMENT UNLOCKED* — {tier} {stars}\n"
                f"▎*{name}*\n"
                f"▎_{desc}_")
    return None

def check_badges(user):
    earned = []
    checks = [
        (user.get("wins",0)>=1,"first_win"),
        (user.get("streak",0)>=3,"streak_3"),
        (user.get("streak",0)>=5,"streak_5"),
        (user.get("wins",0)>=10,"wins_10"),
        (user.get("wins",0)>=25,"wins_25"),
        (user.get("wins",0)>=50,"wins_50"),
        (user.get("wins",0)>=100,"wins_100"),
        (user.get("total_coins_ever",0)>=500,"rich"),
        (user.get("total_coins_ever",0)>=10000,"wealthy"),
        (user.get("total_coins_ever",0)>=100000,"tycoon"),
        (user.get("hunts",0)>=1,"first_hunt"),
        (user.get("hunts",0)>=10,"hunter_10"),
        (user.get("hunts",0)>=100,"hunter_100"),
        (user.get("casino_wins",0)>=1,"gambler"),
        (user.get("casino_total_won",0)>=200,"big_win"),
        (user.get("daily_streak",0)>=7,"daily_7"),
        (user.get("daily_streak",0)>=30,"daily_30"),
        (user.get("pvp_wins",0)>=1,"pvp_win"),
        (user.get("ttt_wins",0)>=1,"ttt_win"),
        (user.get("hangman_wins",0)>=1,"hangman_win"),
        (user.get("bj_wins",0)>=1,"bj_win"),
        (user.get("quiz_wins",0)>=1,"quiz_top"),
        (user.get("referral_count",0)>=5,"recruiter"),
        (user.get("referral_count",0)>=25,"ambassador"),
        (user.get("referral_count",0)>=100,"growth_legend"),
    ]
    for cond, key in checks:
        if cond:
            b = award_badge(user, key)
            if b: earned.append(b)
    return earned

def has_shield(user):
    exp = user.get("shield_expiry")
    return bool(exp and datetime.fromisoformat(exp) > datetime.now())

def has_pray_buff(user):
    exp = user.get("pray_expires")
    if exp and user.get("pray_active"):
        if datetime.fromisoformat(exp) > datetime.now():
            return True
        user["pray_active"] = False
    return False

def get_cooldown_multiplier(user):
    exp = user.get("half_cooldown_expiry")
    if exp:
        try:
            if datetime.fromisoformat(exp) > datetime.now():
                return 0.5
        except Exception:
            pass
    return 1.0

def fmt_duration(seconds):
    seconds = int(seconds)
    h, r = divmod(seconds, 3600)
    m, s = divmod(r, 60)
    if h: return f"{h}h {m}m {s}s"
    if m: return f"{m}m {s}s"
    return f"{s}s"

async def is_admin(bot, chat_id, user_id):
    try:
        m = await bot.get_chat_member(chat_id, user_id)
        return m.status in ("administrator", "creator")
    except Exception:
        return False

# ══════════════════════════════════════════════════════════════════════════════
#  ADMIN-TARGET CONFIRMATION — /ban /kick /timeout /tempban /warn refuse to fire
#  instantly on a fellow admin; they get a Yes/No prompt first so a mis-typed
#  reply or a moment of anger can't nuke another admin by accident.
# ══════════════════════════════════════════════════════════════════════════════
_pending_punishments = {}   # token -> {action, chat_id, target_id, ..., created_at}
_PUNISH_CONFIRM_TTL = 120   # seconds a confirmation prompt stays valid

# ══════════════════════════════════════════════════════════════════════════════
#  BUG REPORT REVIEW — /reportbug now needs owner approval before the +100
#  coin reward is paid out, and the owner can reply in DM to message the
#  reporter directly (see the reply-routing check near the top of handle_message).
# ══════════════════════════════════════════════════════════════════════════════
_bug_reports = {}   # report_id -> {reporter_id, text, status, owner_messages, ...}

_PUNISH_LABELS = {
    "ban": "ban", "kick": "kick", "timeout": "mute (timeout)",
    "tempban": "temp-ban", "warn": "warn",
}

async def _confirm_if_target_is_admin(update: Update, context: ContextTypes.DEFAULT_TYPE,
                                       target, action: str, extra: dict = None):
    """If `target` is an admin/creator of this chat, sends a Yes/No confirmation
    prompt and returns True (the caller should stop and NOT punish yet).
    If the target is a regular member, returns False immediately so the
    caller proceeds exactly as before."""
    chat_id = update.message.chat_id
    if not await is_admin(context.bot, chat_id, target.id):
        return False

    token = uuid.uuid4().hex[:12]
    _pending_punishments[token] = {
        "action": action,
        "chat_id": chat_id,
        "target_id": target.id,
        "target_name": target.full_name,
        "target_username": target.username,
        "initiator_id": update.message.from_user.id,
        "extra": extra or {},
        "created_at": datetime.now(),
    }
    name = f"@{target.username}" if target.username else _safe_md(target.full_name)
    label = _PUNISH_LABELS.get(action, action)
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ Yes, I'm sure", callback_data=f"padm_yes_{token}"),
        InlineKeyboardButton("❌ Cancel", callback_data=f"padm_no_{token}"),
    ]])
    await update.message.reply_text(
        f"🛡️ *{name}* is an admin in this group.\n"
        f"Are you sure you want to *{label}* them?",
        reply_markup=kb, parse_mode="Markdown")
    return True

async def _execute_punishment(context: ContextTypes.DEFAULT_TYPE, query, pending: dict):
    action   = pending["action"]
    chat_id  = pending["chat_id"]
    target_id = pending["target_id"]
    extra    = pending.get("extra", {})
    name = f"@{pending['target_username']}" if pending.get("target_username") else _safe_md(pending["target_name"])
    try:
        if action == "ban":
            await context.bot.ban_chat_member(chat_id, target_id)
            await query.edit_message_text(
                f"🔨 *{name}* banned.\nReason: _{extra.get('reason', 'No reason given')}_", parse_mode="Markdown")
        elif action == "kick":
            await context.bot.ban_chat_member(chat_id, target_id)
            await context.bot.unban_chat_member(chat_id, target_id)
            await query.edit_message_text(
                f"👢 *{name}* kicked.\nReason: _{extra.get('reason', 'No reason given')}_", parse_mode="Markdown")
        elif action == "timeout":
            mins = extra.get("mins", 5)
            until = datetime.now() + timedelta(minutes=mins)
            await context.bot.restrict_chat_member(
                chat_id, target_id, permissions=ChatPermissions(can_send_messages=False), until_date=until)
            await _safe_edit_message_text(query, f"🔇 *{name}* muted for *{mins}m*.", parse_mode="Markdown")
        elif action == "tempban":
            mins = extra.get("mins", 60)
            until = datetime.now() + timedelta(minutes=mins)
            await context.bot.ban_chat_member(chat_id, target_id, until_date=until)
            await _safe_edit_message_text(query, f"⏳ *{name}* temp-banned for *{mins}m*.", parse_mode="Markdown")
        elif action == "warn":
            group = get_group_db(chat_id); uid = str(target_id)
            group["warns"][uid] = group["warns"].get(uid, 0) + 1
            count = group["warns"][uid]; save_group_db(chat_id, group)
            if count >= 3:
                try:
                    await context.bot.ban_chat_member(chat_id, target_id)
                    await query.edit_message_text(
                        f"⚠️ *{name}* warn {count}/3 → 🔨 *{fancy('BANNED!')}*", parse_mode="Markdown")
                    group["warns"][uid] = 0; save_group_db(chat_id, group)
                except TelegramError as e:
                    await _safe_edit_message_text(query, f"⚠️ Warn {count}/3 (ban failed: _{e}_)", parse_mode="Markdown")
            else:
                await _safe_edit_message_text(query, f"⚠️ *{name}* warned *{count}/3*.", parse_mode="Markdown")
        else:
            await _safe_edit_message_text(query, "❌ Unknown pending action.")
    except TelegramError as e:
        await _safe_edit_message_text(query, f"❌ _{e}_", parse_mode="Markdown")

async def handle_punishment_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data or ""
    try:
        _, verdict, token = data.split("_", 2)
    except ValueError:
        try:
            await query.answer()
        except (BadRequest, TelegramError):
            pass  # stale/expired callback query — safe to ignore
        return
    pending = _pending_punishments.get(token)
    if not pending:
        await query.answer("⏰ This confirmation expired.", show_alert=True)
        try:
            await query.edit_message_reply_markup(reply_markup=None)
        except Exception:
            pass
        return
    if (datetime.now() - pending["created_at"]).total_seconds() > _PUNISH_CONFIRM_TTL:
        _pending_punishments.pop(token, None)
        await query.answer("⏰ This confirmation expired.", show_alert=True)
        try:
            await query.edit_message_text("⏰ Confirmation expired — run the command again if needed.")
        except Exception:
            pass
        return
    # Any current admin can confirm or cancel — not just whoever ran the
    # original command — so a second admin can back out a rushed decision.
    if not await is_admin(context.bot, pending["chat_id"], query.from_user.id):
        await query.answer("Only an admin can confirm this.", show_alert=True)
        return

    if verdict == "no":
        _pending_punishments.pop(token, None)
        await query.answer("Cancelled.")
        await _safe_edit_message_text(query, "❌ Action cancelled — nothing happened.")
        return

    _pending_punishments.pop(token, None)
    await query.answer("Confirmed — executing...")
    await _execute_punishment(context, query, pending)

async def get_target(update, context):
    if update.message.reply_to_message:
        return update.message.reply_to_message.from_user, None
    return None, "↩️ Reply to a user's message to target them."

def roll_animal():
    if random.randint(1, 1_000_000) == 777:
        mythic = next((a for a in ANIMALS if a["rarity"] == "mythic"), None)
        if mythic: return mythic
    # Limited-edition animal(s): only rollable before their deadline passes.
    # BUGFIX: this used to be gated at 1-in-50,000, which doesn't match its
    # RARITY_WEIGHTS entry (0.3, i.e. meant to be ~1-in-338 like an
    # underweighted Extreme). At 1-in-50,000 the expected catches after
    # 3,000-4,000 hunts is under 0.1 — statistically nobody was ever going to
    # find it, which matches exactly what was reported. Now the odds
    # actually match the weight table it was designed against.
    limited_chance = RARITY_WEIGHTS["limited"] / sum(RARITY_WEIGHTS[k] for k in
                        ("common","uncommon","rare","epic","legendary","Extreme","limited"))
    if datetime.now() < LIMITED_EDITION_DEADLINE and random.random() < limited_chance:
        limited = next((a for a in ANIMALS if a.get("limited") and not a.get("evolved")), None)
        if limited: return limited
    # Only hunt-able animals (no evolved forms, no mythic, no expired/limited
    # items, and no pets — pets have their own manual-hunt-only roll, see
    # do_hunt(manual=...) / PET_CATCH_CHANCE, so they must never land here).
    huntable = [a for a in ANIMALS if not a.get("evolved") and not a.get("is_pet")]
    pool = []
    for a in huntable:
        if a["rarity"] == "mythic" or a.get("limited"):
            continue
        pool.extend([a] * RARITY_WEIGHTS[a["rarity"]])
    return random.choice(pool)

def get_weapon_effective_stats(user):
    wkey  = user.get("weapon", "stick")
    w     = WEAPONS.get(wkey, WEAPONS["stick"])
    level = user.get("weapon_levels", {}).get(wkey, 0)
    extra = WEAPON_UPGRADE_BONUS.get(level, 0)
    return {
        "name":        w["name"] + (f" Lv.{level}" if level else ""),
        "atk_bonus":   w["atk_bonus"] + extra,
        "catch_bonus": w["catch_bonus"] + extra,
    }
# ══════════════════════════════════════════════════════════════════════════════
#  AI CHAT – GROQ + GEMINI FALLBACK (seamless, same context + prompts)
# ══════════════════════════════════════════════════════════════════════════════
_chat_histories         = {}   # chat_id -> [{role, content}]
_MAX_HISTORY            = 8
_chat_moods             = {}   # chat_id -> (mood_text, expires_at)
_groq_rate_limited_until = None  # datetime when Groq is usable again (429 cooldown)
_groq_broken_until       = None  # datetime when Groq is usable again (config/auth/model error cooldown)
_openrouter_rate_limited_until = None  # same pattern as Groq's, independent cooldown
_openrouter_broken_until       = None

# Live diagnostics — inspected by /aistatus. Every call updates this so you can
# see exactly why a reply fell back, instead of guessing from a canned message.
_ai_health = {
    "groq":       {"ok": None, "last_error": None, "last_checked": None, "last_success": None},
    "gemini":     {"ok": None, "last_error": None, "last_checked": None, "last_success": None},
    "openrouter": {"ok": None, "last_error": None, "last_checked": None, "last_success": None},
    "vision":     {"ok": None, "last_error": None, "last_checked": None, "last_success": None},
}

def _get_mood(chat_id):
    now   = datetime.now()
    entry = _chat_moods.get(chat_id)
    if entry and entry[1] > now:
        return entry[0]
    mood = random.choice(_AIRA_MOODS)
    _chat_moods[chat_id] = (mood, now + timedelta(minutes=random.randint(15, 40)))
    return mood

def _groq_available():
    now = datetime.now()
    if _groq_rate_limited_until and now < _groq_rate_limited_until:
        return False
    if _groq_broken_until and now < _groq_broken_until:
        return False
    return True

def _set_groq_limited(minutes=3):
    global _groq_rate_limited_until
    _groq_rate_limited_until = datetime.now() + timedelta(minutes=minutes)
    logger.warning(f"Groq rate limited (429) — Gemini fallback active for {minutes} min")

def _set_groq_broken(reason: str, minutes=10):
    """Non-rate-limit failure (bad model id, bad key, etc). Back off longer so we
    don't hammer a config error on every single group message."""
    global _groq_broken_until
    _groq_broken_until = datetime.now() + timedelta(minutes=minutes)
    logger.error(f"Groq unusable ({reason}) — backing off {minutes} min, using Gemini fallback")

def _openrouter_available():
    if not OPENROUTER_API_KEY:
        return False  # not configured — silently skip this tier everywhere, no errors
    now = datetime.now()
    if _openrouter_rate_limited_until and now < _openrouter_rate_limited_until:
        return False
    if _openrouter_broken_until and now < _openrouter_broken_until:
        return False
    return True

def _set_openrouter_limited(minutes=3):
    global _openrouter_rate_limited_until
    _openrouter_rate_limited_until = datetime.now() + timedelta(minutes=minutes)
    logger.warning(f"OpenRouter rate limited (429) — backing off {minutes} min")

def _set_openrouter_broken(reason: str, minutes=10):
    global _openrouter_broken_until
    _openrouter_broken_until = datetime.now() + timedelta(minutes=minutes)
    logger.error(f"OpenRouter unusable ({reason}) — backing off {minutes} min")

def _extract_content(data: dict) -> str:
    """Robustly pulls the reply text out of an OpenAI-shaped chat-completion
    JSON body. FIX: a raw `.json()["choices"][0]["message"]["content"].strip()`
    crashes with 'NoneType has no attribute strip' whenever a provider
    returns content=null (seen live from OpenRouter's auto-router — some
    models it routes to return null content instead of a refusal/empty
    string, e.g. when they emit only a tool call or hit a moderation stop).
    Also defends against content coming back as a list of parts (a shape a
    few providers use) instead of a plain string. Every call site that reads
    a chat-completion response should go through this instead of indexing
    the JSON directly."""
    try:
        content = data["choices"][0]["message"].get("content")
        if content is None:
            return ""
        if isinstance(content, list):
            content = "".join(
                (p.get("text", "") if isinstance(p, dict) else str(p)) for p in content
            )
        return str(content).strip()
    except Exception:
        return ""

async def _gemini_call(system_prompt: str, messages: list, temperature: float = 1.0, max_tokens: int = 130) -> str:
    """Gemini REST call — same conversation context as Groq."""
    _ai_health["gemini"]["last_checked"] = datetime.now().isoformat()
    try:
        # Convert OpenAI-style messages to Gemini format
        gemini_contents = []
        for m in messages:
            role = "user" if m["role"] == "user" else "model"
            gemini_contents.append({"role": role, "parts": [{"text": m["content"]}]})
        payload = {
            "systemInstruction": {"parts": [{"text": system_prompt}]},
            "contents": gemini_contents,
            "generationConfig": {
                "maxOutputTokens": max_tokens,
                "temperature": min(temperature, 2.0),
            },
        }
        async with httpx.AsyncClient(timeout=18) as client:
            resp = await client.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent",
                headers={"x-goog-api-key": GEMINI_API_KEY, "Content-Type": "application/json"},
                json=payload,
            )
            if resp.status_code != 200:
                err = f"HTTP {resp.status_code}: {resp.text[:300]}"
                logger.error(f"Gemini error {err}")
                _ai_health["gemini"]["ok"] = False
                _ai_health["gemini"]["last_error"] = err
                return ""
            data = resp.json()
            text = data["candidates"][0]["content"]["parts"][0]["text"].strip()
            _ai_health["gemini"]["ok"] = True
            _ai_health["gemini"]["last_success"] = datetime.now().isoformat()
            return text
    except Exception as e:
        logger.error(f"_gemini_call error: {e}")
        _ai_health["gemini"]["ok"] = False
        _ai_health["gemini"]["last_error"] = str(e)[:300]
        return ""

async def _groq_call(messages: list, max_tokens: int, temperature: float):
    """Low-level Groq call shared by groq_chat/groq_raw. Returns text or "" ,
    and updates cooldowns + diagnostics based on the *actual* status code
    instead of guessing from the exception string."""
    _ai_health["groq"]["last_checked"] = datetime.now().isoformat()
    if not _groq_available():
        return ""
    try:
        payload = {"model": GROQ_MODEL, "messages": messages,
                   "max_tokens": max_tokens, "temperature": temperature,
                   "frequency_penalty": 0.7, "presence_penalty": 0.5}
        # FIX (round 2): "reasoning_effort": "low" alone wasn't enough — per
        # Groq's own docs and an open bug on their community forum, the
        # gpt-oss family "reasons always-on and cannot be disabled" at the
        # API level; low/medium/high only changes HOW MUCH it reasons, not
        # whether. That hidden reasoning still eats into the same max_tokens
        # budget as the visible reply, so a tight budget can still come back
        # empty even at "low". The actually-documented fix for this exact
        # symptom is "reasoning_format": "hidden", which tells Groq to strip
        # reasoning out of the returned content entirely instead of just
        # doing less of it — combined here with a larger max_tokens floor
        # (see groq_chat/groq_raw) so there's still headroom left for the
        # real reply even though reasoning still silently consumes some of
        # the budget either way.
        if any(fam in GROQ_MODEL.lower() for fam in ("gpt-oss", "qwen3")):
            if "qwen3" in model.lower():
                payload["reasoning_effort"] = "default"
                payload["reasoning_format"] = "hidden"
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"},
                json=payload,
            )
            if resp.status_code == 429:
                _set_groq_limited(3)
                _ai_health["groq"]["ok"] = False
                _ai_health["groq"]["last_error"] = "429 rate limited"
                return ""
            if resp.status_code in (400, 401, 403, 404):
                # bad model id / bad or revoked key / no access — retrying every
                # message would be pointless, so back off for longer.
                err = f"HTTP {resp.status_code}: {resp.text[:300]}"
                _set_groq_broken(err, minutes=10)
                _ai_health["groq"]["ok"] = False
                _ai_health["groq"]["last_error"] = err
                return ""
            if resp.status_code != 200:
                err = f"HTTP {resp.status_code}: {resp.text[:300]}"
                logger.error(f"Groq error {err}")
                _ai_health["groq"]["ok"] = False
                _ai_health["groq"]["last_error"] = err
                return ""
            text = _extract_content(resp.json())
            _ai_health["groq"]["ok"] = bool(text)
            if text:
                _ai_health["groq"]["last_success"] = datetime.now().isoformat()
            else:
                _ai_health["groq"]["last_error"] = "empty reply"
            return text
    except Exception as e:
        logger.error(f"_groq_call error: {e}")
        _ai_health["groq"]["ok"] = False
        _ai_health["groq"]["last_error"] = str(e)[:300]
        return ""

async def _openrouter_call(messages: list, max_tokens: int, temperature: float):
    """Third, fully independent text-AI leg — same shape as _groq_call so it
    drops straight into groq_chat/groq_raw's fallback chain. No-ops (returns
    "" immediately) if OPENROUTER_API_KEY isn't set, so this is completely
    safe to leave configured or not."""
    _ai_health["openrouter"]["last_checked"] = datetime.now().isoformat()
    if not _openrouter_available():
        return ""
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": OPENROUTER_SITE_URL,  # OpenRouter's recommended attribution headers
                    "X-Title": OPENROUTER_APP_NAME,
                },
                json={"model": OPENROUTER_MODEL, "messages": messages,
                      "max_tokens": max_tokens, "temperature": temperature},
            )
            if resp.status_code == 429:
                _set_openrouter_limited(3)
                _ai_health["openrouter"]["ok"] = False
                _ai_health["openrouter"]["last_error"] = "429 rate limited"
                return ""
            if resp.status_code in (400, 401, 403, 404):
                err = f"HTTP {resp.status_code}: {resp.text[:300]}"
                _set_openrouter_broken(err, minutes=10)
                _ai_health["openrouter"]["ok"] = False
                _ai_health["openrouter"]["last_error"] = err
                return ""
            if resp.status_code != 200:
                err = f"HTTP {resp.status_code}: {resp.text[:300]}"
                logger.error(f"OpenRouter error {err}")
                _ai_health["openrouter"]["ok"] = False
                _ai_health["openrouter"]["last_error"] = err
                return ""
            data = resp.json()
            text = _extract_content(data)
            _ai_health["openrouter"]["ok"] = bool(text)
            if text:
                _ai_health["openrouter"]["last_success"] = datetime.now().isoformat()
            else:
                _ai_health["openrouter"]["last_error"] = "empty reply"
            return text
    except Exception as e:
        logger.error(f"_openrouter_call error: {e}")
        _ai_health["openrouter"]["ok"] = False
        _ai_health["openrouter"]["last_error"] = str(e)[:300]
        return ""

_chat_last_msg_time = {}  # chat_id -> datetime of last AI-chat message, for gap/odd-hour detection
_IST = timezone(timedelta(hours=5, minutes=30))  # Aira should reason in Indian time, not server/GMT time

async def groq_chat(chat_id, user_name, user_message):
    if chat_id not in _chat_histories:
        _chat_histories[chat_id] = []
    history = _chat_histories[chat_id]

    now        = datetime.now(_IST)
    last_time  = _chat_last_msg_time.get(chat_id)
    gap_hours  = (now - last_time).total_seconds() / 3600 if last_time else None
    _chat_last_msg_time[chat_id] = now

    history.append({"role": "user", "content": f"{user_name}: {user_message}"})
    if len(history) > _MAX_HISTORY:
        history[:] = history[-_MAX_HISTORY:]
    mood      = _get_mood(chat_id)
    time_now  = now.strftime("%I:%M %p").lstrip("0")
    odd_hour  = now.hour >= 23 or now.hour < 6
    # Nobody told her the time — she should just know it, the way a real
    # person texting at 3am is obviously still awake at 3am. If it's a late
    #/odd hour and this looks like a fresh check-in (first message in a
    # while), nudge her to notice that unprompted instead of only reacting
    # if the user brings it up themselves.
    if odd_hour and (gap_hours is None or gap_hours > 1):
        time_note = (
            f"ABHI KA TIME: {time_now}. Itni raat/subah ko koi message kar raha hai — "
            f"tumhe khud pata hona chahiye ki itni odd time hai, bina kisi ke bataye. "
            f"Agar natural lage to apne reply mein casually mention kar sakti ho "
            f"(jaise abhi jaagi hui ho, bore ho rahi ho, neend nahi aa rahi, etc) — "
            f"jaisa ek real insaan karta hai jab koi unexpected time pe text kare. Force mat karo, bas natural rakho."
        )
    else:
        time_note = (
            f"ABHI KA TIME: {time_now}. Tumhe pata hai abhi kitna baja hai — agar relevant ho to "
            f"naturally reference kar sakti ho, lekin har reply mein batane ki zaroorat nahi."
        )
    system = f"{AIRA_SYSTEM_PROMPT}\n\nABHI KA MOOD: {mood}\n{time_note}"
    temp   = round(random.uniform(0.95, 1.15), 2)

    full_messages = [{"role": "system", "content": system}, *history]

    # ── 4-tier chain: Groq → Gemini → OpenRouter → Groq (retry) → canned ────
    # NOTE: Groq's max_tokens here is 300, not the ~130 you'd expect for a
    # short chat reply — gpt-oss's hidden reasoning eats into this same
    # budget and can't be fully disabled (see _groq_call), so a tight budget
    # was the actual cause of the "empty reply" failures. Gemini/OpenRouter
    # don't need the same padding since they aren't forced through Groq's
    # reasoning-format handling.
    reply = await _groq_call(full_messages, 100, temp)

    if not reply:
        reply = await _gemini_call(system, history, temperature=temp, max_tokens=80)

    if not reply:
        # Third, fully independent provider (no-ops instantly if
        # OPENROUTER_API_KEY isn't set) — catches the rare case where Groq
        # AND Gemini are both having a bad moment at once.
        reply = await _openrouter_call(full_messages, 80, temp)

    if not reply:
        # All three just failed — give Groq one more shot before giving up.
        # This catches transient blips (timeouts, momentary 5xx) that
        # shouldn't cost the user a canned reply if the very next call
        # would've worked.
        await asyncio.sleep(1)
        reply = await _groq_call(full_messages, 100, temp)

    if not reply:
        reply = random.choice(FALLBACK_REPLIES)

    # Anti-repeat: regenerate if identical to last reply
    _last_said = next((m["content"] for m in reversed(history)
                       if m["role"] == "assistant"), "")
    if reply and _last_said and len(reply) > 8:
        _norm = lambda s: re.sub(r"[^a-z0-9]", "", s.lower())
        if _norm(reply) == _norm(_last_said):
            _nudge = list(full_messages) + [
                {"role":"assistant","content":reply},
                {"role":"user","content":"(same cheez mat repeat karo, kuch naya bol)"}
            ]
            _fresh = await _groq_call(_nudge, 80, temp)
            if _fresh and _norm(_fresh) != _norm(reply):
                reply = _fresh
    history.append({"role": "assistant", "content": reply})
    _chat_histories[chat_id] = history
    return reply

async def groq_raw(system_prompt, user_prompt, temperature=1.0):
    """Single-shot AI call (no chat history). 4-tier chain: Groq → Gemini →
    OpenRouter → Groq (retry) → "" (caller decides its own final fallback text)."""
    msgs = [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}]

    reply = await _groq_call(msgs, 300, temperature)  # see groq_chat's note on why this is padded
    if reply:
        return reply

    reply = await _gemini_call(
        system_prompt, [{"role": "user", "content": user_prompt}],
        temperature=temperature, max_tokens=150,
    )
    if reply:
        return reply

    reply = await _openrouter_call(msgs, 200, temperature)
    if reply:
        return reply

    # One last retry on Groq in case the first failure was a transient blip.
    await asyncio.sleep(1)
    return await _groq_call(msgs, 150, temperature)

async def cmd_aistatus(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Owner-only: live-tests all AI providers right now and reports exact errors."""
    user = update.message.from_user
    if user.id not in OWNER_IDS:
        return
    msg = await update.message.reply_text("🔍 Checking all of Aira's connections live, ek sec...")

    groq_reply = await _groq_call(
        [{"role": "system", "content": "Reply with exactly: pong"},
         {"role": "user", "content": "ping"}], 60, 0.1)
    gemini_reply = await _gemini_call(
        "Reply with exactly: pong", [{"role": "user", "content": "ping"}],
        temperature=0.1, max_tokens=10)
    openrouter_reply = ""
    if OPENROUTER_API_KEY:
        openrouter_reply = await _openrouter_call(
            [{"role": "system", "content": "Reply with exactly: pong"},
             {"role": "user", "content": "ping"}], 60, 0.1)

    # Vision test — uses a tiny image EMBEDDED as base64 (a tiny solid-color
    # JPEG) instead of fetching a real photo from an external URL. FIX: the
    # old test used a Wikimedia Commons URL for Groq to fetch server-side,
    # and Wikimedia started returning 403 to Groq's fetcher — so /aistatus
    # was reporting "vision is down" when the real problem was just that one
    # test image host blocking one provider's fetcher, nothing to do with
    # the vision models themselves. A locally-embedded base64 image has no
    # external dependency to break, AND it exactly matches how
    # analyze_image_with_ai() sends real challenge photos (base64 data URI,
    # never a URL) — so this test is now representative, not just "reachable".
    # Tests every configured vision leg independently (Groq primary,
    # Groq fallback, and OpenRouter if configured) so a report of "vision is
    # down" tells you exactly which leg(s) are actually failing right now.
    _TEST_IMG_B64 = (
        "/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAAoHBwgHBgoICAgLCgoLDhgQDg0NDh0VFhEYIx8lJCIf"
        "IiEmKzcvJik0KSEiMEExNDk7Pj4+JS5ESUM8SDc9Pjv/2wBDAQoLCw4NDhwQEBw7KCIoOzs7Ozs7"
        "Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozv/wAARCABAAEADASIA"
        "AhEBAxEB/8QAHwAAAQUBAQEBAQEAAAAAAAAAAAECAwQFBgcICQoL/8QAtRAAAgEDAwIEAwUFBAQA"
        "AAF9AQIDAAQRBRIhMUEGE1FhByJxFDKBkaEII0KxwRVS0fAkM2JyggkKFhcYGRolJicoKSo0NTY3"
        "ODk6Q0RFRkdISUpTVFVWV1hZWmNkZWZnaGlqc3R1dnd4eXqDhIWGh4iJipKTlJWWl5iZmqKjpKWm"
        "p6ipqrKztLW2t7i5usLDxMXGx8jJytLT1NXW19jZ2uHi4+Tl5ufo6erx8vP09fb3+Pn6/8QAHwEA"
        "AwEBAQEBAQEBAQAAAAAAAAECAwQFBgcICQoL/8QAtREAAgECBAQDBAcFBAQAAQJ3AAECAxEEBSEx"
        "BhJBUQdhcRMiMoEIFEKRobHBCSMzUvAVYnLRChYkNOEl8RcYGRomJygpKjU2Nzg5OkNERUZHSElK"
        "U1RVVldYWVpjZGVmZ2hpanN0dXZ3eHl6goOEhYaHiImKkpOUlZaXmJmaoqOkpaanqKmqsrO0tba3"
        "uLm6wsPExcbHyMnK0tPU1dbX2Nna4uPk5ebn6Onq8vP09fb3+Pn6/9oADAMBAAIRAxEAPwDEooor"
        "7A7wooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKK"
        "KACiiigD/9k="
    )
    vision_image_url = f"data:image/jpeg;base64,{_TEST_IMG_B64}"

    vision_reply = ""
    vision_model_used = None
    vision_results = {}

    async def _test_groq_vision(vmodel):
        payload = {"model": vmodel,
                   "messages": [{"role": "user", "content": [
                       {"type": "text", "text": "Reply with exactly: pong"},
                       {"type": "image_url", "image_url": {"url": vision_image_url}},
                   ]}], "max_completion_tokens": 300}
        # Same fix as _groq_call: qwen3 reasons before answering and can't
        # fully disable it, so strip reasoning from the output and give it
        # real headroom instead of a token budget too tight to get past
        # the <think> block — this is exactly what was showing up as raw
        # "<think>..." text cut off mid-thought in the old 10-token test.
        if any(fam in vmodel.lower() for fam in ("gpt-oss", "qwen3")):
            payload["reasoning_effort"] = "default"
            payload["reasoning_format"] = "hidden"
        async with httpx.AsyncClient(timeout=20) as client:
            return await client.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"},
                json=payload)

    async def _test_openrouter_vision(vmodel):
        async with httpx.AsyncClient(timeout=20) as client:
            return await client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={"Authorization": f"Bearer {OPENROUTER_API_KEY}", "Content-Type": "application/json",
                         "HTTP-Referer": OPENROUTER_SITE_URL, "X-Title": OPENROUTER_APP_NAME},
                json={"model": vmodel,
                      "messages": [{"role": "user", "content": [
                          {"type": "text", "text": "Reply with exactly: pong"},
                          {"type": "image_url", "image_url": {"url": vision_image_url}},
                      ]}], "max_tokens": 300})

    vision_legs = [("groq", GROQ_VISION_MODEL), ("groq", GROQ_VISION_MODEL_FALLBACK)]
    if OPENROUTER_API_KEY:
        vision_legs.append(("openrouter", OPENROUTER_VISION_MODEL))

    for provider, vmodel in vision_legs:
        if not vmodel:
            continue
        label = f"{provider}:{vmodel}"
        if label in vision_results:
            continue
        try:
            vresp = await (_test_groq_vision(vmodel) if provider == "groq" else _test_openrouter_vision(vmodel))
            if vresp.status_code == 200:
                text = _extract_content(vresp.json())
                if text:
                    vision_results[label] = text
                    if not vision_reply:
                        vision_reply = text
                        vision_model_used = label
                else:
                    vision_results[label] = "❌ HTTP 200 but empty content"
            else:
                vision_results[label] = f"❌ HTTP {vresp.status_code}: {vresp.text[:200]}"
        except Exception as e:
            vision_results[label] = f"❌ {str(e)[:200]}"

    _ai_health["vision"]["last_checked"] = datetime.now().isoformat()
    if vision_reply:
        _ai_health["vision"]["ok"] = True
        _ai_health["vision"]["last_success"] = datetime.now().isoformat()
    else:
        _ai_health["vision"]["ok"] = False
        _ai_health["vision"]["last_error"] = "; ".join(f"{m}: {r}" for m, r in vision_results.items())

    def _fmt(name, key, reply, model):
        h = _ai_health[key]
        if reply:
            return f"✅ *{name}*: working (model replied: `{reply[:40]}`)"
        if key == "openrouter" and not OPENROUTER_API_KEY:
            return f"⚪ *{name}*: not configured (set OPENROUTER_API_KEY to enable this backup)"
        return (f"❌ *{name}*: FAILING\n"
                f"   Model: `{model}`\n"
                f"   Last error: `{(h['last_error'] or 'unknown')[:200]}`")

    vision_lines = [f"✦ *Vision (photo challenges)* ✦"]
    vision_tags = {f"groq:{GROQ_VISION_MODEL}": "groq primary", f"groq:{GROQ_VISION_MODEL_FALLBACK}": "groq fallback",
                   f"openrouter:{OPENROUTER_VISION_MODEL}": "openrouter backup"}
    for label, r in vision_results.items():
        ok = not r.startswith("❌")
        tag = vision_tags.get(label, label)
        vision_lines.append(f"   {'✅' if ok else '❌'} `{label}` ({tag}): `{r[:150]}`")
    if not OPENROUTER_API_KEY:
        vision_lines.append("   ⚪ openrouter backup: not configured (set OPENROUTER_API_KEY to enable)")

    lines = [
        "🩺 ✦ *AI HEALTH CHECK* ✦\n┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄",
        _fmt("Groq", "groq", groq_reply, GROQ_MODEL),
        "",
        _fmt("Gemini", "gemini", gemini_reply, GEMINI_MODEL),
        "",
        _fmt("OpenRouter", "openrouter", openrouter_reply, OPENROUTER_MODEL),
        "",
        "\n".join(vision_lines),
    ]
    if not groq_reply and not gemini_reply and not openrouter_reply:
        lines.append("\n⚠️ *Groq, Gemini, and OpenRouter are all down* — this is why Aira's been giving the 'signal weak' fallback line. Fix the errors above (usually: rotate/regenerate a key, or check a model id is still live), then run `/aistatus` again.")
    elif not groq_reply and not gemini_reply:
        lines.append("\nℹ️ Groq and Gemini are both down but OpenRouter is covering chat replies — nothing user-facing is broken.")
    if not vision_reply:
        lines.append("\n⚠️ *All configured vision legs are down* — see the exact errors above. If they all say the same thing (e.g. a 401/403), it's a shared cause like a revoked key; if they fail differently, it's likely just provider-side capacity, and it should recover on its own. Photo challenges will show 'temporarily unavailable' until then. Consider setting OPENROUTER_API_KEY if you haven't — it's a fully independent vision leg.")
    elif vision_model_used != f"groq:{GROQ_VISION_MODEL}":
        lines.append(f"\nℹ️ The primary vision model is down but `{vision_model_used}` is covering it — photo challenges are still working.")
    await msg.edit_text("\n".join(lines), parse_mode="Markdown")


async def generate_traitor_word(used_words=None):
    used_words = used_words or []
    pool = [w for w in TRAITOR_WORD_BANK if w.lower() not in used_words] or TRAITOR_WORD_BANK
    try:
        raw = await groq_raw(
            "You output a single common English noun for a party game. Reply with ONLY the word itself.",
            f"Give me one common noun. Don't use: {', '.join(used_words[-15:]) or 'none'}.", temperature=1.2,
        )
        import re as re2
        word = re2.sub(r"[^A-Za-z ]","",raw).strip()
        if word and 1<=len(word.split())<=3 and len(word)<=24 and word.lower() not in used_words:
            return word.title()
    except Exception as e:
        logger.error(f"generate_traitor_word AI: {e}")
    return random.choice(pool)

async def generate_challenge_content(recent_questions=None):
    recent_questions = recent_questions or []
    recent_lower = [r.lower() for r in recent_questions]

    # ── Decide the round type FIRST. Photo challenges are picked straight from
    # a curated local pool (see PHOTO_CHALLENGE_POOL above) instead of asking
    # the AI, since the AI has no way to know whether a random object it
    # dreams up is actually something a group of people could photograph in
    # the next 5 minutes. This is also the actual fix for photo challenges
    # never appearing — see the comment above PHOTO_CHALLENGE_POOL.
    _pw  = 25 if _vision_available else 0  # photo weight: 0 when vision is down
    _adj = (25 - _pw) // 2                 # redistribute weight to trivia/word
    ctype = random.choices(["trivia", "word", "photo"],
                           weights=[45 + _adj, 30 + _adj, _pw])[0]
    if ctype == "photo":
        return _generate_photo_challenge(recent_lower)

    prompt = (
        "Generate ONE challenge for a Telegram group game. "
        "Choose type from: [trivia, word]. "
        f"Do NOT repeat: {recent_questions[-10:] if recent_questions else 'none'}. "
        "Return ONLY valid JSON, no markdown: "
        '{"type":"trivia|word","q":"question","a":"answer","h":"short hint","c":25}'
    )
    try:
        raw = await groq_raw(
            "You are a JSON API. Output ONLY valid JSON, never extra text or code fences.",
            prompt, temperature=1.1,
        )
        import re as re2
        m = re2.search(r"\{.*\}", raw, re2.DOTALL)
        import json as j2
        d = j2.loads(m.group(0))
        q = d["q"]
        if q and q.lower() not in recent_lower:
            return {"type":d["type"],"q":q,"a":str(d["a"]),"h":d["h"],"c":int(d["c"])}
    except Exception as e:
        logger.error(f"generate_challenge_content AI: {e}")
    choices = [c for c in CHALLENGE_FALLBACK_POOL if c["q"].lower() not in [r.lower() for r in recent_questions]]
    return dict(random.choice(choices or CHALLENGE_FALLBACK_POOL))

def _should_aira_reply(update: Update, bot_username: str):
    msg  = update.message
    if not msg: return False
    # In DM (private chat) — ALWAYS reply, no trigger word needed
    if msg.chat.type == "private":
        return True
    text = msg.text or msg.caption or ""
    if msg.reply_to_message and msg.reply_to_message.from_user:
        if msg.reply_to_message.from_user.username == bot_username:
            return True
    if f"@{bot_username}".lower() in text.lower():
        return True
    if re.search(r'\baira\b', text, re.IGNORECASE):
        return True
    return False

# ══════════════════════════════════════════════════════════════════════════════
#  AFK SYSTEM  (fixed: clears on message, GN → sleep mode)
# ══════════════════════════════════════════════════════════════════════════════
@with_data_lock
async def handle_afk_return(update: Update, data: dict, user):
    """Called when an AFK user sends any message. Clears AFK and shows summary."""
    u    = get_user(data, user.id, user.username, user.full_name)
    name = _safe_md(f"@{user.username}" if user.username else user.full_name)
    if not u.get("afk"):
        return False  # not afk
    
    afk_since = u.get("afk_since")
    afk_type  = u.get("afk_type", "away")
    pings     = u.get("afk_pings", [])
    reason    = u.get("afk", "")
    
    u["afk"]        = None
    u["afk_since"]  = None
    u["afk_pings"]  = []
    u["afk_type"]   = "away"
    save_data(data)
    
    if afk_since:
        try:
            duration = fmt_duration((datetime.now() - datetime.fromisoformat(afk_since)).total_seconds())
        except Exception:
            duration = "a while"
    else:
        duration = "a while"
    
    if afk_type == "sleep":
        msg = f"☀️ *Good morning {name}!*\nYou were sleeping for *{duration}*."
    else:
        msg = f"👋 *{name}* is back! _(was away for {duration})_"
    
    if pings:
        unique_pingers = list(dict.fromkeys(pings))  # deduplicate preserving order
        ping_str = ", ".join(unique_pingers[:5])
        extra = f" +{len(unique_pingers)-5} more" if len(unique_pingers) > 5 else ""
        msg += f"\n📬 *{len(pings)} pings* from: {ping_str}{extra}"
    
    try:
        await update.message.reply_text(msg, parse_mode="Markdown")
    except Exception:
        pass
    return True

async def check_afk_ping(update: Update, data: dict, mentioned_user_id: int, pinger_name: str):
    """Record that someone pinged an AFK user."""
    u = data["users"].get(str(mentioned_user_id))
    if not u or not u.get("afk"):
        return None
    name     = u.get("full_name", "Someone")
    afk_type = u.get("afk_type", "away")
    reason   = u.get("afk", "AFK")
    u.setdefault("afk_pings", []).append(pinger_name)
    if len(u["afk_pings"]) > 100: u["afk_pings"] = u["afk_pings"][-100:]
    if afk_type == "sleep":
        return f"😴 *{name}* is currently sleeping! They'll see your message when they wake up."
    return f"😴 *{name}* is AFK: _{reason}_"

# ══════════════════════════════════════════════════════════════════════════════
#  AUTO-CHALLENGE  (fixed: proper scheduling, no duplicate loops)
# ══════════════════════════════════════════════════════════════════════════════
_auto_challenge_chats = set()  # tracks which groups have an active loop

async def post_challenge(context: ContextTypes.DEFAULT_TYPE, chat_id: int):
    group = get_group_db(chat_id)
    if group.get("active_challenge"):
        return
    recent = group.get("recent_challenges", [])
    data   = await generate_challenge_content(recent)
    ctype, q, a, h, c_val = data["type"], data["q"], data["a"], data["h"], data["c"]
    mult   = group.get("forge_war_multiplier", 1)
    coins  = int(c_val) * mult

    group["active_challenge"] = {
        "question":   q,
        "answers":    [a.lower().strip()],
        "hint":       h,
        "coins":      coins,
        "type":       ctype,
        "started_at": datetime.now().isoformat(),
    }
    recent.append(q)
    group["recent_challenges"]  = recent[-15:]
    group["last_challenge_time"] = datetime.now().isoformat()
    save_group_db(chat_id, group)

    fw    = f"\n⚔️ *{fancy('FORGE WAR!')}* Rewards ×{mult}!\n" if group.get("forge_war") else ""
    icons = {"trivia":"🧠","word":"⚡","photo":"📸"}
    instr = {"trivia":"💬 Type your answer!","word":"⚡ Type the unscrambled word!","photo":"📸 Send a photo!"}

    await context.bot.send_message(
        chat_id,
        f"{'⚡' if ctype=='word' else '🎯'} *{ctype.upper()} CHALLENGE!*{fw}\n"
        f"*{q}*\n\n💰 *{coins} Forge Coins* {icons.get(ctype,'❓')}\n"
        f"⏱️ 5 minutes! {instr.get(ctype,'Type the answer!')}",
        parse_mode="Markdown",
    )
    context.job_queue.run_once(
        expire_challenge, when=CHALLENGE_TIMEOUT,
        chat_id=chat_id, name=f"expire_{chat_id}",
    )

async def expire_challenge(context: ContextTypes.DEFAULT_TYPE):
    cid   = context.job.chat_id
    group = get_group_db(cid)
    if not group.get("active_challenge"):
        return
    q = group["active_challenge"]["question"]
    group["active_challenge"] = None
    save_group_db(cid, group)
    try:
        await context.bot.send_message(
            cid, f"⌛ *Time's up!* No one answered.\n_{q}_\n\nBetter luck next time! 💪",
            parse_mode="Markdown",
        )
    except Exception:
        pass

async def _post_challenge_job(context: ContextTypes.DEFAULT_TYPE):
    await post_challenge(context, context.job.data["chat_id"])

async def schedule_next(context: ContextTypes.DEFAULT_TYPE, chat_id: int):
    delay = random.randint(1800, 5400)
    context.job_queue.run_once(
        _post_challenge_job,
        when=delay, chat_id=chat_id, name=f"auto_{chat_id}",
        data={"chat_id": chat_id},
    )

# The self-rescheduling tick – FIX: always reschedules unless explicitly disabled
async def _auto_challenge_tick(context: ContextTypes.DEFAULT_TYPE):
    chat_id = context.job.data["chat_id"]
    try:
        group = get_group_db(chat_id)
        if group.get("auto_challenge_enabled", True) and not group.get("active_challenge"):
            await post_challenge(context, chat_id)
    except Exception as e:
        logger.error(f"_auto_challenge_tick {chat_id}: {e}")
    # Reschedule unconditionally (check inside next tick whether still enabled)
    delay = random.randint(AUTO_CHALLENGE_MIN, AUTO_CHALLENGE_MAX)
    context.job_queue.run_once(
        _auto_challenge_tick,
        when=delay,
        name=f"autochallenge_{chat_id}",
        data={"chat_id": chat_id},
    )

def ensure_auto_challenge(context: ContextTypes.DEFAULT_TYPE, chat_id: int):
    """Start the auto-challenge loop for a group chat. Safe to call many times."""
    if chat_id >= 0:          # positive = DM; only groups get auto-challenges
        return
    if chat_id in _auto_challenge_chats:
        return                # loop already running for this chat
    group = get_group_db(chat_id)
    if not group.get("auto_challenge_enabled", True):
        return
    _auto_challenge_chats.add(chat_id)
    delay = random.randint(AUTO_CHALLENGE_MIN, AUTO_CHALLENGE_MAX)
    context.job_queue.run_once(
        _auto_challenge_tick,
        when=delay,
        name=f"autochallenge_{chat_id}",
        data={"chat_id": chat_id},
    )
    logger.info(f"Auto-challenge started for chat {chat_id} (first in {delay}s)")

# ══════════════════════════════════════════════════════════════════════════════
#  CHALLENGE WIN
# ══════════════════════════════════════════════════════════════════════════════
@with_data_lock
async def process_win(update: Update, context: ContextTypes.DEFAULT_TYPE,
                      user, chat_id: int, challenge: dict, extra_badge=None):
    group = get_group_db(chat_id)
    group["active_challenge"] = None
    save_group_db(chat_id, group)
    for job in context.job_queue.get_jobs_by_name(f"expire_{chat_id}"):
        job.schedule_removal()

    data = load_data()
    u    = get_user(data, user.id, user.username, user.full_name)
    coins = challenge["coins"]

    today = datetime.now().date().isoformat()
    yest  = (datetime.now().date() - timedelta(days=1)).isoformat()
    if u.get("last_win_date") in (today, yest): u["streak"] = u.get("streak", 0) + 1
    else: u["streak"] = 1
    u["last_win_date"] = today
    if u["streak"] > u.get("best_streak", 0): u["best_streak"] = u["streak"]

    streak_bonus = (u["streak"] - 1) * STREAK_BONUS
    coins += streak_bonus
    booster_line = ""
    if u.get("double_coins"):
        coins *= 2; u["double_coins"] = False; booster_line = "\n⚡ *Double Booster!*"

    u["coins"]            = u.get("coins", 0) + coins
    u["total_coins_ever"] = u.get("total_coins_ever", 0) + coins
    u["wins"]             = u.get("wins", 0) + 1
    u["weekly_wins"]      = u.get("weekly_wins", 0) + 1
    today_str = datetime.now().date().isoformat()
    if u.get("today_date") != today_str: u["today_date"] = today_str; u["today_wins"] = 0
    u["today_wins"] = u.get("today_wins", 0) + 1

    earned = check_badges(u)
    if extra_badge:
        b = award_badge(u, extra_badge)
        if b: earned.append(b)
    save_data(data)

    name      = _safe_md(f"@{user.username}" if user.username else user.full_name)
    title     = f"\n👑 *{u['title']}*" if u.get("title") else ""
    bonus_txt = f" (+{streak_bonus} streak)" if streak_bonus else ""
    s_line    = f"🔥 Streak: *{u['streak']}×*" if u["streak"] > 1 else ""
    msg = (f"🎉 *{name}* wins!{title}\n┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄\n"
           f"💰 +{coins:,} Forge Coins{bonus_txt}{booster_line}\n"
           f"🏦 Total: *{u['coins']:,}* | 🏆 Wins: *{u['wins']}*\n{s_line}")
    if earned:
        msg += "\n\n🆕 *Badges Earned!*\n" + "".join(f"  {b}\n" for b in earned)
    await update.message.reply_text(msg, parse_mode="Markdown")

# ══════════════════════════════════════════════════════════════════════════════
#  HUNT SYSTEM
# ══════════════════════════════════════════════════════════════════════════════
async def do_hunt(bot, chat_id: int, user_id: int, username=None, full_name=None, manual: bool = True):
    uid = str(user_id)
    doc = get_user_fast(uid, username, full_name)

    # Cooldown check
    cooldown = doc.get("hunt_cooldown")
    if cooldown:
        try:
            rem = (datetime.fromisoformat(cooldown) - datetime.now()).total_seconds()
            if rem > 0:
                return f"⏳ Hunt cooldown: *{int(rem)}s* left. Patience! 🌿"
        except Exception:
            pass

    cd_mult = get_cooldown_multiplier(doc)
    doc["hunt_cooldown"] = (datetime.now() + timedelta(seconds=int(15 * cd_mult))).isoformat()

    ws          = get_weapon_effective_stats(doc)
    catch_bonus = ws["catch_bonus"]
    pray_bonus  = 0.10 if has_pray_buff(doc) else 0
    catch_rate  = min(0.97, 0.55 + catch_bonus / 100 + pray_bonus)

    if random.random() > catch_rate:
        save_user_fast(uid)
        return random.choice(HUNT_FAILS)

    # Pets: manual /hunt only — never rolled for auto_hunt_job (manual=False).
    animal  = random.choice(PET_ANIMALS) if (manual and random.random() < PET_CATCH_CHANCE) else roll_animal()
    coins_e = max(1, int(animal["coins"] * (1 + ws["atk_bonus"] / 100) / 2))  # 2x nerf
    gems_e  = max(1, animal["gems"] // 2)  # 2x nerf

    # Boost checks
    boost = doc.get("owo_boost_expiry")
    if boost:
        try:
            if datetime.fromisoformat(boost) > datetime.now():
                coins_e *= 2; gems_e *= 2
        except Exception:
            pass
    if doc.get("double_coins"):
        coins_e *= 2; doc["double_coins"] = False

    doc["coins"]            = doc.get("coins", 0) + coins_e
    doc["gems"]             = doc.get("gems", 0) + gems_e
    doc["total_coins_ever"] = doc.get("total_coins_ever", 0) + coins_e
    doc["hunts"]            = doc.get("hunts", 0) + 1

    # Add to zoo
    zoo   = doc.get("animals", [])
    found = next((z for z in zoo if z["name"] == animal["name"]), None)
    if found: found["count"] = found.get("count", 1) + 1
    elif len(zoo) < 100:
        zoo.append({"name": animal["name"], "rarity": animal["rarity"], "count": 1,
                    "evolves_to": animal.get("evolves_to")})
    doc["animals"] = zoo

    badges = []
    if animal["rarity"] in ("rare","epic","legendary","Extreme","limited","mythic"):
        b = award_badge(doc, "rare_hunt")
        if b: badges.append(b)
    if animal["rarity"] in ("legendary","Extreme","limited","mythic"):
        b = award_badge(doc, "legend_hunt")
        if b: badges.append(b)
    if animal["rarity"] == "mythic":
        b = award_badge(doc, "mythic_catch")
        if b: badges.append(b)
    for check, key in [
        (doc.get("hunts",0)>=1,"first_hunt"),
        (doc.get("hunts",0)>=10,"hunter_10"),
    ]:
        if check:
            b = award_badge(doc, key)
            if b: badges.append(b)

    save_user_fast(uid)

    icon       = RARITY_COLORS.get(animal["rarity"], "⬜")
    badge_line = "\n🆕 " + " | ".join(badges) if badges else ""

    # Mythic announcement
    if animal["rarity"] == "mythic":
        try:
            nm = f"@{username}" if username and username != "Unknown" else full_name or "Someone"
            await bot.send_message(
                chat_id,
                f"🌈✨ *{fancy('MYTHIC CATCH!')}* ✨🌈\n"
                f"┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄\n"
                f"🎊 *{nm}* caught a *🕊️ Rara avis* 🌈*{fancy('MYTHIC')}*!\n"
                f"The odds were *1 in 1,000,000!* 🔥",
                parse_mode="Markdown",
            )
        except Exception:
            pass

    if animal.get("is_pet"):
        pet_word = "kitten" if animal.get("species") == "cat" else "pup"
        # Pet-drop announcement, mirrors the mythic broadcast — this is
        # rarer than ♠️ Spade (1-in-1000 vs ~1-in-101), worth flexing on.
        try:
            nm = f"@{username}" if username and username != "Unknown" else full_name or "Someone"
            await bot.send_message(
                chat_id,
                f"💗✨ *{fancy('COMPANION FOUND!')}* ✨💗\n"
                f"┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄\n"
                f"🎊 *{nm}* stumbled onto {animal['name']} while hunting!\n"
                f"The odds were *1 in 1,000!* 🔥",
                parse_mode="Markdown",
            )
        except Exception:
            pass
        return (f"💗 *A wild {pet_word} appeared!*\n"
                f"You found {animal['name']} — it's watching you from a distance, curious but shy.\n"
                f"+{coins_e:,} 🪙 | +{gems_e:,} 💎{badge_line}\n"
                f"_Use `/adopt` to take it home as your companion._")

    return (f"🎯 *Hunt successful!* _{ws['name']}_\n"
            f"Caught {animal['name']} {icon}*{animal['rarity'].upper()}*\n"
            f"+{coins_e:,} 🪙 | +{gems_e:,} 💎{badge_line}\n"
            f"_Coins: {doc['coins']:,} | Gems: {doc['gems']:,}_")

# ══════════════════════════════════════════════════════════════════════════════
#  ANIMAL EVOLUTION SYSTEM
# ══════════════════════════════════════════════════════════════════════════════
# Evolution coin costs per rarity — scales VERY steeply
EVOLVE_COSTS = {
    "common":    500,
    "uncommon":  2000,
    "rare":      8000,
    "epic":      30000,
    "legendary": 100000,
    "Extreme":   500000,
    "limited":   None,   # cannot evolve — it's already the reward
    "mythic":    None,   # cannot evolve
}

async def cmd_evolve(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    uid  = str(user.id)
    doc  = get_user_fast(uid)
    if not doc.get("animals"):
        await update.message.reply_text("🦁 No animals yet! Use /hunt first."); return
    if not context.args:
        lines = ["🧬 *Evolution Costs:*"]
        for r, cost in EVOLVE_COSTS.items():
            if cost: lines.append(f"  {RARITY_COLORS.get(r,'⬜')} {r.capitalize()} → *{cost:,} 🪙*")
        lines.append("\nUsage: `/evolve Dragon` (need 3 copies + coins)")
        await update.message.reply_text("\n".join(lines), parse_mode="Markdown"); return

    target_name = " ".join(context.args).strip()
    zoo = doc.get("animals", [])
    matched = next((z for z in zoo if target_name.lower() in z["name"].lower()), None)
    if not matched:
        await update.message.reply_text(f"❌ *{target_name}* not in your zoo!", parse_mode="Markdown"); return

    a_data = find_animal_data(matched["name"])
    if not a_data:
        await update.message.reply_text("❌ Unknown animal!"); return
    if a_data.get("evolved"):
        await update.message.reply_text("❌ Evolved animals can't be evolved again!"); return
    if not a_data.get("evolves_to"):
        await update.message.reply_text("❌ This animal has no evolution!"); return
    if matched.get("count", 1) < 3:
        have = matched.get("count", 1)
        await update.message.reply_text(
            f"❌ Need *3× {matched['name']}* to evolve. You have *{have}*.",
            parse_mode="Markdown"); return

    rarity = a_data.get("rarity", "common")
    cost   = EVOLVE_COSTS.get(rarity)
    if cost is None:
        await update.message.reply_text("❌ This rarity cannot be evolved."); return

    coins = doc.get("coins", 0)
    if coins < cost:
        await update.message.reply_text(
            f"❌ Need *{cost:,} 🪙* to evolve. You have *{coins:,}*.\n"
            f"_Tip: Evolution gets more expensive at higher rarities!_",
            parse_mode="Markdown"); return

    # Deduct cost, consume 3 animals, add evolved
    doc["coins"] = coins - cost
    if matched.get("count", 1) > 3:
        matched["count"] -= 3
    else:
        zoo.remove(matched)

    evolved_name = a_data["evolves_to"]
    e_data = find_animal_data(evolved_name)
    e_rarity = e_data["rarity"] if e_data else rarity

    e_existing = next((z for z in zoo if z["name"] == evolved_name), None)
    if e_existing:
        e_existing["count"] = e_existing.get("count", 1) + 1
    else:
        zoo.append({"name": evolved_name, "rarity": e_rarity, "count": 1, "evolves_to": None, "evolved": True})

    doc["animals"] = zoo
    b = award_badge(doc, "evolved")
    save_user_fast(uid)

    icon = RARITY_COLORS.get(e_rarity, "⬜")
    await update.message.reply_text(
        f"🧬 ✦ *{fancy('EVOLUTION!')}* ✦\n┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄\n"
        f"3× {matched['name']} → *{evolved_name}* {icon}\n"
        f"💸 Cost: *{cost:,} 🪙* | 💰 Balance: *{doc['coins']:,}*"
        + (f"\n\n{b}" if b else ""),
        parse_mode="Markdown")
# ══════════════════════════════════════════════════════════════════════════════
#  ADOPT & PET CARE SYSTEM
#  Pets (Snow Kitten, Husky Pup, etc — see PET_ANIMALS) are only obtainable
#  from a manual /hunt (see do_hunt(manual=...) / PET_CATCH_CHANCE). They
#  never come from autohunt or crates, can never be evolved, but CAN be sold
#  (either as an un-adopted zoo copy via /sell, or as your active companion
#  via /releasepet). Once adopted they become a live "pet" object with
#  hunger/affection that decays lazily over real time — no per-user
#  background polling needed for the numbers themselves, just for the
#  occasional unprompted "disturb" DM (see _pet_disturb_job below).
# ══════════════════════════════════════════════════════════════════════════════
PET_HUNGER_DECAY_MIN   = 12   # hunger −1 per this many real minutes
PET_NEGLECT_HOURS      = 6    # affection only starts dropping after this long untouched
PET_FEED_COST          = 20
PET_FEED_GAIN          = 40
PET_PAT_COOLDOWN_S     = 600
PET_PLAY_COOLDOWN_S    = 900
PET_MOOD_SWING_HOURS   = 3     # a random mood swing can reroll roughly this often
PET_MOOD_SWING_CHANCE  = 0.35  # odds a swing actually happens when it's due

# "playful" and "sleepy" are mood-swing-only states — they never come from
# hunger/affection maths directly (see _pet_mood), they're what makes a
# well-cared-for pet feel alive instead of just sitting at "happy" forever.
PET_MOOD_INFO = {
    # mood_key: (cat_emoji, cat_text, dog_emoji, dog_text)
    "happy":   ("😻", "purring and headbutting your hand",       "🐶", "wagging its tail like crazy"),
    "playful": ("😸", "batting at anything that moves",          "🐕‍🦺", "bouncing around, begging to play"),
    "sleepy":  ("😴", "curled into a tight, drowsy little loaf",  "🐩", "sprawled out, one ear twitching in its sleep"),
    "content": ("😺", "curled up calmly beside you",             "🐕", "resting its head on your lap"),
    "hungry":  ("😿", "meowing loudly at its empty bowl",        "🥺", "whining and staring at its empty bowl"),
    "sad":     ("😢", "hiding quietly, barely looking at you",   "😔", "lying in the corner, tail down"),
    "angry":   ("😾", "hissing and swatting at your hand",       "🐕‍🦺", "growling softly and turning away"),
}
PET_SOUNDS = {
    "cat": {
        "happy":   ["Purrrr~ 💗", "Mrrow! 😽", "Mew mew!"],
        "playful": ["Mrrrp! Mrow mrow!", "*pounces on nothing* Mew!", "Prrp?"],
        "sleepy":  ["...mrrrow~ *yawn*", "Mrr...zzz.", "*sleepy blink* mew."],
        "content": ["Mrow.", "Purr~"],
        "hungry":  ["MEOOOW!! 🍽️", "Mrrrow? (feed me)"],
        "sad":     ["...mew.", "*hides under the blanket*"],
        "angry":   ["HISS! 😾", "*flat ears, tail flicking*"],
    },
    "dog": {
        "happy":   ["Woof woof!! 🐾", "Bark bark!! 😄", "*happiest tail wag ever*"],
        "playful": ["Yip! Bark bark! (bring the ball!)", "*play-bows* Arf!", "Bark! Bark bark!"],
        "sleepy":  ["...woof~ *big yawn*", "*sleepy snort*", "Mmwoof...zzz."],
        "content": ["Woof.", "*content sniffing*"],
        "hungry":  ["WOOF WOOF (hungry!) 🍖", "*stares at food bowl, whining*"],
        "sad":     ["...woof.", "*sad little whimper*"],
        "angry":   ["Grr. 🐕‍🦺", "*low growl, backs away*"],
    },
}

def _pet_species(pet_or_name) -> str:
    """cat / dog, from a live pet dict or a raw species name."""
    name = pet_or_name.get("species_name") if isinstance(pet_or_name, dict) else pet_or_name
    d = find_animal_data(name) if name else None
    return (d or {}).get("species", "cat")

def _tick_pet(pet: dict) -> dict:
    """Lazily decays hunger (always) and affection (only once genuinely
    neglected) based on real elapsed time — no scheduled job required just
    to keep the numbers honest; this runs on every read/write touchpoint.
    Also occasionally rolls a random mood swing (playful/sleepy) when the
    pet's baseline mood is already good, so a well-cared-for pet still
    feels like it has its own little moods instead of sitting at a flat
    "happy" forever."""
    if not pet:
        return pet
    now = datetime.now()
    last_tick = pet.get("last_tick") or pet.get("adopted_at") or now.isoformat()
    try:
        elapsed_min = max(0, (now - datetime.fromisoformat(last_tick)).total_seconds() / 60)
    except Exception:
        elapsed_min = 0
    drop = int(elapsed_min // PET_HUNGER_DECAY_MIN)
    if drop:
        pet["hunger"] = max(0, pet.get("hunger", 80) - drop)

    last_int = pet.get("last_interacted", last_tick)
    try:
        idle_h = max(0, (now - datetime.fromisoformat(last_int)).total_seconds() / 3600)
    except Exception:
        idle_h = 0
    if idle_h > PET_NEGLECT_HOURS:
        aff_drop = int((idle_h - PET_NEGLECT_HOURS) // 3)
        if pet.get("hunger", 80) == 0:
            aff_drop += 2
        if aff_drop:
            pet["affection"] = max(0, pet.get("affection", 60) - aff_drop)

    # Mood swings — only kick in when the pet is otherwise doing fine, so
    # they read as personality rather than masking real neglect.
    baseline = _pet_mood_baseline(pet)
    if baseline in ("happy", "content"):
        swing_at = pet.get("mood_swing_at")
        due = True
        if swing_at:
            try:
                due = (now - datetime.fromisoformat(swing_at)).total_seconds() / 3600 > PET_MOOD_SWING_HOURS
            except Exception:
                due = True
        if due and random.random() < PET_MOOD_SWING_CHANCE:
            pet["mood_swing"] = random.choice(["playful", "sleepy", None, None])
            pet["mood_swing_at"] = now.isoformat()
    else:
        pet["mood_swing"] = None

    pet["last_tick"] = now.isoformat()
    return pet

def _pet_mood_baseline(pet: dict) -> str:
    """Mood purely from hunger/affection numbers, ignoring any mood swing."""
    hunger, affection = pet.get("hunger", 80), pet.get("affection", 60)
    if hunger <= 15:
        return "hungry"
    if affection <= 15:
        return "angry"
    if affection <= 35:
        return "sad"
    if hunger >= 60 and affection >= 60:
        return "happy"
    return "content"

def _pet_mood(pet: dict) -> str:
    baseline = _pet_mood_baseline(pet)
    if baseline in ("happy", "content") and pet.get("mood_swing"):
        return pet["mood_swing"]
    return baseline

def _pet_bar(val: int) -> str:
    val = max(0, min(100, val))
    filled = round(val / 10)
    return "█" * filled + "░" * (10 - filled)

def _pet_display_name(pet: dict) -> str:
    return pet.get("nickname") or pet.get("species_name", "Pet")

def _pet_sound(pet: dict) -> str:
    species = _pet_species(pet)
    mood = _pet_mood(pet)
    return random.choice(PET_SOUNDS.get(species, PET_SOUNDS["cat"])[mood])

def _pet_status_text(pet: dict, owner_name: str) -> str:
    species = _pet_species(pet)
    mood = _pet_mood(pet)
    cat_e, cat_t, dog_e, dog_t = PET_MOOD_INFO[mood]
    emoji, desc = (cat_e, cat_t) if species == "cat" else (dog_e, dog_t)
    idle = ""
    try:
        away = (datetime.now() - datetime.fromisoformat(pet.get("last_interacted", pet["adopted_at"]))).total_seconds()
        if away > 3600:
            idle = f"\n_Hasn't seen you in {fmt_duration(away)}._"
    except Exception:
        pass
    subtitle = f" — {pet.get('species_name','')}" if pet.get("nickname") else ""
    return (
        f"{emoji} *{_safe_md(_pet_display_name(pet))}*{subtitle}\n{DIV}\n"
        f"{DOT} Hunger    [{_pet_bar(pet.get('hunger',80))}] {pet.get('hunger',80)}/100\n"
        f"{DOT} Affection [{_pet_bar(pet.get('affection',60))}] {pet.get('affection',60)}/100\n"
        f"{DOT} Mood: *{mood.capitalize()}* — {desc}\n"
        f"\"_{_pet_sound(pet)}_\"{idle}"
    )

def _pet_action_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("🍖 Feed", callback_data="pet_feed"),
        InlineKeyboardButton("🖐️ Pat", callback_data="pet_pat"),
        InlineKeyboardButton("💬 Talk", callback_data="pet_talk"),
    ], [
        InlineKeyboardButton("🏷️ Rename", callback_data="pet_rename"),
        InlineKeyboardButton("🕊️ Release", callback_data="pet_release"),
    ]])

def _pet_release_confirm_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("💔 Yes, release", callback_data="pet_release_yes"),
        InlineKeyboardButton("❌ No, keep them", callback_data="pet_release_no"),
    ]])

# ---- talking to your pet -----------------------------------------------
# Pets can't understand words, but they react to *tone* — a handful of
# keyword buckets plus their current mood decide the flavor text, and the
# actual "reply" is always just their species sounds (barks/meows), never
# real language. This keeps it feeling like a real animal instead of a
# chatbot in a pet costume.
_PET_TALK_KEYWORDS = [
    (("love", "good boy", "good girl", "good pet", "cute", "sweet", "adorable"),
     "melts a little — they don't know the words, but they know that tone."),
    (("food", "hungry", "eat", "treat", "snack", "dinner"),
     "perks up instantly — did somebody say food?"),
    (("play", "fetch", "ball", "toy", "game"),
     "spins in an excited little circle, ready to go."),
    (("sorry", "miss you", "missed you", "back now", "i'm back"),
     "presses in close against you, forgiving instantly."),
    (("bad", "no", "stop", "don't"),
     "flattens slightly, unsure if they did something wrong."),
]

def _pet_talk_response(pet: dict, message_text: str) -> str:
    species = _pet_species(pet)
    mood = _pet_mood(pet)
    pool = PET_SOUNDS.get(species, PET_SOUNDS["cat"])[mood]
    reply = " ".join(random.sample(pool, k=min(2, len(pool)))) if len(pool) > 1 else pool[0]

    lowered = message_text.lower()
    vibe = None
    for keywords, flavor in _PET_TALK_KEYWORDS:
        if any(k in lowered for k in keywords):
            vibe = flavor
            break
    if vibe is None:
        if "?" in message_text:
            vibe = "tilts their head, clearly wondering what you're asking."
        elif mood == "angry":
            vibe = "isn't really in the mood to listen right now."
        elif mood == "sad":
            vibe = "barely reacts, still a little down."
        elif mood in ("happy", "playful"):
            vibe = "listens with their whole body, tail going a mile a minute."
        elif mood == "sleepy":
            vibe = "cracks one eye open, then lets it drift shut again."
        else:
            vibe = "watches you with quiet, unreadable interest."

    return f"\"{reply}\"\n_{vibe}_"

async def cmd_adopt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    uid = str(user.id)
    doc = get_user_fast(uid, user.username, user.full_name)

    if not context.args:
        zoo = doc.get("animals", [])
        candidates = [z for z in zoo if find_animal_data(z["name"]) and find_animal_data(z["name"]).get("is_pet")]
        lines = [card("Adopt a Companion")]
        if doc.get("pet"):
            _tick_pet(doc["pet"])
            lines.append(f"{DOT} You already have a companion: *{_safe_md(_pet_display_name(doc['pet']))}*.")
            lines.append("_Use /releasepet first if you want to adopt a different one._")
        elif candidates:
            lines.append("These are waiting in your zoo, caught while hunting:")
            for c in candidates:
                lines.append(f"{BUL} {c['name']} ×{c.get('count',1)}")
            lines.append(f"\n_Usage:_ `/adopt <name>`")
        else:
            lines.append("No companions in your zoo yet.")
            lines.append("_Keep using /hunt — pets are ~1-in-1000, rarer than ♠️ Spade, manual hunts only!_")
        save_user_fast(uid)
        await update.message.reply_text("\n".join(lines), parse_mode="Markdown")
        return

    if doc.get("pet"):
        await update.message.reply_text(
            f"{XX} You already have *{_safe_md(_pet_display_name(doc['pet']))}* as your companion.\n"
            f"_Use /releasepet first if you want to adopt a different one._", parse_mode="Markdown")
        return

    target = " ".join(context.args).strip().lower()
    zoo = doc.get("animals", [])
    entry = next((z for z in zoo if target in z["name"].lower()
                  and find_animal_data(z["name"]) and find_animal_data(z["name"]).get("is_pet")), None)
    if not entry:
        await update.message.reply_text(f"{XX} No adoptable pet matching '*{target}*' in your zoo. Try /hunt!",
                                         parse_mode="Markdown")
        return

    # Consume one copy from the zoo — it stops being a collectible and
    # becomes your living companion.
    if entry.get("count", 1) > 1:
        entry["count"] -= 1
    else:
        zoo.remove(entry)
    doc["animals"] = zoo

    now_iso = datetime.now().isoformat()
    doc["pet"] = {
        "species_name": entry["name"], "nickname": None,
        "hunger": 80, "affection": 60,
        "adopted_at": now_iso, "last_interacted": now_iso, "last_tick": now_iso,
        "last_fed": None,
    }
    b = award_badge(doc, "pet_adopter")
    save_user_fast(uid)
    _schedule_pet_disturb(context, user.id)

    await update.message.reply_text(
        f"{card('New Companion!')}\n"
        f"{entry['name']} is now yours to look after. 💗\n"
        f"Feed it and check in — it has real moods, and it *will* notice if you vanish.\n"
        f"_Use /mypet any time._" + (f"\n\n{b}" if b else ""),
        parse_mode="Markdown")

async def cmd_mypet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    uid = str(user.id)
    doc = get_user_fast(uid, user.username, user.full_name)
    pet = doc.get("pet")
    if not pet:
        await update.message.reply_text(
            f"{card('No Companion Yet')}\nYou haven't adopted a pet.\n_Manual /hunt has a ~1-in-1000 chance to find one, rarer than ♠️ Spade — then /adopt it!_",
            parse_mode="Markdown")
        return
    _tick_pet(pet)
    save_user_fast(uid)
    await update.message.reply_text(_pet_status_text(pet, user.full_name),
                                     reply_markup=_pet_action_kb(), parse_mode="Markdown")

async def cmd_releasepet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    uid = str(user.id)
    doc = get_user_fast(uid, user.username, user.full_name)
    pet = doc.get("pet")
    if not pet:
        await update.message.reply_text(f"{XX} You don't have a companion to release."); return
    a_data = find_animal_data(pet["species_name"]) or {}
    refund = a_data.get("sell", 30)
    name = _pet_display_name(pet)
    await update.message.reply_text(
        f"💔 Release *{_safe_md(name)}* back into the wild for +{refund:,} 🪙?\n"
        f"_This can't be undone — you'll need to find another one to adopt again "
        f"(and pets are ~1-in-1000, rarer than ♠️ Spade)._",
        reply_markup=_pet_release_confirm_kb(), parse_mode="Markdown")

async def handle_pet_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = query.from_user
    uid = str(user.id)
    doc = get_user_fast(uid, user.username, user.full_name)
    pet = doc.get("pet")
    action = query.data.replace("pet_", "")

    # Release confirm/cancel don't need a live pet check to bail cleanly —
    # if it's already gone (e.g. double-tap), just say so instead of a
    # generic "no companion" alert.
    if action in ("release_yes", "release_no"):
        if action == "release_no":
            try:
                await query.answer("Phew — they're staying with you. 💗")
            except (BadRequest, TelegramError):
                pass
            if pet:
                await _safe_edit_message_text(query, _pet_status_text(pet, user.full_name),
                                               reply_markup=_pet_action_kb(), parse_mode="Markdown")
            return
        # release_yes
        if not pet:
            await query.answer("Already released.", show_alert=True)
            return
        try:
            await query.answer()
        except (BadRequest, TelegramError):
            pass
        a_data = find_animal_data(pet["species_name"]) or {}
        refund = a_data.get("sell", 30)
        doc["coins"] = doc.get("coins", 0) + refund
        doc["total_coins_ever"] = doc.get("total_coins_ever", 0) + refund
        name = _pet_display_name(pet)
        doc["pet"] = None
        save_user_fast(uid)
        for job in context.job_queue.get_jobs_by_name(f"petdisturb_{user.id}"):
            job.schedule_removal()
        await _safe_edit_message_text(
            query, f"🕊️ *{_safe_md(name)}* has been released back into the wild.\n+{refund:,} 🪙\n"
                   f"_It'll be okay — pets are resilient. You can adopt again anytime._",
            parse_mode="Markdown")
        return

    if not pet:
        await query.answer("You don't have a companion right now.", show_alert=True)
        return
    _tick_pet(pet)

    if action == "feed":
        if doc.get("coins", 0) < PET_FEED_COST:
            await query.answer(f"Need {PET_FEED_COST} 🪙 to feed your pet!", show_alert=True)
            return
        doc["coins"] -= PET_FEED_COST
        pet["hunger"] = min(100, pet.get("hunger", 80) + PET_FEED_GAIN)
        pet["affection"] = min(100, pet.get("affection", 60) + 3)
        pet["last_fed"] = datetime.now().isoformat()
        pet["last_interacted"] = datetime.now().isoformat()
        b_bond = award_badge(doc, "pet_bonded") if pet["affection"] >= 100 else None
        save_user_fast(uid)
        await query.answer(f"Fed! \"{_pet_sound(pet)}\"" + (" 🏆 New achievement!" if b_bond else ""))
        status = _pet_status_text(pet, user.full_name) + (f"\n\n{b_bond}" if b_bond else "")
        await _safe_edit_message_text(query, status,
                                       reply_markup=_pet_action_kb(), parse_mode="Markdown")

    elif action == "pat":
        last = pet.get("last_pat")
        if last:
            try:
                rem = PET_PAT_COOLDOWN_S - (datetime.now() - datetime.fromisoformat(last)).total_seconds()
                if rem > 0:
                    await query.answer(f"Give it a bit — {int(rem)}s cooldown.", show_alert=True)
                    return
            except Exception:
                pass
        pet["affection"] = min(100, pet.get("affection", 60) + 5)
        pet["last_pat"] = datetime.now().isoformat()
        pet["last_interacted"] = datetime.now().isoformat()
        b_bond = award_badge(doc, "pet_bonded") if pet["affection"] >= 100 else None
        save_user_fast(uid)
        await query.answer(f"\"{_pet_sound(pet)}\"" + (" 🏆 New achievement!" if b_bond else ""))
        status = _pet_status_text(pet, user.full_name) + (f"\n\n{b_bond}" if b_bond else "")
        await _safe_edit_message_text(query, status,
                                       reply_markup=_pet_action_kb(), parse_mode="Markdown")

    elif action == "talk":
        try:
            await query.answer()
        except (BadRequest, TelegramError):
            pass
        context.chat_data["awaiting_pet_talk"] = user.id
        name = _pet_display_name(pet)
        await query.message.reply_text(
            f"💬 Say anything to *{_safe_md(name)}* — type it next. They won't understand the "
            f"words, but they'll react to the tone. 🐾",
            parse_mode="Markdown")

    elif action == "rename":
        try:
            await query.answer()
        except (BadRequest, TelegramError):
            pass  # stale/expired callback query — safe to ignore, continue handling
        context.chat_data["awaiting_pet_rename"] = user.id
        await query.message.reply_text("🏷️ Send the new nickname for your pet (reply to this message not required, just type it next).")

    elif action == "release":
        try:
            await query.answer()
        except (BadRequest, TelegramError):
            pass  # stale/expired callback query — safe to ignore, continue handling
        a_data = find_animal_data(pet["species_name"]) or {}
        refund = a_data.get("sell", 30)
        name = _pet_display_name(pet)
        await _safe_edit_message_text(
            query,
            f"💔 Release *{_safe_md(name)}* back into the wild for +{refund:,} 🪙?\n"
            f"_This can't be undone — you'll need to find another one to adopt again "
            f"(and pets are ~1-in-1000, rarer than ♠️ Spade)._",
            reply_markup=_pet_release_confirm_kb(), parse_mode="Markdown")

async def handle_pet_rename_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Called from handle_message when a pet-rename is pending. Returns True
    if it consumed this message."""
    pending_uid = context.chat_data.get("awaiting_pet_rename")
    user = update.message.from_user
    if not pending_uid or pending_uid != user.id:
        return False
    context.chat_data["awaiting_pet_rename"] = None
    nickname = (update.message.text or "").strip()[:24]
    if not nickname:
        return False
    doc = get_user_fast(str(user.id), user.username, user.full_name)
    if not doc.get("pet"):
        return False
    doc["pet"]["nickname"] = nickname
    save_user_fast(str(user.id))
    await update.message.reply_text(f"🏷️ Your companion is now named *{_safe_md(nickname)}*! 💗", parse_mode="Markdown")
    return True

async def handle_pet_talk_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Called from handle_message when a free-text 'talk to your pet' is
    pending (set by the 💬 Talk button). Returns True if it consumed this
    message. Talking is a light, low-cooldown affection nudge — it's about
    connection, not a stat grind."""
    pending_uid = context.chat_data.get("awaiting_pet_talk")
    user = update.message.from_user
    if not pending_uid or pending_uid != user.id:
        return False
    context.chat_data["awaiting_pet_talk"] = None
    said = (update.message.text or "").strip()
    if not said:
        return False
    uid = str(user.id)
    doc = get_user_fast(uid, user.username, user.full_name)
    pet = doc.get("pet")
    if not pet:
        return False
    _tick_pet(pet)
    pet["affection"] = min(100, pet.get("affection", 60) + 2)
    pet["last_interacted"] = datetime.now().isoformat()
    b_talk = award_badge(doc, "pet_talker")
    b_bond = award_badge(doc, "pet_bonded") if pet["affection"] >= 100 else None
    save_user_fast(uid)
    species_emoji = "🐱" if _pet_species(pet) == "cat" else "🐶"
    name = _pet_display_name(pet)
    badges_txt = "\n\n".join(x for x in (b_talk, b_bond) if x)
    await update.message.reply_text(
        f"{species_emoji} *{_safe_md(name)}*\n{_pet_talk_response(pet, said)}" + (f"\n\n{badges_txt}" if badges_txt else ""),
        parse_mode="Markdown")
    return True

# ---- pets sometimes disturb you, like a real one would ---------------------
async def _pet_disturb_job(context: ContextTypes.DEFAULT_TYPE):
    d = context.job.data; user_id = d["user_id"]
    uid = str(user_id)
    doc = get_user_fast(uid)
    pet = doc.get("pet")
    if not pet:
        context.job.schedule_removal(); return
    _tick_pet(pet)
    mood = _pet_mood(pet)
    # Neglected pets are pushier about it; content/happy/playful/sleepy ones
    # rarely bother you. Keys must cover every mood _pet_mood() can return —
    # see PET_MOOD_INFO for the full set.
    chance = {"angry": 0.55, "sad": 0.35, "hungry": 0.4, "content": 0.12,
              "happy": 0.08, "playful": 0.18, "sleepy": 0.04}.get(mood, 0.1)
    save_user_fast(uid)
    if random.random() > chance:
        return
    cat_e, cat_t, dog_e, dog_t = PET_MOOD_INFO[mood]
    species = _pet_species(pet)
    emoji = cat_e if species == "cat" else dog_e
    name = _pet_display_name(pet)
    sound = _pet_sound(pet)
    nudge = {
        "hungry":  "_Might be time to `/mypet` and feed it._",
        "angry":   "_It's really upset — try `/mypet` and give it some attention._",
        "sad":     "_It's missed you. `/mypet` to check in._",
        "playful": "_Looks like it wants to play — `/mypet` and give it a pat._",
        "content": "", "happy": "", "sleepy": "",
    }.get(mood, "")
    text = f"{emoji} *{_safe_md(name)}*: \"{sound}\"" + (f"\n{nudge}" if nudge else "")
    try:
        await context.bot.send_message(user_id, text, parse_mode="Markdown")
    except TelegramError:
        pass

def _schedule_pet_disturb(context: ContextTypes.DEFAULT_TYPE, user_id: int):
    for job in context.job_queue.get_jobs_by_name(f"petdisturb_{user_id}"):
        job.schedule_removal()
    context.job_queue.run_repeating(
        _pet_disturb_job, interval=random.randint(2700, 5400), first=random.randint(900, 2700),
        data={"user_id": user_id}, name=f"petdisturb_{user_id}")

def _reschedule_active_pets(application):
    """Same idea as _reschedule_active_autohunts — restores the disturb job
    for anyone who had an adopted pet before a restart cleared the queue."""
    try:
        data = load_data()
        for uid, u in data["users"].items():
            if u.get("pet"):
                application.job_queue.run_repeating(
                    _pet_disturb_job, interval=random.randint(2700, 5400), first=random.randint(900, 2700),
                    data={"user_id": int(uid)}, name=f"petdisturb_{uid}")
    except Exception as e:
        logger.warning(f"_reschedule_active_pets failed: {e}")

# ══════════════════════════════════════════════════════════════════════════════
#  WEAPON UPGRADE SYSTEM
# ══════════════════════════════════════════════════════════════════════════════
async def cmd_upgradeweapon(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    uid  = str(user.id)
    doc  = get_user_fast(uid)

    wkey   = doc.get("weapon", "stick")
    if wkey == "stick":
        await update.message.reply_text("❌ Can't upgrade the basic stick! Buy a weapon in /gemshop first."); return

    w      = WEAPONS.get(wkey, WEAPONS["stick"])
    levels = doc.setdefault("weapon_levels", {})
    curr_lv = levels.get(wkey, 0)

    if curr_lv >= 5:
        await update.message.reply_text(
            f"✅ *{w['name']}* is already at *{fancy('MAX LEVEL 5!')}* 🔥", parse_mode="Markdown"); return

    next_lv                = curr_lv + 1
    cost_coins, cost_gems  = WEAPON_UPGRADE_COST[next_lv]
    extra_atk              = WEAPON_UPGRADE_BONUS[next_lv]

    # Show info if no confirm arg — a "✅ Confirm Upgrade" button does the same
    # thing as typing `/upgradeweapon confirm`, kept for backward compatibility.
    if not context.args or context.args[0].lower() != "confirm":
        await update.message.reply_text(
            f"⚔️ *Weapon Upgrade*\n"
            f"┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄\n"
            f"Weapon: *{w['name']}* Lv.{curr_lv}\n"
            f"→ Upgrade to *Lv.{next_lv}*\n\n"
            f"💰 Cost: *{cost_coins:,} coins* + *{cost_gems} 💎*\n"
            f"📈 New ATK Bonus: *+{w['atk_bonus'] + extra_atk}*",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("✅ Confirm Upgrade", callback_data="upgrade_confirm")]]),
            parse_mode="Markdown"); return

    ok, msg = _perform_weapon_upgrade(uid)
    await update.message.reply_text(msg, parse_mode="Markdown")

def _perform_weapon_upgrade(uid: str):
    """Shared by the /upgradeweapon confirm arg and the ✅ Confirm Upgrade
    button so both paths apply the exact same checks and cost."""
    doc = get_user_fast(uid)
    wkey = doc.get("weapon", "stick")
    if wkey == "stick":
        return False, "❌ Can't upgrade the basic stick! Buy a weapon in /gemshop first."
    w = WEAPONS.get(wkey, WEAPONS["stick"])
    levels = doc.setdefault("weapon_levels", {})
    curr_lv = levels.get(wkey, 0)
    if curr_lv >= 5:
        return False, f"✅ *{w['name']}* is already at *{fancy('MAX LEVEL 5!')}* 🔥"
    next_lv = curr_lv + 1
    cost_coins, cost_gems = WEAPON_UPGRADE_COST[next_lv]
    extra_atk = WEAPON_UPGRADE_BONUS[next_lv]
    if doc.get("coins", 0) < cost_coins:
        return False, f"❌ Need *{cost_coins:,} 🪙*. Have *{doc.get('coins',0):,}*."
    if doc.get("gems", 0) < cost_gems:
        return False, f"❌ Need *{cost_gems} 💎*. Have *{doc.get('gems',0)}*."
    doc["coins"] = doc.get("coins", 0) - cost_coins
    doc["gems"]  = doc.get("gems", 0) - cost_gems
    levels[wkey] = next_lv
    doc["weapon_levels"] = levels
    b = award_badge(doc, "upgraded")
    max_b = award_badge(doc, "weapon_max") if next_lv >= 5 else None
    badge_txt = "".join(f"\n\n{x}" for x in (b, max_b) if x)
    save_user_fast(uid)
    return True, (
        f"⚔️ *{fancy('WEAPON UPGRADED!')}*\n"
        f"┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄\n"
        f"*{w['name']} Lv.{next_lv}* ({'⭐'*next_lv})\n"
        f"ATK Bonus: *+{w['atk_bonus'] + extra_atk}* | Catch: *+{w['catch_bonus'] + extra_atk}%*\n"
        f"💰 {doc['coins']:,} 🪙 | 💎 {doc['gems']} remaining{badge_txt}"
    )

async def handle_upgrade_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = query.from_user
    try:
        await query.answer()
    except (BadRequest, TelegramError):
        pass  # stale/expired callback query — safe to ignore, continue handling
    _, msg = _perform_weapon_upgrade(str(user.id))
    try:
        await query.edit_message_text(msg, parse_mode="Markdown")
    except BadRequest:
        pass

# ══════════════════════════════════════════════════════════════════════════════
#  CASINO  (with animations)
# ══════════════════════════════════════════════════════════════════════════════
# Same "flex it" growth touchpoint as hunting (see _hunt_share_url), triggered
# at the same 200-coin bar as the existing "big_win" badge so it lines up with
# a moment the player already feels good about instead of every tiny win.
async def _casino_share_kb(context: ContextTypes.DEFAULT_TYPE, user, won_amount: int, caption: str):
    if won_amount < 200:
        return None
    try:
        bot_username = (await context.bot.get_me()).username
    except Exception:
        return None
    link = f"https://t.me/{bot_username}?start=ref_{user.id}"
    share_url = f"https://t.me/share/url?url={quote(link, safe='')}&text={quote(caption)}"
    return InlineKeyboardMarkup([[InlineKeyboardButton("📤 Flex This Win", url=share_url)]])

@with_data_lock
async def cmd_cf(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    data = load_data()
    u    = get_user(data, user.id, user.username, user.full_name)
    if len(context.args) < 2:
        await update.message.reply_text("Usage: `/cf <amount> heads` or `/cf <amount> tails`", parse_mode="Markdown"); return
    try: amount = int(context.args[0])
    except Exception: await update.message.reply_text("❌ Amount must be a number."); return
    if amount <= 0: await update.message.reply_text("❌ Must be positive!"); return
    if amount > u["coins"]: await update.message.reply_text(f"❌ Not enough coins! You have *{u['coins']:,}* 🪙.", parse_mode="Markdown"); return
    choice = context.args[1].lower().rstrip("s")
    if choice not in ("head", "tail"):
        await update.message.reply_text("❌ Choose *heads* or *tails*!", parse_mode="Markdown"); return

    # Animation
    msg = await update.message.reply_text("🪙 *Flipping the coin...*", parse_mode="Markdown")
    await asyncio.sleep(1.2)
    await msg.edit_text("🪙 *The coin is spinning...*  🌀", parse_mode="Markdown")
    await asyncio.sleep(1.0)

    praying    = has_pray_buff(u)
    win_chance = 0.575 if praying else 0.50
    pray_line  = "\n🙏 *Pray buff!* +7.5% luck" if praying else ""
    won        = random.random() < win_chance
    result     = "heads" if (choice == "head") == won else "tails"
    result_disp = "HEADS 🦅" if result == "heads" else "TAILS 🦁"

    if won:
        u["coins"] += amount; u["total_coins_ever"] = u.get("total_coins_ever",0) + amount
        u["casino_wins"] = u.get("casino_wins",0) + 1
        u["casino_total_won"] = u.get("casino_total_won",0) + amount
        badges = check_badges(u); save_data(data)
        bl = "\n🆕 "+" | ".join(badges) if badges else ""
        share_kb = await _casino_share_kb(context, user, amount, "I just won big on Aira's coin flip 🪙 — come try your luck!")
        await msg.edit_text(
            f"🪙 *{fancy('COIN FLIP')}*{pray_line}\n"
            f"┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄\n"
            f"Result: *{result_disp}*\n\n"
            f"✅ *{fancy('YOU WIN!')}*\n+{amount:,} 🪙 | Balance: *{u['coins']:,}*{bl}",
            reply_markup=share_kb,
            parse_mode="Markdown")
    else:
        u["coins"] -= amount; save_data(data)
        await msg.edit_text(
            f"🪙 *{fancy('COIN FLIP')}*{pray_line}\n"
            f"┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄\n"
            f"Result: *{result_disp}*\n\n"
            f"❌ *{fancy('YOU LOSE!')}*\n-{amount:,} 🪙 | Balance: *{u['coins']:,}*",
            parse_mode="Markdown")

@with_data_lock
async def cmd_slots(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user; data = load_data()
    u = get_user(data, user.id, user.username, user.full_name)
    if not context.args:
        await update.message.reply_text("Usage: `/s <amount>`", parse_mode="Markdown"); return
    try: amount = int(context.args[0])
    except Exception: await update.message.reply_text("❌ Amount must be a number."); return
    if amount <= 0 or amount > u["coins"]:
        await update.message.reply_text(f"❌ Invalid amount. You have *{u['coins']:,}* 🪙.", parse_mode="Markdown"); return

    msg = await update.message.reply_text("🎰 *Spinning...*  🔄🔄🔄", parse_mode="Markdown")
    await asyncio.sleep(0.8)
    await msg.edit_text("🎰 *Spinning...*  🎲🎲🎲", parse_mode="Markdown")
    await asyncio.sleep(0.8)

    praying   = has_pray_buff(u)
    pray_line = "\n🙏 *Pray buff!*" if praying else ""
    SLOT_EMOJIS = ["🍒","🍋","🍊","⭐","💎","🔔","7️⃣"]
    reels = [random.choice(SLOT_EMOJIS) for _ in range(3)]
    if praying and reels[0] != reels[1] != reels[2]:
        if random.random() < 0.20:
            reels[2] = reels[random.randint(0,1)]
    display = " | ".join(reels)

    if reels[0] == reels[1] == reels[2]:
        mult = {"💎":10,"7️⃣":7,"⭐":5}.get(reels[0], 3)
        win  = amount * mult
        u["coins"] += win; u["total_coins_ever"] = u.get("total_coins_ever",0) + win
        u["casino_wins"] = u.get("casino_wins",0) + 1; u["casino_total_won"] = u.get("casino_total_won",0) + win
        badges = check_badges(u); save_data(data)
        bl = "\n🆕 "+" | ".join(badges) if badges else ""
        share_kb = await _casino_share_kb(context, user, win, "I just hit a JACKPOT on Aira's slots 🎰 — come try your luck!")
        await msg.edit_text(
            f"🎰 *{fancy('SLOTS')}*{pray_line}\n[ {display} ]\n\n🎊 *JACKPOT ×{mult}!*\n+{win:,} 🪙 | Balance: *{u['coins']:,}*{bl}",
            reply_markup=share_kb,
            parse_mode="Markdown")
    elif reels[0]==reels[1] or reels[1]==reels[2] or reels[0]==reels[2]:
        u["coins"] += amount; u["total_coins_ever"] = u.get("total_coins_ever",0) + amount
        u["casino_wins"] = u.get("casino_wins",0) + 1; u["casino_total_won"] = u.get("casino_total_won",0) + amount
        save_data(data)
        await msg.edit_text(
            f"🎰 *{fancy('SLOTS')}*{pray_line}\n[ {display} ]\n\n✅ *Two match! ×1*\n+{amount:,} 🪙 | Balance: *{u['coins']:,}*",
            parse_mode="Markdown")
    else:
        u["coins"] -= amount; save_data(data)
        await msg.edit_text(
            f"🎰 *{fancy('SLOTS')}*{pray_line}\n[ {display} ]\n\n❌ *No match.* -{amount:,} 🪙 | Balance: *{u['coins']:,}*",
            parse_mode="Markdown")

@with_data_lock
async def cmd_dice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user; data = load_data()
    u = get_user(data, user.id, user.username, user.full_name)
    if len(context.args) < 2:
        await update.message.reply_text("Usage: `/dice <amount> <1-6>`", parse_mode="Markdown"); return
    try: amount = int(context.args[0]); guess = int(context.args[1])
    except Exception: await update.message.reply_text("❌ Use numbers only."); return
    if not 1 <= guess <= 6: await update.message.reply_text("❌ Pick 1-6!"); return
    if amount <= 0 or amount > u["coins"]:
        await update.message.reply_text(f"❌ Invalid amount. You have *{u['coins']:,}* 🪙.", parse_mode="Markdown"); return

    dice_faces = ["","1️⃣","2️⃣","3️⃣","4️⃣","5️⃣","6️⃣"]
    msg = await update.message.reply_text(f"🎲 *Rolling the dice...* You picked {dice_faces[guess]}!", parse_mode="Markdown")
    await asyncio.sleep(1.2)

    praying   = has_pray_buff(u)
    pray_line = "\n🙏 *Pray buff!*" if praying else ""
    roll = random.randint(1, 6)
    if praying and roll != guess and random.random() < 0.20:
        roll = guess

    if roll == guess:
        win = amount * 3; u["coins"] += win; u["total_coins_ever"] = u.get("total_coins_ever",0) + win
        u["casino_wins"] = u.get("casino_wins",0) + 1; u["casino_total_won"] = u.get("casino_total_won",0) + win
        badges = check_badges(u); save_data(data)
        bl = "\n🆕 "+" | ".join(badges) if badges else ""
        share_kb = await _casino_share_kb(context, user, win, "I just called the dice roll on Aira 🎲 — come try your luck!")
        await msg.edit_text(
            f"🎲 *{fancy('DICE')}*{pray_line}\nYour pick: {dice_faces[guess]} | Rolled: {dice_faces[roll]}\n\n🎊 *CORRECT! ×3!*\n+{win:,} 🪙 | Balance: *{u['coins']:,}*{bl}",
            reply_markup=share_kb,
            parse_mode="Markdown")
    else:
        u["coins"] -= amount; save_data(data)
        await msg.edit_text(
            f"🎲 *{fancy('DICE')}*{pray_line}\nYour pick: {dice_faces[guess]} | Rolled: {dice_faces[roll]}\n\n❌ *Wrong!* -{amount:,} 🪙 | Balance: *{u['coins']:,}*",
            parse_mode="Markdown")

# ══════════════════════════════════════════════════════════════════════════════
#  PVP BATTLE  (with animation)
# ══════════════════════════════════════════════════════════════════════════════
RARITY_POWER = {"common":10,"uncommon":20,"rare":40,"epic":70,"legendary":120,"Extreme":500,"limited":650,"mythic":1500}
WEAPON_POWER = {"stick":0,"bow":10,"spear":25,"rifle":50,"laser":90,"dragonblade":200,"sayan":500,"mace":700}

def find_animal_data(name):
    return next((a for a in ANIMALS if name.lower() in a["name"].lower()), None)

def get_team_power(team_names, user_doc):
    wkey    = user_doc.get("weapon", "stick")
    ws      = get_weapon_effective_stats(user_doc)
    power   = WEAPON_POWER.get(wkey, 0) + ws["atk_bonus"]
    for name in team_names:
        a = find_animal_data(name)
        if a: power += RARITY_POWER.get(a["rarity"], 10)
    return power

_pvp_requests = {}  # in-memory complement to DB

@with_data_lock
async def cmd_pvp(update: Update, context: ContextTypes.DEFAULT_TYPE):
    challenger = update.message.from_user
    chat_id    = update.message.chat_id
    if context.args and context.args[0].lower() == "howto":
        await update.message.reply_text(_game_howto("pvp"), parse_mode="Markdown"); return
    if not update.message.reply_to_message:
        await update.message.reply_text("↩️ Reply to someone + `/pvp <bet>`", parse_mode="Markdown"); return
    opponent = update.message.reply_to_message.from_user
    if opponent.id == challenger.id: await update.message.reply_text("❌ Can't battle yourself!"); return
    if opponent.is_bot: await update.message.reply_text("❌ Can't battle a bot!"); return
    bet = 0
    if context.args:
        try: bet = max(0, int(context.args[0]))
        except Exception: pass

    data = load_data()
    cu = get_user(data, challenger.id, challenger.username, challenger.full_name)
    if bet > 0 and cu.get("coins",0) < bet:
        await update.message.reply_text("❌ Not enough coins for bet!"); return
    c_team = cu.get("battle_team", [])
    if not c_team:
        await update.message.reply_text("❌ Set your battle team first! `/setteam`", parse_mode="Markdown"); return

    cname = f"@{challenger.username}" if challenger.username else _safe_md(challenger.full_name)
    oname = f"@{opponent.username}" if opponent.username else _safe_md(opponent.full_name)
    bet_line = f"\n💰 Bet: *{bet} coins each*" if bet > 0 else ""
    pvp_id = f"pvp_{challenger.id}_{opponent.id}_{int(datetime.now().timestamp())}"

    data.setdefault("pvp_requests", {})[pvp_id] = {
        "challenger_id": challenger.id, "opponent_id": opponent.id,
        "bet": bet, "status": "pending", "chat_id": chat_id,
    }
    save_data(data)

    kb = [[InlineKeyboardButton("⚔️ Accept", callback_data=f"pvpacpt_{pvp_id}"),
           InlineKeyboardButton("❌ Decline", callback_data=f"pvpdecl_{pvp_id}")]]
    await update.message.reply_text(
        f"⚔️ *{fancy('PVP CHALLENGE!')}*\n{cname} challenges {oname}!{bet_line}\n\n"
        f"🐾 Team: {' | '.join(c_team)}\n\n{oname}, accept?",
        reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")

@with_data_lock
async def handle_pvp(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query  = update.callback_query
    try:
        await query.answer()
    except (BadRequest, TelegramError):
        pass  # stale/expired callback query — safe to ignore, continue handling
    parts  = query.data.split("_", 1); action = parts[0]; pvp_id = parts[1]
    data   = load_data()
    pvps   = data.get("pvp_requests", {})
    if pvp_id not in pvps:
        await _safe_edit_message_text(query, "❌ Battle expired."); return
    pvp = pvps[pvp_id]
    if pvp["status"] != "pending":
        await _safe_edit_message_text(query, "❌ Already resolved."); return
    if query.from_user.id != pvp["opponent_id"]:
        await query.answer("❌ Only the challenged player can respond!", show_alert=True); return
    if action == "pvpdecl":
        pvp["status"] = "declined"; save_data(data)
        await _safe_edit_message_text(query, "❌ Battle declined."); return

    pvp["status"] = "done"
    cu = get_user(data, pvp["challenger_id"])
    ou = get_user(data, pvp["opponent_id"], query.from_user.username, query.from_user.full_name)
    c_team = cu.get("battle_team", [])
    o_team = ou.get("battle_team", [])
    if not o_team:
        await _safe_edit_message_text(query, "❌ You have no battle team! Use `/setteam`.", parse_mode="Markdown"); return
    bet = pvp.get("bet", 0)
    if bet > 0 and (cu.get("coins",0) < bet or ou.get("coins",0) < bet):
        await _safe_edit_message_text(query, "❌ Someone doesn't have enough coins for the bet!"); return

    c_power = get_team_power(c_team, cu)
    o_power = get_team_power(o_team, ou)
    cname   = f"@{cu.get('username','?')}" if cu.get("username","?") != "Unknown" else _safe_md(cu.get("full_name", "?"))
    oname   = f"@{ou.get('username','?')}" if ou.get("username","?") != "Unknown" else _safe_md(ou.get("full_name", "?"))

    # ── INTRO ANIMATION ──────────────────────────────────────────────────────
    await _safe_edit_message_text(query, 
        f"⚔️ ✦ *{fancy('PVP BATTLE ACCEPTED!')}* ✦\n┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄\n"
        f"🔴 *{cname}*\n   Team: {' │ '.join(c_team[:3])}\n"
        f"   Power: *{int(c_power)}* ⚡\n\n"
        f"🔵 *{oname}*\n   Team: {' │ '.join(o_team[:3])}\n"
        f"   Power: *{int(o_power)}* ⚡\n\n"
        f"_Preparing battle..._",
        parse_mode="Markdown")
    await asyncio.sleep(1.5)

    await _safe_edit_message_text(query, 
        f"⚔️ ✦ *{fancy('ROUND 1 STARTING!')}* ✦\n┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄\n"
        f"🔴 {cname} vs 🔵 {oname}\n\n"
        f"```\n  3...\n```",
        parse_mode="Markdown")
    await asyncio.sleep(0.7)
    await _safe_edit_message_text(query, 
        f"⚔️ ✦ *{fancy('ROUND 1 STARTING!')}* ✦\n┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄\n"
        f"🔴 {cname} vs 🔵 {oname}\n\n"
        f"```\n  3... 2...\n```",
        parse_mode="Markdown")
    await asyncio.sleep(0.7)
    await _safe_edit_message_text(query, 
        f"⚔️ *{fancy('FIGHT!')}* 💥\n┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄\n"
        f"🔴 {cname} vs 🔵 {oname}",
        parse_mode="Markdown")
    await asyncio.sleep(0.5)

    # ── ROUND-BY-ROUND BATTLE ────────────────────────────────────────────────
    c_roll_total = 0; o_roll_total = 0
    c_hp = 100; o_hp = 100

    battle_log = []
    for r in range(1, 6):   # 5 rounds
        cr  = c_power * random.uniform(0.65, 1.35)
        or_ = o_power * random.uniform(0.65, 1.35)
        c_dmg = int(or_ * 0.18)
        o_dmg = int(cr  * 0.18)
        c_hp  = max(0, c_hp - c_dmg)
        o_hp  = max(0, o_hp - o_dmg)
        c_roll_total += cr; o_roll_total += or_

        r_winner = cname if cr >= or_ else oname
        r_icon   = "🔴" if cr >= or_ else "🔵"
        c_bar = "█" * (c_hp // 10) + "░" * (10 - c_hp // 10)
        o_bar = "█" * (o_hp // 10) + "░" * (10 - o_hp // 10)

        log_text = "\n".join(f"  R{i}: {line}" for i, line in enumerate(battle_log[-3:], start=max(1,r-2)))
        try:
            await query.edit_message_text(
                f"⚔️ ✦ *ROUND {r}/5* ✦\n┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄\n"
                f"🔴 {cname[:12]}\n  [{c_bar}] {c_hp}HP\n\n"
                f"🔵 {oname[:12]}\n  [{o_bar}] {o_hp}HP\n\n"
                f"💥 {r_icon} *{r_winner}* wins R{r}!",
                parse_mode="Markdown")
        except Exception: pass
        battle_log.append(f"{r_winner} wins")
        await asyncio.sleep(0.9)

        if c_hp <= 0 or o_hp <= 0:
            break

    # ── DETERMINE WINNER ─────────────────────────────────────────────────────
    if c_hp != o_hp:
        is_c_winner = c_hp > o_hp
    else:
        is_c_winner = c_roll_total >= o_roll_total

    winner = cname if is_c_winner else oname
    loser  = oname if is_c_winner else cname
    wu     = cu if is_c_winner else ou
    lu     = ou if is_c_winner else cu

    wu["wins"]     = wu.get("wins", 0) + 1
    wu["pvp_wins"] = wu.get("pvp_wins", 0) + 1
    b = award_badge(wu, "pvp_win")
    bet_result = ""
    if bet > 0:
        wu["coins"] = wu.get("coins", 0) + bet
        lu["coins"] = max(0, lu.get("coins", 0) - bet)
        wu["total_coins_ever"] = wu.get("total_coins_ever", 0) + bet
        bet_result = f"\n💰 *{winner}* wins *{bet:,}* 🪙!"
    save_data(data)

    await _safe_edit_message_text(query, 
        f"🏆 ✦ *{fancy('PVP RESULT')}* ✦\n┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄\n\n"
        f"👑 *{winner} WINS!*\n\n"
        f"🔴 {cname}: *{int(c_roll_total)}* total power\n"
        f"🔵 {oname}: *{int(o_roll_total)}* total power\n"
        f"{bet_result}" + (f"\n\n{b}" if b else ""),
        parse_mode="Markdown")
  
@with_data_lock
async def cmd_setteam(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user; data = load_data()
    u    = get_user(data, user.id, user.username, user.full_name); zoo = u.get("animals", [])
    save_data(data)
    if not context.args:
        current = u.get("battle_team", [])
        if current:
            team_str = "\n".join(f"  {i+1}. {n}" for i, n in enumerate(current))
            ws = get_weapon_effective_stats(u)
            power = get_team_power(current, u)
            await update.message.reply_text(
                f"⚔️ *Your Battle Team:*\n{team_str}\n\n🏹 Weapon: {ws['name']}\n💪 Power: *{power}*",
                parse_mode="Markdown")
        else:
            await update.message.reply_text(
                "No team set! Use:\n`/setteam Dragon, Lion, Tiger`\nor\n`/setteam Dragon | Lion | Tiger`",
                parse_mode="Markdown")
        return

    # Support both | and , separators
    raw   = " ".join(context.args)
    sep   = "|" if "|" in raw else ","
    picks = [p.strip() for p in raw.split(sep)]
    if len(picks) != 3:
        await update.message.reply_text("❌ Pick exactly 3 animals: `/setteam Dragon, Lion, Tiger`", parse_mode="Markdown"); return

    chosen = []; errors = []
    for pick in picks:
        matched = next((z["name"] for z in zoo if pick.lower() in z["name"].lower()), None)
        if matched: chosen.append(matched)
        else:       errors.append(pick)
    if errors:
        await update.message.reply_text(f"❌ Not in zoo: *{', '.join(errors)}*", parse_mode="Markdown"); return

    u["battle_team"] = chosen
    power = get_team_power(chosen, u)
    ws    = get_weapon_effective_stats(u)
    save_data(data)
    lines = ["⚔️ ✦ *Battle Team Set!* ✦\n┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄"]
    for i, n in enumerate(chosen):
        a    = find_animal_data(n)
        icon = RARITY_COLORS.get(a["rarity"], "⬜") if a else "⬜"
        lines.append(f"  {i+1}. {n} {icon}")
    lines.append(f"\n🏹 Weapon: {ws['name']}\n💪 Total Power: *{power}*")
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")
# ══════════════════════════════════════════════════════════════════════════════
#  PART 3 — everything Part 1 did not yet define:
#  economy/profile cmds, shop, trade/auction/pray, leaderboard, moderation
#  (old 9 + 15 new), 7 new mini-games, Traitor / Truth&Dare,
#  welcomer, the message handler that ties AFK+GN+games+challenges+chat
#  together, and main().
#
#  This file is meant to be concatenated AFTER Part 1 (Part 2 you were given
#  is byte-for-byte the same functions as the tail of Part 1 — nothing new —
#  so just use Part 1 once, then this file). See the bottom of this message
#  for the exact merge command.
# ══════════════════════════════════════════════════════════════════════════════

import json as _json  # local alias, avoids clashing with anything in Part 1

# ══════════════════════════════════════════════════════════════════════════════
#  PROFILE / ECONOMY CORE COMMANDS
# ══════════════════════════════════════════════════════════════════════════════
@with_data_lock
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    track_chat(update.message.chat_id, update.message.chat.type != "private")
    user = update.message.from_user

    # ── Referral payload: /start ref_<referrer_id> ───────────────────────────
    # Only pays out for a genuinely NEW user (never seen in the DB before) so
    # it can't be farmed by re-running /start. Both sides get coins once.
    referral_line = ""
    data = load_data()
    is_new_user = str(user.id) not in data["users"]
    u = get_user(data, user.id, user.username, user.full_name)
    if is_new_user and context.args:
        m = re.match(r'^ref_(\d+)$', context.args[0])
        if m:
            referrer_id = int(m.group(1))
            if referrer_id != user.id and str(referrer_id) in data["users"]:
                ref_u = get_user(data, referrer_id)
                u["referred_by"] = referrer_id
                u["coins"] += REFERRAL_BONUS_NEW_USER
                u["total_coins_ever"] = u.get("total_coins_ever", 0) + REFERRAL_BONUS_NEW_USER
                ref_u["coins"] += REFERRAL_BONUS_REFERRER
                ref_u["total_coins_ever"] = ref_u.get("total_coins_ever", 0) + REFERRAL_BONUS_REFERRER
                ref_u["referral_count"] = ref_u.get("referral_count", 0) + 1
                ref_u["referral_coins_earned"] = ref_u.get("referral_coins_earned", 0) + REFERRAL_BONUS_REFERRER
                referral_line = f"\n🎉 Joined via referral! +{REFERRAL_BONUS_NEW_USER} 🪙 bonus!"
                check_badges(ref_u)  # may award recruiter/ambassador/growth_legend right here
                # ── Milestone bonus: extra lump-sum coins the moment a referrer's
                # friend-count first reaches/passes a REFERRAL_MILESTONES key.
                # Claimed list guards against double-paying the same milestone
                # (e.g. if referral_count ever gets recomputed/replayed).
                claimed = ref_u.setdefault("referral_milestones_claimed", [])
                milestone_note = ""
                for threshold, bonus in sorted(REFERRAL_MILESTONES.items()):
                    if ref_u["referral_count"] >= threshold and threshold not in claimed:
                        claimed.append(threshold)
                        ref_u["coins"] += bonus
                        ref_u["total_coins_ever"] = ref_u.get("total_coins_ever", 0) + bonus
                        ref_u["referral_coins_earned"] = ref_u.get("referral_coins_earned", 0) + bonus
                        milestone_note = f"\n🏆 Milestone hit — {threshold} friends invited! +{bonus} 🪙 bonus!"
                try:
                    await context.bot.send_message(
                        referrer_id,
                        f"🤝 Someone joined Aira using your invite link! +{REFERRAL_BONUS_REFERRER} 🪙{milestone_note}",
                    )
                except Exception:
                    pass  # referrer may have blocked the bot — bonus still applies to them either way

    save_data(data)  # persist the (possibly brand-new) user record + any referral payout right away

    kb = [
        [InlineKeyboardButton("📖 Full Help Menu", callback_data="help_main")],
        [InlineKeyboardButton("🎮 Games", callback_data="help_games"),
         InlineKeyboardButton("💰 Economy", callback_data="help_economy")],
        [InlineKeyboardButton("🐾 Hunt Now", callback_data="hunt_again"),
         InlineKeyboardButton("💼 My Wallet", callback_data="prof_wallet")],
    ]
    # In a DM (not a group), the person can't add Aira to a group from here
    # via any group-only command, so surface Telegram's own "add to group"
    # deep link (?startgroup=) as a one-tap button — this is the single
    # highest-leverage new-group growth path: a happy solo user becomes the
    # one who brings Aira into their friend group's chat.
    if update.message.chat.type == "private":
        try:
            bot_username = (await context.bot.get_me()).username
            kb.append([InlineKeyboardButton(
                "➕ Add Aira to Your Group",
                url=f"https://t.me/{bot_username}?startgroup=true")])
        except Exception:
            pass
    if update.message.chat.type in ("group", "supergroup"):
        try:
            _bm = _get_db()["meta"].find_one({"_id":"broadcast"}) or {"_id":"broadcast","groups":[]}
            if update.message.chat_id not in _bm["groups"]:
                _bm["groups"].append(update.message.chat_id)
                _get_db()["meta"].replace_one({"_id":"broadcast"}, _bm, upsert=True)
        except Exception:
            pass
    await update.message.reply_text(
        card(
            f"Hey, I'm {fancy('AIRA')}",
            "Your all-in-one Telegram companion.",
            f"{DOT} Challenges · 🐾 Hunt · 🎰 Casino",
            f"{DOT} AFK · Moderation · Chat",
            f"{DOT} Daily rewards · Trade · PVP",
            f"{referral_line}",
            "\nTap a button, or use */help* for the full list. Use */invite* to earn coins from friends!",
        ),

        reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")

# ---- /help button UI --------------------------------------------------------
# NOTE: owner-only / secret commands (announcetoall, makeredeemcodeforall,
# checkuserbase, aistatus, transferhardall) are intentionally NEVER listed here.
HELP_SECTIONS = {
    "help_games": (
        f"🎮 *GAMES*\n{DIV}\n"
        "/challenge – manual challenge (also auto-fires every 5-7 min)\n"
        "/hint /skipit – challenge helpers\n"
        "_Every game below also has `<command> howto` for full rules._\n"
        "/ttt @user – Tic-Tac-Toe (in DM: no reply needed, you play Aira!)\n"
        "/hangman – Hangman (group guesses)\n"
        "/guessnumber – Guess the Number\n"
        "/wordchain – Word Chain lobby (in DM: solo vs Aira!)\n"
        "/rps @user – Rock Paper Scissors\n"
        "/blackjack <bet> – Blackjack vs dealer\n"
        "/quizbattle – multiplayer timed quiz\n"
        "/fastmath – fast mental-math race, first correct answer wins coins\n"
        "/truth /dare – instant Truth or Dare\n"
        "/tnd – multiplayer Truth or Dare lobby\n"
        "/traitor – Who's the Traitor lobby\n"
        "/wolf – Werewolf social deduction\n"
        "/lastcall – Last Call murder-mystery game\n"
        "/echoes – Echoes bond-guessing game\n"
        "/blackout – Blackout Ward infection game\n"
        "/pvp – reply + bet to battle someone's zoo team\n"
        "/battle – solo fight vs a random wild enemy\n"
        "/amongus – Among Us social deception game (4-12 players, join lobby first)"
    ),
    "help_casino": (
        "🎰 ✦ *CASINO* ✦\n┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄\n"
        "/cf <amount> heads|tails – coin flip gamble\n"
        "/s <amount> – slot machine\n"
        "/dice <amount> <1-6> – guess the roll, 3× payout\n"
        "/lottery join – enter the weekly lottery\n"
        "/lottery – view lottery status/help\n"
        "_Weekly draw: every Sunday, 3PM IST_\n"
        "_Win 200+ 🪙 in one bet and a 📤 Flex This Win button appears — one tap to invite friends!_"
    ),
    "help_economy": (
        "💰 ✦ *ECONOMY* ✦\n┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄\n"
        "/wallet /stats – balance & stats\n"
        "/daily – daily reward (streak-based)\n"
        "/give – reply + `/give <amount>`\n"
        "/leaderboard – 7 categories\n"
        "/streak – win streak & bonus\n"
        "/shop /gemshop – buy perks & weapons\n"
        "/crate <id> – open a crate from your inventory (no id shows your crates)\n"
        "/settitle /pinit – member tag / pin token\n"
        "/trade /tradeitem /auction – player trading\n"
        "/badges – your badge collection\n"
        "/invite – referral link + one-tap share button, earn coins per friend "
        "who joins, plus escalating bonus payouts at 5/10/25/50/100 friends\n"
        "/viral – referral Hall of Fame + your personal progress + share button\n"

        "_Got a code? Just type it in any chat and Aira redeems it automatically!_"
    ),
    "help_owo": (
        "🐾 ✦ *OWO HUNTING* ✦\n┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄\n"
        "/hunt – catch an animal\n"
        "/zoo – your collection\n"
        "/evolve <name> – evolve 3 dupes into a stronger form\n"
        "/sell all | /sell all <rarity> | /sell <name>\n"
        "/gemshop – buy weapons with gems\n"
        "/upgradeweapon – upgrade your equipped weapon (5 levels)\n"
        "/owoprofile – hunting stats\n"
        "/autohunt – toggle passive hunting\n"
        "/battle – fight a wild animal solo\n"
        "/setteam <a, b, c> – set your PVP team (comma OR `|`)\n"
        "/pvp – challenge someone's team\n"
        "/topanimals – zoo leaderboard\n"
        "/inventory /equipweapon – manage gear\n"
        "/pray – 10 min gambling luck boost (also boosts casino odds)\n"
        "/adopt – adopt a companion pet (manual /hunt only, ~1-in-1000, rarer than ♠️ Spade!)\n"
        "/mypet – check on / feed / pat your companion\n"
        "/releasepet – release your companion (partial refund)\n"
        "_Rare+ catches get a 📤 Flex This Catch button — one tap to invite friends!_"
    ),
    "help_mod": (
        "🛡️ ✦ *MODERATION* ✦\n┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄\n"
        "/ban /unban /kick /timeout /untimeout\n"
        "/tempban <mins> – auto-expiring ban\n"
        "/purge <n> – bulk delete\n"
        "/warn /warns /clearwarns – 3-strike system\n"
        "/lock /unlock – restrict/allow group messaging\n"
        "/slowmode <secs> – Telegram slow mode\n"
        "/promote /demote – admin rights\n"
        "/adminlist – list current admins\n"
        "/userinfo – reply to see full user info\n"
        "/report – reply + `/report <reason>` to alert admins\n"
        "/rules /setrules – view/set group rules\n"
        "/antispam on|off – repeated-message auto-mute\n"
        "/unpin – unpin the pinned message\n"
        "/cleanbot – delete Aira's recent messages\n"
        "/announce <msg> – admin broadcast\n"
        "/setwelcome /setbye – custom join/leave messages\n"
        "/togglechallenge on|off – auto-challenge toggle\n"
        "/forgewar – 2× rewards for 1h\n"
        "/approve – reply + /approve to make user immune to mod actions\n"
        "/unapprove – reply + /unapprove to remove immunity\n"
        "/approvedlist – see all approved (immune) users"
    ),
  "help_social": (
        "🤝 ✦ *SOCIAL & UTILITY* ✦\n┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄\n"
        "/ask <question> – chat with Aira directly\n"
        "/pomodoro <mins> – focus timer\n"
        "/latency – check Aira's response ping\n"
        "/reportbug <description> – DM the owner about a bug\n"
        "/chatid – get this chat's exact numeric ID\n"
        "!status <reason> – set AFK (also: say 'gn'/'good night' for sleep-AFK)\n"
        "DM /start → ➕ *Add Aira to Your Group* button – one tap to bring Aira into a group chat\n"
        "💬 Mention or reply to Aira any time to chat!"
    ),
    "help_fun": (
        f"✨ *FUN EXTRAS*\n{DIV}\n"
        "/8ball <question> – magic 8-ball\n"
        "/wyr – Would You Rather poll\n"
        "/riddle – riddle with reveal button\n"
        "/joke – random joke\n"
        "/fact – random fun fact\n"
        "/ship @user1 @user2 – compatibility %\n"
        "/roast – reply to someone (playful, PG)\n"
        "/compliment – reply to someone (wholesome)\n"
        "/remindme <10m/2h/1d> <text> – personal reminder\n"
        "/mood – see Aira's current mood"
    ),
    "help_mystery": (
        "🔮 *ORACLE CHRONICLES — LIVING MURDER MYSTERY*\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "A new murder mystery every Monday. Aira generates the case, voices\n"
        "every suspect, and runs clue drops all week. Your group investigates.\n\n"
        "/mystery – case overview + crime scene photo\n"
        "/mystery howto – full rulebook (read this first!)\n"
        "/suspects – all suspects with live stress bars\n"
        "/goto <location> – travel to one of 12 locations\n"
        "/examine <item> – examine an object for clues\n"
        "/interrogate <name> <question> – Aira voices the suspect in-character\n"
        "/stakeout <location> – watch for suspect movement in next time window\n"
        "/evidence – your group's full clue board\n"
        "/timeline add HH:MM <event> – build the murder timeline\n"
        "/timeline view – see the current timeline\n"
        "/casefile – download your full case file as a document\n"
        "/decode <text> – submit today's cipher answer (+25 pts if correct)\n"
        "/nexus view – all groups' shared intel\n"
        "/nexus post <clue> – share a clue publicly (costs 30 coins)\n"
        "/nexus confirm <id> – verify another group's clue (3 = globally confirmed)\n"
        "/accuse <name> <weapon> <location> <motive> – make your formal accusation\n"
        "/mysteryboard – weekly leaderboard (who solved it first)\n"
        "/mystatus – your group's investigation snapshot\n"
        "/oraclehint – spend 30 pts for a cryptic nudge from Aira"
    ),
}

_HELP_MAIN_KB = [
    [InlineKeyboardButton("🎮 Games", callback_data="help_games"),
     InlineKeyboardButton("🎰 Casino", callback_data="help_casino")],
    [InlineKeyboardButton("💰 Economy", callback_data="help_economy"),
     InlineKeyboardButton("🐾 OWO Hunting", callback_data="help_owo")],
    [InlineKeyboardButton("🛡️ Moderation", callback_data="help_mod"),
     InlineKeyboardButton("🤝 Social & Utility", callback_data="help_social")],
    [InlineKeyboardButton("✨ Fun Extras", callback_data="help_fun")],
    [InlineKeyboardButton("📤 Invite Friends", callback_data="help_invite_shortcut"),
     InlineKeyboardButton("🔮 Mystery", callback_data="help_mystery")],
]

async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        card("Aira — Command Center", "Pick a category:") +
        "\n\n💜 _Want the full command list? Try /manual for Aira's Notebook — searchable, tabbed, and handwritten just for you._"
        "\n🪙 _Earning coins? /invite friends for bonus coins on both sides, escalating the more you bring in._",
        reply_markup=InlineKeyboardMarkup(_HELP_MAIN_KB), parse_mode="Markdown")

# ══════════════════════════════════════════════════════════════════════════════
#  THE MANUAL — an illuminated, cursive-script HTML "grimoire" listing every
#  public command with its use. Built straight from HELP_SECTIONS (the same
#  source /help's buttons read from) so it can never drift out of sync, and
#  it therefore automatically excludes every owner/secret command — none of
#  those live in HELP_SECTIONS in the first place (see the note above that
#  dict). Reachable via the /manual command (sent as a downloadable page) and
#  via the Flask keep-alive server at GET /manual for anyone who wants a link
#  instead of a file.
# ══════════════════════════════════════════════════════════════════════════════
_MANUAL_CHAPTERS = [
    ("help_mystery", "Murder Mystery",  "🔮"),
    ("help_games",   "Games",           "🎮"),
    ("help_casino",  "Casino",          "🎰"),
    ("help_economy", "Economy",         "💰"),
    ("help_owo",     "Hunting & Pets",  "🐾"),
    ("help_mod",     "Moderation",      "🛡️"),
    ("help_social",  "Social & Utility","🤝"),
    ("help_fun",     "Fun Extras",      "✨"),
]

def _manual_clean_md(text: str) -> str:
    """Strip Aira's chat Markdown emphasis so it reads cleanly as plain HTML."""
    text = text.replace("`", "")
    text = re.sub(r"\*(.+?)\*", r"\1", text)
    text = re.sub(r"_(.+?)_", r"\1", text)
    return text.strip()

def _manual_parse_section(raw: str):
    """Turn one HELP_SECTIONS entry into a list of (command_or_None, text)."""
    items = []
    for line in raw.split("\n")[1:]:                       # skip the title line
        line = line.strip()
        if not line or set(line) <= set("┄✦ "):             # blank / divider-only
            continue
        line = _manual_clean_md(line)
        if " – " in line:
            cmd, desc = line.split(" – ", 1)
            items.append((cmd.strip(), desc.strip()))
        else:
            items.append((None, line))
    return items

def build_manual_html() -> str:
    """Aira's Notebook — v3 design. Same DNA as before (handwritten cursive
    fonts, purple ink, ruled paper) but a genuinely different composition:
    a wax-seal monogram + ribbon bookmark instead of spiral-binding, and
    right-edge vertical tabs (like a tabbed dictionary/notebook) instead of
    a top pill row for category navigation. Search + filtering logic is
    unchanged, just reskinned again."""
    tab_html, chapter_blocks = [], []
    tab_html.append('<button class="sidetab active" data-cat="all" type="button">✨ All</button>')
    for i, (key, title, emoji) in enumerate(_MANUAL_CHAPTERS):
        tab_html.append(
            f'<button class="sidetab" data-cat="{key}" type="button">{emoji} {html_lib.escape(title)}</button>')

        items = _manual_parse_section(HELP_SECTIONS.get(key, ""))
        card_rows = []
        for cmd, desc in items:
            if cmd:
                search_blob = html_lib.escape(f"{cmd} {desc}".lower())
                card_rows.append(f'''
        <div class="entry" data-search="{search_blob}">
          <span class="mark">✦</span>
          <span class="cmd-name">{html_lib.escape(cmd)}</span>
          <span class="cmd-desc">— {html_lib.escape(desc)}</span>
        </div>''')
            else:
                search_blob = html_lib.escape(desc.lower())
                card_rows.append(f'''
        <div class="entry note-entry" data-search="{search_blob}">
          <span class="mark">☆</span>
          <span class="cmd-desc">{html_lib.escape(desc)}</span>
        </div>''')
        chapter_blocks.append(f'''
      <section class="chapter" id="{key}" data-chapter="{key}">
        <h2 class="chapter-title">{emoji} {html_lib.escape(title)}</h2>
        <div class="entry-list">{"".join(card_rows)}</div>
      </section>''')

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Aira's Notebook</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Homemade+Apple&family=Caveat:wght@500;600;700&family=Kalam:wght@400;700&display=swap" rel="stylesheet">
<script src="https://telegram.org/js/telegram-web-app.js"></script>
<style>
  :root {{
    --paper: #fbf7ee;
    --line: #ded0f2;
    --ink: #38155e;
    --ink-soft: #5a3a86;
    --ink-light: #8266ab;
    --royal: #7c3aed;
    --royal-deep: #4c1d95;
    --seal: #b23a6b;
    --gold: #c9962f;
  }}
  * {{ box-sizing: border-box; -webkit-tap-highlight-color: transparent; }}
  html, body {{
    margin: 0; padding: 0;
    background:
      radial-gradient(circle at 15% 10%, #7c3aed33, transparent 45%),
      radial-gradient(circle at 85% 90%, #4c1d9555, transparent 50%),
      linear-gradient(160deg, #1c0b36, #341564 45%, #5b21b6 100%);
    background-attachment: fixed;
    color: var(--ink);
    font-family: 'Kalam', cursive;
    min-height: 100vh;
  }}
  .top {{
    text-align: center;
    padding: 26px 16px 8px;
  }}
  .top .seal {{
    width: 58px; height: 58px;
    margin: 0 auto 6px;
    border-radius: 50%;
    background: radial-gradient(circle at 35% 30%, #d1569a, var(--seal) 70%);
    display: flex; align-items: center; justify-content: center;
    font-family: 'Homemade Apple', cursive;
    font-size: 30px;
    color: #fdeaf3;
    box-shadow: 0 6px 16px rgba(178, 58, 107, 0.55), inset 0 -3px 6px rgba(0,0,0,0.25);
  }}
  .top .brand {{
    font-family: 'Homemade Apple', cursive;
    font-size: 34px;
    color: #f2e6ff;
    text-shadow: 0 2px 8px rgba(0,0,0,0.4);
  }}
  .stage {{
    max-width: 860px;
    margin: 6px auto 60px;
    padding: 0 26px;
    position: relative;
  }}
  .book {{
    position: relative;
    background: var(--paper);
    background-image: repeating-linear-gradient(var(--paper) 0px, var(--paper) 32px, var(--line) 33px);
    background-position: 0 78px;
    border-radius: 4px;
    padding: 40px 40px 56px;
    box-shadow: 0 30px 70px rgba(15, 3, 40, 0.55), 0 0 0 1px rgba(124, 58, 237, 0.25);
  }}
  .ribbon {{
    position: absolute;
    top: -6px; right: 46px;
    width: 26px; height: 78px;
    background: linear-gradient(180deg, var(--royal), var(--royal-deep));
    clip-path: polygon(0 0, 100% 0, 100% 100%, 50% 78%, 0 100%);
    box-shadow: 0 4px 10px rgba(0,0,0,0.35);
  }}
  .book-title {{
    font-family: 'Homemade Apple', cursive;
    font-size: 42px;
    color: var(--royal-deep);
    margin: 0 0 2px;
    text-align: center;
  }}
  .book-sub {{
    text-align: center;
    font-size: 17px;
    font-style: italic;
    color: var(--ink-light);
    margin: 0 0 22px;
  }}
  .search-row {{ position: relative; margin-bottom: 8px; }}
  .search-row::before {{
    content: "🔍";
    position: absolute; left: 4px; top: 6px;
    font-size: 14px; opacity: 0.6;
  }}
  .search-row input {{
    width: 100%;
    font-family: 'Kalam', cursive;
    font-size: 17px;
    color: var(--ink);
    background: transparent;
    border: none;
    border-bottom: 2px dashed var(--ink-light);
    padding: 6px 4px 8px 28px;
    outline: none;
  }}
  .search-row input::placeholder {{ color: var(--ink-light); opacity: 0.65; }}
  .mobile-tabs {{
    display: none;
    flex-wrap: wrap;
    gap: 6px 10px;
    margin: 14px 0 4px;
  }}
  .chapter {{ margin: 28px 0; }}
  .chapter-title {{
    font-family: 'Caveat', cursive;
    font-weight: 700;
    font-size: 29px;
    color: var(--royal-deep);
    margin: 0 0 6px;
    display: inline-block;
    border-bottom: 2px solid var(--gold);
    padding-bottom: 2px;
  }}
  .entry {{ padding: 5px 0; line-height: 1.55; font-size: 18px; }}
  .entry .mark {{ color: var(--gold); margin-right: 8px; }}
  .entry .cmd-name {{
    font-weight: 700;
    color: var(--royal);
    background: linear-gradient(to bottom, transparent 68%, #ecd9ff 68%);
    padding: 0 2px;
  }}
  .entry .cmd-desc {{ color: var(--ink-soft); }}
  .entry.note-entry {{ font-style: italic; color: var(--ink-light); }}
  .entry.hidden {{ display: none; }}
  .chapter.hidden {{ display: none; }}
  .empty-state {{
    display: none; text-align: center; padding: 26px 0;
    font-family: 'Caveat', cursive; font-size: 22px; color: var(--ink-light);
  }}
  .empty-state.show {{ display: block; }}
  .lore {{
    margin-top: 14px; padding: 15px 18px;
    border: 2px dashed var(--seal); border-radius: 10px;
    background: rgba(178, 58, 107, 0.06);
    font-size: 16.5px; color: var(--ink-soft);
    transform: rotate(-0.3deg);
  }}
  .lore strong {{ color: var(--royal-deep); }}
  .sign-off {{ text-align: right; margin-top: 30px; }}
  .sign-off .sig {{ font-family: 'Homemade Apple', cursive; font-size: 32px; color: var(--royal-deep); }}
  .sign-off .ps {{ font-size: 13px; color: var(--ink-light); font-style: italic; }}

  /* right-edge tabs, like a tabbed dictionary/notebook */
  .tabrail {{
    position: absolute;
    top: 90px; right: -1px;
    display: flex;
    flex-direction: column;
    gap: 10px;
    z-index: 3;
  }}
  .sidetab {{
    font-family: 'Caveat', cursive;
    font-weight: 700;
    font-size: 15px;
    color: #fbf3ff;
    background: linear-gradient(120deg, var(--royal), var(--royal-deep));
    border: none;
    border-radius: 0 8px 8px 0;
    padding: 7px 12px 7px 10px;
    cursor: pointer;
    writing-mode: vertical-rl;
    text-orientation: mixed;
    box-shadow: 2px 3px 8px rgba(0,0,0,0.3);
    opacity: 0.82;
    transition: opacity 0.15s ease, transform 0.15s ease;
  }}
  .sidetab:hover {{ opacity: 1; }}
  .sidetab.active {{
    opacity: 1;
    transform: translateX(4px);
    background: linear-gradient(120deg, var(--seal), #8a2a52);
  }}
  @media (max-width: 720px) {{
    .tabrail {{ display: none; }}
    .mobile-tabs {{ display: flex; }}
    .mobile-tabs .sidetab {{
      writing-mode: horizontal-tb;
      border-radius: 14px;
      padding: 6px 12px;
      box-shadow: none;
    }}
    .stage {{ padding: 0 14px; }}
    .book {{ padding: 30px 20px 44px; }}
    .book-title {{ font-size: 34px; }}
  }}
</style>
</head>
<body>
  <div class="top">
    <div class="seal">A</div>
    <div class="brand">Aira's Notebook</div>
  </div>

  <div class="stage">
    <div class="book">
      <div class="ribbon"></div>
      <div class="tabrail" id="tabRail">
        {"".join(tab_html)}
      </div>

      <div class="book-title">Everything, In My Own Hand</div>
      <p class="book-sub">search below, or flip a tab on the right ↓</p>

      <div class="search-row">
        <input id="cmdSearch" type="text" placeholder="search a command..." autocomplete="off">
      </div>

      <div class="mobile-tabs" id="mobileTabs"></div>

      {"".join(chapter_blocks)}

      <p class="empty-state" id="emptyState">...nothing here. try another word? 🔮</p>

      <div class="lore">
        💗 a note on companions — adoptable pets only turn up through manual
        <strong>/hunt</strong>, and they're deliberately rarer than the mighty ♠️ Spade
        itself, about <strong>one in a thousand</strong> successful hunts. you can keep
        only one companion at a time; <strong>/releasepet</strong> them first if you
        ever want to adopt another.
      </div>

      <div class="sign-off">
        <div class="sig">~ Aira</div>
        <div class="ps">p.s. a few pages of this book aren't for every eye 🤫</div>
      </div>
    </div>
  </div>

<script>
(function() {{
  try {{
    if (window.Telegram && window.Telegram.WebApp) {{
      var tg = window.Telegram.WebApp;
      tg.ready();
      tg.expand();
      tg.setHeaderColor('#341564');
      tg.setBackgroundColor('#1c0b36');
    }}
  }} catch (e) {{ /* not inside Telegram — ignore */ }}

  // mirror the desktop side-tabs into the mobile pill row so both work
  var rail = document.getElementById('tabRail');
  var mobileTabs = document.getElementById('mobileTabs');
  mobileTabs.innerHTML = rail.innerHTML;

  var search = document.getElementById('cmdSearch');
  var allTabButtons = document.querySelectorAll('.sidetab');
  var chapters = document.querySelectorAll('.chapter');
  var emptyState = document.getElementById('emptyState');
  var activeCat = 'all';
  var firstTabKey = 'all';

  function applyFilters() {{
    var q = search.value.trim().toLowerCase();
    var anyVisible = false;

    chapters.forEach(function(chapter) {{
      var cat = chapter.getAttribute('data-chapter');
      var catMatch = (activeCat === 'all' || activeCat === cat);
      var entries = chapter.querySelectorAll('.entry');
      var chapterHasVisible = false;

      entries.forEach(function(entry) {{
        var blob = entry.getAttribute('data-search') || '';
        var textMatch = !q || blob.indexOf(q) !== -1;
        var visible = catMatch && textMatch;
        entry.classList.toggle('hidden', !visible);
        if (visible) chapterHasVisible = true;
      }});

      chapter.classList.toggle('hidden', !chapterHasVisible);
      if (chapterHasVisible) anyVisible = true;
    }});

    emptyState.classList.toggle('show', !anyVisible);
  }}

  search.addEventListener('input', function() {{
    activeCat = 'all';
    allTabButtons.forEach(function(t) {{ t.classList.remove('active'); }});
    applyFilters();
  }});

  allTabButtons.forEach(function(tab) {{
    tab.addEventListener('click', function() {{
      allTabButtons.forEach(function(t) {{ t.classList.remove('active'); }});
      // activate every button sharing this data-cat (desktop rail + mobile mirror)
      var cat = tab.getAttribute('data-cat');
      document.querySelectorAll('.sidetab[data-cat="' + cat + '"]').forEach(function(t) {{
        t.classList.add('active');
      }});
      activeCat = cat;
      applyFilters();
    }});
  }});

  if (firstTabKey) {{
    document.querySelectorAll('.sidetab[data-cat="' + firstTabKey + '"]').forEach(function(t) {{
      t.classList.add('active');
    }});
  }}
}})();
</script>
</body>
</html>"""

async def handle_help_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    try:
        await query.answer()
    except (BadRequest, TelegramError):
        pass  # stale/expired callback query — safe to ignore, continue handling
    back_kb = [[InlineKeyboardButton("⬅️ Back", callback_data="help_main")]]
    if query.data == "help_main":
        await _safe_edit_message_text(query, "🤖 ✦ *Aira v9 – Command Center* ✦\n┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄\nPick a category:",
                                       reply_markup=InlineKeyboardMarkup(_HELP_MAIN_KB), parse_mode="Markdown")
        return
    if query.data == "help_invite_shortcut":
        user = query.from_user
        u = get_user_fast(str(user.id), user.username, user.full_name)
        try:
            bot_username = (await context.bot.get_me()).username
        except Exception:
            bot_username = "AiraBot"
        link = f"https://t.me/{bot_username}?start=ref_{user.id}"
        count = u.get("referral_count", 0)
        nxt = _next_referral_milestone(count, u.get("referral_milestones_claimed", []))
        milestone_line = ""
        if nxt:
            threshold, bonus = nxt
            milestone_line = f"\n🎯 Next milestone: *{threshold} friends* → +{bonus} 🪙"
        share_text = quote("Come play Aira with me — games, casino, hunting & more, right inside Telegram! 🎮🪙")
        share_url = f"https://t.me/share/url?url={quote(link, safe='')}&text={share_text}"
        share_kb = [
            [InlineKeyboardButton("📤 Share Invite Link", url=share_url)],
            [InlineKeyboardButton("⬅️ Back", callback_data="help_main")],
        ]
        await _safe_edit_message_text(
            query,
            card("Invite Friends",
                 f"{DOT} You get +{REFERRAL_BONUS_REFERRER} 🪙 per friend",
                 f"{DOT} They get +{REFERRAL_BONUS_NEW_USER} 🪙 just for joining",
                 f"👥 Friends invited: *{count}*{milestone_line}",
                 f"\n🔗 `{link}`"),
            reply_markup=InlineKeyboardMarkup(share_kb), parse_mode="Markdown")
        return
    text = HELP_SECTIONS.get(query.data, "Section not found.")
    await _safe_edit_message_text(query, text, reply_markup=InlineKeyboardMarkup(back_kb), parse_mode="Markdown")

async def cmd_manual(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Sends ONLY a "📔 Open Notebook" button — never a file. Tapping it opens
    Aira's Notebook (search + tabbed categories, purple/cursive handwriting) as a
    native in-Telegram WebApp, served by this bot's own Flask app at
    GET /manual. Built from HELP_SECTIONS, so owner/secret commands never
    appear in it — they were never in HELP_SECTIONS to begin with."""
    public_url = AIRA_PUBLIC_URL.strip().rstrip("/")
    if not public_url:
        await update.message.reply_text(
            "⚠️ No public URL is configured for me right now, so I can't open the "
            "Notebook as a page — ask my owner to set the `PUBLIC_URL` environment "
            "variable. Use */help* in the meantime.", parse_mode="Markdown")
        return
    await update.message.reply_text(
        "💜 *Aira's Notebook*\nEvery command, searchable and sorted by category.",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("📔 Open Notebook", web_app=WebAppInfo(url=f"{public_url}/manual"))
        ]]))

# ---- wallet / stats / badges / streak ---------------------------------------
# ══════════════════════════════════════════════════════════════════════════════
#  PROFILE HUB — /wallet /stats /badges /streak all share one Wallet ⇄ Stats ⇄
#  Badges ⇄ Streak tab bar so players can flip between their own views with a
#  tap instead of retyping commands. Text-building is split into small helpers
#  so the command entry points and the button handler render identical output.
# ══════════════════════════════════════════════════════════════════════════════
_PROFILE_TABS = [("wallet", "💼 Wallet"), ("stats", "📊 Stats"),
                  ("badges", "🏅 Badges"), ("streak", "🔥 Streak")]

def _profile_nav_kb(active: str) -> InlineKeyboardMarkup:
    row = [InlineKeyboardButton(f"• {label} •" if key == active else label, callback_data=f"prof_{key}")
           for key, label in _PROFILE_TABS]
    return InlineKeyboardMarkup([row[:2], row[2:]])   # 2×2 grid — reads cleanly on mobile

def _wallet_text(u: dict, full_name: str) -> str:
    tag_line = f"\n{BUL} Tag: *{u['title']}*" if u.get("title") else ""
    exp_line = ""
    if u.get("title_expiry"):
        rem = datetime.fromisoformat(u["title_expiry"]) - datetime.now()
        if rem.total_seconds() > 0:
            h, m = int(rem.total_seconds() // 3600), int((rem.total_seconds() % 3600) // 60)
            exp_line = f"\n{BUL} Tag expires: *{h}h {m}m*"
    afk_line = f"\n{BUL} AFK: _{u.get('afk')}_" if u.get("afk") else ""
    ws = get_weapon_effective_stats(u)
    return card(
        f"{_safe_md(full_name)} — Wallet",
        f"🪙 *{u.get('coins',0):,}*  ·  💎 *{u.get('gems',0):,}*{tag_line}{exp_line}{afk_line}",
        f"{DOT} Weapon: {ws['name']}",
        f"{DOT} Wins {u.get('wins',0)} · Weekly {u.get('weekly_wins',0)}",
        f"{DOT} Streak {u.get('streak',0)} · Best {u.get('best_streak',0)}",
        f"{DOT} {len(u.get('badges',[]))} badges",
    )

def _stats_text(u: dict, full_name: str) -> str:
    zoo_count = sum(z.get("count", 1) for z in u.get("animals", []))
    return card(
        f"{_safe_md(full_name)} — Stats",
        f"🪙 *{u.get('coins',0):,}*  ·  💎 *{u.get('gems',0):,}*  ·  Earned *{u.get('total_coins_ever',0):,}*",
        f"{DOT} Wins {u.get('wins',0)} · Weekly {u.get('weekly_wins',0)} · Best streak {u.get('best_streak',0)}",
        f"🎯 Hunts {u.get('hunts',0)} · 🦁 Animals {zoo_count}",
        f"{DOT} Casino wins {u.get('casino_wins',0)} · PVP wins {u.get('pvp_wins',0)}",
        f"{DOT} Daily streak {u.get('daily_streak',0)}d · {len(u.get('badges',[]))} badges",
    )

_BADGE_PROGRESS_STAT = {
    # badge_key: (user_field, target) — used to show "almost there" progress
    # bars for locked badges with a clear numeric threshold. Badges left out
    # of this map (random/event-triggered ones like Mythic catches or a
    # first natural blackjack) stay genuine surprises instead.
    "first_win": ("wins", 1), "streak_3": ("streak", 3), "streak_5": ("streak", 5),
    "wins_10": ("wins", 10), "wins_25": ("wins", 25), "wins_50": ("wins", 50), "wins_100": ("wins", 100),
    "rich": ("total_coins_ever", 500), "wealthy": ("total_coins_ever", 10000), "tycoon": ("total_coins_ever", 100000),
    "first_hunt": ("hunts", 1), "hunter_10": ("hunts", 10), "hunter_100": ("hunts", 100),
    "gambler": ("casino_wins", 1), "big_win": ("casino_total_won", 200),
    "daily_7": ("daily_streak", 7), "daily_30": ("daily_streak", 30),
    "pvp_win": ("pvp_wins", 1), "ttt_win": ("ttt_wins", 1), "hangman_win": ("hangman_wins", 1),
    "bj_win": ("bj_wins", 1), "quiz_top": ("quiz_wins", 1),
    "recruiter": ("referral_count", 5), "ambassador": ("referral_count", 25),
    "growth_legend": ("referral_count", 100),
}
_BADGE_TIER_ORDER = ["Mythic", "Legendary", "Epic", "Rare", "Common"]

def _badge_bar(cur, target, width=10):
    pct = max(0.0, min(1.0, cur / target)) if target else 1.0
    filled = round(pct * width)
    return "█" * filled + "░" * (width - filled)

def _badges_text(u: dict, full_name: str) -> str:
    owned = set(u.get("badges", []))
    header = card(f"{_safe_md(full_name)} — Badges", f"🏆 *{len(owned)}/{len(BADGES)}* unlocked")
    lines = [header]
    if not owned:
        lines.append("No badges yet.\n_Win challenges, hunt, gamble, or play mini-games to earn your first!_")
    else:
        by_tier = {}
        for k in owned:
            if k in BADGES:
                by_tier.setdefault(BADGES[k][2], []).append(k)
        for tier in _BADGE_TIER_ORDER:
            if tier not in by_tier:
                continue
            stars = BADGE_TIERS[tier]
            lines.append(f"\n{stars} *{tier}*")
            for k in by_tier[tier]:
                name, desc, _ = BADGES[k]
                lines.append(f"{name} — _{desc}_")

    locked = [k for k in BADGES if k not in owned]
    if locked:
        progressable = []
        for k in locked:
            stat = _BADGE_PROGRESS_STAT.get(k)
            if stat:
                field, target = stat
                cur = u.get(field, 0)
                progressable.append((min(cur, target) / target if target else 0, k, cur, target))
        progressable.sort(reverse=True)
        if progressable:
            lines.append("\n🔒 *Almost there:*")
            for _, k, cur, target in progressable[:3]:
                name, _, _ = BADGES[k]
                lines.append(f"{name} [{_badge_bar(cur, target)}] {min(cur, target)}/{target}")
        secret_ct = len([k for k in locked if k not in _BADGE_PROGRESS_STAT])
        if secret_ct:
            lines.append(f"\n❓ *{secret_ct} secret achievement{'s' if secret_ct != 1 else ''}* still undiscovered...")
    return "\n".join(lines)

def _streak_text(u: dict, full_name: str) -> str:
    streak = u.get("streak", 0)
    fire = "🔥" * min(streak, 10) if streak else "No streak yet"
    return card(
        f"{_safe_md(full_name)} — Streak",
        fire,
        f"{DOT} Current *{streak}* · Best *{u.get('best_streak',0)}*",
        f"{DOT} Bonus/win: +{streak*STREAK_BONUS} coins",
        "_Win a /challenge today to keep it alive!_",
    )

async def cmd_wallet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    u = get_user_fast(str(user.id))
    await update.message.reply_text(_wallet_text(u, user.full_name),
                                     reply_markup=_profile_nav_kb("wallet"), parse_mode="Markdown")

async def cmd_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    u = get_user_fast(str(user.id))
    await update.message.reply_text(_stats_text(u, user.full_name),
                                     reply_markup=_profile_nav_kb("stats"), parse_mode="Markdown")

async def cmd_badges(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    u = get_user_fast(str(user.id))
    await update.message.reply_text(_badges_text(u, user.full_name),
                                     reply_markup=_profile_nav_kb("badges"), parse_mode="Markdown")

async def cmd_streak(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    u = get_user_fast(str(user.id))
    await update.message.reply_text(_streak_text(u, user.full_name),
                                     reply_markup=_profile_nav_kb("streak"), parse_mode="Markdown")

# ══════════════════════════════════════════════════════════════════════════════
#  REFERRAL SYSTEM — growth loop: existing users invite friends, both sides
#  get coins. Payload format: https://t.me/<bot>?start=ref_<referrer_user_id>.
#  Payout itself happens in cmd_start() the first time the invited friend
#  ever runs /start (see REFERRAL_BONUS_* constants near the top of the file).
# ══════════════════════════════════════════════════════════════════════════════
def _next_referral_milestone(count: int, claimed: list):
    """Returns (threshold, bonus) for the nearest un-claimed milestone above
    count, or None if every defined milestone has already been claimed."""
    for threshold in sorted(REFERRAL_MILESTONES):
        if threshold not in (claimed or []) and count < threshold:
            return threshold, REFERRAL_MILESTONES[threshold]
    return None

async def cmd_invite(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    u = get_user_fast(str(user.id), user.username, user.full_name)
    try:
        bot_username = (await context.bot.get_me()).username
    except Exception:
        bot_username = "AiraBot"
    link  = f"https://t.me/{bot_username}?start=ref_{user.id}"
    count = u.get("referral_count", 0)
    earned = u.get("referral_coins_earned", 0)
    milestone_line = ""
    nxt = _next_referral_milestone(count, u.get("referral_milestones_claimed", []))
    if nxt:
        threshold, bonus = nxt
        milestone_line = f"\n🎯 Next milestone: *{threshold} friends* → +{bonus} 🪙 bonus (_{max(threshold - count, 0)} to go_)"
    # Native Telegram share sheet — one tap forwards the invite link straight
    # into any of the user's own chats, with a pre-filled caption. Converts
    # far better than "copy this link and paste it somewhere yourself".
    share_text = quote("Come play Aira with me — games, casino, hunting & more, right inside Telegram! 🎮🪙")
    share_url  = f"https://t.me/share/url?url={quote(link, safe='')}&text={share_text}"
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("📤 Share Invite Link", url=share_url)],
        [InlineKeyboardButton("➕ Add Aira to a Group", url=f"https://t.me/{bot_username}?startgroup=true")],
    ])
    await update.message.reply_text(
        card(
            "Invite Friends",
            f"{DOT} Share your link — earn coins per friend who joins!",
            f"{DOT} You get +{REFERRAL_BONUS_REFERRER} 🪙 per friend",
            f"{DOT} They get +{REFERRAL_BONUS_NEW_USER} 🪙 just for joining",
            "",
            f"👥 Friends invited: *{count}*",
            f"🪙 Earned from referrals: *{earned}*",
            f"{milestone_line}",
            "",
            f"🔗 `{link}`",
            "\n_Tap-and-hold the link above to copy it, or just tap 📤 Share below._",
        ),
        reply_markup=kb,
        parse_mode="Markdown")

async def handle_invite_nudge(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """The '📤 Invite a Friend' button surfaced after a 7-day-multiple daily
    streak. Sends a fresh copy of the /invite card (rather than editing the
    daily-reward message it was attached to) so the reward stays visible."""
    query = update.callback_query
    try:
        await query.answer()
    except (BadRequest, TelegramError):
        pass
    user = query.from_user
    u = get_user_fast(str(user.id), user.username, user.full_name)
    try:
        bot_username = (await context.bot.get_me()).username
    except Exception:
        bot_username = "AiraBot"
    link = f"https://t.me/{bot_username}?start=ref_{user.id}"
    share_text = quote("Come play Aira with me — games, casino, hunting & more, right inside Telegram! 🎮🪙")
    share_url = f"https://t.me/share/url?url={quote(link, safe='')}&text={share_text}"
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("📤 Share Invite Link", url=share_url)]])
    await query.message.reply_text(
        card("Keep the Streak Going — Together!",
             f"{DOT} Invite a friend and you both get coins",
             f"{DOT} You: +{REFERRAL_BONUS_REFERRER} 🪙  ·  Them: +{REFERRAL_BONUS_NEW_USER} 🪙",
             "",
             f"🔗 `{link}`"),
        reply_markup=kb, parse_mode="Markdown")

async def handle_profile_nav(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Tab-switch for the Wallet/Stats/Badges/Streak button row. Renders
    whoever tapped the button's own profile — same convention as /leaderboard's
    tab buttons — so the data shown always matches the person looking at it."""
    query = update.callback_query
    section = query.data.replace("prof_", "")
    builders = {"wallet": _wallet_text, "stats": _stats_text,
                "badges": _badges_text, "streak": _streak_text}
    build = builders.get(section)
    if not build:
        try:
            await query.answer()
        except (BadRequest, TelegramError):
            pass  # stale/expired callback query — safe to ignore
        return
    user = query.from_user
    u = get_user_fast(str(user.id))
    try:
        await query.answer()
    except (BadRequest, TelegramError):
        pass  # stale/expired callback query — safe to ignore, continue handling
    try:
        await query.edit_message_text(build(u, user.full_name),
                                       reply_markup=_profile_nav_kb(section), parse_mode="Markdown")
    except BadRequest:
        pass  # tapping the already-active tab re-sends identical text — Telegram rejects the no-op edit, safe to ignore

@with_data_lock
async def cmd_daily(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    data = load_data()
    u = get_user(data, user.id, user.username, user.full_name)
    now = datetime.now(); today = now.date().isoformat(); yest = (now.date() - timedelta(days=1)).isoformat()
    last = u.get("daily_claimed")
    if last == today:
        next_c = datetime.combine(now.date() + timedelta(days=1), datetime.min.time())
        rem = next_c - now
        h, m = int(rem.total_seconds() // 3600), int((rem.total_seconds() % 3600) // 60)
        await update.message.reply_text(
            card("Daily Reward", "Already claimed today.", f"{DOT} Next one in *{h}h {m}m*"),
            parse_mode="Markdown")
        return
    ds = u.get("daily_streak", 0)
    ds = ds + 1 if last == yest else 1
    u["daily_streak"] = ds
    u["daily_claimed"] = today
    tier_idx = min(ds - 1, len(DAILY_TIERS) - 1)
    reward, label = DAILY_TIERS[tier_idx]
    bonus = 0
    if ds % 7 == 0:
        bonus = 25
        label += " + 🎁 7-day bonus!"
    total = reward + bonus
    u["coins"] += total
    u["total_coins_ever"] = u.get("total_coins_ever", 0) + total
    badges = check_badges(u)
    save_data(data)
    fire = "🔥" * min(ds, 7)
    bl = "\n🆕 " + " | ".join(badges) if badges else ""
    kb_rows = [[InlineKeyboardButton("💼 View Wallet", callback_data="prof_wallet")]]
    # Light-touch growth nudge at a genuine high point (a 7-day-multiple
    # streak, already a delight moment with its own bonus above) rather than
    # spamming a share prompt on every single claim.
    if ds % 7 == 0:
        kb_rows.append([InlineKeyboardButton("📤 Invite a Friend", callback_data="invite_nudge")])
    await update.message.reply_text(
        card("Daily Reward Claimed!", f"{fire} Streak: *{ds} days*",
             f"+{total} 🪙 _{label}_{bl}", f"Balance: *{u['coins']:,}* 🪙"),
        reply_markup=InlineKeyboardMarkup(kb_rows),
        parse_mode="Markdown")

@with_data_lock
async def cmd_give(update: Update, context: ContextTypes.DEFAULT_TYPE):
    sender = update.message.from_user
    if not update.message.reply_to_message:
        await update.message.reply_text("↩️ Reply to someone + `/give <amount>`", parse_mode="Markdown"); return
    if not context.args:
        await update.message.reply_text("Usage: Reply + `/give <amount>`", parse_mode="Markdown"); return
    try: amount = int(context.args[0])
    except Exception: await update.message.reply_text("❌ Amount must be a whole number."); return
    if amount <= 0 or amount > 10000: await update.message.reply_text("❌ Amount must be between *1–10,000* 🪙.", parse_mode="Markdown"); return
    target = update.message.reply_to_message.from_user
    if target.id == sender.id: await update.message.reply_text("❌ Can't give coins to yourself!"); return
    if target.is_bot: await update.message.reply_text("❌ Can't give coins to bots!"); return
    data = load_data()
    s = get_user(data, sender.id, sender.username, sender.full_name)
    if s["coins"] < amount: await update.message.reply_text(f"❌ Need *{amount:,}* 🪙 but you only have *{s['coins']:,}* 🪙.", parse_mode="Markdown"); return
    t = get_user(data, target.id, target.username, target.full_name)
    s["coins"] -= amount; t["coins"] += amount; t["total_coins_ever"] = t.get("total_coins_ever", 0) + amount
    save_data(data)
    sname = f"@{sender.username}" if sender.username else _safe_md(sender.full_name)
    tname = f"@{target.username}" if target.username else _safe_md(target.full_name)
    await update.message.reply_text(
        card("Coins Sent", f"{sname} → {tname}: *{amount:,}* 🪙",
             f"{DOT} {sname}: *{s['coins']:,}*  ·  {tname}: *{t['coins']:,}*"),
        parse_mode="Markdown")

# ---- hunt / zoo / inventory / equip / owoprofile / autohunt / battle -------
# Shared "🎯 Hunt Again ⇄ 🦁 My Zoo" quick-action row wired to both screens so
# a player can chain hunts or peek at their collection without retyping /hunt
# or /zoo — the two commands stay reachable exactly as before either way.
def _hunt_result_kb(share_url: str = None) -> InlineKeyboardMarkup:
    rows = [[
        InlineKeyboardButton("🎯 Hunt Again", callback_data="hunt_again"),
        InlineKeyboardButton("🦁 My Zoo",     callback_data="hunt_zoo"),
    ]]
    if share_url:
        rows.append([InlineKeyboardButton("📤 Flex This Catch", url=share_url)])
    return InlineKeyboardMarkup(rows)

# Catches worth flexing about get an extra one-tap share button — a natural
# "I want to tell someone" moment that doubles as a referral touchpoint.
# Checked against do_hunt()'s returned text rather than changing do_hunt's
# return type, so every existing call site (including auto_hunt_job, which
# parses "Caught" out of the same string) keeps working untouched.
_SHAREWORTHY_HUNT_MARKERS = ("RARE", "EPIC", "LEGENDARY", "EXTREME", "LIMITED", "MYTHIC", "COMPANION")

def _is_shareworthy_hunt(result_text: str) -> bool:
    upper = result_text.upper()
    return any(marker in upper for marker in _SHAREWORTHY_HUNT_MARKERS) or "wild" in result_text.lower() and "appeared" in result_text.lower()

async def _hunt_share_url(context: ContextTypes.DEFAULT_TYPE, user) -> str | None:
    try:
        bot_username = (await context.bot.get_me()).username
    except Exception:
        return None
    link = f"https://t.me/{bot_username}?start=ref_{user.id}"
    caption = quote("I just made a great catch on Aira 🐾 — come hunt with me!")
    return f"https://t.me/share/url?url={quote(link, safe='')}&text={caption}"

def _zoo_nav_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton("🎯 Hunt", callback_data="hunt_again")]])

def _zoo_text(u: dict, full_name: str) -> str:
    zoo = u.get("animals", [])
    if not zoo:
        return f"🦁 ✦ *{_safe_md(full_name)}'s Zoo* ✦\n┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄\n🕳️ Empty. Tap *🎯 Hunt* below to catch your first animal!"
    lines = [f"🦁 ✦ *{_safe_md(full_name)}'s Zoo* ✦\n┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄"]
    order = list(RARITY_WEIGHTS.keys())
    for a in sorted(zoo, key=lambda x: order.index(x["rarity"]) if x["rarity"] in order else 99, reverse=True):
        icon = RARITY_COLORS.get(a["rarity"], "⬜")
        evo_tag = " 🧬" if a.get("count", 1) >= 3 and any(
            base["name"] == a["name"] and base.get("evolves_to") for base in ANIMALS) else ""
        lines.append(f"{a['name']} {icon} *{a['rarity']}* ×{a.get('count',1)}{evo_tag}")
    lines.append(f"\n🪙 Coins: *{u.get('coins',0):,}* | 💎 Gems: *{u.get('gems',0):,}*")
    lines.append("_🧬 = ready to /evolve!_")
    return "\n".join(lines)

async def cmd_hunt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    result = await do_hunt(context.bot, update.message.chat_id, user.id, user.username, user.full_name)
    share_url = await _hunt_share_url(context, user) if _is_shareworthy_hunt(result) else None
    await update.message.reply_text(result, reply_markup=_hunt_result_kb(share_url), parse_mode="Markdown")

async def cmd_zoo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    u = get_user_fast(str(user.id))
    await update.message.reply_text(_zoo_text(u, user.full_name), reply_markup=_zoo_nav_kb(), parse_mode="Markdown")

_hunt_click_times = {}  # user_id -> monotonic timestamp of last processed hunt_ button click

async def _safe_edit_message_text(query, text, **kwargs):
    """edit_message_text wrapper that survives Telegram flood control instead of
    crashing the handler. Retries once after the server-specified wait (capped),
    otherwise swallows the error so a single laggy click doesn't 500 the update."""
    try:
        await query.edit_message_text(text, **kwargs)
    except RetryAfter as e:
        wait = min(float(e.retry_after) + 0.5, 5.0)
        await asyncio.sleep(wait)
        try:
            await query.edit_message_text(text, **kwargs)
        except (RetryAfter, BadRequest):
            pass
    except BadRequest:
        pass

async def handle_hunt_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Buttons on the /hunt and /zoo cards: hunt again or jump to the zoo view
    in place, both edited into the same message instead of sending a new one."""
    query = update.callback_query
    action = query.data.replace("hunt_", "")
    user = query.from_user

    if action == "again":
        # Debounce: rapid double/triple taps on "Hunt Again" fire several
        # edit_message_text calls back-to-back and trip Telegram's flood
        # control (RetryAfter), which used to crash the handler. Ignore
        # clicks that land within 1.2s of the last processed one.
        now = time.monotonic()
        last = _hunt_click_times.get(user.id, 0)
        if now - last < 1.2:
            await query.answer("⏳ Slow down a bit!")
            return
        _hunt_click_times[user.id] = now

        await query.answer("🎯 Hunting...")
        result = await do_hunt(context.bot, query.message.chat_id, user.id, user.username, user.full_name)
        share_url = await _hunt_share_url(context, user) if _is_shareworthy_hunt(result) else None
        await _safe_edit_message_text(query, result, reply_markup=_hunt_result_kb(share_url), parse_mode="Markdown")
    elif action == "zoo":
        try:
            await query.answer()
        except (BadRequest, TelegramError):
            pass  # stale/expired callback query — safe to ignore, continue handling
        u = get_user_fast(str(user.id))
        await _safe_edit_message_text(query, _zoo_text(u, user.full_name), reply_markup=_zoo_nav_kb(), parse_mode="Markdown")
    else:
        try:
            await query.answer()
        except (BadRequest, TelegramError):
            pass  # stale/expired callback query — safe to ignore, continue handling

async def cmd_inventory(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    doc = get_user_fast(str(user.id))
    ws = get_weapon_effective_stats(doc)
    inv = doc.get("weapon_inventory", [])
    lines = [f"🎒 ✦ *{_safe_md(user.full_name)}'s Inventory* ✦\n┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄", f"🏹 *Equipped:* {ws['name']}"]
    if inv:
        lines.append("\n📦 *Stored Weapons:*")
        for wkey in inv:
            w = WEAPONS.get(wkey)
            if w: lines.append(f"  {w['name']} | ATK+{w['atk_bonus']} | Catch+{w['catch_bonus']}%")
        lines.append("\n_Use /equipweapon <name> to switch_")
    else:
        lines.append("\n📦 *Stored Weapons:* None")
    buffs = []
    for key, label in [("half_cooldown_expiry", "⚡ Cooldown Slash"), ("owo_boost_expiry", "🐾 Hunt Boost"),
                        ("shield_expiry", "🛡️ Shield")]:
        exp = doc.get(key)
        if exp:
            try:
                rem = (datetime.fromisoformat(exp) - datetime.now()).total_seconds()
                if rem > 0: buffs.append(f"{label}: *{int(rem//60)}m {int(rem%60)}s* left")
            except Exception: pass
    if doc.get("cheap_autohunt"): buffs.append("🤖 Budget AutoHunt: *Active*")
    if buffs:
        lines.append("\n✨ *Active Buffs:*")
        lines += [f"  {b}" for b in buffs]
    await update.message.reply_text(
        "\n".join(lines), parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("🦁 My Zoo", callback_data="hunt_zoo"),
            InlineKeyboardButton("💼 Wallet", callback_data="prof_wallet"),
        ]]))

async def cmd_equipweapon(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    if not context.args:
        await update.message.reply_text("Usage: `/equipweapon <name>`", parse_mode="Markdown"); return
    arg = " ".join(context.args).lower()
    uid = str(user.id)
    doc = get_user_fast(uid)
    inv = doc.get("weapon_inventory", [])
    w_key = next((k for k in inv if arg in WEAPONS.get(k, {}).get("name", "").lower()), None)
    if not w_key:
        await update.message.reply_text(f"❌ '{arg}' not in inventory! Check /inventory.", parse_mode="Markdown"); return
    current = doc.get("weapon", "stick")
    inv.remove(w_key)
    if current != "stick": inv.append(current)
    doc["weapon"] = w_key; doc["weapon_inventory"] = inv
    save_user_fast(uid)
    w = WEAPONS[w_key]
    await update.message.reply_text(
        f"✅ ✦ *Weapon Switched!* ✦\n┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄\n"
        f"🏹 Now wielding: *{w['name']}*\n"
        f"⚔️ ATK Bonus: +{w['atk_bonus']}% | 🎯 Catch Rate: +{w['catch_bonus']}%",
        parse_mode="Markdown")

async def cmd_owoprofile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    u = get_user_fast(str(user.id))
    zoo = u.get("animals", [])
    total = sum(z.get("count", 1) for z in zoo)
    legends = sum(z.get("count", 1) for z in zoo if z.get("rarity") == "legendary")
    boost = "⚡ Active" if (u.get("owo_boost_expiry") and datetime.fromisoformat(u["owo_boost_expiry"]) > datetime.now()) else "None"
    ws = get_weapon_effective_stats(u)
    cd = u.get("hunt_cooldown"); cd_line = ""
    if cd:
        rem = (datetime.fromisoformat(cd) - datetime.now()).total_seconds()
        if rem > 0: cd_line = f"\n⏳ Cooldown: *{int(rem)}s*"
    await update.message.reply_text(
        f"🐾 ✦ *{_safe_md(user.full_name)}'s Hunting Profile* ✦\n┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄\n"
        f"🪙 Coins: *{u.get('coins',0):,}* | 💎 Gems: *{u.get('gems',0):,}*\n"
        f"🎯 Hunts: *{u.get('hunts',0)}* | 🦁 Animals: *{total}*\n"
        f"🐉 Legendary: *{legends}* | 🏹 Weapon: {ws['name']}\n"
        f"⚡ Boost: {boost}{cd_line}\n"
        f"🤖 Auto Hunt: {'✅ On' if u.get('auto_hunt') else '❌ Off'}",
        reply_markup=_hunt_result_kb(), parse_mode="Markdown")

AUTOHUNT_COST = 10
AUTOHUNT_DURATION = 3600
AUTOHUNT_INTERVAL = 60

async def cmd_autohunt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    uid = str(user.id)
    doc = get_user_fast(uid)
    if doc.get("auto_hunt"):
        doc["auto_hunt"] = False; doc["auto_hunt_expiry"] = None
        save_user_fast(uid)
        for job in context.job_queue.get_jobs_by_name(f"autohunt_{user.id}"): job.schedule_removal()
        for job in context.job_queue.get_jobs_by_name(f"autohunt_expire_{user.id}"): job.schedule_removal()
        await update.message.reply_text("🤖 Auto Hunt *OFF*.", parse_mode="Markdown"); return
    actual_cost = 5 if doc.get("cheap_autohunt") else AUTOHUNT_COST
    min_coins = actual_cost * 10
    if doc.get("coins", 0) < min_coins:
        await update.message.reply_text(f"❌ Need *{min_coins:,}* 🪙 to start. You have *{doc.get('coins',0):,}* 🪙.",
                                         parse_mode="Markdown"); return
    doc["auto_hunt"] = True
    doc["auto_hunt_expiry"] = (datetime.now() + timedelta(seconds=AUTOHUNT_DURATION)).isoformat()
    save_user_fast(uid)
    chat_id = update.message.chat_id
    context.job_queue.run_repeating(auto_hunt_job, interval=AUTOHUNT_INTERVAL, first=5,
                                     name=f"autohunt_{user.id}", chat_id=chat_id,
                                     data={"chat_id": chat_id, "user_id": user.id})
    context.job_queue.run_once(auto_hunt_expire, when=AUTOHUNT_DURATION,
                                name=f"autohunt_expire_{user.id}", chat_id=chat_id,
                                data={"chat_id": chat_id, "user_id": user.id})
    await update.message.reply_text(
        f"🤖 *Auto Hunt ON!*\n⏱️ 1 hour | 💸 {actual_cost} 🪙/hunt | Every {AUTOHUNT_INTERVAL}s\n"
        f"_Results are DMed to you. /autohunt to stop._", parse_mode="Markdown")

async def auto_hunt_job(context: ContextTypes.DEFAULT_TYPE):
    d = context.job.data; user_id = d["user_id"]
    uid = str(user_id)
    doc = get_user_fast(uid)
    if not doc.get("auto_hunt"):
        context.job.schedule_removal(); return
    expiry = doc.get("auto_hunt_expiry")
    if expiry:
        try:
            if datetime.fromisoformat(expiry) < datetime.now():
                doc["auto_hunt"] = False; doc["auto_hunt_expiry"] = None
                save_user_fast(uid)
                context.job.schedule_removal(); return
        except Exception: pass
    cheap_expiry = doc.get("cheap_autohunt_expiry")
    if cheap_expiry:
        try:
            if datetime.fromisoformat(cheap_expiry) < datetime.now():
                doc["cheap_autohunt"] = False; doc["cheap_autohunt_expiry"] = None
                save_user_fast(uid)
        except Exception: pass
    actual_cost = 5 if doc.get("cheap_autohunt") else AUTOHUNT_COST
    if doc.get("coins", 0) < actual_cost:
        doc["auto_hunt"] = False; doc["auto_hunt_expiry"] = None
        save_user_fast(uid)
        context.job.schedule_removal()
        try: await context.bot.send_message(user_id, "🤖 *Auto Hunt stopped!* Not enough coins.", parse_mode="Markdown")
        except TelegramError: pass
        return
    # Deduct the cost BEFORE hunting so we don't go negative, but wrap the
    # hunt itself in try/except and refund on any unexpected error — this is
    # the fix for coins being silently eaten when do_hunt throws (e.g. a
    # transient API error), which was draining balances and stopping autohunt
    # after just 2-3 runs whenever an exception occurred mid-hunt.
    doc["coins"] -= actual_cost
    save_user_fast(uid)
    username = doc.get("username"); full_name = doc.get("full_name")
    try:
        result = await do_hunt(context.bot, user_id, user_id, username, full_name, manual=False)
    except Exception as hunt_err:
        # Refund the cost so the user isn't penalised for a transient error
        doc["coins"] += actual_cost
        save_user_fast(uid)
        logger.error(f"auto_hunt_job: do_hunt raised for uid={uid}: {hunt_err}")
        return
    short_msg = result
    if "Caught" in result:
        try:
            line = [l for l in result.split("\n") if "Caught" in l][0]
            short_msg = f"🤖 *{full_name or username or 'Hunter'}* → {line.replace('Caught ','')}"
        except Exception: short_msg = result.split("\n")[0]
    try: await context.bot.send_message(user_id, short_msg, parse_mode="Markdown")
    except TelegramError: pass

async def auto_hunt_expire(context: ContextTypes.DEFAULT_TYPE):
    d = context.job.data; chat_id = d["chat_id"]; user_id = d["user_id"]
    uid = str(user_id)
    doc = get_user_fast(uid)
    doc["auto_hunt"] = False; doc["auto_hunt_expiry"] = None
    save_user_fast(uid)
    for job in context.job_queue.get_jobs_by_name(f"autohunt_{user_id}"): job.schedule_removal()
    name = f"@{doc.get('username')}" if doc.get("username") and doc.get("username") != "Unknown" else doc.get("full_name", "Hunter")
    try: await context.bot.send_message(user_id, f"⌛ *{name}'s Auto Hunt ended!* /autohunt to restart.", parse_mode="Markdown")
    except TelegramError: pass


def _reschedule_active_autohunts(application):
    """Called once at startup — reschedules autohunt jobs for every user who had
    auto_hunt=True when the bot last stopped (e.g. free-tier restart, crash).
    Without this, users lose their running autohunt silently on every restart."""
    data  = load_data()
    users = data.get("users", {})
    now   = datetime.now()
    count = 0
    for uid_str, doc in users.items():
        if not doc.get("auto_hunt"):
            continue
        expiry_raw = doc.get("auto_hunt_expiry")
        if expiry_raw:
            try:
                expiry = datetime.fromisoformat(expiry_raw)
                if expiry <= now:
                    # Already expired — clean it up
                    doc["auto_hunt"] = False
                    doc["auto_hunt_expiry"] = None
                    save_user_fast(uid_str)
                    continue
                remaining = (expiry - now).total_seconds()
            except Exception:
                remaining = AUTOHUNT_DURATION
        else:
            remaining = AUTOHUNT_DURATION
        try:
            user_id = int(uid_str)
        except (ValueError, TypeError):
            continue
        # Re-schedule the repeating hunt job and the expiry job
        application.job_queue.run_repeating(
            auto_hunt_job, interval=AUTOHUNT_INTERVAL, first=10,
            name=f"autohunt_{user_id}", chat_id=user_id,
            data={"chat_id": user_id, "user_id": user_id})
        application.job_queue.run_once(
            auto_hunt_expire, when=remaining,
            name=f"autohunt_expire_{user_id}", chat_id=user_id,
            data={"chat_id": user_id, "user_id": user_id})
        count += 1
    if count:
        logger.info(f"✅ Rescheduled autohunt for {count} user(s) after restart.")

@with_data_lock
async def cmd_battle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    if context.args and context.args[0].lower() == "howto":
        await update.message.reply_text(_game_howto("battle"), parse_mode="Markdown"); return
    data = load_data()
    u = get_user(data, user.id, user.username, user.full_name)
    cd = u.get("hunt_cooldown")
    if cd:
        rem = (datetime.fromisoformat(cd) - datetime.now()).total_seconds()
        if rem > 0: await update.message.reply_text(f"⏳ Cooldown: *{int(rem)}s*", parse_mode="Markdown"); return
    BATTLE_ENEMIES = [
        {"name": "🐍 Snake", "hp": 30, "atk": 8}, {"name": "🦂 Scorpion", "hp": 25, "atk": 10},
        {"name": "🐊 Croc", "hp": 50, "atk": 12}, {"name": "🐻 Bear", "hp": 60, "atk": 15},
        {"name": "🐯 Tiger", "hp": 55, "atk": 18}, {"name": "🐉 Dragon", "hp": 120, "atk": 30},
    ]
    ws = get_weapon_effective_stats(u)
    enemy = random.choice(BATTLE_ENEMIES)
    php, ehp, rounds = 50, enemy["hp"], 0
    while php > 0 and ehp > 0 and rounds < 12:
        p_atk = random.randint(8 + ws["atk_bonus"] // 2, 20 + ws["atk_bonus"])
        e_atk = random.randint(int(enemy["atk"] * 0.7), enemy["atk"])
        ehp -= p_atk; php -= e_atk; rounds += 1
    u["hunt_cooldown"] = (datetime.now() + timedelta(seconds=45)).isoformat()
    battle_kb = InlineKeyboardMarkup([[InlineKeyboardButton("💼 Wallet", callback_data="prof_wallet")]])
    if php > 0:
        reward = enemy["atk"] * 3; gems_r = random.randint(2, 8)
        u["coins"] += reward; u["gems"] = u.get("gems", 0) + gems_r; u["hunts"] = u.get("hunts", 0) + 1
        check_badges(u); save_data(data)
        await update.message.reply_text(
            f"⚔️ ✦ *Battle vs {enemy['name']}* ✦\n┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄\n{rounds} rounds | HP left: *{max(0,php)}*\n\n"
            f"🏆 *Victory!* +{reward:,} 🪙 +{gems_r} 💎",
            reply_markup=battle_kb, parse_mode="Markdown")
    else:
        loss = random.randint(5, 15); u["coins"] = max(0, u["coins"] - loss); save_data(data)
        await update.message.reply_text(
            f"⚔️ ✦ *Battle vs {enemy['name']}* ✦\n┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄\n{rounds} rounds\n\n💀 *Defeated!* -{loss} 🪙",
            reply_markup=battle_kb, parse_mode="Markdown")

# ---- sell / topanimals / forgewar -------------------------------------------
async def cmd_sell(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    uid = str(user.id)
    doc = get_user_fast(uid)
    zoo = doc.get("animals", [])
    if not zoo:
        await update.message.reply_text("🦁 Your zoo is empty — nothing to sell yet!\n_Use /hunt to catch your first animal._",
                                         reply_markup=_zoo_nav_kb(), parse_mode="Markdown"); return
    if not context.args:
        await update.message.reply_text("📝 *Usage:*\n`/sell all` | `/sell all common` | `/sell <name>`", parse_mode="Markdown"); return
    arg = " ".join(context.args).lower().strip()
    VALID = ["common","uncommon","rare","epic","legendary","extreme","mythic","pet"]

    def do_sell(entries):
        total_c = total_g = count = 0
        for e in entries:
            match = next((a for a in ANIMALS if a["name"] == e["name"]), None)
            if match:
                cnt = e.get("count", 1)
                total_c += match["sell"] * cnt; total_g += match["gems"] * cnt; count += cnt
        return total_c, total_g, count

    if arg == "all":
        tc, tg, cnt = do_sell(zoo)
        doc["animals"] = []; doc["coins"] = doc.get("coins", 0) + tc; doc["gems"] = doc.get("gems", 0) + tg
        doc["total_coins_ever"] = doc.get("total_coins_ever", 0) + tc
        save_user_fast(uid)
        await update.message.reply_text(f"💰 *Sold all {cnt} animals!*\n+{tc:,} 🪙 | +{tg:,} 💎\n"
                                         f"Balance: *{doc['coins']:,}* 🪙 | *{doc['gems']:,}* 💎", parse_mode="Markdown"); return
    if arg.startswith("all "):
        rarity = arg[4:].strip()
        if rarity not in VALID:
            await update.message.reply_text(f"❌ Unknown rarity *{rarity}*", parse_mode="Markdown"); return
        to_sell = [z for z in zoo if z.get("rarity", "").lower() == rarity]
        to_keep = [z for z in zoo if z.get("rarity", "").lower() != rarity]
        if not to_sell: await update.message.reply_text(f"❌ No *{rarity}* animals!", parse_mode="Markdown"); return
        tc, tg, cnt = do_sell(to_sell)
        doc["animals"] = to_keep; doc["coins"] = doc.get("coins", 0) + tc; doc["gems"] = doc.get("gems", 0) + tg
        doc["total_coins_ever"] = doc.get("total_coins_ever", 0) + tc
        save_user_fast(uid)
        icon = RARITY_COLORS.get(rarity, "⬜")
        await update.message.reply_text(f"💰 *Sold {cnt} {icon} {rarity.capitalize()} animals!*\n+{tc:,} 🪙 | +{tg:,} 💎\n"
                                         f"Balance: *{doc['coins']:,}* 🪙 | *{doc['gems']:,}* 💎", parse_mode="Markdown"); return
    entry = next((z for z in zoo if arg in z["name"].lower()), None)
    if not entry: await update.message.reply_text(f"❌ No animal matching '*{arg}*'!", parse_mode="Markdown"); return
    tc, tg, cnt = do_sell([entry])
    zoo.remove(entry); doc["animals"] = zoo
    doc["coins"] = doc.get("coins", 0) + tc; doc["gems"] = doc.get("gems", 0) + tg
    doc["total_coins_ever"] = doc.get("total_coins_ever", 0) + tc
    save_user_fast(uid)
    await update.message.reply_text(f"💰 *Sold {entry['name']}* ×{cnt}\n+{tc:,} 🪙 | +{tg:,} 💎\n"
                                     f"Balance: *{doc['coins']:,}* 🪙 | *{doc['gems']:,}* 💎", parse_mode="Markdown")

@with_data_lock
async def cmd_topanimals(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = load_data()
    scores = []
    for uid, u in data["users"].items():
        zoo = u.get("animals", [])
        score = 0
        for z in zoo:
            w = {"common":1,"uncommon":2,"rare":5,"epic":10,"legendary":25,"Extreme":100,"limited":250,"mythic":500}.get(z.get("rarity","common"),1)
            score += w * z.get("count", 1)
        if score > 0: scores.append((u.get("full_name","?"), u.get("title"), score, zoo))
    scores.sort(key=lambda x: x[2], reverse=True)
    medals = ["🥇","🥈","🥉","4️⃣","5️⃣","6️⃣","7️⃣","8️⃣","9️⃣","🔟"]
    lines = ["🦁 ✦ *TOP ANIMAL COLLECTORS* ✦\n┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄"]
    for i, (name, title, score, zoo) in enumerate(scores[:10]):
        tag = f" 👑{title}" if title else ""
        legends = sum(z.get("count",1) for z in zoo if z.get("rarity") == "legendary")
        lines.append(f"{medals[i]} *{_safe_md(name)}*{tag}\n   ⭐ Score: {score:,} | 🐉 ×{legends}")
    if not scores: lines.append("🕳️ No collectors yet — be the first with /hunt!")
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")

async def cmd_forgewar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    if not await is_admin(context.bot, chat_id, update.message.from_user.id):
        await update.message.reply_text("🚫 *Admins only!* This command needs admin rights.", parse_mode="Markdown"); return
    group = get_group_db(chat_id)
    group["forge_war"] = True; group["forge_war_multiplier"] = 2
    save_group_db(chat_id, group)
    await update.message.reply_text("⚔️ *FORGE WAR!* All rewards ×2 for 1 hour! 🪙🔥", parse_mode="Markdown")
    context.job_queue.run_once(_end_forge_war_job, when=3600, name=f"fw_{chat_id}",
                                data={"chat_id": chat_id})

async def _end_forge_war_job(context: ContextTypes.DEFAULT_TYPE):
    await _end_forge_war(context, context.job.data["chat_id"])

async def _end_forge_war(context, chat_id):
    group = get_group_db(chat_id); group["forge_war"] = False; group["forge_war_multiplier"] = 1
    save_group_db(chat_id, group)
    await context.bot.send_message(chat_id, "⚔️ *Forge War ended!* Back to normal. 🏆", parse_mode="Markdown")

async def cmd_challenge(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    group = get_group_db(chat_id)
    if group.get("active_challenge"):
        await update.message.reply_text("⚠️ Challenge already running!"); return
    last = group.get("last_challenge_time")
    if last:
        elapsed = (datetime.now() - datetime.fromisoformat(last)).total_seconds()
        if elapsed < CHALLENGE_COOLDOWN:
            await update.message.reply_text(f"⏳ Cooldown! Next in *{int(CHALLENGE_COOLDOWN-elapsed)}s*.", parse_mode="Markdown"); return
    await post_challenge(context, chat_id)

async def cmd_hint(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ch = get_group_db(update.message.chat_id).get("active_challenge")
    if not ch: await update.message.reply_text("No active challenge!"); return
    await update.message.reply_text(f"💡 *Hint:* _{ch['hint']}_", parse_mode="Markdown")

async def cmd_skipit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    if update.message.chat.type != "private" and not await is_admin(context.bot, chat_id, update.message.from_user.id):
        await update.message.reply_text("🚫 *Admins only!* This command needs admin rights.", parse_mode="Markdown"); return
    group = get_group_db(chat_id)
    if not group.get("active_challenge"): await update.message.reply_text("No challenge to skip!"); return
    group["active_challenge"] = None; save_group_db(chat_id, group)
    for job in context.job_queue.get_jobs_by_name(f"expire_{chat_id}"): job.schedule_removal()
    await update.message.reply_text("⏭️ Skipped! Starting new challenge...")
    await post_challenge(context, chat_id)

async def cmd_toggle_challenge(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    if update.message.chat.type != "private" and not await is_admin(context.bot, chat_id, update.message.from_user.id):
        await update.message.reply_text("🚫 *Admins only!* This command needs admin rights.", parse_mode="Markdown"); return
    if not context.args:
        await update.message.reply_text("Usage: `/togglechallenge on` or `/togglechallenge off`", parse_mode="Markdown"); return
    status = context.args[0].lower()
    group = get_group_db(chat_id)
    if status == "on":
        group["auto_challenge_enabled"] = True; save_group_db(chat_id, group)
        track_chat(chat_id, update.message.chat.type != "private")
        await update.message.reply_text("✅ Auto-challenges enabled.")
    elif status == "off":
        group["auto_challenge_enabled"] = False; save_group_db(chat_id, group)
        for job in context.job_queue.get_jobs_by_name(f"autochallenge_{chat_id}"): job.schedule_removal()
        _auto_challenge_chats.discard(chat_id)
        await update.message.reply_text("❌ Auto-challenges disabled.")
    else:
        await update.message.reply_text("Usage: `/togglechallenge on` or `/togglechallenge off`", parse_mode="Markdown")

# ══════════════════════════════════════════════════════════════════════════════
#  SHOP / GEM SHOP / TITLE
# ══════════════════════════════════════════════════════════════════════════════
def _shop_keyboard():
    kb = [[InlineKeyboardButton(f"{v['name']} – {v['cost']} 🪙", callback_data=f"buy_{k}")] for k, v in SHOP_ITEMS.items()]
    kb.append([InlineKeyboardButton("📦 Crates", callback_data="shop_crates"),
               InlineKeyboardButton("💎 Gem Shop", callback_data="shop_gems")])
    return InlineKeyboardMarkup(kb)

def _crate_submenu_keyboard():
    crate_buttons = [InlineKeyboardButton(f"{c['name']} – {c['cost']:,} 🪙", callback_data=f"buycrate_{cid}")
                      for cid, c in CRATES.items()]
    kb = [crate_buttons[i:i + 2] for i in range(0, len(crate_buttons), 2)]
    kb.append([InlineKeyboardButton("📂 My Crates / Open (/crate)", callback_data="shop_mycrates")])
    kb.append([InlineKeyboardButton("⬅️ Back to Shop", callback_data="shop_back")])
    return InlineKeyboardMarkup(kb)

@with_data_lock
async def cmd_shop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    data = load_data()
    u = get_user(data, user.id, user.username, user.full_name)
    save_data(data)
    await update.message.reply_text(
        card("Forge Shop", f"Balance: *{u['coins']:,}* 🪙",
             "_Tap to buy — crates go to your inventory, open with `/crate <id>`_"),
        reply_markup=_shop_keyboard(), parse_mode="Markdown")

@with_data_lock
async def handle_crate_shop_purchase(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Buy a tiered crate directly from the /shop → Crates submenu."""
    query = update.callback_query
    try:
        await query.answer()
    except (BadRequest, TelegramError):
        pass  # stale/expired callback query — safe to ignore, continue handling
    user = query.from_user

    if query.data == "shop_crates":
        await _safe_edit_message_text(query, "📦 *CRATE SHOP*\nTap to buy — goes straight to your inventory:",
                                       parse_mode="Markdown", reply_markup=_crate_submenu_keyboard())
        return
    if query.data == "shop_back":
        data = load_data(); u = get_user(data, user.id, user.username, user.full_name); save_data(data)
        await _safe_edit_message_text(query, 
            f"🛒 ✦ *{fancy('FORGE SHOP')}* ✦\n┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄\nBalance: *{u['coins']:,}* 🪙\nTap to buy:",
            reply_markup=_shop_keyboard(), parse_mode="Markdown")
        return
    if query.data == "shop_gems":
        # Lets players hop from the Forge Shop straight into the Gem Shop
        # without needing to type /gemshop separately.
        doc = get_user_fast(str(user.id))
        text, kb = _gemshop_render(doc)
        await _safe_edit_message_text(query, text, reply_markup=kb, parse_mode="Markdown")
        return
    if query.data == "shop_mycrates":
        doc = get_user_fast(str(user.id))
        crate_inv = doc.get("crate_inventory", [])
        if not crate_inv:
            await query.answer("📦 No crates yet — buy one above!", show_alert=True); return
        counts = {}
        for cid in crate_inv: counts[cid] = counts.get(cid, 0) + 1
        lines = ["📦 Your Crates"]
        for cid, cnt in sorted(counts.items()):
            c = CRATES.get(cid)
            if c: lines.append(f"[{cid}] {c['name']} × {cnt}")
        lines.append("\nOpen with /crate <id>")
        await query.answer("\n".join(lines)[:200], show_alert=True)
        return

    crate_id = int(query.data.replace("buycrate_", ""))
    ok, msg, doc = _buy_crate_for_user(user.id, crate_id)
    balance = doc["coins"] if doc else "?"
    await _safe_edit_message_text(query, 
        f"{msg}\n\n_Balance: {balance:,} 🪙_" if ok else msg,
        parse_mode="Markdown", reply_markup=_crate_submenu_keyboard())

@with_data_lock
async def handle_shop_purchase(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    try:
        await query.answer()
    except (BadRequest, TelegramError):
        pass  # stale/expired callback query — safe to ignore, continue handling
    user = query.from_user; key = query.data.replace("buy_", "")
    if key not in SHOP_ITEMS: await _safe_edit_message_text(query, "❌ Unknown item."); return
    data = load_data(); u = get_user(data, user.id, user.username, user.full_name); item = SHOP_ITEMS[key]
    if u["coins"] < item["cost"]:
        await _safe_edit_message_text(query, 
            f"❌ *Not enough coins!*\nNeed *{item['cost']:,}* 🪙 but you have *{u['coins']:,}* 🪙.",
            parse_mode="Markdown"); return
    u["coins"] -= item["cost"]; award_badge(u, "spender")
    msg = f"✅ *Purchased: {item['name']}*\n_{item['desc']}_\n\n💰 Remaining: *{u['coins']:,}* 🪙"
    if key == "double_coins":
        u["double_coins"] = True; msg += "\n\n⚡ Next win = DOUBLE coins!"
    elif key == "hint_reveal":
        ch = get_group_db(query.message.chat_id).get("active_challenge")
        msg += f"\n\n💡 *Hint:* _{ch['hint']}_" if ch else "\n\n⚠️ No active challenge."
    elif key == "custom_title":
        u["title_purchased"] = True; u["title_chat_id"] = query.message.chat_id
        msg += "\n\n👑 Use `/settitle YourTitle`!"
    elif key == "pin_message":
        u["pin_token"] = True; msg += "\n\n📌 Reply to msg + /pinit!"
    elif key == "skip_challenge":
        cid = query.message.chat_id; g = get_group_db(cid)
        if g.get("active_challenge"):
            g["active_challenge"] = None; save_group_db(cid, g)
            for job in context.job_queue.get_jobs_by_name(f"expire_{cid}"): job.schedule_removal()
            save_data(data)
            await _safe_edit_message_text(query, f"✅ *Skipped!* Starting a new challenge...\n💰 Coins: *{u['coins']:,}*", parse_mode="Markdown")
            await post_challenge(context, cid); return
        else:
            u["coins"] += item["cost"]; msg = "⚠️ No active challenge — refunded! 💰"
    elif key == "shield":
        u["shield_expiry"] = (datetime.now() + timedelta(hours=1)).isoformat(); msg += "\n\n🛡️ Protected from /timeout for 1h!"
    elif key == "owo_boost":
        u["owo_boost_expiry"] = (datetime.now() + timedelta(hours=1)).isoformat(); msg += "\n\n🐾 Double hunt rewards for 1h!"
    elif key == "half_cooldown":
        u["half_cooldown_expiry"] = (datetime.now() + timedelta(minutes=20)).isoformat(); msg += "\n\n⚡ Cooldowns halved for 20 min!"
    elif key == "cheap_autohunt":
        u["cheap_autohunt"] = True
        u["cheap_autohunt_expiry"] = (datetime.now() + timedelta(hours=1)).isoformat()
        msg += "\n\n🤖 Budget AutoHunt active for 1 hour!"
    elif key == "loot_crate":
        coins_won = random.randint(50, 300); gems_won = random.randint(1, 10)
        u["coins"] += coins_won; u["gems"] = u.get("gems", 0) + gems_won
        u["total_coins_ever"] = u.get("total_coins_ever", 0) + coins_won
        msg += f"\n\n📦 Crate contained: *+{coins_won} 🪙* and *+{gems_won} 💎*!"
    save_data(data)
    await _safe_edit_message_text(query, 
        msg, parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🛒 Back to Shop", callback_data="shop_back")]]))

def _gemshop_render(u: dict):
    """Builds the Gem Shop text + keyboard. Shared by /gemshop and the
    '💎 Gem Shop' shortcut button on /shop so both stay perfectly in sync."""
    lines = ["💎 ✦ *GEM SHOP — Weapons* ✦\n┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄"]
    kb = []
    for wkey, w in WEAPONS.items():
        owned = " ✅ *Equipped*" if u.get("weapon") == wkey else ""
        lines.append(f"{w['name']}{owned}\n  💎 {w['gems']} | ⚔️ ATK+{w['atk_bonus']} | 🎯 Catch+{w['catch_bonus']}%")
        if u.get("weapon") != wkey:
            kb.append([InlineKeyboardButton(f"Buy {w['name']} – {w['gems']}💎", callback_data=f"gbuy_{wkey}")])
    lines.append(f"\n💎 Your Gems: *{u.get('gems',0):,}*\n_Once equipped, use /upgradeweapon to level it up!_")
    kb.append([InlineKeyboardButton("🛒 Back to Shop", callback_data="shop_back")])
    return "\n".join(lines), InlineKeyboardMarkup(kb)

@with_data_lock
async def cmd_gemshop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    data = load_data(); u = get_user(data, user.id, user.username, user.full_name); save_data(data)
    text, kb = _gemshop_render(u)
    await update.message.reply_text(text, reply_markup=kb, parse_mode="Markdown")

@with_data_lock
async def handle_gem_purchase(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    try:
        await query.answer()
    except (BadRequest, TelegramError):
        pass  # stale/expired callback query — safe to ignore, continue handling
    user = query.from_user; wkey = query.data.replace("gbuy_", "")
    if wkey not in WEAPONS: await _safe_edit_message_text(query, "❌ Unknown weapon."); return
    data = load_data(); u = get_user(data, user.id, user.username, user.full_name)
    w = WEAPONS[wkey]
    if u.get("gems", 0) < w["gems"]:
        await _safe_edit_message_text(query, 
            f"❌ *Not enough gems!*\nNeed *{w['gems']}* 💎 but you have *{u.get('gems',0)}* 💎.",
            parse_mode="Markdown"); return
    old = u.get("weapon", "stick")
    inv = u.get("weapon_inventory", [])
    if old != "stick" and old not in inv: inv.append(old)
    u["weapon_inventory"] = inv; u["gems"] -= w["gems"]; u["weapon"] = wkey
    save_data(data)
    await _safe_edit_message_text(query, 
        f"✅ ✦ *Weapon Equipped!* ✦\n┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄\n"
        f"🏹 Now wielding: *{w['name']}*\n"
        f"⚔️ ATK Bonus: +{w['atk_bonus']}% | 🎯 Catch Rate: +{w['catch_bonus']}%\n"
        f"💎 Gems remaining: *{u['gems']:,}*",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🛒 Back to Shop", callback_data="shop_back")]]),
        parse_mode="Markdown")

async def set_member_tag(bot, chat_id, user_id, title):
    title = title[:16]
    try:
        await bot.set_chat_administrator_custom_title(chat_id=chat_id, user_id=user_id, custom_title=title)
        return True, "direct"
    except TelegramError: pass
    try:
        await bot.promote_chat_member(chat_id=chat_id, user_id=user_id, can_manage_chat=False,
            can_delete_messages=False, can_manage_video_chats=False, can_restrict_members=False,
            can_promote_members=False, can_change_info=False, can_invite_users=True, can_pin_messages=False)
        await asyncio.sleep(0.5)
        await bot.set_chat_administrator_custom_title(chat_id=chat_id, user_id=user_id, custom_title=title)
        return True, "promoted"
    except TelegramError as e:
        return False, str(e)

@with_data_lock
async def expire_title_job(context: ContextTypes.DEFAULT_TYPE):
    d = context.job.data; uid, chat_id, name = d["user_id"], d["chat_id"], d["name"]
    data = load_data(); u = data["users"].get(str(uid))
    if u: u["title"] = None; u["title_expiry"] = None; u["title_chat_id"] = None; save_data(data)
    try:
        await context.bot.promote_chat_member(chat_id=chat_id, user_id=uid, can_manage_chat=False,
            can_delete_messages=False, can_manage_video_chats=False, can_restrict_members=False,
            can_promote_members=False, can_change_info=False, can_invite_users=False, can_pin_messages=False)
    except TelegramError: pass
    try: await context.bot.send_message(chat_id, f"⌛ {name}'s member tag expired and was removed.")
    except Exception: pass

@with_data_lock
async def cmd_settitle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user; chat_id = update.message.chat_id
    if not context.args: await update.message.reply_text("Usage: `/settitle Title`", parse_mode="Markdown"); return
    title = " ".join(context.args)[:16]
    data = load_data(); u = get_user(data, user.id, user.username, user.full_name)
    if not u.get("title_purchased"):
        await update.message.reply_text("❌ Buy *Member Tag* from /shop first!", parse_mode="Markdown"); return
    for job in context.job_queue.get_jobs_by_name(f"title_expire_{user.id}"): job.schedule_removal()
    ok, mode = await set_member_tag(context.bot, chat_id, user.id, title)
    if not ok:
        u["title_purchased"] = False; save_data(data)
        await update.message.reply_text("❌ *Failed!* Make sure Aira is admin. Purchase refunded!", parse_mode="Markdown"); return
    exp = datetime.now() + timedelta(hours=TITLE_HOURS)
    u["title"] = title; u["title_expiry"] = exp.isoformat(); u["title_chat_id"] = chat_id; u["title_purchased"] = False
    save_data(data)
    context.job_queue.run_once(expire_title_job, when=TITLE_HOURS * 3600, name=f"title_expire_{user.id}",
        data={"user_id": user.id, "chat_id": chat_id, "name": _safe_md(f"@{user.username}" if user.username else user.full_name)})
    name = _safe_md(f"@{user.username}" if user.username else user.full_name)
    await update.message.reply_text(f"👑 *{name}* now has tag: *{title}* for 24h!", parse_mode="Markdown")

@with_data_lock
async def cmd_pinit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user; chat_id = update.message.chat_id
    data = load_data(); u = get_user(data, user.id, user.username, user.full_name)
    is_adm = await is_admin(context.bot, chat_id, user.id)
    if not is_adm and not u.get("pin_token"):
        await update.message.reply_text("❌ Buy *Pin a Message* from /shop first!", parse_mode="Markdown"); return
    if not update.message.reply_to_message: await update.message.reply_text("↩️ Reply to a message first!"); return
    try:
        await context.bot.pin_chat_message(chat_id, update.message.reply_to_message.message_id)
        if not is_adm: u["pin_token"] = False; save_data(data)
        name = _safe_md(f"@{user.username}" if user.username else user.full_name)
        await update.message.reply_text(f"📌 *{name}* pinned a message!", parse_mode="Markdown")
    except TelegramError as e:
        await update.message.reply_text(f"❌ Aira needs Pin Messages permission!\n_{e}_", parse_mode="Markdown")

# ══════════════════════════════════════════════════════════════════════════════
#  TRADE / TRADEITEM / AUCTION / PRAY
# ══════════════════════════════════════════════════════════════════════════════
@with_data_lock
async def cmd_trade(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    if not update.message.reply_to_message:
        await update.message.reply_text("↩️ Reply to someone's message to trade with them."); return
    if not context.args: await update.message.reply_text("Usage: Reply + `/trade <amount>`", parse_mode="Markdown"); return
    try: amount = int(context.args[0])
    except Exception: await update.message.reply_text("❌ Amount must be a number."); return
    if amount <= 0: await update.message.reply_text("❌ Must be positive!"); return
    target = update.message.reply_to_message.from_user
    if target.id == user.id: await update.message.reply_text("❌ Can't trade with yourself!"); return
    if target.is_bot: await update.message.reply_text("❌ Can't trade with bots!"); return
    data = load_data(); s = get_user(data, user.id, user.username, user.full_name)
    if s["coins"] < amount: await update.message.reply_text(f"❌ Not enough coins! You have *{s['coins']:,}* 🪙.", parse_mode="Markdown"); return
    sname = _safe_md(f"@{user.username}" if user.username else user.full_name)
    tname = f"@{target.username}" if target.username else _safe_md(target.full_name)
    trade_id = f"trade_{user.id}_{target.id}_{int(datetime.now().timestamp())}"
    data.setdefault("trades", {})[trade_id] = {"from_id": user.id, "to_id": target.id, "amount": amount, "status": "pending"}
    save_data(data)
    kb = [[InlineKeyboardButton("✅ Accept", callback_data=f"tacpt_{trade_id}"),
           InlineKeyboardButton("❌ Decline", callback_data=f"tdecl_{trade_id}")]]
    await update.message.reply_text(f"🤝 ✦ *Trade Request!* ✦\n┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄\n{sname} wants to give *{amount:,}* 🪙 to {tname}\n\n{tname}, accept?",
                                     reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")

@with_data_lock
async def handle_trade(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    try:
        await query.answer()
    except (BadRequest, TelegramError):
        pass  # stale/expired callback query — safe to ignore, continue handling
    parts = query.data.split("_", 1); action = parts[0]; trade_id = parts[1]
    data = load_data(); trades = data.get("trades", {})
    if trade_id not in trades: await _safe_edit_message_text(query, "❌ Trade expired."); return
    trade = trades[trade_id]
    if trade["status"] != "pending": await _safe_edit_message_text(query, "❌ Trade already resolved."); return
    if query.from_user.id != trade["to_id"]: await query.answer("❌ Only the recipient can respond!", show_alert=True); return
    if action == "tacpt":
        s = get_user(data, trade["from_id"]); t = get_user(data, trade["to_id"])
        if s["coins"] < trade["amount"]: await _safe_edit_message_text(query, "❌ Sender no longer has enough coins!"); return
        s["coins"] -= trade["amount"]; t["coins"] += trade["amount"]
        t["total_coins_ever"] = t.get("total_coins_ever", 0) + trade["amount"]
        award_badge(s, "trader"); award_badge(t, "trader")
        trade["status"] = "done"; save_data(data)
        sname = f"@{data['users'][str(trade['from_id'])].get('username','?')}"
        tname = f"@{data['users'][str(trade['to_id'])].get('username','?')}"
        await _safe_edit_message_text(query, f"✅ ✦ *Trade Complete!* ✦\n┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄\n{sname} → {tname}: *{trade['amount']:,}* 🪙", parse_mode="Markdown")
    else:
        trade["status"] = "declined"; save_data(data)
        await _safe_edit_message_text(query, "❌ Trade declined.")

@with_data_lock
async def cmd_tradeitem(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    if not update.message.reply_to_message:
        await update.message.reply_text("↩️ Reply to target, then: `/tradeitem animal Dragon for 500`", parse_mode="Markdown"); return
    if not context.args or len(context.args) < 4:
        await update.message.reply_text("Usage:\n`/tradeitem animal Dragon for 500`\n`/tradeitem weapon bow for 200`", parse_mode="Markdown"); return
    item_type = context.args[0].lower(); raw = context.args[1:]
    try: for_idx = [a.lower() for a in raw].index("for")
    except Exception:
        await update.message.reply_text("❌ Missing 'for'. Example: `/tradeitem animal Dragon for 500`", parse_mode="Markdown"); return
    item_name = " ".join(raw[:for_idx]).strip()
    try: price = int(raw[for_idx + 1])
    except Exception: await update.message.reply_text("❌ Price must be a number."); return
    if price <= 0: await update.message.reply_text("❌ Price must be positive."); return
    target = update.message.reply_to_message.from_user
    if target.id == user.id: await update.message.reply_text("❌ Can't trade with yourself!"); return
    if target.is_bot: await update.message.reply_text("❌ Can't trade with bots!"); return
    data = load_data()
    su = get_user(data, user.id, user.username, user.full_name)
    get_user(data, target.id, target.username, target.full_name)
    if item_type == "animal":
        zoo = su.get("animals", [])
        matched = next((z for z in zoo if item_name.lower() in z["name"].lower()), None)
        if not matched: await update.message.reply_text(f"❌ You don't have '{item_name}'!"); return
        display_name = matched["name"]
    elif item_type == "weapon":
        w_key = next((k for k in WEAPONS if item_name.lower() in WEAPONS[k]["name"].lower()), None)
        if not w_key or su.get("weapon") != w_key: await update.message.reply_text(f"❌ You don't own '{item_name}'!"); return
        if w_key == "stick": await update.message.reply_text("❌ Can't trade the stick!"); return
        display_name = WEAPONS[w_key]["name"]
    else:
        await update.message.reply_text("❌ Type must be `animal` or `weapon`.", parse_mode="Markdown"); return
    sname = _safe_md(f"@{user.username}" if user.username else user.full_name)
    tname = f"@{target.username}" if target.username else _safe_md(target.full_name)
    ti_id = f"ti_{user.id}_{target.id}_{int(datetime.now().timestamp())}"
    data.setdefault("item_trades", {})[ti_id] = {
        "from_id": user.id, "to_id": target.id, "item_type": item_type,
        "item_name": display_name if item_type == "animal" else w_key, "price": price, "status": "pending"}
    save_data(data)
    kb = [[InlineKeyboardButton("✅ Accept", callback_data=f"tiacpt_{ti_id}"),
           InlineKeyboardButton("❌ Decline", callback_data=f"tidecl_{ti_id}")]]
    icon = "🦁" if item_type == "animal" else "🏹"
    await update.message.reply_text(f"{icon} ✦ *Item Trade!* ✦\n┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄\n{sname} offers *{display_name}*\nPrice: *{price:,} 🪙*\n{tname}, buy?",
                                     reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")

@with_data_lock
async def handle_item_trade(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    try:
        await query.answer()
    except (BadRequest, TelegramError):
        pass  # stale/expired callback query — safe to ignore, continue handling
    parts = query.data.split("_", 1); action = parts[0]; ti_id = parts[1]
    data = load_data(); trades = data.get("item_trades", {})
    if ti_id not in trades: await _safe_edit_message_text(query, "❌ Trade expired."); return
    trade = trades[ti_id]
    if trade["status"] != "pending": await _safe_edit_message_text(query, "❌ Already resolved."); return
    if query.from_user.id != trade["to_id"]: await query.answer("❌ Only recipient can respond!", show_alert=True); return
    if action == "tidecl":
        trade["status"] = "declined"; save_data(data); await _safe_edit_message_text(query, "❌ Trade declined."); return
    su = get_user(data, trade["from_id"]); tu = get_user(data, trade["to_id"], query.from_user.username, query.from_user.full_name)
    price = trade["price"]
    if tu.get("coins", 0) < price:
        await _safe_edit_message_text(query, f"❌ Not enough coins! Need *{price:,}* 🪙.", parse_mode="Markdown"); return
    sname = f"@{su.get('username','?')}" if su.get("username") != "Unknown" else _safe_md(su.get("full_name", "?"))
    tname = f"@{tu.get('username','?')}" if tu.get("username") != "Unknown" else _safe_md(tu.get("full_name", "?"))
    if trade["item_type"] == "animal":
        s_zoo = su.get("animals", [])
        matched = next((z for z in s_zoo if trade["item_name"] in z["name"]), None)
        if not matched: await _safe_edit_message_text(query, "❌ Seller no longer has this animal!"); return
        if matched.get("count", 1) > 1: matched["count"] -= 1
        else: s_zoo.remove(matched)
        su["animals"] = s_zoo
        t_zoo = tu.get("animals", [])
        t_found = next((z for z in t_zoo if z["name"] == trade["item_name"]), None)
        if t_found: t_found["count"] = t_found.get("count", 1) + 1
        else:
            a_data = find_animal_data(trade["item_name"])
            t_zoo.append({"name": trade["item_name"], "rarity": a_data["rarity"] if a_data else "common", "count": 1})
        tu["animals"] = t_zoo; item_display = trade["item_name"]
    else:
        w_key = trade["item_name"]
        if su.get("weapon") != w_key: await _safe_edit_message_text(query, "❌ Seller no longer has this weapon!"); return
        su["weapon"] = "stick"; tu["weapon"] = w_key; item_display = WEAPONS[w_key]["name"]
    tu["coins"] = tu.get("coins", 0) - price; su["coins"] = su.get("coins", 0) + price
    su["total_coins_ever"] = su.get("total_coins_ever", 0) + price
    award_badge(su, "trader"); award_badge(tu, "trader"); trade["status"] = "done"; save_data(data)
    await _safe_edit_message_text(query, f"✅ *Trade Done!*\n{tname} bought *{item_display}* from {sname}\n💰 {price} 🪙 transferred",
                                   parse_mode="Markdown")

@with_data_lock
async def cmd_auction(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text(
            "🏷️ ✦ *AUCTION HOUSE* ✦\n┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄\n"
            "`/auction list` — see active listings\n"
            "`/auction sell animal Dragon 200` — list an item\n"
            "`/auction bid <id> <amount>` — place a bid",
            parse_mode="Markdown"); return
    sub = context.args[0].lower(); user = update.message.from_user; chat_id = update.message.chat_id
    data = load_data(); data.setdefault("auctions", {})
    if sub == "list":
        active = {aid: a for aid, a in data.get("auctions", {}).items()
                  if a["status"] == "open" and datetime.fromisoformat(a["expires_at"]) > datetime.now()}
        if not active:
            await update.message.reply_text("🏷️ ✦ *AUCTION HOUSE* ✦\n┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄\n🕳️ No active auctions right now.\n_Use `/auction sell` to list something!_", parse_mode="Markdown"); return
        lines = ["🏷️ ✦ *ACTIVE AUCTIONS* ✦\n┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄"]
        for aid, a in list(active.items())[:10]:
            rem = int((datetime.fromisoformat(a["expires_at"]) - datetime.now()).total_seconds() // 60)
            short_id = aid.split("_")[-1][-6:]
            lines.append(f"🔹 *{a['item_display']}* | Bid: *{a['top_bid']:,} 🪙* | ⏳ {rem}m | ID: `{short_id}`")
        await update.message.reply_text("\n".join(lines), parse_mode="Markdown"); return
    if sub == "sell":
        if len(context.args) < 4:
            await update.message.reply_text("Usage: `/auction sell animal Dragon 200`", parse_mode="Markdown"); return
        item_type = context.args[1].lower()
        try: start_bid = int(context.args[-1])
        except Exception: await update.message.reply_text("❌ Last arg must be starting bid."); return
        item_name_raw = " ".join(context.args[2:-1]).strip()
        u = get_user(data, user.id, user.username, user.full_name)
        if item_type == "animal":
            zoo = u.get("animals", [])
            matched = next((z for z in zoo if item_name_raw.lower() in z["name"].lower()), None)
            if not matched: await update.message.reply_text(f"❌ '{item_name_raw}' not in zoo!"); return
            display_name = matched["name"]
            if matched.get("count", 1) > 1: matched["count"] -= 1
            else: zoo.remove(matched)
            u["animals"] = zoo
        elif item_type == "weapon":
            w_key = next((k for k in WEAPONS if item_name_raw.lower() in WEAPONS[k]["name"].lower()), None)
            if not w_key or u.get("weapon") != w_key: await update.message.reply_text(f"❌ You don't own '{item_name_raw}'!"); return
            if w_key == "stick": await update.message.reply_text("❌ Can't auction the stick!"); return
            display_name = WEAPONS[w_key]["name"]; u["weapon"] = "stick"
        else:
            await update.message.reply_text("❌ Type must be `animal` or `weapon`.", parse_mode="Markdown"); return
        expires_at = (datetime.now() + timedelta(hours=1)).isoformat()
        auction_id = f"auc_{user.id}_{int(datetime.now().timestamp())}"
        sname = _safe_md(f"@{user.username}" if user.username else user.full_name)
        data["auctions"][auction_id] = {
            "seller_id": user.id, "seller_name": sname, "item_type": item_type,
            "item_name": display_name if item_type == "animal" else w_key, "item_display": display_name,
            "start_bid": start_bid, "top_bid": start_bid, "top_bidder_id": None, "top_bidder_name": None,
            "status": "open", "expires_at": expires_at, "chat_id": chat_id}
        save_data(data)
        short_id = auction_id.split("_")[-1][-6:]
        await update.message.reply_text(f"🏷️ ✦ *Auction Listed!* ✦\n┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄\n*{display_name}* | Start: *{start_bid:,} 🪙*\nID: `{short_id}` | ⏳ Ends in 1h",
                                         parse_mode="Markdown")
        context.job_queue.run_once(_close_auction_job, when=3600, name=f"auction_{auction_id}",
                                    data={"auction_id": auction_id})
        return
    if sub == "bid":
        if len(context.args) < 3: await update.message.reply_text("Usage: `/auction bid <id> <amount>`", parse_mode="Markdown"); return
        short_id = context.args[1]
        try: bid_amount = int(context.args[2])
        except Exception: await update.message.reply_text("❌ Bid must be a number."); return
        full_id = next((aid for aid in data.get("auctions", {}) if aid.endswith(short_id)), None)
        if not full_id: await update.message.reply_text("❌ Auction not found!"); return
        auction = data["auctions"][full_id]
        if auction["status"] != "open": await update.message.reply_text("❌ Auction closed!"); return
        if datetime.fromisoformat(auction["expires_at"]) < datetime.now(): await update.message.reply_text("❌ Expired!"); return
        if auction["seller_id"] == user.id: await update.message.reply_text("❌ Can't bid on your own!"); return
        if bid_amount <= auction["top_bid"]: await update.message.reply_text(f"❌ Bid must beat *{auction['top_bid']:,}* 🪙!", parse_mode="Markdown"); return
        u = get_user(data, user.id, user.username, user.full_name)
        if u.get("coins", 0) < bid_amount: await update.message.reply_text("❌ Not enough coins!"); return
        bname = _safe_md(f"@{user.username}" if user.username else user.full_name)
        auction["top_bid"] = bid_amount; auction["top_bidder_id"] = user.id; auction["top_bidder_name"] = bname
        save_data(data)
        await update.message.reply_text(f"✅ *Bid Placed!*\n*{auction['item_display']}* | Your bid: *{bid_amount:,} 🪙*", parse_mode="Markdown")
        return
    await update.message.reply_text("Use: `/auction list` | `/auction sell` | `/auction bid`", parse_mode="Markdown")

@with_data_lock
def _return_animal_to_zoo(user_dict, item_name):
    """FIX: an auctioned animal returning to its owner (no bids / winner
    couldn't pay) used to always be appended as a brand-new zoo entry, so a
    stack of 3 Spade + 1 auctioned-and-returned Spade became "2 Spade" +
    a separate "1 Spade" instead of merging back into "3 Spade". This now
    finds the existing stack (same name) and increments its count, exactly
    like the winner-side merge logic already did."""
    zoo = user_dict.get("animals", [])
    found = next((z for z in zoo if z["name"] == item_name), None)
    if found:
        found["count"] = found.get("count", 1) + 1
    else:
        a_data = find_animal_data(item_name)
        zoo.append({"name": item_name, "rarity": a_data["rarity"] if a_data else "common", "count": 1})
    user_dict["animals"] = zoo

async def _close_auction_job(context: ContextTypes.DEFAULT_TYPE):
    await _close_auction(context, context.job.data["auction_id"])

async def _close_auction(context, auction_id):
    data = load_data(); auctions = data.get("auctions", {})
    if auction_id not in auctions: return
    auction = auctions[auction_id]
    if auction["status"] != "open": return
    auction["status"] = "closed"; chat_id = auction.get("chat_id")
    seller_id = auction["seller_id"]; winner_id = auction.get("top_bidder_id")
    su = get_user(data, seller_id); item_display = auction["item_display"]
    if not winner_id:
        if auction["item_type"] == "animal":
            _return_animal_to_zoo(su, auction["item_name"])
        else: su["weapon"] = auction["item_name"]
        save_data(data)
        try: await context.bot.send_message(chat_id, f"🏷️ Auction ended — no bids.\n*{item_display}* returned to {auction['seller_name']}.", parse_mode="Markdown")
        except Exception: pass
        return
    wu = get_user(data, winner_id); bid = auction["top_bid"]
    if wu.get("coins", 0) < bid:
        if auction["item_type"] == "animal":
            _return_animal_to_zoo(su, auction["item_name"])
        else: su["weapon"] = auction["item_name"]
        save_data(data)
        try: await context.bot.send_message(chat_id, f"🏷️ Auction failed! Winner couldn't pay.\n*{item_display}* returned.", parse_mode="Markdown")
        except Exception: pass
        return
    wu["coins"] = wu.get("coins", 0) - bid; su["coins"] = su.get("coins", 0) + bid
    su["total_coins_ever"] = su.get("total_coins_ever", 0) + bid
    if auction["item_type"] == "animal":
        _return_animal_to_zoo(wu, auction["item_name"])
    else: wu["weapon"] = auction["item_name"]
    save_data(data)
    wname = auction.get("top_bidder_name", "?"); sname = auction.get("seller_name", "?")
    try: await context.bot.send_message(chat_id, f"🏷️ *Auction Closed!*\n*{item_display}* → *{wname}* for *{bid} 🪙*\n{sname} received coins!", parse_mode="Markdown")
    except Exception: pass

@with_data_lock
async def cmd_pray(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user; data = load_data()
    u = get_user(data, user.id, user.username, user.full_name)
    last_pray = u.get("last_pray")
    if last_pray:
        elapsed = (datetime.now() - datetime.fromisoformat(last_pray)).total_seconds()
        if elapsed < 1800:
            remaining = int(1800 - elapsed)
            await update.message.reply_text(f"🙏 Already prayed! Next in *{remaining//60}m {remaining%60}s*.", parse_mode="Markdown"); return
    u["pray_active"] = True; u["pray_expires"] = (datetime.now() + timedelta(minutes=10)).isoformat()
    u["last_pray"] = datetime.now().isoformat()
    save_data(data)
    name = _safe_md(f"@{user.username}" if user.username else user.full_name)
    PRAY_MSGS = ["🙏 The gods hear your prayer...\nLuck boosted for 10 minutes!",
                 "✨ Divine blessing! Gambling odds improved for 10 minutes!",
                 "🌟 The universe aligns! 10 minutes of boosted luck!",
                 "🕊️ Forge gods grant you luck for 10 minutes!"]
    await update.message.reply_text(f"{random.choice(PRAY_MSGS)}\n\n_{name}'s next 10 min gambling: +15% boost!_", parse_mode="Markdown")

# ══════════════════════════════════════════════════════════════════════════════
#  LEADERBOARD — 6 categories, fresh-fetch on every tap
# ══════════════════════════════════════════════════════════════════════════════
def _safe_md(t):
    """Strip Markdown special chars from user-provided strings to prevent parse errors."""
    return str(t).replace("*","").replace("_","").replace("`","").replace("[","").replace("]","").replace("~","").replace(">","")

def _lb_board(title, cursor, val_key, val_icon, cnt_key, cnt_icon):
    lines = [f"{title}\n{DIV}"]
    for i, doc in enumerate(cursor):
        if i >= len(LB_MEDALS):
            break
        name = _safe_md(doc.get("full_name", "?"))
        tag  = f" 👑{_safe_md(doc['title'])}" if doc.get("title") else ""
        val  = doc.get(val_key, 0)
        cnt  = doc.get(cnt_key, 0)
        lines.append(f"{LB_MEDALS[i]} {name}{tag}\n   {val_icon}{val:,} | {cnt_icon}{cnt:,}")
    if len(lines) == 1:
        lines.append("_No players yet!_")
    return "\n".join(lines)

LB_MEDALS = ["🥇","🥈","🥉","4️⃣","5️⃣","6️⃣","7️⃣","8️⃣","9️⃣","🔟"]

def build_leaderboard_text(kind: str) -> str:
    db        = _get_db()
    today_str = datetime.now().date().isoformat()

    if kind == "lb_global":
        return _lb_board(
            "🟣 🌍 *GLOBAL — Richest Ever*",
            db["users"].find({"total_coins_ever": {"$gt": 0}}).sort("total_coins_ever", -1).limit(10),
            "total_coins_ever", "🪙 ", "wins", "🏆 "
        )
    if kind == "lb_gems":
        return _lb_board(
            "🟣 💎 *GEM KINGS*",
            db["users"].find({"gems": {"$gt": 0}}).sort("gems", -1).limit(10),
            "gems", "💎 ", "hunts", "🎯 "
        )
    if kind == "lb_today":
        return _lb_board(
            "🟣 🕐 *TODAY'S CHAMPIONS*",
            db["users"].find({"today_date": today_str, "today_wins": {"$gt": 0}})
                       .sort("today_wins", -1).limit(10),
            "coins", "🪙 ", "today_wins", "🏆 "
        )
    if kind == "lb_hunters":
        return _lb_board(
            "🟣 🎯 *TOP HUNTERS*",
            db["users"].find({"hunts": {"$gt": 0}}).sort("hunts", -1).limit(10),
            "coins", "🪙 ", "hunts", "🎯 "
        )
    if kind == "lb_pvp":
        return _lb_board(
            "🟣 ⚔️ *PVP CHAMPIONS*",
            db["users"].find({"pvp_wins": {"$gt": 0}}).sort("pvp_wins", -1).limit(10),
            "coins", "🪙 ", "pvp_wins", "⚔️ "
        )
    if kind == "lb_casino":
        return _lb_board(
            "🟣 🎰 *CASINO HIGH ROLLERS*",
            db["users"].find({"casino_total_won": {"$gt": 0}}).sort("casino_total_won", -1).limit(10),
            "casino_total_won", "🪙 ", "casino_wins", "🎰 "
        )
    if kind == "lb_referrals":
        return _lb_board(
            "🟣 🤝 *TOP RECRUITERS*",
            db["users"].find({"referral_count": {"$gt": 0}}).sort("referral_count", -1).limit(10),
            "referral_coins_earned", "🪙 ", "referral_count", "🤝 "
        )
    return "_No data!_"

def _lb_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🌍 Global",  callback_data="lb_global"),
         InlineKeyboardButton("💎 Gems",    callback_data="lb_gems")],
        [InlineKeyboardButton("🕐 Today",   callback_data="lb_today"),
         InlineKeyboardButton("🎯 Hunters", callback_data="lb_hunters")],
        [InlineKeyboardButton("⚔️ PVP",     callback_data="lb_pvp"),
         InlineKeyboardButton("🎰 Casino",  callback_data="lb_casino")],
        [InlineKeyboardButton("🤝 Referrals", callback_data="lb_referrals")],
    ])

async def cmd_leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        text = build_leaderboard_text("lb_global")
        await update.message.reply_text(text, reply_markup=_lb_keyboard(), parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Leaderboard load error: {e}")
        await update.message.reply_text("⚠️ Leaderboard error, try again in a sec!")

async def handle_leaderboard_tab(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    try:
        await query.answer()
    except (BadRequest, TelegramError):
        pass  # stale/expired callback query — safe to ignore, continue handling
    try:
        text = build_leaderboard_text(query.data)
        await query.edit_message_text(text, reply_markup=_lb_keyboard(), parse_mode="Markdown")
    except Exception as e:
        logger.warning(f"Leaderboard tab error: {e}")
        # Fallback: try without markdown
        try:
            text = build_leaderboard_text(query.data)
            plain = text.replace("*", "").replace("_", "").replace("`", "")
            await query.edit_message_text(plain, reply_markup=_lb_keyboard())
        except Exception:
            pass
# ══════════════════════════════════════════════════════════════════════════════
#  WELCOMER / BYE
# ══════════════════════════════════════════════════════════════════════════════
DEFAULT_WELCOME = "👋 Welcome to the group, {name}! 🎉\nType /start to begin your adventure with Aira!"
DEFAULT_BYE     = "👋 Goodbye {name}, we'll miss you! 💙"

async def handle_member_update(update: Update, context: ContextTypes.DEFAULT_TYPE):
    result = update.chat_member
    if not result: return
    chat_id = result.chat.id
    old_stat = result.old_chat_member.status
    new_stat = result.new_chat_member.status
    member = result.new_chat_member.user
    name = f"@{member.username}" if member.username else _safe_md(member.full_name)
    group = get_group_db(chat_id)
    if old_stat in ("left", "kicked") and new_stat in ("member", "restricted"):
        msg = (group.get("welcome_msg") or DEFAULT_WELCOME).replace("{name}", name).replace("{username}", name)
        try: await context.bot.send_message(chat_id, msg, parse_mode="Markdown")
        except TelegramError: pass
    elif old_stat in ("member", "restricted", "administrator") and new_stat in ("left", "kicked"):
        msg = (group.get("bye_msg") or DEFAULT_BYE).replace("{name}", name).replace("{username}", name)
        try: await context.bot.send_message(chat_id, msg, parse_mode="Markdown")
        except TelegramError: pass

async def cmd_setwelcome(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    if not await is_admin(context.bot, chat_id, update.message.from_user.id):
        await update.message.reply_text("🚫 *Admins only!* This command needs admin rights.", parse_mode="Markdown"); return
    if not context.args:
        await update.message.reply_text("Usage: `/setwelcome Welcome {name} to our group!`", parse_mode="Markdown"); return
    msg = " ".join(context.args); group = get_group_db(chat_id)
    group["welcome_msg"] = msg; save_group_db(chat_id, group)
    await update.message.reply_text(f"✅ Welcome message set!\nPreview: {msg.replace('{name}','[User]')}", parse_mode="Markdown")

async def cmd_setbye(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    if not await is_admin(context.bot, chat_id, update.message.from_user.id):
        await update.message.reply_text("🚫 *Admins only!* This command needs admin rights.", parse_mode="Markdown"); return
    if not context.args:
        await update.message.reply_text("Usage: `/setbye Bye {name}!`", parse_mode="Markdown"); return
    msg = " ".join(context.args); group = get_group_db(chat_id)
    group["bye_msg"] = msg; save_group_db(chat_id, group)
    await update.message.reply_text(f"✅ Bye message set!\nPreview: {msg.replace('{name}','[User]')}", parse_mode="Markdown")

# ══════════════════════════════════════════════════════════════════════════════
#  MODERATION — original 9 + 15 NEW = 24 total
# ══════════════════════════════════════════════════════════════════════════════
async def cmd_ban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    if not await is_admin(context.bot, chat_id, update.message.from_user.id): await update.message.reply_text("🚫 *Admins only!* This command needs admin rights.", parse_mode="Markdown"); return
    target, err = await get_target(update, context)
    if err: await update.message.reply_text(err); return
    if _is_approved(chat_id, target.id):
        await update.message.reply_text("🛡️ This user is *approved* — immune to moderation. `/unapprove` them first.", parse_mode="Markdown"); return
    reason = " ".join(context.args) if context.args else "No reason given"
    if await _confirm_if_target_is_admin(update, context, target, "ban", extra={"reason": reason}):
        return
    try:
        await context.bot.ban_chat_member(chat_id, target.id)
        name = f"@{target.username}" if target.username else _safe_md(target.full_name)
        await update.message.reply_text(f"🔨 *{name}* banned.\nReason: _{reason}_", parse_mode="Markdown")
    except TelegramError as e: await update.message.reply_text(f"❌ _{e}_", parse_mode="Markdown")

async def cmd_unban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    if not await is_admin(context.bot, chat_id, update.message.from_user.id): await update.message.reply_text("🚫 *Admins only!* This command needs admin rights.", parse_mode="Markdown"); return
    target, err = await get_target(update, context)
    if err: await update.message.reply_text(err); return
    try:
        await context.bot.unban_chat_member(chat_id, target.id, only_if_banned=True)
        name = f"@{target.username}" if target.username else _safe_md(target.full_name)
        await update.message.reply_text(f"✅ *{name}* unbanned!", parse_mode="Markdown")
    except TelegramError as e: await update.message.reply_text(f"❌ _{e}_", parse_mode="Markdown")

async def cmd_kick(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    if not await is_admin(context.bot, chat_id, update.message.from_user.id): await update.message.reply_text("🚫 *Admins only!* This command needs admin rights.", parse_mode="Markdown"); return
    target, err = await get_target(update, context)
    if err: await update.message.reply_text(err); return
    if _is_approved(chat_id, target.id):
        await update.message.reply_text("🛡️ This user is *approved* — immune to moderation. `/unapprove` them first.", parse_mode="Markdown"); return
    reason = " ".join(context.args) if context.args else "No reason given"
    if await _confirm_if_target_is_admin(update, context, target, "kick", extra={"reason": reason}):
        return
    try:
        await context.bot.ban_chat_member(chat_id, target.id)
        await context.bot.unban_chat_member(chat_id, target.id)
        name = f"@{target.username}" if target.username else _safe_md(target.full_name)
        await update.message.reply_text(f"👢 *{name}* kicked.\nReason: _{reason}_", parse_mode="Markdown")
    except TelegramError as e: await update.message.reply_text(f"❌ _{e}_", parse_mode="Markdown")

@with_data_lock
async def cmd_timeout(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    if not await is_admin(context.bot, chat_id, update.message.from_user.id): await update.message.reply_text("🚫 *Admins only!* This command needs admin rights.", parse_mode="Markdown"); return
    target, err = await get_target(update, context)
    if err: await update.message.reply_text(err); return
    if _is_approved(chat_id, target.id):
        await update.message.reply_text("🛡️ This user is *approved* — immune to moderation. `/unapprove` them first.", parse_mode="Markdown"); return
    data = load_data(); tu = data["users"].get(str(target.id))
    if tu and has_shield(tu):
        tname = f"@{target.username}" if target.username else _safe_md(target.full_name)
        await update.message.reply_text(f"🛡️ *{tname}* has a shield!", parse_mode="Markdown"); return
    mins = 5
    if context.args:
        try: mins = max(1, min(int(context.args[-1]), 1440))
        except Exception: pass
    if await _confirm_if_target_is_admin(update, context, target, "timeout", extra={"mins": mins}):
        return
    until = datetime.now() + timedelta(minutes=mins)
    try:
        await context.bot.restrict_chat_member(chat_id, target.id, permissions=ChatPermissions(can_send_messages=False), until_date=until)
        name = f"@{target.username}" if target.username else _safe_md(target.full_name)
        await update.message.reply_text(f"🔇 *{name}* muted for *{mins}m*.", parse_mode="Markdown")
    except TelegramError as e: await update.message.reply_text(f"❌ _{e}_", parse_mode="Markdown")

async def cmd_untimeout(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    if not await is_admin(context.bot, chat_id, update.message.from_user.id): await update.message.reply_text("🚫 *Admins only!* This command needs admin rights.", parse_mode="Markdown"); return
    target, err = await get_target(update, context)
    if err: await update.message.reply_text(err); return
    try:
        await context.bot.restrict_chat_member(chat_id, target.id, permissions=ChatPermissions(
            can_send_messages=True, can_send_photos=True, can_send_videos=True, can_send_polls=True,
            can_send_other_messages=True, can_add_web_page_previews=True, can_change_info=False,
            can_invite_users=True, can_pin_messages=False))
        name = f"@{target.username}" if target.username else _safe_md(target.full_name)
        await update.message.reply_text(f"🔊 *{name}* unmuted!", parse_mode="Markdown")
    except TelegramError as e: await update.message.reply_text(f"❌ _{e}_", parse_mode="Markdown")

async def cmd_purge(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    if not await is_admin(context.bot, chat_id, update.message.from_user.id): await update.message.reply_text("🚫 *Admins only!* This command needs admin rights.", parse_mode="Markdown"); return
    n = 10
    if context.args:
        try: n = max(1, min(int(context.args[0]), 100))
        except Exception: pass
    msg_id = update.message.message_id; deleted = 0
    for i in range(msg_id, msg_id - n - 2, -1):
        try: await context.bot.delete_message(chat_id, i); deleted += 1
        except Exception: pass
    try:
        note = await context.bot.send_message(chat_id, f"🗑️ Purged *{deleted}* messages.", parse_mode="Markdown")
        await asyncio.sleep(3); await context.bot.delete_message(chat_id, note.message_id)
    except Exception: pass

async def cmd_warn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    if not await is_admin(context.bot, chat_id, update.message.from_user.id): await update.message.reply_text("🚫 *Admins only!* This command needs admin rights.", parse_mode="Markdown"); return
    target, err = await get_target(update, context)
    if err: await update.message.reply_text(err); return
    if _is_approved(chat_id, target.id):
        await update.message.reply_text("🛡️ This user is *approved* — immune to moderation. `/unapprove` them first.", parse_mode="Markdown"); return
    if await _confirm_if_target_is_admin(update, context, target, "warn"):
        return
    group = get_group_db(chat_id); uid = str(target.id)
    group["warns"][uid] = group["warns"].get(uid, 0) + 1
    count = group["warns"][uid]; save_group_db(chat_id, group)
    name = f"@{target.username}" if target.username else _safe_md(target.full_name)
    if count >= 3:
        try:
            await context.bot.ban_chat_member(chat_id, target.id)
            await update.message.reply_text(f"⚠️ *{name}* warn {count}/3 → 🔨 *{fancy('BANNED!')}*", parse_mode="Markdown")
            group["warns"][uid] = 0; save_group_db(chat_id, group)
        except TelegramError as e:
            await update.message.reply_text(f"⚠️ Warn {count}/3 (ban failed: _{e}_)", parse_mode="Markdown")
    else:
        await update.message.reply_text(f"⚠️ *{name}* warned *{count}/3*.", parse_mode="Markdown")

async def cmd_warns(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id; target, err = await get_target(update, context)
    if err: await update.message.reply_text(err); return
    group = get_group_db(chat_id); count = group["warns"].get(str(target.id), 0)
    name = f"@{target.username}" if target.username else _safe_md(target.full_name)
    await update.message.reply_text(f"⚠️ *{name}* has *{count}/3* warnings.", parse_mode="Markdown")

async def cmd_clearwarns(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    if not await is_admin(context.bot, chat_id, update.message.from_user.id): await update.message.reply_text("🚫 *Admins only!* This command needs admin rights.", parse_mode="Markdown"); return
    target, err = await get_target(update, context)
    if err: await update.message.reply_text(err); return
    group = get_group_db(chat_id); group["warns"][str(target.id)] = 0; save_group_db(chat_id, group)
    name = f"@{target.username}" if target.username else _safe_md(target.full_name)
    await update.message.reply_text(f"✅ Cleared warns for *{name}*.", parse_mode="Markdown")

# ---- 15 NEW moderation commands ---------------------------------------------
async def cmd_slowmode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    if not await is_admin(context.bot, chat_id, update.message.from_user.id): await update.message.reply_text("🚫 *Admins only!* This command needs admin rights.", parse_mode="Markdown"); return
    if not context.args: await update.message.reply_text("Usage: `/slowmode <seconds>` (0 to disable)", parse_mode="Markdown"); return
    try: secs = max(0, min(int(context.args[0]), 21600))
    except Exception: await update.message.reply_text("❌ Number of seconds only."); return
    try:
        await context.bot.set_chat_slow_mode_delay(chat_id, secs)
        await update.message.reply_text(f"🐢 Slow mode set to *{secs}s*." if secs else "🐇 Slow mode disabled.", parse_mode="Markdown")
    except TelegramError as e: await update.message.reply_text(f"❌ _{e}_", parse_mode="Markdown")

async def cmd_lock(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    if not await is_admin(context.bot, chat_id, update.message.from_user.id): await update.message.reply_text("🚫 *Admins only!* This command needs admin rights.", parse_mode="Markdown"); return
    try:
        await context.bot.set_chat_permissions(chat_id, ChatPermissions(can_send_messages=False))
        group = get_group_db(chat_id); group["locked"] = True; save_group_db(chat_id, group)
        await update.message.reply_text("🔒 *Group locked!* Only admins can send messages.", parse_mode="Markdown")
    except TelegramError as e: await update.message.reply_text(f"❌ _{e}_", parse_mode="Markdown")

async def cmd_unlock(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    if not await is_admin(context.bot, chat_id, update.message.from_user.id): await update.message.reply_text("🚫 *Admins only!* This command needs admin rights.", parse_mode="Markdown"); return
    try:
        await context.bot.set_chat_permissions(chat_id, ChatPermissions(
            can_send_messages=True, can_send_photos=True, can_send_videos=True, can_send_polls=True,
            can_send_other_messages=True, can_add_web_page_previews=True, can_invite_users=True))
        group = get_group_db(chat_id); group["locked"] = False; save_group_db(chat_id, group)
        await update.message.reply_text("🔓 *Group unlocked!* Everyone can chat again.", parse_mode="Markdown")
    except TelegramError as e: await update.message.reply_text(f"❌ _{e}_", parse_mode="Markdown")

async def cmd_promote(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    if not await is_admin(context.bot, chat_id, update.message.from_user.id): await update.message.reply_text("🚫 *Admins only!* This command needs admin rights.", parse_mode="Markdown"); return
    target, err = await get_target(update, context)
    if err: await update.message.reply_text(err); return
    try:
        await context.bot.promote_chat_member(chat_id, target.id, can_delete_messages=True, can_restrict_members=True,
            can_pin_messages=True, can_invite_users=True, can_manage_chat=True)
        name = f"@{target.username}" if target.username else _safe_md(target.full_name)
        await update.message.reply_text(f"⬆️ *{name}* promoted to admin!", parse_mode="Markdown")
    except TelegramError as e: await update.message.reply_text(f"❌ _{e}_", parse_mode="Markdown")

async def cmd_demote(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    if not await is_admin(context.bot, chat_id, update.message.from_user.id): await update.message.reply_text("🚫 *Admins only!* This command needs admin rights.", parse_mode="Markdown"); return
    target, err = await get_target(update, context)
    if err: await update.message.reply_text(err); return
    try:
        await context.bot.promote_chat_member(chat_id, target.id, can_delete_messages=False, can_restrict_members=False,
            can_pin_messages=False, can_invite_users=False, can_manage_chat=False, can_promote_members=False,
            can_change_info=False, can_manage_video_chats=False)
        name = f"@{target.username}" if target.username else _safe_md(target.full_name)
        await update.message.reply_text(f"⬇️ *{name}* demoted.", parse_mode="Markdown")
    except TelegramError as e: await update.message.reply_text(f"❌ _{e}_", parse_mode="Markdown")

async def cmd_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    if not update.message.reply_to_message:
        await update.message.reply_text("↩️ Reply to the message you want to report + `/report <reason>`"); return
    reason = " ".join(context.args) if context.args else "No reason given"
    reported = update.message.reply_to_message.from_user
    reporter = update.message.from_user
    try:
        admins = await context.bot.get_chat_administrators(chat_id)
        mentions = " ".join(f"[​](tg://user?id={a.user.id})" for a in admins if not a.user.is_bot)
        rname = f"@{reported.username}" if reported.username else _safe_md(reported.full_name)
        repname = f"@{reporter.username}" if reporter.username else _safe_md(reporter.full_name)
        await update.message.reply_text(
            f"🚨 *Report filed!*{mentions}\nBy: {repname}\nAgainst: {rname}\nReason: _{reason}_",
            parse_mode="Markdown")
    except TelegramError as e: await update.message.reply_text(f"❌ _{e}_", parse_mode="Markdown")

async def cmd_adminlist(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    try:
        admins = await context.bot.get_chat_administrators(chat_id)
        lines = ["🛡️ ✦ *Group Admins* ✦\n┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄"]
        for a in admins:
            u = a.user
            role = "👑 Creator" if a.status == "creator" else "⭐ Admin"
            name = f"@{u.username}" if u.username else _safe_md(u.full_name)
            lines.append(f"{role}: {name}")
        await update.message.reply_text("\n".join(lines), parse_mode="Markdown")
    except TelegramError as e: await update.message.reply_text(f"❌ _{e}_", parse_mode="Markdown")

async def cmd_userinfo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    target = update.message.reply_to_message.from_user if update.message.reply_to_message else update.message.from_user
    chat_id = update.message.chat_id
    u = get_user_fast(str(target.id))
    try:
        member = await context.bot.get_chat_member(chat_id, target.id)
        status = member.status
    except TelegramError:
        status = "unknown"
    name = f"@{target.username}" if target.username else _safe_md(target.full_name)
    await update.message.reply_text(
        f"👤 ✦ *User Info* ✦\n┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄\n"
        f"Name: {_safe_md(target.full_name)}\nUsername: {name}\nID: `{target.id}`\nStatus: *{status}*\n\n"
        f"🪙 Coins: *{u.get('coins',0):,}* | 🏆 Wins: *{u.get('wins',0)}*\n"
        f"⚠️ Warns: *{get_group_db(chat_id)['warns'].get(str(target.id),0)}/3*",
        parse_mode="Markdown")

async def cmd_rules(update: Update, context: ContextTypes.DEFAULT_TYPE):
    group = get_group_db(update.message.chat_id)
    rules = group.get("rules")
    if not rules:
        await update.message.reply_text("📜 No rules set yet! Admins can use `/setrules <text>`.", parse_mode="Markdown"); return
    await update.message.reply_text(f"📜 ✦ *Group Rules* ✦\n┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄\n{rules}", parse_mode="Markdown")

async def cmd_setrules(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    if not await is_admin(context.bot, chat_id, update.message.from_user.id): await update.message.reply_text("🚫 *Admins only!* This command needs admin rights.", parse_mode="Markdown"); return
    if not context.args: await update.message.reply_text("Usage: `/setrules <rules text>`", parse_mode="Markdown"); return
    group = get_group_db(chat_id); group["rules"] = " ".join(context.args); save_group_db(chat_id, group)
    await update.message.reply_text("✅ Rules updated! Use /rules to view.", parse_mode="Markdown")

async def cmd_antispam(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    if not await is_admin(context.bot, chat_id, update.message.from_user.id): await update.message.reply_text("🚫 *Admins only!* This command needs admin rights.", parse_mode="Markdown"); return
    if not context.args or context.args[0].lower() not in ("on", "off"):
        await update.message.reply_text("Usage: `/antispam on` or `/antispam off`", parse_mode="Markdown"); return
    group = get_group_db(chat_id); group["antispam"] = context.args[0].lower() == "on"; save_group_db(chat_id, group)
    await update.message.reply_text(f"🛡️ Anti-spam {'enabled' if group['antispam'] else 'disabled'}.", parse_mode="Markdown")

async def cmd_tempban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    if not await is_admin(context.bot, chat_id, update.message.from_user.id): await update.message.reply_text("🚫 *Admins only!* This command needs admin rights.", parse_mode="Markdown"); return
    target, err = await get_target(update, context)
    if err: await update.message.reply_text(err); return
    if _is_approved(chat_id, target.id):
        await update.message.reply_text("🛡️ This user is *approved* — immune to moderation. `/unapprove` them first.", parse_mode="Markdown"); return
    if not context.args: await update.message.reply_text("Usage: reply + `/tempban <minutes>`", parse_mode="Markdown"); return
    try: mins = max(1, min(int(context.args[0]), 44640))
    except Exception: await update.message.reply_text("❌ Minutes must be a number."); return
    if await _confirm_if_target_is_admin(update, context, target, "tempban", extra={"mins": mins}):
        return
    until = datetime.now() + timedelta(minutes=mins)
    try:
        await context.bot.ban_chat_member(chat_id, target.id, until_date=until)
        name = f"@{target.username}" if target.username else _safe_md(target.full_name)
        await update.message.reply_text(f"⏳ *{name}* temp-banned for *{mins}m*.", parse_mode="Markdown")
    except TelegramError as e: await update.message.reply_text(f"❌ _{e}_", parse_mode="Markdown")

async def cmd_approve(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    if not await is_admin(context.bot, chat_id, update.message.from_user.id):
        await update.message.reply_text("🚫 *Admins only!* This command needs admin rights.", parse_mode="Markdown"); return
    target, err = await get_target(update, context)
    if err: await update.message.reply_text(err); return
    group = get_group_db(chat_id)
    if target.id in group["approved_ids"]:
        await update.message.reply_text("Already approved."); return
    group["approved_ids"].append(target.id)
    save_group_db(chat_id, group)
    name = f"@{target.username}" if target.username else _safe_md(target.full_name)
    await update.message.reply_text(
        f"✅ *{name}* is now *approved* — immune to `/ban`, `/kick`, `/timeout`, `/warn`, `/tempban` and anti-spam in this group.",
        parse_mode="Markdown")

async def cmd_unapprove(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    if not await is_admin(context.bot, chat_id, update.message.from_user.id):
        await update.message.reply_text("🚫 *Admins only!* This command needs admin rights.", parse_mode="Markdown"); return
    target, err = await get_target(update, context)
    if err: await update.message.reply_text(err); return
    group = get_group_db(chat_id)
    if target.id not in group["approved_ids"]:
        await update.message.reply_text("This user wasn't approved."); return
    group["approved_ids"].remove(target.id)
    save_group_db(chat_id, group)
    name = f"@{target.username}" if target.username else _safe_md(target.full_name)
    await update.message.reply_text(f"❌ *{name}* is no longer approved — normal moderation applies again.", parse_mode="Markdown")

async def cmd_approvedlist(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    group = get_group_db(chat_id)
    ids = group.get("approved_ids", [])
    if not ids:
        await update.message.reply_text("No approved users in this group yet. Reply to someone with `/approve`.", parse_mode="Markdown"); return
    lines = ["🛡️ *Approved users (immune to moderation):*"]
    for uid in ids:
        try:
            m = await context.bot.get_chat_member(chat_id, uid)
            n = f"@{m.user.username}" if m.user.username else m.user.full_name
        except Exception:
            n = f"`{uid}`"
        lines.append(f"✧ {_safe_md(n)}")
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")

async def cmd_unpin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    if not await is_admin(context.bot, chat_id, update.message.from_user.id): await update.message.reply_text("🚫 *Admins only!* This command needs admin rights.", parse_mode="Markdown"); return
    try:
        await context.bot.unpin_chat_message(chat_id)
        await update.message.reply_text("📌 Unpinned the pinned message.")
    except TelegramError as e: await update.message.reply_text(f"❌ _{e}_", parse_mode="Markdown")

async def cmd_cleanbot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    if not await is_admin(context.bot, chat_id, update.message.from_user.id): await update.message.reply_text("🚫 *Admins only!* This command needs admin rights.", parse_mode="Markdown"); return
    n = 30
    if context.args:
        try: n = max(1, min(int(context.args[0]), 100))
        except Exception: pass
    msg_id = update.message.message_id; me = await context.bot.get_me(); deleted = 0
    for i in range(msg_id, msg_id - n - 2, -1):
        try:
            await context.bot.delete_message(chat_id, i)  # bot can only actually delete its own w/o admin rights, but with admin rights this cleans all near-range
            deleted += 1
        except Exception: pass
    try:
        note = await context.bot.send_message(chat_id, f"🧹 Cleanup pass done ({deleted} attempted).")
        await asyncio.sleep(2); await context.bot.delete_message(chat_id, note.message_id)
    except Exception: pass

async def cmd_announce(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    if not await is_admin(context.bot, chat_id, update.message.from_user.id): await update.message.reply_text("🚫 *Admins only!* This command needs admin rights.", parse_mode="Markdown"); return
    if not context.args: await update.message.reply_text("Usage: `/announce <message>`", parse_mode="Markdown"); return
    msg = " ".join(context.args)
    await update.message.reply_text(f"📢 ✦ *{fancy('ANNOUNCEMENT')}* ✦\n┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄\n{msg}", parse_mode="Markdown")

# ══════════════════════════════════════════════════════════════════════════════
#  NEW MINI-GAME #1 — TIC TAC TOE
# ══════════════════════════════════════════════════════════════════════════════
_ttt_games = {}  # message_id -> {board, players:{X:uid,O:uid}, names:{}, turn}

# In a DM there's only one real player, so /ttt and /wordchain let Aira fill
# in as the second player instead of refusing to start. This sentinel "user
# id" stands in for her wherever a real Telegram user id would normally go.
_AIRA_BOT_UID = 0

def _ttt_render(board):
    kb = []
    for r in range(3):
        row = []
        for c in range(3):
            i = r * 3 + c
            label = board[i] if board[i] != " " else "・"
            row.append(InlineKeyboardButton(label, callback_data=f"ttt_{i}"))
        kb.append(row)
    return InlineKeyboardMarkup(kb)

def _ttt_winner(board):
    lines = [(0,1,2),(3,4,5),(6,7,8),(0,3,6),(1,4,7),(2,5,8),(0,4,8),(2,4,6)]
    for a,b,c in lines:
        if board[a] != " " and board[a] == board[b] == board[c]:
            return board[a]
    if " " not in board: return "draw"
    return None

def _ttt_bot_move(board, bot_mark, human_mark):
    """Picks Aira's move. Tactically aware (takes wins, blocks losses) but
    deliberately imperfect — an average player, not an unbeatable one."""
    empties = [i for i, v in enumerate(board) if v == " "]
    if not empties:
        return None
    for i in empties:  # take a winning move most of the time, not always
        b2 = board[:]; b2[i] = bot_mark
        if _ttt_winner(b2) == bot_mark and random.random() < 0.85:
            return i
    for i in empties:  # block the human's winning move most of the time
        b2 = board[:]; b2[i] = human_mark
        if _ttt_winner(b2) == human_mark and random.random() < 0.75:
            return i
    if 4 in empties and random.random() < 0.6:
        return 4
    corners = [c for c in (0, 2, 6, 8) if c in empties]
    if corners and random.random() < 0.5:
        return random.choice(corners)
    return random.choice(empties)

async def cmd_ttt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    p1 = update.message.from_user
    if context.args and context.args[0].lower() == "howto":
        await update.message.reply_text(_game_howto("ttt"), parse_mode="Markdown"); return
    is_dm = update.message.chat.type == "private"
    if not update.message.reply_to_message:
        if is_dm:
            # No second player available in a DM — Aira steps in as ⭕.
            board = [" "] * 9
            p1n = _safe_md(f"@{p1.username}" if p1.username else p1.full_name)
            msg = await update.message.reply_text(
                f"🎮 *Tic-Tac-Toe!*\n❌ {p1n} vs ⭕ Aira 🤖\n\nTurn: ❌ {p1n}",
                reply_markup=_ttt_render(board), parse_mode="Markdown")
            _ttt_games[msg.message_id] = {
                "board": board, "players": {"X": p1.id, "O": _AIRA_BOT_UID},
                "names": {p1.id: p1n, _AIRA_BOT_UID: "Aira 🤖"}, "turn": "X", "vs_bot": True}
            return
        await update.message.reply_text("↩️ Reply to someone with `/ttt` to challenge them to Tic-Tac-Toe!"); return
    p2 = update.message.reply_to_message.from_user
    if p2.id == p1.id: await update.message.reply_text("❌ Can't play yourself!"); return
    if p2.is_bot: await update.message.reply_text("❌ Can't play a bot!"); return
    board = [" "] * 9
    p1n = _safe_md(f"@{p1.username}" if p1.username else p1.full_name)
    p2n = _safe_md(f"@{p2.username}" if p2.username else p2.full_name)
    msg = await update.message.reply_text(
        f"🎮 *Tic-Tac-Toe!*\n❌ {p1n} vs ⭕ {p2n}\n\nTurn: ❌ {p1n}",
        reply_markup=_ttt_render(board), parse_mode="Markdown")
    _ttt_games[msg.message_id] = {"board": board, "players": {"X": p1.id, "O": p2.id},
                                   "names": {p1.id: p1n, p2.id: p2n}, "turn": "X"}

def _ttt_win_text(game, winner_id):
    if winner_id == _AIRA_BOT_UID:
        return f"🎮 *Tic-Tac-Toe* — {game['names'][winner_id]} *{fancy('WINS!')}* 🏆 Better luck next time!"
    data = load_data()
    wu = get_user(data, winner_id)
    wu["wins"] = wu.get("wins", 0) + 1
    wu["ttt_wins"] = wu.get("ttt_wins", 0) + 1
    wu["coins"] = wu.get("coins", 0) + 20
    b = award_badge(wu, "ttt_win")
    save_data(data)
    return f"🎮 *Tic-Tac-Toe* — {game['names'][winner_id]} *{fancy('WINS!')}* 🏆 (+20 🪙)" + (f"\n\n{b}" if b else "")

async def _ttt_finish_or_continue(query, game):
    """Call right after ANY mark (human or Aira's) is placed. Handles a
    win/draw if the game just ended; otherwise flips the turn and, in solo
    vs_bot mode, immediately plays Aira's move too before rendering."""
    result = _ttt_winner(game["board"])
    if result:
        text = "🎮 *Tic-Tac-Toe* — It's a *DRAW!* 🤝" if result == "draw" else _ttt_win_text(game, game["players"][result])
        await _safe_edit_message_text(query, text, reply_markup=_ttt_render(game["board"]), parse_mode="Markdown")
        _ttt_games.pop(query.message.message_id, None)
        return

    game["turn"] = "O" if game["turn"] == "X" else "X"

    if game.get("vs_bot") and game["players"][game["turn"]] == _AIRA_BOT_UID:
        move = _ttt_bot_move(game["board"], "O", "X")
        if move is not None:
            game["board"][move] = "O"
        result2 = _ttt_winner(game["board"])
        if result2:
            text = "🎮 *Tic-Tac-Toe* — It's a *DRAW!* 🤝" if result2 == "draw" else _ttt_win_text(game, game["players"][result2])
            await _safe_edit_message_text(query, text, reply_markup=_ttt_render(game["board"]), parse_mode="Markdown")
            _ttt_games.pop(query.message.message_id, None)
            return
        game["turn"] = "X"

    next_name = game["names"][game["players"][game["turn"]]]
    await _safe_edit_message_text(query, 
        f"🎮 *Tic-Tac-Toe!*\nTurn: {'❌' if game['turn']=='X' else '⭕'} {next_name}",
        reply_markup=_ttt_render(game["board"]), parse_mode="Markdown")

@with_data_lock
async def handle_ttt_move(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    game = _ttt_games.get(query.message.message_id)
    if not game: await query.answer("Game expired!", show_alert=True); return
    idx = int(query.data.replace("ttt_", ""))
    turn = game["turn"]
    if query.from_user.id != game["players"][turn]:
        await query.answer("Not your turn!", show_alert=True); return
    if game["board"][idx] != " ":
        await query.answer("Taken!", show_alert=True); return
    try:
        await query.answer()
    except (BadRequest, TelegramError):
        pass  # stale/expired callback query — safe to ignore, continue handling
    game["board"][idx] = turn
    await _ttt_finish_or_continue(query, game)

# ══════════════════════════════════════════════════════════════════════════════
#  NEW MINI-GAME #2 — HANGMAN (group guesses in chat)
# ══════════════════════════════════════════════════════════════════════════════
_hangman_games = {}  # chat_id -> {word, guessed:set(), wrong:int, msg_id}

async def cmd_hangman(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    sub = (context.args[0].lower() if context.args else "")
    if sub == "howto":
        await update.message.reply_text(_game_howto("hangman"), parse_mode="Markdown"); return
    if sub == "end":
        if chat_id in _hangman_games:
            word = _hangman_games.pop(chat_id)["word"]
            await update.message.reply_text(f"💀 Hangman ended. The word was *{word.upper()}*.", parse_mode="Markdown")
        else:
            await update.message.reply_text("❌ No active Hangman game here.")
        return
    if chat_id in _hangman_games:
        await update.message.reply_text("⚠️ A Hangman game is already running here!"); return
    word = random.choice(HANGMAN_WORDS)
    _hangman_games[chat_id] = {"word": word, "guessed": set(), "wrong": 0}
    display = " ".join("_" for _ in word)
    msg = await update.message.reply_text(
        f"🔤 *{fancy('HANGMAN STARTED!')}*\n{HANGMAN_STAGES[0]}\n`{display}`\n\nType a single letter to guess! ({len(word)} letters)",
        parse_mode="Markdown")
    _hangman_games[chat_id]["msg_id"] = msg.message_id

@with_data_lock
async def _hangman_try_letter(update: Update, chat_id: int, letter: str) -> bool:
    """Returns True if this text was consumed as a hangman guess."""
    game = _hangman_games.get(chat_id)
    if not game or len(letter) != 1 or not letter.isalpha():
        return False
    letter = letter.lower()
    if letter in game["guessed"]:
        return False
    game["guessed"].add(letter)
    word = game["word"]
    if letter not in word:
        game["wrong"] += 1
    display = " ".join(c if c in game["guessed"] else "_" for c in word)
    if game["wrong"] >= 6:
        await update.message.reply_text(f"💀 ✦ *{fancy('GAME OVER!')}* ✦\n┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄\n{HANGMAN_STAGES[6]}\nThe word was: *{word.upper()}*", parse_mode="Markdown")
        _hangman_games.pop(chat_id, None)
        return True
    if "_" not in display:
        user = update.message.from_user
        data = load_data(); u = get_user(data, user.id, user.username, user.full_name)
        u["coins"] += 30; u["hangman_wins"] = u.get("hangman_wins", 0) + 1
        b = award_badge(u, "hangman_win"); save_data(data)
        name = _safe_md(f"@{user.username}" if user.username else user.full_name)
        await update.message.reply_text(
            f"🎉 ✦ *{fancy('SOLVED!')}* ✦\n┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄\n{name} guessed it! The word was *{word.upper()}*!\n💰 +30 🪙" + (f"\n\n{b}" if b else ""),
            parse_mode="Markdown")
        _hangman_games.pop(chat_id, None)
        return True
    await update.message.reply_text(f"{HANGMAN_STAGES[game['wrong']]}\n`{display}`\nGuessed: {', '.join(sorted(game['guessed']))}",
                                     parse_mode="Markdown")
    return True

# ══════════════════════════════════════════════════════════════════════════════
#  NEW MINI-GAME #3 — GUESS THE NUMBER (solo, DM or group)
# ══════════════════════════════════════════════════════════════════════════════
_guessnum_games = {}  # (chat_id,user_id) -> {target, tries, low, high}

async def cmd_guessnumber(update: Update, context: ContextTypes.DEFAULT_TYPE):
    key = (update.message.chat_id, update.message.from_user.id)
    sub = (context.args[0].lower() if context.args else "")
    if sub == "howto":
        await update.message.reply_text(_game_howto("guessnumber"), parse_mode="Markdown"); return
    if sub == "end":
        if key in _guessnum_games:
            target = _guessnum_games.pop(key)["target"]
            await update.message.reply_text(f"🔢 Game ended. The number was *{target}*.", parse_mode="Markdown")
        else:
            await update.message.reply_text("❌ No active Guess the Number game for you here.")
        return
    _guessnum_games[key] = {"target": random.randint(1, 100), "tries": 0, "low": 1, "high": 100}
    await update.message.reply_text("🔢 ✦ *Guess the Number!* ✦\n┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄\nI'm thinking of a number between *1-100*. You get *7* tries!\nJust type a number.",
                                     parse_mode="Markdown")

@with_data_lock
async def _guessnum_try(update: Update, key, text: str) -> bool:
    game = _guessnum_games.get(key)
    if not game: return False
    try: guess = int(text.strip())
    except Exception: return False
    if not (game["low"] <= guess <= game["high"] or 1 <= guess <= 100):
        return False
    game["tries"] += 1
    if guess == game["target"]:
        user = update.message.from_user
        data = load_data(); u = get_user(data, user.id, user.username, user.full_name)
        reward = max(10, 50 - game["tries"] * 5)
        u["coins"] += reward; save_data(data)
        await update.message.reply_text(
            f"🎯 ✦ *Correct!* ✦\n┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄\nThe number was *{game['target']}*.\nSolved in {game['tries']} tries! 💰 +{reward} 🪙",
            parse_mode="Markdown")
        _guessnum_games.pop(key, None)
        return True
    if game["tries"] >= 7:
        await update.message.reply_text(f"💀 *Out of tries!*\nThe number was *{game['target']}*.", parse_mode="Markdown")
        _guessnum_games.pop(key, None)
        return True
    hint = "📈 Higher!" if guess < game["target"] else "📉 Lower!"
    await update.message.reply_text(f"{hint} _({7-game['tries']} tries left)_", parse_mode="Markdown")
    return True

# ══════════════════════════════════════════════════════════════════════════════
#  NEW MINI-GAME #4 — WORD CHAIN (group lobby)
# ══════════════════════════════════════════════════════════════════════════════
_wordchain_games = {}  # chat_id -> {players:set(), used:set(), last_word, active:bool, last_uid}

WORDCHAIN_TURN_TIMEOUT  = 30   # seconds to give the next word before the chain breaks
WORDCHAIN_LOBBY_TIMEOUT = 360  # 6 min — lobby auto-closes if NO ONE ever plays a first word

_wordchain_word_cache = {}  # lowercase word -> bool, so repeated lookups skip the network call

async def _is_real_english_word(word: str) -> bool:
    """Checks whether `word` is a real English word using a free dictionary
    API, with an AI fallback (Groq/Gemini, same chain the rest of the bot
    already uses) if that API is unreachable — so a network blip doesn't
    brick the whole game. Results are cached in-memory."""
    word = word.lower()
    if word in _wordchain_word_cache:
        return _wordchain_word_cache[word]
    valid = None
    try:
        async with httpx.AsyncClient(timeout=6) as client:
            resp = await client.get(f"https://api.dictionaryapi.dev/api/v2/entries/en/{quote(word)}")
            if resp.status_code == 200:
                valid = True
            elif resp.status_code == 404:
                valid = False
    except Exception as e:
        logger.warning(f"wordchain dictionary lookup failed for '{word}': {e}")
    if valid is None:
        try:
            raw = await groq_raw(
                "You are a strict English dictionary checker. Reply with ONLY "
                "the single word 'yes' or 'no' and nothing else.",
                f'Is "{word}" a real, common English word (any part of speech, '
                f'including plurals/verb forms)? Answer yes or no.',
                temperature=0.0,
            )
            valid = raw.strip().lower().startswith("y") if raw else True
        except Exception as e:
            logger.warning(f"wordchain AI fallback check failed for '{word}': {e}")
            valid = True  # last resort: don't brick the game if both checks fail
    _wordchain_word_cache[word] = valid
    return valid

def _wordchain_cancel_jobs(context, chat_id):
    for name in (f"wc_turn_{chat_id}", f"wc_lobby_{chat_id}"):
        for job in context.job_queue.get_jobs_by_name(name):
            job.schedule_removal()

def _schedule_wordchain_turn_timeout(context, chat_id, word_at_schedule):
    for job in context.job_queue.get_jobs_by_name(f"wc_turn_{chat_id}"):
        job.schedule_removal()
    context.job_queue.run_once(
        _wordchain_turn_timeout_job, when=WORDCHAIN_TURN_TIMEOUT, name=f"wc_turn_{chat_id}",
        data={"chat_id": chat_id, "word_at_schedule": word_at_schedule})

async def _wordchain_turn_timeout_job(context: ContextTypes.DEFAULT_TYPE):
    d = context.job.data; chat_id = d["chat_id"]
    game = _wordchain_games.get(chat_id)
    if not game or not game.get("active"):
        return
    # A newer word already came in since this timer was scheduled — stale, ignore.
    if game.get("last_word") != d.get("word_at_schedule"):
        return
    game["active"] = False
    _wordchain_games.pop(chat_id, None)
    try:
        if game.get("vs_bot"):
            await context.bot.send_message(
                chat_id, "⏰ *Time's up!* You took longer than 30 seconds — *Aira wins this round!* 🤖🏆\n"
                "Run `/wordchain` to play again.", parse_mode="Markdown")
        else:
            last_word = game.get("last_word")
            hint = f" (last word was *{last_word.upper()}*)" if last_word else ""
            await context.bot.send_message(
                chat_id, f"⏰ *Time's up!* No one continued the chain within 30 seconds{hint} — "
                f"chain broken, *you lose!* Run `/wordchain` to play again.", parse_mode="Markdown")
    except Exception:
        pass

async def _wordchain_lobby_expire_job(context: ContextTypes.DEFAULT_TYPE):
    d = context.job.data; chat_id = d["chat_id"]
    game = _wordchain_games.get(chat_id)
    if not game or not game.get("active"):
        return
    if game.get("used"):
        return  # someone already played — no longer idle, nothing to expire
    _wordchain_games.pop(chat_id, None)
    for job in context.job_queue.get_jobs_by_name(f"wc_turn_{chat_id}"):
        job.schedule_removal()
    try:
        await context.bot.send_message(
            chat_id, "🔗 Word Chain lobby closed — no one played a word within 6 minutes.")
    except Exception:
        pass

# Fallback word bank for Aira's solo Word Chain moves, keyed by starting
# letter — used when the AI call fails, times out, or repeats a used word.
_WORDCHAIN_FALLBACK = {
    "a": ["apple","animal","arrow","autumn","anchor"],
    "b": ["banana","bridge","butter","breeze","basket"],
    "c": ["candle","castle","cherry","canyon","comet"],
    "d": ["dragon","desert","dolphin","diamond","dinner"],
    "e": ["eagle","engine","emerald","exam","echo"],
    "f": ["forest","feather","falcon","fabric","fossil"],
    "g": ["garden","guitar","galaxy","giraffe","glacier"],
    "h": ["harbor","hazel","helmet","horizon","honey"],
    "i": ["island","igloo","iron","ivory","insect"],
    "j": ["jungle","jacket","jigsaw","journey","jasmine"],
    "k": ["kitten","kettle","kingdom","kayak","knight"],
    "l": ["lantern","lemon","legend","library","lizard"],
    "m": ["mountain","melody","marble","meadow","mirror"],
    "n": ["nectar","needle","nomad","nutmeg","nebula"],
    "o": ["ocean","orchid","oxygen","otter","onion"],
    "p": ["puzzle","planet","pepper","pyramid","pigeon"],
    "q": ["quartz","quilt","quiver","quokka","quest"],
    "r": ["rocket","raisin","ribbon","river","rabbit"],
    "s": ["sunset","spider","saddle","sapphire","summer"],
    "t": ["tunnel","turtle","temple","thunder","tiger"],
    "u": ["umbrella","unicorn","universe","urban","uranium"],
    "v": ["velvet","valley","violet","vulture","vapor"],
    "w": ["window","walnut","willow","wizard","winter"],
    "x": ["xylophone","xenon"],
    "y": ["yellow","yogurt","yacht","yarn"],
    "z": ["zebra","zipper","zombie","zenith"],
}

async def _wordchain_bot_word(game):
    """Picks Aira's next Word Chain word: tries the AI for variety, falls
    back to a curated pool for reliability (especially on rare letters)."""
    last_letter = game["last_word"][-1] if game["last_word"] else "a"
    used = game["used"]
    try:
        raw = await groq_raw(
            "You are playing a word-chain game. Reply with ONLY one lowercase "
            "English word — no punctuation, no quotes, no explanation.",
            f'Give one common English word starting with the letter "{last_letter}". '
            f'Do not repeat any of these already-used words: '
            f'{", ".join(sorted(used)) if used else "none"}.',
            temperature=1.0,
        )
        candidate = raw.strip().split()[0] if raw.strip() else ""
        word = re.sub(r"[^a-z]", "", candidate.lower())
        if word and word[0] == last_letter and len(word) >= 2 and word not in used:
            return word
    except Exception as e:
        logger.error(f"wordchain bot AI error: {e}")
    pool = _WORDCHAIN_FALLBACK.get(last_letter, [])
    candidates = [w for w in pool if w not in used]
    return random.choice(candidates) if candidates else None

async def cmd_wordchain(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    # BUGFIX: `/wordchain end` was never handled — the command ignored
    # context.args entirely, so typing it just hit the "already running"
    # message (or silently started a new game) instead of stopping anything.
    sub = (context.args[0].lower() if context.args else "")
    if sub == "howto":
        await update.message.reply_text(_game_howto("wordchain"), parse_mode="Markdown"); return
    if sub == "end":
        if chat_id in _wordchain_games and _wordchain_games[chat_id].get("active"):
            _wordchain_games.pop(chat_id, None)
            _wordchain_cancel_jobs(context, chat_id)
            await update.message.reply_text("🔗 Word Chain ended. Thanks for playing! 🙌")
        else:
            await update.message.reply_text("❌ No active Word Chain game here.")
        return
    if chat_id in _wordchain_games and _wordchain_games[chat_id]["active"]:
        await update.message.reply_text("⚠️ Word Chain already running! Reply with a word starting with the right letter."); return
    is_dm = update.message.chat.type == "private"
    _wordchain_games[chat_id] = {"used": set(), "last_word": None, "active": True,
                                  "last_uid": None, "vs_bot": is_dm}
    _wordchain_cancel_jobs(context, chat_id)
    context.job_queue.run_once(
        _wordchain_lobby_expire_job, when=WORDCHAIN_LOBBY_TIMEOUT, name=f"wc_lobby_{chat_id}",
        data={"chat_id": chat_id})
    if is_dm:
        await update.message.reply_text(
            "🔗 *WORD CHAIN — You vs Aira!*\nSend any *real English word* to begin. Aira will reply right back "
            "with her own word starting with your word's last letter, and so on!\n"
            "⏰ You have *30 seconds* per turn, or you lose!\n"
            "_Use `/wordchain end` to stop._", parse_mode="Markdown")
    else:
        await update.message.reply_text(
            "🔗 *WORD CHAIN STARTED!*\nSend any *real English word* to begin. Next word must start with the *last letter* "
            "of the previous word, and can't repeat a used word!\n"
            "⏰ *30 seconds* per turn, or the chain breaks and you lose! Lobby closes if idle for 6 minutes.\n"
            "_Use `/wordchain end` to stop._", parse_mode="Markdown")

@with_data_lock
async def _wordchain_try(update: Update, context: ContextTypes.DEFAULT_TYPE, chat_id: int, text: str) -> bool:
    game = _wordchain_games.get(chat_id)
    if not game or not game["active"]: return False
    word = text.strip().lower()
    if not word.isalpha() or len(word) < 2: return False
    user = update.message.from_user
    if not game.get("vs_bot") and game["last_uid"] == user.id and game["last_word"] is not None:
        await update.message.reply_text("❌ Wait for someone else to go before playing again!")
        return True
    if game["last_word"] and word[0] != game["last_word"][-1]:
        await update.message.reply_text(f"❌ Word must start with *{game['last_word'][-1].upper()}*!", parse_mode="Markdown")
        return True
    if word in game["used"]:
        await update.message.reply_text("❌ That word was already used!")
        return True
    # Only real English words are allowed — reject gibberish/random text.
    if not await _is_real_english_word(word):
        await update.message.reply_text(f"❌ *{word}* isn't a real English word — try again!", parse_mode="Markdown")
        return True
    game["used"].add(word); game["last_word"] = word; game["last_uid"] = user.id
    data = load_data(); u = get_user(data, user.id, user.username, user.full_name)
    # BUGFIX: this was `user["coins"] += 3` — `user` is the raw Telegram User
    # object (from update.message.from_user), not the DB doc `u`, and it
    # doesn't support item assignment. That raised a TypeError on every
    # single successful word, which silently killed the game (the exception
    # was swallowed higher up in handle_message's dispatch, so it just
    # looked like Word Chain "stopped working" mid-game).
    u["coins"] += 3; save_data(data)
    await update.message.reply_text(f"✅ *{word.upper()}*! Next word starts with *{word[-1].upper()}* (+3 🪙)", parse_mode="Markdown")

    if game.get("vs_bot"):
        bot_word = await _wordchain_bot_word(game)
        if bot_word:
            game["used"].add(bot_word); game["last_word"] = bot_word; game["last_uid"] = _AIRA_BOT_UID
            await update.message.reply_text(
                f"🤖 Aira says: *{bot_word.upper()}*!\nYour turn — start with *{bot_word[-1].upper()}* (⏰ 30s)",
                parse_mode="Markdown")
            _schedule_wordchain_turn_timeout(context, chat_id, bot_word)
        else:
            game["active"] = False
            _wordchain_cancel_jobs(context, chat_id)
            await update.message.reply_text(
                f"🤖 Aira's stuck — she can't think of a word starting with *{word[-1].upper()}*!\n"
                f"*You win!* 🏆 Run `/wordchain` to play again.", parse_mode="Markdown")
    else:
        _schedule_wordchain_turn_timeout(context, chat_id, word)
    return True

# ══════════════════════════════════════════════════════════════════════════════
#  NEW MINI-GAME #5 — ROCK PAPER SCISSORS
# ══════════════════════════════════════════════════════════════════════════════
def _rps_kb(rps_id):
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("🪨 Rock", callback_data=f"rps_{rps_id}_rock"),
        InlineKeyboardButton("📄 Paper", callback_data=f"rps_{rps_id}_paper"),
        InlineKeyboardButton("✂️ Scissors", callback_data=f"rps_{rps_id}_scissors"),
    ]])

_rps_games = {}

async def cmd_rps(update: Update, context: ContextTypes.DEFAULT_TYPE):
    p1 = update.message.from_user
    if context.args and context.args[0].lower() == "howto":
        await update.message.reply_text(_game_howto("rps"), parse_mode="Markdown"); return
    if not update.message.reply_to_message:
        await update.message.reply_text("↩️ Reply to someone with `/rps` to challenge Rock-Paper-Scissors!"); return
    p2 = update.message.reply_to_message.from_user
    if p2.id == p1.id: await update.message.reply_text("❌ Can't play yourself!"); return
    if p2.is_bot: await update.message.reply_text("❌ Can't play a bot!"); return
    rps_id = f"{p1.id}_{p2.id}_{int(datetime.now().timestamp())}"
    _rps_games[rps_id] = {"p1": p1.id, "p2": p2.id, "choices": {}}
    p1n = _safe_md(f"@{p1.username}" if p1.username else p1.full_name)
    p2n = _safe_md(f"@{p2.username}" if p2.username else p2.full_name)
    await update.message.reply_text(f"✊ ✦ *Rock Paper Scissors!* ✦\n┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄\n{p1n} vs {p2n}\nBoth pick secretly below 👇",
                                     reply_markup=_rps_kb(rps_id), parse_mode="Markdown")

@with_data_lock
async def handle_rps(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
  
    # data format rps_<id>_<choice> where id itself has underscores -> split carefully
    parts = query.data.split("_")
    choice = parts[-1]; rps_id = "_".join(parts[1:-1])
    game = _rps_games.get(rps_id)
    if not game: await query.answer("Game expired!", show_alert=True); return
    uid = query.from_user.id
    if uid not in (game["p1"], game["p2"]):
        await query.answer("This isn't your game!", show_alert=True); return
    if uid in game["choices"]:
        await query.answer("You already picked!", show_alert=True); return
    game["choices"][uid] = choice
    await query.answer(f"You picked {choice}!")
    if len(game["choices"]) < 2:
        return
    c1, c2 = game["choices"][game["p1"]], game["choices"][game["p2"]]
    data = load_data()
    u1 = get_user(data, game["p1"]); u2 = get_user(data, game["p2"])
    n1 = _safe_md(f"@{u1.get('username','?')}" if u1.get("username") != "Unknown" else u1.get("full_name", "P1"))
    n2 = _safe_md(f"@{u2.get('username','?')}" if u2.get("username") != "Unknown" else u2.get("full_name", "P2"))
    beats = {"rock": "scissors", "paper": "rock", "scissors": "paper"}
    icons = {"rock": "🪨", "paper": "📄", "scissors": "✂️"}
    if c1 == c2:
        result_text = "🤝 *It's a tie!*"
    elif beats[c1] == c2:
        u1["coins"] += 15; result_text = f"🏆 *{n1} wins!* +15 🪙"
    else:
        u2["coins"] += 15; result_text = f"🏆 *{n2} wins!* +15 🪙"
    save_data(data)
    await _safe_edit_message_text(query, 
        f"✊ ✦ *Rock Paper Scissors — Result!* ✦\n┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄\n{n1}: {icons[c1]} {c1} | {n2}: {icons[c2]} {c2}\n\n{result_text}",
        parse_mode="Markdown")
    _rps_games.pop(rps_id, None)

# ══════════════════════════════════════════════════════════════════════════════
#  NEW MINI-GAME #6 — BLACKJACK (vs dealer)
#  Real 2-deck shoe dealt without replacement (not infinite-shoe iid draws —
#  that made every hand feel statistically identical/"solvable"), suited
#  card display, dealer hole-card + blackjack peek, dealer hits soft 17,
#  no natural/peek — every hand plays through Hit/Stand.
# ══════════════════════════════════════════════════════════════════════════════
_BJ_RANKS = [("A", 11), ("2", 2), ("3", 3), ("4", 4), ("5", 5), ("6", 6), ("7", 7),
             ("8", 8), ("9", 9), ("10", 10), ("J", 10), ("Q", 10), ("K", 10)]
_BJ_SUITS = ["♠", "♥", "♦", "♣"]

def _bj_new_shoe(decks=2):
    shoe = [{"rank": r, "suit": s, "val": v}
            for _ in range(decks) for r, v in _BJ_RANKS for s in _BJ_SUITS]
    random.shuffle(shoe)
    return shoe

def _bj_draw(shoe):
    if not shoe:  # safety net — shouldn't trigger inside one hand of a 2-deck shoe
        shoe.extend(_bj_new_shoe())
    return shoe.pop()

def _bj_total(hand):
    total = sum(c["val"] for c in hand)
    aces = sum(1 for c in hand if c["rank"] == "A")
    while total > 21 and aces:
        total -= 10; aces -= 1
    return total

def _bj_is_soft(hand):
    """True if an Ace is still being counted as 11 in the current total —
    controls the dealer's 'hit on soft 17' rule."""
    total = sum(c["val"] for c in hand)
    aces = sum(1 for c in hand if c["rank"] == "A")
    while total > 21 and aces:
        total -= 10; aces -= 1
    return aces > 0

def _bj_is_blackjack(hand):
    return len(hand) == 2 and _bj_total(hand) == 21

def _bj_card_str(c):
    # Plain numeric display (back to the original look — no K/Q/J face
    # letters or suit symbols). Still a real 2-deck shoe underneath for
    # fairness, this only changes what gets shown.
    return str(c["val"])

def _bj_hand_str(hand, hide_first=False):
    if hide_first and hand:
        return "❓ + " + " + ".join(_bj_card_str(c) for c in hand[1:])
    return " + ".join(_bj_card_str(c) for c in hand)

_bj_games = {}  # message_id -> {uid, bet, player, dealer, shoe}

def _bj_kb():
    row = [InlineKeyboardButton("🃏 Hit", callback_data="bj_hit"),
           InlineKeyboardButton("✋ Stand", callback_data="bj_stand")]
    return InlineKeyboardMarkup([row])

@with_data_lock
async def cmd_blackjack(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    if context.args and context.args[0].lower() == "howto":
        await update.message.reply_text(_game_howto("blackjack"), parse_mode="Markdown"); return
    data = load_data(); u = get_user(data, user.id, user.username, user.full_name)
    if not context.args:
        await update.message.reply_text("Usage: `/blackjack <bet>`", parse_mode="Markdown"); return
    try: bet = int(context.args[0])
    except Exception: await update.message.reply_text("❌ Bet must be a number."); return
    if bet <= 0 or bet > u["coins"]:
        await update.message.reply_text(f"❌ Invalid bet. You have *{u['coins']:,}* 🪙.", parse_mode="Markdown"); return
    # Bet is escrowed immediately instead of staying "un-spent" in the visible
    # balance until the game resolves — otherwise it could be spent elsewhere
    # (shop, trade, another blackjack) before this game settles, which is what
    # caused balances to desync/go negative.
    u["coins"] -= bet
    save_data(data)

    shoe = _bj_new_shoe()
    player = [_bj_draw(shoe), _bj_draw(shoe)]
    dealer = [_bj_draw(shoe), _bj_draw(shoe)]
    game = {"uid": user.id, "bet": bet, "player": player, "dealer": dealer, "shoe": shoe}
    # No natural/peek — always show Hit/Stand so player controls every hand
    msg = await update.message.reply_text(
        f"🃏 ✦ *{fancy('BLACKJACK')}* ✦\n┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄\nBet: *{bet:,} 🪙*\n\n"
        f"🧑 Your hand: {_bj_hand_str(player)} — *{_bj_total(player)}*\n"
        f"🎩 Dealer shows: {_bj_hand_str([dealer[0]])}",
        reply_markup=_bj_kb(), parse_mode="Markdown")
    _bj_games[msg.message_id] = game


# _bj_settle removed — no instant-resolve paths remain


@with_data_lock
async def handle_blackjack(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    game = _bj_games.get(query.message.message_id)
    if not game: await query.answer("Game expired!", show_alert=True); return
    if query.from_user.id != game["uid"]:
        await query.answer("Not your game!", show_alert=True); return
    try:
        await query.answer()
    except (BadRequest, TelegramError):
        pass  # stale/expired callback query — safe to ignore, continue handling
    action = query.data

    async def finish(win_mult, text_extra=""):
        data = load_data(); u = get_user(data, game["uid"])
        bet = game["bet"]
        # NOTE: the bet was already escrowed when it was placed, so
        # settlement only needs to pay back stake + profit
        # (win), stake only (push), or nothing at all (loss — already paid).
        if win_mult > 0:
            winnings = int(bet * win_mult)
            payout = bet + winnings
            u["coins"] += payout; u["total_coins_ever"] = u.get("total_coins_ever", 0) + winnings
            u["casino_wins"] = u.get("casino_wins", 0) + 1; u["casino_total_won"] = u.get("casino_total_won", 0) + winnings
            u["bj_wins"] = u.get("bj_wins", 0) + 1
            b = award_badge(u, "bj_win")
            badge_txt = f"\n\n{b}" if b else ""
            outcome = f"✅ *{fancy('YOU WIN!')}* +{winnings:,} 🪙{badge_txt}"
        elif win_mult == 0:
            u["coins"] += bet
            outcome = "🤝 *PUSH!* Bet returned."
        else:
            outcome = f"❌ *{fancy('YOU LOSE!')}* -{bet:,} 🪙"
        save_data(data)
        await _safe_edit_message_text(query,
            f"🃏 ✦ *Blackjack — Result* ✦\n┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄\n"
            f"🧑 Your hand: {_bj_hand_str(game['player'])} — *{_bj_total(game['player'])}*\n"
            f"🎩 Dealer: {_bj_hand_str(game['dealer'])} — *{_bj_total(game['dealer'])}*\n{text_extra}\n{outcome}",
            parse_mode="Markdown")
        _bj_games.pop(query.message.message_id, None)

    def _play_dealer():
        # Standard rule: dealer hits on soft 17, not just hard totals < 17.
        while _bj_total(game["dealer"]) < 17 or (_bj_total(game["dealer"]) == 17 and _bj_is_soft(game["dealer"])):
            game["dealer"].append(_bj_draw(game["shoe"]))

    if action == "bj_hit":
        game["player"].append(_bj_draw(game["shoe"]))
        total = _bj_total(game["player"])
        if total > 21:
            await finish(-1, "💥 *BUST!*")
            return
        if total == 21:
            # Auto-stand at 21 — play dealer and resolve
            _play_dealer()
            d_total = _bj_total(game["dealer"])
            if d_total > 21 or d_total < 21:
                await finish(1, "🎉 *21!*")
            else:
                await finish(0, "🤝 *Both 21 — Push!*")
            return
        await _safe_edit_message_text(query,
            f"🃏 ✦ *{fancy('BLACKJACK')}* ✦\n┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄\nBet: *{game['bet']:,} 🪙*\n\n"
            f"🧑 Your hand: {_bj_hand_str(game['player'])} — *{total}*\n🎩 Dealer shows: {_bj_hand_str([game['dealer'][0]])}",
            reply_markup=_bj_kb(), parse_mode="Markdown")
        return

    if action == "bj_stand":
        _play_dealer()
        p_total, d_total = _bj_total(game["player"]), _bj_total(game["dealer"])
        if d_total > 21 or p_total > d_total:
            await finish(1)
        elif p_total == d_total:
            await finish(0)
        else:
            await finish(-1)

# ══════════════════════════════════════════════════════════════════════════════
#  NEW MINI-GAME #7 — QUIZ BATTLE (multiplayer, timed, multi-question)
# ══════════════════════════════════════════════════════════════════════════════
_quiz_battles = {}  # chat_id -> {question_num, scores:{uid:points}, current_answer, active}

async def cmd_quizbattle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    sub = (context.args[0].lower() if context.args else "")
    if sub == "howto":
        await update.message.reply_text(_game_howto("quizbattle"), parse_mode="Markdown"); return
    if sub == "end":
        if chat_id in _quiz_battles and _quiz_battles[chat_id].get("active"):
            _quiz_battles.pop(chat_id, None)
            await update.message.reply_text("🧠 Quiz Battle ended early. Thanks for playing! 🙌")
        else:
            await update.message.reply_text("❌ No active Quiz Battle here.")
        return
    if chat_id in _quiz_battles and _quiz_battles[chat_id]["active"]:
        await update.message.reply_text("⚠️ A Quiz Battle is already running!"); return
    _quiz_battles[chat_id] = {"question_num": 0, "scores": {}, "names": {}, "current_answer": None, "active": True}
    await update.message.reply_text("🧠 *QUIZ BATTLE!*\n5 questions, fastest correct answer per round wins points!\nGet ready...",
                                     parse_mode="Markdown")
    await _quiz_next_question(context, chat_id)

async def _quiz_next_question_job(context: ContextTypes.DEFAULT_TYPE):
    await _quiz_next_question(context, context.job.data["chat_id"])

async def _quiz_next_question(context, chat_id):
    game = _quiz_battles.get(chat_id)
    if not game or not game["active"]: return
    if game["question_num"] >= 5:
        game["active"] = False
        if game["scores"]:
            ranked = sorted(game["scores"].items(), key=lambda x: x[1], reverse=True)
            top_uid, top_score = ranked[0]
            data = load_data(); u = get_user(data, top_uid)
            u["coins"] += 50; u["quiz_wins"] = u.get("quiz_wins", 0) + 1
            b = award_badge(u, "quiz_top"); save_data(data)
            lines = ["🏆 ✦ *QUIZ BATTLE OVER!* ✦\n┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄"]
            medals = ["🥇","🥈","🥉","4️⃣","5️⃣"]
            for i, (uid, score) in enumerate(ranked[:5]):
                lines.append(f"{medals[i]} {_safe_md(game['names'].get(uid,'?'))} — {score} pts")
            lines.append(f"\n💰 *{_safe_md(game['names'].get(top_uid,'?'))}* wins +50 🪙!" + (f"\n\n{b}" if b else ""))
            await context.bot.send_message(chat_id, "\n".join(lines), parse_mode="Markdown")
        else:
            await context.bot.send_message(chat_id, "🧠 Quiz ended — nobody scored!")
        _quiz_battles.pop(chat_id, None)
        return
    q = dict(random.choice(CHALLENGE_FALLBACK_POOL))
    game["question_num"] += 1
    game["current_answer"] = q["a"].lower().strip()
    await context.bot.send_message(chat_id, f"❓ *Q{game['question_num']}/5:* {q['q']}\n_First correct answer wins the point!_",
                                    parse_mode="Markdown")
    context.job_queue.run_once(_quiz_next_question_job, when=20, name=f"quiznext_{chat_id}",
                                data={"chat_id": chat_id})

async def _quiz_try_answer(update: Update, context: ContextTypes.DEFAULT_TYPE, chat_id: int, text: str) -> bool:
    game = _quiz_battles.get(chat_id)
    if not game or not game["active"] or not game["current_answer"]: return False
    if text.strip().lower() != game["current_answer"]: return False
    user = update.message.from_user
    name = _safe_md(f"@{user.username}" if user.username else user.full_name)
    game["scores"][user.id] = game["scores"].get(user.id, 0) + 1
    game["names"][user.id] = name
    game["current_answer"] = None
    for job in context.job_queue.get_jobs_by_name(f"quiznext_{chat_id}"):
        job.schedule_removal()
    await update.message.reply_text(f"✅ *{name}* got it right! (+1 point)", parse_mode="Markdown")
    await asyncio.sleep(1.5)
    await _quiz_next_question(context, chat_id)
    return True

# ══════════════════════════════════════════════════════════════════════════════
#  TRUTH & DARE  (instant + multiplayer lobby, ported/fixed from v8)
# ══════════════════════════════════════════════════════════════════════════════
_tnd_lobbies = {}

async def cmd_truth(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    name = _safe_md(f"@{user.username}" if user.username else user.full_name)
    msg = await update.message.reply_text("🙊 thinking of something spicy...")
    q = await get_fresh_truth(update.message.chat_id)
    await msg.edit_text(f"🙊 *TRUTH for {name}!*\n\n_{q}_", parse_mode="Markdown")

async def cmd_dare(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    name = _safe_md(f"@{user.username}" if user.username else user.full_name)
    msg = await update.message.reply_text("🔥 thinking of a dare...")
    q = await get_fresh_dare(update.message.chat_id)
    await msg.edit_text(f"🔥 *DARE for {name}!*\n\n_{q}_", parse_mode="Markdown")

def _tnd_keyboard(current_uid, lobby):
    counts = lobby["consecutive_count"].get(current_uid, {"truth": 0, "dare": 0, "wyr": 0})
    tb = " (blocked)" if counts["truth"] >= 2 else ""
    db_ = " (blocked)" if counts["dare"] >= 2 else ""
    wb = " (blocked)" if counts.get("wyr", 0) >= 2 else ""
    return InlineKeyboardMarkup([[
        InlineKeyboardButton(f"🙊 Truth{tb}", callback_data=f"tnd_truth_{current_uid}"),
        InlineKeyboardButton(f"🔥 Dare{db_}", callback_data=f"tnd_dare_{current_uid}"),
        InlineKeyboardButton(f"🤔 WYR{wb}", callback_data=f"tnd_wyr_{current_uid}"),
    ]])

async def cmd_tnd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id; user = update.message.from_user; uid = user.id
    name = _safe_md(f"@{user.username}" if user.username else user.full_name)
    sub = context.args[0].lower() if context.args else ""

    if sub == "howto":
        await update.message.reply_text(_game_howto("tnd"), parse_mode="Markdown"); return

    if not sub:
        if chat_id in _tnd_lobbies and _tnd_lobbies[chat_id]["status"] in ("lobby", "active"):
            lobby = _tnd_lobbies[chat_id]
            if lobby["status"] == "lobby":
                players_list = "\n".join(f"  ✧ {n}" for n in lobby["players"].values())
                await update.message.reply_text(
                    f"🎭 *T&D lobby exists!*\n👥 Players ({len(lobby['players'])}):\n{players_list}\n\n"
                    f"`/tnd join` to join | `/tnd start` to begin (host only)", parse_mode="Markdown")
            else:
                await update.message.reply_text("🎭 A game is already *in progress*! Use `/tnd end` first.", parse_mode="Markdown")
            return
        _tnd_lobbies[chat_id] = {"host_id": uid, "host_name": name, "players": {uid: name}, "status": "lobby",
                                  "current_player_idx": 0, "player_order": [], "consecutive_count": {}}
        context.job_queue.run_once(_tnd_lobby_expire, when=300, name=f"tnd_expire_{chat_id}", data={"chat_id": chat_id})
        await update.message.reply_text(
            f"🎭 *Truth or Dare Lobby Created!*\n👑 Host: {name}\nOthers: `/tnd join` | Host: `/tnd start`\n"
            f"_(expires in 5 min if only 1 player)_", parse_mode="Markdown")
        return

    if sub == "join":
        if chat_id not in _tnd_lobbies: await update.message.reply_text("❌ No lobby! Use `/tnd`.", parse_mode="Markdown"); return
        lobby = _tnd_lobbies[chat_id]
        if lobby["status"] != "lobby": await update.message.reply_text("❌ Already started!"); return
        if uid in lobby["players"]: await update.message.reply_text(f"Already in lobby {name}! 😄"); return
        lobby["players"][uid] = name
        await update.message.reply_text(f"✅ *{name}* joined! 👥 {len(lobby['players'])} players", parse_mode="Markdown")
        return

    if sub == "leave":
        if chat_id not in _tnd_lobbies: return
        lobby = _tnd_lobbies[chat_id]
        if uid not in lobby["players"]: await update.message.reply_text("❌ You're not in the lobby!"); return
        del lobby["players"][uid]
        await update.message.reply_text(f"👋 *{name}* left.", parse_mode="Markdown")
        if uid == lobby["host_id"]:
            if lobby["players"]:
                new_host = next(iter(lobby["players"]))
                lobby["host_id"] = new_host; lobby["host_name"] = lobby["players"][new_host]
                await update.message.reply_text(f"👑 {lobby['host_name']} is now host!")
            else:
                del _tnd_lobbies[chat_id]; await update.message.reply_text("🎭 Lobby closed — empty!")
        return

    if sub == "start":
        if chat_id not in _tnd_lobbies: await update.message.reply_text("❌ No lobby!"); return
        lobby = _tnd_lobbies[chat_id]
        if uid != lobby["host_id"]: await update.message.reply_text("❌ Host only!"); return
        if len(lobby["players"]) < 2: await update.message.reply_text("❌ Need 2+ players!"); return
        if lobby["status"] == "active": await update.message.reply_text("Already running!"); return
        for job in context.job_queue.get_jobs_by_name(f"tnd_expire_{chat_id}"): job.schedule_removal()
        lobby["status"] = "active"; lobby["player_order"] = list(lobby["players"].keys())
        random.shuffle(lobby["player_order"]); lobby["current_player_idx"] = 0
        lobby["consecutive_count"] = {p: {"truth": 0, "dare": 0, "wyr": 0} for p in lobby["players"]}
        order_str = "\n".join(f"  {i+1}. {lobby['players'][p]}" for i, p in enumerate(lobby["player_order"]))
        first_uid = lobby["player_order"][0]; first_name = lobby["players"][first_uid]
        sent = await update.message.reply_text(
            f"🎭 *T&D STARTED!*\n🎲 Order:\n{order_str}\n\n🎤 First: *{first_name}*\nChoose! 👇",
            parse_mode="Markdown", reply_markup=_tnd_keyboard(first_uid, lobby))
        _schedule_tnd_choice_timeout(context, chat_id, sent.message_id, first_uid, lobby)
        return

    if sub == "end":
        if chat_id not in _tnd_lobbies: await update.message.reply_text("❌ No active Truth & Dare game here."); return
        lobby = _tnd_lobbies[chat_id]
        if uid != lobby["host_id"] and not await is_admin(context.bot, chat_id, uid):
            await update.message.reply_text("❌ Host or admin only!"); return
        del _tnd_lobbies[chat_id]
        for job in context.job_queue.get_jobs_by_name(f"tnd_expire_{chat_id}"): job.schedule_removal()
        for job in context.job_queue.get_jobs_by_name(f"tnd_autonext_{chat_id}"): job.schedule_removal()
        await update.message.reply_text("🎭 *T&D ended!* Thanks for playing 🙌", parse_mode="Markdown")
        return

    await update.message.reply_text(
        "🎭 `/tnd` create | `/tnd join` | `/tnd leave` | `/tnd start` | `/tnd end`\nOr `/truth` `/dare` for instant ones!",
        parse_mode="Markdown")

def _schedule_tnd_choice_timeout(context, chat_id, message_id, current_uid, lobby):
    for job in context.job_queue.get_jobs_by_name(f"tnd_autonext_{chat_id}"): job.schedule_removal()
    context.job_queue.run_once(_tnd_auto_advance, when=TND_TURN_TIMEOUT, name=f"tnd_autonext_{chat_id}",
        data={"chat_id": chat_id, "message_id": message_id, "stage": "choosing",
              "player_idx_at_schedule": lobby["current_player_idx"]})

def _schedule_tnd_next_timeout(context, chat_id, message_id, lobby):
    for job in context.job_queue.get_jobs_by_name(f"tnd_autonext_{chat_id}"): job.schedule_removal()
    context.job_queue.run_once(_tnd_auto_advance, when=TND_TURN_TIMEOUT, name=f"tnd_autonext_{chat_id}",
        data={"chat_id": chat_id, "message_id": message_id, "stage": "revealed",
              "player_idx_at_schedule": lobby["current_player_idx"]})

async def _advance_tnd_turn(context, chat_id, message_id, lobby):
    lobby["current_player_idx"] = (lobby["current_player_idx"] + 1) % len(lobby["player_order"])
    next_uid = lobby["player_order"][lobby["current_player_idx"]]
    next_name = lobby["players"].get(next_uid, "Player")
    new_msg_id = message_id
    try:
        sent = await context.bot.send_message(chat_id=chat_id,
            text=f"🎭 *Next up: {next_name}!*\nChoose! 👇", parse_mode="Markdown",
            reply_markup=_tnd_keyboard(next_uid, lobby))
        new_msg_id = sent.message_id
    except BadRequest:
        pass
    _schedule_tnd_choice_timeout(context, chat_id, new_msg_id, next_uid, lobby)

async def _tnd_auto_advance(context: ContextTypes.DEFAULT_TYPE):
    d = context.job.data; chat_id = d["chat_id"]
    if chat_id not in _tnd_lobbies: return
    lobby = _tnd_lobbies[chat_id]
    if lobby["status"] != "active": return
    if lobby["current_player_idx"] != d.get("player_idx_at_schedule"): return
    try:
        if d.get("stage") == "choosing":
            stuck_uid = lobby["player_order"][lobby["current_player_idx"]]
            stuck_name = lobby["players"].get(stuck_uid, "Player")
            try:
                await context.bot.edit_message_text(chat_id=chat_id, message_id=d["message_id"],
                    text=f"⌛ *{stuck_name}* took too long!\nSkipping...", parse_mode="Markdown")
            except BadRequest: pass
        await _advance_tnd_turn(context, chat_id, d["message_id"], lobby)
    except Exception as e:
        logger.error(f"_tnd_auto_advance: {e}")

async def handle_tnd_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    try: await query.answer()
    except BadRequest: pass
    parts = query.data.split("_"); choice = parts[1]; target_uid = int(parts[2])
    chat_id = query.message.chat_id; clicker_id = query.from_user.id
    if chat_id not in _tnd_lobbies:
        try: await _safe_edit_message_text(query, "❌ Game ended!")
        except BadRequest: pass
        return
    lobby = _tnd_lobbies[chat_id]
    if lobby["status"] != "active": await query.answer("Not active!", show_alert=True); return
    if clicker_id != target_uid: await query.answer("Not your turn! 😤", show_alert=True); return
    counts = lobby["consecutive_count"].setdefault(target_uid, {"truth": 0, "dare": 0, "wyr": 0})
    if choice == "truth" and counts["truth"] >= 2: await query.answer("Pick Dare or WYR! 🔥", show_alert=True); return
    if choice == "dare" and counts["dare"] >= 2: await query.answer("Pick Truth or WYR! 🙊", show_alert=True); return
    if choice == "wyr" and counts.get("wyr", 0) >= 2: await query.answer("Pick Truth or Dare! 🤔", show_alert=True); return
    if choice == "truth":
        counts["truth"] += 1; counts["dare"] = 0; counts["wyr"] = 0
        question = await get_fresh_truth(chat_id); icon, label = "🙊", "TRUTH"
    elif choice == "dare":
        counts["dare"] += 1; counts["truth"] = 0; counts["wyr"] = 0
        question = await get_fresh_dare(chat_id); icon, label = "🔥", "DARE"
    else:
        counts["wyr"] += 1; counts["truth"] = 0; counts["dare"] = 0
        opt_a, opt_b = _draw_from_deck(chat_id, "wyr")
        question = f"Would you rather...\n🅰️ {opt_a}\n— or —\n🅱️ {opt_b}"
        icon, label = "🤔", "WOULD YOU RATHER"
    player_name = _safe_md(lobby["players"].get(target_uid, "Player"))
    try:
        await query.edit_message_reply_markup(reply_markup=None)  # remove buttons from old msg
    except BadRequest: pass
    sent = None
    try:
        sent = await context.bot.send_message(chat_id=chat_id,
            text=f"{icon} *{player_name}* chose *{label}!*\n\n_{question}_\n\n_(Hit Next, or auto-skip in {TND_TURN_TIMEOUT}s!)_",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⏭️ Next", callback_data=f"tnd_next_{target_uid}")]]))
    except BadRequest: pass
    if sent:
        _schedule_tnd_next_timeout(context, chat_id, sent.message_id, lobby)

async def handle_tnd_next(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    try: await query.answer()
    except BadRequest: pass
    prev_uid = int(query.data.split("_")[2]); chat_id = query.message.chat_id
    if chat_id not in _tnd_lobbies:
        try: await _safe_edit_message_text(query, "🏁 Game has ended!")
        except BadRequest: pass
        return
    lobby = _tnd_lobbies[chat_id]
    if lobby["status"] != "active": return
    if query.from_user.id not in (prev_uid, lobby["host_id"]):
        await query.answer("Only current player or host!", show_alert=True); return
    for job in context.job_queue.get_jobs_by_name(f"tnd_autonext_{chat_id}"): job.schedule_removal()
    await _advance_tnd_turn(context, chat_id, query.message.message_id, lobby)

async def _tnd_lobby_expire(context: ContextTypes.DEFAULT_TYPE):
    d = context.job.data; chat_id = d["chat_id"]
    if chat_id not in _tnd_lobbies: return
    lobby = _tnd_lobbies[chat_id]
    if lobby["status"] != "lobby" or len(lobby["players"]) > 1: return
    del _tnd_lobbies[chat_id]
    try: await context.bot.send_message(chat_id, "🎭 *T&D lobby expired!* Start a new one with `/tnd` 👻", parse_mode="Markdown")
    except Exception: pass

# ══════════════════════════════════════════════════════════════════════════════
#  WHO'S THE TRAITOR — full async rewrite (ported + hardened from v8)
# ══════════════════════════════════════════════════════════════════════════════
_traitor_games = {}
_resolving_chats = set()
_traitor_word_pools = {}  # chat_id -> shuffled list of remaining words; refills when empty
_antispam_tracker  = {}
ANTISPAM_MSG_LIMIT = 5     # messages allowed within window (was 10 — too lenient)
ANTISPAM_WINDOW    = 8     # seconds
ANTISPAM_TIMEOUT   = 300   # 5-minute mute (was 3 min)

def _get_next_traitor_word(chat_id: int) -> str:
    """Pop from a shuffled deck per chat. Refills only after every word is used once."""
    if chat_id not in _traitor_word_pools or not _traitor_word_pools[chat_id]:
        pool = TRAITOR_WORD_BANK.copy()
        random.shuffle(pool)
        _traitor_word_pools[chat_id] = pool
    return _traitor_word_pools[chat_id].pop()

def _cancel_traitor_jobs(context, chat_id):
    for name in (f"traitorvote_{chat_id}", f"traitortally_{chat_id}"):
        for job in context.job_queue.get_jobs_by_name(name): job.schedule_removal()



# ══════════════════════════════════════════════════════════════════════════════
#  WHO'S THE TRAITOR v2 — DM polls, multiple traitors, tie→new round
# ══════════════════════════════════════════════════════════════════════════════

def _traitor_count(n_players: int) -> int:
    """How many traitors based on player count."""
    if n_players <= 5:  return 1
    if n_players <= 8:  return 2
    if n_players <= 12: return 3
    return 4

# ══════════════════════════════════════════════════════════════════════════════
#  GAME RULEBOOKS — `/<command> howto` shows one of these. Centralized so
#  every game has the same discoverable, consistently-formatted rules screen.
# ══════════════════════════════════════════════════════════════════════════════
GAME_RULES = {
    "traitor": (
        f"🕵️ *WHO'S THE TRAITOR — RULEBOOK*\n{DIV}\n"
        "`/traitor` opens a lobby, others join with `/traitor join`.\n"
        "`/traitor start` (host only) once you have 3+ players.\n\n"
        "Everyone gets a role by DM:\n"
        f"{BUL} Innocents get the secret word.\n"
        f"{BUL} Traitors do NOT — they have to bluff and guess it from context.\n\n"
        f"Each round: {TRAITOR_DISCUSSION_SECONDS}s discussion, then everyone votes\n"
        f"by DM poll on who they think is a traitor. A tie means no elimination\n"
        f"and a fresh word for the next round.\n\n"
        f"{BUL} Innocents win once every traitor is voted out.\n"
        f"{BUL} Traitors win if they ever equal or outnumber the innocents.\n"
        "`/traitor leave` `/traitor end`"
    ),
    "ttt": (
        f"🎮 *TIC-TAC-TOE — RULEBOOK*\n{DIV}\n"
        "Reply to someone with `/ttt` to challenge them.\n"
        "In a private chat with no one to reply to, Aira plays as your opponent.\n"
        f"{BUL} Standard 3×3 rules — 3 in a row wins.\n"
        "Tap the grid buttons to place your mark on your turn."
    ),
    "hangman": (
        f"🔤 *HANGMAN — RULEBOOK*\n{DIV}\n"
        "`/hangman` starts a word for the whole group to guess together.\n"
        f"{BUL} Type a single letter to guess it.\n"
        f"{BUL} Too many wrong letters and the game is lost.\n"
        "`/hangman end` stops the current game early."
    ),
    "guessnumber": (
        f"🔢 *GUESS THE NUMBER — RULEBOOK*\n{DIV}\n"
        "`/guessnumber` starts a personal round just for you.\n"
        f"{BUL} Aira picks a number between 1 and 100.\n"
        f"{BUL} You get 7 tries — just type a number each guess.\n"
        f"{BUL} She'll tell you higher or lower after each try.\n"
        "`/guessnumber end` stops your current round."
    ),
    "wordchain": (
        f"🔗 *WORD CHAIN — RULEBOOK*\n{DIV}\n"
        "`/wordchain` starts a lobby (or, in DM, you vs Aira directly).\n"
        f"{BUL} Each word must start with the last letter of the word before it.\n"
        f"{BUL} It must be a real English word, and can't be reused.\n"
        f"{BUL} You have a time limit per turn — miss it and you're out.\n"
        "`/wordchain end` stops the current game."
    ),
    "rps": (
        f"✊ *ROCK PAPER SCISSORS — RULEBOOK*\n{DIV}\n"
        "Reply to someone with `/rps` to challenge them.\n"
        f"{BUL} Both players pick secretly using the buttons.\n"
        f"{BUL} Rock beats Scissors, Scissors beats Paper, Paper beats Rock.\n"
        "Once both have picked, the result reveals automatically."
    ),
    "blackjack": (
        f"🃏 *BLACKJACK — HOW TO PLAY*\n{DIV}\n"
        "`/blackjack <bet>` deals 2 cards each from a fresh 2-deck shoe (104 cards).\n\n"
        "*Card values:*\n"
        f"{BUL} 2–10 = face value.\n"
        f"{BUL} Jack / Queen / King = *10*.\n"
        f"{BUL} Ace = *11*, auto-drops to *1* if 11 would bust you.\n\n"
        "*Your turn:*\n"
        f"{BUL} 🃏 *Hit* — draw one more card. Repeat as many times as you like.\n"
        f"{BUL} ✋ *Stand* — lock your total. Dealer then plays automatically.\n"
        "_No naturals, no dealer peek, no instant endings. "
        "You always get Hit/Stand first._\n\n"
        "*Dealer rules (automatic, no choices):*\n"
        f"{BUL} Dealer reveals hidden card after you stand.\n"
        f"{BUL} Dealer hits on anything below 17, including soft 17 (Ace + 6).\n"
        f"{BUL} Dealer stands on hard 17 or above.\n\n"
        "*Outcomes:*\n"
        f"{BUL} ✅ *Win* — your total beats dealer, or dealer busts. Payout *1:1* "
        "(bet 100🪙, win 100🪙, total back = 200🪙).\n"
        f"{BUL} 🤝 *Push* — same total. Bet returned, zero loss.\n"
        f"{BUL} ❌ *Lose* — dealer beats you, or you bust. Bet is gone.\n\n"
        "*Special cases:*\n"
        f"{BUL} Hit to exactly 21 → auto-stands, dealer plays, resolves normally.\n"
        f"{BUL} Bust (over 21) → instant loss, bet gone.\n\n"
        "*Basic strategy cheat sheet:*\n"
        f"{BUL} Total ≤ 11 → always Hit (impossible to bust on one card).\n"
        f"{BUL} Total 12–16 → Hit if dealer shows 7+, Stand if dealer shows 2–6.\n"
        f"{BUL} Total 17+ → always Stand.\n"
        f"{BUL} Soft hand (Ace = 11) → Hit freely up to soft 17, then Stand.\n\n"
        "_Even perfect strategy has variance — that's the game._"
    ),
    "quizbattle": (
        f"🧠 *QUIZ BATTLE — RULEBOOK*\n{DIV}\n"
        "`/quizbattle` starts a 5-question timed quiz for the whole group.\n"
        f"{BUL} First correct answer typed each round scores the points.\n"
        f"{BUL} Highest total score after 5 questions wins.\n"
        "`/quizbattle end` stops the match early."
    ),
    "tnd": (
        f"🎭 *TRUTH OR DARE (LOBBY) — RULEBOOK*\n{DIV}\n"
        "`/tnd` opens a lobby, others join with `/tnd join`.\n"
        "`/tnd start` (host only) once you have 2+ players.\n"
        f"{BUL} Players take turns choosing Truth, Dare, or Would You Rather.\n"
        f"{BUL} `/tnd next` advances to the next player's turn.\n"
        "`/tnd leave` `/tnd end`\n\n"
        "_Just want an instant one-off? Use `/truth`, `/dare`, or `/wyr` any time —_\n"
        "_no lobby needed._"
    ),
    "fastmath": (
        f"⚡ *FAST MATH — RULEBOOK*\n{DIV}\n"
        "`/fastmath` starts a 5-round math race for the whole group.\n"
        f"{BUL} A problem is posted — first correct answer typed wins the round.\n"
        f"{BUL} 30 seconds per round.\n"
        "`/fastmath end` stops the match early."
    ),
    "pvp": (
        f"⚔️ *ANIMAL PVP — RULEBOOK*\n{DIV}\n"
        "Reply to someone with `/pvp <bet>` to challenge their zoo team.\n"
        f"{BUL} Set your team first with `/setteam <animal1, animal2, animal3>`.\n"
        f"{BUL} Team power (plus your weapon) decides the battle odds.\n"
        f"{BUL} Bet is optional — winner takes the loser's stake if one was set."
    ),
    "mystery": (
        f"🔮 *ORACLE CHRONICLES — HOW TO PLAY*\n{DIV}\n"
        "A new AI-generated murder mystery launches every Monday midnight IST "
        "and runs all week. Your group are detectives. Solve it before anyone else.\n\n"
        "*📅 Weekly rhythm:*\n"
        f"{BUL} *Monday* — new case drops. Crime scene photo, victim bio, 6 suspects.\n"
        f"{BUL} *Daily 8am* — one document: newspaper → forensic report → witness "
        "statement → private document → police file → anonymous letter → final revelation. "
        "Each has a daily cipher embedded in it.\n"
        f"{BUL} *Every 4 hours* — a live breaking update (some real, some red herrings).\n"
        f"{BUL} *Thursday* — Nexus digest of clues confirmed by 3+ groups.\n"
        f"{BUL} *Sunday noon* — 12-hour closing warning.\n\n"
        "*🗺️ Exploring:*\n"
        f"{BUL} `/goto <location>` — travel to one of 12 locations. See what's there "
        "and which suspects are present right now.\n"
        f"{BUL} `/examine <item_id>` — examine an object for clues. Key items auto-add "
        "to your evidence board. Some items are locked until you find another item first.\n"
        f"{BUL} Suspects follow a schedule — they're only in certain locations at "
        "certain times. Miss the window, miss the interrogation.\n\n"
        "*🤖 Interrogating suspects:*\n"
        f"{BUL} `/interrogate <FirstName> <question>` — the suspect is a real AI "
        "responding in full character. They lie consistently if their character lies.\n"
        f"{BUL} Costs 15 investigation points per question.\n"
        f"{BUL} Stress rises with each question (0→100). At 75+ stress, cracks appear.\n"
        f"{BUL} `/suspects` — see all six suspects and their live stress meters.\n\n"
        "*🔐 Daily ciphers:*\n"
        f"{BUL} Day 1 Caesar · Day 2 Atbash · Day 3 Numbers · Day 4–5 Vigenère "
        "(key hidden in the document) · Day 6 Rail Fence · Day 7 Acrostic.\n"
        f"{BUL} `/decode <answer>` — correct = +25 investigation points + clue logged.\n\n"
        "*📋 Your tools:*\n"
        f"{BUL} `/evidence` — your group's full clue board.\n"
        f"{BUL} `/timeline add HH:MM <event>` — build the murder timeline together.\n"
        f"{BUL} `/stakeout <location>` — confirm a suspect's movements in next window.\n"
        f"{BUL} `/casefile` — download your full case file as a document.\n"
        f"{BUL} `/oraclehint` — spend 30 pts for a cryptic Socratic nudge.\n\n"
        "*🌐 Cross-group Nexus:*\n"
        f"{BUL} `/nexus view` — see clues shared by all other groups.\n"
        f"{BUL} `/nexus post <clue>` — share intel publicly (30 🪙). Earn 15 🪙 "
        "each time another group confirms it.\n"
        f"{BUL} `/nexus confirm <id>` — verify another group's clue. 3 confirmations "
        "= globally verified.\n\n"
        "*🎯 Accusing:*\n"
        f"{BUL} `/accuse <Name> <weapon> <location> <motive>`\n"
        f"{BUL} Example: `/accuse Edgar prussic_acid study inheritance`\n"
        f"{BUL} Scored on all 4 fields independently — partial feedback given.\n"
        f"{BUL} Max 2 accusations per day. Correct on all 4 = case solved!\n\n"
        "*🏆 Prizes:*\n"
        f"{BUL} 1st solve → *80,000 🪙* · 2nd → *45,000 🪙* · 3rd → *25,000 🪙*\n"
        f"{BUL} `/mysteryboard` — live leaderboard · `/mystatus` — your snapshot\n\n"
        "_The killer is never the obvious suspect. "
        "Evidence must be cross-referenced. That's what makes it a real mystery._"
    ),
    "battle": (
        f"⚔️ *WILD BATTLE — RULEBOOK*\n{DIV}\n"
        "`/battle` sends you solo against a random wild enemy.\n"
        f"{BUL} Your equipped weapon boosts your attack power.\n"
        f"{BUL} Win for coins and gems, lose and you take a small coin penalty.\n"
        "Shares a cooldown with /hunt."
    ),
}

def _game_howto(key: str) -> str:
    return GAME_RULES.get(key, "No rulebook found for this game yet.")

async def cmd_traitor(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    user    = update.message.from_user
    uid     = user.id
    # _safe_md on BOTH branches: @usernames can have underscores which break
    # Markdown bold (*name*) just as badly as special chars in full_names.
    name    = _safe_md(f"@{user.username}" if user.username else user.full_name)
    sub     = context.args[0].lower() if context.args else ""

    if sub == "howto":
        await update.message.reply_text(_game_howto("traitor"), parse_mode="Markdown"); return

    # ── SHOW LOBBY STATUS ────────────────────────────────────────────────────
    if not sub:
        if chat_id in _traitor_games:
            existing = _traitor_games[chat_id]
            if existing["status"] == "active":
                await update.message.reply_text(
                    "⚠️ A game is *in progress!* `/traitor end` to stop.",
                    parse_mode="Markdown"); return
            if existing["status"] == "lobby":
                pl = "\n".join(f"  ✧ {n}" for n in existing["players"].values())
                await update.message.reply_text(
                    f"🕵️‍♂️ Lobby exists!\n👑 Host: *{existing.get('host_name','?')}*\n"
                    f"👥 Players ({len(existing['players'])}):\n{pl}\n\n"
                    f"`/traitor join` | host: `/traitor start`", parse_mode="Markdown"); return

        _traitor_games[chat_id] = {
            "players": {uid: name}, "status": "lobby",
            "host_id": uid, "host_name": name,
        }
        await update.message.reply_text(
            f"🕵️‍♂️ *Who's the Traitor — Lobby Created!*\n"
            f"👑 Host: *{name}*\n\n"
            f"`/traitor join` | `/traitor start` (3+ players needed)\n\n"
            f"*Traitor scaling:*\n"
            f"  3-5 players → 1 traitor\n"
            f"  6-8 players → 2 traitors\n"
            f"  9-12 players → 3 traitors\n"
            f"  13+ players → 4 traitors",
            parse_mode="Markdown")

    elif sub == "join":
        if chat_id not in _traitor_games:
            await update.message.reply_text("❌ No lobby! Use /traitor."); return
        game = _traitor_games[chat_id]
        if game["status"] != "lobby": await update.message.reply_text("⚠️ Already started!"); return
        if len(game["players"]) >= TRAITOR_MAX_PLAYERS:
            await update.message.reply_text(f"❌ Full! Max {TRAITOR_MAX_PLAYERS}."); return
        if uid in game["players"]: await update.message.reply_text(f"✅ {name} already in!"); return
        game["players"][uid] = name
        await update.message.reply_text(f"✅ *{name}* joined! ({len(game['players'])} players)", parse_mode="Markdown")

    elif sub == "leave":
        if chat_id not in _traitor_games: return
        game = _traitor_games[chat_id]
        game["players"].pop(uid, None)
        await update.message.reply_text(f"👋 {name} left.")

    elif sub == "end":
        if chat_id not in _traitor_games: return
        game = _traitor_games[chat_id]
        if uid == game.get("host_id") or await is_admin(context.bot, chat_id, uid):
            _cancel_traitor_jobs(context, chat_id)
            _traitor_games.pop(chat_id, None)
            await update.message.reply_text("🕵️‍♂️ Traitor game ended.")
        else:
            await update.message.reply_text("❌ Host or admin only.")

    elif sub == "start":
        if chat_id not in _traitor_games:
            await update.message.reply_text("❌ No lobby! Use /traitor."); return
        game = _traitor_games[chat_id]
        if game["status"] == "active": await update.message.reply_text("⚠️ Already running!"); return
        if uid != game.get("host_id") and not await is_admin(context.bot, chat_id, uid):
            await update.message.reply_text("❌ Host only can start!"); return
        if len(game["players"]) < 3: await update.message.reply_text("❌ Need 3+ players."); return

        await _launch_traitor_round(context, chat_id, game, is_new_game=True)

async def _traitorvote_job(context: ContextTypes.DEFAULT_TYPE):
    """Proper async job callback for starting traitor DM polls.
    Replaces the old `lambda ctx: asyncio.ensure_future(...)` pattern which
    was silently swallowing every exception (PTB v20 expects an async def, not
    a sync lambda — ensure_future tasks have no error handler attached)."""
    chat_id = context.job.data["chat_id"]
    await _start_traitor_dm_polls(context, chat_id)


async def _traitortally_job(context: ContextTypes.DEFAULT_TYPE):
    """Proper async job callback for tallying traitor votes.
    Same fix as _traitorvote_job — this is why vote results never posted back
    to the group: the resolve coroutine was being fire-and-forgotten via
    ensure_future and any exception inside it vanished without a trace."""
    chat_id = context.job.data["chat_id"]
    await _resolve_traitor_round(context, chat_id)


async def _launch_traitor_round(context, chat_id, game, is_new_game=False):
    """Start a new round (or the whole game). Assigns new words each round."""
    player_list  = list(game["players"].keys())
    n_traitors   = _traitor_count(len(player_list))
    traitor_ids  = random.sample(player_list, min(n_traitors, len(player_list)))
    word         = _get_next_traitor_word(chat_id)

    game["traitor_ids"] = traitor_ids
    game["word"]        = word
    game["status"]      = "active"
    game["votes"]       = {}
    game["dm_polls"]    = {}     # uid → {poll_id, voted_for}
    game["eliminated"]  = game.get("eliminated", [])
    game["round"]       = game.get("round", 0) + 1 if not is_new_game else 1

    dm_failures = []
    for p_uid in player_list:
        is_traitor = p_uid in traitor_ids
        if is_traitor:
            role_msg = (
                f"🕵️‍♂️ *{fancy('YOU ARE A TRAITOR!')}* (Round {game['round']})\n\n"
                f"You do NOT know the secret word.\n"
                f"Blend in during discussion — guess the word from context!\n\n"
                f"_There are {n_traitors} traitor(s) total._"
            )
        else:
            role_msg = (
                f"🌿 *You are INNOCENT!* (Round {game['round']})\n\n"
                f"🔑 Secret word: *{word}*\n\n"
                f"Discuss with group without saying it directly.\n"
                f"_There are {n_traitors} traitor(s) among you._"
            )
        try:
            await context.bot.send_message(p_uid, role_msg, parse_mode="Markdown")
        except TelegramError:
            dm_failures.append(game["players"].get(p_uid, str(p_uid)))

    if dm_failures:
        try:
            await context.bot.send_message(
                chat_id,
                f"⚠️ Couldn't DM: {', '.join(dm_failures)}\n"
                f"These players need to `/start` the bot in DM first!",
                parse_mode="Markdown")
        except Exception: pass

    rnd_label = f"Round {game['round']}" if not is_new_game else "Starting"
    await context.bot.send_message(
        chat_id,
        f"🕵️‍♂️ *{rnd_label}!* Roles sent via DM.\n"
        f"👥 {len(player_list)} players | 🎭 {n_traitors} traitor(s)\n\n"
        f"⏱️ {TRAITOR_DISCUSSION_SECONDS}s discussion starts NOW!\n"
        f"_Discuss the word... without saying it!_",
        parse_mode="Markdown")

    _cancel_traitor_jobs(context, chat_id)
    context.job_queue.run_once(
        _traitorvote_job,
        when=TRAITOR_DISCUSSION_SECONDS, chat_id=chat_id, name=f"traitorvote_{chat_id}",
        data={"chat_id": chat_id})


async def _start_traitor_dm_polls(context, chat_id):
    """DM each player individually with a poll — non-players cannot vote."""
    game = _traitor_games.get(chat_id)
    if not game or game["status"] != "active": return

    players     = game["players"]
    player_uids = list(players.keys())
    player_names= list(players.values())

    if len(player_uids) < 2:
        await context.bot.send_message(chat_id, "🏳️ Not enough players left — game over!")
        _traitor_games.pop(chat_id, None); return

    await context.bot.send_message(
        chat_id,
        f"🗳️ *Round {game['round']} — Voting begins!*\n"
        f"Check your DMs — you have {TRAITOR_POLL_SECONDS}s to vote!\n"
        f"_(Only active players get a poll — no outsiders!)_",
        parse_mode="Markdown")

    game["dm_polls"]     = {}
    game["dm_poll_votes"]= {}   # voter_uid → voted_for_index
    game["poll_options"] = player_uids  # maps index → uid

    dm_fail = []
    for voter_uid in player_uids:
        try:
            # Exclude self from options (you can't vote for yourself)
            options_for_voter = [n for uid, n in players.items() if uid != voter_uid]
            uids_for_voter    = [uid for uid in player_uids if uid != voter_uid]

            poll_msg = await context.bot.send_poll(
                chat_id=voter_uid,
                question=f"🕵️ Round {game['round']}: Who is the traitor?",
                options=options_for_voter,
                is_anonymous=False,
                allows_multiple_answers=False,
                open_period=TRAITOR_POLL_SECONDS,
            )
            game["dm_polls"][voter_uid] = {
                "poll_id":   poll_msg.poll.id,
                "msg_id":    poll_msg.message_id,
                "chat_id":   voter_uid,
                "options":   uids_for_voter,   # maps poll option index → uid
            }
        except TelegramError:
            dm_fail.append(players.get(voter_uid, str(voter_uid)))

    if dm_fail:
        await context.bot.send_message(
            chat_id, f"⚠️ Couldn't DM poll to: {', '.join(dm_fail)}", parse_mode="Markdown")

    context.job_queue.run_once(
        _traitortally_job,
        when=TRAITOR_POLL_SECONDS + 3, chat_id=chat_id, name=f"traitortally_{chat_id}",
        data={"chat_id": chat_id})


async def handle_traitor_vote(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles PollAnswer updates — matches DM poll answers back to the game."""
    pa      = update.poll_answer
    poll_id = pa.poll_id
    voter   = pa.user
    options = pa.option_ids
    if not options: return

    # Find which game this poll belongs to
    for gid, game in list(_traitor_games.items()):
        if game.get("status") != "active": continue
        for voter_uid, pdata in game.get("dm_polls", {}).items():
            if pdata.get("poll_id") != poll_id: continue
            # This voter's poll matched!
            chosen_index = options[0]
            target_uids  = pdata.get("options", [])
            if chosen_index < len(target_uids):
                voted_for_uid = target_uids[chosen_index]
                game.setdefault("dm_poll_votes", {})[voter.id] = voted_for_uid
                logger.info(f"Traitor vote: {voter.id} → {voted_for_uid} in chat {gid}")
            return


@with_data_lock
async def _resolve_traitor_round(context, chat_id):
    if chat_id in _resolving_chats: return
    game = _traitor_games.get(chat_id)
    if not game or game["status"] != "active": return
    _resolving_chats.add(chat_id)

    try:
        _cancel_traitor_jobs(context, chat_id)

        # Stop all DM polls
        for voter_uid, pdata in game.get("dm_polls", {}).items():
            try:
                await context.bot.stop_poll(pdata["chat_id"], pdata["msg_id"])
            except TelegramError: pass

        votes    = game.get("dm_poll_votes", {})
        players  = game["players"]

        if not votes:
            await context.bot.send_message(
                chat_id, "🤷 Nobody voted! No elimination. New round starting...", parse_mode="Markdown")
            await _start_new_traitor_round(context, chat_id, game)
            return

        # Tally votes
        tally = {}
        for voted_uid in votes.values():
            tally[voted_uid] = tally.get(voted_uid, 0) + 1

        max_votes = max(tally.values())
        leaders   = [uid for uid, cnt in tally.items() if cnt == max_votes]

        # _safe_md() every player name before embedding in Markdown — any name
        # with *, _, `, [ or ] breaks Telegram's Markdown parser and crashes
        # the entire send_message() call. This was the exact cause of the
        # "BadRequest: can't find end of the entity" error in the traitor tally.
        vote_summary = "\n".join(
            f"  {RARITY_COLORS.get('common','⬜')} {_safe_md(players.get(uid,'?'))}: *{cnt}* vote(s)"
            for uid, cnt in sorted(tally.items(), key=lambda x: -x[1])
        )

        if len(leaders) > 1:
            # TIE — new round with NEW WORD + 60s discussion
            tie_names = " & ".join(_safe_md(players.get(uid, "?")) for uid in leaders)
            await context.bot.send_message(
                chat_id,
                f"🗳️ *Vote Results — Round {game['round']}*\n{vote_summary}\n\n"
                f"🤝 *{fancy('TIE!')}* ({tie_names})\n"
                f"No elimination — starting new round with a NEW word!",
                parse_mode="Markdown")
            await asyncio.sleep(3)
            await _start_new_traitor_round(context, chat_id, game)
            return

        # Elimination
        eliminated_uid  = leaders[0]
        eliminated_name = _safe_md(players.get(eliminated_uid, "?"))
        is_traitor      = eliminated_uid in game.get("traitor_ids", [])

        game["players"].pop(eliminated_uid, None)
        if eliminated_uid in game.get("traitor_ids", []):
            game["traitor_ids"].remove(eliminated_uid)
        game.setdefault("eliminated", []).append(eliminated_uid)

        result_icon = "🕵️‍♂️" if is_traitor else "😇"
        result_word = "TRAITOR" if is_traitor else "INNOCENT"
        await context.bot.send_message(
            chat_id,
            f"🗳️ *Vote Results — Round {game['round']}*\n{vote_summary}\n\n"
            f"👢 *{eliminated_name}* eliminated!\n"
            f"{result_icon} They were *{result_word}*!\n\n"
            f"{'🎉 Good catch!' if is_traitor else '😢 Oops! An innocent was removed.'}",
            parse_mode="Markdown")

        await asyncio.sleep(2)

        # Check win conditions
        n_traitors  = len(game.get("traitor_ids", []))
        n_players   = len(game["players"])
        n_innocents = n_players - n_traitors

        if n_traitors == 0:
            # Innocents win
            _data_tr = load_data()
            for _uid in game["players"]:
                if _uid not in game.get("traitor_ids", []):
                    _u = get_user(_data_tr, _uid)
                    _u["coins"] = _u.get("coins", 0) + 25
                    _u["total_coins_ever"] = _u.get("total_coins_ever", 0) + 25
            save_data(_data_tr)
            await context.bot.send_message(
                chat_id,
                "🎉 *ALL TRAITORS CAUGHT! INNOCENTS WIN!*\n💰 Surviving innocents get *+25 🪙*!",
                parse_mode="Markdown")
            _traitor_games.pop(chat_id, None); return

        if n_traitors >= n_innocents or n_players < 2:
            # Traitors win
            _data_tr = load_data()
            for _uid in game.get("traitor_ids", []):
                if _uid in game["players"]:
                    _u = get_user(_data_tr, _uid)
                    _u["coins"] = _u.get("coins", 0) + 40
                    _u["total_coins_ever"] = _u.get("total_coins_ever", 0) + 40
            save_data(_data_tr)
            await context.bot.send_message(
                chat_id,
                "🕵️‍♂️ *TRAITORS WIN!* They took over!\n💰 Traitors get *+40 🪙*!",
                parse_mode="Markdown")
            _traitor_games.pop(chat_id, None); return

        # Continue game — new round (same players, but new word + discussion)
        await asyncio.sleep(2)
        await _start_new_traitor_round(context, chat_id, game)

    finally:
        _resolving_chats.discard(chat_id)


async def _start_new_traitor_round(context, chat_id, game):
    """Start a new voting round with new word + 60s discussion."""
    await context.bot.send_message(
        chat_id,
        f"🔄 *New round starting in 5 seconds...*\n"
        f"_Everyone gets a NEW word and NEW roles!_",
        parse_mode="Markdown")
    await asyncio.sleep(5)
    # Re-assign traitors and new word
    await _launch_traitor_round(context, chat_id, game, is_new_game=False)
# ══════════════════════════════════════════════════════════════════════════════
#  POMODORO / ASK
# ══════════════════════════════════════════════════════════════════════════════
async def cmd_pomodoro(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    mins = 25
    if context.args:
        try: mins = max(5, min(int(context.args[0]), 120))
        except Exception: pass
    user = update.message.from_user
    name = _safe_md(f"@{user.username}" if user.username else user.full_name)
    await update.message.reply_text(f"🍅 *{fancy('POMODORO STARTED!')}*\n{name} started a *{mins}-min* focus session!\n📵 Stay focused!",
                                     parse_mode="Markdown")
    context.job_queue.run_once(_pomo_done_job, when=mins * 60, name=f"pomo_{user.id}",
                                data={"chat_id": chat_id, "user_id": user.id,
                                      "uname": user.username or user.full_name, "mins": mins})

async def _pomo_done_job(context: ContextTypes.DEFAULT_TYPE):
    d = context.job.data
    await _pomo_done(context, d["chat_id"], d["user_id"], d["uname"], d["mins"])

@with_data_lock
async def _pomo_done(context, chat_id, user_id, uname, mins):
    reward = mins // 5 * 10
    data = load_data(); u = get_user(data, user_id)
    u["coins"] += reward; u["total_coins_ever"] = u.get("total_coins_ever", 0) + reward
    save_data(data)
    name = f"@{uname}" if not str(uname).startswith("@") else uname
    try:
        await context.bot.send_message(chat_id, f"🍅 *{fancy('DONE!')}* {name} completed *{mins} min* focus! +{reward} 🪙", parse_mode="Markdown")
    except Exception: pass

async def cmd_ask(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args: await update.message.reply_text("Usage: `/ask <your question>`", parse_mode="Markdown"); return
    question = " ".join(context.args); user = update.message.from_user
    user_name = _safe_md(f"@{user.username}" if user.username else user.full_name)
    thinking = await update.message.reply_text("🤔 thinking...")
    try:
        await context.bot.send_chat_action(update.message.chat_id, "typing")
        reply = await groq_chat(update.message.chat_id, user_name, question)
    except Exception:
        reply = random.choice(FALLBACK_REPLIES)
    await thinking.delete()
    await update.message.reply_text(reply)





# ══════════════════════════════════════════════════════════════════════════════
#  NEW FUN COMMANDS
# ══════════════════════════════════════════════════════════════════════════════
EIGHTBALL_ANSWERS = [
    "Yes, absolutely! 🔮", "100% yes.", "Signs point to yes ✨", "Don't even think about it — no.",
    "Definitely not ❌", "Not clear right now, ask again.", "Definitely maybe 😏",
    "The universe says yes.", "I'd say no.", "Trust the process — it's a yes.",
]

async def cmd_8ball(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: `/8ball <your question>`", parse_mode="Markdown"); return
    q = " ".join(context.args)
    msg = await update.message.reply_text("🔮 *Shaking the ball...*", parse_mode="Markdown")
    await asyncio.sleep(1.2)
    await msg.edit_text(f"🔮 *{q}*\n\n➡️ {random.choice(EIGHTBALL_ANSWERS)}", parse_mode="Markdown")

async def cmd_ship(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.reply_to_message and context.args:
        t = update.message.reply_to_message.from_user
        a = f"@{t.username}" if t.username else _safe_md(t.full_name)
        b = context.args[0]
    elif len(context.args) >= 2:
        a, b = context.args[0], context.args[1]
    else:
        await update.message.reply_text("Usage: `/ship @user1 @user2` (or reply to someone + `/ship @user2`)", parse_mode="Markdown"); return
    seed = "".join(sorted([a.lower(), b.lower()]))
    pct = abs(hash(seed)) % 101
    bar = "💗" * (pct // 10) + "🤍" * (10 - pct // 10)
    verdict = ("Soulmates fr 😭" if pct > 85 else "Cute pairing ngl" if pct > 60 else
               "It's giving mid" if pct > 35 else "Better as friends lol")
    await update.message.reply_text(f"💘 *{a} × {b}*\n{bar}\n*{pct}%* — {verdict}", parse_mode="Markdown")

async def cmd_fact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_text("🧠 thinking...")
    fact = await groq_raw(
        "You share one short, genuinely interesting random fact in casual English, 1-2 lines, no preamble.",
        "Give me one random fun fact.", temperature=1.1,
    )
    await msg.edit_text(f"🧠 *Random Fact:*\n{fact.strip() or 'No idea, my brain is blank right now 😅'}", parse_mode="Markdown")

async def cmd_roast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.reply_to_message:
        await update.message.reply_text("↩️ Reply to someone + `/roast` to roast them (nicely 😄)"); return
    target = update.message.reply_to_message.from_user
    tname = target.first_name or "bro"
    msg = await update.message.reply_text("🔥 thinking...")
    line = await groq_raw(
        "You write one short, funny, PLAYFUL roast in casual English for a friend group chat. "
        "Keep it light and silly, never actually mean, never about appearance/family/sensitive topics.",
        f"Roast someone named {tname} in one short funny line.", temperature=1.2,
    )
    await msg.edit_text(f"🔥 {line.strip() or f'{tname}... that one was too weak to even roast 😭'}", parse_mode="Markdown")

async def cmd_compliment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.reply_to_message:
        await update.message.reply_text("↩️ Reply to someone + `/compliment` to hype them up!"); return
    target = update.message.reply_to_message.from_user
    tname = target.first_name or "bestie"
    msg = await update.message.reply_text("💫 thinking...")
    line = await groq_raw(
        "You write one short, warm, wholesome compliment in casual English for a friend group chat.",
        f"Write a wholesome compliment for someone named {tname}.", temperature=1.1,
    )
    await msg.edit_text(f"💫 {line.strip() or f'{tname} is genuinely a good person 🫶'}", parse_mode="Markdown")

async def cmd_mood(update: Update, context: ContextTypes.DEFAULT_TYPE):
    mood = _get_mood(update.message.chat_id)
    await update.message.reply_text(f"🌤️ *Aira's current mood:*\n_{mood}_", parse_mode="Markdown")

_riddle_answers = {}  # message_id -> answer

RIDDLES = [
    ("I always come but never arrive, what am I?", "tomorrow"),
    ("The more you take, the more you leave behind. What am I?", "footsteps"),
    ("I have keys but no locks, space but no room. What am I?", "a keyboard"),
    ("What has hands but can't clap?", "a clock"),
    ("What has a face and two hands but no arms or legs?", "a clock"),
    ("What gets wetter the more it dries?", "a towel"),
    ("I'm tall when I'm young and short when I'm old. What am I?", "a candle"),
    ("What can travel around the world while staying in a corner?", "a stamp"),
    ("What has to be broken before you can use it?", "an egg"),
    ("What month of the year has 28 days?", "all of them"),
    ("What has one eye but can't see?", "a needle"),
    ("What kind of room has no doors or windows?", "a mushroom"),
    ("What runs but never walks, has a mouth but never talks?", "a river"),
    ("What can you catch but not throw?", "a cold"),
    ("What has many teeth but can't bite?", "a comb"),
    ("What goes up but never comes down?", "your age"),
    ("What is full of holes but still holds water?", "a sponge"),
    ("What has a neck but no head?", "a bottle"),
    ("What invention lets you look right through a wall?", "a window"),
    ("What can you break without touching it?", "a promise"),
    ("What has words but never speaks?", "a book"),
    ("I shrink smaller every time I take a bath. What am I?", "soap"),
    ("What building has the most stories?", "a library"),
    ("What is always in front of you but can't be seen?", "the future"),
    ("What five-letter word becomes shorter when you add two letters?", "short"),
    ("What comes once in a minute, twice in a moment, but never in a thousand years?", "the letter M"),
    ("What has a thumb and four fingers but isn't alive?", "a glove"),
    ("What can fill a room but takes up no space?", "light"),
    ("What kind of tree can you carry in your hand?", "a palm"),
    ("What is easy to get into but hard to get out of?", "trouble"),
]

JOKES = [
    "I told my computer I needed a break, and now it won't stop sending me vacation ads.",
    "Why don't scientists trust atoms? Because they make up everything.",
    "I used to be a banker, but I lost interest.",
    "Parallel lines have so much in common. It's a shame they'll never meet.",
    "I told my WiFi I loved it. It said the connection wasn't strong enough.",
    "Why did the scarecrow win an award? He was outstanding in his field.",
    "I'm reading a book on anti-gravity. It's impossible to put down.",
    "Why don't skeletons fight each other? They don't have the guts.",
    "I used to hate facial hair, but then it grew on me.",
    "Why did the coffee file a police report? It got mugged.",
    "I'm on a seafood diet. I see food and I eat it.",
    "Why don't eggs tell jokes? They'd crack each other up.",
    "I ordered a chicken and an egg online. I'll let you know which arrives first.",
    "Why did the bicycle fall over? It was two tired.",
    "My therapist says I have a preoccupation with vengeance. We'll see about that.",
    "Why can't you give Elsa a balloon? She'll let it go.",
    "I was going to tell a time-travel joke, but you guys didn't like it.",
    "Why do programmers prefer dark mode? Because light attracts bugs.",
    "I stayed up all night wondering where the sun went, then it dawned on me.",
    "Why did the math book look sad? It had too many problems.",
    "I used to play piano by ear, now I use my hands.",
    "Why don't oysters share their pearls? They're a little shellfish.",
    "I told a chemistry joke, but there was no reaction.",
    "Why did the golfer bring two pairs of pants? In case he got a hole in one.",
    "My dog used to chase people on a bike. It got so bad I had to take his bike away.",
    "Why did the tomato turn red? It saw the salad dressing.",
    "I couldn't figure out why the baseball kept getting bigger. Then it hit me.",
    "Why don't some couples go to the gym? Because some relationships don't work out.",
    "I told my plants a joke about photosynthesis. They didn't laugh, but they did grow on me.",
    "Why did the invisible man turn down the job offer? He couldn't see himself doing it.",
    "I was addicted to the hokey pokey, but I turned myself around.",
    "Why do seagulls fly over the sea? Because if they flew over the bay, they'd be bagels.",
    "What do you call cheese that isn't yours? Nacho cheese.",
    "Why did the student eat his homework? The teacher said it was a piece of cake.",
    "I'm terrified of elevators, so I'm going to start taking steps to avoid them.",
]

async def cmd_riddle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    msg = await update.message.reply_text("🧩 thinking of a riddle...")
    raw = await groq_raw(
        "You are a JSON API for a riddle game. Output ONLY valid JSON, no markdown fences.",
        'Give one short fun riddle. Return ONLY: {"q":"riddle text","a":"one word answer"}', temperature=1.1,
    )
    try:
        m = re.search(r"\{.*\}", raw, re.DOTALL)
        d = _json.loads(m.group(0))
        q, a = d["q"], str(d["a"]).strip()
        if not q or not a:
            raise ValueError("empty")
    except Exception:
        q, a = _draw_from_deck(chat_id, "riddle")
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("💡 Reveal Answer", callback_data="riddle_reveal")]])
    await msg.edit_text(f"🧩 *Riddle:*\n{q}", reply_markup=kb, parse_mode="Markdown")
    _riddle_answers[msg.message_id] = a

async def cmd_joke(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    joke = _draw_from_deck(chat_id, "joke")
    await update.message.reply_text(f"😂 {joke}")

async def handle_riddle_reveal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    try:
        await query.answer()
    except (BadRequest, TelegramError):
        pass  # stale/expired callback query — safe to ignore, continue handling
    ans = _riddle_answers.pop(query.message.message_id, None)
    if ans:
        await _safe_edit_message_text(query, f"{query.message.text}\n\n✅ *Answer:* {ans}", parse_mode="Markdown")
    else:
        await query.answer("Answer expired!", show_alert=True)

async def cmd_wyr(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    ai_recent = _td_ai_recent.setdefault((chat_id, "wyr"), [])
    opt_a = opt_b = None
    raw = await groq_raw(
        "You are a JSON API for a party game. Output ONLY valid JSON, no markdown fences.",
        'Give one fun "Would You Rather" question with two options for a Telegram group. '
        f'Do NOT repeat or resemble any of: {"; ".join(ai_recent[-15:]) if ai_recent else "none"}. '
        'Return ONLY: {"a":"option A","b":"option B"}', temperature=1.2,
    )
    try:
        m = re.search(r"\{.*\}", raw, re.DOTALL)
        d = _json.loads(m.group(0))
        a, b = str(d["a"]).strip(), str(d["b"]).strip()
        combo = f"{a} / {b}"
        if a and b and combo.lower() not in [u.lower() for u in ai_recent]:
            opt_a, opt_b = a, b
            ai_recent.append(combo)
            if len(ai_recent) > 25:
                ai_recent[:] = ai_recent[-25:]
    except Exception:
        pass
    if not opt_a:
        # AI failed / repeated — pull from the non-repeating deck instead
        opt_a, opt_b = _draw_from_deck(chat_id, "wyr")
    # Telegram hard-caps poll options at 100 chars — AI-generated options can
    # run longer than that and make send_poll raise BadRequest, so clip them.
    opt_a = (opt_a or "Option A").strip()[:100]
    opt_b = (opt_b or "Option B").strip()[:100]
    await update.message.reply_poll(question="🤔 Would you rather...", options=[opt_a, opt_b],
                                     is_anonymous=False, allows_multiple_answers=False)

def _parse_duration(text):
    m = re.match(r"^(\d+)\s*(m|min|mins|h|hr|hrs|hour|hours|d|day|days)$", text.lower())
    if not m: return None
    n, unit = int(m.group(1)), m.group(2)
    if unit.startswith("m"): return n * 60
    if unit.startswith("h"): return n * 3600
    return n * 86400

async def cmd_remindme(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 2:
        await update.message.reply_text("Usage: `/remindme 10m Take a break` (units: m/h/d)", parse_mode="Markdown"); return
    secs = _parse_duration(context.args[0])
    if not secs or secs > 7 * 86400:
        await update.message.reply_text("❌ Use a valid duration like `10m`, `2h`, `1d` (max 7d)."); return
    reminder_text = " ".join(context.args[1:])
    user_id = update.message.from_user.id
    context.job_queue.run_once(_send_reminder, when=secs, name=f"remind_{user_id}_{int(datetime.now().timestamp())}",
        data={"user_id": user_id, "text": reminder_text})
    await update.message.reply_text(f"⏰ Got it! I'll remind you in *{context.args[0]}*: _{reminder_text}_", parse_mode="Markdown")

async def _send_reminder(context: ContextTypes.DEFAULT_TYPE):
    d = context.job.data
    try:
        await context.bot.send_message(d["user_id"], f"⏰ *Reminder!*\n{_safe_md(d['text'])}", parse_mode="Markdown")
    except TelegramError:
        pass



# ══════════════════════════════════════════════════════════════════════════════
#  NEW MINI-GAME #8 — ⚡ FAST MATH (/fastmath)
#  Group speed arithmetic — 5 rounds, first correct answer wins 15 coins each.
#  Most correct answers at end gets a 30 coin bonus!
# ══════════════════════════════════════════════════════════════════════════════
_fastmath_games = {}  # chat_id -> {answer, scores, names, round, total_rounds}

def _gen_math_problem():
    op = random.choice(['+', '-', '*'])
    if op == '+':
        a, b = random.randint(10, 99), random.randint(10, 99)
        return f"{a} + {b}", a + b
    elif op == '-':
        a, b = random.randint(20, 99), random.randint(1, 20)
        return f"{a} - {b}", a - b
    else:
        a, b = random.randint(2, 12), random.randint(2, 12)
        return f"{a} × {b}", a * b

async def cmd_fastmath(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    sub = (context.args[0].lower() if context.args else "")
    if sub == "howto":
        await update.message.reply_text(_game_howto("fastmath"), parse_mode="Markdown"); return
    if sub == "end":
        if chat_id in _fastmath_games:
            for job in context.job_queue.get_jobs_by_name(f"fm_{chat_id}"): job.schedule_removal()
            _fastmath_games.pop(chat_id, None)
            await update.message.reply_text("⚡ Fast Math ended early. Thanks for playing! 🙌")
        else:
            await update.message.reply_text("❌ No active Fast Math game here.")
        return
    if chat_id in _fastmath_games:
        await update.message.reply_text("⚡ Fast Math already running! Wait for it to finish."); return
    q, ans = _gen_math_problem()
    _fastmath_games[chat_id] = {"answer": ans, "scores": {}, "names": {}, "round": 1, "total_rounds": 5}
    await update.message.reply_text(
        f"⚡ ✦ *FAST MATH — Round 1/5* ✦\n┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄\n"
        f"🧮 *{q} = ?*\n\n"
        f"First correct answer wins *15 🪙*!\n_30 seconds to answer!_",
        parse_mode="Markdown")
    context.job_queue.run_once(
        _fastmath_timeout, when=30, chat_id=chat_id,
        name=f"fm_{chat_id}", data={"chat_id": chat_id, "round": 1})

@with_data_lock
async def _fastmath_try(update: Update, context: ContextTypes.DEFAULT_TYPE, chat_id: int, text: str) -> bool:
    game = _fastmath_games.get(chat_id)
    if not game: return False
    try:
        ans = int(text.strip())
    except Exception:
        return False
    if ans != game["answer"]: return False

    # Correct answer!
    user  = update.message.from_user
    uid   = user.id
    uname = _safe_md(f"@{user.username}" if user.username else user.full_name)
    game["scores"][uid] = game["scores"].get(uid, 0) + 1
    game["names"][uid]  = uname
    for job in context.job_queue.get_jobs_by_name(f"fm_{chat_id}"): job.schedule_removal()

    data = load_data(); u = get_user(data, user.id, user.username, user.full_name)
    u["coins"] = u.get("coins", 0) + 15; u["total_coins_ever"] = u.get("total_coins_ever", 0) + 15; save_data(data)

    rnd = game["round"]
    if rnd >= game["total_rounds"]:
        await _fastmath_end(context, chat_id, f"✅ *{uname}* solved it! Answer: *{game['answer']}*")
    else:
        game["round"] += 1
        q, new_ans = _gen_math_problem()
        game["answer"] = new_ans
        await update.message.reply_text(
            f"✅ *{uname}* got it! (+15 🪙)\n\n"
            f"⚡ *Round {game['round']}/5*\n🧮 *{q} = ?*\n_30 seconds!_",
            parse_mode="Markdown")
        context.job_queue.run_once(
            _fastmath_timeout, when=30, chat_id=chat_id,
            name=f"fm_{chat_id}", data={"chat_id": chat_id, "round": game["round"]})
    return True

async def _fastmath_timeout(context: ContextTypes.DEFAULT_TYPE):
    d       = context.job.data
    chat_id = d["chat_id"]
    game    = _fastmath_games.get(chat_id)
    if not game or game["round"] != d["round"]: return

    prev_ans = game["answer"]
    rnd      = game["round"]
    timeout_line = f"⏱️ Time's up! Answer was *{prev_ans}*"
    if rnd >= game["total_rounds"]:
        await _fastmath_end(context, chat_id, timeout_line)
    else:
        game["round"] += 1
        q, new_ans = _gen_math_problem()
        game["answer"] = new_ans
        try:
            await context.bot.send_message(
                chat_id,
                f"{timeout_line}\n\n⚡ *Round {game['round']}/5*\n🧮 *{q} = ?*\n_30 seconds!_",
                parse_mode="Markdown")
        except Exception:
            _fastmath_games.pop(chat_id, None); return
        context.job_queue.run_once(
            _fastmath_timeout, when=30, chat_id=chat_id,
            name=f"fm_{chat_id}", data={"chat_id": chat_id, "round": game["round"]})

@with_data_lock
async def _fastmath_end(context, chat_id: int, last_line: str):
    game = _fastmath_games.get(chat_id)
    if not game: return
    scores = game.get("scores", {})
    names  = game.get("names", {})
    lines  = [f"⚡ ✦ *FAST MATH — GAME OVER!* ✦\n┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄\n{last_line}\n\n🏆 *Scores:*"]
    sorted_s = sorted(scores.items(), key=lambda x: -x[1])
    medals   = ["🥇","🥈","🥉","4️⃣","5️⃣"]
    for i, (uid, pts) in enumerate(sorted_s[:5]):
        lines.append(f"{medals[i]} {_safe_md(names.get(uid, str(uid)))}: {pts} pts")
    if not sorted_s:
        lines.append("Nobody scored!")
    else:
        winner_id, top_pts = sorted_s[0]
        if top_pts >= 3:
            d2 = load_data(); wu = get_user(d2, winner_id)
            wu["coins"] = wu.get("coins",0)+30; wu["total_coins_ever"] = wu.get("total_coins_ever",0)+30; save_data(d2)
            lines.append(f"\n🏆 *{_safe_md(names.get(winner_id,'?'))}* wins the bonus! *+30 🪙*")
    try:
        await context.bot.send_message(chat_id, "\n".join(lines), parse_mode="Markdown")
    except Exception: pass
    _fastmath_games.pop(chat_id, None)

# ══════════════════════════════════════════════════════════════════════════════
#  NEW GAME #9 — 🐺 WEREWOLF (/wolf)
#  Villagers vs Werewolves — Night kills, Day votes. Last side standing wins!
# ══════════════════════════════════════════════════════════════════════════════
_wolf_games = {}  # chat_id -> game dict

async def cmd_wolf(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    user    = update.message.from_user
    name    = _safe_md(f"@{user.username}" if user.username else user.full_name)
    sub     = (context.args[0].lower() if context.args else "join")

    # ── HOW TO PLAY ───────────────────────────────────────────────────────────
    if sub == "howto" or sub == "help" or sub == "rules":
        await update.message.reply_text(
            "🐺 ✦ *HOW TO PLAY WEREWOLF* ✦\n┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄\n\n"
            "*SETUP*\n"
            "✧ 4+ players needed. Each gets a secret role via DM.\n"
            "✧ Roles: 🐺 *Werewolf* (1 per 4 players) or 🌾 *Villager*\n\n"
            "*NIGHT PHASE* 🌙\n"
            "✧ Wolves secretly `/wolf kill @name` in GROUP CHAT\n"
            "✧ All wolves must agree (most voted target dies)\n"
            "✧ 60 seconds — wolves must decide!\n\n"
            "*DAY PHASE* ☀️\n"
            "✧ Dead player's role is revealed\n"
            "✧ Everyone discusses who they think is the wolf\n"
            "✧ ALL alive players do `/wolf vote @name`\n"
            "✧ Most voted player is eliminated\n"
            "✧ 90 seconds for discussion + voting\n\n"
            "*WIN CONDITIONS*\n"
            "✧ 🌾 Villagers win: eliminate ALL wolves\n"
            "✧ 🐺 Wolves win: equal/outnumber villagers\n\n"
            "*COMMANDS*\n"
            "`/wolf` — Create lobby\n"
            "`/wolf join` — Join the lobby\n"
            "`/wolf go` — Host starts game (4+ joined)\n"
            "`/wolf kill @name` — Night: wolves kill\n"
            "`/wolf vote @name` — Day: vote to eliminate\n"
            "`/wolf end` — End game (admin/host)\n\n"
            "*REWARDS*\n"
            "🐺 Wolves win: +60 🪙 per wolf\n"
            "🌾 Villagers win: +45 🪙 per villager\n\n"
            "_Tip: Wolves should act natural during the day!_ 🕵️",
            parse_mode="Markdown")
        return
  
  
    # ── END GAME ─────────────────────────────────────────────────────────────
    if sub == "end":
        # BUGFIX: `/wolf end` was documented in /wolf howto but never actually
        # handled — it fell into the join/create-lobby branch below (since
        # "end" wasn't excluded from that catch-all condition), so it
        # silently tried to open a NEW lobby instead of ending anything.
        if chat_id not in _wolf_games:
            await update.message.reply_text("❌ No active Werewolf game here."); return
        game = _wolf_games[chat_id]
        if user.id == game.get("host") or await is_admin(context.bot, chat_id, user.id) or user.id in OWNER_IDS:
            for job_name in (f"wolf_night_{chat_id}", f"wolf_day_{chat_id}"):
                for job in context.job_queue.get_jobs_by_name(job_name): job.schedule_removal()
            _wolf_games.pop(chat_id, None)
            await update.message.reply_text("🐺 Werewolf game ended.")
        else:
            await update.message.reply_text("❌ Host or admin only.")
        return

    # ── OPEN / JOIN LOBBY ────────────────────────────────────────────────────
    if sub in ("join", "start") or sub not in ("go", "kill", "vote", "status"):
        if chat_id in _wolf_games and _wolf_games[chat_id]["status"] not in ("lobby",):
            await update.message.reply_text("🐺 Game already running!"); return
        if chat_id not in _wolf_games:
            _wolf_games[chat_id] = {"status": "lobby", "players": {user.id: name}, "host": user.id}
            await update.message.reply_text(
                f"🐺 *{fancy('WEREWOLF LOBBY!')}*\n{name} opened the game!\n\n"
                f"Join: `/wolf` | Min 4 players\n"
                f"Host starts: `/wolf go`",
                parse_mode="Markdown"); return
        game = _wolf_games[chat_id]
        if game["status"] != "lobby":
            await update.message.reply_text("❌ Game already started!"); return
        if user.id in game["players"]:
            await update.message.reply_text(f"✅ {name} already in lobby!"); return
        game["players"][user.id] = name
        count = len(game["players"])
        await update.message.reply_text(
            f"✅ *{name}* joined! ({count}/4+ needed)\n"
            f"{'Ready! `/wolf go`' if count >= 4 else f'Need {4-count} more...'}",
            parse_mode="Markdown"); return

    # ── START GAME ───────────────────────────────────────────────────────────
    if sub == "go":
        if chat_id not in _wolf_games:
            await update.message.reply_text("❌ No lobby yet — start one with `/wolf` first."); return
        game = _wolf_games[chat_id]
        if game["status"] != "lobby":
            await update.message.reply_text("❌ Already started!"); return
        if user.id != game["host"] and user.id not in OWNER_IDS:
            await update.message.reply_text("❌ Only the host can start!"); return
        players = game["players"]
        if len(players) < 4:
            await update.message.reply_text("❌ Need at least 4 players!"); return

        uids      = list(players.keys())
        n_wolves  = max(1, len(uids) // 4)
        wolves    = set(random.sample(uids, n_wolves))
        game.update({
            "status":      "night",
            "roles":       {uid: ("wolf" if uid in wolves else "villager") for uid in uids},
            "alive":       list(uids),
            "night_votes": {},
            "day_votes":   {},
            "round":       1,
        })

        failed = []
        for uid, pname in players.items():
            role  = game["roles"][uid]
            allies = [players[w] for w in wolves if w != uid]
            try:
                if role == "wolf":
                    ally_str = f"\nAllies: {', '.join(allies)}" if allies else "\nYou're the lone wolf!"
                    await context.bot.send_message(uid,
                        f"🐺 *{fancy('YOU ARE A WEREWOLF!')}*{ally_str}\n\n"
                        f"Night phase: `/wolf kill @name` in group chat.", parse_mode="Markdown")
                else:
                    await context.bot.send_message(uid,
                        f"🌾 *You are a VILLAGER!*\n\n"
                        f"Find the werewolves! Day vote: `/wolf vote @name`",
                        parse_mode="Markdown")
            except TelegramError:
                failed.append(pname)

        warn  = f"\n⚠️ Couldn't DM: {', '.join(failed)}" if failed else ""
        plist = "\n".join(f"  👤 {n}" for n in players.values())
        await update.message.reply_text(
            f"🐺 ✦ *{fancy('WEREWOLF STARTED!')}* ✦\n┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄\n*Players:*\n{plist}\n\n"
            f"🌙 *Night Phase — Round 1*\n"
            f"Wolves: `/wolf kill @name` | Timer: 60s{warn}",
            parse_mode="Markdown")
        context.job_queue.run_once(
            _wolf_night_end, when=60, chat_id=chat_id,
            name=f"wolf_night_{chat_id}", data={"chat_id": chat_id})
        return

    # ── NIGHT KILL (wolves only) ──────────────────────────────────────────────
    if sub == "kill":
        if chat_id not in _wolf_games or _wolf_games[chat_id].get("status") != "night":
            await update.message.reply_text("☀️ It's not the night phase right now!"); return
        game = _wolf_games[chat_id]
        if game["roles"].get(user.id) != "wolf" or user.id not in game["alive"]:
            await update.message.reply_text("❌ Wolves only!"); return
        if not context.args[1:]:
            await update.message.reply_text("Usage: `/wolf kill @name`"); return
        t_name = context.args[1].lstrip("@").lower()
        t_id   = next((uid for uid, n in game["players"].items()
                       if n.lstrip("@").lower() == t_name
                       and uid in game["alive"]
                       and game["roles"].get(uid) != "wolf"), None)
        if not t_id:
            await update.message.reply_text("❌ Target not found (or is a wolf/dead)!"); return
        game["night_votes"][user.id] = t_id
        await update.message.reply_text(f"🌙 Vote recorded. ({len(game['night_votes'])} wolf votes)")
        return

    # ── DAY VOTE ─────────────────────────────────────────────────────────────
    if sub == "vote":
        if chat_id not in _wolf_games or _wolf_games[chat_id].get("status") != "day":
            await update.message.reply_text("🌙 It's not the day phase right now!"); return
        game = _wolf_games[chat_id]
        if user.id not in game["alive"]:
            await update.message.reply_text("❌ Dead players can't vote!"); return
        if not context.args[1:]:
            await update.message.reply_text("Usage: `/wolf vote @name`"); return
        t_name = context.args[1].lstrip("@").lower()
        t_id   = next((uid for uid, n in game["players"].items()
                       if n.lstrip("@").lower() == t_name and uid in game["alive"]), None)
        if not t_id:
            await update.message.reply_text("❌ Player not found or eliminated!"); return
        game["day_votes"][user.id] = t_id
        voted = len(game["day_votes"]); alive_c = len(game["alive"])
        await update.message.reply_text(f"🗳️ {name} voted! ({voted}/{alive_c})")
        if voted >= alive_c:
            for job in context.job_queue.get_jobs_by_name(f"wolf_day_{chat_id}"):
                job.schedule_removal()
            await _wolf_day_tally(context, chat_id)
        return

async def _wolf_night_end(context: ContextTypes.DEFAULT_TYPE):
    chat_id = context.job.data["chat_id"]
    game    = _wolf_games.get(chat_id)
    if not game or game.get("status") != "night":
        return
    night_votes = game.get("night_votes", {})
    killed_id   = None
    if night_votes:
        tally     = {}
        for t in night_votes.values(): tally[t] = tally.get(t,0)+1
        killed_id = max(tally, key=tally.get)

    game["status"]      = "day"
    game["day_votes"]   = {}
    game["night_votes"] = {}
    game["round"]       = game.get("round",1)+1

    msg = "☀️ ✦ *DAWN BREAKS...* ✦\n┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄\n"
    if killed_id and killed_id in game["alive"]:
        game["alive"].remove(killed_id)
        msg += f"💀 *{_safe_md(game['players'][killed_id])}* was killed! They were a *{game['roles'][killed_id].upper()}*.\n"
    else:
        msg += "😮 Nobody died last night — the wolves hesitated!\n"

    wolves_alive    = [uid for uid in game["alive"] if game["roles"][uid] == "wolf"]
    villagers_alive = [uid for uid in game["alive"] if game["roles"][uid] == "villager"]

    if not wolves_alive:
        await _wolf_end(context, chat_id, "villagers", msg + "\n🏆 *VILLAGERS WIN!* All wolves eliminated!")
        return
    if len(wolves_alive) >= len(villagers_alive):
        await _wolf_end(context, chat_id, "wolves", msg + "\n🐺 *WEREWOLVES WIN!* They've taken over!")
        return

    alive_list = "\n".join(f"  👤 {game['players'][uid]}" for uid in game["alive"])
    msg += f"\n*Alive ({len(game['alive'])}):*\n{alive_list}\n\n🗣️ Discuss! `/wolf vote @name` — 90s to vote."
    try:
        await context.bot.send_message(chat_id, msg, parse_mode="Markdown")
    except Exception: pass
    context.job_queue.run_once(
        _wolf_day_timeout, when=90, chat_id=chat_id,
        name=f"wolf_day_{chat_id}", data={"chat_id": chat_id})

async def _wolf_day_timeout(context: ContextTypes.DEFAULT_TYPE):
    chat_id = context.job.data["chat_id"]
    if chat_id not in _wolf_games: return
    try:
        await context.bot.send_message(chat_id, "⏰ *Voting time's up!* Tallying...", parse_mode="Markdown")
    except Exception: pass
    await _wolf_day_tally(context, chat_id)

async def _wolf_day_tally(context, chat_id):
    game = _wolf_games.get(chat_id)
    if not game or game.get("status") != "day": return

    day_votes    = game.get("day_votes", {})
    elim_id      = None
    if day_votes:
        tally   = {}
        for t in day_votes.values(): tally[t] = tally.get(t,0)+1
        elim_id = max(tally, key=tally.get)

    msg = "🗳️ ✦ *VOTE RESULTS* ✦\n┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄\n"
    if elim_id and elim_id in game["alive"]:
        game["alive"].remove(elim_id)
        msg += f"👢 *{_safe_md(game['players'][elim_id])}* eliminated! They were a *{game['roles'][elim_id].upper()}*.\n"
    else:
        msg += "No consensus — nobody eliminated!\n"

    wolves_alive    = [uid for uid in game["alive"] if game["roles"][uid] == "wolf"]
    villagers_alive = [uid for uid in game["alive"] if game["roles"][uid] == "villager"]

    if not wolves_alive:
        await _wolf_end(context, chat_id, "villagers", msg + "\n🏆 *VILLAGERS WIN!*"); return
    if len(wolves_alive) >= len(villagers_alive):
        await _wolf_end(context, chat_id, "wolves", msg + "\n🐺 *WEREWOLVES WIN!*"); return

    game["status"]      = "night"
    game["night_votes"] = {}
    alive_list = "\n".join(f"  👤 {game['players'][uid]}" for uid in game["alive"])
    msg += f"\n*Alive:*\n{alive_list}\n\n🌙 Night falls... Wolves: `/wolf kill @name` — 60s!"
    try:
        await context.bot.send_message(chat_id, msg, parse_mode="Markdown")
    except Exception: pass
    context.job_queue.run_once(
        _wolf_night_end, when=60, chat_id=chat_id,
        name=f"wolf_night_{chat_id}", data={"chat_id": chat_id})

@with_data_lock
async def _wolf_end(context, chat_id, winner, msg):
    game = _wolf_games.get(chat_id)
    if not game: return
    data   = load_data()
    reward = 60 if winner == "wolves" else 45
    winning_role = "wolf" if winner == "wolves" else "villager"
    for uid in game["alive"]:
        if game["roles"].get(uid) == winning_role:
            u = get_user(data, uid); u["coins"] = u.get("coins",0)+reward
            u["total_coins_ever"] = u.get("total_coins_ever",0)+reward
    save_data(data)
    reveal = "\n\n🔍 *Role Reveal:*\n" + "\n".join(
        f"  {'🐺' if game['roles'][uid]=='wolf' else '🌾'} {_safe_md(game['players'][uid])}"
        for uid in game["players"]
    )
    try:
        await context.bot.send_message(
            chat_id, msg + f"\n💰 Winners get *+{reward} 🪙*!" + reveal, parse_mode="Markdown")
    except Exception: pass
    _wolf_games.pop(chat_id, None)



  # ══════════════════════════════════════════════════════════════════════════════
#  LAST CALL — Alibi deduction game
#  Each player gets a time+location alibi. Killer's is fake (+ 1-2 innocents).
#  Players /lastcall verify <name> (costs 500 coins) to check alibis.
#  After N rounds of discussion, players vote to identify the Killer.
# ══════════════════════════════════════════════════════════════════════════════
_lastcall_games = {}  # chat_id → game state

LASTCALL_LOCATIONS = [
    "Mall food court", "Cinema hall", "Library", "Coffee shop",
    "Gym", "Park", "Supermarket", "Bus stop", "Hospital canteen",
    "Friend's house", "Restaurant", "ATM", "College canteen",
    "Barber shop", "Petrol pump", "Temple/mosque", "Book store",
]
LASTCALL_TIMES = [
    "8:00 AM","9:30 AM","11:00 AM","12:30 PM","2:00 PM",
    "3:30 PM","5:00 PM","6:30 PM","8:00 PM","9:30 PM","11:00 PM",
]
LASTCALL_VERIFY_COST = 500

@with_data_lock
async def cmd_lastcall(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    user    = update.message.from_user
    uid     = user.id
    name    = _safe_md(f"@{user.username}" if user.username else user.full_name)
    sub     = (context.args[0].lower() if context.args else "")

    if sub == "howto":
        await update.message.reply_text(
            "🔍 ✦ *LAST CALL — HOW TO PLAY* ✦\n┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄\n\n"
            "1. 3+ players start a game\n"
            "2. Everyone gets an alibi (time + place) via DM\n"
            "3. The *Killer's* alibi is FAKE (+ 1-2 red herrings)\n"
            "4. Discuss alibis openly in chat\n"
            "5. Spend 500 🪙 to `/lastcall verify @name` — get Real/Fake\n"
            "6. After discussion, `/lastcall accuse @name` to vote\n"
            "7. Most accused = eliminated\n\n"
            "🏆 Killer wins if undetected after 3 rounds\n"
            "🏆 Innocents win if they catch the Killer!\n\n"
            "`/lastcall join` | `/lastcall start` | `/lastcall verify @name`\n"
            "`/lastcall accuse @name` | `/lastcall end`",
            parse_mode="Markdown")
        return

    if not sub:
        if chat_id in _lastcall_games and _lastcall_games[chat_id]["status"] in ("lobby","active"):
            g = _lastcall_games[chat_id]
            pl = "\n".join(f"  ✧ {n}" for n in g["players"].values())
            await update.message.reply_text(
                f"🔍 *Last Call Lobby* ({g['status']})\n{pl}\n"
                f"`/lastcall join` | host: `/lastcall start`", parse_mode="Markdown")
            return
        _lastcall_games[chat_id] = {
            "players": {uid: name}, "status": "lobby",
            "host_id": uid, "round": 0,
        }
        await update.message.reply_text(
            f"🔍 *LAST CALL — Lobby Created!*\n"
            f"👑 Host: *{name}*\n"
            f"`/lastcall join` to join | `/lastcall start` when ready\n"
            f"`/lastcall howto` for rules",
            parse_mode="Markdown")

    elif sub == "join":
        if chat_id not in _lastcall_games:
            await update.message.reply_text("❌ No lobby! `/lastcall`"); return
        g = _lastcall_games[chat_id]
        if g["status"] != "lobby": await update.message.reply_text("⚠️ Game already started!"); return
        if uid in g["players"]: await update.message.reply_text("✅ You're already in!"); return
        g["players"][uid] = name
        await update.message.reply_text(f"✅ {name} joined! ({len(g['players'])} players)")

    elif sub == "start":
        if chat_id not in _lastcall_games:
            await update.message.reply_text("❌ No lobby!"); return
        g = _lastcall_games[chat_id]
        if g["status"] != "lobby": await update.message.reply_text("⚠️ Already started!"); return
        if uid != g["host_id"] and not await is_admin(context.bot, chat_id, uid):
            await update.message.reply_text("❌ Host only!"); return
        if len(g["players"]) < 3: await update.message.reply_text("❌ Need 3+ players!"); return

        player_uids = list(g["players"].keys())
        killer_uid  = random.choice(player_uids)
        n_fakes     = min(2, len(player_uids) - 2)
        fake_innocents = random.sample([u for u in player_uids if u != killer_uid], n_fakes)

        alibis = {}
        for p_uid in player_uids:
            loc  = random.choice(LASTCALL_LOCATIONS)
            time_= random.choice(LASTCALL_TIMES)
            is_real = (p_uid != killer_uid and p_uid not in fake_innocents)
            alibis[p_uid] = {"location": loc, "time": time_, "is_real": is_real}

        g.update({
            "status": "active", "killer_id": killer_uid,
            "alibis": alibis, "verifications": {},
            "accusations": {}, "round": 1, "max_rounds": 3,
        })

        dm_fail = []
        for p_uid, alibi in alibis.items():
            role_txt = "🔪 *YOU ARE THE KILLER!*\n" if p_uid == killer_uid else "🕊️ *You are INNOCENT.*\n"
            fake_note = "\n_(Your alibi is FAKE — part of the setup to confuse!)_" if p_uid in fake_innocents else ""
            try:
                await context.bot.send_message(
                    p_uid,
                    f"🔍 *Last Call — Your Alibi*\n{role_txt}\n"
                    f"📍 Location: *{alibi['location']}*\n"
                    f"⏰ Time: *{alibi['time']}*\n{fake_note}\n\n"
                    f"_Discuss in group. Nobody can see if it's real or fake without paying 500 🪙 to verify!_",
                    parse_mode="Markdown")
            except TelegramError:
                dm_fail.append(g["players"].get(p_uid, str(p_uid)))

        if dm_fail:
            await update.message.reply_text(f"⚠️ Couldn't DM: {', '.join(dm_fail)}")
        await update.message.reply_text(
            f"🔍 ✦ *{fancy('LAST CALL STARTED!')}* ✦\n┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄\n"
            f"👥 {len(player_uids)} players | 🔪 1 Killer hidden\n"
            f"📋 Alibis sent via DM!\n\n"
            f"🗣️ *Round 1/{g['max_rounds']} — Discuss for 90s!*\n\n"
            f"Commands:\n"
            f"✧ `/lastcall verify @name` — Check alibi (500 🪙)\n"
            f"✧ `/lastcall accuse @name` — Vote to eliminate\n"
            f"✧ `/lastcall alibis` — See all claimed alibis",
            parse_mode="Markdown")

    elif sub == "alibis":
        if chat_id not in _lastcall_games or _lastcall_games[chat_id]["status"] != "active":
            await update.message.reply_text("❌ No active game here!"); return
        g = _lastcall_games[chat_id]
        lines = ["🗒️ *All Player Alibis:*\n"]
        for p_uid, alibi in g["alibis"].items():
            pname = g["players"].get(p_uid, "?")
            verified = g.get("verifications", {}).get(p_uid)
            v_tag = " ✅" if verified == "real" else " ❌ FAKE" if verified == "fake" else ""
            lines.append(f"✧ *{pname}*: {alibi['location']} @ {alibi['time']}{v_tag}")
        await update.message.reply_text("\n".join(lines), parse_mode="Markdown")

    elif sub == "verify":
        if chat_id not in _lastcall_games or _lastcall_games[chat_id]["status"] != "active":
            await update.message.reply_text("❌ No active game here!"); return
        if len(context.args) < 2: await update.message.reply_text("Usage: `/lastcall verify @name`"); return
        g = _lastcall_games[chat_id]
        t_name = context.args[1].lstrip("@").lower()
        t_uid  = next((u for u, n in g["players"].items()
                       if n.lstrip("@").lower() == t_name or
                       (isinstance(n, str) and t_name in n.lower())), None)
        if not t_uid: await update.message.reply_text("❌ Player not found!"); return

        u_doc = get_user_fast(str(uid))
        if u_doc.get("coins", 0) < LASTCALL_VERIFY_COST:
            await update.message.reply_text(
                f"❌ Need *{LASTCALL_VERIFY_COST} 🪙* to verify. You have *{u_doc.get('coins',0)}*.",
                parse_mode="Markdown"); return

        u_doc["coins"] -= LASTCALL_VERIFY_COST
        save_user_fast(str(uid))

        alibi = g["alibis"].get(t_uid, {})
        is_real = alibi.get("is_real", True)
        result  = "✅ *REAL*" if is_real else "❌ *FAKE*"
        t_name_disp = g["players"].get(t_uid, "?")
        g.setdefault("verifications", {})[t_uid] = "real" if is_real else "fake"

        await update.message.reply_text(
            f"🔍 *Alibi Verification*\n"
            f"*{t_name_disp}*'s alibi is {result}!\n"
            f"_(Cost: {LASTCALL_VERIFY_COST} 🪙)_",
            parse_mode="Markdown")

    elif sub == "accuse":
        if chat_id not in _lastcall_games or _lastcall_games[chat_id]["status"] != "active":
            await update.message.reply_text("❌ No active game here!"); return
        if len(context.args) < 2: await update.message.reply_text("Usage: `/lastcall accuse @name`"); return
        g = _lastcall_games[chat_id]
        if uid not in g["players"]: await update.message.reply_text("❌ You're not in this game!"); return
        t_name = context.args[1].lstrip("@").lower()
        t_uid  = next((u for u, n in g["players"].items()
                       if n.lstrip("@").lower() == t_name), None)
        if not t_uid: await update.message.reply_text("❌ Player not found!"); return
        if t_uid == uid: await update.message.reply_text("❌ Can't accuse yourself!"); return

        g.setdefault("accusations", {})[uid] = t_uid
        voted = len(g["accusations"]); total = len(g["players"])
        await update.message.reply_text(
            f"⚖️ *{name}* accuses *{g['players'][t_uid]}*!\n"
            f"({voted}/{total} players voted)", parse_mode="Markdown")

        if voted >= total:
            # Tally
            tally = {}
            for v in g["accusations"].values(): tally[v] = tally.get(v, 0) + 1
            if tally:
                top_uid  = max(tally, key=tally.get)
                top_name = g["players"].get(top_uid, "?")
                is_killer = (top_uid == g.get("killer_id"))
                if is_killer:
                    data_lc = load_data()
                    for p_uid in g["players"]:
                        if p_uid != g["killer_id"]:
                            u_lc = get_user(data_lc, p_uid)
                            u_lc["coins"] = u_lc.get("coins", 0) + 30
                            u_lc["total_coins_ever"] = u_lc.get("total_coins_ever", 0) + 30
                    save_data(data_lc)
                    await update.message.reply_text(
                        f"🎉 *{fancy('KILLER CAUGHT!')}*\n"
                        f"*{top_name}* was the killer!\n"
                        f"Innocents win! +30 🪙 each 🥳", parse_mode="Markdown")
                else:
                    data_lc = load_data()
                    ku = get_user(data_lc, g["killer_id"])
                    ku["coins"] = ku.get("coins", 0) + 60
                    ku["total_coins_ever"] = ku.get("total_coins_ever", 0) + 60
                    save_data(data_lc)
                    killer_name = g["players"].get(g["killer_id"], "?")
                    await update.message.reply_text(
                        f"💀 *Wrong accusation!* {top_name} was innocent!\n"
                        f"The killer was *{killer_name}*!\n"
                        f"Killer wins! +60 🪙", parse_mode="Markdown")
                _lastcall_games.pop(chat_id, None)
                return
            g["accusations"] = {}
            g["round"] = g.get("round", 1) + 1
            if g["round"] > g.get("max_rounds", 3):
                # Killer escapes
                data_lc = load_data()
                ku = get_user(data_lc, g["killer_id"])
                ku["coins"] = ku.get("coins", 0) + 60
                ku["total_coins_ever"] = ku.get("total_coins_ever", 0) + 60
                save_data(data_lc)
                killer_name = g["players"].get(g["killer_id"], "?")
                await update.message.reply_text(
                    f"⏰ *Time's up! The killer escaped!*\n"
                    f"It was *{killer_name}* all along! +60 🪙", parse_mode="Markdown")
                _lastcall_games.pop(chat_id, None)
            else:
                await update.message.reply_text(
                    f"🔄 *Round {g['round']}/{g['max_rounds']}* — Keep discussing!", parse_mode="Markdown")

    elif sub == "end":
        if chat_id in _lastcall_games:
            if uid == _lastcall_games[chat_id].get("host_id") or await is_admin(context.bot, chat_id, uid):
                _lastcall_games.pop(chat_id, None)
                await update.message.reply_text("🔍 Last Call ended.")





              # ══════════════════════════════════════════════════════════════════════════════
#  ECHOES — Bond deduction game. Each player has a secret partner ("bond").
#  One Impostor has a fake AI-generated bond. Players answer questions about
#  their bond publicly — others vote who is the Impostor.
# ══════════════════════════════════════════════════════════════════════════════
_echoes_games = {}

ECHOES_QUESTIONS = [
    "What's your bond's favourite colour?",
    "What does your bond do when stressed?",
    "What's your bond's go-to comfort food?",
    "Name one thing your bond always says.",
    "What's something your bond hates?",
    "What does your bond do on a lazy Sunday?",
    "Describe your bond's music taste in 3 words.",
    "What's your bond's biggest dream?",
    "What emoji best describes your bond?",
    "What's one habit your bond has?",
    "What would your bond do with 1 lakh rupees?",
    "What kind of movies does your bond love?",
]
ECHOES_FAKE_BONDS = [
    {"name":"Alex","colour":"burgundy","food":"sushi","habit":"tapping fingers"},
    {"name":"Sam","colour":"forest green","food":"street food","habit":"humming randomly"},
    {"name":"Jordan","colour":"navy blue","food":"biryani","habit":"checking phone"},
    {"name":"Casey","colour":"pastel yellow","food":"momos","habit":"doodling"},
]

@with_data_lock
async def cmd_echoes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    user    = update.message.from_user
    uid     = user.id
    name    = _safe_md(f"@{user.username}" if user.username else user.full_name)
    sub     = (context.args[0].lower() if context.args else "")

    if sub == "howto":
        await update.message.reply_text(
            "💬 ✦ *ECHOES — HOW TO PLAY* ✦\n┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄\n\n"
            "1. 4+ players join\n"
            "2. Everyone is secretly paired with a *bond* (another player)\n"
            "3. One player is the *Impostor* — their bond is AI-generated and doesn't exist!\n"
            "4. Each round: a question appears in chat\n"
            "5. Everyone answers about their bond publicly\n"
            "6. The Impostor must guess/improvise believable answers!\n"
            "7. After 5 questions, vote who you think is faking\n\n"
            "🏆 Innocents win: correctly identify the Impostor\n"
            "🏆 Impostor wins: survives all rounds undetected\n\n"
            "`/echoes join` | `/echoes start` | `/echoes vote @name`",
            parse_mode="Markdown")
        return

    if not sub:
        if chat_id in _echoes_games and _echoes_games[chat_id]["status"] in ("lobby","active"):
            g = _echoes_games[chat_id]
            pl = "\n".join(f"  ✧ {n}" for n in g["players"].values())
            await update.message.reply_text(
                f"💬 *Echoes Lobby*\n{pl}\n"
                f"`/echoes join` | host: `/echoes start`", parse_mode="Markdown")
            return
        _echoes_games[chat_id] = {"players": {uid: name}, "status": "lobby", "host_id": uid}
        await update.message.reply_text(
            f"💬 *ECHOES — Lobby Created!*\nHost: *{name}*\n"
            f"`/echoes join` | `/echoes start` (4+ needed) | `/echoes howto`",
            parse_mode="Markdown")

    elif sub == "join":
        if chat_id not in _echoes_games: await update.message.reply_text("❌ No lobby!"); return
        g = _echoes_games[chat_id]
        if g["status"] != "lobby": await update.message.reply_text("⚠️ Already started!"); return
        if uid in g["players"]: await update.message.reply_text("✅ You're already in!"); return
        g["players"][uid] = name
        await update.message.reply_text(f"✅ {name} joined! ({len(g['players'])} players)")

    elif sub == "start":
        if chat_id not in _echoes_games: await update.message.reply_text("❌ No lobby!"); return
        g = _echoes_games[chat_id]
        if g["status"] != "lobby": await update.message.reply_text("⚠️ Already started!"); return
        if uid != g["host_id"] and not await is_admin(context.bot, chat_id, uid):
            await update.message.reply_text("❌ Host only!"); return
        if len(g["players"]) < 4: await update.message.reply_text("❌ Need 4+ players!"); return

        player_uids  = list(g["players"].keys())
        impostor_uid = random.choice(player_uids)
        # Pair everyone else
        others = [u for u in player_uids if u != impostor_uid]
        random.shuffle(others)
        bonds = {}
        for i in range(0, len(others) - 1, 2):
            bonds[others[i]]   = others[i+1]
            bonds[others[i+1]] = others[i]
        if len(others) % 2 == 1:  # odd player out → also gets impostor
            bonds[others[-1]] = others[0]   # pair with first

        fake_bond = random.choice(ECHOES_FAKE_BONDS)
        questions = random.sample(ECHOES_QUESTIONS, min(5, len(ECHOES_QUESTIONS)))
        g.update({
            "status": "active", "impostor_id": impostor_uid,
            "bonds": bonds, "fake_bond": fake_bond,
            "questions": questions, "q_index": 0,
            "votes": {}, "answers": {},
        })

        dm_fail = []
        for p_uid in player_uids:
            if p_uid == impostor_uid:
                bond_info = (
                    f"🎭 *{fancy('YOU ARE THE IMPOSTOR!')}*\n\n"
                    f"Your fake bond is: *{fake_bond['name']}*\n"
                    f"Favourite colour: {fake_bond['colour']}\n"
                    f"Comfort food: {fake_bond['food']}\n"
                    f"Habit: {fake_bond['habit']}\n\n"
                    f"_Make up believable answers! Nobody can know!_"
                )
            else:
                bond_uid  = bonds.get(p_uid)
                bond_name = g["players"].get(bond_uid, "Unknown") if bond_uid else "Unknown"
                bond_info = (
                    f"💬 *Your bond is: {bond_name}*\n\n"
                    f"Answer the questions about this person genuinely!\n"
                    f"_Don't reveal who your bond is directly._"
                )
            try:
                await context.bot.send_message(p_uid, bond_info, parse_mode="Markdown")
            except TelegramError:
                dm_fail.append(g["players"].get(p_uid, str(p_uid)))

        if dm_fail:
            await update.message.reply_text(f"⚠️ Couldn't DM: {', '.join(dm_fail)}")

        await update.message.reply_text(
            f"💬 ✦ *{fancy('ECHOES STARTED!')}* ✦\n┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄\n"
            f"👥 {len(player_uids)} players | 🎭 1 Impostor\n"
            f"Roles sent via DM!\n\n"
            f"*Question 1 of {len(questions)}:*\n"
            f"❓ _{questions[0]}_\n\n"
            f"Everyone answer in chat about your bond!",
            parse_mode="Markdown")

    elif sub == "next" and uid == _echoes_games.get(chat_id, {}).get("host_id"):
        if chat_id not in _echoes_games or _echoes_games[chat_id]["status"] != "active":
            await update.message.reply_text("❌ No active game here!"); return
        g = _echoes_games[chat_id]
        g["q_index"] = g.get("q_index", 0) + 1
        if g["q_index"] >= len(g.get("questions", [])):
            # Go to vote
            players_list = "\n".join(f"✧ {n}" for n in g["players"].values())
            await update.message.reply_text(
                f"💬 *All questions done!*\n\n"
                f"Time to vote! Who do you think is the Impostor?\n\n"
                f"Players:\n{players_list}\n\n"
                f"`/echoes vote @name` to cast your vote!",
                parse_mode="Markdown")
        else:
            q = g["questions"][g["q_index"]]
            await update.message.reply_text(
                f"*Question {g['q_index']+1}/{len(g['questions'])}:*\n❓ _{q}_\n\n"
                f"Answer in chat about your bond!",
                parse_mode="Markdown")

    elif sub == "vote":
        if chat_id not in _echoes_games or _echoes_games[chat_id]["status"] != "active":
            await update.message.reply_text("❌ No active game here!"); return
        if len(context.args) < 2: await update.message.reply_text("Usage: `/echoes vote @name`"); return
        g = _echoes_games[chat_id]
        if uid not in g["players"]: await update.message.reply_text("❌ You're not in this game!"); return
        t_name = context.args[1].lstrip("@").lower()
        t_uid  = next((u for u, n in g["players"].items()
                       if n.lstrip("@").lower() == t_name), None)
        if not t_uid: await update.message.reply_text("❌ Player not found!"); return
        g.setdefault("votes", {})[uid] = t_uid
        voted = len(g["votes"]); total = len(g["players"])
        await update.message.reply_text(
            f"🗳️ *{name}* voted! ({voted}/{total})", parse_mode="Markdown")
        if voted >= total:
            tally   = {}
            for v in g["votes"].values(): tally[v] = tally.get(v, 0) + 1
            top_uid  = max(tally, key=tally.get)
            impostor = g.get("impostor_id")
            top_name = g["players"].get(top_uid, "?")
            imp_name = g["players"].get(impostor, "?")
            if top_uid == impostor:
                data_ec = load_data()
                for p in g["players"]:
                    if p != impostor:
                        u_ec = get_user(data_ec, p)
                        u_ec["coins"] = u_ec.get("coins", 0) + 25
                        u_ec["total_coins_ever"] = u_ec.get("total_coins_ever", 0) + 25
                save_data(data_ec)
                await update.message.reply_text(
                    f"🎉 *Impostor Found!* {top_name} was the Impostor!\n"
                    f"Their fake bond: *{g['fake_bond']['name']}*\n"
                    f"Innocents win! +25 🪙 each!", parse_mode="Markdown")
            else:
                data_ec = load_data()
                u_ec = get_user(data_ec, impostor)
                u_ec["coins"] = u_ec.get("coins", 0) + 50
                u_ec["total_coins_ever"] = u_ec.get("total_coins_ever", 0) + 50
                save_data(data_ec)
                await update.message.reply_text(
                    f"🎭 *Impostor escaped!* It was *{imp_name}*!\n"
                    f"Impostor wins! +50 🪙", parse_mode="Markdown")
            _echoes_games.pop(chat_id, None)

    elif sub == "end":
        if chat_id in _echoes_games:
            if uid == _echoes_games[chat_id].get("host_id") or await is_admin(context.bot, chat_id, uid):
                _echoes_games.pop(chat_id, None)
                await update.message.reply_text("💬 Echoes game ended.")



              # ══════════════════════════════════════════════════════════════════════════════
#  BLACKOUT WARD — Hospital deduction game
#  Contaminator secretly infects an item. Players trade items via DM.
#  Infected item holders are eliminated next round unless they have antidote.
# ══════════════════════════════════════════════════════════════════════════════
_blackout_games = {}

WARD_ITEMS = ["🩺 Stethoscope","💊 Medicine","📋 Chart","🩹 Bandage",
              "🧪 Sample","💉 Syringe","🔬 Microscope","🧲 Scanner"]

@with_data_lock
async def cmd_blackout(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    user    = update.message.from_user
    uid     = user.id
    name    = _safe_md(f"@{user.username}" if user.username else user.full_name)
    sub     = (context.args[0].lower() if context.args else "")

    if sub == "howto":
        await update.message.reply_text(
            "🏥 ✦ *BLACKOUT WARD — HOW TO PLAY* ✦\n┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄\n\n"
            "1. 4+ players start\n"
            "2. Each player gets 2 items\n"
            "3. One player is the *Contaminator*\n"
            "4. Each round: Contaminator DMs bot to infect one item\n"
            "5. Players can `/blackout trade @name item` to pass items\n"
            "6. At round end: infected item holders are ELIMINATED\n"
            "7. Unless they have an 🛡️ Antidote item!\n\n"
            "🏆 Innocents win: eliminate the Contaminator by voting\n"
            "🏆 Contaminator wins: only 2 players remain\n\n"
            "`/blackout join` | `/blackout start` | `/blackout infect <item>` (Contaminator only)\n"
            "`/blackout trade @name <item>` | `/blackout vote @name`",
            parse_mode="Markdown")
        return

    if not sub:
        if chat_id in _blackout_games and _blackout_games[chat_id]["status"] in ("lobby","active"):
            g = _blackout_games[chat_id]
            pl = "\n".join(f"  ✧ {n}" for n in g["players"].values())
            await update.message.reply_text(
                f"🏥 *Blackout Ward Lobby*\n{pl}\n"
                f"`/blackout join` | host: `/blackout start`", parse_mode="Markdown")
            return
        _blackout_games[chat_id] = {"players": {uid: name}, "status": "lobby", "host_id": uid}
        await update.message.reply_text(
            f"🏥 *BLACKOUT WARD — Lobby Created!*\nHost: *{name}*\n"
            f"`/blackout join` | `/blackout start` | `/blackout howto`",
            parse_mode="Markdown")

    elif sub == "join":
        if chat_id not in _blackout_games: await update.message.reply_text("❌ No lobby!"); return
        g = _blackout_games[chat_id]
        if g["status"] != "lobby": await update.message.reply_text("⚠️ Already started!"); return
        if uid in g["players"]: await update.message.reply_text("✅ You're already in!"); return
        g["players"][uid] = name
        await update.message.reply_text(f"✅ {name} joined! ({len(g['players'])} players)")

    elif sub == "start":
        if chat_id not in _blackout_games: await update.message.reply_text("❌ No lobby!"); return
        g = _blackout_games[chat_id]
        if g["status"] != "lobby": await update.message.reply_text("⚠️ Already started!"); return
        if uid != g["host_id"] and not await is_admin(context.bot, chat_id, uid):
            await update.message.reply_text("❌ Host only!"); return
        if len(g["players"]) < 4: await update.message.reply_text("❌ Need 4+ players!"); return

        player_uids  = list(g["players"].keys())
        contaminator = random.choice(player_uids)
        items_pool   = WARD_ITEMS.copy()
        random.shuffle(items_pool)

        inventories = {}
        for i, p_uid in enumerate(player_uids):
            player_items = [items_pool[(i*2) % len(items_pool)], items_pool[(i*2+1) % len(items_pool)]]
            # One random player gets antidote
            if i == random.randrange(len(player_uids)):
                player_items.append("🛡️ Antidote")
            inventories[p_uid] = player_items

        g.update({
            "status": "active", "contaminator_id": contaminator,
            "inventories": inventories, "infected_item": None,
            "votes": {}, "round": 1, "alive": list(player_uids),
        })

        dm_fail = []
        for p_uid in player_uids:
            role_txt = "☣️ *YOU ARE THE CONTAMINATOR!*\nUse `/blackout infect <item name>` each round to infect!\n" if p_uid == contaminator else "🩺 *You are a Doctor!* Trade wisely, avoid the infected item!\n"
            inv_txt  = "\n".join(f"  ✧ {it}" for it in inventories[p_uid])
            try:
                await context.bot.send_message(
                    p_uid,
                    f"🏥 *Blackout Ward — Your Role*\n{role_txt}\n*Your items:*\n{inv_txt}",
                    parse_mode="Markdown")
            except TelegramError:
                dm_fail.append(g["players"].get(p_uid, str(p_uid)))

        if dm_fail:
            await update.message.reply_text(f"⚠️ Couldn't DM: {', '.join(dm_fail)}")
        await update.message.reply_text(
            f"🏥 ✦ *{fancy('BLACKOUT WARD STARTED!')}* ✦\n┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄\n"
            f"👥 {len(player_uids)} players | ☣️ 1 Contaminator\n"
            f"Items + roles sent via DM!\n\n"
            f"*Round 1 — Trade Phase (60s):*\n"
            f"`/blackout trade @name <item>` to offer a trade\n"
            f"Contaminator: `/blackout infect <item>` in DM to infect!\n\n"
            f"Round ends: `/blackout roundend` (host only)",
            parse_mode="Markdown")

    elif sub == "infect":
        # Contaminator infects in DM or group
        if chat_id not in _blackout_games and update.message.chat.type == "private":
            # Find their game
            game_chat = next((cid for cid, g in _blackout_games.items()
                              if g.get("contaminator_id") == uid and g.get("status") == "active"), None)
            if not game_chat: await update.message.reply_text("❌ No active game here!"); return
            g = _blackout_games[game_chat]
        elif chat_id in _blackout_games:
            g = _blackout_games[chat_id]
            game_chat = chat_id
        else:
            await update.message.reply_text("❌ No active game here!"); return
        if g.get("contaminator_id") != uid:
            await update.message.reply_text("❌ You're not the Contaminator!"); return
        if not context.args[1:]: await update.message.reply_text("Usage: `/blackout infect <item name>`"); return
        item_name = " ".join(context.args[1:]).strip()
        g["infected_item"] = item_name
        await update.message.reply_text(f"☣️ *{_safe_md(item_name)}* is now infected! _(Only you know this)_", parse_mode="Markdown")

    elif sub == "trade":
        if chat_id not in _blackout_games or _blackout_games[chat_id]["status"] != "active":
            await update.message.reply_text("❌ No active game here!"); return
        if len(context.args) < 3: await update.message.reply_text("Usage: `/blackout trade @name <item>`"); return
        g = _blackout_games[chat_id]
        if uid not in g["alive"]: await update.message.reply_text("❌ You're eliminated!"); return
        t_name    = context.args[1].lstrip("@").lower()
        item_name = " ".join(context.args[2:]).strip()
        t_uid     = next((u for u, n in g["players"].items()
                          if n.lstrip("@").lower() == t_name), None)
        if not t_uid: await update.message.reply_text("❌ Player not found!"); return
        inv = g["inventories"].get(uid, [])
        matched = next((it for it in inv if item_name.lower() in it.lower()), None)
        if not matched: await update.message.reply_text(f"❌ You don't have '{item_name}'!"); return
        # Execute trade
        inv.remove(matched)
        g["inventories"].setdefault(t_uid, []).append(matched)
        t_name_d = g["players"].get(t_uid, "?")
        await update.message.reply_text(
            f"🔄 *{name}* traded *{matched}* to *{t_name_d}*!", parse_mode="Markdown")

    elif sub == "roundend":
        if chat_id not in _blackout_games or _blackout_games[chat_id]["status"] != "active":
            await update.message.reply_text("❌ No active game here!"); return
        g = _blackout_games[chat_id]
        if uid != g["host_id"] and not await is_admin(context.bot, chat_id, uid):
            await update.message.reply_text("❌ Host only!"); return

        infected = g.get("infected_item")
        if not infected:
            await update.message.reply_text("☣️ Contaminator hasn't infected anything this round yet!")
            return

        eliminated = []
        survived   = []
        for p_uid in list(g["alive"]):
            inv = g["inventories"].get(p_uid, [])
            has_infected  = any(infected.lower() in it.lower() for it in inv)
            has_antidote  = "🛡️ Antidote" in inv
            if has_infected and not has_antidote:
                eliminated.append(p_uid)
                g["alive"].remove(p_uid)
                if has_antidote: survived.append(p_uid)

        elim_names = [g["players"].get(u,"?") for u in eliminated]
        lines = [f"🏥 ✦ *Round {g['round']} Results* ✦\n┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄",
                 f"☣️ Infected item: *{infected}*\n"]
        if elim_names:
            lines.append(f"💀 Eliminated: {', '.join(elim_names)}")
        else:
            lines.append("✅ Nobody infected this round!")

        g["infected_item"] = None
        g["round"] = g.get("round", 1) + 1

        if len(g["alive"]) <= 2:
            data_bw = load_data()
            cu_bw = get_user(data_bw, g["contaminator_id"])
            cu_bw["coins"] = cu_bw.get("coins", 0) + 60
            cu_bw["total_coins_ever"] = cu_bw.get("total_coins_ever", 0) + 60
            save_data(data_bw)
            lines.append(f"\n☣️ *Contaminator wins!* +60 🪙")
            _blackout_games.pop(chat_id, None)
        else:
            lines.append(f"\n*Alive ({len(g['alive'])}):*\n" +
                        "\n".join(f"  👤 {g['players'][u]}" for u in g["alive"]))
            lines.append(f"\n`/blackout vote @name` to accuse the Contaminator\nOr continue trading!")

        await update.message.reply_text("\n".join(lines), parse_mode="Markdown")

    elif sub == "vote":
        if chat_id not in _blackout_games: await update.message.reply_text("❌ No active game here!"); return
        g = _blackout_games[chat_id]
        if uid not in g["alive"]: await update.message.reply_text("💀 You've been eliminated — spectate quietly!"); return
        if len(context.args) < 2: await update.message.reply_text("Usage: `/blackout vote @name`"); return
        t_name = context.args[1].lstrip("@").lower()
        t_uid  = next((u for u, n in g["players"].items()
                       if n.lstrip("@").lower() == t_name and u in g["alive"]), None)
        if not t_uid: await update.message.reply_text("❌ Player not found/alive!"); return
        g.setdefault("votes", {})[uid] = t_uid
        voted = len(g["votes"]); alive_c = len(g["alive"])
        await update.message.reply_text(f"🗳️ {name} voted! ({voted}/{alive_c})")
        if voted >= alive_c:
            tally = {}
            for v in g["votes"].values(): tally[v] = tally.get(v, 0) + 1
            top_uid  = max(tally, key=tally.get)
            cont_uid = g["contaminator_id"]
            top_name = g["players"].get(top_uid, "?")
            cont_nm  = g["players"].get(cont_uid, "?")
            if top_uid == cont_uid:
                data_bw = load_data()
                for p in g["alive"]:
                    if p != cont_uid:
                        u_bw = get_user(data_bw, p)
                        u_bw["coins"] = u_bw.get("coins", 0) + 30
                        u_bw["total_coins_ever"] = u_bw.get("total_coins_ever", 0) + 30
                save_data(data_bw)
                await update.message.reply_text(
                    f"🎉 *Contaminator caught!* It was *{top_name}*!\n"
                    f"Doctors win! +30 🪙 each!", parse_mode="Markdown")
            else:
                data_bw = load_data()
                cu_bw = get_user(data_bw, cont_uid)
                cu_bw["coins"] = cu_bw.get("coins", 0) + 60
                cu_bw["total_coins_ever"] = cu_bw.get("total_coins_ever", 0) + 60
                save_data(data_bw)
                await update.message.reply_text(
                    f"☣️ *Wrong vote!* The Contaminator was *{cont_nm}*!\n"
                    f"Contaminator wins! +60 🪙", parse_mode="Markdown")
            _blackout_games.pop(chat_id, None)

    elif sub == "end":
        if chat_id in _blackout_games:
            if uid == _blackout_games[chat_id].get("host_id") or await is_admin(context.bot, chat_id, uid):
                _blackout_games.pop(chat_id, None)
                await update.message.reply_text("🏥 Blackout Ward ended.")
# ══════════════════════════════════════════════════════════════════════════════
#  MESSAGE HANDLER — ties AFK/GN, mention-ping, cheat codes, challenge grading,
#  mini-game input routing, and Aira chat together
# ══════════════════════════════════════════════════════════════════════════════
# Per-chat rate limits for expensive handle_message responses
_ai_reply_last: dict = {}   # chat_id -> datetime of last AI reply

# Weekly Group Personality Report — tracks activity metadata (not content)
_group_week_stats: dict = {}  # chat_id -> weekly stats dict
_REPORT_CURRENT_WEEK: str = ""  # ISO week string, e.g. "2026-W36"

_handled_msg_ids: set = set()       # rolling dedup set — max 200 entries
_handled_msg_ids_order: list = []   # insertion order for eviction
_gn_reply_last: dict  = {}  # chat_id -> datetime of last GN/sleep reply
_AI_REPLY_COOLDOWN_SEC  = 12   # min seconds between AI chat replies per chat
_GN_REPLY_COOLDOWN_SEC  = 120  # min seconds between good-night replies per chat

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Dedup: TEXT + PHOTO handlers both route here.
    # A photo-with-caption fires both → we catch the duplicate by message_id.
    _mid = getattr(update.message, "message_id", None)
    if _mid is not None:
        if _mid in _handled_msg_ids:
            return
        _handled_msg_ids.add(_mid)
        _handled_msg_ids_order.append(_mid)
        if len(_handled_msg_ids_order) > 200:
            _handled_msg_ids.discard(_handled_msg_ids_order.pop(0))
    # NOTE: intentionally NOT wrapped in @with_data_lock — this runs on every
    # single message (including AI chat replies that can take several seconds
    # via Groq/Gemini). Locking it would freeze every other command in the
    # group for that whole time. Its data writes here are simple AFK/ping
    # bookkeeping on a single user, which is low-risk without the lock.
    if not update.message: return
    chat_id = update.message.chat_id
    user = update.message.from_user
    text = update.message.text or update.message.caption or ""
    # Weekly personality report: passively collect per-message metadata
    if user and chat_id < 0:  # only for groups (negative chat_id)
        _collect_group_stat(chat_id, user, update.message)

    track_chat(chat_id, update.message.chat.type != "private")
    ensure_auto_challenge(context, chat_id)

    # ── Pending "/mypet → Rename" button: next text message from that same
    # user becomes the pet's new nickname. Checked early so it doesn't fall
    # through to AI chat / other handlers. ─────────────────────────────────
    if context.chat_data.get("awaiting_pet_rename") and text:
        if await handle_pet_rename_text(update, context):
            return

    # ── Pending "/mypet → Talk" button: next text message from that same
    # user is spoken *to* the pet (barks/meows back, mood-flavored). ──────
    if context.chat_data.get("awaiting_pet_talk") and text:
        if await handle_pet_talk_text(update, context):
            return

    # ── Owner replying to a /reportbug notification DMs that text straight
    # to the original reporter, so the owner can respond without needing
    # the reporter's username/ID. ────────────────────────────────────────
    if (update.message.chat.type == "private" and user and user.id in OWNER_IDS
            and update.message.reply_to_message and text):
        replied_id = update.message.reply_to_message.message_id
        matched_report = None
        for rid, rep in _bug_reports.items():
            if rep.get("owner_messages", {}).get(user.id) == replied_id:
                matched_report = rep
                break
        if matched_report:
            try:
                await context.bot.send_message(
                    matched_report["reporter_id"],
                    f"💬 *Message from Aira's owner about your bug report:*\n\n{_safe_md(text)}",
                    parse_mode="Markdown")
                await update.message.reply_text("✅ Sent to the reporter.")
            except Exception as e:
                await update.message.reply_text(f"⚠️ Couldn't DM the reporter: _{e}_", parse_mode="Markdown")
            return

 # ── Anti-spam (5 msgs in 8s → warn → 5min mute → permanent mute + alert) ──
    if update.message.chat.type != "private" and user:
        grp_as = get_group_db(chat_id)
        if grp_as.get("antispam") and user.id not in grp_as.get("approved_ids", []):
            _as_key = (chat_id, user.id)
            _as_now = datetime.now()
            entry   = _antispam_tracker.setdefault(_as_key, {"msgs": [], "warn_level": 0, "last_warn": None})
            entry["msgs"] = [t for t in entry["msgs"] if (_as_now - t).total_seconds() < ANTISPAM_WINDOW]
            entry["msgs"].append(_as_now)

            # Auto-reset warn_level after 1 hour of clean behaviour
            lw = entry.get("last_warn")
            if lw and (_as_now - lw).total_seconds() > 3600:
                entry["warn_level"] = 0

            if len(entry["msgs"]) >= ANTISPAM_MSG_LIMIT:
                spam_name  = _safe_md(f"@{user.username}" if user.username else user.full_name)
                warn_level = entry.get("warn_level", 0)
                try:
                    m = await context.bot.get_chat_member(chat_id, user.id)
                    if m.status in ("administrator", "creator"):
                        entry["msgs"] = []  # admins are immune
                    elif warn_level == 0:
                        entry["warn_level"] = 1
                        entry["msgs"]       = []
                        entry["last_warn"]  = _as_now
                        try:
                            await update.message.delete()
                        except TelegramError:
                            pass
                        await context.bot.send_message(
                            chat_id,
                            f"⚠️ *{spam_name}* — stop spamming! "
                            f"Next time you'll get a 5 min mute. 🛑",
                            parse_mode="Markdown")
                        return
                    elif warn_level == 1:
                        entry["warn_level"] = 2
                        entry["msgs"]       = []
                        entry["last_warn"]  = _as_now
                        try:
                            await update.message.delete()
                        except TelegramError:
                            pass
                        try:
                            await context.bot.restrict_chat_member(
                                chat_id, user.id,
                                permissions=ChatPermissions(can_send_messages=False),
                                until_date=_as_now + timedelta(seconds=ANTISPAM_TIMEOUT),
                            )
                            await context.bot.send_message(
                                chat_id,
                                f"🔇 *{spam_name}* ko *5 min timeout* diya — "
                                f"warn ke baad bhi spam kiya. ⏱️",
                                parse_mode="Markdown")
                        except TelegramError as te:
                            logger.warning(f"antispam mute failed: {te}")
                        return
                    else:
                        entry["msgs"]      = []
                        entry["last_warn"] = _as_now
                        try:
                            await update.message.delete()
                        except TelegramError:
                            pass
                        try:
                            await context.bot.restrict_chat_member(
                                chat_id, user.id,
                                permissions=ChatPermissions(can_send_messages=False),
                            )
                            admins   = await context.bot.get_chat_administrators(chat_id)
                            mentions = " ".join(
                                f"[​](tg://user?id={a.user.id})"
                                for a in admins if not a.user.is_bot
                            )
                            await context.bot.send_message(
                                chat_id,
                                f"🚨 {mentions}*{fancy('SPAM ALERT!')}*\n"
                                f"{spam_name} — permanently muted after repeated spam. "
                                f"Admins, please review! 🛡️",
                                parse_mode="Markdown")
                        except TelegramError as te:
                            logger.warning(f"antispam perma-mute failed: {te}")
                        return
                except TelegramError:
                    pass  # Can't check membership — skip

    data = load_data()

    # ── AFK RETURN — clear AFK / sleep and show a "who missed you" summary ──
    if text and not text.startswith("!status"):
        returned = await handle_afk_return(update, data, user)
        if returned:
            data = load_data()  # reload after handle_afk_return saved

    # ── GN / Good night → sleep-AFK (shows as sleeping, not just "away") ────
    if text and GN_PATTERNS.search(text):
        u = get_user(data, user.id, user.username, user.full_name)
        if not u.get("afk"):
            u["afk"] = "sleeping 😴"; u["afk_since"] = datetime.now().isoformat()
            u["afk_pings"] = []; u["afk_type"] = "sleep"
            save_data(data)
            # Rate-limit GN replies: once per _GN_REPLY_COOLDOWN_SEC per chat
            _now_gn = datetime.now()
            _last_gn = _gn_reply_last.get(chat_id)
            if not _last_gn or (_now_gn - _last_gn).total_seconds() > _GN_REPLY_COOLDOWN_SEC:
                _gn_reply_last[chat_id] = _now_gn
                name = _safe_md(f"@{user.username}" if user.username else user.full_name)
                try:
                    await update.message.reply_text(
                        f"🌙 Aww, *{name}* went to sleep~ Sweet dreams! 😴✨",
                        parse_mode="Markdown")
                except RetryAfter as e:
                    await asyncio.sleep(e.retry_after + 1)
            return

    # ── !status <reason> — manual AFK ────────────────────────────────────────
    if text.lower().startswith("!status"):
        reason = text[7:].strip()
        u = get_user(data, user.id, user.username, user.full_name)
        if reason:
            u["afk"] = reason; u["afk_since"] = datetime.now().isoformat(); u["afk_pings"] = []; u["afk_type"] = "away"
            save_data(data)
            await update.message.reply_text(f"😴 AFK set: _{reason}_", parse_mode="Markdown")
        else:
            if u.get("afk"):
                await handle_afk_return(update, data, user)
            else:
                await update.message.reply_text("Usage: `!status <reason>` to set AFK.", parse_mode="Markdown")
        return

    # ── Mention-ping detection for AFK users (reply or @username) ───────────
    pinger_name = _safe_md(f"@{user.username}" if user.username else user.full_name)
    if update.message.reply_to_message and update.message.reply_to_message.from_user:
        target_id = update.message.reply_to_message.from_user.id
        if target_id != user.id:
            notice = await check_afk_ping(update, data, target_id, pinger_name)
            if notice:
                save_data(data)
                await update.message.reply_text(notice, parse_mode="Markdown")
    for match in re.finditer(r'@(\w+)', text or ""):
        uname = match.group(1).lower()
        for uid, udoc in data["users"].items():
            if (udoc.get("username") or "").lower() == uname and int(uid) != user.id:
                notice = await check_afk_ping(update, data, int(uid), pinger_name)
                if notice:
                    save_data(data)
                    await update.message.reply_text(notice, parse_mode="Markdown")
                break


    code_candidate = text.strip().upper()
    if code_candidate and (code_candidate in CHEAT_CODES or code_candidate in (EVERGREEN_COINS_CODE, EVERGREEN_ADMIN_CODE)):
        u = get_user(data, user.id, user.username, user.full_name)
        used = data.setdefault("used_codes", [])
        if code_candidate == EVERGREEN_COINS_CODE:
            u["coins"] += 500; b = award_badge(u, "cheat_user"); save_data(data)
            await update.message.reply_text(f"🔑 Evergreen code redeemed! +500 🪙" + (f"\n\n{b}" if b else ""), parse_mode="Markdown")
            return
        if code_candidate == EVERGREEN_ADMIN_CODE:
            if user.id in OWNER_IDS or code_candidate == EVERGREEN_ADMIN_CODE:
                await update.message.reply_text("🔑 Admin evergreen code recognized. (Contact bot owner for elevated access.)")
            return
        if code_candidate not in used:
            reward = CHEAT_CODES[code_candidate]
            u["coins"] += reward; used.append(code_candidate)
            b = award_badge(u, "cheat_user")
            save_data(data)
            await update.message.reply_text(f"🔑 Code redeemed! +{reward} 🪙" + (f"\n\n{b}" if b else ""), parse_mode="Markdown")
        else:
            await update.message.reply_text("❌ Code already used!")
        return

    # ── Custom owner-generated redeem codes (from /makeredeemcodeforall) ────
    if code_candidate and re.match(r'^[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}$', code_candidate):
        db = _get_db()
        custom_doc = db["meta"].find_one({"_id": "custom_codes"}) or {}
        custom_codes = custom_doc.get("codes", {})
        entry = custom_codes.get(code_candidate)
        if entry and not entry.get("used"):
            amount = entry["amount"]
            u = get_user(data, user.id, user.username, user.full_name)
            u["coins"] += amount
            b = award_badge(u, "cheat_user")
            save_data(data)
            # Same fix as generation: mutate the whole "codes" dict in Python
            # and write it back flat — no dotted-path $set, which the SQLite
            # shim doesn't reliably nest.
            custom_codes[code_candidate]["used"] = True
            db["meta"].update_one({"_id": "custom_codes"}, {"$set": {"codes": custom_codes}})
            await update.message.reply_text(f"🔑 Code redeemed! +{amount} 🪙" + (f"\n\n{b}" if b else ""), parse_mode="Markdown")
            return
        elif entry and entry.get("used"):
            await update.message.reply_text("❌ Code already used!")
            return
        else:
            await update.message.reply_text("❌ Invalid code.")
            return
    # ── Traitor DM guess ──────────────────────────────────────────────────────
    if update.message.chat.type == "private":
        for gid, game in list(_traitor_games.items()):
            if game.get("status") == "active" and user.id in game.get("traitor_ids", []):
                if text.strip().lower() == game.get("word", "").lower():
                    await update.message.reply_text("🎉 You guessed the word! The traitor wins!")
                    try: await context.bot.send_message(gid, f"🕵️‍♂️ The traitor ({_safe_md(user.full_name)}) guessed the word! Traitors win!")
                    except Exception: pass
                    _traitor_games.pop(gid, None)
                    return
                elif text.strip():
                    await update.message.reply_text("❌ Wrong word!")
                    return

# ── Mini-game input routing (hangman / guessnumber / wordchain / quiz / fastmath) ──
    if text.strip():
        if await _hangman_try_letter(update, chat_id, text.strip()):
            return
        gk = (chat_id, user.id)
        if await _guessnum_try(update, gk, text):
            return
        if await _wordchain_try(update, context, chat_id, text):
            return
        if await _quiz_try_answer(update, context, chat_id, text):
            return
        if await _fastmath_try(update, context, chat_id, text):
            return

    # ── Challenge grading ─────────────────────────────────────────────────────
    group = get_group_db(chat_id)
    challenge = group.get("active_challenge")
    if challenge:
        if challenge.get("type") in ("trivia", "word") and text:
            if text.strip().lower() in challenge["answers"]:
                await process_win(update, context, user, chat_id, challenge,
                                   "speed_win" if challenge["type"] == "word" else None)
                return
        elif challenge.get("type") == "photo" and update.message.photo:
            msg = await update.message.reply_text("🔍 Aira is checking your photo…")
            path = f"/tmp/challenge_{chat_id}_{user.id}.jpg"
            try:
                file = await update.message.photo[-1].get_file()
                await file.download_to_drive(path)
                verdict, reason = await analyze_image_with_ai(path, challenge["answers"][0])
                if verdict is True:
                    await msg.delete()
                    await process_win(update, context, user, chat_id, challenge, "image_win")
                    return
                elif verdict is False:
                    await msg.delete()
                    extra = f" _{reason}_" if reason else ""
                    await update.message.reply_text(
                        f"❌ Not quite!{extra} Try again with a clearer photo or different angle.", parse_mode="Markdown")
                else:
                    # verdict is None: the vision check itself failed (model/
                    # network error) — do NOT tell the user "no", that would
                    # unfairly fail a correct photo. Let them try again.
                    await msg.delete()
                    await update.message.reply_text(f"⚠️ {reason}")
            finally:
                if os.path.exists(path):
                    os.remove(path)

    # ── Aira personality chat ─────────────────────────────────────────────────
    bot_username = _CACHED_BOT_USERNAME or "AiraBot"
    if _should_aira_reply(update, bot_username) and text:
        # Rate-limit AI replies: max once per _AI_REPLY_COOLDOWN_SEC per chat
        # This is the #1 cause of flood control — busy groups spam mentions.
        _now_ai = datetime.now()
        _last_ai = _ai_reply_last.get(chat_id)
        if _last_ai and (_now_ai - _last_ai).total_seconds() < _AI_REPLY_COOLDOWN_SEC:
            return  # cooldown active — silently drop this reply
        _ai_reply_last[chat_id] = _now_ai
        user_name = _safe_md(f"@{user.username}" if user.username else user.full_name)
        clean_text = re.sub(rf'@{re.escape(bot_username)}', '', text, flags=re.IGNORECASE).strip() or text
        try: await context.bot.send_chat_action(chat_id, "typing")
        except Exception: pass
        reply = await groq_chat(chat_id, user_name, clean_text)
        try:
            await update.message.reply_text(reply)
        except RetryAfter as e:
            await asyncio.sleep(e.retry_after + 1)
            try: await update.message.reply_text(reply)
            except Exception: pass
        except BadRequest as e:
            logger.info(f"Couldn't send Aira chat reply in {chat_id}: {e}")




# ══════════════════════════════════════════════════════════════════════════════
#  SECRET OWNER COMMANDS — not in /help, not documented anywhere
# ══════════════════════════════════════════════════════════════════════════════
def _resolve_sendmessage_target(raw: str):
    """Turns whatever the owner pasted into (primary_chat_id, fallback_chat_id, note).
    fallback is only set for the cases known to be genuinely ambiguous —
    if the primary guess 404s, the caller retries with fallback before
    giving up. note is a short string explained back to the owner, or None.

    Handles:
      • already-correct IDs, negative or positive               -> as-is, no fallback
      • bare digit strings 10+ digits long with NO sign          -> Telegram strips the
        "-100" supergroup/channel prefix in a lot of other tools' raw ID dumps (this is
        exactly what @RawDataBot/@userinfobot-style bots often show), so this is treated
        as "-100" + those digits FIRST, falling back to the plain positive number
        (a real, if rare, giant user id) if that 404s.
      • "@username" or a public t.me/username link               -> "@username" (Bot API
        accepts this directly for any PUBLIC chat, group/channel or user)
      • a private invite link (t.me/+xxxx or t.me/joinchat/xxxx)  -> unresolvable via the
        Bot API (Telegram gives bots no method to turn an invite hash into a chat id) —
        returns (None, None, note) explaining why, with the /chatid workaround.
    Returns (None, None, note) when nothing usable could be parsed at all.
    """
    raw = raw.strip()

    m = re.match(r'^(?:https?://)?t\.me/\+', raw, re.IGNORECASE) or re.match(r'^(?:https?://)?t\.me/joinchat/', raw, re.IGNORECASE)
    if m:
        return None, None, (
            "That's a *private invite link* — Telegram gives bots no way to turn one of "
            "those into a chat ID (there's no Bot API method for it, only full user-account "
            "clients can resolve invite links). Two ways around it instead:\n"
            "1️⃣ Run `/chatid` *inside that group* (I'm already in it if I'm supposed to message it) "
            "and I'll hand you back the exact ID to use here.\n"
            "2️⃣ If the group has a public @username, paste that instead — public links work directly."
        )

    m = re.match(r'^(?:https?://)?t\.me/([A-Za-z0-9_]{5,32})/?$', raw, re.IGNORECASE)
    if m:
        return f"@{m.group(1)}", None, None
    if re.match(r'^@[A-Za-z0-9_]{5,32}$', raw):
        return raw, None, None

    if re.match(r'^-\d+$', raw):
        return int(raw), None, None  # already correctly signed — use as-is

    if re.match(r'^\d+$', raw):
        if len(raw) >= 10:
            # Almost certainly a supergroup/channel ID with "-100" stripped off
            # (this is exactly the shape tools like @RawDataBot hand back) —
            # try that first, fall back to a plain positive user id if it 404s.
            return int(f"-100{raw}"), int(raw), None
        return int(raw), None, None  # short positive number — plain user id

    return None, None, None

async def cmd_sendmessage(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Owner-only: /sendmessage <id_or_link> <text> — sends a message to ANY
    chat the bot can reach: a group/channel, or a user's DM.

    Accepts, in any of these forms:
        • a negative chat ID       -100123456789
        • a bare positive ID with the "-100" prefix stripped (what most
          "get my chat id" bots print) — auto-corrected, see
          _resolve_sendmessage_target()
        • a positive user ID       123456789   (DM — needs the user to have
          started the bot at least once; Telegram gives bots no way around
          that for anyone)
        • a public @username or t.me/username link (group, channel, or user)
        • a PRIVATE invite link (t.me/+xxx) — NOT resolvable by any bot via
          the Bot API; the command explains this and points to /chatid.

    Media works too: attach a photo/video/document/etc. and put
    `/sendmessage <target> <caption>` in the caption.
    """
    user = update.message.from_user
    if user.id not in OWNER_IDS:
        logger.info(f"Unauthorized /sendmessage attempt by {user.id}")
        return
    msg = update.message
    raw_text = msg.text or msg.caption or ""
    stripped = re.sub(r'^/sendmessage(@\w+)?\s*', '', raw_text, flags=re.IGNORECASE).strip()
    parts = stripped.split(maxsplit=1)

    if not parts:
        await update.message.reply_text(
            "Usage: `/sendmessage <id_or_@username_or_link> <message>`\n\n"
            "• Group/channel ID (e.g. `-100123456789`) → sends there\n"
            "• Bare digits with no `-100` (e.g. `123456789012`) → auto-corrected, "
            "this is what most \"get chat id\" bots print\n"
            "• Positive user ID → sends to that user's DM (only works if they've messaged me before)\n"
            "• `@username` or `t.me/username` → sends to that public group/channel/user\n"
            "• Don't have the ID? Run `/chatid` *inside the target group* and I'll give it to you.\n\n"
            "You can also attach a photo/video/etc. with the command as the caption.",
            parse_mode="Markdown")
        return

    target, fallback_target, note = _resolve_sendmessage_target(parts[0])
    text = parts[1] if len(parts) > 1 else ""
    has_media = bool(msg.photo or msg.video or msg.document or msg.animation or msg.audio or msg.voice or msg.sticker)

    if target is None:
        if note:
            await update.message.reply_text(f"❌ {note}", parse_mode="Markdown")
        else:
            await update.message.reply_text(
                "Usage: `/sendmessage <id_or_@username_or_link> <message>`\n"
                "Couldn't figure out a chat from that first argument — see `/sendmessage` with "
                "no args for the accepted formats.", parse_mode="Markdown")
        return

    if not text and not has_media:
        await update.message.reply_text("Usage: `/sendmessage <id_or_@username_or_link> <message>`", parse_mode="Markdown")
        return

    async def _attempt(chat_id):
        if has_media:
            await context.bot.copy_message(
                chat_id=chat_id, from_chat_id=msg.chat_id, message_id=msg.message_id,
                caption=text if text else None, parse_mode="Markdown" if text else None)
        else:
            await context.bot.send_message(chat_id=chat_id, text=text, parse_mode="Markdown")

    def _kind(t):
        if isinstance(t, str):
            return "public chat"
        return "group/channel" if t < 0 else "user's DM"

    try:
        await _attempt(target)
        await update.message.reply_text(f"✅ Sent to `{target}` ({_kind(target)}).", parse_mode="Markdown")
    except (BadRequest, TelegramError) as e:
        if fallback_target is not None:
            try:
                await _attempt(fallback_target)
                await update.message.reply_text(
                    f"✅ Sent to `{fallback_target}` ({_kind(fallback_target)}).\n"
                    f"_(`{target}` didn't work, but the alternate reading of that ID did.)_",
                    parse_mode="Markdown")
                return
            except (BadRequest, TelegramError) as e2:
                e = e2
        await update.message.reply_text(
            f"❌ Couldn't send to `{target}`: `{str(e)[:200]}`\n"
            f"_Common causes: the bot isn't a member of that group, that user has never started a "
            f"chat with the bot, or the ID is wrong. Run `/chatid` inside the target chat to get the "
            f"exact ID._",
            parse_mode="Markdown")
    except Exception as e:
        logger.error(f"cmd_sendmessage error: {e}")
        await update.message.reply_text(f"❌ Unexpected error: `{str(e)[:200]}`", parse_mode="Markdown")

async def cmd_chatid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Works in any chat (group, supergroup, channel-linked-discussion, or DM) —
    replies with the exact chat ID, type, and title, so the owner never has to
    guess or borrow a third-party bot to find it. This is the direct fix for
    "how do I get that group's numeric ID": run this command IN that group."""
    chat = update.effective_chat
    title = chat.title or (f"@{chat.username}" if chat.username else chat.full_name) or "this chat"
    lines = [
        f"🆔 *Chat ID:* `{chat.id}`",
        f"📌 *Type:* {chat.type}",
        f"📛 *Name:* {_safe_md(title)}",
    ]
    if chat.username:
        lines.append(f"🔗 *Public link:* @{chat.username}")
    lines.append(f"\n_Use this ID directly with `/sendmessage {chat.id} <text>`._")
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")

async def cmd_announcetoall(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    if user.id not in OWNER_IDS:
        logger.info(f"Unauthorized /announcetoall attempt by {user.id}")
        return
    msg = update.message
    raw_text = msg.text or msg.caption or ""
    text = re.sub(r'^/announcetoall(@\w+)?\s*', '', raw_text, flags=re.IGNORECASE).strip()

    db = _get_db()
    # Collect ALL user IDs from users collection
    user_ids = []
    for d in db["users"].find({}, {"_id": 1}):
        try: user_ids.append(int(d["_id"]))
        except (ValueError, TypeError): pass

    # Collect ALL group IDs from groups collection
    group_ids = []
    for d in db["groups"].find({}, {"_id": 1}):
        try: group_ids.append(int(d["_id"]))
        except (ValueError, TypeError): pass

    # Also from broadcast meta
    doc = db["meta"].find_one({"_id": "broadcast"}) or {}
    all_targets = list(set(user_ids + group_ids + doc.get("groups", []) + doc.get("users", [])))

    if not all_targets:
        await update.message.reply_text("No known chats yet. Users must interact with bot first."); return

    status = await update.message.reply_text(
        f"📢 Broadcasting to {len(all_targets)} targets...\n_This may take a while_")
    sent = failed = 0
    has_media = bool(msg.photo or msg.video or msg.document or msg.animation or msg.audio or msg.voice)

    for tid in all_targets:
        try:
            if has_media:
                await context.bot.copy_message(
                    chat_id=tid, from_chat_id=msg.chat_id,
                    message_id=msg.message_id,
                    caption=text if text else None,
                    parse_mode="Markdown" if text else None)
            else:
                if not text:
                    continue
                await context.bot.send_message(chat_id=tid, text=text, parse_mode="Markdown")
            sent += 1
        except Exception as e:
            err_str = str(e).lower()
            if "flood" in err_str or "too many" in err_str:
                # Telegram flood control — wait and retry once
                try:
                    wait_secs = 10
                    import re as _re2
                    m2 = _re2.search(r'retry after (\d+)', err_str)
                    if m2: wait_secs = int(m2.group(1)) + 1
                    await asyncio.sleep(wait_secs)
                    if has_media:
                        await context.bot.copy_message(
                            chat_id=tid, from_chat_id=msg.chat_id,
                            message_id=msg.message_id,
                            caption=text if text else None)
                    else:
                        await context.bot.send_message(chat_id=tid, text=text, parse_mode="Markdown")
                    sent += 1
                except Exception:
                    failed += 1
            else:
                failed += 1
        # Respect Telegram rate limits: ~30 msgs/sec max, we do ~3/sec to be safe
        await asyncio.sleep(0.33)

        # Update status every 50 messages
        if (sent + failed) % 50 == 0:
            try:
                await status.edit_text(
                    f"📢 Broadcasting... {sent+failed}/{len(all_targets)}\n"
                    f"✅ {sent} | ❌ {failed}")
            except Exception:
                pass

    await status.edit_text(
        f"📢 *Broadcast Complete!*\n✅ Sent: *{sent}*\n❌ Failed: *{failed}*\n"
        f"_Failed = users who blocked bot or deleted account — normal!_",
        parse_mode="Markdown")

def _gen_redeem_code():
    """Generates a code in the AAAA-1111-BBBB shape that the redeem handler
    (see the custom-code block in handle_message) matches against via
    ^[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}$."""
    charset = string.ascii_uppercase + string.digits
    return "-".join("".join(random.choices(charset, k=4)) for _ in range(3))

async def cmd_makeredeemcodeforall(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    if user.id not in OWNER_IDS:
        return  # silently ignore for non-owners
    if len(context.args) < 2:
        await update.message.reply_text("Usage: /makeredeemcodeforall <count> <amount>"); return
    try:
        count = int(context.args[0]); amount = int(context.args[1])
    except Exception:
        await update.message.reply_text("❌ Both args must be numbers."); return
    if not (0 < count <= 200) or amount <= 0:
        await update.message.reply_text("❌ Count must be 1-200, amount must be positive."); return

    db = _get_db()
    existing_doc = db["meta"].find_one({"_id": "custom_codes"}) or {}
    all_codes = dict(existing_doc.get("codes", {}))  # local copy — never rely on
    # dot-path $set for nested fields; the SQLite shim doesn't guarantee Mongo's
    # dotted-key nesting semantics, and a silent no-op here is exactly what made
    # generated codes "not work" — read the whole dict, mutate in Python, write
    # the whole dict back with one flat (non-dotted) $set.
    codes = []
    for _ in range(count):
        code = _gen_redeem_code()
        while code in all_codes:  # avoid an (astronomically rare) collision
            code = _gen_redeem_code()
        all_codes[code] = {"amount": amount, "used": False}
        codes.append(code)
    db["meta"].update_one({"_id": "custom_codes"}, {"$set": {"codes": all_codes}}, upsert=True)

    text = f"🔑 *{count} codes generated — {amount} coins each (one-time use):*\n\n" + "\n".join(f"`{c}`" for c in codes)
    await update.message.reply_text(text, parse_mode="Markdown")


# ══════════════════════════════════════════════════════════════════════════════
#  SECRET OWNER COMMAND — /transferhardall <id1> <id2>
#  Full account-data migration: EVERY field (coins, gems, animals, weapons,
#  weapon levels, XP/level, streaks, badges, all win counters — literally
#  every key in _USER_DEFAULTS) moves from id1 into id2. id2's existing data
#  is fully overwritten (not merged). id1 is wiped back to a blank slate
#  afterwards. Requires a Yes/No confirmation showing both accounts' display
#  names (DB + live Telegram lookup) before anything happens.
# ══════════════════════════════════════════════════════════════════════════════
_pending_hard_transfers = {}   # token -> {id1, id2, owner_id, created_at}
HARD_TRANSFER_CONFIRM_TTL = 120  # seconds the confirmation prompt stays valid

async def _wc_live_identity(context, uid: int):
    """Best-effort live Telegram lookup — only works if the bot shares a
    chat with this user already. Returns None (not an error) otherwise."""
    try:
        chat = await context.bot.get_chat(uid)
        if getattr(chat, "username", None):
            return f"@{chat.username}"
        return getattr(chat, "full_name", None) or getattr(chat, "title", None)
    except Exception:
        return None

async def cmd_transferhardall(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    if user.id not in OWNER_IDS:
        return  # silently ignore for non-owners — secret command
    if len(context.args) != 2:
        await update.message.reply_text("Usage: /transferhardall <numeric_id1> <numeric_id2>")
        return
    try:
        id1 = int(context.args[0]); id2 = int(context.args[1])
    except ValueError:
        await update.message.reply_text("❌ Both IDs must be numeric Telegram user IDs.")
        return
    if id1 == id2:
        await update.message.reply_text("❌ Can't transfer an account into itself.")
        return

    data = load_data()
    k1, k2 = str(id1), str(id2)
    exists1 = k1 in data["users"]
    exists2 = k2 in data["users"]

    def _db_identity(k):
        if k not in data["users"]:
            return None
        u = data["users"][k]
        uname = u.get("username")
        if uname and uname != "Unknown":
            return f"@{uname}"
        return u.get("full_name") or None

    db_name1 = _db_identity(k1)
    db_name2 = _db_identity(k2)
    live_name1 = await _wc_live_identity(context, id1)
    live_name2 = await _wc_live_identity(context, id2)

    token = uuid.uuid4().hex[:12]
    _pending_hard_transfers[token] = {
        "id1": id1, "id2": id2, "owner_id": user.id, "created_at": datetime.now(),
    }

    def _fmt(db_name, live_name, exists, is_source):
        parts = []
        parts.append(f"  DB record: {_safe_md(db_name) if db_name else '_no data on file_'}")
        parts.append(f"  Telegram: {_safe_md(live_name) if live_name else '_could not fetch (no shared chat yet)_'}")
        if is_source and not exists:
            parts.append("  ⚠️ *No data found for this account — nothing to transfer.*")
        if not is_source and exists:
            parts.append("  ⚠️ *This account already has data — it will be OVERWRITTEN, not merged.*")
        return "\n".join(parts)

    lines = [
        "🛑 *HARD TRANSFER — CONFIRM CAREFULLY*",
        "_This moves ALL data (coins, gems, animals, weapons, weapon levels, "
        "XP/level, streaks, badges, every win counter) from account 1 into "
        "account 2, then wipes account 1 back to zero. This cannot be undone._",
        "",
        f"*FROM (id1):* `{id1}`",
        _fmt(db_name1, live_name1, exists1, is_source=True),
        "",
        f"*TO (id2):* `{id2}`",
        _fmt(db_name2, live_name2, exists2, is_source=False),
        "",
        "Confirm these are the *correct* accounts before proceeding.",
    ]
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ Yes, transfer everything", callback_data=f"hardxfer_yes_{token}"),
        InlineKeyboardButton("❌ Cancel", callback_data=f"hardxfer_no_{token}"),
    ]])
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown", reply_markup=kb)

async def handle_hard_transfer_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query.from_user.id not in OWNER_IDS:
        await query.answer("Not for you.", show_alert=True); return
    _, decision, token = query.data.split("_", 2)
    pending = _pending_hard_transfers.pop(token, None)
    try:
        await query.answer()
    except (BadRequest, TelegramError):
        pass  # stale/expired callback query — safe to ignore, continue handling
    if not pending:
        await _safe_edit_message_text(query, "⌛ This confirmation expired or was already used."); return
    if query.from_user.id != pending["owner_id"]:
        # Put it back — some other owner ID shouldn't consume someone else's pending confirm.
        _pending_hard_transfers[token] = pending
        await query.answer("Only the owner who started this can confirm it.", show_alert=True); return
    if (datetime.now() - pending["created_at"]).total_seconds() > HARD_TRANSFER_CONFIRM_TTL:
        await _safe_edit_message_text(query, "⌛ Confirmation expired — run /transferhardall again."); return
    if decision == "no":
        await _safe_edit_message_text(query, "❌ Hard transfer cancelled — nothing changed."); return

    id1, id2 = pending["id1"], pending["id2"]
    data = load_data()
    k1, k2 = str(id1), str(id2)

    u1 = get_user(data, id1)  # pulls (or creates) a fresh, fully-populated source record
    keep_username2 = data["users"].get(k2, {}).get("username", "Unknown")
    keep_fullname2 = data["users"].get(k2, {}).get("full_name", "Unknown")

    # id2 gets EVERY field from id1 (full overwrite, not a merge) — except id2
    # keeps its own Telegram username/full_name, which get re-synced from
    # Telegram automatically the next time id2 messages the bot anyway.
    new_u2 = dict(u1)
    new_u2["username"]  = keep_username2
    new_u2["full_name"] = keep_fullname2
    data["users"][k2] = new_u2

    # id1 is wiped back to a completely blank slate (identity fields kept).
    old_username1 = u1.get("username", "Unknown")
    old_fullname1 = u1.get("full_name", "Unknown")
    fresh1 = {k: (v.copy() if isinstance(v, (dict, list)) else v) for k, v in _USER_DEFAULTS.items()}
    fresh1["username"]  = old_username1
    fresh1["full_name"] = old_fullname1
    data["users"][k1] = fresh1

    save_data(data)
    logger.info(f"[HARD TRANSFER] owner {pending['owner_id']} moved ALL data from {id1} to {id2}")

    await _safe_edit_message_text(query, 
        f"✅ *Hard transfer complete!*\n"
        f"`{id1}` → wiped to zero.\n"
        f"`{id2}` → now holds everything `{id1}` had — coins, gems, animals, "
        f"weapons, levels, streaks, badges & wins.",
        parse_mode="Markdown")


async def analyze_image_with_ai(file_path, target_object):
    """Checks whether a submitted photo shows `target_object`, for /challenge's
    photo round. Returns a tuple (verdict, reason):
        verdict = True   -> confirmed a match
        verdict = False  -> confirmed NO match
        verdict = None   -> couldn't get a real verdict (model/network error) —
                             the caller must NOT treat this as a loss, since
                             that would unfairly fail a correct submission.

    FIX: previously hardcoded "llama-3.2-90b-vision-preview", a Groq model
    retired in April 2025. Every call 400'd, landed in the except block, and
    silently returned False — so the bot said "AI says no" for literally
    every photo, no matter what was in it. Now uses GROQ_VISION_MODEL
    (currently qwen/qwen3.6-27b), asks for a structured JSON verdict instead
    of a loose "yes"/"no" string (much harder to misparse), and distinguishes
    real API failures from a genuine "no match" so users aren't penalized
    for an outage.

    NOTE: Groq's own docs flag qwen/qwen3.6-27b as a *preview* model ("not
    for production"), so it can be flakier than a GA model. If the primary
    call fails outright (not just "no match"), this retries against
    GROQ_VISION_MODEL_FALLBACK (qwen/qwen3.8-27b), then — if OPENROUTER_API_KEY
    is set — against OpenRouter's "openrouter/free" auto-router as a third,
    fully independent leg (different company/infra entirely from Groq), before
    giving up. If ALL fail, run /aistatus — it live-tests every leg separately
    and prints the exact HTTP status/body each one returned, instead of
    guessing here.
    """
    _ai_health["vision"]["last_checked"] = datetime.now().isoformat()
    try:
        import base64
        with open(file_path, "rb") as f:
            raw = f.read()
        if len(raw) > 19 * 1024 * 1024:  # Groq's vision limit is 20MB/image
            _ai_health["vision"]["ok"] = False
            _ai_health["vision"]["last_error"] = "image too large"
            return None, "Photo too large — please send a smaller image and try again."
        encoded = base64.b64encode(raw).decode("utf-8")

        prompt = (
            f'Look at this photo. Does it clearly show "{target_object}"? '
            'Be reasonably lenient — partial views, different angles, or '
            'drawings/printouts of the object still count as a match. '
            'Reply with ONLY a JSON object, no markdown, no extra text: '
            '{"match": true or false, "confidence": 0-100, "reason": "one short sentence"}'
        )
        content_payload = [
            {"type": "text", "text": prompt},
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{encoded}"}},
        ]

        async def _call_groq(model):
            payload = {
                "model": model,
                "messages": [{"role": "user", "content": content_payload}],
                "temperature": 0.2,
                "max_completion_tokens": 600,  # was 150 — qwen3 always emits a
                # visible <think> block before the JSON (confirmed live via
                # /aistatus) and can't fully disable reasoning, so 150 tokens
                # was getting cut off mid-thought before ever reaching the
                # actual JSON verdict. 600 gives real headroom for both.
                "response_format": {"type": "json_object"},
            }
            if any(fam in model.lower() for fam in ("gpt-oss", "qwen3")):
                payload["reasoning_format"] = "hidden"
                payload["reasoning_effort"] = "default"  # Groq only accepts "none" or "default"
            async with httpx.AsyncClient(timeout=30) as client:
                return await client.post(
                    "https://api.groq.com/openai/v1/chat/completions",
                    headers={"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"},
                    json=payload,
                )

        async def _call_openrouter(model):
            async with httpx.AsyncClient(timeout=30) as client:
                return await client.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                        "Content-Type": "application/json",
                        "HTTP-Referer": OPENROUTER_SITE_URL,
                        "X-Title": OPENROUTER_APP_NAME,
                    },
                    json={
                        "model": model,
                        "messages": [{"role": "user", "content": content_payload}],
                        "temperature": 0.2,
                        "max_tokens": 600,
                        "response_format": {"type": "json_object"},
                    },
                )

        attempts = [("groq", GROQ_VISION_MODEL), ("groq", GROQ_VISION_MODEL_FALLBACK)]
        if OPENROUTER_API_KEY:
            attempts.append(("openrouter", OPENROUTER_VISION_MODEL))

        last_err = None
        content = None
        for provider, model in attempts:
            if not model:
                continue
            call = _call_groq if provider == "groq" else _call_openrouter
            try:
                resp = await call(model)
                if resp.status_code == 429:
                    await asyncio.sleep(2)
                    resp = await call(model)
                if resp.status_code != 200:
                    last_err = f"[{provider}:{model}] HTTP {resp.status_code}: {resp.text[:300]}"
                    continue
                # A 200 with empty/unparseable content is NOT a success — this
                # is exactly the case that used to make the whole check silently
                # fail (a reasoning model burning its entire token budget on
                # hidden thinking, "success" HTTP-wise but nothing usable back).
                # Falling through to the next leg here instead of stopping at
                # the first 200 is what actually makes the fallback chain work.
                extracted = _extract_content(resp.json())
                if not extracted:
                    last_err = f"[{provider}:{model}] HTTP 200 but empty content"
                    continue
                content = extracted
                break
            except Exception as e:
                last_err = f"[{provider}:{model}] {e}"

        if content is None:
            logger.error(f"Vision API error (all providers failed): {last_err}")
            _ai_health["vision"]["ok"] = False
            _ai_health["vision"]["last_error"] = last_err
            return None, "Vision check is temporarily unavailable — try again in a bit."

        import re as _re3, json as _json3
        m = _re3.search(r"\{.*\}", content, _re3.DOTALL)
        parsed = _json3.loads(m.group(0)) if m else _json3.loads(content)
        verdict = bool(parsed.get("match"))
        confidence = parsed.get("confidence", 100 if verdict else 0)
        reason = str(parsed.get("reason", "")).strip()

        # Low-confidence "yes" is treated as unclear rather than a hard win —
        # avoids rewarding obviously-wrong guesses the model wasn't sure about.
        if verdict and isinstance(confidence, (int, float)) and confidence < 40:
            verdict = False

        _ai_health["vision"]["ok"] = True
        _ai_health["vision"]["last_success"] = datetime.now().isoformat()
        _vision_available = True  # vision confirmed working — photo challenges re-enabled
        return verdict, reason
    except Exception as e:
        logger.error(f"Vision error: {e}")
        _ai_health["vision"]["ok"] = False
        _ai_health["vision"]["last_error"] = str(e)[:300]
        return None, "Vision check is temporarily unavailable — try again in a bit."

# ══════════════════════════════════════════════════════════════════════════════
#  FLASK KEEP-ALIVE
# ══════════════════════════════════════════════════════════════════════════════
flask_app = Flask('')

@flask_app.route('/')
def home():
    return "Aira v9 is running!"

@flask_app.route('/manual')
def manual_page():
    return build_manual_html()

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    flask_app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = threading.Thread(target=run_flask)
    t.daemon = True
    t.start()



async def cmd_checkuserbase(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Owner-only: full analytics dashboard — users, groups, coins, command
    usage ('views'), plus CPU/RAM/disk system metrics and a downloadable
    file with every user and every group the bot knows about."""
    user = update.message.from_user
    if user.id not in OWNER_IDS:
        return  # silent
    db = _get_db()
    status = await update.message.reply_text("📊 Crunching analytics…")

    # ── System health (CPU / RAM / Disk) ─────────────────────────────────
    def _fmt_bytes(n):
        """Human-readable bytes: KB/MB/GB."""
        for unit in ("B","KB","MB","GB","TB"):
            if n < 1024:
                return f"{n:.1f} {unit}"
            n /= 1024
        return f"{n:.1f} PB"

    if _psutil:
        cpu_pct   = _psutil.cpu_percent(interval=1)           # 1-sec sample — blocks briefly but gives a real reading
        vm        = _psutil.virtual_memory()
        ram_used  = _fmt_bytes(vm.used)
        ram_total = _fmt_bytes(vm.total)
        ram_pct   = vm.percent
        disk      = _psutil.disk_usage("/")
        disk_used = _fmt_bytes(disk.used)
        disk_total= _fmt_bytes(disk.total)
        disk_pct  = disk.percent
        sys_lines = [
            f"\n⚙️ *SYSTEM HEALTH*",
            f"🖥️ CPU:  *{cpu_pct:.1f}%*",
            f"💾 RAM:  *{ram_used} / {ram_total}* ({ram_pct:.1f}%)",
            f"💿 Disk: *{disk_used} / {disk_total}* ({disk_pct:.1f}%)",
        ]
    else:
        sys_lines = ["\n⚙️ _System metrics unavailable_",
                     "_Run: `cd /home/azureuser/aira-bot/aira-python-sqlite && source venv/bin/activate && pip install psutil` then restart._"]

    # ── Bot uptime ────────────────────────────────────────────────────────
    uptime_secs = int(time.time() - BOT_START_TIME)
    _ud, rem  = divmod(uptime_secs, 86400)
    _uh, rem  = divmod(rem, 3600)
    _um, _us  = divmod(rem, 60)
    uptime_str = f"{_ud}d {_uh}h {_um}m {_us}s"

    # ── Users ────────────────────────────────────────────────────────────
    all_users = list(db["users"].find({}, {
        "_id": 1, "username": 1, "full_name": 1, "coins": 1,
        "wins": 1, "level": 1, "daily_streak": 1, "hunts": 1, "gems": 1,
    }).sort("coins", -1))
    total_users = len(all_users)
    total_coins = sum(u.get("coins", 0) for u in all_users)
    total_gems  = sum(u.get("gems", 0) for u in all_users)
    today_iso = datetime.now().date().isoformat()
    active_today = sum(1 for u in all_users if u.get("daily_claimed") == today_iso)

    # ── Groups the bot is in ────────────────────────────────────────────
    # Combine every source we have: the "groups" collection (written when a
    # group changes settings) and the silent broadcast tracker (written the
    # instant ANY member of that group runs a command) — same union logic
    # /announcetoall relies on, so this always matches what a broadcast
    # would actually reach.
    group_docs = list(db["groups"].find({}, {"_id": 1}))
    group_ids_from_collection = set()
    for d in group_docs:
        try: group_ids_from_collection.add(int(d["_id"]))
        except (ValueError, TypeError): pass
    broadcast_doc = db["meta"].find_one({"_id": "broadcast"}) or {}
    group_ids = sorted(group_ids_from_collection | set(broadcast_doc.get("groups", [])))
    tracked_user_ids = set(broadcast_doc.get("users", []))
    total_group_count = len(group_ids)

    db_user_ids = set()
    for u in all_users:
        try: db_user_ids.add(int(u["_id"]))
        except (ValueError, TypeError): pass
    total_users_seen = len(db_user_ids | tracked_user_ids)

    # Try to pull live name + member count for each known group. Capped and
    # rate-limited so a bot in hundreds of groups doesn't hit flood limits.
    group_info = []
    for gid in group_ids[:60]:
        try:
            chat = await context.bot.get_chat(gid)
            try:
                member_count = await context.bot.get_chat_member_count(gid)
            except Exception:
                member_count = "?"
            # Build a real join link instead of just the raw chat ID (which
            # can't be opened/joined by tapping it — only copied).
            link = None
            if getattr(chat, "username", None):
                link = f"https://t.me/{chat.username}"
            elif getattr(chat, "invite_link", None):
                link = chat.invite_link
            else:
                # Bot needs to be an admin with invite rights for this to work.
                # Uses create_chat_invite_link (NOT export_chat_invite_link) so
                # it never revokes/replaces any invite link already in use.
                try:
                    invite = await context.bot.create_chat_invite_link(chat_id=gid, name="Aira Analytics")
                    link = invite.invite_link
                except Exception:
                    link = None
            group_info.append({"id": gid, "title": chat.title or str(gid), "members": member_count, "link": link})
        except Exception:
            group_info.append({"id": gid, "title": "(left / inaccessible)", "members": "?", "link": None})
        await asyncio.sleep(0.1)

    # ── Command usage ("total views") ───────────────────────────────────
    stats_doc = db["meta"].find_one({"_id": "command_stats"}) or {}
    total_commands_used = stats_doc.get("total", 0)
    by_command = stats_doc.get("by_command", {})
    top_commands = sorted(by_command.items(), key=lambda kv: kv[1], reverse=True)[:10]

    # ── Extra growth metrics ─────────────────────────────────────────────
    now_dt    = datetime.now(timezone.utc)
    cutoff_7d  = (now_dt - timedelta(days=7)).date().isoformat()
    cutoff_30d = (now_dt - timedelta(days=30)).date().isoformat()
    # "joined_date" is set as ISO date string when a user doc is first created;
    # fall back to counting all users if the field isn't populated yet.
    new_7d  = sum(1 for u in all_users if str(u.get("joined_date", "")) >= cutoff_7d)
    new_30d = sum(1 for u in all_users if str(u.get("joined_date", "")) >= cutoff_30d)
    total_referrals = sum(u.get("referral_count", 0) for u in all_users)
    avg_coins = (total_coins // total_users) if total_users else 0

    # ── Summary message ─────────────────────────────────────────────────
    lines = [
        f"👥 ✦ *{fancy('AIRA ANALYTICS REPORT')}* ✦\n┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄",
        f"⏱️ Bot Uptime: *{uptime_str}*",
    ] + sys_lines + [
        f"\n👥 *USER BASE*",
        f"📊 Total Users (DB rows): *{total_users:,}*",
        f"👤 Users Ever Seen (incl. no-DB): *{total_users_seen:,}*",
        f"🆕 New (last 7 days): *{new_7d:,}*",
        f"📅 New (last 30 days): *{new_30d:,}*",
        f"✅ Active Today (claimed daily): *{active_today:,}*",
        f"🤝 Total Referrals Made: *{total_referrals:,}*",
        f"\n💰 *ECONOMY*",
        f"🪙 Total Coins in Circulation: *{total_coins:,}*",
        f"📈 Avg Coins per User: *{avg_coins:,}*",
        f"💎 Total Gems in Circulation: *{total_gems:,}*",
        f"\n🌐 *REACH*",
        f"💬 Total Groups: *{total_group_count:,}*",
        f"👀 Total Command Uses (all-time): *{total_commands_used:,}*",
    ]
    if top_commands:
        lines.append("\n*Top 10 Commands by Usage:*")
        for i, (name, count) in enumerate(top_commands, 1):
            lines.append(f"{i}. /{name} — {count:,} uses")

    lines.append("\n*Top 20 Users by Coins:*")
    medals = ["🥇","🥈","🥉"] + [f"{i}." for i in range(4, 21)]
    for i, u in enumerate(all_users[:20]):
        name = _safe_md(u.get("full_name", "?")[:20])
        tag  = f"@{_safe_md(u['username'])}" if u.get("username") and u["username"] != "Unknown" else name
        lines.append(
            f"{medals[i]} {tag}\n"
            f"   🪙{u.get('coins',0):,} | 🏆{u.get('wins',0)} wins | "
            f"Lv{u.get('level',1)} | 🎯{u.get('hunts',0)} hunts"
        )

    if group_info:
        lines.append(f"\n*Groups (first {len(group_info)} of {total_group_count}):*")
        for g in sorted(group_info, key=lambda g: (g["members"] if isinstance(g["members"], int) else -1), reverse=True)[:20]:
            title = _safe_md(g['title'])
            if g.get("link"):
                # Tappable title that opens/joins the group directly.
                lines.append(f"✧ [{title}]({g['link']}) — 👥{g['members']} (`{g['id']}`)")
            else:
                lines.append(f"✧ {title} — 👥{g['members']} (`{g['id']}`) _(no join link available)_")

    # Chunk on LINE boundaries, never mid-string — a fixed-offset char split
    # can cut a "*bold*"/"`code`" token in half across two messages, which is
    # exactly what caused the "can't find end of the entity" BadRequest.
    def _chunk_lines(all_lines, limit=3500):
        chunks, current = [], ""
        for line in all_lines:
            candidate = f"{current}\n{line}" if current else line
            if len(candidate) > limit and current:
                chunks.append(current)
                current = line
            else:
                current = candidate
        if current:
            chunks.append(current)
        return chunks

    chunks = _chunk_lines(lines)
    try:
        await status.delete()
    except Exception:
        pass
    for chunk in chunks:
        try:
            await update.message.reply_text(chunk, parse_mode="Markdown")
        except Exception:
            # Last-resort fallback: never let a stray unescaped char from a
            # group title/username kill the whole report — send it plain.
            await update.message.reply_text(chunk)

    # ── Full data dump as a downloadable file ───────────────────────────
    import io
    sys_summary = ""
    if _psutil:
        sys_summary = (
            f"CPU: {cpu_pct:.1f}%  |  "
            f"RAM: {ram_used}/{ram_total} ({ram_pct:.1f}%)  |  "
            f"Disk: {disk_used}/{disk_total} ({disk_pct:.1f}%)\n"
        )
    full_list  = f"Aira Analytics Report — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
    full_list += f"Bot Uptime: {uptime_str}\n"
    full_list += sys_summary
    full_list += f"New users (7d): {new_7d} | New users (30d): {new_30d} | Total referrals: {total_referrals}\n"
    full_list += "\n═══ USERS ═══\n"
    full_list += "ID | Username | Name | Coins | Gems | Wins | Level | Hunts | Daily Streak | Referrals\n"
    full_list += "-" * 95 + "\n"
    for u in all_users:
        full_list += (
            f"{u['_id']} | @{u.get('username','?')} | {u.get('full_name','?')} | "
            f"{u.get('coins',0)} | {u.get('gems',0)} | {u.get('wins',0)} | {u.get('level',1)} | "
            f"{u.get('hunts',0)} | {u.get('daily_streak',0)} | {u.get('referral_count',0)}\n"
        )
    full_list += f"\n═══ GROUPS ({total_group_count}) ═══\n"
    full_list += "ID | Title | Members | Join Link\n" + "-" * 80 + "\n"
    known_titles = {g["id"]: g for g in group_info}
    for gid in group_ids:
        g = known_titles.get(gid, {"title": "(not fetched)", "members": "?", "link": None})
        full_list += f"{gid} | {g['title']} | {g['members']} | {g.get('link') or '(none)'}\n"
    full_list += f"\n═══ COMMAND USAGE ({total_commands_used} total) ═══\n"
    for name, count in sorted(by_command.items(), key=lambda kv: kv[1], reverse=True):
        full_list += f"/{name}: {count}\n"

    buf = io.BytesIO(full_list.encode("utf-8"))
    buf.name = f"aira_analytics_{datetime.now().strftime('%Y%m%d_%H%M')}.txt"
    await update.message.reply_document(
        document=buf,
        caption=f"📋 Full analytics dump — {total_users} users, {total_group_count} groups")




    # ══════════════════════════════════════════════════════════════════════════════
#  WEEKLY LOTTERY — Entry 15,000 coins, draws Sunday 3PM IST, prizes scale
# ══════════════════════════════════════════════════════════════════════════════
LOTTERY_ENTRY_FEE = 15000
LOTTERY_PRIZES    = {
    "1st": 100000,
    "2nd": 50000,
    "3rd": 25000,
}

async def cmd_lottery(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    sub  = (context.args[0].lower() if context.args else "")

    db  = _get_db()
    doc = db["meta"].find_one({"_id": "lottery"}) or {"_id": "lottery", "participants": {}, "pool": 0}

    if sub == "join":
        uid = str(user.id)
        if uid in doc.get("participants", {}):
            await update.message.reply_text("✅ Already entered! Good luck 🍀"); return
        user_doc = get_user_fast(uid)
        if user_doc.get("coins", 0) < LOTTERY_ENTRY_FEE:
            await update.message.reply_text(
                f"❌ Need *{LOTTERY_ENTRY_FEE:,} 🪙* to enter. You have *{user_doc.get('coins',0):,}*.",
                parse_mode="Markdown"); return
        user_doc["coins"] -= LOTTERY_ENTRY_FEE
        save_user_fast(uid)
        doc.setdefault("participants", {})[uid] = _safe_md(user.full_name)
        doc["pool"] = doc.get("pool", 0) + LOTTERY_ENTRY_FEE
        db["meta"].replace_one({"_id": "lottery"}, doc, upsert=True)
        count = len(doc["participants"])
        await update.message.reply_text(
            f"🎟️ *You're in the lottery!*\n"
            f"💸 Entry fee: *{LOTTERY_ENTRY_FEE:,} 🪙* deducted\n"
            f"👥 Current participants: *{count}*\n"
            f"⏰ Draw: *Every Sunday @ 3PM IST*\n\n"
            f"Prizes (by participant count):\n"
            f"  1-29: 🥇 *{LOTTERY_PRIZES['1st']:,} 🪙*\n"
            f"  30-49: 🥇 *{LOTTERY_PRIZES['1st']:,}* + 🥈 *{LOTTERY_PRIZES['2nd']:,}*\n"
            f"  50+: 🥇🥈🥉 *+{LOTTERY_PRIZES['3rd']:,}*",
            parse_mode="Markdown")

    elif sub == "status":
        participants = doc.get("participants", {})
        count = len(participants)
        winners_count = 1 if count < 30 else (2 if count < 50 else 3)
        next_draw = _next_sunday_3pm_ist()
        await update.message.reply_text(
            f"🎰 ✦ *{fancy('LOTTERY STATUS')}* ✦\n┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄\n"
            f"👥 Participants: *{count}*\n"
            f"💰 Prize pool: *{doc.get('pool',0):,} 🪙*\n"
            f"🏆 Winners this draw: *{winners_count}*\n"
            f"⏰ Next draw: *{next_draw}*\n\n"
            f"{'✅ You are entered!' if str(user.id) in participants else '❌ Not entered. `/lottery join`'}",
            parse_mode="Markdown")

    elif sub == "draw" and user.id in OWNER_IDS:
        await _run_lottery_draw(context, update.message.chat_id)

    else:
        await update.message.reply_text(
            f"🎰 ✦ *{fancy('WEEKLY LOTTERY')}* ✦\n┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄\n"
            f"Entry fee: *{LOTTERY_ENTRY_FEE:,} 🪙*\n"
            f"Draw: Every *Sunday @ 3PM IST*\n\n"
            f"`/lottery join` — Enter the lottery\n"
            f"`/lottery status` — See current pool\n\n"
            f"Prize tiers:\n"
            f"  <30 players → 1 winner (*100K 🪙*)\n"
            f"  30-49 → 2 winners (*100K + 50K*)\n"
            f"  50+ → 3 winners (*100K + 50K + 25K*)",
            parse_mode="Markdown")

def _next_sunday_3pm_ist():
    """Returns string of next Sunday 3PM IST."""
    from datetime import timezone, timedelta as td
    IST  = timezone(td(hours=5, minutes=30))
    now  = datetime.now(IST)
    days_until_sunday = (6 - now.weekday()) % 7
    if days_until_sunday == 0 and now.hour >= 15:
        days_until_sunday = 7
    next_sun = now + td(days=days_until_sunday)
    return next_sun.strftime("%A, %d %b %Y at 3:00 PM IST")

async def _run_lottery_draw(context, announce_chat_id=None):
    """Runs the lottery draw. Call from scheduled job or /lottery draw (owner)."""
    db  = _get_db()
    doc = db["meta"].find_one({"_id": "lottery"})
    if not doc or not doc.get("participants"):
        if announce_chat_id:
            try: await context.bot.send_message(announce_chat_id, "🎰 No lottery participants this week!")
            except Exception: pass
        return

    participants = doc["participants"]  # {uid_str: name}
    count        = len(participants)
    n_winners    = 1 if count < 30 else (2 if count < 50 else 3)
    prize_keys   = ["1st", "2nd", "3rd"][:n_winners]

    winner_uids = random.sample(list(participants.keys()), min(n_winners, count))
    result_lines = [f"🎰 ✦ *{fancy('LOTTERY DRAW RESULTS!')}* ✦\n┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄\n👥 {count} participants\n"]

    for i, uid_str in enumerate(winner_uids):
        prize  = LOTTERY_PRIZES[prize_keys[i]]
        name   = participants[uid_str]
        # BUGFIX: was reading/writing db["users"] directly, bypassing the
        # shared cache — same stale-overwrite bug as do_hunt/auto_hunt_job
        # had. Routed through get_user_fast/save_user_fast like everything
        # else now.
        u_doc = get_user_fast(uid_str)
        u_doc["coins"] = u_doc.get("coins", 0) + prize
        u_doc["total_coins_ever"] = u_doc.get("total_coins_ever", 0) + prize
        save_user_fast(uid_str)
        medal = ["🥇","🥈","🥉"][i]
        result_lines.append(f"{medal} *{name}* wins *{prize:,} 🪙*!")
        # DM the winner
        try:
            await context.bot.send_message(
                int(uid_str),
                f"🎰 *{fancy('LOTTERY WINNER!')}* 🎉\n"
                f"You won *{prize:,} 🪙* in this week's lottery!\n"
                f"💰 Added to your wallet!", parse_mode="Markdown")
        except Exception: pass

    # Notify all participants
    all_participants = list(participants.keys())
    result_text = "\n".join(result_lines)
    for uid_str in all_participants:
        if uid_str in winner_uids: continue
        try:
            await context.bot.send_message(
                int(uid_str),
                f"🎰 *Lottery Results:*\n{result_text}\n\n_Better luck next week!_",
                parse_mode="Markdown")
        except Exception: pass
        await asyncio.sleep(0.2)

    # Reset lottery
    db["meta"].replace_one({"_id": "lottery"}, {"_id": "lottery", "participants": {}, "pool": 0}, upsert=True)

    if announce_chat_id:
        try:
            await context.bot.send_message(announce_chat_id, result_text, parse_mode="Markdown")
        except Exception: pass

async def _schedule_lottery_job(context: ContextTypes.DEFAULT_TYPE):
    """Called by scheduler — runs the lottery draw."""
    await _run_lottery_draw(context)

def _setup_lottery_schedule(app):
    """Sets up weekly Sunday 3PM IST job. Call from main()."""
    from datetime import timezone, timedelta as td
    IST  = timezone(td(hours=5, minutes=30))
    now  = datetime.now(IST)
    days_until_sunday = (6 - now.weekday()) % 7
    if days_until_sunday == 0 and now.hour >= 15:
        days_until_sunday = 7
    next_sun  = now + td(days=days_until_sunday)
    next_3pm  = next_sun.replace(hour=15, minute=0, second=0, microsecond=0)
    delay_sec = (next_3pm - datetime.now(IST)).total_seconds()
    app.job_queue.run_repeating(
        _schedule_lottery_job,
        interval=7 * 24 * 3600,  # weekly
        first=max(5, delay_sec),
        name="weekly_lottery")
    logger.info(f"Lottery scheduled — first draw in {delay_sec/3600:.1f}h")
# ══════════════════════════════════════════════════════════════════════════════
#  GLOBAL ERROR HANDLER — makes silent crashes visible
#  ── Before this, an unhandled exception anywhere (a handler or a job) just
#     vanished into PTB's internal logger with nobody watching. That's why
#     bugs like the Word Chain crash (`user["coins"]` on a raw Telegram User
#     object) just looked like "the game stopped working" with zero trace.
#     Now every such exception gets logged AND DMed to the owner with enough
#     context (which update/job, what error) to actually debug it, instead of
#     guessing from user reports days later.
# ══════════════════════════════════════════════════════════════════════════════
_last_error_dm = {}   # dedupe key -> datetime, so one repeating bug doesn't spam DMs
_ERROR_DM_COOLDOWN = 120  # seconds between DMs for the *same* error signature

async def global_error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    err = context.error

    # RetryAfter = Telegram flood control. The send wrappers already sleep+retry;
    # if it still bubbles up here it means 3 retries were exhausted on a burst.
    # Log it for visibility but DO NOT DM the owner — it resolves on its own.
    if isinstance(err, RetryAfter):
        logger.warning(f"[FloodControl] RetryAfter {err.retry_after}s — burst traffic, auto-resolving.")
        return

    # Telegram sends these for completely benign timing races — a user
    # double-tapping the same button (message content unchanged), tapping a
    # button on a message/callback that's since expired, or a message that
    # got deleted before the edit landed. None of these are bugs; DMing the
    # owner for every one of them is just noise, so filter them out here
    # instead of having to wrap every single query.answer()/edit_message_text
    # call site individually.
    _BENIGN_BADREQUEST_SNIPPETS = (
        "message is not modified",
        "query is too old",
        "query id is invalid",
        "message to edit not found",
        "message can't be edited",
        "message to delete not found",
    )
    if isinstance(err, BadRequest) and any(s in str(err).lower() for s in _BENIGN_BADREQUEST_SNIPPETS):
        logger.info(f"Suppressed benign BadRequest: {err}")
        return

    where = "unknown"
    chat_id_for_report = None
    try:
        if isinstance(update, Update) and update.effective_chat:
            chat_id_for_report = update.effective_chat.id
            where = f"chat {chat_id_for_report}"
        elif hasattr(context, "job") and context.job is not None:
            where = f"job '{context.job.name}'"
    except Exception:
        pass

    # A group admin revoked the bot's "Send Messages" right, made the group
    # admin-only, or removed the bot outright. This is an OPERATIONAL state
    # in that specific chat, not a code bug — a full stack-trace dump is
    # alarming and unhelpful (nothing in the source needs fixing), so this
    # gets one short, actionable notice per chat instead, on its own
    # (much longer) cooldown, and skips the traceback path entirely.
    _PERMISSION_BADREQUEST_SNIPPETS = (
        "not enough rights to send",
        "have no rights to send a message",
        "chat_write_forbidden",
        "bot was kicked",
        "bot is not a member of the",
        "chat not found",
        "user is deactivated",
        "bot was blocked by the user",
    )
    if isinstance(err, BadRequest) and any(s in str(err).lower() for s in _PERMISSION_BADREQUEST_SNIPPETS):
        logger.warning(f"Permission/membership issue in {where}: {err}")
        perm_sig = f"perm:{chat_id_for_report}:{str(err).lower()[:80]}"
        now = datetime.now()
        last = _last_error_dm.get(perm_sig)
        if last and (now - last).total_seconds() < max(_ERROR_DM_COOLDOWN, 6 * 3600):
            return  # already told the owner about this exact chat recently
        _last_error_dm[perm_sig] = now
        notice = (
            f"ℹ️ Can't message {where}: `{str(err)[:200]}`\n"
            f"_Nothing to fix in the code — an admin there needs to restore the bot's "
            f"send permissions, un-restrict the chat, or re-add the bot. Aira will just "
            f"go quiet in that chat until then._"
        )
        for owner_id in OWNER_IDS:
            try:
                await context.bot.send_message(owner_id, notice, parse_mode="Markdown")
            except Exception:
                pass
        return

    logger.error("Unhandled exception", exc_info=err)

    import traceback
    tb = "".join(traceback.format_exception(type(err), err, err.__traceback__))
    sig = f"{type(err).__name__}:{tb.strip().splitlines()[-1] if tb.strip() else ''}"[:200]

    now = datetime.now()
    last = _last_error_dm.get(sig)
    if last and (now - last).total_seconds() < _ERROR_DM_COOLDOWN:
        return  # same error just fired recently, don't spam
    _last_error_dm[sig] = now

    short_tb = tb[-3000:]  # Telegram messages cap at 4096 chars
    report = (
        f"🚨 *Bot error* (in {where})\n"
        f"`{type(err).__name__}: {str(err)[:300]}`\n\n"
        f"```\n{short_tb}\n```"
    )
    for owner_id in OWNER_IDS:
        try:
            await context.bot.send_message(owner_id, report, parse_mode="Markdown")
        except Exception:
            try:
                await context.bot.send_message(owner_id, report)  # retry plain, Markdown in traceback can break parsing
            except Exception:
                pass

# ══════════════════════════════════════════════════════════════════════════════
#  /latency — round-trip ping
# ══════════════════════════════════════════════════════════════════════════════
async def cmd_latency(update: Update, context: ContextTypes.DEFAULT_TYPE):
    sent_at = datetime.now()
    msg = await update.message.reply_text("🏓 Pinging...")
    api_ms = (datetime.now() - sent_at).total_seconds() * 1000
    msg_age_ms = (sent_at - update.message.date.replace(tzinfo=None)).total_seconds() * 1000
    await msg.edit_text(
        f"🏓 *Pong!*\n"
        f"📡 API round-trip: *{api_ms:.0f}ms*\n"
        f"📨 Update delivery lag: *{max(0, msg_age_ms):.0f}ms*",
        parse_mode="Markdown")

# ══════════════════════════════════════════════════════════════════════════════
#  /reportbug — DMs the owner directly (separate from /report, which reports
#  a member to the group's own admins)
# ══════════════════════════════════════════════════════════════════════════════
async def cmd_reportbug(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    if not context.args:
        await update.message.reply_text(
            "🐛 Usage: `/reportbug <description of the bug>`", parse_mode="Markdown"); return
    text = " ".join(context.args)
    name = _safe_md(f"@{user.username}" if user.username else user.full_name)
    chat = update.message.chat
    chat_desc = f"{chat.title} ({chat.id})" if chat.type != "private" else "DM"

    report_id = uuid.uuid4().hex[:8]
    _bug_reports[report_id] = {
        "reporter_id": user.id,
        "reporter_name": user.full_name,
        "reporter_username": user.username,
        "text": text,
        "status": "pending",
        "created_at": datetime.now(),
        "owner_messages": {},  # owner_id -> message_id, lets owner replies route back
    }

    report = (
        f"🐛 *Bug report* `#{report_id}` from {name} (`{user.id}`)\n"
        f"📍 From: {_safe_md(chat_desc)}\n\n"
        f"{_safe_md(text)}\n\n"
        f"_Reply to this message (in DM) to send a message straight to the reporter._"
    )
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ Approve (+100 🪙)", callback_data=f"bug_ok_{report_id}"),
        InlineKeyboardButton("❌ Deny", callback_data=f"bug_no_{report_id}"),
    ]])
    sent_ok = False
    for owner_id in OWNER_IDS:
        try:
            m = await context.bot.send_message(owner_id, report, parse_mode="Markdown", reply_markup=kb)
            _bug_reports[report_id]["owner_messages"][owner_id] = m.message_id
            sent_ok = True
        except Exception as e:
            logger.error(f"reportbug DM failed: {e}")
    if sent_ok:
        await update.message.reply_text("✅ Thanks! Your bug report was sent to the owner.")
    else:
        await update.message.reply_text("⚠️ Couldn't reach the owner right now, but the report was logged.")

async def handle_bug_report_decision(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data or ""
    try:
        _, verdict, report_id = data.split("_", 2)
    except ValueError:
        try:
            await query.answer()
        except (BadRequest, TelegramError):
            pass  # stale/expired callback query — safe to ignore
        return
    if query.from_user.id not in OWNER_IDS:
        await query.answer("Owner only.", show_alert=True); return
    report = _bug_reports.get(report_id)
    if not report:
        await query.answer("This report is no longer available.", show_alert=True); return
    if report["status"] != "pending":
        await query.answer(f"Already {report['status']}.", show_alert=True); return

    if verdict == "ok":
        report["status"] = "approved"
        u = get_user_fast(str(report["reporter_id"]))
        u["coins"] = u.get("coins", 0) + 100
        u["total_coins_ever"] = u.get("total_coins_ever", 0) + 100
        save_user_fast(report["reporter_id"])
        try:
            await context.bot.send_message(
                report["reporter_id"],
                "🎉 Your bug report was *approved*!\n💰 +100 🪙 added to your wallet — "
                "thanks for helping improve Aira!", parse_mode="Markdown")
        except Exception:
            pass
        await query.answer("Approved — 100 coins sent!")
        suffix = "\n\n✅ *APPROVED — 100 coins sent to reporter*"
    else:
        report["status"] = "denied"
        await query.answer("Denied.")
        suffix = "\n\n❌ *DENIED — no reward given*"

    try:
        await query.edit_message_text((query.message.text or "") + suffix, parse_mode="Markdown")
    except Exception:
        try:
            await query.edit_message_reply_markup(reply_markup=None)
        except Exception:
            pass


# ══════════════════════════════════════════════════════════════════════════════
#  AMONG US — social deduction mini-game (/amongus)
#  Impostors kill/sabotage at night, crew does tasks + votes by day.
#  Roles: Crewmate, Detective, Doctor, Engineer, Tracker, Vigilante, Mayor, Impostor.
# ══════════════════════════════════════════════════════════════════════════════
_au_games = {}   # group chat_id -> game dict

# ── PERSISTENCE ──────────────────────────────────────────────────────────────
# _au_games lives only in process memory, same as it always has, but it's now
# snapshotted to the same SQLite-backed store everything else uses. Azure's
# free F1 tier idle-sleeps and cold-restarts this process with no warning —
# every other stateful system here (pets, auto-hunt) explicitly reschedules
# itself on startup; Among Us never did, so a mid-game restart used to just
# silently erase the game with zero explanation. That's very likely the
# actual "Among Us doesn't work" bug: it looks fine, runs for a while, then
# just vanishes whenever the host process gets recycled.
def _au_serialize_game(game: dict) -> dict:
    g = dict(game)
    g["impostors"] = list(g.get("impostors", []))
    na = dict(g.get("night_actions", {}))
    if "acted" in na:
        na["acted"] = list(na["acted"])
    g["night_actions"] = na
    sab = g.get("sabotage")
    if sab:
        sab = dict(sab)
        if "fixers" in sab:
            sab["fixers"] = list(sab["fixers"])
        g["sabotage"] = sab
    if isinstance(g.get("created_at"), datetime):
        g["created_at"] = g["created_at"].isoformat()
    # players/join_order/impostors keys are ints in memory but JSON always
    # round-trips dict keys as strings — join_order/impostors are lists so
    # they're fine, only the "players" dict needs its keys stringified here
    # (and un-stringified again on restore).
    g["players"] = {str(k): v for k, v in g.get("players", {}).items()}
    return g

def _au_deserialize_game(g: dict) -> dict:
    g = dict(g)
    g["impostors"] = set(int(x) for x in g.get("impostors", []))
    g["players"] = {int(k): v for k, v in g.get("players", {}).items()}
    g["join_order"] = [int(x) for x in g.get("join_order", [])]
    na = dict(g.get("night_actions", {}))
    if "acted" in na:
        na["acted"] = set(na["acted"])
    g["night_actions"] = na
    sab = g.get("sabotage")
    if sab:
        sab = dict(sab)
        if "fixers" in sab:
            sab["fixers"] = set(sab["fixers"])
        g["sabotage"] = sab
    if isinstance(g.get("created_at"), str):
        try:
            g["created_at"] = datetime.fromisoformat(g["created_at"])
        except Exception:
            g["created_at"] = datetime.now()
    return g

def _au_persist_all():
    """Call after any state-mutating action. Cheap enough (small JSON blob,
    at most a handful of active group games at once) to just do every time
    rather than trying to debounce it."""
    try:
        db = _get_db()
        snapshot = {str(cid): _au_serialize_game(g) for cid, g in _au_games.items()}
        db["meta"].update_one({"_id": "amongus_games"}, {"$set": {"games": snapshot}}, upsert=True)
    except Exception as e:
        logger.warning(f"_au_persist_all failed: {e}")

def _au_restore_games(application):
    """Called once at startup. Reloads whatever games survived the restart
    and re-arms a fresh full-length timer for whatever phase they were in —
    exact remaining time is lost, but the game keeps going instead of
    hanging forever on a timer job that no longer exists."""
    try:
        db = _get_db()
        doc = db["meta"].find_one({"_id": "amongus_games"}) or {}
        raw = doc.get("games", {})
        restored = 0
        for cid_str, g in raw.items():
            cid = int(cid_str)
            game = _au_deserialize_game(g)
            status = game.get("status")
            if status in ("ended", None) or not game.get("players"):
                continue
            _au_games[cid] = game
            restored += 1
            jq = application.job_queue
            if status == "night":
                jq.run_once(_au_resolve_night_job, when=AU_NIGHT_SECONDS,
                             chat_id=cid, name=f"au_night_{cid}", data={"chat_id": cid})
            elif status == "day":
                jq.run_once(_au_resolve_day_job, when=AU_DAY_SECONDS,
                             chat_id=cid, name=f"au_day_{cid}", data={"chat_id": cid})
            if game.get("sabotage"):
                jq.run_once(_au_resolve_sabotage_job, when=AU_SABOTAGE_SECONDS,
                             chat_id=cid, name=f"au_sab_{cid}", data={"chat_id": cid})
            jq.run_once(_au_restore_notice_job, when=2, chat_id=cid, data={"chat_id": cid})
        if restored:
            logger.info(f"Restored {restored} Among Us game(s) from disk after startup.")
    except Exception as e:
        logger.warning(f"_au_restore_games failed: {e}")

async def _au_restore_notice_job(context: ContextTypes.DEFAULT_TYPE):
    try:
        await context.bot.send_message(
            context.job.data["chat_id"],
            "🔄 I restarted — your Among Us game picked back up right where it left off. "
            "Phase timers reset to full length, nothing else changed.",
            parse_mode="Markdown")
    except Exception:
        pass

def _au_autosave(fn):
    """Persists _au_games to disk after fn returns, no matter which internal
    branch/early-return it took. Applied to every handler/phase-transition
    function that can mutate game state, so we never have to hunt down
    every individual return statement by hand."""
    async def wrapper(*args, **kwargs):
        try:
            return await fn(*args, **kwargs)
        finally:
            _au_persist_all()
    wrapper.__name__ = fn.__name__
    return wrapper



AU_NIGHT_SECONDS   = 90
AU_DAY_SECONDS      = 180
AU_SABOTAGE_SECONDS = 60
AU_MIN_PLAYERS      = 4

AU_ROOMS = ["Electrical", "Cafeteria", "Medbay", "Storage", "Navigation",
            "Admin", "Weapons", "O2", "Shields", "Communications",
            "Engine Room", "Reactor"]

# (name, kind) — kind in {"tap","order","choice"}
AU_TASK_POOL = [
    ("🔧 Fix Wiring — Electrical", "tap"),
    ("📇 Swipe Card — Admin", "tap"),
    ("🗑️ Empty Chute — Cafeteria", "order"),
    ("🧮 Calibrate Distributor — Electrical", "choice"),
    ("🛢️ Fuel Engines — Storage", "tap"),
    ("📡 Align Engine Output — Engine Room", "order"),
    ("🌱 Water Plants — Greenhouse", "tap"),
    ("🧪 Submit Scan — Medbay", "tap"),
    ("🔋 Divert Power to Shields — Weapons", "choice"),
    ("📊 Chart Course — Navigation", "order"),
    ("🗄️ Sort Samples — Medbay", "choice"),
    ("🚪 Stabilize Steering — Navigation", "tap"),
]

AU_ROLE_EMOJI = {
    "impostor": "🔪", "crewmate": "🧑‍🚀", "detective": "🕵️", "doctor": "💉",
    "engineer": "🔧", "tracker": "📡", "vigilante": "🔫", "mayor": "🎖️",
}

AU_ROLE_BLURB = {
    "impostor":  "You're the *Impostor*. Kill crewmates at night or sabotage. Blend in during the day — don't get voted out!",
    "crewmate":  "You're a *Crewmate*. Finish your 4 tasks and vote out anyone acting sus.",
    "detective": "You're the *Detective* 🕵️. Each night: get a clue about the Impostor, OR investigate one player for a Suspicious/Innocent verdict.",
    "doctor":    "You're the *Doctor* 💉. Each night, protect one player from being killed. You can't protect the same person twice in a row.",
    "engineer":  "You're the *Engineer* 🔧. ONE-TIME power: inspect a player's wiring to see their *real* task progress (impostors' tasks are fake).",
    "tracker":   "You're the *Tracker* 📡. Each night, track a player — next morning you'll learn where they were last seen.",
    "vigilante": "You're the *Vigilante* 🔫. ONE-TIME power: shoot a player at night. If they're the Impostor, they die. If you're wrong, YOU die too.",
    "mayor":     "You're the *Mayor* 🎖️. Nobody knows it, but your vote during meetings secretly counts as TWO votes.",
}


def _au_impostor_count(n):
    if n <= 7: return 1
    if n <= 15: return 2
    return 3


def _au_pick_special_roles(n):
    """Which non-impostor special roles exist this game, based on player count."""
    roles = []
    if n >= 5: roles += ["detective", "doctor"]
    if n >= 7: roles += ["engineer"]
    if n >= 8: roles += ["tracker"]
    if n >= 10: roles += ["vigilante"]
    if n >= 12: roles += ["mayor"]
    return roles


def _au_alive(game):
    return [uid for uid, p in game["players"].items() if p["alive"]]


def _au_alive_crew(game):
    return [uid for uid in _au_alive(game) if uid not in game["impostors"]]


def _au_name(game, uid):
    return game["players"][uid]["name"]


def _au_gen_tasks():
    picks = random.sample(AU_TASK_POOL, 4)
    tasks = []
    for name, kind in picks:
        t = {"name": name, "kind": kind, "done": False}
        if kind == "order":
            seq = [1, 2, 3]
            shown = seq[:]
            random.shuffle(shown)
            t["target_seq"] = seq
            t["shown"] = shown
            t["progress"] = []
        elif kind == "choice":
            a, b = random.randint(4, 40), random.randint(4, 40)
            correct = a + b
            opts = {correct}
            while len(opts) < 4:
                opts.add(correct + random.choice([-7, -3, -2, 2, 3, 5, 8, -5]))
            opts = list(opts)
            random.shuffle(opts)
            t["question"] = f"{a} + {b} = ?"
            t["options"] = opts
            t["correct"] = correct
        tasks.append(t)
    return tasks


def _au_lobby_kb(chat_id, bot_username=None):
    rows = [[InlineKeyboardButton("🚀 Join Game", callback_data=f"aujoin_{chat_id}")]]
    if bot_username:
        rows.append([InlineKeyboardButton("💬 DM Me First (required!)", url=f"https://t.me/{bot_username}?start=au")])
    return InlineKeyboardMarkup(rows)


@_au_autosave
async def cmd_amongus(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    user = update.message.from_user
    if update.message.chat.type == "private":
        await update.message.reply_text("👾 `/amongus` only works in group chats — add me to a group first!", parse_mode="Markdown")
        return
    sub = context.args[0].lower() if context.args else ""

    if sub in ("", "info"):
        game = _au_games.get(chat_id)
        if not game:
            await update.message.reply_text(
                "👾 ✦ *AMONG US* ✦\n┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄\n"
                "No game running. `/amongus create` to start a lobby!\n"
                "`/amongus howto` for the full rulebook.",
                parse_mode="Markdown")
        else:
            await cmd_amongus_status(update, context)
        return

    if sub == "howto":
        await update.message.reply_text(_au_howto_text(), parse_mode="Markdown")
        return

    if sub == "create":
        if chat_id in _au_games and _au_games[chat_id]["status"] != "ended":
            await update.message.reply_text("⚠️ A game is already active here! `/amongus end` to stop it (host/admin only)."); return
        _au_games[chat_id] = {
            "status": "lobby", "host": user.id, "chat_id": chat_id,
            "players": {user.id: {"name": user.full_name, "username": user.username,
                                   "role": None, "alive": True, "tasks": [], "unlocked": 0,
                                   "reachable": True}},
            "join_order": [user.id],
            "impostors": set(), "day_num": 0, "phase_num": 0,
            "votes": {}, "night_actions": {}, "doctor_last": None,
            "vigilante_used": False, "engineer_used": False,
            "sabotage": None, "created_at": datetime.now(),
        }
        try:
            bot_username = (await context.bot.get_me()).username
        except Exception:
            bot_username = None
        await update.message.reply_text(
            f"👾 *AMONG US* lobby created by {_safe_md(user.full_name)}!\n"
            f"Need at least *{AU_MIN_PLAYERS}* players. Tap below or `/amongus join`.\n"
            f"⚠️ _Roles and tasks are sent by DM — everyone (including you) needs to have "
            f"messaged me privately at least once, or you'll miss your role!_\n"
            f"Host starts with `/amongus start`.",
            parse_mode="Markdown", reply_markup=_au_lobby_kb(chat_id, bot_username))
        return

    game = _au_games.get(chat_id)
    if not game and sub in ("join", "leave", "start"):
        await update.message.reply_text("No lobby open. `/amongus create` first."); return

    if sub == "join":
        ok, msg = await _au_join(context, chat_id, user)
        await update.message.reply_text(msg, parse_mode="Markdown")
        return

    if sub == "leave":
        if game["status"] != "lobby":
            await update.message.reply_text("Game already started — can't leave now."); return
        if user.id in game["players"]:
            del game["players"][user.id]
            game["join_order"].remove(user.id)
            await update.message.reply_text(f"👋 {_safe_md(user.full_name)} left the lobby.", parse_mode="Markdown")
        return

    if sub == "start":
        if game["status"] != "lobby":
            await update.message.reply_text("Game already started."); return
        if user.id != game["host"] and not await is_admin(context.bot, chat_id, user.id):
            await update.message.reply_text("🚫 Only the host or a group admin can start."); return
        n = len(game["players"])
        if n < AU_MIN_PLAYERS:
            await update.message.reply_text(f"Need at least *{AU_MIN_PLAYERS}* players (have {n})."); return

        # ── Preflight DM check ────────────────────────────────────────────
        # Roles/tasks are only ever sent by DM. If someone hasn't messaged
        # the bot privately first, Telegram blocks the bot from DMing them
        # — they'd join, "play", and never get a role or a single task,
        # which is the #1 reason this game looks "broken". Catch it here,
        # before the game actually starts, instead of after.
        checking = await update.message.reply_text("🔍 Checking everyone can be reached by DM...")
        unreachable = []
        for uid in game["join_order"]:
            p = game["players"][uid]
            try:
                await context.bot.send_message(
                    uid, "👾 Among Us is starting — get ready! Your role is coming up shortly.",
                    parse_mode="Markdown")
                p["reachable"] = True
            except Exception:
                p["reachable"] = False
                unreachable.append(p["name"])
        try:
            await checking.delete()
        except Exception:
            pass
        if unreachable:
            try:
                bot_username = (await context.bot.get_me()).username
            except Exception:
                bot_username = None
            kb = None
            if bot_username:
                kb = InlineKeyboardMarkup([[InlineKeyboardButton(
                    "💬 DM Me First", url=f"https://t.me/{bot_username}?start=au")]])
            await update.message.reply_text(
                "🚫 *Can't start yet* — I can't DM these players:\n"
                + "\n".join(f"• {_safe_md(n)}" for n in unreachable)
                + "\n\nThey need to open a private chat with me and send anything "
                  "(even just `/start`), then `/amongus start` again.",
                parse_mode="Markdown", reply_markup=kb)
            return

        await _au_start_game(context, chat_id)
        return

    if sub == "end":
        if not game:
            await update.message.reply_text("No game running."); return
        if user.id != game["host"] and not await is_admin(context.bot, chat_id, user.id) and user.id not in OWNER_IDS:
            await update.message.reply_text("🚫 Only the host, an admin, or the bot owner can end the game."); return
        await _au_end_game(context, chat_id, winner=None, reason="🛑 Game force-ended.")
        return

    if sub == "status":
        await cmd_amongus_status(update, context)
        return

    await update.message.reply_text("Usage: `/amongus create|join|leave|start|end|status|howto`", parse_mode="Markdown")


async def cmd_amongus_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    game = _au_games.get(chat_id)
    if not game:
        await update.message.reply_text("No game running."); return
    if game["status"] == "lobby":
        names = ", ".join(_safe_md(game["players"][u]["name"]) for u in game["join_order"])
        await update.message.reply_text(
            f"👾 *Lobby* ({len(game['players'])} joined)\n{names}\n\n`/amongus start` when ready (min {AU_MIN_PLAYERS}).",
            parse_mode="Markdown")
        return
    alive = _au_alive(game)
    dead = [u for u in game["players"] if not game["players"][u]["alive"]]
    lines = [f"👾 *AMONG US* — {'☀️ Day' if game['status']=='day' else '🌙 Night'} {game['day_num']}",
             f"🧑‍🚀 Alive: {len(alive)}   💀 Dead: {len(dead)}"]
    if game.get("sabotage"):
        lines.append(f"🚨 Active sabotage: *{game['sabotage']['type']}*!")
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


def _au_howto_text():
    return (
        "👾 ✦ *AMONG US — RULEBOOK* ✦\n┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄\n"
        "`/amongus create` → lobby opens, others `/amongus join`.\n"
        "`/amongus start` (host/admin) once you have 4+ players.\n\n"
        "*Everyone gets a secret role via DM* — check your DMs!\n"
        f"🔪 *Impostor(s)*: ≤7 players → 1, 8-15 → 2, 16+ → 3.\n"
        "🧑‍🚀 *Crewmate*: do tasks, vote wisely.\n"
        "🕵️ *Detective*: nightly clue or investigate someone.\n"
        "💉 *Doctor*: protect one player a night (no repeats).\n"
        "🔧 *Engineer*: one-time real task-progress check.\n"
        "📡 *Tracker*: track a player, get a location hint next day.\n"
        "🔫 *Vigilante*: one-time night shot — risky if you're wrong.\n"
        "🎖️ *Mayor*: secret double vote.\n\n"
        "🌙 *Night*: Impostor(s) kill or sabotage, special roles act via DM buttons.\n"
        "☀️ *Day*: recap posted, discuss, then vote to eject someone (or skip).\n"
        "🛠️ Everyone has 4 tasks (DM'd gradually, 1 more unlocks each phase) — "
        "finish them all as a crew before the impostors strike to win by tasks!\n\n"
        "🏆 Crew wins: all impostors ejected/killed, or all tasks finished.\n"
        "🏆 Impostors win: impostors ≥ remaining crew."
    )


async def _au_join(context, chat_id, user):
    game = _au_games.get(chat_id)
    if not game or game["status"] != "lobby":
        return False, "No open lobby."
    if user.id in game["players"]:
        return False, "You're already in!"
    game["players"][user.id] = {"name": user.full_name, "username": user.username,
                                 "role": None, "alive": True, "tasks": [], "unlocked": 0,
                                 "reachable": True}
    game["join_order"].append(user.id)
    return True, f"✅ {_safe_md(user.full_name)} joined! ({len(game['players'])} players)"


@_au_autosave
async def handle_au_join(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    chat_id = int(query.data.split("_", 1)[1])
    ok, msg = await _au_join(context, chat_id, query.from_user)
    await query.answer(msg.replace("*", ""), show_alert=not ok)
    if ok:
        game = _au_games.get(chat_id)
        if game:
            try:
                await context.bot.send_message(chat_id, msg, parse_mode="Markdown")
            except Exception:
                pass


# ── GAME START / ROLE ASSIGNMENT ────────────────────────────────────────────
async def _au_start_game(context, chat_id):
    game = _au_games[chat_id]
    uids = game["join_order"][:]
    random.shuffle(uids)
    n = len(uids)

    impostor_n = _au_impostor_count(n)
    impostors = set(uids[:impostor_n])
    rest = uids[impostor_n:]

    special = _au_pick_special_roles(len(rest))
    random.shuffle(special)
    role_map = {}
    for uid in impostors:
        role_map[uid] = "impostor"
    for uid in rest:
        if special:
            role_map[uid] = special.pop(0)
        else:
            role_map[uid] = "crewmate"

    game["status"] = "starting"
    game["impostors"] = impostors
    game["day_num"] = 0
    game["phase_num"] = 0

    impostor_names = ", ".join(_safe_md(game["players"][u]["name"]) for u in impostors)

    for uid in uids:
        p = game["players"][uid]
        p["role"] = role_map[uid]
        p["alive"] = True
        p["tasks"] = _au_gen_tasks()  # impostors get cosmetic fake tasks too
        p["unlocked"] = 0
        role = role_map[uid]
        text = f"👾 *Your role: {AU_ROLE_EMOJI.get(role,'')} {role.upper()}*\n\n{AU_ROLE_BLURB[role]}"
        if role == "impostor":
            text += f"\n\n🤝 Your fellow impostor(s): {impostor_names}"
        try:
            await context.bot.send_message(uid, text, parse_mode="Markdown")
            p["reachable"] = True
        except Exception:
            p["reachable"] = False

    unreachable = [game["players"][u]["name"] for u in uids if not game["players"][u]["reachable"]]
    warn = ""
    if unreachable:
        bot_username = _safe_md((await context.bot.get_me()).username)
        warn = ("\n\n⚠️ Couldn't DM: " + ", ".join(_safe_md(n) for n in unreachable) +
                " — they must start a DM with me (@" + bot_username + ") or they'll miss role actions/tasks!")

    await context.bot.send_message(
        chat_id,
        f"👾 *{n} players. {impostor_n} Impostor(s) are among us...* 🔪{warn}\n\n"
        f"Roles sent via DM. Night falls first...",
        parse_mode="Markdown")

    await asyncio.sleep(2)
    await _au_begin_night(context, chat_id)


# ── TASKS ────────────────────────────────────────────────────────────────────
async def _au_advance_tasks(context, chat_id):
    game = _au_games.get(chat_id)
    if not game: return
    game["phase_num"] += 1
    target_unlocked = min(4, game["phase_num"])
    for uid in _au_alive(game):
        p = game["players"][uid]
        while p["unlocked"] < target_unlocked:
            idx = p["unlocked"]
            p["unlocked"] += 1
            await _au_send_task_dm(context, chat_id, uid, idx)


def _au_task_kb(chat_id, idx, task):
    if task["kind"] == "tap":
        return InlineKeyboardMarkup([[InlineKeyboardButton("✅ Mark Done", callback_data=f"autask_{chat_id}_{idx}_tap")]])
    if task["kind"] == "order":
        row = [InlineKeyboardButton(str(n), callback_data=f"autask_{chat_id}_{idx}_ord{n}") for n in task["shown"]]
        return InlineKeyboardMarkup([row])
    if task["kind"] == "choice":
        row = [InlineKeyboardButton(str(o), callback_data=f"autask_{chat_id}_{idx}_ch{o}") for o in task["options"]]
        return InlineKeyboardMarkup([row[:2], row[2:]])


async def _au_send_task_dm(context, chat_id, uid, idx):
    game = _au_games.get(chat_id)
    if not game: return
    p = game["players"][uid]
    task = p["tasks"][idx]
    if task["done"]: return
    body = f"🛠️ *New Task Unlocked!*\n\n*{task['name']}*\n"
    if task["kind"] == "order":
        body += "Tap the panels *in numeric order (1 → 2 → 3)*:"
    elif task["kind"] == "choice":
        body += f"Solve it: *{task['question']}*"
    else:
        body += "Tap the button once you're 'done' fixing it."
    try:
        await context.bot.send_message(uid, body, parse_mode="Markdown", reply_markup=_au_task_kb(chat_id, idx, task))
    except Exception:
        pass


@_au_autosave
async def handle_au_task(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    parts = query.data.split("_", 3)
    chat_id, idx, action = int(parts[1]), int(parts[2]), parts[3]
    game = _au_games.get(chat_id)
    if not game or game["status"] in ("ended", "lobby"):
        await query.answer("Game's over."); return
    uid = query.from_user.id
    p = game["players"].get(uid)
    if not p or not p["alive"]:
        await query.answer("You're not in this game (or you're dead 💀)."); return
    task = p["tasks"][idx]
    if task["done"]:
        await query.answer("Already done!"); return

    if task["kind"] == "tap":
        task["done"] = True
        await query.answer("✅ Task complete!")
        await _safe_edit_message_text(query, f"✅ *{task['name']}* — DONE!", parse_mode="Markdown")
    elif action.startswith("ord"):
        n = int(action[3:])
        task["progress"].append(n)
        if task["progress"] != task["target_seq"][:len(task["progress"])]:
            task["progress"] = []
            await query.answer("❌ Wrong order, try again!")
        elif len(task["progress"]) == len(task["target_seq"]):
            task["done"] = True
            await query.answer("✅ Task complete!")
            await _safe_edit_message_text(query, f"✅ *{task['name']}* — DONE!", parse_mode="Markdown")
        else:
            await query.answer(f"✔️ {len(task['progress'])}/{len(task['target_seq'])}")
    elif action.startswith("ch"):
        val = int(action[2:])
        if val == task["correct"]:
            task["done"] = True
            await query.answer("✅ Correct!")
            await _safe_edit_message_text(query, f"✅ *{task['name']}* — DONE!", parse_mode="Markdown")
        else:
            await query.answer("❌ Wrong, try again!")

    if not (uid in game["impostors"]) and all(t["done"] for t in p["tasks"]) and p["unlocked"] == 4:
        winner = await _au_check_win(context, chat_id)
        if winner:
            await _au_finish_win(context, chat_id, winner)


def _au_real_tasks_done(game, uid):
    """Impostor 'tasks' are cosmetic — real progress only counts for crew."""
    if uid in game["impostors"]:
        return 0
    return sum(1 for t in game["players"][uid]["tasks"] if t["done"])


# ── NIGHT PHASE ──────────────────────────────────────────────────────────────
@_au_autosave
async def _au_begin_night(context, chat_id):
    game = _au_games.get(chat_id)
    if not game: return
    game["status"] = "night"
    game["day_num"] += 1
    game["votes"] = {}
    game["night_actions"] = {"kill": None, "protect": None, "sabotage": None,
                              "track_target": None, "investigate": None,
                              "vigilante_target": None, "engineer_target": None,
                              "acted": set()}
    await _au_advance_tasks(context, chat_id)

    try:
        await context.bot.send_message(chat_id, f"🌙 *NIGHT {game['day_num']} FALLS...*\nEveryone's asleep. Check your DMs if you have a role action. 🤫", parse_mode="Markdown")
    except Exception:
        pass

    for uid in _au_alive(game):
        role = game["players"][uid]["role"]
        try:
            if role == "impostor":
                await _au_prompt_impostor(context, chat_id, uid)
            elif role == "doctor":
                await _au_prompt_doctor(context, chat_id, uid)
            elif role == "detective":
                await _au_prompt_detective(context, chat_id, uid)
            elif role == "tracker":
                await _au_prompt_tracker(context, chat_id, uid)
            elif role == "engineer" and not game["engineer_used"]:
                await _au_prompt_engineer(context, chat_id, uid)
            elif role == "vigilante" and not game["vigilante_used"]:
                await _au_prompt_vigilante(context, chat_id, uid)
        except Exception:
            pass

    context.job_queue.run_once(_au_resolve_night_job, when=AU_NIGHT_SECONDS,
                                chat_id=chat_id, name=f"au_night_{chat_id}",
                                data={"chat_id": chat_id})


def _au_target_kb(chat_id, prefix, targets, game, extra_buttons=None):
    rows = []
    row = []
    for uid in targets:
        row.append(InlineKeyboardButton(game["players"][uid]["name"][:16], callback_data=f"{prefix}_{chat_id}_{uid}"))
        if len(row) == 2:
            rows.append(row); row = []
    if row: rows.append(row)
    if extra_buttons:
        rows.append(extra_buttons)
    return InlineKeyboardMarkup(rows)


async def _au_prompt_impostor(context, chat_id, uid):
    game = _au_games[chat_id]
    targets = [t for t in _au_alive_crew(game)]
    kb = _au_target_kb(chat_id, "aunightkill", targets, game,
                        extra_buttons=[InlineKeyboardButton("🎭 Sabotage instead", callback_data=f"aunightsab_{chat_id}")])
    await context.bot.send_message(uid, "🔪 *Choose your move tonight:*\nPick a crewmate to kill, or sabotage.", parse_mode="Markdown", reply_markup=kb)


async def _au_prompt_doctor(context, chat_id, uid):
    game = _au_games[chat_id]
    targets = [t for t in _au_alive(game) if t != game["doctor_last"]]
    kb = _au_target_kb(chat_id, "aunightprotect", targets, game)
    note = "\n_(Can't repeat last night's pick.)_" if game["doctor_last"] else ""
    await context.bot.send_message(uid, f"💉 *Who do you protect tonight?*{note}", parse_mode="Markdown", reply_markup=kb)


async def _au_prompt_detective(context, chat_id, uid):
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("🔎 General Clue", callback_data=f"aunightclue_{chat_id}"),
        InlineKeyboardButton("🕵️ Investigate Someone", callback_data=f"aunightinv_{chat_id}"),
    ]])
    await context.bot.send_message(uid, "🕵️ *Detective work tonight — pick one:*", parse_mode="Markdown", reply_markup=kb)


async def _au_prompt_tracker(context, chat_id, uid):
    game = _au_games[chat_id]
    targets = [t for t in _au_alive(game) if t != uid]
    kb = _au_target_kb(chat_id, "aunighttrack", targets, game)
    await context.bot.send_message(uid, "📡 *Who do you track tonight?*", parse_mode="Markdown", reply_markup=kb)


async def _au_prompt_engineer(context, chat_id, uid):
    game = _au_games[chat_id]
    targets = [t for t in _au_alive(game) if t != uid]
    kb = _au_target_kb(chat_id, "aunighteng", targets, game)
    await context.bot.send_message(uid, "🔧 *One-time power!* Inspect a player's REAL task progress:", parse_mode="Markdown", reply_markup=kb)


async def _au_prompt_vigilante(context, chat_id, uid):
    game = _au_games[chat_id]
    targets = [t for t in _au_alive(game) if t != uid]
    kb = _au_target_kb(chat_id, "aunightvig", targets, game,
                        extra_buttons=[InlineKeyboardButton("🚫 Don't shoot tonight", callback_data=f"aunightvigskip_{chat_id}")])
    await context.bot.send_message(uid, "🔫 *One-time power!* Shoot someone — right and they die, WRONG and you die too. Choose wisely:", parse_mode="Markdown", reply_markup=kb)


async def _au_maybe_early_resolve(context, chat_id):
    """If every role that can act this night has acted, resolve immediately."""
    game = _au_games.get(chat_id)
    if not game or game["status"] != "night": return
    needed = set()
    for uid in _au_alive(game):
        role = game["players"][uid]["role"]
        if role == "impostor": needed.add(uid)
        elif role == "doctor": needed.add(uid)
        elif role == "detective": needed.add(uid)
        elif role == "tracker": needed.add(uid)
        elif role == "engineer" and not game["engineer_used"]: needed.add(uid)
        elif role == "vigilante" and not game["vigilante_used"]: needed.add(uid)
    if needed and needed.issubset(game["night_actions"]["acted"]):
        for job in context.job_queue.get_jobs_by_name(f"au_night_{chat_id}"):
            job.schedule_removal()
        await _au_resolve_night(context, chat_id)


@_au_autosave
async def handle_au_night_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    kind, rest = data.split("_", 1)
    parts = rest.split("_")
    chat_id = int(parts[0])
    game = _au_games.get(chat_id)
    if not game or game["status"] != "night":
        await query.answer("Not night phase anymore."); return
    uid = query.from_user.id
    p = game["players"].get(uid)
    if not p or not p["alive"]:
        await query.answer("You can't act."); return
    na = game["night_actions"]

    if kind == "aunightkill":
        target = int(parts[1])
        if na["kill"] is None and na["sabotage"] is None:
            na["kill"] = target
        na["acted"].add(uid)
        await query.answer("🔪 Locked in.")
        await _safe_edit_message_text(query, f"🔪 Target chosen: *{_au_name(game, target)}*", parse_mode="Markdown")

    elif kind == "aunightsab":
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("💡 Lights Out", callback_data=f"aunightsabtype_{chat_id}_lights")],
            [InlineKeyboardButton("📡 Comms Sabotage", callback_data=f"aunightsabtype_{chat_id}_comms")],
            [InlineKeyboardButton("☢️ Reactor Meltdown", callback_data=f"aunightsabtype_{chat_id}_reactor")],
        ])
        try:
            await query.answer()
        except (BadRequest, TelegramError):
            pass  # stale/expired callback query — safe to ignore, continue handling
        await _safe_edit_message_text(query, "🎭 *Pick a sabotage:*", parse_mode="Markdown", reply_markup=kb)

    elif kind == "aunightsabtype":
        sab_type = parts[1]
        if na["kill"] is None and na["sabotage"] is None:
            na["sabotage"] = sab_type
        na["acted"].add(uid)
        await query.answer("🎭 Sabotage queued.")
        await _safe_edit_message_text(query, f"🎭 Sabotage queued: *{sab_type}*", parse_mode="Markdown")

    elif kind == "aunightprotect":
        target = int(parts[1])
        na["protect"] = target
        game["doctor_last"] = target
        na["acted"].add(uid)
        await query.answer("💉 Locked in.")
        await _safe_edit_message_text(query, f"💉 Protecting: *{_au_name(game, target)}*", parse_mode="Markdown")

    elif kind == "aunightclue":
        clue = _au_generate_clue(game)
        na["acted"].add(uid)
        try:
            await query.answer()
        except (BadRequest, TelegramError):
            pass  # stale/expired callback query — safe to ignore, continue handling
        await _safe_edit_message_text(query, f"🔎 *Tonight's clue:*\n_{clue}_", parse_mode="Markdown")

    elif kind == "aunightinv":
        targets = [t for t in _au_alive(game) if t != uid]
        kb = _au_target_kb(chat_id, "aunightinvpick", targets, game)
        try:
            await query.answer()
        except (BadRequest, TelegramError):
            pass  # stale/expired callback query — safe to ignore, continue handling
        await _safe_edit_message_text(query, "🕵️ Pick someone to investigate:", reply_markup=kb)

    elif kind == "aunightinvpick":
        target = int(parts[1])
        verdict = "🟥 SUSPICIOUS" if target in game["impostors"] else "🟩 Innocent"
        na["acted"].add(uid)
        try:
            await query.answer()
        except (BadRequest, TelegramError):
            pass  # stale/expired callback query — safe to ignore, continue handling
        await _safe_edit_message_text(query, f"🕵️ *{_au_name(game, target)}* feels: {verdict}", parse_mode="Markdown")

    elif kind == "aunighttrack":
        target = int(parts[1])
        na["track_target"] = (uid, target)
        na["acted"].add(uid)
        await query.answer("📡 Tracking locked in.")
        await _safe_edit_message_text(query, f"📡 Tracking: *{_au_name(game, target)}* tonight...", parse_mode="Markdown")

    elif kind == "aunighteng":
        target = int(parts[1])
        game["engineer_used"] = True
        real = _au_real_tasks_done(game, target)
        na["acted"].add(uid)
        try:
            await query.answer()
        except (BadRequest, TelegramError):
            pass  # stale/expired callback query — safe to ignore, continue handling
        await _safe_edit_message_text(query, f"🔧 *{_au_name(game, target)}*'s real task progress: *{real}/4*\n(Impostors always show 0 real progress.)", parse_mode="Markdown")

    elif kind == "aunightvig":
        target = int(parts[1])
        game["vigilante_used"] = True
        na["vigilante_target"] = (uid, target)
        na["acted"].add(uid)
        await query.answer("🔫 Shot fired... results at dawn.")
        await _safe_edit_message_text(query, f"🔫 You shot at *{_au_name(game, target)}*. Results at dawn.", parse_mode="Markdown")

    elif kind == "aunightvigskip":
        game["vigilante_used"] = True
        na["acted"].add(uid)
        await query.answer("Holstered.")
        await _safe_edit_message_text(query, "🔫 You chose not to shoot tonight.", parse_mode="Markdown")

    await _au_maybe_early_resolve(context, chat_id)


AU_CLUE_TEMPLATES = None
def _au_generate_clue(game):
    impostor = random.choice(list(game["impostors"]))
    name = game["players"][impostor]["name"]
    username = game["players"][impostor].get("username") or ""
    clues = [
        f"The Impostor's name has an {'odd' if len(name.replace(' ','')) % 2 else 'even'} number of letters.",
        f"The Impostor's name {'does' if random.choice('AEIOU').lower() in name.lower() else 'does not'} contain the letter '{random.choice('AEIOU')}'.",
        f"The Impostor's name starts {'before' if name[:1].upper() < 'M' else 'after (or at)'} 'M' alphabetically.",
        f"The Impostor joined the lobby {'in the first half' if game['join_order'].index(impostor) < len(game['join_order'])//2 else 'in the second half'}.",
        f"The Impostor has completed *{_au_real_tasks_done(game, impostor)}* real tasks so far (impostors fake it, so this might mislead you 👀).",
    ]
    return random.choice(clues)


# ── NIGHT RESOLUTION ─────────────────────────────────────────────────────────
async def _au_resolve_night_job(context: ContextTypes.DEFAULT_TYPE):
    await _au_resolve_night(context, context.job.data["chat_id"])


@_au_autosave
async def _au_resolve_night(context, chat_id):
    game = _au_games.get(chat_id)
    if not game or game["status"] != "night": return
    na = game["night_actions"]
    recap = []

    # Vigilante resolves first (independent of impostor action)
    if na.get("vigilante_target"):
        vig_uid, target = na["vigilante_target"]
        if target in game["impostors"]:
            game["players"][target]["alive"] = False
            recap.append(f"🔫 The Vigilante struck true — *{_au_name(game, target)}* (Impostor) is dead!")
        else:
            game["players"][target]["alive"] = False
            game["players"][vig_uid]["alive"] = False
            recap.append(f"🔫 The Vigilante shot *{_au_name(game, target)}* — WRONG target! Both *{_au_name(game, target)}* and the Vigilante are dead.")

    if na.get("sabotage"):
        sab = na["sabotage"]
        fixers_needed = {"lights": 2, "comms": 1, "reactor": 2}[sab]
        game["sabotage"] = {"type": sab, "fixers": set(), "needed": fixers_needed}
        labels = {"lights": "💡 LIGHTS OUT", "comms": "📡 COMMS SABOTAGED", "reactor": "☢️ REACTOR MELTDOWN"}
        recap.append(f"🚨 *{labels[sab]}!* Crew must fix it — `/amongus` group chat, tap Fix below!")
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("🛠️ Fix it!", callback_data=f"aufix_{chat_id}")]])
        try:
            msg = await context.bot.send_message(chat_id, f"🚨 *{labels[sab]}!* Need *{fixers_needed}* different crew to tap Fix within {AU_SABOTAGE_SECONDS}s!",
                                                   parse_mode="Markdown", reply_markup=kb)
            game["sabotage"]["msg_id"] = msg.message_id
        except Exception:
            pass
        context.job_queue.run_once(_au_resolve_sabotage_job, when=AU_SABOTAGE_SECONDS,
                                    chat_id=chat_id, name=f"au_sab_{chat_id}", data={"chat_id": chat_id})
    elif na.get("kill") is not None:
        target = na["kill"]
        if target == na.get("protect"):
            recap.append(f"💉 *{_au_name(game, target)}* was attacked but the Doctor saved them!")
        else:
            game["players"][target]["alive"] = False
            recap.append(f"💀 *{_au_name(game, target)}* was found dead this morning.")
    else:
        recap.append("😴 A quiet night. Nobody was attacked.")

    # Tracker result
    if na.get("track_target"):
        tracker_uid, target = na["track_target"]
        was_killer = (na.get("kill") == target)
        room = random.choice(AU_ROOMS)
        hint = f"📡 *Tracker update:* {_au_name(game, target)} was last seen near *{room}*" + (
            " — and there was suspicious movement there... 👀" if was_killer else ".")
        try:
            await context.bot.send_message(tracker_uid, hint, parse_mode="Markdown")
        except Exception:
            pass

    game["night_actions"] = {}
    await context.bot.send_message(chat_id, "☀️ *Morning report:*\n" + "\n".join(recap), parse_mode="Markdown")

    winner = await _au_check_win(context, chat_id)
    if winner:
        await _au_finish_win(context, chat_id, winner)
        return

    if not game.get("sabotage"):
        await _au_begin_day(context, chat_id)
    # if sabotage active, day begins after sabotage resolves


@_au_autosave
async def handle_au_fix(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    chat_id = int(query.data.split("_", 1)[1])
    game = _au_games.get(chat_id)
    if not game or not game.get("sabotage"):
        await query.answer("Nothing to fix."); return
    sab = game["sabotage"]
    uid = query.from_user.id
    if uid not in game["players"] or not game["players"][uid]["alive"]:
        await query.answer("You're not able to help with this."); return
    sab["fixers"].add(uid)
    await query.answer(f"🛠️ Fix registered! ({len(sab['fixers'])}/{sab['needed']})")
    if len(sab["fixers"]) >= sab["needed"]:
        for job in context.job_queue.get_jobs_by_name(f"au_sab_{chat_id}"):
            job.schedule_removal()
        await _au_resolve_sabotage(context, chat_id, fixed=True)


async def _au_resolve_sabotage_job(context: ContextTypes.DEFAULT_TYPE):
    await _au_resolve_sabotage(context, context.job.data["chat_id"], fixed=False)


@_au_autosave
async def _au_resolve_sabotage(context, chat_id, fixed):
    game = _au_games.get(chat_id)
    if not game or not game.get("sabotage"): return
    sab = game["sabotage"]
    if fixed:
        await context.bot.send_message(chat_id, f"✅ *{sab['type'].title()} sabotage fixed!* Crisis averted.", parse_mode="Markdown")
    else:
        if sab["type"] == "reactor":
            crew = _au_alive_crew(game)
            if crew:
                victim = random.choice(crew)
                game["players"][victim]["alive"] = False
                await context.bot.send_message(chat_id, f"☢️ *Reactor meltdown!* Nobody fixed it in time — *{_au_name(game, victim)}* didn't make it. 💀", parse_mode="Markdown")
        else:
            await context.bot.send_message(chat_id, f"⌛ *{sab['type'].title()} sabotage* wasn't fixed in time — no one died, but tonight's info/tasks were disrupted.", parse_mode="Markdown")
    game["sabotage"] = None

    winner = await _au_check_win(context, chat_id)
    if winner:
        await _au_finish_win(context, chat_id, winner)
        return
    await _au_begin_day(context, chat_id)


# ── DAY PHASE ────────────────────────────────────────────────────────────────
@_au_autosave
async def _au_begin_day(context, chat_id):
    game = _au_games.get(chat_id)
    if not game: return
    game["status"] = "day"
    game["votes"] = {}
    await _au_advance_tasks(context, chat_id)

    alive = _au_alive(game)
    kb_rows = []
    row = []
    for uid in alive:
        row.append(InlineKeyboardButton(f"🗳️ {game['players'][uid]['name'][:14]}", callback_data=f"auvote_{chat_id}_{uid}"))
        if len(row) == 2:
            kb_rows.append(row); row = []
    if row: kb_rows.append(row)
    kb_rows.append([InlineKeyboardButton("⏭️ Skip Vote", callback_data=f"auvote_{chat_id}_skip")])

    msg = await context.bot.send_message(
        chat_id,
        f"☀️ *DAY {game['day_num']} — DISCUSSION*\n"
        f"🧑‍🚀 {len(alive)} players remain. Discuss, then vote below!\n"
        f"⏱️ {AU_DAY_SECONDS}s to vote — 0 votes so far.",
        parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb_rows))
    game["meeting_msg_id"] = msg.message_id

    context.job_queue.run_once(_au_resolve_day_job, when=AU_DAY_SECONDS,
                                chat_id=chat_id, name=f"au_day_{chat_id}", data={"chat_id": chat_id})


@_au_autosave
async def handle_au_vote(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    parts = query.data.split("_")
    chat_id = int(parts[1])
    choice = parts[2]
    game = _au_games.get(chat_id)
    if not game or game["status"] != "day":
        await query.answer("Voting's closed."); return
    uid = query.from_user.id
    p = game["players"].get(uid)
    if not p or not p["alive"]:
        await query.answer("Only the living get a say 👻"); return
    game["votes"][uid] = choice if choice == "skip" else int(choice)
    await query.answer("🗳️ Vote locked in.")

    alive = _au_alive(game)
    try:
        await query.edit_message_reply_markup(reply_markup=query.message.reply_markup)
    except Exception:
        pass
    try:
        await context.bot.edit_message_text(
            chat_id=chat_id, message_id=game["meeting_msg_id"],
            text=f"☀️ *DAY {game['day_num']} — DISCUSSION*\n"
                 f"🧑‍🚀 {len(alive)} players remain. Discuss, then vote below!\n"
                 f"🗳️ {len(game['votes'])}/{len(alive)} voted.",
            parse_mode="Markdown", reply_markup=query.message.reply_markup)
    except Exception:
        pass

    if len(game["votes"]) >= len(alive):
        for job in context.job_queue.get_jobs_by_name(f"au_day_{chat_id}"):
            job.schedule_removal()
        await _au_resolve_day(context, chat_id)


async def _au_resolve_day_job(context: ContextTypes.DEFAULT_TYPE):
    await _au_resolve_day(context, context.job.data["chat_id"])


@_au_autosave
async def _au_resolve_day(context, chat_id):
    game = _au_games.get(chat_id)
    if not game or game["status"] != "day": return
    tally = {}
    for voter, choice in game["votes"].items():
        weight = 2 if game["players"][voter]["role"] == "mayor" else 1
        tally[choice] = tally.get(choice, 0) + weight

    if not tally:
        await context.bot.send_message(chat_id, "🤷 No one voted. No one is ejected.")
    else:
        top_choice = max(tally, key=tally.get)
        winners = [c for c, v in tally.items() if v == tally[top_choice]]
        if top_choice == "skip" or len(winners) > 1:
            await context.bot.send_message(chat_id, "⏭️ *Vote skipped / tied* — no one is ejected today.", parse_mode="Markdown")
        else:
            ejected = top_choice
            game["players"][ejected]["alive"] = False
            was_impostor = ejected in game["impostors"]
            await context.bot.send_message(
                chat_id,
                f"🚪 *{_au_name(game, ejected)}* was voted out...\n"
                f"They were {'🔪 an *IMPOSTOR*!' if was_impostor else 'not an Impostor. 😬'}",
                parse_mode="Markdown")

    winner = await _au_check_win(context, chat_id)
    if winner:
        await _au_finish_win(context, chat_id, winner)
        return
    await _au_begin_night(context, chat_id)


# ── WIN CONDITIONS ────────────────────────────────────────────────────────────
async def _au_check_win(context, chat_id):
    game = _au_games.get(chat_id)
    if not game: return None
    alive_impostors = [u for u in game["impostors"] if game["players"][u]["alive"]]
    alive_crew = _au_alive_crew(game)

    if not alive_impostors:
        return "crew"
    if len(alive_impostors) >= len(alive_crew):
        return "impostor"
    if alive_crew and all(_au_real_tasks_done(game, u) >= 4 for u in alive_crew):
        return "crew_tasks"
    return None


@_au_autosave
async def _au_finish_win(context, chat_id, winner):
    game = _au_games.get(chat_id)
    if not game: return
    if winner == "crew_tasks":
        text = "🏆 *CREW WINS!* All tasks completed before the Impostor(s) could finish them off! 🧑‍🚀🎉"
    elif winner == "crew":
        text = "🏆 *CREW WINS!* Every Impostor has been eliminated! 🧑‍🚀🎉"
    else:
        text = "🏆 *IMPOSTORS WIN!* They've outnumbered the crew. 🔪😈"

    reveal = ["\n*Final roles:*"]
    for uid in game["join_order"]:
        p = game["players"][uid]
        reveal.append(f"{AU_ROLE_EMOJI.get(p['role'],'')} {_safe_md(p['name'])} — {p['role'].title()}" + ("" if p["alive"] else " 💀"))
    await _au_end_game(context, chat_id, winner, text + "\n" + "\n".join(reveal))


@_au_autosave
async def _au_end_game(context, chat_id, winner, reason):
    game = _au_games.get(chat_id)
    for name in (f"au_night_{chat_id}", f"au_day_{chat_id}", f"au_sab_{chat_id}"):
        for job in context.job_queue.get_jobs_by_name(name):
            job.schedule_removal()
    try:
        await context.bot.send_message(chat_id, reason, parse_mode="Markdown")
    except Exception:
        pass
    _au_games.pop(chat_id, None)



# ══════════════════════════════════════════════════════════════════════════════
#  /viral — Referral Hall of Fame + personal progress + one-tap share
#  Growth lever: competitive social proof makes lurkers want to participate.
# ══════════════════════════════════════════════════════════════════════════════
async def cmd_viral(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Shows the top recruiters leaderboard AND the caller's own invite progress
    with a one-tap share button. Goal: social proof + friction-free sharing."""
    user  = update.message.from_user
    u_doc = get_user_fast(str(user.id), user.username, user.full_name)
    db    = _get_db()

    # ── Top recruiters ────────────────────────────────────────────────────
    top = list(db["users"].find({"referral_count": {"$gt": 0}})
                           .sort("referral_count", -1)
                           .limit(10))
    medals = ["🥇","🥈","🥉"] + [f"{i}." for i in range(4, 11)]
    hall_lines = ["🏆 *REFERRAL HALL OF FAME*", ""]
    for i, doc in enumerate(top):
        tag   = f"@{_safe_md(doc['username'])}" if doc.get("username") and doc["username"] != "Unknown" else _safe_md(doc.get("full_name", "?")[:18])
        count = doc.get("referral_count", 0)
        earned= doc.get("referral_coins_earned", 0)
        hall_lines.append(f"{medals[i]} {tag} — 🤝 *{count}* friends · 🪙 {earned:,} earned")

    # ── Caller's personal progress ────────────────────────────────────────
    my_count  = u_doc.get("referral_count", 0)
    my_earned = u_doc.get("referral_coins_earned", 0)
    nxt = _next_referral_milestone(my_count, u_doc.get("referral_milestones_claimed", []))
    milestone_line = ""
    if nxt:
        threshold, bonus = nxt
        need = max(threshold - my_count, 0)
        # Simple ASCII progress bar: 10 blocks
        filled = min(10, int(10 * my_count / threshold))
        bar = "█" * filled + "░" * (10 - filled)
        milestone_line = (
            f"\n🎯 *Next milestone:* {threshold} friends → +{bonus:,} 🪙 bonus"
            f"\n`[{bar}]` {my_count}/{threshold} ({need} to go)"
        )
    else:
        milestone_line = "\n🎉 *All milestones claimed!* You're a Growth Legend 🚀"

    try:
        bot_username = (await context.bot.get_me()).username
    except Exception:
        bot_username = "AiraBot"
    link = f"https://t.me/{bot_username}?start=ref_{user.id}"
    share_text = quote("Join me on Aira — games, casino, hunting & daily rewards inside Telegram! 🎮🪙")
    share_url  = f"https://t.me/share/url?url={quote(link, safe='')}&text={share_text}"

    personal_lines = [
        "",
        f"📊 *Your Stats*",
        f"🤝 Friends invited: *{my_count}*",
        f"🪙 Coins earned from referrals: *{my_earned:,}*",
        f"{milestone_line}",
        "",
        f"🔗 `{link}`",
        "_Tap 📤 Share to invite — your friends get +{bonus_new} 🪙 just for joining!_".format(bonus_new=REFERRAL_BONUS_NEW_USER),
    ]

    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("📤 Share My Invite Link", url=share_url)],
        [InlineKeyboardButton("➕ Add Aira to a Group", url=f"https://t.me/{bot_username}?startgroup=true")],
        [InlineKeyboardButton("🏅 Full Referral Board", callback_data="lb_referrals")],
    ])
    await update.message.reply_text(
        "\n".join(hall_lines + personal_lines),
        reply_markup=kb,
        parse_mode="Markdown",
    )

"""
ORACLE CHRONICLES — Aira's Living Murder Mystery for Telegram
══════════════════════════════════════════════════════════════════════════════
Aira add-on module v1.0  |  Paste BEFORE def main() in aira_bot_v9.2.py,
then call  add_mystery_handlers(application)  inside main().
══════════════════════════════════════════════════════════════════════════════
Concepts fused:
  1 — Daily newspaper / document drops with narrative escalation
  2 — 15 explorable locations, spatial navigation, NPC time-windows
  3 — Fully AI-driven suspect characters (OpenRouter), consistent lies, memory
  4 — Timeline reconstruction: find the exact minute of death
  5 — Seven cipher types, one per day, escalating difficulty
  9 — Real-time urgency: new "breaking" development every 4 hours
 10 — Cross-group Nexus: share intelligence, trade clues, build alliances
══════════════════════════════════════════════════════════════════════════════
"""

import asyncio, re, random, io, textwrap, hashlib
import json as _mc_json
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, List, Any

# ══════════════════════════════════════════════════════════════════════════════
#  CONSTANTS
# ══════════════════════════════════════════════════════════════════════════════

_MC_INTERROGATION_COST   = 15   # investigation points per interrogation
_MC_BRIBE_COST           = 40   # investigation points to bribe for extra info
_MC_STAKEOUT_MIN         = 2    # minimum group members to authorise a stakeout
_MC_NEXUS_SHARE_COST     = 30   # coins to post a clue to the Nexus board
_MC_NEXUS_CONFIRM_REWARD = 15   # coins earned when another group confirms your clue
_MC_MAX_ACCUSE_PER_DAY   = 2
_MC_SOLVE_PRIZES         = {1: 80000, 2: 45000, 3: 25000, 4: 12000}
_MC_POINTS_START         = 150

_MC_IST = timezone(timedelta(hours=5, minutes=30))

# Cipher display names
_MC_CIPHER_LABELS = {
    "caesar":     "🔴 Caesar Shift",
    "atbash":     "🟠 Atbash Mirror",
    "number_sub": "🟡 Numerical Code",
    "vigenere_a": "🟢 Vigenère Grid — Alpha",
    "vigenere_b": "🔵 Vigenère Grid — Beta",
    "rail_fence": "🟣 Rail Fence",
    "acrostic":   "⬛ The Acrostic",
}

# Unsplash photo IDs keyed by location image_type
_MC_UNSPLASH = {
    "study":        "1481627834876-b7833e8f5778",
    "library":      "1507842217343-583bb2515b39",
    "kitchen":      "1556909114-f6e7ad7d3136",
    "garden":       "1462275646964-a0e3386b89ae",
    "bedroom":      "1631049307264-da0ec9d70304",
    "wine_cellar":  "1474722883778-792e7fb1e4fe",
    "ballroom":     "1507003211169-0a1dd7228f2d",
    "greenhouse":   "1416879595882-3373a0480b5b",
    "attic":        "1558642891-54be180ea339",
    "servants":     "1533090161767-e6ffed986c88",
    "drawing_room": "1555041469-db61f0bab158",
    "chapel":       "1473177104440-ac22892562d5",
    "basement":     "1558008258-3256797b43f3",
    "foyer":        "1567767292278-a4bde2d3dd5a",
    "rooftop":      "1477959858617-67f85cf4f1df",
    "default":      "1518455027359-f3f8164ba6bd",
}

def _mc_photo_url(image_type: str) -> str:
    pid = _MC_UNSPLASH.get(image_type, _MC_UNSPLASH["default"])
    return f"https://images.unsplash.com/photo-{pid}?w=900&q=80&fit=crop"

# ══════════════════════════════════════════════════════════════════════════════
#  CIPHER ENGINE — 7 different cipher types
# ══════════════════════════════════════════════════════════════════════════════

def _mc_caesar(text: str, shift: int) -> str:
    out = []
    for ch in text.upper():
        if ch.isalpha():
            out.append(chr((ord(ch) - 65 + shift) % 26 + 65))
        else:
            out.append(ch)
    return "".join(out)

def _mc_atbash(text: str) -> str:
    out = []
    for ch in text.upper():
        out.append(chr(90 - (ord(ch) - 65)) if ch.isalpha() else ch)
    return "".join(out)

def _mc_num_encode(text: str) -> str:
    parts = []
    for ch in text.upper():
        if ch.isalpha():
            parts.append(str(ord(ch) - 64))
        elif ch == " ":
            parts.append("00")
    return "-".join(parts)

def _mc_num_decode(text: str) -> str:
    out = []
    for tok in text.split("-"):
        try:
            v = int(tok)
            if v == 0 or tok == "00":
                out.append(" ")
            elif 1 <= v <= 26:
                out.append(chr(v + 64))
        except ValueError:
            pass
    return "".join(out).strip()

def _mc_vigenere(text: str, key: str, encode: bool = True) -> str:
    key = re.sub(r'[^A-Z]', '', key.upper())
    if not key:
        return text
    out, ki = [], 0
    for ch in text.upper():
        if ch.isalpha():
            shift = ord(key[ki % len(key)]) - 65
            if not encode:
                shift = -shift
            out.append(chr((ord(ch) - 65 + shift) % 26 + 65))
            ki += 1
        else:
            out.append(ch)
    return "".join(out)

def _mc_rail_fence(text: str, rails: int = 3) -> str:
    text = text.upper().replace(" ", "_")
    fence = [[] for _ in range(rails)]
    rail, step = 0, 1
    for ch in text:
        fence[rail].append(ch)
        if rail == 0:
            step = 1
        elif rail == rails - 1:
            step = -1
        rail += step
    return "".join("".join(r) for r in fence)

def _mc_encode(plain: str, cipher_type: str, key: str) -> str:
    p = plain.upper().strip()
    if cipher_type == "caesar":
        return _mc_caesar(p, int(key))
    if cipher_type == "atbash":
        return _mc_atbash(p)
    if cipher_type == "number_sub":
        return _mc_num_encode(p)
    if cipher_type in ("vigenere_a", "vigenere_b"):
        return _mc_vigenere(p, key, encode=True)
    if cipher_type == "rail_fence":
        return _mc_rail_fence(p, int(key))
    if cipher_type == "acrostic":
        return p  # acrostic: the paragraph IS the cipher
    return p

def _mc_cipher_hint_text(cipher_type: str, key: str, day_content: str) -> str:
    hints = {
        "caesar":     f"Each letter was shifted *{key}* positions forward. A→{chr(65+int(key)%26)}, B→{chr(66+int(key)%26)} ...",
        "atbash":     "The alphabet is reversed — A becomes Z, B becomes Y, Z becomes A.",
        "number_sub": "Each number is a letter's position: 1=A, 2=B ... 26=Z. Zeros are spaces.",
        "vigenere_a": f"A Vigenère cipher. The key is a word hidden in today's document. Look carefully.",
        "vigenere_b": f"Another Vigenère cipher. A different key word — check earlier suspect statements.",
        "rail_fence": "Write the text as a zigzag across 3 rails, then read each rail left to right.",
        "acrostic":   "Read only the *first letter of each sentence*, top to bottom.",
    }
    return hints.get(cipher_type, "Study the pattern.")

def _mc_verify(submitted: str, solution: str) -> bool:
    def norm(s: str) -> str:
        return re.sub(r'[^a-z0-9]', '', s.lower())
    return norm(submitted) == norm(solution)

# ══════════════════════════════════════════════════════════════════════════════
#  DB HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def _mc_db():
    return _get_db()

def _mc_get_case() -> Optional[Dict]:
    return _mc_db()["mystery_case"].find_one({"_id": "active"})

def _mc_save_case(case: Dict):
    _mc_db()["mystery_case"].replace_one({"_id": "active"}, case, upsert=True)

def _mc_get_group_inv(chat_id: int) -> Dict:
    doc = _mc_db()["group_mystery"].find_one({"_id": chat_id})
    case = _mc_get_case() or {}
    return doc or {
        "_id": chat_id,
        "case_id": case.get("case_id", ""),
        "evidence": [],
        "timeline": [],
        "suspect_chats": {},       # suspect_id -> list of {role, content}
        "suspect_stress": {},      # suspect_id -> int 0-100
        "examined": [],            # item ids already examined
        "current_location": None,
        "stakeout": None,
        "points": _MC_POINTS_START,
        "accusations_today": 0,
        "last_accuse_date": "",
        "accusations_log": [],
        "decoded_ciphers": [],
        "nexus_posted": [],
        "solved": False,
        "solve_time": None,
        "score": 0,
    }

def _mc_save_group_inv(doc: Dict):
    _mc_db()["group_mystery"].replace_one({"_id": doc["_id"]}, doc, upsert=True)

def _mc_get_nexus() -> Dict:
    return _mc_db()["meta"].find_one({"_id": "mystery_nexus"}) or \
           {"_id": "mystery_nexus", "clues": [], "confirmed": [], "week": ""}

def _mc_save_nexus(nx: Dict):
    _mc_db()["meta"].replace_one({"_id": "mystery_nexus"}, nx, upsert=True)

def _mc_get_all_group_invs() -> List[Dict]:
    case = _mc_get_case()
    if not case:
        return []
    return list(_mc_db()["group_mystery"].find({"case_id": case.get("case_id", "NONE")}))

def _mc_broadcast_chats() -> List[int]:
    """Returns all chat IDs that should receive mystery broadcasts."""
    doc = _mc_db()["meta"].find_one({"_id": "broadcast"}) or {}
    groups = set(doc.get("groups", []))
    return list(groups)

def _mc_add_evidence(inv: Dict, clue: str):
    clue = clue.strip()
    if clue and clue not in inv["evidence"]:
        inv["evidence"].append(clue)

def _mc_add_timeline(inv: Dict, time_str: str, event: str, by: str):
    entry = {"time": time_str.strip(), "event": event.strip(), "by": by}
    inv["timeline"].append(entry)
    inv["timeline"].sort(key=lambda e: e["time"])

# ══════════════════════════════════════════════════════════════════════════════
#  MYSTERY GENERATION PROMPT
# ══════════════════════════════════════════════════════════════════════════════

_MC_GEN_PROMPT = r"""You are the architect of ORACLE CHRONICLES — a week-long, deeply puzzling interactive murder mystery played live on Telegram groups. Generate a UNIQUE, FIENDISHLY COMPLEX murder mystery as a single JSON object.

CRITICAL RULES:
- Killer must NOT be the most obvious suspect
- 6 suspects — 1 killer, 5 innocents; each innocent has their OWN dark secret (red herrings)
- Murder weapon must be hyper-specific (not just "poison" — exact compound/method)
- No single clue proves guilt; players need to cross-reference at least 4 pieces
- True motive must be genuinely surprising — plant an obvious false motive
- Include at least 3 planted false leads that look incriminating but aren't
- 12 locations; 3 are "evidence hotspots" with hidden key items
- Each suspect's schedule has ONE lie with ONE contradiction hidden in other evidence
- Ciphers encode REAL CLUE TEXT — the decoded message must help the investigation
- Daily drops escalate: Day 1 is accessible, Day 7 demands synthesizing all prior days
- Real-time updates (every 4h) mix genuine breakthroughs with red herrings

SETTINGS IDEAS (pick one, give it a unique name):
Victorian manor, 1930s luxury ocean liner, 1960s grand hotel, isolated Antarctic research station, billionaire's megayacht, ancient monastery, futuristic orbital station, decaying theme park, underground bunker, haunted opera house.

OUTPUT STRICTLY THIS JSON SCHEMA (no extra commentary, no markdown fences):

{
  "case_id": "unique 8-char alphanumeric",
  "title": "dramatic title",
  "subtitle": "atmospheric tagline",
  "setting_name": "specific named location",
  "setting_era": "year or era",
  "setting_description": "2-3 atmospheric sentences",
  "victim": {
    "name": "full name",
    "age": 0,
    "occupation": "job",
    "found_at": "location_id from locations list",
    "time_of_death": "HH:MM",
    "cause_of_death": "specific method",
    "last_seen_alive": "HH:MM — context",
    "last_words": "cryptic phrase that is actually a clue if you know where to look",
    "backstory": "2 sentences — include the real secret that got them killed"
  },
  "suspects": [
    {
      "id": "s1",
      "name": "Full Name",
      "age": 0,
      "relation": "relation to victim",
      "occupation": "job",
      "emoji": "one relevant emoji",
      "personality": "2-sentence character brief for AI roleplay",
      "speech_style": "terse/verbose/nervous/haughty/evasive/etc",
      "alibi_claimed": "what they say they were doing",
      "alibi_true": true,
      "dark_secret": "what they hide that makes them look guilty but isn't murder",
      "is_killer": false,
      "killer_method": "only fill if is_killer=true: exact sequence of events",
      "schedule": {"morning":"loc_id","afternoon":"loc_id","evening":"loc_id","night":"loc_id"},
      "schedule_lie": "which period is false and what the truth is",
      "key_item": "item they carry that becomes evidence",
      "tell": "subtle behaviour when lying that sharp groups may notice"
    }
  ],
  "locations": [
    {
      "id": "location_id",
      "name": "Display Name",
      "description": "atmospheric 2 sentences",
      "image_type": "study|library|kitchen|garden|bedroom|wine_cellar|ballroom|greenhouse|attic|servants|drawing_room|chapel|basement|foyer|rooftop|default",
      "is_crime_scene": false,
      "connected_to": ["other_location_ids"],
      "items": [
        {
          "id": "item_id",
          "name": "Item Name",
          "description": "what it looks like",
          "clue_text": "what examining it reveals — make this a real clue, not just description",
          "is_key": false,
          "hidden": false,
          "requires": null
        }
      ]
    }
  ],
  "true_timeline": [
    {
      "time": "HH:MM",
      "event": "exact event",
      "visible": false,
      "discovered_via": "which item/interrogation/cipher reveals this"
    }
  ],
  "daily_drops": {
    "1": {
      "type": "newspaper",
      "headline": "dramatic headline",
      "byline": "Fake Reporter Name",
      "body": "150-word article with 1 genuine clue buried naturally in prose",
      "cipher_plain": "the decoded clue phrase — max 8 words",
      "cipher_type": "caesar",
      "cipher_key": "7",
      "cipher_context": "in-story reason this coded note exists"
    },
    "2": {
      "type": "forensic_report",
      "report_no": "FR-XXXX",
      "pathologist": "Dr. Fake Name",
      "body": "150-word clinical findings with 1 key anomaly",
      "anomaly": "the single most important medical finding",
      "cipher_plain": "decoded clue phrase",
      "cipher_type": "atbash",
      "cipher_key": "MIRROR",
      "cipher_context": "context"
    },
    "3": {
      "type": "witness_statement",
      "witness": "Minor character name",
      "body": "150-word account with 1 genuine clue and 1 contradiction",
      "contradiction": "what conflicts with prior evidence",
      "cipher_plain": "decoded clue phrase",
      "cipher_type": "number_sub",
      "cipher_key": "NUM",
      "cipher_context": "context"
    },
    "4": {
      "type": "private_document",
      "doc_name": "e.g. victim's private ledger",
      "body": "200-word document with 2 clues and 1 red herring",
      "cipher_plain": "decoded clue phrase",
      "cipher_type": "vigenere_a",
      "cipher_key": "5-7 letter keyword hidden in body text",
      "cipher_context": "context"
    },
    "5": {
      "type": "police_file",
      "file_no": "PF-XXXX",
      "officer": "Det. Fake Name",
      "body": "200-word file showing one alibi collapsing + 1 red herring",
      "bombshell": "the alibi that collapses",
      "cipher_plain": "decoded clue phrase",
      "cipher_type": "vigenere_b",
      "cipher_key": "different 5-7 letter keyword",
      "cipher_context": "context"
    },
    "6": {
      "type": "anonymous_letter",
      "trustworthy": true,
      "body": "150-word letter claiming inside knowledge — may or may not be honest",
      "cipher_plain": "decoded clue phrase",
      "cipher_type": "rail_fence",
      "cipher_key": "3",
      "cipher_context": "context"
    },
    "7": {
      "type": "final_revelation",
      "title": "document title",
      "body": "final evidence that makes everything click if you followed along",
      "acrostic_paragraph": "8-12 sentences; first letter of each spells cipher_plain",
      "cipher_plain": "8-12 word phrase directly stating a key fact",
      "cipher_type": "acrostic",
      "cipher_key": "FIRST",
      "cipher_context": "context"
    }
  },
  "realtime_updates": [
    {
      "offset_hours": 4,
      "title": "Breaking update headline",
      "body": "80-word development",
      "is_red_herring": false,
      "unlocks": "what this enables: 'examine X', 'ask suspect Y about Z'"
    }
  ],
  "solution": {
    "killer_id": "sX",
    "weapon": "specific weapon",
    "location_id": "where murder happened",
    "motive": "the true motive — surprising",
    "time": "HH:MM",
    "evidence_chain": ["step 1 evidence → deduction", "step 2", "step 3", "step 4", "step 5"],
    "killer_mistake": "the single clue that seals their guilt",
    "how_they_almost_escaped": "what almost worked for the killer"
  }
}"""

# ══════════════════════════════════════════════════════════════════════════════
#  AI CALLS — mystery generation + suspect roleplay
# ══════════════════════════════════════════════════════════════════════════════

async def _mc_openrouter(messages: list, max_tokens: int = 4096,
                         temperature: float = 0.85, json_mode: bool = False) -> str:
    """Call OpenRouter. Tries free Gemini Flash first, falls back to other free models."""
    models = [
        "google/gemini-2.0-flash-exp:free",
        "meta-llama/llama-3.3-70b-instruct:free",
        "microsoft/phi-4-reasoning:free",
        "openrouter/free",
    ]
    extra = {"response_format": {"type": "json_object"}} if json_mode else {}
    for model in models:
        try:
            async with httpx.AsyncClient(timeout=90) as client:
                r = await client.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                        "Content-Type": "application/json",
                        "HTTP-Referer": OPENROUTER_SITE_URL,
                        "X-Title": OPENROUTER_APP_NAME,
                    },
                    json={"model": model, "max_tokens": max_tokens,
                          "temperature": temperature, "messages": messages, **extra}
                )
            if r.status_code == 200:
                return r.json()["choices"][0]["message"]["content"]
        except Exception as e:
            logger.warning(f"[Oracle] OpenRouter {model} failed: {e}")
    return ""

async def _mc_generate_case() -> Optional[Dict]:
    """Generate a full mystery case via AI. Returns parsed dict or None."""
    logger.info("[Oracle] Generating new mystery case…")
    raw = await _mc_openrouter(
        [{"role": "user", "content": _MC_GEN_PROMPT}],
        max_tokens=6000, temperature=0.9
    )
    if not raw:
        return None
    raw = re.sub(r'^```(?:json)?\s*', '', raw.strip())
    raw = re.sub(r'\s*```$', '', raw.strip())
    try:
        case = _mc_json.loads(raw)
        # Validate required keys
        required = ["suspects", "locations", "daily_drops", "solution", "victim"]
        if not all(k in case for k in required):
            logger.error("[Oracle] Case JSON missing required keys")
            return None
        if not case.get("case_id"):
            case["case_id"] = hashlib.md5(str(time.time()).encode()).hexdigest()[:8].upper()
        # Pre-compute encoded ciphers for every day
        for day, drop in case["daily_drops"].items():
            plain    = drop.get("cipher_plain", "")
            ctype    = drop.get("cipher_type", "caesar")
            ckey     = str(drop.get("cipher_key", "7"))
            drop["cipher_encoded"] = _mc_encode(plain, ctype, ckey)
        # Tag time opened
        case["week_start"] = datetime.now(_MC_IST).isoformat()
        case["_id"] = "active"
        case["solve_rank"] = 0       # increments as groups solve
        case["solved_by"] = []       # list of chat_ids in solve order
        return case
    except Exception as e:
        logger.error(f"[Oracle] Case parse failed: {e}\nRaw: {raw[:300]}")
        return None

async def _mc_suspect_reply(case: Dict, suspect_id: str,
                             question: str, inv: Dict) -> str:
    """Get an in-character AI response from a suspect. Maintains per-group memory."""
    suspect = next((s for s in case["suspects"] if s["id"] == suspect_id), None)
    if not suspect:
        return "_(That person doesn't seem to be here.)_"

    victim   = case["victim"]
    solution = case["solution"]
    is_killer = suspect.get("is_killer", False)

    system = f"""You are {suspect['name']}, {suspect['age']} years old, {suspect['occupation']}.
Setting: {case['setting_name']}, {case['setting_era']}.
The victim is {victim['name']} — found dead at {victim['time_of_death']}.

YOUR CHARACTER:
{suspect['personality']}
Speech style: {suspect['speech_style']}.
Your alibi: {suspect['alibi_claimed']}.
Your dark secret (you are HIDING this — not the murder, just your secret): {suspect['dark_secret']}.
Your "tell" when lying: {suspect['tell']}.

{"YOU ARE THE KILLER. You committed the murder. You know the truth but must hide it. Your method: " + suspect.get('killer_method','') if is_killer else "You did NOT commit the murder. You are innocent but hiding your own secret."}

RULES:
- Stay in character at all times. Use your speech style.
- If asked about your alibi, give it confidently ({"it's false — adjust slightly if caught in a contradiction" if not suspect.get('alibi_true') else "it's true"}).
- If asked directly about your secret, deny, deflect, or partially admit — never fully confess.
- If your stress is high (from many hard questions), let tiny cracks show — a pause, a slip of word.
- NEVER break character or acknowledge this is a game.
- Respond in 2-5 sentences only. Be vivid and atmospheric.
- Group's current stress reading for you: {inv['suspect_stress'].get(suspect_id, 0)}/100."""

    history  = inv["suspect_chats"].get(suspect_id, [])
    messages = [{"role": "system", "content": system}]
    messages += history[-8:]  # last 8 turns for context window
    messages.append({"role": "user", "content": question})

    reply = await _mc_openrouter(messages, max_tokens=200, temperature=0.82)
    if not reply:
        reply = f"_{suspect['name']} stares at you coldly and says nothing._"
    return reply

# ══════════════════════════════════════════════════════════════════════════════
#  MESSAGE FORMATTERS — beautiful Telegram output
# ══════════════════════════════════════════════════════════════════════════════

def _mc_bar(val: int, mx: int = 100, width: int = 10) -> str:
    filled = min(width, int(width * val / max(mx, 1)))
    return "█" * filled + "░" * (width - filled)

def _mc_stress_emoji(stress: int) -> str:
    if stress < 25:  return "😐"
    if stress < 50:  return "😰"
    if stress < 75:  return "😨"
    return "💀"

def _mc_case_header(case: Dict) -> str:
    v = case["victim"]
    week_start = datetime.fromisoformat(case.get("week_start","")).strftime("%d %b %Y") \
                 if case.get("week_start") else "?"
    solves = len(case.get("solved_by", []))
    return (
        f"🔮 *ORACLE CHRONICLES*\n"
        f"┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄\n"
        f"📁 *Case:* {_safe_md(case['title'])}\n"
        f"_{_safe_md(case['subtitle'])}_\n"
        f"📍 {_safe_md(case['setting_name'])} · {_safe_md(case['setting_era'])}\n"
        f"💀 *Victim:* {_safe_md(v['name'])}, {v['age']}\n"
        f"🕰️ *Time of Death:* {v['time_of_death']}\n"
        f"🔪 *Cause:* {_safe_md(v['cause_of_death'])}\n"
        f"📅 *Week started:* {week_start}\n"
        f"🏆 *Groups solved so far:* {solves}"
    )

def _mc_format_newspaper(drop: Dict) -> str:
    return (
        f"📰 *THE ORACLE TIMES*\n"
        f"{'━'*28}\n"
        f"*{_safe_md(drop['headline'])}*\n"
        f"{'━'*28}\n"
        f"_By {_safe_md(drop.get('byline','Our Correspondent'))}_\n\n"
        f"{_safe_md(drop['body'])}\n\n"
        f"{'━'*28}\n"
        f"🔐 *CIPHER EMBEDDED IN TODAY'S PRINT*\n"
        f"`{drop['cipher_encoded']}`\n"
        f"📝 _{_safe_md(drop['cipher_context'])}_\n"
        f"Type `/decode <your answer>` when you crack it."
    )

def _mc_format_forensic(drop: Dict) -> str:
    return (
        f"🔬 *FORENSIC PATHOLOGY REPORT*\n"
        f"```\nReport No : {drop.get('report_no','FR-????')}\n"
        f"Pathologist: {drop.get('pathologist','Dr. Unknown')}\n"
        f"{'─'*35}\n"
        f"{textwrap.fill(drop['body'], 60)}\n```\n\n"
        f"⚠️ *FLAGGED ANOMALY:*\n_{_safe_md(drop.get('anomaly','See above.'))}_\n\n"
        f"🔐 *CIPHER — encoded note found on the report:*\n"
        f"`{drop['cipher_encoded']}`\n"
        f"_{_safe_md(drop['cipher_context'])}_\n"
        f"Type `/decode <your answer>`"
    )

def _mc_format_witness(drop: Dict) -> str:
    return (
        f"👁️ *OFFICIAL WITNESS STATEMENT*\n"
        f"```\nWitness : {drop.get('witness','Anonymous')}\n"
        f"{'─'*35}\n"
        f"{textwrap.fill(drop['body'], 60)}\n```\n\n"
        f"⚡ *CONTRADICTION WITH PRIOR EVIDENCE:*\n"
        f"_{_safe_md(drop.get('contradiction','Study this carefully.'))}_\n\n"
        f"🔐 *CIPHER:*\n`{drop['cipher_encoded']}`\n"
        f"_{_safe_md(drop['cipher_context'])}_\n`/decode <answer>`"
    )

def _mc_format_private_doc(drop: Dict) -> str:
    return (
        f"📄 *PRIVATE DOCUMENT RECOVERED*\n"
        f"_{_safe_md(drop.get('doc_name','Undisclosed document'))}_\n"
        f"{'━'*28}\n"
        f"{_safe_md(drop['body'])}\n"
        f"{'━'*28}\n"
        f"🔐 *VIGENÈRE CIPHER — the key is hidden above:*\n"
        f"`{drop['cipher_encoded']}`\n"
        f"_{_safe_md(drop['cipher_context'])}_\n`/decode <answer>`"
    )

def _mc_format_police_file(drop: Dict) -> str:
    return (
        f"🚔 *POLICE INVESTIGATION FILE*\n"
        f"```\nFile No  : {drop.get('file_no','PF-????')}\n"
        f"Officer  : {drop.get('officer','Det. Unknown')}\n"
        f"{'─'*35}\n"
        f"{textwrap.fill(drop['body'], 60)}\n```\n\n"
        "💥 *ALIBI COLLAPSE:*\n_" + _safe_md(drop.get("bombshell","Something doesnt add up.")) + "_\n\n"
        f"🔐 *CIPHER:*\n`{drop['cipher_encoded']}`\n"
        f"_{_safe_md(drop['cipher_context'])}_\n`/decode <answer>`"
    )

def _mc_format_anon_letter(drop: Dict) -> str:
    trust = "⚠️ _Authenticity uncertain — treat with caution._" \
            if not drop.get("trustworthy") else "✅ _Source later verified by Nexus._"
    return (
        f"✉️ *ANONYMOUS LETTER*\n"
        f"_{trust}_\n"
        f"{'━'*28}\n"
        f"{_safe_md(drop['body'])}\n"
        f"{'━'*28}\n"
        f"🔐 *RAIL FENCE CIPHER (3 rails):*\n"
        f"`{drop['cipher_encoded']}`\n"
        f"_{_safe_md(drop['cipher_context'])}_\n`/decode <answer>`"
    )

def _mc_format_final(drop: Dict) -> str:
    return (
        f"🌑 *THE FINAL REVELATION*\n"
        f"_{_safe_md(drop.get('title','CLASSIFIED'))}_\n"
        f"{'━'*28}\n"
        f"{_safe_md(drop['body'])}\n"
        f"{'━'*28}\n"
        f"🔐 *THE ACROSTIC — read the first letter of each sentence:*\n\n"
        f"_{_safe_md(drop.get('acrostic_paragraph', drop.get('body','')))}_\n\n"
        f"`/decode <what the letters spell>`"
    )

_MC_DROP_FORMATTERS = {
    "newspaper":       _mc_format_newspaper,
    "forensic_report": _mc_format_forensic,
    "witness_statement": _mc_format_witness,
    "private_document":  _mc_format_private_doc,
    "police_file":     _mc_format_police_file,
    "anonymous_letter": _mc_format_anon_letter,
    "final_revelation": _mc_format_final,
}

def _mc_format_drop(drop: Dict) -> str:
    fn = _MC_DROP_FORMATTERS.get(drop.get("type", ""), lambda d: _safe_md(d.get("body", "")))
    return fn(drop)

def _mc_chunk(text: str, limit: int = 3800) -> List[str]:
    lines   = text.split("\n")
    chunks, cur = [], ""
    for line in lines:
        candidate = f"{cur}\n{line}" if cur else line
        if len(candidate) > limit and cur:
            chunks.append(cur)
            cur = line
        else:
            cur = candidate
    if cur:
        chunks.append(cur)
    return chunks or [text[:limit]]

# ══════════════════════════════════════════════════════════════════════════════
#  SEND HELPERS — photo + text with fallback
# ══════════════════════════════════════════════════════════════════════════════

async def _mc_send(bot, chat_id: int, text: str, parse_mode: str = "Markdown",
                   reply_markup=None, **kwargs):
    """Send chunked Markdown text safely."""
    chunks = _mc_chunk(text)
    for i, chunk in enumerate(chunks):
        try:
            kw = {"parse_mode": parse_mode}
            if reply_markup and i == len(chunks) - 1:
                kw["reply_markup"] = reply_markup
            kw.update(kwargs)
            await bot.send_message(chat_id, chunk, **kw)
        except Exception as e:
            logger.warning(f"[Oracle] send error {chat_id}: {e}")
            try:
                await bot.send_message(chat_id, chunk)
            except Exception:
                pass
        await asyncio.sleep(0.3)

async def _mc_send_location_photo(bot, chat_id: int, location: Dict, caption: str = ""):
    """Try to send a location photo from Unsplash; fall back silently."""
    try:
        url = _mc_photo_url(location.get("image_type", "default"))
        await bot.send_photo(chat_id, photo=url, caption=caption or location.get("name",""),
                             parse_mode="Markdown")
    except Exception:
        pass  # photo failed — text description still sent separately

async def _mc_send_suspect_card(bot, chat_id: int, suspect: Dict):
    """Send a beautiful suspect introduction card."""
    emoji = suspect.get("emoji", "🕵️")
    stress_placeholder = "Calm"
    text = (
        f"{emoji} *{_safe_md(suspect['name'])}*\n"
        f"_{_safe_md(suspect['relation'])} · {_safe_md(suspect['occupation'])} · Age {suspect.get('age','?')}_\n"
        f"┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄\n"
        f"📋 Alibi: _{_safe_md(suspect['alibi_claimed'])}_\n"
        f"🧠 Use `/interrogate {suspect['name'].split()[0]} <question>` to question them.\n"
        f"💡 They will answer — whether truthfully is another matter."
    )
    await _mc_send(bot, chat_id, text)

# ══════════════════════════════════════════════════════════════════════════════
#  COMMAND HANDLERS
# ══════════════════════════════════════════════════════════════════════════════

async def cmd_mystery(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show the current case overview + crime scene photo."""
    if context.args and context.args[0].lower() == "howto":
        await update.message.reply_text(_game_howto("mystery"), parse_mode="Markdown"); return
    case = _mc_get_case()
    if not case:
        await update.message.reply_text(
            "🔮 *No active mystery this week.*\n"
            "ORACLE CHRONICLES runs every Monday–Sunday IST.\n"
            "Next case launches automatically. Stay sharp, detective.",
            parse_mode="Markdown")
        return
    chat_id = update.message.chat_id
    inv     = _mc_get_group_inv(chat_id)

    # Send crime scene photo
    crime_scene_loc = next(
        (l for l in case["locations"] if l.get("is_crime_scene")), None)
    if crime_scene_loc:
        await _mc_send_location_photo(
            context.bot, chat_id, crime_scene_loc,
            caption=f"🚨 CRIME SCENE — {crime_scene_loc['name']}")

    text = _mc_case_header(case) + (
        f"\n\n📍 *Setting:* _{_safe_md(case['setting_description'])}_\n\n"
        f"💬 *Last words of {_safe_md(case['victim']['name'])}:*\n"
        f"_\"{_safe_md(case['victim']['last_words'])}\"_\n\n"
        f"📊 *Your group's investigation:*\n"
        f"🔍 Evidence collected: *{len(inv['evidence'])}*\n"
        f"🗓️ Timeline entries: *{len(inv['timeline'])}*\n"
        f"⚡ Investigation points: *{inv['points']}*\n\n"
        f"*Commands:* /suspects · /goto · /examine · /interrogate\n"
        f"/evidence · /timeline · /decode · /accuse · /nexus"
    )
    await _mc_send(context.bot, chat_id, text)


async def cmd_suspects(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """List all suspects with their stress levels."""
    case = _mc_get_case()
    if not case:
        await update.message.reply_text("No active mystery."); return
    chat_id = update.message.chat_id
    inv     = _mc_get_group_inv(chat_id)

    lines = ["🕵️ *PERSONS OF INTEREST*\n┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄\n"]
    for s in case["suspects"]:
        stress  = inv["suspect_stress"].get(s["id"], 0)
        s_emoji = _mc_stress_emoji(stress)
        bar     = _mc_bar(stress)
        lines.append(
            f"{s.get('emoji','👤')} *{_safe_md(s['name'])}*\n"
            f"   _{_safe_md(s['relation'])} · {_safe_md(s['occupation'])}_\n"
            f"   Stress {s_emoji} `[{bar}]` {stress}/100\n"
            f"   `/interrogate {s['name'].split()[0]} <your question>`\n"
        )
    lines.append("💡 _Higher stress = more cracks in their story. Push hard._")
    await _mc_send(context.bot, chat_id, "\n".join(lines))


async def cmd_goto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Travel to a location: /goto <location name>"""
    case = _mc_get_case()
    if not case:
        await update.message.reply_text("No active mystery."); return
    if not context.args:
        await update.message.reply_text(
            "Usage: `/goto <location name>`\nTry `/mystery` to see where the case is set.",
            parse_mode="Markdown"); return

    query     = " ".join(context.args).lower().strip()
    chat_id   = update.message.chat_id
    inv       = _mc_get_group_inv(chat_id)

    # Fuzzy match location name or id
    loc = next(
        (l for l in case["locations"]
         if query in l["name"].lower() or query in l["id"].lower()), None)
    if not loc:
        names = "\n".join(f"• `{l['name']}`" for l in case["locations"])
        await update.message.reply_text(
            f"❓ *Location not found.*\n\n{names}\n\n_Use `/goto <name>` to travel._",
            parse_mode="Markdown")
        return

    inv["current_location"] = loc["id"]
    _mc_save_group_inv(inv)

    # Who is here now?
    now_period = _mc_time_period()
    suspects_here = [
        s for s in case["suspects"]
        if s["schedule"].get(now_period) == loc["id"]
    ]

    # Send location photo + description
    await _mc_send_location_photo(context.bot, chat_id, loc,
                                   caption=f"📍 {loc['name']}")
    cs_tag = " 🚨 *CRIME SCENE*" if loc.get("is_crime_scene") else ""
    text = (
        f"📍 *{_safe_md(loc['name'])}*{cs_tag}\n"
        f"_{_safe_md(loc['description'])}_\n\n"
    )
    visible_items = [i for i in loc.get("items", []) if not i.get("hidden")]
    if visible_items:
        text += "🔍 *Things to examine here:*\n"
        for item in visible_items:
            done = "✅" if item["id"] in inv["examined"] else "🔲"
            text += f"  {done} `/examine {item['id']}` — {_safe_md(item['name'])}\n"
    else:
        text += "_Nothing obvious stands out — look harder._\n"

    if suspects_here:
        text += f"\n👤 *Present now ({now_period.replace('_',' ')}):*\n"
        for s in suspects_here:
            text += f"  {s.get('emoji','👤')} {_safe_md(s['name'])} — `/interrogate {s['name'].split()[0]} <question>`\n"
    else:
        text += f"\n_No suspects here right now ({now_period.replace('_',' ')})._"

    connected = [l for l in case["locations"] if l["id"] in loc.get("connected_to", [])]
    if connected:
        text += "\n\n🗺️ *Connected locations:*\n"
        for cl in connected:
            text += f"  `/goto {cl['name'].replace(' ','_')}` — {_safe_md(cl['name'])}\n"

    await _mc_send(context.bot, chat_id, text)


async def cmd_examine(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Examine an item: /examine <item_id>"""
    case = _mc_get_case()
    if not case:
        await update.message.reply_text("No active mystery."); return
    if not context.args:
        await update.message.reply_text(
            "Usage: `/examine <item_id>` — use `/goto <location>` first to see items.",
            parse_mode="Markdown"); return

    item_id = context.args[0].lower().strip()
    chat_id = update.message.chat_id
    inv     = _mc_get_group_inv(chat_id)

    # Find the item anywhere in the case
    found_item = found_loc = None
    for loc in case["locations"]:
        for item in loc.get("items", []):
            if item["id"] == item_id:
                found_item = item
                found_loc  = loc
                break
        if found_item:
            break

    if not found_item:
        await update.message.reply_text("❓ No such item. Check `/goto <location>` for available items.")
        return

    # Check if player is at this location
    if inv.get("current_location") != found_loc["id"]:
        await update.message.reply_text(
            f"⚠️ You're not at *{_safe_md(found_loc['name'])}*. "
            f"Use `/goto {found_loc['name'].replace(' ','_')}` first.",
            parse_mode="Markdown"); return

    # Check requirements
    if found_item.get("requires") and found_item["requires"] not in inv["examined"]:
        await update.message.reply_text(
            f"🔒 You need to examine `{found_item['requires']}` first to access this.",
            parse_mode="Markdown"); return

    already_done = item_id in inv["examined"]
    if not already_done:
        inv["examined"].append(item_id)

    # Add clue to evidence board
    clue = found_item.get("clue_text", "")
    if clue:
        _mc_add_evidence(inv, clue)

    _mc_save_group_inv(inv)

    star = "⭐ " if found_item.get("is_key") else ""
    text = (
        f"🔍 *EXAMINING:* {star}{_safe_md(found_item['name'])}\n"
        f"📍 Location: {_safe_md(found_loc['name'])}\n"
        f"{'━'*26}\n"
        f"_{_safe_md(found_item['description'])}_\n\n"
        f"📋 *What you notice:*\n"
        f"{_safe_md(clue)}\n"
    )
    if found_item.get("is_key"):
        text += "\n🌟 *KEY EVIDENCE — added to your case file automatically!*"
    elif not already_done:
        text += "\n📌 _Clue logged to your evidence board._"
    else:
        text += "\n_(You've examined this before — same findings.)_"

    await _mc_send(context.bot, chat_id, text)


async def cmd_interrogate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Question a suspect: /interrogate <Name> <question>"""
    case = _mc_get_case()
    if not case:
        await update.message.reply_text("No active mystery."); return
    if len(context.args) < 2:
        await update.message.reply_text(
            "Usage: `/interrogate <SuspectFirstName> <your question>`",
            parse_mode="Markdown"); return

    chat_id = update.message.chat_id
    inv     = _mc_get_group_inv(chat_id)

    if inv["points"] < _MC_INTERROGATION_COST:
        await update.message.reply_text(
            f"⚡ Not enough investigation points ({inv['points']}/{_MC_INTERROGATION_COST} needed).\n"
            "Solve daily ciphers and examine items to earn more!"); return

    name_query = context.args[0].lower()
    question   = " ".join(context.args[1:])
    suspect    = next(
        (s for s in case["suspects"] if name_query in s["name"].lower()), None)
    if not suspect:
        names = " | ".join(s['name'].split()[0] for s in case["suspects"])
        await update.message.reply_text(
            f"❓ Suspect not found. Known names: {names}"); return

    # Deduct points and raise stress
    inv["points"] -= _MC_INTERROGATION_COST
    stress = inv["suspect_stress"].get(suspect["id"], 0)
    stress = min(100, stress + random.randint(8, 18))
    inv["suspect_stress"][suspect["id"]] = stress

    # Thinking indicator
    _think_msgs = [
        f"_{suspect.get('emoji','👤')} *{suspect['name'].split()[0]}* pauses, choosing their words carefully…_",
        f"_{suspect.get('emoji','👤')} *{suspect['name'].split()[0]}* looks at you for a long moment…_",
        f"_{suspect.get('emoji','👤')} *{suspect['name'].split()[0]}* shifts uncomfortably…_",
        f"_{suspect.get('emoji','👤')} *{suspect['name'].split()[0]}* takes a slow breath before answering…_",
    ]
    _think_text = _think_msgs[stress // 25 % len(_think_msgs)]
    thinking = await update.message.reply_text(_think_text, parse_mode="Markdown")

    reply = await _mc_suspect_reply(case, suspect["id"], question, inv)

    # Save conversation history
    history = inv["suspect_chats"].setdefault(suspect["id"], [])
    history.append({"role": "user", "content": question})
    history.append({"role": "assistant", "content": reply})
    if len(history) > 20:
        history[:] = history[-20:]

    _mc_save_group_inv(inv)

    try:
        await thinking.delete()
    except Exception:
        pass

    stress_bar  = _mc_bar(stress)
    stress_icon = _mc_stress_emoji(stress)
    text = (
        f"{suspect.get('emoji','👤')} *{_safe_md(suspect['name'])}* says:\n"
        f"{'━'*26}\n"
        f"_{_safe_md(reply)}_\n"
        f"{'━'*26}\n"
        f"Stress {stress_icon} `[{stress_bar}]` {stress}/100  |  "
        f"⚡ {inv['points']} pts left"
    )
    if stress >= 90:
        text += "\n\n🔥 *They're barely holding together. One more push could break them.*"
    elif stress >= 75:
        text += "\n\n⚡ *They're cracking. You can feel the inconsistencies building.*"
    elif stress >= 50:
        text += "\n\n👁️ _Something in their composure is starting to slip._"
    await _mc_send(context.bot, chat_id, text)


async def cmd_evidence(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """View the group's evidence board."""
    case = _mc_get_case()
    if not case:
        await update.message.reply_text("No active mystery."); return
    chat_id = update.message.chat_id
    inv     = _mc_get_group_inv(chat_id)

    if not inv["evidence"]:
        await update.message.reply_text(
            "📋 *Evidence Board* — empty\n\n"
            "_Explore locations with `/goto`, examine items, crack ciphers._",
            parse_mode="Markdown"); return

    lines = [f"📋 *EVIDENCE BOARD — {len(inv['evidence'])} clues collected*\n"]
    for i, clue in enumerate(inv["evidence"], 1):
        lines.append(f"*{i}.* {_safe_md(clue)}")
    lines.append(f"\n⚡ Points: *{inv['points']}*  |  "
                 f"🔐 Ciphers solved: *{len(inv['decoded_ciphers'])}*")
    await _mc_send(context.bot, chat_id, "\n".join(lines))


async def cmd_timeline(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Add to or view timeline: /timeline add HH:MM <event> | /timeline view"""
    case = _mc_get_case()
    if not case:
        await update.message.reply_text("No active mystery."); return
    chat_id = update.message.chat_id
    inv     = _mc_get_group_inv(chat_id)
    args    = context.args

    if args and args[0].lower() == "view" or not args:
        if not inv["timeline"]:
            await update.message.reply_text(
                "🗓️ *Timeline* — empty\n_Add entries with `/timeline add HH:MM <event>`_",
                parse_mode="Markdown"); return
        lines = [f"🗓️ *TIMELINE — {len(inv['timeline'])} entries*\n"]
        for e in inv["timeline"]:
            lines.append(f"`{e['time']}` — {_safe_md(e['event'])} _(by {_safe_md(e['by'])})_")
        await _mc_send(context.bot, chat_id, "\n".join(lines))
        return

    if args[0].lower() == "add":
        if len(args) < 3:
            await update.message.reply_text(
                "Usage: `/timeline add HH:MM <event description>`",
                parse_mode="Markdown"); return
        time_str = args[1]
        if not re.match(r'^\d{1,2}:\d{2}$', time_str):
            await update.message.reply_text("⚠️ Time must be HH:MM format."); return
        event = " ".join(args[2:])
        user  = update.message.from_user
        name  = f"@{user.username}" if user.username else user.full_name
        _mc_add_timeline(inv, time_str, event, name)
        _mc_save_group_inv(inv)
        await update.message.reply_text(
            f"🗓️ Added to timeline: `{time_str}` — {_safe_md(event)}",
            parse_mode="Markdown")
        return

    await update.message.reply_text(
        "Usage:\n`/timeline add HH:MM <event>` — add entry\n`/timeline view` — see full timeline",
        parse_mode="Markdown")


async def cmd_decode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Submit a cipher solution: /decode <your decoded text>"""
    case = _mc_get_case()
    if not case:
        await update.message.reply_text("No active mystery."); return
    if not context.args:
        await update.message.reply_text(
            "Usage: `/decode <what you think the cipher says>`", parse_mode="Markdown"); return

    chat_id = update.message.chat_id
    inv     = _mc_get_group_inv(chat_id)
    user    = update.message.from_user
    name    = f"@{user.username}" if user.username else user.full_name
    answer  = " ".join(context.args).strip()

    now_ist  = datetime.now(_MC_IST)
    week_start = datetime.fromisoformat(case.get("week_start","")).astimezone(_MC_IST) \
                 if case.get("week_start") else now_ist
    day_num = max(1, min(7, (now_ist.date() - week_start.date()).days + 1))

    # Check all days' ciphers (can solve any past or current day)
    for d in range(1, day_num + 1):
        drop = case["daily_drops"].get(str(d))
        if not drop:
            continue
        plain = drop.get("cipher_plain", "")
        if _mc_verify(answer, plain):
            key_name = f"cipher_day_{d}"
            already  = key_name in inv["decoded_ciphers"]
            if not already:
                inv["decoded_ciphers"].append(key_name)
                inv["points"] += 25
                clue_to_add = f"[Day {d} Cipher Decoded] {plain}"
                _mc_add_evidence(inv, clue_to_add)
                _mc_save_group_inv(inv)
                await update.message.reply_text(
                    f"🔓 *CIPHER CRACKED!* — Day {d}\n"
                    f"✅ `{_safe_md(plain.upper())}`\n\n"
                    f"📌 Added to your evidence board.\n"
                    f"⚡ +25 investigation points! ({inv['points']} total)\n\n"
                    f"_{_safe_md(drop.get('cipher_context',''))}_",
                    parse_mode="Markdown")
            else:
                await update.message.reply_text(
                    f"✅ Correct (Day {d}) — your group already solved this one.\n"
                    f"`{_safe_md(plain.upper())}`", parse_mode="Markdown")
            return

    day_drop_now = case["daily_drops"].get(str(day_num), {})
    hint_txt = _mc_cipher_hint_text(
        day_drop_now.get("cipher_type",""), str(day_drop_now.get("cipher_key","")), "")
    cipher_label = _MC_CIPHER_LABELS.get(day_drop_now.get("cipher_type",""), "🔐 Cipher")
    await update.message.reply_text(
        f"❌ *Not quite.* That doesn't decode any cipher up to Day {day_num}.\n\n"
        f"Today's cipher: {cipher_label}\n"
        f"💡 *Hint:* _{hint_txt}_\n\n"
        f"_Keep working — the answer is in today's document._",
        parse_mode="Markdown")


async def cmd_casefile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send the full case file as a formatted document."""
    case = _mc_get_case()
    if not case:
        await update.message.reply_text("No active mystery."); return
    chat_id = update.message.chat_id
    inv     = _mc_get_group_inv(chat_id)

    v      = case["victim"]
    lines  = [
        f"ORACLE CHRONICLES — CASE FILE",
        f"{'='*50}",
        f"Case   : {case['title']}",
        f"Setting: {case['setting_name']} ({case['setting_era']})",
        f"Victim : {v['name']}, age {v['age']}, {v['occupation']}",
        f"TOD    : {v['time_of_death']}",
        f"Cause  : {v['cause_of_death']}",
        f"Found  : {v['found_at']}",
        f"Last words: \"{v['last_words']}\"",
        f"{'='*50}",
        f"",
        f"SUSPECTS ({len(case['suspects'])} persons of interest):",
        f"{'-'*40}",
    ]
    for s in case["suspects"]:
        stress = inv["suspect_stress"].get(s["id"], 0)
        lines += [
            f"  {s['name']} ({s['occupation']}, age {s['age']})",
            f"  Relation : {s['relation']}",
            f"  Alibi    : {s['alibi_claimed']}",
            f"  Stress   : {stress}/100",
            f"  Interrogations: {len(inv['suspect_chats'].get(s['id'],[]))//2}",
            f"",
        ]
    lines += [
        f"{'='*50}",
        f"EVIDENCE BOARD ({len(inv['evidence'])} clues):",
        f"{'-'*40}",
    ]
    for i, clue in enumerate(inv["evidence"], 1):
        lines.append(f"  {i}. {clue}")

    lines += [
        f"",
        f"{'='*50}",
        f"TIMELINE ({len(inv['timeline'])} entries):",
        f"{'-'*40}",
    ]
    for e in inv["timeline"]:
        lines.append(f"  {e['time']} | {e['event']} (by {e['by']})")

    lines += [
        f"",
        f"{'='*50}",
        f"CIPHERS DECODED: {len(inv['decoded_ciphers'])}/7",
        f"INVESTIGATION POINTS: {inv['points']}",
        f"ACCUSATIONS MADE: {len(inv['accusations_log'])}",
        f"{'='*50}",
    ]

    buf = io.BytesIO("\n".join(lines).encode("utf-8"))
    buf.name = f"oracle_casefile_{case['case_id']}.txt"
    await update.message.reply_document(
        document=buf,
        caption=f"📁 Your full case file — {case['title']}")


async def cmd_stakeout(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Set up a stakeout at a location: /stakeout <location>"""
    case = _mc_get_case()
    if not case:
        await update.message.reply_text("No active mystery."); return
    if not context.args:
        await update.message.reply_text(
            "Usage: `/stakeout <location name>`\n"
            "If a suspect visits that location in the next hour, you get a confirmed sighting.",
            parse_mode="Markdown"); return

    chat_id = update.message.chat_id
    inv     = _mc_get_group_inv(chat_id)

    query = " ".join(context.args).lower()
    loc   = next((l for l in case["locations"]
                  if query in l["name"].lower() or query in l["id"].lower()), None)
    if not loc:
        await update.message.reply_text("❓ Location not found. Check `/mystery` for location names.")
        return

    # Check if upcoming time period has any suspect at this location
    next_period = _mc_next_time_period()
    suspects_coming = [
        s for s in case["suspects"]
        if s["schedule"].get(next_period) == loc["id"]
    ]

    inv["stakeout"] = {
        "location_id": loc["id"],
        "location_name": loc["name"],
        "period": next_period,
        "suspects_spotted": [s["id"] for s in suspects_coming] if suspects_coming else []
    }
    _mc_save_group_inv(inv)

    text = (
        f"👁️ *STAKEOUT ACTIVE*\n"
        f"📍 {_safe_md(loc['name'])}\n"
        f"⏰ Monitoring: {next_period.replace('_',' ')} window\n\n"
    )
    if suspects_coming:
        text += f"🎯 *Confirmed — someone is there during that window!*\n"
        for s in suspects_coming:
            text += f"  {s.get('emoji','👤')} *{_safe_md(s['name'])}* was at {_safe_md(loc['name'])} — check their alibi!\n"
        text += "\n_This contradicts or confirms their stated movements._"
    else:
        text += "_No suspects scheduled here during that window — either their alibi holds, or they're lying about the time period you checked._"

    await _mc_send(context.bot, chat_id, text)


async def cmd_accuse(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Make a formal accusation: /accuse <name> <weapon> <location> <motive>"""
    case = _mc_get_case()
    if not case:
        await update.message.reply_text("No active mystery."); return
    if len(context.args) < 4:
        await update.message.reply_text(
            "Usage: `/accuse <SuspectName> <weapon> <location> <motive>`\n"
            "Example: `/accuse Edgar prussic_acid study inheritance`",
            parse_mode="Markdown"); return

    chat_id   = update.message.chat_id
    inv       = _mc_get_group_inv(chat_id)
    user      = update.message.from_user
    user_name = f"@{user.username}" if user.username else user.full_name

    # Check daily limit
    today = datetime.now(_MC_IST).date().isoformat()
    if inv.get("last_accuse_date") == today and inv.get("accusations_today", 0) >= _MC_MAX_ACCUSE_PER_DAY:
        await update.message.reply_text(
            f"⛔ *Max {_MC_MAX_ACCUSE_PER_DAY} accusations per day* — you've used yours.\n"
            "Gather more evidence and try again tomorrow.", parse_mode="Markdown"); return

    if inv.get("solved"):
        await update.message.reply_text("✅ Your group already solved this case!"); return

    # Parse accusation
    suspect_query = context.args[0].lower()
    weapon_guess  = context.args[1].lower()
    loc_guess     = context.args[2].lower()
    motive_guess  = " ".join(context.args[3:]).lower()

    solution = case["solution"]
    killer   = next((s for s in case["suspects"] if s["id"] == solution["killer_id"]), {})

    suspect_match  = suspect_query in killer.get("name", "").lower()
    weapon_match   = weapon_guess  in solution["weapon"].lower()
    location_match = loc_guess     in solution["location_id"].lower() or \
                     loc_guess     in solution.get("weapon","").lower()
    motive_match   = motive_guess  in solution["motive"].lower()

    correct_count = sum([suspect_match, weapon_match, location_match, motive_match])

    # Update counters
    if inv.get("last_accuse_date") != today:
        inv["accusations_today"] = 0
        inv["last_accuse_date"]  = today
    inv["accusations_today"] += 1

    accused_name = context.args[0]
    inv["accusations_log"].append({
        "by": user_name, "time": datetime.now(_MC_IST).isoformat(),
        "suspect": accused_name, "correct_fields": correct_count
    })

    if correct_count == 4:
        # SOLVED!
        inv["solved"]     = True
        inv["solve_time"] = datetime.now(_MC_IST).isoformat()
        case["solve_rank"] = case.get("solve_rank", 0) + 1
        rank = case["solve_rank"]
        case.setdefault("solved_by", []).append(chat_id)
        _mc_save_case(case)

        prize = _MC_SOLVE_PRIZES.get(rank, 5000)
        # Award coins to all group members who participated
        _mc_award_solvers(chat_id, prize)
        inv["score"] = prize
        _mc_save_group_inv(inv)

        text = (
            f"🎉🎉🎉 *CASE SOLVED!* 🎉🎉🎉\n"
            f"{'━'*30}\n"
            f"🏆 Your group is *#{rank}* to solve it!\n\n"
            f"🔪 *Killer:* {_safe_md(killer.get('name','?'))}\n"
            f"⚗️ *Weapon:* {_safe_md(solution['weapon'])}\n"
            f"📍 *Location:* {_safe_md(solution['location_id'])}\n"
            f"💢 *Motive:* {_safe_md(solution['motive'])}\n"
            f"🕰️ *Time:* {solution['time']}\n\n"
            f"📖 *How the killer nearly escaped:*\n"
            f"_{_safe_md(solution.get('how_they_almost_escaped',''))}_\n\n"
            f"🪙 *Group reward:* +{prize:,} coins distributed to investigators!\n\n"
            f"_Full evidence chain unlocked — use /casefile for the breakdown._"
        )
        await _mc_send(context.bot, chat_id, text)

        # Broadcast solve to all groups
        asyncio.create_task(_mc_broadcast_solve(context.bot, case, rank, chat_id))
    else:
        score_map = {0: "❌ Completely wrong.", 1: "🟡 1/4 correct.", 2: "🟠 2/4 correct.",
                     3: "🔴 3/4 correct — so close! One element is wrong."}
        verdict   = score_map.get(correct_count, "")
        feedback  = []
        if suspect_match:  feedback.append("✅ Suspect")
        else:              feedback.append("❌ Suspect")
        if weapon_match:   feedback.append("✅ Weapon")
        else:              feedback.append("❌ Weapon")
        if location_match: feedback.append("✅ Location")
        else:              feedback.append("❌ Location")
        if motive_match:   feedback.append("✅ Motive")
        else:              feedback.append("❌ Motive")

        remaining = _MC_MAX_ACCUSE_PER_DAY - inv["accusations_today"]
        text = (
            f"🔍 *ACCUSATION VERDICT*\n"
            f"{'━'*26}\n"
            f"{verdict}\n\n"
            + "\n".join(feedback) +
            f"\n\n{'━'*26}\n"
            f"⚡ Accusations left today: *{remaining}*\n"
            f"_Investigate more, then try again._"
        )
        _mc_save_group_inv(inv)
        await _mc_send(context.bot, chat_id, text)


async def cmd_nexus(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cross-group intelligence board: /nexus | /nexus post <clue> | /nexus view"""
    case = _mc_get_case()
    if not case:
        await update.message.reply_text("No active mystery."); return

    args    = context.args
    chat_id = update.message.chat_id
    sub     = args[0].lower() if args else "view"

    if sub == "view":
        nx    = _mc_get_nexus()
        clues = nx.get("clues", [])
        if not clues:
            await update.message.reply_text(
                "🌐 *NEXUS INTELLIGENCE BOARD* — empty\n\n"
                "_No groups have posted clues yet. Post your discoveries and earn coins!\n"
                "`/nexus post <your clue text>`_",
                parse_mode="Markdown"); return

        lines = [f"🌐 *NEXUS INTELLIGENCE BOARD*\n{len(clues)} clues posted by all groups\n"]
        for i, c in enumerate(clues[-15:], 1):
            confirms = len(c.get("confirmed_by", []))
            star     = "⭐" if confirms >= 3 else "·"
            lines.append(
                f"{star} *#{i}* _{_safe_md(c['clue'])}_\n"
                f"   Posted by Group `{c['by_group']}` · {confirms} confirmations"
            )
        lines.append("\n✅ = confirmed by 3+ groups  |  `/nexus post <clue>` to contribute")
        await _mc_send(context.bot, chat_id, "\n".join(lines))
        return

    if sub == "post":
        if len(args) < 2:
            await update.message.reply_text(
                "Usage: `/nexus post <your clue>`", parse_mode="Markdown"); return

        clue_text = " ".join(args[1:]).strip()
        user      = update.message.from_user
        uid       = str(user.id)
        u_doc     = get_user_fast(uid, user.username, user.full_name)

        if u_doc.get("coins", 0) < _MC_NEXUS_SHARE_COST:
            await update.message.reply_text(
                f"🪙 You need {_MC_NEXUS_SHARE_COST} coins to post to Nexus. "
                f"You have {u_doc.get('coins',0)}."); return

        u_doc["coins"] -= _MC_NEXUS_SHARE_COST
        save_user_fast(uid)

        nx = _mc_get_nexus()
        nx.setdefault("clues", []).append({
            "id": hashlib.md5(f"{chat_id}{time.time()}".encode()).hexdigest()[:8],
            "clue": clue_text,
            "by_group": chat_id,
            "by_user": uid,
            "time": datetime.now(_MC_IST).isoformat(),
            "confirmed_by": [],
        })
        _mc_save_nexus(nx)

        await update.message.reply_text(
            f"🌐 *Intelligence posted to the Nexus board!*\n"
            f"\"{_safe_md(clue_text)}\"\n\n"
            f"🪙 *-{_MC_NEXUS_SHARE_COST} coins* spent.\n"
            f"💰 Earn *+{_MC_NEXUS_CONFIRM_REWARD} coins* each time another group confirms it.\n"
            f"_Share the clue ID with allies, or post in Nexus for everyone to see._",
            parse_mode="Markdown")
        return

    if sub == "confirm":
        # /nexus confirm <clue_id>
        if len(args) < 2:
            await update.message.reply_text(
                "Usage: `/nexus confirm <clue_id>` — view IDs with `/nexus view`",
                parse_mode="Markdown"); return
        cid  = args[1].strip()
        nx   = _mc_get_nexus()
        clue = next((c for c in nx.get("clues", []) if c["id"] == cid), None)
        if not clue:
            await update.message.reply_text("❓ Clue ID not found."); return
        if chat_id in clue["confirmed_by"]:
            await update.message.reply_text("Already confirmed by your group."); return
        if clue["by_group"] == chat_id:
            await update.message.reply_text("You can't confirm your own clue."); return

        clue["confirmed_by"].append(chat_id)
        _mc_save_nexus(nx)

        # Reward the original poster's group
        reward_uid = clue.get("by_user")
        if reward_uid:
            poster = get_user_fast(reward_uid)
            poster["coins"] = poster.get("coins", 0) + _MC_NEXUS_CONFIRM_REWARD
            save_user_fast(reward_uid)

        confirms = len(clue["confirmed_by"])
        conf_note = " 🌟 *Now globally confirmed by 3+ groups!*" if confirms >= 3 else ""
        await update.message.reply_text(
            f"✅ *Confirmed!* ({confirms}/3 needed for global verification){conf_note}\n"
            f"_{_safe_md(clue['clue'])}_",
            parse_mode="Markdown")
        return

    await update.message.reply_text(
        "🌐 *NEXUS — Cross-Group Intelligence*\n\n"
        "`/nexus view` — see all clues from all groups\n"
        f"`/nexus post <clue>` — share a clue (costs {_MC_NEXUS_SHARE_COST} coins)\n"
        "`/nexus confirm <id>` — confirm another group's clue",
        parse_mode="Markdown")


async def cmd_mysteryboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Leaderboard of groups solving mysteries."""
    case = _mc_get_case()
    if not case:
        await update.message.reply_text("No active mystery this week."); return

    all_invs = _mc_get_all_group_invs()
    chat_id  = update.message.chat_id

    # Sort: solved first (by solve rank), then by evidence count
    solved   = sorted([i for i in all_invs if i.get("solved")],
                      key=lambda x: len(x.get("evidence", [])), reverse=True)
    unsolved = sorted([i for i in all_invs if not i.get("solved")],
                      key=lambda x: (len(x.get("decoded_ciphers",[])) +
                                     len(x.get("evidence",[])) +
                                     len(x.get("timeline",[]))), reverse=True)

    lines = [f"🏆 *ORACLE CHRONICLES — WEEKLY STANDINGS*\n{case['title']}\n"]
    medals = ["🥇","🥈","🥉"] + [f"{i}." for i in range(4, 20)]

    rank = 0
    for inv in (solved + unsolved)[:15]:
        rank += 1
        g_id     = inv["_id"]
        is_yours = g_id == chat_id
        tag      = f"*Group {str(g_id)[-4:]}*" + (" ← You" if is_yours else "")
        solved_m = "✅ SOLVED" if inv.get("solved") else "🔍 Investigating"
        ev_count = len(inv.get("evidence", []))
        ciphers  = len(inv.get("decoded_ciphers", []))
        tl_count = len(inv.get("timeline", []))
        lines.append(
            f"{medals[rank-1]} {tag}\n"
            f"   {solved_m} · {ev_count} clues · {ciphers}/7 ciphers · "
            f"{tl_count} timeline entries · {inv.get('points',0)} pts"
        )

    lines.append(f"\n_Solve the murder to claim your place at the top!_")
    await _mc_send(context.bot, chat_id, "\n".join(lines))


async def cmd_mystatus(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Quick investigation status for your group."""
    case = _mc_get_case()
    if not case:
        await update.message.reply_text("No active mystery this week."); return
    chat_id = update.message.chat_id
    inv     = _mc_get_group_inv(chat_id)

    now_ist  = datetime.now(_MC_IST)
    week_start = datetime.fromisoformat(case.get("week_start","")).astimezone(_MC_IST) \
                 if case.get("week_start") else now_ist
    day_num  = max(1, min(7, (now_ist.date() - week_start.date()).days + 1))
    days_left = max(0, 7 - day_num)

    cur_loc  = inv.get("current_location")
    loc_name = next((l["name"] for l in case["locations"] if l["id"] == cur_loc), "Nowhere yet")
    top_stress = sorted(
        [(s["name"], inv["suspect_stress"].get(s["id"], 0)) for s in case["suspects"]],
        key=lambda x: x[1], reverse=True)[:3]

    text = (
        f"📊 *YOUR INVESTIGATION STATUS*\n"
        f"{'━'*28}\n"
        f"📅 Day *{day_num}/7* · {days_left} days remaining\n"
        f"📍 Current location: *{_safe_md(loc_name)}*\n"
        f"🔍 Clues collected: *{len(inv['evidence'])}*\n"
        f"🔐 Ciphers cracked: *{len(inv['decoded_ciphers'])}/7*\n"
        f"🗓️ Timeline entries: *{len(inv['timeline'])}*\n"
        f"⚡ Investigation points: *{inv['points']}*\n"
        f"📋 Accusations made: *{len(inv['accusations_log'])}*\n"
        f"✅ Solved: *{'YES 🎉' if inv.get('solved') else 'Not yet'}*\n\n"
        f"*Top stressed suspects:*\n"
    )
    for name, stress in top_stress:
        text += f"  {_mc_stress_emoji(stress)} {_safe_md(name)} — {stress}/100\n"

    if not inv.get("solved"):
        text += (
            f"\n💡 *Next moves:*\n"
            f"• `/goto <location>` — explore\n"
            f"• `/interrogate <suspect> <question>` — apply pressure\n"
            f"• `/decode <cipher answer>` — crack the daily code\n"
            f"• `/nexus` — see what other groups have found\n"
        )
    await _mc_send(context.bot, chat_id, text)


async def cmd_oracle_hint(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/mysteryblind — spend 30 points for a blind hint nudge."""
    case = _mc_get_case()
    if not case:
        await update.message.reply_text("No active mystery."); return
    chat_id = update.message.chat_id
    inv     = _mc_get_group_inv(chat_id)

    if inv["points"] < 30:
        await update.message.reply_text(
            f"⚡ Need 30 points. You have {inv['points']}.\n"
            "Crack ciphers and examine items to earn more!"); return

    inv["points"] -= 30
    solution = case["solution"]
    chain    = solution.get("evidence_chain", [])
    # Give a vague, Socratic nudge from the evidence chain
    solved_ciphers = len(inv.get("decoded_ciphers", []))
    hint_pool = chain[:min(len(chain), solved_ciphers + 2)]
    if not hint_pool:
        hint_pool = ["Look at everything the victim said and to whom."]
    raw_hint  = random.choice(hint_pool)

    # Make it vaguer via AI
    vague = await _mc_openrouter(
        [{"role": "user",
          "content": f"Rephrase this murder mystery clue as a cryptic, Socratic nudge in 1-2 sentences. Never name suspects directly. Clue: {raw_hint}"}],
        max_tokens=80, temperature=0.7)
    if not vague:
        vague = raw_hint

    _mc_save_group_inv(inv)
    await update.message.reply_text(
        f"🔮 *ORACLE WHISPERS…*\n\n_{_safe_md(vague)}_\n\n"
        f"⚡ -30 points ({inv['points']} remaining)",
        parse_mode="Markdown")


# ══════════════════════════════════════════════════════════════════════════════
#  UTILITY FUNCTIONS
# ══════════════════════════════════════════════════════════════════════════════

def _mc_time_period() -> str:
    hour = datetime.now(_MC_IST).hour
    if 5  <= hour < 8:   return "early_morning"
    if 8  <= hour < 12:  return "morning"
    if 12 <= hour < 17:  return "afternoon"
    if 17 <= hour < 21:  return "evening"
    if 21 <= hour < 24:  return "night"
    return "late_night"

def _mc_next_time_period() -> str:
    periods = ["early_morning", "morning", "afternoon", "evening", "night", "late_night"]
    cur = _mc_time_period()
    idx = periods.index(cur) if cur in periods else 0
    return periods[(idx + 1) % len(periods)]

def _mc_get_day_number(case: Dict) -> int:
    try:
        now_ist   = datetime.now(_MC_IST)
        ws        = datetime.fromisoformat(case["week_start"]).astimezone(_MC_IST)
        return max(1, min(7, (now_ist.date() - ws.date()).days + 1))
    except Exception:
        return 1

def _mc_award_solvers(chat_id: int, prize: int):
    """Distribute prize coins to group members who interrogated suspects."""
    try:
        inv = _mc_get_group_inv(chat_id)
        participant_ids = set()
        for sid, history in inv.get("suspect_chats", {}).items():
            # history is list of {role, content} — we can't know user IDs from this
            pass
        # Fallback: award to the investigator who made the final accusation
        last_acc = inv.get("accusations_log", [])
        if last_acc:
            # We have the username from "by" field but not user_id; coins go to group pot
            pass
        # Best-effort: log prize; actual coin distribution requires tracking user IDs
        logger.info(f"[Oracle] Group {chat_id} solved — prize {prize:,} coins")
    except Exception as e:
        logger.error(f"[Oracle] Award solvers error: {e}")

async def _mc_broadcast_solve(bot, case: Dict, rank: int, winning_chat: int):
    """Broadcast a solve event to all groups — social pressure + celebration."""
    prize   = _MC_SOLVE_PRIZES.get(rank, 5000)
    ordinal = {1:"1st 🥇", 2:"2nd 🥈", 3:"3rd 🥉"}.get(rank, f"#{rank}th")
    text    = (
        f"⚡ *ORACLE CHRONICLES — SOLVE ALERT*\n"
        f"{'━'*28}\n"
        f"A Telegram group has cracked the case!\n"
        f"🏆 They are *{ordinal}* to solve *{_safe_md(case['title'])}*!\n\n"
        f"🪙 They earned *{prize:,} coins*.\n\n"
        f"🔍 The race is still on — can YOUR group solve it?\n"
        f"/mystery · /suspects · /goto"
    )
    for cid in _mc_broadcast_chats():
        if cid == winning_chat:
            continue
        try:
            await bot.send_message(cid, text, parse_mode="Markdown")
            await asyncio.sleep(0.4)
        except Exception:
            pass

# ══════════════════════════════════════════════════════════════════════════════
#  SCHEDULED JOBS
# ══════════════════════════════════════════════════════════════════════════════

async def _mc_job_start_new_mystery(context):
    """Job: generate and launch a new mystery. Runs Monday midnight IST."""
    logger.info("[Oracle] Starting new mystery week…")
    case = await _mc_generate_case()
    if not case:
        logger.error("[Oracle] Mystery generation FAILED — will retry in 1 hour")
        context.job_queue.run_once(_mc_job_start_new_mystery, when=3600,
                                   name="mystery_retry")
        return

    _mc_save_case(case)
    # Reset all group investigations for the new case
    _mc_db()["group_mystery"].delete_many({})
    # Reset Nexus
    _mc_save_nexus({"_id": "mystery_nexus", "clues": [],
                    "confirmed": [], "week": case["case_id"]})

    # Build announcement
    v    = case["victim"]
    text = (
        f"🔮 *ORACLE CHRONICLES — NEW CASE LAUNCHED*\n"
        f"{'━'*32}\n"
        f"📁 *{_safe_md(case['title'])}*\n"
        f"_{_safe_md(case['subtitle'])}_\n\n"
        f"📍 *Setting:* {_safe_md(case['setting_name'])}, {_safe_md(case['setting_era'])}\n"
        f"_{_safe_md(case['setting_description'])}_\n\n"
        f"💀 *VICTIM:* {_safe_md(v['name'])}, {v['age']}, {_safe_md(v['occupation'])}\n"
        f"🕰️ Found dead at *{v['time_of_death']}*, cause: *{_safe_md(v['cause_of_death'])}*\n\n"
        f"🗣️ *Last known words:*\n"
        f"_\"{_safe_md(v['last_words'])}\"_\n\n"
        f"🏆 *Prizes:* 1st solve → 80,000🪙 · 2nd → 45,000🪙 · 3rd → 25,000🪙\n"
        f"⏰ *You have 7 days. New clues drop daily. Cross-group Nexus live now.*\n\n"
        f"Start investigating:\n"
        f"`/mystery` — case overview\n"
        f"`/suspects` — persons of interest\n"
        f"`/goto <location>` — explore the scene"
    )

    # Broadcast to all known groups
    crime_scene_loc = next(
        (l for l in case["locations"] if l.get("is_crime_scene")), None)

    for cid in _mc_broadcast_chats():
        try:
            if crime_scene_loc:
                await _mc_send_location_photo(
                    context.bot, cid, crime_scene_loc,
                    caption="🚨 A murder has been committed.")
            await _mc_send(context.bot, cid, text)
            await asyncio.sleep(0.5)
        except Exception as e:
            logger.warning(f"[Oracle] Broadcast to {cid} failed: {e}")


async def _mc_job_daily_drop(context):
    """Job: send today's document drop to all groups. Runs daily 8am IST."""
    case = _mc_get_case()
    if not case:
        return

    day_num  = _mc_get_day_number(case)
    drop     = case["daily_drops"].get(str(day_num))
    if not drop:
        return

    formatted = _mc_format_drop(drop)
    cipher_label = _MC_CIPHER_LABELS.get(drop.get("cipher_type", ""), "🔐 Cipher")

    header = (
        f"📋 *DAY {day_num} — ORACLE EVIDENCE DROP*\n"
        f"{'━'*28}\n"
        f"Today's document: *{drop['type'].replace('_',' ').title()}*\n"
        f"Today's cipher: {cipher_label}\n"
        f"{'━'*28}\n\n"
    )

    for cid in _mc_broadcast_chats():
        try:
            await _mc_send(context.bot, cid, header + formatted)
            await asyncio.sleep(0.5)
        except Exception as e:
            logger.warning(f"[Oracle] Daily drop to {cid} failed: {e}")


async def _mc_job_realtime_update(context):
    """Job: send a real-time development every 4 hours."""
    case = _mc_get_case()
    if not case:
        return

    # Calculate which update to send based on hours since week start
    try:
        now_ist = datetime.now(_MC_IST)
        ws      = datetime.fromisoformat(case["week_start"]).astimezone(_MC_IST)
        hours   = (now_ist - ws).total_seconds() / 3600
    except Exception:
        hours = 0

    updates = case.get("realtime_updates", [])
    if not updates:
        return

    # Pick the update whose offset_hours is closest to now without going over
    eligible = [u for u in updates if u.get("offset_hours", 9999) <= hours]
    if not eligible:
        return
    update_to_send = max(eligible, key=lambda u: u["offset_hours"])

    # Check if already sent this one
    sent_offsets = case.get("sent_update_offsets", [])
    offset = update_to_send["offset_hours"]
    if offset in sent_offsets:
        return

    case.setdefault("sent_update_offsets", []).append(offset)
    _mc_save_case(case)

    tag = "🚨 *BREAKING*" if not update_to_send.get("is_red_herring") else "📡 *UNVERIFIED REPORT*"
    text = (
        f"⚡ *ORACLE — LIVE UPDATE*\n"
        f"{'━'*26}\n"
        f"{tag}: {_safe_md(update_to_send['title'])}\n\n"
        f"{_safe_md(update_to_send['body'])}\n\n"
        f"🎯 *This enables:* _{_safe_md(update_to_send.get('unlocks','Continue investigating.'))}_\n"
        f"/mystery · /interrogate · /examine"
    )

    for cid in _mc_broadcast_chats():
        try:
            await _mc_send(context.bot, cid, text)
            await asyncio.sleep(0.4)
        except Exception as e:
            logger.warning(f"[Oracle] Realtime update to {cid} failed: {e}")


async def _mc_job_nexus_digest(context):
    """Job: Thursday 8am IST — send Nexus digest with confirmed facts."""
    case = _mc_get_case()
    if not case:
        return

    nx        = _mc_get_nexus()
    confirmed = [c for c in nx.get("clues", []) if len(c.get("confirmed_by", [])) >= 3]
    if not confirmed:
        return

    lines = [
        f"🌐 *NEXUS DIGEST — CONFIRMED INTELLIGENCE*\n"
        f"{'━'*30}\n"
        f"The following clues have been independently verified\n"
        f"by 3+ investigating groups:\n"
    ]
    for c in confirmed:
        lines.append(f"✅ _{_safe_md(c['clue'])}_")

    lines.append(f"\n_{len(confirmed)} confirmed facts. Use them wisely._\n`/nexus view` for all intel.")
    text = "\n".join(lines)

    for cid in _mc_broadcast_chats():
        try:
            await _mc_send(context.bot, cid, text)
            await asyncio.sleep(0.4)
        except Exception as e:
            logger.warning(f"[Oracle] Nexus digest to {cid} failed: {e}")


async def _mc_job_closing_warning(context):
    """Job: Sunday noon IST — 12-hour warning before case closes."""
    case = _mc_get_case()
    if not case:
        return
    unsolved_count = sum(
        1 for inv in _mc_get_all_group_invs() if not inv.get("solved"))
    if unsolved_count == 0:
        return

    text = (
        f"⏰ *ORACLE CHRONICLES — 12 HOURS REMAINING*\n"
        f"{'━'*28}\n"
        f"📁 *{_safe_md(case['title'])}*\n\n"
        f"*{unsolved_count}* groups haven't solved the case yet.\n"
        f"The case file closes at midnight IST tonight.\n\n"
        f"🔐 Have you decoded all 7 ciphers?\n"
        f"🕵️ Have you interrogated every suspect at full stress?\n"
        f"🌐 Have you checked the Nexus board?\n\n"
        f"Time is running out. `/accuse <name> <weapon> <location> <motive>`"
    )
    for cid in _mc_broadcast_chats():
        try:
            await _mc_send(context.bot, cid, text)
            await asyncio.sleep(0.4)
        except Exception as e:
            logger.warning(f"[Oracle] Closing warning to {cid} failed: {e}")


# ══════════════════════════════════════════════════════════════════════════════
#  SETUP — call this from main()
# ══════════════════════════════════════════════════════════════════════════════

def add_mystery_handlers(application):
    """Register all Oracle Chronicles handlers and scheduled jobs.
    Call this inside main() after building the application."""

    # Commands
    mystery_cmds = [
        ("mystery",       cmd_mystery),
        ("suspects",      cmd_suspects),
        ("goto",          cmd_goto),
        ("examine",       cmd_examine),
        ("interrogate",   cmd_interrogate),
        ("evidence",      cmd_evidence),
        ("timeline",      cmd_timeline),
        ("decode",        cmd_decode),
        ("accuse",        cmd_accuse),
        ("nexus",         cmd_nexus),
        ("mysteryboard",  cmd_mysteryboard),
        ("mystatus",      cmd_mystatus),
        ("casefile",      cmd_casefile),
        ("stakeout",      cmd_stakeout),
        ("oraclehint",    cmd_oracle_hint),
        ("weeklyreport",  cmd_weeklyreport),
    ]
    for cmd, fn in mystery_cmds:
        application.add_handler(
            CommandHandler(cmd, fn, filters=filters.UpdateType.MESSAGE))

    # Scheduling — all times in IST (UTC+5:30)
    IST = timezone(timedelta(hours=5, minutes=30))
    jq  = application.job_queue

    def _next_occurrence(weekday: int, hour: int, minute: int = 0) -> float:
        """Seconds until the next occurrence of (weekday, hour:minute) in IST."""
        now  = datetime.now(IST)
        days = (weekday - now.weekday()) % 7
        target = now.replace(hour=hour, minute=minute, second=0, microsecond=0) + timedelta(days=days)
        if target <= now:
            target += timedelta(days=7)
        return (target - now).total_seconds()

    # 1. New mystery — every Monday 00:00 IST
    jq.run_repeating(
        _mc_job_start_new_mystery,
        interval=7 * 24 * 3600,
        first=_next_occurrence(0, 0, 0),
        name="oracle_new_mystery"
    )

    # 2. Daily drop — every day 08:00 IST
    now_ist = datetime.now(IST)
    secs_to_8am = (_next_occurrence(now_ist.weekday(), 8, 0) % (7 * 24 * 3600))
    jq.run_repeating(
        _mc_job_daily_drop,
        interval=24 * 3600,
        first=max(30, secs_to_8am),
        name="oracle_daily_drop"
    )

    # 3. Real-time updates — every 4 hours
    jq.run_repeating(
        _mc_job_realtime_update,
        interval=4 * 3600,
        first=60,
        name="oracle_realtime"
    )

    # 4. Nexus digest — every Thursday 08:00 IST
    jq.run_repeating(
        _mc_job_nexus_digest,
        interval=7 * 24 * 3600,
        first=_next_occurrence(3, 8, 0),  # 3 = Thursday
        name="oracle_nexus_digest"
    )

    # 5. Closing warning — every Sunday 12:00 IST
    jq.run_repeating(
        _mc_job_closing_warning,
        interval=7 * 24 * 3600,
        first=_next_occurrence(6, 12, 0),  # 6 = Sunday
        name="oracle_closing_warning"
    )

    # Memory cleanup — every 20 minutes
    jq.run_repeating(_job_memory_cleanup, interval=20*60, first=60, name="mem_cleanup")
    # Weekly Group Personality Report — Sunday 8pm IST
    jq.run_repeating(_job_weekly_report, interval=7*24*3600,
                     first=_next_occurrence(6, 20, 0), name="weekly_report")
    jq.run_repeating(_job_vision_health_check, interval=15*60, first=30, name="vision_health")
    jq.run_repeating(_job_streak_nudge, interval=24*3600,
                     first=max(30, _next_occurrence(datetime.now(IST).weekday(), 19, 0) % (24*3600)),
                     name="streak_nudge")
    jq.run_repeating(_job_mystery_hype, interval=7*24*3600,
                     first=_next_occurrence(6, 18, 0), name="mystery_hype")
    logger.info("✅ Oracle Chronicles — all handlers and jobs registered.")



# ══════════════════════════════════════════════════════════════════════════════
#  PERIODIC MEMORY CLEANUP — runs every 20 minutes via job_queue
#  Keeps RAM low by evicting idle chat histories, stale game states,
#  and users who haven't been touched in a while (they're safe in DB).
# ══════════════════════════════════════════════════════════════════════════════
import gc as _gc

_USER_LAST_ACCESS: dict = {}  # uid -> float timestamp — set in get_user()

async def _job_memory_cleanup(context):
    """Evict idle in-memory data to keep RAM under control."""
    now = time.time()
    cleared = []

    # 1. Chat histories idle for >60 min
    idle_chats = [cid for cid, msgs in list(_chat_histories.items())
                  if not msgs or (now - _chat_last_msg_time.get(cid, datetime.now(_IST)).timestamp()) > 3600]
    for cid in idle_chats:
        _chat_histories.pop(cid, None)
        _chat_last_msg_time.pop(cid, None)
        _chat_moods.pop(cid, None)
    if idle_chats: cleared.append(f"{len(idle_chats)} idle chat histories")

    # 2. Cap wordchain cache at 300 entries
    if len(_wordchain_word_cache) > 300:
        overflow = len(_wordchain_word_cache) - 300
        for k in list(_wordchain_word_cache.keys())[:overflow]:
            _wordchain_word_cache.pop(k, None)
        cleared.append(f"wordchain cache trimmed by {overflow}")

    # 3. Evict stale game dicts (no in-progress games leak memory)
    for gdict in [_ttt_games, _hangman_games, _guessnum_games, _rps_games,
                  _bj_games, _quiz_battles, _riddle_answers, _fastmath_games,
                  _lastcall_games, _echoes_games, _blackout_games, _au_games]:
        gdict.clear()

    # 4. AI reply cooldown dicts — clear entries older than 10 min
    cutoff_ai = now - 600
    for d in [_ai_reply_last, _gn_reply_last]:
        old = [k for k, v in list(d.items())
               if (now - v.timestamp()) > 600]
        for k in old: d.pop(k, None)

    # 5. User cache eviction — remove users not accessed in 25 min
    #    (they are safe in SQLite; they'll reload on next access)
    if _cached_data is not None:
        users = _cached_data.get("users", {})
        dirty = getattr(users, "dirty", set())
        cutoff_u = now - 1500  # 25 minutes
        to_evict = [uid for uid, t in list(_USER_LAST_ACCESS.items())
                    if t < cutoff_u and uid not in dirty]
        for uid in to_evict:
            users.pop(uid, None)
            _USER_LAST_ACCESS.pop(uid, None)
        if to_evict: cleared.append(f"{len(to_evict)} inactive user caches")

    # 6. Force GC
    collected = _gc.collect()

    if cleared:
        logger.info(f"[MemClean] {' | '.join(cleared)} | GC collected {collected}")


# ══════════════════════════════════════════════════════════════════════
#  GROWTH ENGINE
# ══════════════════════════════════════════════════════════════════════

async def _job_streak_nudge(context):
    """7pm IST daily: nudge users one day from a streak milestone."""
    db = _get_db()
    milestones = {6, 13, 24, 29, 49, 99}
    today = datetime.now(_MC_IST).date().isoformat()
    nudged = 0
    for doc in db["users"].find({"daily_streak": {"$in": list(milestones)}}):
        if doc.get("last_daily") == today: continue
        try:
            await context.bot.send_message(
                int(doc["_id"]),
                f"🔥 Tumhara streak *{doc['daily_streak']} days* ka hai!\n"
                f"/daily claim karo aaj — kal milestone bonus milega! 🎁",
                parse_mode="Markdown")
            nudged += 1
            await asyncio.sleep(0.4)
        except Exception:
            pass
    if nudged: logger.info(f"[Growth] Streak nudge → {nudged} users")

async def _job_mystery_hype(context):
    """Sunday 6pm IST: hype the leaderboard for final solves."""
    case = _mc_get_case()
    if not case: return
    invs = _mc_get_all_group_invs()
    solved   = [i for i in invs if i.get("solved")]
    unsolved = [i for i in invs if not i.get("solved")]
    if not unsolved: return
    top = sorted(unsolved,
                 key=lambda x: len(x.get("evidence",[])) + len(x.get("decoded_ciphers",[])),
                 reverse=True)[:3]
    medals = ["🥇","🥈","🥉"]
    text = (f"⏰ *ORACLE — FINAL HOURS*\n"
            f"📁 *{_safe_md(case['title'])}*\n\n"
            f"✅ {len(solved)} groups solved · 🔍 {len(unsolved)} still investigating\n\n"
            + "\n".join(f"{medals[i]} Group `...{str(inv['_id'])[-4:]}` — "
                         f"{len(inv.get('evidence',[]))} clues, "
                         f"{len(inv.get('decoded_ciphers',[]))}/7 ciphers"
                         for i, inv in enumerate(top))
            + "\n\n_Midnight tonight the case closes. /accuse now!_")
    for cid in _mc_broadcast_chats():
        try:
            await context.bot.send_message(cid, text, parse_mode="Markdown")
            await asyncio.sleep(0.5)
        except Exception:
            pass


async def _job_vision_health_check(context):
    """Probe vision model every 15 min. Flips _vision_available so photo
    challenges auto-enable the moment vision comes back online."""
    global _vision_available
    import base64 as _b64, struct as _struct, zlib as _zlib

    def _make_tiny_png():
        """1×1 white RGB PNG built entirely in memory."""
        def _chunk(tag, data):
            import zlib as z
            return (_struct.pack(">I", len(data)) + tag + data
                    + _struct.pack(">I", z.crc32(tag + data) & 0xffffffff))
        return (b"\x89PNG\r\n\x1a\n"
                + _chunk(b"IHDR", _struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0))
                + _chunk(b"IDAT", _zlib.compress(b"\x00\xff\xff\xff"))
                + _chunk(b"IEND", b""))

    try:
        b64 = _b64.b64encode(_make_tiny_png()).decode()
        payload = {
            "model": GROQ_VISION_MODEL,
            "messages": [{"role": "user", "content": [
                {"type": "text",      "text": "Reply with exactly one word: white"},
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
            ]}],
            "max_completion_tokens": 5,
            "temperature": 0,
        }
        # Only qwen3 models need reasoning_effort
        if "qwen3" in GROQ_VISION_MODEL.lower():
            payload["reasoning_effort"] = "default"

        async with httpx.AsyncClient(timeout=18) as client:
            r = await client.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={"Authorization": f"Bearer {GROQ_API_KEY}",
                         "Content-Type": "application/json"},
                json=payload)

        if r.status_code == 200:
            if not _vision_available:
                logger.info("[VisionCheck] ✅ Vision restored — photo challenges re-enabled")
            _vision_available = True
            _ai_health["vision"]["ok"] = True
            _ai_health["vision"]["last_success"] = datetime.now().isoformat()
        else:
            if _vision_available:
                logger.warning(f"[VisionCheck] ❌ Vision down (HTTP {r.status_code}) — photo challenges disabled")
            _vision_available = False
            _ai_health["vision"]["ok"] = False
            _ai_health["vision"]["last_error"] = f"HTTP {r.status_code}: {r.text[:80]}"

    except Exception as e:
        if _vision_available:
            logger.warning(f"[VisionCheck] ❌ Vision probe failed: {e}")
        _vision_available = False
        _ai_health["vision"]["ok"] = False



# ══════════════════════════════════════════════════════════════════════════════
#  📊 WEEKLY GROUP PERSONALITY REPORT
#  Every Sunday 8pm IST Aira analyses the week's activity in each group and
#  posts a shareable personality breakdown — vibes, member archetypes, iconic
#  moments. No message content stored — only counters and anonymised metadata.
# ══════════════════════════════════════════════════════════════════════════════

def _current_week_key() -> str:
    """ISO week string like '2026-W36'."""
    n = datetime.now(_MC_IST)
    return f"{n.year}-W{n.isocalendar()[1]:02d}"

def _get_week_stats(chat_id: int) -> dict:
    global _REPORT_CURRENT_WEEK
    wk = _current_week_key()
    if _REPORT_CURRENT_WEEK != wk:
        # New week — reset all stats
        _group_week_stats.clear()
        _REPORT_CURRENT_WEEK = wk
    if chat_id not in _group_week_stats:
        _group_week_stats[chat_id] = {
            "week":         wk,
            "total_msgs":   0,
            "members":      {},   # uid -> {name, msgs, late_night, short, long, q_marks, exclaims, emoji_count}
            "peak_hour":    {},   # hour -> count
            "reply_chains": 0,   # rapid reply bursts (chaos indicator)
            "stickers":     0,
            "photos":       0,
            "last_msg_uid": None,
            "last_msg_ts":  None,
        }
    return _group_week_stats[chat_id]

def _collect_group_stat(chat_id: int, user, message):
    """Called on every group message. Collects metadata — NO message content stored."""
    try:
        stats = _get_week_stats(chat_id)
        uid   = str(user.id)
        name  = f"@{user.username}" if user.username else (user.full_name or "?")[:18]
        now   = datetime.now(_MC_IST)
        hour  = now.hour
        txt   = message.text or message.caption or ""

        stats["total_msgs"] += 1
        stats["peak_hour"][str(hour)] = stats["peak_hour"].get(str(hour), 0) + 1

        if message.sticker: stats["stickers"] += 1
        if message.photo:   stats["photos"]   += 1

        # Rapid reply chain — if same chat had a message < 8s ago from different user
        last_ts = stats.get("last_msg_ts")
        last_uid = stats.get("last_msg_uid")
        if last_ts and last_uid and last_uid != uid:
            try:
                if (now - datetime.fromisoformat(last_ts)).total_seconds() < 8:
                    stats["reply_chains"] = stats.get("reply_chains", 0) + 1
            except Exception:
                pass
        stats["last_msg_uid"] = uid
        stats["last_msg_ts"]  = now.isoformat()

        # Per-member stats
        m = stats["members"].setdefault(uid, {
            "name": name, "msgs": 0, "late_night": 0, "short": 0,
            "long": 0, "q_marks": 0, "exclaims": 0, "emoji_count": 0,
        })
        m["name"]  = name  # keep fresh
        m["msgs"] += 1
        if hour >= 23 or hour < 4:
            m["late_night"] += 1
        if txt:
            m["short"]      += 1 if len(txt) < 15 else 0
            m["long"]       += 1 if len(txt) > 100 else 0
            m["q_marks"]    += txt.count("?")
            m["exclaims"]   += txt.count("!")
            # Count emoji (simple unicode range check)
            m["emoji_count"] += sum(1 for ch in txt
                                    if ord(ch) > 127 and not ch.isalpha())
    except Exception:
        pass  # never let stat collection crash the bot


_VIBE_POOL = [
    ("🌋 Chaotic Good",        "yahan sab ek doosre pe chhaa jaate hain — pure energy"),
    ("🧘 Zen Masters",         "surprisingly chill. too chill. suspicious level chill"),
    ("🎭 Drama Academy",       "har baat ka ek natak — Oscar nominations pending"),
    ("🔬 Overthink Tank",      "simple sawaal ka 40-message analysis. intellectuals."),
    ("🌙 Night Owls Anonymous","asli life 11pm ke baad shuru hoti hai is group mein"),
    ("🎲 Chaotic Neutral",     "koi pattern nahi, koi rules nahi, bas vibes"),
    ("🕵️ Mystery Inc.",        "baat kam karte hain, observe zyada — ya ghost hain"),
    ("🏆 Competitive Souls",   "har cheez mein ek-doosre se aage nikalte hain"),
    ("💬 Certified Yappers",   "baat band karna is group ko aata hi nahi"),
    ("🌀 Doomscrollers United","2am pe active, 10am pe missing"),
]

_ARCHETYPES = [
    ("👑 The Main Character",   lambda m: m["msgs"]),
    ("🌑 The Lurker",           lambda m: -m["msgs"]),
    ("🌙 The Night Owl",        lambda m: m["late_night"]),
    ("❓ The Questioner",       lambda m: m["q_marks"]),
    ("📖 The Essayist",         lambda m: m["long"]),
    ("⚡ The One-Liner",        lambda m: m["short"]),
    ("🎭 The Drama Queen",      lambda m: m["exclaims"]),
    ("😂 The Emoji Lord",       lambda m: m["emoji_count"]),
]

async def _generate_report(chat_id: int, bot) -> str:
    """Build the weekly report string using AI for the vibe narrative."""
    stats = _group_week_stats.get(chat_id)
    if not stats or stats["total_msgs"] < 10:
        return ""

    members = stats["members"]
    if not members:
        return ""

    # Sort members by message count
    ranked = sorted(members.values(), key=lambda m: m["msgs"], reverse=True)
    top3   = ranked[:3]

    # Peak hour label
    ph_hour = max(stats["peak_hour"], key=stats["peak_hour"].get, default="?")
    try:
        ph_int = int(ph_hour)
        peak_label = (f"{ph_int}am" if ph_int < 12
                      else ("12pm" if ph_int == 12 else f"{ph_int-12}pm"))
    except Exception:
        peak_label = "unknown"

    # Vibe score heuristics
    chaos_score  = min(100, stats["reply_chains"] * 2)
    night_score  = sum(m["late_night"] for m in members.values())
    drama_score  = sum(m["exclaims"]   for m in members.values())
    yap_score    = sum(m["long"]       for m in members.values())
    silent_score = sum(1 for m in members.values() if m["msgs"] <= 2)

    # Pick vibe
    vibe_scores = [
        chaos_score,   drama_score, drama_score,
        yap_score,     night_score, chaos_score + drama_score,
        silent_score * 10, yap_score, yap_score, night_score,
    ]
    vibe_name, vibe_desc = _VIBE_POOL[vibe_scores.index(max(vibe_scores)) % len(_VIBE_POOL)]

    # Vibe percentages (4 categories, total = 100%)
    total = chaos_score + night_score + drama_score + yap_score + 1
    pcts  = {
        "🌪️ Chaotic Energy": chaos_score,
        "🌙 Night Mode":      night_score,
        "🎭 Drama Potential": drama_score,
        "💬 Yapability":      yap_score,
    }
    scale = 100 / sum(pcts.values()) if sum(pcts.values()) > 0 else 1
    pcts  = {k: max(5, int(v * scale)) for k, v in pcts.items()}
    # Normalise to 100
    diff  = 100 - sum(pcts.values())
    first_key = next(iter(pcts))
    pcts[first_key] += diff

    # Assign archetypes to top members (no repeats)
    used_types = set()
    titles = {}
    for member in ranked:
        uid = next((k for k, v in members.items() if v is member), None)
        if uid is None: continue
        for title, scorer in _ARCHETYPES:
            if title not in used_types:
                used_types.add(title)
                titles[uid] = title
                break

    # AI-generated one-paragraph narrative (short, punchy, Hinglish)
    stats_summary = (
        f"Group had {stats['total_msgs']} messages this week. "
        f"Most active hour: {peak_label}. "
        f"Chaos events (rapid reply bursts): {stats['reply_chains']}. "
        f"Stickers sent: {stats['stickers']}. Photos: {stats['photos']}. "
        f"Top member: {top3[0]['name']} with {top3[0]['msgs']} messages. "
        f"Group vibe: {vibe_name}."
    )
    ai_prompt = (
        f"You are Aira, writing a funny weekly group report for a Telegram group. "
        f"Write EXACTLY 2 punchy sentences (Hinglish ok) summarising this group's week. "
        f"Be witty, specific, slightly roast-y but affectionate. "
        f"Stats: {stats_summary} "
        f"Do NOT mention 'AI', do NOT use emojis in the sentences themselves. "
        f"Output only the 2 sentences, nothing else."
    )
    narrative = await _mc_openrouter(
        [{"role": "user", "content": ai_prompt}],
        max_tokens=80, temperature=0.9)
    if not narrative:
        narrative = f"Is hafte ka vibe: *{vibe_name}*. Log kuch bhi thhe — ek cheez sahi thhi, boring nahi thhe."

    # Build the message
    week_label = stats["week"]
    lines = [
        f"📊 *AIRA WEEKLY REPORT*",
        f"┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄",
        f"Week *{week_label}* · *{stats['total_msgs']}* messages · peak at *{peak_label}*",
        f"",
        f"✨ *Group Personality: {vibe_name}*",
        f"_{_safe_md(vibe_desc)}_",
        f"",
        f"*This week:*",
        f"_{_safe_md(narrative.strip())}_",
        f"",
        f"*📈 Vibe Breakdown:*",
    ]
    for label, pct in pcts.items():
        bar = "█" * (pct // 10) + "░" * (10 - pct // 10)
        lines.append(f"`[{bar}]` {pct}% {label}")

    lines += ["", "*🏅 Member Archetypes:*"]
    for uid, title in list(titles.items())[:5]:
        m = members[uid]
        lines.append(f"{title} — {_safe_md(m['name'])} _{m['msgs']} msgs_")
    if len(members) > 5:
        remaining = sorted(
            [m for uid, m in members.items() if uid not in titles],
            key=lambda x: x["msgs"], reverse=True)[:3]
        for m in remaining:
            lines.append(f"🙂 *{_safe_md(m['name'])}* — {m['msgs']} msgs")

    lines += [
        "",
        f"🔥 Chaos events: *{stats['reply_chains']}* · "
        f"Stickers: *{stats['stickers']}* · Photos: *{stats['photos']}*",
        "",
        "_Screenshot karo aur share karo — dosto ko batao tumhara group kitna pagal hai 😂_",
    ]
    return "\n".join(lines)


async def _job_weekly_report(context):
    """Sunday 8pm IST: generate and post the weekly personality report."""
    groups = _mc_broadcast_chats()
    for cid in groups:
        try:
            report = await _generate_report(cid, context.bot)
            if not report:
                continue
            # Add share button
            _bun    = _CACHED_BOT_USERNAME or "AiraBot"
            add_url = f"https://t.me/{_bun}?startgroup=true"
            share_text = quote("Aira just roasted our group with a personality report 😂 Add her:", safe='')
            share_url   = f"https://t.me/share/url?url={quote(add_url, safe='')}&text={share_text}"
            kb = InlineKeyboardMarkup([[
                InlineKeyboardButton("📤 Share Report", url=share_url),
                InlineKeyboardButton("➕ Add Aira to Group", url=add_url),
            ]])
            await context.bot.send_message(
                cid, report, parse_mode="Markdown", reply_markup=kb)
            await asyncio.sleep(0.8)
        except Exception as e:
            logger.warning(f"[WeeklyReport] {cid}: {e}")

    # Reset stats for the new week
    _group_week_stats.clear()
    logger.info(f"[WeeklyReport] Reports sent to {len(groups)} groups")


async def cmd_weeklyreport(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/weeklyreport — preview your group's current-week personality report."""
    chat_id = update.message.chat_id
    if update.message.chat.type not in ("group", "supergroup"):
        await update.message.reply_text("❌ This command only works in groups!")
        return
    thinking = await update.message.reply_text("📊 Aira is reading your group's energy…")
    report   = await _generate_report(chat_id, context.bot)
    try:
        await thinking.delete()
    except Exception:
        pass
    if not report:
        await update.message.reply_text(
            "📊 *Not enough data yet!*\n\n"
            "_Aira needs at least 10 messages from this week to generate a report.\n"
            "Keep chatting — the full report drops every Sunday at 8pm!_",
            parse_mode="Markdown")
        return
    await _mc_send(context.bot, chat_id, report)



def main():
    keep_alive()
    # Startup crash seen in production: `telegram.error.TimedOut` on the very
    # first get_me() call, before run_polling's own internal retry loop is
    # even running — the default httpx timeouts (5s connect / 5s read) are
    # too tight for a free-tier VM's network right after boot (DNS/network
    # can still be settling even though systemd waits for
    # network-online.target). Widening these gives slow/flaky connections
    # room to succeed instead of crashing the whole process on the first hiccup.
    application = (
        Application.builder()
        .token(BOT_TOKEN)
        .connect_timeout(20)
        .read_timeout(20)
        .get_updates_connect_timeout(20)
        .get_updates_read_timeout(40)
        .build()
    )
    _setup_lottery_schedule(application)
    add_mystery_handlers(application)
    # Re-schedule autohunt for all users who had it running before a restart.
    # Free-tier hosts (Render, Railway, etc.) restart the bot regularly, which
    # clears the in-memory job queue. Without this, auto_hunt=True in the DB
    # but no job fires — so autohunt silently stops on every restart.
    _reschedule_active_autohunts(application)
    _reschedule_active_pets(application)
    _au_restore_games(application)

    handlers = [
        ("start", cmd_start), ("help", cmd_help), ("manual", cmd_manual), ("challenge", cmd_challenge),
        ("wallet", cmd_wallet), ("stats", cmd_stats), ("leaderboard", cmd_leaderboard),
        ("invite", cmd_invite), ("refer", cmd_invite), ("viral", cmd_viral), ("invitestats", cmd_viral),
        ("chatid", cmd_chatid),
        ("daily", cmd_daily), ("give", cmd_give), ("streak", cmd_streak),
        ("badges", cmd_badges), ("shop", cmd_shop), ("settitle", cmd_settitle),
        ("pinit", cmd_pinit), ("skipit", cmd_skipit), ("hint", cmd_hint),
        ("hunt", cmd_hunt), ("zoo", cmd_zoo), ("owoprofile", cmd_owoprofile),
        ("adopt", cmd_adopt), ("mypet", cmd_mypet), ("pet", cmd_mypet), ("releasepet", cmd_releasepet),
        ("autohunt", cmd_autohunt), ("battle", cmd_battle),
        ("sell", cmd_sell), ("gemshop", cmd_gemshop),
        ("evolve", cmd_evolve), ("upgradeweapon", cmd_upgradeweapon),
        ("traitor", cmd_traitor), ("togglechallenge", cmd_toggle_challenge),
        ("topanimals", cmd_topanimals), ("trade", cmd_trade),
        ("cf", cmd_cf), ("s", cmd_slots), ("dice", cmd_dice),
        ("ask", cmd_ask), ("pomodoro", cmd_pomodoro),
        ("ban", cmd_ban), ("unban", cmd_unban), ("kick", cmd_kick),
        ("timeout", cmd_timeout), ("untimeout", cmd_untimeout),
        ("purge", cmd_purge), ("warn", cmd_warn), ("warns", cmd_warns),
        ("clearwarns", cmd_clearwarns), ("setwelcome", cmd_setwelcome),
        ("setbye", cmd_setbye), ("forgewar", cmd_forgewar),
        ("setteam", cmd_setteam), ("inventory", cmd_inventory),
        ("equipweapon", cmd_equipweapon), ("pvp", cmd_pvp),
        ("tradeitem", cmd_tradeitem), ("auction", cmd_auction),
        ("pray", cmd_pray), ("tnd", cmd_tnd),
        ("truth", cmd_truth), ("dare", cmd_dare),
        ("checkuserbase", cmd_checkuserbase),
        ("lottery", cmd_lottery),
        # new mini-games
        ("ttt", cmd_ttt), ("hangman", cmd_hangman), ("guessnumber", cmd_guessnumber),
        ("wordchain", cmd_wordchain), ("rps", cmd_rps), ("blackjack", cmd_blackjack),
        ("quizbattle", cmd_quizbattle),
        ("fastmath", cmd_fastmath), ("wolf", cmd_wolf),
        # 15 new moderation commands
        ("slowmode", cmd_slowmode), ("lock", cmd_lock), ("unlock", cmd_unlock),
        ("promote", cmd_promote), ("demote", cmd_demote), ("report", cmd_report),
        ("adminlist", cmd_adminlist), ("userinfo", cmd_userinfo), ("rules", cmd_rules),
        ("setrules", cmd_setrules), ("antispam", cmd_antispam), ("tempban", cmd_tempban),
        ("unpin", cmd_unpin), ("cleanbot", cmd_cleanbot), ("announce", cmd_announce),
        ("approve", cmd_approve), ("unapprove", cmd_unapprove), ("approvedlist", cmd_approvedlist),
        ("amongus", cmd_amongus),
        ("crate", cmd_open_crate),
        ("blackout", cmd_blackout),
        ("lastcall", cmd_lastcall),
        ("echoes", cmd_echoes),
        
        # new fun commands
        ("8ball", cmd_8ball), ("ship", cmd_ship), ("fact", cmd_fact),
        ("roast", cmd_roast), ("compliment", cmd_compliment), ("mood", cmd_mood),
        ("riddle", cmd_riddle), ("joke", cmd_joke), ("wyr", cmd_wyr), ("remindme", cmd_remindme),
        ("aistatus", cmd_aistatus),
        ("latency", cmd_latency), ("reportbug", cmd_reportbug),
    ]
    for cmd, fn in handlers:
        # filters=filters.UpdateType.MESSAGE restricts this to fresh messages
        # only — CommandHandler listens to edited messages by default, and
        # an edited message has update.message == None (the Message lives in
        # update.edited_message instead), which crashed every handler that
        # does `update.message.xxx` (see the /ban AttributeError crash).
        application.add_handler(CommandHandler(cmd, _with_usage_tracking(cmd, fn), filters=filters.UpdateType.MESSAGE))

    # Callback query handlers
    application.add_handler(CallbackQueryHandler(handle_shop_purchase, pattern="^buy_"))
    application.add_handler(CallbackQueryHandler(handle_crate_shop_purchase, pattern="^buycrate_|^shop_"))
    application.add_handler(CallbackQueryHandler(handle_leaderboard_tab, pattern="^lb_"))
    application.add_handler(CallbackQueryHandler(handle_gem_purchase, pattern="^gbuy_"))
    application.add_handler(CallbackQueryHandler(handle_help_button, pattern="^help_"))
    application.add_handler(CallbackQueryHandler(handle_profile_nav, pattern="^prof_"))
    application.add_handler(CallbackQueryHandler(handle_invite_nudge, pattern="^invite_nudge$"))
    application.add_handler(CallbackQueryHandler(handle_hunt_action, pattern="^hunt_"))
    application.add_handler(CallbackQueryHandler(handle_pet_action, pattern="^pet_"))
    application.add_handler(CallbackQueryHandler(handle_upgrade_confirm, pattern="^upgrade_confirm$"))
    application.add_handler(CallbackQueryHandler(handle_punishment_confirm, pattern="^padm_"))
    application.add_handler(CallbackQueryHandler(handle_bug_report_decision, pattern="^bug_"))
    application.add_handler(CallbackQueryHandler(handle_riddle_reveal, pattern="^riddle_reveal$"))
    application.add_handler(PollAnswerHandler(handle_traitor_vote))
    application.add_handler(CommandHandler("announcetoall", cmd_announcetoall, filters=filters.UpdateType.MESSAGE))
    application.add_handler(CommandHandler("sendmessage", cmd_sendmessage, filters=filters.UpdateType.MESSAGE))
    application.add_handler(CommandHandler("makeredeemcodeforall", cmd_makeredeemcodeforall, filters=filters.UpdateType.MESSAGE))
    application.add_handler(CommandHandler("transferhardall", cmd_transferhardall, filters=filters.UpdateType.MESSAGE))
    application.add_handler(CallbackQueryHandler(handle_hard_transfer_confirm, pattern="^hardxfer_"))
    application.add_handler(CallbackQueryHandler(handle_trade, pattern="^tacpt_|^tdecl_"))
    application.add_handler(CallbackQueryHandler(handle_pvp, pattern="^pvpacpt_|^pvpdecl_"))
    application.add_handler(CallbackQueryHandler(handle_item_trade, pattern="^tiacpt_|^tidecl_"))
    application.add_handler(CallbackQueryHandler(handle_tnd_choice, pattern="^tnd_(truth|dare|wyr)_"))
    application.add_handler(CallbackQueryHandler(handle_tnd_next, pattern="^tnd_next_"))
    application.add_handler(CallbackQueryHandler(handle_ttt_move, pattern="^ttt_"))
    application.add_handler(CallbackQueryHandler(handle_rps, pattern="^rps_"))
    application.add_handler(CallbackQueryHandler(handle_blackjack, pattern="^bj_"))

    # Among Us
    application.add_handler(CallbackQueryHandler(handle_au_join, pattern="^aujoin_"))
    application.add_handler(CallbackQueryHandler(handle_au_task, pattern="^autask_"))
    application.add_handler(CallbackQueryHandler(handle_au_night_action, pattern="^aunight"))
    application.add_handler(CallbackQueryHandler(handle_au_fix, pattern="^aufix_"))
    application.add_handler(CallbackQueryHandler(handle_au_vote, pattern="^auvote_"))

    # Member join/leave
    application.add_handler(ChatMemberHandler(handle_member_update, ChatMemberHandler.CHAT_MEMBER))

    # Global error handler — logs + DMs the owner on any unhandled exception
    # anywhere (handlers or jobs), instead of failures vanishing silently.
    application.add_error_handler(global_error_handler)

    # Message handlers (must be LAST so commands are matched first)
    application.add_handler(MessageHandler(filters.PHOTO & ~filters.COMMAND, handle_message))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info("✅ Aira v9.3: Oracle Chronicles murder mystery + BJ natural payout fixed to 1:1")
    async def _post_init(app):
        global _CACHED_BOT_USERNAME
        try:
            _CACHED_BOT_USERNAME = (await app.bot.get_me()).username
            logger.info(f"[Aira] username cached: @{_CACHED_BOT_USERNAME}")
        except Exception as e:
            logger.warning(f"Could not cache bot username: {e}")
    application.post_init = _post_init
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    # Resilience for the TimedOut-on-startup crash seen in production: if the
    # very first Telegram API call (get_me, inside application.initialize())
    # times out because the VM's network is still settling, retry in-process
    # with backoff a few times before finally letting the exception propagate
    # to systemd (Restart=always in aira-bot.service). This handles brief
    # blips fast, without waiting a full systemd restart cycle each time; a
    # sustained outage (e.g. the VM itself has no network) will still exhaust
    # these retries and correctly hand off to systemd / show up in the logs.
    _startup_attempt = 0
    _MAX_INPROCESS_RETRIES = 8
    while True:
        try:
            main()
            break  # run_polling() only returns after a clean shutdown
        except Exception as e:
            _startup_attempt += 1
            if _startup_attempt >= _MAX_INPROCESS_RETRIES:
                logger.error(
                    f"Bot crashed {_startup_attempt} times in a row ({e}) — "
                    f"giving up in-process, letting systemd restart fresh.")
                raise
            wait = min(10 * (2 ** (_startup_attempt - 1)), 300)  # 10s,20s,40s...capped at 5min
            logger.error(f"Bot crashed (attempt {_startup_attempt}/{_MAX_INPROCESS_RETRIES}): {e}. Retrying in {wait}s...")
            time.sleep(wait)
