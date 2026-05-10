# position-advisor Specification

## Purpose
TBD - created by archiving change add-regime-scoring-engine. Update Purpose after archive.
## Requirements
### Requirement: Portfolio CSV Upload and Parsing
系统 SHALL 接收用户 portfolio 持仓 CSV 上传，字段包括：ticker、type、shares_or_contracts、cost_basis、current_price、market_value、notional_exposure、sector、conviction（S/A/B/C/Hedge）、beta_spx、underlying（options）、expiry（options）。系统 SHALL 同时接收 total_value 与 cash 两个独立输入。

#### Scenario: Valid CSV upload
- **WHEN** 用户上传包含全部必填字段且数据类型有效的 CSV
- **THEN** portfolio 被解析为结构化 holding 记录用于分析

#### Scenario: Invalid CSV format
- **WHEN** 上传的 CSV 缺少必填字段或包含无效数据
- **THEN** 展示清晰错误信息并列出具体问题

### Requirement: Risk Exposure Calculation
系统 SHALL 将 total Risk Exposure 计算为所有非 Hedge 持仓的 notional_exposure 之和。conviction = "Hedge" 的持仓 SHALL 从 risk exposure 与 trim 优先级计算中排除。当前仓位百分比 = Risk Exposure / Total Account Value。

#### Scenario: Hedge positions excluded
- **WHEN** portfolio 中包含 conviction = "Hedge" 的保护性 put
- **THEN** 这些持仓不计入 risk exposure 计算

#### Scenario: Current position percentage
- **WHEN** risk exposure 为 $70,000 且 total account value 为 $100,000
- **THEN** 当前仓位百分比为 70%

### Requirement: Conviction-Regime Position Limits
系统 SHALL 基于可配置 Conviction × L2 Regime 矩阵执行单持仓最大仓位限制。超过上限的持仓 SHALL 被建议 trim。上限为 0% 的持仓 SHALL 被建议 close。

#### Scenario: Low conviction in risk-off regime
- **WHEN** 某持仓 conviction = "C" 且 L2 regime 为 RISK_OFF
- **THEN** 该持仓上限为 0%，并被建议 CLOSE

#### Scenario: High conviction in strong risk-on regime
- **WHEN** 某持仓 conviction = "S" 且 L2 regime 为 STRONG_RISK_ON
- **THEN** 该持仓上限为 25%

### Requirement: Trim Priority Sorting
当当前 exposure 超过 Target Max 时，系统 SHALL 按以下顺序对待减仓持仓排序：(1) Conviction 升序（C → B → A → S），(2) conviction 相同则 Beta 降序（先减高波动），(3) conviction 与 beta 都相同则 unrealized gain percentage 降序（先减盈利仓以提升税务效率）。

#### Scenario: Trim priority ordering
- **WHEN** portfolio 处于 overweight，且同时有 C-conviction 与 S-conviction 股票
- **THEN** C-conviction 股票在 trim 优先级列表中排在 S-conviction 之前

#### Scenario: Same conviction tiebreak by beta
- **WHEN** 存在两个 B-conviction 持仓，beta 分别为 1.8 和 0.9
- **THEN** beta=1.8 的持仓优先被 trim

### Requirement: Regime-Specific Rules
系统 SHALL 根据当前 regime 状态执行自动规则。

#### Scenario: Options cap in contracting liquidity
- **WHEN** L1 regime 为 CONTRACTING 或 SEVERE_CONTRACTION
- **THEN** total options notional exposure SHALL 限制在 portfolio value 的 10% 以内
- **AND** 禁止使用 leverage/margin

#### Scenario: Severe contraction S-only rule
- **WHEN** L1 regime 为 SEVERE_CONTRACTION
- **THEN** 仅保留 S-conviction 持仓；其余全部建议 CLOSE

#### Scenario: MOVE Spike freeze
- **WHEN** L3 Bond Vol Spike sentinel 处于 TRIGGERED
- **THEN** 不允许新增仓位（FREEZE action）
- **AND** 现有持仓不受影响

#### Scenario: Any L3 sentinel triggered
- **WHEN** 任一带 forced_ceiling 的 L3 sentinel 处于 TRIGGERED
- **THEN** 系统进入 emergency mode 并仅保留核心持仓

### Requirement: Position Action Types
每个 holding SHALL 严格获得一个 action 建议：CLOSE（全部清仓）、TRIM（部分减仓至目标）、HOLD（维持当前）、或 ADD（低配时加仓）。

#### Scenario: Generate TRIM recommendation
- **WHEN** 某持仓当前占比超过其 conviction-regime 上限
- **THEN** action 为 TRIM，目标占比等于该上限

#### Scenario: Generate ADD recommendation
- **WHEN** 当前总 exposure 低于 Target Min 且某持仓低于其上限
- **THEN** action 为 ADD

### Requirement: Position Advisory Output
系统 SHALL 为每个 holding 输出结构化结果，包含：priority rank、ticker、conviction、current percentage、target percentage、action type、adjustment amount（USD）和 reason。系统 SHALL 同时输出当前生效的 regime 规则列表。

#### Scenario: Complete advisory output
- **WHEN** portfolio 当前 70% 且 Target Max 为 51%（即 overweight）
- **THEN** 输出包含 is_overweight = true、excess_dollars > 0，以及按优先级排序的 trim/close 持仓列表

