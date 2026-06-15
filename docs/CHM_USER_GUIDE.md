# Codebase Health Monitor — 用户手册

## 安装

```bash
git clone https://github.com/lighthouse/chm.git
cd chm
pip install -e .
```

## 命令参考

### `chm analyze` — 完整分析

```bash
# 基础用法
chm analyze /path/to/repo

# 生成 HTML 报告
chm analyze . --report html --output report.html

# 生成 JSON 输出
chm analyze . --report json --output data.json

# 限制分析范围
chm analyze . -n 1000
```

### `chm hotspots` — 代码热区

```bash
chm hotspots .
chm hotspots . --top 20
```

### `chm authors` — 贡献者分析

```bash
chm authors .
```

### `chm pulse` — 团队脉动

```bash
chm pulse .
```

### `chm churn` — 流失率概览

```bash
chm churn .
```

## 健康度评分说明

| 分数 | 等级 | 含义 |
|------|------|------|
| 80-100 | 🟢 健康 | 代码库状态良好 |
| 50-79 | 🟡 一般 | 存在一些值得关注的问题 |
| 20-49 | 🟠 需关注 | 多个风险指标异常 |
| 0-19 | 🔴 高危 | 需要立即干预 |

### 评分因素

- **巴士因子**: 低则扣分（关键人物风险）
- **代码集中度**: 前 3 文件改动占比 > 50% 则扣分
- **活跃度**: 持续日常提交加分
- **复杂度**: 高风险文件多则扣分

## 最佳实践

1. **定期运行**: 建议每周运行一次，跟踪趋势
2. **CI 集成**: 将 `chm analyze --report json` 加入 CI 流程
3. **团队分享**: HTML 报告可直接分享给团队和管理层
4. **设定基线**: 为新项目建立健康度基线，监控恶化趋势
