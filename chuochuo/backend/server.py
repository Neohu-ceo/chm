"""戳戳 ChuoChuo — Backend API Server.

Device pairing · interaction sync · leaderboard · expression marketplace · subscriptions.
"""

import os
import json
import time
import secrets
import hashlib
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from contextlib import contextmanager

from flask import Flask, request, jsonify, session, g, redirect, url_for
import functools

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", secrets.token_hex(32))

DB_PATH = Path(__file__).parent / "data" / "chuochuo.db"
DB_PATH.parent.mkdir(parents=True, exist_ok=True)


def get_db():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


@contextmanager
def db_session():
    conn = get_db()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    with db_session() as db:
        db.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE,
            password_hash TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS devices (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL REFERENCES users(id),
            device_name TEXT NOT NULL,
            device_secret TEXT NOT NULL,
            firmware_version TEXT DEFAULT '1.0.0',
            paired_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_seen TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS interactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            device_id TEXT NOT NULL REFERENCES devices(id),
            type TEXT NOT NULL,  -- 'poke', 'shake', 'squeeze', 'pet'
            intensity INTEGER DEFAULT 1,
            emotion_before TEXT,
            emotion_after TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS emotions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            device_id TEXT NOT NULL REFERENCES devices(id),
            emotion TEXT NOT NULL,
            triggered_by TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS expressions (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            creator_id TEXT REFERENCES users(id),
            pixel_data TEXT NOT NULL,
            animation_frames INTEGER DEFAULT 1,
            price INTEGER DEFAULT 0,
            downloads INTEGER DEFAULT 0,
            category TEXT DEFAULT 'basic',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS owned_expressions (
            user_id TEXT NOT NULL REFERENCES users(id),
            expression_id TEXT NOT NULL REFERENCES expressions(id),
            acquired_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (user_id, expression_id)
        );

        CREATE TABLE IF NOT EXISTS leaderboard (
            user_id TEXT PRIMARY KEY REFERENCES users(id),
            total_pokes INTEGER DEFAULT 0,
            total_shakes INTEGER DEFAULT 0,
            streak_days INTEGER DEFAULT 0,
            last_active DATE,
            weekly_score INTEGER DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS subscriptions (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL REFERENCES users(id),
            plan TEXT DEFAULT 'free',
            status TEXT DEFAULT 'active',
            started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            expires_at TIMESTAMP
        );

        -- Seed default expressions
        INSERT OR IGNORE INTO expressions (id, name, creator_id, pixel_data, animation_frames, price, category)
        VALUES
        ('happy', '开心', 'system', '0011100001001000100000010100001001000000001001000100001000111100', 2, 0, 'basic'),
        ('sleepy', '困了', 'system', '0000000000000000011110000100010001000100000000000001100000100000', 2, 0, 'basic'),
        ('angry', '生气', 'system', '0100001000000000011110000100010000000000010010000000000001100000', 2, 0, 'basic'),
        ('surprised', '惊讶', 'system', '0011100001001000000000000111100000000000010010000000000000000000', 2, 0, 'basic'),
        ('heart', '爱心', 'system', '0000000001100110011111100111110001111100001110000011100000000000', 1, 0, 'basic'),
        ('party', '派对', 'system', '0101010010101010010101001010101001010100101010100101010010101010', 4, 3, 'premium');
        """)
    print("✅ 戳戳 DB initialized")


init_db()

# ── Auth ─────────────────────────────────────────────────────────

def login_required(f):
    @functools.wraps(f)
    def wrapped(*args, **kwargs):
        user_id = session.get("user_id")
        if not user_id:
            return jsonify({"error": "请先登录"}), 401
        g.user = dict(get_db().execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone() or {})
        return f(*args, **kwargs)
    return wrapped


@app.route("/api/auth/register", methods=["POST"])
def register():
    d = request.get_json() or {}
    uid = secrets.token_hex(16)
    pw = hashlib.sha256(d.get("password", "").encode()).hexdigest()
    try:
        with db_session() as db:
            db.execute("INSERT INTO users (id,username,email,password_hash) VALUES (?,?,?,?)",
                       (uid, d["username"], d.get("email"), pw))
            db.execute("INSERT INTO subscriptions (id,user_id,plan) VALUES (?,?,'free')",
                       (secrets.token_hex(8), uid))
            db.execute("INSERT INTO leaderboard (user_id) VALUES (?)", (uid,))
        session["user_id"] = uid
        return jsonify({"success": True, "user_id": uid}), 201
    except sqlite3.IntegrityError:
        return jsonify({"error": "用户名已存在"}), 409


@app.route("/api/auth/login", methods=["POST"])
def login():
    d = request.get_json() or {}
    pw = hashlib.sha256(d.get("password", "").encode()).hexdigest()
    row = get_db().execute("SELECT * FROM users WHERE username=? AND password_hash=?",
                           (d.get("username"), pw)).fetchone()
    if row:
        session["user_id"] = row["id"]
        return jsonify({"success": True, "user_id": row["id"]})
    return jsonify({"error": "用户名或密码错误"}), 401


# ── Device Pairing ──────────────────────────────────────────────

@app.route("/api/devices/pair", methods=["POST"])
@login_required
def pair_device():
    d = request.get_json() or {}
    device_id = secrets.token_hex(8)
    device_secret = secrets.token_hex(16)
    with db_session() as db:
        db.execute("INSERT INTO devices (id,user_id,device_name,device_secret) VALUES (?,?,?,?)",
                   (device_id, g.user["id"], d.get("name", "我的戳戳"), device_secret))
    return jsonify({"device_id": device_id, "secret": device_secret, "name": d.get("name")}), 201


@app.route("/api/devices", methods=["GET"])
@login_required
def list_devices():
    rows = get_db().execute("SELECT * FROM devices WHERE user_id=?", (g.user["id"],)).fetchall()
    return jsonify({"devices": [dict(r) for r in rows]})


# ── Interactions ────────────────────────────────────────────────

@app.route("/api/interactions", methods=["POST"])
def record_interaction():
    """Called by device firmware or app to log an interaction."""
    d = request.get_json() or {}
    device_id = d.get("device_id")
    secret = d.get("secret")

    # Verify device ownership
    dev = get_db().execute("SELECT * FROM devices WHERE id=? AND device_secret=?",
                           (device_id, secret)).fetchone()
    if not dev:
        return jsonify({"error": "设备未配对"}), 403

    with db_session() as db:
        db.execute("INSERT INTO interactions (device_id,type,intensity,emotion_before,emotion_after) VALUES (?,?,?,?,?)",
                   (device_id, d.get("type"), d.get("intensity", 1), d.get("emotion_before"), d.get("emotion_after")))
        db.execute("UPDATE devices SET last_seen=CURRENT_TIMESTAMP WHERE id=?", (device_id,))
        # Update leaderboard
        db.execute("UPDATE leaderboard SET total_pokes=total_pokes+1, last_active=DATE('now'), weekly_score=weekly_score+1 WHERE user_id=?",
                   (dev["user_id"],))

    # Check for streak
    update_streak(dev["user_id"])
    return jsonify({"success": True})


def update_streak(user_id):
    db = get_db()
    today = datetime.now().date()
    lb = db.execute("SELECT * FROM leaderboard WHERE user_id=?", (user_id,)).fetchone()
    if lb and lb["last_active"]:
        last = datetime.fromisoformat(lb["last_active"]).date()
        if last == today - timedelta(days=1):
            db.execute("UPDATE leaderboard SET streak_days=streak_days+1 WHERE user_id=?", (user_id,))
            db.commit()
        elif last != today:
            db.execute("UPDATE leaderboard SET streak_days=1 WHERE user_id=?", (user_id,))
            db.commit()


# ── Leaderboard ─────────────────────────────────────────────────

@app.route("/api/leaderboard", methods=["GET"])
def get_leaderboard():
    board = "weekly" if request.args.get("type") == "weekly" else "alltime"
    if board == "weekly":
        rows = get_db().execute("""
            SELECT u.username, l.total_pokes, l.streak_days, l.weekly_score
            FROM leaderboard l JOIN users u ON l.user_id=u.id
            ORDER BY l.weekly_score DESC LIMIT 20
        """).fetchall()
    else:
        rows = get_db().execute("""
            SELECT u.username, l.total_pokes, l.streak_days, l.weekly_score
            FROM leaderboard l JOIN users u ON l.user_id=u.id
            ORDER BY l.total_pokes DESC LIMIT 20
        """).fetchall()
    return jsonify({"leaderboard": [dict(r) for r in rows]})


@app.route("/api/stats", methods=["GET"])
@login_required
def get_stats():
    db = get_db()
    lb = db.execute("SELECT * FROM leaderboard WHERE user_id=?", (g.user["id"],)).fetchone()
    devices = db.execute("SELECT COUNT(*) as c FROM devices WHERE user_id=?", (g.user["id"],)).fetchone()
    today_pokes = db.execute(
        "SELECT COUNT(*) as c FROM interactions i JOIN devices d ON i.device_id=d.id WHERE d.user_id=? AND DATE(i.created_at)=DATE('now')",
        (g.user["id"],)).fetchone()
    return jsonify({
        "total_pokes": lb["total_pokes"] if lb else 0,
        "streak_days": lb["streak_days"] if lb else 0,
        "weekly_score": lb["weekly_score"] if lb else 0,
        "devices": devices["c"] if devices else 0,
        "today_pokes": today_pokes["c"] if today_pokes else 0,
    })


# ── Expression Marketplace ──────────────────────────────────────

@app.route("/api/expressions", methods=["GET"])
def list_expressions():
    category = request.args.get("category", "all")
    if category == "all":
        rows = get_db().execute("SELECT * FROM expressions ORDER BY downloads DESC LIMIT 50").fetchall()
    else:
        rows = get_db().execute("SELECT * FROM expressions WHERE category=? ORDER BY downloads DESC LIMIT 50",
                                (category,)).fetchall()
    return jsonify({"expressions": [dict(r) for r in rows]})


@app.route("/api/expressions/purchase", methods=["POST"])
@login_required
def purchase_expression():
    d = request.get_json() or {}
    expr_id = d.get("expression_id")
    expr = get_db().execute("SELECT * FROM expressions WHERE id=?", (expr_id,)).fetchone()
    if not expr:
        return jsonify({"error": "表情不存在"}), 404
    if expr["price"] > 0:
        # In production: check payment
        pass
    with db_session() as db:
        try:
            db.execute("INSERT INTO owned_expressions (user_id,expression_id) VALUES (?,?)",
                       (g.user["id"], expr_id))
            db.execute("UPDATE expressions SET downloads=downloads+1 WHERE id=?", (expr_id,))
        except sqlite3.IntegrityError:
            return jsonify({"error": "已拥有"}), 409
    return jsonify({"success": True})


@app.route("/api/expressions/mine", methods=["GET"])
@login_required
def my_expressions():
    rows = get_db().execute(
        "SELECT e.* FROM expressions e JOIN owned_expressions o ON e.id=o.expression_id WHERE o.user_id=?",
        (g.user["id"],)).fetchall()
    return jsonify({"expressions": [dict(r) for r in rows]})


# ── Subscriptions ───────────────────────────────────────────────

@app.route("/api/subscription", methods=["GET"])
@login_required
def get_subscription():
    row = get_db().execute(
        "SELECT * FROM subscriptions WHERE user_id=? AND status='active' ORDER BY started_at DESC LIMIT 1",
        (g.user["id"],)).fetchone()
    return jsonify({"subscription": dict(row) if row else {"plan": "free"}})


@app.route("/api/subscription/upgrade", methods=["POST"])
@login_required
def upgrade_subscription():
    """Creates Stripe checkout session for Pro upgrade."""
    d = request.get_json() or {}
    plan = d.get("plan", "pro")

    # Deactivate current
    with db_session() as db:
        db.execute("UPDATE subscriptions SET status='inactive' WHERE user_id=? AND status='active'",
                   (g.user["id"],))
        sid = secrets.token_hex(8)
        db.execute("INSERT INTO subscriptions (id,user_id,plan,status,expires_at) VALUES (?,?,?,'active',?)",
                   (sid, g.user["id"], plan, (datetime.now() + timedelta(days=30)).isoformat()))

    return jsonify({"success": True, "plan": plan})


# ── Health ──────────────────────────────────────────────────────

@app.route("/health")
def health():
    return jsonify({"status": "healthy", "product": "chuochuo", "version": "0.1.0"})


if __name__ == "__main__":
    print("🖐️  戳戳 Backend starting on :5002")
    app.run(host="0.0.0.0", port=5002, debug=True)
