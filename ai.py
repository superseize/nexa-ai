# ===================== NEXA AI (DUAL AI + WATERMARK) =====================

import os, sqlite3, uuid, time, requests
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse

# ===================== CONFIG =====================
APP_NAME = "NEXA AI"
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

# ===================== AI SYSTEM =====================
def online_ai(question: str) -> str:

    # ---------- OpenRouter ----------
    try:
        OPENROUTER_KEY = os.getenv("OPENROUTER_API_KEY")

        if OPENROUTER_KEY:
            headers = {
                "Authorization": f"Bearer {OPENROUTER_KEY}",
                "Content-Type": "application/json"
            }

            data = {
                "model": "openai/gpt-3.5-turbo",
                "messages": [{"role": "user", "content": question}]
            }

            r = requests.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers=headers,
                json=data,
                timeout=10
            )

            if r.status_code == 200:
                return r.json()["choices"][0]["message"]["content"]

    except:
        pass

    # ---------- HuggingFace Fallback ----------
    try:
        API_URL = "https://api-inference.huggingface.co/models/google/flan-t5-base"

        r = requests.post(API_URL, json={"inputs": question}, timeout=15)

        if r.status_code == 200:
            data = r.json()
            if isinstance(data, list):
                return data[0]["generated_text"]

        return "⚠ Model busy. Try again."

    except Exception as e:
        return f"⚠ AI error: {str(e)}"

# ===================== UI =====================
HTML = """
<!DOCTYPE html>
<html>
<head>
<title>NEXA AI</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
body{
 margin:0;
 font-family:Arial;
 background:#020617;
 color:#fff;
 overflow:hidden;
}

/* Watermark */
body::before{
 content:"ISHTIAQ AHMAD MAGRAY";
 position:fixed;
 top:50%;
 left:50%;
 transform:translate(-50%, -50%) rotate(-30deg);
 font-size:60px;
 color:rgba(255,255,255,0.05);
 white-space:nowrap;
 pointer-events:none;
 z-index:0;
}

header{
 display:flex;
 justify-content:space-between;
 padding:15px;
 position:relative;
 z-index:2;
}

#chat{
 padding:10px;
 height:70vh;
 overflow:auto;
 position:relative;
 z-index:2;
}

.msg{
 background:#1e293b;
 margin:10px;
 padding:10px;
 border-radius:10px;
}

.user{color:#38bdf8}
.ai{color:#a7f3d0}

.controls{
 position:fixed;
 bottom:0;
 width:100%;
 background:#020617;
 padding:10px;
 z-index:2;
}

input{
 width:65%;
 padding:10px;
 border-radius:8px;
 border:none;
}

button{
 padding:10px;
 border:none;
 border-radius:8px;
 cursor:pointer;
}
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
