#!/usr/bin/env python3
"""Bounty Scout — continuously discovers paying GitHub issues.

Part of Lighthouse Analytics Bounty Division.
Runs every 15 minutes via cron.
"""

import json, re, time, urllib.request
from datetime import datetime
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"
DATA_DIR.mkdir(exist_ok=True)
SCOUT_LOG = DATA_DIR / "scout_log.jsonl"
BOUNTY_DB = DATA_DIR / "bounties.json"

TOKEN = None  # Set from env or config

# ── Search Patterns ────────────────────────────────────────────

SEARCHES = [
    # Core searches — full text "bounty" + filters
    ("python-bounty", 'bounty+state:open+is:issue+language:python', "python"),
    ("javascript-bounty", 'bounty+state:open+is:issue+language:javascript', "frontend"),
    ("typescript-bounty", 'bounty+state:open+is:issue+language:typescript', "frontend"),
    ("docs-bounty", 'bounty+state:open+is:issue+label:documentation', "docs"),
    ("good-first-bounty", '"good+first+issue"+bounty+state:open', "general"),
    ("security-bounty", 'bounty+state:open+is:issue+label:security', "security"),
    ("go-bounty", 'bounty+state:open+is:issue+language:go', "python"),
    ("rust-bounty", 'bounty+state:open+is:issue+language:rust', "python"),
]

DEPARTMENTS = {
    "skills": {"name": "🔌 Skills Dept", "color": "#2563eb"},
    "python": {"name": "🐍 Python Dept", "color": "#10b981"},
    "docs": {"name": "📝 Docs Dept", "color": "#f59e0b"},
    "general": {"name": "🔧 General Dept", "color": "#8b5cf6"},
    "security": {"name": "🛡️ Security Dept", "color": "#ef4444"},
    "frontend": {"name": "🎨 Frontend Dept", "color": "#ec4899"},
}


def search_bounties(token: str) -> list[dict]:
    """Search all configured patterns and return deduplicated bounties."""
    all_found = {}

    for name, query, dept in SEARCHES:
        url = f"https://api.github.com/search/issues?q={urllib.request.quote(query)}&sort=created&order=desc&per_page=10"
        req = urllib.request.Request(url)
        req.add_header("Authorization", f"token {token}")
        req.add_header("Accept", "application/vnd.github+json")

        try:
            with urllib.request.urlopen(req, timeout=15) as r:
                data = json.loads(r.read())
        except Exception as e:
            print(f"  ⚠️ {name}: {e}")
            continue

        for item in data.get("items", []):
            issue_id = str(item["id"])
            if issue_id in all_found:
                continue

            body = (item.get("body", "") or "")[:1000]
            title = item["title"]
            labels = [l["name"] for l in item.get("labels", [])]

            # Extract payment info
            payment = extract_payment(title, body, labels)

            all_found[issue_id] = {
                "id": issue_id,
                "title": title,
                "url": item["html_url"],
                "repo": item["repository_url"].split("/")[-2:],
                "labels": labels,
                "department": dept,
                "payment": payment,
                "created_at": item["created_at"],
                "updated_at": item["updated_at"],
                "comments": item.get("comments", 0),
                "state": item["state"],
                "discovered_at": datetime.now().isoformat(),
                "claimed": False,
                "submitted": False,
                "pr_url": None,
                "paid": False,
                "paid_amount": None,
            }

    return list(all_found.values())


def extract_payment(title: str, body: str, labels: list[str]) -> dict:
    """Extract payment information from issue text."""
    payment = {"type": "unknown", "amount": None, "currency": None}

    text = title + " " + body

    # USD amounts
    usd = re.findall(r'\$\s*(\d[\d,]*)', text)
    if usd:
        payment["type"] = "fiat"
        payment["amount"] = int(usd[0].replace(",", ""))
        payment["currency"] = "USD"
        return payment

    # USDC/USDT
    usdc = re.findall(r'(\d+)\s*USDC', text)
    if usdc:
        payment["type"] = "crypto"
        payment["amount"] = int(usdc[0])
        payment["currency"] = "USDC"
        return payment

    usdt = re.findall(r'(\d+)\s*USDT', text)
    if usdt:
        payment["type"] = "crypto"
        payment["amount"] = int(usdt[0])
        payment["currency"] = "USDT"
        return payment

    # ETH
    eth = re.findall(r'(\d+\.?\d*)\s*ETH', text)
    if eth:
        payment["type"] = "crypto"
        payment["amount"] = float(eth[0])
        payment["currency"] = "ETH"
        return payment

    # Label-based: check for price tags
    for label in labels:
        dollar_label = re.match(r'.*\$(\d+)', label)
        if dollar_label:
            payment["type"] = "fiat"
            payment["amount"] = int(dollar_label.group(1))
            payment["currency"] = "USD"
            return payment

    return payment


def save_bounties(bounties: list[dict]):
    """Save bounty database."""
    with open(BOUNTY_DB, "w") as f:
        json.dump(bounties, f, indent=2, default=str)


def load_bounties() -> list[dict]:
    """Load existing bounty database."""
    if BOUNTY_DB.exists():
        try:
            return json.loads(BOUNTY_DB.read_text())
        except (json.JSONDecodeError, OSError):
            pass
    return []


def log_discovery(bounties: list[dict], new_count: int):
    """Log scouting run."""
    with open(SCOUT_LOG, "a") as f:
        entry = {
            "timestamp": datetime.now().isoformat(),
            "total_found": len(bounties),
            "new": new_count,
            "with_payment": len([b for b in bounties if b["payment"]["amount"]]),
        }
        f.write(json.dumps(entry) + "\n")


def run(token: str) -> dict:
    """Run one scouting cycle. Returns summary."""
    print(f"🔍 Bounty Scout — {datetime.now().strftime('%H:%M:%S')}")

    old_bounties = load_bounties()
    old_ids = {b["id"] for b in old_bounties}

    new_bounties = search_bounties(token)
    new_ids = {b["id"] for b in new_bounties}
    fresh = len(new_ids - old_ids)

    # Merge: keep old bounties, add new ones
    merged = {b["id"]: b for b in old_bounties}
    for b in new_bounties:
        if b["id"] not in merged:
            merged[b["id"]] = b

    bounties = list(merged.values())
    save_bounties(bounties)
    log_discovery(bounties, fresh)

    # Stats
    with_payment = [b for b in bounties if b["payment"]["amount"]]
    by_dept = {}
    for b in bounties:
        dept = b["department"]
        by_dept[dept] = by_dept.get(dept, 0) + 1

    summary = {
        "total": len(bounties),
        "new": fresh,
        "with_payment": len(with_payment),
        "total_value": sum(b["payment"]["amount"] or 0 for b in with_payment),
        "by_department": by_dept,
    }

    print(f"  📊 {fresh} new | {len(bounties)} total | {len(with_payment)} with payment")
    if with_payment:
        valuable = sorted(with_payment, key=lambda b: b["payment"]["amount"] or 0, reverse=True)[:3]
        for b in valuable:
            print(f"  💰 ${b['payment']['amount']} — {b['title'][:60]}")

    return summary


if __name__ == "__main__":
    import os, sys
    token = os.getenv("GITHUB_TOKEN", sys.argv[1] if len(sys.argv) > 1 else "")
    if not token:
        print("Usage: GITHUB_TOKEN=ghp_xxx python scout.py")
        sys.exit(1)
    run(token)
