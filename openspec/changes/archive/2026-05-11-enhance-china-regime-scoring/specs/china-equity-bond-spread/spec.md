## ADDED Requirements

### Requirement: Compute Daily Equity-Bond Yield Spread
系统 SHALL 每日计算 A 股股债利差 = 沪深300盈利收益率（1 ÷ PE_TTM）- 10年期中国国债收益率，单位为百分比，存入 `data_cache/china/equity_bond_spread.csv`。

数据来源：
- 沪深300 PE TTM：Tushare `index_dailybasic`（ts_code=`399300.SZ`），有约 1 日滞后
- 10年期中国国债收益率：Tushare 宏观接口 `cn_bond_price` 或 `pro.yield_curve`

#### Scenario: Successful computation
- **WHEN** 当日沪深300 PE TTM 和 10Y CGB 收益率均可获取
- **THEN** 系统计算 `spread = (1 / PE_TTM) * 100 - bond_yield_pct`，写入缓存

#### Scenario: PE data has 1-day lag
- **WHEN** 当日 PE TTM 数据尚未发布（T 日收盘后约 1 日滞后）
- **THEN** 使用 T-1 日 PE TTM 计算利差，并在 UI 数据时效说明中标注"PE 数据含1日滞后"

#### Scenario: Cache hit skips API call
- **WHEN** 今日利差条目已存在于缓存
- **THEN** 直接读取缓存，不调用 Tushare

#### Scenario: Bond yield fetch failure
- **WHEN** 国债收益率 API 失败
- **THEN** 返回最近一个有效利差值并传递 `data_stale=True`；不使 pipeline 崩溃

### Requirement: Historical Reference Levels for Equity-Bond Spread
系统 SHALL 在折线图中标注三个历史牛市起点参考水位：
- 2008 年底牛市起点（历史最高利差，约 8%–10%）
- 2014 年底牛市起点
- 2022 年底低点

#### Scenario: Reference lines rendered
- **WHEN** 渲染股债利差折线图
- **THEN** 图表叠加三条虚线参考水位（2008、2014、2022），并标注对应值

#### Scenario: Latest value card shows valuation interpretation
- **WHEN** 渲染最新值卡片
- **THEN** 卡片显示当前利差值，并附文字（"> 3%：A 股低估，配置价值高" / "1%–3%：中性" / "< 1%：A 股相对高估"）

### Requirement: Equity-Bond Spread Layer 2 Signal Classification
系统 SHALL 将当前股债利差映射为体制信号：`UNDERVALUED`（> 3%）、`NEUTRAL`（1%–3%）、`OVERVALUED`（< 1%），供 Layer 2 体制分类使用。

#### Scenario: Undervalued signal
- **WHEN** 当前股债利差 > 3%
- **THEN** 输出 `UNDERVALUED`；在 Layer 2 估值维度得分为 +1

#### Scenario: Overvalued signal
- **WHEN** 当前股债利差 < 1%
- **THEN** 输出 `OVERVALUED`；在 Layer 2 估值维度得分为 -1

#### Scenario: Neutral signal
- **WHEN** 当前股债利差在 1%–3% 范围内
- **THEN** 输出 `NEUTRAL`；在 Layer 2 估值维度得分为 0
