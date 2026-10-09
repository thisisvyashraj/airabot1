import sqlite3, glob, json, re

files = glob.glob("aira.db*")
best_doc = None
max_coins = -1

for fn in files:
    try:
        with open(fn, "rb") as f:
            b = f.read()
        for m in re.finditer(b'\\{"_id"\\s*:\\s*"8607105155"', b):
            start = m.start()
            chunk = b[start:start+12000]
            depth = 0
            curr = []
            for byte in chunk:
                curr.append(byte)
                if byte == ord('{'):
                    depth += 1
                elif byte == ord('}'):
                    depth -= 1
                    if depth == 0:
                        try:
                            s = bytes(curr).decode('utf-8', errors='ignore')
                            obj = json.loads(s)
                            coins = int(obj.get("coins", 0))
                            if coins > 300000:
                                anims = obj.get("animals", [])
                                if len(anims) > 0:
                                    best_doc = obj
                                    break
                                elif coins > max_coins:
                                    best_doc = obj
                                    max_coins = coins
                        except:
                            pass
            if best_doc and len(best_doc.get("animals", [])) > 0:
                break
    except:
        pass
    if best_doc and len(best_doc.get("animals", [])) > 0:
        break
if best_doc:
    conn = sqlite3.connect("aira.db")
    c = conn.cursor()
    best_doc["_id"] = "8607105155"
    raw_json = json.dumps(best_doc)
    c.execute("UPDATE users SET doc = ? WHERE _id = ?", (raw_json, "8607105155"))
    conn.commit()
    conn.close()
    print("--- RECOVERY SUCCESSFUL ---")
    print("Coins:", best_doc.get("coins"))
    print("Animals:", len(best_doc.get("animals", [])))
    print("Gems:", best_doc.get("gems"))
    print("Weapon:", best_doc.get("weapon"))
    print("Hunts:", best_doc.get("hunts"))
else:
    print("FAILED: No document with animals found.")
