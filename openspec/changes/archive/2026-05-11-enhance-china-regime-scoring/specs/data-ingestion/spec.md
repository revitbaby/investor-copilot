## ADDED Requirements

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

## MODIFIED Requirements

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
