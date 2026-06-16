"""CSV export — export analysis results for spreadsheet analysis."""

import csv
import io
from pathlib import Path

from chm.git_collector import GitCollector
from chm.analyzers import (
    HotspotAnalyzer, AuthorAnalyzer, PulseAnalyzer, ComplexityAnalyzer,
    DeadCodeAnalyzer, TestCoverageAnalyzer, DuplicationAnalyzer, DependencyAnalyzer,
)


def export_csv(repo_path: str) -> str:
    """Export full analysis as CSV. Returns CSV string."""
    collector = GitCollector(repo_path)

    hotspots = HotspotAnalyzer(collector).analyze()
    authors = AuthorAnalyzer(collector).analyze()
    pulse = PulseAnalyzer(collector).analyze()
    complexity = ComplexityAnalyzer(collector).analyze()
    dead_code = DeadCodeAnalyzer(collector).analyze()
    coverage = TestCoverageAnalyzer(collector).analyze()
    dupes = DuplicationAnalyzer(collector).analyze()
    deps = DependencyAnalyzer(collector).analyze()

    output = io.StringIO()
    w = csv.writer(output)

    # Overview
    w.writerow(["# CHM Analysis —", collector.repo_name()])
    w.writerow(["total_commits", collector.total_commits()])
    w.writerow(["total_files", collector.total_files()])
    w.writerow([])

    # Hotspots
    w.writerow(["# Hotspots"])
    w.writerow(["file", "changes", "additions", "deletions", "total_churn", "unique_authors"])
    for h in hotspots["top_hotspots"]:
        w.writerow([h["file"], h["changes"], h["additions"], h["deletions"], h["total_churn"], h["unique_authors"]])
    w.writerow([])

    # Contributors
    w.writerow(["# Contributors"])
    w.writerow(["name", "email", "commits", "files_touched", "total_churn"])
    for c in authors["contributors"]:
        w.writerow([c["name"], c.get("email", ""), c["commits"], c.get("files_touched", 0), c.get("total_churn", 0)])
    w.writerow(["bus_factor", authors.get("bus_factor", "")])
    w.writerow([])

    # Complexity
    w.writerow(["# Complexity"])
    w.writerow(["file", "lines", "code_lines", "comment_lines", "comment_ratio", "complexity_score"])
    for f in complexity.get("top_complex", []):
        w.writerow([f["file"], f["lines"], f["code_lines"], f.get("comment_lines", 0), f["comment_ratio"], f["complexity_score"]])
    w.writerow([])

    # Dead Code
    w.writerow(["# Dead Code"])
    w.writerow(["file", "last_modified", "months_stale"])
    for f in dead_code.get("very_stale_files", []):
        w.writerow([f["file"], f["last_modified"], f["months_stale"]])
    for f in dead_code.get("stale_files", []):
        w.writerow([f["file"], f["last_modified"], f["months_stale"]])
    w.writerow([])

    # Test Coverage
    w.writerow(["# Test Coverage"])
    w.writerow(["estimated_coverage_pct", coverage.get("estimated_coverage_pct", 0)])
    w.writerow(["covered_files", coverage.get("covered_files", 0)])
    w.writerow(["uncovered_files", coverage.get("uncovered_files", 0)])
    w.writerow([])

    # Duplication
    w.writerow(["# Duplication"])
    w.writerow(["file_a", "file_b", "shared_lines"])
    for d in dupes.get("top_duplicate_pairs", []):
        w.writerow([d["file_a"], d["file_b"], d["shared_lines"]])
    w.writerow([])

    # Dependencies
    w.writerow(["# Dependencies"])
    w.writerow(["module", "imported_by_count"])
    for m in deps.get("top_coupled_modules", []):
        w.writerow([m["module"], m["imported_by_count"]])

    return output.getvalue()
