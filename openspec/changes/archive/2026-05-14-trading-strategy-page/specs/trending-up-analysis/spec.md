## ADDED Requirements

### Requirement: TrendingUpAnalyzer 为纯函数
`TrendingUpAnalyzer.analyze(df: pd.DataFrame) -> TrendAnalysis` SHALL 是纯函数，无 I/O 副作用。输入为包含 OHLCV 日线数据的 DataFrame（至少 120 行），输出为 `TrendAnalysis` dataclass。None/空 DataFrame 输入时返回带 `data_insufficient=True` 的默认 TrendAnalysis，不抛异常。

#### Scenario: Valid input produces full analysis
- **WHEN** 输入包含至少 120 行 OHLCV 数据的合法 DataFrame
- **THEN** 返回包含所有字段的 TrendAnalysis，`data_insufficient=False`

#### Scenario: None input handled gracefully
- **WHEN** 输入为 None 或空 DataFrame
- **THEN** 返回 `TrendAnalysis(data_insufficient=True)`，不抛异常

### Requirement: 趋势确认清单（6项）
系统 SHALL 计算并输出以下 6 项布尔型趋势确认信号：
1. `price_above_ma20: bool` — 最新收盘价 > MA20
2. `ma_bullish_alignment: bool` — MA20 > MA60 > MA120（均线多头排列）
3. `adx_strong: bool` — ADX(14) > 25
4. `higher_lows: bool` — 最近 3 次回调低点逐次抬高（回看 60 日）
5. `pullback_volume_shrink: bool` — 最近回调时成交量低于 MA20 成交量
6. `rsi_healthy: bool` — RSI(14) 在 40–70 之间（非超买超卖）

`trend_score: int` = 满足项数（0–6）。

#### Scenario: Full bull trend
- **WHEN** 6 项全部满足
- **THEN** `trend_score=6`，`is_uptrend=True`

#### Scenario: Weak or no trend
- **WHEN** 满足项数 ≤ 2
- **THEN** `is_uptrend=False`，建议策略为"不符合趋势条件，暂不操作"

### Requirement: 趋势阶段判断
系统 SHALL 将当前行情归类为以下 5 个阶段之一：

| 阶段 | 英文 key | 判断逻辑 |
|------|----------|----------|
| 突破期 | `breakout` | 价格突破近 20 日高点 + 成交量 ≥ MA20量 × 1.5 |
| 回踩期 | `pullback` | 价格位于 MA20 ±3% 区间 + 成交量萎缩至 MA20量 × 0.8 以下 |
| 整固期 | `consolidation` | 连续 5–15 日最高-最低价幅度 ≤ 5% + ADX 趋平 |
| 加速期 | `acceleration` | 价格偏离 MA20 超 15% 且 RSI > 70 |
| 衰竭期 | `topping` | 出现天量滞涨（量创新高但价不创新高）或 RSI 顶背离 |

当多个条件同时满足时，优先级：衰竭期 > 加速期 > 回踩期 > 突破期 > 整固期。

#### Scenario: Pullback phase detection
- **WHEN** 收盘价在 MA20 ±3% 区间且成交量 < MA20量 × 0.8
- **THEN** `trend_phase="pullback"`，recommended_strategy 为"策略2：回踩均线买入"

#### Scenario: Acceleration phase - no entry
- **WHEN** 收盘价偏离 MA20 超 15% 且 RSI > 70
- **THEN** `trend_phase="acceleration"`，recommended_strategy 为"策略4：不追，等下次回踩"

#### Scenario: Topping signal
- **WHEN** 当日成交量创 20 日新高但收盘价未创新高（天量不创价）
- **THEN** `trend_phase="topping"`，`exit_warning=True`

### Requirement: 金字塔仓位建议
系统 SHALL 根据建仓次序输出金字塔仓位建议：
- 第 1 次建仓：建议仓位 40% 总资金
- 第 2 次加仓：建议仓位 30%
- 第 3 次加仓：建议仓位 20%
- 第 4 次加仓：建议仓位 10%

输出 `suggested_position_pct: float`（考虑体制乘数后的最终建议仓位比例）。

#### Scenario: First entry in BULL regime
- **WHEN** 建仓次序=1，regime_multiplier=1.0
- **THEN** `suggested_position_pct=0.40`

#### Scenario: Position capped by BULL_WATCH regime
- **WHEN** 建仓次序=1，regime_multiplier=0.75
- **THEN** `suggested_position_pct=0.40 × 0.75 = 0.30`

#### Scenario: Position capped by BEAR regime
- **WHEN** 任意建仓次序，regime_multiplier=0.30
- **THEN** `suggested_position_pct` 不超过总仓位 × 0.30

### Requirement: 止损与止盈目标计算
系统 SHALL 基于最新收盘价计算：
- `stop_loss_price: float` — 入场价 × (1 - 0.065)（默认 -6.5%，趋势确立后跟踪至 MA20）
- `target_price_1: float` — 入场价 × 1.25（+25%，首次减仓 1/4）
- `target_price_2: float` — 入场价 × 1.45（+45%，二次减仓 1/4）
- `trailing_stop_pct: float` — 盈利 >30% 后改为最高价回撤 10%；>50% 后改为 12%

#### Scenario: Initial stop loss
- **WHEN** 用户未持仓（建仓次序=1），入场价=100
- **THEN** `stop_loss_price=93.5`，`target_price_1=125`，`target_price_2=145`

#### Scenario: Trailing stop at profit 35%
- **WHEN** 当前盈利 35%（当前价 135，成本 100）
- **THEN** `trailing_stop_pct=0.10`，trailing stop price = 135 × (1 - 0.10) = 121.5

### Requirement: 衰竭信号清单
系统 SHALL 计算并输出 deal_strategy.md 第五章的 9 项衰竭危险信号，以布尔列表形式输出。触发 ≥ 2 项时 `exit_warning=True`。

信号列表：
1. `exhaustion_vol_no_price`: 天量滞涨
2. `rsi_divergence`: RSI 顶背离（价格新高但 RSI 未创新高）
3. `macd_histogram_shrink`: MACD 柱状体持续缩短（连续 3 日）
4. `steep_slope_acceleration`: 上涨斜率突然变陡（近 5 日涨幅 > 近 20 日日均涨幅 × 3）
5. `gap_up_long_upper_shadow`: 跳空高开后长上影线
6. `below_ma20_no_recovery`: 跌破 MA20 后反抽未能收回
7. `adx_peak_reversal`: ADX > 40 后开始下降
8. `sector_peers_weaker`: 无法从日线数据自动判断，输出 None
9. `fundamental_negative`: 无法从日线数据自动判断，输出 None

#### Scenario: Two exhaustion signals trigger warning
- **WHEN** 计算出 rsi_divergence=True 且 macd_histogram_shrink=True
- **THEN** `exit_warning=True`，UI 展示红色减仓提醒

#### Scenario: One signal not enough for warning
- **WHEN** 只有 exhaustion_vol_no_price=True，其余为 False
- **THEN** `exit_warning=False`，UI 展示黄色关注提示
