"""README badge generator — SVG shields.io-style code health badges.

Usage:
    chm badge .                    # Generate badge from current analysis
    chm badge . --output badge.svg # Save to file
    chm badge . --style flat       # Badge style: flat, plastic, square

The badge can be embedded in GitHub README:
    ![Code Health](https://img.shields.io/badge/...)
    OR (offline):
    ![Code Health](./badge.svg)
"""

from pathlib import Path
from chm.git_collector import GitCollector
from chm.analyzers import (
    HotspotAnalyzer, AuthorAnalyzer, PulseAnalyzer, ComplexityAnalyzer,
    DeadCodeAnalyzer, DependencyAnalyzer, TestCoverageAnalyzer, DuplicationAnalyzer,
)
from chm.reporters import TerminalReporter

# Badge color scheme
COLORS = {
    "green": ("#4c1", "#fff"),
    "yellow": ("#dfb317", "#fff"),
    "orange": ("#fe7d37", "#fff"),
    "red": ("#e05d44", "#fff"),
}


def generate_badge(repo_path: str = ".", style: str = "flat") -> str:
    """Generate an SVG code health badge."""
    repo_path = Path(repo_path).resolve()
    collector = GitCollector(str(repo_path))

    # Quick analysis
    results = {
        "hotspots": HotspotAnalyzer(collector).analyze(),
        "authors": AuthorAnalyzer(collector).analyze(),
        "pulse": PulseAnalyzer(collector).analyze(),
        "complexity": ComplexityAnalyzer(collector).analyze(),
        "dead_code": DeadCodeAnalyzer(collector).analyze(),
        "dependencies": DependencyAnalyzer(collector).analyze(),
        "test_coverage": TestCoverageAnalyzer(collector).analyze(),
        "duplication": DuplicationAnalyzer(collector).analyze(),
    }

    tr = TerminalReporter()
    score = tr._calculate_health_score(results)

    # Determine color and label
    if score >= 80:
        color, text_color = COLORS["green"]
        label = "healthy"
    elif score >= 60:
        color, text_color = COLORS["yellow"]
        label = "fair"
    elif score >= 40:
        color, text_color = COLORS["orange"]
        label = "needs work"
    else:
        color, text_color = COLORS["red"]
        label = "at risk"

    # Generate SVG
    left_text = "code health"
    right_text = f"{label} {score}%"

    # Calculate text widths (approximate: ~7px per char)
    left_width = len(left_text) * 7 + 20
    right_width = len(right_text) * 7 + 20
    total_width = left_width + right_width
    height = 20

    radius = 2 if style == "flat" else 3

    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="{total_width}" height="{height}" role="img" aria-label="Code Health: {score}/100">
  <title>Code Health: {score}/100 — {label}</title>
  <linearGradient id="s" x2="0" y2="100%">
    <stop offset="0" stop-color="#bbb" stop-opacity=".1"/>
    <stop offset="1" stop-opacity=".1"/>
  </linearGradient>
  <clipPath id="r">
    <rect width="{total_width}" height="{height}" rx="{radius}" fill="#fff"/>
  </clipPath>
  <g clip-path="url(#r)">
    <rect width="{left_width}" height="{height}" fill="#555"/>
    <rect x="{left_width}" width="{right_width}" height="{height}" fill="{color}"/>
    <rect width="{total_width}" height="{height}" fill="url(#s)"/>
  </g>
  <g fill="{text_color}" text-anchor="middle" font-family="Verdana,Geneva,DejaVu Sans,sans-serif" font-size="11">
    <text x="{left_width / 2}" y="14" fill="#fff">{left_text}</text>
    <text x="{left_width + right_width / 2}" y="14">{right_text}</text>
  </g>
</svg>"""

    return svg


def generate_shields_url(repo_path: str = ".") -> str:
    """Generate a shields.io dynamic badge URL (requires hosted endpoint)."""
    collector = GitCollector(str(repo_path))
    results = {
        "hotspots": HotspotAnalyzer(collector).analyze(),
        "authors": AuthorAnalyzer(collector).analyze(),
        "pulse": PulseAnalyzer(collector).analyze(),
        "complexity": ComplexityAnalyzer(collector).analyze(),
        "dead_code": DeadCodeAnalyzer(collector).analyze(),
        "dependencies": DependencyAnalyzer(collector).analyze(),
        "test_coverage": TestCoverageAnalyzer(collector).analyze(),
        "duplication": DuplicationAnalyzer(collector).analyze(),
    }
    tr = TerminalReporter()
    score = tr._calculate_health_score(results)

    color = "green" if score >= 80 else "yellow" if score >= 60 else "orange" if score >= 40 else "red"
    return f"https://img.shields.io/badge/code_health-{score}%25-{color}"
