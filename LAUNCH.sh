#!/bin/bash
# ============================================================================
# Lighthouse Analytics — One-Click Launch Script
# ============================================================================
# This script does EVERYTHING needed to take Lighthouse Analytics live.
# Run it once you have:
#   1. A GitHub account
#   2. A PyPI account (or API token)
#   3. Optional: Stripe/WeChat Pay keys
#   4. Optional: A domain name
#
# Usage:
#   chmod +x LAUNCH.sh
#   ./LAUNCH.sh
# ============================================================================

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
BOLD='\033[1m'
NC='\033[0m'

banner() {
    echo ""
    echo -e "${BLUE}╔══════════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║${NC}  ${BOLD}🏠 Lighthouse Analytics — LAUNCH${NC}             ${BLUE}║${NC}"
    echo -e "${BLUE}╚══════════════════════════════════════════════╝${NC}"
    echo ""
}

step() { echo -e "${GREEN}▶${NC} ${BOLD}$1${NC}"; }
info() { echo -e "  ${BLUE}ℹ${NC} $1"; }
ok() { echo -e "  ${GREEN}✅${NC} $1"; }
warn() { echo -e "  ${RED}⚠️${NC} $1"; }

banner

# ── Step 1: GitHub ─────────────────────────────────────────────
step "Step 1/5: GitHub Repository"

if git remote get-url origin &>/dev/null; then
    ok "GitHub remote already configured: $(git remote get-url origin)"
else
    echo ""
    info "Create a new repo on GitHub: https://github.com/new"
    echo "   Name: chm (or lighthouse-analytics)"
    echo "   Description: Codebase Health Monitor — illuminate the dark corners of your codebase"
    echo "   Do NOT initialize with README (we already have one)"
    echo ""
    read -p "  GitHub repo URL (e.g. git@github.com:YOU/chm.git): " REPO_URL

    if [ -n "$REPO_URL" ]; then
        git remote add origin "$REPO_URL"
        ok "Remote added: $REPO_URL"
    else
        warn "Skipped — you can add a remote later with: git remote add origin <url>"
    fi
fi

# Push if remote exists
if git remote get-url origin &>/dev/null; then
    info "Pushing to GitHub..."
    git branch -M main
    git push -u origin main && ok "Code pushed to GitHub!" || warn "Push failed. Check your SSH/HTTPS access."
fi

# ── Step 2: PyPI ───────────────────────────────────────────────
step "Step 2/5: PyPI Publication"

if [ -f product/dist/chm-0.1.0-py3-none-any.whl ]; then
    ok "Package already built: product/dist/"
else
    info "Building package..."
    cd product
    python3 -m build --wheel
    cd ..
    ok "Package built"
fi

echo ""
info "To publish to PyPI, you need a PyPI account and API token:"
echo "   1. Register at https://pypi.org"
echo "   2. Create API token at https://pypi.org/manage/account/token/"
echo "   3. Set the token: export TWINE_USERNAME=__token__ && export TWINE_PASSWORD=pypi-xxx"
echo ""

read -p "  Publish to PyPI now? (y/n): " PUBLISH
if [ "$PUBLISH" = "y" ] || [ "$PUBLISH" = "Y" ]; then
    pip3 install twine 2>/dev/null || pip install twine
    python3 -m twine upload product/dist/*
    ok "Published to PyPI! pip install chm"
else
    warn "Skipped. Publish later with: twine upload product/dist/*"
fi

# ── Step 3: Payment Keys ───────────────────────────────────────
step "Step 3/5: Payment Integration"

cat << 'PAYEOF'
Configure payment providers by setting environment variables.

Stripe:
  export STRIPE_SECRET_KEY=sk_live_xxx
  export STRIPE_PRICE_IDS='{"pro":"price_xxx","enterprise":"price_yyy"}'

WeChat Pay:
  export WECHAT_APP_ID=xxx
  export WECHAT_MCH_ID=xxx
  export WECHAT_API_KEY=xxx

Alipay:
  export ALIPAY_APP_ID=xxx

PayPal:
  export PAYPAL_CLIENT_ID=xxx
  export PAYPAL_SECRET=xxx

PAYEOF

read -p "  Configure any payment keys now? (y/n): " CONFIG_PAY
if [ "$CONFIG_PAY" = "y" ] || [ "$CONFIG_PAY" = "Y" ]; then
    read -p "  Stripe Secret Key (or Enter to skip): " STRIPE_KEY
    [ -n "$STRIPE_KEY" ] && export STRIPE_SECRET_KEY="$STRIPE_KEY" && ok "Stripe configured"

    read -p "  WeChat App ID (or Enter to skip): " WECHAT_APP
    [ -n "$WECHAT_APP" ] && export WECHAT_APP_ID="$WECHAT_APP" && ok "WeChat Pay configured"

    read -p "  Alipay App ID (or Enter to skip): " ALIPAY_APP
    [ -n "$ALIPAY_APP" ] && export ALIPAY_APP_ID="$ALIPAY_APP" && ok "Alipay configured"
fi

# ── Step 4: Start Services ─────────────────────────────────────
step "Step 4/5: Start SaaS Platform"

# Kill any existing instance
pkill -f "python.*server.py" 2>/dev/null || true
sleep 1

# Start production server
cd "$(dirname "$0")/saas"
nohup ../product/.venv/bin/python server.py > ../ops/data/server.log 2>&1 &
sleep 2

if curl -s http://localhost:5001/health >/dev/null 2>&1; then
    ok "SaaS platform running on http://localhost:5001"
else
    warn "Server may not have started. Check ops/data/server_error.log"
fi

# ── Step 5: Launch Summary ─────────────────────────────────────
step "Step 5/5: Launch Complete!"

echo ""
echo -e "${BOLD}🌐 Your Links:${NC}"
echo "   Website:     http://localhost:5001"
echo "   Login:       http://localhost:5001/login"
echo "   Pricing:     http://localhost:5001/pricing"
echo "   Admin:       http://localhost:5001/admin"
echo "   Health:      http://localhost:5001/health"
echo "   Free Report: http://localhost:5001/../website/free-report.html"
echo ""
echo -e "${BOLD}📦 Product:${NC}"
echo "   Local install:  pip install -e product/"
echo "   PyPI (if published): pip install chm"
echo "   CLI command:     chm analyze ."
echo ""
echo -e "${BOLD}⏰ Automation:${NC}"
echo "   Daily health check:  9:07 AM"
echo "   Weekly report:       Monday 9:37 AM"
echo "   Server auto-restart: launchd KeepAlive"
echo ""
echo -e "${GOLD}🚀 Lighthouse Analytics is LIVE!${NC}"
