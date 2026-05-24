"""
Aira v6 – Ultimate Telegram Bot
Challenges • OWO Hunting • Casino • AFK System • AI Chat • Admin Tools
Welcomer • Daily Rewards • Trading • Pomodoro • Weather • Tournaments
"""

import logging, random, asyncio, json, os, re
from datetime import datetime, timedelta
from telegram import (Update, InlineKeyboardButton, InlineKeyboardMarkup,
                      ChatPermissions, ReactionTypeEmoji)
from telegram.error import TelegramError
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, filters, ContextTypes, ChatMemberHandler,
)

# ══════════════════════════════════════════════════════════════════════════════
#  CONFIG
# ══════════════════════════════════════════════════════════════════════════════
BOT_TOKEN          = "8823107490:AAGPfcyAz4lKTzMCOENhUSOgjjO_jzRozmc"
CHALLENGE_TIMEOUT  = 300
CHALLENGE_COOLDOWN = 300
INTERVAL_MIN       = 1800
INTERVAL_MAX       = 5400
STREAK_BONUS       = 2
DATA_FILE          = "aira_data.json"
TITLE_HOURS        = 24

# ── Evergreen admin codes (never expire) ──────────────────────────────────────
EVERGREEN_COINS_CODE  = "AIRA-FORGE-INFINITE"
# Usage: AIRA-FORGE-INFINITE 500          → adds 500 to sender
EVERGREEN_ADMIN_CODE  = "AIRA-GOD-MODE-9Z"
# Usage: AIRA-GOD-MODE-9Z @username +300  → add 300 to @username
#         AIRA-GOD-MODE-9Z @username -200  → remove 200 from @username

# ── One-time codes ─────────────────────────────────────────────────────────
CHEAT_CODES = {
    "FORGE-ALPHA-7X2Q":500,"AIRA-SECRET-K9MP":500,"COINS-BLAST-3RNV":500,
    "VAULT-OPEN-Z5TW":500,"MINT-RUSH-8YCL":500,"FORGE-DELTA-4PXJ":500,
    "AIRA-PRIME-6KQB":500,"COINS-MAX-2HFG":500,"SHADOW-KEY-9LMR":500,
    "AIRA-OMEGA-7VNS":500,"FORGE-NOVA-3ZKP":500,"LUCKY-PULL-5TGX":500,
    "AIRA-BOOST-1WQM":500,"COINS-DROP-8YBF":500,"VAULT-CODE-4RJH":500,
    "FORGE-ULTRA-2MPK":500,"AIRA-FLASH-6XNQ":500,"COINS-FIRE-9LVT":500,
    "MINT-KING-7GZR":500,"FORGE-FINAL-3CWY":500,
    "MINI-BOOST-A1BC":200,"QUICK-CASH-D2EF":200,"SMALL-WIN-G3HI":200,
    "EASY-COIN-J4KL":200,"FAST-MINT-M5NO":200,
}

logging.basicConfig(format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

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
]

RARITY_WEIGHTS = {"common":50,"uncommon":25,"rare":15,"epic":7,"legendary":3,"Extreme":1}
RARITY_COLORS = {"common":"⬜","uncommon":"🟩","rare":"🟦","epic":"🟪","legendary":"🟡","Extreme":"⚫"}

HUNT_FAILS = [
    "You crept through the forest... nothing there 🍃",
    "Animals sensed you and ran! 🌿",
    "Something ate your bait 😅",
    "The animal escaped at the last second 💨",
    "You found tracks… but lost the trail 🐾",
    "A twig snapped and scared everything away 🌲",
]

# ══════════════════════════════════════════════════════════════════════════════
#  WEAPONS (buyable with gems)
# ══════════════════════════════════════════════════════════════════════════════
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

# ══════════════════════════════════════════════════════════════════════════════
#  QUESTIONS  (130+)
# ══════════════════════════════════════════════════════════════════════════════
QUESTIONS = [
    # Math (35)
    {"type":"math","q":"🔢 What is 15 × 13?","a":["195"],"hint":"15×10=150 then +45","coins":10},
    {"type":"math","q":"🔢 √144 = ?","a":["12"],"hint":"12×12=?","coins":10},
    {"type":"math","q":"🔢 Solve: 2x+6=20, x=?","a":["7"],"hint":"Subtract 6 first","coins":12},
    {"type":"math","q":"🔢 25% of 200 = ?","a":["50"],"hint":"1/4 of 200","coins":8},
    {"type":"math","q":"🔢 7³ = ?","a":["343"],"hint":"7×7=49 then ×7","coins":12},
    {"type":"math","q":"🔢 π to 2 decimal places?","a":["3.14"],"hint":"Starts 3.1...","coins":8},
    {"type":"math","q":"🔢 LCM of 4 and 6?","a":["12"],"hint":"Smallest div by both","coins":10},
    {"type":"math","q":"🔢 HCF of 36 and 48?","a":["12"],"hint":"List factors","coins":12},
    {"type":"math","q":"🔢 Triangle: 60°+80°+?=180°","a":["40","40°"],"hint":"180-140","coins":10},
    {"type":"math","q":"🔢 0.5 as fraction?","a":["1/2"],"hint":"Half","coins":8},
    {"type":"math","q":"🔢 3²+4²=?","a":["25"],"hint":"Pythagoras!","coins":10},
    {"type":"math","q":"🔢 1000÷25=?","a":["40"],"hint":"40×25=1000","coins":8},
    {"type":"math","q":"🔢 Perimeter of square, side 7cm?","a":["28","28cm"],"hint":"4 sides","coins":8},
    {"type":"math","q":"🔢 18²=?","a":["324"],"hint":"(20-2)²","coins":12},
    {"type":"math","q":"🔢 2⁸=?","a":["256"],"hint":"Double 8 times","coins":12},
    {"type":"math","q":"🔢 Area of 8×5 rectangle?","a":["40"],"hint":"L×W","coins":8},
    {"type":"math","q":"🔢 5x=75, x=?","a":["15"],"hint":"Divide by 5","coins":10},
    {"type":"math","q":"🔢 √81=?","a":["9"],"hint":"9×9","coins":8},
    {"type":"math","q":"🔢 2/5 as percentage?","a":["40","40%"],"hint":"×100","coins":8},
    {"type":"math","q":"🔢 Volume of cube, side 3?","a":["27"],"hint":"3³","coins":10},
    {"type":"math","q":"🔢 11²=?","a":["121"],"hint":"11×11","coins":8},
    {"type":"math","q":"🔢 Speed 60km/h × 2.5h = ?","a":["150","150km"],"hint":"S×T","coins":12},
    {"type":"math","q":"🔢 5! = ?","a":["120"],"hint":"5×4×3×2×1","coins":12},
    {"type":"math","q":"🔢 Median of 3,7,9,11,15?","a":["9"],"hint":"Middle value","coins":10},
    {"type":"math","q":"🔢 Angles in quadrilateral?","a":["360","360°"],"hint":"Two triangles","coins":10},
    {"type":"math","q":"🔢 3/4 as decimal?","a":["0.75"],"hint":"75 hundredths","coins":8},
    {"type":"math","q":"🔢 17×3=?","a":["51"],"hint":"51","coins":8},
    {"type":"math","q":"🔢 100²=?","a":["10000"],"hint":"100×100","coins":8},
    {"type":"math","q":"🔢 13×7=?","a":["91"],"hint":"91","coins":10},
    {"type":"math","q":"🔢 What is 9×9?","a":["81"],"hint":"9 squared","coins":8},
    {"type":"math","q":"🔢 Solve: 3x - 9 = 0","a":["3"],"hint":"Add 9 both sides then ÷3","coins":10},
    {"type":"math","q":"🔢 What is 144 ÷ 12?","a":["12"],"hint":"Reverse of 12²","coins":8},
    {"type":"math","q":"🔢 Sum of first 10 natural numbers?","a":["55"],"hint":"n(n+1)/2","coins":12},
    {"type":"math","q":"🔢 What is 2³ × 2²?","a":["32"],"hint":"Add the exponents","coins":12},
    {"type":"math","q":"🔢 What is 15% of 300?","a":["45"],"hint":"10%=30, 5%=15","coins":10},

    # Science (30)
    {"type":"trivia","q":"🔬 Chemical formula of water?","a":["h2o"],"hint":"2H 1O","coins":8},
    {"type":"trivia","q":"🔬 Speed of light in km/s?","a":["300000","3×10^5"],"hint":"3 + 5 zeros","coins":12},
    {"type":"trivia","q":"🔬 The Red Planet?","a":["mars"],"hint":"4th from Sun","coins":8},
    {"type":"trivia","q":"🔬 Newton's 2nd Law formula?","a":["f=ma","f = ma"],"hint":"Force=Mass×?","coins":12},
    {"type":"trivia","q":"🔬 Atomic number of Carbon?","a":["6"],"hint":"Period 2 Group 14","coins":10},
    {"type":"trivia","q":"🔬 Gas plants absorb in photosynthesis?","a":["carbon dioxide","co2"],"hint":"We exhale it","coins":8},
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
    {"type":"trivia","q":"🔬 Process plants use to make food?","a":["photosynthesis"],"hint":"Sunlight+CO2","coins":8},
    {"type":"trivia","q":"🔬 Adult human teeth?","a":["32"],"hint":"Inc. wisdom teeth","coins":8},

    # General Knowledge (20)
    {"type":"trivia","q":"🌍 Capital of France?","a":["paris"],"hint":"City of Love","coins":8},
    {"type":"trivia","q":"🌍 How many continents?","a":["7","seven"],"hint":"Asia, Africa...","coins":6},
    {"type":"trivia","q":"🌍 Who wrote Romeo and Juliet?","a":["shakespeare","william shakespeare"],"hint":"English playwright","coins":8},
    {"type":"trivia","q":"🌍 Sides of a hexagon?","a":["6","six"],"hint":"Honeycomb","coins":6},
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
    {"type":"trivia","q":"🌍 Capital of Japan?","a":["tokyo"],"hint":"Godzilla attacks here","coins":6},
    {"type":"trivia","q":"🌍 How many strings on a guitar?","a":["6","six"],"hint":"Standard guitar","coins":6},
    {"type":"trivia","q":"🌍 Author of Harry Potter?","a":["jk rowling","rowling","j.k. rowling"],"hint":"British author","coins":8},
    {"type":"trivia","q":"🌍 Tallest mountain?","a":["mount everest","everest"],"hint":"Himalayas","coins":8},
    {"type":"trivia","q":"🌍 Zeros in a billion?","a":["9","nine"],"hint":"1,000,000,000","coins":8},

    # Speed/Word (25)
    {"type":"word","q":"⚡ SPEED! First to type *FORGE* wins!","a":["forge"],"hint":"Our coins!","coins":15},
    {"type":"word","q":"⚡ SPEED! First to type *PHOTON* wins!","a":["photon"],"hint":"Particle of light","coins":15},
    {"type":"word","q":"⚡ SPEED! First to type *QUANTUM* wins!","a":["quantum"],"hint":"Physics term","coins":15},
    {"type":"word","q":"⚡ SPEED! First to type *NUCLEUS* wins!","a":["nucleus"],"hint":"Centre of atom","coins":15},
    {"type":"word","q":"⚡ SPEED! First to type *GRAVITY* wins!","a":["gravity"],"hint":"Newton's favourite","coins":15},
    {"type":"word","q":"⚡ SPEED! First to type *ALGEBRA* wins!","a":["algebra"],"hint":"Maths with x,y","coins":15},
    {"type":"word","q":"⚡ SPEED! First to type *PROTON* wins!","a":["proton"],"hint":"Positive particle","coins":15},
    {"type":"word","q":"⚡ SPEED! First to type *OSMOSIS* wins!","a":["osmosis"],"hint":"Through membrane","coins":15},
    {"type":"word","q":"⚡ SPEED! First to type *CARBON* wins!","a":["carbon"],"hint":"Element 6","coins":15},
    {"type":"word","q":"⚡ SPEED! First to type *NEUTRON* wins!","a":["neutron"],"hint":"No charge","coins":15},
    {"type":"word","q":"⚡ SPEED! First to type *VELOCITY* wins!","a":["velocity"],"hint":"Speed+direction","coins":15},
    {"type":"word","q":"⚡ SPEED! First to type *ELECTRON* wins!","a":["electron"],"hint":"Negative charge","coins":15},
    {"type":"word","q":"⚡ SPEED! First to type *MOLECULE* wins!","a":["molecule"],"hint":"Atoms bonded","coins":15},
    {"type":"word","q":"⚡ SPEED! First to type *FRICTION* wins!","a":["friction"],"hint":"Resists motion","coins":15},
    {"type":"word","q":"⚡ SPEED! First to type *REACTION* wins!","a":["reaction"],"hint":"Chemical process","coins":15},
    {"type":"word","q":"⚡ SPEED! First to type *AIRA* wins!","a":["aira"],"hint":"Our bot!","coins":15},
    {"type":"word","q":"⚡ SPEED! First to type *HYDROGEN* wins!","a":["hydrogen"],"hint":"Lightest element","coins":15},
    {"type":"word","q":"⚡ SPEED! First to type *OXYGEN* wins!","a":["oxygen"],"hint":"We breathe it","coins":15},
    {"type":"word","q":"⚡ SPEED! First to type *CHAMPION* wins!","a":["champion"],"hint":"The best!","coins":15},
    {"type":"word","q":"⚡ SPEED! First to type *LEADERBOARD* wins!","a":["leaderboard"],"hint":"Rankings","coins":15},
    {"type":"word","q":"⚡ SPEED! First to type *BIOLOGY* wins!","a":["biology"],"hint":"Study of life","coins":15},
    {"type":"word","q":"⚡ SPEED! First to type *GEOMETRY* wins!","a":["geometry"],"hint":"Shapes+angles","coins":15},
    {"type":"word","q":"⚡ SPEED! First to type *POLYNOMIAL* wins!","a":["polynomial"],"hint":"Multi-term math","coins":18},
    {"type":"word","q":"⚡ SPEED! First to type *MITOCHONDRIA* wins!","a":["mitochondria"],"hint":"Cell powerhouse","coins":18},
    {"type":"word","q":"⚡ SPEED! First to type *PHOTOSYNTHESIS* wins!","a":["photosynthesis"],"hint":"Plants making food","coins":20},

    # Image (15)
    {"type":"image","q":"📸 IMAGE! First to send something *RED* wins! 🔴","a":[],"hint":"Any red object!","coins":20},
    {"type":"image","q":"📸 IMAGE! First to send a *BOOK* wins! 📚","a":[],"hint":"Any book","coins":20},
    {"type":"image","q":"📸 IMAGE! First to send something *ROUND* wins! ⭕","a":[],"hint":"Circular object","coins":20},
    {"type":"image","q":"📸 IMAGE! First to send a *SELFIE* wins! 🤳","a":[],"hint":"Quick snap!","coins":20},
    {"type":"image","q":"📸 IMAGE! First to send the *SKY* wins! ☁️","a":[],"hint":"Look up!","coins":20},
    {"type":"image","q":"📸 IMAGE! First to send *FOOD* wins! 🍕","a":[],"hint":"Anything edible","coins":20},
    {"type":"image","q":"📸 IMAGE! First to send something *BLUE* wins! 🔵","a":[],"hint":"Blue object","coins":20},
    {"type":"image","q":"📸 IMAGE! First to send your *STUDY NOTES* wins! 📝","a":[],"hint":"Show notes!","coins":20},
    {"type":"image","q":"📸 IMAGE! First to send something *GREEN* wins! 🟢","a":[],"hint":"Plant counts!","coins":20},
    {"type":"image","q":"📸 IMAGE! First to send a *PEN or PENCIL* wins! ✏️","a":[],"hint":"Writing tool","coins":20},
    {"type":"image","q":"📸 IMAGE! First to send *SHOES* wins! 👟","a":[],"hint":"Any footwear","coins":20},
    {"type":"image","q":"📸 IMAGE! First to send a *CLOCK or WATCH* wins! ⏰","a":[],"hint":"Timepiece","coins":20},
    {"type":"image","q":"📸 IMAGE! First to send something *YELLOW* wins! 🟡","a":[],"hint":"Banana counts!","coins":20},
    {"type":"image","q":"📸 IMAGE! First to send a *PLANT* wins! 🌿","a":[],"hint":"Any plant","coins":20},
    {"type":"image","q":"📸 IMAGE! First to send a *SCREEN* wins! 🖥️","a":[],"hint":"Phone/TV/laptop","coins":20},
]

# ══════════════════════════════════════════════════════════════════════════════
#  SHOP
# ══════════════════════════════════════════════════════════════════════════════
SHOP_ITEMS = {
    "custom_title":    {"name":"👑 Member Tag (1 day)",       "desc":"Real Telegram tag for 24h!",         "cost":50},
    "double_coins":    {"name":"⚡ Double Coins Booster",     "desc":"2× coins on next win!",              "cost":60},
    "hint_reveal":     {"name":"💡 Hint Reveal",              "desc":"Reveal hint for active challenge!",  "cost":15},
    "choose_challenge":{"name":"🎯 Choose Next Challenge",    "desc":"Pick the next question!",            "cost":40},
    "pin_message":     {"name":"📌 Pin a Message",            "desc":"Reply + /pinit to pin!",             "cost":80},
    "skip_challenge":  {"name":"⏭️ Skip Challenge",          "desc":"End current, start new!",            "cost":30},
    "shield":          {"name":"🛡️ Timeout Shield (1h)",     "desc":"Immune to /timeout for 1h!",         "cost":100},
    "owo_boost":       {"name":"🐾 Hunt Boost (1h)",          "desc":"Double OWO+coins from hunts 1h!",   "cost":75},
}

# ══════════════════════════════════════════════════════════════════════════════
#  BADGES
# ══════════════════════════════════════════════════════════════════════════════
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
}

# ══════════════════════════════════════════════════════════════════════════════
#  DAILY REWARDS
# ══════════════════════════════════════════════════════════════════════════════
DAILY_TIERS = [(50,"Base"),(75,"Bonus!"),(100,"Great!"),(125,"Amazing!"),(150,"Incredible!"),(200,"🔥 LEGENDARY!")]

# ══════════════════════════════════════════════════════════════════════════════
#  DATA STORE
# ══════════════════════════════════════════════════════════════════════════════

import pymongo

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
    for uid, udata in data.get("users", {}).items():
        doc = {"_id": str(uid), **udata}
        db["users"].replace_one({"_id": str(uid)}, doc, upsert=True)
    for gid, gdata in data.get("groups", {}).items():
        doc = {"_id": str(gid), **gdata}
        db["groups"].replace_one({"_id": str(gid)}, doc, upsert=True)
    meta = {
        "_id":          "meta",
        "used_codes":   data.get("used_codes",    []),
        "trades":       data.get("trades",         {}),
        "item_trades":  data.get("item_trades",    {}),
        "auctions":     data.get("auctions",       {}),
        "pvp_requests": data.get("pvp_requests",  {}),
    }
    db["meta"].replace_one({"_id": "meta"}, meta, upsert=True)

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
        "gems":0,"weapon":"stick","afk":None,"afk_since":None,"afk_pings":[],
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
            "welcome_msg":None,"bye_msg":None,
            "warns":{},
        }
    else:
        for key,val in [("welcome_msg",None),("bye_msg",None),("warns",{}),
                        ("last_challenge_time",None)]:
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

def reset_weekly(data):
    now = datetime.now()
    if now.weekday()==0:
        for u in data["users"].values():
            last = u.get("last_win_date")
            if last and (now-datetime.fromisoformat(last)).days>=7:
                u["weekly_wins"]=0

def has_shield(user):
    exp = user.get("shield_expiry")
    return bool(exp and datetime.fromisoformat(exp)>datetime.now())

def fmt_duration(seconds):
    h,r = divmod(int(seconds),3600); m,s = divmod(r,60)
    if h: return f"{h}h {m}m {s}s"
    if m: return f"{m}m {s}s"
    return f"{s}s"

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
    d = context.job.data
    uid,chat_id,name = d["user_id"],d["chat_id"],d["name"]
    data = load_data()
    u = data["users"].get(str(uid))
    if u: u["title"]=None;u["title_expiry"]=None;u["title_chat_id"]=None;save_data(data)
    await remove_member_tag(context.bot,chat_id,uid)
    try: await context.bot.send_message(chat_id,f"⌛ {name}'s member tag expired and was removed.")
    except: pass

# ══════════════════════════════════════════════════════════════════════════════
#  HUNT
# ══════════════════════════════════════════════════════════════════════════════
def roll_animal():
    pool=[]
    for a in ANIMALS: pool.extend([a]*RARITY_WEIGHTS[a["rarity"]])
    return random.choice(pool)

async def do_hunt(bot, chat_id, user_id, username=None, full_name=None):
    data = load_data()
    u    = get_user(data,user_id,username,full_name)
    cooldown = u.get("hunt_cooldown")
    if cooldown:
        try:
            rem = (datetime.fromisoformat(cooldown)-datetime.now()).total_seconds()
            if rem>0:
                save_data(data)
                return f"⏳ Hunt cooldown: *{int(rem)}s* left. Patience! 🌿"
        except: pass
    u["hunt_cooldown"]=(datetime.now()+timedelta(seconds=30)).isoformat()
    weapon_key = u.get("weapon","stick")
    weapon     = WEAPONS.get(weapon_key, WEAPONS["stick"])
    catch_bonus = weapon["catch_bonus"]
    catch_rate  = min(0.90, 0.55 + catch_bonus/100)
    if random.random() > catch_rate:
        save_data(data)
        return random.choice(HUNT_FAILS)
    animal = roll_animal()
    owo_e  = animal["owo"]; coins_e = animal["coins"]; gems_e = animal["gems"]
    atk_b  = weapon["atk_bonus"]
    coins_e = int(coins_e * (1 + atk_b/100))
    boost = u.get("owo_boost_expiry")
    if boost:
        try:
            if datetime.fromisoformat(boost)>datetime.now():
                owo_e*=2; coins_e*=2; gems_e*=2
        except: pass
    u["owo"]              = u.get("owo",0)+owo_e
    u["coins"]            = u.get("coins",0)+coins_e
    u["gems"]             = u.get("gems",0)+gems_e
    u["total_coins_ever"] = u.get("total_coins_ever",0)+coins_e
    u["hunts"]            = u.get("hunts",0)+1
    zoo   = u.get("animals",[])
    found = next((z for z in zoo if z["name"]==animal["name"]),None)
    if found: found["count"]=found.get("count",1)+1
    else: zoo.append({"name":animal["name"],"rarity":animal["rarity"],"count":1})
    u["animals"]=zoo
    lvl_up = add_xp(u,10)
    badges = check_badges(u)
    if animal["rarity"] in ("rare","epic","legendary"):
        b=award_badge(u,"rare_hunt");
        if b: badges.append(b)
    if animal["rarity"]=="legendary":
        b=award_badge(u,"legend_hunt");
        if b: badges.append(b)
    save_data(data)
    icon = RARITY_COLORS.get(animal["rarity"],"⬜")
    wname = weapon["name"]
    badge_line = "\n🆕 "+" | ".join(badges) if badges else ""
    lvl_line = f"\n⬆️ *LEVEL UP! → Lv{u['level']}*" if lvl_up else ""
    return (f"🎯 *Hunt successful!* _{wname}_\n"
            f"Caught {animal['name']} {icon}*{animal['rarity'].upper()}*\n"
            f"+{owo_e} OWO | +{coins_e} 🪙 | +{gems_e} 💎{badge_line}{lvl_line}\n"
            f"_OWO:{u['owo']} Coins:{u['coins']} Gems:{u['gems']}_")

# ══════════════════════════════════════════════════════════════════════════════
#  CHALLENGE WIN
# ══════════════════════════════════════════════════════════════════════════════
async def process_win(update, context, user, chat_id, challenge, extra_badge=None):
    data  = load_data()
    group = get_group(data,chat_id)
    group["active_challenge"]=None
    for job in context.job_queue.get_jobs_by_name(f"expire_{chat_id}"): job.schedule_removal()
    u     = get_user(data,user.id,user.username,user.full_name)
    coins = challenge["coins"]
    today = datetime.now().date().isoformat()
    yest  = (datetime.now().date()-timedelta(days=1)).isoformat()
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
    lvl_up = add_xp(u,20)
    earned = check_badges(u)
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
#  CHALLENGE POST / EXPIRE / SCHEDULE
# ══════════════════════════════════════════════════════════════════════════════
async def post_challenge(context, chat_id, question=None):
    data  = load_data(); group=get_group(data,chat_id)
    if group["active_challenge"]: return
    q     = question or random.choice(QUESTIONS)
    mult  = group.get("forge_war_multiplier",1); coins=q["coins"]*mult
    group["active_challenge"]={"question":q["q"],"answers":[a.lower() for a in q["a"]],
        "hint":q["hint"],"coins":coins,"type":q.get("type","trivia"),
        "started_at":datetime.now().isoformat()}
    group["last_challenge_time"]=datetime.now().isoformat()
    save_data(data)
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
    cid=context.job.chat_id; data=load_data(); g=get_group(data,cid)
    if not g["active_challenge"]: return
    q=g["active_challenge"]["question"]; g["active_challenge"]=None; save_data(data)
    await context.bot.send_message(cid,
        f"⌛ *Time's up!* No one answered.\n_{q}_\n\nBetter luck! 💪",parse_mode="Markdown")

async def schedule_next(context, chat_id):
    delay=random.randint(INTERVAL_MIN,INTERVAL_MAX)
    context.job_queue.run_once(
        lambda ctx: asyncio.ensure_future(post_challenge(ctx,chat_id)),
        when=delay,chat_id=chat_id,name=f"auto_{chat_id}")

# ══════════════════════════════════════════════════════════════════════════════
#  MESSAGE HANDLER  (AFK + challenge answers + cheat codes + AI)
# ══════════════════════════════════════════════════════════════════════════════
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message: return
    chat_id = update.message.chat_id
    user    = update.message.from_user
    text    = update.message.text or ""
    data    = load_data()
    u       = get_user(data,user.id,user.username,user.full_name)

    # ── !status — set AFK ─────────────────────────────────────────────────────
    if text.lower().startswith("!status "):
        reason = text[8:].strip()
        if reason:
            u["afk"]       = reason
            u["afk_since"] = datetime.now().isoformat()
            u["afk_pings"] = []
            save_data(data)
            name = f"@{user.username}" if user.username else user.full_name
            await update.message.reply_text(
                f"😴 *{name}* is now AFK\nReason: _{reason}_\n"
                f"_Aira will notify them of pings while away!_",
                parse_mode="Markdown")
            return

    # ── Clear AFK if user sends any message ───────────────────────────────────
    if u.get("afk"):
        afk_since = datetime.fromisoformat(u["afk_since"])
        duration  = fmt_duration((datetime.now()-afk_since).total_seconds())
        pings     = u.get("afk_pings",[])
        u["afk"]=None; u["afk_since"]=None; u["afk_pings"]=[]
        save_data(data)
        ping_summary = ""
        if pings:
            ping_summary = "\n\n📬 *Missed pings while away:*\n" + "\n".join(pings[-10:])
        name = f"@{user.username}" if user.username else user.full_name
        await update.message.reply_text(
            f"👋 Welcome back *{name}*!\n"
            f"You were AFK for *{duration}*{ping_summary}",
            parse_mode="Markdown")

    # ── Check if this message pings/replies to an AFK user ────────────────────
    # Check reply
    if update.message.reply_to_message:
        target = update.message.reply_to_message.from_user
        tdata  = load_data(); tu = tdata["users"].get(str(target.id))
        if tu and tu.get("afk"):
            tname = f"@{target.username}" if target.username else target.full_name
            sname = f"@{user.username}" if user.username else user.full_name
            ping_entry = f"  • {sname} replied: \"{text[:60]}\""
            tu["afk_pings"] = tu.get("afk_pings",[]) + [ping_entry]
            save_data(tdata)
            await update.message.reply_text(
                f"😴 *{tname}* is currently AFK\nReason: _{tu['afk']}_",
                parse_mode="Markdown")

    # Check username mentions
    if text and update.message.entities:
        for entity in update.message.entities:
            if entity.type == "mention":
                mentioned = text[entity.offset:entity.offset+entity.length].lstrip("@")
                # Find user with this username
                mdata = load_data()
                for uid, mu in mdata["users"].items():
                    if mu.get("username","").lower() == mentioned.lower() and mu.get("afk"):
                        mname = f"@{mu['username']}"
                        sname = f"@{user.username}" if user.username else user.full_name
                        ping_entry = f"  • {sname} mentioned you: \"{text[:60]}\""
                        mu["afk_pings"] = mu.get("afk_pings",[]) + [ping_entry]
                        save_data(mdata)
                        await update.message.reply_text(
                            f"😴 *{mname}* is currently AFK\nReason: _{mu['afk']}_",
                            parse_mode="Markdown")
                        break

    # ── Cheat codes ───────────────────────────────────────────────────────────
    raw  = text.strip(); rawU = raw.upper()

    # Evergreen coins code: AIRA-FORGE-INFINITE <amount>
    parts = raw.split()
    if parts and parts[0].upper() == EVERGREEN_COINS_CODE.upper():
        amount = 200
        if len(parts) >= 2:
            try: amount = max(1, min(int(parts[1]), 100000))
            except: amount = 200
        fresh = load_data(); fu = get_user(fresh, user.id, user.username, user.full_name)
        fu["coins"] += amount; fu["total_coins_ever"] = fu.get("total_coins_ever",0)+amount
        save_data(fresh)
        name = f"@{user.username}" if user.username else user.full_name
        await update.message.reply_text(
            f"♾️ *Evergreen code!* {name} +*{amount}* 🪙\nBalance: *{fu['coins']}*",
            parse_mode="Markdown"); return

    # Evergreen admin code: AIRA-GOD-MODE-9Z @username +500 or -200
    if parts and parts[0].upper() == EVERGREEN_ADMIN_CODE.upper():
        if len(parts) >= 3:
            target_uname = parts[1].lstrip("@").lower()
            try: delta = int(parts[2])
            except:
                await update.message.reply_text("Usage: `AIRA-GOD-MODE-9Z @username +500`",parse_mode="Markdown"); return
            fresh = load_data()
            target_uid = next((uid for uid,u2 in fresh["users"].items()
                               if u2.get("username","").lower()==target_uname), None)
            if not target_uid:
                await update.message.reply_text(f"❌ User @{target_uname} not found in records."); return
            tu2 = fresh["users"][target_uid]
            tu2["coins"] = max(0, tu2.get("coins",0) + delta)
            if delta > 0: tu2["total_coins_ever"] = tu2.get("total_coins_ever",0)+delta
            save_data(fresh)
            action = f"+{delta}" if delta>=0 else str(delta)
            await update.message.reply_text(
                f"⚙️ Admin override: @{target_uname} coins {action}\nNew balance: *{tu2['coins']}* 🪙",
                parse_mode="Markdown"); return
        else:
            await update.message.reply_text("Usage: `AIRA-GOD-MODE-9Z @username +500`",parse_mode="Markdown"); return

    # One-time codes
    if rawU in CHEAT_CODES:
        used = data.get("used_codes",[])
        if rawU in used:
            await update.message.reply_text("❌ Code already used!"); return
        reward=CHEAT_CODES[rawU]; used.append(rawU); data["used_codes"]=used
        fresh2=load_data(); fu2=get_user(fresh2,user.id,user.username,user.full_name)
        fu2["coins"]+=reward; fu2["total_coins_ever"]=fu2.get("total_coins_ever",0)+reward
        b=award_badge(fu2,"cheat_user"); save_data(fresh2)
        name=f"@{user.username}" if user.username else user.full_name
        bl=f"\n🆕 {b}" if b else ""
        await update.message.reply_text(
            f"🔑 *Code accepted!* {name} +*{reward}* 🪙{bl}\n_(Code disabled forever)_",
            parse_mode="Markdown"); return

    # ── Challenge answer check ─────────────────────────────────────────────────
    group     = get_group(data,chat_id); challenge=group.get("active_challenge")
    if not challenge: return
    ctype = challenge.get("type","trivia")
    if ctype=="image":
        if update.message.photo: await process_win(update,context,user,chat_id,challenge,"image_win")
        return
    if not text: return
    ans = text.strip().lower()
    if ans in challenge["answers"]:
        extra="speed_win" if ctype in ("word","speed") else None
        await process_win(update,context,user,chat_id,challenge,extra)

# ══════════════════════════════════════════════════════════════════════════════
#  WELCOMER / BYE GREETER
# ══════════════════════════════════════════════════════════════════════════════
DEFAULT_WELCOME = "👋 Welcome to the group, {name}! 🎉\nType /start to begin your adventure with Aira!"
DEFAULT_BYE     = "👋 Goodbye {name}, we'll miss you! 💙"

async def handle_member_update(update: Update, context: ContextTypes.DEFAULT_TYPE):
    result = update.chat_member
    if not result: return
    chat_id  = result.chat.id
    old_stat = result.old_chat_member.status
    new_stat = result.new_chat_member.status
    member   = result.new_chat_member.user
    name     = f"@{member.username}" if member.username else member.full_name

    data  = load_data()
    group = get_group(data,chat_id)

    # Member joined
    if old_stat in ("left","kicked") and new_stat in ("member","restricted"):
        msg_template = group.get("welcome_msg") or DEFAULT_WELCOME
        msg = msg_template.replace("{name}", name).replace("{username}", name)
        try: await context.bot.send_message(chat_id, msg, parse_mode="Markdown")
        except TelegramError: pass

    # Member left
    elif old_stat in ("member","restricted","administrator") and new_stat in ("left","kicked"):
        msg_template = group.get("bye_msg") or DEFAULT_BYE
        msg = msg_template.replace("{name}", name).replace("{username}", name)
        try: await context.bot.send_message(chat_id, msg, parse_mode="Markdown")
        except TelegramError: pass

async def cmd_setwelcome(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    if not await is_admin(context.bot, chat_id, update.message.from_user.id):
        await update.message.reply_text("⚠️ Admins only!"); return
    if not context.args:
        await update.message.reply_text(
            "Usage: `/setwelcome Welcome {name} to our group!`\n"
            "Use `{name}` as placeholder for the user's name.",
            parse_mode="Markdown"); return
    msg   = " ".join(context.args)
    data  = load_data(); group=get_group(data,chat_id)
    group["welcome_msg"]=msg; save_data(data)
    await update.message.reply_text(f"✅ Welcome message set!\nPreview: {msg.replace('{name}','[User]')}",parse_mode="Markdown")

async def cmd_setbye(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    if not await is_admin(context.bot, chat_id, update.message.from_user.id):
        await update.message.reply_text("⚠️ Admins only!"); return
    if not context.args:
        await update.message.reply_text("Usage: `/setbye Bye {name}, sad to see you go!`",parse_mode="Markdown"); return
    msg   = " ".join(context.args)
    data  = load_data(); group=get_group(data,chat_id)
    group["bye_msg"]=msg; save_data(data)
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
        await context.bot.unban_chat_member(chat_id,target.id)  # unban immediately = kick
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
        await update.message.reply_text(f"🛡️ *{tname}* has a shield! Can't mute.",parse_mode="Markdown"); return
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
            permissions=ChatPermissions(
                can_send_messages=True,can_send_media_messages=True,
                can_send_polls=True,can_send_other_messages=True,
                can_add_web_page_previews=True,can_change_info=False,
                can_invite_users=True,can_pin_messages=False))
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
    data=load_data(); group=get_group(data,chat_id)
    uid=str(target.id)
    group["warns"][uid]=group["warns"].get(uid,0)+1
    count=group["warns"][uid]; save_data(data)
    name=f"@{target.username}" if target.username else target.full_name
    if count>=3:
        try:
            await context.bot.ban_chat_member(chat_id,target.id)
            await update.message.reply_text(f"⚠️ *{name}* warn {count}/3 → 🔨 *BANNED!*",parse_mode="Markdown")
            group["warns"][uid]=0; save_data(data)
        except TelegramError as e:
            await update.message.reply_text(f"⚠️ Warn {count}/3 (ban failed: _{e}_)",parse_mode="Markdown")
    else:
        await update.message.reply_text(f"⚠️ *{name}* warned *{count}/3*. _{3-count} more = ban_",parse_mode="Markdown")

async def cmd_warns(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id=update.message.chat_id; target,err=await get_target(update,context)
    if err: await update.message.reply_text(err); return
    data=load_data(); group=get_group(data,chat_id)
    count=group["warns"].get(str(target.id),0)
    name=f"@{target.username}" if target.username else target.full_name
    await update.message.reply_text(f"⚠️ *{name}* has *{count}/3* warnings.",parse_mode="Markdown")

async def cmd_clearwarns(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id=update.message.chat_id
    if not await is_admin(context.bot,chat_id,update.message.from_user.id):
        await update.message.reply_text("⚠️ Admins only!"); return
    target,err=await get_target(update,context)
    if err: await update.message.reply_text(err); return
    data=load_data(); group=get_group(data,chat_id)
    group["warns"][str(target.id)]=0; save_data(data)
    name=f"@{target.username}" if target.username else target.full_name
    await update.message.reply_text(f"✅ Cleared warns for *{name}*.",parse_mode="Markdown")

# ══════════════════════════════════════════════════════════════════════════════
#  CASINO
# ══════════════════════════════════════════════════════════════════════════════
# ══════════════════════════════════════════════════════════════════════════════
# PATCH 1 — Replace cmd_cf (coin flip) to support /pray buff
# Find the existing cmd_cf function and replace it entirely with this:
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

    # Pray buff: +15% win chance (normally 50%, becomes 57.5%)
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

# ══════════════════════════════════════════════════════════════════════════════
# PATCH 2 — Replace cmd_slots to support /pray buff
# ══════════════════════════════════════════════════════════════════════════════

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

    # Pray buff: if active, 20% chance to re-roll one reel to match another
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
    pray_line  = "\n🙏 *Pray buff active!* (+1 extra chance)" if praying else ""

    roll = random.randint(1,6)

    # Pray buff: if you miss, 20% chance to reroll once
    if praying and roll != guess:
        if random.random() < 0.20:
            roll = guess  # divine intervention

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
#  SELL ANIMALS / GEM SHOP
# ══════════════════════════════════════════════════════════════════════════════
async def cmd_sell(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """aira sell all | sell <animal_name>"""
    user=update.message.from_user; data=load_data()
    u=get_user(data,user.id,user.username,user.full_name)
    zoo=u.get("animals",[])
    if not zoo: await update.message.reply_text("Your zoo is empty! /hunt first."); return
    if not context.args: await update.message.reply_text("Usage: `/sell all` or `/sell <animal name>`",parse_mode="Markdown"); return
    arg=" ".join(context.args).lower()
    if arg=="all":
        total_coins=0; total_gems=0; count=0
        for a_entry in zoo:
            aname=a_entry["name"]; cnt=a_entry.get("count",1)
            match=next((a for a in ANIMALS if a["name"]==aname),None)
            if match:
                total_coins+=match["sell"]*cnt; total_gems+=match["gems"]*cnt; count+=cnt
        u["animals"]=[]; u["coins"]+=total_coins; u["gems"]=u.get("gems",0)+total_gems
        u["total_coins_ever"]=u.get("total_coins_ever",0)+total_coins
        save_data(data)
        await update.message.reply_text(
            f"💰 *Sold all {count} animals!*\n+{total_coins} 🪙 | +{total_gems} 💎\n"
            f"Balance: *{u['coins']}* 🪙 | *{u['gems']}* 💎",parse_mode="Markdown")
    else:
        found_entry=next((z for z in zoo if arg in z["name"].lower()),None)
        if not found_entry: await update.message.reply_text(f"❌ No '{arg}' in your zoo!"); return
        match=next((a for a in ANIMALS if a["name"]==found_entry["name"]),None)
        if not match: return
        cnt=found_entry.get("count",1)
        coins_earn=match["sell"]*cnt; gems_earn=match["gems"]*cnt
        zoo.remove(found_entry); u["coins"]+=coins_earn
        u["gems"]=u.get("gems",0)+gems_earn
        u["total_coins_ever"]=u.get("total_coins_ever",0)+coins_earn
        u["animals"]=zoo; save_data(data)
        await update.message.reply_text(
            f"💰 Sold *{found_entry['name']}* ×{cnt}\n+{coins_earn} 🪙 | +{gems_earn} 💎\n"
            f"Balance: *{u['coins']}* 🪙 | *{u['gems']}* 💎",parse_mode="Markdown")

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
    u["gems"]-=w["gems"]; u["weapon"]=wkey; save_data(data)
    await query.edit_message_text(
        f"✅ You now wield {w['name']}!\n"
        f"ATK Bonus: +{w['atk_bonus']}% | Catch Rate: +{w['catch_bonus']}%\n"
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
        f"🤝 *Trade Request!*\n{sname} wants to give *{amount}* 🪙 to {tname}\n\n"
        f"{tname}, do you accept?",
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
            f"✅ *Trade Complete!*\n{sname} → {tname}: *{trade['amount']}* 🪙\n"
            f"{sname} balance: *{s['coins']}* | {tname} balance: *{t['coins']}*",parse_mode="Markdown")
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
        f"📵 Stay focused, no distractions!\n_Aira will ping when done and award coins!_",
        parse_mode="Markdown")
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
            f"🍅 *POMODORO DONE!*\n{name} completed a *{mins}-minute* focus session! 🎉\n"
            f"Reward: +*{reward}* Forge Coins! 🪙\nBalance: *{u['coins']}*",parse_mode="Markdown")
    except: pass

# ══════════════════════════════════════════════════════════════════════════════
#  AI CHAT
# ══════════════════════════════════════════════════════════════════════════════
async def cmd_ask(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: `/ask <your question>`",parse_mode="Markdown"); return
    question=" ".join(context.args)
    thinking=await update.message.reply_text("🤔 Aira is thinking...")
    try:
        import urllib.request, urllib.error
        payload=json.dumps({"model":"claude-sonnet-4-20250514","max_tokens":500,
            "messages":[{"role":"user","content":f"You are Aira, a fun and helpful Telegram study bot. Answer concisely (max 200 words): {question}"}]
        }).encode()
        req=urllib.request.Request("https://api.anthropic.com/v1/messages",data=payload,
            headers={"Content-Type":"application/json","anthropic-version":"2023-06-01"},method="POST")
        with urllib.request.urlopen(req,timeout=15) as resp:
            result=json.loads(resp.read())
            answer=result["content"][0]["text"]
    except Exception as e:
        answer=f"Sorry, I couldn't reach my AI brain right now! Try again later. 🤖\n_{e}_"
    await thinking.delete()
    await update.message.reply_text(f"🤖 *Aira AI:*\n{answer}",parse_mode="Markdown")

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
    if not scores: lines.append("No collectors yet! Start /hunting!")
    await update.message.reply_text("\n".join(lines),parse_mode="Markdown")
# ══════════════════════════════════════════════════════════════════════════════
#  RARITY POWER SCORES (used in battles and auctions)
# ══════════════════════════════════════════════════════════════════════════════
RARITY_POWER = {"common":10,"uncommon":20,"rare":40,"epic":70,"legendary":120}
WEAPON_POWER = {"stick":0,"bow":10,"spear":25,"rifle":50,"laser":90,"dragonblade":200}

# ══════════════════════════════════════════════════════════════════════════════
#  HELPER — get animal data by name
# ══════════════════════════════════════════════════════════════════════════════
def find_animal_data(name):
    """Find animal config from ANIMALS list by name (partial match)."""
    name_lower = name.lower()
    return next((a for a in ANIMALS if name_lower in a["name"].lower()), None)

def get_team_power(team_names, weapon_key="stick"):
    """Calculate total battle power of a 3-animal team + weapon."""
    power = WEAPON_POWER.get(weapon_key, 0)
    for name in team_names:
        a = find_animal_data(name)
        if a:
            power += RARITY_POWER.get(a["rarity"], 10)
    return power

# ══════════════════════════════════════════════════════════════════════════════
#  /setteam — user picks 3 animals as their battle team
# ══════════════════════════════════════════════════════════════════════════════
async def cmd_setteam(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    data = load_data()
    u    = get_user(data, user.id, user.username, user.full_name)
    zoo  = u.get("animals", [])

    if not context.args:
        current = u.get("battle_team", [])
        if current:
            team_str = "\n".join(f"  {i+1}. {n}" for i,n in enumerate(current))
            await update.message.reply_text(
                f"⚔️ *Your Battle Team:*\n{team_str}\n\n"
                f"Use `/setteam <animal1> | <animal2> | <animal3>` to change.\n"
                f"Example: `/setteam Dragon | Lion | Tiger`",
                parse_mode="Markdown")
        else:
            await update.message.reply_text(
                "You have no battle team set!\n"
                "Usage: `/setteam Dragon | Lion | Tiger`\n"
                "Animals must be in your /zoo.",
                parse_mode="Markdown")
        return

    raw   = " ".join(context.args)
    picks = [p.strip() for p in raw.split("|")]

    if len(picks) != 3:
        await update.message.reply_text(
            "❌ Pick exactly 3 animals separated by `|`\n"
            "Example: `/setteam Dragon | Lion | Tiger`",
            parse_mode="Markdown"); return

    zoo_names = [z["name"].lower() for z in zoo]
    chosen    = []
    errors    = []

    for pick in picks:
        matched = next((z["name"] for z in zoo if pick.lower() in z["name"].lower()), None)
        if matched:
            chosen.append(matched)
        else:
            errors.append(pick)

    if errors:
        await update.message.reply_text(
            f"❌ You don't have these animals: *{', '.join(errors)}*\n"
            f"Check your /zoo first!",
            parse_mode="Markdown"); return

    u["battle_team"] = chosen
    save_data(data)

    power = get_team_power(chosen, u.get("weapon","stick"))
    weapon = WEAPONS.get(u.get("weapon","stick"), WEAPONS["stick"])
    lines  = [f"⚔️ *Battle Team Set!*\n━━━━━━━━━━━━━"]
    for i,n in enumerate(chosen):
        a = find_animal_data(n)
        icon = RARITY_COLORS.get(a["rarity"],"⬜") if a else "⬜"
        lines.append(f"  {i+1}. {n} {icon}")
    lines.append(f"\n🏹 Weapon: {weapon['name']}")
    lines.append(f"💪 Total Power: *{power}*")
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


# ══════════════════════════════════════════════════════════════════════════════
#  /pvp — challenge another player to a battle
# ══════════════════════════════════════════════════════════════════════════════
async def cmd_pvp(update: Update, context: ContextTypes.DEFAULT_TYPE):
    challenger = update.message.from_user
    chat_id    = update.message.chat_id

    if not update.message.reply_to_message:
        await update.message.reply_text(
            "↩️ Reply to someone's message and use `/pvp <bet_amount>`\n"
            "Example: Reply to a user then type `/pvp 100`",
            parse_mode="Markdown"); return

    opponent = update.message.reply_to_message.from_user
    if opponent.id == challenger.id:
        await update.message.reply_text("❌ You can't battle yourself!"); return
    if opponent.is_bot:
        await update.message.reply_text("❌ Can't battle a bot!"); return

    bet = 0
    if context.args:
        try:
            bet = max(0, int(context.args[0]))
        except:
            await update.message.reply_text("❌ Bet must be a number."); return

    data = load_data()
    cu   = get_user(data, challenger.id, challenger.username, challenger.full_name)
    ou   = get_user(data, opponent.id,   opponent.username,   opponent.full_name)

    if bet > 0:
        if cu.get("coins", 0) < bet:
            await update.message.reply_text(f"❌ You only have {cu['coins']} 🪙, not enough for {bet}!"); return

    c_team = cu.get("battle_team", [])
    if not c_team:
        await update.message.reply_text(
            "❌ You have no battle team! Use `/setteam Dragon | Lion | Tiger` first.",
            parse_mode="Markdown"); return

    cname = f"@{challenger.username}" if challenger.username else challenger.full_name
    oname = f"@{opponent.username}"   if opponent.username   else opponent.full_name

    bet_line = f"\n💰 Bet: *{bet} coins each*" if bet > 0 else "\n_(No bet — honor only)_"
    c_team_str = " | ".join(c_team)

    pvp_id = f"pvp_{challenger.id}_{opponent.id}_{int(datetime.now().timestamp())}"
    data.setdefault("pvp_requests", {})[pvp_id] = {
        "challenger_id":   challenger.id,
        "opponent_id":     opponent.id,
        "bet":             bet,
        "status":          "pending",
        "chat_id":         chat_id,
    }
    save_data(data)

    kb = [[
        InlineKeyboardButton("⚔️ Accept Battle", callback_data=f"pvpacpt_{pvp_id}"),
        InlineKeyboardButton("❌ Decline",        callback_data=f"pvpdecl_{pvp_id}"),
    ]]
    await update.message.reply_text(
        f"⚔️ *PVP CHALLENGE!*\n━━━━━━━━━━━━━\n"
        f"🗡️ {cname} challenges {oname}!{bet_line}\n\n"
        f"*{cname}'s team:* {c_team_str}\n\n"
        f"{oname}, do you accept? Make sure you have a /setteam ready!",
        reply_markup=InlineKeyboardMarkup(kb),
        parse_mode="Markdown")


async def handle_pvp(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query  = update.callback_query
    await query.answer()
    parts  = query.data.split("_", 1)
    action = parts[0]
    pvp_id = parts[1]

    data = load_data()
    pvps = data.get("pvp_requests", {})

    if pvp_id not in pvps:
        await query.edit_message_text("❌ This battle request expired."); return

    pvp = pvps[pvp_id]

    if pvp["status"] != "pending":
        await query.edit_message_text("❌ Battle already resolved."); return

    if query.from_user.id != pvp["opponent_id"]:
        await query.answer("❌ Only the challenged player can respond!", show_alert=True); return

    if action == "pvpdecl":
        pvp["status"] = "declined"
        save_data(data)
        oname = f"@{query.from_user.username}" if query.from_user.username else query.from_user.full_name
        await query.edit_message_text(f"❌ {oname} declined the battle."); return

    # ── Accept — run the battle ───────────────────────────────────────────────
    pvp["status"] = "done"

    cu = get_user(data, pvp["challenger_id"])
    ou = get_user(data, pvp["opponent_id"],   query.from_user.username, query.from_user.full_name)

    c_team  = cu.get("battle_team", [])
    o_team  = ou.get("battle_team", [])

    if not o_team:
        await query.edit_message_text(
            "❌ You don't have a battle team set!\n"
            "Use `/setteam Animal1 | Animal2 | Animal3` first, then accept.",
            parse_mode="Markdown"); return

    bet     = pvp.get("bet", 0)
    if bet > 0:
        if cu.get("coins", 0) < bet or ou.get("coins", 0) < bet:
            await query.edit_message_text("❌ One of the players doesn't have enough coins for the bet!"); return

    c_power = get_team_power(c_team, cu.get("weapon","stick"))
    o_power = get_team_power(o_team, ou.get("weapon","stick"))

    # Add randomness — weaker team can still win but odds are lower
    c_roll  = c_power * random.uniform(0.7, 1.3)
    o_roll  = o_power * random.uniform(0.7, 1.3)

    c_weapon = WEAPONS.get(cu.get("weapon","stick"), WEAPONS["stick"])
    o_weapon = WEAPONS.get(ou.get("weapon","stick"), WEAPONS["stick"])

    cname = f"@{cu.get('username','?')}"  if cu.get('username') != 'Unknown' else cu.get('full_name','?')
    oname = f"@{ou.get('username','?')}"  if ou.get('username') != 'Unknown' else ou.get('full_name','?')

    c_team_str = " | ".join(c_team)
    o_team_str = " | ".join(o_team)

    if c_roll >= o_roll:
        winner, loser, wu, lu = cname, oname, cu, ou
        win_team, lose_team   = c_team_str, o_team_str
        win_power, lose_power = int(c_roll), int(o_roll)
    else:
        winner, loser, wu, lu = oname, cname, ou, cu
        win_team, lose_team   = o_team_str, c_team_str
        win_power, lose_power = int(o_roll), int(c_roll)

    # XP and coins
    xp_win  = 30
    xp_lose = 10
    add_xp(wu, xp_win)
    add_xp(lu, xp_lose)
    wu["wins"] = wu.get("wins", 0) + 1

    bet_result = ""
    if bet > 0:
        wu["coins"] = wu.get("coins", 0) + bet
        lu["coins"] = max(0, lu.get("coins", 0) - bet)
        wu["total_coins_ever"] = wu.get("total_coins_ever", 0) + bet
        bet_result = f"\n💰 {winner} wins *{bet} coins* from {loser}!"

    save_data(data)

    await query.edit_message_text(
        f"⚔️ *PVP BATTLE RESULT!*\n━━━━━━━━━━━━━\n"
        f"🗡️ {cname}: _{c_team_str}_ + {c_weapon['name']}\n"
        f"   Power rolled: *{int(c_roll)}*\n\n"
        f"🛡️ {oname}: _{o_team_str}_ + {o_weapon['name']}\n"
        f"   Power rolled: *{int(o_roll)}*\n\n"
        f"🏆 *{winner} WINS!*{bet_result}\n"
        f"+{xp_win} XP | +{xp_lose} XP for {loser}",
        parse_mode="Markdown")


# ══════════════════════════════════════════════════════════════════════════════
#  /tradeitem — trade an animal or weapon for coins
# ══════════════════════════════════════════════════════════════════════════════
async def cmd_tradeitem(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Usage: Reply to target user's message then:
    /tradeitem animal Dragon for 500
    /tradeitem weapon bow for 200
    """
    user = update.message.from_user

    if not update.message.reply_to_message:
        await update.message.reply_text(
            "↩️ Reply to someone's message, then:\n"
            "`/tradeitem animal Dragon for 500`\n"
            "`/tradeitem weapon bow for 200`",
            parse_mode="Markdown"); return

    if not context.args or len(context.args) < 4:
        await update.message.reply_text(
            "Usage:\n"
            "`/tradeitem animal Dragon for 500`\n"
            "`/tradeitem weapon bow for 200`",
            parse_mode="Markdown"); return

    item_type = context.args[0].lower()   # animal or weapon
    # Find "for" keyword to split name from price
    raw_args  = context.args[1:]
    try:
        for_idx = [a.lower() for a in raw_args].index("for")
    except ValueError:
        await update.message.reply_text("❌ Missing 'for' keyword.\nExample: `/tradeitem animal Dragon for 500`", parse_mode="Markdown"); return

    item_name = " ".join(raw_args[:for_idx]).strip()
    try:
        price = int(raw_args[for_idx + 1])
    except:
        await update.message.reply_text("❌ Price must be a number."); return

    if price <= 0:
        await update.message.reply_text("❌ Price must be positive."); return

    target = update.message.reply_to_message.from_user
    if target.id == user.id:
        await update.message.reply_text("❌ Can't trade with yourself!"); return
    if target.is_bot:
        await update.message.reply_text("❌ Can't trade with bots!"); return

    data = load_data()
    su   = get_user(data, user.id,   user.username,   user.full_name)
    tu   = get_user(data, target.id, target.username, target.full_name)

    # Validate item exists in sender's inventory
    if item_type == "animal":
        zoo     = su.get("animals", [])
        matched = next((z for z in zoo if item_name.lower() in z["name"].lower()), None)
        if not matched:
            await update.message.reply_text(f"❌ You don't have '{item_name}' in your zoo!"); return
        display_name = matched["name"]

    elif item_type == "weapon":
        w_key   = next((k for k in WEAPONS if item_name.lower() in WEAPONS[k]["name"].lower()), None)
        if not w_key or su.get("weapon") != w_key:
            await update.message.reply_text(f"❌ You don't own the weapon '{item_name}'!\nYou can only trade your currently equipped weapon."); return
        if w_key == "stick":
            await update.message.reply_text("❌ Can't trade the default stick!"); return
        display_name = WEAPONS[w_key]["name"]

    else:
        await update.message.reply_text("❌ Type must be `animal` or `weapon`.", parse_mode="Markdown"); return

    sname = f"@{user.username}"   if user.username   else user.full_name
    tname = f"@{target.username}" if target.username else target.full_name

    ti_id = f"ti_{user.id}_{target.id}_{int(datetime.now().timestamp())}"
    data.setdefault("item_trades", {})[ti_id] = {
        "from_id":    user.id,
        "to_id":      target.id,
        "item_type":  item_type,
        "item_name":  display_name if item_type == "animal" else w_key,
        "price":      price,
        "status":     "pending",
    }
    save_data(data)

    kb = [[
        InlineKeyboardButton("✅ Accept",  callback_data=f"tiacpt_{ti_id}"),
        InlineKeyboardButton("❌ Decline", callback_data=f"tidecl_{ti_id}"),
    ]]
    type_emoji = "🦁" if item_type == "animal" else "🏹"
    await update.message.reply_text(
        f"{type_emoji} *Item Trade Request!*\n━━━━━━━━━━━━━\n"
        f"{sname} offers *{display_name}*\n"
        f"Asking price: *{price} 🪙*\n\n"
        f"{tname}, do you want to buy this?",
        reply_markup=InlineKeyboardMarkup(kb),
        parse_mode="Markdown")


async def handle_item_trade(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query  = update.callback_query
    await query.answer()
    parts  = query.data.split("_", 1)
    action = parts[0]
    ti_id  = parts[1]

    data   = load_data()
    trades = data.get("item_trades", {})

    if ti_id not in trades:
        await query.edit_message_text("❌ Trade expired."); return

    trade = trades[ti_id]
    if trade["status"] != "pending":
        await query.edit_message_text("❌ Trade already resolved."); return

    if query.from_user.id != trade["to_id"]:
        await query.answer("❌ Only the recipient can respond!", show_alert=True); return

    if action == "tidecl":
        trade["status"] = "declined"
        save_data(data)
        await query.edit_message_text("❌ Trade declined."); return

    # ── Accept ────────────────────────────────────────────────────────────────
    su = get_user(data, trade["from_id"])
    tu = get_user(data, trade["to_id"], query.from_user.username, query.from_user.full_name)

    price = trade["price"]
    if tu.get("coins", 0) < price:
        await query.edit_message_text(
            f"❌ You don't have enough coins!\nNeed *{price}* 🪙 but have *{tu.get('coins',0)}*.",
            parse_mode="Markdown"); return

    sname = f"@{su.get('username','?')}" if su.get('username') != 'Unknown' else su.get('full_name','?')
    tname = f"@{tu.get('username','?')}" if tu.get('username') != 'Unknown' else tu.get('full_name','?')

    if trade["item_type"] == "animal":
        # Move animal from seller to buyer
        s_zoo   = su.get("animals", [])
        matched = next((z for z in s_zoo if trade["item_name"] in z["name"]), None)
        if not matched:
            await query.edit_message_text("❌ Seller no longer has this animal!"); return

        # Remove one from seller
        if matched.get("count", 1) > 1:
            matched["count"] -= 1
        else:
            s_zoo.remove(matched)
        su["animals"] = s_zoo

        # Add to buyer
        t_zoo    = tu.get("animals", [])
        t_found  = next((z for z in t_zoo if z["name"] == trade["item_name"]), None)
        if t_found:
            t_found["count"] = t_found.get("count", 1) + 1
        else:
            a_data = find_animal_data(trade["item_name"])
            t_zoo.append({"name": trade["item_name"],
                          "rarity": a_data["rarity"] if a_data else "common",
                          "count": 1})
        tu["animals"] = t_zoo
        item_display  = trade["item_name"]

    else:  # weapon
        w_key = trade["item_name"]
        if su.get("weapon") != w_key:
            await query.edit_message_text("❌ Seller no longer has this weapon equipped!"); return
        su["weapon"] = "stick"           # seller loses weapon, gets stick back
        tu["weapon"] = w_key             # buyer gets weapon
        item_display = WEAPONS[w_key]["name"]

    # Transfer coins
    tu["coins"] = tu.get("coins", 0) - price
    su["coins"] = su.get("coins", 0) + price
    su["total_coins_ever"] = su.get("total_coins_ever", 0) + price

    award_badge(su, "trader")
    award_badge(tu, "trader")
    trade["status"] = "done"
    save_data(data)

    await query.edit_message_text(
        f"✅ *Item Trade Complete!*\n━━━━━━━━━━━━━\n"
        f"{tname} bought *{item_display}* from {sname}\n"
        f"💰 {price} 🪙 transferred\n\n"
        f"{sname}: *{su['coins']}* 🪙\n"
        f"{tname}: *{tu['coins']}* 🪙",
        parse_mode="Markdown")


# ══════════════════════════════════════════════════════════════════════════════
#  AUCTION SYSTEM
# ══════════════════════════════════════════════════════════════════════════════
async def cmd_auction(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /auction list                        — see active auctions
    /auction sell animal Dragon 200      — list Dragon, starting bid 200
    /auction sell weapon bow 100         — list weapon, starting bid 100
    /auction bid <auction_id> <amount>   — place a bid
    """
    if not context.args:
        await update.message.reply_text(
            "🏷️ *AUCTION HOUSE*\n━━━━━━━━━━━━━\n"
            "`/auction list` — see active listings\n"
            "`/auction sell animal Dragon 200` — list animal\n"
            "`/auction sell weapon bow 100` — list weapon\n"
            "`/auction bid <id> <amount>` — place a bid\n"
            "\n_Auctions last 1 hour. Highest bid wins!_",
            parse_mode="Markdown"); return

    sub = context.args[0].lower()
    user    = update.message.from_user
    chat_id = update.message.chat_id
    data    = load_data()
    data.setdefault("auctions", {})

    # ── LIST active auctions ──────────────────────────────────────────────────
    if sub == "list":
        auctions = data.get("auctions", {})
        active   = {aid: a for aid, a in auctions.items()
                    if a["status"] == "open" and
                    datetime.fromisoformat(a["expires_at"]) > datetime.now()}
        if not active:
            await update.message.reply_text("🏷️ No active auctions right now!\nUse `/auction sell` to list something.", parse_mode="Markdown"); return

        lines = ["🏷️ *ACTIVE AUCTIONS*\n━━━━━━━━━━━━━"]
        for aid, a in list(active.items())[:10]:
            exp     = datetime.fromisoformat(a["expires_at"])
            rem     = exp - datetime.now()
            mins    = int(rem.total_seconds() // 60)
            seller  = a.get("seller_name", "?")
            top_bid = a.get("top_bid", a["start_bid"])
            top_who = a.get("top_bidder_name", "No bids yet")
            short_id = aid.split("_")[-1][-6:]
            lines.append(
                f"🔹 *{a['item_name']}* _{a['item_type']}_\n"
                f"   Seller: {seller} | Start: {a['start_bid']} 🪙\n"
                f"   Top bid: *{top_bid} 🪙* by {top_who}\n"
                f"   ⏱️ {mins}m left | ID: `{short_id}`"
            )
        lines.append("\nUse `/auction bid <ID> <amount>` to bid!")
        await update.message.reply_text("\n".join(lines), parse_mode="Markdown"); return

    # ── SELL ──────────────────────────────────────────────────────────────────
    if sub == "sell":
        if len(context.args) < 4:
            await update.message.reply_text(
                "Usage:\n`/auction sell animal Dragon 200`\n`/auction sell weapon bow 100`",
                parse_mode="Markdown"); return

        item_type  = context.args[1].lower()
        try:
            start_bid = int(context.args[-1])
        except:
            await update.message.reply_text("❌ Last argument must be the starting bid number."); return

        item_name_raw = " ".join(context.args[2:-1]).strip()
        u = get_user(data, user.id, user.username, user.full_name)

        if item_type == "animal":
            zoo     = u.get("animals", [])
            matched = next((z for z in zoo if item_name_raw.lower() in z["name"].lower()), None)
            if not matched:
                await update.message.reply_text(f"❌ '{item_name_raw}' not in your zoo!"); return
            display_name = matched["name"]
            # Reserve it (remove from zoo, restore if no bid or outbid)
            if matched.get("count", 1) > 1:
                matched["count"] -= 1
            else:
                zoo.remove(matched)
            u["animals"] = zoo

        elif item_type == "weapon":
            w_key = next((k for k in WEAPONS if item_name_raw.lower() in WEAPONS[k]["name"].lower()), None)
            if not w_key or u.get("weapon") != w_key:
                await update.message.reply_text(f"❌ You don't own '{item_name_raw}' as your equipped weapon!"); return
            if w_key == "stick":
                await update.message.reply_text("❌ Can't auction the default stick!"); return
            display_name = WEAPONS[w_key]["name"]
            u["weapon"]  = "stick"   # equip stick while weapon is listed

        else:
            await update.message.reply_text("❌ Type must be `animal` or `weapon`.", parse_mode="Markdown"); return

        expires_at = (datetime.now() + timedelta(hours=1)).isoformat()
        auction_id = f"auc_{user.id}_{int(datetime.now().timestamp())}"
        sname      = f"@{user.username}" if user.username else user.full_name

        data["auctions"][auction_id] = {
            "seller_id":         user.id,
            "seller_name":       sname,
            "item_type":         item_type,
            "item_name":         display_name if item_type == "animal" else w_key,
            "item_display":      display_name,
            "start_bid":         start_bid,
            "top_bid":           start_bid,
            "top_bidder_id":     None,
            "top_bidder_name":   None,
            "status":            "open",
            "expires_at":        expires_at,
            "chat_id":           chat_id,
        }
        save_data(data)

        short_id = auction_id.split("_")[-1][-6:]
        await update.message.reply_text(
            f"🏷️ *Auction Listed!*\n━━━━━━━━━━━━━\n"
            f"Item: *{display_name}*\n"
            f"Starting bid: *{start_bid} 🪙*\n"
            f"⏱️ Ends in 1 hour\n"
            f"ID: `{short_id}`\n\n"
            f"Others can bid with `/auction bid {short_id} <amount>`",
            parse_mode="Markdown")

        # Schedule auction end
        context.job_queue.run_once(
            lambda ctx: asyncio.ensure_future(_close_auction(ctx, auction_id)),
            when=3600,
            name=f"auction_{auction_id}"
        )
        return

    # ── BID ───────────────────────────────────────────────────────────────────
    if sub == "bid":
        if len(context.args) < 3:
            await update.message.reply_text("Usage: `/auction bid <id> <amount>`", parse_mode="Markdown"); return

        short_id = context.args[1]
        try:
            bid_amount = int(context.args[2])
        except:
            await update.message.reply_text("❌ Bid amount must be a number."); return

        # Find auction by short ID
        full_id = next((aid for aid in data.get("auctions", {})
                        if aid.endswith(short_id)), None)
        if not full_id:
            await update.message.reply_text("❌ Auction not found! Check the ID from `/auction list`.", parse_mode="Markdown"); return

        auction = data["auctions"][full_id]

        if auction["status"] != "open":
            await update.message.reply_text("❌ This auction is closed!"); return
        if datetime.fromisoformat(auction["expires_at"]) < datetime.now():
            await update.message.reply_text("❌ This auction has expired!"); return
        if auction["seller_id"] == user.id:
            await update.message.reply_text("❌ You can't bid on your own auction!"); return
        if bid_amount <= auction["top_bid"]:
            await update.message.reply_text(
                f"❌ Bid must be higher than current top bid of *{auction['top_bid']} 🪙*!",
                parse_mode="Markdown"); return

        u = get_user(data, user.id, user.username, user.full_name)
        if u.get("coins", 0) < bid_amount:
            await update.message.reply_text(f"❌ Not enough coins! Have {u['coins']} 🪙"); return

        bname = f"@{user.username}" if user.username else user.full_name
        auction["top_bid"]          = bid_amount
        auction["top_bidder_id"]    = user.id
        auction["top_bidder_name"]  = bname
        save_data(data)

        await update.message.reply_text(
            f"✅ *Bid placed!*\n"
            f"Item: *{auction['item_display']}*\n"
            f"Your bid: *{bid_amount} 🪙*\n"
            f"_{bname} is now the top bidder!_",
            parse_mode="Markdown")

        # Notify group
        try:
            await context.bot.send_message(
                chat_id,
                f"🏷️ *New bid on {auction['item_display']}!*\n"
                f"{bname} bid *{bid_amount} 🪙*",
                parse_mode="Markdown")
        except:
            pass
        return

    await update.message.reply_text("Unknown subcommand. Use `/auction list`, `/auction sell`, or `/auction bid`.", parse_mode="Markdown")


async def _close_auction(context, auction_id):
    """Called after 1 hour to close auction and transfer item."""
    data    = load_data()
    auctions = data.get("auctions", {})

    if auction_id not in auctions:
        return

    auction = auctions[auction_id]
    if auction["status"] != "open":
        return

    auction["status"] = "closed"
    chat_id = auction.get("chat_id")

    seller_id  = auction["seller_id"]
    winner_id  = auction.get("top_bidder_id")
    su         = get_user(data, seller_id)
    item_display = auction["item_display"]

    if not winner_id:
        # No bids — return item to seller
        if auction["item_type"] == "animal":
            zoo = su.get("animals", [])
            found = next((z for z in zoo if z["name"] == auction["item_name"]), None)
            if found:
                found["count"] = found.get("count", 1) + 1
            else:
                a_data = find_animal_data(auction["item_name"])
                zoo.append({"name": auction["item_name"],
                            "rarity": a_data["rarity"] if a_data else "common", "count": 1})
            su["animals"] = zoo
        else:
            su["weapon"] = auction["item_name"]
        save_data(data)
        try:
            await context.bot.send_message(chat_id,
                f"🏷️ *Auction ended — no bids!*\n"
                f"*{item_display}* returned to {auction['seller_name']}.",
                parse_mode="Markdown")
        except:
            pass
        return

    # Has a winner
    wu  = get_user(data, winner_id)
    bid = auction["top_bid"]

    if wu.get("coins", 0) < bid:
        # Winner can't pay — return item to seller
        if auction["item_type"] == "animal":
            zoo = su.get("animals", [])
            zoo.append({"name": auction["item_name"], "rarity": "common", "count": 1})
            su["animals"] = zoo
        else:
            su["weapon"] = auction["item_name"]
        save_data(data)
        try:
            await context.bot.send_message(chat_id,
                f"🏷️ *Auction failed!* Winner couldn't pay.\n"
                f"*{item_display}* returned to {auction['seller_name']}.",
                parse_mode="Markdown")
        except:
            pass
        return

    # Transfer: deduct coins from winner, give to seller
    wu["coins"] = wu.get("coins", 0) - bid
    su["coins"] = su.get("coins", 0) + bid
    su["total_coins_ever"] = su.get("total_coins_ever", 0) + bid

    # Transfer item to winner
    if auction["item_type"] == "animal":
        t_zoo  = wu.get("animals", [])
        found  = next((z for z in t_zoo if z["name"] == auction["item_name"]), None)
        if found:
            found["count"] = found.get("count", 1) + 1
        else:
            a_data = find_animal_data(auction["item_name"])
            t_zoo.append({"name": auction["item_name"],
                          "rarity": a_data["rarity"] if a_data else "common", "count": 1})
        wu["animals"] = t_zoo
    else:
        wu["weapon"] = auction["item_name"]

    save_data(data)

    wname = auction.get("top_bidder_name", "?")
    sname = auction.get("seller_name", "?")
    try:
        await context.bot.send_message(chat_id,
            f"🏷️ *Auction Closed!*\n━━━━━━━━━━━━━\n"
            f"Item: *{item_display}*\n"
            f"🏆 Winner: *{wname}* with *{bid} 🪙*\n"
            f"💰 {sname} received *{bid} coins*!",
            parse_mode="Markdown")
    except:
        pass


# ══════════════════════════════════════════════════════════════════════════════
#  /pray — increase gambling luck for 10 minutes
# ══════════════════════════════════════════════════════════════════════════════
async def cmd_pray(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    data = load_data()
    u    = get_user(data, user.id, user.username, user.full_name)

    # Check cooldown — can pray once every 30 minutes
    last_pray = u.get("last_pray")
    if last_pray:
        elapsed = (datetime.now() - datetime.fromisoformat(last_pray)).total_seconds()
        if elapsed < 1800:
            remaining = int(1800 - elapsed)
            await update.message.reply_text(
                f"🙏 You already prayed recently!\nNext prayer in *{remaining//60}m {remaining%60}s*.",
                parse_mode="Markdown"); return

    # Set pray buff — lasts 10 minutes
    u["pray_active"]  = True
    u["pray_expires"] = (datetime.now() + timedelta(minutes=10)).isoformat()
    u["last_pray"]    = datetime.now().isoformat()
    save_data(data)

    name = f"@{user.username}" if user.username else user.full_name
    PRAY_MSGS = [
        "🙏 The gods hear your prayer...\nLuck is on your side for the next 10 minutes! +15% win chance on all bets.",
        "✨ A divine blessing descends!\nYour gambling odds improved for 10 minutes!",
        "🌟 The universe aligns in your favour!\n10 minutes of boosted luck activated.",
        "🕊️ Your prayer echoes through the cosmos...\nForge gods grant you luck for 10 minutes!",
    ]
    await update.message.reply_text(
        f"{random.choice(PRAY_MSGS)}\n\n"
        f"_{name}'s next 10 minutes of gambling has +15% win boost!_",
        parse_mode="Markdown")


def has_pray_buff(user):
    """Returns True if user has active pray buff."""
    exp = user.get("pray_expires")
    if exp and user.get("pray_active"):
        if datetime.fromisoformat(exp) > datetime.now():
            return True
        else:
            user["pray_active"] = False
    return False
# ══════════════════════════════════════════════════════════════════════════════
#  CORE COMMANDS
# ══════════════════════════════════════════════════════════════════════════════
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 I'm *Aira* – your ultimate Telegram bot!\n\n"
        "🎮 Challenges | 🐾 OWO Hunt | 🎰 Casino\n"
        "😴 AFK System | 🛡️ Admin Tools | 🤖 AI Chat\n"
        "📅 Daily Rewards | 🤝 Trade | 🍅 Pomodoro\n\n"
        "*/help* – Full command list ⚡",parse_mode="Markdown")

async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 *Aira – Command List*\n━━━━━━━━━━━━━\n"
        "*🎮 Challenges*\n"
        "/challenge – Start challenge (5m cooldown)\n"
        "/hint – Hint for active challenge\n"
        "/skipit – Skip challenge (admin free)\n\n"
        "*💰 Economy*\n"
        "/wallet – Coins, gems, wins, streak\n"
        "/daily – Daily reward (streak bonus!)\n"
        "/give – Reply + /give <amount>\n"
        "/leaderboard – Global/Weekly/Today tabs\n"
        "/streak – Win streak\n"
        "/shop – Buy perks\n"
        "/settitle – Set member tag (after purchase)\n"
        "/pinit – Pin msg (reply, after purchase)\n\n"
        "*🐾 OWO*\n"
        "/hunt – Catch an animal\n"
        "/zoo – Your animal collection\n"
        "/sell all | sell <name> – Sell animals for coins+gems\n"
        "/gemshop – Buy weapons with gems\n"
        "/owoprofile – OWO stats\n"
        "/autohunt – Toggle auto hunting\n"
        "/battle – Fight wild animal\n"
        "/topanimals – Global zoo leaderboard\n\n"
        "*🎰 Casino*\n"
        "/cf <amount> heads/tails – Coin flip\n"
        "/s <amount> – Slot machine\n"
        "/dice <amount> <1-6> – Dice ×3 if correct\n\n"
        "*🤝 Social*\n"
        "/trade – Reply + /trade <amount>\n"
        "/ask <question> – Ask Aira AI\n"
        "/pomodoro <mins> – Focus timer + coins\n"
        "!status <reason> – Set AFK status\n\n"
        "*🏆 Stats*\n"
        "/badges – Badge collection\n"
        "/stats – Full stats\n\n"
        "*🛡️ Admin*\n"
        "/ban /unban /kick – Manage members\n"
        "/timeout @user <mins> – Mute\n"
        "/untimeout – Unmute (reply to user)\n"
        "/purge <n> – Delete last n msgs\n"
        "/warn /warns /clearwarns\n"
        "/setwelcome <msg> – Custom welcome\n"
        "/setbye <msg> – Custom bye message\n"
        "/forgewar – 2× rewards 1hr",parse_mode="Markdown")

async def cmd_challenge(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id=update.message.chat_id; data=load_data(); group=get_group(data,chat_id)
    if group["active_challenge"]:
        await update.message.reply_text("⚠️ A challenge is already running!"); return
    last=group.get("last_challenge_time")
    if last:
        elapsed=(datetime.now()-datetime.fromisoformat(last)).total_seconds()
        if elapsed<CHALLENGE_COOLDOWN:
            await update.message.reply_text(f"⏳ Cooldown! Next in *{int(CHALLENGE_COOLDOWN-elapsed)}s*.",parse_mode="Markdown"); return
    save_data(data); await post_challenge(context,chat_id)

async def cmd_wallet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user=update.message.from_user; data=load_data()
    u=get_user(data,user.id,user.username,user.full_name); save_data(data)
    tag_line=f"\n👑 Tag: *{u['title']}*" if u.get("title") else ""
    exp_line=""
    if u.get("title_expiry"):
        rem=datetime.fromisoformat(u["title_expiry"])-datetime.now()
        if rem.total_seconds()>0:
            h,m=int(rem.total_seconds()//3600),int((rem.total_seconds()%3600)//60)
            exp_line=f"\n⏳ Tag expires: *{h}h {m}m*"
    afk_line=f"\n😴 AFK: _{u.get('afk')}_" if u.get("afk") else ""
    weapon=WEAPONS.get(u.get("weapon","stick"),WEAPONS["stick"])
    await update.message.reply_text(
        f"💼 *{user.full_name}'s Wallet*{tag_line}{exp_line}{afk_line}\n"
        f"━━━━━━━━━━━━━\n"
        f"🪙 Coins: *{u['coins']}* | 💎 Gems: *{u.get('gems',0)}*\n"
        f"🐾 OWO: *{u.get('owo',0)}* | 🏹 Weapon: {weapon['name']}\n"
        f"🏆 Wins: *{u['wins']}* | 📅 Weekly: *{u.get('weekly_wins',0)}*\n"
        f"🔥 Streak: *{u['streak']}* | ⭐ Best: *{u.get('best_streak',0)}*\n"
        f"⬆️ Level: *{u.get('level',1)}* | XP: *{u.get('xp',0)}*\n"
        f"🛡️ Shield: {'✅' if has_shield(u) else 'None'} | "
        f"📌 Pin: {'✅' if u.get('pin_token') else 'None'}\n"
        f"🏅 Badges: *{len(u['badges'])}*",parse_mode="Markdown")

async def cmd_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user=update.message.from_user; data=load_data()
    u=get_user(data,user.id,user.username,user.full_name); save_data(data)
    zoo_count=sum(z.get("count",1) for z in u.get("animals",[]))
    await update.message.reply_text(
        f"📊 *{user.full_name}'s Stats*\n━━━━━━━━━━━━━\n"
        f"🪙 Coins: *{u['coins']}* | 💎 Gems: *{u.get('gems',0)}*\n"
        f"💎 Total Earned: *{u.get('total_coins_ever',0)}*\n"
        f"🏆 Wins: *{u['wins']}* | 📅 Weekly: *{u.get('weekly_wins',0)}*\n"
        f"🔥 Best Streak: *{u.get('best_streak',0)}*\n"
        f"⬆️ Level: *{u.get('level',1)}* (XP: {u.get('xp',0)})\n"
        f"🐾 OWO: *{u.get('owo',0)}* | 🎯 Hunts: *{u.get('hunts',0)}*\n"
        f"🦁 Animals: *{zoo_count}* | 🎰 Casino Wins: *{u.get('casino_wins',0)}*\n"
        f"📅 Daily Streak: *{u.get('daily_streak',0)}* days\n"
        f"🏅 Badges: *{len(u['badges'])}*",parse_mode="Markdown")

async def cmd_leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data=load_data(); reset_weekly(data)
    today_str=datetime.now().date().isoformat()
    for u in data["users"].values():
        if u.get("today_date")!=today_str: u["today_date"]=today_str;u["today_wins"]=0
    if not data["users"]: await update.message.reply_text("No players yet!"); return
    medals=["🥇","🥈","🥉","4️⃣","5️⃣","6️⃣","7️⃣","8️⃣","9️⃣","🔟"]
    def board(title,items):
        lines=[f"{title}\n━━━━━━━━━━━━━"]
        for i,(name,tag,c,w) in enumerate(items[:10]):
            t=f" 👑{tag}" if tag else ""
            lines.append(f"{medals[i]} {name}{t}\n   🪙{c} | 🏆{w}W")
        return "\n".join(lines)
    all_u=list(data["users"].items())
    context.bot_data["lb_global"]=board("🌍 *GLOBAL* (All-time coins)",
        [(u.get("full_name","?"),u.get("title"),u.get("total_coins_ever",0),u.get("wins",0))
         for _,u in sorted(all_u,key=lambda x:x[1].get("total_coins_ever",0),reverse=True)])
    context.bot_data["lb_weekly"]=board("📅 *WEEKLY*",
        [(u.get("full_name","?"),u.get("title"),u.get("coins",0),u.get("weekly_wins",0))
         for _,u in sorted(all_u,key=lambda x:x[1].get("weekly_wins",0),reverse=True)])
    context.bot_data["lb_today"]=board("🕐 *TODAY*",
        [(u.get("full_name","?"),u.get("title"),u.get("coins",0),u.get("today_wins",0))
         for _,u in sorted(all_u,key=lambda x:x[1].get("today_wins",0),reverse=True)])
    context.bot_data["lb_owo"]=board("🐾 *OWO HUNTERS*",
        [(u.get("full_name","?"),u.get("title"),u.get("owo",0),u.get("hunts",0))
         for _,u in sorted(all_u,key=lambda x:x[1].get("owo",0),reverse=True)])
    kb=[[InlineKeyboardButton("🌍 Global",callback_data="lb_global"),
         InlineKeyboardButton("📅 Weekly",callback_data="lb_weekly")],
        [InlineKeyboardButton("🕐 Today",callback_data="lb_today"),
         InlineKeyboardButton("🐾 OWO",callback_data="lb_owo")]]
    await update.message.reply_text("🏆 *LEADERBOARD* — Choose a view:",
        reply_markup=InlineKeyboardMarkup(kb),parse_mode="Markdown")

async def handle_leaderboard_tab(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query=update.callback_query; await query.answer()
    text=context.bot_data.get(query.data,"No data yet!")
    kb=[[InlineKeyboardButton("🌍 Global",callback_data="lb_global"),
         InlineKeyboardButton("📅 Weekly",callback_data="lb_weekly")],
        [InlineKeyboardButton("🕐 Today",callback_data="lb_today"),
         InlineKeyboardButton("🐾 OWO",callback_data="lb_owo")]]
    await query.edit_message_text(text,reply_markup=InlineKeyboardMarkup(kb),parse_mode="Markdown")

async def cmd_streak(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user=update.message.from_user; data=load_data()
    u=get_user(data,user.id,user.username,user.full_name); save_data(data)
    fire="🔥"*min(u["streak"],10)
    await update.message.reply_text(
        f"{fire}\n*{user.full_name}'s Streak*\n━━━━━━━━━━━━━\n"
        f"Current: *{u['streak']}* | Best: *{u.get('best_streak',0)}*\n"
        f"Bonus/win: *+{u['streak']*STREAK_BONUS}* coins",parse_mode="Markdown")

async def cmd_badges(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user=update.message.from_user; data=load_data()
    u=get_user(data,user.id,user.username,user.full_name); save_data(data)
    if not u["badges"]: await update.message.reply_text("No badges yet! Win challenges and hunt! 🏅"); return
    lines=[f"🏅 *{user.full_name}'s Badges*\n━━━━━━━━━━━━━"]
    for k in u["badges"]:
        if k in BADGES: n,d=BADGES[k]; lines.append(f"{n}\n  _{d}_")
    lines.append(f"\n🔒 *{len([k for k in BADGES if k not in u['badges']])} locked*")
    await update.message.reply_text("\n".join(lines),parse_mode="Markdown")

async def cmd_hint(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id=update.message.chat_id; data=load_data()
    ch=get_group(data,chat_id).get("active_challenge")
    if not ch: await update.message.reply_text("No active challenge!"); return
    await update.message.reply_text(f"💡 *Hint:* _{ch['hint']}_",parse_mode="Markdown")

async def cmd_shop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user=update.message.from_user; data=load_data()
    u=get_user(data,user.id,user.username,user.full_name); save_data(data)
    kb=[[InlineKeyboardButton(f"{v['name']} – {v['cost']} 🪙",callback_data=f"buy_{k}")]
        for k,v in SHOP_ITEMS.items()]
    await update.message.reply_text(f"🛒 *FORGE SHOP*\n━━━━━━━━━━━━━\nBalance: *{u['coins']}* 🪙\n\nTap to buy:",
        reply_markup=InlineKeyboardMarkup(kb),parse_mode="Markdown")

async def handle_shop_purchase(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query=update.callback_query; await query.answer()
    user=query.from_user; key=query.data.replace("buy_","")
    if key not in SHOP_ITEMS: await query.edit_message_text("❌ Unknown item."); return
    data=load_data(); u=get_user(data,user.id,user.username,user.full_name); item=SHOP_ITEMS[key]
    if u["coins"]<item["cost"]:
        await query.edit_message_text(f"❌ Need *{item['cost']}* 🪙 but have *{u['coins']}*.",parse_mode="Markdown"); return
    u["coins"]-=item["cost"]; award_badge(u,"spender")
    msg=f"✅ *{item['name']}*\n_{item['desc']}_\n\n💰 Remaining: *{u['coins']}* 🪙"
    if key=="double_coins": u["double_coins"]=True; msg+="\n\n⚡ Next win = DOUBLE coins!"
    elif key=="hint_reveal":
        ch=get_group(data,query.message.chat_id).get("active_challenge")
        msg+=f"\n\n💡 *Hint:* _{ch['hint']}_" if ch else "\n\n⚠️ No active challenge."
    elif key=="custom_title": u["title_purchased"]=True;u["title_chat_id"]=query.message.chat_id;msg+="\n\n👑 Use `/settitle YourTitle` in group!"
    elif key=="choose_challenge":
        g=get_group(data,query.message.chat_id);g["pending_chooser"]=user.username or user.full_name;msg+="\n\n🎯 Next /challenge is your pick!"
    elif key=="pin_message": u["pin_token"]=True;msg+="\n\n📌 Reply to msg + /pinit!"
    elif key=="skip_challenge":
        cid=query.message.chat_id;g=get_group(data,cid)
        if g.get("active_challenge"):
            g["active_challenge"]=None
            for job in context.job_queue.get_jobs_by_name(f"expire_{cid}"): job.schedule_removal()
            save_data(data); await query.edit_message_text(f"✅ Skipped! Starting new...\nCoins: *{u['coins']}* 🪙",parse_mode="Markdown")
            await post_challenge(context,cid); return
        else: u["coins"]+=item["cost"];msg="⚠️ No active challenge. Refunded!"
    elif key=="shield": u["shield_expiry"]=(datetime.now()+timedelta(hours=1)).isoformat();msg+="\n\n🛡️ Protected from /timeout for 1h!"
    elif key=="owo_boost": u["owo_boost_expiry"]=(datetime.now()+timedelta(hours=1)).isoformat();msg+="\n\n🐾 Double hunt rewards for 1h!"
    save_data(data); await query.edit_message_text(msg,parse_mode="Markdown")

async def cmd_settitle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user=update.message.from_user; chat_id=update.message.chat_id
    if not context.args: await update.message.reply_text("Usage: `/settitle Title` (max 16 chars)",parse_mode="Markdown"); return
    title=" ".join(context.args)[:16]; data=load_data()
    u=get_user(data,user.id,user.username,user.full_name)
    if not u.get("title_purchased"): await update.message.reply_text("❌ Buy *Custom Member Tag* from /shop first!",parse_mode="Markdown"); return
    for job in context.job_queue.get_jobs_by_name(f"title_expire_{user.id}"): job.schedule_removal()
    success,mode=await set_member_tag(context.bot,chat_id,user.id,title)
    if not success:
        u["title_purchased"]=False; save_data(data)
        await update.message.reply_text("❌ *Failed to set tag.*\nMake sure Aira is admin with *'Add New Admins'* permission.\nPurchase *refunded*!",parse_mode="Markdown"); return
    exp=datetime.now()+timedelta(hours=TITLE_HOURS)
    u["title"]=title;u["title_expiry"]=exp.isoformat();u["title_chat_id"]=chat_id;u["title_purchased"]=False
    save_data(data)
    context.job_queue.run_once(expire_title_job,when=TITLE_HOURS*3600,name=f"title_expire_{user.id}",
        data={"user_id":user.id,"chat_id":chat_id,"name":f"@{user.username}" if user.username else user.full_name})
    name=f"@{user.username}" if user.username else user.full_name
    await update.message.reply_text(f"👑 *{name}* now has tag: *{title}* for 24h!",parse_mode="Markdown")

async def cmd_pinit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user=update.message.from_user; chat_id=update.message.chat_id
    data=load_data(); u=get_user(data,user.id,user.username,user.full_name)
    member=await context.bot.get_chat_member(chat_id,user.id)
    is_adm=member.status in ("administrator","creator")
    if not is_adm and not u.get("pin_token"):
        await update.message.reply_text("❌ Buy *Pin a Message* from /shop first!",parse_mode="Markdown"); return
    if not update.message.reply_to_message: await update.message.reply_text("↩️ Reply to a message first, then /pinit"); return
    try:
        await context.bot.pin_chat_message(chat_id,update.message.reply_to_message.message_id)
        if not is_adm: u["pin_token"]=False;save_data(data)
        name=f"@{user.username}" if user.username else user.full_name
        await update.message.reply_text(f"📌 *{name}* pinned a message!",parse_mode="Markdown")
    except TelegramError as e:
        await update.message.reply_text(f"❌ Make sure Aira has *Pin Messages* permission!\n_{e}_",parse_mode="Markdown")

async def cmd_skipit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id=update.message.chat_id; data=load_data(); group=get_group(data,chat_id)
    member=await context.bot.get_chat_member(chat_id,update.message.from_user.id)
    if member.status not in ("administrator","creator"): await update.message.reply_text("⚠️ Admins only!"); return
    if not group.get("active_challenge"): await update.message.reply_text("No challenge to skip!"); return
    group["active_challenge"]=None
    for job in context.job_queue.get_jobs_by_name(f"expire_{chat_id}"): job.schedule_removal()
    save_data(data); await update.message.reply_text("⏭️ Skipped! Starting new challenge...")
    await post_challenge(context,chat_id)

async def cmd_daily(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user=update.message.from_user; data=load_data()
    u=get_user(data,user.id,user.username,user.full_name)
    now=datetime.now(); today=now.date().isoformat(); yest=(now.date()-timedelta(days=1)).isoformat()
    last=u.get("daily_claimed")
    if last==today:
        next_c=datetime.combine(now.date()+timedelta(days=1),datetime.min.time())
        rem=next_c-now; h,m=int(rem.total_seconds()//3600),int((rem.total_seconds()%3600)//60)
        await update.message.reply_text(f"⏳ Already claimed! Next in *{h}h {m}m* ⏰",parse_mode="Markdown"); return
    ds=u.get("daily_streak",0)
    ds = ds+1 if last==yest else 1
    u["daily_streak"]=ds; u["daily_claimed"]=today
    tier_idx=min(ds-1,len(DAILY_TIERS)-1); reward,label=DAILY_TIERS[tier_idx]
    bonus=0
    if ds%7==0: bonus=100; label+=" + 🎁 7-day bonus!"
    total=reward+bonus; u["coins"]+=total; u["total_coins_ever"]=u.get("total_coins_ever",0)+total
    badges=check_badges(u); save_data(data)
    fire="🔥"*min(ds,7)
    bl="\n🆕 "+" | ".join(badges) if badges else ""
    await update.message.reply_text(
        f"🎁 *Daily Reward!*\n━━━━━━━━━━━━━\n{fire} Streak: *{ds} days*\n"
        f"💰 +*{total}* coins _{label}_{bl}\n🏦 Balance: *{u['coins']}*\n_Come back tomorrow!_",parse_mode="Markdown")

async def cmd_give(update: Update, context: ContextTypes.DEFAULT_TYPE):
    sender=update.message.from_user
    if not update.message.reply_to_message:
        await update.message.reply_text("↩️ Reply to someone + `/give <amount>`",parse_mode="Markdown"); return
    if not context.args: await update.message.reply_text("Usage: Reply + `/give <amount>`",parse_mode="Markdown"); return
    try: amount=int(context.args[0])
    except: await update.message.reply_text("❌ Number only."); return
    if amount<=0 or amount>10000: await update.message.reply_text("❌ 1–10000 only."); return
    target=update.message.reply_to_message.from_user
    if target.id==sender.id: await update.message.reply_text("❌ Can't give to yourself!"); return
    if target.is_bot: await update.message.reply_text("❌ Can't give to bots!"); return
    data=load_data(); s=get_user(data,sender.id,sender.username,sender.full_name)
    if s["coins"]<amount: await update.message.reply_text(f"❌ Need {amount} but have {s['coins']} 🪙"); return
    t=get_user(data,target.id,target.username,target.full_name)
    s["coins"]-=amount; t["coins"]+=amount; t["total_coins_ever"]=t.get("total_coins_ever",0)+amount
    save_data(data)
    sname=f"@{sender.username}" if sender.username else sender.full_name
    tname=f"@{target.username}" if target.username else target.full_name
    await update.message.reply_text(
        f"🎁 *{sname}* gave *{amount}* 🪙 to *{tname}*!\n"
        f"{sname}: *{s['coins']}* | {tname}: *{t['coins']}*",parse_mode="Markdown")

async def cmd_hunt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user=update.message.from_user
    result=await do_hunt(context.bot,update.message.chat_id,user.id,user.username,user.full_name)
    await update.message.reply_text(result,parse_mode="Markdown")

async def cmd_zoo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user=update.message.from_user; data=load_data()
    u=get_user(data,user.id,user.username,user.full_name); save_data(data)
    zoo=u.get("animals",[])
    if not zoo: await update.message.reply_text("Zoo empty! Use /hunt to catch animals. 🎯"); return
    lines=[f"🦁 *{user.full_name}'s Zoo*\n━━━━━━━━━━━━━"]
    order=list(RARITY_WEIGHTS.keys())
    for a in sorted(zoo,key=lambda x:order.index(x["rarity"]) if x["rarity"] in order else 99,reverse=True):
        icon=RARITY_COLORS.get(a["rarity"],"⬜")
        lines.append(f"{a['name']} {icon}*{a['rarity']}* ×{a.get('count',1)}")
    lines.append(f"\n🐾 OWO: *{u.get('owo',0)}* | 💎 Gems: *{u.get('gems',0)}*")
    await update.message.reply_text("\n".join(lines),parse_mode="Markdown")

async def cmd_owoprofile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user=update.message.from_user; data=load_data()
    u=get_user(data,user.id,user.username,user.full_name); save_data(data)
    zoo=u.get("animals",[]); total=sum(z.get("count",1) for z in zoo)
    legends=sum(z.get("count",1) for z in zoo if z.get("rarity")=="legendary")
    boost="⚡ Active" if (u.get("owo_boost_expiry") and datetime.fromisoformat(u["owo_boost_expiry"])>datetime.now()) else "None"
    weapon=WEAPONS.get(u.get("weapon","stick"),WEAPONS["stick"])
    cd=u.get("hunt_cooldown")
    cd_line=""
    if cd:
        rem=(datetime.fromisoformat(cd)-datetime.now()).total_seconds()
        if rem>0: cd_line=f"\n⏳ Cooldown: *{int(rem)}s*"
    await update.message.reply_text(
        f"🐾 *{user.full_name}'s OWO Profile*\n━━━━━━━━━━━━━\n"
        f"🐾 OWO: *{u.get('owo',0)}* | 💎 Gems: *{u.get('gems',0)}*\n"
        f"🎯 Hunts: *{u.get('hunts',0)}* | 🦁 Animals: *{total}*\n"
        f"🐉 Legendary: *{legends}* | 🏹 Weapon: {weapon['name']}\n"
        f"⚡ Boost: {boost}{cd_line}\n"
        f"🤖 Auto: {'✅' if u.get('auto_hunt') else '❌'}",parse_mode="Markdown")

# ── Auto Hunt config ──────────────────────────────────────────────────────────
AUTOHUNT_COST     = 10    # coins per auto-hunt attempt
AUTOHUNT_DURATION = 3600 # 1 hour session in seconds
AUTOHUNT_INTERVAL = 60   # hunt every 60 seconds

async def cmd_autohunt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    data = load_data()
    u    = get_user(data, user.id, user.username, user.full_name)

    # If auto hunt is currently ON, turn it OFF
    if u.get("auto_hunt"):
        u["auto_hunt"]         = False
        u["auto_hunt_expiry"]  = None
        save_data(data)
        for job in context.job_queue.get_jobs_by_name(f"autohunt_{user.id}"):
            job.schedule_removal()
        for job in context.job_queue.get_jobs_by_name(f"autohunt_expire_{user.id}"):
            job.schedule_removal()
        await update.message.reply_text("🤖 Auto Hunt *OFF*. Session ended early.", parse_mode="Markdown")
        return

    # Check if they have enough coins to start (minimum 10 hunts worth)
    min_coins = AUTOHUNT_COST * 10
    if u.get("coins", 0) < min_coins:
        await update.message.reply_text(
            f"❌ Need at least *{min_coins}* 🪙 to start Auto Hunt.\n"
            f"Each auto-hunt costs *{AUTOHUNT_COST}* 🪙 per attempt.\n"
            f"You have: *{u.get('coins', 0)}* 🪙",
            parse_mode="Markdown"
        )
        return

    # Turn ON
    expiry = (datetime.now() + timedelta(seconds=AUTOHUNT_DURATION)).isoformat()
    u["auto_hunt"]        = True
    u["auto_hunt_expiry"] = expiry
    save_data(data)

    chat_id = update.message.chat_id

    # Repeating job — hunts every 60s
    context.job_queue.run_repeating(
        lambda ctx: asyncio.ensure_future(auto_hunt_job(ctx, chat_id, user.id)),
        interval=AUTOHUNT_INTERVAL,
        first=5,
        name=f"autohunt_{user.id}",
        chat_id=chat_id
    )

    # Expiry job — stops auto hunt after 1 hour
    context.job_queue.run_once(
        lambda ctx: asyncio.ensure_future(auto_hunt_expire(ctx, chat_id, user.id)),
        when=AUTOHUNT_DURATION,
        name=f"autohunt_expire_{user.id}",
        chat_id=chat_id
    )

    await update.message.reply_text(
        f"🤖 *Auto Hunt ON!*\n"
        f"━━━━━━━━━━━━━\n"
        f"⏱️ Session: *1 hour*\n"
        f"💸 Cost: *{AUTOHUNT_COST} 🪙* per hunt attempt\n"
        f"🔁 Hunts every *{AUTOHUNT_INTERVAL}s*\n\n"
        f"_Aira will post results here. Use /autohunt again to stop early._\n"
        f"_Session auto-stops after 1 hour — type /autohunt to renew!_",
        parse_mode="Markdown"
    )


async def auto_hunt_job(context, chat_id, user_id):
    data = load_data()
    u    = get_user(data, user_id)

    # Stop if auto_hunt was turned off or expired
    if not u.get("auto_hunt"):
        for job in context.job_queue.get_jobs_by_name(f"autohunt_{user_id}"):
            job.schedule_removal()
        return

    # Check expiry
    expiry = u.get("auto_hunt_expiry")
    if expiry and datetime.fromisoformat(expiry) < datetime.now():
        return  # expire job will handle the message

    # Deduct cost before hunting
    if u.get("coins", 0) < AUTOHUNT_COST:
        # Out of coins — stop auto hunt
        u["auto_hunt"]        = False
        u["auto_hunt_expiry"] = None
        save_data(data)
        for job in context.job_queue.get_jobs_by_name(f"autohunt_{user_id}"):
            job.schedule_removal()
        for job in context.job_queue.get_jobs_by_name(f"autohunt_expire_{user_id}"):
            job.schedule_removal()
        try:
            await context.bot.send_message(
                chat_id,
                f"🤖 *Auto Hunt stopped!*\nNot enough coins to continue.\n"
                f"_(Need {AUTOHUNT_COST} 🪙 per hunt)_\n"
                f"Recharge and use /autohunt to start a new session!",
                parse_mode="Markdown"
            )
        except TelegramError:
            pass
        return

    u["coins"] -= AUTOHUNT_COST
    save_data(data)

    result = await do_hunt(context.bot, chat_id, user_id, u.get("username"), u.get("full_name"))
    try:
        await context.bot.send_message(chat_id, f"🤖 *Auto:* {result}", parse_mode="Markdown")
    except TelegramError:
        pass


async def auto_hunt_expire(context, chat_id, user_id):
    """Called after 1 hour — stops auto hunt and asks user to renew."""
    data = load_data()
    u    = get_user(data, user_id)
    u["auto_hunt"]        = False
    u["auto_hunt_expiry"] = None
    save_data(data)
    for job in context.job_queue.get_jobs_by_name(f"autohunt_{user_id}"):
        job.schedule_removal()
    username = u.get("username")
    name     = f"@{username}" if username and username != "Unknown" else u.get("full_name", "Hunter")
    try:
        await context.bot.send_message(
            chat_id,
            f"⌛ *{name}'s Auto Hunt session ended!*\n"
            f"1 hour is up. Type /autohunt to start a new session! 🎯",
            parse_mode="Markdown"
        )
    except TelegramError:
        pass

async def cmd_battle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user=update.message.from_user; data=load_data()
    u=get_user(data,user.id,user.username,user.full_name)
    cd=u.get("hunt_cooldown")
    if cd:
        rem=(datetime.fromisoformat(cd)-datetime.now()).total_seconds()
        if rem>0: await update.message.reply_text(f"⏳ Cooldown: *{int(rem)}s*",parse_mode="Markdown"); return
    BATTLE_ENEMIES=[{"name":"🐍 Snake","hp":30,"atk":8},{"name":"🦂 Scorpion","hp":25,"atk":10},
        {"name":"🐊 Croc","hp":50,"atk":12},{"name":"🐻 Bear","hp":60,"atk":15},
        {"name":"🐯 Tiger","hp":55,"atk":18},{"name":"🐉 Dragon","hp":120,"atk":30}]
    weapon=WEAPONS.get(u.get("weapon","stick"),WEAPONS["stick"])
    enemy=random.choice(BATTLE_ENEMIES); php=50; ehp=enemy["hp"]; rounds=0
    while php>0 and ehp>0 and rounds<12:
        p_atk=random.randint(8+weapon["atk_bonus"]//2,20+weapon["atk_bonus"])
        e_atk=random.randint(int(enemy["atk"]*0.7),enemy["atk"])
        ehp-=p_atk; php-=e_atk; rounds+=1
    u["hunt_cooldown"]=(datetime.now()+timedelta(seconds=45)).isoformat()
    if php>0:
        reward=enemy["atk"]*3; gems_r=random.randint(2,8)
        u["coins"]+=reward; u["gems"]=u.get("gems",0)+gems_r; u["hunts"]=u.get("hunts",0)+1
        check_badges(u); save_data(data)
        await update.message.reply_text(
            f"⚔️ *BATTLE vs {enemy['name']}*\n{rounds} rounds | HP left: *{max(0,php)}*\n\n"
            f"🏆 *Victory!* +{reward} 🪙 +{gems_r} 💎",parse_mode="Markdown")
    else:
        loss=random.randint(5,15); u["coins"]=max(0,u["coins"]-loss); save_data(data)
        await update.message.reply_text(
            f"⚔️ *BATTLE vs {enemy['name']}*\n{rounds} rounds\n\n💀 *Defeated!* -{loss} 🪙",parse_mode="Markdown")

async def cmd_forgewar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id=update.message.chat_id
    if not await is_admin(context.bot,chat_id,update.message.from_user.id):
        await update.message.reply_text("⚠️ Admins only!"); return
    data=load_data(); group=get_group(data,chat_id)
    group["forge_war"]=True; group["forge_war_multiplier"]=2; save_data(data)
    await update.message.reply_text("⚔️ *FORGE WAR!* All rewards ×2 for 1 hour! 🪙🔥",parse_mode="Markdown")
    context.job_queue.run_once(lambda ctx:asyncio.ensure_future(_end_forge_war(ctx,chat_id)),
        when=3600,name=f"fw_{chat_id}")

async def _end_forge_war(context, chat_id):
    data=load_data(); group=get_group(data,chat_id)
    group["forge_war"]=False; group["forge_war_multiplier"]=1; save_data(data)
    await context.bot.send_message(chat_id,"⚔️ *Forge War ended!* Back to normal. 🏆",parse_mode="Markdown")

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
        ("setteam",    cmd_setteam),
        ("pvp",        cmd_pvp),
        ("tradeitem",  cmd_tradeitem),
        ("auction",    cmd_auction),
        ("pray",       cmd_pray),
    ]
    for cmd,fn in handlers: app.add_handler(CommandHandler(cmd,fn))
    app.add_handler(CallbackQueryHandler(handle_shop_purchase,pattern="^buy_"))
    app.add_handler(CallbackQueryHandler(handle_leaderboard_tab,pattern="^lb_"))
    app.add_handler(CallbackQueryHandler(handle_gem_purchase,pattern="^gbuy_"))
    app.add_handler(CallbackQueryHandler(handle_trade,pattern="^tacpt_|^tdecl_"))
    app.add_handler(ChatMemberHandler(handle_member_update, ChatMemberHandler.CHAT_MEMBER))
    app.add_handler(MessageHandler(filters.PHOTO&~filters.COMMAND,handle_message))
    app.add_handler(MessageHandler(filters.TEXT&~filters.COMMAND,handle_message))
    app.add_handler(CallbackQueryHandler(handle_pvp,        pattern="^pvpacpt_|^pvpdecl_"))
    app.add_handler(CallbackQueryHandler(handle_item_trade, pattern="^tiacpt_|^tidecl_"))
    logger.info("Aira v6 running!")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__=="__main__":
    main()
ENDOFFILE
