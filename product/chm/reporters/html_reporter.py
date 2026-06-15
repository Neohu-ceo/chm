"""HTML report generator — beautiful, shareable analysis reports."""

import json
from pathlib import Path
from typing import Any

TEMPLATE_DIR = Path(__file__).parent.parent / "templates"


class HTMLReporter:
    """Generates a self-contained HTML report."""

    def render_all(self, results: dict[str, Any]) -> str:
        """Return complete HTML document as string."""
        template = self._load_template()
        data_json = json.dumps(results, indent=2, ensure_ascii=False, default=str)

        # Calculate health score and color
        score = results.get("health_score", 50)
        if score >= 70:
            score_color = "#10b981"
            score_label = "健康"
        elif score >= 40:
            score_color = "#f59e0b"
            score_label = "一般"
        else:
            score_color = "#ef4444"
            score_label = "需关注"

        # Fill template
        html = template.replace("{{DATA_JSON}}", data_json)
        html = html.replace("{{REPO_NAME}}", results.get("repo_name", "Unknown"))
        html = html.replace("{{HEALTH_SCORE}}", str(score))
        html = html.replace("{{SCORE_COLOR}}", score_color)
        html = html.replace("{{SCORE_LABEL}}", score_label)
        html = html.replace("{{TOTAL_COMMITS}}", str(results.get("total_commits", 0)))
        html = html.replace("{{TOTAL_FILES}}", str(results.get("total_files", 0)))

        return html

    def _load_template(self) -> str:
        """Load the HTML template."""
        template_path = TEMPLATE_DIR / "report.html"
        if template_path.exists():
            return template_path.read_text(encoding="utf-8")
        return self._fallback_template()

    def _fallback_template(self) -> str:
        """Minimal fallback template."""
        return """<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <title>CHM Report - {{REPO_NAME}}</title>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, sans-serif; max-width: 960px; margin: 0 auto; padding: 2rem; background: #f8fafc; color: #1e293b; }
        .header { background: linear-gradient(135deg, #0f172a, #1e293b); color: white; padding: 2rem; border-radius: 12px; margin-bottom: 2rem; }
        .score { font-size: 4rem; font-weight: bold; color: {{SCORE_COLOR}}; }
        .card { background: white; border-radius: 8px; padding: 1.5rem; margin-bottom: 1.5rem; box-shadow: 0 1px 3px rgba(0,0,0,.1); }
        table { width: 100%; border-collapse: collapse; }
        th, td { padding: .5rem .75rem; text-align: left; border-bottom: 1px solid #e2e8f0; }
        th { background: #f1f5f9; font-weight: 600; }
        .bar { display: inline-block; height: .8rem; border-radius: 4px; background: #3b82f6; }
        pre { background: #1e293b; color: #e2e8f0; padding: 1rem; border-radius: 8px; overflow-x: auto; }
    </style>
</head>
<body>
    <div class="header">
        <h1>🏠 Lighthouse Analytics</h1>
        <h2>Codebase Health Report: {{REPO_NAME}}</h2>
        <div class="score">{{HEALTH_SCORE}}</div>
        <p>Health Score — {{SCORE_LABEL}}</p>
    </div>
    <div class="card">
        <h3>📊 概览</h3>
        <p>Commits: {{TOTAL_COMMITS}} | Files: {{TOTAL_FILES}}</p>
    </div>
    <pre id="raw-data"></pre>
    <script>
        const data = {{DATA_JSON}};
        document.getElementById('raw-data').textContent = JSON.stringify(data, null, 2);
    </script>
</body>
</html>"""
