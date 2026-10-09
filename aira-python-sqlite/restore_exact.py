import sqlite3
import json

exact_animals = [
    {"name": "🐍 Icchadhari Moonie", "rarity": "limited", "count": 6},
    {"name": "♠️ Spade", "rarity": "Extreme", "count": 49},
    {"name": "🐉 Dragon", "rarity": "legendary", "count": 89},
    {"name": "🔱 Leviathan", "rarity": "legendary", "count": 91},
    {"name": "🦄 Unicorn", "rarity": "legendary", "count": 62},
    {"name": "⭐ Phoenix", "rarity": "legendary", "count": 87},
    {"name": "🐘 Elephant", "rarity": "epic", "count": 34},
    {"name": "🦏 Rhino", "rarity": "epic", "count": 36},
    {"name": "🐋 Whale", "rarity": "epic", "count": 26},
    {"name": "🦍 Gorilla", "rarity": "epic", "count": 26},
    {"name": "🦬 Bison", "rarity": "epic", "count": 31},
    {"name": "🦌 Deer", "rarity": "rare", "count": 69},
    {"name": "🦁 Lion", "rarity": "rare", "count": 69},
    {"name": "🐯 Tiger", "rarity": "rare", "count": 75},
    {"name": "🐻 Bear", "rarity": "rare", "count": 75},
    {"name": "🦈 Shark", "rarity": "rare", "count": 51},
    {"name": "🐗 Boar", "rarity": "uncommon", "count": 135},
    {"name": "🦅 Eagle", "rarity": "uncommon", "count": 104},
    {"name": "🦊 Fox", "rarity": "uncommon", "count": 118},
    {"name": "🦝 Raccoon", "rarity": "uncommon", "count": 106},
    {"name": "🐺 Wolf", "rarity": "uncommon", "count": 127},
    {"name": "🐶 Dog", "rarity": "common", "count": 211},
    {"name": "🐱 Cat", "rarity": "common", "count": 205},
    {"name": "🐭 Mouse", "rarity": "common", "count": 214},
    {"name": "🐰 Rabbit", "rarity": "common", "count": 233},
    {"name": "🐦 Bird", "rarity": "common", "count": 209}
]

conn = sqlite3.connect("aira.db")
cur = conn.cursor()

cur.execute("SELECT doc FROM users WHERE _id = '8607105155';")
row = cur.fetchone()
if row:
    doc = json.loads(row[0])
else:
    doc = {"_id": "8607105155"}

# Set exact data
doc["gems"] = 98755
doc["coins"] = 387781
doc["total_coins_ever"] = max(doc.get("total_coins_ever", 0), 8642948)
doc["animals"] = exact_animals
doc["battle_team"] = ["♠️ Spade", "🐉 Dragon", "🐍 Icchadhari Moonie"]

cur.execute("UPDATE users SET doc = ? WHERE _id = '8607105155';", (json.dumps(doc, ensure_ascii=False),))
conn.commit()
conn.close()
print("SUCCESS: Exactly restored 98,755 gems, 387k coins, and all 26 animal species!")
