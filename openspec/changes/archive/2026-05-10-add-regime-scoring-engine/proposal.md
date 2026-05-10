# Change: Add Three-Layer Regime Scoring Engine

## Why

当前 dashboard 提供的是原始宏观指标和纯 LLM 驱动叙事，但缺少一个结构化、规则驱动的框架来把宏观条件转化为可执行的仓位 sizing 指引。用户需要手动解读信号并决定 exposure 水平，容易出错且一致性差。引入一个阈值可配置、确定性的 scoring engine，可在保留 LLM 可读解释能力的同时，提供可复现、可审计的仓位建议。

## What Changes

- **NEW** `regime-scoring` capability：新增三层评分引擎（Liquidity Foundation → Market Regime → Instant Sentinels），通过确定性规则计算 Target Position Envelope。包含 YAML 配置化阈值/权重、采用非对称触发/重置逻辑的 sentinel 状态持久化，以及每次数据刷新后的重算。
- **NEW** `position-advisor` capability：新增基于 CSV 的组合上传与分析，支持 conviction-regime 单仓上限、优先级 trim/close 建议，以及 regime 专属规则（options notional 上限、禁止 leverage、MOVE freeze）。
- **MODIFIED** `data-ingestion`：通过 Sector ETF 近似方案新增 S5FI market breadth 数据（11 个 SPDR ETF 相对 50DMA），并支持可配置行业权重与 graceful degradation。
- **MODIFIED** `dashboard`：新增 6 个 UI 组件——L3 Alert Banner（sticky）、Regime Gauge（hero）、L1/L2 Scoring Tables（双栏）、L3 Sentinel Row、Position Advisory 卡片、Regime Timeline（12 个月堆叠历史）。全部插入到现有内容上方。
- **MODIFIED** `llm-agent`：重构 LLM prompt 以接收结构化评分结果 + position advice；生成 6 个叙事分段（L1/L2/L3 summaries、Executive Summary、Position Narrative、Investment Playbook）；替换现有 Executive Summary 与 Investment Playbook 的内容来源，并保留当前 LLM 输出作为 fallback。

## Impact

- Affected specs：`regime-scoring`（new）、`position-advisor`（new）、`data-ingestion`、`dashboard`、`llm-agent`
- Affected code:
  - New：`src/regime/`（scoring engine、config、sentinel state）、`src/portfolio/`（position advisor）
  - New：`config/regime_defaults.yaml`（全部可配置阈值）
  - Modified：`src/data/market_client.py`（为 S5FI 增加 11 个行业 ETF）
  - Modified：`src/ui/app.py`（在现有布局上方插入新组件）
  - Modified：`src/llm/analyst.py`（重构 prompt、支持 6 段输出解析）
  - New：`src/ui/regime_components.py`（全部 regime UI widgets）
- 不移除任何既有功能；现有 charts 与 Liquidity Analysis / Risk Signals 区块保持不变
- **BREAKING**：Executive Summary 与 Investment Playbook 的内容来源由 raw-LLM 变为 regime-aware LLM（LLM 失败时回退至当前行为）
