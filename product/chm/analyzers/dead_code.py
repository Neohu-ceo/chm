"""Dead code detection — finds files that haven't been modified recently."""

from datetime import datetime, timedelta
from chm.git_collector import GitCollector


class DeadCodeAnalyzer:
    """Identifies potentially dead/abandoned files.

    A file is considered "stale" if it hasn't been modified in a long time
    relative to the repository's activity level.
    """

    def __init__(self, collector: GitCollector):
        self.collector = collector

    def analyze(self, stale_months: int = 6) -> dict:
        """Find files that haven't been touched recently."""
        # Get all file changes with dates
        changes = self.collector.get_file_changes()

        # Build last-modified map
        last_modified = {}
        for c in changes:
            try:
                date_str = c["date"]
                if "T" in date_str:
                    dt = datetime.fromisoformat(date_str[:19])
                elif " " in date_str:
                    dt = datetime.strptime(date_str[:19], "%Y-%m-%d %H:%M:%S")
                else:
                    continue
                fname = c["file"]
                if fname not in last_modified or dt > last_modified[fname]:
                    last_modified[fname] = dt
            except (ValueError, KeyError):
                continue

        # Also check all tracked files that have NEVER been in recent changes
        all_files = set(self.collector.get_file_list())
        changed_files = set(last_modified.keys())
        never_touched = all_files - changed_files

        # Classify staleness
        now = datetime.now()
        cutoff = now - timedelta(days=stale_months * 30)

        stale_files = []
        very_stale_files = []
        very_stale_cutoff = now - timedelta(days=stale_months * 2 * 30)

        for fname, last_dt in last_modified.items():
            if last_dt < very_stale_cutoff:
                very_stale_files.append({
                    "file": fname,
                    "last_modified": last_dt.strftime("%Y-%m-%d"),
                    "months_stale": round((now - last_dt).days / 30, 1),
                })
            elif last_dt < cutoff:
                stale_files.append({
                    "file": fname,
                    "last_modified": last_dt.strftime("%Y-%m-%d"),
                    "months_stale": round((now - last_dt).days / 30, 1),
                })

        # Sort by staleness
        very_stale_files.sort(key=lambda x: x["months_stale"], reverse=True)
        stale_files.sort(key=lambda x: x["months_stale"], reverse=True)

        return {
            "stale_files": stale_files,
            "very_stale_files": very_stale_files,
            "never_touched_in_history": sorted(never_touched),
            "total_stale": len(stale_files) + len(very_stale_files),
            "total_never_touched": len(never_touched),
            "staleness_ratio": round(
                (len(stale_files) + len(very_stale_files) + len(never_touched))
                / max(len(all_files), 1), 3
            ),
        }
