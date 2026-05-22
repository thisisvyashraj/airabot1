"""
Aira – Telegram Study Group Bot
A gamified quiz bot with Forge Coins, streaks, leaderboard, and shop.
"""

import logging
import random
import asyncio
import json
import os
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
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
CHALLENGE_TIMEOUT = 300          # 5 minutes in seconds
CHALLENGE_INTERVAL_MIN = 1800    # 30 min min gap between auto challenges
CHALLENGE_INTERVAL_MAX = 5400    # 90 min max gap
BASE_COINS = 10
STREAK_BONUS_PER_LEVEL = 2       # extra coins per streak level
DATA_FILE = "aira_data.json"

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ─── Question Bank ────────────────────────────────────────────────────────────

QUESTIONS = [
    # Math
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
    # Science
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
        "name": "👑 Custom Title (1 day)",
        "desc": "Display a custom title next to your name in the group for 1 day!",
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
    "first_win":    ("🏅 First Blood",   "Won your first challenge!"),
    "streak_3":     ("🔥 On Fire",       "3-win streak!"),
    "streak_5":     ("🌟 Unstoppable",   "5-win streak!"),
    "wins_10":      ("💪 Veteran",       "10 total wins!"),
    "wins_25":      ("🏆 Champion",      "25 total wins!"),
    "spender":      ("🛍️ Shopaholic",   "Made your first shop purchase!"),
    "rich":         ("💰 Minted",        "Collected 500 Forge Coins!"),
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
    if user["wins"] >= 1:
        b = award_badge(user, "first_win")
        if b: new_badges.append(b)
    if user["streak"] >= 3:
        b = award_badge(user, "streak_3")
        if b: new_badges.append(b)
    if user["streak"] >= 5:
        b = award_badge(user, "streak_5")
        if b: new_badges.append(b)
    if user["wins"] >= 10:
        b = award_badge(user, "wins_10")
        if b: new_badges.append(b)
    if user["wins"] >= 25:
        b = award_badge(user, "wins_25")
        if b: new_badges.append(b)
    if user["coins"] >= 500:
        b = award_badge(user, "rich")
        if b: new_badges.append(b)
    return new_badges

def reset_weekly_if_needed(data: dict):
    """Reset weekly wins every Monday."""
    now = datetime.now()
    if now.weekday() == 0:  # Monday
        for uid in data["users"]:
            u = data["users"][uid]
            last = u.get("last_win_date")
            if last:
                last_dt = datetime.fromisoformat(last)
                if (now - last_dt).days >= 7:
                    u["weekly_wins"] = 0

# ─── Challenge Logic ──────────────────────────────────────────────────────────

async def post_challenge(context: ContextTypes.DEFAULT_TYPE, chat_id: int, question: dict = None):
    data = load_data()
    group = get_group(data, chat_id)

    if group["active_challenge"] is not None:
        return  # already a challenge running

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

    # Schedule expiry
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
        text=f"⌛ *Time's up!* No one answered the challenge correctly.\n_{q}_\n\nBetter luck next time! 💪",
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

# ─── Message Handler (Answer Checking) ───────────────────────────────────────

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

    correct_answers = challenge["answers"]
    if text not in correct_answers:
        return

    # ── Correct answer! ──
    group["active_challenge"] = None

    # Cancel expiry job
    jobs = context.job_queue.get_jobs_by_name(f"expire_{chat_id}")
    for job in jobs:
        job.schedule_removal()

    u = get_user(data, user.id, user.username, user.full_name)
    coins_earned = challenge["coins"]

    # Streak logic
    today = datetime.now().date().isoformat()
    if u.get("last_win_date") == today:
        u["streak"] += 1
    else:
        if u.get("last_win_date") == (datetime.now().date() - timedelta(days=1)).isoformat():
            u["streak"] += 1
        else:
            u["streak"] = 1
    u["last_win_date"] = today

    if u["streak"] > u.get("best_streak", 0):
        u["best_streak"] = u["streak"]

    # Streak bonus
    streak_bonus = (u["streak"] - 1) * STREAK_BONUS_PER_LEVEL
    coins_earned += streak_bonus

    # Double coins booster
    booster_msg = ""
    if u.get("double_coins"):
        coins_earned *= 2
        u["double_coins"] = False
        booster_msg = "\n⚡ *Double Coins Booster* activated! Coins doubled!"

    u["coins"] += coins_earned
    u["wins"] += 1
    u["weekly_wins"] = u.get("weekly_wins", 0) + 1

    # Check badges
    new_badges = check_badges(u)
    save_data(data)

    # Build win message
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

    # Schedule next auto challenge
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

    # Check if someone bought "choose_challenge"
    chooser = group.get("pending_chooser")
    if chooser:
        group["pending_chooser"] = None
        save_data(data)
        await update.message.reply_text(
            f"🎯 <@{chooser}> gets to choose the next challenge! "
            f"Reply with your question and I'll use it... "
            f"(Feature: DM me the question to set it!)"
        )
        return

    save_data(data)
    await post_challenge(context, chat_id)


async def cmd_wallet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    data = load_data()
    u = get_user(data, user.id, user.username, user.full_name)
    save_data(data)

    title_line = f"\n👑 Title: *{u['title']}*" if u.get("title") else ""
    booster = "⚡ Active" if u.get("double_coins") else "None"

    await update.message.reply_text(
        f"💼 *{user.full_name}'s Wallet*{title_line}\n"
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

    medals = ["🥇", "🥈", "🥉"] + ["4️⃣","5️⃣","6️⃣","7️⃣","8️⃣","9️⃣","🔟"]
    lines = ["🏆 *WEEKLY LEADERBOARD*\n━━━━━━━━━━━━━"]
    for i, (uid, u) in enumerate(sorted_users):
        name = u.get("full_name") or u.get("username") or "Unknown"
        title = f" [{u['title']}]" if u.get("title") else ""
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
            msg += "\n\n⚠️ No active challenge right now. Hint will apply to the next one."

    elif item_key == "custom_title":
        msg += "\n\n👑 Reply with your desired title (max 20 chars) and I'll set it for 24 hours!\n(Use /settitle <your title>)"

    elif item_key == "choose_challenge":
        chat_id = query.message.chat_id
        group = get_group(data, chat_id)
        group["pending_chooser"] = user.username or user.full_name
        msg += "\n\n🎯 Next time someone calls /challenge, *you* pick the question!\nSend me a DM with your question."

    save_data(data)
    await query.edit_message_text(msg, parse_mode="Markdown")


async def cmd_settitle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    if not context.args:
        await update.message.reply_text("Usage: /settitle <your title>")
        return

    title = " ".join(context.args)[:20]
    data = load_data()
    u = get_user(data, user.id, user.username, user.full_name)
    u["title"] = title
    u["title_expiry"] = (datetime.now() + timedelta(days=1)).isoformat()
    save_data(data)

    await update.message.reply_text(
        f"👑 Your title is now *{title}* for 24 hours! Show it off!",
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
        lambda ctx: end_forge_war(ctx, chat_id),
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
        "/settitle <title> – Set custom title (after purchase)\n"
        "/hint – Get a hint for active challenge\n"
        "/forgewar – Start Forge War (admins only)\n"
        "/help – This message\n\n"
        "💡 Answer challenges by simply typing the answer in chat!",
        parse_mode="Markdown"
    )

# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    app = Application.builder().token(BOT_TOKEN).build()

    # Commands
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

    # Shop button callbacks
    app.add_handler(CallbackQueryHandler(handle_shop_purchase, pattern="^buy_"))

    # Answer detection (must be last)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info("Aira is running...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
