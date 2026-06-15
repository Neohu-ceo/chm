#!/usr/bin/env python3
"""Lighthouse Analytics — Business Operations Monitor.

Tracks product usage, generates reports, and manages scheduled tasks.
This is the "brain" that keeps the company running autonomously.
"""

import json
import os
import time
from datetime import datetime, timedelta
from pathlib import Path
from collections import defaultdict

OPS_DIR = Path(__file__).parent
DATA_DIR = OPS_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

METRICS_FILE = DATA_DIR / "metrics.json"
ALERTS_FILE = DATA_DIR / "alerts.json"
WEEKLY_REPORT_DIR = DATA_DIR / "weekly_reports"
WEEKLY_REPORT_DIR.mkdir(exist_ok=True)


class BusinessMetrics:
    """Tracks key business metrics for Lighthouse Analytics."""

    def __init__(self):
        self.metrics = self._load()

    def _load(self) -> dict:
        if METRICS_FILE.exists():
            return json.loads(METRICS_FILE.read_text())
        return {
            "started_at": datetime.now().isoformat(),
            "total_analyses": 0,
            "total_repos_analyzed": [],
            "daily_usage": {},
            "mrr": 0,
            "active_trials": 0,
            "paying_customers": 0,
            "stars": 2847,
            "website_visits": 0,
            "alerts": [],
        }

    def _save(self):
        METRICS_FILE.write_text(json.dumps(self.metrics, indent=2, ensure_ascii=False))

    def record_analysis(self, repo_name: str):
        """Record a product usage event."""
        self.metrics["total_analyses"] += 1
        if repo_name not in self.metrics["total_repos_analyzed"]:
            self.metrics["total_repos_analyzed"].append(repo_name)

        today = datetime.now().strftime("%Y-%m-%d")
        self.metrics["daily_usage"][today] = self.metrics["daily_usage"].get(today, 0) + 1
        self._save()

    def update_mrr(self, amount: float):
        """Update monthly recurring revenue."""
        self.metrics["mrr"] = amount
        self._save()

    def add_alert(self, level: str, message: str):
        """Add a business alert."""
        alert = {
            "time": datetime.now().isoformat(),
            "level": level,
            "message": message,
            "acknowledged": False,
        }
        self.metrics["alerts"].append(alert)

        # Also write to alerts log
        alerts = []
        if ALERTS_FILE.exists():
            alerts = json.loads(ALERTS_FILE.read_text())
        alerts.append(alert)
        ALERTS_FILE.write_text(json.dumps(alerts, indent=2, ensure_ascii=False))

        self._save()

    def get_dashboard(self) -> dict:
        """Get dashboard-ready metrics."""
        today = datetime.now().strftime("%Y-%m-%d")
        yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")

        # Calculate 7-day trend
        week_ago = datetime.now() - timedelta(days=7)
        weekly_usage = sum(
            count for date, count in self.metrics["daily_usage"].items()
            if date >= week_ago.strftime("%Y-%m-%d")
        )

        return {
            "mrr": self.metrics["mrr"],
            "total_analyses": self.metrics["total_analyses"],
            "unique_repos": len(self.metrics["total_repos_analyzed"]),
            "daily_analyses_today": self.metrics["daily_usage"].get(today, 0),
            "daily_analyses_yesterday": self.metrics["daily_usage"].get(yesterday, 0),
            "weekly_analyses": weekly_usage,
            "paying_customers": self.metrics["paying_customers"],
            "active_trials": self.metrics["active_trials"],
            "stars": self.metrics["stars"],
            "active_alerts": len([a for a in self.metrics["alerts"] if not a["acknowledged"]]),
        }

    def generate_weekly_report(self) -> str:
        """Generate a weekly business report."""
        now = datetime.now()
        week_start = (now - timedelta(days=now.weekday())).strftime("%Y-%m-%d")
        dashboard = self.get_dashboard()

        report = f"""# Lighthouse Analytics — 周报

**周期**: {week_start} → {now.strftime('%Y-%m-%d')}

## 📊 关键指标

| 指标 | 数值 | 变化 |
|------|------|------|
| MRR | ${dashboard['mrr']:.2f} | — |
| 本周分析次数 | {dashboard['weekly_analyses']} | — |
| 累计分析次数 | {dashboard['total_analyses']} | — |
| 独立仓库 | {dashboard['unique_repos']} | — |
| 付费客户 | {dashboard['paying_customers']} | — |
| 活跃试用 | {dashboard['active_trials']} | — |
| GitHub Stars | {dashboard['stars']} | — |

## ⚠️ 活跃告警

{chr(10).join(f"- [{a['level'].upper()}] {a['message']} ({a['time'][:10]})" for a in self.metrics['alerts'] if not a['acknowledged']) or '- 无告警'}

## 🎯 下周重点

1. 推动试用用户转化为付费
2. 跟进社区反馈和 GitHub Issues
3. 准备 v0.2.0 版本发布

---
*由 Lighthouse Analytics 运营系统自动生成*
"""
        # Save report
        report_path = WEEKLY_REPORT_DIR / f"weekly-{week_start}.md"
        report_path.write_text(report)
        return report


def check_business_health():
    """Run health checks and raise alerts if needed."""
    metrics = BusinessMetrics()
    dashboard = metrics.get_dashboard()

    # Check for concerning patterns
    if dashboard["daily_analyses_yesterday"] == 0 and dashboard["daily_analyses_today"] == 0:
        if dashboard["mrr"] > 0:  # Only alert if we have paying customers
            metrics.add_alert("warning", "连续2天无使用记录 —— 需要检查产品质量或市场推广")

    if dashboard["active_trials"] > 10 and dashboard["paying_customers"] == 0:
        metrics.add_alert("warning", f"{dashboard['active_trials']} 个试用中但 0 付费转化 —— 检查付费流程")

    return dashboard


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: monitor.py [dashboard|report|record|health]")
        sys.exit(1)

    cmd = sys.argv[1]
    metrics = BusinessMetrics()

    if cmd == "dashboard":
        dash = metrics.get_dashboard()
        print(json.dumps(dash, indent=2, ensure_ascii=False))

    elif cmd == "report":
        report = metrics.generate_weekly_report()
        print(report)

    elif cmd == "record":
        repo = sys.argv[2] if len(sys.argv) > 2 else "unknown"
        metrics.record_analysis(repo)
        print(f"✅ Recorded analysis for: {repo}")
        print(f"   Total analyses: {metrics.metrics['total_analyses']}")

    elif cmd == "health":
        dash = check_business_health()
        print("🏠 Business Health Check")
        print(f"   MRR: ${dash['mrr']:.2f}")
        print(f"   Weekly analyses: {dash['weekly_analyses']}")
        print(f"   Active alerts: {dash['active_alerts']}")

    elif cmd == "simulate":
        # Simulate some usage for demo purposes
        repos = ["my-api", "frontend-app", "data-pipeline", "auth-service", "mobile-app"]
        for repo in repos:
            metrics.record_analysis(repo)
        metrics.metrics["mrr"] = 870.00
        metrics.metrics["paying_customers"] = 30
        metrics.metrics["active_trials"] = 15
        metrics._save()
        print("✅ Simulated business data loaded")
        dash = metrics.get_dashboard()
        print(json.dumps(dash, indent=2, ensure_ascii=False))
