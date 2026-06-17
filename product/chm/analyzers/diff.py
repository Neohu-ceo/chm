"""Diff analyzer — compare current health against previous snapshot.

Used in CI/CD to fail the build when health degrades.
"""

import json
from pathlib import Path
from chm.analyzers.trends import TrendTracker


class DiffAnalyzer:
    """Compares current health against last snapshot. Returns deltas."""

    def __init__(self, repo_path: str):
        self.tracker = TrendTracker(repo_path)

    def diff(self) -> dict:
        """Compare current vs last snapshot. Returns changes and CI status."""
        history = self.tracker._load_history()
        if len(history) < 1:
            return {"error": "No snapshots yet. Run 'chm snapshot .' first."}

        # Take current snapshot
        current = self.tracker.snapshot()
        previous = history[-1] if len(history) == 1 else history[-2]

        deltas = {
            "commits": current["total_commits"] - previous["total_commits"],
            "files": current["total_files"] - previous["total_files"],
            "total_churn": (current["hotspots"].get("total_churn", 0) -
                           previous["hotspots"].get("total_churn", 0)),
            "bus_factor": (current["authors"].get("bus_factor", 1) -
                          previous["authors"].get("bus_factor", 1)),
            "avg_complexity": round(
                (current["complexity"].get("avg_complexity", 0) or 0) -
                (previous["complexity"].get("avg_complexity", 0) or 0), 1),
            "risky_files": (len(current["complexity"].get("risky_files", [])) -
                           len(previous["complexity"].get("risky_files", []))),
            "test_coverage": round(
                (current.get("test_coverage", {}).get("estimated_coverage_pct", 0) or 0) -
                (previous.get("test_coverage", {}).get("estimated_coverage_pct", 0) or 0), 1),
            "new_hotspots": self._new_items(
                previous["hotspots"].get("top_hotspots", []),
                current["hotspots"].get("top_hotspots", []),
                "file"
            ),
        }

        # Determine CI status
        degraded = False
        warnings = []

        if deltas["bus_factor"] < 0:
            degraded = True
            warnings.append(f"⚠️ Bus factor decreased by {abs(deltas['bus_factor'])}")

        new_hotspots = deltas["new_hotspots"]
        if new_hotspots:
            warnings.append(f"🔥 {len(new_hotspots)} new hotspots: {', '.join(h['file'].split('/')[-1] for h in new_hotspots[:3])}")

        if deltas["risky_files"] > 0:
            degraded = True
            warnings.append(f"🧩 +{deltas['risky_files']} risky files")

        if deltas["test_coverage"] < -5:
            degraded = True
            warnings.append(f"📉 Test coverage dropped by {abs(deltas['test_coverage'])}%")

        deltas["ci_status"] = "fail" if degraded else "pass"
        deltas["ci_warnings"] = warnings
        deltas["health_score_current"] = self._score(current)
        deltas["health_score_previous"] = self._score(previous)

        return deltas

    def _new_items(self, old_list, new_list, key):
        old_keys = {item[key] for item in old_list}
        return [item for item in new_list if item[key] not in old_keys]

    def _score(self, snap):
        from chm.reporters import TerminalReporter
        tr = TerminalReporter()
        return tr._calculate_health_score({
            "hotspots": snap.get("hotspots", {}),
            "authors": snap.get("authors", {}),
            "pulse": snap.get("pulse", {}),
            "complexity": snap.get("complexity", {}),
            "dead_code": snap.get("dead_code", {}),
            "dependencies": snap.get("dependencies", {}),
            "test_coverage": snap.get("test_coverage", {}),
            "duplication": snap.get("duplication", {}),
        })
