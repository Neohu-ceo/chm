# Changelog

All notable changes to Codebase Health Monitor (CHM).

## [0.3.0] — 2026-06-16

### Added
- **Dead code detection** 💀 — Identifies files untouched for 6+ months
- **Dependency analysis** 🔗 — Import coupling, circular dep detection
- **Test coverage estimation** 🧪 — Source↔test file matching by naming convention
- **Duplication detection** 📋 — Cross-file duplicate line detection
- **`chm init`** — Interactive onboarding wizard with baseline snapshot
- **4 new CLI commands**: `deadcode`, `deps`, `coverage`, `duplicates`
- **4 new MCP tools**: `get_dead_code`, `get_dependencies`, `get_test_coverage`, `get_duplication`
- Health score now factors all 8 dimensions (was 4)
- Tutorial documentation (`docs/TUTORIAL.md`)
- Competitive analysis report (`marketing/competitive-analysis-2026.md`)

### Changed
- CLI expanded from 10 → 14 commands
- MCP tools expanded from 8 → 12 tools + 1 resource
- Analysis dimensions: 4 → 8

## [0.2.0] — 2026-06-15

### Added
- **Trend tracking**: `chm snapshot` and `chm trends` for historical health monitoring
- **Snapshot comparison**: `chm compare` to diff two points in time
- **SaaS integration**: `chm login`, `chm status`, API key/license validation
- **SaaS platform**: Full Flask web app with user management, subscriptions, payments
- **Payment integrations**: Stripe, PayPal, WeChat Pay, Alipay stubs
- **License key system**: Offline validation for paid plans
- **Admin dashboard**: Business metrics (MRR, users, usage)
- **Free online report**: Web-based git analysis tool
- **Marketing website**: Landing page, pricing, comparison, technical blog
- **Password reset flow**: Token-based reset with PBKDF2 hashing
- **Email verification**: Token-based verification system
- **Rate limiting**: Per-IP rate limits on auth endpoints
- **API key revocation**: `DELETE /api/keys/<id>`
- **Database backup**: Automated compressed backups with rotation
- **Health check**: `/health` monitoring endpoint

### Changed
- **BREAKING**: Password hashing upgraded from SHA256 to PBKDF2-SHA256 (600k iterations)
- Legacy SHA256 hashes auto-upgraded on successful login
- `get_commit_times()` fixed — was broken in 0.1.0

### Fixed
- Empty git repositories now handled gracefully (no crash)
- `.chm/` directory excluded from complexity analysis
- API key revocation now functional

## [0.1.0] — 2026-06-15

### Added
- Initial release
- `chm analyze` — Full health analysis (terminal, HTML, JSON)
- `chm hotspots` — File churn hotspots
- `chm authors` — Contributor statistics with bus factor
- `chm pulse` — Team activity rhythm (24h distribution)
- `chm churn` — Code churn overview
- Health score (0-100) with color-coded output
- HTML report with interactive charts
- JSON machine-readable output
- Git-native, zero-config architecture
