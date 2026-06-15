"""Author contribution and collaboration analysis."""

from collections import defaultdict
from chm.git_collector import GitCollector


class AuthorAnalyzer:
    """Analyzes contributor patterns."""

    def __init__(self, collector: GitCollector):
        self.collector = collector

    def analyze(self) -> dict:
        """Return author analysis results."""
        commits = self.collector.get_commits()
        contributors = self.collector.get_contributor_stats()

        # Per-author file changes
        changes = self.collector.get_file_changes()
        author_files = defaultdict(set)
        author_churn = defaultdict(int)

        for change in changes:
            author_files[change["author"]].add(change["file"])
            author_churn[change["author"]] += change["churn"]

        # Build author summaries
        summaries = []
        for c in contributors:
            name = c["name"]
            summaries.append({
                "name": name,
                "email": c["email"],
                "commits": c["commits"],
                "files_touched": len(author_files.get(name, set())),
                "total_churn": author_churn.get(name, 0),
                "avg_churn_per_commit": (
                    author_churn.get(name, 0) / c["commits"]
                    if c["commits"] > 0 else 0
                ),
                "top_files": sorted(
                    author_files.get(name, set()),
                    key=lambda f: sum(
                        1 for ch in changes
                        if ch["author"] == name and ch["file"] == f
                    ),
                    reverse=True,
                )[:5],
            })

        summaries.sort(key=lambda x: x["commits"], reverse=True)

        # Bus factor estimation
        total_commits = sum(s["commits"] for s in summaries)
        bus_factor = self._estimate_bus_factor(summaries, total_commits)

        return {
            "contributors": summaries,
            "total_contributors": len(summaries),
            "total_commits": total_commits,
            "bus_factor": bus_factor,
            "top_contributor": summaries[0] if summaries else None,
        }

    def _estimate_bus_factor(self, summaries: list, total: int) -> int:
        """Estimate bus factor — min contributors covering 50% of commits."""
        cumulative = 0
        for i, s in enumerate(summaries):
            cumulative += s["commits"]
            if cumulative >= total * 0.5:
                return i + 1
        return len(summaries)
