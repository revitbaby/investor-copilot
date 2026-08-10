# Stock Daily Data Specification

## Purpose
描述股票日线 ETL-on-demand 缓存及 A股/美股/港股各市场数据源拉取与降级行为。
## Requirements

### Requirement: ETL-on-demand daily bar cache
系统 SHALL 对每只标的维护 T-1 日线缓存文件于 `data_cache/stocks/{safe_ticker}/daily.csv`，其中 `safe_ticker` 为 ticker 中特殊字符（`.`）替换为 `_` 后的字符串（如 `600519_SH`、`AAPL`）。缓存文件包含列：`date, open, high, low, close, volume`，index 为日期字符串。

#### Scenario: Cache hit
- **WHEN** 缓存文件存在且最后一条记录为昨日（T-1 交易日）
- **THEN** 直接返回缓存数据，不调用 API

#### Scenario: Cache miss - file not exist
- **WHEN** 缓存文件不存在
- **THEN** 调用对应 API 拉取 500 个交易日历史数据，写入缓存，返回数据

#### Scenario: Cache stale - outdated
- **WHEN** 缓存文件存在但最后一条记录早于 T-1 交易日
- **THEN** 调用 API 拉取缺失日期的增量数据，追加写回缓存

### Requirement: A股日线数据通过 Tushare pro.daily() 获取
系统 SHALL 通过 `pro.daily(ts_code=ticker, start_date=..., end_date=...)` 拉取 A股日线数据。market == "A股" 的标的使用此路径。

#### Scenario: Successful fetch for A-share
- **WHEN** ticker 为合法 Tushare 格式（如 `600519.SH`）且 API 调用成功
- **THEN** 返回包含 date/open/high/low/close/volume 的 DataFrame，按日期升序排列

#### Scenario: API failure returns stale data
- **WHEN** Tushare API 调用失败（网络错误/积分不足）
- **THEN** 返回 `(cached_df, stale=True)`，不抛异常到 UI 层；若无缓存则返回 `(None, stale=True)`

#### Scenario: Rate limit protection
- **WHEN** 批量拉取多只 A股标的时
- **THEN** 每次 API 调用之间 sleep 0.3s，避免触发 Tushare 频率限制

### Requirement: 美股日线数据通过 yfinance 获取
系统 SHALL 通过 `yfinance.download(ticker, ...)` 拉取美股日线数据。market == "美股" 的标的使用此路径。

#### Scenario: Successful fetch for US stock
- **WHEN** ticker 为合法 Yahoo Finance 格式（如 `AAPL`）且 API 调用成功
- **THEN** 返回包含 date/open/high/low/close/volume 的 DataFrame，按日期升序排列

#### Scenario: yfinance HTTP failure returns stale data
- **WHEN** yfinance 返回空 DataFrame 或抛出异常
- **THEN** 返回 `(cached_df, stale=True)`，不抛异常到 UI 层

### Requirement: 港股标的返回 None 并标记待接入
系统 SHALL 对 market == "港股" 的标的，不调用任何 API，直接返回 `(None, stale=True)`，UI 显示"港股数据待接入"。

#### Scenario: HK stock placeholder
- **WHEN** StockPoolItem.market == "港股" 时调用数据拉取函数
- **THEN** 立即返回 `(None, stale=True)`，无网络请求发生

### Requirement: 数据量最少 120 个交易日
系统 SHALL 确保返回的日线数据不少于 120 个交易日，以保证 MA120 可计算。初次拉取时请求 500 个交易日历史。

#### Scenario: Sufficient data for MA120
- **WHEN** 缓存数据不少于 120 行
- **THEN** TrendingUpAnalyzer 可计算 MA120，不出现 NaN

#### Scenario: Insufficient data warning
- **WHEN** 缓存数据少于 120 行（如新上市标的）
- **THEN** TrendingUpAnalyzer 返回 TrendAnalysis 但将 `data_insufficient=True`，UI 显示"数据不足，部分指标不可用"
