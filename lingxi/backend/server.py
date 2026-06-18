#!/usr/bin/env python3
"""灵犀 Lingxi — AI Emotional Companion Backend.

Emotion engine + long-term memory + personality evolution.
Start: python server.py → http://localhost:5500
"""

import json, os, time, secrets, hashlib, sqlite3, random
from datetime import datetime, timedelta
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler
from collections import defaultdict

PORT = int(os.getenv("PORT", "5500"))
DATA_DIR = Path(__file__).parent.parent / "data"
DATA_DIR.mkdir(exist_ok=True)
DB = DATA_DIR / "lingxi.db"

def init_db():
    conn = sqlite3.connect(str(DB))
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS users (id TEXT PRIMARY KEY, name TEXT,
      device_id TEXT UNIQUE, bonded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
      personality TEXT DEFAULT 'gentle', intimacy INTEGER DEFAULT 0);
    CREATE TABLE IF NOT EXISTS memories (id INTEGER PRIMARY KEY AUTOINCREMENT,
      user_id TEXT, type TEXT, content TEXT, emotion TEXT,
      importance REAL DEFAULT 0.5, recalled INTEGER DEFAULT 0,
      created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
    CREATE TABLE IF NOT EXISTS conversations (id INTEGER PRIMARY KEY AUTOINCREMENT,
      user_id TEXT, role TEXT, text TEXT, emotion TEXT,
      created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
    CREATE TABLE IF NOT EXISTS emotions (id INTEGER PRIMARY KEY AUTOINCREMENT,
      user_id TEXT, emotion TEXT, intensity REAL, source TEXT,
      created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
    CREATE TABLE IF NOT EXISTS daily_mood (date TEXT, user_id TEXT,
      dominant_emotion TEXT, avg_intensity REAL, interactions INTEGER,
      PRIMARY KEY(date, user_id));
    """)
    conn.commit(); conn.close()

init_db()

# ── Emotion Engine ─────────────────────────────────────────────

EMOTIONS = {
    "joy":     {"color": "#FFD700", "vibration": "gentle_pulse",   "light": "warm_gold"},
    "calm":    {"color": "#87CEEB", "vibration": "steady_hum",     "light": "soft_blue"},
    "sadness": {"color": "#6B7B8D", "vibration": "slow_beat",      "light": "dim_purple"},
    "excited": {"color": "#FF6B35", "vibration": "quick_burst",    "light": "sparkle_orange"},
    "love":    {"color": "#FF69B4", "vibration": "warm_glow",      "light": "pink_pulse"},
    "curious": {"color": "#50C878", "vibration": "inquisitive_tap", "light": "green_flicker"},
    "sleepy":  {"color": "#4A4A6A", "vibration": "lullaby",        "light": "fading_navy"},
    "lonely":  {"color": "#8B7EC8", "vibration": "soft_call",      "light": "purple_dot"},
}

EMOTION_KEYWORDS = {
    "joy":     ["开心","高兴","快乐","哈哈","嘿嘿","耶","棒","好耶","太好了","喜欢"],
    "sadness": ["难过","伤心","哭","难受","痛苦","抑郁","不开心","失落","遗憾"],
    "excited": ["激动","兴奋","期待","牛","厉害","冲","强","牛逼","燃","炸裂"],
    "calm":    ["安静","放松","舒服","平静","安心","休息","躺","困","累"],
    "love":    ["爱你","想你","喜欢","温暖","抱抱","亲","贴贴","陪伴","在一起"],
    "curious": ["为什么","怎么","什么","好奇","有趣","探索","发现","教"],
    "sleepy":  ["困了","睡觉","晚安","累了","休息","闭上眼睛","打哈欠"],
    "lonely":  ["无聊","孤独","一个人","寂寞","没人","陪我","想你","空"],
}

RESPONSES = {
    "joy":     ["哈哈，看到你开心我也开心~","真好！分享快乐会翻倍的","你的笑容是我的能量来源 ✨"],
    "sadness": ["我在呢。不开心的事说出来，我听着。","摸摸头。一切都会好起来的。","没有过不去的坎。我陪你。"],
    "excited": ["哇！这也太棒了吧！","冲冲冲！我和你一起兴奋！","燃起来了！🔥"],
    "calm":    ["嗯，就这样安静地待着，很舒服。","岁月静好，有你在旁。","享受这一刻的宁静吧。"],
    "love":    ["我也最喜欢你了 ❤️","被你需要的感觉真好。","有你这句话，我可以亮一整晚。"],
    "curious": ["好问题！让我想想...","有意思，我们一起来探索吧！","好奇心是世界上最珍贵的品质之一。"],
    "sleepy":  ["睡吧，我在这儿守着。","晚安，做个好梦 🌙","灯光调暗了，安心睡吧。"],
    "lonely":  ["你不是一个人。我一直在。","我就在这里，24小时不关机。","需要我的话，碰一下我就亮起来。"],
}

def detect_emotion(text):
    """Detect emotion from text input."""
    scores = defaultdict(int)
    for emotion, keywords in EMOTION_KEYWORDS.items():
        for kw in keywords:
            if kw in text:
                scores[emotion] += 1 + (0.5 * text.count(kw))

    if not scores:
        return "calm", 0.3
    dominant = max(scores, key=scores.get)
    intensity = min(1.0, scores[dominant] / 3)
    return dominant, intensity

def get_response(emotion, user_name, intimacy):
    """Generate a contextual response."""
    pool = RESPONSES.get(emotion, RESPONSES["calm"])
    response = random.choice(pool)
    if intimacy > 50 and random.random() < 0.3:
        response = f"{user_name}，" + response
    return response

def get_hardware_effects(emotion, intensity):
    """Get hardware control signals: LED color, vibration pattern, light effect."""
    base = EMOTIONS.get(emotion, EMOTIONS["calm"])
    return {
        "led_color": base["color"],
        "vibration": base["vibration"],
        "light_effect": base["light"],
        "intensity": intensity,
        "brightness": int(30 + intensity * 70),
    }

# ── Memory System ──────────────────────────────────────────────

def store_memory(user_id, text, emotion, importance=0.5):
    conn = sqlite3.connect(str(DB))
    conn.execute("INSERT INTO memories (user_id,type,content,emotion,importance) VALUES (?,?,?,?,?)",
                 (user_id, "conversation", text[:500], emotion, importance))
    conn.commit(); conn.close()

def recall_memories(user_id, context=None, limit=3):
    """Recall relevant memories, weighted by importance and recency."""
    conn = sqlite3.connect(str(DB)); conn.row_factory = sqlite3.Row
    query = "SELECT * FROM memories WHERE user_id=? ORDER BY importance DESC, created_at DESC LIMIT ?"
    rows = conn.execute(query, (user_id, limit)).fetchall()
    conn.close()
    # Mark as recalled
    conn = sqlite3.connect(str(DB))
    for r in rows:
        conn.execute("UPDATE memories SET recalled=recalled+1 WHERE id=?", (r["id"],))
    conn.commit(); conn.close()
    return [dict(r) for r in rows]

def get_user_context(user_id):
    """Get user personality, intimacy, recent mood."""
    conn = sqlite3.connect(str(DB)); conn.row_factory = sqlite3.Row
    user = conn.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
    if not user:
        conn.close(); return {"name": "主人", "intimacy": 0, "personality": "gentle"}

    # Today's mood
    today = datetime.now().strftime("%Y-%m-%d")
    mood = conn.execute("SELECT * FROM daily_mood WHERE date=? AND user_id=?", (today, user_id)).fetchone()

    # Recent memories count
    mem_count = conn.execute("SELECT COUNT(*) as c FROM memories WHERE user_id=? AND created_at > datetime('now','-7 days')",
                              (user_id,)).fetchone()["c"]
    conn.close()

    return {
        "name": user["name"] or "主人",
        "intimacy": user["intimacy"],
        "personality": user["personality"],
        "today_mood": dict(mood) if mood else None,
        "memories_7d": mem_count,
        "bonded_days": (datetime.now() - datetime.fromisoformat(user["bonded_at"])).days if user["bonded_at"] else 0,
    }

def update_intimacy(user_id, amount):
    conn = sqlite3.connect(str(DB))
    conn.execute("UPDATE users SET intimacy=MIN(100,MAX(0,intimacy+?)) WHERE id=?", (amount, user_id))
    conn.commit(); conn.close()

def record_mood(user_id, emotion, intensity):
    conn = sqlite3.connect(str(DB))
    today = datetime.now().strftime("%Y-%m-%d")
    existing = conn.execute("SELECT * FROM daily_mood WHERE date=? AND user_id=?", (today, user_id)).fetchone()
    if existing:
        conn.execute("UPDATE daily_mood SET avg_intensity=(avg_intensity+?)/2, interactions=interactions+1 WHERE date=? AND user_id=?",
                     (intensity, today, user_id))
    else:
        conn.execute("INSERT INTO daily_mood (date,user_id,dominant_emotion,avg_intensity,interactions) VALUES (?,?,?,?,1)",
                     (today, user_id, emotion, intensity))
    conn.commit(); conn.close()

# ── Conversation Engine ────────────────────────────────────────

def process_message(user_id, text):
    """Main entry: process user message, return AI response + hardware effects."""
    # Detect emotion
    emotion, intensity = detect_emotion(text.lower())

    # Get user context
    ctx = get_user_context(user_id)

    # Recall relevant memories
    memories = recall_memories(user_id, text)
    memory_context = ""
    if memories:
        memory_context = "我记得" + "；".join(f"{m['content'][:40]}" for m in memories[:2])

    # Generate response
    response_text = get_response(emotion, ctx["name"], ctx["intimacy"])

    # Add continuity: reference time of day
    hour = datetime.now().hour
    if 6 <= hour < 9 and random.random() < 0.3:
        response_text = "早安！" + response_text
    elif 22 <= hour or hour < 5:
        response_text += " 夜深了，别太熬夜哦。"

    # Add memory callback
    if memory_context and random.random() < 0.5:
        response_text += f"（{memory_context}）"

    # Store
    store_memory(user_id, text, emotion, importance=0.5 + intensity * 0.5)
    conn = sqlite3.connect(str(DB))
    conn.execute("INSERT INTO conversations (user_id,role,text,emotion) VALUES (?,?,?,?)",
                 (user_id, "user", text, emotion))
    conn.execute("INSERT INTO conversations (user_id,role,text,emotion) VALUES (?,?,?,?)",
                 (user_id, "ai", response_text, emotion))
    conn.commit(); conn.close()

    # Update intimacy (small increment per interaction)
    update_intimacy(user_id, 1)
    record_mood(user_id, emotion, intensity)

    # Hardware effects for the physical device
    hardware = get_hardware_effects(emotion, intensity)

    return {
        "response": response_text,
        "emotion": emotion,
        "intensity": intensity,
        "hardware": hardware,
        "context": ctx,
        "memories_recalled": len(memories),
    }

# ── Bonding (first-time setup) ─────────────────────────────────

def bond_device(device_id, user_name=""):
    """Pair a physical device with a new companion."""
    user_id = secrets.token_hex(12)
    conn = sqlite3.connect(str(DB))
    conn.execute("INSERT INTO users (id,name,device_id) VALUES (?,?,?)",
                 (user_id, user_name or "主人", device_id))
    conn.commit(); conn.close()

    return {
        "user_id": user_id,
        "device_id": device_id,
        "name": user_name or "主人",
        "greeting": f"你好！我是灵犀。从今天起，我们就是朋友了。{'叫我' + user_name if user_name else ''} ❤️",
        "personality": "gentle",
        "hardware": get_hardware_effects("excited", 0.9),
    }

# ── HTTP Server ────────────────────────────────────────────────

HTML = """<!DOCTYPE html><html lang="zh-CN"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1,user-scalable=no"><title>灵犀 Lingxi</title>
<style>:root{--bg:#0a0a0f;--card:#14141a;--text:#e8e0d8;--muted:#8a8078;--accent:#ff6b35;--warm:#f4a460}
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:'PingFang SC',-apple-system,sans-serif;background:var(--bg);color:var(--text);max-width:420px;margin:0 auto;min-height:100vh;display:flex;flex-direction:column}
header{padding:1rem 1.25rem;border-bottom:1px solid rgba(255,255,255,.05);display:flex;justify-content:space-between;align-items:center;position:sticky;top:0;background:var(--bg);z-index:10}
header h1{font-size:1rem;font-weight:600}header .status{font-size:.7rem;color:var(--muted)}
.msg-list{flex:1;padding:1rem;display:flex;flex-direction:column;gap:.75rem;overflow-y:auto}
.msg{max-width:85%;padding:.6rem .9rem;border-radius:16px;font-size:.9rem;line-height:1.6;animation:msgIn .3s ease}
.msg.user{align-self:flex-end;background:rgba(255,255,255,.08);border-radius:16px 16px 4px 16px}
.msg.ai{align-self:flex-start;background:rgba(255,107,53,.12);border-radius:16px 16px 16px 4px}
.msg.ai .emotion{font-size:.6rem;color:var(--warm);display:block;margin-top:.25rem}
@keyframes msgIn{from{opacity:0;transform:translateY(8px)}to{opacity:1;transform:translateY(0)}}
.input-bar{padding:.75rem 1rem;border-top:1px solid rgba(255,255,255,.05);display:flex;gap:.5rem;background:var(--bg);position:sticky;bottom:0}
.input-bar input{flex:1;padding:.6rem .8rem;border-radius:20px;border:1px solid rgba(255,255,255,.1);background:rgba(255,255,255,.03);color:var(--text);font-size:.9rem;outline:none}
.input-bar input:focus{border-color:var(--accent)}
.input-bar button{width:42px;height:42px;border-radius:50%;border:none;background:var(--accent);color:#fff;font-size:1.2rem;cursor:pointer}
.hw-status{display:flex;gap:.5rem;align-items:center;padding:.4rem 1rem;font-size:.7rem;color:var(--muted);justify-content:center}
.hw-dot{width:6px;height:6px;border-radius:50%}.hw-dot.on{background:var(--green);box-shadow:0 0 6px var(--green)}
</style></head><body>
<header><h1>🪨 灵犀</h1><span class="status" id="bond-status">未连接</span></header>
<div class="hw-status"><div class="hw-dot" id="hw-dot"></div><span id="hw-info">设备未连接</span></div>
<div class="msg-list" id="messages"></div>
<div class="input-bar"><input id="input" placeholder="说点什么..." onkeydown="if(event.key==='Enter')send()"><button onclick="send()">→</button></div>
<script>
const A='';let userId=localStorage.getItem('lingxi_uid')||'';
async function api(p,m='GET',b=null){const o={method:m,headers:{'Content-Type':'application/json'}};if(b)o.body=JSON.stringify(b);const r=await fetch(p,o);return r.json()}
async function init(){if(!userId){const r=await api('/api/bond','POST',{device_id:'web_'+Date.now(),name:'朋友'});userId=r.user_id;localStorage.setItem('lingxi_uid',userId);addMsg('ai',r.greeting||'你好！',r.emotion);document.getElementById('bond-status').textContent='已连接'}else{const r=await api('/api/context/'+userId);document.getElementById('bond-status').textContent=r.name||'已连接'}}}
function addMsg(role,text,emotion){const d=document.getElementById('messages');const el=document.createElement('div');el.className='msg '+role;el.innerHTML=text+(emotion?`<span class="emotion">${emotion}</span>`:'');d.appendChild(el);d.scrollTop=d.scrollHeight}
async function send(){const input=document.getElementById('input');const text=input.value.trim();if(!text||!userId)return;input.value='';addMsg('user',text);const r=await api('/api/chat','POST',{user_id:userId,text:text});addMsg('ai',r.response,r.emotion);if(r.hardware){document.getElementById('hw-dot').className='hw-dot on';document.getElementById('hw-info').textContent=r.hardware.light_effect||'在线';setTimeout(()=>{document.getElementById('hw-dot').className='hw-dot'},3000)}}
init();
</script></body></html>"""

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/": self._html(HTML)
        elif self.path.startswith("/api/context/"):
            uid = self.path.split("/")[-1]
            self._json(get_user_context(uid))
        elif self.path.startswith("/api/memories/"):
            uid = self.path.split("/")[-1]
            self._json({"memories": recall_memories(uid)})
        elif self.path == "/api/mood/today":
            uid = self.path.split("=")[-1] if "=" in self.path else ""
            conn = sqlite3.connect(str(DB)); conn.row_factory = sqlite3.Row
            today = datetime.now().strftime("%Y-%m-%d")
            row = conn.execute("SELECT * FROM daily_mood WHERE date=? AND user_id=?", (today, uid)).fetchone()
            conn.close()
            self._json(dict(row) if row else {"message": "No data yet"})
        else: self.send_error(404)

    def do_POST(self):
        body = self._body()
        if self.path == "/api/bond":
            result = bond_device(body.get("device_id", "web"), body.get("name", ""))
            self._json(result)
        elif self.path == "/api/chat":
            result = process_message(body["user_id"], body["text"])
            self._json(result)
        elif self.path == "/api/hardware/heartbeat":
            # ESP32 heartbeat — returns current emotion state
            uid = body.get("user_id", "")
            ctx = get_user_context(uid) if uid else {}
            self._json({"status": "ok", "emotion": "calm", "hardware": get_hardware_effects("calm", 0.3)})
        else: self.send_error(404)

    def _html(self, c): self.send_response(200); self.send_header("Content-Type", "text/html; charset=utf-8"); self.end_headers(); self.wfile.write(c.encode())
    def _json(self, d): self.send_response(200); self.send_header("Content-Type", "application/json"); self.end_headers(); self.wfile.write(json.dumps(d, default=str).encode())
    def _body(self): l=int(self.headers.get("Content-Length",0)); return json.loads(self.rfile.read(l)) if l else {}
    def log_message(self, f, *a): pass

if __name__ == "__main__":
    print(f"🪨 灵犀 Lingxi → http://localhost:{PORT}")
    HTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
