#!/usr/bin/env python3
"""戳戳桌面版 — Desktop Pet Server.

A tiny local server that powers your desktop companion.
Start with: python pet_server.py
Then open: http://localhost:5200
"""

import os
import json
import time
import secrets
import sqlite3
import webbrowser
from datetime import datetime, timedelta
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler

DATA_DIR = Path(__file__).parent / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = DATA_DIR / "pet.db"
STATE_FILE = DATA_DIR / "state.json"

# ── Database ────────────────────────────────────────────────────

def init_db():
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("""CREATE TABLE IF NOT EXISTS interactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        type TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")
    conn.execute("""CREATE TABLE IF NOT EXISTS daily_stats (
        date DATE PRIMARY KEY, pokes INTEGER DEFAULT 0,
        active_minutes INTEGER DEFAULT 0, emotion_changes INTEGER DEFAULT 0)""")
    conn.commit()
    conn.close()

init_db()

# ── Pet State ───────────────────────────────────────────────────

DEFAULT_STATE = {
    "name": "戳戳",
    "level": 1,
    "xp": 0,
    "xp_to_next": 100,
    "streak_days": 0,
    "last_active_date": None,
    "total_pokes": 0,
    "emotion": "happy",
    "hatched_at": datetime.now().isoformat(),
    "personality": "playful",  # playful / chill / spicy
    "accessories": [],
}

def load_state():
    if STATE_FILE.exists():
        return {**DEFAULT_STATE, **json.loads(STATE_FILE.read_text())}
    return dict(DEFAULT_STATE)

def save_state(s):
    STATE_FILE.write_text(json.dumps(s, indent=2))

def check_streak(state):
    today = datetime.now().date().isoformat()
    last = state.get("last_active_date")
    if last == today:
        return
    if last:
        last_date = datetime.fromisoformat(last).date()
        yesterday = (datetime.now() - timedelta(days=1)).date()
        if last_date == yesterday:
            state["streak_days"] += 1
        elif last_date != datetime.now().date():
            state["streak_days"] = 1
    else:
        state["streak_days"] = 1
    state["last_active_date"] = today
    save_state(state)

def add_xp(state, amount):
    state["xp"] += amount
    while state["xp"] >= state["xp_to_next"]:
        state["xp"] -= state["xp_to_next"]
        state["level"] += 1
        state["xp_to_next"] = int(state["xp_to_next"] * 1.3)

def get_daily_emotion():
    """Emotion based on time of day."""
    h = datetime.now().hour
    if 6 <= h < 9:   return "sleepy"
    if 9 <= h < 12:  return "happy"
    if 12 <= h < 14: return "hungry"
    if 14 <= h < 16: return "sleepy"
    if 16 <= h < 18: return "excited"
    if 18 <= h < 20: return "happy"
    return "sleepy"

def get_stats(state):
    today = datetime.now().date().isoformat()
    conn = sqlite3.connect(str(DB_PATH))
    pokes_today = conn.execute("SELECT COUNT(*) FROM interactions WHERE DATE(created_at)=? AND type='poke'", (today,)).fetchone()[0]
    conn.close()
    return {
        "level": state["level"],
        "xp": state["xp"],
        "xp_to_next": state["xp_to_next"],
        "streak_days": state["streak_days"],
        "total_pokes": state["total_pokes"],
        "pokes_today": pokes_today,
        "emotion": state["emotion"],
        "time_emotion": get_daily_emotion(),
    }


# ── HTTP Server ─────────────────────────────────────────────────

TEMPLATE_DIR = Path(__file__).parent / "templates"

class PetHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/" or self.path == "/pet":
            self.serve_file("pet.html", "text/html")
        elif self.path == "/api/state":
            self.serve_json(get_stats(load_state()))
        elif self.path == "/api/stats":
            self.serve_json(get_stats(load_state()))
        else:
            self.send_error(404)

    def do_POST(self):
        if self.path == "/api/poke":
            state = load_state()
            check_streak(state)
            state["total_pokes"] += 1
            add_xp(state, 10 + (5 if state["emotion"] == "happy" else 0))
            # Random emotion change on poke
            import random
            emotions = ["happy", "surprised", "excited", "love"]
            if random.random() < 0.3:
                state["emotion"] = random.choice(emotions)
            save_state(state)

            conn = sqlite3.connect(str(DB_PATH))
            conn.execute("INSERT INTO interactions (type) VALUES ('poke')")
            conn.commit()
            conn.close()

            self.serve_json({
                "reaction": state["emotion"],
                "xp_gained": 10,
                "stats": get_stats(state),
                "message": random.choice([
                    "嘿嘿~", "再戳一下！", "好痒！", "你真好~", "😊", "噗！",
                    "别停呀", "戳戳戳！", "今日第"+str(state["total_pokes"])+"次"
                ])
            })

        elif self.path == "/api/rename":
            body = self.read_body()
            state = load_state()
            state["name"] = body.get("name", state["name"])
            save_state(state)
            self.serve_json({"name": state["name"]})

        elif self.path == "/api/evolve":
            state = load_state()
            # Evolution at certain levels
            if state["level"] >= 10 and state["personality"] == "playful":
                state["personality"] = "evolved"
                save_state(state)
                self.serve_json({"evolved": True, "message": "🎉 你的戳戳进化了！它现在更懂你了。"})
            else:
                self.serve_json({"evolved": False})

        else:
            self.send_error(404)

    def serve_file(self, filename, content_type):
        path = TEMPLATE_DIR / filename
        if path.exists():
            content = path.read_bytes()
        else:
            # Fallback: inline the HTML
            content = b"<h1>Template not found</h1>"
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(content)

    def serve_json(self, data):
        body = json.dumps(data, ensure_ascii=False).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def read_body(self):
        length = int(self.headers.get("Content-Length", 0))
        if length:
            return json.loads(self.rfile.read(length))
        return {}

    def log_message(self, format, *args):
        pass  # Quiet


def main():
    port = 5200
    server = HTTPServer(("0.0.0.0", port), PetHandler)
    print(f"""
╔══════════════════════════════════════╗
║  🖐️  戳戳 ChuoChuo — Desktop Pet    ║
║                                      ║
║  http://localhost:{port}              ║
║                                      ║
║  Keep this window open.              ║
║  Open the link in a small browser.   ║
╚══════════════════════════════════════╝
""")
    webbrowser.open(f"http://localhost:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n👋 戳戳下班了，明天见！")


if __name__ == "__main__":
    main()
