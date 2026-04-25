# data-ingestion 规范 (Specification)

## 目的 (Purpose)
待定 (TBD) - 由归档变更 create-macro-liquidity-analyst 创建。归档后更新目的。

## 需求 (Requirements)
### 需求：央行数据摄取 (Central Bank Data Ingestion)
系统必须 (MUST) 从 FRED API 检索关键流动性指标 (liquidity indicators) 的历史数据。

#### 场景 (Scenario)：获取美联储资产负债表 (Fed Balance Sheet)
- **当 (WHEN)** 数据管道 (data pipeline) 运行时
- **那么 (THEN)** 它获取 `WALCL`（总资产 / Total Assets）、`RRPONTSYD`（逆回购 / Reverse Repo）和 `WTREGEN`（财政部一般账户 / TGA）
- **并且 (AND)** 将它们标准化为通用的每日时间序列 (time series)

### 需求：市场数据摄取 (Market Data Ingestion)
系统必须 (MUST) 从 Yahoo Finance 检索市场价格和成交量数据 (volume data)。

#### 场景 (Scenario)：获取市场指标 (Market Indicators)
- **当 (WHEN)** 数据管道 (data pipeline) 运行时
- **那么 (THEN)** 它获取 `SPY`（标普500 / S&P 500）、`VIX`（波动率 / Volatility）、`DX-Y.NYB`（美元指数 / Dollar Index）和 `GC=F`（黄金 / Gold）
- **并且 (AND)** 将它们与央行数据日期对齐

### 需求：利率数据 (Interest Rate Data)
系统必须 (MUST) 从 FRED 摄取担保隔夜融资利率 (Secured Overnight Financing Rate / SOFR)。

#### 场景 (Scenario)：获取 SOFR
- **当 (WHEN)** 数据更新时
- **那么 (THEN)** 从 FRED 获取 `SOFR` 序列并与其他每日数据对齐

### 需求：信贷市场数据 (Credit Market Data)
系统必须 (MUST) 摄取 JNK（SPDR彭博高收益债券ETF / SPDR Bloomberg High Yield Bond ETF）的高收益债券 ETF (High Yield Bond ETF) 数据。

#### 场景 (Scenario)：获取 JNK
- **当 (WHEN)** 获取市场数据时
- **那么 (THEN)** 从 Yahoo Finance 检索 `JNK` 的每日价格数据

### 需求：交易量数据 (Trading Volume Data)
系统必须 (MUST) 摄取标普500 ETF (S&P 500 ETF / SPY) 的交易量数据。

#### 场景 (Scenario)：获取 SPY 交易量
- **当 (WHEN)** 获取市场数据时
- **那么 (THEN)** 检索并存储 `SPY` 的每日交易量

### 需求：中国宏观数据摄取 (China Macro Data Ingestion)
系统必须 (MUST) 从 AkShare 摄取中国宏观经济指标 (macro-economic indicators)。

#### 场景 (Scenario)：获取中国宏观指标
- **当 (WHEN)** 数据管道 (data pipeline) 运行时
- **那么 (THEN)** 它获取 DR007（回购利率 / Repo Rate）、OMO/MLF（公开市场操作 / Open Market Operations）、SHIBOR（同业拆借利率 / Interbank Rate）、M1/M2 货币供应量 (Money Supply) 和社会融资 (Social Financing)
- **并且 (AND)** 将它们标准化为通用的每日/每月时间序列

### 需求：中国市场数据摄取 (China Market Data Ingestion)
系统必须 (MUST) 从 AkShare 摄取中国A股市场指标 (A-Share market indicators)。

#### 场景 (Scenario)：获取中国市场指标
- **当 (WHEN)** 数据管道 (data pipeline) 运行时
- **那么 (THEN)** 它获取A股换手率 (A-Share Turnover)、北向资金流向 (Northbound Fund Flows)、融资融券余额 (Margin Balance) 和 ETF 成交量 (ETF Volumes)（例如 510300）

### 需求：香港市场数据摄取 (Hong Kong Market Data Ingestion)
系统必须 (MUST) 摄取香港市场指标。

#### 场景 (Scenario)：获取香港指标 (HK Indicators)
- **当 (WHEN)** 数据管道 (data pipeline) 运行时
- **那么 (THEN)** 它从 AkShare 获取南向资金流向 (Southbound Fund Flows) 和 AH 股溢价指数 (AH Premium Index)
- **并且 (AND)** 从 Yahoo Finance 获取 USD/CNH 汇率 (exchange rate)
