# china-equity-bond-spread Specification

## Purpose
描述 A 股股债利差（Equity-Bond Yield Spread = 沪深300盈利收益率 - 10Y 国债收益率）的数据获取、历史 backfill、图表锚点与体制评分分类逻辑。

## Requirements

### Requirement: Compute Daily Equity-Bond Yield Spread

系统 SHALL 每日计算 A 股股债利差 = 沪深300盈利收益率（1 ÷ PE_TTM）- 10年期中国国债收益率，单位为百分比，存入 `data_cache/china/equity_bond_spread.csv`。

数据来源：
- 沪深300 PE TTM：Tushare `pro.index_dailybasic`（ts_code=`000300.SH`），有约 1 日滞后
- 10年期中国国债收益率：AkShare `ak.bond_china_yield`（中债国债收益率曲线，10年列），非 Tushare

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

### Requirement: Historical Backfill from 2015

系统 SHALL 在首次加载时自动 backfill 2015-01-01 至今的股债利差历史数据。

Backfill 实现约束（见 data-ingestion spec 中"API Row-Count and Date-Range Constraints"）：
- `pro.index_dailybasic`（CSI300 PE）无行数截断问题，可一次性批量获取 2015-今（约 2755 行）
- `ak.bond_china_yield` 单次调用日期范围必须 < 1 年，必须按年分批并 concat

#### Scenario: Backfill on empty cache

- **WHEN** 缓存为空或最早日期晚于 2015-01-01
- **THEN** 系统自动执行 backfill，写入 2015-01-05（首个交易日）至今的日频数据，约 2700+ 行

#### Scenario: 2015 bull peak verifiable

- **WHEN** backfill 完成后检查 2015-06-15 数据
- **THEN** 该日股债利差应在 1.6%–1.9% 范围内（历史实测值约 1.67%）

### Requirement: Bull Market Reference Anchors

系统 SHALL 在图表中以**空心圆圈标记**（`circle-open`）标注以下历史牛市峰值锚点，替代原水平虚线：

| 锚点名称 | 日期 | 参考值 |
|---------|------|--------|
| 2008年牛市 | 2008-01-14 | -2.22% |
| 2015年牛市 | 2015-06-15 | 1.81% |
| 2021年牛市 | 2021-02-18 | 2.63% |

注：2008 锚点早于历史数据起点（2015），在 15Y 以内视图中均不可见，图表应自动跳过。

#### Scenario: Anchor markers rendered

- **WHEN** 系统渲染股债利差折线图
- **THEN** 图表在对应日期位置显示空心圆圈 + 标注文字
- **AND** 若锚点日期不在当前时间范围，则自动跳过，不报错

#### Scenario: Distance cards show latest vs anchors

- **WHEN** 渲染最新值区域
- **THEN** 渲染 N+1 列卡片（N = 时间范围内可见的锚点数量，最后一列为最新值）

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
