"""Test coverage estimation — checks if source files have corresponding tests."""

import re
from pathlib import Path
from collections import defaultdict
from chm.git_collector import GitCollector


class TestCoverageAnalyzer:
    """Estimates test coverage by matching source files to test files.

    Uses naming conventions (not actual coverage data):
    - src/foo.py → tests/test_foo.py
    - lib/bar.js → test/bar.test.js, __tests__/bar.js
    """

    TEST_PATTERNS = {
        # Python
        "test_*.py": ".py",
        "*_test.py": ".py",
        # JavaScript/TypeScript
        "*.test.js": ".js",
        "*.spec.js": ".js",
        "*.test.ts": ".ts",
        "*.spec.ts": ".ts",
        # Go
        "*_test.go": ".go",
        # Rust
        "*_test.rs": ".rs",
        # Java
        "*Test.java": ".java",
    }

    # Common test directory names
    TEST_DIRS = {"tests", "test", "__tests__", "spec", "specs", "testing"}

    def __init__(self, collector: GitCollector):
        self.collector = collector

    def analyze(self) -> dict:
        """Estimate test coverage across the codebase."""
        repo_path = self.collector.repo_path
        all_files = self.collector.get_file_list()

        # Separate source and test files
        source_files = []
        test_files = []
        test_dir_files = set()

        for f in all_files:
            parts = Path(f).parts
            is_test_dir = any(d in self.TEST_DIRS for d in parts)
            if is_test_dir:
                test_files.append(f)
                test_dir_files.add(f)
            else:
                fname = Path(f).name
                is_test_file = any(
                    Path(f).match(pattern)
                    for pattern in self.TEST_PATTERNS
                )
                if is_test_file:
                    test_files.append(f)
                else:
                    source_files.append(f)

        # Try to match source files to test files
        covered = []
        uncovered = []
        test_file_set = set(test_files)

        for sf in source_files:
            sf_path = Path(sf)
            sf_stem = sf_path.stem
            sf_name = sf_path.name
            sf_ext = sf_path.suffix

            # Generate possible test file names
            candidates = [
                f"test_{sf_name}",
                f"{sf_stem}_test{sf_ext}",
                f"{sf_stem}.test{sf_ext}",
                f"{sf_stem}.spec{sf_ext}",
                f"{sf_stem}Test{sf_ext}",
                f"{sf_stem}_test{sf_ext if sf_ext != '.go' else '.go'}",
            ]

            # Also check in test directories
            found = False
            for candidate in candidates:
                for test_dir in self.TEST_DIRS:
                    candidate_path = f"{test_dir}/{candidate}"
                    if candidate_path in test_file_set:
                        found = True
                        break
                if not found:
                    if candidate in test_file_set:
                        found = True
                if found:
                    break

            if found:
                covered.append(sf)
            else:
                uncovered.append(sf)

        total_source = len(source_files)
        coverage_pct = round(len(covered) / max(total_source, 1) * 100, 1)

        # Identify high-risk uncovered files (top hotspots without tests)
        changes = self.collector.get_file_changes()
        file_churn = defaultdict(int)
        for c in changes:
            file_churn[c["file"]] += c["churn"]

        high_risk_uncovered = [
            {"file": f, "churn": file_churn.get(f, 0)}
            for f in uncovered
        ]
        high_risk_uncovered.sort(key=lambda x: x["churn"], reverse=True)

        return {
            "total_source_files": total_source,
            "total_test_files": len(test_files),
            "covered_files": len(covered),
            "uncovered_files": len(uncovered),
            "estimated_coverage_pct": coverage_pct,
            "coverage_grade": (
                "A" if coverage_pct >= 80
                else "B" if coverage_pct >= 60
                else "C" if coverage_pct >= 40
                else "D" if coverage_pct >= 20
                else "F"
            ),
            "high_risk_uncovered": high_risk_uncovered[:10],
            "uncovered_hotspots_warning": (
                f"🚨 {len([f for f in high_risk_uncovered if f['churn'] > 50])} "
                f"high-churn files have no tests!"
                if any(f["churn"] > 50 for f in high_risk_uncovered)
                else None
            ),
        }
