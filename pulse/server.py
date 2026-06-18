#!/usr/bin/env python3
"""Pulse — Website & API Monitoring SaaS.

Monitor uptime, response times, SSL certs. Public status pages.
Start: python server.py → http://localhost:5300
"""

import json, os, time, secrets, hashlib, sqlite3, urllib.request, ssl, threading
from datetime import datetime, timedelta
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler

PORT = int(os.getenv("PORT", "5300"))
DATA_DIR = Path(__file__).parent / "data"
DATA_DIR.mkdir(exist_ok=True)
DB = DATA_DIR / "pulse.db"

def init_db():
    conn = sqlite3.connect(str(DB))
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS monitors (id TEXT PRIMARY KEY, user_id TEXT, url TEXT,
      name TEXT, interval_sec INTEGER DEFAULT 60, active BOOLEAN DEFAULT 1,
      created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
    CREATE TABLE IF NOT EXISTS checks (id INTEGER PRIMARY KEY AUTOINCREMENT,
      monitor_id TEXT, status TEXT, response_ms INTEGER, status_code INTEGER,
      error TEXT, checked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
    CREATE TABLE IF NOT EXISTS users (id TEXT PRIMARY KEY, email TEXT UNIQUE,
      password_hash TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
    CREATE TABLE IF NOT EXISTS status_pages (id TEXT PRIMARY KEY, user_id TEXT,
      slug TEXT UNIQUE, title TEXT, public BOOLEAN DEFAULT 1);
    CREATE TABLE IF NOT EXISTS page_monitors (page_id TEXT, monitor_id TEXT,
      PRIMARY KEY(page_id, monitor_id));
    """)
    conn.commit(); conn.close()

init_db()

def hash_pw(pw): return hashlib.sha256(pw.encode()).hexdigest()
def row_dict(row): return {k: row[k] for k in row.keys()} if row else {}

def db_query(query, *params):
    conn = sqlite3.connect(str(DB))
    conn.row_factory = sqlite3.Row
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [row_dict(r) for r in rows]

def db_exec(query, *params):
    conn = sqlite3.connect(str(DB))
    conn.execute(query, params)
    conn.commit()
    conn.close()

# ── Monitor Engine ──────────────────────────────────────────────

_monitors = {}  # monitor_id -> thread

def check_url(monitor_id, url):
    start = time.time()
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Pulse/1.0"})
        ctx = ssl.create_default_context()
        with urllib.request.urlopen(req, timeout=15, context=ctx) as r:
            ms = int((time.time() - start) * 1000)
            return "up", ms, r.status, None
    except urllib.error.HTTPError as e:
        ms = int((time.time() - start) * 1000)
        return "down", ms, e.code, str(e)
    except Exception as e:
        ms = int((time.time() - start) * 1000)
        return "down", ms, None, str(e)[:200]

def save_check(monitor_id, status, ms, code, error):
    conn = sqlite3.connect(str(DB))
    conn.execute("INSERT INTO checks (monitor_id,status,response_ms,status_code,error) VALUES (?,?,?,?,?)",
                 (monitor_id, status, ms, code, error))
    # Keep only last 1000 checks per monitor
    conn.execute("DELETE FROM checks WHERE monitor_id=? AND id NOT IN (SELECT id FROM checks WHERE monitor_id=? ORDER BY id DESC LIMIT 1000)",
                 (monitor_id, monitor_id))
    conn.commit(); conn.close()

def monitor_loop(monitor_id, url, interval):
    while _monitors.get(monitor_id):
        status, ms, code, error = check_url(monitor_id, url)
        save_check(monitor_id, status, ms, code, error)
        time.sleep(interval)

def start_monitor(monitor_id, url, interval=60):
    stop_monitor(monitor_id)
    t = threading.Thread(target=monitor_loop, args=(monitor_id, url, interval), daemon=True)
    _monitors[monitor_id] = t
    t.start()

def stop_monitor(monitor_id):
    if monitor_id in _monitors:
        del _monitors[monitor_id]

# Resume all active monitors on startup
def resume_monitors():
    conn = sqlite3.connect(str(DB))
    conn.row_factory = sqlite3.Row
    for row in conn.execute("SELECT * FROM monitors WHERE active=1").fetchall():
        start_monitor(row["id"], row["url"], row["interval_sec"])
    conn.close()

# ── HTML Templates ──────────────────────────────────────────────

TEMPLATES = {
    "index": """<!DOCTYPE html><html lang="zh-CN"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Pulse — 网站监控</title>
<style>:root{--bg:#0a0f18;--card:rgba(255,255,255,.03);--text:#e0e8f0;--muted:#6b8299;--green:#10b981;--red:#ef4444;--yellow:#f59e0b;--accent:#2563eb}
*{margin:0;padding:0;box-sizing:border-box}body{font-family:-apple-system,sans-serif;background:var(--bg);color:var(--text);line-height:1.6}
.container{max-width:800px;margin:0 auto;padding:2rem}h1{font-size:1.5rem}h1 span{color:var(--accent)}
.monitor{background:var(--card);border-radius:12px;padding:1rem 1.25rem;margin:0.75rem 0;border:1px solid rgba(255,255,255,.05);display:flex;justify-content:space-between;align-items:center}
.monitor .name{font-weight:600}.monitor .url{font-size:.8rem;color:var(--muted)}
.monitor .status{font-size:.8rem;padding:.2rem .6rem;border-radius:10px;font-weight:600}
.status-up{background:rgba(16,185,129,.15);color:var(--green)}.status-down{background:rgba(239,68,68,.15);color:var(--red)}
.monitor .meta{font-size:.75rem;color:var(--muted)}.monitor .meta span{margin-left:1rem}
.btn{display:inline-block;padding:.5rem 1.25rem;border-radius:8px;font-weight:600;font-size:.85rem;cursor:pointer;border:none;text-decoration:none;color:#fff;background:var(--accent)}
.btn-outline{background:transparent;border:1px solid rgba(255,255,255,.15);color:var(--text);margin-left:.5rem}
input{width:100%;padding:.6rem .75rem;border-radius:8px;border:1px solid rgba(255,255,255,.1);background:rgba(255,255,255,.03);color:var(--text);font-size:.9rem;margin-bottom:.5rem}
footer{text-align:center;padding:2rem;color:var(--muted);font-size:.75rem}
.bar-wrap{display:flex;align-items:flex-end;gap:1px;height:24px;margin-top:.5rem}
.bar{flex:1;border-radius:2px 2px 0 0;min-width:2px}.bar-up{background:var(--green)}.bar-down{background:var(--red)}
</style></head><body><div class="container">
<h1>📡 <span>Pulse</span> 监控</h1><p style="color:var(--muted);margin:.25rem 0 1.5rem">网站 & API 可用性监控 · 宕机告警 · 公开状态页</p>
<div id="monitors"></div>
<div style="margin-top:1.5rem;display:flex;gap:.5rem;flex-wrap:wrap">
<input id="new-url" placeholder="https://example.com" style="flex:1;min-width:200px">
<input id="new-name" placeholder="名称（可选）" style="max-width:200px;min-width:150px">
<button class="btn" onclick="addMonitor()">+ 添加</button></div>
<div id="status-bar" style="margin-top:1rem;display:flex;gap:1rem" class="meta"></div>
<footer>📡 Pulse by Lighthouse Analytics · 首个监控免费 · Pro $9/月</footer>
</div>
<script>
const A='';async function api(p,m='GET',b=null){const o={method:m,headers:{'Content-Type':'application/json'}};if(b)o.body=JSON.stringify(b);const r=await fetch(p,o);return r.json()}
async function load(){const d=await api('/api/monitors');document.getElementById('monitors').innerHTML=(d.monitors||[]).map(m=>`<div class="monitor"><div><div class="name">${m.name||m.url}</div><div class="url">${m.url}</div><div class="bar-wrap">${(m.recent||[]).slice(-40).map(c=>`<div class="bar bar-${c.status}"></div>`).join('')}</div></div><div style="text-align:right"><div class="status status-${m.current_status}">${m.current_status==='up'?'🟢':'🔴'} ${m.current_status}</div><div class="meta"><span>${m.response_ms||'?'}ms</span><span>${m.uptime_pct||'?'}%</span></div><a href="/status/${m.id}" style="font-size:.7rem;color:var(--accent)">状态页</a></div></div>`).join('')||'<p style="color:var(--muted)">还没有监控。添加一个 URL 开始。</p>'}
async function addMonitor(){const url=document.getElementById('new-url').value.trim();if(!url)return;const name=document.getElementById('new-name').value.trim()||url;await api('/api/monitors','POST',{url,name});document.getElementById('new-url').value='';document.getElementById('new-name').value='';load()}
load();setInterval(load,15000);
</script></body></html>""",

    "status": """<!DOCTYPE html><html lang="zh-CN"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{{title}} — 状态</title>
<style>:root{--bg:#0a0f18;--text:#e0e8f0;--muted:#6b8299;--green:#10b981;--red:#ef4444}
*{margin:0;padding:0;box-sizing:border-box}body{font-family:-apple-system,sans-serif;background:var(--bg);color:var(--text);text-align:center;min-height:100vh;display:flex;flex-direction:column;align-items:center;justify-content:center}
.status-dot{width:32px;height:32px;border-radius:50%;margin-bottom:1rem}.up{background:var(--green);box-shadow:0 0 20px rgba(16,185,129,.3)}.down{background:var(--red);box-shadow:0 0 20px rgba(239,68,68,.3)}
h1{font-size:2rem;margin-bottom:.5rem}.uptime{font-size:3rem;font-weight:900}.uptime span{font-size:1rem;color:var(--muted)}
footer{position:fixed;bottom:2rem;color:var(--muted);font-size:.75rem}
</style></head><body>
<div class="status-dot {{status_class}}"></div><h1>{{title}}</h1><p style="color:var(--muted);margin-bottom:2rem">{{status_text}}</p>
<div class="uptime">{{uptime}}%<br><span>过去 24 小时可用率</span></div>
<footer>📡 由 Pulse 监控 · Lighthouse Analytics</footer></body></html>"""
}

# ── HTTP Handler ────────────────────────────────────────────────

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/": self._render("index")
        elif self.path.startswith("/status/"):
            mid = self.path.split("/")[-1]
            conn = sqlite3.connect(str(DB))
            row = conn.execute("SELECT * FROM monitors WHERE id=?", (mid,)).fetchone()
            if not row: self.send_error(404); conn.close(); return
            # Calc 24h uptime
            day_ago = (datetime.now() - timedelta(hours=24)).isoformat()
            checks = conn.execute("SELECT status FROM checks WHERE monitor_id=? AND checked_at>? ORDER BY checked_at DESC",
                                   (mid, day_ago)).fetchall()
            conn.close()
            up = sum(1 for c in checks if c["status"]=="up")
            total = len(checks) or 1
            uptime = round(up/total*100, 1) if total > 0 else 100
            status = "up" if checks and checks[0]["status"]=="up" else "down"
            html = TEMPLATES["status"].replace("{{title}}", m["name"] or m["url"])
            html = html.replace("{{status_class}}", status)
            html = html.replace("{{status_text}}", "所有系统正常" if status=="up" else "服务中断")
            html = html.replace("{{uptime}}", str(uptime))
            self._html(html)
        elif self.path == "/api/monitors":
            conn = sqlite3.connect(str(DB))
            conn.row_factory = sqlite3.Row
            monitors = []
            for row in conn.execute("SELECT * FROM monitors WHERE active=1 ORDER BY created_at DESC").fetchall():
                m = row_dict(row)
                # Recent checks
                recent = conn.execute("SELECT status FROM checks WHERE monitor_id=? ORDER BY checked_at DESC LIMIT 100",
                                      (row["id"],)).fetchall()
                m["recent"] = [row_dict(c) for c in recent]
                m["current_status"] = recent[0]["status"] if recent else "unknown"
                # Last response time
                last = conn.execute("SELECT response_ms FROM checks WHERE monitor_id=? AND status='up' ORDER BY checked_at DESC LIMIT 1",
                                    (row["id"],)).fetchone()
                m["response_ms"] = last["response_ms"] if last else None
                # 24h uptime
                day_ago = (datetime.now() - timedelta(hours=24)).isoformat()
                total = conn.execute("SELECT COUNT(*) as c FROM checks WHERE monitor_id=? AND checked_at>?",
                                     (row["id"], day_ago)).fetchone()["c"]
                up = conn.execute("SELECT COUNT(*) as c FROM checks WHERE monitor_id=? AND checked_at>? AND status='up'",
                                  (row["id"], day_ago)).fetchone()["c"]
                m["uptime_pct"] = round(up/max(total,1)*100, 1)
                monitors.append(m)
            conn.close()
            self._json({"monitors": monitors})
        else:
            self.send_error(404)

    def do_POST(self):
        body = self._body()
        if self.path == "/api/monitors":
            mid = secrets.token_hex(8)
            conn = sqlite3.connect(str(DB))
            conn.execute("INSERT INTO monitors (id,url,name,interval_sec) VALUES (?,?,?,?)",
                         (mid, body["url"], body.get("name", body["url"]), body.get("interval", 60)))
            conn.commit(); conn.close()
            start_monitor(mid, body["url"], body.get("interval", 60))
            self._json({"id": mid, "url": body["url"]})

    def _html(self, content):
        self.send_response(200); self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers(); self.wfile.write(content.encode())
    def _render(self, name):
        self._html(TEMPLATES.get(name, "<h1>404</h1>"))
    def _json(self, data):
        self.send_response(200); self.send_header("Content-Type", "application/json")
        self.end_headers(); self.wfile.write(json.dumps(data).encode())
    def _body(self):
        length = int(self.headers.get("Content-Length", 0))
        return json.loads(self.rfile.read(length)) if length else {}
    def log_message(self, format, *args): pass

if __name__ == "__main__":
    resume_monitors()
    print(f"📡 Pulse → http://localhost:{PORT}")
    HTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
