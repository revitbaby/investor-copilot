# 账本域用 SQLite 单库，市场数据缓存维持文件模式

- **账本域**（持仓、交易流水、周度快照、基金穿透结果、主线映射）存于 `data_cache/ledger.db`（SQLite），聚合逻辑（如"卫星仓真实占比" = 持仓 × 穿透 × 主线映射 join）用 SQL 表达。理由：账本是系统里唯一"写错会导致错误决策"的数据，需要事务/外键/唯一约束保一致性；数据量小不是选型依据，一致性才是。
- **市场数据缓存**维持 ETL-on-demand CSV/JSON 现状：可 diff、可人眼检查、坏了删掉重拉，是"缓存污染自愈"机制的基础，迁库是负收益。
- **Agent 不直接碰数据库文件**：Agent 仪式层写账本必须走 Python 内核提供的写入接口（如 `uv run python -m ledger.record_fund_holdings --json ...`），否则账本一致性交给了 LLM 的概率输出。

## 代码结构

新域按 `src/ledger/`（账本+快照）、`src/themes/`（主线记分卡）、`src/dossier/`（尽调卡+基金审查）、`jobs/`（headless 入口）组织。现有市场引擎代码（`src/analysis/`、`src/regime/` 等）不动——已按 ADR-0001 降级为约束子模块，改名重构无业务收益。

2026-08-07，经 grilling 会话裁决。
