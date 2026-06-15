"""Tests for CHM analyzers using the demo repository."""

import pytest
import sys
from pathlib import Path

# Add product dir to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from chm.git_collector import GitCollector
from chm.analyzers import (
    HotspotAnalyzer, AuthorAnalyzer, PulseAnalyzer, ComplexityAnalyzer,
)
from chm.analyzers.trends import TrendTracker

DEMO_REPO = Path("/tmp/chm-demo")
COLLECTOR = GitCollector(str(DEMO_REPO))


class TestGitCollector:
    def test_repo_name(self):
        assert COLLECTOR.repo_name() == "chm-demo"

    def test_total_commits(self):
        assert COLLECTOR.total_commits() >= 12

    def test_total_files(self):
        assert COLLECTOR.total_files() >= 10

    def test_get_commits(self):
        commits = COLLECTOR.get_commits()
        assert len(commits) >= 12
        assert "hash" in commits[0]
        assert "author" in commits[0]
        assert "message" in commits[0]

    def test_get_file_changes(self):
        changes = COLLECTOR.get_file_changes()
        assert len(changes) > 0
        assert "file" in changes[0]
        assert "churn" in changes[0]

    def test_get_contributor_stats(self):
        stats = COLLECTOR.get_contributor_stats()
        names = [s["name"] for s in stats]
        assert "Alice" in names
        assert "Bob" in names

    def test_error_on_non_repo(self):
        with pytest.raises(ValueError):
            GitCollector("/tmp")


class TestHotspotAnalyzer:
    def test_analyze_returns_data(self):
        data = HotspotAnalyzer(COLLECTOR).analyze()
        assert "top_hotspots" in data
        assert "total_churn" in data
        assert data["total_churn"] > 0

    def test_top_hotspot_is_file(self):
        data = HotspotAnalyzer(COLLECTOR).analyze()
        top = data["top_hotspots"]
        assert len(top) > 0
        assert "src/api/server.py" in [h["file"] for h in top]


class TestAuthorAnalyzer:
    def test_analyze_returns_data(self):
        data = AuthorAnalyzer(COLLECTOR).analyze()
        assert "contributors" in data
        assert "bus_factor" in data
        assert data["total_contributors"] >= 2

    def test_bus_factor_reasonable(self):
        data = AuthorAnalyzer(COLLECTOR).analyze()
        assert 1 <= data["bus_factor"] <= data["total_contributors"]


class TestPulseAnalyzer:
    def test_analyze_returns_data(self):
        data = PulseAnalyzer(COLLECTOR).analyze()
        assert "streaks" in data
        assert "avg_commits_per_day" in data
        assert data["streaks"]["longest_streak_days"] >= 1


class TestComplexityAnalyzer:
    def test_analyze_returns_data(self):
        data = ComplexityAnalyzer(COLLECTOR).analyze()
        assert "files_analyzed" in data
        assert "avg_complexity" in data
        assert data["files_analyzed"] > 0

    def test_skips_non_code(self):
        data = ComplexityAnalyzer(COLLECTOR).analyze()
        files = [f["file"] for f in data["top_complex"]]
        assert not any(f.endswith(".md") for f in files)
        assert not any(f.endswith(".gitignore") for f in files)


class TestTrendTracker:
    def test_snapshot_creates_history(self):
        tracker = TrendTracker(str(DEMO_REPO))
        snap = tracker.snapshot(COLLECTOR)
        assert "timestamp" in snap
        assert "hotspots" in snap

    def test_trends_with_history(self):
        tracker = TrendTracker(str(DEMO_REPO))
        data = tracker.get_trends()
        assert "snapshots" in data
        # We have at least 2 from previous test run
        assert data["snapshots"] >= 2

    def test_compare(self):
        tracker = TrendTracker(str(DEMO_REPO))
        data = tracker.compare(-2, -1)
        assert "new_hotspots" in data or "error" in data


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
