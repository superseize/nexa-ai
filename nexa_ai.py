# ===================== NEXA AI (ONLINE + OFFLINE OLLAMA, SINGLE FILE) =====================

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
import sqlite3, uuid, time, socket, requests

# ===================== CONFIG =====================
APP_NAME = "NEXA AI"
RATE_LIMIT_PER_MIN = 5

# -------- ONLINE AI (OpenAI) --------
USE_ONLINE_AI = True
OPENAI_API_KEY = ""        # <- اپنی OpenAI key یہاں ڈالیں
OPENAI_MODEL = "gpt-4o-mini"

# -------- OFFLINE AI (OLLAMA) --------
USE_OFFLINE_AI = False
OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "mistral"   # یا qwen2.5

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
 answer TEXT
)
""")
cur.execute("""
CREATE TABLE IF NOT EXISTS limits(
 session_id TEXT,
 last_time INTEGER,
 count INTEGER
)
""")
db.commit()

# ===================== INTERNET CHECK =====================
def internet_available():
    try:
        socket.create_connection(("8.8.8.8", 53), timeout=2)
        return True
    except:
        return False

# ===================== RATE LIMIT =====================
def allowed(session_id):
    now = int(time.time())
    row = cur.execute(
        "SELECT last_time,count FROM limits WHERE session_id=?",
        (session_id,)
    ).fetchone()

    if not row:
        cur.execute("INSERT INTO limits VALUES(?,?,?)", (session_id, now, 1))
        db.commit()
        return True

    last, count = row
    if now - last > 60:
        cur.execute(
            "UPDATE limits SET last_time=?,count=? WHERE session_id=?",
            (now,1,session_id)
        )
        db.commit()
        return True

    if count >= RATE_LIMIT_PER_MIN:
        return False

    cur.execute(
        "UPDATE limits SET count=count+1 WHERE session_id=?",
        (session_id,)
    )
    db.commit()
    return True

# ===================== LANGUAGE DETECT =====================
def detect_lang(text):
    for ch in text:
        if '\u0600' <= ch <= '\u06FF':
            return "ur"
    return "en"

# ===================== OFFLINE AI (OLLAMA) =====================
def offline_ai(question):
    try:
        r = requests.post(
            OLLAMA_URL,
            json={
                "model": OLLAMA_MODEL,
                "prompt": question,
                "stream": False
            },
            timeout=60
        )
        return r.json().get("response", "").strip()
    except:
        return "⚠️ Offline AI not available"

# ===================== ONLINE AI (OPENAI) =====================
def online_ai(question):
    from openai import OpenAI
    client = OpenAI(api_key=OPENAI_API_KEY)
    res = client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=[{"role":"user","content":question}]
    )
    return res.choices[0].message.content

# ===================== AI ROUTER =====================
def ai_answer(question):
    lang = detect_lang(question)

    if USE_ONLINE_AI and internet_available() and OPENAI_API_KEY:
        try:
            ans = online_ai(question)
        except:
            ans = offline_ai(question)
    else:
        ans = offline_ai(question)

    if lang == "ur":
        return f"🤖 {APP_NAME}\n\n{ans}"
    return ans

# ===================== SESSION =====================
def get_sid(req: Request):
    return req.cookies.get("sid") or str(uuid.uuid4())

# ===================== UI =====================
HTML = """
<!DOCTYPE html>
<html>
<head>
<title>NEXA AI</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<link rel="manifest" href="/manifest.json">
<style>
body{margin:0;background:#020617;color:#fff;font-family:Arial}
header{padding:15px;font-weight:bold}
#chat{padding:10px;height:70vh;overflow:auto}
.msg{background:#1e293b;padding:10px;margin:10px;border-radius:10px}
.user{color:#38bdf8}
.ai{color:#a7f3d0}
.controls{position:fixed;bottom:0;width:100%;background:#020617;padding:10px}
input{width:65%;padding:10px;border-radius:8px;border:none}
button{padding:10px;border:none;border-radius:8px}
</style>
</head>
<body>

<header>NEXA AI </header>
<div id="chat"></div>

<div class="controls">
<input id="q" placeholder="Ask in Urdu or English..." />
<button onclick="send()">Send</button>
<button onclick="clearAll()">Clear</button>
</div>

<script>
async function load(){
 let r=await fetch("/history");
 let d=await r.json();
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
async function send(){
 let q=document.getElementById("q").value;
 if(!q)return;
 let r=await fetch("/ask",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({q:q})});
 let d=await r.json();
 if(d.error) alert(d.error);
 document.getElementById("q").value="";
 load();
}
async function clearAll(){
 await fetch("/clear",{method:"POST"});
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
        "SELECT question,answer FROM chats WHERE session_id=?",
        (sid,)
    ).fetchall()
    return [{"q":r[0],"a":r[1]} for r in rows]

@app.post("/ask")
async def ask(req: Request):
    sid = get_sid(req)
    if not allowed(sid):
        return {"error":"Rate limit exceeded"}
    q = (await req.json())["q"]
    a = ai_answer(q)
    cur.execute(
        "INSERT INTO chats(session_id,question,answer) VALUES(?,?,?)",
        (sid,q,a)
    )
    db.commit()
    return {"answer":a}

@app.post("/clear")
def clear(req: Request):
    sid = get_sid(req)
    cur.execute("DELETE FROM chats WHERE session_id=?", (sid,))
    db.commit()
    return {"ok":True}

# ===================== PWA =====================
@app.get("/manifest.json")
def manifest():
    return {
        "name":"NEXA AI",
        "short_name":"NEXA",
        "start_url":"/",
        "display":"standalone",
        "background_color":"#020617",
        "theme_color":"#020617"
    }

# ===================== END =====================
