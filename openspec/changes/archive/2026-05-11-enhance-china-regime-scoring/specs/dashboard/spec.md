## ADDED Requirements

### Requirement: China Three-Indicator Chart Cards
系统 SHALL 在 China 模块顶部渲染三个指标卡片，每个包含折线图（或月频散点图）+ 最新值 + 历史参考水位 + 文字解释：
1. 两融余额市值比（日频折线图）
2. 股债利差（日频折线图）
3. 存款市值比（月频散点图）

#### Scenario: Three cards render with historical reference levels
- **WHEN** 用户打开 China 模块
- **THEN** 三个指标卡片均可见，每个图表叠加历史牛市参考水位虚线，并标注参考值文字

#### Scenario: Latest value card with proximity description
- **WHEN** 渲染最新值卡片
- **THEN** 每个卡片显示最新值，并附与历史参考点距离的文字描述（"很远 / 较远 / 较近 / 接近"）

#### Scenario: Data freshness note displayed
- **WHEN** 渲染 China 指标卡片区域
- **THEN** 区域底部显示小字数据来源和最新更新日期（例如"融资融券余额：日更，至 2026-05-10 | PE：日更，约1日滞后 | M2：月更，至 2026-04"）

#### Scenario: Deposit ratio uses monthly dot chart
- **WHEN** 渲染存款市值比图表
- **THEN** 图表使用月频散点而非日频连线，x 轴以月份为单位

### Requirement: China Regime Scoring Table
系统 SHALL 在 China 模块中部渲染 A 股体制评分表，展示三层评分的当前状态：
- Layer 1：4 个信号的各自得分 (+1/0/-1)、Composite Score、Ceiling
- Layer 2：体制分类名称、各维度信号状态、Utilization Rate 区间
- Layer 3：5 个哨兵各自状态（CLEAR / TRIGGERED / COOLING）

#### Scenario: Scoring table renders all three layers
- **WHEN** China 体制评分计算完成
- **THEN** Dashboard 显示三层评分表，每层标题清晰，信号状态以颜色区分（绿/黄/红）

#### Scenario: L2 regime name localized
- **WHEN** 用户界面语言为中文
- **THEN** L2 体制名称显示为中文（"价值牛市" / "情绪牛市" / "恐慌底部" / "高估风险" / "中性"）

#### Scenario: Reasoning text shown per layer
- **WHEN** 渲染体制评分表
- **THEN** 每层附一行简短推理说明（如"M1 同比转正，DR007 低于 OMO，流动性趋于宽松"）

### Requirement: China Target Position Envelope Gauge
系统 SHALL 在 China 模块中部渲染一个 Gauge 仪表盘，显示 A 股 Target Position Envelope（min%–max%），样式与 US 模块 Envelope Gauge 一致。

#### Scenario: Gauge renders envelope range
- **WHEN** 三层合成完成
- **THEN** Gauge 显示当前 A 股建议仓位区间（如 "48%–60%"），并标注当前体制名称

#### Scenario: Emergency mode gauge changes color
- **WHEN** Layer 3 触发 emergency override
- **THEN** Gauge 以橙色或红色渲染，并附"哨兵触发中"提示文字

### Requirement: China Sentinel Warning Banner
系统 SHALL 在 China 模块顶部（条件显示）渲染警告横幅：当任意 Layer 3 哨兵处于 TRIGGERED 或 COOLING 状态时显示；无哨兵触发时隐藏。

#### Scenario: Banner appears on sentinel trigger
- **WHEN** `LIMIT_DOWN_PANIC` 哨兵 TRIGGERED
- **THEN** China 模块顶部显示橙色/红色警告横幅，描述触发原因（如"⚠️ 跌停恐慌哨兵触发：当日跌停股 62 只，超出阈值 50"）

#### Scenario: Multiple sentinels in banner
- **WHEN** 2 个及以上哨兵 TRIGGERED
- **THEN** 横幅列出所有触发的哨兵名称和触发值

#### Scenario: Banner hidden when all clear
- **WHEN** 所有 Layer 3 哨兵均为 CLEAR
- **THEN** 警告横幅不显示，不占用 UI 空间

### Requirement: China 12-Month Regime Timeline
系统 SHALL 在 China 模块底部渲染过去 12 个月的 A 股体制色带时间轴，每日使用对应 L2 体制颜色填充（`VALUE_BULL`=深绿，`SENTIMENT_BULL`=浅绿，`NEUTRAL`=黄，`PANIC_BOTTOM`=橙，`OVERVALUATION_RISK`=红），样式与 US 模块 Regime Timeline 一致。

#### Scenario: Timeline renders 12 months of history
- **WHEN** `china_regime_history.csv` 包含过去 12 个月记录
- **THEN** 色带时间轴完整渲染，当日用较深边框高亮

#### Scenario: Insufficient history shows available data
- **WHEN** 历史记录不足 12 个月（如初次部署）
- **THEN** 时间轴仅显示已有的历史范围，并标注"历史不足 12 个月"提示

## MODIFIED Requirements

### Requirement: AI Report Display
当 A 股体制评分可用时，系统 SHALL 将 `ChinaRegimeResult` 注入到 LLM Agent 的中国宏观分析 prompt 中（此部分为准备工作，LLM 叙事生成本身在本 change 范围外）。Dashboard SHALL 保留现有 AI Report 区块不变。

#### Scenario: Regime data available for future LLM injection
- **WHEN** China 体制评分计算完成
- **THEN** `ChinaRegimeResult` 对象在 session_state 中可访问，供后续 LLM 集成使用

#### Scenario: Existing AI Report fallback unchanged
- **WHEN** 本次变更部署后
- **THEN** 现有 AI 报告生成逻辑保持不变，不因本次 change 而退化
