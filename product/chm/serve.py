"""Local web dashboard — start a server to view health data.

Usage: chm serve .
Then open http://localhost:5299
"""

import json
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path

from chm.git_collector import GitCollector
from chm.analyzers import (
    HotspotAnalyzer, AuthorAnalyzer, PulseAnalyzer, ComplexityAnalyzer,
    DeadCodeAnalyzer, DependencyAnalyzer, TestCoverageAnalyzer, DuplicationAnalyzer,
)
from chm.reporters import TerminalReporter, HTMLReporter


def run_analysis(repo_path: str) -> dict:
    c = GitCollector(repo_path)
    results = {
        "repo": c.repo_name(),
        "commits": c.total_commits(),
        "files": c.total_files(),
        "hotspots": HotspotAnalyzer(c).analyze(),
        "authors": AuthorAnalyzer(c).analyze(),
        "pulse": PulseAnalyzer(c).analyze(),
        "complexity": ComplexityAnalyzer(c).analyze(),
        "dead_code": DeadCodeAnalyzer(c).analyze(),
        "deps": DependencyAnalyzer(c).analyze(),
        "coverage": TestCoverageAnalyzer(c).analyze(),
        "dupes": DuplicationAnalyzer(c).analyze(),
    }
    tr = TerminalReporter()
    results["health_score"] = tr._calculate_health_score(results)
    return results


DASHBOARD_HTML = """<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>CHM Dashboard</title>
<style>:root{--bg:#0a0f18;--card:rgba(255,255,255,.03);--text:#e0e8f0;--muted:#6b8299;--accent:#2563eb;--green:#10b981;--yellow:#f59e0b;--red:#ef4444}
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:-apple-system,sans-serif;background:var(--bg);color:var(--text);line-height:1.6}
.container{max-width:960px;margin:0 auto;padding:2rem}
h1{font-size:1.5rem;margin-bottom:.5rem}h1 span{color:var(--accent)}
.score-ring{width:100px;height:100px;border-radius:50%;border:4px solid;display:flex;align-items:center;justify-content:center;margin:1rem auto}
.score-ring .num{font-size:2rem;font-weight:800}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:.75rem;margin:1.5rem 0}
.metric{background:var(--card);border-radius:12px;padding:1rem;text-align:center;border:1px solid rgba(255,255,255,.05)}
.metric .val{font-size:1.5rem;font-weight:700}.metric .lbl{font-size:.7rem;color:var(--muted)}
.card{background:var(--card);border-radius:12px;padding:1.25rem;border:1px solid rgba(255,255,255,.05);margin-bottom:1rem}
.card h3{margin-bottom:.75rem;font-size:.95rem}
table{width:100%;border-collapse:collapse;font-size:.85rem}
th{text-align:left;padding:.4rem;color:var(--muted);font-size:.7rem;text-transform:uppercase}
td{padding:.35rem .4rem;border-top:1px solid rgba(255,255,255,.04)}
footer{text-align:center;padding:2rem;color:var(--muted);font-size:.75rem}
</style></head><body><div class="container">
<h1>🏠 <span>CHM</span> Dashboard</h1>
<p style="color:var(--muted);font-size:.85rem" id="repo-info"></p>
<div id="score"></div><div class="grid" id="metrics"></div>
<div class="card"><h3>🔥 Hotspots</h3><div id="hotspots"></div></div>
<div class="card"><h3>👥 Contributors</h3><div id="authors"></div></div>
<footer>CHM Local Dashboard · :5299 · Auto-refresh every 30s</footer>
</div>
<script>
async function load(){const r=await(await fetch('/api/data')).json()
document.getElementById('repo-info').textContent=`${r.repo} · ${r.commits} commits · ${r.files} files`
const s=r.health_score;const c=s>=70?'var(--green)':s>=40?'var(--yellow)':'var(--red)'
document.getElementById('score').innerHTML=`<div class="score-ring" style="border-color:${c}"><span class="num" style="color:${c}">${s}</span></div>`
document.getElementById('metrics').innerHTML=`
<div class="metric"><div class="val">${r.authors.bus_factor||'?'}</div><div class="lbl">Bus Factor</div></div>
<div class="metric"><div class="val">${r.authors.total_contributors||0}</div><div class="lbl">Contributors</div></div>
<div class="metric"><div class="val">${r.hotspots.total_churn||0}</div><div class="lbl">Total Churn</div></div>
<div class="metric"><div class="val">${r.coverage.coverage_grade||'?'}</div><div class="lbl">Test Coverage</div></div>`
document.getElementById('hotspots').innerHTML='<table><tr><th>File</th><th>Changes</th><th>Churn</th><th>Authors</th></tr>'+ (r.hotspots.top_hotspots||[]).slice(0,8).map(h=>`<tr><td>${h.file.slice(-50)}</td><td>${h.changes}</td><td>${h.total_churn}</td><td>${h.unique_authors}</td></tr>`).join('')+'</table>'
document.getElementById('authors').innerHTML='<table><tr><th>Name</th><th>Commits</th><th>Files</th><th>Churn</th></tr>'+ (r.authors.contributors||[]).slice(0,8).map(c=>`<tr><td>${c.name}</td><td>${c.commits}</td><td>${c.files_touched||0}</td><td>${c.total_churn||0}</td></tr>`).join('')+'</table>'
}
load();setInterval(load,30000)
</script></body></html>"""


class DashboardHandler(BaseHTTPRequestHandler):
    repo_path = "."

    def do_GET(self):
        if self.path == "/" or self.path == "/dashboard":
            self._html(DASHBOARD_HTML)
        elif self.path == "/api/data":
            self._json(run_analysis(self.repo_path))
        else:
            self.send_error(404)

    def _html(self, content):
        self.send_response(200); self.send_header("Content-Type", "text/html"); self.end_headers()
        self.wfile.write(content.encode())

    def _json(self, data):
        self.send_response(200); self.send_header("Content-Type", "application/json"); self.end_headers()
        self.wfile.write(json.dumps(data, default=str).encode())

    def log_message(self, format, *args): pass


def serve(repo_path: str, port: int = 5299):
    DashboardHandler.repo_path = str(Path(repo_path).resolve())
    server = HTTPServer(("0.0.0.0", port), DashboardHandler)
    print(f"🏠 CHM Dashboard → http://localhost:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n👋 Shutting down...")
