import sqlite3,json,os
from fastapi import FastAPI,Request,Form
from fastapi.responses import HTMLResponse,RedirectResponse
from starlette.middleware.sessions import SessionMiddleware
app=FastAPI()
app.add_middleware(SessionMiddleware,secret_key="ghevar")
DB=os.path.expanduser("~/aira-bot/aira-python-sqlite/aira.db")
OWNERS={"yash":{"n":"Yash","p":"ghevar"},"moonie":{"n":"Moonie","p":"nashta"}}
@app.get("/")
def h(r:Request):
 return HTMLResponse("<form method=post action=/login><h3>Aira Godmode</h3><select name=a><option value=yash>Yash</option><option value=moonie>Moonie</option></select><input type=password name=p placeholder=Passphrase><button>Login</button></form>")
@app.post("/login")
def l(r:Request,a:str=Form(...),p:str=Form(...)):
 o=OWNERS.get(a)
 if o and (p==o["p"] or p in ["ghevar","nashta"]):
  r.session["u"]=o
  return RedirectResponse("/dash",302)
 return HTMLResponse("Denied",400)
@app.get("/dash")
def d(r:Request,s:str=None):
 if not r.session.get("u"): return RedirectResponse("/")
 conn=sqlite3.connect(DB); doc=""
 if s:
  row=conn.cursor().execute("SELECT doc FROM users WHERE _id=?",(s.strip(),)).fetchone()
  if row: doc=row[0]
 conn.close()
 return HTMLResponse(f"<h3>Dual Admin: {r.session['u']['n']}</h3><a href=/logout>Logout</a><br><form><input name=s value='{s or ""}' placeholder=ID><button>Search</button></form><form method=post action=/up><input type=hidden name=uid value='{s or ""}'><textarea name=raw rows=12 cols=60>{doc}</textarea><br><button>Save</button></form>")
@app.get("/logout")
def lo(r:Request): r.session.clear(); return RedirectResponse("/")
@app.post("/up")
def u(r:Request,uid:str=Form(...),raw:str=Form(...)):
 if not r.session.get("u"): return RedirectResponse("/")
 conn=sqlite3.connect(DB); conn.execute("UPDATE users SET doc=? WHERE _id=?",(json.dumps(json.loads(raw),ensure_ascii=False),str(uid))); conn.commit(); conn.close()
 return RedirectResponse(f"/dash?s={uid}",302)
