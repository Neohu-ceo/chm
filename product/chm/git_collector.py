"""Git data collector — gathers raw data from git repositories."""

import subprocess
import os
from collections import defaultdict
from datetime import datetime
from pathlib import Path


class GitCollector:
    """Collects raw data from a git repository."""

    def __init__(self, repo_path: str = "."):
        self.repo_path = Path(repo_path).resolve()
        if not (self.repo_path / ".git").exists():
            raise ValueError(f"Not a git repository: {self.repo_path}")

    def _run(self, *args: str) -> str:
        """Run a git command and return stripped stdout. Raises on error."""
        try:
            result = subprocess.run(
                ["git", "-C", str(self.repo_path), *args],
                capture_output=True,
                text=True,
                timeout=60,
            )
            result.check_returncode()
            return result.stdout.strip()
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"Git command failed: {' '.join(args)}\n{e.stderr}")

    def _run_safe(self, *args: str) -> str:
        """Run a git command, returning empty string on failure (e.g. empty repo)."""
        try:
            return self._run(*args)
        except RuntimeError:
            return ""

    def get_commits(self, max_count: int = 500) -> list[dict]:
        """Get commit log as a list of dicts."""
        output = self._run_safe(
            "log",
            f"-{max_count}",
            "--pretty=format:%H|%an|%ae|%ad|%s",
            "--date=iso",
        )

        commits = []
        for line in output.split("\n"):
            if not line.strip():
                continue
            parts = line.split("|", 4)
            if len(parts) < 5:
                continue
            commits.append({
                "hash": parts[0][:8],
                "author": parts[1],
                "email": parts[2],
                "date": parts[3],
                "message": parts[4],
            })
        return commits

    def get_file_changes(self, max_count: int = 500) -> list[dict]:
        """Get file change statistics per commit."""
        output = self._run_safe(
            "log",
            f"-{max_count}",
            "--pretty=format:COMMIT:%H|%an|%ad",
            "--date=iso",
            "--numstat",
        )

        changes = []
        current_commit = None

        for line in output.split("\n"):
            if not line.strip():
                continue

            if line.startswith("COMMIT:"):
                parts = line[7:].split("|")
                if len(parts) >= 2:
                    current_commit = {
                        "hash": parts[0][:8],
                        "author": parts[1],
                        "date": parts[2] if len(parts) > 2 else "",
                    }
            elif current_commit and "\t" in line:
                parts = line.split("\t")
                if len(parts) == 3:
                    adds = int(parts[0]) if parts[0] != "-" else 0
                    dels = int(parts[1]) if parts[1] != "-" else 0
                    changes.append({
                        **current_commit,
                        "file": parts[2],
                        "additions": adds,
                        "deletions": dels,
                        "churn": adds + dels,
                    })

        return changes

    def get_file_list(self) -> list[str]:
        """Get list of all tracked files."""
        output = self._run("ls-files")
        return [f for f in output.split("\n") if f.strip()]

    def get_contributor_stats(self, max_count: int = 500) -> list[dict]:
        """Get per-author commit statistics."""
        output = self._run(
            "shortlog", "-sne", f"-{max_count}", "--all"
        )
        stats = []
        for line in output.split("\n"):
            line = line.strip()
            if not line:
                continue
            # Format: "  123 Author Name <email>"
            parts = line.split(None, 1)
            if len(parts) >= 2:
                count = int(parts[0])
                name_email = parts[1]
                # Extract name and email
                if "<" in name_email:
                    name, email = name_email.rsplit("<", 1)
                    email = email.rstrip(">")
                else:
                    name = name_email
                    email = ""
                stats.append({
                    "name": name.strip(),
                    "email": email.strip(),
                    "commits": count,
                })
        return stats

    def get_commit_times(self, max_count: int = 500) -> list[datetime]:
        """Get commit timestamps for pulse analysis."""
        output = self._run_safe(
            "log",
            f"-{max_count}",
            "--pretty=format:%ad",
            "--date=iso-strict",
        )
        times = []
        for line in output.split("\n"):
            line = line.strip()
            if not line:
                continue
            try:
                # Handle ISO 8601 variants: strip timezone suffix
                clean = line.rstrip("Z")
                if "+" in clean:
                    clean = clean.rsplit("+", 1)[0]
                elif clean.count("-") > 2 and "T" in clean:
                    # Has timezone offset like -05:00 — remove it
                    parts = clean.rsplit("-", 1)
                    if ":" in parts[-1] and len(parts[-1]) <= 6:
                        clean = parts[0]
                dt = datetime.fromisoformat(clean)
                times.append(dt)
            except (ValueError, IndexError):
                continue
        return times

    def repo_name(self) -> str:
        """Get the repository name."""
        return self.repo_path.name

    def total_files(self) -> int:
        """Get total number of tracked files."""
        return len(self.get_file_list())

    def total_commits(self) -> int:
        """Get total commit count."""
        try:
            output = self._run("rev-list", "--count", "HEAD")
            return int(output.strip())
        except RuntimeError:
            return 0
