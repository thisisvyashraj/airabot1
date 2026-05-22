"""
Aira – Telegram Study Group Bot
A gamified quiz bot with Forge Coins, streaks, leaderboard, and shop.
Now with real Telegram member tags via admin promotion (auto-demote after 24h).
"""

import logging
import random
import asyncio
import json
import os
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ChatPermissions
from telegram.error import TelegramError
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes,
)

# ─── Config ──────────────────────────────────────────────────────────────────

BOT_TOKEN = "8823107490:AAGPfcyAz4lKTzMCOENhUSOgjjO_jzRozmc"
CHALLENGE_TIMEOUT = 300
CHALLENGE_INTERVAL_MIN = 1800
CHALLENGE_INTERVAL_MAX = 5400
BASE_COINS = 10
STREAK_BONUS_PER_LEVEL = 2
DATA_FILE = "aira_data.json"
TITLE_DURATION_HOURS = 24

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ─── Question Bank ────────────────────────────────────────────────────────────

QUESTIONS = [
    {"q": "🔢 What is 15 × 13?", "a": ["195"], "hint": "15 × 10 = 150, then add 15 × 3", "coins": 10},
    {"q": "🔢 What is the square root of 144?", "a": ["12"], "hint": "Think: 12 × 12 = ?", "coins": 10},
    {"q": "🔢 Solve: 2x + 6 = 20. What is x?", "a": ["7"], "hint": "Subtract 6 from both sides first", "coins": 12},
    {"q": "🔢 What is 25% of 200?", "a": ["50"], "hint": "25% = 1/4", "coins": 8},
    {"q": "🔢 What is 7³ (7 cubed)?", "a": ["343"], "hint": "7 × 7 = 49, then multiply by 7 again", "coins": 12},
    {"q": "🔢 What is the value of π (pi) to 2 decimal places?", "a": ["3.14"], "hint": "It starts with 3.1...", "coins": 8},
    {"q": "🔢 What is the LCM of 4 and 6?", "a": ["12"], "hint": "Find the smallest number divisible by both", "coins": 10},
    {"q": "🔢 What is the HCF of 36 and 48?", "a": ["12"], "hint": "List factors of both numbers", "coins": 12},
    {"q": "🔢 If a triangle has angles 60° and 80°, what is the third angle?", "a": ["40", "40°"], "hint": "Angles in a triangle sum to 180°", "coins": 10},
    {"q": "🔢 What is 0.5 as a fraction in simplest form?", "a": ["1/2"], "hint": "Half of 1", "coins": 8},
    {"q": "🔢 Solve: 3² + 4² = ?", "a": ["25"], "hint": "This is the Pythagorean identity!", "coins": 10},
    {"q": "🔢 What is 1000 ÷ 25?", "a": ["40"], "hint": "Think of it as 1000 ÷ 25", "coins": 8},
    {"q": "🔢 What is the perimeter of a square with side 7 cm?", "a": ["28", "28 cm"], "hint": "All 4 sides are equal", "coins": 8},
    {"q": "🔢 What is 18² (18 squared)?", "a": ["324"], "hint": "Break it: (20-2)² = 400 - 80 + 4", "coins": 12},
    {"q": "🔢 Simplify: 5/10 + 3/10", "a": ["8/10", "4/5"], "hint": "Add numerators, keep denominator", "coins": 8},
    {"q": "🔬 What is the chemical formula of water?", "a": ["h2o", "H2O"], "hint": "2 Hydrogen, 1 Oxygen", "coins": 8},
    {"q": "🔬 What is the speed of light (in km/s, approximately)?", "a": ["300000", "3×10^5", "3 x 10^5"], "hint": "It's 3 followed by 5 zeros km/s", "coins": 12},
    {"q": "🔬 Which planet is known as the Red Planet?", "a": ["mars", "Mars"], "hint": "4th planet from the Sun", "coins": 8},
    {"q": "🔬 What is Newton's 2nd Law formula?", "a": ["f=ma", "F=ma", "F = ma", "f = ma"], "hint": "Force = Mass × ___", "coins": 12},
    {"q": "🔬 What is the atomic number of Carbon?", "a": ["6"], "hint": "It's in the 2nd period, group 14", "coins": 10},
    {"q": "🔬 What gas do plants absorb during photosynthesis?", "a": ["carbon dioxide", "co2", "CO2"], "hint": "It's what we breathe out", "coins": 8},
    {"q": "🔬 What is the unit of electric current?", "a": ["ampere", "amp", "A"], "hint": "Named after a French physicist", "coins": 8},
    {"q": "🔬 How many bones are in the adult human body?", "a": ["206"], "hint": "It's between 200 and 210", "coins": 10},
    {"q": "🔬 What is the chemical symbol for Gold?", "a": ["au", "Au", "AU"], "hint": "From the Latin word 'Aurum'", "coins": 8},
    {"q": "🔬 What force keeps planets in orbit around the Sun?", "a": ["gravity", "gravitational force"], "hint": "The same force that makes apples fall", "coins": 8},
    {"q": "🔬 What is the powerhouse of the cell?", "a": ["mitochondria"], "hint": "It produces ATP energy", "coins": 8},
    {"q": "🔬 What is the SI unit of energy?", "a": ["joule", "J"], "hint": "Named after James Prescott ___", "coins": 8},
    {"q": "🔬 What is the chemical formula of table salt?", "a": ["nacl", "NaCl"], "hint": "Sodium + Chloride", "coins": 10},
    {"q": "🔬 In which organ does digestion of proteins begin?", "a": ["stomach"], "hint": "It's not the mouth!", "coins": 10},
    {"q": "🔬 What is the boiling point of water in Celsius?", "a": ["100", "100°C", "100 c"], "hint": "Standard atmospheric pressure", "coins": 8},
    {"q": "🔬 What particle has a negative charge in an atom?", "a": ["electron", "electrons"], "hint": "It orbits the nucleus", "coins": 8},
    {"q": "🔬 What is the process by which water changes to vapour called?", "a": ["evaporation", "vaporization", "vaporisation"], "hint": "Happens when you boil water", "coins": 8},
]

# ─── Shop Items ───────────────────────────────────────────────────────────────

SHOP_ITEMS = {
    "custom_title": {
        "name": "👑 Custom Member Tag (1 day)",
        "desc": "Get a real Telegram member tag visible to everyone in the group for 24 hours!",
        "cost": 50,
    },
    "choose_challenge": {
        "name": "🎯 Choose Next Challenge",
        "desc": "Pick the next question that Aira will ask the group!",
        "cost": 40,
    },
    "hint_reveal": {
        "name": "💡 Hint Reveal",
        "desc": "Reveal the hint for the current active challenge!",
        "cost": 15,
    },
    "double_coins": {
        "name": "⚡ Double Coins Booster",
        "desc": "Earn 2× coins for your next win!",
        "cost": 60,
    },
    "pin_sticker": {
        "name": "📌 Pin a Message",
        "desc": "Aira will pin your chosen sticker or message in the group!",
        "cost": 80,
    },
}

# ─── Badges ───────────────────────────────────────────────────────────────────

BADGES = {
    "first_win":  ("🏅 First Blood",   "Won your first challenge!"),
    "streak_3":   ("🔥 On Fire",       "3-win streak!"),
    "streak_5":   ("🌟 Unstoppable",   "5-win streak!"),
    "wins_10":    ("💪 Veteran",       "10 total wins!"),
    "wins_25":    ("🏆 Champion",      "25 total wins!"),
    "spender":    ("🛍️ Shopaholic",   "Made your first shop purchase!"),
    "rich":       ("💰 Minted",        "Collected 500 Forge Coins!"),
}

# ─── Data Store ───────────────────────────────────────────────────────────────

def load_data() -> dict:
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    return {"users": {}, "groups": {}}

def save_data(data: dict):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)

def get_user(data: dict, user_id: int, username: str = None, full_name: str = None) -> dict:
    uid = str(user_id)
    if uid not in data["users"]:
        data["users"][uid] = {
            "username": username or "Unknown",
            "full_name": full_name or "Unknown",
            "coins": 0,
            "wins": 0,
            "streak": 0,
            "best_streak": 0,
            "badges": [],
            "title": None,
            "title_expiry": None,
            "title_chat_id": None,
            "title_purchased": False,
            "double_coins": False,
            "weekly_wins": 0,
            "last_win_date": None,
        }
    else:
        if username:
            data["users"][uid]["username"] = username
        if full_name:
            data["users"][uid]["full_name"] = full_name
    return data["users"][uid]

def get_group(data: dict, chat_id: int) -> dict:
    gid = str(chat_id)
    if gid not in data["groups"]:
        data["groups"][gid] = {
            "active_challenge": None,
            "forge_war": False,
            "forge_war_multiplier": 1,
            "pending_chooser": None,
        }
    return data["groups"][gid]

def award_badge(user: dict, badge_key: str) -> str | None:
    if badge_key not in user["badges"]:
        user["badges"].append(badge_key)
        name, desc = BADGES[badge_key]
        return f"{name} – {desc}"
    return None

def check_badges(user: dict) -> list[str]:
    new_badges = []
    checks = [
        (user["wins"] >= 1,  "first_win"),
        (user["streak"] >= 3, "streak_3"),
        (user["streak"] >= 5, "streak_5"),
        (user["wins"] >= 10,  "wins_10"),
        (user["wins"] >= 25,  "wins_25"),
        (user["coins"] >= 500, "rich"),
    ]
    for condition, key in checks:
        if condition:
            b = award_badge(user, key)
            if b:
                new_badges.append(b)
    return new_badges

def reset_weekly_if_needed(data: dict):
    now = datetime.now()
    if now.weekday() == 0:
        for uid in data["users"]:
            u = data["users"][uid]
            last = u.get("last_win_date")
            if last:
                last_dt = datetime.fromisoformat(last)
                if (now - last_dt).days >= 7:
                    u["weekly_wins"] = 0

# ─── Title / Admin Tag Logic ──────────────────────────────────────────────────

async def promote_with_title(bot, chat_id: int, user_id: int, title: str) -> bool:
    """Promote user to admin with zero permissions and set their custom title."""
    try:
        # Promote with all permissions set to False — title only
        await bot.promote_chat_member(
            chat_id=chat_id,
            user_id=user_id,
            can_manage_chat=False,
            can_delete_messages=False,
            can_manage_video_chats=False,
            can_restrict_members=False,
            can_promote_members=False,
            can_change_info=False,
            can_invite_users=False,
            can_pin_messages=False,
        )
        # Telegram requires at least 1 permission to be True for custom title to work
        # So we give can_invite_users=True (harmless) then set the title
        await bot.promote_chat_member(
            chat_id=chat_id,
            user_id=user_id,
            can_invite_users=True,
        )
        # Set the visible member tag
        title_clean = title[:16]  # Telegram limit is 16 chars for custom titles
        await bot.set_chat_administrator_custom_title(
            chat_id=chat_id,
            user_id=user_id,
            custom_title=title_clean,
        )
        return True
    except TelegramError as e:
        logger.error(f"Failed to promote user {user_id}: {e}")
        return False

async def demote_user(bot, chat_id: int, user_id: int):
    """Remove all admin permissions from user (demote back to member)."""
    try:
        await bot.promote_chat_member(
            chat_id=chat_id,
            user_id=user_id,
            can_manage_chat=False,
            can_delete_messages=False,
            can_manage_video_chats=False,
            can_restrict_members=False,
            can_promote_members=False,
            can_change_info=False,
            can_invite_users=False,
            can_pin_messages=False,
        )
    except TelegramError as e:
        logger.error(f"Failed to demote user {user_id}: {e}")

async def expire_title(context: ContextTypes.DEFAULT_TYPE):
    """Called by job queue after 24h to remove title and demote user."""
    job_data = context.job.data
    user_id = job_data["user_id"]
    chat_id = job_data["chat_id"]
    username = job_data["username"]

    data = load_data()
    u = data["users"].get(str(user_id))
    if u:
        u["title"] = None
        u["title_expiry"] = None
        u["title_chat_id"] = None
        u["title_purchased"] = False
        save_data(data)

    await demote_user(context.bot, chat_id, user_id)

    try:
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"⌛ {username}'s custom title has expired and their member tag has been removed.",
            parse_mode="Markdown",
        )
    except TelegramError:
        pass

# ─── Challenge Logic ──────────────────────────────────────────────────────────

async def post_challenge(context: ContextTypes.DEFAULT_TYPE, chat_id: int, question: dict = None):
    data = load_data()
    group = get_group(data, chat_id)

    if group["active_challenge"] is not None:
        return

    if question is None:
        question = random.choice(QUESTIONS)

    multiplier = group.get("forge_war_multiplier", 1)
    coins = question["coins"] * multiplier

    group["active_challenge"] = {
        "question": question["q"],
        "answers": [a.lower() for a in question["a"]],
        "hint": question["hint"],
        "coins": coins,
        "started_at": datetime.now().isoformat(),
        "hint_used": False,
    }
    save_data(data)

    forge_war_banner = ""
    if group.get("forge_war"):
        forge_war_banner = f"\n⚔️ *FORGE WAR ACTIVE!* Rewards are ×{multiplier}!\n"

    msg = (
        f"⚡ *NEW CHALLENGE!*{forge_war_banner}\n"
        f"{question['q']}\n\n"
        f"💰 Reward: *{coins} Forge Coins*\n"
        f"⏱️ You have 5 minutes. First correct answer wins!\n"
        f"Type your answer in the chat!"
    )
    await context.bot.send_message(chat_id=chat_id, text=msg, parse_mode="Markdown")

    context.job_queue.run_once(
        expire_challenge,
        when=CHALLENGE_TIMEOUT,
        chat_id=chat_id,
        name=f"expire_{chat_id}",
    )


async def expire_challenge(context: ContextTypes.DEFAULT_TYPE):
    chat_id = context.job.chat_id
    data = load_data()
    group = get_group(data, chat_id)

    if group["active_challenge"] is None:
        return

    q = group["active_challenge"]["question"]
    group["active_challenge"] = None
    save_data(data)

    await context.bot.send_message(
        chat_id=chat_id,
        text=f"⌛ *Time's up!* No one answered correctly.\n_{q}_\n\nBetter luck next time! 💪",
        parse_mode="Markdown",
    )


async def schedule_next_challenge(context: ContextTypes.DEFAULT_TYPE, chat_id: int):
    delay = random.randint(CHALLENGE_INTERVAL_MIN, CHALLENGE_INTERVAL_MAX)
    context.job_queue.run_once(
        lambda ctx: asyncio.ensure_future(post_challenge(ctx, chat_id)),
        when=delay,
        chat_id=chat_id,
        name=f"auto_challenge_{chat_id}",
    )

# ─── Message Handler ──────────────────────────────────────────────────────────

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    chat_id = update.message.chat_id
    user = update.message.from_user
    text = update.message.text.strip().lower()

    data = load_data()
    group = get_group(data, chat_id)
    challenge = group["active_challenge"]

    if challenge is None:
        return

    if text not in challenge["answers"]:
        return

    # Correct answer!
    group["active_challenge"] = None

    jobs = context.job_queue.get_jobs_by_name(f"expire_{chat_id}")
    for job in jobs:
        job.schedule_removal()

    u = get_user(data, user.id, user.username, user.full_name)
    coins_earned = challenge["coins"]

    today = datetime.now().date().isoformat()
    yesterday = (datetime.now().date() - timedelta(days=1)).isoformat()
    if u.get("last_win_date") == today:
        u["streak"] += 1
    elif u.get("last_win_date") == yesterday:
        u["streak"] += 1
    else:
        u["streak"] = 1
    u["last_win_date"] = today

    if u["streak"] > u.get("best_streak", 0):
        u["best_streak"] = u["streak"]

    streak_bonus = (u["streak"] - 1) * STREAK_BONUS_PER_LEVEL
    coins_earned += streak_bonus

    booster_msg = ""
    if u.get("double_coins"):
        coins_earned *= 2
        u["double_coins"] = False
        booster_msg = "\n⚡ *Double Coins Booster* activated! Coins doubled!"

    u["coins"] += coins_earned
    u["wins"] += 1
    u["weekly_wins"] = u.get("weekly_wins", 0) + 1

    new_badges = check_badges(u)
    save_data(data)

    streak_line = f"🔥 Streak: {u['streak']}x" if u["streak"] > 1 else ""
    bonus_line = f"  (+{streak_bonus} streak bonus)" if streak_bonus > 0 else ""
    title_line = f"\n👑 *{u['title']}*" if u.get("title") else ""
    name_display = f"@{user.username}" if user.username else user.full_name

    win_msg = (
        f"🎉 *{name_display}* answered correctly!{title_line}\n"
        f"💰 +{coins_earned} Forge Coins{bonus_line}{booster_msg}\n"
        f"🏦 Total: {u['coins']} coins | 🏆 Wins: {u['wins']}\n"
        f"{streak_line}"
    )

    if new_badges:
        win_msg += "\n\n🆕 *New Badges Unlocked!*\n" + "\n".join(f"  {b}" for b in new_badges)

    await update.message.reply_text(win_msg, parse_mode="Markdown")
    await schedule_next_challenge(context, chat_id)

# ─── Commands ─────────────────────────────────────────────────────────────────

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Hello! I'm *Aira*, your study group's AI challenge bot!\n\n"
        "I'll randomly post Math & Science challenges throughout the day.\n"
        "First correct answer wins *Forge Coins* 🪙\n\n"
        "📋 *Commands:*\n"
        "/challenge – Start a challenge now\n"
        "/wallet – Check your Forge Coins\n"
        "/leaderboard – Weekly top players\n"
        "/streak – Your current streak\n"
        "/shop – Spend your coins\n"
        "/badges – Your badge collection\n"
        "/forgewar – Start a Forge War event (admin)\n\n"
        "Let the games begin! ⚡",
        parse_mode="Markdown"
    )


async def cmd_challenge(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    data = load_data()
    group = get_group(data, chat_id)

    if group["active_challenge"] is not None:
        await update.message.reply_text("⚠️ A challenge is already active! Answer it first.")
        return

    save_data(data)
    await post_challenge(context, chat_id)


async def cmd_wallet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    data = load_data()
    u = get_user(data, user.id, user.username, user.full_name)
    save_data(data)

    title_line = f"\n👑 Member Tag: *{u['title']}*" if u.get("title") else ""
    booster = "⚡ Active" if u.get("double_coins") else "None"

    # Show time remaining on title
    expiry_line = ""
    if u.get("title_expiry"):
        expiry_dt = datetime.fromisoformat(u["title_expiry"])
        remaining = expiry_dt - datetime.now()
        hours_left = int(remaining.total_seconds() // 3600)
        mins_left = int((remaining.total_seconds() % 3600) // 60)
        if remaining.total_seconds() > 0:
            expiry_line = f"\n⏳ Tag expires in: *{hours_left}h {mins_left}m*"

    await update.message.reply_text(
        f"💼 *{user.full_name}'s Wallet*{title_line}{expiry_line}\n"
        f"━━━━━━━━━━━━━\n"
        f"🪙 Forge Coins: *{u['coins']}*\n"
        f"🏆 Total Wins: *{u['wins']}*\n"
        f"🔥 Current Streak: *{u['streak']}*\n"
        f"⭐ Best Streak: *{u.get('best_streak', 0)}*\n"
        f"📅 Weekly Wins: *{u.get('weekly_wins', 0)}*\n"
        f"⚡ Double Coins Booster: {booster}\n"
        f"🏅 Badges: *{len(u['badges'])}* earned",
        parse_mode="Markdown"
    )


async def cmd_leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = load_data()
    reset_weekly_if_needed(data)

    users = data["users"]
    if not users:
        await update.message.reply_text("No players yet! Use /challenge to start.")
        return

    sorted_users = sorted(
        users.items(),
        key=lambda x: x[1].get("weekly_wins", 0),
        reverse=True
    )[:10]

    medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
    lines = ["🏆 *WEEKLY LEADERBOARD*\n━━━━━━━━━━━━━"]
    for i, (uid, u) in enumerate(sorted_users):
        name = u.get("full_name") or u.get("username") or "Unknown"
        title = f" 👑 {u['title']}" if u.get("title") else ""
        lines.append(
            f"{medals[i]} {name}{title}\n"
            f"   🪙 {u['coins']} coins | 🏆 {u.get('weekly_wins', 0)} wins this week"
        )

    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


async def cmd_streak(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    data = load_data()
    u = get_user(data, user.id, user.username, user.full_name)
    save_data(data)

    fire = "🔥" * min(u["streak"], 10)
    bonus = u["streak"] * STREAK_BONUS_PER_LEVEL
    await update.message.reply_text(
        f"{fire}\n*{user.full_name}'s Streak*\n"
        f"━━━━━━━━━━━━━\n"
        f"Current Streak: *{u['streak']}* wins\n"
        f"Best Streak: *{u.get('best_streak', 0)}* wins\n"
        f"Streak Bonus: *+{bonus} coins* per win\n\n"
        f"Keep answering to grow your streak! 💪",
        parse_mode="Markdown"
    )


async def cmd_badges(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    data = load_data()
    u = get_user(data, user.id, user.username, user.full_name)
    save_data(data)

    if not u["badges"]:
        await update.message.reply_text(
            "You haven't earned any badges yet! Start winning challenges to collect them. 🏅"
        )
        return

    lines = [f"🏅 *{user.full_name}'s Badges*\n━━━━━━━━━━━━━"]
    for badge_key in u["badges"]:
        if badge_key in BADGES:
            name, desc = BADGES[badge_key]
            lines.append(f"{name}\n  _{desc}_")

    remaining = [k for k in BADGES if k not in u["badges"]]
    lines.append(f"\n🔒 *Locked ({len(remaining)}):* Keep playing to unlock more!")

    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


async def cmd_shop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    data = load_data()
    u = get_user(data, user.id, user.username, user.full_name)
    save_data(data)

    keyboard = []
    for key, item in SHOP_ITEMS.items():
        label = f"{item['name']} – {item['cost']} 🪙"
        keyboard.append([InlineKeyboardButton(label, callback_data=f"buy_{key}")])

    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        f"🛒 *FORGE SHOP*\n"
        f"━━━━━━━━━━━━━\n"
        f"Your balance: *{u['coins']} Forge Coins* 🪙\n\n"
        f"Tap an item to purchase:",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )


async def handle_shop_purchase(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user = query.from_user
    item_key = query.data.replace("buy_", "")

    if item_key not in SHOP_ITEMS:
        await query.edit_message_text("❌ Unknown item.")
        return

    data = load_data()
    u = get_user(data, user.id, user.username, user.full_name)
    item = SHOP_ITEMS[item_key]

    if u["coins"] < item["cost"]:
        await query.edit_message_text(
            f"❌ Not enough coins!\n"
            f"You need *{item['cost']}* 🪙 but have *{u['coins']}* 🪙.",
            parse_mode="Markdown"
        )
        return

    u["coins"] -= item["cost"]
    award_badge(u, "spender")

    msg = f"✅ *Purchased: {item['name']}*\n_{item['desc']}_\n\n💰 Remaining: *{u['coins']} coins*"

    if item_key == "double_coins":
        u["double_coins"] = True
        msg += "\n\n⚡ Your next win will earn DOUBLE coins!"

    elif item_key == "hint_reveal":
        chat_id = query.message.chat_id
        group = get_group(data, chat_id)
        challenge = group["active_challenge"]
        if challenge:
            msg += f"\n\n💡 *Hint for current challenge:*\n_{challenge['hint']}_"
        else:
            msg += "\n\n⚠️ No active challenge right now."

    elif item_key == "custom_title":
        u["title_purchased"] = True
        u["title_chat_id"] = query.message.chat_id
        msg += (
            "\n\n👑 Now use the command below in the group to set your member tag:\n"
            "`/settitle YourTitleHere`\n\n"
            "Max 16 characters. It will appear next to your name for 24 hours!"
        )

    elif item_key == "choose_challenge":
        chat_id = query.message.chat_id
        group = get_group(data, chat_id)
        group["pending_chooser"] = user.username or user.full_name
        msg += "\n\n🎯 Next /challenge will let you pick the question!"

    save_data(data)
    await query.edit_message_text(msg, parse_mode="Markdown")


async def cmd_settitle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    chat_id = update.message.chat_id

    if not context.args:
        await update.message.reply_text(
            "Usage: `/settitle YourTitle`\nMax 16 characters.",
            parse_mode="Markdown"
        )
        return

    title = " ".join(context.args)[:16]

    data = load_data()
    u = get_user(data, user.id, user.username, user.full_name)

    # Check if they've purchased a title
    if not u.get("title_purchased"):
        await update.message.reply_text(
            "❌ You need to purchase a *Custom Member Tag* from /shop first!",
            parse_mode="Markdown"
        )
        return

    # If they already have an active title, demote first
    if u.get("title") and u.get("title_chat_id"):
        old_chat = u["title_chat_id"]
        await demote_user(context.bot, old_chat, user.id)
        # Remove old expiry job
        old_jobs = context.job_queue.get_jobs_by_name(f"title_expire_{user.id}")
        for job in old_jobs:
            job.schedule_removal()

    # Promote with the new title
    success = await promote_with_title(context.bot, chat_id, user.id, title)

    if not success:
        # Refund the purchase
        u["title_purchased"] = False
        save_data(data)
        await update.message.reply_text(
            "❌ Failed to set your member tag.\n\n"
            "Make sure *Aira is an admin* with the *'Add Admins'* permission enabled.\n"
            "Ask your group owner to give Aira that permission, then try again.\n\n"
            "Your purchase has been refunded!",
            parse_mode="Markdown"
        )
        return

    # Save title info
    expiry = datetime.now() + timedelta(hours=TITLE_DURATION_HOURS)
    u["title"] = title
    u["title_expiry"] = expiry.isoformat()
    u["title_chat_id"] = chat_id
    u["title_purchased"] = False
    save_data(data)

    # Schedule auto-demotion after 24h
    context.job_queue.run_once(
        expire_title,
        when=TITLE_DURATION_HOURS * 3600,
        name=f"title_expire_{user.id}",
        data={
            "user_id": user.id,
            "chat_id": chat_id,
            "username": f"@{user.username}" if user.username else user.full_name,
        }
    )

    name_display = f"@{user.username}" if user.username else user.full_name
    await update.message.reply_text(
        f"👑 *{name_display}* now has the member tag: *{title}*\n"
        f"It will be visible next to their name for 24 hours!\n"
        f"_(Auto-removed after {TITLE_DURATION_HOURS}h)_",
        parse_mode="Markdown"
    )


async def cmd_forgewar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    member = await context.bot.get_chat_member(chat_id, update.message.from_user.id)
    if member.status not in ("administrator", "creator"):
        await update.message.reply_text("⚠️ Only admins can start Forge Wars!")
        return

    data = load_data()
    group = get_group(data, chat_id)
    group["forge_war"] = True
    group["forge_war_multiplier"] = 2
    save_data(data)

    await update.message.reply_text(
        "⚔️ *FORGE WAR HAS BEGUN!* ⚔️\n\n"
        "All challenge rewards are now *2× for the next hour!*\n"
        "Fight for glory and Forge Coins! 🪙🔥",
        parse_mode="Markdown"
    )

    context.job_queue.run_once(
        lambda ctx: asyncio.ensure_future(end_forge_war(ctx, chat_id)),
        when=3600,
        name=f"forgewar_end_{chat_id}",
    )


async def end_forge_war(context: ContextTypes.DEFAULT_TYPE, chat_id: int):
    data = load_data()
    group = get_group(data, chat_id)
    group["forge_war"] = False
    group["forge_war_multiplier"] = 1
    save_data(data)
    await context.bot.send_message(
        chat_id=chat_id,
        text="⚔️ *Forge War has ended!* Rewards return to normal. Great battles were fought today! 🏆",
        parse_mode="Markdown"
    )


async def cmd_hint(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    data = load_data()
    group = get_group(data, chat_id)
    challenge = group["active_challenge"]

    if not challenge:
        await update.message.reply_text("No active challenge right now!")
        return

    await update.message.reply_text(
        f"💡 *Hint:* _{challenge['hint']}_",
        parse_mode="Markdown"
    )


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 *Aira – Command Help*\n"
        "━━━━━━━━━━━━━\n"
        "/challenge – Trigger a new challenge\n"
        "/wallet – Your coins, wins & streak\n"
        "/leaderboard – Weekly top players\n"
        "/streak – Your win streak\n"
        "/badges – Your badge collection\n"
        "/shop – Spend Forge Coins\n"
        "/settitle <title> – Set your member tag (after purchase)\n"
        "/hint – Get a hint for active challenge\n"
        "/forgewar – Start Forge War (admins only)\n"
        "/help – This message\n\n"
        "💡 Answer challenges by simply typing the answer in chat!",
        parse_mode="Markdown"
    )

# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("challenge", cmd_challenge))
    app.add_handler(CommandHandler("wallet", cmd_wallet))
    app.add_handler(CommandHandler("leaderboard", cmd_leaderboard))
    app.add_handler(CommandHandler("streak", cmd_streak))
    app.add_handler(CommandHandler("badges", cmd_badges))
    app.add_handler(CommandHandler("shop", cmd_shop))
    app.add_handler(CommandHandler("settitle", cmd_settitle))
    app.add_handler(CommandHandler("forgewar", cmd_forgewar))
    app.add_handler(CommandHandler("hint", cmd_hint))

    app.add_handler(CallbackQueryHandler(handle_shop_purchase, pattern="^buy_"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info("Aira is running...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
