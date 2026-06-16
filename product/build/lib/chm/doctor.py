"""chm doctor — Intelligent diagnosis and actionable recommendations.

Analyzes all 8 health dimensions and outputs a prioritized, specific,
actionable list of things to fix. Think of it as a "codebase doctor's prescription."
"""

from chm.git_collector import GitCollector
from chm.analyzers import (
    HotspotAnalyzer, AuthorAnalyzer, PulseAnalyzer, ComplexityAnalyzer,
    DeadCodeAnalyzer, DependencyAnalyzer, TestCoverageAnalyzer, DuplicationAnalyzer,
)
from chm.reporters import TerminalReporter


class Doctor:
    """Diagnoses a codebase and prescribes actionable fixes."""

    def __init__(self, repo_path: str):
        self.collector = GitCollector(repo_path)
        self.repo_name = self.collector.repo_name()

    def diagnose(self) -> dict:
        """Run full diagnosis and return structured recommendations."""
        # Gather all data
        hotspots = HotspotAnalyzer(self.collector).analyze()
        authors = AuthorAnalyzer(self.collector).analyze()
        pulse = PulseAnalyzer(self.collector).analyze()
        complexity = ComplexityAnalyzer(self.collector).analyze()
        dead_code = DeadCodeAnalyzer(self.collector).analyze()
        deps = DependencyAnalyzer(self.collector).analyze()
        coverage = TestCoverageAnalyzer(self.collector).analyze()
        dupes = DuplicationAnalyzer(self.collector).analyze()

        # Calculate score
        tr = TerminalReporter()
        score = tr._calculate_health_score({
            "hotspots": hotspots, "authors": authors, "pulse": pulse,
            "complexity": complexity, "dead_code": dead_code,
            "dependencies": deps, "test_coverage": coverage,
            "duplication": dupes,
        })

        # Generate recommendations
        prescriptions = []
        prescriptions.extend(self._check_bus_factor(authors))
        prescriptions.extend(self._check_hotspots(hotspots))
        prescriptions.extend(self._check_coverage(coverage, hotspots))
        prescriptions.extend(self._check_complexity(complexity))
        prescriptions.extend(self._check_dead_code(dead_code))
        prescriptions.extend(self._check_circular_deps(deps))
        prescriptions.extend(self._check_duplication(dupes))
        prescriptions.extend(self._check_pulse(pulse))

        # Sort by priority: critical > high > medium > low
        priority_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        prescriptions.sort(key=lambda p: priority_order.get(p["priority"], 99))

        return {
            "repo": self.repo_name,
            "health_score": score,
            "prescriptions": prescriptions,
            "summary": self._summarize(score, prescriptions),
        }

    def _check_bus_factor(self, authors: dict) -> list[dict]:
        """Check bus factor risk."""
        rx = []
        bf = authors.get("bus_factor", 99)
        contributors = authors.get("contributors", [])

        if bf == 1:
            top = contributors[0] if contributors else {"name": "unknown"}
            rx.append({
                "priority": "critical",
                "category": "团队风险",
                "title": "巴士因子 = 1 —— 单点故障",
                "detail": f"只有 {top['name']} 一个人贡献了 50% 以上的提交。如果TA离开，项目立即瘫痪。",
                "actions": [
                    "立即开始结对编程，让第二个人熟悉核心模块",
                    "安排知识分享会，每周一次",
                    f"核心文件：{', '.join(top.get('top_files', [])[:3])} —— 让其他人先读这些",
                ],
            })
        elif bf <= 2:
            rx.append({
                "priority": "high",
                "category": "团队风险",
                "title": f"巴士因子偏低 ({bf})",
                "detail": f"只有 {bf} 个人掌握了项目核心知识。",
                "actions": [
                    "Code review 改为至少 2 人批准",
                    "关键模块应该有 backup owner",
                ],
            })

        return rx

    def _check_hotspots(self, hotspots: dict) -> list[dict]:
        """Check code hotspots."""
        rx = []
        top = hotspots.get("top_hotspots", [])
        total = hotspots.get("total_churn", 1)
        top3_churn = sum(h.get("total_churn", 0) for h in top[:3])

        if total > 0 and top3_churn / total > 0.5:
            files = [h["file"] for h in top[:3]]
            rx.append({
                "priority": "high",
                "category": "代码热区",
                "title": f"前 3 个文件占据 {int(top3_churn / total * 100)}% 的改动",
                "detail": f"这些文件改动过于频繁，是 bug 的温床：{', '.join(files)}",
                "actions": [
                    f"优先重构 {top[0]['file']} —— 它被 {top[0].get('unique_authors', '?')} 个人改了 {top[0].get('changes', '?')} 次",
                    "考虑拆分成更小的模块",
                    "为这些文件补充单元测试",
                ],
            })

        # Individual high-churn files
        for h in top[:5]:
            if h.get("unique_authors", 0) >= 3:
                rx.append({
                    "priority": "medium",
                    "category": "代码热区",
                    "title": f"{h['file']} 被多人频繁修改",
                    "detail": f"{h['unique_authors']} 个人改了 {h['changes']} 次，churn: {h['total_churn']}",
                    "actions": [
                        "检查是否缺乏清晰的所有权",
                        "考虑是否需要重新设计接口",
                    ],
                })

        return rx

    def _check_coverage(self, coverage: dict, hotspots: dict) -> list[dict]:
        """Check test coverage."""
        rx = []
        cov_pct = coverage.get("estimated_coverage_pct", 100)
        grade = coverage.get("coverage_grade", "A")

        if grade in ("D", "F"):
            rx.append({
                "priority": "critical" if grade == "F" else "high",
                "category": "测试",
                "title": f"测试覆盖率极低 ({grade}, {cov_pct}%)",
                "detail": f"{coverage.get('uncovered_files', 0)} 个源文件没有对应测试。",
                "actions": [
                    "从高流失文件开始写测试：",
                    *[f"  ▸ {f['file']} ({f.get('churn', 0)} churn)"
                      for f in (coverage.get("high_risk_uncovered", []) or [])[:3]],
                    "每个 sprint 至少增加 5% 的覆盖率",
                ],
            })

        return rx

    def _check_complexity(self, complexity: dict) -> list[dict]:
        """Check code complexity."""
        rx = []
        risky = complexity.get("risky_files", [])

        if risky:
            rx.append({
                "priority": "medium",
                "category": "代码质量",
                "title": f"{len(risky)} 个文件复杂度高且注释少",
                "detail": "高复杂度 + 低注释率 = 难以维护的代码。",
                "actions": [
                    f"最复杂的文件：{risky[0]['file']}（复杂度 {risky[0].get('complexity_score', '?')}，注释率 {risky[0].get('comment_ratio', 0):.1%}）",
                    "为这些文件添加函数级别的文档注释",
                    "考虑拆分为更小的函数/类",
                ],
            })

        return rx

    def _check_dead_code(self, dead_code: dict) -> list[dict]:
        """Check dead code."""
        rx = []
        vstale = dead_code.get("very_stale_files", [])

        if vstale:
            rx.append({
                "priority": "low",
                "category": "维护",
                "title": f"{len(vstale)} 个文件超过一年未修改",
                "detail": "这些可能是死代码，占用认知负担和构建时间。",
                "actions": [
                    f"审查：{vstale[0]['file']}（{vstale[0].get('months_stale', '?')} 个月未修改）",
                    "确认是否仍然需要——不需要就删除（git 历史可以恢复）",
                ],
            })

        return rx

    def _check_circular_deps(self, deps: dict) -> list[dict]:
        """Check circular dependencies."""
        rx = []
        circular = deps.get("potential_circular_deps", [])

        if circular:
            rx.append({
                "priority": "high",
                "category": "架构",
                "title": f"发现 {len(circular)} 个潜在循环依赖",
                "detail": "循环依赖让测试和重构变得困难。",
                "actions": [
                    f"最严重的一对：{circular[0].get('file_a', '?')} ↔ {circular[0].get('file_b', '?')}",
                    "提取共享接口/抽象类",
                    "使用依赖注入打破循环",
                ],
            })

        return rx

    def _check_duplication(self, dupes: dict) -> list[dict]:
        """Check code duplication."""
        rx = []
        pairs = dupes.get("top_duplicate_pairs", [])

        if len(pairs) > 5:
            rx.append({
                "priority": "low",
                "category": "代码质量",
                "title": f"{len(pairs)} 对文件存在显著重复",
                "detail": "重复代码意味着修改一个地方还要改另一个。",
                "actions": [
                    f"重复最多的对：{pairs[0].get('file_a', '?').split('/')[-1]} ↔ {pairs[0].get('file_b', '?').split('/')[-1]} ({pairs[0].get('shared_lines', '?')} 行)",
                    "提取公共函数/模块",
                ],
            })

        return rx

    def _check_pulse(self, pulse: dict) -> list[dict]:
        """Check team pulse."""
        rx = []
        if pulse.get("error"):
            return rx

        gap = pulse.get("streaks", {}).get("longest_gap_days", 0)
        if gap > 14:
            rx.append({
                "priority": "medium",
                "category": "团队",
                "title": f"最长开发空白期: {gap} 天",
                "detail": "超过两周没有提交可能意味着项目停滞或团队流失。",
                "actions": [
                    "确认项目是否仍在活跃开发",
                    "如果项目已完成，更新 README 标记状态",
                ],
            })

        return rx

    def _summarize(self, score: int, prescriptions: list[dict]) -> str:
        """Generate a human-readable summary."""
        if score >= 80:
            header = f"🟢 代码库整体健康 ({score}/100)。"
        elif score >= 50:
            header = f"🟡 代码库有改进空间 ({score}/100)。"
        else:
            header = f"🔴 代码库需要立即关注 ({score}/100)。"

        critical = [p for p in prescriptions if p["priority"] == "critical"]
        high = [p for p in prescriptions if p["priority"] == "high"]
        medium = [p for p in prescriptions if p["priority"] == "medium"]

        parts = [header]
        if critical:
            parts.append(f"🚨 {len(critical)} 个严重问题必须立即处理。")
        if high:
            parts.append(f"⚠️ {len(high)} 个高优先级问题。")
        if medium:
            parts.append(f"📝 {len(medium)} 个改进建议。")
        if not critical and not high and not medium:
            parts.append("没有发现重大问题。继续保持！")

        return " ".join(parts)
