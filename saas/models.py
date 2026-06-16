"""Database models for Lighthouse Analytics SaaS platform."""

import sqlite3
import hashlib
import secrets
import uuid
import os
from datetime import datetime, timedelta
from pathlib import Path
from contextlib import contextmanager

DB_PATH = Path(__file__).parent / "data" / "lighthouse.db"

# ── Password Hashing (PBKDF2-SHA256) ───────────────────────────

def hash_password(password: str) -> str:
    """Hash a password using PBKDF2-SHA256 with a random salt.
    Returns a string: pbkdf2:sha256:iterations$salt$hash"""
    iterations = 600_000
    salt = os.urandom(16)
    key = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, iterations)
    return f"pbkdf2:sha256:{iterations}${salt.hex()}${key.hex()}"


def verify_password(password: str, stored: str) -> bool:
    """Verify a password against a stored hash."""
    try:
        if stored.startswith("pbkdf2:sha256:"):
            # New format: pbkdf2:sha256:iterations$salt$hash
            _, _, params = stored.split(":", 2)
            iterations_str, salt_hex, key_hex = params.split("$")
            iterations = int(iterations_str)
            salt = bytes.fromhex(salt_hex)
            expected_key = bytes.fromhex(key_hex)
            new_key = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, iterations)
            return secrets.compare_digest(new_key, expected_key)
        elif len(stored) == 64:
            # Legacy SHA256 format — upgrade on successful login
            return stored == hashlib.sha256(password.encode()).hexdigest()
        else:
            return False
    except (ValueError, AttributeError):
        return False


def get_db():
    """Get a database connection."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


@contextmanager
def db_session():
    """Context manager for database transactions."""
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
    """Initialize database schema."""
    with db_session() as db:
        db.executescript("""
        -- Users
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            name TEXT NOT NULL,
            company TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            email_verified BOOLEAN DEFAULT 0,
            last_login TIMESTAMP
        );

        -- API Keys
        CREATE TABLE IF NOT EXISTS api_keys (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL REFERENCES users(id),
            key_hash TEXT UNIQUE NOT NULL,
            key_prefix TEXT NOT NULL,
            name TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_used TIMESTAMP,
            revoked BOOLEAN DEFAULT 0
        );

        -- Subscriptions
        CREATE TABLE IF NOT EXISTS subscriptions (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL REFERENCES users(id),
            plan TEXT NOT NULL DEFAULT 'free',
            status TEXT NOT NULL DEFAULT 'active',
            started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            current_period_start TIMESTAMP,
            current_period_end TIMESTAMP,
            canceled_at TIMESTAMP,
            payment_provider TEXT,
            provider_subscription_id TEXT
        );

        -- Payments
        CREATE TABLE IF NOT EXISTS payments (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL REFERENCES users(id),
            amount REAL NOT NULL,
            currency TEXT DEFAULT 'USD',
            status TEXT NOT NULL DEFAULT 'pending',
            provider TEXT NOT NULL,
            provider_payment_id TEXT,
            description TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            completed_at TIMESTAMP
        );

        -- License Keys (for offline/CLI validation)
        CREATE TABLE IF NOT EXISTS license_keys (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL REFERENCES users(id),
            license_key TEXT UNIQUE NOT NULL,
            plan TEXT NOT NULL,
            max_seats INTEGER DEFAULT 1,
            issued_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            expires_at TIMESTAMP,
            revoked BOOLEAN DEFAULT 0
        );

        -- Usage Tracking
        CREATE TABLE IF NOT EXISTS usage_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT REFERENCES users(id),
            api_key_id TEXT REFERENCES api_keys(id),
            action TEXT NOT NULL,
            repo_name TEXT,
            metadata TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        -- Teams
        CREATE TABLE IF NOT EXISTS teams (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            owner_id TEXT NOT NULL REFERENCES users(id),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS team_members (
            team_id TEXT NOT NULL REFERENCES teams(id),
            user_id TEXT NOT NULL REFERENCES users(id),
            role TEXT DEFAULT 'member',
            joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (team_id, user_id)
        );

        -- Password Reset Tokens
        CREATE TABLE IF NOT EXISTS reset_tokens (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL REFERENCES users(id),
            token TEXT UNIQUE NOT NULL,
            expires_at TIMESTAMP NOT NULL,
            used BOOLEAN DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        -- Email Verification Tokens
        CREATE TABLE IF NOT EXISTS verification_tokens (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL REFERENCES users(id),
            token TEXT UNIQUE NOT NULL,
            expires_at TIMESTAMP NOT NULL,
            used BOOLEAN DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        -- Indexes
        CREATE INDEX IF NOT EXISTS idx_api_keys_user ON api_keys(user_id);
        CREATE INDEX IF NOT EXISTS idx_subscriptions_user ON subscriptions(user_id);
        CREATE INDEX IF NOT EXISTS idx_payments_user ON payments(user_id);
        CREATE INDEX IF NOT EXISTS idx_license_keys_user ON license_keys(user_id);
        CREATE INDEX IF NOT EXISTS idx_usage_user ON usage_logs(user_id);
        CREATE INDEX IF NOT EXISTS idx_usage_date ON usage_logs(created_at);
        CREATE INDEX IF NOT EXISTS idx_reset_tokens_user ON reset_tokens(user_id);
        CREATE INDEX IF NOT EXISTS idx_verification_tokens_user ON verification_tokens(user_id);
        """)
    print("✅ Database initialized at", DB_PATH)


# ── User Operations ────────────────────────────────────────────

def create_user(email: str, password: str, name: str, company: str = None) -> dict:
    """Create a new user. Returns user dict or raises."""
    user_id = str(uuid.uuid4())
    password_hash = hash_password(password)

    with db_session() as db:
        try:
            db.execute(
                "INSERT INTO users (id, email, password_hash, name, company) VALUES (?, ?, ?, ?, ?)",
                (user_id, email.lower().strip(), password_hash, name.strip(), company)
            )
        except sqlite3.IntegrityError:
            raise ValueError(f"Email {email} already registered")

        # Create free subscription
        sub_id = str(uuid.uuid4())
        db.execute(
            "INSERT INTO subscriptions (id, user_id, plan, status) VALUES (?, ?, 'free', 'active')",
            (sub_id, user_id)
        )

        # Create default API key
        _create_api_key(db, user_id, "Default Key")

    return get_user_by_id(user_id)


def authenticate_user(email: str, password: str) -> dict | None:
    """Authenticate user by email and password."""
    with db_session() as db:
        row = db.execute(
            "SELECT * FROM users WHERE email = ?",
            (email.lower().strip(),)
        ).fetchone()

        if row and verify_password(password, row["password_hash"]):
            # Upgrade legacy hash on successful login
            if not row["password_hash"].startswith("pbkdf2:"):
                new_hash = hash_password(password)
                db.execute(
                    "UPDATE users SET password_hash = ? WHERE id = ?",
                    (new_hash, row["id"])
                )
                row = dict(row)
                row["password_hash"] = new_hash
            else:
                row = dict(row)

            db.execute(
                "UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE id = ?",
                (row["id"],)
            )
            return row

    return None


def get_user_by_id(user_id: str) -> dict | None:
    """Get user by ID."""
    with db_session() as db:
        row = db.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        return dict(row) if row else None


def get_user_by_email(email: str) -> dict | None:
    """Get user by email."""
    with db_session() as db:
        row = db.execute(
            "SELECT * FROM users WHERE email = ?", (email.lower().strip(),)
        ).fetchone()
        return dict(row) if row else None


def update_user(user_id: str, **kwargs) -> dict | None:
    """Update user fields. Only allowed keys: name, company."""
    allowed = {"name", "company"}
    updates = {k: v for k, v in kwargs.items() if k in allowed and v is not None}
    if not updates:
        return get_user_by_id(user_id)
    with db_session() as db:
        set_clause = ", ".join(f"{k} = ?" for k in updates)
        values = list(updates.values()) + [user_id]
        db.execute(f"UPDATE users SET {set_clause} WHERE id = ?", values)
        return get_user_by_id(user_id)


# ── Password Reset ─────────────────────────────────────────────

def create_reset_token(email: str) -> dict | None:
    """Create a password reset token. Returns token info or None if user not found."""
    user = get_user_by_email(email)
    if not user:
        return None

    token = secrets.token_urlsafe(32)
    token_id = str(uuid.uuid4())
    expires_at = (datetime.now() + timedelta(hours=1)).isoformat()

    with db_session() as db:
        db.execute(
            "INSERT INTO reset_tokens (id, user_id, token, expires_at) VALUES (?, ?, ?, ?)",
            (token_id, user["id"], token, expires_at)
        )

    return {
        "token": token,
        "expires_at": expires_at,
        "email": email,
    }


def verify_reset_token(token: str) -> dict | None:
    """Verify a reset token. Returns user dict if valid."""
    with db_session() as db:
        row = db.execute(
            """SELECT rt.*, u.email FROM reset_tokens rt
               JOIN users u ON rt.user_id = u.id
               WHERE rt.token = ? AND rt.used = 0 AND rt.expires_at > CURRENT_TIMESTAMP""",
            (token,)
        ).fetchone()
        return dict(row) if row else None


def consume_reset_token(token: str, new_password: str) -> bool:
    """Use a reset token to set a new password."""
    token_info = verify_reset_token(token)
    if not token_info:
        return False

    new_hash = hash_password(new_password)
    with db_session() as db:
        db.execute("UPDATE users SET password_hash = ? WHERE id = ?", (new_hash, token_info["user_id"]))
        db.execute("UPDATE reset_tokens SET used = 1 WHERE token = ?", (token,))
    return True


# ── Email Verification ─────────────────────────────────────────

def create_verification_token(user_id: str) -> dict:
    """Create an email verification token."""
    token = secrets.token_urlsafe(32)
    token_id = str(uuid.uuid4())
    expires_at = (datetime.now() + timedelta(days=7)).isoformat()

    with db_session() as db:
        db.execute(
            "INSERT INTO verification_tokens (id, user_id, token, expires_at) VALUES (?, ?, ?, ?)",
            (token_id, user_id, token, expires_at)
        )

    return {"token": token, "expires_at": expires_at}


def verify_email(token: str) -> bool:
    """Verify an email using a verification token."""
    with db_session() as db:
        row = db.execute(
            "SELECT * FROM verification_tokens WHERE token = ? AND used = 0 AND expires_at > CURRENT_TIMESTAMP",
            (token,)
        ).fetchone()
        if not row:
            return False
        db.execute("UPDATE users SET email_verified = 1 WHERE id = ?", (row["user_id"],))
        db.execute("UPDATE verification_tokens SET used = 1 WHERE token = ?", (token,))
        return True


# ── API Key Operations ─────────────────────────────────────────

def _create_api_key(db, user_id: str, name: str) -> dict:
    """Internal: create an API key."""
    key_id = str(uuid.uuid4())
    raw_key = f"chm_{secrets.token_hex(24)}"
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
    key_prefix = raw_key[:11]

    db.execute(
        "INSERT INTO api_keys (id, user_id, key_hash, key_prefix, name) VALUES (?, ?, ?, ?, ?)",
        (key_id, user_id, key_hash, key_prefix, name)
    )
    return {"id": key_id, "key": raw_key, "prefix": key_prefix, "name": name}


def create_api_key(user_id: str, name: str) -> dict:
    """Create a new API key for a user. Returns dict with 'key' (show once!)."""
    with db_session() as db:
        return _create_api_key(db, user_id, name)


def list_api_keys(user_id: str) -> list[dict]:
    """List all API keys for a user (never returns raw keys)."""
    with db_session() as db:
        rows = db.execute(
            "SELECT id, key_prefix, name, created_at, last_used, revoked FROM api_keys WHERE user_id = ? ORDER BY created_at DESC",
            (user_id,)
        ).fetchall()
        return [dict(r) for r in rows]


def validate_api_key(raw_key: str) -> dict | None:
    """Validate an API key. Returns user dict if valid."""
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()

    with db_session() as db:
        row = db.execute(
            """SELECT ak.*, u.email, u.name as user_name, s.plan, s.status as sub_status
               FROM api_keys ak
               JOIN users u ON ak.user_id = u.id
               JOIN subscriptions s ON s.user_id = u.id
               WHERE ak.key_hash = ? AND ak.revoked = 0 AND s.status = 'active'""",
            (key_hash,)
        ).fetchone()

        if row:
            db.execute(
                "UPDATE api_keys SET last_used = CURRENT_TIMESTAMP WHERE id = ?",
                (row["id"],)
            )
            return dict(row)

    return None


# ── Subscription Operations ────────────────────────────────────

PLANS = {
    "free": {"price": 0, "max_repos": 3, "max_team_members": 1, "features": ["terminal", "json"]},
    "pro": {"price": 29, "max_repos": 50, "max_team_members": 10, "features": ["terminal", "json", "html", "history", "email_reports"]},
    "enterprise": {"price": 99, "max_repos": 999, "max_team_members": 999, "features": ["terminal", "json", "html", "history", "email_reports", "ci_cd", "sso", "audit_log"]},
}


def get_subscription(user_id: str) -> dict | None:
    """Get current subscription for a user (active or trialing)."""
    with db_session() as db:
        row = db.execute(
            "SELECT * FROM subscriptions WHERE user_id = ? AND status IN ('active', 'trialing') ORDER BY started_at DESC LIMIT 1",
            (user_id,)
        ).fetchone()
        if row:
            sub = dict(row)
            sub["plan_details"] = PLANS.get(sub["plan"], PLANS["free"])
            return sub
        return None


def change_plan(user_id: str, new_plan: str, payment_provider: str = None) -> dict:
    """Change subscription plan."""
    if new_plan not in PLANS:
        raise ValueError(f"Invalid plan: {new_plan}")

    with db_session() as db:
        # Deactivate current subscription
        db.execute(
            "UPDATE subscriptions SET status = 'inactive', canceled_at = CURRENT_TIMESTAMP WHERE user_id = ? AND status IN ('active', 'trialing')",
            (user_id,)
        )

        # Create new subscription
        sub_id = str(uuid.uuid4())
        now = datetime.now()
        period_end = now + timedelta(days=30)

        db.execute(
            """INSERT INTO subscriptions (id, user_id, plan, status, started_at, current_period_start, current_period_end, payment_provider)
               VALUES (?, ?, ?, 'active', ?, ?, ?, ?)""",
            (sub_id, user_id, new_plan, now.isoformat(), now.isoformat(), period_end.isoformat(), payment_provider)
        )

        return get_subscription(user_id)


# ── License Key Operations ─────────────────────────────────────

def generate_license_key(user_id: str, plan: str, max_seats: int = 1, days_valid: int = 365) -> dict:
    """Generate a license key for offline/CLI use."""
    license_id = str(uuid.uuid4())
    raw_key = f"CHM-{secrets.token_hex(4).upper()}-{secrets.token_hex(4).upper()}-{secrets.token_hex(4).upper()}"

    expires_at = datetime.now() + timedelta(days=days_valid)

    with db_session() as db:
        db.execute(
            "INSERT INTO license_keys (id, user_id, license_key, plan, max_seats, expires_at) VALUES (?, ?, ?, ?, ?, ?)",
            (license_id, user_id, raw_key, plan, max_seats, expires_at.isoformat())
        )
        return {"id": license_id, "license_key": raw_key, "plan": plan, "expires_at": expires_at.isoformat()}


def validate_license_key(license_key: str) -> dict | None:
    """Validate a license key. Returns validation result."""
    with db_session() as db:
        row = db.execute(
            """SELECT lk.*, u.email, s.status as sub_status
               FROM license_keys lk
               JOIN users u ON lk.user_id = u.id
               LEFT JOIN subscriptions s ON s.user_id = u.id AND s.status = 'active'
               WHERE lk.license_key = ? AND lk.revoked = 0 AND lk.expires_at > CURRENT_TIMESTAMP""",
            (license_key,)
        ).fetchone()
        return dict(row) if row else None


# ── Payment Operations ─────────────────────────────────────────

def create_payment(user_id: str, amount: float, provider: str, currency: str = "USD", description: str = "") -> dict:
    """Record a new payment intent."""
    payment_id = str(uuid.uuid4())

    with db_session() as db:
        db.execute(
            "INSERT INTO payments (id, user_id, amount, currency, provider, description) VALUES (?, ?, ?, ?, ?, ?)",
            (payment_id, user_id, amount, currency, provider, description)
        )
        return {"id": payment_id, "amount": amount, "currency": currency, "status": "pending"}


def complete_payment(payment_id: str, provider_payment_id: str) -> dict:
    """Mark a payment as completed."""
    with db_session() as db:
        db.execute(
            "UPDATE payments SET status = 'completed', provider_payment_id = ?, completed_at = CURRENT_TIMESTAMP WHERE id = ?",
            (provider_payment_id, payment_id)
        )
        row = db.execute("SELECT * FROM payments WHERE id = ?", (payment_id,)).fetchone()
        return dict(row) if row else None


def get_payment_history(user_id: str) -> list[dict]:
    """Get payment history for a user."""
    with db_session() as db:
        rows = db.execute(
            "SELECT * FROM payments WHERE user_id = ? ORDER BY created_at DESC LIMIT 50",
            (user_id,)
        ).fetchall()
        return [dict(r) for r in rows]


def revoke_api_key(user_id: str, key_id: str) -> bool:
    """Revoke an API key."""
    with db_session() as db:
        cursor = db.execute(
            "UPDATE api_keys SET revoked = 1 WHERE id = ? AND user_id = ?",
            (key_id, user_id)
        )
        return cursor.rowcount > 0


# ── Usage Tracking ─────────────────────────────────────────────

def record_usage(user_id: str, action: str, repo_name: str = None, metadata: str = None):
    """Record a usage event."""
    with db_session() as db:
        db.execute(
            "INSERT INTO usage_logs (user_id, action, repo_name, metadata) VALUES (?, ?, ?, ?)",
            (user_id, action, repo_name, metadata)
        )


def get_usage_stats(user_id: str, days: int = 30) -> dict:
    """Get usage statistics for a user."""
    with db_session() as db:
        total = db.execute(
            "SELECT COUNT(*) as count FROM usage_logs WHERE user_id = ?",
            (user_id,)
        ).fetchone()["count"]

        recent = db.execute(
            "SELECT COUNT(*) as count FROM usage_logs WHERE user_id = ? AND created_at >= date('now', ? || ' days')",
            (user_id, f'-{days}')
        ).fetchone()["count"]

        unique_repos = db.execute(
            "SELECT COUNT(DISTINCT repo_name) as count FROM usage_logs WHERE user_id = ? AND repo_name IS NOT NULL",
            (user_id,)
        ).fetchone()["count"]

        return {
            "total_analyses": total,
            f"analyses_last_{days}_days": recent,
            "unique_repos": unique_repos,
        }


# ── Trial Management ───────────────────────────────────────────

def start_trial(user_id: str, plan: str = "pro", days: int = 14) -> dict:
    """Start a free trial for a paid plan."""
    sub_id = str(uuid.uuid4())
    now = datetime.now()
    trial_end = now + timedelta(days=days)

    with db_session() as db:
        # Deactivate current free sub
        db.execute(
            "UPDATE subscriptions SET status = 'inactive' WHERE user_id = ? AND status = 'active'",
            (user_id,)
        )
        # Create trial subscription
        db.execute(
            """INSERT INTO subscriptions (id, user_id, plan, status, started_at,
               current_period_start, current_period_end)
               VALUES (?, ?, ?, 'trialing', ?, ?, ?)""",
            (sub_id, user_id, plan, now.isoformat(), now.isoformat(), trial_end.isoformat())
        )
    return get_subscription(user_id)


def get_trial_status(user_id: str) -> dict:
    """Get trial status for a user. Returns days_left, is_active, etc."""
    sub = get_subscription(user_id)
    if not sub or sub.get("status") != "trialing":
        return {"in_trial": False, "days_left": 0, "plan": sub.get("plan", "free") if sub else "free"}

    end_str = sub.get("current_period_end")
    if not end_str:
        return {"in_trial": False, "days_left": 0}

    try:
        end = datetime.fromisoformat(end_str)
        days_left = (end - datetime.now()).days
    except (ValueError, TypeError):
        return {"in_trial": False, "days_left": 0}

    return {
        "in_trial": days_left > 0,
        "expired": days_left <= 0,
        "days_left": max(0, days_left),
        "plan": sub["plan"],
        "ends_at": end_str,
        "should_upgrade": days_left <= 3,
    }


def expire_trial(user_id: str) -> bool:
    """Expire a trial and downgrade to free."""
    sub = get_subscription(user_id)
    if not sub or sub.get("status") != "trialing":
        return False

    change_plan(user_id, "free")
    return True


def get_trials_ending_soon(days: int = 3) -> list[dict]:
    """Get all trials ending within N days (for reminder emails)."""
    cutoff = (datetime.now() + timedelta(days=days)).isoformat()
    now = datetime.now().isoformat()

    with db_session() as db:
        rows = db.execute(
            """SELECT s.*, u.email, u.name FROM subscriptions s
               JOIN users u ON s.user_id = u.id
               WHERE s.status = 'trialing'
               AND s.current_period_end BETWEEN ? AND ?
               ORDER BY s.current_period_end""",
            (now, cutoff)
        ).fetchall()
        return [dict(r) for r in rows]


# ── Dashboard ───────────────────────────────────────────────────

def get_business_dashboard() -> dict:
    """Get platform-wide business metrics."""
    with db_session() as db:
        total_users = db.execute("SELECT COUNT(*) as c FROM users").fetchone()["c"]
        paying_users = db.execute(
            "SELECT COUNT(DISTINCT user_id) as c FROM subscriptions WHERE plan != 'free' AND status = 'active'"
        ).fetchone()["c"]

        mrr_row = db.execute(
            """SELECT COALESCE(SUM(
                   CASE s.plan
                       WHEN 'pro' THEN 29
                       WHEN 'enterprise' THEN 99
                       ELSE 0
                   END
               ), 0) as mrr
               FROM subscriptions s WHERE s.status = 'active'"""
        ).fetchone()

        total_analyses = db.execute("SELECT COUNT(*) as c FROM usage_logs").fetchone()["c"]

        today = datetime.now().strftime("%Y-%m-%d")
        today_analyses = db.execute(
            "SELECT COUNT(*) as c FROM usage_logs WHERE date(created_at) = ?",
            (today,)
        ).fetchone()["c"]

        # Recent payments
        recent_payments = db.execute(
            "SELECT * FROM payments WHERE status = 'completed' ORDER BY completed_at DESC LIMIT 5"
        ).fetchall()

        return {
            "total_users": total_users,
            "paying_users": paying_users,
            "mrr": mrr_row["mrr"],
            "total_analyses": total_analyses,
            "today_analyses": today_analyses,
            "recent_payments": [dict(p) for p in recent_payments],
        }
