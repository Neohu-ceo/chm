#!/usr/bin/env python3
"""戳戳桌面版 v2.0 — Full Nurturing System.

Start: python pet_server.py → http://localhost:5200
"""

import json, time, secrets, sqlite3, random, webbrowser
from datetime import datetime, timedelta
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler

DATA_DIR = Path(__file__).parent / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = DATA_DIR / "pet_v2.db"
STATE_FILE = DATA_DIR / "state_v2.json"

# ── Pet System ──────────────────────────────────────────────────

STAGE_NAMES = {0: "蛋", 1: "幼年", 2: "成年", 3: "完全体"}
QUESTS = [
    {"id":"poke10","name":"戳击新手","desc":"戳 10 次","target":10,"reward_xp":50},
    {"id":"feed5","name":"投喂达人","desc":"喂食 5 次","target":5,"reward_xp":80},
    {"id":"play3","name":"玩耍时间","desc":"玩 3 次小游戏","target":3,"reward_xp":100},
    {"id":"streak3","name":"坚持不懈","desc":"连续 3 天","target":3,"reward_xp":150},
]
ACHIEVEMENTS = [
    {"id":"first_poke","name":"初次见面","desc":"第一次戳戳","icon":"👆"},
    {"id":"poke_100","name":"百戳不厌","desc":"累计 100 次戳击","icon":"💯"},
    {"id":"poke_1000","name":"戳戳大师","desc":"累计 1000 次戳击","icon":"👑"},
    {"id":"level_5","name":"小有成就","desc":"达到 Level 5","icon":"⭐"},
    {"id":"level_10","name":"进化之光","desc":"达到 Level 10","icon":"✨"},
    {"id":"streak_7","name":"一周之约","desc":"连续 7 天","icon":"🔥"},
    {"id":"all_care","name":"全能保姆","desc":"喂食+玩耍+戳击各10次","icon":"🏆"},
]
ACCESSORIES = [
    {"id":"hat_cowboy","name":"牛仔帽","type":"hat","cost":200,"icon":"🤠"},
    {"id":"hat_crown","name":"皇冠","type":"hat","cost":500,"icon":"👑"},
    {"id":"glasses_cool","name":"墨镜","type":"glasses","cost":300,"icon":"😎"},
    {"id":"bow_tie","name":"领结","type":"neck","cost":150,"icon":"🎀"},
    {"id":"cat_ears","name":"猫耳","type":"hat","cost":400,"icon":"🐱"},
]

DEFAULT_STATE = {
    "name": "戳戳", "level": 1, "xp": 0, "xp_to_next": 100, "stage": 0,
    "hunger": 80, "happiness": 80, "energy": 80,
    "total_pokes": 0, "total_feed": 0, "total_plays": 0, "total_sleeps": 0,
    "streak_days": 0, "last_active_date": None, "hatched_at": datetime.now().isoformat(),
    "emotion": "happy", "unlocked_emotions": ["happy"],
    "coins": 50, "accessories": [], "wearing": {},
    "quest_progress": {}, "achievements": [],
}

def load_state():
    if STATE_FILE.exists():
        s = {**DEFAULT_STATE, **json.loads(STATE_FILE.read_text())}
        return s
    return dict(DEFAULT_STATE)

def save_state(s):
    STATE_FILE.write_text(json.dumps(s, indent=2))

def decay_stats(s):
    """Stats decay based on time since last update."""
    now = datetime.now()
    last = s.get("_last_decay")
    if not last:
        s["_last_decay"] = now.isoformat()
        return
    elapsed = (now - datetime.fromisoformat(last)).total_seconds() / 60  # minutes
    if elapsed < 1: return
    s["hunger"] = max(0, s["hunger"] - elapsed * 0.3)
    s["happiness"] = max(0, s["happiness"] - elapsed * 0.2)
    s["energy"] = max(0, s["energy"] - elapsed * 0.15)
    s["_last_decay"] = now.isoformat()

def update_emotion(s):
    """Determine emotion from stats."""
    if s["hunger"] < 20: s["emotion"] = "hungry"
    elif s["energy"] < 20: s["emotion"] = "sleepy"
    elif s["happiness"] > 80: s["emotion"] = "excited"
    elif s["happiness"] > 60: s["emotion"] = "happy"
    elif s["happiness"] > 30: s["emotion"] = "surprised"
    else: s["emotion"] = "hungry"
    # Time-based override
    h = datetime.now().hour
    if 14 <= h < 16: s["emotion"] = "sleepy"
    if 16 <= h < 18 and s["happiness"] > 30: s["emotion"] = "excited"

def add_xp(s, amount):
    s["xp"] += amount
    while s["xp"] >= s["xp_to_next"]:
        s["xp"] -= s["xp_to_next"]
        s["level"] += 1
        s["xp_to_next"] = int(s["xp_to_next"] * 1.3)
        s["coins"] += 25
        # Check stage evolution
        if s["level"] >= 10: s["stage"] = 3
        elif s["level"] >= 5: s["stage"] = 2
        elif s["level"] >= 2: s["stage"] = 1
        # Unlock emotions
        if s["level"] >= 7 and "love" not in s["unlocked_emotions"]:
            s["unlocked_emotions"].append("love")

def check_streak(s):
    today = datetime.now().date().isoformat()
    last = s.get("last_active_date")
    if last == today: return
    if last and datetime.fromisoformat(last).date() == (datetime.now()-timedelta(days=1)).date():
        s["streak_days"] += 1
    elif last != today:
        s["streak_days"] = 1
    s["last_active_date"] = today

def check_quests(s):
    completed = []
    for q in QUESTS:
        pid = q["id"]
        prog = s["quest_progress"].get(pid, 0)
        if pid.startswith("poke"): prog = s["total_pokes"]
        elif pid.startswith("feed"): prog = s["total_feed"]
        elif pid.startswith("play"): prog = s["total_plays"]
        elif pid.startswith("streak"): prog = s["streak_days"]
        s["quest_progress"][pid] = prog
        if prog >= q["target"] and pid not in s.get("_completed_quests", []):
            s.setdefault("_completed_quests", []).append(pid)
            add_xp(s, q["reward_xp"])
            completed.append(q)
    return completed

def check_achievements(s):
    new_ach = []
    def unlock(aid):
        if aid not in s["achievements"]:
            s["achievements"].append(aid)
            new_ach.append(next(a for a in ACHIEVEMENTS if a["id"]==aid))
    if s["total_pokes"] >= 1: unlock("first_poke")
    if s["total_pokes"] >= 100: unlock("poke_100")
    if s["total_pokes"] >= 1000: unlock("poke_1000")
    if s["level"] >= 5: unlock("level_5")
    if s["level"] >= 10: unlock("level_10")
    if s["streak_days"] >= 7: unlock("streak_7")
    if s["total_feed"] >= 10 and s["total_plays"] >= 10 and s["total_pokes"] >= 10:
        unlock("all_care")
    return new_ach

def get_state_dict(s):
    decay_stats(s)
    update_emotion(s)
    return {
        "name": s["name"], "level": s["level"], "xp": s["xp"], "xp_to_next": s["xp_to_next"],
        "stage": s["stage"], "stage_name": STAGE_NAMES.get(s["stage"], "?"),
        "hunger": round(s["hunger"]), "happiness": round(s["happiness"]), "energy": round(s["energy"]),
        "emotion": s["emotion"], "total_pokes": s["total_pokes"], "total_feed": s["total_feed"],
        "total_plays": s["total_plays"], "total_sleeps": s["total_sleeps"],
        "streak_days": s["streak_days"], "coins": s["coins"],
        "accessories": s["accessories"], "wearing": s["wearing"],
        "unlocked_emotions": s["unlocked_emotions"],
        "quests": [{"id":q["id"],"name":q["name"],"desc":q["desc"],"target":q["target"],"progress":s["quest_progress"].get(q["id"],0),"reward_xp":q["reward_xp"]} for q in QUESTS],
        "achievements": s["achievements"],
    }

# ── HTTP Server ─────────────────────────────────────────────────

TEMPLATE_DIR = Path(__file__).parent / "templates"

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path in ("/", "/pet"):
            self._file("pet.html", "text/html")
        elif self.path == "/api/state":
            s = load_state()
            self._json(get_state_dict(s))
        else:
            self.send_error(404)

    def do_POST(self):
        s = load_state()
        decay_stats(s)

        if self.path == "/api/poke":
            s["total_pokes"] += 1
            s["happiness"] = min(100, s["happiness"] + 8)
            s["energy"] = max(0, s["energy"] - 2)
            add_xp(s, 10)
            check_streak(s)
            quests_done = check_quests(s)
            ach_new = check_achievements(s)
            update_emotion(s); save_state(s)
            self._json({"reaction": s["emotion"], "xp": 10,
                "message": random.choice(["嘿嘿~","再戳！","好痒！","噗！","戳戳戳！","你真好~"]),
                "quests_done": [q["name"] for q in quests_done],
                "achievements_new": [a["name"] for a in ach_new],
                "stats": get_state_dict(s)})

        elif self.path == "/api/feed":
            if s["coins"] < 10: self._json({"error":"金币不足！戳戳戳赚金币吧~"}); return
            s["coins"] -= 10
            s["total_feed"] += 1
            s["hunger"] = min(100, s["hunger"] + 25)
            s["happiness"] = min(100, s["happiness"] + 5)
            add_xp(s, 15)
            check_streak(s); update_emotion(s); save_state(s)
            self._json({"reaction": "love","message": random.choice(["好吃！","再来一份~","嗝~","美味！","谢谢款待！"]),
                "stats": get_state_dict(s)})

        elif self.path == "/api/play":
            s["total_plays"] += 1
            s["happiness"] = min(100, s["happiness"] + 15)
            s["energy"] = max(0, s["energy"] - 15)
            add_xp(s, 20)
            check_streak(s); update_emotion(s); save_state(s)
            self._json({"reaction": "excited","message": random.choice(["好玩！","再来一局！","耶~","哈哈哈！"]),
                "stats": get_state_dict(s)})

        elif self.path == "/api/sleep":
            s["total_sleeps"] += 1
            s["energy"] = min(100, s["energy"] + 40)
            s["hunger"] = max(0, s["hunger"] - 10)
            add_xp(s, 5)
            s["emotion"] = "sleepy"
            check_streak(s); save_state(s)
            self._json({"reaction": "sleepy","message": random.choice(["zzZ...","晚安~","好梦！","困了困了"]),
                "stats": get_state_dict(s)})

        elif self.path == "/api/rename":
            body = self._body()
            s["name"] = body.get("name", s["name"])
            save_state(s); self._json({"name": s["name"]})

        elif self.path == "/api/wear":
            body = self._body()
            acc_id = body.get("accessory_id")
            if acc_id in s["accessories"]:
                acc = next(a for a in ACCESSORIES if a["id"]==acc_id)
                s["wearing"][acc["type"]] = acc_id
                save_state(s); self._json({"wearing": s["wearing"]})
            else:
                self._json({"error": "未拥有此配饰"})

        elif self.path == "/api/buy":
            body = self._body()
            acc_id = body.get("accessory_id")
            acc = next((a for a in ACCESSORIES if a["id"]==acc_id), None)
            if not acc: self._json({"error":"不存在"}); return
            if acc_id in s["accessories"]: self._json({"error":"已拥有"}); return
            if s["coins"] < acc["cost"]: self._json({"error":f'需要 {acc["cost"]} 金币'}); return
            s["coins"] -= acc["cost"]
            s["accessories"].append(acc_id)
            save_state(s); self._json({"bought": acc["name"], "coins": s["coins"]})

        else:
            self.send_error(404)

    def _file(self, name, ct):
        path = TEMPLATE_DIR / name
        content = path.read_bytes() if path.exists() else b"Not found"
        self.send_response(200); self.send_header("Content-Type", ct)
        self.send_header("Access-Control-Allow-Origin", "*"); self.end_headers()
        self.wfile.write(content)

    def _json(self, data):
        body = json.dumps(data, ensure_ascii=False).encode()
        self.send_response(200); self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*"); self.end_headers()
        self.wfile.write(body)

    def _body(self):
        length = int(self.headers.get("Content-Length", 0))
        return json.loads(self.rfile.read(length)) if length else {}

    def log_message(self, format, *args): pass

def main():
    port = 5200
    server = HTTPServer(("0.0.0.0", port), Handler)
    print(f"🖐️ 戳戳 v2.0 → http://localhost:{port}")
    webbrowser.open(f"http://localhost:{port}")
    try: server.serve_forever()
    except KeyboardInterrupt: print("\n👋 明天见！")

if __name__ == "__main__":
    main()
