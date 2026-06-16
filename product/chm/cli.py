"""CHM CLI — Codebase Health Monitor command-line interface."""

import sys
import time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

import click

from chm import __version__
from chm.git_collector import GitCollector
from chm.analyzers import (
    HotspotAnalyzer,
    AuthorAnalyzer,
    PulseAnalyzer,
    ComplexityAnalyzer,
    DeadCodeAnalyzer,
    DependencyAnalyzer,
    TestCoverageAnalyzer,
    DuplicationAnalyzer,
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

    # Collect base data (must be sequential — shared git calls)
    total_commits = collector.total_commits()
    total_files = collector.total_files()

    # Run all 8 analyzers in parallel
    analyzers = {
        "hotspots": lambda: HotspotAnalyzer(collector).analyze(),
        "authors": lambda: AuthorAnalyzer(collector).analyze(),
        "pulse": lambda: PulseAnalyzer(collector).analyze(),
        "complexity": lambda: ComplexityAnalyzer(collector).analyze(),
        "dead_code": lambda: DeadCodeAnalyzer(collector).analyze(),
        "dependencies": lambda: DependencyAnalyzer(collector).analyze(),
        "test_coverage": lambda: TestCoverageAnalyzer(collector).analyze(),
        "duplication": lambda: DuplicationAnalyzer(collector).analyze(),
    }

    results_partial = {}
    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = {executor.submit(fn): name for name, fn in analyzers.items()}
        for future in as_completed(futures):
            name = futures[future]
            click.echo(f"  ├─ {name}...")
            results_partial[name] = future.result()

    hotspots = results_partial["hotspots"]
    authors = results_partial["authors"]
    pulse = results_partial["pulse"]
    complexity = results_partial["complexity"]
    dead_code = results_partial["dead_code"]
    dependencies = results_partial["dependencies"]
    test_coverage = results_partial["test_coverage"]
    duplication = results_partial["duplication"]

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
        "dead_code": dead_code,
        "dependencies": dependencies,
        "test_coverage": test_coverage,
        "duplication": duplication,
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


@main.command()
@click.option("--http", type=int, default=None, help="HTTP port (default: stdio)")
@click.option("--host", default="127.0.0.1", help="HTTP host")
def mcp(http: int, host: str):
    """Start CHM as an MCP (Model Context Protocol) server.

    Exposes 8 tools and 1 resource for AI agents to query codebase health.
    Use stdio transport by default, or --http for HTTP transport.

    \b
    Examples:
      chm mcp                  # stdio (for Claude Desktop)
      chm mcp --http 8080      # HTTP (for network access)
      claude mcp add chm -- chm mcp
    """
    from chm.mcp_server import main as mcp_main
    import sys
    # Simulate: python -m chm.mcp_server --http PORT
    sys.argv = ["chm-mcp"]
    if http:
        sys.argv.extend(["--http", str(http), "--host", host])
    mcp_main()


@main.command()
@click.argument("path", default=".", type=click.Path(exists=True))
def deadcode(path: str):
    """Detect files that haven't been modified recently (potential dead code)."""
    try:
        collector = GitCollector(str(Path(path).resolve()))
    except ValueError as e:
        click.echo(f"❌ {e}", err=True)
        sys.exit(1)

    data = DeadCodeAnalyzer(collector).analyze()
    click.echo(f"\n💀 Dead Code Analysis — {collector.repo_name()}")
    click.echo(f"   Stale files: {data['total_stale']}")
    click.echo(f"   Never touched: {data['total_never_touched']}")
    click.echo(f"   Staleness ratio: {data['staleness_ratio']:.1%}")

    if data["very_stale_files"]:
        click.echo(f"\n   {click.style('Very Stale (1+ year):', 'red')}")
        for f in data["very_stale_files"][:10]:
            click.echo(f"   💀 {f['file']} ({f['months_stale']} months)")


@main.command()
@click.argument("path", default=".", type=click.Path(exists=True))
def deps(path: str):
    """Analyze dependencies and coupling between files."""
    try:
        collector = GitCollector(str(Path(path).resolve()))
    except ValueError as e:
        click.echo(f"❌ {e}", err=True)
        sys.exit(1)

    data = DependencyAnalyzer(collector).analyze()
    click.echo(f"\n🔗 Dependency Analysis — {collector.repo_name()}")
    click.echo(f"   Files with imports: {data['files_with_imports']}")
    click.echo(f"   Total import relations: {data['total_import_relations']}")
    click.echo(f"   {data['circular_dep_warning']}")

    if data["top_coupled_modules"]:
        click.echo(f"\n   Most-coupled modules:")
        for m in data["top_coupled_modules"][:5]:
            click.echo(f"   📦 {m['module']} — imported by {m['imported_by_count']} files")


@main.command()
@click.argument("path", default=".", type=click.Path(exists=True))
def coverage(path: str):
    """Estimate test coverage by matching source files to test files."""
    try:
        collector = GitCollector(str(Path(path).resolve()))
    except ValueError as e:
        click.echo(f"❌ {e}", err=True)
        sys.exit(1)

    data = TestCoverageAnalyzer(collector).analyze()
    grade_color = "green" if data["coverage_grade"] in ("A", "B") else "yellow" if data["coverage_grade"] == "C" else "red"
    click.echo(f"\n🧪 Test Coverage Estimate — {collector.repo_name()}")
    click.echo(f"   Source files: {data['total_source_files']}")
    click.echo(f"   Test files: {data['total_test_files']}")
    cov_str = f"{data['coverage_grade']} — {data['estimated_coverage_pct']}%"
    click.echo(f"   Estimated coverage: {click.style(cov_str, fg=grade_color)}")

    if data["uncovered_hotspots_warning"]:
        click.echo(f"   {click.style(data['uncovered_hotspots_warning'], 'red')}")


@main.command()
@click.argument("path", default=".", type=click.Path(exists=True))
def duplicates(path: str):
    """Detect duplicate code blocks across files."""
    try:
        collector = GitCollector(str(Path(path).resolve()))
    except ValueError as e:
        click.echo(f"❌ {e}", err=True)
        sys.exit(1)

    data = DuplicationAnalyzer(collector).analyze()
    click.echo(f"\n📋 Duplication Detection — {collector.repo_name()}")
    click.echo(f"   {data['duplication_summary']}")

    if data["top_duplicate_pairs"]:
        click.echo(f"\n   Top duplicate file pairs:")
        for d in data["top_duplicate_pairs"][:8]:
            click.echo(f"   📋 {d['file_a']} ↔ {d['file_b']} ({d['shared_lines']} lines)")


@main.command()
@click.argument("path", default=".", type=click.Path(exists=True))
def init(path: str):
    """Initialize CHM for a project — guided onboarding wizard.

    Takes a first snapshot, sets up config, and shows next steps.
    """
    repo_path = Path(path).resolve()

    try:
        collector = GitCollector(str(repo_path))
    except ValueError as e:
        click.echo(f"❌ {e}", err=True)
        sys.exit(1)

    # Fancy header
    click.echo(f"""
{click.style('╔══════════════════════════════════════════╗', fg='blue')}
{click.style('║', fg='blue')}  {click.style('🏠 Welcome to Lighthouse Analytics!', bold=True)}  {click.style('║', fg='blue')}
{click.style('╚══════════════════════════════════════════╝', fg='blue')}
""")

    click.echo(f"  Repository: {click.style(collector.repo_name(), fg='cyan')}")
    click.echo(f"  Path: {repo_path}")
    click.echo(f"  Total commits: {collector.total_commits()}")
    click.echo(f"  Total files: {collector.total_files()}")
    click.echo()

    # Step 1: First snapshot
    click.echo(f"  {click.style('📸 Step 1: Taking baseline snapshot...', fg='yellow')}")
    from chm.analyzers.trends import TrendTracker
    tracker = TrendTracker(str(repo_path))
    snap = tracker.snapshot(collector)
    click.echo(f"  ✅ Baseline saved ({snap['timestamp'][:19]})")

    # Step 2: Quick analysis
    click.echo(f"\n  {click.style('🔍 Step 2: Quick health scan...', fg='yellow')}")
    hotspots = HotspotAnalyzer(collector).analyze()
    authors = AuthorAnalyzer(collector).analyze()
    pulse = PulseAnalyzer(collector).analyze()
    complexity = ComplexityAnalyzer(collector).analyze()
    dead_code = DeadCodeAnalyzer(collector).analyze()
    test_coverage = TestCoverageAnalyzer(collector).analyze()

    # Quick summary
    bf = authors.get("bus_factor", "?")
    bf_warn = "⚠️" if (isinstance(bf, int) and bf <= 2) else "✅"
    score = TerminalReporter()._calculate_health_score({
        "hotspots": hotspots, "authors": authors, "pulse": pulse,
        "complexity": complexity, "dead_code": dead_code,
        "test_coverage": test_coverage, "dependencies": {}, "duplication": {},
    })

    click.echo(f"  {bf_warn} Bus Factor: {bf}")
    click.echo(f"  🔥 Hotspots: {len(hotspots['top_hotspots'])} files")
    click.echo(f"  🧪 Test Coverage: {test_coverage.get('coverage_grade', '?')} ({test_coverage.get('estimated_coverage_pct', 0)}%)")
    click.echo(f"  🧬 Health Score: {score}/100")

    # Step 3: What's next
    click.echo(f"""
{click.style('  ── Next Steps ──', bold=True)}
  {click.style('1.', fg='green')} Review your report:  {click.style('chm analyze .', fg='cyan')}
  {click.style('2.', fg='green')} Generate HTML:      {click.style('chm analyze . --report html -o report.html', fg='cyan')}
  {click.style('3.', fg='green')} Track trends:       {click.style('chm snapshot .', fg='cyan')} (run weekly)
  {click.style('4.', fg='green')} Compare snapshots:  {click.style('chm compare .', fg='cyan')}
  {click.style('5.', fg='green')} Share with team:    {click.style('open report.html', fg='cyan')}

  Run {click.style('chm --help', bold=True)} to see all 14 commands.
""")

    # Step 4: SaaS mention
    click.echo(f"  {click.style('💡 Pro tip:', fg='yellow')} Get HTML reports + team dashboards at")
    click.echo(f"     {click.style('http://localhost:5001', fg='cyan')} (SaaS running locally)")

    click.echo(f"\n{click.style('  🎉 Ready! Lighthouse is watching your codebase.', fg='green')}\n")


@main.command()
@click.argument("path", default=".", type=click.Path(exists=True))
@click.option("--install/--uninstall", default=True, help="Install or uninstall the git hook")
def watch(path: str, install: bool):
    """Auto-monitor: install a git post-commit hook to run analysis on every commit.

    \b
    Examples:
      chm watch .             # Install hook
      chm watch . --uninstall # Remove hook
    """
    repo_path = Path(path).resolve()
    hooks_dir = repo_path / ".git" / "hooks"
    hook_path = hooks_dir / "post-commit"

    if not hooks_dir.exists():
        click.echo("❌ Not a git repository", err=True)
        sys.exit(1)

    if not install:
        if hook_path.exists():
            hook_path.unlink()
            click.echo("🗑️  Git hook removed. CHM will no longer auto-analyze commits.")
        else:
            click.echo("No hook installed.")
        return

    # Create the hook
    chm_path = sys.argv[0] if sys.argv[0].endswith("chm") else "chm"
    hook_script = f"""#!/bin/bash
# CHM auto-analysis hook — installed by 'chm watch'
# Runs a quick health snapshot after each commit.

CHM="{chm_path}"
REPO="{repo_path}"

# Quick analysis (silent, logs to .chm/)
mkdir -p "$REPO/.chm/"
$CHM snapshot "$REPO" --max-commits 100 >> "$REPO/.chm/watch.log" 2>&1
echo "  🏠 CHM snapshot saved" >> "$REPO/.chm/watch.log"
"""

    hook_path.write_text(hook_script)
    hook_path.chmod(0o755)

    click.echo(f"✅ Git post-commit hook installed!")
    click.echo(f"   Hook: {hook_path}")
    click.echo(f"   CHM will snapshot after each commit.")
    click.echo(f"   Logs: {repo_path}/.chm/watch.log")
    click.echo(f"")
    click.echo(f"   To uninstall: {click.style('chm watch . --uninstall', fg='yellow')}")


@main.command()
@click.argument("path", default=".", type=click.Path(exists=True))
@click.option("--output", "-o", type=click.Path(), help="Save badge to file")
@click.option("--shields", is_flag=True, help="Generate shields.io URL instead of SVG")
def badge(path: str, output: str, shields: bool):
    """Generate a code health badge (SVG) for README.

    \b
    Examples:
      chm badge .                    # Print SVG badge
      chm badge . -o badge.svg       # Save to file
      chm badge . --shields          # Print shields.io URL
    """
    from chm.badge import generate_badge, generate_shields_url

    repo_path = Path(path).resolve()
    try:
        GitCollector(str(repo_path))
    except ValueError as e:
        click.echo(f"❌ {e}", err=True)
        sys.exit(1)

    if shields:
        url = generate_shields_url(str(repo_path))
        click.echo(url)
    else:
        svg = generate_badge(str(repo_path))
        if output:
            Path(output).write_text(svg)
            click.echo(f"✅ Badge saved to {output}")
        else:
            click.echo(svg)


@main.command()
@click.argument("path", default=".", type=click.Path(exists=True))
def doctor(path: str):
    """Run a full diagnosis and get an actionable prescription.

    Analyzes all 8 health dimensions and outputs a prioritized list
    of specific, actionable recommendations to improve your codebase.
    """
    from chm.doctor import Doctor

    repo_path = Path(path).resolve()
    try:
        diagnosis = Doctor(str(repo_path)).diagnose()
    except ValueError as e:
        click.echo(f"❌ {e}", err=True)
        sys.exit(1)

    score = diagnosis["health_score"]
    color = "green" if score >= 70 else "yellow" if score >= 40 else "red"

    click.echo(f"""
{click.style('🏥 CHM Doctor — Diagnosis for ' + diagnosis['repo'], bold=True)}
{'═' * 60}

  Health Score: {click.style(f'{score}/100', fg=color)}

  {diagnosis['summary']}
""")

    for i, p in enumerate(diagnosis["prescriptions"]):
        icon = {"critical": "🚨", "high": "⚠️", "medium": "📝", "low": "💡"}.get(p["priority"], "•")
        pri_color = {"critical": "red", "high": "yellow", "medium": "blue", "low": "white"}.get(p["priority"], "white")

        tag = f"[{p['category']}] {p['title']}"
        click.echo(f"\n  {icon} {click.style(tag, fg=pri_color, bold=True)}")
        click.echo(f"  {p['detail']}")
        click.echo(f"\n  {click.style('处方:', bold=True)}")
        for action in p["actions"]:
            click.echo(f"    {click.style('▸', fg='green')} {action}")

    click.echo(f"\n{'═' * 60}")
    click.echo(f"  {len(diagnosis['prescriptions'])} issues found. Start from the top.\n")


@main.command()
def demo():
    """Run a demonstration with a generated repo — no git project needed.

    Creates a realistic demo repository with 23 commits from 3 contributors
    and runs a full analysis. Perfect for trying out CHM.
    """
    from chm.demo import create_demo_repo

    click.echo(f"{click.style('🎬 Generating demo repository...', fg='yellow')}")
    repo_path = create_demo_repo()
    click.echo(f"   Demo repo: {repo_path}")

    click.echo(f"\n{click.style('🔍 Running full analysis...', fg='yellow')}")
    import sys as _sys
    _sys.argv = ["chm", "analyze", repo_path, "--report", "terminal"]
    try:
        main(standalone_mode=False)
    except SystemExit:
        pass


if __name__ == "__main__":
    main()
