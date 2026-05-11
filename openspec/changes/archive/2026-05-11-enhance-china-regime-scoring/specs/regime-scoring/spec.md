## ADDED Requirements

### Requirement: China Layer 1 Liquidity Floor Scoring
系统 SHALL 评估 4 个 A 股流动性基底信号（DR007偏差、M1 YoY、M1-M2 增速差、TSF增速），每项打分 +1/0/-1，求和得到 L1 Composite Score（-4 到 +4），映射为 Position Ceiling。

信号与判断方向：
- DR007 偏差：DR007 持续低于 OMO 利率 → +1（宽松）；高于 → -1（偏紧）
- M1 YoY：M1 同比转正或加速 → +1；持续负增长 → -1
- M1-M2 增速差：差值收窄或转正 → +1；持续扩大负值 → -1
- TSF 增速：社融同比加速 → +1；减速 → -1

#### Scenario: Full bullish L1
- **WHEN** 全部 4 个 L1 信号评分均为 +1（Composite = +4）
- **THEN** Position Ceiling 为 80%，L1 Regime 标记为 `EXPANSIONARY`

#### Scenario: Mixed L1 signals
- **WHEN** L1 Composite Score 在 0 到 +2 范围内
- **THEN** Position Ceiling 为 60%，L1 Regime 标记为 `NEUTRAL`

#### Scenario: Bearish L1
- **WHEN** L1 Composite Score ≤ -2
- **THEN** Position Ceiling 为 40%，L1 Regime 标记为 `CONTRACTING`

#### Scenario: L1 data failure graceful degradation
- **WHEN** 某个 L1 信号数据获取失败
- **THEN** 该信号得分默认为 0（neutral），其余信号继续评估

### Requirement: China Layer 2 Market Regime Classification
系统 SHALL 基于股债利差、两融余额市值比和 QVIX（可选）信号，将 A 股市场体制分类为四种命名状态之一，并输出对应的 Utilization Rate 区间。

四种体制状态与触发条件：
- `VALUE_BULL`：股债利差 `UNDERVALUED` + 两融比 `NORMAL` or `COLD` + QVIX < 20（或缺失）→ Utilization 80%–100%
- `SENTIMENT_BULL`：股债利差 `NEUTRAL`/`UNDERVALUED` + 两融比 `OVERHEATED` + QVIX < 25 → Utilization 60%–80%
- `PANIC_BOTTOM`：股债利差 `UNDERVALUED` + QVIX > 30 → Utilization 40%–60%（左侧机会）
- `OVERVALUATION_RISK`：股债利差 `OVERVALUED` + 两融比 `OVERHEATED` → Utilization 20%–40%

默认（不满足任何明确分类）：`NEUTRAL` → Utilization 50%–70%

北向资金净流入方向（via Tushare `pro.moneyflow_hsgt`）作为辅助调整信号，在四态分类确定后对 Utilization Rate 的上下限进行微调（±5%）：持续净流入 → +5%；持续净流出 → -5%；方向不明确 → 不调整。

#### Scenario: Value Bull classification
- **WHEN** 股债利差 > 3% 且两融余额市值比 < 2.5% 且 QVIX < 20（或 QVIX 数据不可用）
- **THEN** L2 Regime 为 `VALUE_BULL`，Utilization Rate 区间 80%–100%

#### Scenario: Overvaluation Risk classification
- **WHEN** 股债利差 < 1% 且两融余额市值比 > 2.5%
- **THEN** L2 Regime 为 `OVERVALUATION_RISK`，Utilization Rate 区间 20%–40%

#### Scenario: Panic Bottom classification
- **WHEN** 股债利差 > 3% 且 QVIX > 30
- **THEN** L2 Regime 为 `PANIC_BOTTOM`，Utilization Rate 区间 40%–60%

#### Scenario: QVIX unavailable fallback
- **WHEN** QVIX 数据不可用
- **THEN** 忽略 QVIX 维度，仅用股债利差与两融比决定体制分类；记录 warning 日志

#### Scenario: Northbound flow adjusts utilization upward
- **WHEN** 北向资金过去 5 个交易日累计净流入为正，且绝对值超过 20 亿元
- **THEN** 在四态分类确定的 Utilization Rate 上下限基础上各加 5 个百分点（不超过 100%）

#### Scenario: Northbound flow adjusts utilization downward
- **WHEN** 北向资金过去 5 个交易日累计净流入为负，且绝对值超过 20 亿元
- **THEN** 在四态分类确定的 Utilization Rate 上下限基础上各减 5 个百分点（不低于 0%）

#### Scenario: Northbound flow data unavailable fallback
- **WHEN** Tushare 北向资金数据获取失败
- **THEN** 北向资金调整项默认为 0（不调整 Utilization），记录 warning 日志，四态分类不受影响

### Requirement: China Layer 3 Instant Sentinel Triggers
系统 SHALL 监控 5 个 A 股日度哨兵信号，触发时向 Dashboard 传递警告状态，并降低 Target Position Envelope。所有哨兵触发后保持至少 3 个交易日（hold-down），状态持久化到 `data_cache/china_sentinel_state.json`。

| 哨兵名称 | 触发条件 | 效果 |
|----------|----------|------|
| `LIMIT_UP_HEAT` | 当日涨停股数量 > 200 | 情绪过热；Envelope 降低 10% |
| `LIMIT_DOWN_PANIC` | 当日跌停股数量 > 50 | 恐慌信号；Envelope 降低 15% |
| `ZT_DT_EXTREME` | ZT/DT 比率 > 10 或 < 0.2 | 极端单边情绪；Envelope 降低 10% |
| `SOUTHBOUND_SURGE` | 南向单日净买额 > 历史均值 +2σ 或 < -2σ | 港资异动；Envelope 降低 10% |
| `VOLUME_SPIKE` | 全市场成交额 > 20日均值 × 1.5 | 量价异常；Envelope 降低 5% |

多哨兵同时触发：Envelope 强制降至 Layer 1 Ceiling × 50%。

#### Scenario: Limit-up heat sentinel triggers
- **WHEN** 当日涨停股数量 > 200 且 `LIMIT_UP_HEAT` 哨兵当前为 CLEAR
- **THEN** 哨兵转为 TRIGGERED，当日 Target Position Envelope 降低 10%

#### Scenario: Sentinel hold-down prevents premature reset
- **WHEN** `LIMIT_DOWN_PANIC` 处于 TRIGGERED，且触发条件在次日已不满足（跌停数恢复正常），但未满 3 个交易日
- **THEN** 哨兵保持 TRIGGERED，继续降低 Envelope

#### Scenario: Sentinel state persists across restarts
- **WHEN** `LIMIT_DOWN_PANIC` 处于 TRIGGERED，应用重启
- **THEN** 哨兵以 TRIGGERED 状态加载，原始触发时间戳保留

#### Scenario: Multiple sentinels take compound reduction
- **WHEN** `LIMIT_DOWN_PANIC` 和 `SOUTHBOUND_SURGE` 同时 TRIGGERED
- **THEN** Target Position Envelope 强制降至 Layer 1 Ceiling 的 50%

#### Scenario: Data completeness check prevents false trigger
- **WHEN** 当日涨停计数数据返回值 < 5（不合理低值，疑似数据缺失）
- **THEN** `LIMIT_UP_HEAT` 哨兵保持 CLEAR，记录 warning 日志

### Requirement: China Target Position Envelope Synthesis
系统 SHALL 合成 A 股 Target Position Envelope：

```
Target Position Envelope = Layer1 Ceiling × Layer2 Utilization Rate Range
                          经 Layer3 Sentinel Override 修正
```

Sentinel Override 规则：
- 单哨兵触发：Envelope 降低 10%–15%（按哨兵定义的降幅）
- 多哨兵同时触发：强制降至 Layer 1 Ceiling × 50%
- 无哨兵：不修正

#### Scenario: Normal mode synthesis
- **WHEN** L1 = NEUTRAL（Ceiling 60%）、L2 = VALUE_BULL（Utilization 80%–100%）、L3 全 CLEAR
- **THEN** Target Min = 48%，Target Max = 60%

#### Scenario: Sentinel override in emergency mode
- **WHEN** 多个哨兵同时 TRIGGERED，L1 Ceiling = 60%
- **THEN** Target Position Envelope 上限强制降至 30%（60% × 50%）

#### Scenario: Full bullish envelope
- **WHEN** L1 = EXPANSIONARY（80%）、L2 = VALUE_BULL（80%–100%）、L3 全 CLEAR
- **THEN** Target Max = 80%

### Requirement: China Regime History Persistence
系统 SHALL 在每次评分后将 A 股日度快照追加写入 `data_cache/china_regime_history.csv`，字段包括：date、L1_regime、L2_regime、L3_active_sentinels、target_min、target_max、csi300_close。

#### Scenario: First run creates history file
- **WHEN** `china_regime_history.csv` 不存在
- **THEN** 系统创建带表头的文件并写入首日快照

#### Scenario: History used for 12-month regime timeline
- **WHEN** Dashboard 渲染 A 股体制时间轴
- **THEN** 从 history CSV 读取过去 12 个月的日度记录，生成体制色带

## MODIFIED Requirements

### Requirement: China Macro Analysis
系统 SHALL 替换原有 `analyze_china_signals()` 两信号平坦规则，使用新的三层评分框架 `compute_china_regime()` 作为 China 模块的主评分入口。原有 M1-M2 差值计算逻辑 SHALL 保留并迁移至 Layer 1 信号之一（M1-M2 增速差）。

#### Scenario: Three-layer output replaces two-signal output
- **WHEN** China 模块请求体制评分
- **THEN** 系统调用 `compute_china_regime()`，返回包含 L1/L2/L3 结果及 Target Position Envelope 的结构化对象
- **AND** 旧的 `analyze_china_signals()` 不再作为主评分函数被 Dashboard 调用

#### Scenario: M1-M2 signal preserved in Layer 1
- **WHEN** Layer 1 评分计算
- **THEN** M1-M2 增速差信号仍参与 Layer 1 Composite 计算

