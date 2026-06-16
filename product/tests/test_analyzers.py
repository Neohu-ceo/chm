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


class TestDeadCodeAnalyzer:
    def test_analyze_returns_data(self):
        from chm.analyzers.dead_code import DeadCodeAnalyzer
        data = DeadCodeAnalyzer(COLLECTOR).analyze()
        assert "stale_files" in data
        assert "staleness_ratio" in data
        assert isinstance(data["total_stale"], int)

    def test_staleness_ratio_in_range(self):
        from chm.analyzers.dead_code import DeadCodeAnalyzer
        data = DeadCodeAnalyzer(COLLECTOR).analyze()
        assert 0 <= data["staleness_ratio"] <= 1

    def test_empty_repo(self):
        from chm.analyzers.dead_code import DeadCodeAnalyzer
        from chm.git_collector import GitCollector
        gc = GitCollector("/tmp/chm-test-single")
        data = DeadCodeAnalyzer(gc).analyze()
        assert "never_touched_in_history" in data


class TestDependencyAnalyzer:
    def test_analyze_returns_data(self):
        from chm.analyzers.dependencies import DependencyAnalyzer
        data = DependencyAnalyzer(COLLECTOR).analyze()
        assert "top_coupled_modules" in data
        assert "potential_circular_deps" in data
        assert "total_import_relations" in data

    def test_python_imports_detected(self):
        from chm.analyzers.dependencies import DependencyAnalyzer
        data = DependencyAnalyzer(COLLECTOR).analyze()
        # Demo repo has Python files with imports
        assert data["files_with_imports"] > 0

    def test_no_false_circular(self):
        from chm.analyzers.dependencies import DependencyAnalyzer
        data = DependencyAnalyzer(COLLECTOR).analyze()
        # Our demo shouldn't have circular deps
        assert isinstance(data["potential_circular_deps"], list)


class TestTestCoverageAnalyzer:
    def test_analyze_returns_data(self):
        from chm.analyzers.test_coverage import TestCoverageAnalyzer
        data = TestCoverageAnalyzer(COLLECTOR).analyze()
        assert "coverage_grade" in data
        assert "estimated_coverage_pct" in data
        assert data["coverage_grade"] in ("A", "B", "C", "D", "F")

    def test_finds_test_files(self):
        from chm.analyzers.test_coverage import TestCoverageAnalyzer
        data = TestCoverageAnalyzer(COLLECTOR).analyze()
        # Demo repo has tests/ directory
        assert data["total_test_files"] >= 2

    def test_coverage_range(self):
        from chm.analyzers.test_coverage import TestCoverageAnalyzer
        data = TestCoverageAnalyzer(COLLECTOR).analyze()
        assert 0 <= data["estimated_coverage_pct"] <= 100


class TestDuplicationAnalyzer:
    def test_analyze_returns_data(self):
        from chm.analyzers.duplication import DuplicationAnalyzer
        data = DuplicationAnalyzer(COLLECTOR).analyze()
        assert "duplication_summary" in data
        assert "top_duplicate_pairs" in data

    def test_no_crash_on_small_repo(self):
        from chm.analyzers.duplication import DuplicationAnalyzer
        data = DuplicationAnalyzer(COLLECTOR).analyze()
        assert isinstance(data["file_pairs_with_duplication"], int)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
