#!/usr/bin/env python3
"""Portfolio Tracker — OKX positions, P&L, price alerts.

Start: python server.py → http://localhost:5400
API keys optional: public data works without; private needs OKX API key.
"""

import json, os, time, secrets, threading, sqlite3
from datetime import datetime
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler

# ── Init ──────────────────────────────────────────────────────────

PORT = int(os.getenv("PORT", "5400"))
DATA_DIR = Path(__file__).parent / "data"
DATA_DIR.mkdir(exist_ok=True)
DB = DATA_DIR / "trade.db"

def init_db():
    conn = sqlite3.connect(str(DB))
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS alerts (id TEXT PRIMARY KEY, symbol TEXT,
      target_price REAL, direction TEXT, active BOOLEAN DEFAULT 1,
      triggered BOOLEAN DEFAULT 0, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
    CREATE TABLE IF NOT EXISTS trades (id TEXT PRIMARY KEY, symbol TEXT,
      side TEXT, amount REAL, price REAL, cost REAL, fee REAL,
      pnl REAL, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
    CREATE TABLE IF NOT EXISTS api_keys (exchange TEXT PRIMARY KEY,
      api_key TEXT, secret TEXT, password TEXT);
    """)
    conn.commit(); conn.close()

init_db()

# ── OKX Data Fetching ──────────────────────────────────────────────

import ccxt
_exchange_cache = {}

def get_exchange():
    """Get OKX exchange instance. Uses API key if configured."""
    conn = sqlite3.connect(str(DB))
    row = conn.execute("SELECT * FROM api_keys WHERE exchange='okx'").fetchone()
    conn.close()

    config = {"enableRateLimit": True}
    if row:
        config["apiKey"] = row["api_key"]
        config["secret"] = row["secret"]
        if row["password"]:
            config["password"] = row["password"]
    return ccxt.okx(config)

def fetch_tickers(symbols=None):
    """Fetch current prices from OKX."""
    try:
        ex = get_exchange()
        if symbols:
            tickers = {}
            for s in symbols:
                try:
                    t = ex.fetch_ticker(s)
                    tickers[s] = {"last": t["last"], "change_24h": t.get("percentage", 0), "high": t["high"], "low": t["low"], "volume": t["baseVolume"]}
                except: pass
            return tickers
        else:
            tickers = ex.fetch_tickers()
            return {s: {"last": t["last"], "change_24h": t.get("percentage", 0), "high": t["high"], "low": t["low"], "volume": t.get("baseVolume", 0)} for s, t in tickers.items()}
    except Exception as e:
        return {"error": str(e)}

def fetch_balance():
    """Fetch account balance. Requires API key."""
    try:
        ex = get_exchange()
        balance = ex.fetch_balance()
        total_usdt = balance.get("total", {}).get("USDT", 0) or 0
        # Get non-zero balances
        assets = {}
        for coin, data in (balance.get("total", {}) or {}).items():
            if data and data > 0 and coin != "USDT":
                assets[coin] = {"amount": data, "free": balance.get("free", {}).get(coin, 0)}
        return {"total_usdt": total_usdt, "assets": assets}
    except Exception as e:
        return {"error": str(e), "need_api_key": "authentication" in str(e).lower()}

def fetch_positions():
    """Fetch open positions. Requires API key."""
    try:
        ex = get_exchange()
        positions = ex.fetch_positions()
        active = []
        total_pnl = 0
        for p in positions:
            if p.get("contracts", 0) > 0:
                active.append({
                    "symbol": p["symbol"],
                    "side": p["side"],
                    "amount": p["contracts"],
                    "entry_price": p["entryPrice"],
                    "mark_price": p.get("markPrice", 0),
                    "pnl": p.get("unrealizedPnl", 0),
                    "pnl_pct": p.get("percentage", 0),
                    "leverage": p.get("leverage", 1),
                })
                total_pnl += p.get("unrealizedPnl", 0) or 0
        return {"positions": active, "total_pnl": total_pnl, "count": len(active)}
    except Exception as e:
        return {"error": str(e), "positions": [], "total_pnl": 0, "count": 0}

# ── Price Alerts ───────────────────────────────────────────────────

_alert_threads = {}

def alert_loop(alert_id, symbol, target, direction):
    ex = get_exchange()
    while _alert_threads.get(alert_id):
        try:
            ticker = ex.fetch_ticker(symbol)
            price = ticker["last"]
            triggered = False
            if direction == "above" and price >= target:
                triggered = True
            elif direction == "below" and price <= target:
                triggered = True

            if triggered:
                conn = sqlite3.connect(str(DB))
                conn.execute("UPDATE alerts SET triggered=1, active=0 WHERE id=?", (alert_id,))
                conn.commit(); conn.close()
                del _alert_threads[alert_id]
                print(f"🚨 Alert: {symbol} {direction} {target} — now at {price}")
                break
        except: pass
        time.sleep(30)

def start_alert(alert_id, symbol, target, direction):
    stop_alert(alert_id)
    t = threading.Thread(target=alert_loop, args=(alert_id, symbol, target, direction), daemon=True)
    _alert_threads[alert_id] = t
    t.start()

def stop_alert(alert_id):
    if alert_id in _alert_threads:
        del _alert_threads[alert_id]

# ── HTTP ────────────────────────────────────────────────────────────

HTML = """<!DOCTYPE html><html lang="zh-CN"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Portfolio Tracker</title>
<style>:root{--bg:#0a0f18;--card:rgba(255,255,255,.03);--text:#e0e8f0;--muted:#6b8299;--green:#10b981;--red:#ef4444;--accent:#2563eb}
*{margin:0;padding:0;box-sizing:border-box}body{font-family:-apple-system,sans-serif;background:var(--bg);color:var(--text);line-height:1.6}
.container{max-width:900px;margin:0 auto;padding:1.5rem}h1{font-size:1.4rem}h1 span{color:var(--accent)}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:.75rem;margin:1rem 0}
.card{background:var(--card);border-radius:12px;padding:1rem 1.25rem;border:1px solid rgba(255,255,255,.05)}
.card h3{font-size:.8rem;color:var(--muted);text-transform:uppercase;letter-spacing:.05em;margin-bottom:.5rem}
.metric .val{font-size:1.8rem;font-weight:800}.metric .sub{font-size:.8rem;color:var(--muted)}
table{width:100%;border-collapse:collapse;font-size:.85rem}
th{text-align:left;padding:.4rem .5rem;color:var(--muted);font-size:.7rem;text-transform:uppercase;border-bottom:1px solid rgba(255,255,255,.05)}
td{padding:.35rem .5rem;border-bottom:1px solid rgba(255,255,255,.03)}
.up{color:var(--green)}.down{color:var(--red)}
.btn{display:inline-block;padding:.4rem 1rem;border-radius:6px;font-weight:600;font-size:.8rem;cursor:pointer;border:none;color:#fff;background:var(--accent)}
input,select{width:100%;padding:.5rem .6rem;border-radius:6px;border:1px solid rgba(255,255,255,.1);background:rgba(255,255,255,.03);color:var(--text);font-size:.85rem}
label{font-size:.75rem;color:var(--muted);display:block;margin:.75rem 0 .2rem}
footer{text-align:center;padding:2rem;color:var(--muted);font-size:.75rem}
.pnl-bar{height:4px;border-radius:2px;margin-top:.25rem}
</style></head><body><div class="container">
<h1>📊 <span>Portfolio</span> Tracker</h1>
<p style="color:var(--muted);font-size:.85rem;margin-bottom:1rem">OKX · 实时持仓 · 盈亏追踪 · 价格提醒</p>

<div class="grid" id="overview"></div>
<div class="card" style="margin-bottom:1rem"><h3>📈 持仓</h3><div id="positions"></div></div>

<div style="display:grid;grid-template-columns:2fr 1fr;gap:1rem;">
<div class="card"><h3>💰 热门行情</h3><div id="tickers"></div></div>
<div class="card"><h3>🚨 价格提醒</h3><div id="alerts"></div>
<label>币种</label><input id="alert-symbol" placeholder="BTC/USDT">
<label>目标价</label><input id="alert-price" placeholder="50000">
<label>方向</label><select id="alert-dir"><option value="above">涨到以上</option><option value="below">跌到以下</option></select>
<button class="btn" onclick="addAlert()" style="margin-top:.5rem;width:100%">+ 添加提醒</button></div></div>
<footer>📊 Portfolio Tracker by Lighthouse Analytics · 数据来自 OKX</footer></div>
<script>
const A='';async function api(p,m='GET',b=null){const o={method:m,headers:{'Content-Type':'application/json'}};if(b)o.body=JSON.stringify(b);try{const r=await fetch(p,o);return r.json()}catch(e){return{}}}
async function load(){
  const d=await api('/api/summary');
  document.getElementById('overview').innerHTML=`
    <div class="card metric"><h3>总权益 (USDT)</h3><div class="val">${(d.balance?.total_usdt||0).toFixed(2)}</div></div>
    <div class="card metric"><h3>持仓盈亏</h3><div class="val ${d.positions?.total_pnl>=0?'up':'down'}">${(d.positions?.total_pnl||0).toFixed(2)}</div></div>
    <div class="card metric"><h3>持仓数</h3><div class="val">${d.positions?.count||0}</div></div>
    <div class="card metric"><h3>活跃提醒</h3><div class="val">${d.alerts?.active||0}</div></div>`;

  const tickers=d.tickers||{};
  document.getElementById('tickers').innerHTML='<table><tr><th>币种</th><th>价格</th><th>24h</th></tr>'+Object.entries(tickers).slice(0,8).map(([s,t])=>`<tr><td>${s}</td><td>${(t.last||0).toFixed(t.last<1?6:2)}</td><td class="${t.change_24h>=0?'up':'down'}">${(t.change_24h||0).toFixed(2)}%</td></tr>`).join('')+'</table>';

  const pos=d.positions?.positions||[];
  document.getElementById('positions').innerHTML=pos.length?`<table><tr><th>币种</th><th>方向</th><th>数量</th><th>开仓价</th><th>标记价</th><th>盈亏</th></tr>${pos.map(p=>`<tr><td>${p.symbol}</td><td class="${p.side==='long'?'up':'down'}">${p.side}</td><td>${p.amount}</td><td>${p.entry_price}</td><td>${p.mark_price}</td><td class="${p.pnl>=0?'up':'down'}">${(p.pnl||0).toFixed(2)} (${(p.pnl_pct||0).toFixed(2)}%)</td></tr>`).join('')}</table>`:'<p style="color:var(--muted)">暂无持仓。需要 OKX API Key 才能查看。</p>';

  const alerts=d.alerts?.list||[];
  document.getElementById('alerts').innerHTML=alerts.length?alerts.map(a=>`<div style="padding:.3rem 0;border-bottom:1px solid rgba(255,255,255,.03);display:flex;justify-content:space-between"><span>${a.symbol} ${a.direction} ${a.target_price}</span><span class="${a.triggered?'up':'down'}">${a.triggered?'✅ 触发':'⏳'}</span></div>`).join(''):'<p style="color:var(--muted)">暂无提醒</p>';
}
async function addAlert(){const s=document.getElementById('alert-symbol').value.trim().toUpperCase();const p=parseFloat(document.getElementById('alert-price').value);const d=document.getElementById('alert-dir').value;if(!s||!p)return;await api('/api/alerts','POST',{symbol:s,target_price:p,direction:d});document.getElementById('alert-symbol').value='';document.getElementById('alert-price').value='';load()}
load();setInterval(load,30000);
</script></body></html>"""

DEFAULT_SYMBOLS = ["BTC/USDT","ETH/USDT","SOL/USDT","WLD/USDT","DOGE/USDT","SUI/USDT","BNB/USDT","XRP/USDT"]

def get_summary():
    tickers = fetch_tickers(DEFAULT_SYMBOLS)
    balance = {}
    positions = {"positions":[], "total_pnl":0, "count":0}
    try:
        balance = fetch_balance()
        if balance.get("need_api_key"): balance = {"total_usdt": 0, "assets": {}, "note": "需要 OKX API Key"}
    except: pass
    try:
        positions = fetch_positions()
    except: pass

    conn = sqlite3.connect(str(DB))
    active_alerts = conn.execute("SELECT COUNT(*) as c FROM alerts WHERE active=1").fetchone()[0]
    alert_list = conn.execute("SELECT * FROM alerts ORDER BY created_at DESC LIMIT 20").fetchall()
    conn.close()

    return {
        "tickers": tickers if "error" not in tickers else {},
        "balance": balance,
        "positions": positions,
        "alerts": {"active": active_alerts, "list": [dict(r) for r in alert_list]},
    }

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/": self._html(HTML)
        elif self.path == "/api/summary": self._json(get_summary())
        else: self.send_error(404)

    def do_POST(self):
        body = self._body()
        if self.path == "/api/alerts":
            aid = secrets.token_hex(8)
            conn = sqlite3.connect(str(DB))
            conn.execute("INSERT INTO alerts (id,symbol,target_price,direction) VALUES (?,?,?,?)",
                         (aid, body["symbol"], body["target_price"], body["direction"]))
            conn.commit(); conn.close()
            start_alert(aid, body["symbol"], body["target_price"], body["direction"])
            self._json({"id": aid})
        elif self.path == "/api/apikey":
            conn = sqlite3.connect(str(DB))
            conn.execute("INSERT OR REPLACE INTO api_keys (exchange,api_key,secret,password) VALUES ('okx',?,?,?)",
                         (body.get("api_key",""), body.get("secret",""), body.get("password","")))
            conn.commit(); conn.close()
            self._json({"ok": True})

    def _html(self, c):
        self.send_response(200); self.send_header("Content-Type", "text/html; charset=utf-8"); self.end_headers()
        self.wfile.write(c.encode())
    def _json(self, d):
        self.send_response(200); self.send_header("Content-Type", "application/json"); self.end_headers()
        self.wfile.write(json.dumps(d, default=str).encode())
    def _body(self):
        l = int(self.headers.get("Content-Length", 0))
        return json.loads(self.rfile.read(l)) if l else {}
    def log_message(self, f, *a): pass

if __name__ == "__main__":
    print(f"📊 Portfolio Tracker → http://localhost:{PORT}")
    HTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
