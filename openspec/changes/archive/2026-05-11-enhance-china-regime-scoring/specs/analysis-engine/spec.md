## ADDED Requirements

### Requirement: China Layer 1 Scoring Function
系统 SHALL 提供纯函数 `compute_china_layer1(signals: ChinaL1Signals) -> ChinaL1Result`，接受 4 个 Layer 1 信号值，返回 Composite Score、L1 Regime label 和 Position Ceiling。

#### Scenario: All signals bullish
- **WHEN** DR007 偏差为负（DR007 < OMO）、M1 YoY 为正、M1-M2 差收窄、TSF 同比加速
- **THEN** 函数返回 Composite Score = 4，Regime = `EXPANSIONARY`，Position Ceiling = 80%

#### Scenario: Mixed signals
- **WHEN** 4 个信号中 2 个为 +1、2 个为 -1
- **THEN** 函数返回 Composite Score = 0，Regime = `NEUTRAL`，Position Ceiling = 60%

#### Scenario: Missing signal defaults to neutral
- **WHEN** TSF 数据传入为 None
- **THEN** TSF 信号得分默认为 0，其余 3 个信号正常参与计算

### Requirement: China Layer 2 Regime Classification Function
系统 SHALL 提供纯函数 `classify_china_regime(equity_bond_signal, margin_signal, qvix_signal) -> ChinaL2Result`，返回四态体制 label（`VALUE_BULL`、`SENTIMENT_BULL`、`PANIC_BOTTOM`、`OVERVALUATION_RISK`、`NEUTRAL`）及对应 Utilization Rate 区间。

#### Scenario: Value Bull classification
- **WHEN** equity_bond_signal = `UNDERVALUED`，margin_signal = `NORMAL`，qvix_signal < 20
- **THEN** 返回 `VALUE_BULL`，Utilization = (0.80, 1.00)

#### Scenario: QVIX absent — classification with 2 signals
- **WHEN** qvix_signal = None
- **THEN** 函数仅基于 equity_bond_signal 和 margin_signal 进行分类，不因 QVIX 缺失而抛出异常

### Requirement: China Layer 3 Sentinel Evaluation Function
系统 SHALL 提供函数 `evaluate_china_sentinels(market_data: ChinaDailySentinelData, current_state: ChinaSentinelState) -> ChinaSentinelState`，评估 5 个 A 股哨兵并返回更新后的状态（含 hold-down 逻辑）。

#### Scenario: Limit-down panic triggers and persists
- **WHEN** market_data.limit_down_count > 50 且 current_state.LIMIT_DOWN_PANIC = CLEAR
- **THEN** 返回状态中 LIMIT_DOWN_PANIC = TRIGGERED，trigger_date = today

#### Scenario: Hold-down prevents early reset
- **WHEN** current_state.LIMIT_DOWN_PANIC = TRIGGERED，current_date - trigger_date < 3 个交易日
- **THEN** 无论当日跌停数是否低于阈值，状态保持 TRIGGERED

#### Scenario: Auto-reset after hold-down
- **WHEN** current_state.LIMIT_DOWN_PANIC = TRIGGERED，current_date - trigger_date ≥ 3 个交易日，且触发条件已不满足
- **THEN** 状态转为 CLEAR

### Requirement: China Target Position Envelope Function
系统 SHALL 提供纯函数 `compute_china_envelope(l1_result, l2_result, l3_state) -> ChinaEnvelopeResult`，根据三层结果合成 Target Position Envelope（min%、max%），并标记是否处于 emergency override 模式。

#### Scenario: Normal mode synthesis
- **WHEN** l1.ceiling = 0.60，l2.utilization_range = (0.80, 1.00)，l3 全 CLEAR
- **THEN** 返回 target_min = 0.48，target_max = 0.60，mode = `NORMAL`

#### Scenario: Multi-sentinel emergency override
- **WHEN** l3_state 包含 2 个及以上 TRIGGERED 哨兵
- **THEN** 返回 target_max = l1.ceiling × 0.50，mode = `EMERGENCY`

### Requirement: China Regime History Writer
系统 SHALL 提供函数 `write_china_regime_snapshot(date, l1_result, l2_result, l3_state, envelope, csi300_close)`，将日度快照追加写入 `data_cache/china_regime_history.csv`。

#### Scenario: Snapshot appended correctly
- **WHEN** 函数被调用且 history 文件存在
- **THEN** 新行以正确字段追加，不覆盖历史记录

#### Scenario: File creation on first run
- **WHEN** `china_regime_history.csv` 不存在
- **THEN** 函数创建文件并写入表头，然后追加首行数据

## MODIFIED Requirements

### Requirement: China Macro Analysis
系统 SHALL 将 `analyze_china_signals()` 的调用点替换为 `compute_china_regime()`，后者内部依次调用 Layer 1、Layer 2、Layer 3 函数并合成 Envelope，返回统一的 `ChinaRegimeResult` 对象供 Dashboard 消费。

原有 M1-M2 差值计算逻辑 SHALL 迁移至 `compute_china_layer1()` 内部，不再作为独立函数直接被 Dashboard 调用。

#### Scenario: compute_china_regime returns structured result
- **WHEN** Dashboard 调用 `compute_china_regime(data)`
- **THEN** 返回包含 `l1`、`l2`、`l3`、`envelope`、`indicator_values` 字段的对象

#### Scenario: Backward compat — existing M1-M2 value still accessible
- **WHEN** 任何现有代码读取 M1-M2 差值
- **THEN** 该值可从 `result.l1.signal_values["m1_m2_spread"]` 读取，不破坏现有图表
