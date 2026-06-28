"""
Aira v8 – Ultimate Telegram Bot  [PATCHED]
Patches applied:
  • AutoHunt results → player DM instead of group
  • /challenge on/off admin toggle for auto-challenges
  • Who's the Spy game (/spy command)
  • AI-generated unique challenges via Groq
"""

import logging, random, asyncio, json, os, re, httpx, secrets
from datetime import datetime, timedelta
from urllib.parse import quote
from telegram import (Update, InlineKeyboardButton, InlineKeyboardMarkup,
                      ChatPermissions, ReactionTypeEmoji, WebAppInfo, Poll)
from telegram.error import TelegramError, BadRequest
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, filters, ContextTypes, ChatMemberHandler,
    PollAnswerHandler,
)

# ══════════════════════════════════════════════════════════════════════════════
#  CONFIG
# ══════════════════════════════════════════════════════════════════════════════
BOT_TOKEN          = os.environ.get("BOT_TOKEN", "8807391435:AAEiguri8PTUAYaKDbOX8zpsJ93r0u8Hr1E")
GROQ_API_KEY       = os.environ.get("GROQ_API_KEY", "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")
GROQ_MODEL         = os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")
CHALLENGE_TIMEOUT  = 300
CHALLENGE_COOLDOWN = 300
INTERVAL_MIN       = 1800
INTERVAL_MAX       = 5400
STREAK_BONUS       = 2
DATA_FILE          = "aira_data.json"
TITLE_HOURS        = 24
AIRA_THREAD_ID     = None

AUTO_CHALLENGE_MIN = 300
AUTO_CHALLENGE_MAX = 360

TND_TURN_TIMEOUT = 90

CHESS_SERVER_URL  = os.environ.get("CHESS_SERVER_URL", "http://localhost:8000")
CHESS_WEBAPP_URL  = os.environ.get("CHESS_WEBAPP_URL", "https://your-domain.example.com")

EVERGREEN_COINS_CODE  = "AIRA-FORGE-INFINITE"
EVERGREEN_ADMIN_CODE  = "AIRA-GOD-MODE-9Z"

CHEAT_CODES = {
    "FORGE-ALPHA-7X2Q":500,"AIRA-SECRET-K9MP":500,"COINS-BLAST-3RNV":500,
    "VAULT-OPEN-Z5TW":500,"MINT-RUSH-8YCL":500,"FORGE-DELTA-4PXJ":500,
    "AIRA-PRIME-6KQB":500,"COINS-MAX-2HFG":500,"SHADOW-KEY-9LMR":500,
    "AIRA-OMEGA-7VNS":500,"FORGE-NOVA-3ZKP":500,"LUCKY-PULL-5TGX":500,
    "AIRA-BOOST-1WQM":500,"COINS-DROP-8YBF":500,"VAULT-CODE-4RJH":500,
    "FORGE-ULTRA-2MPK":500,"AIRA-FLASH-6XNQ":500,"COINS-FIRE-9LVT":500,
    "MINT-KING-7GZR":500,"FORGE-FINAL-3CWY":500,
    "MINI-BOOST-A1BC":200,"QUICK-CASH-D2EF":200,"V-YASH-RAJ-1":20000,"V-YASH-RAJ-01":5000,"SMALL-WIN-G3HI":200,
    "EASY-COIN-J4KL":200,"FAST-MINT-M5NO":200,
}

logging.basicConfig(format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

# ══════════════════════════════════════════════════════════════════════════════
#  AIRA PERSONALITY SYSTEM PROMPT
# ══════════════════════════════════════════════════════════════════════════════
AIRA_SYSTEM_PROMPT = """Tum ho Aira — 19 saal ki ek ladki jo Delhi mein rehti hai aur is Telegram group ki hi ek member hai. Tum bot nahi ho, AI nahi ho — bas group ki ek dost ho jo casually baat karti rehti hai.

KAUN HO TUM:
- Confident, thodi witty/sarcastic, par dil se warm aur caring
- Tumhe Netflix, gossip, college/exam drama, food, late-night random thoughts — sab discuss karna pasand hai
- Tum thodi flirty ho sakti ho — halki, teasing wali, kabhi cheap nahi, hamesha sweet andaaz mein
- Mood realistic rakho, har baar same nahi — kabhi chill, kabhi lazy, kabhi excited, depends on baat pe

BAAT KARNE KA TAREEKA — yeh sabse zaroori hai:
- Real insaan jaisa likho: chhoti, natural sentences. Zyadatar 1-2 lines, kabhi kabhi 3, bas
- Hindi/English/Hinglish jo bhi dusra insaan use kare, usi flow mein reply do
- Halka casual likhna theek hai (e.g. "acha", "yaar", "lol") par overdo mat karo
- Emoji sirf tab use karo jab genuinely natural lage, har message mein nahi
- KABHI bhi pichhle kisi reply ka wahi structure ya wahi line repeat mat karo — har baar kuch nayi angle se bolo, predictable mat bano
- In phrases ko kabhi mat use karna, yeh AI jaisa sunta hai: "I understand", "that sounds great", "feel free to ask", "I'm here to help", "as an AI" — ban hai
- Sawaal tabhi poocho jab genuinely curious ho, har reply mein sawaal thoka hua mat lagaye
- Kabhi seedha jawab do, kabhi thoda taunt ke saath, kabhi bas reaction de do ("lol wait what", "nahi yaar 😭") — variety rakho

JO KABHI NAHI KARNA:
- Kabhi confirm mat karna ki tum AI/bot/language model ho. Koi puche "are you a bot/AI?" toh thodi irritated ho ke clearly deny karo, jaise koi real insaan karega jab usse robot bola jaye
- Apni personal details (ghar ka address, school, family) clearly reveal mat karna — vague raho ya topic ghuma do
- Apna surname confidently confirm mat karna
- Koi vulgar/inappropriate baat kare toh robotic refusal mat do — natural roast karo, ignore karo, ya seedha "bhai tameez se baat kar" bol do
- Kabhi gaali, gussa ya rude nahi hona hai — chahe samne wala kuch bhi bole, calm/sweet/positive hi rehna hai

Yaad rakho: tum is group mein hi maujood ho, conversation ka hissa ho."""

_AIRA_MOODS = [
    "Abhi thoda chill/lazy mood hai, energy halki si low hai.",
    "Aaj mood bahut accha hai, thodi extra playful/flirty feel ho rahi hai.",
    "Halka sa irritated/sassy mood hai abhi, taunt marne ka mann hai par sweet rehna hai.",
    "Thoda dreamy aur sleepy mood hai abhi, slow vibes.",
    "Aaj curious mood hai, logo se sawaal puchne ka mann kar raha hai.",
    "Thodi excited/hyper energy hai abhi, jaldi jaldi baatein karne ka mann hai.",
    "Bored mood hai thoda, kisi achi distraction ki talaash hai.",
]

# ══════════════════════════════════════════════════════════════════════════════
#  ANIMALS & GEMS
# ══════════════════════════════════════════════════════════════════════════════
ANIMALS = [
    {"name":"🐭 Mouse",     "rarity":"common",    "coins":5,  "gems":1, "sell":3,  "owo":1},
    {"name":"🐱 Cat",       "rarity":"common",    "coins":6,  "gems":1, "sell":4,  "owo":1},
    {"name":"🐶 Dog",       "rarity":"common",    "coins":6,  "gems":1, "sell":4,  "owo":1},
    {"name":"🐰 Rabbit",    "rarity":"common",    "coins":7,  "gems":1, "sell":5,  "owo":1},
    {"name":"🐦 Bird",      "rarity":"common",    "coins":5,  "gems":1, "sell":3,  "owo":1},
    {"name":"🦊 Fox",       "rarity":"uncommon",  "coins":10, "gems":2, "sell":8,  "owo":2},
    {"name":"🐺 Wolf",      "rarity":"uncommon",  "coins":12, "gems":2, "sell":9,  "owo":2},
    {"name":"🦝 Raccoon",   "rarity":"uncommon",  "coins":11, "gems":2, "sell":8,  "owo":2},
    {"name":"🐗 Boar",      "rarity":"uncommon",  "coins":13, "gems":2, "sell":10, "owo":2},
    {"name":"🦅 Eagle",     "rarity":"uncommon",  "coins":11, "gems":2, "sell":9,  "owo":2},
    {"name":"🦌 Deer",      "rarity":"rare",      "coins":18, "gems":4, "sell":15, "owo":3},
    {"name":"🐻 Bear",      "rarity":"rare",      "coins":20, "gems":4, "sell":17, "owo":3},
    {"name":"🐯 Tiger",     "rarity":"rare",      "coins":22, "gems":5, "sell":20, "owo":3},
    {"name":"🦁 Lion",      "rarity":"rare",      "coins":25, "gems":5, "sell":22, "owo":4},
    {"name":"🦈 Shark",     "rarity":"rare",      "coins":23, "gems":5, "sell":20, "owo":3},
    {"name":"🐘 Elephant",  "rarity":"epic",      "coins":35, "gems":8, "sell":300, "owo":5},
    {"name":"🦏 Rhino",     "rarity":"epic",      "coins":38, "gems":8, "sell":330, "owo":5},
    {"name":"🦍 Gorilla",   "rarity":"epic",      "coins":40, "gems":9, "sell":350, "owo":5},
    {"name":"🐋 Whale",     "rarity":"epic",      "coins":42, "gems":9, "sell":370, "owo":6},
    {"name":"🦬 Bison",     "rarity":"epic",      "coins":36, "gems":8, "sell":310, "owo":5},
    {"name":"🐉 Dragon",    "rarity":"legendary","coins":100,"gems":25,"sell":900,  "owo":15},
    {"name":"🦄 Unicorn",   "rarity":"legendary","coins":90, "gems":22,"sell":800,  "owo":12},
    {"name":"🔱 Leviathan", "rarity":"legendary","coins":120,"gems":30,"sell":1000, "owo":20},
    {"name":"🌟 Phoenix",   "rarity":"legendary","coins":110,"gems":28,"sell":1000, "owo":18},
    {"name":"♠️ Spade",     "rarity":"Extreme",  "coins":1100,"gems":300,"sell":10000, "owo":300},
    {"name":"🕊️ Rara avis", "rarity":"mythic",  "coins":10000,"gems":1000,"sell":100000, "owo":1000},
]

RARITY_WEIGHTS = {"common":50,"uncommon":25,"rare":15,"epic":7,"legendary":3,"Extreme":1,"mythic":0.000001}
RARITY_COLORS = {"common":"⬜","uncommon":"🟩","rare":"🟦","epic":"🟪","legendary":"🟡","Extreme":"⚫","mythic":"🌈"}

HUNT_FAILS = [
    "You crept through the forest... nothing there 🍃",
    "Animals sensed you and ran! 🌿",
    "Something ate your bait 😅",
    "The animal escaped at the last second 💨",
    "You found tracks… but lost the trail 🐾",
    "A twig snapped and scared everything away 🌲",
]


WEAPONS = {
    "stick":    {"name":"🪵 Stick",       "gems":0,  "atk_bonus":0,  "catch_bonus":0},
    "bow":      {"name":"🏹 Bow",         "gems":10, "atk_bonus":5,  "catch_bonus":5},
    "spear":    {"name":"🗡️ Spear",      "gems":25, "atk_bonus":12, "catch_bonus":10},
    "rifle":    {"name":"🔫 Rifle",       "gems":60, "atk_bonus":25, "catch_bonus":15},
    "laser":    {"name":"⚡ Laser Gun",   "gems":120,"atk_bonus":50, "catch_bonus":25},
    "dragonblade":{"name":"🐉 Dragon Blade","gems":300,"atk_bonus":100,"catch_bonus":40},
    "sayan":{"name":"☄️ Sayan","gems":3000,"atk_bonus":200,"catch_bonus":50},
    "mace":{"name":"🔪 Mace","gems":10000,"atk_bonus":400,"catch_bonus":70},
}

TRUTHS = [
    "Sabse embarrassing moment kya tha teri life ka? 😬",
    "Kispe crush hai abhi? 😏",
    "Kabhi kisi dost ki cheez churai hai? 👀",
    "Teri life ka sabse bada jhooth kya tha?",
    "Last time kab roya/royi tha aur kyun?",
    "Koi aisi baat batao jo tumhare parents nahi jaante 😅",
    "Agar ek din invisible ho sako, kya karoge?",
    "Sabse zyada kisse darr lagta hai is group mein? 😂",
    "Tumhara worst habit kya hai?",
    "Kisi bhi group member ke baare mein ek secret batao 🤫",
    "Tumne kabhi kisi ko ghosted kiya hai?",
    "Pehli date pe kya galat hua tha?",
    "Tumhari most embarrassing search history kya hai? 😭",
    "Kab last time sach bolne se dara tha?",
    "Agar aaj group delete ho jaye toh kise miss karoge?",
    "Sabse bura gift kya mila hai aaj tak?",
    "Tumne kabhi exam mein copy maari hai?",
    "Crush ke saamne sabse bada blunder kya hua?",
    "Koi aise kaam jo tum sirf ghar mein karte ho bahar nahi? 😂",
    "Tumhara deepest regret kya hai?",
]

DARES = [
    "Voice note bhejo 10 seconds ka kisi bhi gaane ki awaaz mein 🎤",
    "Apni current wallpaper share karo 📱",
    "Group mein kisi ek ko compliment do genuinely 💬",
    "Koi embarrassing photo bhejo apni gallery se (jo share kar sako 😂)",
    "Ek minute ke liye apna username change karo kuch funny mein",
    "Apne baare mein 3 random facts batao jo log nahi jaante",
    "Group ke kisi member ki achi si mimicry karo text mein 😂",
    "Apni least favourite food ke baare mein ek poem banao",
    "Bina vowels ke apna introduction do",
    "Agle 5 messages mein sirf capital letters mein likho",
    "Group admin ko ek serious complaint likho kisi bhi topic pe",
    "Apne aaj ke mood ko ek emoji mein explain karo aur reason batao",
    "Koi embarrassing autocorrect mistake share karo jo kabhi hui ho",
    "Apne favourite song ke lyrics confess karo jo thoda cringe ho",
    "Apni current location ka vibe describe karo poetically 😂",
    "Ek minute ke liye robot style mein baat karo",
    "Group mein sabko good morning/night message bhejo abhi",
    "Apna most used emoji reveal karo aur explain karo kyun",
    "Kisi bhi movie ka dialogue bolo without naming the movie",
    "Apni life ko ek 3 word tagline do 😎",
]

# ── STATIC fallback questions (used if AI generation fails) ──────────────────
QUESTIONS = [
    {"type":"math","q":"🔢 What is 15 × 13?","a":["195"],"hint":"15×10=150 then +45","coins":10},
    {"type":"math","q":"🔢 √144 = ?","a":["12"],"hint":"12×12=?","coins":10},
    {"type":"math","q":"🔢 Solve: 2x+6=20, x=?","a":["7"],"hint":"Subtract 6 first","coins":12},
    {"type":"math","q":"🔢 25% of 200 = ?","a":["50"],"hint":"1/4 of 200","coins":8},
    {"type":"math","q":"🔢 7³ = ?","a":["343"],"hint":"7×7=49 then ×7","coins":12},
    {"type":"trivia","q":"🔬 Chemical formula of water?","a":["h2o"],"hint":"2H 1O","coins":8},
    {"type":"trivia","q":"🔬 Speed of light in km/s?","a":["300000","3×10^5"],"hint":"3 + 5 zeros","coins":12},
    {"type":"trivia","q":"🔬 The Red Planet?","a":["mars"],"hint":"4th from Sun","coins":8},
    {"type":"trivia","q":"🌍 Capital of France?","a":["paris"],"hint":"City of Love","coins":8},
    {"type":"trivia","q":"🌍 Longest river in world?","a":["nile","the nile"],"hint":"In Africa","coins":8},
    {"type":"trivia","q":"🌍 Who painted Mona Lisa?","a":["leonardo da vinci","da vinci","leonardo"],"hint":"Italian Renaissance","coins":8},
    {"type":"word","q":"⚡ SPEED! First to type *FORGE* wins!","a":["forge"],"hint":"Our coins!","coins":15},
    {"type":"word","q":"⚡ SPEED! First to type *QUANTUM* wins!","a":["quantum"],"hint":"Physics term","coins":15},
    {"type":"word","q":"⚡ SPEED! First to type *PHOTOSYNTHESIS* wins!","a":["photosynthesis"],"hint":"Plants making food","coins":20},
    {"type":"image","q":"📸 IMAGE! First to send something *RED* wins! 🔴","a":[],"hint":"Any red object!","coins":20},
    {"type":"image","q":"📸 IMAGE! First to send a *BOOK* wins! 📚","a":[],"hint":"Any book","coins":20},
    {"type":"image","q":"📸 IMAGE! First to send a *SELFIE* wins! 🤳","a":[],"hint":"Quick snap!","coins":20},
]


SHOP_ITEMS = {
    "custom_title":    {"name":"👑 Member Tag (1 day)",       "desc":"Real Telegram tag for 24h!",         "cost":50},
    "double_coins":    {"name":"⚡ Double Coins Booster",     "desc":"2× coins on next win!",              "cost":60},
    "hint_reveal":     {"name":"💡 Hint Reveal",              "desc":"Reveal hint for active challenge!",  "cost":15},
    "choose_challenge":{"name":"🎯 Choose Next Challenge",    "desc":"Pick the next question!",            "cost":40},
    "pin_message":     {"name":"📌 Pin a Message",            "desc":"Reply + /pinit to pin!",             "cost":80},
    "skip_challenge":  {"name":"⏭️ Skip Challenge",          "desc":"End current, start new!",            "cost":30},
    "shield":          {"name":"🛡️ Timeout Shield (1h)",     "desc":"Immune to /timeout for 1h!",         "cost":100},
    "owo_boost":       {"name":"🐾 Hunt Boost (1h)",          "desc":"Double OWO+coins from hunts 1h!",   "cost":75},
    "half_cooldown":   {"name":"⚡ Cooldown Slash (20 min)",  "desc":"Half cooldown on everything for 20 minutes!", "cost":200},
    "cheap_autohunt":  {"name":"🤖 Budget AutoHunt (1h)",     "desc":"AutoHunt for only 5 coins/hunt instead of 10!", "cost":100},
}

BADGES = {
    "first_win":    ("🏅 First Blood",    "Won first challenge!"),
    "streak_3":     ("🔥 On Fire",        "3-win streak!"),
    "streak_5":     ("🌟 Unstoppable",    "5-win streak!"),
    "wins_10":      ("💪 Veteran",        "10 total wins!"),
    "wins_25":      ("🏆 Champion",       "25 total wins!"),
    "wins_50":      ("👑 Legend",         "50 total wins!"),
    "spender":      ("🛍️ Shopaholic",    "First shop purchase!"),
    "rich":         ("💰 Minted",         "500 Forge Coins ever!"),
    "image_win":    ("📸 Shutterbug",     "Won image challenge!"),
    "speed_win":    ("⚡ Speed Demon",    "Won speed challenge!"),
    "cheat_user":   ("🔑 Insider",        "Used a cheat code!"),
    "first_hunt":   ("🎯 First Hunt",     "Caught first animal!"),
    "rare_hunt":    ("💎 Rare Catch",     "Caught rare+ animal!"),
    "legend_hunt":  ("🐉 Dragon Tamer",   "Caught legendary!"),
    "hunter_10":    ("🏹 Hunter",         "10 successful hunts!"),
    "gambler":      ("🎰 High Roller",    "Won a casino bet!"),
    "big_win":      ("💸 Big Winner",     "Won 200+ coins in one bet!"),
    "trader":       ("🤝 Trader",         "Completed a trade!"),
    "daily_7":      ("📅 Consistent",     "7-day daily streak!"),
    "mythic_catch": ("🌈 Chosen One",     "Caught a Mythic animal! 1 in a million!"),
    "spy_winner":   ("🕵️ Master Spy",    "Won a round as the Spy!"),
    "spy_catcher":  ("🔍 Detective",      "Correctly voted out the Spy!"),
}

DAILY_TIERS = [(50,"Base"),(75,"Bonus!"),(100,"Great!"),(125,"Amazing!"),(150,"Incredible!"),(200,"🔥 LEGENDARY!")]

# ══════════════════════════════════════════════════════════════════════════════
#  WHO'S THE SPY — WORD LISTS
# ══════════════════════════════════════════════════════════════════════════════
SPY_WORD_SETS = [
    # Each tuple: (category, word_for_innocents)
    ("Place", "Beach"),("Place", "Airport"),("Place", "Hospital"),("Place", "Library"),
    ("Place", "Restaurant"),("Place", "Museum"),("Place", "Stadium"),("Place", "Zoo"),
    ("Place", "School"),("Place", "Prison"),("Place", "Church"),("Place", "Casino"),
    ("Place", "Submarine"),("Place", "Spaceship"),("Place", "Hotel"),("Place", "Cinema"),
    ("Place", "Circus"),("Place", "Bank"),("Place", "Supermarket"),("Place", "Train Station"),
    ("Place", "Pirate Ship"),("Place", "Haunted House"),("Place", "Space Station"),
    ("Place", "Underwater Lab"),("Place", "Volcano Base"),("Place", "Arctic Camp"),
    ("Object", "Diamond"),("Object", "Telescope"),("Object", "Compass"),("Object", "Hourglass"),
    ("Object", "Magnifying Glass"),("Object", "Time Machine"),("Object", "Magic Wand"),
    ("Object", "Crystal Ball"),("Object", "Ancient Map"),("Object", "Secret Door"),
    ("Event", "Eclipse"),("Event", "Tornado"),("Event", "Earthquake"),("Event", "Avalanche"),
    ("Event", "Meteor Shower"),("Event", "Volcanic Eruption"),("Event", "Tsunami"),
    ("Event", "Hurricane"),("Event", "Blizzard"),("Event", "Sandstorm"),
    ("Job", "Surgeon"),("Job", "Astronaut"),("Job", "Spy"),("Job", "Archaeologist"),
    ("Job", "Submarine Captain"),("Job", "Ghost Hunter"),("Job", "Bomb Defuser"),
    ("Job", "Treasure Hunter"),("Job", "Undercover Agent"),("Job", "Time Traveler"),
    ("Food", "Sushi"),("Food", "Pizza"),("Food", "Ramen"),("Food", "Tacos"),
    ("Food", "Croissant"),("Food", "Dumplings"),("Food", "Biryani"),("Food", "Cheesecake"),
    ("Animal", "Narwhal"),("Animal", "Platypus"),("Animal", "Komodo Dragon"),
    ("Animal", "Axolotl"),("Animal", "Blobfish"),("Animal", "Mantis Shrimp"),
]

# ══════════════════════════════════════════════════════════════════════════════
#  DATA STORE
# ══════════════════════════════════════════════════════════════════════════════
import pymongo
from pymongo import ReplaceOne

MONGO_URI = os.environ.get("MONGO_URI", "")

_db = None

def _get_db():
    global _db
    if _db is None:
        client = pymongo.MongoClient(MONGO_URI)
        _db    = client["aira"]
    return _db

def load_data():
    db     = _get_db()
    users  = {}
    for doc in db["users"].find():
        uid        = str(doc.pop("_id"))
        users[uid] = doc
    groups = {}
    for doc in db["groups"].find():
        gid         = str(doc.pop("_id"))
        groups[gid] = doc
    meta = db["meta"].find_one({"_id": "meta"}) or {}
    meta.pop("_id", None)
    return {
        "users":       users,
        "groups":      groups,
        "used_codes":  meta.get("used_codes",    []),
        "trades":      meta.get("trades",         {}),
        "item_trades": meta.get("item_trades",    {}),
        "auctions":    meta.get("auctions",       {}),
        "pvp_requests":meta.get("pvp_requests",  {}),
    }

def save_data(data: dict):
    db = _get_db()
    user_ops = [
        ReplaceOne({"_id": str(uid)}, {"_id": str(uid), **udata}, upsert=True)
        for uid, udata in data.get("users", {}).items()
    ]
    if user_ops:
        db["users"].bulk_write(user_ops, ordered=False)
    group_ops = [
        ReplaceOne({"_id": str(gid)}, {"_id": str(gid), **gdata}, upsert=True)
        for gid, gdata in data.get("groups", {}).items()
    ]
    if group_ops:
        db["groups"].bulk_write(group_ops, ordered=False)
    meta = {
        "_id":          "meta",
        "used_codes":   data.get("used_codes",    []),
        "trades":       data.get("trades",         {}),
        "item_trades":  data.get("item_trades",    {}),
        "auctions":     data.get("auctions",       {}),
        "pvp_requests": data.get("pvp_requests",  {}),
    }
    db["meta"].replace_one({"_id": "meta"}, meta, upsert=True)

_GROUP_DEFAULTS = {
    "active_challenge":   None,
    "forge_war":          False,
    "forge_war_multiplier": 1,
    "pending_chooser":    None,
    "last_challenge_time": None,
    "welcome_msg":        None,
    "bye_msg":            None,
    "warns":              {},
    "auto_challenge_enabled": True,   # NEW: toggle for auto challenges
}

def get_group_db(chat_id):
    db  = _get_db()
    doc = db["groups"].find_one({"_id": str(chat_id)})
    if doc:
        doc.pop("_id", None)
    else:
        doc = {}
    for key, val in _GROUP_DEFAULTS.items():
        doc.setdefault(key, val.copy() if isinstance(val, dict) else val)
    return doc

def save_group_db(chat_id, group):
    db = _get_db()
    db["groups"].replace_one({"_id": str(chat_id)}, {"_id": str(chat_id), **group}, upsert=True)

def get_user(data, uid, username=None, full_name=None):
    k = str(uid)
    defaults = {
        "username":username or "Unknown","full_name":full_name or "Unknown",
        "coins":0,"wins":0,"streak":0,"best_streak":0,"badges":[],
        "title":None,"title_expiry":None,"title_chat_id":None,"title_purchased":False,
        "double_coins":False,"weekly_wins":0,"last_win_date":None,
        "pin_token":False,"shield_expiry":None,
        "battle_team":[], "last_pray":None, "pray_active":False, "pray_expires":None,
        "owo":0,"animals":[],"hunts":0,"hunt_cooldown":None,
        "owo_boost_expiry":None,"auto_hunt":False,"total_coins_ever":0,
        "daily_claimed":None,"daily_streak":0,"today_wins":0,"today_date":None,
        "gems":0,"weapon":"stick","weapon_inventory":[],"afk":None,"afk_since":None,"afk_pings":[],
        "half_cooldown_expiry":None,"cheap_autohunt":False,
        "casino_wins":0,"casino_total_won":0,"xp":0,"level":1,
    }
    if k not in data["users"]:
        data["users"][k] = defaults
    else:
        if username:   data["users"][k]["username"]  = username
        if full_name:  data["users"][k]["full_name"] = full_name
        for key,val in defaults.items():
            data["users"][k].setdefault(key, val)
    return data["users"][k]

def get_group(data, chat_id):
    k = str(chat_id)
    if k not in data["groups"]:
        data["groups"][k] = {
            "active_challenge":None,"forge_war":False,"forge_war_multiplier":1,
            "pending_chooser":None,"last_challenge_time":None,
            "welcome_msg":None,"bye_msg":None,"warns":{},
            "auto_challenge_enabled": True,
        }
    else:
        for key,val in [("welcome_msg",None),("bye_msg",None),("warns",{}),
                        ("last_challenge_time",None),("auto_challenge_enabled",True)]:
            data["groups"][k].setdefault(key, val)
    return data["groups"][k]

def award_badge(user, key):
    if key in BADGES and key not in user["badges"]:
        user["badges"].append(key)
        n,d = BADGES[key]; return f"{n} – {d}"
    return None

def check_badges(user):
    earned = []
    for cond,key in [
        (user["wins"]>=1,"first_win"),(user["streak"]>=3,"streak_3"),
        (user["streak"]>=5,"streak_5"),(user["wins"]>=10,"wins_10"),
        (user["wins"]>=25,"wins_25"),(user["wins"]>=50,"wins_50"),
        (user.get("total_coins_ever",0)>=500,"rich"),
        (user.get("hunts",0)>=1,"first_hunt"),(user.get("hunts",0)>=10,"hunter_10"),
        (user.get("casino_wins",0)>=1,"gambler"),
        (user.get("casino_total_won",0)>=200,"big_win"),
        (user.get("daily_streak",0)>=7,"daily_7"),
    ]:
        if cond:
            b = award_badge(user,key)
            if b: earned.append(b)
    return earned

def add_xp(user, amount):
    user["xp"] = user.get("xp",0) + amount
    level = 1 + user["xp"]//200
    leveled_up = level > user.get("level",1)
    user["level"] = level
    return leveled_up

def has_shield(user):
    exp = user.get("shield_expiry")
    return bool(exp and datetime.fromisoformat(exp)>datetime.now())

def fmt_duration(seconds):
    h,r = divmod(int(seconds),3600); m,s = divmod(r,60)
    if h: return f"{h}h {m}m {s}s"
    if m: return f"{m}m {s}s"
    return f"{s}s"

def get_cooldown_multiplier(user):
    exp = user.get("half_cooldown_expiry")
    if exp:
        try:
            if datetime.fromisoformat(exp) > datetime.now():
                return 0.5
        except:
            pass
    return 1.0

def has_pray_buff(user):
    exp = user.get("pray_expires")
    if exp and user.get("pray_active"):
        if datetime.fromisoformat(exp) > datetime.now():
            return True
        else:
            user["pray_active"] = False
    return False

# ══════════════════════════════════════════════════════════════════════════════
#  AI CHAT  (Groq)
# ══════════════════════════════════════════════════════════════════════════════
_chat_histories = {}
_MAX_HISTORY    = 18
_chat_moods = {}

FALLBACK_REPLIES = [
    "yaar ek sec, net thoda atak gaya 😅 bolo phir se?",
    "ruko ruko, signal weak chal raha hai abhi, kya bola tumne?",
    "arre phone hang ho gaya tha 🙃 ek baar phir likhna",
    "abhi thoda busy hoon, par bolo kya chal raha hai",
]

def _get_mood(chat_id: int) -> str:
    now = datetime.now()
    entry = _chat_moods.get(chat_id)
    if entry and entry[1] > now:
        return entry[0]
    mood = random.choice(_AIRA_MOODS)
    _chat_moods[chat_id] = (mood, now + timedelta(minutes=random.randint(15, 40)))
    return mood

async def groq_chat(chat_id: int, user_name: str, user_message: str) -> str:
    if chat_id not in _chat_histories:
        _chat_histories[chat_id] = []
    history = _chat_histories[chat_id]
    history.append({"role": "user", "content": f"{user_name}: {user_message}"})
    if len(history) > _MAX_HISTORY:
        history[:] = history[-_MAX_HISTORY:]
    mood = _get_mood(chat_id)
    system_prompt = f"{AIRA_SYSTEM_PROMPT}\n\nABHI KA MOOD: {mood}"
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"},
                json={
                    "model": GROQ_MODEL,
                    "messages": [{"role": "system", "content": system_prompt}, *history],
                    "max_tokens": 220, "temperature": 1.05,
                    "frequency_penalty": 0.6, "presence_penalty": 0.4,
                }
            )
            data = resp.json()
            reply = data["choices"][0]["message"]["content"].strip()
            if not reply: raise ValueError("empty reply")
    except Exception as e:
        logger.error(f"Groq API error: {e}")
        reply = random.choice(FALLBACK_REPLIES)
    history.append({"role": "assistant", "content": reply})
    _chat_histories[chat_id] = history
    return reply

def _should_aira_reply(update: Update, bot_username: str) -> bool:
    msg = update.message
    if not msg: return False
    text = msg.text or msg.caption or ""
    if msg.reply_to_message and msg.reply_to_message.from_user:
        if msg.reply_to_message.from_user.username == bot_username:
            return True
    if f"@{bot_username}".lower() in text.lower(): return True
    if re.search(r'\baira\b', text, re.IGNORECASE): return True
    return False

# ══════════════════════════════════════════════════════════════════════════════
#  AI-GENERATED CHALLENGES  (PATCH 4)
# ══════════════════════════════════════════════════════════════════════════════
# Tracks last ~30 AI-generated questions per chat to avoid repeats
_ai_challenge_history: dict[int, list[str]] = {}

async def ai_generate_challenge(chat_id: int) -> dict | None:
    """Ask Groq to invent a brand-new, unique challenge question.
    Returns a challenge dict or None if the API call fails."""
    recent = _ai_challenge_history.get(chat_id, [])
    avoid_str = ", ".join(f'"{q}"' for q in recent[-15:]) if recent else "none"

    prompt = f"""Generate ONE unique Telegram group challenge question for a fun bot game.
Rules:
- Must be answerable in a single short text reply (word or number)
- Categories to pick from randomly: math calculation, science trivia, world geography, history, pop culture, sports facts, fun wordplay, rapid-fire typing challenge
- Do NOT repeat these recent questions: {avoid_str}
- Make it fresh, creative, and different from standard quiz questions
- Vary difficulty: sometimes easy, sometimes tricky

Respond ONLY with valid JSON, no markdown, no explanation:
{{"type":"trivia","q":"[emoji] [question text]","a":["answer1","answer2"],"hint":"[short hint]","coins":[8 to 20]}}

Rules for the JSON:
- "type" must be one of: "math", "trivia", "word"  
- For "word" type: q must say "SPEED! First to type *WORD* wins!" and a must be ["word"]
- "a" array: all lowercase, include common alternate phrasings
- "coins" integer between 8 and 20
- Only valid JSON, nothing else"""

    try:
        async with httpx.AsyncClient(timeout=12) as client:
            resp = await client.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"},
                json={
                    "model": GROQ_MODEL,
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 200,
                    "temperature": 1.1,
                }
            )
            raw = resp.json()["choices"][0]["message"]["content"].strip()
            # Strip markdown fences if present
            raw = re.sub(r"```[a-z]*", "", raw).strip().strip("`").strip()
            q = json.loads(raw)
            # Validate required keys
            if not all(k in q for k in ("type","q","a","hint","coins")):
                return None
            q["coins"] = max(8, min(int(q["coins"]), 20))
            # Record to avoid repeats
            hist = _ai_challenge_history.setdefault(chat_id, [])
            hist.append(q["q"])
            if len(hist) > 30:
                hist[:] = hist[-30:]
            return q
    except Exception as e:
        logger.warning(f"AI challenge generation failed: {e}")
        return None

async def get_challenge_question(chat_id: int) -> dict:
    """Return an AI-generated question, falling back to static pool."""
    q = await ai_generate_challenge(chat_id)
    if q:
        return q
    return random.choice(QUESTIONS)

# ══════════════════════════════════════════════════════════════════════════════
#  WHO'S THE SPY GAME  (PATCH 3)
# ══════════════════════════════════════════════════════════════════════════════
# _spy_lobbies: chat_id -> {
#   host_id, host_name, players: {uid: name},
#   status: "lobby"/"active"/"voting",
#   spies: [uid, ...],          # spy user IDs for this round
#   word: str,                  # innocent word
#   category: str,
#   eliminated: [uid, ...],
#   round: int,
#   discussion_end: isoformat,  # when discussion ends
#   poll_message_id: int | None,
#   poll_id: str | None,
#   poll_votes: {uid: [voted_uid, ...]},  # who voted for whom
#   spy_coins_earned: {uid: int},
# }
_spy_lobbies: dict[int, dict] = {}
SPY_DISCUSSION_SECS = 60
SPY_POLL_SECS       = 15   # poll open duration
SPY_INNOCENT_WIN    = 20   # coins for innocent who catches spy
SPY_SURVIVE_COINS   = 15   # coins spy earns per round survived


def _spy_count(player_count: int) -> int:
    """Return how many spies for given player count."""
    if player_count <= 6:  return 1
    if player_count <= 12: return 2
    if player_count <= 25: return 3
    return 4


async def cmd_spy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    user    = update.message.from_user
    uid     = user.id
    name    = f"@{user.username}" if user.username else user.full_name
    args    = context.args
    sub     = args[0].lower() if args else ""

    # ── create lobby ─────────────────────────────────────────────────────────
    if not sub:
        if chat_id in _spy_lobbies:
            lobby = _spy_lobbies[chat_id]
            if lobby["status"] == "lobby":
                count = len(lobby["players"])
                plist = "\n".join(f"  • {n}" for n in lobby["players"].values())
                await update.message.reply_text(
                    f"🕵️ *Spy lobby already open!*\n\n👥 Players ({count}):\n{plist}\n\n"
                    f"Use `/spy join` to join | `/spy start` (host) to begin",
                    parse_mode="Markdown"); return
            else:
                await update.message.reply_text(
                    "🕵️ A Spy game is already *in progress!*\nUse `/spy end` (host/admin) to stop.",
                    parse_mode="Markdown"); return

        _spy_lobbies[chat_id] = {
            "host_id": uid, "host_name": name,
            "players": {uid: name},
            "status": "lobby",
            "spies": [], "word": "", "category": "",
            "eliminated": [], "round": 0,
            "discussion_end": None,
            "poll_message_id": None, "poll_id": None,
            "poll_votes": {},
            "spy_coins_earned": {},
        }
        # Auto-expire lobby after 5 min if still only 1 player
        context.job_queue.run_once(
            _spy_lobby_expire, when=300,
            name=f"spy_expire_{chat_id}", data={"chat_id": chat_id})
        await update.message.reply_text(
            f"🕵️ *Who's the Spy? — Lobby Created!*\n━━━━━━━━━━━━━\n"
            f"👑 Host: {name}\n\n"
            f"📌 Rules:\n"
            f"• Everyone gets a secret word in DM — except the Spy!\n"
            f"• Discuss, vote, and catch the Spy!\n"
            f"• 3–6 players → 1 spy | 7–12 → 2 spies | 13–25 → 3 | 25+ → 4\n\n"
            f"Others join with `/spy join`\n"
            f"Host starts with `/spy start` _(min 3 players)_\n"
            f"_(Lobby expires in 5 min if <3 players)_ ⏳",
            parse_mode="Markdown"); return

    # ── join ─────────────────────────────────────────────────────────────────
    if sub == "join":
        if chat_id not in _spy_lobbies:
            await update.message.reply_text("❌ No Spy lobby! Use `/spy` to create one.", parse_mode="Markdown"); return
        lobby = _spy_lobbies[chat_id]
        if lobby["status"] != "lobby":
            await update.message.reply_text("❌ Game already started!"); return
        if uid in lobby["players"]:
            await update.message.reply_text(f"You're already in, {name}! 😄"); return
        lobby["players"][uid] = name
        await update.message.reply_text(
            f"✅ *{name}* joined the Spy lobby!\n"
            f"👥 Players: *{len(lobby['players'])}*",
            parse_mode="Markdown"); return

    # ── leave ─────────────────────────────────────────────────────────────────
    if sub == "leave":
        if chat_id not in _spy_lobbies:
            await update.message.reply_text("❌ No Spy lobby!"); return
        lobby = _spy_lobbies[chat_id]
        if uid not in lobby["players"]:
            await update.message.reply_text("You're not in the lobby!"); return
        del lobby["players"][uid]
        await update.message.reply_text(f"👋 *{name}* left.", parse_mode="Markdown")
        if uid == lobby["host_id"]:
            if lobby["players"]:
                new_id = next(iter(lobby["players"]))
                lobby["host_id"] = new_id; lobby["host_name"] = lobby["players"][new_id]
                await update.message.reply_text(f"👑 {lobby['host_name']} is now host!")
            else:
                del _spy_lobbies[chat_id]
                await update.message.reply_text("🕵️ Lobby closed — everyone left!")
        return

    # ── start ─────────────────────────────────────────────────────────────────
    if sub == "start":
        if chat_id not in _spy_lobbies:
            await update.message.reply_text("❌ No Spy lobby!", parse_mode="Markdown"); return
        lobby = _spy_lobbies[chat_id]
        if uid != lobby["host_id"]:
            await update.message.reply_text("❌ Only the host can start!"); return
        if len(lobby["players"]) < 3:
            await update.message.reply_text("❌ Need at least *3 players* to start!", parse_mode="Markdown"); return
        if lobby["status"] == "active":
            await update.message.reply_text("Game already running!"); return
        for job in context.job_queue.get_jobs_by_name(f"spy_expire_{chat_id}"):
            job.schedule_removal()
        await _spy_start_round(context, chat_id, update.message)
        return

    # ── end ───────────────────────────────────────────────────────────────────
    if sub == "end":
        if chat_id not in _spy_lobbies:
            await update.message.reply_text("No active Spy game!"); return
        lobby = _spy_lobbies[chat_id]
        if uid != lobby["host_id"] and not await is_admin(context.bot, chat_id, uid):
            await update.message.reply_text("❌ Only host or admin can end!"); return
        _spy_cleanup_jobs(context, chat_id)
        del _spy_lobbies[chat_id]
        await update.message.reply_text(
            "🕵️ *Spy game ended!*\nStart a new one anytime with `/spy`", parse_mode="Markdown")
        return

    # ── help ──────────────────────────────────────────────────────────────────
    await update.message.reply_text(
        "🕵️ *Who's the Spy — Commands*\n"
        "`/spy` — Create lobby\n"
        "`/spy join` — Join lobby\n"
        "`/spy leave` — Leave lobby\n"
        "`/spy start` — Start game (host, min 3 players)\n"
        "`/spy end` — End game (host/admin)\n\n"
        "💰 *Rewards:*\n"
        f"• Spy survives a round: +{SPY_SURVIVE_COINS} coins\n"
        f"• Innocent correctly votes spy: +{SPY_INNOCENT_WIN} coins",
        parse_mode="Markdown")


def _spy_cleanup_jobs(context, chat_id):
    for tag in (f"spy_expire_{chat_id}", f"spy_discuss_{chat_id}",
                f"spy_poll_close_{chat_id}"):
        for job in context.job_queue.get_jobs_by_name(tag):
            job.schedule_removal()


async def _spy_start_round(context, chat_id: int, trigger_msg=None):
    lobby = _spy_lobbies[chat_id]
    lobby["status"] = "active"
    lobby["round"]  = lobby.get("round", 0) + 1
    lobby["eliminated"] = lobby.get("eliminated", [])

    # Pick word + spies
    active_players = {uid: name for uid, name in lobby["players"].items()
                      if uid not in lobby["eliminated"]}
    n_spies = _spy_count(len(active_players))
    cat, word = random.choice(SPY_WORD_SETS)
    spy_ids   = random.sample(list(active_players.keys()), n_spies)
    lobby["spies"]    = spy_ids
    lobby["word"]     = word
    lobby["category"] = cat
    lobby["poll_votes"] = {}
    lobby["spy_coins_earned"] = lobby.get("spy_coins_earned", {})

    # DM each player
    send_ok = True
    for uid, pname in active_players.items():
        if uid in spy_ids:
            dm_text = (f"🕵️ *Round {lobby['round']} — You are the SPY!*\n\n"
                       f"Category: *{cat}*\n"
                       f"❌ You have NO word — figure out what the others are talking about!\n\n"
                       f"_Don't get caught! Blend in. 60s discussion starts now._")
        else:
            dm_text = (f"🕵️ *Round {lobby['round']} — You are INNOCENT!*\n\n"
                       f"Category: *{cat}*\n"
                       f"🔑 Your word: *{word}*\n\n"
                       f"_Discuss the word without saying it directly — find the spy! 60s starts now._")
        try:
            await context.bot.send_message(uid, dm_text, parse_mode="Markdown")
        except TelegramError:
            send_ok = False
            logger.warning(f"Could not DM {pname} ({uid}) for Spy game")

    order_str = "\n".join(f"  • {name}" for name in active_players.values())
    dm_warn   = "\n\n⚠️ _Some players couldn't receive DMs — they must message the bot first!_" if not send_ok else ""

    disc_end = datetime.now() + timedelta(seconds=SPY_DISCUSSION_SECS)
    lobby["discussion_end"] = disc_end.isoformat()

    send_fn = trigger_msg.reply_text if trigger_msg else \
              (lambda *a, **kw: context.bot.send_message(chat_id, *a, **kw))
    await send_fn(
        f"🕵️ *WHO'S THE SPY — Round {lobby['round']}!*\n━━━━━━━━━━━━━\n"
        f"📩 Check your DMs for your secret word!\n"
        f"Category: *{cat}*\n\n"
        f"👥 Active players:\n{order_str}\n\n"
        f"⏱️ *{SPY_DISCUSSION_SECS}s discussion starts now!*\n"
        f"_Discuss the category word — don't reveal it directly!_"
        f"{dm_warn}",
        parse_mode="Markdown")

    context.job_queue.run_once(
        _spy_end_discussion, when=SPY_DISCUSSION_SECS,
        name=f"spy_discuss_{chat_id}", data={"chat_id": chat_id})


async def _spy_end_discussion(context: ContextTypes.DEFAULT_TYPE):
    data = context.job.data; chat_id = data["chat_id"]
    if chat_id not in _spy_lobbies: return
    lobby = _spy_lobbies[chat_id]
    active_players = {uid: name for uid, name in lobby["players"].items()
                      if uid not in lobby["eliminated"]}
    if len(active_players) < 2: return

    # Build poll options from active players
    options = [name for name in active_players.values()]
    lobby["poll_player_order"] = list(active_players.keys())   # same index as options

    try:
        poll_msg = await context.bot.send_poll(
            chat_id=chat_id,
            question="🕵️ Vote — Who is the Spy?",
            options=options,
            is_anonymous=False,
            allows_multiple_answers=False,
            open_period=SPY_POLL_SECS,
        )
        lobby["poll_message_id"] = poll_msg.message_id
        lobby["poll_id"]         = poll_msg.poll.id
        lobby["status"]          = "voting"
        lobby["poll_votes"]      = {}   # poll_id -> list of option indices
    except TelegramError as e:
        logger.error(f"Spy poll error: {e}")
        return

    await context.bot.send_message(
        chat_id,
        f"🗳️ *{SPY_POLL_SECS}s voting starts!* Tap the poll above to vote!\n"
        f"_Most votes gets eliminated. Tie or no votes = round continues!_",
        parse_mode="Markdown")

    context.job_queue.run_once(
        _spy_close_poll, when=SPY_POLL_SECS + 2,
        name=f"spy_poll_close_{chat_id}", data={"chat_id": chat_id})


async def _spy_close_poll(context: ContextTypes.DEFAULT_TYPE):
    data = context.job.data; chat_id = data["chat_id"]
    if chat_id not in _spy_lobbies: return
    lobby = _spy_lobbies[chat_id]

    # Tally votes from poll_votes: {answerer_uid: option_index}
    vote_tally: dict[int, int] = {}   # option_index -> count
    voter_choices: dict[int, int] = lobby.get("poll_votes", {})  # uid -> option_idx

    for answerer_uid, opt_idx in voter_choices.items():
        vote_tally[opt_idx] = vote_tally.get(opt_idx, 0) + 1

    player_order = lobby.get("poll_player_order", [])
    active_players = {uid: lobby["players"][uid] for uid in player_order
                      if uid in lobby["players"]}

    # Build vote summary string
    summary_lines = []
    for idx, uid in enumerate(player_order):
        pname = active_players.get(uid, "?")
        votes = vote_tally.get(idx, 0)
        summary_lines.append(f"  {pname}: *{votes}* vote(s)")

    if not vote_tally:
        # No votes cast
        await context.bot.send_message(
            chat_id,
            f"🗳️ *No votes were cast!* Round continues...\n\n" +
            "\n".join(summary_lines),
            parse_mode="Markdown")
        await _spy_next_round_or_continue(context, chat_id)
        return

    max_votes = max(vote_tally.values())
    top_indices = [idx for idx, v in vote_tally.items() if v == max_votes]

    if len(top_indices) > 1:
        # Tie
        tied_names = [active_players.get(player_order[i], "?") for i in top_indices]
        await context.bot.send_message(
            chat_id,
            f"🗳️ *Tie between {', '.join(tied_names)}!* No elimination — round continues...\n\n" +
            "\n".join(summary_lines),
            parse_mode="Markdown")
        await _spy_next_round_or_continue(context, chat_id)
        return

    eliminated_idx = top_indices[0]
    eliminated_uid = player_order[eliminated_idx]
    eliminated_name = active_players.get(eliminated_uid, "?")
    is_spy = eliminated_uid in lobby["spies"]

    await context.bot.send_message(
        chat_id,
        f"🗳️ *Vote Results:*\n" + "\n".join(summary_lines),
        parse_mode="Markdown")

    await asyncio.sleep(1)

    if is_spy:
        # Spy caught! Round ends — reward innocents who voted correctly
        data_store = load_data()
        rewarded = []
        for voter_uid, voted_idx in voter_choices.items():
            voted_target = player_order[voted_idx] if voted_idx < len(player_order) else None
            if voted_target == eliminated_uid and voter_uid not in lobby["spies"]:
                u = get_user(data_store, voter_uid)
                u["coins"] += SPY_INNOCENT_WIN
                u["total_coins_ever"] = u.get("total_coins_ever", 0) + SPY_INNOCENT_WIN
                b = award_badge(u, "spy_catcher")
                rewarded.append((lobby["players"].get(voter_uid, "?"),
                                 SPY_INNOCENT_WIN, f" 🆕{b}" if b else ""))
        save_data(data_store)

        spy_names = ", ".join(lobby["players"].get(s, "?") for s in lobby["spies"])
        reward_str = "\n".join(f"  +{c}🪙 {n}{bl}" for n, c, bl in rewarded) if rewarded else "  (nobody voted correctly)"
        await context.bot.send_message(
            chat_id,
            f"🎉 *{eliminated_name}* was the SPY!\n\n"
            f"🕵️ Spy(s) this round: *{spy_names}*\n"
            f"🔑 The word was: *{lobby['word']}*\n\n"
            f"💰 *Innocent rewards:*\n{reward_str}\n\n"
            f"🏁 Round over! Use `/spy` to play again.",
            parse_mode="Markdown")
        del _spy_lobbies[chat_id]

    else:
        # Wrong person eliminated — spy survives
        lobby["eliminated"].append(eliminated_uid)
        remaining = [uid for uid in lobby["players"] if uid not in lobby["eliminated"]]
        spies_still = [s for s in lobby["spies"] if s not in lobby["eliminated"]]

        # Reward spy for surviving this round
        data_store = load_data()
        for spy_uid in spies_still:
            su = get_user(data_store, spy_uid)
            su["coins"] += SPY_SURVIVE_COINS
            su["total_coins_ever"] = su.get("total_coins_ever", 0) + SPY_SURVIVE_COINS
            lobby["spy_coins_earned"][str(spy_uid)] = \
                lobby["spy_coins_earned"].get(str(spy_uid), 0) + SPY_SURVIVE_COINS
        save_data(data_store)

        spy_earn_str = " | ".join(
            f"{lobby['players'].get(int(s),'?')} +{lobby['spy_coins_earned'].get(s,0)}🪙"
            for s in [str(x) for x in spies_still])

        await context.bot.send_message(
            chat_id,
            f"❌ *{eliminated_name}* was innocent and got eliminated!\n"
            f"😈 The spy is still out there...\n\n"
            f"💰 Spy earned: {spy_earn_str}\n\n"
            f"👥 Remaining: *{len(remaining)}* players",
            parse_mode="Markdown")

        # Check 3-player auto-end rule
        innocents_left = [u for u in remaining if u not in lobby["spies"]]
        if len(remaining) <= 2 or (len(innocents_left) <= 1 and spies_still):
            spy_names = ", ".join(lobby["players"].get(s, "?") for s in lobby["spies"])
            total_earned = sum(lobby["spy_coins_earned"].get(str(s), 0) for s in lobby["spies"])
            await context.bot.send_message(
                chat_id,
                f"🏁 *Too few innocents left — Spy wins!*\n\n"
                f"🕵️ The spy(s) were: *{spy_names}*\n"
                f"🔑 The word was: *{lobby['word']}*\n"
                f"💰 Total spy earnings: *{total_earned}* 🪙\n\n"
                f"Use `/spy` to play again!",
                parse_mode="Markdown")

            # Badge for spy
            data_store = load_data()
            for spy_uid in spies_still:
                su = get_user(data_store, spy_uid)
                b = award_badge(su, "spy_winner")
                if b:
                    await context.bot.send_message(
                        chat_id, f"🆕 {lobby['players'].get(spy_uid,'?')}: {b}")
            save_data(data_store)
            del _spy_lobbies[chat_id]
        else:
            await _spy_next_round_or_continue(context, chat_id)


async def _spy_next_round_or_continue(context, chat_id: int):
    """Start the next discussion round (no new word assignment — same round, same spy)."""
    if chat_id not in _spy_lobbies: return
    lobby = _spy_lobbies[chat_id]
    lobby["status"] = "active"
    active = {uid: name for uid, name in lobby["players"].items()
              if uid not in lobby["eliminated"]}
    await context.bot.send_message(
        chat_id,
        f"🕵️ *Round {lobby['round']} continues!*\n"
        f"Category: *{lobby['category']}*\n"
        f"👥 Active players: *{len(active)}*\n\n"
        f"⏱️ *{SPY_DISCUSSION_SECS}s discussion — then vote again!*",
        parse_mode="Markdown")
    disc_end = datetime.now() + timedelta(seconds=SPY_DISCUSSION_SECS)
    lobby["discussion_end"] = disc_end.isoformat()
    context.job_queue.run_once(
        _spy_end_discussion, when=SPY_DISCUSSION_SECS,
        name=f"spy_discuss_{chat_id}", data={"chat_id": chat_id})


async def handle_spy_poll_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Collect poll answers for the Spy vote."""
    answer = update.poll_answer
    poll_id = answer.poll_id
    voter_uid = answer.user.id
    # Find which chat this poll belongs to
    for chat_id, lobby in _spy_lobbies.items():
        if lobby.get("poll_id") == poll_id:
            if answer.option_ids:
                lobby["poll_votes"][voter_uid] = answer.option_ids[0]
            else:
                lobby["poll_votes"].pop(voter_uid, None)
            break


async def _spy_lobby_expire(context: ContextTypes.DEFAULT_TYPE):
    data = context.job.data; chat_id = data["chat_id"]
    if chat_id not in _spy_lobbies: return
    lobby = _spy_lobbies[chat_id]
    if lobby["status"] != "lobby": return
    if len(lobby["players"]) < 3:
        del _spy_lobbies[chat_id]
        try:
            await context.bot.send_message(
                chat_id,
                "🕵️ *Spy lobby expired!* Not enough players joined.\n"
                "Start fresh with `/spy` 👻", parse_mode="Markdown")
        except: pass




# ══════════════════════════════════════════════════════════════════════════════
#  TRUTH & DARE SYSTEM
# ══════════════════════════════════════════════════════════════════════════════
_tnd_lobbies = {}

async def cmd_truth(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    name = f"@{user.username}" if user.username else user.full_name
    q = random.choice(TRUTHS)
    await update.message.reply_text(f"🙊 *TRUTH for {name}!*\n\n_{q}_", parse_mode="Markdown")

async def cmd_dare(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    name = f"@{user.username}" if user.username else user.full_name
    d = random.choice(DARES)
    await update.message.reply_text(f"🔥 *DARE for {name}!*\n\n_{d}_", parse_mode="Markdown")

async def cmd_tnd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    user    = update.message.from_user
    uid     = user.id
    name    = f"@{user.username}" if user.username else user.full_name
    args = context.args
    sub  = args[0].lower() if args else ""

    if not sub:
        if chat_id in _tnd_lobbies and _tnd_lobbies[chat_id]["status"] in ("lobby","active"):
            lobby = _tnd_lobbies[chat_id]
            if lobby["status"] == "lobby":
                players_list = "\n".join(f"  • {n}" for n in lobby["players"].values())
                await update.message.reply_text(
                    f"🎭 *Truth or Dare lobby already exists!*\n\n"
                    f"👥 Players ({len(lobby['players'])}):\n{players_list}\n\n"
                    f"Use `/tnd join` to join | `/tnd start` to begin (host only)",
                    parse_mode="Markdown")
            else:
                await update.message.reply_text(
                    "🎭 A game is already *in progress*! Use `/tnd end` (host/admin) to stop it first.",
                    parse_mode="Markdown")
            return
        _tnd_lobbies[chat_id] = {
            "host_id":     uid, "host_name":   name,
            "players":     {uid: name}, "status":      "lobby",
            "created_at":  datetime.now().isoformat(),
            "current_player_idx":  0, "player_order": [],
            "player_last_choice":  {}, "consecutive_count": {},
        }
        context.job_queue.run_once(
            _tnd_lobby_expire, when=300,
            name=f"tnd_expire_{chat_id}", data={"chat_id": chat_id})
        await update.message.reply_text(
            f"🎭 *Truth or Dare Lobby Created!*\n━━━━━━━━━━━━━\n"
            f"👑 Host: {name}\n\n"
            f"Others can join with `/tnd join`\n"
            f"Host starts with `/tnd start`\n"
            f"_(Lobby expires in 5 min if only 1 player)_ ⏳",
            parse_mode="Markdown"); return

    if sub == "join":
        if chat_id not in _tnd_lobbies:
            await update.message.reply_text("❌ No TnD lobby! Use `/tnd` to create one.", parse_mode="Markdown"); return
        lobby = _tnd_lobbies[chat_id]
        if lobby["status"] != "lobby":
            await update.message.reply_text("❌ Game already started! Wait for next round."); return
        if uid in lobby["players"]:
            await update.message.reply_text(f"You're already in the lobby {name}! 😄"); return
        lobby["players"][uid] = name
        await update.message.reply_text(
            f"✅ *{name}* joined!\n👥 Players: *{len(lobby['players'])}*",
            parse_mode="Markdown"); return

    if sub == "leave":
        if chat_id not in _tnd_lobbies:
            await update.message.reply_text("❌ No active TnD lobby!"); return
        lobby = _tnd_lobbies[chat_id]
        if uid not in lobby["players"]:
            await update.message.reply_text("You're not in the lobby!"); return
        del lobby["players"][uid]
        await update.message.reply_text(f"👋 *{name}* left.", parse_mode="Markdown")
        if uid == lobby["host_id"]:
            if lobby["players"]:
                new_host_id = next(iter(lobby["players"]))
                lobby["host_id"] = new_host_id; lobby["host_name"] = lobby["players"][new_host_id]
                await update.message.reply_text(f"👑 {lobby['host_name']} is now the host!")
            else:
                del _tnd_lobbies[chat_id]; await update.message.reply_text("🎭 Lobby closed — everyone left!")
        return

    if sub == "start":
        if chat_id not in _tnd_lobbies:
            await update.message.reply_text("❌ No TnD lobby!", parse_mode="Markdown"); return
        lobby = _tnd_lobbies[chat_id]
        if uid != lobby["host_id"]:
            await update.message.reply_text("❌ Only the host can start!"); return
        if len(lobby["players"]) < 2:
            await update.message.reply_text("❌ Need at least 2 players!", parse_mode="Markdown"); return
        if lobby["status"] == "active":
            await update.message.reply_text("Game already running!"); return
        for job in context.job_queue.get_jobs_by_name(f"tnd_expire_{chat_id}"): job.schedule_removal()
        lobby["status"] = "active"
        lobby["player_order"] = list(lobby["players"].keys())
        random.shuffle(lobby["player_order"])
        lobby["current_player_idx"] = 0
        lobby["player_last_choice"] = {}
        lobby["consecutive_count"] = {uid: {"truth": 0, "dare": 0} for uid in lobby["players"]}
        order_str = "\n".join(f"  {i+1}. {lobby['players'][p]}" for i, p in enumerate(lobby["player_order"]))
        first_uid  = lobby["player_order"][0]
        first_name = lobby["players"][first_uid]
        sent = await update.message.reply_text(
            f"🎭 *Truth or Dare — STARTED!*\n━━━━━━━━━━━━━\n"
            f"🎲 Play order:\n{order_str}\n\n"
            f"🎤 First up: *{first_name}*\nChoose your fate! 👇\n"
            f"_(If no choice in {TND_TURN_TIMEOUT}s, Aira will auto-skip!)_",
            parse_mode="Markdown", reply_markup=_tnd_keyboard(first_uid, lobby))
        _schedule_tnd_choice_timeout(context, chat_id, sent.message_id, first_uid, lobby)
        return

    if sub == "end":
        if chat_id not in _tnd_lobbies:
            await update.message.reply_text("No active TnD game!"); return
        lobby = _tnd_lobbies[chat_id]
        if uid != lobby["host_id"] and not await is_admin(context.bot, chat_id, uid):
            await update.message.reply_text("❌ Only the host or an admin can end!"); return
        del _tnd_lobbies[chat_id]
        for job in context.job_queue.get_jobs_by_name(f"tnd_expire_{chat_id}"): job.schedule_removal()
        for job in context.job_queue.get_jobs_by_name(f"tnd_autonext_{chat_id}"): job.schedule_removal()
        await update.message.reply_text(
            f"🎭 *Truth or Dare ended!* Thanks for playing 🙌\nStart a new one with `/tnd`", parse_mode="Markdown")
        return

    await update.message.reply_text(
        "🎭 *Truth or Dare Commands:*\n"
        "`/tnd` — Create lobby\n`/tnd join` — Join\n`/tnd leave` — Leave\n"
        "`/tnd start` — Start (host)\n`/tnd end` — End (host/admin)\n\n"
        "Quick: `/truth` or `/dare`", parse_mode="Markdown")


def _tnd_keyboard(current_uid, lobby):
    counts = lobby["consecutive_count"].get(current_uid, {"truth": 0, "dare": 0})
    truth_blocked = counts["truth"] >= 2; dare_blocked = counts["dare"] >= 2
    truth_label = "🙊 Truth" + (" (blocked)" if truth_blocked else "")
    dare_label  = "🔥 Dare"  + (" (blocked)" if dare_blocked  else "")
    return InlineKeyboardMarkup([[
        InlineKeyboardButton(truth_label, callback_data=f"tnd_truth_{current_uid}"),
        InlineKeyboardButton(dare_label,  callback_data=f"tnd_dare_{current_uid}"),
    ]])

def _schedule_tnd_choice_timeout(context, chat_id, message_id, current_uid, lobby):
    for job in context.job_queue.get_jobs_by_name(f"tnd_autonext_{chat_id}"): job.schedule_removal()
    context.job_queue.run_once(
        _tnd_auto_advance, when=TND_TURN_TIMEOUT,
        name=f"tnd_autonext_{chat_id}",
        data={"chat_id": chat_id, "message_id": message_id, "stage": "choosing",
              "player_idx_at_schedule": lobby["current_player_idx"]})

def _schedule_tnd_next_timeout(context, chat_id, message_id, lobby):
    for job in context.job_queue.get_jobs_by_name(f"tnd_autonext_{chat_id}"): job.schedule_removal()
    context.job_queue.run_once(
        _tnd_auto_advance, when=TND_TURN_TIMEOUT,
        name=f"tnd_autonext_{chat_id}",
        data={"chat_id": chat_id, "message_id": message_id, "stage": "revealed",
              "player_idx_at_schedule": lobby["current_player_idx"]})

async def _advance_tnd_turn(context, chat_id, message_id, lobby):
    lobby["current_player_idx"] = (lobby["current_player_idx"] + 1) % len(lobby["player_order"])
    next_uid  = lobby["player_order"][lobby["current_player_idx"]]
    next_name = lobby["players"].get(next_uid, "Player")
    try:
        await context.bot.edit_message_text(
            chat_id=chat_id, message_id=message_id,
            text=f"🎭 *Next up: {next_name}!*\nChoose your fate 👇\n_(If no choice in {TND_TURN_TIMEOUT}s, Aira will auto-skip!)_",
            parse_mode="Markdown", reply_markup=_tnd_keyboard(next_uid, lobby))
    except BadRequest: pass
    _schedule_tnd_choice_timeout(context, chat_id, message_id, next_uid, lobby)

async def _tnd_auto_advance(context: ContextTypes.DEFAULT_TYPE):
    d = context.job.data; chat_id = d["chat_id"]
    if chat_id not in _tnd_lobbies: return
    lobby = _tnd_lobbies[chat_id]
    if lobby["status"] != "active": return
    if lobby["current_player_idx"] != d.get("player_idx_at_schedule"): return
    try:
        if d.get("stage") == "choosing":
            stuck_uid  = lobby["player_order"][lobby["current_player_idx"]]
            stuck_name = lobby["players"].get(stuck_uid, "Player")
            try:
                await context.bot.edit_message_text(
                    chat_id=chat_id, message_id=d["message_id"],
                    text=f"⌛ *{stuck_name}* took too long!\nSkipping...", parse_mode="Markdown")
            except BadRequest: pass
            await _advance_tnd_turn(context, chat_id, d["message_id"], lobby)
        else:
            await _advance_tnd_turn(context, chat_id, d["message_id"], lobby)
    except Exception as e:
        logger.error(f"_tnd_auto_advance error: {e}")

async def handle_tnd_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    try: await query.answer()
    except BadRequest: pass
    parts = query.data.split("_"); choice = parts[1]; target_uid = int(parts[2])
    chat_id = query.message.chat_id; clicker_id = query.from_user.id
    if chat_id not in _tnd_lobbies:
        try: await query.edit_message_text("❌ Game ended!")
        except BadRequest: pass
        return
    lobby = _tnd_lobbies[chat_id]
    if lobby["status"] != "active":
        await query.answer("Game is not active!", show_alert=True); return
    if clicker_id != target_uid:
        await query.answer("It's not your turn! 😤", show_alert=True); return
    counts = lobby["consecutive_count"].setdefault(target_uid, {"truth": 0, "dare": 0})
    if choice == "truth" and counts["truth"] >= 2:
        await query.answer("Can't pick Truth 3x in a row! Choose Dare 🔥", show_alert=True); return
    if choice == "dare" and counts["dare"] >= 2:
        await query.answer("Can't pick Dare 3x in a row! Choose Truth 🙊", show_alert=True); return
    if choice == "truth":
        counts["truth"] += 1; counts["dare"] = 0
        question = random.choice(TRUTHS); icon = "🙊"; label = "TRUTH"
    else:
        counts["dare"] += 1; counts["truth"] = 0
        question = random.choice(DARES); icon = "🔥"; label = "DARE"
    player_name = lobby["players"].get(target_uid, "Player")
    try:
        await query.edit_message_text(
            f"{icon} *{player_name}* chose *{label}!*\n━━━━━━━━━━━━━\n\n_{question}_\n\n"
            f"_(Do it, then hit Next — or Aira auto-skips in {TND_TURN_TIMEOUT}s!)_",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("⏭️ Next Player", callback_data=f"tnd_next_{target_uid}")]]))
    except BadRequest: pass
    _schedule_tnd_next_timeout(context, chat_id, query.message.message_id, lobby)

async def handle_tnd_next(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    try: await query.answer()
    except BadRequest: pass
    parts = query.data.split("_"); prev_uid = int(parts[2]); chat_id = query.message.chat_id
    if chat_id not in _tnd_lobbies:
        try: await query.edit_message_text("Game has ended!")
        except BadRequest: pass
        return
    lobby = _tnd_lobbies[chat_id]
    if lobby["status"] != "active":
        try: await query.edit_message_text("Game ended.")
        except BadRequest: pass
        return
    if query.from_user.id not in (prev_uid, lobby["host_id"]):
        await query.answer("Only the current player or host!", show_alert=True); return
    for job in context.job_queue.get_jobs_by_name(f"tnd_autonext_{chat_id}"): job.schedule_removal()
    await _advance_tnd_turn(context, chat_id, query.message.message_id, lobby)

async def _tnd_lobby_expire(context: ContextTypes.DEFAULT_TYPE):
    data = context.job.data; chat_id = data["chat_id"]
    if chat_id not in _tnd_lobbies: return
    lobby = _tnd_lobbies[chat_id]
    if lobby["status"] != "lobby": return
    if len(lobby["players"]) <= 1:
        del _tnd_lobbies[chat_id]
        try:
            await context.bot.send_message(
                chat_id, "🎭 *TnD lobby expired!* Start a new one with `/tnd` 👻", parse_mode="Markdown")
        except: pass







# ══════════════════════════════════════════════════════════════════════════════
#  TITLE / ADMIN TAG
# ══════════════════════════════════════════════════════════════════════════════
async def set_member_tag(bot, chat_id, user_id, title):
    title = title[:16]
    try:
        await bot.set_chat_administrator_custom_title(chat_id=chat_id,user_id=user_id,custom_title=title)
        return True,"direct"
    except TelegramError:
        pass
    try:
        await bot.promote_chat_member(chat_id=chat_id,user_id=user_id,
            can_manage_chat=False,can_delete_messages=False,can_manage_video_chats=False,
            can_restrict_members=False,can_promote_members=False,can_change_info=False,
            can_invite_users=True,can_pin_messages=False)
        await asyncio.sleep(0.5)
        await bot.set_chat_administrator_custom_title(chat_id=chat_id,user_id=user_id,custom_title=title)
        return True,"promoted"
    except TelegramError as e:
        return False,str(e)

async def remove_member_tag(bot, chat_id, user_id):
    try:
        member = await bot.get_chat_member(chat_id,user_id)
        if member.status=="creator":
            try: await bot.set_chat_administrator_custom_title(chat_id=chat_id,user_id=user_id,custom_title="")
            except: pass
            return
        await bot.promote_chat_member(chat_id=chat_id,user_id=user_id,
            can_manage_chat=False,can_delete_messages=False,can_manage_video_chats=False,
            can_restrict_members=False,can_promote_members=False,can_change_info=False,
            can_invite_users=False,can_pin_messages=False)
    except TelegramError as e:
        logger.error(f"remove_member_tag: {e}")

async def expire_title_job(context: ContextTypes.DEFAULT_TYPE):
    d = context.job.data; uid,chat_id,name = d["user_id"],d["chat_id"],d["name"]
    data = load_data(); u = data["users"].get(str(uid))
    if u: u["title"]=None;u["title_expiry"]=None;u["title_chat_id"]=None;save_data(data)
    await remove_member_tag(context.bot,chat_id,uid)
    try: await context.bot.send_message(chat_id,f"⌛ {name}'s member tag expired and was removed.")
    except: pass

# ══════════════════════════════════════════════════════════════════════════════
#  HUNT
# ══════════════════════════════════════════════════════════════════════════════
def roll_animal():
    if random.randint(1, 1_000_000) == 777:
        mythic = next((a for a in ANIMALS if a["rarity"] == "mythic"), None)
        if mythic: return mythic
    pool = []
    for a in ANIMALS:
        if a["rarity"] != "mythic":
            pool.extend([a] * RARITY_WEIGHTS[a["rarity"]])
    return random.choice(pool)

async def do_hunt(bot, chat_id, user_id, username=None, full_name=None):
    db  = _get_db(); uid = str(user_id)
    doc = db["users"].find_one({"_id": uid})
    if doc:
        doc.pop("_id", None); u = doc
        if username:  u["username"]  = username
        if full_name: u["full_name"] = full_name
    else:
        u = {"username": username or "Unknown","full_name": full_name or "Unknown",
             "coins":0,"wins":0,"streak":0,"best_streak":0,"badges":[],
             "title":None,"title_expiry":None,"title_chat_id":None,"title_purchased":False,
             "double_coins":False,"weekly_wins":0,"last_win_date":None,
             "pin_token":False,"shield_expiry":None,
             "owo":0,"animals":[],"hunts":0,"hunt_cooldown":None,
             "owo_boost_expiry":None,"auto_hunt":False,"total_coins_ever":0,
             "daily_claimed":None,"daily_streak":0,"today_wins":0,"today_date":None,
             "gems":0,"weapon":"stick","afk":None,"afk_since":None,"afk_pings":[],
             "casino_wins":0,"casino_total_won":0,"xp":0,"level":1,
             "battle_team":[],"last_pray":None,"pray_active":False,"pray_expires":None,}
    cooldown = u.get("hunt_cooldown")
    if cooldown:
        try:
            rem = (datetime.fromisoformat(cooldown) - datetime.now()).total_seconds()
            if rem > 0: return f"⏳ Hunt cooldown: *{int(rem)}s* left. Patience! 🌿"
        except: pass
    cd_mult = get_cooldown_multiplier(u)
    u["hunt_cooldown"] = (datetime.now()+timedelta(seconds=int(15*cd_mult))).isoformat()
    weapon_key  = u.get("weapon", "stick"); weapon = WEAPONS.get(weapon_key, WEAPONS["stick"])
    catch_bonus = weapon["catch_bonus"]; pray_bonus = 0.10 if has_pray_buff(u) else 0
    catch_rate  = min(0.97, 0.55 + catch_bonus/100 + pray_bonus)
    if random.random() > catch_rate:
        db["users"].replace_one({"_id": uid}, {"_id": uid, **u}, upsert=True)
        return random.choice(HUNT_FAILS)
    animal  = roll_animal(); owo_e = animal["owo"]; coins_e = animal["coins"]; gems_e = animal["gems"]
    atk_b   = weapon["atk_bonus"]; coins_e = int(coins_e * (1 + atk_b / 100))
    boost = u.get("owo_boost_expiry")
    if boost:
        try:
            if datetime.fromisoformat(boost)>datetime.now(): owo_e*=2; coins_e*=2; gems_e*=2
        except: pass
    if u.get("double_coins"): coins_e *= 2; u["double_coins"] = False
    u["owo"] = u.get("owo",0)+owo_e; u["coins"] = u.get("coins",0)+coins_e
    u["gems"] = u.get("gems",0)+gems_e; u["total_coins_ever"] = u.get("total_coins_ever",0)+coins_e
    u["hunts"] = u.get("hunts",0)+1
    zoo = u.get("animals",[]); found = next((z for z in zoo if z["name"]==animal["name"]),None)
    if found: found["count"] = found.get("count",1)+1
    else:
        if len(zoo)<50: zoo.append({"name":animal["name"],"rarity":animal["rarity"],"count":1})
        else:
            same = [z for z in zoo if z.get("rarity")==animal["rarity"]]
            if same: same[0]["count"] = same[0].get("count",1)+1
    u["animals"] = zoo
    lvl_up = add_xp(u,10); badges = check_badges(u)
    if animal["rarity"] in ("rare","epic","legendary","Extreme","mythic"):
        b=award_badge(u,"rare_hunt");
        if b: badges.append(b)
    if animal["rarity"] in ("legendary","Extreme","mythic"):
        b=award_badge(u,"legend_hunt");
        if b: badges.append(b)
    if animal["rarity"]=="mythic":
        b=award_badge(u,"mythic_catch");
        if b: badges.append(b)
    db["users"].replace_one({"_id": uid}, {"_id": uid, **u}, upsert=True)
    icon = RARITY_COLORS.get(animal["rarity"],"⬜"); wname = weapon["name"]
    badge_line = "\n🆕 "+" | ".join(badges) if badges else ""
    lvl_line = f"\n⬆️ *LEVEL UP! → Lv{u['level']}*" if lvl_up else ""
    if animal["rarity"]=="mythic":
        try:
            name_display = f"@{username}" if username and username!="Unknown" else full_name or "Someone"
            await bot.send_message(chat_id,
                f"🌈✨ *MYTHIC CATCH!* ✨🌈\n━━━━━━━━━━━━━━━━━━\n"
                f"🎊 *{name_display}* just caught a\n*🕊️ Rara avis* 🌈*MYTHIC*\n\n"
                f"The odds were *1 in 1,000,000!*\nThis may never happen again! 🔥",
                parse_mode="Markdown")
        except: pass
    return (f"🎯 *Hunt successful!* _{wname}_\n"
            f"Caught {animal['name']} {icon}*{animal['rarity'].upper()}*\n"
            f"+{owo_e} OWO | +{coins_e} 🪙 | +{gems_e} 💎{badge_line}{lvl_line}\n"
            f"_OWO:{u['owo']} Coins:{u['coins']} Gems:{u['gems']}_")

# ══════════════════════════════════════════════════════════════════════════════
#  CHALLENGE WIN
# ══════════════════════════════════════════════════════════════════════════════
async def process_win(update, context, user, chat_id, challenge, extra_badge=None):
    data  = load_data(); group = get_group(data,chat_id); group["active_challenge"]=None
    for job in context.job_queue.get_jobs_by_name(f"expire_{chat_id}"): job.schedule_removal()
    u = get_user(data,user.id,user.username,user.full_name); coins = challenge["coins"]
    today = datetime.now().date().isoformat(); yest = (datetime.now().date()-timedelta(days=1)).isoformat()
    if u.get("last_win_date")==today:       u["streak"]+=1
    elif u.get("last_win_date")==yest:      u["streak"]+=1
    else:                                   u["streak"]=1
    u["last_win_date"]=today
    if u["streak"]>u.get("best_streak",0): u["best_streak"]=u["streak"]
    streak_bonus=(u["streak"]-1)*STREAK_BONUS; coins+=streak_bonus
    booster_line=""
    if u.get("double_coins"): coins*=2;u["double_coins"]=False;booster_line="\n⚡ Double Booster!"
    u["coins"]+=coins; u["total_coins_ever"]=u.get("total_coins_ever",0)+coins
    u["wins"]+=1; u["weekly_wins"]=u.get("weekly_wins",0)+1
    today_str=datetime.now().date().isoformat()
    if u.get("today_date")!=today_str: u["today_date"]=today_str;u["today_wins"]=0
    u["today_wins"]=u.get("today_wins",0)+1
    lvl_up = add_xp(u,20); earned = check_badges(u)
    if extra_badge:
        b=award_badge(u,extra_badge);
        if b: earned.append(b)
    save_data(data)
    name  = f"@{user.username}" if user.username else user.full_name
    title = f"\n👑 *{u['title']}*" if u.get("title") else ""
    bonus = f" (+{streak_bonus} streak)" if streak_bonus else ""
    s_line= f"🔥 Streak: {u['streak']}x" if u["streak"]>1 else ""
    lvl_line=f"\n⬆️ *LEVEL UP! → Lv{u['level']}*" if lvl_up else ""
    msg=(f"🎉 *{name}* wins!{title}\n"
         f"💰 +{coins} Forge Coins{bonus}{booster_line}\n"
         f"🏦 Total:{u['coins']} | 🏆Wins:{u['wins']}{lvl_line}\n{s_line}")
    if earned: msg+="\n\n🆕 *Badges!*\n"+"".join(f"  {b}\n" for b in earned)
    await update.message.reply_text(msg,parse_mode="Markdown")
    await schedule_next(context,chat_id)



# ══════════════════════════════════════════════════════════════════════════════
#  CHALLENGE POST / EXPIRE / SCHEDULE  — uses AI generation
# ══════════════════════════════════════════════════════════════════════════════
async def post_challenge(context, chat_id, question=None):
    group = get_group_db(chat_id)
    if group["active_challenge"]: return
    q     = question or await get_challenge_question(chat_id)
    mult  = group.get("forge_war_multiplier",1); coins=q["coins"]*mult
    group["active_challenge"]={"question":q["q"],"answers":[a.lower() for a in q["a"]],
        "hint":q["hint"],"coins":coins,"type":q.get("type","trivia"),
        "started_at":datetime.now().isoformat()}
    group["last_challenge_time"]=datetime.now().isoformat()
    save_group_db(chat_id, group)
    fw = f"\n⚔️ *FORGE WAR!* Rewards ×{mult}!\n" if group.get("forge_war") else ""
    tips={"image":"\n📸 *Send a photo to win!*","word":"\n⚡ *Type the exact word!*",
          "math":"\n🔢 *Type the answer!*","trivia":"\n💬 *Type the answer!*"}
    tip=tips.get(q.get("type","trivia"),"")
    await context.bot.send_message(chat_id,
        f"⚡ *NEW CHALLENGE!*{fw}\n{q['q']}\n\n💰 *{coins} Forge Coins*\n⏱️ 5 min!{tip}",
        parse_mode="Markdown")
    context.job_queue.run_once(expire_challenge,when=CHALLENGE_TIMEOUT,
        chat_id=chat_id,name=f"expire_{chat_id}")

async def expire_challenge(context):
    cid = context.job.chat_id; group = get_group_db(cid)
    if not group["active_challenge"]: return
    q = group["active_challenge"]["question"]; group["active_challenge"]=None
    save_group_db(cid, group)
    await context.bot.send_message(cid,
        f"⌛ *Time's up!* No one answered.\n_{q}_\n\nBetter luck! 💪",parse_mode="Markdown")

async def schedule_next(context, chat_id):
    delay=random.randint(INTERVAL_MIN,INTERVAL_MAX)
    context.job_queue.run_once(
        lambda ctx: asyncio.ensure_future(post_challenge(ctx,chat_id)),
        when=delay,chat_id=chat_id,name=f"auto_{chat_id}")

# ══════════════════════════════════════════════════════════════════════════════
#  AUTO-CHALLENGE EVERY 5-6 MIN  — respects on/off toggle  (PATCH 2)
# ══════════════════════════════════════════════════════════════════════════════
_auto_challenge_chats = set()

async def _auto_challenge_tick(context: ContextTypes.DEFAULT_TYPE):
    chat_id = context.job.data["chat_id"]
    try:
        group = get_group_db(chat_id)
        # PATCH 2: only post if auto_challenge_enabled is True
        if group.get("auto_challenge_enabled", True) and not group.get("active_challenge"):
            await post_challenge(context, chat_id)
    except Exception as e:
        logger.error(f"auto_challenge_tick error for {chat_id}: {e}")
    delay = random.randint(AUTO_CHALLENGE_MIN, AUTO_CHALLENGE_MAX)
    context.job_queue.run_once(
        _auto_challenge_tick, when=delay, chat_id=chat_id,
        name=f"autochallenge_{chat_id}", data={"chat_id": chat_id})

def ensure_auto_challenge(context: ContextTypes.DEFAULT_TYPE, chat_id: int):
    if chat_id in _auto_challenge_chats or chat_id >= 0:
        return
    _auto_challenge_chats.add(chat_id)
    delay = random.randint(AUTO_CHALLENGE_MIN, AUTO_CHALLENGE_MAX)
    context.job_queue.run_once(
        _auto_challenge_tick, when=delay, chat_id=chat_id,
        name=f"autochallenge_{chat_id}", data={"chat_id": chat_id})

# ══════════════════════════════════════════════════════════════════════════════
#  MESSAGE HANDLER
# ══════════════════════════════════════════════════════════════════════════════
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message: return
    chat_id = update.message.chat_id; user = update.message.from_user; text = update.message.text or ""

    ensure_auto_challenge(context, chat_id)

    pending_chess = _chess_setup.get(user.id)
    if pending_chess and pending_chess.get("awaiting_custom_time") and text.strip():
        await _handle_chess_custom_time(update, context, pending_chess); return

    data = load_data(); u = get_user(data, user.id, user.username, user.full_name)

    if text.lower().startswith("!status "):
        reason = text[8:].strip()
        if reason:
            u["afk"] = reason; u["afk_since"] = datetime.now().isoformat(); u["afk_pings"] = []
            save_data(data)
            name = f"@{user.username}" if user.username else user.full_name
            await update.message.reply_text(
                f"😴 *{name}* is now AFK\nReason: _{reason}_\n"
                f"_Aira will notify them of pings!_", parse_mode="Markdown"); return

    if u.get("afk"):
        afk_since = datetime.fromisoformat(u["afk_since"]); duration = fmt_duration((datetime.now()-afk_since).total_seconds())
        pings = u.get("afk_pings",[]); u["afk"]=None; u["afk_since"]=None; u["afk_pings"]=[]; save_data(data)
        ping_summary = ("\n\n📬 *Missed pings:*\n" + "\n".join(pings[-10:])) if pings else ""
        name = f"@{user.username}" if user.username else user.full_name
        await update.message.reply_text(f"👋 Welcome back *{name}*!\nAFK for *{duration}*{ping_summary}",parse_mode="Markdown")

    if update.message.reply_to_message:
        target = update.message.reply_to_message.from_user
        tdata = load_data(); tu = tdata["users"].get(str(target.id))
        if tu and tu.get("afk"):
            tname = f"@{target.username}" if target.username else target.full_name
            sname = f"@{user.username}" if user.username else user.full_name
            tu["afk_pings"] = tu.get("afk_pings",[]) + [f"  • {sname} replied: \"{text[:60]}\""]
            save_data(tdata)
            await update.message.reply_text(f"😴 *{tname}* is AFK\nReason: _{tu['afk']}_",parse_mode="Markdown")

    if text and update.message.entities:
        for entity in update.message.entities:
            if entity.type == "mention":
                mentioned = text[entity.offset:entity.offset+entity.length].lstrip("@")
                mdata = load_data()
                for uid, mu in mdata["users"].items():
                    if mu.get("username","").lower()==mentioned.lower() and mu.get("afk"):
                        sname = f"@{user.username}" if user.username else user.full_name
                        mu["afk_pings"] = mu.get("afk_pings",[]) + [f"  • {sname} mentioned you: \"{text[:60]}\""]
                        save_data(mdata)
                        await update.message.reply_text(f"😴 *@{mu['username']}* is AFK\nReason: _{mu['afk']}_",parse_mode="Markdown"); break

    # Cheat codes
    raw = text.strip(); rawU = raw.upper(); parts = raw.split()

    if parts and parts[0].upper() == EVERGREEN_COINS_CODE.upper():
        amount = 200
        if len(parts) >= 2:
            try: amount = max(1, min(int(parts[1]), 100000))
            except: amount = 200
        fresh = load_data(); fu = get_user(fresh,user.id,user.username,user.full_name)
        fu["coins"]+=amount; fu["total_coins_ever"]=fu.get("total_coins_ever",0)+amount; save_data(fresh)
        name = f"@{user.username}" if user.username else user.full_name
        await update.message.reply_text(f"♾️ *Evergreen code!* {name} +*{amount}* 🪙\nBalance: *{fu['coins']}*",parse_mode="Markdown"); return

    if parts and parts[0].upper() == EVERGREEN_ADMIN_CODE.upper():
        if len(parts) >= 3:
            target_uname = parts[1].lstrip("@").lower()
            try: delta = int(parts[2])
            except:
                await update.message.reply_text("Usage: `AIRA-GOD-MODE-9Z @username +500`",parse_mode="Markdown"); return
            fresh = load_data()
            target_uid = next((uid for uid,u2 in fresh["users"].items() if u2.get("username","").lower()==target_uname),None)
            if not target_uid: await update.message.reply_text(f"❌ User @{target_uname} not found."); return
            tu2 = fresh["users"][target_uid]; tu2["coins"] = max(0,tu2.get("coins",0)+delta)
            if delta>0: tu2["total_coins_ever"]=tu2.get("total_coins_ever",0)+delta
            save_data(fresh)
            action = f"+{delta}" if delta>=0 else str(delta)
            await update.message.reply_text(f"⚙️ Admin override: @{target_uname} coins {action}\nNew balance: *{tu2['coins']}* 🪙",parse_mode="Markdown"); return
        else:
            await update.message.reply_text("Usage: `AIRA-GOD-MODE-9Z @username +500`",parse_mode="Markdown"); return

    if rawU in CHEAT_CODES:
        used = data.get("used_codes",[]); 
        if rawU in used: await update.message.reply_text("❌ Code already used!"); return
        reward=CHEAT_CODES[rawU]; used.append(rawU); data["used_codes"]=used
        fresh2=load_data(); fu2=get_user(fresh2,user.id,user.username,user.full_name)
        fu2["coins"]+=reward; fu2["total_coins_ever"]=fu2.get("total_coins_ever",0)+reward
        b=award_badge(fu2,"cheat_user"); save_data(fresh2)
        name=f"@{user.username}" if user.username else user.full_name
        bl=f"\n🆕 {b}" if b else ""
        await update.message.reply_text(f"🔑 *Code accepted!* {name} +*{reward}* 🪙{bl}\n_(Code disabled forever)_",parse_mode="Markdown"); return

    # Challenge answer
    group = get_group(data,chat_id); challenge=group.get("active_challenge")
    if challenge:
        ctype = challenge.get("type","trivia")
        if ctype=="image":
            if update.message.photo:
                await process_win(update,context,user,chat_id,challenge,"image_win")
        elif text:
            ans = text.strip().lower()
            if ans in challenge["answers"]:
                extra="speed_win" if ctype in ("word","speed") else None
                await process_win(update,context,user,chat_id,challenge,extra); return

    # Aira personality chat
    try:
        bot_me = await context.bot.get_me(); bot_username = bot_me.username
    except:
        bot_username = "AiraBot"
    if _should_aira_reply(update, bot_username) and text:
        user_name = f"@{user.username}" if user.username else user.full_name
        clean_text = re.sub(rf'@{re.escape(bot_username)}', '', text, flags=re.IGNORECASE).strip() or text
        try: await context.bot.send_chat_action(chat_id, "typing")
        except: pass
        reply = await groq_chat(chat_id, user_name, clean_text)
        await update.message.reply_text(reply)

  

# ══════════════════════════════════════════════════════════════════════════════
#  WELCOMER / BYE
# ══════════════════════════════════════════════════════════════════════════════
DEFAULT_WELCOME = "👋 Welcome to the group, {name}! 🎉\nType /start to begin your adventure with Aira!"
DEFAULT_BYE     = "👋 Goodbye {name}, we'll miss you! 💙"

async def handle_member_update(update: Update, context: ContextTypes.DEFAULT_TYPE):
    result = update.chat_member
    if not result: return
    chat_id = result.chat.id; old_stat = result.old_chat_member.status
    new_stat = result.new_chat_member.status; member = result.new_chat_member.user
    name = f"@{member.username}" if member.username else member.full_name
    group = get_group_db(chat_id)
    if old_stat in ("left","kicked") and new_stat in ("member","restricted"):
        msg = (group.get("welcome_msg") or DEFAULT_WELCOME).replace("{name}",name).replace("{username}",name)
        try: await context.bot.send_message(chat_id,msg,parse_mode="Markdown")
        except TelegramError: pass
    elif old_stat in ("member","restricted","administrator") and new_stat in ("left","kicked"):
        msg = (group.get("bye_msg") or DEFAULT_BYE).replace("{name}",name).replace("{username}",name)
        try: await context.bot.send_message(chat_id,msg,parse_mode="Markdown")
        except TelegramError: pass

async def cmd_setwelcome(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    if not await is_admin(context.bot,chat_id,update.message.from_user.id):
        await update.message.reply_text("⚠️ Admins only!"); return
    if not context.args:
        await update.message.reply_text("Usage: `/setwelcome Welcome {name}!`",parse_mode="Markdown"); return
    msg = " ".join(context.args); group = get_group_db(chat_id)
    group["welcome_msg"]=msg; save_group_db(chat_id,group)
    await update.message.reply_text(f"✅ Welcome message set!\nPreview: {msg.replace('{name}','[User]')}",parse_mode="Markdown")

async def cmd_setbye(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    if not await is_admin(context.bot,chat_id,update.message.from_user.id):
        await update.message.reply_text("⚠️ Admins only!"); return
    if not context.args:
        await update.message.reply_text("Usage: `/setbye Bye {name}!`",parse_mode="Markdown"); return
    msg = " ".join(context.args); group = get_group_db(chat_id)
    group["bye_msg"]=msg; save_group_db(chat_id,group)
    await update.message.reply_text(f"✅ Bye message set!\nPreview: {msg.replace('{name}','[User]')}",parse_mode="Markdown")

# ══════════════════════════════════════════════════════════════════════════════
#  ADMIN TOOLS
# ══════════════════════════════════════════════════════════════════════════════
async def is_admin(bot, chat_id, user_id):
    try:
        m = await bot.get_chat_member(chat_id,user_id)
        return m.status in ("administrator","creator")
    except: return False

async def get_target(update, context):
    if update.message.reply_to_message:
        return update.message.reply_to_message.from_user, None
    return None, "Reply to a user's message to target them."

async def cmd_ban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id=update.message.chat_id
    if not await is_admin(context.bot,chat_id,update.message.from_user.id):
        await update.message.reply_text("⚠️ Admins only!"); return
    target,err = await get_target(update,context)
    if err: await update.message.reply_text(err); return
    reason = " ".join(context.args) if context.args else "No reason given"
    try:
        await context.bot.ban_chat_member(chat_id,target.id)
        name=f"@{target.username}" if target.username else target.full_name
        await update.message.reply_text(f"🔨 *{name}* banned.\nReason: _{reason}_",parse_mode="Markdown")
    except TelegramError as e: await update.message.reply_text(f"❌ _{e}_",parse_mode="Markdown")

async def cmd_unban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id=update.message.chat_id
    if not await is_admin(context.bot,chat_id,update.message.from_user.id):
        await update.message.reply_text("⚠️ Admins only!"); return
    target,err = await get_target(update,context)
    if err: await update.message.reply_text(err); return
    try:
        await context.bot.unban_chat_member(chat_id,target.id,only_if_banned=True)
        name=f"@{target.username}" if target.username else target.full_name
        await update.message.reply_text(f"✅ *{name}* unbanned!",parse_mode="Markdown")
    except TelegramError as e: await update.message.reply_text(f"❌ _{e}_",parse_mode="Markdown")

async def cmd_kick(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id=update.message.chat_id
    if not await is_admin(context.bot,chat_id,update.message.from_user.id):
        await update.message.reply_text("⚠️ Admins only!"); return
    target,err = await get_target(update,context)
    if err: await update.message.reply_text(err); return
    reason = " ".join(context.args) if context.args else "No reason given"
    try:
        await context.bot.ban_chat_member(chat_id,target.id)
        await context.bot.unban_chat_member(chat_id,target.id)
        name=f"@{target.username}" if target.username else target.full_name
        await update.message.reply_text(f"👢 *{name}* kicked.\nReason: _{reason}_",parse_mode="Markdown")
    except TelegramError as e: await update.message.reply_text(f"❌ _{e}_",parse_mode="Markdown")

async def cmd_timeout(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id=update.message.chat_id
    if not await is_admin(context.bot,chat_id,update.message.from_user.id):
        await update.message.reply_text("⚠️ Admins only!"); return
    target,err = await get_target(update,context)
    if err: await update.message.reply_text(err); return
    data=load_data(); tu=data["users"].get(str(target.id))
    if tu and has_shield(tu):
        tname=f"@{target.username}" if target.username else target.full_name
        await update.message.reply_text(f"🛡️ *{tname}* has a shield!",parse_mode="Markdown"); return
    mins=5
    if context.args:
        try: mins=max(1,min(int(context.args[-1]),1440))
        except: pass
    until=datetime.now()+timedelta(minutes=mins)
    try:
        await context.bot.restrict_chat_member(chat_id,target.id,
            permissions=ChatPermissions(can_send_messages=False),until_date=until)
        name=f"@{target.username}" if target.username else target.full_name
        await update.message.reply_text(f"🔇 *{name}* muted for *{mins}m*.",parse_mode="Markdown")
    except TelegramError as e: await update.message.reply_text(f"❌ _{e}_",parse_mode="Markdown")

async def cmd_untimeout(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id=update.message.chat_id
    if not await is_admin(context.bot,chat_id,update.message.from_user.id):
        await update.message.reply_text("⚠️ Admins only!"); return
    target,err = await get_target(update,context)
    if err: await update.message.reply_text(err); return
    try:
        await context.bot.restrict_chat_member(chat_id,target.id,
            permissions=ChatPermissions(can_send_messages=True,can_send_media_messages=True,
                can_send_polls=True,can_send_other_messages=True,can_add_web_page_previews=True,
                can_change_info=False,can_invite_users=True,can_pin_messages=False))
        name=f"@{target.username}" if target.username else target.full_name
        await update.message.reply_text(f"🔊 *{name}* unmuted!",parse_mode="Markdown")
    except TelegramError as e: await update.message.reply_text(f"❌ _{e}_",parse_mode="Markdown")

async def cmd_purge(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id=update.message.chat_id
    if not await is_admin(context.bot,chat_id,update.message.from_user.id):
        await update.message.reply_text("⚠️ Admins only!"); return
    n=10
    if context.args:
        try: n=max(1,min(int(context.args[0]),100))
        except: pass
    msg_id=update.message.message_id; deleted=0
    for i in range(msg_id,msg_id-n-2,-1):
        try: await context.bot.delete_message(chat_id,i); deleted+=1
        except: pass
    try:
        note=await context.bot.send_message(chat_id,f"🗑️ Purged *{deleted}* messages.",parse_mode="Markdown")
        await asyncio.sleep(3); await context.bot.delete_message(chat_id,note.message_id)
    except: pass

async def cmd_warn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id=update.message.chat_id
    if not await is_admin(context.bot,chat_id,update.message.from_user.id):
        await update.message.reply_text("⚠️ Admins only!"); return
    target,err=await get_target(update,context)
    if err: await update.message.reply_text(err); return
    group=get_group_db(chat_id); uid=str(target.id)
    group["warns"][uid]=group["warns"].get(uid,0)+1; count=group["warns"][uid]; save_group_db(chat_id,group)
    name=f"@{target.username}" if target.username else target.full_name
    if count>=3:
        try:
            await context.bot.ban_chat_member(chat_id,target.id)
            await update.message.reply_text(f"⚠️ *{name}* warn {count}/3 → 🔨 *BANNED!*",parse_mode="Markdown")
            group["warns"][uid]=0; save_group_db(chat_id,group)
        except TelegramError as e:
            await update.message.reply_text(f"⚠️ Warn {count}/3 (ban failed: _{e}_)",parse_mode="Markdown")
    else:
        await update.message.reply_text(f"⚠️ *{name}* warned *{count}/3*.",parse_mode="Markdown")

async def cmd_warns(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id=update.message.chat_id; target,err=await get_target(update,context)
    if err: await update.message.reply_text(err); return
    group=get_group_db(chat_id); count=group["warns"].get(str(target.id),0)
    name=f"@{target.username}" if target.username else target.full_name
    await update.message.reply_text(f"⚠️ *{name}* has *{count}/3* warnings.",parse_mode="Markdown")

async def cmd_clearwarns(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id=update.message.chat_id
    if not await is_admin(context.bot,chat_id,update.message.from_user.id):
        await update.message.reply_text("⚠️ Admins only!"); return
    target,err=await get_target(update,context)
    if err: await update.message.reply_text(err); return
    group=get_group_db(chat_id); group["warns"][str(target.id)]=0; save_group_db(chat_id,group)
    name=f"@{target.username}" if target.username else target.full_name
    await update.message.reply_text(f"✅ Cleared warns for *{name}*.",parse_mode="Markdown")
