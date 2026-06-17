# 一键分发文案包

> 复制 → 粘贴 → 发。每个平台 2 分钟。

---

## 知乎专栏

**标题**：做了个开源工具：一行命令诊断你的代码库健康度（8个指标·免费）

**正文**：

你多久没检查过代码库的健康了？

我分析了 200+ 个开源仓库，发现 60% 的 bug 修复集中在不到 10% 的文件里。这些「热区文件」高频修改、多人触碰、低注释率、没有测试——但大多数团队根本不知道它们在哪。

于是我做了 CHM。一个 pip install，读 Git 历史，30 秒出 8 维健康报告：谁改得太多？巴士因子多少？哪些文件没测试？有没有循环依赖？

```bash
pip install chm-cli
chm doctor .
```

免费开源。代码从不出你的电脑。

GitHub：https://github.com/Neohu-ceo/chm

---

## CSDN

**标题**：【开源推荐】CHM——一行命令诊断Git仓库健康度，8个指标免费看

**正文**：

## 它能做什么

在终端输入 `chm doctor .`，30秒后你会得到：

- 哪些文件改动最频繁（热区 = bug温床）
- 巴士因子是多少（几个人离职项目就瘫痪）
- 24小时提交分布（团队什么时候在工作）
- 哪些代码复杂度高但注释少
- 哪些文件超过半年没动过（死代码）
- 有没有循环依赖
- 哪些源文件没测试
- 哪些代码是复制粘贴的

## 安装

```bash
pip install chm-cli
chm doctor .
```

## 为什么做

SonarQube $150+/月，需要服务器。CodeClimate $49+/月。CHM：一个 pip install，免费开源，MIT协议。

## 链接

GitHub：https://github.com/Neohu-ceo/chm
PyPI：https://pypi.org/project/chm-cli/

如果对你有用，帮忙点个 Star ⭐

---

## 思否 (SegmentFault)

**标题**：CHM：一个命令检查代码库健康度（开源·免费·MIT）

**正文**：

```bash
pip install chm-cli
chm doctor .
```

8 个维度：热区 · 巴士因子 · 团队脉动 · 复杂度 · 死代码 · 依赖 · 测试覆盖 · 重复代码

Python 实现 · 40 个自动化测试 · 12 个 MCP 工具 · 零配置 · 本地运行

GitHub：https://github.com/Neohu-ceo/chm

求反馈求 Star 🙏

---

## V2EX

**标题**：Show HN: 做了一个开源 CLI 工具，一行命令看代码库健不健康

**正文**：

```bash
pip install chm-cli
chm doctor .
```

输出 8 个指标：热区分析、巴士因子、24h 活动分布、复杂度、死代码、循环依赖、测试覆盖、重复代码。

纯 Python，MIT 开源，代码不出你电脑。求大佬们试用反馈 👉 https://github.com/Neohu-ceo/chm

---

## Reddit r/programming

**Title**: Show r/programming: CHM — one command to check your codebase health (8 metrics, MIT)

**Body**:

Most teams don't use code quality tools because they're too heavy (SonarQube needs a server, CodeClimate costs $49+/mo).

So I built CHM — one `pip install`, reads your git history, 30 seconds to an 8-dimension health report.

```bash
pip install chm-cli
chm doctor .
```

Free. Open source. MIT. Code never leaves your machine.

GitHub: https://github.com/Neohu-ceo/chm

---

## Hacker News (Show HN)

**Title**: Show HN: CHM — one-command codebase health check (8 metrics, free, MIT)

**Body**: (same as Reddit above)

```bash
pip install chm-cli
chm doctor .
```

8 dimensions: hotspots, bus factor, team pulse, complexity, dead code, circular deps, test coverage, duplication. Python, 40 tests, 12 MCP tools. GitHub: https://github.com/Neohu-ceo/chm
