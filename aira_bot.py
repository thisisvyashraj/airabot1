"""
Aira v8 – Ultimate Telegram Bot
Challenges • OWO Hunting • Casino • AFK System • AI Chat • Admin Tools
Welcomer • Daily Rewards • Trading • Pomodoro • Weather • Tournaments
Truth & Dare • Aira Personality Chat • Chess (vs bot / friend / random, rated)
"""

import logging, random, asyncio, json, os, re, httpx, secrets, base64
from datetime import datetime, timedelta
from urllib.parse import quote
from telegram.ext import PollAnswerHandler
from telegram import (Update, InlineKeyboardButton, InlineKeyboardMarkup,
                      ChatPermissions, ReactionTypeEmoji, WebAppInfo)
from telegram.error import TelegramError, BadRequest
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, filters, ContextTypes, ChatMemberHandler,
)

# ══════════════════════════════════════════════════════════════════════════════
#  CONFIG
# ══════════════════════════════════════════════════════════════════════════════
# NOTE: these were hardcoded in the original file. They now read from the
# environment first (with the old values kept ONLY as a fallback so nothing
# breaks if you haven't set env vars yet). You shared the real token + key in
# this conversation -- please rotate both in @BotFather / Groq's console and
# then set them as env vars instead of leaving them in source. Anyone who
# sees this file can take over the bot / spend your API quota otherwise.
BOT_TOKEN          = os.environ.get("BOT_TOKEN", "8807391435:AAEiguri8PTUAYaKDbOX8zpsJ93r0u8Hr1E")
GROQ_API_KEY       = os.environ.get("GROQ_API_KEY", "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")
GROQ_MODEL         = os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")  # bigger model = far less repetitive than 8b-instant
CHALLENGE_TIMEOUT  = 300
CHALLENGE_COOLDOWN = 300
INTERVAL_MIN       = 1800
INTERVAL_MAX       = 5400
STREAK_BONUS       = 2
DATA_FILE          = "aira_data.json"
TITLE_HOURS        = 24
AIRA_THREAD_ID     = None

# ── Auto-challenge (new) ──────────────────────────────────────────────────
# In addition to the manual /challenge command, Aira now drops a fresh
# challenge in every active group on its own, every 5-6 minutes, as long as
# there isn't already one running.
AUTO_CHALLENGE_MIN = 300   # 5 min
AUTO_CHALLENGE_MAX = 360   # 6 min

# ── Truth & Dare (new) ─────────────────────────────────────────────────────
TND_TURN_TIMEOUT = 90      # seconds before Aira auto-advances to next player

# ── Chess service (new) ─────────────────────────────────────────────────────
# The chess engine / rating system / multiplayer relay run as a SEPARATE
# service (chess_server/), because real-time multiplayer + an actual chess
# engine need a websocket server, not a Telegram long-poll loop. See
# chess_server/README for how to run it. CHESS_WEBAPP_URL MUST be a public
# https URL for Telegram's WebApp buttons to work -- localhost will not work
# from a real phone.
CHESS_SERVER_URL  = os.environ.get("CHESS_SERVER_URL", "http://localhost:8000")
CHESS_WEBAPP_URL  = os.environ.get("CHESS_WEBAPP_URL", "https://your-domain.example.com")

# ── Evergreen admin codes ──────────────────────────────────────────────────────
EVERGREEN_COINS_CODE  = "AIRA-FORGE-INFINITE"
EVERGREEN_ADMIN_CODE  = "AIRA-GOD-MODE-9Z"

# ── One-time codes ─────────────────────────────────────────────────────────
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
#  AIRA PERSONALITY SYSTEM PROMPT  (rewritten to sound like an actual person)
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
- Koi vulgar/inappropriate baat kare toh robotic refusal mat do ("I can't do that" jaisa kuch nahi) — natural roast karo, ignore karo, ya seedha "bhai tameez se baat kar" bol do
- Kabhi gaali, gussa ya rude nahi hona hai — chahe samne wala kuch bhi bole, calm/sweet/positive hi rehna hai

Yaad rakho: tum is group mein hi maujood ho, conversation ka hissa ho — kisi screen ke peeche se reply generate nahi kar rahi."""

# Mood flavour text injected on top of the system prompt, refreshed every
# 15-40 minutes per chat, so Aira doesn't sound like the exact same person
# in every single message across a long day.
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

# ══════════════════════════════════════════════════════════════════════════════
#  WEAPONS
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
#  TRUTH & DARE QUESTIONS
# ══════════════════════════════════════════════════════════════════════════════
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

# ══════════════════════════════════════════════════════════════════════════════
#  QUESTIONS (130+)
# ══════════════════════════════════════════════════════════════════════════════
QUESTIONS = [
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
    "half_cooldown":   {"name":"⚡ Cooldown Slash (20 min)",  "desc":"Half cooldown on everything for 20 minutes!", "cost":200},
    "cheap_autohunt":  {"name":"🤖 Budget AutoHunt (1h)",     "desc":"AutoHunt for only 5 coins/hunt instead of 10!", "cost":100},
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
    "mythic_catch": ("🌈 Chosen One", "Caught a Mythic animal! 1 in a million!"),
}

DAILY_TIERS = [(50,"Base"),(75,"Bonus!"),(100,"Great!"),(125,"Amazing!"),(150,"Incredible!"),(200,"🔥 LEGENDARY!")]

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
    "auto_challenge_enabled": True,  # <--- ADD THIS LINE
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
#  AIRA AI CHAT — GROQ  (rewritten: less repetitive, more "human")
# ══════════════════════════════════════════════════════════════════════════════

# Per-chat conversation history (in-memory, short-term)
_chat_histories = {}   # chat_id -> list of {role, content}
_MAX_HISTORY    = 18   # keep last 18 messages

# Per-chat "mood" so Aira doesn't sound identical all day
_chat_moods = {}        # chat_id -> (mood_text, expires_at)

# Friendlier, varied fallbacks instead of one repeated line
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
    """Call Groq API with conversation history and return Aira's reply."""
    if chat_id not in _chat_histories:
        _chat_histories[chat_id] = []

    history = _chat_histories[chat_id]

    # Append user message with name context
    history.append({
        "role": "user",
        "content": f"{user_name}: {user_message}"
    })

    # Trim to last N messages
    if len(history) > _MAX_HISTORY:
        history[:] = history[-_MAX_HISTORY:]

    mood = _get_mood(chat_id)
    system_prompt = f"{AIRA_SYSTEM_PROMPT}\n\nABHI KA MOOD: {mood}"

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {GROQ_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": GROQ_MODEL,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        *history
                    ],
                    "max_tokens": 220,
                    "temperature": 1.05,
                    # These two cut down hard on Aira repeating the same
                    # phrasing turn after turn (OpenAI-compatible params,
                    # supported by Groq's /chat/completions endpoint).
                    "frequency_penalty": 0.6,
                    "presence_penalty": 0.4,
                }
            )
            data = resp.json()
            reply = data["choices"][0]["message"]["content"].strip()
            if not reply:
                raise ValueError("empty reply")
    except Exception as e:
        logger.error(f"Groq API error: {e}")
        reply = random.choice(FALLBACK_REPLIES)

    # Append Aira's reply to history
    history.append({"role": "assistant", "content": reply})
    _chat_histories[chat_id] = history

    return reply


def _should_aira_reply(update: Update, bot_username: str) -> bool:
    """Return True if Aira should reply to this message."""
    msg = update.message
    if not msg:
        return False

    text = msg.text or msg.caption or ""

    # Always reply if someone replied to Aira's own message
    if msg.reply_to_message and msg.reply_to_message.from_user:
        if msg.reply_to_message.from_user.username == bot_username:
            return True

    # Reply if bot is mentioned by @username
    bot_mention = f"@{bot_username}".lower()
    if bot_mention in text.lower():
        return True

    # Reply if "aira" is mentioned (case insensitive)
    if re.search(r'\baira\b', text, re.IGNORECASE):
        return True

    return False


# ══════════════════════════════════════════════════════════════════════════════
#  TRUTH & DARE SYSTEM  (rewritten: auto-advance + sturdier error handling)
# ══════════════════════════════════════════════════════════════════════════════

# Active TND lobbies: chat_id -> { host_id, host_name, players: {uid: name},
#                                  status: "lobby"/"active", current_player_idx,
#                                  player_order: [], player_last_choice: {},
#                                  consecutive_count: {} }
_tnd_lobbies = {}

async def cmd_truth(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Standalone /truth — works without a lobby, just drops a truth question."""
    user = update.message.from_user
    name = f"@{user.username}" if user.username else user.full_name
    q = random.choice(TRUTHS)
    await update.message.reply_text(f"🙊 *TRUTH for {name}!*\n\n_{q}_", parse_mode="Markdown")

async def cmd_dare(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Standalone /dare — works without a lobby, just drops a dare."""
    user = update.message.from_user
    name = f"@{user.username}" if user.username else user.full_name
    d = random.choice(DARES)
    await update.message.reply_text(f"🔥 *DARE for {name}!*\n\n_{d}_", parse_mode="Markdown")

async def cmd_tnd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Master /tnd command handler."""
    chat_id = update.message.chat_id
    user    = update.message.from_user
    uid     = user.id
    name    = f"@{user.username}" if user.username else user.full_name

    args = context.args
    sub  = args[0].lower() if args else ""

    # ── /tnd (no args) — create lobby ────────────────────────────────────────
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
            "host_id":     uid,
            "host_name":   name,
            "players":     {uid: name},
            "status":      "lobby",
            "created_at":  datetime.now().isoformat(),
            "current_player_idx":  0,
            "player_order":        [],
            "player_last_choice":  {},
            "consecutive_count":   {},
        }

        # Auto-expire empty lobby after 5 minutes
        context.job_queue.run_once(
            _tnd_lobby_expire,
            when=300,
            name=f"tnd_expire_{chat_id}",
            data={"chat_id": chat_id}
        )

        await update.message.reply_text(
            f"🎭 *Truth or Dare Lobby Created!*\n━━━━━━━━━━━━━\n"
            f"👑 Host: {name}\n\n"
            f"Others can join with `/tnd join`\n"
            f"Host starts with `/tnd start`\n"
            f"_(Lobby expires in 5 min if only 1 player)_ ⏳",
            parse_mode="Markdown")
        return

    # ── /tnd join ─────────────────────────────────────────────────────────────
    if sub == "join":
        if chat_id not in _tnd_lobbies:
            await update.message.reply_text("❌ No TnD lobby! Use `/tnd` to create one.", parse_mode="Markdown")
            return
        lobby = _tnd_lobbies[chat_id]
        if lobby["status"] != "lobby":
            await update.message.reply_text("❌ Game already started! Wait for next round.")
            return
        if uid in lobby["players"]:
            await update.message.reply_text(f"You're already in the lobby {name}! 😄")
            return
        lobby["players"][uid] = name
        count = len(lobby["players"])
        await update.message.reply_text(
            f"✅ *{name}* joined the lobby!\n👥 Players: *{count}*\n\n"
            f"_Host {lobby['host_name']} can `/tnd start` anytime!_",
            parse_mode="Markdown")
        return

    # ── /tnd leave ────────────────────────────────────────────────────────────
    if sub == "leave":
        if chat_id not in _tnd_lobbies:
            await update.message.reply_text("❌ No active TnD lobby!")
            return
        lobby = _tnd_lobbies[chat_id]
        if uid not in lobby["players"]:
            await update.message.reply_text("You're not in the lobby!")
            return
        del lobby["players"][uid]
        await update.message.reply_text(f"👋 *{name}* left the lobby.")

        # If host left, reassign or close
        if uid == lobby["host_id"]:
            if lobby["players"]:
                new_host_id   = next(iter(lobby["players"]))
                new_host_name = lobby["players"][new_host_id]
                lobby["host_id"]   = new_host_id
                lobby["host_name"] = new_host_name
                await update.message.reply_text(f"👑 {new_host_name} is now the host!")
            else:
                del _tnd_lobbies[chat_id]
                await update.message.reply_text("🎭 Lobby closed — everyone left!")
        return

    # ── /tnd start ────────────────────────────────────────────────────────────
    if sub == "start":
        if chat_id not in _tnd_lobbies:
            await update.message.reply_text("❌ No TnD lobby! Use `/tnd` to create one.", parse_mode="Markdown")
            return
        lobby = _tnd_lobbies[chat_id]
        if uid != lobby["host_id"]:
            await update.message.reply_text("❌ Only the host can start the game!")
            return
        if len(lobby["players"]) < 2:
            await update.message.reply_text("❌ Need at least 2 players to start! Others can `/tnd join`", parse_mode="Markdown")
            return
        if lobby["status"] == "active":
            await update.message.reply_text("Game already running!")
            return

        # Cancel expire job
        for job in context.job_queue.get_jobs_by_name(f"tnd_expire_{chat_id}"):
            job.schedule_removal()

        lobby["status"]       = "active"
        lobby["player_order"] = list(lobby["players"].keys())
        random.shuffle(lobby["player_order"])
        lobby["current_player_idx"]  = 0
        lobby["player_last_choice"]  = {}
        lobby["consecutive_count"]   = {uid: {"truth": 0, "dare": 0} for uid in lobby["players"]}

        order_str = "\n".join(f"  {i+1}. {lobby['players'][p]}" for i, p in enumerate(lobby["player_order"]))
        first_uid  = lobby["player_order"][0]
        first_name = lobby["players"][first_uid]

        sent = await update.message.reply_text(
            f"🎭 *Truth or Dare — STARTED!*\n━━━━━━━━━━━━━\n"
            f"🎲 Play order:\n{order_str}\n\n"
            f"🎤 First up: *{first_name}*\n"
            f"Choose your fate! 👇\n"
            f"_(If no choice in {TND_TURN_TIMEOUT}s, Aira will auto-skip you!)_",
            parse_mode="Markdown",
            reply_markup=_tnd_keyboard(first_uid, lobby)
        )
        _schedule_tnd_choice_timeout(context, chat_id, sent.message_id, first_uid, lobby)
        return

    # ── /tnd end ──────────────────────────────────────────────────────────────
    if sub == "end":
        if chat_id not in _tnd_lobbies:
            await update.message.reply_text("No active TnD game!")
            return
        lobby = _tnd_lobbies[chat_id]
        if uid != lobby["host_id"] and not await is_admin(context.bot, chat_id, uid):
            await update.message.reply_text("❌ Only the host or an admin can end the game!")
            return
        del _tnd_lobbies[chat_id]
        for job in context.job_queue.get_jobs_by_name(f"tnd_expire_{chat_id}"):
            job.schedule_removal()
        for job in context.job_queue.get_jobs_by_name(f"tnd_autonext_{chat_id}"):
            job.schedule_removal()
        await update.message.reply_text(
            f"🎭 *Truth or Dare ended!* Thanks for playing everyone 🙌\n"
            f"Start a new one anytime with `/tnd`", parse_mode="Markdown")
        return

    await update.message.reply_text(
        "🎭 *Truth or Dare Commands:*\n"
        "`/tnd` — Create lobby\n"
        "`/tnd join` — Join lobby\n"
        "`/tnd leave` — Leave lobby\n"
        "`/tnd start` — Start game (host)\n"
        "`/tnd end` — End game (host/admin)\n\n"
        "Just want a quick one without a lobby? Try `/truth` or `/dare` anytime!",
        parse_mode="Markdown")


def _tnd_keyboard(current_uid: int, lobby: dict) -> InlineKeyboardMarkup:
    """Build Truth/Dare choice keyboard, disabling blocked choices."""
    counts = lobby["consecutive_count"].get(current_uid, {"truth": 0, "dare": 0})
    truth_blocked = counts["truth"] >= 2
    dare_blocked  = counts["dare"]  >= 2

    truth_label = "🙊 Truth" + (" (blocked)" if truth_blocked else "")
    dare_label  = "🔥 Dare"  + (" (blocked)" if dare_blocked  else "")

    return InlineKeyboardMarkup([[
        InlineKeyboardButton(truth_label, callback_data=f"tnd_truth_{current_uid}"),
        InlineKeyboardButton(dare_label,  callback_data=f"tnd_dare_{current_uid}"),
    ]])


def _schedule_tnd_choice_timeout(context, chat_id, message_id, current_uid, lobby):
    """Schedule an auto-advance if the current player doesn't act in time."""
    for job in context.job_queue.get_jobs_by_name(f"tnd_autonext_{chat_id}"):
        job.schedule_removal()
    context.job_queue.run_once(
        _tnd_auto_advance,
        when=TND_TURN_TIMEOUT,
        name=f"tnd_autonext_{chat_id}",
        data={
            "chat_id": chat_id,
            "message_id": message_id,
            "stage": "choosing",
            "player_idx_at_schedule": lobby["current_player_idx"],
        }
    )


def _schedule_tnd_next_timeout(context, chat_id, message_id, lobby):
    """After a Truth/Dare question is revealed, auto-advance to the next
    player automatically once the timer runs out -- this is the actual fix
    for 'doesn't move to next player automatically'. Tapping Next manually
    still works and just cancels this timer early."""
    for job in context.job_queue.get_jobs_by_name(f"tnd_autonext_{chat_id}"):
        job.schedule_removal()
    context.job_queue.run_once(
        _tnd_auto_advance,
        when=TND_TURN_TIMEOUT,
        name=f"tnd_autonext_{chat_id}",
        data={
            "chat_id": chat_id,
            "message_id": message_id,
            "stage": "revealed",
            "player_idx_at_schedule": lobby["current_player_idx"],
        }
    )


async def _advance_tnd_turn(context, chat_id, message_id, lobby):
    """Move to the next player and edit the given message in place."""
    lobby["current_player_idx"] = (lobby["current_player_idx"] + 1) % len(lobby["player_order"])
    next_uid  = lobby["player_order"][lobby["current_player_idx"]]
    next_name = lobby["players"].get(next_uid, "Player")
    try:
        await context.bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=f"🎭 *Next up: {next_name}!*\nChoose your fate 👇\n"
                 f"_(If no choice in {TND_TURN_TIMEOUT}s, Aira will auto-skip!)_",
            parse_mode="Markdown",
            reply_markup=_tnd_keyboard(next_uid, lobby)
        )
    except BadRequest:
        pass
    _schedule_tnd_choice_timeout(context, chat_id, message_id, next_uid, lobby)


async def _tnd_auto_advance(context: ContextTypes.DEFAULT_TYPE):
    """Fires when a player doesn't choose Truth/Dare in time, OR doesn't
    move on after their question was revealed -- in both cases Aira just
    advances the game herself so it never gets stuck."""
    d = context.job.data
    chat_id = d["chat_id"]
    if chat_id not in _tnd_lobbies:
        return
    lobby = _tnd_lobbies[chat_id]
    if lobby["status"] != "active":
        return
    # If something else already advanced the turn since this job was
    # scheduled, this job is stale -- do nothing.
    if lobby["current_player_idx"] != d.get("player_idx_at_schedule"):
        return
    try:
        if d.get("stage") == "choosing":
            stuck_uid  = lobby["player_order"][lobby["current_player_idx"]]
            stuck_name = lobby["players"].get(stuck_uid, "Player")
            try:
                await context.bot.edit_message_text(
                    chat_id=chat_id, message_id=d["message_id"],
                    text=f"⌛ *{stuck_name}* took too long to choose!\nSkipping to next player...",
                    parse_mode="Markdown")
            except BadRequest:
                pass
            await _advance_tnd_turn(context, chat_id, d["message_id"], lobby)
        else:
            await _advance_tnd_turn(context, chat_id, d["message_id"], lobby)
    except Exception as e:
        logger.error(f"_tnd_auto_advance error: {e}")


async def handle_tnd_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle Truth/Dare button press."""
    query  = update.callback_query
    try:
        await query.answer()
    except BadRequest:
        pass
    parts  = query.data.split("_")          # tnd_truth_<uid> or tnd_dare_<uid>
    choice = parts[1]                        # "truth" or "dare"
    target_uid = int(parts[2])
    chat_id    = query.message.chat_id
    clicker_id = query.from_user.id

    if chat_id not in _tnd_lobbies:
        try: await query.edit_message_text("❌ Game ended or expired!")
        except BadRequest: pass
        return

    lobby = _tnd_lobbies[chat_id]

    if lobby["status"] != "active":
        await query.answer("Game is not active!", show_alert=True)
        return

    # Only the current player can choose
    if clicker_id != target_uid:
        await query.answer("It's not your turn! 😤", show_alert=True)
        return

    counts = lobby["consecutive_count"].setdefault(target_uid, {"truth": 0, "dare": 0})

    # Check consecutive limit (max 2 same in a row)
    if choice == "truth" and counts["truth"] >= 2:
        await query.answer("You can't pick Truth 3 times in a row! Choose Dare 🔥", show_alert=True)
        return
    if choice == "dare" and counts["dare"] >= 2:
        await query.answer("You can't pick Dare 3 times in a row! Choose Truth 🙊", show_alert=True)
        return

    # Reset opposite counter, increment chosen
    if choice == "truth":
        counts["truth"] += 1
        counts["dare"]   = 0
        question = random.choice(TRUTHS)
        icon = "🙊"
        label = "TRUTH"
    else:
        counts["dare"]  += 1
        counts["truth"]  = 0
        question = random.choice(DARES)
        icon = "🔥"
        label = "DARE"

    player_name = lobby["players"].get(target_uid, "Player")

    try:
        await query.edit_message_text(
            f"{icon} *{player_name}* chose *{label}!*\n━━━━━━━━━━━━━\n\n"
            f"_{question}_\n\n"
            f"_(Do it, then hit Next -- or Aira auto-skips in {TND_TURN_TIMEOUT}s!)_",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("⏭️ Next Player", callback_data=f"tnd_next_{target_uid}")
            ]])
        )
    except BadRequest:
        pass

    # This is the actual fix: schedule an automatic advance so the game
    # never gets stuck waiting for someone to remember to tap "Next".
    _schedule_tnd_next_timeout(context, chat_id, query.message.message_id, lobby)


async def handle_tnd_next(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Move to next player (manual tap) -- cancels the auto-advance timer."""
    query  = update.callback_query
    try:
        await query.answer()
    except BadRequest:
        pass
    parts  = query.data.split("_")
    prev_uid = int(parts[2])
    chat_id  = query.message.chat_id

    if chat_id not in _tnd_lobbies:
        try: await query.edit_message_text("Game has ended!")
        except BadRequest: pass
        return

    lobby = _tnd_lobbies[chat_id]
    if lobby["status"] != "active":
        try: await query.edit_message_text("Game ended.")
        except BadRequest: pass
        return

    # Only the player who just went, or the host, can force-advance early
    if query.from_user.id not in (prev_uid, lobby["host_id"]):
        await query.answer("Only the current player or host can do that!", show_alert=True)
        return

    for job in context.job_queue.get_jobs_by_name(f"tnd_autonext_{chat_id}"):
        job.schedule_removal()

    await _advance_tnd_turn(context, chat_id, query.message.message_id, lobby)


async def _tnd_lobby_expire(context: ContextTypes.DEFAULT_TYPE):
    """Auto-expire lobby if only 1 player after 5 minutes."""
    data    = context.job.data
    chat_id = data["chat_id"]
    if chat_id not in _tnd_lobbies:
        return
    lobby = _tnd_lobbies[chat_id]
    if lobby["status"] != "lobby":
        return
    if len(lobby["players"]) <= 1:
        del _tnd_lobbies[chat_id]
        try:
            await context.bot.send_message(
                chat_id,
                "🎭 *TnD lobby expired!* No one joined within 5 minutes.\n"
                "Start a new one with `/tnd` 👻",
                parse_mode="Markdown"
            )
        except:
            pass






# Game state: chat_id -> { "players": {uid: name}, "status": "lobby"/"active", "spy_id": [], "word": str, "players_left": [] }
_spy_games = {}
async def cmd_spy(update: Update, context: ContextTypes.DEFAULT_TYPE):
  # Save the list of IDs in the exact order they appear in the poll
  # Save the list of IDs in the exact order they appear in the poll
   
    chat_id = update.message.chat_id
    user = update.message.from_user
    uid = user.id
    name = f"@{user.username}" if user.username else user.full_name
    sub = context.args[0].lower() if context.args else ""

    if not sub: # Create lobby
        _spy_games[chat_id] = {"players": {uid: name}, "status": "lobby"}
        await update.message.reply_text("🕵️‍♂️ *Who's the Spy Lobby Created!*\nUse `/spy join` to enter.", parse_mode="Markdown")
    elif sub == "join":
        if chat_id not in _spy_games: return
        _spy_games[chat_id]["players"][uid] = name
        await update.message.reply_text(f"✅ {name} joined! Players: {len(_spy_games[chat_id]['players'])}")
    elif sub == "start":
        game = _spy_games[chat_id]
        if len(game["players"]) < 3: await update.message.reply_text("❌ Need 3+ players."); return
        
        # Logic to pick spies based on count
        player_list = list(game["players"].keys())
        num_spies = 1 if len(player_list) <= 6 else (2 if len(player_list) <= 12 else 3)
        game["spy_ids"] = random.sample(player_list, num_spies)
        game["word"] = "Banana" # Ideally use an AI to pick this
        
        for p_uid in player_list:
            role = "🕵️‍♂️ YOU ARE THE SPY!" if p_uid in game["spy_ids"] else f"Word: {game['word']}"
            try: await context.bot.send_message(p_uid, role)
            except: await update.message.reply_text(f"❌ Could not DM {game['players'][p_uid]}")
        
        game["status"] = "active"
        await update.message.reply_text("🕵️‍♂️ Game started! Words sent via DM. 60s discussion starts now!")
        context.job_queue.run_once(lambda ctx: _start_spy_vote(ctx, chat_id), 60)

async def _start_spy_vote(context, chat_id):
    # Ensure game still exists and is in active state
    if chat_id not in _spy_games:
        return
        
    game = _spy_games[chat_id]
    players = game["players"]
    
    # 1. Maintain strict order: Extract UIDs and Names into parallel lists
    # We save these UIDs so handle_spy_vote knows exactly who corresponds to poll index 0, 1, 2...
    player_uids = list(players.keys())
    player_names = list(players.values())
    
    # 2. Send the poll and capture the message object
    poll_msg = await context.bot.send_poll(
        chat_id=chat_id, 
        question="Who is the spy?", 
        options=player_names, 
        is_anonymous=False, 
        allows_multiple_answers=False,
        close_date=datetime.now() + timedelta(seconds=15)
    )
    
    # 3. Save the metadata required for the voting handler to function
    game["poll_id"] = poll_msg.poll.id
    game["chat_id"] = chat_id
    game["poll_option_uids"] = player_uids # CRITICAL: Map poll index to UID
    
    logger.info(f"Spy voting started in {chat_id} (Poll ID: {poll_msg.poll.id})")

async def handle_spy_vote(update: Update, context: ContextTypes.DEFAULT_TYPE):
    poll_answer = update.poll_answer
    poll_id = poll_answer.poll_id
    user_id = poll_answer.user.id
    option_ids = poll_answer.option_ids
    
    if not option_ids: return 
    vote_index = option_ids[0]
    
    # 1. Find game
    game = next((g for g in _spy_games.values() if g.get("poll_id") == poll_id), None)
    if not game or game["status"] != "active": return

    # 2. Record vote
    game.setdefault("votes", {})[user_id] = vote_index
    
    # 3. Check if all players voted
    if len(game["votes"]) == len(game["players"]):
        tally = {}
        for v in game["votes"].values():
            tally[v] = tally.get(v, 0) + 1
        
        winner_idx = max(tally, key=tally.get)
        
        # Use the UID mapping list
        eliminated_uid = game["poll_option_uids"][winner_idx]
        eliminated_name = game["players"][eliminated_uid]
        is_spy = eliminated_uid in game["spy_ids"]
        
        if is_spy:
            await context.bot.send_message(game["chat_id"], f"🕵️‍♂️ *{eliminated_name}* was a SPY! Innocents win! 🥳", parse_mode="Markdown")
            del _spy_games[game["chat_id"]]
        else:
            # --- FIX: Cleanup the UID mapping list so next round doesn't break ---
            game["players"].pop(eliminated_uid)
            # Remove the UID from the mapping list so indices align with next poll
            game["poll_option_uids"].pop(winner_idx) 
            
            await context.bot.send_message(game["chat_id"], f"❌ *{eliminated_name}* was NOT a spy! Round continues...", parse_mode="Markdown")
            
            if len(game["players"]) <= 3:
                await context.bot.send_message(game["chat_id"], "🕵️‍♂️ The spies have won! Game over.", parse_mode="Markdown")
                del _spy_games[game["chat_id"]]
            else:
                game["votes"] = {}
                # Trigger next round here!
                await _start_spy_vote(context, game["chat_id"])
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
    if random.randint(1, 1_000_000) == 777:
        mythic = next((a for a in ANIMALS if a["rarity"] == "mythic"), None)
        if mythic:
            return mythic
    pool = []
    for a in ANIMALS:
        if a["rarity"] != "mythic":
            pool.extend([a] * RARITY_WEIGHTS[a["rarity"]])
    return random.choice(pool)

async def do_hunt(bot, chat_id, user_id, username=None, full_name=None):
    db  = _get_db()
    uid = str(user_id)
    doc = db["users"].find_one({"_id": uid})
    if doc:
        doc.pop("_id", None)
        u = doc
        if username:  u["username"]  = username
        if full_name: u["full_name"] = full_name
    else:
        u = {
            "username": username or "Unknown","full_name": full_name or "Unknown",
            "coins":0,"wins":0,"streak":0,"best_streak":0,"badges":[],
            "title":None,"title_expiry":None,"title_chat_id":None,"title_purchased":False,
            "double_coins":False,"weekly_wins":0,"last_win_date":None,
            "pin_token":False,"shield_expiry":None,
            "owo":0,"animals":[],"hunts":0,"hunt_cooldown":None,
            "owo_boost_expiry":None,"auto_hunt":False,"total_coins_ever":0,
            "daily_claimed":None,"daily_streak":0,"today_wins":0,"today_date":None,
            "gems":0,"weapon":"stick","afk":None,"afk_since":None,"afk_pings":[],
            "casino_wins":0,"casino_total_won":0,"xp":0,"level":1,
            "battle_team":[],"last_pray":None,"pray_active":False,"pray_expires":None,
        }

    cooldown = u.get("hunt_cooldown")
    if cooldown:
        try:
            rem = (datetime.fromisoformat(cooldown) - datetime.now()).total_seconds()
            if rem > 0:
                return f"⏳ Hunt cooldown: *{int(rem)}s* left. Patience! 🌿"
        except:
            pass

    cd_mult = get_cooldown_multiplier(u)
    u["hunt_cooldown"]=(datetime.now()+timedelta(seconds=int(15*cd_mult))).isoformat()

    weapon_key  = u.get("weapon", "stick")
    weapon      = WEAPONS.get(weapon_key, WEAPONS["stick"])
    catch_bonus = weapon["catch_bonus"]
    pray_bonus  = 0.10 if has_pray_buff(u) else 0
    catch_rate  = min(0.97, 0.55 + catch_bonus/100 + pray_bonus)

    if random.random() > catch_rate:
        db["users"].replace_one({"_id": uid}, {"_id": uid, **u}, upsert=True)
        return random.choice(HUNT_FAILS)

    animal  = roll_animal()
    owo_e   = animal["owo"]
    coins_e = animal["coins"]
    gems_e  = animal["gems"]
    atk_b   = weapon["atk_bonus"]
    coins_e = int(coins_e * (1 + atk_b / 100))

    boost = u.get("owo_boost_expiry")
    if boost:
        try:
            if datetime.fromisoformat(boost)>datetime.now():
                owo_e*=2; coins_e*=2; gems_e*=2
        except: pass

    if u.get("double_coins"):
        coins_e *= 2
        u["double_coins"] = False

    u["owo"]              = u.get("owo", 0) + owo_e
    u["coins"]            = u.get("coins", 0) + coins_e
    u["gems"]             = u.get("gems", 0) + gems_e
    u["total_coins_ever"] = u.get("total_coins_ever", 0) + coins_e
    u["hunts"]            = u.get("hunts", 0) + 1

    zoo   = u.get("animals", [])
    found = next((z for z in zoo if z["name"] == animal["name"]), None)
    if found:
        found["count"] = found.get("count", 1) + 1
    else:
        if len(zoo) < 50:
            zoo.append({"name": animal["name"], "rarity": animal["rarity"], "count": 1})
        else:
            same = [z for z in zoo if z.get("rarity") == animal["rarity"]]
            if same:
                same[0]["count"] = same[0].get("count", 1) + 1
    u["animals"] = zoo

    lvl_up = add_xp(u, 10)
    badges = check_badges(u)
    if animal["rarity"] in ("rare","epic","legendary","Extreme","mythic"):
        b=award_badge(u,"rare_hunt");
        if b: badges.append(b)
    if animal["rarity"] in ("legendary","Extreme","mythic"):
        b=award_badge(u,"legend_hunt");
        if b: badges.append(b)
    if animal["rarity"] == "mythic":
        b=award_badge(u,"mythic_catch");
        if b: badges.append(b)

    db["users"].replace_one({"_id": uid}, {"_id": uid, **u}, upsert=True)

    icon       = RARITY_COLORS.get(animal["rarity"], "⬜")
    wname      = weapon["name"]
    badge_line = "\n🆕 " + " | ".join(badges) if badges else ""
    lvl_line   = f"\n⬆️ *LEVEL UP! → Lv{u['level']}*" if lvl_up else ""

    if animal["rarity"] == "mythic":
        try:
            name_display = f"@{username}" if username and username != "Unknown" else full_name or "Someone"
            await bot.send_message(
                chat_id,
                f"🌈✨ *MYTHIC CATCH!* ✨🌈\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"🎊 *{name_display}* just caught a\n"
                f"*🕊️ Rara avis* 🌈*MYTHIC*\n\n"
                f"The odds were *1 in 1,000,000!*\n"
                f"This may never happen again! 🔥",
                parse_mode="Markdown"
            )
        except:
            pass

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
    group = get_group_db(chat_id)
    if group["active_challenge"]: return

    # --- AI GENERATION ---
    # We ask for a JSON-structured response for easy parsing
    prompt = (
        "Generate a challenge for a Telegram group. Choose ONE type from: [trivia, word_scramble, photo_hunt]. "
        "If trivia: ask a fun question. If word_scramble: provide a scrambled word. If photo_hunt: ask for a photo of an object. "
        "Return ONLY valid JSON in this format:\n"
        '{"type": "trivia|word|photo", "q": "The challenge question", "a": "The answer/object", "h": "A short hint", "c": 25}'
    )
    
    ai_response = await groq_chat(chat_id, "System", prompt)
    
    try:
        # Extract JSON block using regex
        json_match = re.search(r"\{.*\}", ai_response, re.DOTALL)
        data = json.loads(json_match.group(0))
        ctype, q_text, a_text, h_text, c_val = data["type"], data["q"], data["a"], data["h"], data["c"]
    except:
        # Fallback
        ctype, q_text, a_text, h_text, c_val = "trivia", "What is 2+2?", "4", "It's 4", 10

    # --- SAVE TO DB ---
    mult = group.get("forge_war_multiplier", 1)
    coins = int(c_val) * mult
    
    group["active_challenge"] = {
        "question": q_text,
        "answers": [a_text.lower().strip()],
        "hint": h_text,
        "coins": coins,
        "type": ctype, # This will be 'trivia', 'word', or 'photo'
        "started_at": datetime.now().isoformat()
    }
    
    group["last_challenge_time"] = datetime.now().isoformat()
    save_group_db(chat_id, group)
    
    # --- SEND MESSAGE ---
    fw = f"\n⚔️ *FORGE WAR!* Rewards ×{mult}!\n" if group.get("forge_war") else ""
    
    # Custom instructions based on type
    instructions = {
        "trivia": "💬 *Type the answer!*",
        "word": "⚡ *Type the unscrambled word!*",
        "photo": "📸 *Send a photo of this!*"
    }
    instr = instructions.get(ctype, "💬 *Type the answer!*")
    
    await context.bot.send_message(
        chat_id,
        f"⚡ *NEW {ctype.upper()} CHALLENGE!*{fw}\n{q_text}\n\n💰 *{coins} Forge Coins*\n⏱️ 5 min! {instr}",
        parse_mode="Markdown"
    )
    
    context.job_queue.run_once(expire_challenge, when=CHALLENGE_TIMEOUT,
        chat_id=chat_id, name=f"expire_{chat_id}")
async def expire_challenge(context):
    cid = context.job.chat_id
    group = get_group_db(cid)
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




async def analyze_image_with_ai(file_path, target_object):
    """Uses Groq's Llama-3.2-90b-vision-preview to analyze the image."""
    try:
        # Import inside function to avoid global dependency issues
        import base64
        with open(file_path, "rb") as image_file:
            encoded_image = base64.b64encode(image_file.read()).decode('utf-8')
        
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"},
                json={
                    "model": "llama-3.2-90b-vision-preview", 
                    "messages": [{
                        "role": "user",
                        "content": [
                            {"type": "text", "text": f"Does this image contain {target_object}? Answer only 'yes' or 'no'."},
                            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{encoded_image}"}}
                        ]
                    }]
                }
            )
            data = resp.json()
            return "yes" in data["choices"][0]["message"]["content"].lower()
    except Exception as e:
        logger.error(f"Groq Vision error: {e}")
        return False
# ══════════════════════════════════════════════════════════════════════════════
#  AUTO-CHALLENGE EVERY 5-6 MINUTES (new)
# ══════════════════════════════════════════════════════════════════════════════
# This runs ALONGSIDE the manual /challenge command and the old
# win->schedule_next chain above. It's a self-rescheduling job per chat so
# Aira keeps dropping challenges on her own even if nobody wins/asks for one.
_auto_challenge_chats = set()

async def _auto_challenge_tick(context: ContextTypes.DEFAULT_TYPE):
    chat_id = context.job.data["chat_id"]
    try:
        group = get_group_db(chat_id)
        
        # Check if auto-challenge is enabled (defaulting to True if setting is missing)
        if not group.get("auto_challenge_enabled", True):
            return 
            
        if not group.get("active_challenge"):
            await post_challenge(context, chat_id)
            
    except Exception as e:
        logger.error(f"auto_challenge_tick error for {chat_id}: {e}")
        
    delay = random.randint(AUTO_CHALLENGE_MIN, AUTO_CHALLENGE_MAX)
    context.job_queue.run_once(
        _auto_challenge_tick, when=delay, chat_id=chat_id,
        name=f"autochallenge_{chat_id}", data={"chat_id": chat_id})

def ensure_auto_challenge(context: ContextTypes.DEFAULT_TYPE, chat_id: int):
    """Start the auto-challenge loop for this chat if it isn't running yet."""
    # We check if the group has explicitly disabled auto-challenges before starting the loop
    group = get_group_db(chat_id)
    if not group.get("auto_challenge_enabled", True):
        return

    if chat_id in _auto_challenge_chats or chat_id >= 0:
        return  # only groups (negative chat_id) get auto-challenges
        
    _auto_challenge_chats.add(chat_id)
    delay = random.randint(AUTO_CHALLENGE_MIN, AUTO_CHALLENGE_MAX)
    context.job_queue.run_once(
        _auto_challenge_tick, when=delay, chat_id=chat_id,
        name=f"autochallenge_{chat_id}", data={"chat_id": chat_id})
# ══════════════════════════════════════════════════════════════════════════════
#  MESSAGE HANDLER (AFK + challenges + cheat codes + Aira chat)
# ══════════════════════════════════════════════════════════════════════════════
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message: return
    chat_id  = update.message.chat_id
    user     = update.message.from_user
    text     = update.message.text or ""

    # Keep the auto-challenge loop alive for every group that's active
    ensure_auto_challenge(context, chat_id)

    # ── Chess: capture a custom "type the seconds" reply mid-setup ──────────
    pending_chess = _chess_setup.get(user.id)
    if pending_chess and pending_chess.get("awaiting_custom_time") and text.strip():
        await _handle_chess_custom_time(update, context, pending_chess)
        return

    data     = load_data()
    u        = get_user(data, user.id, user.username, user.full_name)

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

    # ── Clear AFK ─────────────────────────────────────────────────────────────
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

    # ── AFK ping detection ─────────────────────────────────────────────────────
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

    if text and update.message.entities:
        for entity in update.message.entities:
            if entity.type == "mention":
                mentioned = text[entity.offset:entity.offset+entity.length].lstrip("@")
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
    parts = raw.split()






async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message: return
    chat_id  = update.message.chat_id
    user     = update.message.from_user
    text     = update.message.text or ""

    # Keep the auto-challenge loop alive
    ensure_auto_challenge(context, chat_id)

    # ── Chess Setup ──────────────────────────────────────────────────────────
    pending_chess = _chess_setup.get(user.id)
    if pending_chess and pending_chess.get("awaiting_custom_time") and text.strip():
        await _handle_chess_custom_time(update, context, pending_chess)
        return

    data = load_data()
    u = get_user(data, user.id, user.username, user.full_name)

    # ── Challenge Grading Engine ───────────────────────────────────────────
    group = get_group(data, chat_id)
    challenge = group.get("active_challenge")
    
    if challenge:
        # 1. Text Grading (Trivia / Word)
        if challenge["type"] in ["trivia", "word"] and text:
            if text.strip().lower() in challenge["answers"]:
                await process_win(update, context, user, chat_id, challenge, 
                                  "speed_win" if challenge["type"] == "word" else None)
                return

        # 2. AI Image Grading (Photo Hunt)
        elif challenge["type"] == "photo" and update.message.photo:
            msg = await update.message.reply_text("🤔 Checking image with AI...")
            try:
                file = await update.message.photo[-1].get_file()
                await file.download_to_drive("temp.jpg")
                
                is_winner = await analyze_image_with_ai("temp.jpg", challenge["answers"][0])
                
                if is_winner:
                    await msg.delete()
                    await process_win(update, context, user, chat_id, challenge, "image_win")
                    return
                else:
                    await msg.delete()
                    await update.message.reply_text("❌ AI says that's not it! Try a different angle.")
            finally:
                # Guaranteed cleanup of the temp file
                if os.path.exists("temp.jpg"):
                    os.remove("temp.jpg")

    # ── EXISTING AFK, CHEAT CODE, AND AIRA CHAT LOGIC ──────────────────────
    # [Paste your existing AFK, Cheat Code, and Aira Chat logic here]
    # (Ensure you keep the _should_aira_reply and groq_chat calls here)

  
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
                await update.message.reply_text(f"❌ User @{target_uname} not found."); return
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
    if challenge:
        ctype = challenge.get("type","trivia")
        if ctype=="image":
            if update.message.photo:
                await process_win(update,context,user,chat_id,challenge,"image_win")
            # After challenge check, fall through to Aira chat if needed
        elif text:
            ans = text.strip().lower()
            if ans in challenge["answers"]:
                extra="speed_win" if ctype in ("word","speed") else None
                await process_win(update,context,user,chat_id,challenge,extra)
                return  # Don't also trigger Aira chat for correct answers

    # ── Aira personality chat ─────────────────────────────────────────────────
    try:
        bot_me = await context.bot.get_me()
        bot_username = bot_me.username
    except:
        bot_username = "AiraBot"

    if _should_aira_reply(update, bot_username) and text:
        user_name = f"@{user.username}" if user.username else user.full_name
        # Clean the text — remove @mention of bot from message
        clean_text = re.sub(rf'@{re.escape(bot_username)}', '', text, flags=re.IGNORECASE).strip()
        if not clean_text:
            clean_text = text

        # Show typing indicator
        try:
            await context.bot.send_chat_action(chat_id, "typing")
        except:
            pass

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
    chat_id  = result.chat.id
    old_stat = result.old_chat_member.status
    new_stat = result.new_chat_member.status
    member   = result.new_chat_member.user
    name     = f"@{member.username}" if member.username else member.full_name
    group    = get_group_db(chat_id)
    if old_stat in ("left","kicked") and new_stat in ("member","restricted"):
        msg_template = group.get("welcome_msg") or DEFAULT_WELCOME
        msg = msg_template.replace("{name}", name).replace("{username}", name)
        try: await context.bot.send_message(chat_id, msg, parse_mode="Markdown")
        except TelegramError: pass
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
            "Usage: `/setwelcome Welcome {name} to our group!`",parse_mode="Markdown"); return
    msg   = " ".join(context.args)
    group = get_group_db(chat_id)
    group["welcome_msg"]=msg; save_group_db(chat_id, group)
    await update.message.reply_text(f"✅ Welcome message set!\nPreview: {msg.replace('{name}','[User]')}",parse_mode="Markdown")

async def cmd_setbye(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    if not await is_admin(context.bot, chat_id, update.message.from_user.id):
        await update.message.reply_text("⚠️ Admins only!"); return
    if not context.args:
        await update.message.reply_text("Usage: `/setbye Bye {name}!`",parse_mode="Markdown"); return
    msg   = " ".join(context.args)
    group = get_group_db(chat_id)
    group["bye_msg"]=msg; save_group_db(chat_id, group)
    await update.message.reply_text(f"✅ Bye message set!\nPreview: {msg.replace('{name}','[User]')}",parse_mode="Markdown")

async def cmd_toggle_challenge(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    if not await is_admin(context.bot, chat_id, update.message.from_user.id):
        await update.message.reply_text("⚠️ Admins only!"); return
    if not context.args:
        await update.message.reply_text("Usage: `/togglechallenge on` or `/togglechallenge off`", parse_mode="Markdown"); return
    
    status = context.args[0].lower()
    group = get_group_db(chat_id)
    
    if status == "on":
        group["auto_challenge_enabled"] = True
        save_group_db(chat_id, group)
        ensure_auto_challenge(context, chat_id)
        await update.message.reply_text("✅ Auto-challenges enabled.")
    elif status == "off":
        group["auto_challenge_enabled"] = False
        save_group_db(chat_id, group)
        for job in context.job_queue.get_jobs_by_name(f"autochallenge_{chat_id}"):
            job.schedule_removal()
        await update.message.reply_text("❌ Auto-challenges disabled.")
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
    group=get_group_db(chat_id)
    uid=str(target.id)
    group["warns"][uid]=group["warns"].get(uid,0)+1
    count=group["warns"][uid]; save_group_db(chat_id, group)
    name=f"@{target.username}" if target.username else target.full_name
    if count>=3:
        try:
            await context.bot.ban_chat_member(chat_id,target.id)
            await update.message.reply_text(f"⚠️ *{name}* warn {count}/3 → 🔨 *BANNED!*",parse_mode="Markdown")
            group["warns"][uid]=0; save_group_db(chat_id, group)
        except TelegramError as e:
            await update.message.reply_text(f"⚠️ Warn {count}/3 (ban failed: _{e}_)",parse_mode="Markdown")
    else:
        await update.message.reply_text(f"⚠️ *{name}* warned *{count}/3*.",parse_mode="Markdown")

async def cmd_warns(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id=update.message.chat_id; target,err=await get_target(update,context)
    if err: await update.message.reply_text(err); return
    group=get_group_db(chat_id)
    count=group["warns"].get(str(target.id),0)
    name=f"@{target.username}" if target.username else target.full_name
    await update.message.reply_text(f"⚠️ *{name}* has *{count}/3* warnings.",parse_mode="Markdown")

async def cmd_clearwarns(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id=update.message.chat_id
    if not await is_admin(context.bot,chat_id,update.message.from_user.id):
        await update.message.reply_text("⚠️ Admins only!"); return
    target,err=await get_target(update,context)
    if err: await update.message.reply_text(err); return
    group=get_group_db(chat_id)
    group["warns"][str(target.id)]=0; save_group_db(chat_id, group)
    name=f"@{target.username}" if target.username else target.full_name
    await update.message.reply_text(f"✅ Cleared warns for *{name}*.",parse_mode="Markdown")

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
#  AI ASK (old system — separate /ask command, now using the same improved chat)
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
#  CHESS  (new) — talks to the separate chess_server for rules/engine/ratings
# ══════════════════════════════════════════════════════════════════════════════
# in-memory per-user "wizard" state while picking mode/color/time/difficulty
_chess_setup = {}   # user_id -> dict

CHESS_TIME_PRESETS = [
    ("Unlimited", 0), ("1 min", 60), ("3 min", 180),
    ("5 min", 300), ("10 min", 600), ("15 min", 900),
]

CHESS_DIFFICULTY_LABELS = [
    "1. Total Beginner", "2. Just Learned", "3. Casual", "4. Club Novice",
    "5. Club Player", "6. Solid Club", "7. Strong Club", "8. Expert",
    "9. Candidate Master", "10. National Master", "11. FIDE Master",
    "12. International Master", "13. Grandmaster", "14. Super-GM",
    "15. World Class", "16. Maximum (engine-strength)",
]

async def _chess_api(method: str, path: str, **kwargs):
    """Talk to the chess_server. Returns (ok, json_or_error_str)."""
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.request(method, f"{CHESS_SERVER_URL}{path}", **kwargs)
            if resp.status_code >= 400:
                return False, resp.text
            return True, resp.json()
    except Exception as e:
        return False, str(e)

def _chess_open_board_button(game_id: str, uid: int, name: str) -> InlineKeyboardMarkup:
    url = f"{CHESS_WEBAPP_URL}/?game={game_id}&uid={uid}&name={quote(name)}"
    return InlineKeyboardMarkup([[InlineKeyboardButton("♟️ Open Chess Board", web_app=WebAppInfo(url=url))]])

async def cmd_chess(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    _chess_setup[user.id] = {}
    kb = [
        [InlineKeyboardButton("🤖 Play vs Bot", callback_data="chess_mode_bot")],
        [InlineKeyboardButton("👥 Play vs Friend (link/code)", callback_data="chess_mode_friend")],
        [InlineKeyboardButton("🎲 Random Opponent", callback_data="chess_mode_random")],
        [InlineKeyboardButton("📊 My Rating", callback_data="chess_rating"),
         InlineKeyboardButton("🏆 Leaderboard", callback_data="chess_lb")],
    ]
    await update.message.reply_text(
        "♟️ *Aira Chess*\n━━━━━━━━━━━━━\nFull rules engine — castling, en passant, "
        "promotion, stalemate, threefold, the lot — plus real Elo-style ratings.\n\nPick a mode:",
        reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")

async def cmd_chessrating(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    ok, res = await _chess_api("GET", f"/api/rating/{user.id}")
    if not ok:
        await update.message.reply_text(
            "♟️ Couldn't reach the chess service. Make sure chess_server is running "
            "and CHESS_SERVER_URL is set correctly."); return
    await update.message.reply_text(
        f"📊 *{user.full_name}'s Chess Rating*\n━━━━━━━━━━━━━\n"
        f"⭐ Rating: *{res.get('rating', 1200)}*\n"
        f"✅ Wins: *{res.get('wins',0)}* | ❌ Losses: *{res.get('losses',0)}* | 🤝 Draws: *{res.get('draws',0)}*\n"
        f"🏔️ Peak: *{res.get('peak_rating', res.get('rating',1200))}*",
        parse_mode="Markdown")

async def cmd_chessleaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ok, res = await _chess_api("GET", "/api/leaderboard")
    if not ok:
        await update.message.reply_text(
            "♟️ Couldn't reach the chess service. Make sure chess_server is running."); return
    medals = ["🥇","🥈","🥉","4️⃣","5️⃣","6️⃣","7️⃣","8️⃣","9️⃣","🔟"]
    lines = ["🏆 *CHESS LEADERBOARD*\n━━━━━━━━━━━━━"]
    for i, row in enumerate(res.get("leaderboard", [])[:10]):
        lines.append(f"{medals[i]} {row.get('name','?')} — *{row.get('rating',1200)}* "
                     f"({row.get('wins',0)}W/{row.get('losses',0)}L/{row.get('draws',0)}D)")
    if len(lines) == 1:
        lines.append("No rated games yet — be the first with /chess!")
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")

async def handle_chess_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = query.from_user
    data_str = query.data
    setup = _chess_setup.setdefault(user.id, {})

    if data_str == "chess_rating":
        ok, res = await _chess_api("GET", f"/api/rating/{user.id}")
        if not ok:
            await query.edit_message_text("♟️ Couldn't reach the chess service."); return
        await query.edit_message_text(
            f"📊 *Your Chess Rating*\n⭐ *{res.get('rating',1200)}*\n"
            f"✅{res.get('wins',0)} ❌{res.get('losses',0)} 🤝{res.get('draws',0)}",
            parse_mode="Markdown")
        return

    if data_str == "chess_lb":
        ok, res = await _chess_api("GET", "/api/leaderboard")
        if not ok:
            await query.edit_message_text("♟️ Couldn't reach the chess service."); return
        medals = ["🥇","🥈","🥉","4️⃣","5️⃣","6️⃣","7️⃣","8️⃣","9️⃣","🔟"]
        lines = ["🏆 *CHESS LEADERBOARD*"]
        for i, row in enumerate(res.get("leaderboard", [])[:10]):
            lines.append(f"{medals[i]} {row.get('name','?')} — *{row.get('rating',1200)}*")
        await query.edit_message_text("\n".join(lines), parse_mode="Markdown")
        return

    if data_str.startswith("chess_mode_"):
        setup["mode"] = data_str.replace("chess_mode_", "")  # bot / friend / random
        kb = [[InlineKeyboardButton("⚪ White", callback_data="chess_color_white"),
               InlineKeyboardButton("⚫ Black", callback_data="chess_color_black"),
               InlineKeyboardButton("🎲 Random", callback_data="chess_color_random")]]
        await query.edit_message_text("🎨 Pick your color:", reply_markup=InlineKeyboardMarkup(kb))
        return

    if data_str.startswith("chess_color_"):
        setup["color"] = data_str.replace("chess_color_", "")
        kb = [[InlineKeyboardButton(label, callback_data=f"chess_time_{secs}")]
              for label, secs in CHESS_TIME_PRESETS]
        kb.append([InlineKeyboardButton("✍️ Custom (type seconds)", callback_data="chess_time_custom")])
        await query.edit_message_text("⏱️ Pick a time control:", reply_markup=InlineKeyboardMarkup(kb))
        return

    if data_str == "chess_time_custom":
        setup["awaiting_custom_time"] = True
        await query.edit_message_text(
            "✍️ Type the time control in seconds (e.g. `120` for 2 min, `0` for unlimited).",
            parse_mode="Markdown")
        return

    if data_str.startswith("chess_time_"):
        setup["time_control"] = int(data_str.replace("chess_time_", ""))
        await _chess_continue_after_time(query, context, user, setup)
        return

    if data_str.startswith("chess_diff_"):
        setup["difficulty"] = int(data_str.replace("chess_diff_", ""))
        await _chess_finalize(query, context, user, setup)
        return

async def _handle_chess_custom_time(update: Update, context: ContextTypes.DEFAULT_TYPE, setup: dict):
    text = update.message.text.strip()
    try:
        secs = max(0, min(int(text), 24 * 3600))
    except ValueError:
        await update.message.reply_text("❌ Please send a plain number of seconds (e.g. `300`).", parse_mode="Markdown")
        return
    setup["awaiting_custom_time"] = False
    setup["time_control"] = secs
    user = update.message.from_user
    await _chess_continue_after_time(update, context, user, setup, is_message=True)

async def _chess_continue_after_time(target, context, user, setup, is_message=False):
    send = (target.reply_text if is_message else target.edit_message_text)
    if setup.get("mode") == "bot":
        kb = [[InlineKeyboardButton(CHESS_DIFFICULTY_LABELS[i], callback_data=f"chess_diff_{i+1}")]
              for i in range(16)]
        # group into rows of 1 already; chunk into pairs for compactness
        rows = [kb[i] + (kb[i+1] if i+1 < len(kb) else []) for i in range(0, len(kb), 2)]
        await send("🤖 Pick bot difficulty (1 = easiest, 16 = strongest):",
                   reply_markup=InlineKeyboardMarkup(rows))
        return
    await _chess_finalize(target, context, user, setup, is_message=is_message)

async def _chess_finalize(target, context, user, setup, is_message=False):
    send = (target.reply_text if is_message else target.edit_message_text)
    name = f"@{user.username}" if user.username else user.full_name
    color = setup.get("color", "random")
    time_control = setup.get("time_control", 0)
    mode = setup.get("mode")

    if mode == "bot":
        ok, res = await _chess_api("POST", "/api/game/vsbot", json={
            "uid": user.id, "name": name, "color": color,
            "time_control": time_control, "level": setup.get("difficulty", 1),
        })
        if not ok:
            await send("♟️ Couldn't reach the chess service. Is chess_server running?"); return
        game_id = res["game_id"]
        await send(
            f"♟️ *Game ready!* vs Bot (Level {setup.get('difficulty',1)})\nTap below to play:",
            reply_markup=_chess_open_board_button(game_id, user.id, name), parse_mode="Markdown")

    elif mode == "friend":
        ok, res = await _chess_api("POST", "/api/room/create", json={
            "uid": user.id, "name": name, "color": color, "time_control": time_control,
        })
        if not ok:
            await send("♟️ Couldn't reach the chess service. Is chess_server running?"); return
        game_id, room_code = res["game_id"], res["room_code"]
        try:
            bot_me = await context.bot.get_me()
            deep_link = f"https://t.me/{bot_me.username}?start=chess_{room_code}"
        except Exception:
            deep_link = f"(open the bot and send) /chessjoin {room_code}"
        await send(
            f"♟️ *Room created!*\nRoom code: `{room_code}`\n\n"
            f"Share this link with your friend:\n{deep_link}\n\n"
            f"Or they can type `/chessjoin {room_code}`.\n\nYour board:",
            reply_markup=_chess_open_board_button(game_id, user.id, name), parse_mode="Markdown")

    else:  # random
        ok, res = await _chess_api("POST", "/api/queue/join", json={
            "uid": user.id, "name": name, "color": color, "time_control": time_control,
        })
        if not ok:
            await send("♟️ Couldn't reach the chess service. Is chess_server running?"); return
        if res.get("queued"):
            await send("🎲 Looking for an opponent... you'll get a message here the moment someone matches!")
        else:
            game_id = res["game_id"]
            await send("🎲 *Matched!* Tap below to play:",
                       reply_markup=_chess_open_board_button(game_id, user.id, name), parse_mode="Markdown")

    _chess_setup.pop(user.id, None)

async def cmd_chessjoin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/chessjoin <room_code> -- joins a friend's room directly."""
    user = update.message.from_user
    if not context.args:
        await update.message.reply_text("Usage: `/chessjoin <room code>`", parse_mode="Markdown"); return
    room_code = context.args[0].upper()
    name = f"@{user.username}" if user.username else user.full_name
    ok, res = await _chess_api("POST", "/api/room/join", json={"room_code": room_code, "uid": user.id, "name": name})
    if not ok:
        await update.message.reply_text(f"❌ Couldn't join that room: {res}"); return
    await update.message.reply_text(
        "♟️ *Joined!* Tap below to play:",
        reply_markup=_chess_open_board_button(res["game_id"], user.id, name), parse_mode="Markdown")

# ══════════════════════════════════════════════════════════════════════════════
#  CORE COMMANDS
# ══════════════════════════════════════════════════════════════════════════════
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Deep-link support: /start chess_<roomcode> joins a chess room directly
    if context.args and context.args[0].startswith("chess_"):
        room_code = context.args[0].replace("chess_", "", 1).upper()
        user = update.message.from_user
        name = f"@{user.username}" if user.username else user.full_name
        ok, res = await _chess_api("POST", "/api/room/join", json={"room_code": room_code, "uid": user.id, "name": name})
        if ok:
            await update.message.reply_text(
                "♟️ *Joined the chess room!* Tap below to play:",
                reply_markup=_chess_open_board_button(res["game_id"], user.id, name), parse_mode="Markdown")
            return
    await update.message.reply_text(
        "👋 I'm *Aira* – your ultimate Telegram bot!\n\n"
        "🎮 Challenges | 🐾 OWO Hunt | 🎰 Casino\n"
        "😴 AFK System | 🛡️ Admin Tools | 💬 Chat\n"
        "📅 Daily Rewards | 🤝 Trade | 🍅 Pomodoro\n"
        "🎭 Truth & Dare | 🏆 Auctions | ⚔️ PVP | ♟️ Chess\n\n"
        "*/help* – Full command list ⚡",parse_mode="Markdown")

async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 *Aira v8 – Command List*\n━━━━━━━━━━━━━\n"
        "*🎮 Challenges*\n"
        "/challenge – Start challenge (also auto-fires every 5-6 min!)\n"
        "/hint – Active challenge hint\n"
        "/skipit – Skip challenge (admin)\n\n"
        "*💰 Economy*\n"
        "/wallet – Your balance & stats\n"
        "/daily – Daily reward\n"
        "/give – Reply + /give <amount>\n"
        "/leaderboard – Global/Weekly/Today\n"
        "/streak – Your win streak\n"
        "/shop – Buy perks\n"
        "/settitle – Set member tag\n"
        "/pinit – Pin a message\n\n"
        "*🐾 OWO*\n"
        "/hunt – Catch an animal\n"
        "/zoo – Your animal collection\n"
        "/sell all | /sell <name>\n"
        "/gemshop – Buy weapons\n"
        "/owoprofile – OWO stats\n"
        "/autohunt – Auto hunt toggle\n"
        "/battle – Fight wild animal\n"
        "/setteam – Set PVP team\n"
        "/pvp – Challenge to battle\n"
        "/topanimals – Zoo leaderboard\n\n"
        "*🎰 Casino*\n"
        "/cf <amount> heads/tails\n"
        "/s <amount> – Slots\n"
        "/dice <amount> <1-6>\n"
        "/pray – Boost luck 10min\n\n"
        "*🎭 Truth & Dare*\n"
        "/truth – Instant truth question\n"
        "/dare – Instant dare\n"
        "/tnd – Create a multiplayer lobby\n"
        "/tnd join | start | end\n\n"
        "*♟️ Chess*\n"
        "/chess – Play vs bot / friend / random, rated\n"
        "/chessjoin <code> – Join a friend's room\n"
        "/chessrating – Your rating & record\n"
        "/chessleaderboard – Top rated players\n\n"
        "*🤝 Social*\n"
        "/trade – Reply + /trade <amount>\n"
        "/tradeitem – Trade animal/weapon\n"
        "/auction – Auction house\n"
        "/ask <question> – Chat with Aira\n"
        "/pomodoro <mins> – Focus timer\n"
        "!status <reason> – Set AFK\n\n"
        "*🏆 Stats*\n"
        "/badges – Badge collection\n"
        "/stats – Full stats\n"
        "/inventory – Items & buffs\n"
        "/equipweapon – Switch weapon\n\n"
        "*🛡️ Admin*\n"
        "/ban /unban /kick /timeout\n"
        "/untimeout /purge /warn /warns\n"
        "/clearwarns /setwelcome /setbye\n"
        "/forgewar – 2× rewards 1hr\n\n"
        "💬 *Just mention or reply to me to chat!*",parse_mode="Markdown")

async def cmd_challenge(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id=update.message.chat_id; group=get_group_db(chat_id)
    if group["active_challenge"]: await update.message.reply_text("⚠️ Challenge already running!"); return
    last=group.get("last_challenge_time")
    if last:
        elapsed=(datetime.now()-datetime.fromisoformat(last)).total_seconds()
        if elapsed<CHALLENGE_COOLDOWN:
            await update.message.reply_text(f"⏳ Cooldown! Next in *{int(CHALLENGE_COOLDOWN-elapsed)}s*.",parse_mode="Markdown"); return
    await post_challenge(context,chat_id)

async def cmd_wallet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user=update.message.from_user; db=_get_db()
    u=db["users"].find_one({"_id":str(user.id)}) or {}; u.pop("_id",None)
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
        f"💼 *{user.full_name}'s Wallet*{tag_line}{exp_line}{afk_line}\n━━━━━━━━━━━━━\n"
        f"🪙 Coins: *{u.get('coins',0)}* | 💎 Gems: *{u.get('gems',0)}*\n"
        f"🐾 OWO: *{u.get('owo',0)}* | 🏹 Weapon: {weapon['name']}\n"
        f"🏆 Wins: *{u.get('wins',0)}* | 📅 Weekly: *{u.get('weekly_wins',0)}*\n"
        f"🔥 Streak: *{u.get('streak',0)}* | ⭐ Best: *{u.get('best_streak',0)}*\n"
        f"⬆️ Level: *{u.get('level',1)}* | XP: *{u.get('xp',0)}*\n"
        f"🏅 Badges: *{len(u.get('badges',[]))}*",parse_mode="Markdown")

async def cmd_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user=update.message.from_user; db=_get_db()
    u=db["users"].find_one({"_id":str(user.id)}) or {}; u.pop("_id",None)
    zoo_count=sum(z.get("count",1) for z in u.get("animals",[]))
    await update.message.reply_text(
        f"📊 *{user.full_name}'s Stats*\n━━━━━━━━━━━━━\n"
        f"🪙 Coins: *{u.get('coins',0)}* | 💎 Gems: *{u.get('gems',0)}*\n"
        f"💎 Total Earned: *{u.get('total_coins_ever',0)}*\n"
        f"🏆 Wins: *{u.get('wins',0)}* | 📅 Weekly: *{u.get('weekly_wins',0)}*\n"
        f"🔥 Best Streak: *{u.get('best_streak',0)}*\n"
        f"⬆️ Level: *{u.get('level',1)}* (XP: {u.get('xp',0)})\n"
        f"🐾 OWO: *{u.get('owo',0)}* | 🎯 Hunts: *{u.get('hunts',0)}*\n"
        f"🦁 Animals: *{zoo_count}* | 🎰 Casino Wins: *{u.get('casino_wins',0)}*\n"
        f"📅 Daily Streak: *{u.get('daily_streak',0)}* days\n"
        f"🏅 Badges: *{len(u.get('badges',[]))}*",parse_mode="Markdown")

async def cmd_leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db=_get_db(); today_str=datetime.now().date().isoformat()
    medals=["🥇","🥈","🥉","4️⃣","5️⃣","6️⃣","7️⃣","8️⃣","9️⃣","🔟"]
    def board(title,cursor,value_key,count_key):
        lines=[f"{title}\n━━━━━━━━━━━━━"]; i=0
        for doc in cursor:
            name=doc.get("full_name","?"); tag=doc.get("title")
            t=f" 👑{tag}" if tag else ""
            lines.append(f"{medals[i]} {name}{t}\n   🪙{doc.get(value_key,0)} | 🏆{doc.get(count_key,0)}W")
            i+=1
        if i==0: lines.append("No players yet!")
        return "\n".join(lines)
    context.bot_data["lb_global"]=board("🌍 *GLOBAL*",db["users"].find().sort("total_coins_ever",-1).limit(10),"total_coins_ever","wins")
    context.bot_data["lb_weekly"]=board("📅 *WEEKLY*",db["users"].find().sort("weekly_wins",-1).limit(10),"coins","weekly_wins")
    context.bot_data["lb_today"]=board("🕐 *TODAY*",db["users"].find({"today_date":today_str}).sort("today_wins",-1).limit(10),"coins","today_wins")
    context.bot_data["lb_owo"]=board("🐾 *OWO HUNTERS*",db["users"].find().sort("owo",-1).limit(10),"owo","hunts")
    kb=[[InlineKeyboardButton("🌍 Global",callback_data="lb_global"),InlineKeyboardButton("📅 Weekly",callback_data="lb_weekly")],
        [InlineKeyboardButton("🕐 Today",callback_data="lb_today"),InlineKeyboardButton("🐾 OWO",callback_data="lb_owo")]]
    await update.message.reply_text("🏆 *LEADERBOARD*",reply_markup=InlineKeyboardMarkup(kb),parse_mode="Markdown")

async def handle_leaderboard_tab(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query=update.callback_query; await query.answer()
    text=context.bot_data.get(query.data,"No data!")
    kb=[[InlineKeyboardButton("🌍 Global",callback_data="lb_global"),InlineKeyboardButton("📅 Weekly",callback_data="lb_weekly")],
        [InlineKeyboardButton("🕐 Today",callback_data="lb_today"),InlineKeyboardButton("🐾 OWO",callback_data="lb_owo")]]
    await query.edit_message_text(text,reply_markup=InlineKeyboardMarkup(kb),parse_mode="Markdown")

async def cmd_streak(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user=update.message.from_user; db=_get_db()
    u=db["users"].find_one({"_id":str(user.id)}) or {}; u.pop("_id",None)
    fire="🔥"*min(u.get("streak",0),10)
    await update.message.reply_text(f"{fire}\n*{user.full_name}'s Streak*\n━━━━━━━━━━━━━\nCurrent: *{u.get('streak',0)}* | Best: *{u.get('best_streak',0)}*\nBonus/win: *+{u.get('streak',0)*STREAK_BONUS}* coins",parse_mode="Markdown")

async def cmd_badges(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user=update.message.from_user; db=_get_db()
    u=db["users"].find_one({"_id":str(user.id)}) or {}; u.pop("_id",None)
    if not u.get("badges"): await update.message.reply_text("No badges yet! Win challenges and hunt! 🏅"); return
    lines=[f"🏅 *{user.full_name}'s Badges*\n━━━━━━━━━━━━━"]
    for k in u["badges"]:
        if k in BADGES: n,d=BADGES[k]; lines.append(f"{n}\n  _{d}_")
    lines.append(f"\n🔒 *{len([k for k in BADGES if k not in u['badges']])} locked*")
    await update.message.reply_text("\n".join(lines),parse_mode="Markdown")

async def cmd_hint(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id=update.message.chat_id
    ch=get_group_db(chat_id).get("active_challenge")
    if not ch: await update.message.reply_text("No active challenge!"); return
    await update.message.reply_text(f"💡 *Hint:* _{ch['hint']}_",parse_mode="Markdown")

async def cmd_shop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user=update.message.from_user; data=load_data()
    u=get_user(data,user.id,user.username,user.full_name); save_data(data)
    kb=[[InlineKeyboardButton(f"{v['name']} – {v['cost']} 🪙",callback_data=f"buy_{k}")] for k,v in SHOP_ITEMS.items()]
    await update.message.reply_text(f"🛒 *FORGE SHOP*\n━━━━━━━━━━━━━\nBalance: *{u['coins']}* 🪙\nTap to buy:",
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
    elif key=="custom_title": u["title_purchased"]=True;u["title_chat_id"]=query.message.chat_id;msg+="\n\n👑 Use `/settitle YourTitle`!"
    elif key=="choose_challenge":
        g=get_group(data,query.message.chat_id);g["pending_chooser"]=user.username or user.full_name;msg+="\n\n🎯 Next /challenge is yours!"
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
    elif key=="half_cooldown": u["half_cooldown_expiry"]=(datetime.now()+timedelta(minutes=20)).isoformat();msg+="\n\n⚡ All cooldowns halved for 20 minutes!"
    elif key=="cheap_autohunt": 
        u["cheap_autohunt"] = True
        u["cheap_autohunt_expiry"] = (datetime.now() + timedelta(hours=1)).isoformat()
        msg += "\n\n🤖 Budget AutoHunt active for 1 hour!"
    save_data(data); await query.edit_message_text(msg,parse_mode="Markdown")

async def cmd_settitle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user=update.message.from_user; chat_id=update.message.chat_id
    if not context.args: await update.message.reply_text("Usage: `/settitle Title`",parse_mode="Markdown"); return
    title=" ".join(context.args)[:16]; data=load_data()
    u=get_user(data,user.id,user.username,user.full_name)
    if not u.get("title_purchased"): await update.message.reply_text("❌ Buy *Custom Member Tag* from /shop first!",parse_mode="Markdown"); return
    for job in context.job_queue.get_jobs_by_name(f"title_expire_{user.id}"): job.schedule_removal()
    success,mode=await set_member_tag(context.bot,chat_id,user.id,title)
    if not success:
        u["title_purchased"]=False; save_data(data)
        await update.message.reply_text("❌ *Failed!* Make sure Aira is admin. Purchase refunded!",parse_mode="Markdown"); return
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
    if not update.message.reply_to_message: await update.message.reply_text("↩️ Reply to a message first!"); return
    try:
        await context.bot.pin_chat_message(chat_id,update.message.reply_to_message.message_id)
        if not is_adm: u["pin_token"]=False;save_data(data)
        name=f"@{user.username}" if user.username else user.full_name
        await update.message.reply_text(f"📌 *{name}* pinned a message!",parse_mode="Markdown")
    except TelegramError as e:
        await update.message.reply_text(f"❌ Aira needs Pin Messages permission!\n_{e}_",parse_mode="Markdown")

async def cmd_skipit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id=update.message.chat_id
    member=await context.bot.get_chat_member(chat_id,update.message.from_user.id)
    if member.status not in ("administrator","creator"): await update.message.reply_text("⚠️ Admins only!"); return
    group=get_group_db(chat_id)
    if not group.get("active_challenge"): await update.message.reply_text("No challenge to skip!"); return
    group["active_challenge"]=None; save_group_db(chat_id,group)
    for job in context.job_queue.get_jobs_by_name(f"expire_{chat_id}"): job.schedule_removal()
    await update.message.reply_text("⏭️ Skipped! Starting new challenge...")
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
    ds=ds+1 if last==yest else 1
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
        f"💰 +*{total}* coins _{label}_{bl}\n🏦 Balance: *{u['coins']}*",parse_mode="Markdown")

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
    await update.message.reply_text(f"🎁 *{sname}* gave *{amount}* 🪙 to *{tname}*!\n{sname}: *{s['coins']}* | {tname}: *{t['coins']}*",parse_mode="Markdown")

async def cmd_hunt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user=update.message.from_user
    result=await do_hunt(context.bot,update.message.chat_id,user.id,user.username,user.full_name)
    await update.message.reply_text(result,parse_mode="Markdown")

async def cmd_zoo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user=update.message.from_user; db=_get_db()
    u=db["users"].find_one({"_id":str(user.id)}) or {}; u.pop("_id",None)
    zoo=u.get("animals",[])
    if not zoo: await update.message.reply_text("Zoo empty! Use /hunt. 🎯"); return
    lines=[f"🦁 *{user.full_name}'s Zoo*\n━━━━━━━━━━━━━"]
    order=list(RARITY_WEIGHTS.keys())
    for a in sorted(zoo,key=lambda x:order.index(x["rarity"]) if x["rarity"] in order else 99,reverse=True):
        icon=RARITY_COLORS.get(a["rarity"],"⬜")
        lines.append(f"{a['name']} {icon}*{a['rarity']}* ×{a.get('count',1)}")
    lines.append(f"\n🐾 OWO: *{u.get('owo',0)}* | 💎 Gems: *{u.get('gems',0)}*")
    await update.message.reply_text("\n".join(lines),parse_mode="Markdown")

async def cmd_inventory(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user=update.message.from_user; db=_get_db(); uid=str(user.id)
    doc=db["users"].find_one({"_id":uid})
    if not doc: await update.message.reply_text("No inventory yet!"); return
    current_weapon=doc.get("weapon","stick"); inv=doc.get("weapon_inventory",[])
    w_current=WEAPONS.get(current_weapon,WEAPONS["stick"])
    lines=[f"🎒 *{user.full_name}'s Inventory*\n━━━━━━━━━━━━━"]
    lines.append(f"🏹 *Equipped:* {w_current['name']}")
    if inv:
        lines.append("\n📦 *Stored Weapons:*")
        for wkey in inv:
            w=WEAPONS.get(wkey)
            if w: lines.append(f"  {w['name']} | ATK+{w['atk_bonus']} | Catch+{w['catch_bonus']}%")
        lines.append("\n_Use /equipweapon <name> to switch_")
    else: lines.append("\n📦 *Stored Weapons:* None")
    buffs=[]
    if doc.get("half_cooldown_expiry"):
        try:
            rem=(datetime.fromisoformat(doc["half_cooldown_expiry"])-datetime.now()).total_seconds()
            if rem>0: buffs.append(f"⚡ Cooldown Slash: *{int(rem//60)}m {int(rem%60)}s* left")
        except: pass
    if doc.get("owo_boost_expiry"):
        try:
            rem=(datetime.fromisoformat(doc["owo_boost_expiry"])-datetime.now()).total_seconds()
            if rem>0: buffs.append(f"🐾 Hunt Boost: *{int(rem//60)}m {int(rem%60)}s* left")
        except: pass
    if doc.get("shield_expiry"):
        try:
            rem=(datetime.fromisoformat(doc["shield_expiry"])-datetime.now()).total_seconds()
            if rem>0: buffs.append(f"🛡️ Shield: *{int(rem//60)}m {int(rem%60)}s* left")
        except: pass
    if doc.get("cheap_autohunt"): buffs.append("🤖 Budget AutoHunt: *Active*")
    if buffs:
        lines.append("\n✨ *Active Buffs:*")
        lines+=[f"  {b}" for b in buffs]
    await update.message.reply_text("\n".join(lines),parse_mode="Markdown")

async def cmd_equipweapon(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user=update.message.from_user
    if not context.args: await update.message.reply_text("Usage: `/equipweapon <name>`",parse_mode="Markdown"); return
    arg=" ".join(context.args).lower(); db=_get_db(); uid=str(user.id)
    doc=db["users"].find_one({"_id":uid})
    if not doc: await update.message.reply_text("No inventory found!"); return
    inv=doc.get("weapon_inventory",[])
    w_key=next((k for k in inv if arg in WEAPONS.get(k,{}).get("name","").lower()),None)
    if not w_key: await update.message.reply_text(f"❌ '{arg}' not in inventory! Check /inventory.",parse_mode="Markdown"); return
    current=doc.get("weapon","stick"); inv.remove(w_key)
    if current!="stick": inv.append(current)
    doc["weapon"]=w_key; doc["weapon_inventory"]=inv
    db["users"].replace_one({"_id":uid},doc,upsert=True)
    w=WEAPONS[w_key]
    await update.message.reply_text(f"✅ Equipped *{w['name']}*!\nATK+{w['atk_bonus']} | Catch+{w['catch_bonus']}%",parse_mode="Markdown")

async def cmd_owoprofile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user=update.message.from_user; db=_get_db()
    doc=db["users"].find_one({"_id":str(user.id)}) or {}; doc.pop("_id",None); u=doc
    zoo=u.get("animals",[]); total=sum(z.get("count",1) for z in zoo)
    legends=sum(z.get("count",1) for z in zoo if z.get("rarity")=="legendary")
    boost="⚡ Active" if (u.get("owo_boost_expiry") and datetime.fromisoformat(u["owo_boost_expiry"])>datetime.now()) else "None"
    weapon=WEAPONS.get(u.get("weapon","stick"),WEAPONS["stick"])
    cd=u.get("hunt_cooldown"); cd_line=""
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

AUTOHUNT_COST=10; AUTOHUNT_DURATION=3600; AUTOHUNT_INTERVAL=60

async def cmd_autohunt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user=update.message.from_user; db=_get_db(); uid=str(user.id)
    doc=db["users"].find_one({"_id":uid}) or {}
    doc.setdefault("auto_hunt",False); doc.setdefault("coins",0); doc.setdefault("cheap_autohunt",False)
    if doc.get("auto_hunt"):
        doc["auto_hunt"]=False; doc["auto_hunt_expiry"]=None
        db["users"].replace_one({"_id":uid},{"_id":uid,**doc},upsert=True)
        for job in context.job_queue.get_jobs_by_name(f"autohunt_{user.id}"): job.schedule_removal()
        for job in context.job_queue.get_jobs_by_name(f"autohunt_expire_{user.id}"): job.schedule_removal()
        await update.message.reply_text("🤖 Auto Hunt *OFF*.",parse_mode="Markdown"); return
    actual_cost=5 if doc.get("cheap_autohunt") else AUTOHUNT_COST
    min_coins=actual_cost*10
    if doc.get("coins",0)<min_coins:
        await update.message.reply_text(f"❌ Need *{min_coins}* 🪙 to start. You have *{doc.get('coins',0)}* 🪙",parse_mode="Markdown"); return
    expiry=(datetime.now()+timedelta(seconds=AUTOHUNT_DURATION)).isoformat()
    doc["auto_hunt"]=True; doc["auto_hunt_expiry"]=expiry
    db["users"].replace_one({"_id":uid},{"_id":uid,**doc},upsert=True)
    chat_id=update.message.chat_id
    context.job_queue.run_repeating(auto_hunt_job,interval=AUTOHUNT_INTERVAL,first=5,name=f"autohunt_{user.id}",chat_id=chat_id,data={"chat_id":chat_id,"user_id":user.id})
    context.job_queue.run_once(auto_hunt_expire,when=AUTOHUNT_DURATION,name=f"autohunt_expire_{user.id}",chat_id=chat_id,data={"chat_id":chat_id,"user_id":user.id})
    await update.message.reply_text(f"🤖 *Auto Hunt ON!*\n⏱️ 1 hour | 💸 {actual_cost} 🪙/hunt | Every {AUTOHUNT_INTERVAL}s\n_/autohunt to stop_",parse_mode="Markdown")

async def auto_hunt_job(context: ContextTypes.DEFAULT_TYPE):
    job_data = context.job.data; chat_id = job_data["chat_id"]; user_id = job_data["user_id"]
    db = _get_db(); uid = str(user_id)
    doc = db["users"].find_one({"_id": uid})
    
    if not doc or not doc.get("auto_hunt"): 
        context.job.schedule_removal(); return
    
    # Check Auto Hunt expiry
    expiry = doc.get("auto_hunt_expiry")
    if expiry:
        try:
            if datetime.fromisoformat(expiry) < datetime.now(): 
                doc["auto_hunt"] = False
                doc["auto_hunt_expiry"] = None
                db["users"].replace_one({"_id": uid}, {"_id": uid, **doc}, upsert=True)
                context.job.schedule_removal(); return
        except: pass

    # --- FIX: Cheap Autohunt Expiration Check ---
    cheap_expiry = doc.get("cheap_autohunt_expiry")
    if cheap_expiry:
        try:
            if datetime.fromisoformat(cheap_expiry) < datetime.now():
                doc["cheap_autohunt"] = False
                doc["cheap_autohunt_expiry"] = None
                db["users"].replace_one({"_id": uid}, {"_id": uid, **doc}, upsert=True)
        except: pass
    # ---------------------------------------------

    actual_cost = 5 if doc.get("cheap_autohunt") else AUTOHUNT_COST
    
    if doc.get("coins", 0) < actual_cost:
        doc["auto_hunt"] = False; doc["auto_hunt_expiry"] = None
        db["users"].replace_one({"_id": uid}, {"_id": uid, **doc}, upsert=True)
        context.job.schedule_removal()
        try: await context.bot.send_message(user_id, "🤖 *Auto Hunt stopped!* Not enough coins.", parse_mode="Markdown")
        except TelegramError: pass
        return
        
    doc["coins"] -= actual_cost
    db["users"].replace_one({"_id": uid}, {"_id": uid, **doc}, upsert=True)
    
    username = doc.get("username"); full_name = doc.get("full_name")
    result = await do_hunt(context.bot, chat_id, user_id, username, full_name)
    
    short_msg = result
    if "Caught" in result:
        try:
            line = [l for l in result.split("\n") if "Caught" in l][0]
            short_msg = f"🤖 *{full_name or username or 'Hunter'}* → {line.replace('Caught ','')}"
        except: short_msg = result.split("\n")[0]
        
    # --- UPDATE: Send to DM (user_id) instead of group (chat_id) ---
    try: await context.bot.send_message(user_id, short_msg, parse_mode="Markdown")
    except TelegramError: pass

async def auto_hunt_expire(context: ContextTypes.DEFAULT_TYPE):
    job_data=context.job.data; chat_id=job_data["chat_id"]; user_id=job_data["user_id"]
    db=_get_db(); uid=str(user_id); doc=db["users"].find_one({"_id":uid}) or {}
    doc["auto_hunt"]=False; doc["auto_hunt_expiry"]=None
    db["users"].replace_one({"_id":uid},{"_id":uid,**doc},upsert=True)
    for job in context.job_queue.get_jobs_by_name(f"autohunt_{user_id}"): job.schedule_removal()
    username=doc.get("username",""); name=f"@{username}" if username and username!="Unknown" else doc.get("full_name","Hunter")
    try: await context.bot.send_message(chat_id,f"⌛ *{name}'s Auto Hunt ended!* Type /autohunt to restart!",parse_mode="Markdown",message_thread_id=AIRA_THREAD_ID)
    except TelegramError: pass

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
    weapon=WEAPONS.get(u.get("weapon","stick"),WEAPONS["stick"]); enemy=random.choice(BATTLE_ENEMIES)
    php=50; ehp=enemy["hp"]; rounds=0
    while php>0 and ehp>0 and rounds<12:
        p_atk=random.randint(8+weapon["atk_bonus"]//2,20+weapon["atk_bonus"])
        e_atk=random.randint(int(enemy["atk"]*0.7),enemy["atk"])
        ehp-=p_atk; php-=e_atk; rounds+=1
    u["hunt_cooldown"]=(datetime.now()+timedelta(seconds=45)).isoformat()
    if php>0:
        reward=enemy["atk"]*3; gems_r=random.randint(2,8)
        u["coins"]+=reward; u["gems"]=u.get("gems",0)+gems_r; u["hunts"]=u.get("hunts",0)+1
        check_badges(u); save_data(data)
        await update.message.reply_text(f"⚔️ *BATTLE vs {enemy['name']}*\n{rounds} rounds | HP left: *{max(0,php)}*\n\n🏆 *Victory!* +{reward} 🪙 +{gems_r} 💎",parse_mode="Markdown")
    else:
        loss=random.randint(5,15); u["coins"]=max(0,u["coins"]-loss); save_data(data)
        await update.message.reply_text(f"⚔️ *BATTLE vs {enemy['name']}*\n{rounds} rounds\n\n💀 *Defeated!* -{loss} 🪙",parse_mode="Markdown")

async def cmd_forgewar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id=update.message.chat_id
    if not await is_admin(context.bot,chat_id,update.message.from_user.id):
        await update.message.reply_text("⚠️ Admins only!"); return
    group=get_group_db(chat_id)
    group["forge_war"]=True; group["forge_war_multiplier"]=2; save_group_db(chat_id,group)
    await update.message.reply_text("⚔️ *FORGE WAR!* All rewards ×2 for 1 hour! 🪙🔥",parse_mode="Markdown")
    context.job_queue.run_once(lambda ctx:asyncio.ensure_future(_end_forge_war(ctx,chat_id)),when=3600,name=f"fw_{chat_id}")

async def _end_forge_war(context,chat_id):
    group=get_group_db(chat_id); group["forge_war"]=False; group["forge_war_multiplier"]=1; save_group_db(chat_id,group)
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
        ("spy", cmd_spy),
        ("togglechallenge", cmd_toggle_challenge),
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
        ("chess",cmd_chess),("chessjoin",cmd_chessjoin),
        ("chessrating",cmd_chessrating),("chessleaderboard",cmd_chessleaderboard),
    ]
    for cmd,fn in handlers: app.add_handler(CommandHandler(cmd,fn))

    # Callback query handlers
    app.add_handler(CallbackQueryHandler(handle_shop_purchase, pattern="^buy_"))
    app.add_handler(CallbackQueryHandler(handle_leaderboard_tab, pattern="^lb_"))
    app.add_handler(CallbackQueryHandler(handle_gem_purchase, pattern="^gbuy_"))
    app.add_handler(PollAnswerHandler(handle_spy_vote)) # DELETE THIS
    app.add_handler(CallbackQueryHandler(handle_trade, pattern="^tacpt_|^tdecl_"))
    app.add_handler(CallbackQueryHandler(handle_pvp, pattern="^pvpacpt_|^pvpdecl_"))
    app.add_handler(CallbackQueryHandler(handle_item_trade, pattern="^tiacpt_|^tidecl_"))
    app.add_handler(CallbackQueryHandler(handle_tnd_choice, pattern="^tnd_(truth|dare)_"))
    app.add_handler(CallbackQueryHandler(handle_tnd_next, pattern="^tnd_next_"))
    app.add_handler(CallbackQueryHandler(handle_chess_callback, pattern="^chess_"))

    # Member join/leave
    app.add_handler(ChatMemberHandler(handle_member_update, ChatMemberHandler.CHAT_MEMBER))

    # Message handlers
    app.add_handler(MessageHandler(filters.PHOTO & ~filters.COMMAND, handle_message))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info("✅ Aira v8 running — chat + TnD fix + auto-challenge + chess enabled!")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
ENDOFFILE
