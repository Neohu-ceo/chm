"""Identifies file change hotspots — files that change too often."""

from collections import defaultdict
from chm.git_collector import GitCollector


class HotspotAnalyzer:
    """Analyzes which files change most frequently."""

    def __init__(self, collector: GitCollector):
        self.collector = collector

    def analyze(self) -> dict:
        """Return hotspot analysis results."""
        changes = self.collector.get_file_changes()

        file_stats = defaultdict(lambda: {
            "changes": 0,
            "additions": 0,
            "deletions": 0,
            "total_churn": 0,
            "authors": set(),
        })

        for change in changes:
            f = file_stats[change["file"]]
            f["changes"] += 1
            f["additions"] += change["additions"]
            f["deletions"] += change["deletions"]
            f["total_churn"] += change["churn"]
            f["authors"].add(change["author"])

        # Convert to sorted list
        ranked = []
        for filepath, stats in file_stats.items():
            ranked.append({
                "file": filepath,
                "changes": stats["changes"],
                "additions": stats["additions"],
                "deletions": stats["deletions"],
                "total_churn": stats["total_churn"],
                "unique_authors": len(stats["authors"]),
                "authors": sorted(stats["authors"]),
            })

        ranked.sort(key=lambda x: x["total_churn"], reverse=True)

        return {
            "top_hotspots": ranked[:20],
            "total_files_changed": len(ranked),
            "total_churn": sum(r["total_churn"] for r in ranked),
            "average_changes_per_file": (
                sum(r["changes"] for r in ranked) / len(ranked) if ranked else 0
            ),
        }
