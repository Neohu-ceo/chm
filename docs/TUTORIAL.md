# CHM Tutorial — From Zero to Codebase Health in 5 Minutes

## Step 1: Install

```bash
pip install chm
```

## Step 2: Initialize Your Project

```bash
cd your-project
chm init
```

This takes a baseline snapshot and runs a quick health scan. You'll see:

```
📸 Step 1: Taking baseline snapshot...
   ✅ Baseline saved

🔍 Step 2: Quick health scan...
   ⚠️ Bus Factor: 1     ← 🚨 If this is 1, you have a bus factor problem
   🔥 Hotspots: 12 files  ← Files that change too often
   🧪 Test Coverage: D    ← Match source files to tests
   🧬 Health Score: 45/100
```

## Step 3: Full Analysis

```bash
chm analyze .
```

This runs all 8 dimensions:
1. **Hotspots** 🔥 — Most frequently changed files (bug factories)
2. **Contributors** 👥 — Who writes what + bus factor
3. **Team Pulse** 💓 — When your team works (24h distribution)
4. **Complexity** 🧩 — Hard-to-understand files
5. **Dead Code** 💀 — Files not touched in 6+ months
6. **Dependencies** 🔗 — Import coupling + circular deps
7. **Test Coverage** 🧪 — Which source files lack tests
8. **Duplication** 📋 — Copy-pasted code blocks

## Step 4: Generate HTML Report

```bash
chm analyze . --report html --output health.html
open health.html
```

Share this with your team. It's a self-contained HTML file — no server needed.

## Step 5: Track Trends

```bash
# Take a snapshot every week
chm snapshot .

# After a few weeks, check trends
chm trends .

# Compare two snapshots
chm compare . -a 0 -b 1
```

## Step 6: Set Up CI/CD

Copy `.github/workflows/code-health.yml` from the CHM repo.
Now every push gets a health report as a build artifact.

## Step 7: Use with AI Agents (MCP)

```bash
# Register CHM as an MCP server
claude mcp add chm -- chm mcp

# Now Claude Code can query your codebase health:
# "What are my top hotspots?"
# "What's my bus factor?"
# "Which files need tests?"
```

## Pro Tips

- **Bus factor = 1?** Start pair programming immediately.
- **Top 3 files > 50% churn?** Refactor them first.
- **Coverage < 40%?** Write tests for your top 5 hotspots first.
- **Dead code > 20%?** Archive or delete stale files.

## Next

- [API Reference](API_REFERENCE.md)
- [User Guide](CHM_USER_GUIDE.md)
- [Register for Pro](http://localhost:5001/register) ($29/month)
