## ADDED Requirements

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

## MODIFIED Requirements

### Requirement: Market Data Ingestion
系统 MUST 从 Yahoo Finance 获取市场价格与成交量数据，覆盖现有 ticker（SPY、VIX、MOVE、HYG、DXY、GOLD、OIL、BTC、US10Y、JNK）以及 regime scoring engine 新增所需 ticker（SPX index、11 个 SPDR 行业 ETF）。

#### Scenario: Fetch Market Indicators
- **WHEN** 数据 pipeline 运行
- **THEN** 系统拉取 SPY、VIX、DX-Y.NYB、GC=F、^MOVE、HYG、JNK、CL=F、BTC-USD、^TNX、^GSPC（SPX）以及 11 个 SPDR 行业 ETF
- **AND** 将这些数据与央行数据日期对齐
