# Product Hunt Launch Kit

> 发布日：待定（等 GitHub 仓库和 PyPI 就绪）

## 标题
**CHM — One command to know if your codebase is rotting**

## 标语
`pip install chm && chm analyze .` — That's it. No servers, no signup, no config.

## 描述

I built CHM because I was tired of:
- SonarQube needing a dedicated server
- CodeClimate costing $49+/month per repo
- Not knowing which files actually need refactoring

CHM reads your git history and tells you:
🔥 Which files are changed too often (hotspots = bug factories)
👥 Your bus factor (how many people can leave before the project dies)
💓 When your team actually works (24h activity distribution)
🧩 Which files are too complex with too few comments

Health score: 78/100 🟢 Healthy

All local. All open source (MIT). Core features free forever.

## 首条评论 (Maker Comment)

Hey Product Hunt! 👋

I built CHM as a solo developer to solve a problem every team has: "we know the codebase has issues, but we don't know where to start."

CHM is NOT a SonarQube replacement — it's complementary. SonarQube tells you about code smells. CHM tells you about *team smells* and *process smells*.

**Tech stack**: Python, Click, Flask, SQLite. ~2,000 lines of Python.

**Why I'm excited**: In the first week of building this, I analyzed 20+ open source repos and found patterns I'd never noticed before. The average open source project has a bus factor of 1.5. That's terrifying.

**Ask**: Try `pip install chm` on your project. It takes 30 seconds. If it gives you useful insight, ⭐ us on GitHub!

**What's next**: 
- GitHub Actions integration (this week)
- VS Code extension
- Team dashboards

Happy to answer any questions! 🙏

## 媒体素材

### Logo
```
   __
  / /_  ______ ___  _____
 / __ \/ __ `/ / / / ___/
/ / / / /_/ / /_/ (__  )
/_/ /_/\__,_/\__, /____/
            /____/
```

### 截图描述
1. Terminal output with full analysis
2. HTML report with charts
3. Trend comparison between two snapshots

## 标签
#developer-tools #git #code-quality #open-source #cli #python #devtools

## 发布清单
- [ ] GitHub repo public with README
- [ ] PyPI package published
- [ ] Website live
- [ ] Demo video / GIF
- [ ] 5 friends ready to upvote
- [ ] Twitter thread prepared
- [ ] Reddit r/programming post drafted
- [ ] Hacker News "Show HN" title ready
