# 架构速查

目录布局、双运行时与信息架构。产品定位见根目录 `CLAUDE.md`；编码约束见 `docs/code-standards.md`；裁决见 `docs/adr/`。

## 目录树

```
src/
  ledger/                # 【新建 P0】总资产账本 Facade + SQLite
  themes/                # 【新建 P2】投资主线 / 景气记分卡
  dossier/               # 【新建 P3】尽调卡 / 基金审查
  analysis/
    china_regime.py      # A 股三层体制：纯函数 + compute_china_regime（有状态）
    engine.py            # 美股体制评分引擎
    trending_up.py       # 趋势「交易时参考」（仓位/固定止损止盈部分待 P1 拆除）
  data/
    china_market_fetcher.py  # A 股 ETL-on-demand CSV
    loader.py            # FRED / Yahoo / AkShare 综合
  ui/                    # Streamlit 查阅层（只读；目标 IA：总资产→约束→主线→微观→周报库）
  utils/
    i18n.py              # t("key")；新 key 仅中文
  regime/                # 美股 RegimeEngine（市场级约束，勿当顶层输出）
  portfolio/             # Position Advisor（待 P1 按账本重构）
  llm/                   # 叙事生成（解释规则结果，不发明仓位数字）

jobs/                    # 【新建】headless 入口（周度快照等）

data_cache/
  ledger.db              # 【新建】总资产账本（gitignore，永不入 git）
  china/                 # A 股指标 CSV
  china_sentinel_state.json
  china_regime_history.csv
  reports/               # LLM 报告缓存

docs/adr/                # ADR 0001–0017（绑定裁决）
CONTEXT.md               # 领域词汇表
.scratch/p0-ledger/      # P0 本地规格

tests/
  test_china_regime.py   # 体制引擎先例（构造输入 → 纯接口 → 断言）
```

## 双运行时与持久化（ADR-0012 / 0013 / 0014）

- **Python 确定性内核**：账本、体制引擎、快照、信号评估；headless 经 `jobs/`；所有数字唯一出处
- **Agent 仪式层**：周报/月审/年审；调 `ttfund-*` Skill 后经写入接口写账本（不直接碰 `ledger.db`）
- **Streamlit**：纯查阅；仪式产物本体是 markdown 工件（邮件送达）
- **账本** = SQLite；**市场数据缓存** = CSV（可 diff、坏了删掉重拉）

## import 边界（ADR-0017）

新域与 `jobs/` → 只准依赖 `src/analysis/`、`src/data/`、`src/utils/`，**禁止** `src/ui/`。  
现有引擎（`analysis/`、`regime/`）保留作市场级约束，不整仓重写。拆除走显式 openspec change。

## 信息架构与可视化（ADR-0015）

- 页面：首页=总资产（偏离 / 卫星占比 / 目标进度三问，**无行情图**）→ 市场约束 → 主线 → 微观 → 周报库+数据管理
- 可视化：凡有区间必画色带；凡有「我」必标持仓/成本；红色只留给需动作事项

## 仪式与交互（ADR-0010 / 0016）

- 周报 / 月审 / 年审为 markdown 工件；仅 L3 哨兵与主线「逻辑破坏」可打破节奏告警（邮件）
- 深度 ad-hoc 查询在 Agent 会话中进行；**不在 Streamlit 内嵌 chat**
