## ADDED Requirements

### Requirement: Configurable Scoring Parameters
系统 SHALL 在启动时从 YAML 配置文件加载所有评分阈值、权重以及 regime-to-ceiling/utilization 映射。任何阈值或权重值 SHALL NOT 进行 hardcoding。

#### Scenario: Load default configuration
- **WHEN** 应用启动且不存在 override 文件
- **THEN** 所有层均使用 `config/regime_defaults.yaml` 的默认值

#### Scenario: Override configuration
- **WHEN** 应用启动且存在 `config/regime_overrides.yaml`
- **THEN** override 值合并覆盖默认配置
- **AND** 合并后配置在加载时完成校验

### Requirement: Layer 1 Liquidity Foundation Scoring
系统 SHALL 评估 4 个宏观流动性指标（Net Liquidity Trend、TGA Trend、RRP Buffer、Policy Rate Direction），每项打分为 +1/0/-1，并求和得到 Composite Score（-4 到 +4），再映射为 regime label 与 Position Ceiling 百分比。

#### Scenario: Net Liquidity Trend scoring
- **WHEN** Net Liquidity 的 20DMA 连续 ≥ N 周上升（默认 3 周），且周增幅 > 阈值（默认 0.5%/week）
- **THEN** Net Liquidity Trend 得分为 +1

#### Scenario: TGA Trend scoring with inverted direction
- **WHEN** 在回看窗口（默认 21 个交易日）内，TGA 余额下降幅度超过下跌阈值（默认 -5%）
- **THEN** TGA Trend 得分为 +1（TGA 下降 = 流动性释放 = bullish）

#### Scenario: RRP Buffer scoring by absolute level
- **WHEN** RRP 余额高于高阈值（默认 $200B）
- **THEN** RRP Buffer 得分为 +1

#### Scenario: Policy Rate Direction scoring
- **WHEN** 当前 SOFR/EFFR 相比 63 个交易日前下降 ≥ 10bp
- **THEN** Policy Rate Direction 得分为 +1

#### Scenario: Composite score maps to EXPANSIONARY regime
- **WHEN** L1 Composite Score ≥ 3
- **THEN** L1 regime 为 EXPANSIONARY，Position Ceiling 为 100%

#### Scenario: Composite score maps to SEVERE CONTRACTION regime
- **WHEN** L1 Composite Score ≤ -2
- **THEN** L1 regime 为 SEVERE_CONTRACTION，Position Ceiling 为 40%

#### Scenario: L1 update frequency
- **WHEN** 新的周度数据到达（周五收盘后）
- **THEN** 重新计算 L1 分数

### Requirement: Layer 2 Market Regime Scoring
系统 SHALL 评估 8 个 market regime 指标，每项打分 +1/0/-1，应用可配置权重后求和为 Weighted Composite（-8.0 到 +8.0），再映射为 regime label 与 Utilization Rate 区间。

#### Scenario: SPX vs 50DMA scoring
- **WHEN** SPX 高于其 50-day moving average 超过 1%
- **THEN** SPX vs 50DMA 得分为 +1

#### Scenario: Market Breadth (S5FI) scoring
- **WHEN** S5FI 近似值超过 60%
- **THEN** Market Breadth 得分为 +1

#### Scenario: VIX Level scoring
- **WHEN** VIX 低于 18
- **THEN** VIX Level 得分为 +1

#### Scenario: DXY Trend non-linear scoring
- **WHEN** DXY 月度变化为温和下跌（处于正常范围）
- **THEN** DXY Trend 得分为 +1
- **WHEN** DXY 月度变化超过 +2% 或低于 -3%
- **THEN** DXY Trend 得分为 -1（任一方向的极端波动都视作 risk-off）

#### Scenario: Weighted composite maps to STRONG RISK-ON
- **WHEN** L2 Weighted Composite ≥ 5.0
- **THEN** L2 regime 为 STRONG_RISK_ON，Utilization Range 为 90%-100%

#### Scenario: Weighted composite maps to STRONG RISK-OFF
- **WHEN** L2 Weighted Composite ≤ -5.0
- **THEN** L2 regime 为 STRONG_RISK_OFF，Utilization Range 为 0%-20%

#### Scenario: L2 update frequency
- **WHEN** 日度市场数据刷新（收盘后）
- **THEN** 重新计算 L2 分数

### Requirement: Layer 3 Sentinel Circuit Breakers
系统 SHALL 监控 4 个二元 sentinel（VIX Spike、Credit Break、Bond Vol Spike、Trend Break）；当触发时可覆盖 L1×L2 envelope。Sentinel 采用非对称触发/重置逻辑：单条件可即时触发，但重置需所有重置条件在连续多个交易日内同时满足。

#### Scenario: VIX Spike triggers
- **WHEN** VIX 超过 35 且 VIX Spike sentinel 为 CLEAR
- **THEN** sentinel 转为 TRIGGERED，并设置 forced_ceiling = 20%

#### Scenario: VIX Spike reset requires consecutive days
- **WHEN** VIX Spike 处于 TRIGGERED，且 VIX 仅 1 天收于 25 以下
- **THEN** sentinel 保持 TRIGGERED（不重置）

#### Scenario: VIX Spike resets after consecutive days met
- **WHEN** VIX Spike 处于 TRIGGERED，且 VIX 连续 3 天收于 25 以下
- **THEN** sentinel 转为 CLEAR

#### Scenario: Credit Break triggers on JNK or HYG
- **WHEN** JNK 或 HYG 单日收益低于 -1.5%
- **THEN** Credit Break sentinel 转为 TRIGGERED，并设置 forced_ceiling = 20%

#### Scenario: Bond Vol Spike triggers freeze mode
- **WHEN** MOVE 指数超过 130
- **THEN** Bond Vol Spike sentinel 转为 TRIGGERED，action = FREEZE（禁止新开仓、现有仓位不受影响、无 forced_ceiling）

#### Scenario: Trend Break triggers on compound condition
- **WHEN** 同一天内 SPX 收于 50DMA 下方且 VIX 超过 25
- **THEN** Trend Break sentinel 转为 TRIGGERED，并设置 forced_ceiling = 20%

#### Scenario: Trend Break reset requires three simultaneous conditions
- **WHEN** Trend Break 处于 TRIGGERED，且连续 3 天同时满足 SPX 收于 50DMA 上方、VIX < 22、S5FI > 50%
- **THEN** sentinel 转为 CLEAR

#### Scenario: Multiple sentinels take minimum forced ceiling
- **WHEN** VIX Spike（forced_ceiling=20%）与 Credit Break（forced_ceiling=20%）同时 TRIGGERED
- **THEN** override ceiling 为 20%（所有非空 forced_ceilings 的最小值）

### Requirement: Sentinel State Persistence
系统 SHALL 在每次评分后将 sentinel 状态（status、trigger timestamp、cooling day counter）持久化到 `data_cache/sentinel_state.json`，并在启动时恢复。

#### Scenario: State survives restart
- **WHEN** 昨日 VIX Spike 处于 TRIGGERED，且应用今日重启
- **THEN** 该 sentinel 以 TRIGGERED 状态加载，并保留原始 trigger timestamp

#### Scenario: Corrupted state file resets to safe default
- **WHEN** sentinel 状态文件损坏或不可读
- **THEN** 所有 sentinel 初始化为 CLEAR，并记录 warning 日志

### Requirement: Sentinel Three-State Model
每个 sentinel SHALL 严格包含三种状态：CLEAR（正常、无影响）、TRIGGERED（紧急措施生效）、COOLING（触发条件已解除但重置条件尚未完全满足，紧急措施仍生效）。

#### Scenario: Transition from TRIGGERED to COOLING
- **WHEN** sentinel 处于 TRIGGERED，且触发条件已不再满足，但重置条件尚未完全满足
- **THEN** sentinel 转为 COOLING，且紧急措施继续生效

### Requirement: Target Position Envelope Computation
系统 SHALL 计算 Target Position Envelope：在 normal mode 下使用 L1 Ceiling × L2 Utilization Range；在 emergency mode 下应用 L3 override。

#### Scenario: Normal mode envelope
- **WHEN** L1 = CONTRACTING（Ceiling 60%）、L2 = RISK_ON（Utilization 70%-85%）、L3 = all CLEAR
- **THEN** Target Min = 42%，Target Max = 51%

#### Scenario: Emergency mode envelope
- **WHEN** 任一 L3 sentinel 的 forced_ceiling 为 20%
- **THEN** 无论 L1 与 L2 取值如何，Target Min = 0%，Target Max = 20%
- **AND** envelope mode 标记为 EMERGENCY

#### Scenario: Full bullish envelope
- **WHEN** L1 = EXPANSIONARY（100%）、L2 = STRONG_RISK_ON（90%-100%）、L3 = all CLEAR
- **THEN** Target Max ≥ 90%

### Requirement: Regime History Persistence
系统 SHALL 在每次评分后将日度快照（date、L1 regime、L2 regime、L3 events、target min、target max、SPX close）追加写入 `data_cache/regime_history.csv`，用于 timeline 可视化。

#### Scenario: First deployment has no history
- **WHEN** regime history 文件不存在
- **THEN** 创建带表头的文件并写入首日快照

#### Scenario: History accumulates over time
- **WHEN** scoring engine 在新的交易日运行
- **THEN** 向 history CSV 追加一行新记录

### Requirement: Single Indicator Failure Graceful Degradation
系统 SHALL 将任何数据拉取失败的指标记为 0（neutral），且不得导致引擎崩溃，以保证其余指标仍可继续评估。

#### Scenario: One data source fails
- **WHEN** RRP 数据源失败，但其他 L1 数据可用
- **THEN** RRP Buffer 分数默认为 0，L1 评分使用其余 3 个指标继续执行
