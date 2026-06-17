#!/usr/bin/env python3
"""CHM MCP Server — expose codebase health analysis as MCP tools.

Usage:
    chm mcp              # Start MCP server on stdio (for Claude Desktop/Code)
    chm mcp --http 8080  # Start with HTTP transport

Add to Claude Code:
    claude mcp add chm -- python -m chm.mcp_server

Or with HTTP:
    claude mcp add --transport http chm http://localhost:8080/mcp
"""

import sys
import json
from pathlib import Path

# Ensure parent dir is on path
sys.path.insert(0, str(Path(__file__).parent.parent))

from mcp.server.fastmcp import FastMCP

from chm.git_collector import GitCollector
from chm.analyzers import (
    HotspotAnalyzer, AuthorAnalyzer, PulseAnalyzer, ComplexityAnalyzer,
    DeadCodeAnalyzer, DependencyAnalyzer, TestCoverageAnalyzer, DuplicationAnalyzer,
)
from chm.analyzers.trends import TrendTracker
from chm.reporters import TerminalReporter

mcp = FastMCP("chm", json_response=True)


# ── Helper ─────────────────────────────────────────────────────

def _get_collector(repo_path: str = ".") -> GitCollector:
    """Get a GitCollector for a path, with error handling."""
    p = Path(repo_path).resolve()
    if not (p / ".git").exists():
        raise ValueError(f"Not a git repository: {p}")
    return GitCollector(str(p))


# ── Tools ──────────────────────────────────────────────────────

@mcp.tool()
def analyze_repo(repo_path: str = ".") -> dict:
    """Run a full health analysis on a git repository.

    Returns hotspots, authors, bus factor, team pulse, complexity, and an overall health score (0-100).
    Use this to get a complete picture of a codebase's health.
    """
    collector = _get_collector(repo_path)

    results = {
        "repo_name": collector.repo_name(),
        "repo_path": str(collector.repo_path),
        "total_commits": collector.total_commits(),
        "total_files": collector.total_files(),
        "hotspots": HotspotAnalyzer(collector).analyze(),
        "authors": AuthorAnalyzer(collector).analyze(),
        "pulse": PulseAnalyzer(collector).analyze(),
        "complexity": ComplexityAnalyzer(collector).analyze(),
        "dead_code": DeadCodeAnalyzer(collector).analyze(),
        "dependencies": DependencyAnalyzer(collector).analyze(),
        "test_coverage": TestCoverageAnalyzer(collector).analyze(),
        "duplication": DuplicationAnalyzer(collector).analyze(),
    }

    # Add health score
    tr = TerminalReporter()
    results["health_score"] = tr._calculate_health_score(results)

    # Add human-readable summary
    results["summary"] = _generate_summary(results)

    return results


@mcp.tool()
def get_hotspots(repo_path: str = ".", top_n: int = 10) -> dict:
    """Get the most frequently changed files (hotspots) in a repository.

    These files are the most likely to contain bugs and should be prioritized for refactoring.
    """
    collector = _get_collector(repo_path)
    data = HotspotAnalyzer(collector).analyze()

    return {
        "repo": collector.repo_name(),
        "top_hotspots": data["top_hotspots"][:top_n],
        "total_churn": data["total_churn"],
        "files_changed": data["total_files_changed"],
    }


@mcp.tool()
def get_contributors(repo_path: str = ".") -> dict:
    """Get contributor statistics including bus factor.

    Bus factor = minimum number of people who contribute 50% of commits.
    A low bus factor (1-2) is a serious risk.
    """
    collector = _get_collector(repo_path)
    data = AuthorAnalyzer(collector).analyze()

    return {
        "repo": collector.repo_name(),
        "total_contributors": data["total_contributors"],
        "bus_factor": data["bus_factor"],
        "bus_factor_warning": (
            "🚨 CRITICAL: Single point of failure" if data["bus_factor"] == 1
            else "⚠️ High risk" if data["bus_factor"] <= 2
            else "✅ Healthy distribution"
        ),
        "contributors": data["contributors"],
    }


@mcp.tool()
def get_team_pulse(repo_path: str = ".") -> dict:
    """Get team activity rhythm — peak hours, active days, commit streaks.

    Useful for understanding when the team works and identifying burnout patterns.
    """
    collector = _get_collector(repo_path)
    data = PulseAnalyzer(collector).analyze()

    if "error" in data:
        return {"error": data["error"]}

    return {
        "repo": collector.repo_name(),
        "date_range": data["date_range"],
        "avg_commits_per_day": data["avg_commits_per_day"],
        "peak_hour": f"{data['peak_hour']}:00",
        "peak_day": data["peak_day"],
        "longest_streak_days": data["streaks"]["longest_streak_days"],
        "longest_gap_days": data["streaks"]["longest_gap_days"],
        "total_active_days": data["streaks"]["total_active_days"],
        "monthly_trend": data.get("monthly_trend", {}),
    }


@mcp.tool()
def get_complexity(repo_path: str = ".") -> dict:
    """Get code complexity analysis — find files with high complexity and low comments.

    Returns risky files that are hard to understand and likely to contain bugs.
    """
    collector = _get_collector(repo_path)
    data = ComplexityAnalyzer(collector).analyze()

    return {
        "repo": collector.repo_name(),
        "files_analyzed": data["files_analyzed"],
        "total_lines": data["total_lines"],
        "avg_complexity": data["avg_complexity"],
        "risky_files": data["risky_files"],
        "risk_summary": f"{len(data['risky_files'])} files with high complexity and low comment ratio",
    }


@mcp.tool()
def get_dead_code(repo_path: str = ".") -> dict:
    """Find files that haven't been modified recently — potential dead code.

    Identifies stale files and files that never appear in recent git history.
    """
    collector = _get_collector(repo_path)
    data = DeadCodeAnalyzer(collector).analyze()
    return {
        "repo": collector.repo_name(),
        "total_stale": data["total_stale"],
        "very_stale_count": len(data["very_stale_files"]),
        "never_touched": data["total_never_touched"],
        "staleness_ratio": data["staleness_ratio"],
        "very_stale_files": data["very_stale_files"][:10],
    }


@mcp.tool()
def get_dependencies(repo_path: str = ".") -> dict:
    """Analyze import patterns, coupling, and circular dependencies."""
    collector = _get_collector(repo_path)
    data = DependencyAnalyzer(collector).analyze()
    return {
        "repo": collector.repo_name(),
        "total_import_relations": data["total_import_relations"],
        "most_coupled": data["top_coupled_modules"][:10],
        "circular_deps": data["potential_circular_deps"],
        "warning": data["circular_dep_warning"],
    }


@mcp.tool()
def get_test_coverage(repo_path: str = ".") -> dict:
    """Estimate test coverage by matching source files to test files.

    Uses naming conventions (test_*.py, *.test.js, etc.) — not actual coverage data.
    """
    collector = _get_collector(repo_path)
    data = TestCoverageAnalyzer(collector).analyze()
    return {
        "repo": collector.repo_name(),
        "coverage_grade": data["coverage_grade"],
        "coverage_pct": data["estimated_coverage_pct"],
        "total_source_files": data["total_source_files"],
        "covered_files": data["covered_files"],
        "uncovered_files": data["uncovered_files"],
        "high_risk_uncovered": data["high_risk_uncovered"][:10],
        "warning": data["uncovered_hotspots_warning"],
    }


@mcp.tool()
def get_duplication(repo_path: str = ".") -> dict:
    """Detect code duplication between files."""
    collector = _get_collector(repo_path)
    data = DuplicationAnalyzer(collector).analyze()
    return {
        "repo": collector.repo_name(),
        "summary": data["duplication_summary"],
        "top_duplicate_pairs": data["top_duplicate_pairs"][:15],
        "total_duplicate_lines": data["total_duplicate_lines"],
    }


@mcp.tool()
def get_trends(repo_path: str = ".") -> dict:
    """Get health trends over time — is the codebase improving or declining?

    Requires at least 2 snapshots (use `chm snapshot .` first).
    """
    collector = _get_collector(repo_path)
    tracker = TrendTracker(str(collector.repo_path))
    data = tracker.get_trends()

    return data


@mcp.tool()
def take_snapshot(repo_path: str = ".") -> dict:
    """Save a snapshot of current codebase health for trend tracking.

    Call this periodically (e.g., weekly) to build up historical data.
    """
    collector = _get_collector(repo_path)
    tracker = TrendTracker(str(collector.repo_path))
    snap = tracker.snapshot(collector)

    return {
        "message": f"Snapshot saved ({len(tracker._load_history())} total)",
        "timestamp": snap["timestamp"],
        "repo": collector.repo_name(),
        "commits": snap["total_commits"],
        "files": snap["total_files"],
    }


@mcp.tool()
def compare_snapshots(repo_path: str = ".", snapshot_a: int = -2, snapshot_b: int = -1) -> dict:
    """Compare two snapshots to see what changed between them.

    Args:
        snapshot_a: First snapshot index (-2 = second-to-last)
        snapshot_b: Second snapshot index (-1 = last)
    """
    collector = _get_collector(repo_path)
    tracker = TrendTracker(str(collector.repo_path))
    return tracker.compare(snapshot_a, snapshot_b)


# ── Resources ──────────────────────────────────────────────────

@mcp.tool()
def get_stats(repo_path: str = ".") -> dict:
    """Get aggregate statistics overview for a repository."""
    collector = _get_collector(repo_path)
    from chm.analyzers import (
        HotspotAnalyzer, AuthorAnalyzer, PulseAnalyzer, ComplexityAnalyzer,
        DeadCodeAnalyzer, TestCoverageAnalyzer, DuplicationAnalyzer, DependencyAnalyzer,
    )
    h = HotspotAnalyzer(collector).analyze()
    a = AuthorAnalyzer(collector).analyze()
    p = PulseAnalyzer(collector).analyze()
    cx = ComplexityAnalyzer(collector).analyze()
    d = DeadCodeAnalyzer(collector).analyze()
    cv = TestCoverageAnalyzer(collector).analyze()
    dup = DuplicationAnalyzer(collector).analyze()
    dep = DependencyAnalyzer(collector).analyze()
    return {
        "repo": collector.repo_name(),
        "commits": collector.total_commits(), "files": collector.total_files(),
        "bus_factor": a["bus_factor"], "contributors": a["total_contributors"],
        "total_churn": h["total_churn"], "hotspots_count": len(h["top_hotspots"]),
        "avg_complexity": cx["avg_complexity"], "risky_files": len(cx["risky_files"]),
        "stale_files": d["total_stale"], "test_coverage": f"{cv['coverage_grade']} ({cv['estimated_coverage_pct']}%)",
        "import_relations": dep["total_import_relations"], "circular_deps": len(dep["potential_circular_deps"]),
        "dup_pairs": dup["file_pairs_with_duplication"],
    }


@mcp.tool()
def get_top_files(repo_path: str = ".", metric: str = "churn", top_n: int = 10) -> dict:
    """Get top files ranked by a metric (churn, changes, authors, complexity, lines)."""
    collector = _get_collector(repo_path)
    from chm.analyzers import HotspotAnalyzer, ComplexityAnalyzer
    if metric in ("churn", "changes", "authors"):
        data = HotspotAnalyzer(collector).analyze()["top_hotspots"]
        if metric == "changes": data.sort(key=lambda x: x["changes"], reverse=True)
        elif metric == "authors": data.sort(key=lambda x: x["unique_authors"], reverse=True)
    else:
        data = ComplexityAnalyzer(collector).analyze()["top_complex"]
        if metric == "lines": data.sort(key=lambda x: x["lines"], reverse=True)
    return {"repo": collector.repo_name(), "metric": metric, "files": data[:top_n]}


@mcp.tool()
def get_file_health(repo_path: str = ".", file_path: str = "") -> dict:
    """Get detailed health information about a specific file."""
    collector = _get_collector(repo_path)
    from chm.analyzers import HotspotAnalyzer, ComplexityAnalyzer
    hotspots = HotspotAnalyzer(collector).analyze()
    complexity = ComplexityAnalyzer(collector).analyze()
    file_hotspot = next((h for h in hotspots["top_hotspots"] if h["file"] == file_path), None)
    file_complex = next((f for f in complexity["top_complex"] if f["file"] == file_path), None)
    return {
        "file": file_path,
        "hotspot": file_hotspot,
        "complexity": file_complex,
        "found": file_hotspot is not None or file_complex is not None,
    }


@mcp.tool()
def get_workspace_health(repo_paths: list[str]) -> dict:
    """Compare health scores across multiple repositories."""
    results = []
    from chm.analyzers import AuthorAnalyzer, HotspotAnalyzer
    from chm.reporters import TerminalReporter
    tr = TerminalReporter()
    for p in repo_paths:
        try:
            c = _get_collector(p)
            h = HotspotAnalyzer(c).analyze()
            a = AuthorAnalyzer(c).analyze()
            score = tr._calculate_health_score({
                "hotspots": h, "authors": a, "pulse": {},
                "complexity": {}, "dead_code": {},
                "dependencies": {}, "test_coverage": {}, "duplication": {},
            })
            results.append({"repo": c.repo_name(), "health_score": score, "bus_factor": a["bus_factor"]})
        except ValueError:
            results.append({"repo": p, "error": "not a git repo"})
    results.sort(key=lambda x: x.get("health_score", 0), reverse=True)
    return {"repos": results, "count": len(results)}


@mcp.resource("health://{repo_path}")
def health_resource(repo_path: str = ".") -> str:
    """Get a human-readable health report for a repository."""
    collector = _get_collector(repo_path)

    results = {
        "repo_name": collector.repo_name(),
        "total_commits": collector.total_commits(),
        "total_files": collector.total_files(),
        "hotspots": HotspotAnalyzer(collector).analyze(),
        "authors": AuthorAnalyzer(collector).analyze(),
        "pulse": PulseAnalyzer(collector).analyze(),
        "complexity": ComplexityAnalyzer(collector).analyze(),
    }

    tr = TerminalReporter()
    results["health_score"] = tr._calculate_health_score(results)

    return _format_health_report(results)


# ── Summary Generator ──────────────────────────────────────────

def _generate_summary(results: dict) -> str:
    """Generate a human-readable summary of analysis results."""
    lines = []
    score = results.get("health_score", 50)

    if score >= 80:
        lines.append(f"🟢 Overall health: {score}/100 — Healthy")
    elif score >= 50:
        lines.append(f"🟡 Overall health: {score}/100 — Fair")
    else:
        lines.append(f"🔴 Overall health: {score}/100 — Needs attention")

    # Hotspots
    hotspots = results.get("hotspots", {})
    top = hotspots.get("top_hotspots", [])
    if top:
        lines.append(f"🔥 Top hotspot: {top[0]['file']} ({top[0]['total_churn']} churn, {top[0]['unique_authors']} authors)")

    # Bus factor
    authors = results.get("authors", {})
    bf = authors.get("bus_factor", "?")
    lines.append(f"👥 Bus factor: {bf} ({authors.get('total_contributors', '?')} contributors)")

    # Activity
    pulse = results.get("pulse", {})
    if pulse and "avg_commits_per_day" in pulse:
        lines.append(f"💓 Activity: {pulse['avg_commits_per_day']} commits/day, peak at {pulse.get('peak_hour', '?')}:00")

    # Complexity
    complexity = results.get("complexity", {})
    risky = complexity.get("risky_files", [])
    if risky:
        lines.append(f"🧩 {len(risky)} risky files (high complexity, low comments)")

    return "\n".join(lines)


def _format_health_report(results: dict) -> str:
    """Format a full health report as text."""
    score = results["health_score"]
    color = "green" if score >= 70 else "yellow" if score >= 40 else "red"

    report = f"""🏠 Codebase Health Report: {results['repo_name']}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Overall Score: {score}/100 ({color})

📊 Overview
  Commits: {results['total_commits']}
  Files: {results['total_files']}

🔥 Top Hotspots
"""
    for h in results["hotspots"]["top_hotspots"][:5]:
        report += f"  {h['file']}: {h['changes']} changes, {h['total_churn']} churn\n"

    authors = results["authors"]
    report += f"""
👥 Contributors
  Total: {authors['total_contributors']}
  Bus Factor: {authors['bus_factor']}
"""

    for c in authors.get("contributors", [])[:3]:
        report += f"  {c['name']}: {c['commits']} commits\n"

    return report


# ── Entry Point ────────────────────────────────────────────────

def main():
    """Entry point for `chm mcp` command."""
    import argparse

    parser = argparse.ArgumentParser(description="CHM MCP Server")
    parser.add_argument("--http", type=int, default=None, help="HTTP port (default: stdio)")
    parser.add_argument("--host", default="127.0.0.1", help="HTTP host")
    args = parser.parse_args()

    if args.http:
        print(f"🚀 CHM MCP Server on http://{args.host}:{args.http}/mcp")
        mcp.run(transport="streamable-http", host=args.host, port=args.http)
    else:
        mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
