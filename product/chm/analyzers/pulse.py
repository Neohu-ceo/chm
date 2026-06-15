"""Team pulse — commit rhythm and activity patterns."""

from collections import defaultdict, Counter
from datetime import datetime
from chm.git_collector import GitCollector


class PulseAnalyzer:
    """Analyzes team commit rhythm and activity patterns."""

    def __init__(self, collector: GitCollector):
        self.collector = collector

    def analyze(self) -> dict:
        """Return pulse analysis results."""
        commits = self.collector.get_commits()

        if not commits:
            return {"error": "No commits found"}

        # Parse dates and analyze patterns
        hours = Counter()
        days_of_week = Counter()
        months = Counter()
        dates = []

        day_names = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]

        for c in commits:
            try:
                # Try ISO format
                date_str = c["date"]
                if "T" in date_str:
                    dt = datetime.fromisoformat(date_str[:19])
                else:
                    # Try other formats
                    for fmt in [
                        "%Y-%m-%d %H:%M:%S %z",
                        "%Y-%m-%d %H:%M:%S",
                    ]:
                        try:
                            dt = datetime.strptime(date_str, fmt)
                            break
                        except ValueError:
                            continue
                    else:
                        continue

                hours[dt.hour] += 1
                days_of_week[dt.weekday()] += 1
                months[dt.strftime("%Y-%m")] += 1
                dates.append(dt)
            except (ValueError, KeyError):
                continue

        if not dates:
            return {"error": "Could not parse commit dates"}

        dates.sort()
        date_range_days = (dates[-1] - dates[0]).days or 1
        avg_commits_per_day = len(dates) / date_range_days

        # Most active hour
        peak_hour = hours.most_common(1)[0] if hours else (0, 0)
        peak_day_idx = days_of_week.most_common(1)[0][0] if days_of_week else 0

        # Commit streak
        streaks = self._find_streaks(dates)

        return {
            "date_range": {
                "start": dates[0].strftime("%Y-%m-%d"),
                "end": dates[-1].strftime("%Y-%m-%d"),
                "days": date_range_days,
            },
            "avg_commits_per_day": round(avg_commits_per_day, 2),
            "peak_hour": peak_hour[0],
            "peak_hour_commits": peak_hour[1],
            "peak_day": day_names[peak_day_idx],
            "peak_day_commits": days_of_week[peak_day_idx],
            "day_distribution": {
                day_names[i]: days_of_week.get(i, 0) for i in range(7)
            },
            "hour_distribution": {
                str(h): hours.get(h, 0) for h in range(24)
            },
            "monthly_trend": {
                m: months[m] for m in sorted(months.keys())[-12:]
            },
            "streaks": streaks,
        }

    def _find_streaks(self, dates: list) -> dict:
        """Find longest commit and gap streaks."""
        if not dates:
            return {}

        date_set = {d.date() for d in dates}
        sorted_dates = sorted(date_set)

        # Longest streak of consecutive days with commits
        longest_streak = 0
        current_streak = 1
        for i in range(1, len(sorted_dates)):
            if (sorted_dates[i] - sorted_dates[i - 1]).days == 1:
                current_streak += 1
            else:
                longest_streak = max(longest_streak, current_streak)
                current_streak = 1
        longest_streak = max(longest_streak, current_streak)

        # Longest gap without commits
        longest_gap = 0
        for i in range(1, len(sorted_dates)):
            gap = (sorted_dates[i] - sorted_dates[i - 1]).days
            longest_gap = max(longest_gap, gap)

        return {
            "longest_streak_days": longest_streak,
            "longest_gap_days": longest_gap,
            "total_active_days": len(date_set),
        }
