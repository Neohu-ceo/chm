# CHM API Reference

> 供 Python 开发者直接调用分析引擎

## Python API

```python
from chm.git_collector import GitCollector
from chm.analyzers import HotspotAnalyzer, AuthorAnalyzer, PulseAnalyzer, ComplexityAnalyzer

# 1. 收集数据
collector = GitCollector("/path/to/repo")

# 2. 运行分析
hotspots = HotspotAnalyzer(collector).analyze()
authors = AuthorAnalyzer(collector).analyze()
pulse = PulseAnalyzer(collector).analyze()
complexity = ComplexityAnalyzer(collector).analyze()

# 3. 使用结果
print(f"Top hotspot: {hotspots['top_hotspots'][0]['file']}")
print(f"Bus factor: {authors['bus_factor']}")
```

## 数据结构

### HotspotAnalysis

```json
{
  "top_hotspots": [
    {
      "file": "src/api/server.py",
      "changes": 4,
      "additions": 92,
      "deletions": 29,
      "total_churn": 121,
      "unique_authors": 2,
      "authors": ["Alice", "Bob"]
    }
  ],
  "total_files_changed": 10,
  "total_churn": 288
}
```

### AuthorAnalysis

```json
{
  "contributors": [
    {
      "name": "Alice",
      "email": "alice@example.com",
      "commits": 6,
      "files_touched": 5,
      "total_churn": 212
    }
  ],
  "total_contributors": 2,
  "bus_factor": 1
}
```

### PulseAnalysis

```json
{
  "date_range": {
    "start": "2026-01-15",
    "end": "2026-02-01",
    "days": 16
  },
  "avg_commits_per_day": 0.69,
  "peak_hour": 9,
  "peak_day": "周日",
  "streaks": {
    "longest_streak_days": 4,
    "longest_gap_days": 4,
    "total_active_days": 11
  }
}
```

### ComplexityAnalysis

```json
{
  "files_analyzed": 7,
  "total_lines": 180,
  "avg_complexity": 4.7,
  "risky_files": [
    {
      "file": "src/api/server.py",
      "lines": 66,
      "code_lines": 62,
      "comment_lines": 1,
      "comment_ratio": 0.016,
      "complexity_score": 15.1
    }
  ]
}
```

## JSON 输出

```bash
chm analyze . --report json --output analysis.json
```

## CI/CD 集成示例

```yaml
# .github/workflows/chm.yml
name: Code Health Check
on: [push]
jobs:
  health:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 500
      - name: Run CHM
        run: |
          pip install chm
          chm analyze . --report json --output health.json
      - name: Upload Report
        uses: actions/upload-artifact@v4
        with:
          name: code-health
          path: health.json
```
