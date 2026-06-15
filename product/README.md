# Codebase Health Monitor (CHM)

```
   __
  / /_  ______ ___  _____
 / __ \/ __ `/ / / / ___/
/ / / / /_/ / /_/ (__  )
/_/ /_/\__,_/\__, /____/
            /____/

Codebase Health Monitor v0.1.0
```

将任何 git 仓库转化为可操作的健康度报告。

## 快速上手

```bash
# 安装
pip install -e .

# 在任意 git 仓库运行
chm analyze .
chm analyze . --report html
chm analyze . --output report.html
```

## 功能

- `chm analyze` — 完整分析
- `chm hotspots` — 显示修改最频繁的文件
- `chm churn` — 代码流失率
- `chm authors` — 贡献者统计
- `chm pulse` — 团队活跃节奏
