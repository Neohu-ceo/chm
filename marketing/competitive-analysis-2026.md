# 2026 代码库健康分析工具全景对比

> 基于公开数据、GitHub 仓库分析和市场调研。更新于 2026-06-15。

---

## 市场格局

2026 年的代码库健康工具市场已经分裂成了三个阵营：

| 阵营 | 代表 | 特点 |
|------|------|------|
| **传统巨头** | SonarQube (93% 市场份额) | 重、贵、需要服务器 |
| **AI 原生新锐** | repowise, desloppify | MCP 集成、AI 驱动修复 |
| **Git 分析工具** | CHM, ContextPulse, GitCompass | 轻量、本地运行、开源 |

CHM 属于第三阵营，但通过 MCP 集成正在向第二阵营靠拢。

---

## 完整对比

| 维度 | CHM | ContextPulse | GitCompass | repowise | desloppify |
|------|-----|-------------|------------|----------|------------|
| **安装** | `pip install chm` | `pip install contextpulse` | `npm i git-compass` | 源码构建 | `pip install desloppify` |
| **语言** | Python | Python | Node.js | Python | Python |
| **许可证** | MIT | MIT | MIT | AGPL-3.0 | ? |
| **MCP 支持** | ✅ 8 tools + 1 resource | ❌ | ❌ | ✅ 9 tools | ❌ |
| **热区检测** | ✅ | ✅ | ✅ | ✅ | ❌ |
| **巴士因子** | ✅ | ✅ | ✅ | ❌ | ❌ |
| **团队脉动** | ✅ 24h分布 | ✅ commit streak | ✅ burnout heatmap | ❌ | ❌ |
| **复杂度分析** | ✅ 15+语言 | ❌ 基础 | ✅ 架构风险 | ✅ 25个生物标记 | ✅ 29语言 |
| **历史趋势** | ✅ snapshot+compare | ✅ | ❌ | ✅ SQLite | ❌ |
| **HTML 报告** | ✅ 精美 | ✅ | ✅ 交互式 | ❌ | ❌ |
| **SaaS 后端** | ✅ 订阅+支付+许可 | ❌ | ❌ | ❌ | ❌ |
| **免费层** | ✅ 功能完整 | ✅ | ✅ | ✅ | ✅ |
| **定价** | $0/$29/$99 | 免费 | 免费+AI | 免费 | 免费 |
| **子命令数** | 10 | 30+ | 5 | 9 (MCP) | 1 修复循环 |
| **AI 修复** | ❌ | ❌ | ⚠️ 可选AI摘要 | ✅ AI agent可用 | ✅ 全自动 |

---

## CHM 的差异化优势

### 1. 唯一同时有 MCP + SaaS 后端的工具
- repowise 有 MCP 但没有 SaaS（没有订阅、支付、许可管理）
- ContextPulse 功能多但没有 MCP 和 SaaS
- **CHM 是唯一可以让 AI agent 分析代码库、同时又能通过 SaaS 变现的工具**

### 2. 最完整的免费层
- ContextPulse 功能虽多，但缺乏报告导出
- GitCompass 需要 Node.js 环境
- CHM 核心功能永久免费，MIT 协议

### 3. 本地优先 + 可选云端
- 不联网也能用全部功能
- SaaS 层是可选的，不是必须的

---

## CHM 需要追赶的地方

| 差距 | 竞品 | 计划 |
|------|------|------|
| 子命令数量 (10 vs 30+) | ContextPulse | v0.3.0 增加至 15+ |
| 代码生物标记 (4 vs 25) | repowise | 增加死代码检测、耦合度 |
| AI 驱动的修复建议 | desloppify | MCP 集成已就绪 |
| 交互式可视化 | GitCompass | HTML 报告增强 |

---

## 结论

CHM 在 2026 年的正确赛道上：**MCP 集成 + 开源 + SaaS 变现**。主要竞争对手都没有同时做到这三点。

短期策略：
1. MCP 工具数量从 8 扩展到 15+
2. 增加死代码检测和依赖健康度
3. 优化 HTML 报告交互性
4. 发布到 PyPI → 获取真实用户反馈
