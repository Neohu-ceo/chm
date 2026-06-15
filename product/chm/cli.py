"""CHM CLI — Codebase Health Monitor command-line interface."""

import sys
import time
from pathlib import Path

import click

from chm import __version__
from chm.git_collector import GitCollector
from chm.analyzers import (
    HotspotAnalyzer,
    AuthorAnalyzer,
    PulseAnalyzer,
    ComplexityAnalyzer,
)
from chm.reporters import TerminalReporter, HTMLReporter, JSONReporter
from chm.analyzers.trends import TrendTracker
from chm import saas_client


@click.group()
@click.version_option(__version__, "-v", "--version")
def main():
    """🏠 CHM — Codebase Health Monitor by Lighthouse Analytics.

    Analyze any git repository and generate health reports.
    """
    pass


@main.command()
@click.argument("path", default=".", type=click.Path(exists=True))
@click.option("--report", "-r", type=click.Choice(["terminal", "html", "json"]),
              default="terminal", help="Report format")
@click.option("--output", "-o", type=click.Path(), help="Output file path")
@click.option("--max-commits", "-n", default=500, help="Maximum commits to analyze")
def analyze(path: str, report: str, output: str, max_commits: int):
    """Run a full health analysis on a git repository."""
    repo_path = Path(path).resolve()

    try:
        collector = GitCollector(str(repo_path))
    except ValueError as e:
        click.echo(f"❌ {e}", err=True)
        sys.exit(1)

    click.echo(f"🔍 Analyzing {click.style(collector.repo_name(), bold=True)}...")
    start_time = time.time()

    # Run all analyzers
    click.echo("  ├─ Collecting commit data...")
    total_commits = collector.total_commits()
    total_files = collector.total_files()

    click.echo("  ├─ Analyzing hotspots...")
    hotspots = HotspotAnalyzer(collector).analyze()

    click.echo("  ├─ Analyzing authors...")
    authors = AuthorAnalyzer(collector).analyze()

    click.echo("  ├─ Analyzing team pulse...")
    pulse = PulseAnalyzer(collector).analyze()

    click.echo("  ├─ Analyzing complexity...")
    complexity = ComplexityAnalyzer(collector).analyze()

    elapsed = time.time() - start_time

    # Assemble results
    results = {
        "repo_name": collector.repo_name(),
        "repo_path": str(repo_path),
        "total_commits": total_commits,
        "total_files": total_files,
        "hotspots": hotspots,
        "authors": authors,
        "pulse": pulse,
        "complexity": complexity,
        "analysis_time_seconds": round(elapsed, 2),
    }

    # Calculate health score
    tr = TerminalReporter()
    results["health_score"] = tr._calculate_health_score(results)

    # Output
    if report == "terminal":
        tr.render_all(results)
        click.echo(f"  ⏱️  Analysis completed in {elapsed:.1f}s")
    elif report == "html":
        html = HTMLReporter().render_all(results)
        if output:
            Path(output).write_text(html, encoding="utf-8")
            click.echo(f"✅ HTML report saved to {output}")
            click.echo(f"   Open with: open {output}")
        else:
            # Print to stdout (useful for piping)
            click.echo(html)
    elif report == "json":
        json_str = JSONReporter().render_all(results)
        if output:
            Path(output).write_text(json_str, encoding="utf-8")
            click.echo(f"✅ JSON report saved to {output}")
        else:
            click.echo(json_str)

    # Quick health summary for terminal
    if report == "terminal":
        score = results["health_score"]
        if score >= 80:
            click.echo(f"  🟢 Overall: {click.style('Healthy', fg='green')}")
        elif score >= 50:
            click.echo(f"  🟡 Overall: {click.style('Fair', fg='yellow')}")
        else:
            click.echo(f"  🔴 Overall: {click.style('Needs Attention', fg='red')}")


@main.command()
@click.argument("path", default=".", type=click.Path(exists=True))
@click.option("--top", "-t", default=15, help="Number of hotspots to show")
def hotspots(path: str, top: int):
    """Show the most frequently changed files."""
    try:
        collector = GitCollector(str(Path(path).resolve()))
    except ValueError as e:
        click.echo(f"❌ {e}", err=True)
        sys.exit(1)

    data = HotspotAnalyzer(collector).analyze()
    reporter = TerminalReporter()
    reporter._header("🔥 Code Hotspots")
    reporter.render_hotspots(data)


@main.command()
@click.argument("path", default=".", type=click.Path(exists=True))
def authors(path: str):
    """Show contributor statistics."""
    try:
        collector = GitCollector(str(Path(path).resolve()))
    except ValueError as e:
        click.echo(f"❌ {e}", err=True)
        sys.exit(1)

    data = AuthorAnalyzer(collector).analyze()
    reporter = TerminalReporter()
    reporter._header("👥 Contributors")
    reporter.render_authors(data)


@main.command()
@click.argument("path", default=".", type=click.Path(exists=True))
def pulse(path: str):
    """Show team activity rhythm."""
    try:
        collector = GitCollector(str(Path(path).resolve()))
    except ValueError as e:
        click.echo(f"❌ {e}", err=True)
        sys.exit(1)

    data = PulseAnalyzer(collector).analyze()
    reporter = TerminalReporter()
    reporter._header("💓 Team Pulse")
    reporter.render_pulse(data)


@main.command()
@click.argument("path", default=".", type=click.Path(exists=True))
def churn(path: str):
    """Show code churn overview."""
    try:
        collector = GitCollector(str(Path(path).resolve()))
    except ValueError as e:
        click.echo(f"❌ {e}", err=True)
        sys.exit(1)

    data = HotspotAnalyzer(collector).analyze()
    click.echo(f"\n  📊 Total churn: {data['total_churn']:,} lines")
    click.echo(f"  📁 Files changed: {data['total_files_changed']}")
    click.echo(f"  📈 Avg changes per file: {data['average_changes_per_file']:.1f}")


@main.command()
@click.argument("path", default=".", type=click.Path(exists=True))
@click.option("--max-commits", "-n", default=500)
def snapshot(path: str, max_commits: int):
    """Save a snapshot for trend tracking."""
    repo_path = Path(path).resolve()
    try:
        collector = GitCollector(str(repo_path))
    except ValueError as e:
        click.echo(f"❌ {e}", err=True)
        sys.exit(1)

    click.echo(f"📸 Taking snapshot of {collector.repo_name()}...")
    tracker = TrendTracker(str(repo_path))
    snap = tracker.snapshot(collector)
    click.echo(f"✅ Snapshot saved ({len(tracker._load_history())} total)")
    click.echo(f"   Commits: {snap['total_commits']}, Files: {snap['total_files']}")


@main.command()
@click.argument("path", default=".", type=click.Path(exists=True))
def trends(path: str):
    """Show health trends over time."""
    repo_path = Path(path).resolve()
    try:
        collector = GitCollector(str(repo_path))
    except ValueError as e:
        click.echo(f"❌ {e}", err=True)
        sys.exit(1)

    tracker = TrendTracker(str(repo_path))
    data = tracker.get_trends()

    if "message" in data:
        click.echo(f"📊 {data['message']}")
        click.echo(f"   Run 'chm snapshot .' to create your first snapshot.")
        return

    # Display trends
    click.echo(f"\n📈 Trends: {data['date_range']}")
    click.echo(f"   Snapshots: {data['snapshots']}")

    click.echo(f"\n{click.style('Deltas:', bold=True)}")
    deltas = data["deltas"]
    for key, val in deltas.items():
        sign = "+" if val > 0 else ""
        color = "green" if (
            (key in ["commits", "bus_factor", "contributors"] and val > 0)
            or (key in ["total_churn", "avg_complexity", "risky_files"] and val < 0)
        ) else "red" if val != 0 else "white"
        click.echo(f"   {key}: {click.style(f'{sign}{val}', fg=color)}")

    direction = data["direction"]
    emoji = "📈" if direction["overall"] == "improving" else "📉" if direction["overall"] == "declining" else "➡️"
    click.echo(f"\n   {emoji} Overall: {direction['overall']}")
    for signal in direction["signals"]:
        click.echo(f"      {signal}")


@main.command()
@click.argument("path", default=".", type=click.Path(exists=True))
@click.option("--a", "-a", default=-2, type=int, help="First snapshot index (-2 = second to last)")
@click.option("--b", "-b", default=-1, type=int, help="Second snapshot index (-1 = last)")
def compare(path: str, a: int, b: int):
    """Compare two snapshots in detail."""
    repo_path = Path(path).resolve()
    tracker = TrendTracker(str(repo_path))
    data = tracker.compare(a, b)

    if "error" in data:
        click.echo(f"❌ {data['error']}")
        return

    click.echo(f"\n📊 Comparing snapshots:")
    click.echo(f"   A: #{data['snapshot_a']['index']} ({data['snapshot_a']['date']})")
    click.echo(f"   B: #{data['snapshot_b']['index']} ({data['snapshot_b']['date']})")

    click.echo(f"\n{click.style('New Hotspots:', 'yellow')}")
    for h in data.get("new_hotspots", []):
        click.echo(f"   ⚠️  {h['file']} (+{h['total_churn']} churn)")

    click.echo(f"\n{click.style('Resolved Hotspots:', 'green')}")
    for h in data.get("resolved_hotspots", []):
        click.echo(f"   ✅ {h['file']} (was {h['previous_churn']} churn)")

    cc = data.get("contributor_changes", {})
    if cc.get("new_contributors"):
        click.echo(f"\n🆕 New contributors: {', '.join(cc['new_contributors'])}")
    if cc.get("departed_contributors"):
        click.echo(f"👋 Departed: {', '.join(cc['departed_contributors'])}")


@main.command()
@click.argument("api_key")
def login(api_key: str):
    """Login with your Lighthouse Analytics API key."""
    saas_client.login(api_key)
    click.echo("✅ Logged in successfully!")
    entitlement = saas_client.check_entitlement()
    click.echo(f"   Plan: {entitlement['plan'].upper()}")
    click.echo(f"   Features: {', '.join(entitlement['features'])}")


@main.command()
def logout():
    """Logout and clear stored credentials."""
    saas_client.logout()
    click.echo("👋 Logged out. Credentials cleared.")


@main.command()
@click.argument("path", default=".", type=click.Path(exists=True))
def status(path: str):
    """Check entitlement and SaaS connection status."""
    entitlement = saas_client.check_entitlement()

    click.echo(f"\n🏠 Lighthouse Analytics — Status")
    click.echo(f"   Plan: {click.style(entitlement['plan'].upper(), bold=True)}")
    click.echo(f"   Auth method: {entitlement['method']}")
    click.echo(f"   Features: {', '.join(entitlement['features'])}")

    # Check if in a git repo
    repo_path = Path(path).resolve()
    try:
        collector = GitCollector(str(repo_path))
        click.echo(f"\n   Current repo: {collector.repo_name()}")
        click.echo(f"   Commits: {collector.total_commits()}")

        tracker = TrendTracker(str(repo_path))
        history = tracker._load_history()
        click.echo(f"   Snapshots: {len(history)}")
    except ValueError:
        click.echo(f"\n   {path} is not a git repository")


if __name__ == "__main__":
    main()
