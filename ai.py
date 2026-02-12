# ===================== NEXA AI (RENDER DEPLOY READY) =====================

import os, sqlite3, uuid, time
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from openai import OpenAI

# ===================== CONFIG =====================
APP_NAME = "NEXA AI"
MODEL_NAME = "gpt-4o-mini"   # free tier compatible
RATE_LIMIT_PER_MIN = 15

# ===================== APP =====================
app = FastAPI(title=APP_NAME)

# ===================== DATABASE =====================
db = sqlite3.connect("nexa_ai.db", check_same_thread=False)
cur = db.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS chats(
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 session_id TEXT,
 question TEXT,
 answer TEXT,
 ts INTEGER
)
""")

cur.execute("""
CREATE TABLE IF NOT EXISTS limits(
 session_id TEXT PRIMARY KEY,
 last_time INTEGER,
 count INTEGER
)
""")
db.commit()

# ===================== SESSION =====================
def get_sid(req: Request):
    return req.cookies.get("sid") or str(uuid.uuid4())

# ===================== RATE LIMIT =====================
def allowed(sid):
    now = int(time.time())
    row = cur.execute(
        "SELECT last_time,count FROM limits WHERE session_id=?",
        (sid,)
    ).fetchone()

    if not row:
        cur.execute("INSERT INTO limits VALUES(?,?,?)", (sid, now, 1))
        db.commit()
        return True

    last, count = row

    if now - last > 60:
        cur.execute(
            "UPDATE limits SET last_time=?,count=? WHERE session_id=?",
            (now, 1, sid)
        )
        db.commit()
        return True

    if count >= RATE_LIMIT_PER_MIN:
        return False

    cur.execute(
        "UPDATE limits SET count=count+1 WHERE session_id=?",
        (sid,)
    )
    db.commit()
    return True

# ===================== LANGUAGE DETECT =====================
def detect_language(text: str) -> str:
    for ch in text:
        if '\u0600' <= ch <= '\u06FF':
            return "urdu"
    if any(w in text.lower() for w in ["kya","hai","ka","ki","ap","tum"]):
        return "roman"
    return "english"

# ===================== ONLINE AI =====================
def online_ai(question: str) -> str:
    key = os.getenv("OPENAI_API_KEY")
    if not key:
        return "API key not set on server."

    lang = detect_language(question)

    system_prompt = {
        "english": "Reply in clear English.",
        "urdu": "جواب اردو میں دیں۔",
        "roman": "Roman Urdu mein jawab dein."
    }[lang]

    client = OpenAI(api_key=key)

    res = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": question}
        ]
    )

    return res.choices[0].message.content.strip()

# ===================== UI =====================
HTML = """
<!DOCTYPE html>
<html>
<head>
<title>NEXA AI</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
body{margin:0;font-family:Arial;background:#020617;color:#fff}
header{display:flex;justify-content:space-between;padding:15px}
#chat{padding:10px;height:70vh;overflow:auto}
.msg{background:#1e293b;margin:10px;padding:10px;border-radius:10px}
.user{color:#38bdf8}
.ai{color:#a7f3d0}
.controls{position:fixed;bottom:0;width:100%;background:#020617;padding:10px}
input{width:65%;padding:10px;border-radius:8px;border:none}
button{padding:10px;border:none;border-radius:8px}
</style>
</head>
<body>

<header>
<span>NEXA AI</span>
</header>

<div id="chat"></div>

<div class="controls">
<input id="q" placeholder="Ask anything..." />
<button onclick="send()">Send</button>
</div>

<script>
function render(d){
 let c=document.getElementById("chat");
 c.innerHTML="";
 d.forEach(x=>{
  c.innerHTML+=`
   <div class="msg">
    <div class="user">You: ${x.q}</div>
    <div class="ai">AI: ${x.a}</div>
   </div>`;
 });
 c.scrollTop=c.scrollHeight;
}

async function load(){
 let r=await fetch("/history");
 render(await r.json());
}

async function send(){
 let q=document.getElementById("q").value;
 if(!q)return;

 await fetch("/ask",{
  method:"POST",
  headers:{"Content-Type":"application/json"},
  body:JSON.stringify({q:q})
 });

 document.getElementById("q").value="";
 load();
}

load();
</script>
</body>
</html>
"""

# ===================== ROUTES =====================
@app.get("/", response_class=HTMLResponse)
def home(req: Request):
    sid = get_sid(req)
    r = HTMLResponse(HTML)
    r.set_cookie("sid", sid)
    return r

@app.get("/history")
def history(req: Request):
    sid = get_sid(req)
    rows = cur.execute(
        "SELECT question,answer FROM chats WHERE session_id=? ORDER BY ts",
        (sid,)
    ).fetchall()
    return [{"q":r[0],"a":r[1]} for r in rows]

@app.post("/ask")
async def ask(req: Request):
    sid = get_sid(req)

    if not allowed(sid):
        return JSONResponse({"error":"Rate limit exceeded"})

    q = (await req.json())["q"]
    a = online_ai(q)

    cur.execute(
        "INSERT INTO chats(session_id,question,answer,ts) VALUES(?,?,?,?)",
        (sid,q,a,int(time.time()))
    )
    db.commit()

    return {"answer":a}

# ===================== END =====================
