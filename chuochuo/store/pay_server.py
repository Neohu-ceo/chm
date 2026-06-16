#!/usr/bin/env python3
"""戳戳 Store — ¥1 Payment Server.

Start: python pay_server.py → http://localhost:5003
"""

import os, json, time, secrets, sqlite3
from datetime import datetime
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler

import stripe

STRIPE_KEY = os.getenv("STRIPE_SECRET_KEY", "")
if not STRIPE_KEY:
    print("⚠️  STRIPE_SECRET_KEY not set — payment will use demo mode")
stripe.api_key = STRIPE_KEY

DATA_DIR = Path(__file__).parent / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = DATA_DIR / "purchases.db"

def init_db():
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("""CREATE TABLE IF NOT EXISTS purchases (
        id TEXT PRIMARY KEY, email TEXT, amount INTEGER,
        session_id TEXT, payment_intent TEXT, status TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")
    conn.commit(); conn.close()
init_db()

TEMPLATE = (Path(__file__).parent / "index.html").read_text()

class StoreHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/" or self.path == "/index.html":
            self._html(TEMPLATE)
        elif self.path == "/api/stats":
            conn = sqlite3.connect(str(DB_PATH))
            count = conn.execute("SELECT COUNT(*) FROM purchases WHERE status='paid'").fetchone()[0]
            revenue_fen = conn.execute("SELECT COALESCE(SUM(amount),0) FROM purchases WHERE status='paid'").fetchone()[0]
            conn.close()
            self._json({"total_sales": count, "total_revenue_yuan": round(revenue_fen / 100, 2)})
        elif self.path.startswith("/download"):
            self.send_response(302)
            self.send_header("Location", "/chuochuo/desktop/pet_float.py")
            self.end_headers()
        else:
            self.send_error(404)

    def do_POST(self):
        if self.path == "/api/create-checkout":
            body = self._body()
            try:
                session = stripe.checkout.Session.create(
                    payment_method_types=["card", "alipay"],
                    line_items=[{
                        "price_data": {
                            "currency": body.get("currency", "cny"),
                            "product_data": {"name": "戳戳 ChuoChuo — 桌面宠物"},
                            "unit_amount": max(400, body.get("amount", 100)),  # Stripe min CNY: ¥4
                        },
                        "quantity": 1,
                    }],
                    mode="payment",
                    success_url="http://localhost:5003/?paid=1",
                    cancel_url="http://localhost:5003/?cancel=1",
                )
                # Record purchase intent
                conn = sqlite3.connect(str(DB_PATH))
                conn.execute("INSERT INTO purchases (id,session_id,amount,status) VALUES (?,?,?,'pending')",
                             (secrets.token_hex(8), session.id, body.get("amount", 100)))
                conn.commit(); conn.close()

                self._json({"url": session.url, "session_id": session.id})
            except Exception as e:
                self._json({"error": str(e)}, 500)

        elif self.path == "/api/webhook":
            payload = self._body()
            # In production: verify Stripe signature
            if payload.get("type") == "checkout.session.completed":
                sid = payload["data"]["object"]["id"]
                conn = sqlite3.connect(str(DB_PATH))
                conn.execute("UPDATE purchases SET status='paid',payment_intent=? WHERE session_id=?",
                             (payload["data"]["object"].get("payment_intent",""), sid))
                conn.commit(); conn.close()
            self._json({"received": True})

        else:
            self.send_error(404)

    def _html(self, content):
        self.send_response(200); self.send_header("Content-Type", "text/html")
        self.send_header("Access-Control-Allow-Origin", "*"); self.end_headers()
        self.wfile.write(content.encode())

    def _json(self, data, code=200):
        self.send_response(code); self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*"); self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def _body(self):
        length = int(self.headers.get("Content-Length", 0))
        return json.loads(self.rfile.read(length)) if length else {}

    def log_message(self, format, *args): pass

if __name__ == "__main__":
    port = 5003
    print(f"🏪 戳戳 Store → http://localhost:{port}")
    HTTPServer(("0.0.0.0", port), StoreHandler).serve_forever()
