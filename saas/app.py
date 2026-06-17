#!/usr/bin/env python3
"""Lighthouse Analytics SaaS Platform — Flask Application.

Start with:
    cd saas && python app.py

Environment variables for production:
    SECRET_KEY=xxx          Flask secret key
    DATABASE_URL=...        Override default SQLite path
    STRIPE_SECRET_KEY=...   Stripe integration
    PAYPAL_CLIENT_ID=...    PayPal integration
    WECHAT_APP_ID=...       WeChat Pay integration
    ALIPAY_APP_ID=...       Alipay integration
    SMTP_HOST=...           Email sending
"""

import os
import json
import time
import secrets
import functools
from collections import defaultdict
from datetime import datetime, timedelta

from flask import (
    Flask, request, jsonify, render_template_string, session,
    redirect, url_for, make_response, g,
)

import models
from payments import get_providers, get_provider, any_provider_available

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", secrets.token_hex(32))
app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(hours=12)

# Ensure DB is initialized
models.init_db()

# ── Simple In-Memory Rate Limiter ──────────────────────────────

_rate_limits: dict[str, list[float]] = defaultdict(list)

def rate_limit(max_requests: int = 60, window: int = 60):
    """Decorator: limit requests per IP per window (seconds)."""
    def decorator(f):
        @functools.wraps(f)
        def wrapped(*args, **kwargs):
            ip = request.remote_addr or "127.0.0.1"
            now = time.time()
            window_start = now - window
            _rate_limits[ip] = [t for t in _rate_limits[ip] if t > window_start]
            if len(_rate_limits[ip]) >= max_requests:
                return jsonify({"error": "请求过于频繁，请稍后再试"}), 429
            _rate_limits[ip].append(now)
            return f(*args, **kwargs)
        return wrapped
    return decorator


# ── Authentication Helpers ─────────────────────────────────────

def login_required(f):
    """Decorator: require user to be logged in."""
    @functools.wraps(f)
    def decorated(*args, **kwargs):
        user_id = session.get("user_id")
        if not user_id:
            if request.is_json or request.headers.get("Accept") == "application/json":
                return jsonify({"error": "Authentication required"}), 401
            return redirect(url_for("login_page"))
        g.user = models.get_user_by_id(user_id)
        if not g.user:
            session.clear()
            return redirect(url_for("login_page"))
        return f(*args, **kwargs)
    return decorated


def api_key_required(f):
    """Decorator: require valid API key (for CLI/API access)."""
    @functools.wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get("Authorization", "")
        api_key = None

        if auth_header.startswith("Bearer "):
            api_key = auth_header[7:]
        elif auth_header.startswith("chm_"):
            api_key = auth_header

        if not api_key:
            return jsonify({"error": "API key required. Use Authorization: Bearer chm_..."}), 401

        result = models.validate_api_key(api_key)
        if not result:
            return jsonify({"error": "Invalid or revoked API key"}), 401

        g.api_key_info = result
        g.user = models.get_user_by_id(result["user_id"])
        return f(*args, **kwargs)
    return decorated


# ── Web UI Pages ───────────────────────────────────────────────

@app.route("/")
def index():
    """Landing page redirect to login or dashboard."""
    if session.get("user_id"):
        return redirect(url_for("dashboard"))
    return redirect(url_for("login_page"))


@app.route("/login")
def login_page():
    return _render_page("login.html", title="登录 — Lighthouse Analytics")


@app.route("/register")
def register_page():
    return _render_page("register.html", title="注册 — Lighthouse Analytics")


@app.route("/dashboard")
@login_required
def dashboard():
    return _render_page("dashboard.html", title="控制台 — Lighthouse Analytics", user=g.user)


@app.route("/pricing")
def pricing_page():
    user = None
    if session.get("user_id"):
        user = models.get_user_by_id(session["user_id"])
    return _render_page("pricing.html", title="定价 — Lighthouse Analytics", user=user)


@app.route("/settings")
@login_required
def settings_page():
    return _render_page("settings.html", title="设置 — Lighthouse Analytics", user=g.user)


@app.route("/demo")
def demo_page():
    """Free online demo — try CHM without installing."""
    demo_path = os.path.join(os.path.dirname(__file__), "..", "chuochuo", "store", "chm-demo.html")
    if os.path.exists(demo_path):
        return open(demo_path).read()
    return "<h1>Demo not found</h1>", 404


@app.route("/docs")
def docs_page():
    """Public documentation page."""
    user = None
    if session.get("user_id"):
        user = models.get_user_by_id(session["user_id"])
    return _render_page("docs.html", title="文档 — Lighthouse Analytics", user=user)


@app.route("/repos")
@login_required
def repos_page():
    return _render_page("repos.html", title="仓库仪表盘 — Lighthouse Analytics", user=g.user)


@app.route("/admin")
@login_required
def admin_page():
    """Simple admin panel for the business owner."""
    dashboard_data = models.get_business_dashboard()
    return _render_page("admin.html", title="管理后台 — Lighthouse Analytics", user=g.user, admin_data=dashboard_data)


# ── Auth API Endpoints ────────────────────────────────────────

@app.route("/api/auth/register", methods=["POST"])
@rate_limit(max_requests=10, window=300)  # 10 registrations per 5 min per IP
def api_register():
    data = request.get_json() or {}
    email = data.get("email", "").strip()
    password = data.get("password", "").strip()
    name = data.get("name", "").strip()
    company = data.get("company", "").strip() or None

    errors = []
    if not email or "@" not in email:
        errors.append("请输入有效的邮箱地址")
    if not password or len(password) < 6:
        errors.append("密码至少需要 6 个字符")
    if not name:
        errors.append("请输入姓名")

    if errors:
        return jsonify({"error": "; ".join(errors)}), 400

    try:
        user = models.create_user(email, password, name, company)
    except ValueError as e:
        return jsonify({"error": str(e)}), 409

    session["user_id"] = user["id"]
    return jsonify({"success": True, "user": {"id": user["id"], "email": user["email"], "name": user["name"]}}), 201


@app.route("/api/auth/login", methods=["POST"])
@rate_limit(max_requests=20, window=300)  # 20 login attempts per 5 min per IP
def api_login():
    data = request.get_json() or {}
    email = data.get("email", "").strip()
    password = data.get("password", "").strip()

    user = models.authenticate_user(email, password)
    if not user:
        return jsonify({"error": "邮箱或密码错误"}), 401

    session["user_id"] = user["id"]
    return jsonify({
        "success": True,
        "user": {"id": user["id"], "email": user["email"], "name": user["name"], "company": user.get("company")},
    })


@app.route("/api/auth/logout", methods=["POST"])
def api_logout():
    session.clear()
    return jsonify({"success": True})


@app.route("/api/auth/me")
@login_required
def api_me():
    sub = models.get_subscription(g.user["id"])
    return jsonify({
        "user": sanitize_user(g.user),
        "subscription": sub,
    })


# ── API Key Endpoints ─────────────────────────────────────────

@app.route("/api/keys", methods=["GET"])
@login_required
def api_list_keys():
    keys = models.list_api_keys(g.user["id"])
    return jsonify({"keys": keys})


@app.route("/api/keys", methods=["POST"])
@login_required
def api_create_key():
    data = request.get_json() or {}
    name = data.get("name", "Unnamed Key")
    result = models.create_api_key(g.user["id"], name)
    return jsonify(result), 201  # CAUTION: key is only returned ONCE here


@app.route("/api/keys/<key_id>", methods=["DELETE"])
@login_required
def api_revoke_key(key_id: str):
    """Revoke an API key."""
    ok = models.revoke_api_key(g.user["id"], key_id)
    if ok:
        return jsonify({"success": True, "message": "API key revoked"})
    return jsonify({"error": "Key not found"}), 404


# ── Trial Endpoints ────────────────────────────────────────────

@app.route("/api/trial/start", methods=["POST"])
@login_required
def api_start_trial():
    """Start a 14-day free trial of Pro."""
    data = request.get_json() or {}
    plan = data.get("plan", "pro")

    # Check if already had a trial
    with models.db_session() as db:
        prev = db.execute(
            "SELECT COUNT(*) as c FROM subscriptions WHERE user_id = ? AND status = 'trialing'",
            (g.user["id"],)
        ).fetchone()
        if prev["c"] > 0:
            return jsonify({"error": "你已经使用过免费试用"}), 400

    sub = models.start_trial(g.user["id"], plan)
    return jsonify({"success": True, "subscription": sub})


@app.route("/api/trial/status")
@login_required
def api_trial_status():
    """Get trial status for the current user."""
    status = models.get_trial_status(g.user["id"])
    return jsonify(status)


# ── Subscription Endpoints ─────────────────────────────────────

@app.route("/api/subscription")
@login_required
def api_subscription():
    sub = models.get_subscription(g.user["id"])
    return jsonify({"subscription": sub})


@app.route("/api/subscription/change", methods=["POST"])
@login_required
def api_change_plan():
    data = request.get_json() or {}
    new_plan = data.get("plan", "free")
    provider_name = data.get("provider")

    if new_plan == "free":
        # Downgrade is immediate
        sub = models.change_plan(g.user["id"], "free")
        return jsonify({"success": True, "subscription": sub})

    # For paid plans, create checkout session
    plan_info = models.PLANS.get(new_plan)
    if not plan_info or plan_info["price"] == 0:
        return jsonify({"error": "Invalid plan"}), 400

    provider = get_provider(provider_name) if provider_name else None
    if not provider:
        # Use first available provider
        providers = get_providers()
        available = [p for p in providers.values()]
        if available:
            provider = available[0]
        else:
            return jsonify({"error": "No payment provider configured"}), 503

    checkout = provider.create_checkout(
        amount=plan_info["price"],
        currency="USD",
        user_email=g.user["email"],
        plan=new_plan,
    )

    # Record payment intent
    models.create_payment(
        g.user["id"],
        plan_info["price"],
        provider.name(),
        description=f"Subscription to {new_plan} plan",
    )

    return jsonify(checkout)


@app.route("/api/payment/verify", methods=["POST"])
@login_required
def api_verify_payment():
    data = request.get_json() or {}
    session_id = data.get("session_id", "")
    provider_name = data.get("provider", "")

    provider = get_provider(provider_name)
    if not provider:
        return jsonify({"error": "Unknown payment provider"}), 400

    result = provider.verify_payment(session_id)
    if result["success"]:
        # Complete payment record
        payments = models.get_payment_history(g.user["id"])
        pending = [p for p in payments if p["status"] == "pending"]
        if pending:
            models.complete_payment(pending[0]["id"], result["provider_payment_id"])

        # Get plan from session
        plan = data.get("plan", "pro")
        models.change_plan(g.user["id"], plan, provider.name())
        return jsonify({"success": True, "plan": plan})

    return jsonify({"success": False, "error": "Payment verification failed"}), 400


# ── Demo Payment Simulation ────────────────────────────────────

@app.route("/demo-payment")
@login_required
def demo_payment():
    """Simulated payment page for demo purposes."""
    session_id = request.args.get("session", "")
    plan = request.args.get("plan", "pro")
    amount = request.args.get("amount", "29")
    return _render_page("demo_payment.html",
                        title="演示支付 — Lighthouse Analytics",
                        user=g.user,
                        session_id=session_id,
                        plan=plan,
                        amount=amount)


@app.route("/api/demo/complete-payment", methods=["POST"])
@login_required
def api_demo_complete():
    """Simulate completion of demo payment."""
    data = request.get_json() or {}
    plan = data.get("plan", "pro")
    provider = data.get("provider", "demo")

    # Record and complete a demo payment
    plan_info = models.PLANS.get(plan, models.PLANS["pro"])
    payment = models.create_payment(g.user["id"], plan_info["price"], provider,
                                     description=f"Demo: {plan} plan")
    models.complete_payment(payment["id"], f"demo_{secrets.token_hex(8)}")
    models.change_plan(g.user["id"], plan, provider)

    return jsonify({"success": True, "plan": plan})


# ── License Key Endpoints ─────────────────────────────────────

@app.route("/api/license", methods=["POST"])
@login_required
def api_generate_license():
    sub = models.get_subscription(g.user["id"])
    plan = sub["plan"] if sub else "free"

    if plan == "free":
        return jsonify({"error": "License keys require a paid plan"}), 402

    license_info = models.generate_license_key(g.user["id"], plan)
    return jsonify(license_info), 201


@app.route("/api/license/validate", methods=["POST"])
def api_validate_license():
    """Public endpoint: validate a license key (for CLI usage)."""
    data = request.get_json() or {}
    key = data.get("license_key", "").strip()

    if not key:
        return jsonify({"valid": False, "error": "No license key provided"}), 400

    result = models.validate_license_key(key)
    if result:
        return jsonify({
            "valid": True,
            "plan": result["plan"],
            "email": result["email"],
            "expires_at": result["expires_at"],
        })
    return jsonify({"valid": False, "error": "Invalid or expired license key"}), 403


# ── Password Reset Endpoints ───────────────────────────────────

@app.route("/api/auth/forgot-password", methods=["POST"])
@rate_limit(max_requests=3, window=300)
def api_forgot_password():
    """Send password reset email (stub: returns token directly in dev)."""
    data = request.get_json() or {}
    email = data.get("email", "").strip()

    if not email:
        return jsonify({"error": "请输入邮箱地址"}), 400

    token_info = models.create_reset_token(email)
    if not token_info:
        # Don't reveal whether the email exists
        return jsonify({"message": "如果该邮箱已注册，你会收到一封重置邮件"})

    # In production: send email with reset link
    # In development: return token directly
    reset_link = f"{request.host_url}reset-password?token={token_info['token']}"
    return jsonify({
        "message": "如果该邮箱已注册，你会收到一封重置邮件",
        "dev_reset_link": reset_link,
        "dev_token": token_info["token"],
    })


@app.route("/api/auth/reset-password", methods=["POST"])
@rate_limit(max_requests=5, window=300)
def api_reset_password():
    """Reset password using a reset token."""
    data = request.get_json() or {}
    token = data.get("token", "").strip()
    new_password = data.get("password", "").strip()

    if not token or len(new_password) < 6:
        return jsonify({"error": "密码至少需要 6 个字符"}), 400

    ok = models.consume_reset_token(token, new_password)
    if ok:
        return jsonify({"success": True, "message": "密码已重置，请登录"})
    return jsonify({"error": "重置链接无效或已过期"}), 400


# ── Email Verification Endpoints ────────────────────────────────

@app.route("/api/auth/verify-email", methods=["POST"])
def api_verify_email():
    """Verify email address."""
    data = request.get_json() or {}
    token = data.get("token", "").strip()

    if models.verify_email(token):
        return jsonify({"success": True, "message": "邮箱已验证"})
    return jsonify({"error": "验证链接无效或已过期"}), 400


@app.route("/api/auth/send-verification", methods=["POST"])
@login_required
def api_send_verification():
    """Send verification email (stub)."""
    token_info = models.create_verification_token(g.user["id"])
    return jsonify({
        "message": "验证邮件已发送（开发环境：token 在此返回）",
        "dev_token": token_info["token"],
    })


# ── Usage/CLI API Endpoints ───────────────────────────────────

@app.route("/api/usage/report", methods=["POST"])
@api_key_required
def api_report_usage():
    """CLI reports usage after analysis."""
    data = request.get_json() or {}
    models.record_usage(
        g.user["id"],
        data.get("action", "analyze"),
        data.get("repo_name"),
        json.dumps(data.get("metadata", {})) if data.get("metadata") else None,
    )
    return jsonify({"success": True})


@app.route("/api/usage/stats")
@login_required
def api_usage_stats():
    stats = models.get_usage_stats(g.user["id"])
    return jsonify(stats)


# ── Admin API ─────────────────────────────────────────────────

@app.route("/api/admin/dashboard")
@login_required
def api_admin_dashboard():
    """Admin-only: business dashboard data."""
    # In production, check admin role
    return jsonify(models.get_business_dashboard())


# ── Error Pages ────────────────────────────────────────────────

@app.errorhandler(404)
def not_found(e):
    if request.is_json or request.headers.get("Accept") == "application/json":
        return jsonify({"error": "Not found"}), 404
    return _render_page("error.html", title="404 — Lighthouse Analytics", code=404, message="页面未找到"), 404


@app.errorhandler(500)
def server_error(e):
    if request.is_json or request.headers.get("Accept") == "application/json":
        return jsonify({"error": "Internal server error"}), 500
    return _render_page("error.html", title="500 — Lighthouse Analytics", code=500, message="服务器错误"), 500


# ── Multi-Repo Dashboard ───────────────────────────────────────

# In-memory per-user repo data
_user_repos: dict[str, list[dict]] = {}


@app.route("/api/repos", methods=["GET"])
@login_required
def api_list_repos():
    """List user's tracked repositories."""
    repos = _user_repos.get(g.user["id"], [])
    return jsonify({"repos": repos})


@app.route("/api/repos", methods=["POST"])
@login_required
def api_add_repo():
    """Add a repo to the user's dashboard."""
    data = request.get_json() or {}
    repo_data = {
        "name": data.get("name", "unknown"),
        "path": data.get("path", ""),
        "health_score": data.get("health_score"),
        "total_commits": data.get("total_commits"),
        "total_files": data.get("total_files"),
        "bus_factor": data.get("bus_factor"),
        "last_analysis": datetime.now().isoformat(),
        "hotspots_count": data.get("hotspots_count", 0),
    }

    if g.user["id"] not in _user_repos:
        _user_repos[g.user["id"]] = []

    # Update existing or append
    existing = [r for r in _user_repos[g.user["id"]] if r["name"] == repo_data["name"]]
    if existing:
        existing[0].update(repo_data)
    else:
        _user_repos[g.user["id"]].append(repo_data)

    return jsonify({"success": True, "repo": repo_data}), 201


@app.route("/api/repos/compare")
@login_required
def api_compare_repos():
    """Compare health across all tracked repos."""
    repos = _user_repos.get(g.user["id"], [])
    if not repos:
        return jsonify({"repos": [], "summary": "No repos tracked yet"})

    scores = [r.get("health_score") or 0 for r in repos]
    avg_score = round(sum(scores) / len(scores), 1) if scores else 0

    return jsonify({
        "repos": repos,
        "count": len(repos),
        "avg_health_score": avg_score,
        "healthiest": max(repos, key=lambda r: r.get("health_score") or 0) if repos else None,
        "riskiest": min(repos, key=lambda r: r.get("health_score") or 100) if repos else None,
    })


# ── Report Sharing ─────────────────────────────────────────────

# In-memory store for shared reports (would be DB in production)
_shared_reports: dict[str, dict] = {}


@app.route("/api/reports/share", methods=["POST"])
@login_required
def api_share_report():
    """Share a report — returns a public link."""
    data = request.get_json() or {}
    report_data = data.get("report", {})

    share_id = secrets.token_urlsafe(12)
    _shared_reports[share_id] = {
        "user_id": g.user["id"],
        "created_at": datetime.now().isoformat(),
        "data": report_data,
    }

    share_url = f"{request.host_url}share/{share_id}"
    return jsonify({"share_id": share_id, "url": share_url}), 201


@app.route("/share/<share_id>")
def view_shared_report(share_id: str):
    """Public: view a shared report."""
    shared = _shared_reports.get(share_id)
    if not shared:
        return _render_page("error.html", code=404, message="报告不存在或已被删除"), 404

    data = shared["data"]
    score = data.get("health_score", 50)

    # Render hotspots table
    hotspots = data.get("hotspots", {}).get("top_hotspots", [])
    max_churn = max((h.get("total_churn", 1) for h in hotspots), default=1)
    hs_rows = ""
    for h in hotspots[:10]:
        pct = int(h.get("total_churn", 0) / max_churn * 100)
        cls = "hot" if pct > 66 else "warm" if pct > 33 else "cool"
        name = h["file"]
        if len(name) > 50:
            name = "..." + name[-47:]
        hs_rows += f'<tr><td title="{h["file"]}">{name}</td><td>{h["changes"]}</td><td><div class="bar-wrap"><div class="bar {cls}" style="width:{pct}%"></div><small>{h.get("total_churn",0)}</small></div></td></tr>'

    # Generate alerts
    alerts = _generate_report_alerts(data)
    alerts_html = "".join(
        f'<div class="alert alert-{a["level"]}">{a["text"]}</div>'
        for a in alerts
    )

    score_color = "#10b981" if score >= 70 else "#f59e0b" if score >= 40 else "#ef4444"
    score_label = "Healthy" if score >= 70 else "Fair" if score >= 40 else "Needs Work"

    return _render_page("shared_report.html",
                        repo_name=data.get("repo_name", "Unknown"),
                        date=shared["created_at"][:10],
                        score=score,
                        score_color=score_color,
                        score_label=score_label,
                        total_commits=data.get("total_commits", 0),
                        total_files=data.get("total_files", 0),
                        bus_factor=data.get("authors", {}).get("bus_factor", "—"),
                        total_churn=f"{data.get('hotspots', {}).get('total_churn', 0):,}",
                        hotspots_table=f'<table><thead><tr><th>File</th><th>Changes</th><th>Churn</th></tr></thead><tbody>{hs_rows}</tbody></table>' if hs_rows else '<p>No data</p>',
                        alerts=alerts_html if alerts_html else '<div class="alert alert-green">✅ No significant issues found</div>')


def _generate_report_alerts(data: dict) -> list[dict]:
    """Generate human-readable alerts from analysis data."""
    alerts = []
    authors = data.get("authors", {})
    bf = authors.get("bus_factor", 1)
    if bf == 1:
        alerts.append({"level": "red", "text": f"🚨 Bus factor = 1 — the project depends on a single person."})
    elif bf <= 2:
        alerts.append({"level": "yellow", "text": f"⚠️ Bus factor is {bf} — knowledge is concentrated in few hands."})

    hotspots = data.get("hotspots", {}).get("top_hotspots", [])
    total_churn = data.get("hotspots", {}).get("total_churn", 1)
    top3 = sum(h.get("total_churn", 0) for h in hotspots[:3])
    if total_churn > 0 and top3 / total_churn > 0.5:
        pct = int(top3 / total_churn * 100)
        alerts.append({"level": "yellow", "text": f"📊 Top 3 files account for {pct}% of all changes — consider refactoring."})

    risky = data.get("complexity", {}).get("risky_files", [])
    if len(risky) > 5:
        alerts.append({"level": "yellow", "text": f"🧩 {len(risky)} files have high complexity with low comment ratio."})

    if not alerts:
        alerts.append({"level": "green", "text": "✅ Codebase looks healthy! No critical issues detected."})

    return alerts


# ── Lead Capture ────────────────────────────────────────────────

# In-memory lead store (would be proper DB table in production)
_leads: list[dict] = []


@app.route("/api/leads/capture", methods=["POST"])
@rate_limit(max_requests=5, window=3600)
def api_capture_lead():
    """Capture email lead from landing pages."""
    data = request.get_json() or {}
    email = data.get("email", "").strip()

    if not email or "@" not in email:
        return jsonify({"error": "Invalid email"}), 400

    _leads.append({
        "email": email,
        "source": data.get("source", "unknown"),
        "timestamp": datetime.now().isoformat(),
        "ip": request.remote_addr,
    })

    # Log to file for persistence
    leads_file = os.path.join(os.path.dirname(__file__), "data", "leads.jsonl")
    os.makedirs(os.path.dirname(leads_file), exist_ok=True)
    with open(leads_file, "a") as f:
        f.write(json.dumps(_leads[-1]) + "\n")

    return jsonify({"success": True, "message": "Welcome aboard!"}), 201


@app.route("/api/leads/count")
@login_required
def api_leads_count():
    """Admin: count captured leads."""
    return jsonify({"total_leads": len(_leads)})


# ── Referral System ─────────────────────────────────────────────

_referrals: dict[str, dict] = {}


@app.route("/api/referral/generate", methods=["POST"])
@login_required
def api_generate_referral():
    """Generate a referral code for the current user."""
    code = f"REF_{g.user['id'][:6].upper()}{secrets.token_hex(4).upper()}"

    _referrals[code] = {
        "user_id": g.user["id"],
        "created_at": datetime.now().isoformat(),
        "uses": 0,
        "rewarded_months": 0,
    }

    referral_url = f"{request.host_url}register?ref={code}"
    return jsonify({
        "code": code,
        "url": referral_url,
        "reward": "你和朋友各得 1 个月专业版免费",
    }), 201


@app.route("/api/referral/apply", methods=["POST"])
def api_apply_referral():
    """Apply a referral code during registration."""
    data = request.get_json() or {}
    code = data.get("code", "").strip()

    ref = _referrals.get(code)
    if not ref:
        return jsonify({"error": "Invalid referral code"}), 400

    ref["uses"] += 1

    # Grant both referrer and new user 1 free month of Pro
    # In production: add credit to subscription
    return jsonify({
        "success": True,
        "message": "Referral applied! You and your friend each get 1 free month of Pro.",
        "reward": "1_month_pro",
    })


# ── Stripe Webhook ─────────────────────────────────────────────

@app.route("/api/stripe/webhook", methods=["POST"])
def api_stripe_webhook():
    """Handle Stripe webhook events for automatic subscription provisioning."""
    import stripe

    stripe.api_key = os.getenv("STRIPE_SECRET_KEY", "")
    payload = request.get_data(as_text=True)
    sig_header = request.headers.get("Stripe-Signature", "")

    # In production: verify webhook signature with STRIPE_WEBHOOK_SECRET
    # For now: parse the event directly
    try:
        event = json.loads(payload)
    except json.JSONDecodeError:
        return jsonify({"error": "Invalid payload"}), 400

    event_type = event.get("type", "")

    if event_type == "checkout.session.completed":
        session = event.get("data", {}).get("object", {})
        customer_email = session.get("customer_email") or session.get("metadata", {}).get("user_email")
        plan = session.get("metadata", {}).get("plan", "pro")

        if customer_email:
            user = models.get_user_by_email(customer_email)
            if user:
                models.change_plan(user["id"], plan, "stripe")
                record = models.create_payment(
                    user["id"],
                    (session.get("amount_total", 0) or 0) / 100,
                    "stripe",
                    description=f"Stripe webhook: {plan} plan",
                )
                models.complete_payment(record["id"], session.get("payment_intent", ""))
                print(f"  ✅ Webhook: upgraded {customer_email} to {plan}")

    return jsonify({"received": True})


# ── Test Utilities ──────────────────────────────────────────────

@app.route("/api/_test/reset-limits", methods=["POST"])
def api_test_reset_limits():
    """Reset rate limits (test only)."""
    _rate_limits.clear()
    return jsonify({"success": True})


# ── Health Check ───────────────────────────────────────────────

@app.route("/health")
def health():
    """Health check endpoint for monitoring."""
    return jsonify({
        "status": "healthy",
        "version": "0.2.0",
        "timestamp": datetime.now().isoformat(),
    })


# ── Helpers ───────────────────────────────────────────────────

def sanitize_user(user: dict) -> dict:
    """Remove sensitive fields from user dict."""
    safe = dict(user)
    safe.pop("password_hash", None)
    return safe


def _render_page(template_name: str, **context):
    """Render a page template from the templates directory."""
    template_path = os.path.join(app.root_path, "templates", template_name)
    if os.path.exists(template_path):
        with open(template_path) as f:
            template_str = f.read()
    else:
        template_str = f"<h1>{template_name}</h1><p>Template not found.</p>"

    # Add global context
    context["session"] = dict(session)
    return render_template_string(template_str, **context)


# ── Main ──────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys

    port = int(os.getenv("PORT", 5000))
    debug = os.getenv("FLASK_DEBUG", "1") == "1"

    print(f"""
╔══════════════════════════════════════════════╗
║  🏠  Lighthouse Analytics SaaS              ║
║  Codebase Health Monitor Platform           ║
║                                              ║
║  Running on: http://localhost:{port}          ║
║  API Docs:   http://localhost:{port}/docs     ║
║  Admin:      http://localhost:{port}/admin    ║
║                                              ║
║  Payment providers ready for keys:           ║
║    • Stripe   (STRIPE_SECRET_KEY)            ║
║    • PayPal   (PAYPAL_CLIENT_ID)             ║
║    • WeChat   (WECHAT_APP_ID)                ║
║    • Alipay   (ALIPAY_APP_ID)                ║
╚══════════════════════════════════════════════╝
    """)

    app.run(host="0.0.0.0", port=port, debug=debug)
