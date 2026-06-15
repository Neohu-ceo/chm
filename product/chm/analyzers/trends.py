"""Historical trend tracking — compare analyses over time."""

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from chm.git_collector import GitCollector
from chm.analyzers import (
    HotspotAnalyzer, AuthorAnalyzer, PulseAnalyzer, ComplexityAnalyzer,
)


class TrendTracker:
    """Tracks codebase health trends by storing and comparing analyses over time."""

    def __init__(self, repo_path: str, storage_dir: str = None):
        self.repo_path = Path(repo_path).resolve()
        if storage_dir:
            self.storage_dir = Path(storage_dir)
        else:
            self.storage_dir = self.repo_path / ".chm"
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.history_file = self.storage_dir / "history.json"

    def snapshot(self, collector: GitCollector = None) -> dict:
        """Take a current snapshot and save it to history."""
        if collector is None:
            collector = GitCollector(str(self.repo_path))

        snapshot = {
            "timestamp": datetime.now().isoformat(),
            "total_commits": collector.total_commits(),
            "total_files": collector.total_files(),
            "hotspots": HotspotAnalyzer(collector).analyze(),
            "authors": AuthorAnalyzer(collector).analyze(),
            "pulse": PulseAnalyzer(collector).analyze(),
            "complexity": ComplexityAnalyzer(collector).analyze(),
        }

        # Load existing history
        history = self._load_history()
        history.append(snapshot)
        self._save_history(history)

        return snapshot

    def get_trends(self) -> dict:
        """Analyze trends across all snapshots."""
        history = self._load_history()
        if len(history) < 2:
            return {"message": "Need at least 2 snapshots for trend analysis", "snapshots_count": len(history)}

        # Extract key metrics over time
        metrics = []
        for i, snap in enumerate(history):
            metrics.append({
                "index": i,
                "date": snap["timestamp"][:10],
                "commits": snap["total_commits"],
                "files": snap["total_files"],
                "total_churn": snap["hotspots"].get("total_churn", 0),
                "bus_factor": snap["authors"].get("bus_factor", 1),
                "avg_complexity": snap["complexity"].get("avg_complexity", 0),
                "risky_files_count": len(snap["complexity"].get("risky_files", [])),
                "contributors": snap["authors"].get("total_contributors", 0),
            })

        # Calculate deltas
        first = metrics[0]
        last = metrics[-1]

        trends = {
            "snapshots": len(history),
            "date_range": f"{first['date']} → {last['date']}",
            "metrics_over_time": metrics,
            "deltas": {
                "commits": last["commits"] - first["commits"],
                "files": last["files"] - first["files"],
                "total_churn": last["total_churn"] - first["total_churn"],
                "bus_factor": last["bus_factor"] - first["bus_factor"],
                "avg_complexity": round(last["avg_complexity"] - first["avg_complexity"], 1),
                "risky_files": last["risky_files_count"] - first["risky_files_count"],
                "contributors": last["contributors"] - first["contributors"],
            },
            "direction": self._assess_direction(metrics),
        }

        return trends

    def compare(self, snapshot_a: int = -2, snapshot_b: int = -1) -> dict:
        """Compare two specific snapshots in detail."""
        history = self._load_history()
        if len(history) < 2:
            return {"error": "Not enough snapshots"}

        a = history[snapshot_a]
        b = history[snapshot_b]

        return {
            "snapshot_a": {"date": a["timestamp"][:10], "index": snapshot_a if snapshot_a >= 0 else len(history) + snapshot_a},
            "snapshot_b": {"date": b["timestamp"][:10], "index": snapshot_b if snapshot_b >= 0 else len(history) + snapshot_b},
            "churn_change": b["hotspots"].get("total_churn", 0) - a["hotspots"].get("total_churn", 0),
            "new_hotspots": self._new_hotspots(a, b),
            "resolved_hotspots": self._resolved_hotspots(a, b),
            "contributor_changes": self._contributor_changes(a, b),
        }

    def _new_hotspots(self, a: dict, b: dict) -> list:
        """Find files that became hotspots since last snapshot."""
        a_files = {h["file"] for h in a["hotspots"].get("top_hotspots", [])}
        b_hotspots = b["hotspots"].get("top_hotspots", [])
        return [h for h in b_hotspots if h["file"] not in a_files][:10]

    def _resolved_hotspots(self, a: dict, b: dict) -> list:
        """Find files that were hotspots but are no longer."""
        a_hotspots = {h["file"]: h["total_churn"] for h in a["hotspots"].get("top_hotspots", [])}
        b_hotspots = {h["file"] for h in b["hotspots"].get("top_hotspots", [])}
        return [{"file": f, "previous_churn": churn} for f, churn in a_hotspots.items() if f not in b_hotspots]

    def _contributor_changes(self, a: dict, b: dict) -> dict:
        """Track contributor changes between snapshots."""
        a_authors = {c["name"]: c["commits"] for c in a["authors"].get("contributors", [])}
        b_authors = {c["name"]: c["commits"] for c in b["authors"].get("contributors", [])}

        new = [n for n in b_authors if n not in a_authors]
        gone = [n for n in a_authors if n not in b_authors]

        # Who increased/decreased most
        deltas = {}
        for name in set(list(a_authors.keys()) + list(b_authors.keys())):
            a_count = a_authors.get(name, 0)
            b_count = b_authors.get(name, 0)
            if a_count != b_count:
                deltas[name] = b_count - a_count

        return {"new_contributors": new, "departed_contributors": gone, "commit_deltas": deltas}

    def _assess_direction(self, metrics: list[dict]) -> dict:
        """Assess overall trend direction."""
        if len(metrics) < 2:
            return {"overall": "insufficient_data"}

        first = metrics[0]
        last = metrics[-1]

        signals = []

        # Commits growing = good
        if last["commits"] > first["commits"] * 1.1:
            signals.append("📈 提交量增长")
        elif last["commits"] < first["commits"] * 0.9:
            signals.append("📉 提交量下降")

        # Bus factor improving = good
        if last["bus_factor"] > first["bus_factor"]:
            signals.append("✅ 巴士因子改善")
        elif last["bus_factor"] < first["bus_factor"]:
            signals.append("⚠️ 巴士因子恶化")

        # Complexity decreasing = good
        if last["avg_complexity"] < first["avg_complexity"]:
            signals.append("✅ 平均复杂度下降")
        elif last["avg_complexity"] > first["avg_complexity"] * 1.1:
            signals.append("⚠️ 平均复杂度上升")

        # Risky files decreasing = good
        if last["risky_files_count"] < first["risky_files_count"]:
            signals.append("✅ 高风险文件减少")
        elif last["risky_files_count"] > first["risky_files_count"]:
            signals.append("⚠️ 高风险文件增加")

        good = len([s for s in signals if "✅" in s or "📈" in s])
        bad = len([s for s in signals if "⚠️" in s or "📉" in s])

        return {
            "signals": signals,
            "overall": "improving" if good > bad else "declining" if bad > good else "stable",
            "good_signals": good,
            "bad_signals": bad,
        }

    def _load_history(self) -> list:
        """Load history from file."""
        if self.history_file.exists():
            try:
                return json.loads(self.history_file.read_text())
            except json.JSONDecodeError:
                return []
        return []

    def _save_history(self, history: list):
        """Save history to file."""
        self.history_file.write_text(json.dumps(history, indent=2, ensure_ascii=False))
