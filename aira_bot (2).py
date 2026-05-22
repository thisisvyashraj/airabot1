"""
Aira – Ultimate Telegram Study + Game Bot
Forge Coins • OWO hunting • Admin tools • Challenges • Shop • Badges
"""

import logging, random, asyncio, json, os, re
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ChatPermissions
from telegram.error import TelegramError
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, filters, ContextTypes,
)

# ══════════════════════════════════════════════════════════
#  CONFIG
# ══════════════════════════════════════════════════════════
BOT_TOKEN          = "8823107490:AAGPfcyAz4lKTzMCOENhUSOgjjO_jzRozmc"
CHALLENGE_TIMEOUT  = 300          # 5 min
CHALLENGE_COOLDOWN = 300          # 5 min cooldown between /challenge calls
INTERVAL_MIN       = 1800
INTERVAL_MAX       = 5400
STREAK_BONUS       = 2
DATA_FILE          = "aira_data.json"
TITLE_HOURS        = 24
EVERGREEN_CODE     = "AIRA-FORGE-INFINITE"   # never expires, adds coins each use

logging.basicConfig(format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

# ══════════════════════════════════════════════════════════
#  ONE-TIME CHEAT CODES  (500 coins each)
# ══════════════════════════════════════════════════════════
CHEAT_CODES = {
    "FORGE-ALPHA-7X2Q": 500, "AIRA-SECRET-K9MP": 500,
    "COINS-BLAST-3RNV": 500, "VAULT-OPEN-Z5TW":  500,
    "MINT-RUSH-8YCL":   500, "FORGE-DELTA-4PXJ": 500,
    "AIRA-PRIME-6KQB":  500, "COINS-MAX-2HFG":   500,
    "SHADOW-KEY-9LMR":  500, "AIRA-OMEGA-7VNS":  500,
    "FORGE-NOVA-3ZKP":  500, "LUCKY-PULL-5TGX":  500,
    "AIRA-BOOST-1WQM":  500, "COINS-DROP-8YBF":  500,
    "VAULT-CODE-4RJH":  500, "FORGE-ULTRA-2MPK": 500,
    "AIRA-FLASH-6XNQ":  500, "COINS-FIRE-9LVT":  500,
    "MINT-KING-7GZR":   500, "FORGE-FINAL-3CWY": 500,
    # 200-coin codes
    "MINI-BOOST-A1BC":  200, "QUICK-CASH-D2EF":  200,
    "SMALL-WIN-G3HI":   200, "EASY-COIN-J4KL":   200,
    "FAST-MINT-M5NO":   200,
}

# ══════════════════════════════════════════════════════════
#  OWO ANIMALS
# ══════════════════════════════════════════════════════════
ANIMALS = [
    {"name":"🐭 Mouse",      "rarity":"common",    "coins":5,   "owo":1},
    {"name":"🐱 Cat",        "rarity":"common",    "coins":6,   "owo":1},
    {"name":"🐶 Dog",        "rarity":"common",    "coins":6,   "owo":1},
    {"name":"🐰 Rabbit",     "rarity":"common",    "coins":7,   "owo":1},
    {"name":"🦊 Fox",        "rarity":"uncommon",  "coins":10,  "owo":2},
    {"name":"🐺 Wolf",       "rarity":"uncommon",  "coins":12,  "owo":2},
    {"name":"🦝 Raccoon",    "rarity":"uncommon",  "coins":11,  "owo":2},
    {"name":"🐗 Boar",       "rarity":"uncommon",  "coins":13,  "owo":2},
    {"name":"🦌 Deer",       "rarity":"rare",      "coins":18,  "owo":3},
    {"name":"🐻 Bear",       "rarity":"rare",      "coins":20,  "owo":3},
    {"name":"🐯 Tiger",      "rarity":"rare",      "coins":22,  "owo":3},
    {"name":"🦁 Lion",       "rarity":"rare",      "coins":25,  "owo":4},
    {"name":"🐘 Elephant",   "rarity":"epic",      "coins":35,  "owo":5},
    {"name":"🦏 Rhino",      "rarity":"epic",      "coins":38,  "owo":5},
    {"name":"🦍 Gorilla",    "rarity":"epic",      "coins":40,  "owo":5},
    {"name":"🐉 Dragon",     "rarity":"legendary", "coins":100, "owo":15},
    {"name":"🦄 Unicorn",    "rarity":"legendary", "coins":90,  "owo":12},
    {"name":"🔱 Leviathan",  "rarity":"legendary", "coins":120, "owo":20},
]

RARITY_WEIGHTS = {"common":50,"uncommon":28,"rare":14,"epic":6,"legendary":2}

RARITY_COLORS = {
    "common":"⬜","uncommon":"🟩","rare":"🟦","epic":"🟪","legendary":"🟡"
}

HUNT_FAIL_MSGS = [
    "You crept through the forest... but found nothing 🍃",
    "The animals sensed you coming and ran away 🌿",
    "You set a trap but something ate your bait 😅",
    "Close call! The animal escaped at the last second 💨",
    "You spotted tracks... but lost the trail 🐾",
]

BATTLE_ANIMALS = [
    {"name":"🐍 Snake",   "hp":30, "atk":8},
    {"name":"🦂 Scorpion","hp":25, "atk":10},
    {"name":"🐊 Croc",    "hp":50, "atk":12},
    {"name":"🐻 Bear",    "hp":60, "atk":15},
    {"name":"🐯 Tiger",   "hp":55, "atk":18},
    {"name":"🐉 Dragon",  "hp":120,"atk":30},
]

# ══════════════════════════════════════════════════════════
#  QUESTION BANK  (120 questions)
# ══════════════════════════════════════════════════════════
QUESTIONS = [
    # ── MATH (30) ──────────────────────────────────────────
    {"type":"math","q":"🔢 What is 15 × 13?","a":["195"],"hint":"15×10=150 then +45","coins":10},
    {"type":"math","q":"🔢 √144 = ?","a":["12"],"hint":"12×12=?","coins":10},
    {"type":"math","q":"🔢 Solve: 2x+6=20","a":["7"],"hint":"Subtract 6 first","coins":12},
    {"type":"math","q":"🔢 25% of 200 = ?","a":["50"],"hint":"1/4 of 200","coins":8},
    {"type":"math","q":"🔢 7³ = ?","a":["343"],"hint":"7×7=49 then ×7","coins":12},
    {"type":"math","q":"🔢 π to 2 decimals?","a":["3.14"],"hint":"Starts 3.1...","coins":8},
    {"type":"math","q":"🔢 LCM of 4 and 6?","a":["12"],"hint":"Smallest divisible by both","coins":10},
    {"type":"math","q":"🔢 HCF of 36 and 48?","a":["12"],"hint":"List factors","coins":12},
    {"type":"math","q":"🔢 Triangle: 60°+80°+?=180°","a":["40","40°"],"hint":"180-140","coins":10},
    {"type":"math","q":"🔢 0.5 as fraction?","a":["1/2"],"hint":"Half","coins":8},
    {"type":"math","q":"🔢 3²+4²=?","a":["25"],"hint":"Pythagoras!","coins":10},
    {"type":"math","q":"🔢 1000÷25=?","a":["40"],"hint":"40×25=1000","coins":8},
    {"type":"math","q":"🔢 Perimeter, square side 7cm?","a":["28","28cm"],"hint":"4 sides","coins":8},
    {"type":"math","q":"🔢 18²=?","a":["324"],"hint":"(20-2)²","coins":12},
    {"type":"math","q":"🔢 5/10+3/10=?","a":["8/10","4/5"],"hint":"Add numerators","coins":8},
    {"type":"math","q":"🔢 2⁸=?","a":["256"],"hint":"Double 8 times","coins":12},
    {"type":"math","q":"🔢 Area of 8×5 rectangle?","a":["40"],"hint":"L×W","coins":8},
    {"type":"math","q":"🔢 5x=75, x=?","a":["15"],"hint":"Divide by 5","coins":10},
    {"type":"math","q":"🔢 √81=?","a":["9"],"hint":"9×9","coins":8},
    {"type":"math","q":"🔢 2/5 as percentage?","a":["40","40%"],"hint":"×100","coins":8},
    {"type":"math","q":"🔢 Volume of cube, side 3?","a":["27"],"hint":"3³","coins":10},
    {"type":"math","q":"🔢 11²=?","a":["121"],"hint":"11×11","coins":8},
    {"type":"math","q":"🔢 Speed 60km/h × 2.5h = ?","a":["150","150km"],"hint":"S×T","coins":12},
    {"type":"math","q":"🔢 5! (factorial) = ?","a":["120"],"hint":"5×4×3×2×1","coins":12},
    {"type":"math","q":"🔢 Median of 3,7,9,11,15?","a":["9"],"hint":"Middle value","coins":10},
    {"type":"math","q":"🔢 Sum of angles in quadrilateral?","a":["360","360°"],"hint":"Two triangles","coins":10},
    {"type":"math","q":"🔢 Convert 3/4 to decimal","a":["0.75"],"hint":"75 hundredths","coins":8},
    {"type":"math","q":"🔢 17×3=?","a":["51"],"hint":"17×3","coins":8},
    {"type":"math","q":"🔢 100²=?","a":["10000"],"hint":"100×100","coins":8},
    {"type":"math","q":"🔢 13×7=?","a":["91"],"hint":"91","coins":10},

    # ── SCIENCE (30) ───────────────────────────────────────
    {"type":"trivia","q":"🔬 Chemical formula of water?","a":["h2o"],"hint":"2H 1O","coins":8},
    {"type":"trivia","q":"🔬 Speed of light in km/s?","a":["300000","3×10^5"],"hint":"3 followed by 5 zeros","coins":12},
    {"type":"trivia","q":"🔬 The Red Planet?","a":["mars"],"hint":"4th from Sun","coins":8},
    {"type":"trivia","q":"🔬 Newton's 2nd Law?","a":["f=ma","f = ma"],"hint":"Force=Mass×?","coins":12},
    {"type":"trivia","q":"🔬 Atomic number of Carbon?","a":["6"],"hint":"Period 2 Group 14","coins":10},
    {"type":"trivia","q":"🔬 Gas plants absorb in photosynthesis?","a":["carbon dioxide","co2"],"hint":"We breathe it out","coins":8},
    {"type":"trivia","q":"🔬 Unit of electric current?","a":["ampere","amp","a"],"hint":"French physicist","coins":8},
    {"type":"trivia","q":"🔬 Bones in adult human body?","a":["206"],"hint":"200-210 range","coins":10},
    {"type":"trivia","q":"🔬 Chemical symbol for Gold?","a":["au"],"hint":"Latin: Aurum","coins":8},
    {"type":"trivia","q":"🔬 Powerhouse of cell?","a":["mitochondria"],"hint":"Makes ATP","coins":8},
    {"type":"trivia","q":"🔬 SI unit of energy?","a":["joule","j"],"hint":"James Prescott ___","coins":8},
    {"type":"trivia","q":"🔬 Formula of table salt?","a":["nacl"],"hint":"Na+Cl","coins":10},
    {"type":"trivia","q":"🔬 Boiling point of water °C?","a":["100","100°c"],"hint":"Standard pressure","coins":8},
    {"type":"trivia","q":"🔬 Particle with negative charge?","a":["electron","electrons"],"hint":"Orbits nucleus","coins":8},
    {"type":"trivia","q":"🔬 Chemical symbol for Iron?","a":["fe"],"hint":"Latin: Ferrum","coins":8},
    {"type":"trivia","q":"🔬 Hardest natural substance?","a":["diamond"],"hint":"Form of carbon","coins":8},
    {"type":"trivia","q":"🔬 Most of Earth's atmosphere?","a":["nitrogen","n2"],"hint":"~78%","coins":10},
    {"type":"trivia","q":"🔬 Unit of force?","a":["newton","n"],"hint":"Sir Isaac ___","coins":8},
    {"type":"trivia","q":"🔬 Human heart chambers?","a":["4","four"],"hint":"2 atria + 2 ventricles","coins":10},
    {"type":"trivia","q":"🔬 Planet with most moons?","a":["saturn"],"hint":"Has rings","coins":10},
    {"type":"trivia","q":"🔬 pH of pure water?","a":["7"],"hint":"Neutral","coins":8},
    {"type":"trivia","q":"🔬 Who discovered Penicillin?","a":["alexander fleming","fleming"],"hint":"Scottish, 1928","coins":10},
    {"type":"trivia","q":"🔬 Closest star to Earth?","a":["sun","the sun"],"hint":"We orbit it","coins":6},
    {"type":"trivia","q":"🔬 Organ that produces insulin?","a":["pancreas"],"hint":"Near stomach","coins":10},
    {"type":"trivia","q":"🔬 Freezing point of water °C?","a":["0","0°c"],"hint":"Ice forms","coins":6},
    {"type":"trivia","q":"🔬 Largest planet?","a":["jupiter"],"hint":"Gas giant","coins":8},
    {"type":"trivia","q":"🔬 H2O2 is?","a":["hydrogen peroxide"],"hint":"Antiseptic","coins":10},
    {"type":"trivia","q":"🔬 Speed of sound in air (m/s)?","a":["343","340"],"hint":"~340 m/s","coins":12},
    {"type":"trivia","q":"🔬 Process plants use to make food?","a":["photosynthesis"],"hint":"Uses sunlight+CO2","coins":8},
    {"type":"trivia","q":"🔬 Adult human teeth?","a":["32"],"hint":"Including wisdom teeth","coins":8},

    # ── GENERAL KNOWLEDGE (20) ─────────────────────────────
    {"type":"trivia","q":"🌍 Capital of France?","a":["paris"],"hint":"City of Love","coins":8},
    {"type":"trivia","q":"🌍 How many continents?","a":["7","seven"],"hint":"Asia, Africa...","coins":6},
    {"type":"trivia","q":"🌍 Who wrote Romeo and Juliet?","a":["shakespeare","william shakespeare"],"hint":"English playwright","coins":8},
    {"type":"trivia","q":"🌍 Sides of a hexagon?","a":["6","six"],"hint":"Honeycomb shape","coins":6},
    {"type":"trivia","q":"🌍 Longest river in world?","a":["nile","the nile"],"hint":"In Africa","coins":8},
    {"type":"trivia","q":"🌍 Days in a leap year?","a":["366"],"hint":"Extra Feb day","coins":6},
    {"type":"trivia","q":"🌍 Language with most native speakers?","a":["mandarin","chinese"],"hint":"China","coins":10},
    {"type":"trivia","q":"🌍 Who invented the telephone?","a":["alexander graham bell","graham bell","bell"],"hint":"Scottish-American","coins":8},
    {"type":"trivia","q":"🌍 Colors in a rainbow?","a":["7","seven"],"hint":"VIBGYOR","coins":6},
    {"type":"trivia","q":"🌍 Most populous country (2023)?","a":["india"],"hint":"South Asia","coins":8},
    {"type":"trivia","q":"🌍 Currency of Japan?","a":["yen"],"hint":"¥ symbol","coins":8},
    {"type":"trivia","q":"🌍 Planets in solar system?","a":["8","eight"],"hint":"Pluto demoted","coins":6},
    {"type":"trivia","q":"🌍 Who painted Mona Lisa?","a":["leonardo da vinci","da vinci","leonardo"],"hint":"Italian Renaissance","coins":8},
    {"type":"trivia","q":"🌍 Smallest country in world?","a":["vatican","vatican city"],"hint":"Inside Rome","coins":10},
    {"type":"trivia","q":"🌍 WW2 ended in which year?","a":["1945"],"hint":"Mid-40s","coins":8},
    {"type":"trivia","q":"🌍 Capital of Japan?","a":["tokyo"],"hint":"Where Godzilla attacks","coins":6},
    {"type":"trivia","q":"🌍 How many strings on a guitar?","a":["6","six"],"hint":"Standard guitar","coins":6},
    {"type":"trivia","q":"🌍 Author of Harry Potter?","a":["jk rowling","rowling","j.k. rowling"],"hint":"British author","coins":8},
    {"type":"trivia","q":"🌍 Tallest mountain?","a":["mount everest","everest"],"hint":"In Himalayas","coins":8},
    {"type":"trivia","q":"🌍 How many zeros in a billion?","a":["9","nine"],"hint":"1,000,000,000","coins":8},

    # ── WORD / SPEED (25) ─────────────────────────────────
    {"type":"word","q":"⚡ SPEED! First to type *FORGE* wins!","a":["forge"],"hint":"The name of our coins","coins":15},
    {"type":"word","q":"⚡ SPEED! First to type *PHOTON* wins!","a":["photon"],"hint":"Particle of light","coins":15},
    {"type":"word","q":"⚡ SPEED! First to type *QUANTUM* wins!","a":["quantum"],"hint":"Physics term","coins":15},
    {"type":"word","q":"⚡ SPEED! First to type *NUCLEUS* wins!","a":["nucleus"],"hint":"Centre of atom","coins":15},
    {"type":"word","q":"⚡ SPEED! First to type *GRAVITY* wins!","a":["gravity"],"hint":"What brings apples down","coins":15},
    {"type":"word","q":"⚡ SPEED! First to type *ALGEBRA* wins!","a":["algebra"],"hint":"Maths with x and y","coins":15},
    {"type":"word","q":"⚡ SPEED! First to type *PROTON* wins!","a":["proton"],"hint":"Positive charge","coins":15},
    {"type":"word","q":"⚡ SPEED! First to type *OSMOSIS* wins!","a":["osmosis"],"hint":"Through a membrane","coins":15},
    {"type":"word","q":"⚡ SPEED! First to type *CARBON* wins!","a":["carbon"],"hint":"Element 6","coins":15},
    {"type":"word","q":"⚡ SPEED! First to type *FORMULA* wins!","a":["formula"],"hint":"Maths rule","coins":15},
    {"type":"word","q":"⚡ SPEED! First to type *NEUTRON* wins!","a":["neutron"],"hint":"No charge particle","coins":15},
    {"type":"word","q":"⚡ SPEED! First to type *VELOCITY* wins!","a":["velocity"],"hint":"Speed + direction","coins":15},
    {"type":"word","q":"⚡ SPEED! First to type *ELECTRON* wins!","a":["electron"],"hint":"Negative charge","coins":15},
    {"type":"word","q":"⚡ SPEED! First to type *MOLECULE* wins!","a":["molecule"],"hint":"Atoms bonded","coins":15},
    {"type":"word","q":"⚡ SPEED! First to type *FRICTION* wins!","a":["friction"],"hint":"Resistance to motion","coins":15},
    {"type":"word","q":"⚡ SPEED! First to type *REACTION* wins!","a":["reaction"],"hint":"Chemical process","coins":15},
    {"type":"word","q":"⚡ SPEED! First to type *AIRA* wins!","a":["aira"],"hint":"Our bot's name!","coins":15},
    {"type":"word","q":"⚡ SPEED! First to type *HYDROGEN* wins!","a":["hydrogen"],"hint":"Lightest element","coins":15},
    {"type":"word","q":"⚡ SPEED! First to type *OXYGEN* wins!","a":["oxygen"],"hint":"We breathe it","coins":15},
    {"type":"word","q":"⚡ SPEED! First to type *SCIENCE* wins!","a":["science"],"hint":"Our favourite subject","coins":15},
    {"type":"word","q":"⚡ SPEED! First to type *CHAMPION* wins!","a":["champion"],"hint":"The best player","coins":15},
    {"type":"word","q":"⚡ SPEED! First to type *LEADERBOARD* wins!","a":["leaderboard"],"hint":"Rankings list","coins":15},
    {"type":"word","q":"⚡ SPEED! First to type *BIOLOGY* wins!","a":["biology"],"hint":"Study of life","coins":15},
    {"type":"word","q":"⚡ SPEED! First to type *GEOMETRY* wins!","a":["geometry"],"hint":"Shapes and angles","coins":15},
    {"type":"word","q":"⚡ SPEED! First to type *POLYNOMIAL* wins!","a":["polynomial"],"hint":"Multi-term expression","coins":18},

    # ── IMAGE (15) ────────────────────────────────────────
    {"type":"image","q":"📸 IMAGE CHALLENGE! First to send a photo of something *RED* wins! 🔴","a":[],"hint":"Any red object!","coins":20},
    {"type":"image","q":"📸 IMAGE CHALLENGE! First to send a photo of a *BOOK* wins! 📚","a":[],"hint":"Any book nearby","coins":20},
    {"type":"image","q":"📸 IMAGE CHALLENGE! First to send something *ROUND* wins! ⭕","a":[],"hint":"Circular object","coins":20},
    {"type":"image","q":"📸 IMAGE CHALLENGE! First to send a *SELFIE* wins! 🤳","a":[],"hint":"Quick snap!","coins":20},
    {"type":"image","q":"📸 IMAGE CHALLENGE! First to send a photo of the *SKY* wins! ☁️","a":[],"hint":"Look up and snap","coins":20},
    {"type":"image","q":"📸 IMAGE CHALLENGE! First to send a photo of *FOOD* wins! 🍕","a":[],"hint":"Anything edible","coins":20},
    {"type":"image","q":"📸 IMAGE CHALLENGE! First to send something *BLUE* wins! 🔵","a":[],"hint":"Blue object","coins":20},
    {"type":"image","q":"📸 IMAGE CHALLENGE! First to send your *STUDY NOTES* wins! 📝","a":[],"hint":"Show your notes!","coins":20},
    {"type":"image","q":"📸 IMAGE CHALLENGE! First to send something *GREEN* wins! 🟢","a":[],"hint":"Plant counts!","coins":20},
    {"type":"image","q":"📸 IMAGE CHALLENGE! First to send a *PEN or PENCIL* wins! ✏️","a":[],"hint":"Any writing tool","coins":20},
    {"type":"image","q":"📸 IMAGE CHALLENGE! First to send a photo of *SHOES* wins! 👟","a":[],"hint":"Any footwear","coins":20},
    {"type":"image","q":"📸 IMAGE CHALLENGE! First to send a photo of a *CLOCK or WATCH* wins! ⏰","a":[],"hint":"Time piece","coins":20},
    {"type":"image","q":"📸 IMAGE CHALLENGE! First to send a photo of something *YELLOW* wins! 🟡","a":[],"hint":"Banana counts!","coins":20},
    {"type":"image","q":"📸 IMAGE CHALLENGE! First to send a photo of a *PLANT* wins! 🌿","a":[],"hint":"Any plant","coins":20},
    {"type":"image","q":"📸 IMAGE CHALLENGE! First to send a photo of a *SCREEN* wins! 🖥️","a":[],"hint":"Phone, TV, laptop...","coins":20},
]

# ══════════════════════════════════════════════════════════
#  SHOP
# ══════════════════════════════════════════════════════════
SHOP_ITEMS = {
    "custom_title":  {"name":"👑 Custom Member Tag (1 day)", "desc":"Real Telegram member tag for 24h!", "cost":50},
    "double_coins":  {"name":"⚡ Double Coins Booster",      "desc":"2× coins on your next win!",        "cost":60},
    "hint_reveal":   {"name":"💡 Hint Reveal",               "desc":"Reveal hint for active challenge!",  "cost":15},
    "choose_challenge":{"name":"🎯 Choose Next Challenge",   "desc":"You pick the next question!",        "cost":40},
    "pin_message":   {"name":"📌 Pin a Message",             "desc":"Use /pinit replying to any msg!",    "cost":80},
    "skip_challenge":{"name":"⏭️ Skip Challenge",           "desc":"End current challenge, start new!",  "cost":30},
    "shield":        {"name":"🛡️ Timeout Shield (1h)",      "desc":"Protects you from /timeout for 1h!", "cost":100},
    "owo_boost":     {"name":"🐾 OWO Hunt Boost (1h)",      "desc":"Double OWO from hunts for 1h!",      "cost":75},
}

# ══════════════════════════════════════════════════════════
#  BADGES
# ══════════════════════════════════════════════════════════
BADGES = {
    "first_win":   ("🏅 First Blood",    "Won first challenge!"),
    "streak_3":    ("🔥 On Fire",        "3-win streak!"),
    "streak_5":    ("🌟 Unstoppable",    "5-win streak!"),
    "wins_10":     ("💪 Veteran",        "10 total wins!"),
    "wins_25":     ("🏆 Champion",       "25 total wins!"),
    "wins_50":     ("👑 Legend",         "50 total wins!"),
    "spender":     ("🛍️ Shopaholic",    "First shop purchase!"),
    "rich":        ("💰 Minted",         "500 Forge Coins!"),
    "image_win":   ("📸 Shutterbug",     "Won image challenge!"),
    "speed_win":   ("⚡ Speed Demon",    "Won speed challenge!"),
    "cheat_user":  ("🔑 Insider",        "Used a cheat code!"),
    "first_hunt":  ("🎯 First Hunt",     "Caught first animal!"),
    "rare_hunt":   ("💎 Rare Catch",     "Caught rare+ animal!"),
    "legend_hunt": ("🐉 Dragon Tamer",   "Caught legendary!"),
    "hunter_10":   ("🏹 Hunter",         "10 successful hunts!"),
}

# ══════════════════════════════════════════════════════════
#  DATA STORE
# ══════════════════════════════════════════════════════════
def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE) as f:
            return json.load(f)
    return {"users":{}, "groups":{}, "used_codes":[]}

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)

def get_user(data, uid, username=None, full_name=None):
    k = str(uid)
    if k not in data["users"]:
        data["users"][k] = {
            "username": username or "Unknown",
            "full_name": full_name or "Unknown",
            "coins":0, "wins":0, "streak":0, "best_streak":0,
            "badges":[], "title":None, "title_expiry":None,
            "title_chat_id":None, "title_purchased":False,
            "double_coins":False, "weekly_wins":0, "last_win_date":None,
            "pin_token":False, "shield_expiry":None,
            # OWO
            "owo":0, "animals":[], "hunts":0, "hunt_cooldown":None,
            "owo_boost_expiry":None, "auto_hunt":False,
            "total_coins_ever":0,
        }
    else:
        if username:   data["users"][k]["username"]  = username
        if full_name:  data["users"][k]["full_name"] = full_name
        # Patch missing keys for existing users
        for key,val in [("pin_token",False),("shield_expiry",None),
                        ("owo",0),("animals",[]),("hunts",0),
                        ("hunt_cooldown",None),("owo_boost_expiry",None),
                        ("auto_hunt",False),("total_coins_ever",0)]:
            data["users"][k].setdefault(key, val)
    return data["users"][k]

def get_group(data, chat_id):
    k = str(chat_id)
    if k not in data["groups"]:
        data["groups"][k] = {
            "active_challenge":None, "forge_war":False,
            "forge_war_multiplier":1, "pending_chooser":None,
            "last_challenge_time":None,
        }
    else:
        data["groups"][k].setdefault("last_challenge_time", None)
    return data["groups"][k]

def award_badge(user, key):
    if key in BADGES and key not in user["badges"]:
        user["badges"].append(key)
        n,d = BADGES[key]
        return f"{n} – {d}"
    return None

def check_badges(user):
    earned = []
    for cond, key in [
        (user["wins"]>=1,       "first_win"),
        (user["streak"]>=3,     "streak_3"),
        (user["streak"]>=5,     "streak_5"),
        (user["wins"]>=10,      "wins_10"),
        (user["wins"]>=25,      "wins_25"),
        (user["wins"]>=50,      "wins_50"),
        (user.get("coins",0)>=500, "rich"),
        (user.get("hunts",0)>=1,   "first_hunt"),
        (user.get("hunts",0)>=10,  "hunter_10"),
    ]:
        if cond:
            b = award_badge(user, key)
            if b: earned.append(b)
    return earned

def reset_weekly(data):
    now = datetime.now()
    if now.weekday() == 0:
        for u in data["users"].values():
            last = u.get("last_win_date")
            if last and (now - datetime.fromisoformat(last)).days >= 7:
                u["weekly_wins"] = 0

def has_shield(user):
    exp = user.get("shield_expiry")
    if exp and datetime.fromisoformat(exp) > datetime.now():
        return True
    return False

# ══════════════════════════════════════════════════════════
#  TITLE / ADMIN TAG  (fixed for owner + existing admins)
# ══════════════════════════════════════════════════════════
async def set_member_tag(bot, chat_id, user_id, title):
    """
    Set custom title for any member including owner/existing admins.
    Strategy:
    1. Try set_chat_administrator_custom_title directly (works if already admin).
    2. If fails, promote first (works for regular members).
    3. If still fails, return False.
    """
    title = title[:16]

    # Step 1: Try directly (owner or already admin)
    try:
        await bot.set_chat_administrator_custom_title(
            chat_id=chat_id, user_id=user_id, custom_title=title
        )
        return True, "direct"
    except TelegramError:
        pass

    # Step 2: Promote with minimal rights, then set title
    try:
        await bot.promote_chat_member(
            chat_id=chat_id, user_id=user_id,
            can_manage_chat=False, can_delete_messages=False,
            can_manage_video_chats=False, can_restrict_members=False,
            can_promote_members=False, can_change_info=False,
            can_invite_users=True, can_pin_messages=False,
        )
        await asyncio.sleep(0.5)
        await bot.set_chat_administrator_custom_title(
            chat_id=chat_id, user_id=user_id, custom_title=title
        )
        return True, "promoted"
    except TelegramError as e:
        logger.error(f"set_member_tag error: {e}")
        return False, str(e)

async def remove_member_tag(bot, chat_id, user_id):
    """Remove tag by demoting. Skips if user is group owner (can't demote owner)."""
    try:
        member = await bot.get_chat_member(chat_id, user_id)
        if member.status == "creator":
            # Can't demote owner - just clear the title text
            try:
                await bot.set_chat_administrator_custom_title(
                    chat_id=chat_id, user_id=user_id, custom_title=""
                )
            except TelegramError:
                pass
            return
        await bot.promote_chat_member(
            chat_id=chat_id, user_id=user_id,
            can_manage_chat=False, can_delete_messages=False,
            can_manage_video_chats=False, can_restrict_members=False,
            can_promote_members=False, can_change_info=False,
            can_invite_users=False, can_pin_messages=False,
        )
    except TelegramError as e:
        logger.error(f"remove_member_tag: {e}")

async def expire_title_job(context: ContextTypes.DEFAULT_TYPE):
    d = context.job.data
    uid, chat_id, name = d["user_id"], d["chat_id"], d["name"]
    data = load_data()
    u = data["users"].get(str(uid))
    if u:
        u["title"] = None; u["title_expiry"] = None
        u["title_chat_id"] = None
        save_data(data)
    await remove_member_tag(context.bot, chat_id, uid)
    try:
        await context.bot.send_message(chat_id=chat_id,
            text=f"⌛ {name}'s member tag has expired and been removed.")
    except TelegramError:
        pass

# ══════════════════════════════════════════════════════════
#  OWO HUNT LOGIC
# ══════════════════════════════════════════════════════════
def roll_animal():
    pool = []
    for a in ANIMALS:
        pool.extend([a] * RARITY_WEIGHTS[a["rarity"]])
    return random.choice(pool)

def hunt_success_chance():
    return random.random() < 0.65  # 65% catch rate

async def do_hunt(bot, chat_id, user_id, data, context=None):
    u = get_user(data, user_id)

    # Cooldown check: 30 seconds between hunts
    cooldown = u.get("hunt_cooldown")
    if cooldown:
        cd_dt = datetime.fromisoformat(cooldown)
        remaining = (cd_dt - datetime.now()).total_seconds()
        if remaining > 0:
            return f"⏳ Hunt cooldown: *{int(remaining)}s* remaining. Patience! 🌿"

    u["hunt_cooldown"] = (datetime.now() + timedelta(seconds=30)).isoformat()

    if not hunt_success_chance():
        save_data(data)
        return random.choice(HUNT_FAIL_MSGS)

    animal = roll_animal()
    owo_earned = animal["owo"]
    coins_earned = animal["coins"]

    # OWO boost check
    boost = u.get("owo_boost_expiry")
    if boost and datetime.fromisoformat(boost) > datetime.now():
        owo_earned *= 2
        coins_earned *= 2

    u["owo"] = u.get("owo", 0) + owo_earned
    u["coins"] += coins_earned
    u["total_coins_ever"] = u.get("total_coins_ever", 0) + coins_earned
    u["hunts"] = u.get("hunts", 0) + 1

    # Add to zoo
    zoo = u.get("animals", [])
    found = next((z for z in zoo if z["name"] == animal["name"]), None)
    if found:
        found["count"] = found.get("count", 1) + 1
    else:
        zoo.append({"name": animal["name"], "rarity": animal["rarity"], "count": 1})
    u["animals"] = zoo

    # Badges
    new_badges = check_badges(u)
    if animal["rarity"] in ("rare","epic","legendary"):
        b = award_badge(u, "rare_hunt")
        if b: new_badges.append(b)
    if animal["rarity"] == "legendary":
        b = award_badge(u, "legend_hunt")
        if b: new_badges.append(b)

    save_data(data)

    rarity_icon = RARITY_COLORS.get(animal["rarity"], "⬜")
    badge_line = "\n🆕 " + " | ".join(new_badges) if new_badges else ""

    return (
        f"🎯 *Hunt successful!*\n"
        f"You caught {animal['name']} {rarity_icon}*{animal['rarity'].upper()}*\n"
        f"+{owo_earned} OWO | +{coins_earned} 🪙{badge_line}\n"
        f"_Total OWO: {u['owo']} | Coins: {u['coins']}_"
    )

# ══════════════════════════════════════════════════════════
#  CHALLENGE WIN
# ══════════════════════════════════════════════════════════
async def process_win(update, context, user, chat_id, challenge, extra_badge=None):
    data = load_data()
    group = get_group(data, chat_id)
    group["active_challenge"] = None

    for job in context.job_queue.get_jobs_by_name(f"expire_{chat_id}"):
        job.schedule_removal()

    u = get_user(data, user.id, user.username, user.full_name)
    coins = challenge["coins"]

    today     = datetime.now().date().isoformat()
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

    streak_bonus = (u["streak"] - 1) * STREAK_BONUS
    coins += streak_bonus

    booster_line = ""
    if u.get("double_coins"):
        coins *= 2
        u["double_coins"] = False
        booster_line = "\n⚡ Double Booster activated!"

    u["coins"] += coins
    u["total_coins_ever"] = u.get("total_coins_ever", 0) + coins
    u["wins"] += 1
    u["weekly_wins"] = u.get("weekly_wins", 0) + 1

    earned = check_badges(u)
    if extra_badge:
        b = award_badge(u, extra_badge)
        if b: earned.append(b)
    save_data(data)

    name  = f"@{user.username}" if user.username else user.full_name
    title = f"\n👑 *{u['title']}*" if u.get("title") else ""
    bonus = f" (+{streak_bonus} streak)" if streak_bonus else ""
    streak_line = f"🔥 Streak: {u['streak']}x" if u["streak"] > 1 else ""

    msg = (
        f"🎉 *{name}* wins!{title}\n"
        f"💰 +{coins} Forge Coins{bonus}{booster_line}\n"
        f"🏦 Total: {u['coins']} | 🏆 Wins: {u['wins']}\n{streak_line}"
    )
    if earned:
        msg += "\n\n🆕 *Badges!*\n" + "\n".join(f"  {b}" for b in earned)

    await update.message.reply_text(msg, parse_mode="Markdown")
    await schedule_next(context, chat_id)

# ══════════════════════════════════════════════════════════
#  CHALLENGE POST / EXPIRE / SCHEDULE
# ══════════════════════════════════════════════════════════
async def post_challenge(context, chat_id, question=None):
    data = load_data()
    group = get_group(data, chat_id)
    if group["active_challenge"]:
        return

    q = question or random.choice(QUESTIONS)
    mult  = group.get("forge_war_multiplier", 1)
    coins = q["coins"] * mult

    group["active_challenge"] = {
        "question": q["q"],
        "answers":  [a.lower() for a in q["a"]],
        "hint":     q["hint"],
        "coins":    coins,
        "type":     q.get("type","trivia"),
        "started_at": datetime.now().isoformat(),
    }
    group["last_challenge_time"] = datetime.now().isoformat()
    save_data(data)

    fw = f"\n⚔️ *FORGE WAR!* Rewards ×{mult}!\n" if group.get("forge_war") else ""
    type_tips = {
        "image":  "\n📸 *Send a photo to win!*",
        "word":   "\n⚡ *Type the exact word to win!*",
        "math":   "\n🔢 *Type the answer to win!*",
        "trivia": "\n💬 *Type the answer to win!*",
    }
    tip = type_tips.get(q.get("type","trivia"), "")

    await context.bot.send_message(
        chat_id=chat_id,
        text=f"⚡ *NEW CHALLENGE!*{fw}\n{q['q']}\n\n💰 *{coins} Forge Coins*\n⏱️ 5 minutes!{tip}",
        parse_mode="Markdown"
    )
    context.job_queue.run_once(expire_challenge, when=CHALLENGE_TIMEOUT,
                               chat_id=chat_id, name=f"expire_{chat_id}")

async def expire_challenge(context):
    cid = context.job.chat_id
    data = load_data()
    g = get_group(data, cid)
    if not g["active_challenge"]:
        return
    q = g["active_challenge"]["question"]
    g["active_challenge"] = None
    save_data(data)
    await context.bot.send_message(cid,
        f"⌛ *Time's up!* No one answered.\n_{q}_\n\nBetter luck next time! 💪",
        parse_mode="Markdown")

async def schedule_next(context, chat_id):
    delay = random.randint(INTERVAL_MIN, INTERVAL_MAX)
    context.job_queue.run_once(
        lambda ctx: asyncio.ensure_future(post_challenge(ctx, chat_id)),
        when=delay, chat_id=chat_id, name=f"auto_{chat_id}"
    )

# ══════════════════════════════════════════════════════════
#  MESSAGE HANDLER
# ══════════════════════════════════════════════════════════
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return
    chat_id = update.message.chat_id
    user    = update.message.from_user
    data    = load_data()

    # ── Cheat code check ──────────────────────────────────
    if update.message.text:
        raw  = update.message.text.strip()
        rawU = raw.upper()

        # Evergreen code
        if rawU == EVERGREEN_CODE.upper():
            try:
                amount = int(context.args[0]) if context.args else 200
            except Exception:
                amount = 200
            # Parse amount from message if present
            parts = raw.split()
            if len(parts) == 2:
                try: amount = int(parts[1])
                except: amount = 200
            u = get_user(data, user.id, user.username, user.full_name)
            u["coins"] += amount
            u["total_coins_ever"] = u.get("total_coins_ever",0) + amount
            save_data(data)
            name = f"@{user.username}" if user.username else user.full_name
            await update.message.reply_text(
                f"♾️ *Evergreen code used!*\n{name} +*{amount}* Forge Coins! 🪙\n"
                f"Balance: *{u['coins']}*", parse_mode="Markdown")
            return

        # One-time codes
        if rawU in CHEAT_CODES:
            used = data.get("used_codes", [])
            if rawU in used:
                await update.message.reply_text("❌ That code has already been used!")
                return
            reward = CHEAT_CODES[rawU]
            used.append(rawU)
            data["used_codes"] = used
            u = get_user(data, user.id, user.username, user.full_name)
            u["coins"] += reward
            u["total_coins_ever"] = u.get("total_coins_ever",0) + reward
            b = award_badge(u, "cheat_user")
            save_data(data)
            name = f"@{user.username}" if user.username else user.full_name
            badge_line = f"\n🆕 {b}" if b else ""
            await update.message.reply_text(
                f"🔑 *Code accepted!* {name} +*{reward}* 🪙{badge_line}\n"
                f"_(Code disabled forever)_", parse_mode="Markdown")
            return

    # ── Challenge answer check ─────────────────────────────
    group     = get_group(data, chat_id)
    challenge = group.get("active_challenge")
    if not challenge:
        return

    ctype = challenge.get("type","trivia")

    if ctype == "image":
        if update.message.photo:
            await process_win(update, context, user, chat_id, challenge, "image_win")
        return

    if not update.message.text:
        return
    text = update.message.text.strip().lower()

    if text in challenge["answers"]:
        extra = "speed_win" if ctype in ("word","speed") else None
        await process_win(update, context, user, chat_id, challenge, extra)

# ══════════════════════════════════════════════════════════
#  COMMANDS – CORE
# ══════════════════════════════════════════════════════════
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Hey! I'm *Aira* – your ultimate study + game bot!\n\n"
        "🎮 *Challenge Types:* Math, Science, GK, Speed Words, Image\n"
        "🐾 *OWO Hunting:* Catch animals, build your zoo!\n"
        "🛡️ *Admin Tools:* Ban, timeout, purge\n\n"
        "📋 */help* for full command list\n\nLet's go! ⚡",
        parse_mode="Markdown"
    )

async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 *Aira – Command List*\n━━━━━━━━━━━━━\n"
        "*🎮 Challenges*\n"
        "/challenge – Start a challenge (5min cooldown)\n"
        "/hint – Hint for active challenge\n"
        "/skipit – Skip (admins free, others buy)\n\n"
        "*💰 Economy*\n"
        "/wallet – Coins, wins, streak\n"
        "/leaderboard – Weekly top 10\n"
        "/streak – Win streak\n"
        "/shop – Buy perks\n"
        "/settitle <text> – Set member tag (after purchase)\n"
        "/pinit – Pin msg (reply to it, after purchase)\n\n"
        "*🐾 OWO*\n"
        "/hunt – Catch an animal\n"
        "/zoo – Your animal collection\n"
        "/owoprofile – OWO stats\n"
        "/autohunt – Toggle auto hunting\n"
        "/battle – Fight a wild animal\n\n"
        "*🏆 Stats*\n"
        "/badges – Your badge collection\n"
        "/stats – Full stats\n\n"
        "*🛡️ Admin Tools*\n"
        "/ban @user – Ban user\n"
        "/unban @user – Unban user\n"
        "/timeout @user <mins> – Mute user\n"
        "/untimeout @user – Unmute user\n"
        "/purge <n> – Delete last n messages\n"
        "/warn @user – Warn user (3 warns = ban)\n"
        "/warns @user – Check warns\n"
        "/clearwarns @user – Clear warns\n"
        "/forgewar – 2× rewards 1hr (admin)\n\n"
        "💡 Answer challenges by typing in chat!",
        parse_mode="Markdown"
    )

async def cmd_challenge(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    data    = load_data()
    group   = get_group(data, chat_id)

    if group["active_challenge"]:
        await update.message.reply_text("⚠️ A challenge is already running! Answer it first.")
        return

    # 5-minute cooldown
    last = group.get("last_challenge_time")
    if last:
        elapsed = (datetime.now() - datetime.fromisoformat(last)).total_seconds()
        if elapsed < CHALLENGE_COOLDOWN:
            remaining = int(CHALLENGE_COOLDOWN - elapsed)
            await update.message.reply_text(
                f"⏳ Cooldown active! Next challenge in *{remaining}s*.",
                parse_mode="Markdown"
            )
            return

    save_data(data)
    await post_challenge(context, chat_id)

async def cmd_wallet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    data = load_data()
    u    = get_user(data, user.id, user.username, user.full_name)
    save_data(data)

    tag_line = f"\n👑 Tag: *{u['title']}*" if u.get("title") else ""
    exp_line = ""
    if u.get("title_expiry"):
        rem = datetime.fromisoformat(u["title_expiry"]) - datetime.now()
        if rem.total_seconds() > 0:
            h,m = int(rem.total_seconds()//3600), int((rem.total_seconds()%3600)//60)
            exp_line = f"\n⏳ Tag expires: *{h}h {m}m*"

    shield = "🛡️ Active" if has_shield(u) else "None"

    await update.message.reply_text(
        f"💼 *{user.full_name}'s Wallet*{tag_line}{exp_line}\n"
        f"━━━━━━━━━━━━━\n"
        f"🪙 Forge Coins: *{u['coins']}*\n"
        f"🏆 Wins: *{u['wins']}* | 📅 Weekly: *{u.get('weekly_wins',0)}*\n"
        f"🔥 Streak: *{u['streak']}* | ⭐ Best: *{u.get('best_streak',0)}*\n"
        f"🐾 OWO: *{u.get('owo',0)}* | 🎯 Hunts: *{u.get('hunts',0)}*\n"
        f"⚡ Booster: {'Active' if u.get('double_coins') else 'None'}\n"
        f"📌 Pin Token: {'✅ Ready' if u.get('pin_token') else 'None'}\n"
        f"🛡️ Shield: {shield}\n"
        f"🏅 Badges: *{len(u['badges'])}*",
        parse_mode="Markdown"
    )

async def cmd_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    data = load_data()
    u    = get_user(data, user.id, user.username, user.full_name)
    save_data(data)
    zoo_count = sum(z.get("count",1) for z in u.get("animals",[]))
    await update.message.reply_text(
        f"📊 *{user.full_name}'s Full Stats*\n━━━━━━━━━━━━━\n"
        f"🪙 Coins Now: *{u['coins']}*\n"
        f"💎 Total Earned: *{u.get('total_coins_ever',0)}*\n"
        f"🏆 Total Wins: *{u['wins']}*\n"
        f"📅 Weekly Wins: *{u.get('weekly_wins',0)}*\n"
        f"🔥 Best Streak: *{u.get('best_streak',0)}*\n"
        f"🐾 OWO: *{u.get('owo',0)}*\n"
        f"🎯 Hunts: *{u.get('hunts',0)}*\n"
        f"🦁 Animals Caught: *{zoo_count}*\n"
        f"🏅 Badges: *{len(u['badges'])}*",
        parse_mode="Markdown"
    )

async def cmd_leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = load_data()
    reset_weekly(data)
    if not data["users"]:
        await update.message.reply_text("No players yet!")
        return
    top = sorted(data["users"].items(), key=lambda x: x[1].get("weekly_wins",0), reverse=True)[:10]
    medals = ["🥇","🥈","🥉","4️⃣","5️⃣","6️⃣","7️⃣","8️⃣","9️⃣","🔟"]
    lines  = ["🏆 *WEEKLY LEADERBOARD*\n━━━━━━━━━━━━━"]
    for i,(uid,u) in enumerate(top):
        name = u.get("full_name") or u.get("username","Unknown")
        tag  = f" 👑{u['title']}" if u.get("title") else ""
        lines.append(f"{medals[i]} {name}{tag}\n   🪙{u['coins']} | 🏆{u.get('weekly_wins',0)}W | 🐾{u.get('owo',0)}OWO")
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")

async def cmd_streak(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    data = load_data()
    u    = get_user(data, user.id, user.username, user.full_name)
    save_data(data)
    fire = "🔥" * min(u["streak"], 10)
    await update.message.reply_text(
        f"{fire}\n*{user.full_name}'s Streak*\n━━━━━━━━━━━━━\n"
        f"Current: *{u['streak']}* | Best: *{u.get('best_streak',0)}*\n"
        f"Bonus per win: *+{u['streak']*STREAK_BONUS}* coins",
        parse_mode="Markdown"
    )

async def cmd_badges(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    data = load_data()
    u    = get_user(data, user.id, user.username, user.full_name)
    save_data(data)
    if not u["badges"]:
        await update.message.reply_text("No badges yet! Win challenges and hunt animals. 🏅")
        return
    lines = [f"🏅 *{user.full_name}'s Badges*\n━━━━━━━━━━━━━"]
    for k in u["badges"]:
        if k in BADGES:
            n,d = BADGES[k]
            lines.append(f"{n}\n  _{d}_")
    locked = len([k for k in BADGES if k not in u["badges"]])
    lines.append(f"\n🔒 *{locked} locked* – keep going!")
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")

async def cmd_hint(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    data    = load_data()
    ch      = get_group(data, chat_id).get("active_challenge")
    if not ch:
        await update.message.reply_text("No active challenge!")
        return
    await update.message.reply_text(f"💡 *Hint:* _{ch['hint']}_", parse_mode="Markdown")

# ══════════════════════════════════════════════════════════
#  SHOP
# ══════════════════════════════════════════════════════════
async def cmd_shop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    data = load_data()
    u    = get_user(data, user.id, user.username, user.full_name)
    save_data(data)
    kb = [[InlineKeyboardButton(f"{v['name']} – {v['cost']} 🪙", callback_data=f"buy_{k}")]
          for k,v in SHOP_ITEMS.items()]
    await update.message.reply_text(
        f"🛒 *FORGE SHOP*\n━━━━━━━━━━━━━\nBalance: *{u['coins']}* 🪙\n\nTap to buy:",
        reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown"
    )

async def handle_shop_purchase(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query   = update.callback_query
    await query.answer()
    user    = query.from_user
    key     = query.data.replace("buy_","")
    if key not in SHOP_ITEMS:
        await query.edit_message_text("❌ Unknown item.")
        return

    data = load_data()
    u    = get_user(data, user.id, user.username, user.full_name)
    item = SHOP_ITEMS[key]

    if u["coins"] < item["cost"]:
        await query.edit_message_text(
            f"❌ Need *{item['cost']}* 🪙 but you have *{u['coins']}*.",
            parse_mode="Markdown"); return

    u["coins"] -= item["cost"]
    award_badge(u, "spender")
    msg = f"✅ *Purchased: {item['name']}*\n_{item['desc']}_\n\n💰 Remaining: *{u['coins']}* 🪙"

    if key == "double_coins":
        u["double_coins"] = True
        msg += "\n\n⚡ Next win = DOUBLE coins!"

    elif key == "hint_reveal":
        cid = query.message.chat_id
        ch  = get_group(data, cid).get("active_challenge")
        msg += f"\n\n💡 *Hint:* _{ch['hint']}_" if ch else "\n\n⚠️ No active challenge."

    elif key == "custom_title":
        u["title_purchased"] = True
        u["title_chat_id"]   = query.message.chat_id
        msg += "\n\n👑 Now use in the group:\n`/settitle YourTitle` _(max 16 chars)_"

    elif key == "choose_challenge":
        g = get_group(data, query.message.chat_id)
        g["pending_chooser"] = user.username or user.full_name
        msg += "\n\n🎯 Next /challenge will be your pick!"

    elif key == "pin_message":
        u["pin_token"] = True
        msg += "\n\n📌 Reply to any message with `/pinit` to pin it!"

    elif key == "skip_challenge":
        cid = query.message.chat_id
        g   = get_group(data, cid)
        if g.get("active_challenge"):
            g["active_challenge"] = None
            for job in context.job_queue.get_jobs_by_name(f"expire_{cid}"):
                job.schedule_removal()
            save_data(data)
            await query.edit_message_text(
                f"✅ Challenge skipped!\n💰 Remaining: *{u['coins']}* 🪙",
                parse_mode="Markdown")
            await post_challenge(context, cid)
            return
        else:
            u["coins"] += item["cost"]
            msg = "⚠️ No active challenge to skip. Refunded!"

    elif key == "shield":
        exp = (datetime.now() + timedelta(hours=1)).isoformat()
        u["shield_expiry"] = exp
        msg += "\n\n🛡️ You're protected from /timeout for 1 hour!"

    elif key == "owo_boost":
        exp = (datetime.now() + timedelta(hours=1)).isoformat()
        u["owo_boost_expiry"] = exp
        msg += "\n\n🐾 OWO hunt rewards doubled for 1 hour!"

    save_data(data)
    await query.edit_message_text(msg, parse_mode="Markdown")

async def cmd_settitle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user    = update.message.from_user
    chat_id = update.message.chat_id
    if not context.args:
        await update.message.reply_text("Usage: `/settitle YourTitle` (max 16 chars)", parse_mode="Markdown")
        return

    title = " ".join(context.args)[:16]
    data  = load_data()
    u     = get_user(data, user.id, user.username, user.full_name)

    if not u.get("title_purchased"):
        await update.message.reply_text("❌ Buy *Custom Member Tag* from /shop first!", parse_mode="Markdown")
        return

    # Cancel old expiry job
    for job in context.job_queue.get_jobs_by_name(f"title_expire_{user.id}"):
        job.schedule_removal()

    success, mode = await set_member_tag(context.bot, chat_id, user.id, title)

    if not success:
        u["title_purchased"] = False
        save_data(data)
        await update.message.reply_text(
            "❌ *Could not set member tag.*\n\n"
            "Make sure:\n"
            "• Aira is an admin\n"
            "• Aira has *'Add New Admins'* permission turned ON\n\n"
            "Purchase *refunded*! Fix permissions then try again.",
            parse_mode="Markdown"); return

    exp = datetime.now() + timedelta(hours=TITLE_HOURS)
    u["title"]         = title
    u["title_expiry"]  = exp.isoformat()
    u["title_chat_id"] = chat_id
    u["title_purchased"] = False
    save_data(data)

    context.job_queue.run_once(
        expire_title_job, when=TITLE_HOURS*3600,
        name=f"title_expire_{user.id}",
        data={"user_id":user.id, "chat_id":chat_id,
              "name": f"@{user.username}" if user.username else user.full_name}
    )
    name = f"@{user.username}" if user.username else user.full_name
    await update.message.reply_text(
        f"👑 *{name}* now has tag: *{title}*\nVisible for *24 hours!*",
        parse_mode="Markdown")

async def cmd_pinit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user    = update.message.from_user
    chat_id = update.message.chat_id
    data    = load_data()
    u       = get_user(data, user.id, user.username, user.full_name)

    # Admins can pin for free
    member   = await context.bot.get_chat_member(chat_id, user.id)
    is_admin = member.status in ("administrator","creator")

    if not is_admin and not u.get("pin_token"):
        await update.message.reply_text(
            "❌ Buy *Pin a Message* from /shop first!\nThen reply to any message with /pinit",
            parse_mode="Markdown"); return

    if not update.message.reply_to_message:
        await update.message.reply_text("↩️ Reply to a message first, then use /pinit")
        return

    try:
        await context.bot.pin_chat_message(
            chat_id=chat_id,
            message_id=update.message.reply_to_message.message_id,
            disable_notification=False
        )
        if not is_admin:
            u["pin_token"] = False
            save_data(data)
        name = f"@{user.username}" if user.username else user.full_name
        await update.message.reply_text(f"📌 *{name}* pinned a message!", parse_mode="Markdown")
    except TelegramError as e:
        await update.message.reply_text(
            f"❌ Can't pin. Make sure Aira has *Pin Messages* permission!\n_{e}_",
            parse_mode="Markdown")

async def cmd_skipit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    data    = load_data()
    group   = get_group(data, chat_id)
    member  = await context.bot.get_chat_member(chat_id, update.message.from_user.id)
    if member.status not in ("administrator","creator"):
        await update.message.reply_text("⚠️ Admins only (or buy Skip from /shop).")
        return
    if not group.get("active_challenge"):
        await update.message.reply_text("No active challenge to skip!")
        return
    group["active_challenge"] = None
    for job in context.job_queue.get_jobs_by_name(f"expire_{chat_id}"):
        job.schedule_removal()
    save_data(data)
    await update.message.reply_text("⏭️ Skipped! Starting new challenge...")
    await post_challenge(context, chat_id)

# ══════════════════════════════════════════════════════════
#  OWO COMMANDS
# ══════════════════════════════════════════════════════════
async def cmd_hunt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user    = update.message.from_user
    chat_id = update.message.chat_id
    data    = load_data()
    result  = await do_hunt(context.bot, chat_id, user.id, data, context)
    await update.message.reply_text(result, parse_mode="Markdown")

async def cmd_zoo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    data = load_data()
    u    = get_user(data, user.id, user.username, user.full_name)
    save_data(data)
    animals = u.get("animals", [])
    if not animals:
        await update.message.reply_text("Your zoo is empty! Use /hunt to catch animals. 🎯")
        return
    lines = [f"🦁 *{user.full_name}'s Zoo*\n━━━━━━━━━━━━━"]
    for a in sorted(animals, key=lambda x: list(RARITY_WEIGHTS.keys()).index(x["rarity"]) if x["rarity"] in RARITY_WEIGHTS else 99, reverse=True):
        icon = RARITY_COLORS.get(a["rarity"],"⬜")
        lines.append(f"{a['name']} {icon}*{a['rarity']}* ×{a.get('count',1)}")
    lines.append(f"\n🐾 Total OWO: *{u.get('owo',0)}*")
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")

async def cmd_owoprofile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    data = load_data()
    u    = get_user(data, user.id, user.username, user.full_name)
    save_data(data)

    animals  = u.get("animals",[])
    total    = sum(z.get("count",1) for z in animals)
    rares    = sum(z.get("count",1) for z in animals if z["rarity"] in ("rare","epic","legendary"))
    legends  = sum(z.get("count",1) for z in animals if z["rarity"]=="legendary")

    boost = "⚡ Active" if (u.get("owo_boost_expiry") and
            datetime.fromisoformat(u["owo_boost_expiry"]) > datetime.now()) else "None"
    auto  = "✅ ON" if u.get("auto_hunt") else "❌ OFF"

    cd = u.get("hunt_cooldown")
    cd_line = ""
    if cd:
        rem = (datetime.fromisoformat(cd) - datetime.now()).total_seconds()
        if rem > 0: cd_line = f"\n⏳ Hunt Cooldown: *{int(rem)}s*"

    await update.message.reply_text(
        f"🐾 *{user.full_name}'s OWO Profile*\n━━━━━━━━━━━━━\n"
        f"🐾 OWO: *{u.get('owo',0)}*\n"
        f"🎯 Total Hunts: *{u.get('hunts',0)}*\n"
        f"🦁 Animals Caught: *{total}*\n"
        f"💎 Rare+: *{rares}* | 🐉 Legendary: *{legends}*\n"
        f"⚡ Hunt Boost: {boost}\n"
        f"🤖 Auto Hunt: {auto}{cd_line}",
        parse_mode="Markdown"
    )

async def cmd_autohunt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    data = load_data()
    u    = get_user(data, user.id, user.username, user.full_name)
    u["auto_hunt"] = not u.get("auto_hunt", False)
    state = "✅ ON" if u["auto_hunt"] else "❌ OFF"
    save_data(data)

    if u["auto_hunt"]:
        # Schedule recurring auto hunt every 60 seconds
        context.job_queue.run_repeating(
            lambda ctx: asyncio.ensure_future(auto_hunt_job(ctx, update.message.chat_id, user.id)),
            interval=60, first=10,
            name=f"autohunt_{user.id}",
            chat_id=update.message.chat_id
        )
        await update.message.reply_text(
            f"🤖 Auto Hunt *ON*! Aira will hunt for you every 60s.\n"
            f"Results posted here. Use /autohunt again to stop.", parse_mode="Markdown")
    else:
        for job in context.job_queue.get_jobs_by_name(f"autohunt_{user.id}"):
            job.schedule_removal()
        await update.message.reply_text("🤖 Auto Hunt *OFF*.", parse_mode="Markdown")

async def auto_hunt_job(context, chat_id, user_id):
    data   = load_data()
    u      = get_user(data, user_id)
    if not u.get("auto_hunt"):
        return
    result = await do_hunt(context.bot, chat_id, user_id, data)
    try:
        await context.bot.send_message(chat_id=chat_id,
            text=f"🤖 *Auto Hunt:* {result}", parse_mode="Markdown")
    except TelegramError:
        pass

async def cmd_battle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user    = update.message.from_user
    chat_id = update.message.chat_id
    data    = load_data()
    u       = get_user(data, user.id, user.username, user.full_name)

    cd = u.get("hunt_cooldown")
    if cd:
        rem = (datetime.fromisoformat(cd) - datetime.now()).total_seconds()
        if rem > 0:
            await update.message.reply_text(f"⏳ Cooldown: *{int(rem)}s*", parse_mode="Markdown")
            return

    enemy  = random.choice(BATTLE_ANIMALS)
    player_hp = 50
    enemy_hp  = enemy["hp"]
    log = [f"⚔️ *{user.full_name}* vs *{enemy['name']}*\n"]

    rounds = 0
    while player_hp > 0 and enemy_hp > 0 and rounds < 10:
        p_atk = random.randint(8, 20)
        e_atk = random.randint(int(enemy["atk"]*0.7), enemy["atk"])
        enemy_hp  -= p_atk
        player_hp -= e_atk
        rounds += 1

    u["hunt_cooldown"] = (datetime.now() + timedelta(seconds=45)).isoformat()

    if player_hp > 0:
        reward_coins = enemy["atk"] * 3
        reward_owo   = random.randint(2,6)
        u["coins"] += reward_coins
        u["owo"]    = u.get("owo",0) + reward_owo
        u["hunts"]  = u.get("hunts",0) + 1
        check_badges(u)
        save_data(data)
        await update.message.reply_text(
            f"⚔️ *BATTLE vs {enemy['name']}*\n"
            f"You survived {rounds} rounds!\n\n"
            f"🏆 *Victory!*\n"
            f"+{reward_coins} 🪙 | +{reward_owo} OWO\n"
            f"HP remaining: *{max(0,player_hp)}*",
            parse_mode="Markdown")
    else:
        loss = random.randint(5,15)
        u["coins"] = max(0, u["coins"] - loss)
        save_data(data)
        await update.message.reply_text(
            f"⚔️ *BATTLE vs {enemy['name']}*\n"
            f"You fell after {rounds} rounds!\n\n"
            f"💀 *Defeated!* Lost {loss} 🪙",
            parse_mode="Markdown")

# ══════════════════════════════════════════════════════════
#  ADMIN COMMANDS
# ══════════════════════════════════════════════════════════
async def is_admin(bot, chat_id, user_id):
    try:
        m = await bot.get_chat_member(chat_id, user_id)
        return m.status in ("administrator","creator")
    except TelegramError:
        return False

async def resolve_target(update, context):
    """Get target user from reply or @mention in args."""
    if update.message.reply_to_message:
        return update.message.reply_to_message.from_user
    if context.args:
        username = context.args[0].lstrip("@")
        # We can't look up users by username without them being in chat
        # So we just return the username as string for display
        return username
    return None

async def cmd_ban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    if not await is_admin(context.bot, chat_id, update.message.from_user.id):
        await update.message.reply_text("⚠️ Admins only!"); return

    target = await resolve_target(update, context)
    if not target:
        await update.message.reply_text("Reply to a user or use /ban @username"); return

    try:
        if hasattr(target, "id"):
            await context.bot.ban_chat_member(chat_id, target.id)
            name = f"@{target.username}" if target.username else target.full_name
            await update.message.reply_text(f"🔨 *{name}* has been banned.", parse_mode="Markdown")
        else:
            await update.message.reply_text(f"⚠️ Reply to the user's message to ban them.")
    except TelegramError as e:
        await update.message.reply_text(f"❌ Failed: _{e}_", parse_mode="Markdown")

async def cmd_unban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    if not await is_admin(context.bot, chat_id, update.message.from_user.id):
        await update.message.reply_text("⚠️ Admins only!"); return
    if not context.args:
        await update.message.reply_text("Usage: /unban @username"); return
    try:
        username = context.args[0].lstrip("@")
        # For unban by username we need chat members; prompt reply instead
        await update.message.reply_text(
            f"⚠️ To unban, please reply to one of their messages with /unban, "
            f"or use Telegram's ban list in group settings.")
    except TelegramError as e:
        await update.message.reply_text(f"❌ _{e}_", parse_mode="Markdown")

async def cmd_timeout(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    if not await is_admin(context.bot, chat_id, update.message.from_user.id):
        await update.message.reply_text("⚠️ Admins only!"); return

    target = await resolve_target(update, context)
    if not target or not hasattr(target, "id"):
        await update.message.reply_text("Reply to a user's message to timeout them."); return

    # Check shield
    data = load_data()
    tu   = data["users"].get(str(target.id))
    if tu and has_shield(tu):
        tname = f"@{target.username}" if target.username else target.full_name
        await update.message.reply_text(f"🛡️ *{tname}* has a timeout shield! Can't mute them.", parse_mode="Markdown")
        return

    mins = 5
    if context.args:
        try: mins = max(1, min(int(context.args[-1]), 1440))
        except: pass

    until = datetime.now() + timedelta(minutes=mins)
    try:
        await context.bot.restrict_chat_member(
            chat_id, target.id,
            permissions=ChatPermissions(can_send_messages=False),
            until_date=until
        )
        name = f"@{target.username}" if target.username else target.full_name
        await update.message.reply_text(
            f"🔇 *{name}* timed out for *{mins} minutes*.", parse_mode="Markdown")
    except TelegramError as e:
        await update.message.reply_text(f"❌ Failed: _{e}_", parse_mode="Markdown")

async def cmd_untimeout(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    if not await is_admin(context.bot, chat_id, update.message.from_user.id):
        await update.message.reply_text("⚠️ Admins only!"); return

    target = await resolve_target(update, context)
    if not target or not hasattr(target, "id"):
        await update.message.reply_text("Reply to the user's message."); return
    try:
        await context.bot.restrict_chat_member(
            chat_id, target.id,
            permissions=ChatPermissions(
                can_send_messages=True, can_send_media_messages=True,
                can_send_polls=True, can_send_other_messages=True,
                can_add_web_page_previews=True, can_change_info=False,
                can_invite_users=True, can_pin_messages=False,
            )
        )
        name = f"@{target.username}" if target.username else target.full_name
        await update.message.reply_text(f"🔊 *{name}* unmuted!", parse_mode="Markdown")
    except TelegramError as e:
        await update.message.reply_text(f"❌ Failed: _{e}_", parse_mode="Markdown")

async def cmd_purge(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    if not await is_admin(context.bot, chat_id, update.message.from_user.id):
        await update.message.reply_text("⚠️ Admins only!"); return

    n = 10
    if context.args:
        try: n = max(1, min(int(context.args[0]), 100))
        except: pass

    msg_id  = update.message.message_id
    deleted = 0
    failed  = 0
    for i in range(msg_id, msg_id - n - 1, -1):
        try:
            await context.bot.delete_message(chat_id, i)
            deleted += 1
        except TelegramError:
            failed += 1

    try:
        notice = await context.bot.send_message(
            chat_id, f"🗑️ Purged *{deleted}* messages.", parse_mode="Markdown")
        await asyncio.sleep(3)
        await context.bot.delete_message(chat_id, notice.message_id)
    except TelegramError:
        pass

async def cmd_warn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    if not await is_admin(context.bot, chat_id, update.message.from_user.id):
        await update.message.reply_text("⚠️ Admins only!"); return

    target = await resolve_target(update, context)
    if not target or not hasattr(target, "id"):
        await update.message.reply_text("Reply to a user's message to warn them."); return

    data = load_data()
    gdata = get_group(data, chat_id)
    warns_key = f"warns_{chat_id}"
    if warns_key not in gdata:
        gdata[warns_key] = {}

    uid   = str(target.id)
    gdata[warns_key][uid] = gdata[warns_key].get(uid, 0) + 1
    count = gdata[warns_key][uid]
    save_data(data)

    name = f"@{target.username}" if target.username else target.full_name

    if count >= 3:
        try:
            await context.bot.ban_chat_member(chat_id, target.id)
            await update.message.reply_text(
                f"⚠️ *{name}* received warn #{count}.\n🔨 *3 warns reached — BANNED!*",
                parse_mode="Markdown")
            gdata[warns_key][uid] = 0
            save_data(data)
        except TelegramError as e:
            await update.message.reply_text(f"⚠️ Warn #{count} but ban failed: _{e}_", parse_mode="Markdown")
    else:
        await update.message.reply_text(
            f"⚠️ *{name}* warned! (*{count}/3*)\n_{3-count} more warns = ban_",
            parse_mode="Markdown")

async def cmd_warns(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    target  = await resolve_target(update, context)
    if not target or not hasattr(target, "id"):
        await update.message.reply_text("Reply to a user's message."); return

    data     = load_data()
    gdata    = get_group(data, chat_id)
    warns_key = f"warns_{chat_id}"
    count    = gdata.get(warns_key, {}).get(str(target.id), 0)
    name     = f"@{target.username}" if target.username else target.full_name
    await update.message.reply_text(
        f"⚠️ *{name}* has *{count}/3* warnings.", parse_mode="Markdown")

async def cmd_clearwarns(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    if not await is_admin(context.bot, chat_id, update.message.from_user.id):
        await update.message.reply_text("⚠️ Admins only!"); return

    target = await resolve_target(update, context)
    if not target or not hasattr(target, "id"):
        await update.message.reply_text("Reply to a user's message."); return

    data      = load_data()
    gdata     = get_group(data, chat_id)
    warns_key = f"warns_{chat_id}"
    if warns_key in gdata:
        gdata[warns_key][str(target.id)] = 0
    save_data(data)
    name = f"@{target.username}" if target.username else target.full_name
    await update.message.reply_text(f"✅ Cleared all warns for *{name}*.", parse_mode="Markdown")

async def cmd_forgewar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    if not await is_admin(context.bot, chat_id, update.message.from_user.id):
        await update.message.reply_text("⚠️ Admins only!"); return
    data  = load_data()
    group = get_group(data, chat_id)
    group["forge_war"] = True
    group["forge_war_multiplier"] = 2
    save_data(data)
    await update.message.reply_text(
        "⚔️ *FORGE WAR HAS BEGUN!* ⚔️\nAll rewards *×2 for 1 hour!* 🪙🔥",
        parse_mode="Markdown")
    context.job_queue.run_once(
        lambda ctx: asyncio.ensure_future(_end_forge_war(ctx, chat_id)),
        when=3600, name=f"fw_{chat_id}")

async def _end_forge_war(context, chat_id):
    data  = load_data()
    group = get_group(data, chat_id)
    group["forge_war"] = False
    group["forge_war_multiplier"] = 1
    save_data(data)
    await context.bot.send_message(chat_id,
        "⚔️ *Forge War ended!* Back to normal. 🏆", parse_mode="Markdown")

# ══════════════════════════════════════════════════════════
#  MAIN
# ══════════════════════════════════════════════════════════
def main():
    app = Application.builder().token(BOT_TOKEN).build()

    handlers = [
        ("start",       cmd_start),
        ("help",        cmd_help),
        ("challenge",   cmd_challenge),
        ("wallet",      cmd_wallet),
        ("stats",       cmd_stats),
        ("leaderboard", cmd_leaderboard),
        ("streak",      cmd_streak),
        ("badges",      cmd_badges),
        ("shop",        cmd_shop),
        ("settitle",    cmd_settitle),
        ("pinit",       cmd_pinit),
        ("skipit",      cmd_skipit),
        ("hint",        cmd_hint),
        ("hunt",        cmd_hunt),
        ("zoo",         cmd_zoo),
        ("owoprofile",  cmd_owoprofile),
        ("autohunt",    cmd_autohunt),
        ("battle",      cmd_battle),
        ("ban",         cmd_ban),
        ("unban",       cmd_unban),
        ("timeout",     cmd_timeout),
        ("untimeout",   cmd_untimeout),
        ("purge",       cmd_purge),
        ("warn",        cmd_warn),
        ("warns",       cmd_warns),
        ("clearwarns",  cmd_clearwarns),
        ("forgewar",    cmd_forgewar),
    ]

    for cmd, fn in handlers:
        app.add_handler(CommandHandler(cmd, fn))

    app.add_handler(CallbackQueryHandler(handle_shop_purchase, pattern="^buy_"))
    app.add_handler(MessageHandler(filters.PHOTO & ~filters.COMMAND, handle_message))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info("Aira v3 is running!")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
ENDOFFILE