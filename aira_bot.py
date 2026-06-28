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
import pymongo
from pymongo import ReplaceOne

# ══════════════════════════════════════════════════════════════════════════════
#  CONFIG
# ══════════════════════════════════════════════════════════════════════════════
BOT_TOKEN          = os.environ.get("BOT_TOKEN", "8807391435:AAEiguri8PTUAYaKDbOX8zpsJ93r0u8Hr1E")
GROQ_API_KEY       = os.environ.get("GROQ_API_KEY", "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")
GROQ_MODEL         = os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")
MONGO_URI          = os.environ.get("MONGO_URI", "")

CHALLENGE_TIMEOUT  = 300
CHALLENGE_COOLDOWN = 300
INTERVAL_MIN       = 1800
INTERVAL_MAX       = 5400
STREAK_BONUS       = 2
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
    {"name":"🐭 Mouse",      "rarity":"common",    "coins":5,  "gems":1, "sell":3,  "owo":1},
    {"name":"🐱 Cat",        "rarity":"common",    "coins":6,  "gems":1, "sell":4,  "owo":1},
    {"name":"🐶 Dog",        "rarity":"common",    "coins":6,  "gems":1, "sell":4,  "owo":1},
    {"name":"🐰 Rabbit",    "rarity":"common",    "coins":7,  "gems":1, "sell":5,  "owo":1},
    {"name":"🐦 Bird",      "rarity":"common",    "coins":5,  "gems":1, "sell":3,  "owo":1},
    {"name":"🦊 Fox",        "rarity":"uncommon",  "coins":10, "gems":2, "sell":8,  "owo":2},
    {"name":"🐺 Wolf",      "rarity":"uncommon",  "coins":12, "gems":2, "sell":9,  "owo":2},
    {"name":"🦝 Raccoon",   "rarity":"uncommon",  "coins":11, "gems":2, "sell":8,  "owo":2},
    {"name":"🐗 Boar",      "rarity":"uncommon",  "coins":13, "gems":2, "sell":10, "owo":2},
    {"name":"🦅 Eagle",      "rarity":"uncommon",  "coins":11, "gems":2, "sell":9,  "owo":2},
    {"name":"🦌 Deer",      "rarity":"rare",      "coins":18, "gems":4, "sell":15, "owo":3},
    {"name":"🐻 Bear",      "rarity":"rare",      "coins":20, "gems":4, "sell":17, "owo":3},
    {"name":"🐯 Tiger",      "rarity":"rare",      "coins":22, "gems":5, "sell":20, "owo":3},
    {"name":"🦁 Lion",      "rarity":"rare",      "coins":25, "gems":5, "sell":22, "owo":4},
    {"name":"🦈 Shark",      "rarity":"rare",      "coins":23, "gems":5, "sell":20, "owo":3},
    {"name":"🐘 Elephant",  "rarity":"epic",      "coins":35, "gems":8, "sell":300, "owo":5},
    {"name":"🦏 Rhino",      "rarity":"epic",      "coins":38, "gems":8, "sell":330, "owo":5},
    {"name":"🦍 Gorilla",   "rarity":"epic",      "coins":40, "gems":9, "sell":350, "owo":5},
    {"name":"🐋 Whale",      "rarity":"epic",      "coins":42, "gems":9, "sell":370, "owo":6},
    {"name":"🦬 Bison",      "rarity":"epic",      "coins":36, "gems":8, "sell":310, "owo":5},
    {"name":"🐉 Dragon",    "rarity":"legendary","coins":100,"gems":25,"sell":900,  "owo":15},
    {"name":"🦄 Unicorn",   "rarity":"legendary","coins":90, "gems":22,"sell":800,  "owo":12},
    {"name":"🔱 Leviathan", "rarity":"legendary","coins":120,"gems":30,"sell":1000, "owo":20},
    {"name":"🌟 Phoenix",   "rarity":"legendary","coins":110,"gems":28,"sell":1000, "owo":18},
    {"name":"♠️ Spade",      "rarity":"Extreme",  "coins":1100,"gems":300,"sell":10000, "owo":300},
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
    "skip_challenge":  {"name":"⏭️ Skip Challenge",          "desc":"End current, start new!",             "cost":30},
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
        "trades":      meta.get("trades",        {}),
        "item_trades": meta.get("item_trades",    {}),
        "auctions":    meta.get("auctions",      {}),
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
        "trades":       data.get("trades",        {}),
        "item_trades":  data.get("item_trades",    {}),
        "auctions":     data.get("auctions",      {}),
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
#  CASINO
# ══════════════════════════════════════════════════════════════════════════════
async def cmd_cf(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user=update.message.from_user; data=load_data()
    u=get_user(data,user.id,user.username,user.full_name)
    if len(context.args)<2:
        await update.message.reply_text("Usage: `/cf <amount> heads` or `/cf <amount> tails`",parse_mode="Markdown"); return
    try: amount=int(context.args[0])
    except: await update.message.reply_text("❌ Amount must be a number."); return
    if amount<=0: await update.message.reply_text("❌ Must be positive!"); return
    if amount>u["coins"]: await update.message.reply_text(f"❌ Not enough! You have {u['coins']} 🪙"); return
    choice=context.args[1].lower()
    if choice not in ("heads","tails","head","tail"):
        await update.message.reply_text("❌ Choose *heads* or *tails*!",parse_mode="Markdown"); return
    praying    = has_pray_buff(u)
    win_chance = 0.575 if praying else 0.50
    pray_line  = "\n🙏 *Pray buff active!* (+7.5% luck)" if praying else ""
    won = random.random() < win_chance
    result = choice.rstrip("s") if won else ("tails" if choice.rstrip("s")=="heads" else "heads")
    result_display = "HEADS" if ("head" in (choice if won else result)) else "TAILS"
    if won:
        u["coins"]+=amount; u["total_coins_ever"]=u.get("total_coins_ever",0)+amount
        u["casino_wins"]=u.get("casino_wins",0)+1
        u["casino_total_won"]=u.get("casino_total_won",0)+amount
        badges=check_badges(u); save_data(data)
        bl="\n🆕 "+" | ".join(badges) if badges else ""
        await update.message.reply_text(
            f"🪙 *COIN FLIP*{pray_line}\nResult: *{result_display}* ✅ You won!\n"
            f"+{amount} 🪙 | Balance: *{u['coins']}*{bl}",parse_mode="Markdown")
    else:
        u["coins"]-=amount; save_data(data)
        await update.message.reply_text(
            f"🪙 *COIN FLIP*{pray_line}\nResult: *{result_display}* ❌ You lost!\n"
            f"-{amount} 🪙 | Balance: *{u['coins']}*",parse_mode="Markdown")

async def cmd_slots(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user=update.message.from_user; data=load_data()
    u=get_user(data,user.id,user.username,user.full_name)
    if not context.args:
        await update.message.reply_text("Usage: `/s <amount>`",parse_mode="Markdown"); return
    try: amount=int(context.args[0])
    except: await update.message.reply_text("❌ Amount must be a number."); return
    if amount<=0: await update.message.reply_text("❌ Must be positive!"); return
    if amount>u["coins"]: await update.message.reply_text(f"❌ Not enough! Have {u['coins']} 🪙"); return
    praying   = has_pray_buff(u)
    pray_line = "\n🙏 *Pray buff active!*" if praying else ""
    SLOT_EMOJIS=["🍒","🍋","🍊","⭐","💎","🔔","7️⃣"]
    reels=[random.choice(SLOT_EMOJIS) for _ in range(3)]
    if praying and reels[0]!=reels[1]!=reels[2]:
        if random.random() < 0.20:
            reels[2] = reels[random.randint(0,1)]
    display=" | ".join(reels)
    if reels[0]==reels[1]==reels[2]:
        if reels[0]=="💎": mult=10
        elif reels[0]=="7️⃣": mult=7
        elif reels[0]=="⭐": mult=5
        else: mult=3
        win=amount*mult; u["coins"]+=win; u["total_coins_ever"]=u.get("total_coins_ever",0)+win
        u["casino_wins"]=u.get("casino_wins",0)+1; u["casino_total_won"]=u.get("casino_total_won",0)+win
        badges=check_badges(u); save_data(data)
        bl="\n🆕 "+" | ".join(badges) if badges else ""
        await update.message.reply_text(
            f"🎰 *SLOTS*{pray_line}\n[ {display} ]\n\n🎊 *JACKPOT! ×{mult}!*\n"
            f"+{win} 🪙 | Balance: *{u['coins']}*{bl}",parse_mode="Markdown")
    elif reels[0]==reels[1] or reels[1]==reels[2] or reels[0]==reels[2]:
        win=amount; u["coins"]+=win; u["total_coins_ever"]=u.get("total_coins_ever",0)+win
        u["casino_wins"]=u.get("casino_wins",0)+1; u["casino_total_won"]=u.get("casino_total_won",0)+win
        save_data(data)
        await update.message.reply_text(
            f"🎰 *SLOTS*{pray_line}\n[ {display} ]\n\n✅ *Two match! ×1*\n"
            f"+{win} 🪙 | Balance: *{u['coins']}*",parse_mode="Markdown")
    else:
        u["coins"]-=amount; save_data(data)
        await update.message.reply_text(
            f"🎰 *SLOTS*{pray_line}\n[ {display} ]\n\n❌ *No match. You lost!*\n"
            f"-{amount} 🪙 | Balance: *{u['coins']}*",parse_mode="Markdown")

async def cmd_dice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user=update.message.from_user; data=load_data()
    u=get_user(data,user.id,user.username,user.full_name)
    if len(context.args)<2:
        await update.message.reply_text("Usage: `/dice <amount> <1-6>`",parse_mode="Markdown"); return
    try: amount=int(context.args[0]); guess=int(context.args[1])
    except: await update.message.reply_text("❌ Use numbers only."); return
    if not 1<=guess<=6: await update.message.reply_text("❌ Pick a number 1-6!"); return
    if amount<=0 or amount>u["coins"]: await update.message.reply_text(f"❌ Invalid amount. Have {u['coins']} 🪙"); return
    praying    = has_pray_buff(u)
    pray_line  = "\n🙏 *Pray buff active!*" if praying else ""
    roll = random.randint(1,6)
    if praying and roll != guess:
        if random.random() < 0.20:
            roll = guess
    dice_faces=["","1️⃣","2️⃣","3️⃣","4️⃣","5️⃣","6️⃣"]
    if roll==guess:
        win=amount*3; u["coins"]+=win; u["total_coins_ever"]=u.get("total_coins_ever",0)+win
        u["casino_wins"]=u.get("casino_wins",0)+1; u["casino_total_won"]=u.get("casino_total_won",0)+win
        badges=check_badges(u); save_data(data)
        bl="\n🆕 "+" | ".join(badges) if badges else ""
        await update.message.reply_text(
            f"🎲 *DICE*{pray_line}\nYou guessed: {dice_faces[guess]} | Rolled: {dice_faces[roll]}\n\n"
            f"🎊 *CORRECT! ×3!*\n+{win} 🪙 | Balance: *{u['coins']}*{bl}",parse_mode="Markdown")
    else:
        u["coins"]-=amount; save_data(data)
        await update.message.reply_text(
            f"🎲 *DICE*{pray_line}\nYou guessed: {dice_faces[guess]} | Rolled: {dice_faces[roll]}\n\n"
            f"❌ *Wrong!* -{amount} 🪙 | Balance: *{u['coins']}*",parse_mode="Markdown")

# ══════════════════════════════════════════════════════════════════════════════
#  SELL / GEM SHOP
# ══════════════════════════════════════════════════════════════════════════════
async def cmd_sell(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    db   = _get_db()
    uid  = str(user.id)
    doc  = db["users"].find_one({"_id": uid})
    if not doc:
        await update.message.reply_text("You have no zoo yet! Use /hunt first."); return
    zoo = doc.get("animals", [])
    if not zoo:
        await update.message.reply_text("Your zoo is empty! /hunt first."); return
    if not context.args:
        await update.message.reply_text(
            "Usage:\n`/sell all` | `/sell all common` | `/sell <name>`",
            parse_mode="Markdown"); return
    arg = " ".join(context.args).lower().strip()
    VALID_RARITIES = ["common","uncommon","rare","epic","legendary","extreme","mythic"]
    if arg == "all":
        total_coins=0; total_gems=0; count=0
        for a_entry in zoo:
            aname=a_entry["name"]; cnt=a_entry.get("count",1)
            match=next((a for a in ANIMALS if a["name"]==aname),None)
            if match:
                total_coins+=match["sell"]*cnt; total_gems+=match["gems"]*cnt; count+=cnt
        doc["animals"]=[]; doc["coins"]=doc.get("coins",0)+total_coins
        doc["gems"]=doc.get("gems",0)+total_gems
        doc["total_coins_ever"]=doc.get("total_coins_ever",0)+total_coins
        db["users"].replace_one({"_id":uid},doc,upsert=True)
        await update.message.reply_text(
            f"💰 *Sold all {count} animals!*\n+{total_coins} 🪙 | +{total_gems} 💎\n"
            f"Balance: *{doc['coins']}* 🪙 | *{doc['gems']}* 💎",parse_mode="Markdown"); return
    if arg.startswith("all "):
        rarity=arg[4:].strip()
        if rarity not in VALID_RARITIES:
            await update.message.reply_text(f"❌ Unknown rarity *{rarity}*",parse_mode="Markdown"); return
        to_sell=[z for z in zoo if z.get("rarity","").lower()==rarity]
        to_keep=[z for z in zoo if z.get("rarity","").lower()!=rarity]
        if not to_sell:
            await update.message.reply_text(f"❌ No *{rarity}* animals!",parse_mode="Markdown"); return
        total_coins=0; total_gems=0; count=0
        for a_entry in to_sell:
            aname=a_entry["name"]; cnt=a_entry.get("count",1)
            match=next((a for a in ANIMALS if a["name"]==aname),None)
            if match:
                total_coins+=match["sell"]*cnt; total_gems+=match["gems"]*cnt; count+=cnt
        doc["animals"]=to_keep; doc["coins"]=doc.get("coins",0)+total_coins
        doc["gems"]=doc.get("gems",0)+total_gems
        doc["total_coins_ever"]=doc.get("total_coins_ever",0)+total_coins
        db["users"].replace_one({"_id":uid},doc,upsert=True)
        icon=RARITY_COLORS.get(rarity,"⬜")
        await update.message.reply_text(
            f"💰 *Sold {count} {icon}{rarity} animals!*\n+{total_coins} 🪙 | +{total_gems} 💎\n"
            f"Balance: *{doc['coins']}* 🪙 | *{doc['gems']}* 💎",parse_mode="Markdown"); return
    found_entry=next((z for z in zoo if arg in z["name"].lower()),None)
    if not found_entry:
        await update.message.reply_text(f"❌ No animal matching '*{arg}*'!",parse_mode="Markdown"); return
    match=next((a for a in ANIMALS if a["name"]==found_entry["name"]),None)
    if not match: return
    cnt=found_entry.get("count",1); coins_earn=match["sell"]*cnt; gems_earn=match["gems"]*cnt
    zoo.remove(found_entry); doc["animals"]=zoo
    doc["coins"]=doc.get("coins",0)+coins_earn; doc["gems"]=doc.get("gems",0)+gems_earn
    doc["total_coins_ever"]=doc.get("total_coins_ever",0)+coins_earn
    db["users"].replace_one({"_id":uid},doc,upsert=True)
    await update.message.reply_text(
        f"💰 Sold *{found_entry['name']}* ×{cnt}\n+{coins_earn} 🪙 | +{gems_earn} 💎\n"
        f"Balance: *{doc['coins']}* 🪙 | *{doc['gems']}* 💎",parse_mode="Markdown")

async def cmd_gemshop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user=update.message.from_user; data=load_data()
    u=get_user(data,user.id,user.username,user.full_name); save_data(data)
    lines=["💎 *GEM SHOP — Weapons*\n━━━━━━━━━━━━━"]
    kb=[]
    for wkey,w in WEAPONS.items():
        owned="✅" if u.get("weapon")==wkey else ""
        lines.append(f"{w['name']} {owned}\n  Cost: {w['gems']} 💎 | ATK+{w['atk_bonus']} | Catch+{w['catch_bonus']}%")
        if u.get("weapon")!=wkey:
            kb.append([InlineKeyboardButton(f"Buy {w['name']} – {w['gems']}💎",callback_data=f"gbuy_{wkey}")])
    lines.append(f"\n💎 Your Gems: *{u.get('gems',0)}*")
    await update.message.reply_text("\n".join(lines),
        reply_markup=InlineKeyboardMarkup(kb) if kb else None,parse_mode="Markdown")

async def handle_gem_purchase(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query=update.callback_query; await query.answer()
    user=query.from_user; wkey=query.data.replace("gbuy_","")
    if wkey not in WEAPONS: await query.edit_message_text("❌ Unknown weapon."); return
    data=load_data(); u=get_user(data,user.id,user.username,user.full_name)
    w=WEAPONS[wkey]
    if u.get("gems",0)<w["gems"]:
        await query.edit_message_text(f"❌ Need {w['gems']} 💎 but you have {u.get('gems',0)} 💎"); return
    old_weapon=u.get("weapon","stick")
    inv=u.get("weapon_inventory",[])
    if old_weapon!="stick" and old_weapon not in inv:
        inv.append(old_weapon)
    u["weapon_inventory"]=inv; u["gems"]-=w["gems"]; u["weapon"]=wkey
    save_data(data)
    await query.edit_message_text(
        f"✅ You now wield {w['name']}!\nATK Bonus: +{w['atk_bonus']}% | Catch Rate: +{w['catch_bonus']}%\n"
        f"Gems remaining: *{u['gems']}* 💎",parse_mode="Markdown")

# ══════════════════════════════════════════════════════════════════════════════
#  TRADE
# ══════════════════════════════════════════════════════════════════════════════
async def cmd_trade(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user=update.message.from_user
    if not update.message.reply_to_message:
        await update.message.reply_text("↩️ Reply to someone's message to trade with them."); return
    if not context.args:
        await update.message.reply_text("Usage: Reply + `/trade <amount>`",parse_mode="Markdown"); return
    try: amount=int(context.args[0])
    except: await update.message.reply_text("❌ Amount must be a number."); return
    if amount<=0: await update.message.reply_text("❌ Must be positive!"); return
    target=update.message.reply_to_message.from_user
    if target.id==user.id: await update.message.reply_text("❌ Can't trade with yourself!"); return
    if target.is_bot: await update.message.reply_text("❌ Can't trade with bots!"); return
    data=load_data(); s=get_user(data,user.id,user.username,user.full_name)
    if s["coins"]<amount: await update.message.reply_text(f"❌ Not enough! Have {s['coins']} 🪙"); return
    sname=f"@{user.username}" if user.username else user.full_name
    tname=f"@{target.username}" if target.username else target.full_name
    trade_id=f"trade_{user.id}_{target.id}_{int(datetime.now().timestamp())}"
    data.setdefault("trades",{})[trade_id]={"from_id":user.id,"to_id":target.id,"amount":amount,"status":"pending"}
    save_data(data)
    kb=[[InlineKeyboardButton("✅ Accept",callback_data=f"tacpt_{trade_id}"),
         InlineKeyboardButton("❌ Decline",callback_data=f"tdecl_{trade_id}")]]
    await update.message.reply_text(
        f"🤝 *Trade Request!*\n{sname} wants to give *{amount}* 🪙 to {tname}\n\n{tname}, accept?",
        reply_markup=InlineKeyboardMarkup(kb),parse_mode="Markdown")

async def handle_trade(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query=update.callback_query; await query.answer()
    parts=query.data.split("_",1); action=parts[0]; trade_id=parts[1]
    data=load_data(); trades=data.get("trades",{})
    if trade_id not in trades:
        await query.edit_message_text("❌ Trade expired."); return
    trade=trades[trade_id]
    if trade["status"]!="pending":
        await query.edit_message_text("❌ Trade already resolved."); return
    if query.from_user.id!=trade["to_id"]:
        await query.answer("❌ Only the recipient can respond!",show_alert=True); return
    if action=="tacpt":
        s=get_user(data,trade["from_id"]); t=get_user(data,trade["to_id"])
        if s["coins"]<trade["amount"]:
            await query.edit_message_text("❌ Sender no longer has enough coins!"); return
        s["coins"]-=trade["amount"]; t["coins"]+=trade["amount"]
        t["total_coins_ever"]=t.get("total_coins_ever",0)+trade["amount"]
        award_badge(s,"trader"); award_badge(t,"trader")
        trade["status"]="done"; save_data(data)
        sname=f"@{data['users'][str(trade['from_id'])].get('username','?')}"
        tname=f"@{data['users'][str(trade['to_id'])].get('username','?')}"
        await query.edit_message_text(
            f"✅ *Trade Complete!*\n{sname} → {tname}: *{trade['amount']}* 🪙",parse_mode="Markdown")
    else:
        trade["status"]="declined"; save_data(data)
        await query.edit_message_text("❌ Trade declined.")

# ══════════════════════════════════════════════════════════════════════════════
#  POMODORO
# ══════════════════════════════════════════════════════════════════════════════
async def cmd_pomodoro(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id=update.message.chat_id
    mins=25
    if context.args:
        try: mins=max(5,min(int(context.args[0]),120))
        except: pass
    user=update.message.from_user
    name=f"@{user.username}" if user.username else user.full_name
    await update.message.reply_text(
        f"🍅 *POMODORO STARTED!*\n{name} started a *{mins}-minute* focus session!\n"
        f"📵 Stay focused!\n_Aira will ping when done!_",parse_mode="Markdown")
    context.job_queue.run_once(
        lambda ctx: asyncio.ensure_future(_pomo_done(ctx,chat_id,user.id,user.username or user.full_name,mins)),
        when=mins*60,name=f"pomo_{user.id}")

async def _pomo_done(context, chat_id, user_id, uname, mins):
    reward=mins//5*10
    data=load_data(); u=get_user(data,user_id)
    u["coins"]+=reward; u["total_coins_ever"]=u.get("total_coins_ever",0)+reward
    save_data(data)
    name=f"@{uname}" if not uname.startswith("@") else uname
    try:
        await context.bot.send_message(chat_id,
            f"🍅 *POMODORO DONE!*\n{name} completed *{mins} minutes* of focus! 🎉\n"
            f"Reward: +*{reward}* Forge Coins! 🪙",parse_mode="Markdown")
    except: pass

# ══════════════════════════════════════════════════════════════════════════════
#  AI ASK
# ══════════════════════════════════════════════════════════════════════════════
async def cmd_ask(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: `/ask <your question>`",parse_mode="Markdown"); return
    question=" ".join(context.args)
    user=update.message.from_user
    user_name=f"@{user.username}" if user.username else user.full_name
    thinking=await update.message.reply_text("🤔 thinking...")
    try:
        await context.bot.send_chat_action(update.message.chat_id, "typing")
        reply = await groq_chat(update.message.chat_id, user_name, question)
    except Exception as e:
        reply = random.choice(FALLBACK_REPLIES)
    await thinking.delete()
    await update.message.reply_text(reply)

# ══════════════════════════════════════════════════════════════════════════════
#  TOP ANIMALS
# ══════════════════════════════════════════════════════════════════════════════
async def cmd_topanimals(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data=load_data()
    scores=[]
    for uid,u in data["users"].items():
        zoo=u.get("animals",[])
        score=0
        for z in zoo:
            w={"common":1,"uncommon":2,"rare":5,"epic":10,"legendary":25}.get(z.get("rarity","common"),1)
            score+=w*z.get("count",1)
        if score>0: scores.append((u.get("full_name","?"),u.get("title"),score,zoo))
    scores.sort(key=lambda x:x[2],reverse=True)
    medals=["🥇","🥈","🥉","4️⃣","5️⃣","6️⃣","7️⃣","8️⃣","9️⃣","🔟"]
    lines=["🦁 *TOP ANIMAL COLLECTORS*\n━━━━━━━━━━━━━"]
    for i,(name,title,score,zoo) in enumerate(scores[:10]):
        tag=f" 👑{title}" if title else ""
        legends=sum(z.get("count",1) for z in zoo if z.get("rarity")=="legendary")
        lines.append(f"{medals[i]} {name}{tag}\n   ⭐Score:{score} | 🐉×{legends}")
    if not scores: lines.append("No collectors yet!")
    await update.message.reply_text("\n".join(lines),parse_mode="Markdown")

# ══════════════════════════════════════════════════════════════════════════════
#  RARITY/WEAPON POWER (PVP)
# ══════════════════════════════════════════════════════════════════════════════
RARITY_POWER = {"common":10,"uncommon":20,"rare":40,"epic":70,"legendary":120,"Extreme":500,"mythic":1000}
WEAPON_POWER = {"stick":0,"bow":10,"spear":25,"rifle":50,"laser":90,"dragonblade":200,"sayan":500,"mace":700}

def find_animal_data(name):
    name_lower = name.lower()
    return next((a for a in ANIMALS if name_lower in a["name"].lower()), None)

def get_team_power(team_names, weapon_key="stick"):
    power = WEAPON_POWER.get(weapon_key, 0)
    for name in team_names:
        a = find_animal_data(name)
        if a:
            power += RARITY_POWER.get(a["rarity"], 10)
    return power

async def cmd_setteam(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user=update.message.from_user; data=load_data()
    u=get_user(data,user.id,user.username,user.full_name); zoo=u.get("animals",[])
    if not context.args:
        current=u.get("battle_team",[])
        if current:
            team_str="\n".join(f"  {i+1}. {n}" for i,n in enumerate(current))
            await update.message.reply_text(f"⚔️ *Your Battle Team:*\n{team_str}",parse_mode="Markdown")
        else:
            await update.message.reply_text("No team! `/setteam Dragon | Lion | Tiger`",parse_mode="Markdown")
        return
    raw=" ".join(context.args); picks=[p.strip() for p in raw.split("|")]
    if len(picks)!=3:
        await update.message.reply_text("❌ Pick exactly 3 animals separated by `|`",parse_mode="Markdown"); return
    chosen=[]; errors=[]
    for pick in picks:
        matched=next((z["name"] for z in zoo if pick.lower() in z["name"].lower()),None)
        if matched: chosen.append(matched)
        else: errors.append(pick)
    if errors:
        await update.message.reply_text(f"❌ You don't have: *{', '.join(errors)}*",parse_mode="Markdown"); return
    u["battle_team"]=chosen; save_data(data)
    power=get_team_power(chosen,u.get("weapon","stick"))
    weapon=WEAPONS.get(u.get("weapon","stick"),WEAPONS["stick"])
    lines=[f"⚔️ *Battle Team Set!*\n━━━━━━━━━━━━━"]
    for i,n in enumerate(chosen):
        a=find_animal_data(n); icon=RARITY_COLORS.get(a["rarity"],"⬜") if a else "⬜"
        lines.append(f"  {i+1}. {n} {icon}")
    lines.append(f"\n🏹 Weapon: {weapon['name']}\n💪 Total Power: *{power}*")
    await update.message.reply_text("\n".join(lines),parse_mode="Markdown")

async def cmd_pvp(update: Update, context: ContextTypes.DEFAULT_TYPE):
    challenger=update.message.from_user; chat_id=update.message.chat_id
    if not update.message.reply_to_message:
        await update.message.reply_text("↩️ Reply to someone + `/pvp <bet>`",parse_mode="Markdown"); return
    opponent=update.message.reply_to_message.from_user
    if opponent.id==challenger.id:
        await update.message.reply_text("❌ Can't battle yourself!"); return
    if opponent.is_bot:
        await update.message.reply_text("❌ Can't battle a bot!"); return
    bet=0
    if context.args:
        try: bet=max(0,int(context.args[0]))
        except: await update.message.reply_text("❌ Bet must be a number."); return
    data=load_data()
    cu=get_user(data,challenger.id,challenger.username,challenger.full_name)
    ou=get_user(data,opponent.id,opponent.username,opponent.full_name)
    if bet>0 and cu.get("coins",0)<bet:
        await update.message.reply_text(f"❌ Not enough coins for bet!"); return
    c_team=cu.get("battle_team",[])
    if not c_team:
        await update.message.reply_text("❌ Set your battle team first! `/setteam`",parse_mode="Markdown"); return
    cname=f"@{challenger.username}" if challenger.username else challenger.full_name
    oname=f"@{opponent.username}" if opponent.username else opponent.full_name
    bet_line=f"\n💰 Bet: *{bet} coins each*" if bet>0 else ""
    pvp_id=f"pvp_{challenger.id}_{opponent.id}_{int(datetime.now().timestamp())}"
    data.setdefault("pvp_requests",{})[pvp_id]={"challenger_id":challenger.id,"opponent_id":opponent.id,"bet":bet,"status":"pending","chat_id":chat_id}
    save_data(data)
    kb=[[InlineKeyboardButton("⚔️ Accept",callback_data=f"pvpacpt_{pvp_id}"),InlineKeyboardButton("❌ Decline",callback_data=f"pvpdecl_{pvp_id}")]]
    await update.message.reply_text(
        f"⚔️ *PVP CHALLENGE!*\n{cname} challenges {oname}!{bet_line}\n\nTeam: {' | '.join(c_team)}\n{oname}, accept?",
        reply_markup=InlineKeyboardMarkup(kb),parse_mode="Markdown")

async def handle_pvp(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query=update.callback_query; await query.answer()
    parts=query.data.split("_",1); action=parts[0]; pvp_id=parts[1]
    data=load_data(); pvps=data.get("pvp_requests",{})
    if pvp_id not in pvps:
        await query.edit_message_text("❌ Battle expired."); return
    pvp=pvps[pvp_id]
    if pvp["status"]!="pending":
        await query.edit_message_text("❌ Already resolved."); return
    if query.from_user.id!=pvp["opponent_id"]:
        await query.answer("❌ Only the challenged player can respond!",show_alert=True); return
    if action=="pvpdecl":
        pvp["status"]="declined"; save_data(data)
        await query.edit_message_text("❌ Battle declined."); return
    pvp["status"]="done"
    cu=get_user(data,pvp["challenger_id"]); ou=get_user(data,pvp["opponent_id"],query.from_user.username,query.from_user.full_name)
    c_team=cu.get("battle_team",[]); o_team=ou.get("battle_team",[])
    if not o_team:
        await query.edit_message_text("❌ You have no battle team! Use `/setteam` first.",parse_mode="Markdown"); return
    bet=pvp.get("bet",0)
    if bet>0 and (cu.get("coins",0)<bet or ou.get("coins",0)<bet):
        await query.edit_message_text("❌ Someone doesn't have enough coins!"); return
    c_power=get_team_power(c_team,cu.get("weapon","stick")); o_power=get_team_power(o_team,ou.get("weapon","stick"))
    c_roll=c_power*random.uniform(0.7,1.3); o_roll=o_power*random.uniform(0.7,1.3)
    c_weapon=WEAPONS.get(cu.get("weapon","stick"),WEAPONS["stick"]); o_weapon=WEAPONS.get(ou.get("weapon","stick"),WEAPONS["stick"])
    cname=f"@{cu.get('username','?')}" if cu.get("username")!="Unknown" else cu.get("full_name","?")
    oname=f"@{ou.get('username','?')}" if ou.get("username")!="Unknown" else ou.get("full_name","?")
    if c_roll>=o_roll: winner,loser,wu,lu=cname,oname,cu,ou
    else: winner,loser,wu,lu=oname,cname,ou,cu
    add_xp(wu,30); add_xp(lu,10); wu["wins"]=wu.get("wins",0)+1
    bet_result=""
    if bet>0:
        wu["coins"]=wu.get("coins",0)+bet; lu["coins"]=max(0,lu.get("coins",0)-bet)
        wu["total_coins_ever"]=wu.get("total_coins_ever",0)+bet
        bet_result=f"\n💰 {winner} wins *{bet} coins*!"
    save_data(data)
    await query.edit_message_text(
        f"⚔️ *PVP RESULT!*\n{cname}: {int(c_roll)} vs {oname}: {int(o_roll)}\n\n🏆 *{winner} WINS!*{bet_result}",
        parse_mode="Markdown")

async def cmd_tradeitem(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user=update.message.from_user
    if not update.message.reply_to_message:
        await update.message.reply_text("↩️ Reply to target, then: `/tradeitem animal Dragon for 500`",parse_mode="Markdown"); return
    if not context.args or len(context.args)<4:
        await update.message.reply_text("Usage:\n`/tradeitem animal Dragon for 500`\n`/tradeitem weapon bow for 200`",parse_mode="Markdown"); return
    item_type=context.args[0].lower(); raw_args=context.args[1:]
    try: for_idx=[a.lower() for a in raw_args].index("for")
    except:
        await update.message.reply_text("❌ Missing 'for'. Example: `/tradeitem animal Dragon for 500`",parse_mode="Markdown"); return
    item_name=" ".join(raw_args[:for_idx]).strip()
    try: price=int(raw_args[for_idx+1])
    except: await update.message.reply_text("❌ Price must be a number."); return
    if price<=0: await update.message.reply_text("❌ Price must be positive."); return
    target=update.message.reply_to_message.from_user
    if target.id==user.id: await update.message.reply_text("❌ Can't trade with yourself!"); return
    if target.is_bot: await update.message.reply_text("❌ Can't trade with bots!"); return
    data=load_data()
    su=get_user(data,user.id,user.username,user.full_name)
    tu=get_user(data,target.id,target.username,target.full_name)
    if item_type=="animal":
        zoo=su.get("animals",[]); matched=next((z for z in zoo if item_name.lower() in z["name"].lower()),None)
        if not matched: await update.message.reply_text(f"❌ You don't have '{item_name}'!"); return
        display_name=matched["name"]
    elif item_type=="weapon":
        w_key=next((k for k in WEAPONS if item_name.lower() in WEAPONS[k]["name"].lower()),None)
        if not w_key or su.get("weapon")!=w_key: await update.message.reply_text(f"❌ You don't own '{item_name}'!"); return
        if w_key=="stick": await update.message.reply_text("❌ Can't trade the stick!"); return
        display_name=WEAPONS[w_key]["name"]
    else:
        await update.message.reply_text("❌ Type must be `animal` or `weapon`.",parse_mode="Markdown"); return
    sname=f"@{user.username}" if user.username else user.full_name
    tname=f"@{target.username}" if target.username else target.full_name
    ti_id=f"ti_{user.id}_{target.id}_{int(datetime.now().timestamp())}"
    data.setdefault("item_trades",{})[ti_id]={"from_id":user.id,"to_id":target.id,"item_type":item_type,"item_name":display_name if item_type=="animal" else w_key,"price":price,"status":"pending"}
    save_data(data)
    kb=[[InlineKeyboardButton("✅ Accept",callback_data=f"tiacpt_{ti_id}"),InlineKeyboardButton("❌ Decline",callback_data=f"tidecl_{ti_id}")]]
    icon="🦁" if item_type=="animal" else "🏹"
    await update.message.reply_text(
        f"{icon} *Item Trade!*\n{sname} offers *{display_name}*\nPrice: *{price} 🪙*\n{tname}, buy?",
        reply_markup=InlineKeyboardMarkup(kb),parse_mode="Markdown")

async def handle_item_trade(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query=update.callback_query; await query.answer()
    parts=query.data.split("_",1); action=parts[0]; ti_id=parts[1]
    data=load_data(); trades=data.get("item_trades",{})
    if ti_id not in trades: await query.edit_message_text("❌ Trade expired."); return
    trade=trades[ti_id]
    if trade["status"]!="pending": await query.edit_message_text("❌ Already resolved."); return
    if query.from_user.id!=trade["to_id"]: await query.answer("❌ Only recipient can respond!",show_alert=True); return
    if action=="tidecl":
        trade["status"]="declined"; save_data(data)
        await query.edit_message_text("❌ Trade declined."); return
    su=get_user(data,trade["from_id"]); tu=get_user(data,trade["to_id"],query.from_user.username,query.from_user.full_name)
    price=trade["price"]
    if tu.get("coins",0)<price:
        await query.edit_message_text(f"❌ Not enough coins! Need *{price}* 🪙",parse_mode="Markdown"); return
    sname=f"@{su.get('username','?')}" if su.get("username")!="Unknown" else su.get("full_name","?")
    tname=f"@{tu.get('username','?')}" if tu.get("username")!="Unknown" else tu.get("full_name","?")
    if trade["item_type"]=="animal":
        s_zoo=su.get("animals",[]); matched=next((z for z in s_zoo if trade["item_name"] in z["name"]),None)
        if not matched: await query.edit_message_text("❌ Seller no longer has this animal!"); return
        if matched.get("count",1)>1: matched["count"]-=1
        else: s_zoo.remove(matched)
        su["animals"]=s_zoo
        t_zoo=tu.get("animals",[]); t_found=next((z for z in t_zoo if z["name"]==trade["item_name"]),None)
        if t_found: t_found["count"]=t_found.get("count",1)+1
        else:
            a_data=find_animal_data(trade["item_name"])
            t_zoo.append({"name":trade["item_name"],"rarity":a_data["rarity"] if a_data else "common","count":1})
        tu["animals"]=t_zoo; item_display=trade["item_name"]
    else:
        w_key=trade["item_name"]
        if su.get("weapon")!=w_key: await query.edit_message_text("❌ Seller no longer has this weapon!"); return
        su["weapon"]="stick"; tu["weapon"]=w_key; item_display=WEAPONS[w_key]["name"]
    tu["coins"]=tu.get("coins",0)-price; su["coins"]=su.get("coins",0)+price
    su["total_coins_ever"]=su.get("total_coins_ever",0)+price
    award_badge(su,"trader"); award_badge(tu,"trader"); trade["status"]="done"; save_data(data)
    await query.edit_message_text(f"✅ *Trade Done!*\n{tname} bought *{item_display}* from {sname}\n💰 {price} 🪙 transferred",parse_mode="Markdown")

# ══════════════════════════════════════════════════════════════════════════════
#  AUCTION
# ══════════════════════════════════════════════════════════════════════════════
async def cmd_auction(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text(
            "🏷️ *AUCTION HOUSE*\n`/auction list` | `/auction sell animal Dragon 200` | `/auction bid <id> <amount>`",
            parse_mode="Markdown"); return
    sub=context.args[0].lower(); user=update.message.from_user; chat_id=update.message.chat_id
    data=load_data(); data.setdefault("auctions",{})
    if sub=="list":
        auctions=data.get("auctions",{})
        active={aid:a for aid,a in auctions.items() if a["status"]=="open" and datetime.fromisoformat(a["expires_at"])>datetime.now()}
        if not active: await update.message.reply_text("🏷️ No active auctions!"); return
        lines=["🏷️ *ACTIVE AUCTIONS*\n━━━━━━━━━━━━━"]
        for aid,a in list(active.items())[:10]:
            rem=int((datetime.fromisoformat(a["expires_at"])-datetime.now()).total_seconds()//60)
            short_id=aid.split("_")[-1][-6:]
            lines.append(f"🔹 *{a['item_display']}* | Bid: *{a['top_bid']} 🪙* | {rem}m | ID: `{short_id}`")
        await update.message.reply_text("\n".join(lines),parse_mode="Markdown"); return
    if sub=="sell":
        if len(context.args)<4: await update.message.reply_text("Usage: `/auction sell animal Dragon 200`",parse_mode="Markdown"); return
        item_type=context.args[1].lower()
        try: start_bid=int(context.args[-1])
        except: await update.message.reply_text("❌ Last arg must be starting bid."); return
        item_name_raw=" ".join(context.args[2:-1]).strip()
        u=get_user(data,user.id,user.username,user.full_name)
        if item_type=="animal":
            zoo=u.get("animals",[]); matched=next((z for z in zoo if item_name_raw.lower() in z["name"].lower()),None)
            if not matched: await update.message.reply_text(f"❌ '{item_name_raw}' not in zoo!"); return
            display_name=matched["name"]
            if matched.get("count",1)>1: matched["count"]-=1
            else: zoo.remove(matched)
            u["animals"]=zoo
        elif item_type=="weapon":
            w_key=next((k for k in WEAPONS if item_name_raw.lower() in WEAPONS[k]["name"].lower()),None)
            if not w_key or u.get("weapon")!=w_key: await update.message.reply_text(f"❌ You don't own '{item_name_raw}'!"); return
            if w_key=="stick": await update.message.reply_text("❌ Can't auction the stick!"); return
            display_name=WEAPONS[w_key]["name"]; u["weapon"]="stick"
        else: await update.message.reply_text("❌ Type must be `animal` or `weapon`.",parse_mode="Markdown"); return
        expires_at=(datetime.now()+timedelta(hours=1)).isoformat()
        auction_id=f"auc_{user.id}_{int(datetime.now().timestamp())}"
        sname=f"@{user.username}" if user.username else user.full_name
        data["auctions"][auction_id]={"seller_id":user.id,"seller_name":sname,"item_type":item_type,"item_name":display_name if item_type=="animal" else w_key,"item_display":display_name,"start_bid":start_bid,"top_bid":start_bid,"top_bidder_id":None,"top_bidder_name":None,"status":"open","expires_at":expires_at,"chat_id":chat_id}
        save_data(data)
        short_id=auction_id.split("_")[-1][-6:]
        await update.message.reply_text(f"🏷️ *Auction Listed!*\n*{display_name}* | Start: *{start_bid} 🪙*\nID: `{short_id}` | Ends in 1h",parse_mode="Markdown")
        context.job_queue.run_once(lambda ctx:asyncio.ensure_future(_close_auction(ctx,auction_id)),when=3600,name=f"auction_{auction_id}")
        return
    if sub=="bid":
        if len(context.args)<3: await update.message.reply_text("Usage: `/auction bid <id> <amount>`",parse_mode="Markdown"); return
        short_id=context.args[1]
        try: bid_amount=int(context.args[2])
        except: await update.message.reply_text("❌ Bid must be a number."); return
        full_id=next((aid for aid in data.get("auctions",{}) if aid.endswith(short_id)),None)
        if not full_id: await update.message.reply_text("❌ Auction not found!"); return
        auction=data["auctions"][full_id]
        if auction["status"]!="open": await update.message.reply_text("❌ Auction closed!"); return
        if datetime.fromisoformat(auction["expires_at"])<datetime.now(): await update.message.reply_text("❌ Expired!"); return
        if auction["seller_id"]==user.id: await update.message.reply_text("❌ Can't bid on your own!"); return
        if bid_amount<=auction["top_bid"]: await update.message.reply_text(f"❌ Bid must beat *{auction['top_bid']} 🪙*!",parse_mode="Markdown"); return
        u=get_user(data,user.id,user.username,user.full_name)
        if u.get("coins",0)<bid_amount: await update.message.reply_text(f"❌ Not enough coins!"); return
        bname=f"@{user.username}" if user.username else user.full_name
        auction["top_bid"]=bid_amount; auction["top_bidder_id"]=user.id; auction["top_bidder_name"]=bname
        save_data(data)
        await update.message.reply_text(f"✅ *Bid placed!*\n*{auction['item_display']}* | Your bid: *{bid_amount} 🪙*",parse_mode="Markdown")
        return
    await update.message.reply_text("Use: `/auction list` | `/auction sell` | `/auction bid`",parse_mode="Markdown")

async def _close_auction(context, auction_id):
    data=load_data(); auctions=data.get("auctions",{})
    if auction_id not in auctions: return
    auction=auctions[auction_id]
    if auction["status"]!="open": return
    auction["status"]="closed"; chat_id=auction.get("chat_id")
    seller_id=auction["seller_id"]; winner_id=auction.get("top_bidder_id")
    su=get_user(data,seller_id); item_display=auction["item_display"]
    if not winner_id:
        if auction["item_type"]=="animal":
            zoo=su.get("animals",[]); a_data=find_animal_data(auction["item_name"])
            zoo.append({"name":auction["item_name"],"rarity":a_data["rarity"] if a_data else "common","count":1}); su["animals"]=zoo
        else: su["weapon"]=auction["item_name"]
        save_data(data)
        try: await context.bot.send_message(chat_id,f"🏷️ Auction ended — no bids.\n*{item_display}* returned to {auction['seller_name']}.",parse_mode="Markdown")
        except: pass
        return
    wu=get_user(data,winner_id); bid=auction["top_bid"]
    if wu.get("coins",0)<bid:
        if auction["item_type"]=="animal":
            zoo=su.get("animals",[]); zoo.append({"name":auction["item_name"],"rarity":"common","count":1}); su["animals"]=zoo
        else: su["weapon"]=auction["item_name"]
        save_data(data)
        try: await context.bot.send_message(chat_id,f"🏷️ Auction failed! Winner couldn't pay.\n*{item_display}* returned.",parse_mode="Markdown")
        except: pass
        return
    wu["coins"]=wu.get("coins",0)-bid; su["coins"]=su.get("coins",0)+bid; su["total_coins_ever"]=su.get("total_coins_ever",0)+bid
    if auction["item_type"]=="animal":
        t_zoo=wu.get("animals",[]); found=next((z for z in t_zoo if z["name"]==auction["item_name"]),None)
        if found: found["count"]=found.get("count",1)+1
        else:
            a_data=find_animal_data(auction["item_name"])
            t_zoo.append({"name":auction["item_name"],"rarity":a_data["rarity"] if a_data else "common","count":1})
        wu["animals"]=t_zoo
    else: wu["weapon"]=auction["item_name"]
    save_data(data)
    wname=auction.get("top_bidder_name","?"); sname=auction.get("seller_name","?")
    try: await context.bot.send_message(chat_id,f"🏷️ *Auction Closed!*\n*{item_display}* → *{wname}* for *{bid} 🪙*\n{sname} received coins!",parse_mode="Markdown")
    except: pass

# ══════════════════════════════════════════════════════════════════════════════
#  PRAY
# ══════════════════════════════════════════════════════════════════════════════
async def cmd_pray(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user=update.message.from_user; data=load_data()
    u=get_user(data,user.id,user.username,user.full_name)
    last_pray=u.get("last_pray")
    if last_pray:
        elapsed=(datetime.now()-datetime.fromisoformat(last_pray)).total_seconds()
        if elapsed<1800:
            remaining=int(1800-elapsed)
            await update.message.reply_text(f"🙏 Already prayed! Next in *{remaining//60}m {remaining%60}s*.",parse_mode="Markdown"); return
    u["pray_active"]=True; u["pray_expires"]=(datetime.now()+timedelta(minutes=10)).isoformat(); u["last_pray"]=datetime.now().isoformat()
    save_data(data)
    name=f"@{user.username}" if user.username else user.full_name
    PRAY_MSGS=["🙏 The gods hear your prayer...\nLuck is on your side for 10 minutes! +15% win chance.","✨ Divine blessing!\nGambling odds improved for 10 minutes!","🌟 The universe aligns!\n10 minutes of boosted luck!","🕊️ Forge gods grant you luck for 10 minutes!"]
    await update.message.reply_text(f"{random.choice(PRAY_MSGS)}\n\n_{name}'s next 10 min gambling: +15% boost!_",parse_mode="Markdown")

# ══════════════════════════════════════════════════════════════════════════════
#  CHESS
# ══════════════════════════════════════════════════════════════════════════════
_chess_setup = {}
CHESS_TIME_PRESETS = [("Unlimited", 0), ("1 min", 60), ("3 min", 180), ("5 min", 300), ("10 min", 600), ("15 min", 900)]
CHESS_DIFFICULTY_LABELS = [
    "1. Total Beginner", "2. Just Learned", "3. Casual", "4. Club Novice",
    "5. Club Player", "6. Solid Club", "7. Strong Club", "8. Expert",
    "9. Candidate Master", "10. National Master", "11. FIDE Master",
    "12. International Master", "13. Grandmaster", "14. Super-GM",
    "15. World Class", "16. Maximum (engine-strength)",
]

async def _chess_api(method: str, path: str, **kwargs):
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.request(method, f"{CHESS_SERVER_URL}{path}", **kwargs)
            if resp.status_code >= 400: return False, resp.text
            return True, resp.json()
    except Exception as e: return False, str(e)

def _chess_open_board_button(game_id: str, uid: int, name: str) -> InlineKeyboardMarkup:
    url = f"{CHESS_WEBAPP_URL}/?game={game_id}&uid={uid}&name={quote(name)}"
    return InlineKeyboardMarkup([[InlineKeyboardButton("♟️ Open Chess Board", web_app=WebAppInfo(url=url))]])

async def cmd_chess(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user; _chess_setup[user.id] = {}
    kb = [
        [InlineKeyboardButton("🤖 Play vs Bot", callback_data="chess_mode_bot")],
        [InlineKeyboardButton("👥 Play vs Friend (link/code)", callback_data="chess_mode_friend")],
        [InlineKeyboardButton("🎲 Random Opponent", callback_data="chess_mode_random")],
        [InlineKeyboardButton("📊 My Rating", callback_data="chess_rating"), InlineKeyboardButton("🏆 Leaderboard", callback_data="chess_lb")],
    ]
    await update.message.reply_text(
        "♟️ *Aira Chess*\n━━━━━━━━━━━━━\nFull rules engine — castling, en passant, "
        "promotion, stalemate, threefold, the lot — plus real Elo-style ratings.\n\nPick a mode:",
        reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")

async def cmd_chessrating(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user; ok, res = await _chess_api("GET", f"/api/rating/{user.id}")
    if not ok:
        await update.message.reply_text("♟️ Couldn't reach the chess service."); return
    await update.message.reply_text(
        f"📊 *{user.full_name}'s Chess Rating*\n━━━━━━━━━━━━━\n"
        f"⭐ Rating: *{res.get('rating', 1200)}*\n"
        f"✅ Wins: *{res.get('wins',0)}* | ❌ Losses: *{res.get('losses',0)}* | 🤝 Draws: *{res.get('draws',0)}*\n"
        f"🏔️ Peak: *{res.get('peak_rating', res.get('rating',1200))}*", parse_mode="Markdown")

async def cmd_chessleaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ok, res = await _chess_api("GET", "/api/leaderboard")
    if not ok: await update.message.reply_text("♟️ Couldn't reach the chess service."); return
    medals = ["🥇","🥈","🥉","4️⃣","5️⃣","6️⃣","7️⃣","8️⃣","9️⃣","🔟"]
    lines = ["🏆 *CHESS LEADERBOARD*\n━━━━━━━━━━━━━"]
    for i, row in enumerate(res.get("leaderboard", [])[:10]):
        lines.append(f"{medals[i]} {row.get('name','?')} — *{row.get('rating',1200)}* "
                     f"({row.get('wins',0)}W/{row.get('losses',0)}L/{row.get('draws',0)}D)")
    if len(lines) == 1: lines.append("No rated games yet — be the first with /chess!")
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")

async def handle_chess_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query; await query.answer()
    user = query.from_user; data_str = query.data; setup = _chess_setup.setdefault(user.id, {})
    if data_str == "chess_rating":
        ok, res = await _chess_api("GET", f"/api/rating/{user.id}")
        if not ok: await query.edit_message_text("♟️ Couldn't reach the chess service."); return
        await query.edit_message_text(
            f"📊 *Your Chess Rating*\n⭐ *{res.get('rating',1200)}*\n"
            f"✅{res.get('wins',0)} ❌{res.get('losses',0)} 🤝{res.get('draws',0)}", parse_mode="Markdown")
        return
    if data_str == "chess_lb":
        ok, res = await _chess_api("GET", "/api/leaderboard")
        if not ok: await query.edit_message_text("♟️ Couldn't reach the chess service."); return
        medals = ["🥇","🥈","🥉","4️⃣","5️⃣","6️⃣","7️⃣","8️⃣","9️⃣","🔟"]
        lines = ["🏆 *CHESS LEADERBOARD*"]
        for i, row in enumerate(res.get("leaderboard", [])[:10]):
            lines.append(f"{medals[i]} {row.get('name','?')} — *{row.get('rating',1200)}*")
        await query.edit_message_text("\n".join(lines), parse_mode="Markdown"); return
    if data_str.startswith("chess_mode_"):
        setup["mode"] = data_str.replace("chess_mode_", "")
        kb = [[InlineKeyboardButton("⚪ White", callback_data="chess_color_white"),
               InlineKeyboardButton("⚫ Black", callback_data="chess_color_black"),
               InlineKeyboardButton("🎲 Random", callback_data="chess_color_random")]]
        await query.edit_message_text("🎨 Pick your color:", reply_markup=InlineKeyboardMarkup(kb)); return
    if data_str.startswith("chess_color_"):
        setup["color"] = data_str.replace("chess_color_", "")
        kb = [[InlineKeyboardButton(label, callback_data=f"chess_time_{secs}")] for label, secs in CHESS_TIME_PRESETS]
        kb.append([InlineKeyboardButton("✍️ Custom (type seconds)", callback_data="chess_time_custom")])
        await query.edit_message_text("⏱️ Pick a time control:", reply_markup=InlineKeyboardMarkup(kb)); return
    if data_str == "chess_time_custom":
        setup["awaiting_custom_time"] = True
        await query.edit_message_text("✍️ Type the time control in seconds (e.g. `120` for 2 min, `0` for unlimited).", parse_mode="Markdown"); return
    if data_str.startswith("chess_time_"):
        setup["time_control"] = int(data_str.replace("chess_time_", ""))
        await _chess_continue_after_time(query, context, user, setup); return
    if data_str.startswith("chess_diff_"):
        setup["difficulty"] = int(data_str.replace("chess_diff_", ""))
        await _chess_finalize(query, context, user, setup); return

async def _handle_chess_custom_time(update: Update, context: ContextTypes.DEFAULT_TYPE, setup: dict):
    text = update.message.text.strip()
    try: secs = max(0, min(int(text), 24 * 3600))
    except ValueError:
        await update.message.reply_text("❌ Please send a plain number of seconds (e.g. `300`).", parse_mode="Markdown"); return
    setup["awaiting_custom_time"] = False; setup["time_control"] = secs
    await _chess_continue_after_time(update, context, update.message.from_user, setup, is_message=True)

async def _chess_continue_after_time(target, context, user, setup, is_message=False):
    send = (target.reply_text if is_message else target.edit_message_text)
    if setup.get("mode") == "bot":
        kb = [[InlineKeyboardButton(CHESS_DIFFICULTY_LABELS[i], callback_data=f"chess_diff_{i+1}")] for i in range(16)]
        rows = [kb[i] + (kb[i+1] if i+1 < len(kb) else []) for i in range(0, len(kb), 2)]
        await send("🤖 Pick bot difficulty (1 = easiest, 16 = strongest):", reply_markup=InlineKeyboardMarkup(rows)); return
    await _chess_finalize(target, context, user, setup, is_message=is_message)

async def _chess_finalize(target, context, user, setup, is_message=False):
    send = (target.reply_text if is_message else target.edit_message_text)
    name = f"@{user.username}" if user.username else user.full_name
    color = setup.get("color", "random"); time_control = setup.get("time_control", 0); mode = setup.get("mode")
    if mode == "bot":
        ok, res = await _chess_api("POST", "/api/game/vsbot", json={"uid": user.id, "name": name, "color": color, "time_control": time_control, "level": setup.get("difficulty", 1)})
        if not ok: await send("♟️ Couldn't reach the chess service."); return
        await send(f"♟️ *Game ready!* vs Bot (Level {setup.get('difficulty',1)})\nTap below to play:", reply_markup=_chess_open_board_button(res["game_id"], user.id, name), parse_mode="Markdown")
    elif mode == "friend":
        ok, res = await _chess_api("POST", "/api/room/create", json={"uid": user.id, "name": name, "color": color, "time_control": time_control})
        if not ok: await send("♟️ Couldn't reach the chess service."); return
        game_id, room_code = res["game_id"], res["room_code"]
        try:
            bot_me = await context.bot.get_me(); deep_link = f"[https://t.me/](https://t.me/){bot_me.username}?start=chess_{room_code}"
        except Exception: deep_link = f"(open the bot and send) /chessjoin {room_code}"
        await send(f"♟️ *Room created!*\nRoom code: `{room_code}`\n\nShare this link with your friend:\n{deep_link}\n\nOr they can type `/chessjoin {room_code}`.\n\nYour board:", reply_markup=_chess_open_board_button(game_id, user.id, name), parse_mode="Markdown")
    else:
        ok, res = await _chess_api("POST", "/api/queue/join", json={"uid": user.id, "name": name, "color": color, "time_control": time_control})
        if not ok: await send("♟️ Couldn't reach the chess service."); return
        if res.get("queued"): await send("🎲 Looking for an opponent... you'll get a message here the moment someone matches!")
        else: await send("🎲 *Matched!* Tap below to play:", reply_markup=_chess_open_board_button(res["game_id"], user.id, name), parse_mode="Markdown")
    _chess_setup.pop(user.id, None)

async def cmd_chessjoin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    if not context.args: await update.message.reply_text("Usage: `/chessjoin <room code>`", parse_mode="Markdown"); return
    room_code = context.args[0].upper(); name = f"@{user.username}" if user.username else user.full_name
    ok, res = await _chess_api("POST", "/api/room/join", json={"room_code": room_code, "uid": user.id, "name": name})
    if not ok: await update.message.reply_text(f"❌ Couldn't join that room: {res}"); return
    await update.message.reply_text("♟️ *Joined!* Tap below to play:", reply_markup=_chess_open_board_button(res["game_id"], user.id, name), parse_mode="Markdown")

# ══════════════════════════════════════════════════════════════════════════════
#  MAIN
# ══════════════════════════════════════════════════════════════════════════════
def main():
    app=Application.builder().token(BOT_TOKEN).build()
    handlers=[
        ("start",cmd_start),("help",cmd_help),("challenge",cmd_challenge),
        ("wallet",cmd_wallet),("stats",cmd_stats),("leaderboard",cmd_leaderboard),
        ("daily",cmd_daily),("give",cmd_give),("streak",cmd_streak),
        ("badges",cmd_badges),("shop",cmd_shop),("settitle",cmd_settitle),
        ("pinit",cmd_pinit),("skipit",cmd_skipit),("hint",cmd_hint),
        ("hunt",cmd_hunt),("zoo",cmd_zoo),("owoprofile",cmd_owoprofile),
        ("autohunt",cmd_autohunt),("battle",cmd_battle),
        ("sell",cmd_sell),("gemshop",cmd_gemshop),
        ("topanimals",cmd_topanimals),("trade",cmd_trade),
        ("cf",cmd_cf),("s",cmd_slots),("dice",cmd_dice),
        ("ask",cmd_ask),("pomodoro",cmd_pomodoro),
        ("ban",cmd_ban),("unban",cmd_unban),("kick",cmd_kick),
        ("timeout",cmd_timeout),("untimeout",cmd_untimeout),
        ("purge",cmd_purge),("warn",cmd_warn),("warns",cmd_warns),
        ("clearwarns",cmd_clearwarns),("setwelcome",cmd_setwelcome),
        ("setbye",cmd_setbye),("forgewar",cmd_forgewar),
        ("setteam",cmd_setteam),("inventory",cmd_inventory),
        ("equipweapon",cmd_equipweapon),("pvp",cmd_pvp),
        ("tradeitem",cmd_tradeitem),("auction",cmd_auction),
        ("pray",cmd_pray),("tnd",cmd_tnd),
        ("truth",cmd_truth),("dare",cmd_dare),
        ("spy",cmd_spy),
        ("chess",cmd_chess),("chessjoin",cmd_chessjoin),
        ("chessrating",cmd_chessrating),("chessleaderboard",cmd_chessleaderboard),
    ]
    for cmd,fn in handlers: app.add_handler(CommandHandler(cmd,fn))

    app.add_handler(CallbackQueryHandler(handle_shop_purchase, pattern="^buy_"))
    app.add_handler(CallbackQueryHandler(handle_leaderboard_tab, pattern="^lb_"))
    app.add_handler(CallbackQueryHandler(handle_gem_purchase, pattern="^gbuy_"))
    app.add_handler(CallbackQueryHandler(handle_trade, pattern="^tacpt_|^tdecl_"))
    app.add_handler(CallbackQueryHandler(handle_pvp, pattern="^pvpacpt_|^pvpdecl_"))
    app.add_handler(CallbackQueryHandler(handle_item_trade, pattern="^tiacpt_|^tidecl_"))
    app.add_handler(CallbackQueryHandler(handle_tnd_choice, pattern="^tnd_(truth|dare)_"))
    app.add_handler(CallbackQueryHandler(handle_tnd_next, pattern="^tnd_next_"))
    app.add_handler(CallbackQueryHandler(handle_chess_callback, pattern="^chess_"))
    app.add_handler(PollAnswerHandler(handle_spy_poll_answer))

    app.add_handler(ChatMemberHandler(handle_member_update, ChatMemberHandler.CHAT_MEMBER))
    app.add_handler(MessageHandler(filters.PHOTO & ~filters.COMMAND, handle_message))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info("✅ Aira v8 patched running — DM AutoHunt, Admin Toggle, Spy Game, AI Challenges")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
ENDOFFILE
