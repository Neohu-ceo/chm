"""Code complexity estimation without full AST parsing."""

import os
from pathlib import Path
from chm.git_collector import GitCollector


class ComplexityAnalyzer:
    """Estimates code complexity from file structure and size."""

    COMPLEXITY_EXTENSIONS = {
        ".py", ".js", ".ts", ".jsx", ".tsx", ".go", ".rs",
        ".java", ".c", ".cpp", ".h", ".hpp", ".rb", ".php",
        ".swift", ".kt", ".scala", ".cs", ".css", ".scss",
    }

    def __init__(self, collector: GitCollector):
        self.collector = collector

    def analyze(self) -> dict:
        """Return complexity analysis."""
        files = self.collector.get_file_list()
        repo_path = self.collector.repo_path

        # Directories to skip
        skip_prefixes = {".git/", ".chm/", "node_modules/", "__pycache__/", ".venv/"}

        file_complexities = []
        total_lines = 0
        total_files_analyzed = 0

        for filepath in files:
            # Skip generated/third-party directories
            if any(filepath.startswith(p) for p in skip_prefixes):
                continue

            ext = Path(filepath).suffix.lower()
            if ext not in self.COMPLEXITY_EXTENSIONS:
                continue

            full_path = repo_path / filepath
            try:
                with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
            except (OSError, PermissionError):
                continue

            lines = content.split("\n")
            line_count = len(lines)
            total_lines += line_count
            total_files_analyzed += 1

            # Simple complexity heuristics
            comment_lines = sum(
                1 for l in lines
                if l.strip().startswith("//")
                or l.strip().startswith("#")
                or l.strip().startswith("/*")
                or l.strip().startswith("*")
                or l.strip().startswith("'''")
                or l.strip().startswith('"""')
            )
            blank_lines = sum(1 for l in lines if not l.strip())
            code_lines = line_count - comment_lines - blank_lines

            # Estimate complexity by counting branches
            branch_keywords = [
                "if ", "elif ", "else:", "for ", "while ",
                "switch", "case ", "catch", "&&", "||",
                "match ", "when ",
            ]
            branch_count = sum(
                content.count(kw) for kw in branch_keywords
            )

            file_complexities.append({
                "file": filepath,
                "lines": line_count,
                "code_lines": code_lines,
                "comment_lines": comment_lines,
                "blank_lines": blank_lines,
                "comment_ratio": round(
                    comment_lines / max(line_count, 1), 3
                ),
                "estimated_branches": branch_count,
                "complexity_score": round(
                    (branch_count / max(code_lines, 1)) * 100, 1
                ),
            })

        # Sort by complexity score
        file_complexities.sort(
            key=lambda x: x["complexity_score"], reverse=True
        )

        # Identify risky files (high complexity, low comments)
        risky = [
            f for f in file_complexities
            if f["complexity_score"] > 15 and f["comment_ratio"] < 0.1
        ]

        return {
            "files_analyzed": total_files_analyzed,
            "total_lines": total_lines,
            "total_code_lines": sum(f["code_lines"] for f in file_complexities),
            "avg_complexity": round(
                sum(f["complexity_score"] for f in file_complexities)
                / max(total_files_analyzed, 1), 1
            ),
            "top_complex": file_complexities[:20],
            "risky_files": risky[:10],
            "file_count": total_files_analyzed,
        }
