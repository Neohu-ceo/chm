"""chm notify — Send health reports to Slack, Discord, or custom webhooks.

Usage:
    chm notify . --slack WEBHOOK_URL
    chm notify . --discord WEBHOOK_URL
    chm notify . --webhook URL

Configure defaults:
    chm config --set slack_webhook https://hooks.slack.com/...
"""

import json
import urllib.request

from chm.git_collector import GitCollector
from chm.analyzers import (
    HotspotAnalyzer, AuthorAnalyzer, PulseAnalyzer, ComplexityAnalyzer,
    DeadCodeAnalyzer, TestCoverageAnalyzer,
)
from chm.reporters import TerminalReporter


def send_slack(repo_path: str, webhook_url: str) -> bool:
    """Send a health summary to Slack."""
    collector = GitCollector(repo_path)
    report = _build_summary(collector)
    return _post_webhook(webhook_url, _format_slack(report))


def send_discord(repo_path: str, webhook_url: str) -> bool:
    """Send a health summary to Discord."""
    collector = GitCollector(repo_path)
    report = _build_summary(collector)
    return _post_webhook(webhook_url, _format_discord(report))


def send_webhook(repo_path: str, webhook_url: str) -> bool:
    """Send a health summary to a generic webhook."""
    collector = GitCollector(repo_path)
    report = _build_summary(collector)
    return _post_webhook(webhook_url, {"text": json.dumps(report, indent=2, default=str)})


def _build_summary(collector: GitCollector) -> dict:
    """Build a summary report for notification."""
    hotspots = HotspotAnalyzer(collector).analyze()
    authors = AuthorAnalyzer(collector).analyze()
    pulse = PulseAnalyzer(collector).analyze()
    complexity = ComplexityAnalyzer(collector).analyze()
    dead_code = DeadCodeAnalyzer(collector).analyze()
    coverage = TestCoverageAnalyzer(collector).analyze()

    tr = TerminalReporter()
    score = tr._calculate_health_score({
        "hotspots": hotspots, "authors": authors, "pulse": pulse,
        "complexity": complexity, "dead_code": dead_code,
        "test_coverage": coverage, "dependencies": {}, "duplication": {},
    })

    return {
        "repo": collector.repo_name(),
        "health_score": score,
        "bus_factor": authors.get("bus_factor"),
        "total_contributors": authors.get("total_contributors"),
        "top_hotspots": [h["file"] for h in hotspots.get("top_hotspots", [])[:5]],
        "total_churn": hotspots.get("total_churn"),
        "test_coverage": f"{coverage.get('coverage_grade', '?')} ({coverage.get('estimated_coverage_pct', 0)}%)",
    }


def _format_slack(report: dict) -> dict:
    """Format a report for Slack incoming webhook."""
    score = report["health_score"]
    color = "#36a64f" if score >= 70 else "#f2c744" if score >= 40 else "#d00000"
    emoji = "🟢" if score >= 70 else "🟡" if score >= 40 else "🔴"

    hotspots_text = "\n".join(
        f"• {h}" for h in report.get("top_hotspots", [])[:5]
    ) or "None"

    return {
        "attachments": [{
            "color": color,
            "title": f"{emoji} Code Health: {report['repo']} — {score}/100",
            "fields": [
                {"title": "Bus Factor", "value": str(report["bus_factor"]), "short": True},
                {"title": "Contributors", "value": str(report["total_contributors"]), "short": True},
                {"title": "Test Coverage", "value": report["test_coverage"], "short": True},
                {"title": "Total Churn", "value": f"{report['total_churn']:,}", "short": True},
                {"title": "🔥 Top Hotspots", "value": hotspots_text, "short": False},
            ],
            "footer": "Lighthouse Analytics — chm-cli",
        }]
    }


def _format_discord(report: dict) -> dict:
    """Format a report for Discord webhook."""
    score = report["health_score"]
    color = 0x36a64f if score >= 70 else 0xf2c744 if score >= 40 else 0xd00000

    hotspots_text = "\n".join(
        f"🔥 {h}" for h in report.get("top_hotspots", [])[:5]
    )

    return {
        "embeds": [{
            "title": f"🏠 Code Health: {report['repo']} — {score}/100",
            "color": color,
            "fields": [
                {"name": "👥 Bus Factor", "value": str(report["bus_factor"]), "inline": True},
                {"name": "🧪 Coverage", "value": report["test_coverage"], "inline": True},
                {"name": "📊 Churn", "value": f"{report['total_churn']:,}", "inline": True},
            ],
            "description": f"**Top Hotspots:**\n{hotspots_text}" if hotspots_text else "",
            "footer": {"text": "Lighthouse Analytics"},
            "timestamp": __import__('datetime').datetime.now().isoformat(),
        }]
    }


def _post_webhook(url: str, payload: dict) -> bool:
    """Post JSON to a webhook URL. Returns True if successful."""
    try:
        data = json.dumps(payload).encode()
        req = urllib.request.Request(
            url, data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status in (200, 204)
    except Exception:
        return False
