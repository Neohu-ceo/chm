#!/usr/bin/env python3
"""Bounty Orchestrator — the never-sleeping agent.

Finds → evaluates → claims → builds → submits → tracks.
Runs continuously. Each cycle: scout, triage, act, report.
"""

import json, time, signal, sys, urllib.request
from datetime import datetime
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"
DATA_DIR.mkdir(exist_ok=True)
STATE_FILE = DATA_DIR / "orchestrator_state.json"
EARNINGS_FILE = DATA_DIR / "earnings.json"

WALLET = "0xD796a580F33024C1A8dD99F60c67675EAB1112be"

# ── Configuration ──────────────────────────────────────────────

MAX_CONCURRENT_BOUNTIES = 3      # Don't spread too thin
MIN_BOUNTY_VALUE = 10            # Skip <$10 bounties
MAX_COMPETITION = 5              # Skip if >5 others claimed
CLAIM_COOLDOWN_MINUTES = 30      # Wait between claims
SCOUT_INTERVAL_SECONDS = 900     # Scout every 15 minutes

# ── State Management ───────────────────────────────────────────

def load_state() -> dict:
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return {
        "total_discovered": 0,
        "total_claimed": 0,
        "total_submitted": 0,
        "total_merged": 0,
        "total_earned_usd": 0,
        "active_bounties": [],
        "last_scout": None,
        "last_claim": None,
        "started_at": datetime.now().isoformat(),
    }

def save_state(state: dict):
    STATE_FILE.write_text(json.dumps(state, indent=2, default=str))

def load_earnings() -> dict:
    if EARNINGS_FILE.exists():
        return json.loads(EARNINGS_FILE.read_text())
    return {"transactions": [], "total": 0}

def save_earnings(earnings: dict):
    EARNINGS_FILE.write_text(json.dumps(earnings, indent=2, default=str))


class BountyOrchestrator:
    """The main agent. Coordinates scouting, claiming, building, tracking."""

    def __init__(self, github_token: str):
        self.token = github_token
        self.state = load_state()
        self.running = True

        signal.signal(signal.SIGINT, self._shutdown)
        signal.signal(signal.SIGTERM, self._shutdown)

    def _shutdown(self, signum=None, frame=None):
        print("\n👋 Orchestrator shutting down...")
        self.running = False

    def run(self):
        """Main loop. Runs until stopped."""
        print(f"""
╔══════════════════════════════════════════╗
║  🏭 Lighthouse Bounty Orchestrator      ║
║  Wallet: {WALLET[:20]}... ║
║  Auto-scout · Auto-claim · Auto-build   ║
╚══════════════════════════════════════════╝
""")
        print(f"  Started: {self.state['started_at']}")
        print(f"  Lifetime earnings: ${self.state['total_earned_usd']}")
        print(f"  Active bounties: {len(self.state['active_bounties'])}")
        print()

        cycle = 0
        while self.running:
            cycle += 1
            print(f"┌─ Cycle #{cycle} — {datetime.now().strftime('%H:%M:%S')}")

            # 1. Scout: find new bounties
            self._scout()

            # 2. Triage: evaluate and pick the best
            candidates = self._triage()

            # 3. Act: claim and build
            if candidates:
                self._act_on_bounties(candidates)

            # 4. Track: check status of submitted PRs
            self._track_submissions()

            # 5. Report
            self._report()

            print(f"└─ Sleeping {SCOUT_INTERVAL_SECONDS}s...")
            for _ in range(SCOUT_INTERVAL_SECONDS):
                if not self.running:
                    break
                time.sleep(1)

    def _scout(self):
        """Find new bounties."""
        from scout import run as scout_run
        try:
            summary = scout_run(self.token)
            self.state["last_scout"] = datetime.now().isoformat()
            self.state["total_discovered"] = summary["total"]
            save_state(self.state)
        except Exception as e:
            print(f"  ⚠️ Scout error: {e}")

    def _triage(self) -> list[dict]:
        """Evaluate bounties and return top candidates."""
        from scout import load_bounties
        bounties = load_bounties()

        if not bounties:
            return []

        # Filter criteria
        candidates = []
        for b in bounties:
            # Skip already claimed
            if b.get("claimed"):
                continue
            # Skip too cheap
            payment = b.get("payment", {})
            amount = payment.get("amount") or 0
            if amount < MIN_BOUNTY_VALUE:
                continue
            # Skip too competitive
            if b.get("comments", 0) > MAX_COMPETITION:
                continue

            # Score: value / competition / recency
            age_hours = 0
            try:
                created = datetime.fromisoformat(b["created_at"].rstrip("Z"))
                age_hours = (datetime.now() - created).total_seconds() / 3600
            except:
                pass

            score = (amount * 10) / (b.get("comments", 1) + 1) / max(age_hours / 24, 1)
            candidates.append((score, b))

        # Sort by score, take top N
        candidates.sort(key=lambda x: x[0], reverse=True)
        top = [b for _, b in candidates[:MAX_CONCURRENT_BOUNTIES]]

        if top:
            print(f"  🎯 Triage: {len(candidates)} candidates → {len(top)} selected")
            for b in top:
                print(f"     ${b['payment']['amount'] or '?'} {b['title'][:50]}...")

        return top

    def _act_on_bounties(self, candidates: list[dict]):
        """Claim and work on selected bounties."""
        for bounty in candidates:
            # Rate limit claims
            last_claim = self.state.get("last_claim")
            if last_claim:
                elapsed = (datetime.now() - datetime.fromisoformat(last_claim)).total_seconds()
                if elapsed < CLAIM_COOLDOWN_MINUTES * 60:
                    continue

            success = self._claim_bounty(bounty)
            if success:
                self.state["last_claim"] = datetime.now().isoformat()
                save_state(self.state)

    def _claim_bounty(self, bounty: dict) -> bool:
        """Post a claim comment on a bounty issue."""
        issue_url = bounty["url"]
        api_url = issue_url.replace("github.com", "api.github.com/repos")
        api_url = api_url.replace("/issues/", "/issues/") + "/comments"

        dept_name = bounty.get("department", "general")
        msg = f"I'll take this one. Lighthouse Analytics Bounty Division — {dept_name} department. Will submit a PR shortly."

        try:
            data = json.dumps({"body": msg}).encode()
            req = urllib.request.Request(api_url, data=data, method="POST")
            req.add_header("Authorization", f"token {self.token}")
            req.add_header("Accept", "application/vnd.github+json")
            req.add_header("Content-Type", "application/json")

            with urllib.request.urlopen(req, timeout=10) as r:
                result = json.loads(r.read())

            bounty["claimed"] = True
            bounty["claimed_at"] = datetime.now().isoformat()
            self.state["total_claimed"] += 1
            self.state["active_bounties"].append(bounty["id"])
            save_state(self.state)

            print(f"  ✅ Claimed: {bounty['title'][:50]}...")
            return True
        except Exception as e:
            print(f"  ❌ Claim failed: {e}")
            return False

    def _track_submissions(self):
        """Check status of submitted PRs."""
        pass  # Will track PR merge status

    def _report(self):
        """Print status report."""
        print(f"  📊 Discovered:{self.state['total_discovered']} "
              f"Claimed:{self.state['total_claimed']} "
              f"Submitted:{self.state['total_submitted']} "
              f"Earned:${self.state['total_earned_usd']}")


if __name__ == "__main__":
    import os

    token = os.getenv("GITHUB_TOKEN") or sys.argv[1] if len(sys.argv) > 1 else ""
    if not token:
        print("Usage: GITHUB_TOKEN=ghp_xxx python orchestrator.py")
        sys.exit(1)

    orch = BountyOrchestrator(token)
    orch.run()
