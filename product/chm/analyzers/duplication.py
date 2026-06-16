"""Code duplication detection — heuristic-based copy-paste detection."""

import hashlib
from pathlib import Path
from collections import defaultdict
from chm.git_collector import GitCollector


class DuplicationAnalyzer:
    """Detects potential code duplication using line-level hashing.

    Not as accurate as AST-based tools (e.g., jscpd, copy-paste-detector),
    but fast and language-agnostic. Good for spotting obvious copy-paste.
    """

    # Minimum line length to consider (ignore short/empty lines)
    MIN_LINE_LENGTH = 10

    # Extensions to analyze
    CODE_EXTENSIONS = {
        ".py", ".js", ".ts", ".jsx", ".tsx", ".go", ".rs",
        ".java", ".c", ".cpp", ".h", ".hpp", ".rb", ".php",
        ".swift", ".kt", ".scala", ".cs",
    }

    def __init__(self, collector: GitCollector):
        self.collector = collector

    def analyze(self, min_duplicate_lines: int = 6) -> dict:
        """Find duplicate code blocks across the codebase."""
        repo_path = self.collector.repo_path
        files = self.collector.get_file_list()

        # Hash every significant line across all files
        # line_hash -> [(file, line_number)]
        line_locations = defaultdict(list)

        for filepath in files:
            ext = Path(filepath).suffix.lower()
            if ext not in self.CODE_EXTENSIONS:
                continue

            try:
                content = (repo_path / filepath).read_text(errors="ignore")
            except OSError:
                continue

            for lineno, line in enumerate(content.split("\n"), 1):
                stripped = line.strip()
                if len(stripped) < self.MIN_LINE_LENGTH:
                    continue
                # Skip comment-only lines
                if stripped.startswith("#") or stripped.startswith("//") or stripped.startswith("*"):
                    continue
                # Skip imports
                if stripped.startswith("import ") or stripped.startswith("from "):
                    continue

                line_hash = hashlib.md5(stripped.encode()).hexdigest()[:12]
                line_locations[line_hash].append((filepath, lineno, stripped[:80]))

        # Find lines that appear in multiple files (potential duplication)
        duplicates = []
        for line_hash, locations in line_locations.items():
            unique_files = set(loc[0] for loc in locations)
            if len(unique_files) >= 2 and len(locations) >= min_duplicate_lines:
                duplicates.append({
                    "line_hash": line_hash,
                    "sample": locations[0][2],
                    "occurrences": len(locations),
                    "files": sorted(unique_files),
                    "file_count": len(unique_files),
                })

        # Group by file pairs to find duplicate blocks
        file_pair_duplicates = defaultdict(int)
        for dup in duplicates:
            files = sorted(dup["files"])
            for i in range(len(files)):
                for j in range(i + 1, len(files)):
                    pair = (files[i], files[j])
                    file_pair_duplicates[pair] += 1

        # Filter to significant duplication (>= min_duplicate_lines shared lines)
        significant_dupes = [
            {"file_a": pair[0], "file_b": pair[1], "shared_lines": count}
            for pair, count in file_pair_duplicates.items()
            if count >= min_duplicate_lines
        ]
        significant_dupes.sort(key=lambda x: x["shared_lines"], reverse=True)

        # Overall stats
        total_duplicate_lines = sum(d["occurrences"] for d in duplicates)

        return {
            "duplicate_line_instances": len(duplicates),
            "file_pairs_with_duplication": len(significant_dupes),
            "total_duplicate_lines": total_duplicate_lines,
            "top_duplicate_pairs": significant_dupes[:15],
            "duplication_summary": (
                f"Found {len(significant_dupes)} file pairs with significant duplication "
                f"({total_duplicate_lines} duplicate line instances)"
                if significant_dupes
                else "No significant duplication detected"
            ),
        }
