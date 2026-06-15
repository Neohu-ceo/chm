"""Terminal reporter — colorful CLI output for analysis results."""

import shutil
from typing import Any


class TerminalReporter:
    """Renders analysis results to the terminal."""

    def __init__(self):
        self.width = shutil.get_terminal_size().columns
        self.colors = {
            "green": "\033[92m",
            "yellow": "\033[93m",
            "red": "\033[91m",
            "blue": "\033[94m",
            "cyan": "\033[96m",
            "bold": "\033[1m",
            "reset": "\033[0m",
        }

    def _c(self, text: str, color: str) -> str:
        """Apply color if terminal supports it."""
        return f"{self.colors.get(color, '')}{text}{self.colors['reset']}"

    def _bar(self, value: float, max_val: float, width: int = 30) -> str:
        """Draw a proportional bar."""
        if max_val == 0:
            return "░" * width
        filled = min(int((value / max_val) * width), width)
        return "█" * filled + "░" * (width - filled)

    def _header(self, title: str):
        """Print a section header."""
        print(f"\n{self._c('━' * self.width, 'blue')}")
        print(f"  {self._c(title, 'bold')}")
        print(f"{self._c('━' * self.width, 'blue')}")

    def render_all(self, results: dict[str, Any]):
        """Render all analysis results."""
        repo = results.get("repo_name", "unknown")
        print(f"\n{self._c(f'  🏠  Lighthouse Analytics — Codebase Health Monitor', 'bold')}")
        print(f"  Repository: {self._c(repo, 'cyan')}")
        print(f"  Total commits analyzed: {results.get('total_commits', 0)}")
        print(f"  Total files: {results.get('total_files', 0)}")

        self.render_hotspots(results.get("hotspots", {}))
        self.render_authors(results.get("authors", {}))
        self.render_pulse(results.get("pulse", {}))
        self.render_complexity(results.get("complexity", {}))

        # Overall health score
        score = self._calculate_health_score(results)
        print(f"\n{self._c('━' * self.width, 'blue')}")
        print(f"  {self._c('🧬 整体健康度评分', 'bold')}")
        score_bar = self._bar(score, 100, 50)
        score_color = "green" if score >= 70 else "yellow" if score >= 40 else "red"
        print(f"  {self._c(f'{score}/100', score_color)} {score_bar}")
        print(f"{self._c('━' * self.width, 'blue')}\n")

    def render_hotspots(self, data: dict):
        """Render hotspot analysis."""
        self._header("🔥 代码热区分析 (Code Hotspots)")
        if not data.get("top_hotspots"):
            print("  No data available")
            return

        print(f"  总改动文件: {data['total_files_changed']}  总改动行数: {data['total_churn']:,}")
        print(f"  平均每文件改动: {data['average_changes_per_file']:.1f} 次\n")

        max_churn = max((h["total_churn"] for h in data["top_hotspots"][:10]), default=1)
        print(f"  {'文件':<50} {'改动':>6} {'+行':>6} {'-行':>6} {'作者数':>5}")
        print(f"  {'─' * 50} {'─' * 6} {'─' * 6} {'─' * 6} {'─' * 5}")
        for h in data["top_hotspots"][:15]:
            bar = self._bar(h["total_churn"], max_churn, 15)
            file_display = h["file"][:47] + "..." if len(h["file"]) > 50 else h["file"]
            print(
                f"  {file_display:<50} {h['changes']:>6} "
                f"{self._c(f'+{h['additions']}', 'green'):>16} "
                f"{self._c(f'-{h['deletions']}', 'red'):>16} "
                f"{h['unique_authors']:>5}  {bar}"
            )

    def render_authors(self, data: dict):
        """Render author contribution analysis."""
        self._header("👥 贡献者分析 (Contributor Analysis)")
        if not data.get("contributors"):
            print("  No data available")
            return

        print(f"  总贡献者: {data['total_contributors']}  总提交: {data['total_commits']}")
        print(f"  {self._c(f'巴士因子: {data["bus_factor"]}', 'yellow' if data["bus_factor"] <= 2 else 'green')}")
        print(f"    (至少 {data['bus_factor']} 人贡献了 50% 的提交)\n")

        print(f"  {'贡献者':<25} {'提交':>6} {'改动行数':>8} {'文件':>5} {'顶级文件':<30}")
        print(f"  {'─' * 25} {'─' * 6} {'─' * 8} {'─' * 5} {'─' * 30}")
        for c in data["contributors"][:10]:
            name = c["name"][:22] + "..." if len(c["name"]) > 25 else c["name"]
            top_file = (c.get("top_files") or ["-"])[0]
            top_file = top_file[:27] + "..." if len(top_file) > 30 else top_file
            print(
                f"  {name:<25} {c['commits']:>6} {c['total_churn']:>8,} "
                f"{c['files_touched']:>5} {top_file:<30}"
            )

    def render_pulse(self, data: dict):
        """Render team pulse analysis."""
        self._header("💓 团队脉动 (Team Pulse)")
        if data.get("error"):
            print(f"  {data['error']}")
            return

        dr = data.get("date_range", {})
        print(f"  分析周期: {dr.get('start', '?')} → {dr.get('end', '?')} ({dr.get('days', '?')} 天)")
        print(f"  平均每日提交: {data['avg_commits_per_day']}")
        print(f"  最活跃时段: {data['peak_hour']}:00 ({data['peak_hour_commits']} 次提交)")
        print(f"  最活跃日: {data['peak_day']}")

        streaks = data.get("streaks", {})
        print(f"  最长连续提交: {streaks.get('longest_streak_days', 0)} 天")
        print(f"  最长空白期: {streaks.get('longest_gap_days', 0)} 天")
        print(f"  总活跃天数: {streaks.get('total_active_days', 0)}")

        # Hour distribution sparkline
        print(f"\n  {self._c('24小时分布:', 'cyan')}")
        hour_data = data.get("hour_distribution", {})
        max_h = max(hour_data.values()) if hour_data else 1
        for row in range(6, 0, -1):
            line = "  "
            for h in range(24):
                val = hour_data.get(str(h), 0)
                level = int((val / max(max_h, 1)) * 6)
                line += [" ", "▁", "▂", "▃", "▄", "▅", "▆", "█"][level]
            print(line)
        print("  " + "".join(f"{h:02d}"[0] for h in range(24)))

    def render_complexity(self, data: dict):
        """Render complexity analysis."""
        self._header("🧩 复杂度分析 (Complexity Analysis)")
        if not data.get("top_complex"):
            print("  No data available")
            return

        print(f"  分析文件: {data['files_analyzed']}  总行数: {data['total_lines']:,}")
        print(f"  平均复杂度: {data['avg_complexity']}  高风险文件: {len(data.get('risky_files', []))}")

        if data.get("risky_files"):
            print(f"\n  {self._c('⚠️  高风险文件 (高复杂度 + 低注释率):', 'yellow')}")
            for f in data["risky_files"][:8]:
                print(
                    f"    {self._c('⚠', 'yellow')} {f['file'][:60]} "
                    f"[复杂度:{f['complexity_score']} 注释率:{f['comment_ratio']}]"
                )

    def _calculate_health_score(self, results: dict) -> int:
        """Calculate overall health score (0-100)."""
        score = 50  # baseline
        reasons = []

        # Hotspot penalty: too many changes concentrated in few files
        hotspots = results.get("hotspots", {})
        if hotspots:
            top = hotspots.get("top_hotspots", [])
            if top:
                top3_churn = sum(h["total_churn"] for h in top[:3])
                total_churn = hotspots.get("total_churn", 1)
                concentration = top3_churn / max(total_churn, 1)
                if concentration > 0.5:
                    score -= 15
                    reasons.append("代码改动高度集中")
                elif concentration > 0.3:
                    score -= 5

        # Author: bus factor
        authors = results.get("authors", {})
        if authors:
            bf = authors.get("bus_factor", 1)
            if bf == 1:
                score -= 20
                reasons.append("巴士因子=1，关键人物风险")
            elif bf <= 2:
                score -= 10
                reasons.append("巴士因子偏低")

        # Pulse: consistency bonus
        pulse = results.get("pulse", {})
        if pulse and pulse.get("avg_commits_per_day", 0) >= 1:
            score += 10
            reasons.append("持续活跃开发")
        elif pulse and pulse.get("avg_commits_per_day", 0) >= 0.3:
            score += 5

        # Complexity: risk penalty
        complexity = results.get("complexity", {})
        if complexity:
            risky_count = len(complexity.get("risky_files", []))
            if risky_count > 10:
                score -= 10
                reasons.append("高风险文件过多")
            elif risky_count > 3:
                score -= 5

            avg_complexity = complexity.get("avg_complexity", 0)
            if avg_complexity > 20:
                score -= 10
                reasons.append("整体复杂度过高")

        # Clamp
        return max(0, min(100, score))
