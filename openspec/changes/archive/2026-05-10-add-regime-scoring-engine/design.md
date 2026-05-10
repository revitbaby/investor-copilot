## Context

现有系统是一个 Streamlit dashboard：拉取宏观数据（FRED + Yahoo Finance），执行简单信号分析，并将原始指标交给 LLM 生成叙事。PRD 要求在数据摄取与 LLM 之间加入一个确定性的三层评分引擎，产出结构化的仓位 sizing 指引。这是一次跨层改动，会同时影响 data、analysis、LLM 与 UI。

**Stakeholders**：需要稳定、规则化仓位 sizing 的宏观交易员/投资者。

**来自 PRD 的约束**：
- 所有阈值/权重 MUST 可配置（禁止 hardcoding）
- 评分逻辑必须纯 rule-based；LLM 只负责解释，不能做决策
- 新模块需采用增量式方式（优先新增文件，而非大量改动现有文件）
- Sentinel 状态需要跨会话持久化

## Goals / Non-Goals

**Goals**：
- 构建确定性、可测试、阈值可配置的三层评分体系
- 清晰分层：scoring engine → position advisor → LLM narrator
- 使用非对称触发/重置机制实现 Sentinel 状态持久化
- 新增 UI 组件并插入到现有 dashboard 内容之上
- 各层具备 graceful degradation（数据失败→中性分；LLM 失败→表格仍可渲染）

**Non-Goals**：
- 实时流式 / WebSocket 更新（仅支持批量刷新）
- 评分引擎 backtesting 框架
- 用户账户或身份认证
- 移动端专项响应式设计
- 自动化交易执行

## Decisions

### D1: Module Structure

**Decision**：在已有 `src/analysis/` 旁新增两个顶层 package：`src/regime/` 与 `src/portfolio/`。

```
src/
├── regime/
│   ├── __init__.py
│   ├── config.py          # Load YAML, expose typed config dataclass
│   ├── layer1.py          # L1 scoring functions (4 indicators)
│   ├── layer2.py          # L2 scoring functions (8 indicators)
│   ├── layer3.py          # L3 sentinel state machine
│   ├── envelope.py        # Combine L1×L2 or L3 override
│   └── engine.py          # Orchestrator: run all layers, return RegimeResult
├── portfolio/
│   ├── __init__.py
│   ├── parser.py          # CSV upload parsing + validation
│   ├── advisor.py         # Position sizing logic + trim priority
│   └── models.py          # Dataclasses for holdings, advice
```

**Rationale**：将评分逻辑与现有 analysis 代码隔离。无 Streamlit 依赖的 pure function 便于单元测试。`regime/` 负责三层评分及其组合；`portfolio/` 负责用户维度的仓位建议。

**Alternatives considered**：将全部逻辑放入 `src/analysis/engine.py` —— 已拒绝，因为该文件已超过 150 行，且 regime engine 的关注点本质不同。

### D2: Configuration System

**Decision**：启动时加载单一 YAML 文件 `config/regime_defaults.yaml`。通过 `RegimeConfig` dataclass 提供强类型访问，默认值与 PRD 保持一致。

**Rationale**：YAML 可读性高且便于 diff。dataclass 层可在启动时捕捉拼写/字段错误。用户可通过 `config/regime_overrides.yaml` 覆盖默认配置并执行 merge。

**Alternatives considered**：Environment variables（参数过多）、JSON（可读性较弱）、TOML（可行但不如 YAML 适合嵌套配置）。

### D3: Sentinel State Persistence

**Decision**：使用 `data_cache/sentinel_state.json` 存储每个 sentinel 的状态（`CLEAR`/`TRIGGERED`/`COOLING`）、触发时间戳与 cooling 天数计数。启动时加载，每次评分后保存。

**Rationale**：方案简单、可人工检查、无数据库依赖。文件损坏时将所有 sentinel 重置为 `CLEAR`（安全默认）。同时与现有 `data_cache/` 报告存储模式一致。

**Alternatives considered**：SQLite（对于 4 个 sentinel 过度设计）、仅 session state（重启后状态丢失）。

### D4: S5FI Market Breadth Approximation

**Decision**：通过现有 `MarketClient` 下载 11 个 SPDR 行业 ETF，计算各 ETF 相对其 50DMA 的位置，再叠加可配置行业权重。任一失败时回退到 50.0（中性）。

**Rationale**：复用现有 Yahoo Finance 基础设施。仅需 11 个 ticker，相比全量 S&P 成分股 500+ 更轻量。对三元评分（+1/0/-1）而言精度已足够。

### D5: LLM Integration Architecture

**Decision**：采用单次 LLM 调用，输入完整结构化评分结果（3 层 + envelope + 可选 position advice）及原始市场数据。输出 6 个带标签分段，使用 delimiter markers 解析。

```
Scoring Engine (rule-based)
    ↓
Position Advisor (rule-based)
    ↓
LLM Narrator (single call)
    ↓ parses into 6 segments
UI rendering
```

**Rationale**：单次 LLM 调用可降低延迟与成本。基于分隔符的解析简单且可靠。Fallback 机制：若解析失败，整段 LLM 响应回退到 legacy 格式。

### D6: UI Component Strategy

**Decision**：新增 `src/ui/regime_components.py`，其中提供纯渲染函数，接收 `RegimeResult` 与 `PositionAdvice` dataclass。由 `app.py` 在现有内容渲染之前调用。

**Rationale**：避免对 `app.py` 进行重度改造。每个组件独立成函数，便于单独测试与替换。

### D7: Regime Timeline Data Storage

**Decision**：将每日评分快照追加写入 `data_cache/regime_history.csv`（date、L1 regime、L2 regime、L3 events、target min/max、SPX close），用于 timeline 可视化读取。

**Rationale**：CSV 简单且易于 append。每年约 365 行，体量很小。暂不提供 backfill 机制——历史从首次部署开始累积。

## Risks / Trade-offs

| Risk | Mitigation |
|------|-----------|
| S5FI 行业 ETF 近似可能偏离真实 breadth | 权重可配置；批处理场景可选 precise mode |
| LLM 输出解析可能因模型变化失效 | 使用 delimiter + 全文 fallback；LLM 失败不阻塞评分展示 |
| Sentinel 状态文件损坏 | 任意解析错误都重置为全 `CLEAR`；记录 warning |
| YAML 配置过大后维护困难 | 按 layer 分组；加载时做 schema 校验 |
| 新增 6 个组件后 UI 可能过高 | L3 Sentinel Row 采用紧凑布局；Position Advisory 条件渲染；Timeline 可折叠 |

## Migration Plan

1. 先部署 scoring engine + config（暂不改 UI）→ 通过测试验证评分正确性  
2. 将 UI 组件插入现有内容上方 → 下方既有 dashboard 内容保持不变  
3. 将 LLM prompt 切到 regime-aware 版本并保留 fallback → Executive Summary / Playbook 的内容来源发生变化  
4. 无需数据迁移；sentinel state 与 regime history 从空状态开始

## Open Questions

- Regime Timeline 图表是否应默认折叠，以降低初始页面高度？
- S5FI 是否应在 v1 即支持可选的 “precise 500-stock” 模式，还是延后到后续变更？
- Sentinel state 中日期格式应采用 UTC 还是 local time？
