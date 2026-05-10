# data-ingestion 规范 (Specification)

## Purpose
待定 (TBD) - 由归档变更 create-macro-liquidity-analyst 创建。归档后更新目的。
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
系统必须 (MUST) 从 AkShare 摄取中国A股市场指标 (A-Share market indicators)。

#### Scenario: 获取中国市场指标
- **当 (WHEN)** 数据管道 (data pipeline) 运行时
- **那么 (THEN)** 它获取A股换手率 (A-Share Turnover)、北向资金流向 (Northbound Fund Flows)、融资融券余额 (Margin Balance) 和 ETF 成交量 (ETF Volumes)（例如 510300）

### Requirement: Hong Kong Market Data Ingestion
系统必须 (MUST) 摄取香港市场指标。

#### Scenario: HK Indicators
- **当 (WHEN)** 数据管道 (data pipeline) 运行时
- **那么 (THEN)** 它从 AkShare 获取南向资金流向 (Southbound Fund Flows) 和 AH 股溢价指数 (AH Premium Index)
- **并且 (AND)** 从 Yahoo Finance 获取 USD/CNH 汇率 (exchange rate)

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

