"""Dependency health — import analysis and coupling detection."""

import re
from pathlib import Path
from collections import defaultdict
from chm.git_collector import GitCollector


class DependencyAnalyzer:
    """Analyzes import patterns and coupling between files.

    Detects:
    - Circular dependency chains
    - Highly-coupled modules (imported by many files)
    - Files with too many dependencies
    """

    IMPORT_PATTERNS = {
        ".py": [r"^(?:from\s+(\S+)\s+import|import\s+(\S+))"],
        ".js": [r"(?:import\s+.*?\s+from\s+['\"]([^'\"]+)['\"]|require\(['\"]([^'\"]+)['\"]\))"],
        ".ts": [r"(?:import\s+.*?\s+from\s+['\"]([^'\"]+)['\"]|require\(['\"]([^'\"]+)['\"]\))"],
        ".go": [r"import\s+\(\s*(.*?)\s*\)", r"import\s+['\"]([^'\"]+)['\"]"],
        ".rs": [r"use\s+(\S+)"],
        ".java": [r"import\s+(\S+)"],
    }

    def __init__(self, collector: GitCollector):
        self.collector = collector

    def analyze(self) -> dict:
        """Analyze dependencies within the codebase."""
        repo_path = self.collector.repo_path
        files = self.collector.get_file_list()

        # Build import graph
        imports_by_file = {}  # file -> [imported_modules]
        imported_by = defaultdict(set)  # module -> [files that import it]

        for filepath in files:
            ext = Path(filepath).suffix
            patterns = self.IMPORT_PATTERNS.get(ext)
            if not patterns:
                continue

            try:
                content = (repo_path / filepath).read_text(errors="ignore")
            except OSError:
                continue

            deps = set()
            for pattern in patterns:
                for match in re.finditer(pattern, content, re.MULTILINE | re.DOTALL):
                    # Extract module name from match groups
                    for group in match.groups():
                        if group:
                            # Normalize: strip quotes, take first segment
                            dep = group.strip().strip("'\"")
                            # For "from X import Y", X is the module
                            deps.add(dep.split(".")[0])
                            break

            if deps:
                imports_by_file[filepath] = sorted(deps)
                for dep in deps:
                    imported_by[dep].add(filepath)

        # Find most-coupled modules
        coupling = [
            {
                "module": mod,
                "imported_by_count": len(files),
                "imported_by_files": sorted(files)[:10],
            }
            for mod, files in imported_by.items()
        ]
        coupling.sort(key=lambda x: x["imported_by_count"], reverse=True)

        # Files with most dependencies
        dep_counts = [
            {"file": f, "dependency_count": len(deps)}
            for f, deps in imports_by_file.items()
        ]
        dep_counts.sort(key=lambda x: x["dependency_count"], reverse=True)

        # Detect potential circular deps (simple check: mutual imports)
        circular = []
        checked = set()
        for f1 in imports_by_file:
            for f2_name in imports_by_file[f1]:
                # Check if f2 imports back from f1's namespace
                f1_module = Path(f1).stem
                if f2_name in imports_by_file:
                    f2_imports = set(imports_by_file.get(f2_name, []))
                    if f1_module in f2_imports:
                        pair = tuple(sorted([f1, f2_name]))
                        if pair not in checked:
                            checked.add(pair)
                            circular.append({"file_a": pair[0], "file_b": pair[1]})

        return {
            "total_import_relations": sum(len(v) for v in imports_by_file.values()),
            "files_with_imports": len(imports_by_file),
            "top_coupled_modules": coupling[:15],
            "top_dependency_heavy": dep_counts[:15],
            "potential_circular_deps": circular[:10],
            "circular_dep_warning": (
                f"Found {len(circular)} potential circular dependencies"
                if circular else "No circular dependencies detected"
            ),
        }
