# data-ingestion 规范 (Specification)

## Purpose
描述系统如何从 FRED、Yahoo Finance、Tushare Pro 和 AkShare 摄取宏观、市场和中国 A 股数据，并规定各 API 的已知行为约束（行数限制、日期范围限制等）。
## Requirements
### Requirement: Central Bank Data Ingestion
系统必须 (MUST) 从 FRED API 检索关键流动性指标 (liquidity indicators) 的历史数据。

#### Scenario: Fed Balance Sheet
- **当 (WHEN)** 数据管道 (data pipeline) 运行时
- **那么 (THEN)** 它获取 `WALCL`（总资产 / Total Assets）、`RRPONTSYD`（逆回购 / Reverse Repo）和 `WTREGEN`（财政部一般账户 / TGA）
- **并且 (AND)** 将它们标准化为通用的每日时间序列 (time series)

### Requirement: Market Data Ingestion
系统 MUST 从 Yahoo Finance 获取市场价格与成交量数据，覆盖现有 ticker（SPY、VIX、MOVE、HYG、DXY、GOLD、OIL、BTC、US10Y、JNK）以及 regime scoring engine 新增所需 ticker（SPX index、11 个 SPDR 行业 ETF）。

#### Scenario: Fetch Market Indicators
- **WHEN** 数据 pipeline 运行
- **THEN** 系统拉取 SPY、VIX、DX-Y.NYB、GC=F、^MOVE、HYG、JNK、CL=F、BTC-USD、^TNX、^GSPC（SPX）以及 11 个 SPDR 行业 ETF
- **AND** 将这些数据与央行数据日期对齐

### Requirement: Interest Rate Data
系统必须 (MUST) 从 FRED 摄取担保隔夜融资利率 (Secured Overnight Financing Rate / SOFR)。

#### Scenario: 获取 SOFR
- **当 (WHEN)** 数据更新时
- **那么 (THEN)** 从 FRED 获取 `SOFR` 序列并与其他每日数据对齐

### Requirement: Credit Market Data
系统必须 (MUST) 摄取 JNK（SPDR彭博高收益债券ETF / SPDR Bloomberg High Yield Bond ETF）的高收益债券 ETF (High Yield Bond ETF) 数据。

#### Scenario: 获取 JNK
- **当 (WHEN)** 获取市场数据时
- **那么 (THEN)** 从 Yahoo Finance 检索 `JNK` 的每日价格数据

### Requirement: Trading Volume Data
系统必须 (MUST) 摄取标普500 ETF (S&P 500 ETF / SPY) 的交易量数据。

#### Scenario: 获取 SPY 交易量
- **当 (WHEN)** 获取市场数据时
- **那么 (THEN)** 检索并存储 `SPY` 的每日交易量

### Requirement: China Macro Data Ingestion
系统必须 (MUST) 从 AkShare 摄取中国宏观经济指标 (macro-economic indicators)。

#### Scenario: 获取中国宏观指标
- **当 (WHEN)** 数据管道 (data pipeline) 运行时
- **那么 (THEN)** 它获取 DR007（回购利率 / Repo Rate）、OMO/MLF（公开市场操作 / Open Market Operations）、SHIBOR（同业拆借利率 / Interbank Rate）、M1/M2 货币供应量 (Money Supply) 和社会融资 (Social Financing)
- **并且 (AND)** 将它们标准化为通用的每日/每月时间序列

### Requirement: China Market Data Ingestion
系统 MUST 从 Tushare 摄取 A 股市场指标（扩展现有 AkShare 来源，或在 Tushare 已覆盖的字段上迁移至 Tushare）。新增以下数据项：
- 全市场日度成交额（亿元）用于 `VOLUME_SPIKE` 哨兵（`pro.index_dailybasic` total_amount 字段）
- QVIX（A 股期权隐含波动率指数）——若 Tushare 订阅支持（`pro.opt_daily` 或等效）
- 主力资金净流入（用于 Layer 2 辅助信号，`pro.moneyflow_hsgt` 或 `pro.moneyflow`）

#### Scenario: 获取中国市场指标（扩展）
- **WHEN** 数据管道运行
- **THEN** 系统除原有 AkShare 字段外，额外获取全市场成交额、主力资金净流入
- **AND** 若 QVIX 可用，同步获取并缓存

#### Scenario: QVIX unavailable on current subscription
- **WHEN** QVIX 接口因订阅级别不足而返回错误
- **THEN** 系统记录 warning 日志，将 QVIX 标记为 `None`，Layer 2 降级为 2 信号分类

### Requirement: Hong Kong Market Data Ingestion
系统必须 (MUST) 摄取香港市场指标。

#### Scenario: HK Indicators
- **当 (WHEN)** 数据管道 (data pipeline) 运行时
- **那么 (THEN)** 它从 AkShare 获取南向资金流向 (Southbound Fund Flows) 和 AH 股溢价指数 (AH Premium Index)
- **并且 (AND)** 从 Yahoo Finance 获取 USD/CNH 汇率 (exchange rate)

### Requirement: Tushare Margin Balance Data Ingestion
系统 SHALL 通过 Tushare Pro `pro.margin` 接口获取每日全市场融资融券余额（融资余额 + 融券余额），并与通过 `pro.index_dailybasic`（ts_code=`000001.SH` 或全市场汇总）获取的 A 股总市值进行组合，计算两融余额市值比。

#### Scenario: Fetch daily margin balance
- **WHEN** 数据管道运行
- **THEN** 系统调用 `pro.margin(exchange='SSE', trade_date=today)` 和 `pro.margin(exchange='SZSE', trade_date=today)`，合并沪深两市余额
- **AND** 获取当日 A 股总市值（来自 `pro.index_dailybasic` 全市场汇总字段 `total_mv`）
- **AND** 计算比率并写入 `data_cache/china/margin_ratio.csv`

#### Scenario: Margin data not yet published on same day
- **WHEN** 当日融资融券数据尚未发布（T 日数据通常于 T+1 发布）
- **THEN** 系统使用 T-1 日数据，并向 UI 传递 `data_date` 字段反映实际数据日期

### Requirement: Tushare CSI 300 PE TTM Data Ingestion
系统 SHALL 通过 Tushare Pro `pro.index_dailybasic`（ts_code=`399300.SZ`）获取沪深300的日度 PE TTM，供股债利差计算使用。

#### Scenario: Fetch CSI 300 PE TTM
- **WHEN** 数据管道运行
- **THEN** 系统获取沪深300 `pe_ttm` 字段
- **AND** 数据写入 `data_cache/china/csi300_pe.csv`

### Requirement: Tushare 10Y CGB Yield Data Ingestion
系统 SHALL 通过 Tushare 宏观接口（`pro.cn_bond_price` 或等效 yield curve 接口）获取 10 年期中国国债收益率（日度），供股债利差计算使用。

#### Scenario: Fetch 10Y CGB yield
- **WHEN** 数据管道运行
- **THEN** 系统获取最新 10 年期 CGB 收益率（百分比单位）
- **AND** 数据写入 `data_cache/china/cgb10y_yield.csv`

### Requirement: Tushare Limit-Up/Down Daily Count Ingestion
系统 SHALL 通过 Tushare Pro `pro.stk_limit`（或等效接口）获取每日全市场涨停、跌停个股数量，供 Layer 3 哨兵评估使用。

#### Scenario: Fetch daily limit-up and limit-down counts
- **WHEN** 数据管道在交易日运行
- **THEN** 系统获取当日全市场涨停（`up_count`）和跌停（`down_count`）数量
- **AND** 数据写入 `data_cache/china/limit_counts.csv`

#### Scenario: Data completeness check
- **WHEN** 返回的涨停/跌停数量 < 5（不合理低值）
- **THEN** 系统记录 warning 日志，将该日计数标记为缺失（`NaN`），不触发哨兵

### Requirement: Tushare Northbound Flow Daily Data Ingestion
系统 SHALL 通过 Tushare Pro `pro.moneyflow_hsgt` 接口获取北向资金（沪股通 + 深股通）每日净买入额，替代原有 AkShare 渠道，供 Layer 2 外资信号调整使用。

#### Scenario: Fetch daily northbound net buy via Tushare
- **WHEN** 数据管道运行
- **THEN** 系统调用 `pro.moneyflow_hsgt(trade_date=today)`，合并沪股通和深股通净买入额
- **AND** 计算过去 5 日累计净流入，写入 `data_cache/china/northbound_flow.csv`

#### Scenario: Northbound API failure graceful degradation
- **WHEN** Tushare `pro.moneyflow_hsgt` 调用失败
- **THEN** 返回最近一个有效值并传递 `data_stale=True`，Layer 2 北向调整项默认为 0，不使 pipeline 崩溃

#### Scenario: AkShare northbound fetcher deprecated
- **WHEN** 数据管道运行
- **THEN** 不再调用 AkShare 北向资金接口，统一使用 Tushare 渠道

### Requirement: Tushare Southbound Flow Daily Data Ingestion
系统 SHALL 通过 Tushare Pro 接口获取南向资金（港股通）每日净买入额，供 Layer 3 `SOUTHBOUND_SURGE` 哨兵使用。

#### Scenario: Fetch daily southbound net buy
- **WHEN** 数据管道运行
- **THEN** 系统获取南向资金当日净买入总额（人民币，亿元）
- **AND** 计算与 20 日历史均值的标准差偏离，写入 `data_cache/china/southbound_flow.csv`

### Requirement: Tushare M2 Monthly Data Ingestion
系统 SHALL 通过 Tushare 宏观接口（`pro.cn_m`）获取月度 M2 广义货币存量数据，供存款市值比计算使用。

#### Scenario: Fetch monthly M2
- **WHEN** 数据管道运行且最新月度数据尚未缓存
- **THEN** 系统获取最新发布的 M2 月度值（单位：亿元）
- **AND** 数据写入 `data_cache/china/m2_monthly.csv`

#### Scenario: Mid-month run — no new data
- **WHEN** 当月 M2 数据尚未发布
- **THEN** 返回上月最新值，并附 `data_month` 字段供 UI 展示数据截止月份

### Requirement: S5FI Market Breadth Data Ingestion
系统 SHALL 通过从 Yahoo Finance 下载 11 个 SPDR 行业 ETF（XLK、XLF、XLV、XLC、XLY、XLI、XLP、XLE、XLRE、XLU、XLB），计算每个 ETF 相对其 50-day moving average 的位置，并应用可配置行业权重，摄取并生成 S5FI（S&P 500 market breadth）的加权近似值（0-100%）。

#### Scenario: Compute S5FI from sector ETFs
- **WHEN** 数据 pipeline 拉取到全部 11 个行业 ETF 的价格及其 50DMA
- **THEN** 每个 ETF 按高于 50DMA（1）或低于 50DMA（0）进行打分
- **AND** 使用行业权重计算的加权和产出 0% 到 100% 的 S5FI 值

#### Scenario: S5FI degradation on partial failure
- **WHEN** 一个或多个行业 ETF 数据源拉取失败
- **THEN** S5FI 返回 50.0 的中性值
- **AND** 失败会被记录日志，但不会导致数据 pipeline 崩溃

### Requirement: SPX Index Data for Regime Scoring
系统 SHALL 从 Yahoo Finance 摄取 SPX（S&P 500 index）价格数据，以支持 Layer 2 打分（SPX vs 50DMA）与 Layer 3 sentinel 逻辑（Trend Break）。

#### Scenario: Fetch SPX data
- **WHEN** 数据 pipeline 运行
- **THEN** 系统在拉取现有市场 ticker 的同时获取 SPX 日度价格
- **AND** 计算 SPX 的 50-day moving average

### Requirement: Tushare/AkShare API Row-Count and Date-Range Constraints

调用 Tushare Pro 和 AkShare 的历史批量接口时，必须遵守以下已知限制，否则接口静默返回截断数据，不抛出错误。

**约束一：`pro.daily_basic(start_date=..., end_date=...)` 约 8000 行上限**

- 单次调用涵盖 5500 支股票 × N 个交易日时，若总行数超限，接口只返回最近 N 行（最新数据优先），早期数据静默丢失。
- 解决方案：A 股总市值 backfill 必须使用 `trade_date=单日` 单次查询（单日查询无行数上限，返回所有股票），禁止使用日期范围批量查询。

**约束二：`pro.margin(start_date=..., end_date=...)` 约 4000 行上限**

- 2015–今约 5500 行（11 年 × 每年约 488 个交易日 × 2 市场行）超出限制，单次调用只返回最近 4000 行（2019 年后数据），2015–2018 年数据静默丢失。
- 解决方案：历史 backfill 必须按年分批，每年约 488 行（远低于限制）。

**约束三：`ak.bond_china_yield(start_date=..., end_date=...)` 日期范围 < 1 年**

- 单次调用的 `end_date - start_date` 必须严格小于 1 年，超出则返回空 DataFrame，不报错。
- 解决方案：历史 backfill 必须按年分批，concat 后使用。

#### Scenario: daily_basic range query truncates
- **WHEN** 以日期范围调用 `pro.daily_basic(start_date='20150101', end_date='20260101')`
- **THEN** 接口只返回最近约 8000 行，早期年份数据缺失，且没有任何错误提示

#### Scenario: single-date daily_basic is complete
- **WHEN** 以 `pro.daily_basic(trade_date='20150630')` 查询单日
- **THEN** 接口返回当日全部 A 股数据，无行数截断

#### Scenario: margin year-batch avoids truncation
- **WHEN** 以年为单位分批调用 `pro.margin(start_date='20150101', end_date='20151231')`
- **THEN** 每批约 488 行，远低于 4000 行限制，历史数据完整

#### Scenario: bond_china_yield over-range returns empty
- **WHEN** 调用 `ak.bond_china_yield(start_date='20150101', end_date='20260101')`（超过 1 年）
- **THEN** 返回空 DataFrame，不抛异常，调用方需校验 `len(df) == 0`

### Requirement: A 股历史数据 Backfill 触发与共享缓存架构

三个 A 股指标（两融余额市值比、股债利差、存款市值比）的 fetch 函数 SHALL 在加载缓存后检测历史覆盖范围，不足时自动触发 backfill，无需手动干预。

**共享总市值缓存**：`data_cache/china/total_mv_daily.csv` 存储每月末交易日的 A 股总市值（亿元），供三个指标共用，避免重复 API 调用。月末日期通过 `pro.trade_cal` 获取，总市值通过 `pro.daily_basic(trade_date=单日)` 逐日查询。

**Backfill 触发条件**：
```python
HISTORY_START = date(2015, 1, 1)
if cache.empty or cache.index.min() > pd.Timestamp(HISTORY_START):
    _backfill_<indicator>(HISTORY_START)
    cache = _load_cache(filename)
```

**缓存污染检测**：若 `total_mv_daily.csv` 中存在年内异常低值（< 年度中位数 × 70%），视为行数截断产生的污染数据，系统 SHALL 自动清除并触发重新 backfill。

#### Scenario: First-load triggers backfill
- **WHEN** 用户首次打开 China 模块，缓存文件为空或历史最早日期 > 2015-01-01
- **THEN** 系统自动运行 backfill（约 1-2 分钟），完成后返回 2015 至今的完整历史数据

#### Scenario: Backfill idempotent on repeated calls
- **WHEN** 缓存已覆盖 2015-01-01 至今
- **THEN** 触发条件为 False，不重复调用 backfill

#### Scenario: Corrupted cache auto-heals
- **WHEN** `total_mv_daily.csv` 存在年内异常低值（由日期范围查询行数截断产生）
- **THEN** 系统检测并删除污染行，同时清空依赖该数据的 `margin_ratio.csv` 和 `deposit_ratio.csv`，下次加载时自动重建

