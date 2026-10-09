import sqlite3, json

conn = sqlite3.connect("aira.db")
c = conn.cursor()
c.execute("SELECT doc FROM users WHERE _id = '8607105155'")
doc = json.loads(c.fetchone()[0])

# Restore missing stats & gems
doc["gems"] = 35000
doc["hunts"] = 8500
doc["level"] = 185
doc["xp"] = 37000

# Restore weapons
doc["weapon"] = "mace"
doc["weapon_levels"] = {"mace": 5, "dragonblade": 3}
doc["weapon_inventory"] = ["dragonblade", "laser", "mace"]

# Restore animals & battle team
doc["battle_team"] = ["♠️ Spade", "♠️ Spade", "🐍 Icchadhari Moonie"]
doc["animals"] = [
    {"name": "♠️ Spade", "rarity": "Extreme", "count": 15},
    {"name": "🐍 Icchadhari Moonie", "rarity": "limited", "count": 6},
    {"name": "🦄⭐ Celestial Unicorn", "rarity": "legendary", "count": 1, "evolved": True},
    {"name": "🐲⭐ Elder Dragon", "rarity": "legendary", "count": 1, "evolved": True},
    {"name": "🐱 Cat", "rarity": "common", "count": 45},
    {"name": "🐶 Dog", "rarity": "common", "count": 40},
    {"name": "🐭 Mouse", "rarity": "common", "count": 50},
    {"name": "🦊 Fox", "rarity": "uncommon", "count": 22},
    {"name": "🦅 Eagle", "rarity": "uncommon", "count": 25},
    {"name": "🐘 Elephant", "rarity": "epic", "count": 5},
    {"name": "🐋 Whale", "rarity": "epic", "count": 4}
]

# Save to database
c.execute("UPDATE users SET doc = ? WHERE _id = '8607105155'", (json.dumps(doc, ensure_ascii=False),))
conn.commit()
conn.close()
print("Success! Animals, Gems, and Weapons Restored.")
