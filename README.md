# 🏠 CHM — Codebase Health Monitor

<p align="center">
  <img src="https://img.shields.io/badge/code_health-know%20yours-blue?style=flat" alt="Code Health">
  <img src="https://img.shields.io/pypi/v/chm-cli?color=blue" alt="PyPI">
  <img src="https://img.shields.io/pypi/pyversions/chm-cli" alt="Python">
  <img src="https://img.shields.io/github/license/Neohu-ceo/chm" alt="License">
  <img src="https://img.shields.io/github/stars/Neohu-ceo/chm" alt="Stars">
</p>

**One command to know your codebase health.** 21 CLI commands, 8 analysis dimensions, MCP server for AI agents. MIT licensed. Local-first. Zero config.

```bash
pip install chm-cli
chm init .
chm doctor .
```

---

## What it does

Chm reads your git history and gives you a **health report** — not opinions, but data:

| Dimension | Tells you |
|-----------|-----------|
| 🔥 **Hotspots** | Which files change too often (bug factories) |
| 👥 **Contributors** | Bus factor — how fragile is your team? |
| 💓 **Team Pulse** | When does your team actually work? |
| 🧩 **Complexity** | Hard-to-maintain files with low comments |
| 💀 **Dead Code** | Files untouched for months — candidates for deletion |
| 🔗 **Dependencies** | Circular deps and over-coupled modules |
| 🧪 **Test Coverage** | Which files lack tests (by naming convention) |
| 📋 **Duplication** | Copy-pasted code across files |

```bash
$ chm doctor .

🏥 CHM Doctor — Diagnosis for my-api

  Health Score: 62/100

  🚨 [Team Risk] Bus factor = 1 — single point of failure
     ▸ 立即开始结对编程，让第二个人熟悉核心模块
     ▸ 核心文件：src/auth.py, src/payment.py

  ⚠️ [Hotspots] Top 3 files account for 52% of churn
     ▸ 优先重构 src/payment.py — 被 3 个人改了 12 次
     ▸ 为这些文件补充单元测试
```

---

## Quick Start

```bash
# Install
pip install chm-cli

# Try it without a real project
chm demo

# Analyze your repo
chm init .          # First-time wizard
chm analyze .       # Full 8-dimension report
chm doctor .        # Actionable prescriptions

# Generate shareable report
chm analyze . --report html -o health.html

# Track trends over time
chm snapshot .      # Save a baseline
chm trends .        # See how health changes

# Generate a README badge
chm badge . -o badge.svg
```

---

## AI Agent Integration (MCP)

Chm is a **Model Context Protocol server** — AI agents can query your codebase health directly:

```bash
# Register with Claude Code
claude mcp add chm -- chm mcp

# Then ask Claude:
# "What are my top hotspots?"
# "What's my bus factor?"
# "Which files need tests the most?"
```

12 MCP tools + 1 resource exposed.

---

## Install

```bash
pip install chm-cli        # Base CLI
pip install chm-cli[mcp]   # With MCP server support
```

Requires Python 3.9+ and Git.

---

## Commands

| Command | Description |
|---------|-------------|
| `analyze` | Full 8-dimension health analysis |
| `doctor` | Diagnosis with prioritized prescriptions |
| `init` | Interactive onboarding wizard |
| `demo` | Run demo without a real repo |
| `hotspots` | Most-changed files |
| `authors` | Contributor stats + bus factor |
| `pulse` | Team activity rhythm |
| `churn` | Code churn overview |
| `complexity` | Code complexity analysis |
| `deadcode` | Stale file detection |
| `deps` | Dependency + coupling analysis |
| `coverage` | Test coverage estimation |
| `duplicates` | Code duplication detection |
| `snapshot` | Save health baseline |
| `trends` | View health trends |
| `compare` | Compare two snapshots |
| `badge` | Generate SVG badge |
| `watch` | Auto-analyze on git commit |
| `mcp` | Start MCP server |
| `login` | Connect SaaS account |
| `status` | SaaS entitlement check |

---

## SaaS Platform

An optional SaaS backend provides:
- 📊 Multi-repo team dashboards
- 📧 Weekly email reports
- 🔑 License key management
- 💳 Subscription billing (Stripe/PayPal/WeChat/Alipay)

[Learn more →](https://github.com/Neohu-ceo/chm#readme)

---

## Why CHM?

| | CHM | SonarQube | CodeClimate | GitCompass |
|---|---|---|---|---|
| Install | `pip install` | Java server | SaaS signup | `npm install` |
| Price | Free / $29 | $150+ | $49+ | Free |
| Local-first | ✅ | ❌ | ❌ | ✅ |
| Open source | ✅ MIT | ❌ | ❌ | ✅ MIT |
| MCP support | ✅ 12 tools | ❌ | ❌ | ❌ |
| SaaS backend | ✅ | ❌ | ✅ | ❌ |

---

## License

MIT — free for individuals and companies. SaaS platform is proprietary.

<p align="center">
  <sub>Built with ❤️ by Lighthouse Analytics</sub>
</p>
