# data-ingestion Specification

## Purpose
TBD - created by archiving change create-macro-liquidity-analyst. Update Purpose after archive.
## Requirements
### Requirement: Central Bank Data Ingestion
The system MUST retrieve historical data from the FRED API for key liquidity indicators.

#### Scenario: Fetch Fed Balance Sheet
- **WHEN** the data pipeline runs
- **THEN** it fetches `WALCL` (Total Assets), `RRPONTSYD` (Reverse Repo), and `WTREGEN` (TGA)
- **AND** normalizes them to a common daily time series

### Requirement: Market Data Ingestion
The system MUST retrieve market price and volume data from Yahoo Finance.

#### Scenario: Fetch Market Indicators
- **WHEN** the data pipeline runs
- **THEN** it fetches `SPY` (S&P 500), `VIX` (Volatility), `DX-Y.NYB` (Dollar Index), and `GC=F` (Gold)
- **AND** aligns them with the Central Bank data dates

### Requirement: Interest Rate Data
The system MUST ingest the Secured Overnight Financing Rate (SOFR) from FRED.

#### Scenario: Fetch SOFR
- **WHEN** data is updated
- **THEN** the `SOFR` series is fetched from FRED and aligned with other daily data

### Requirement: Credit Market Data
The system MUST ingest High Yield Bond ETF data for JNK (SPDR Bloomberg High Yield Bond ETF).

#### Scenario: Fetch JNK
- **WHEN** market data is fetched
- **THEN** daily price data for `JNK` is retrieved from Yahoo Finance

### Requirement: Trading Volume Data
The system MUST ingest trading volume data for the S&P 500 ETF (SPY).

#### Scenario: Fetch SPY Volume
- **WHEN** market data is fetched
- **THEN** daily trading volume for `SPY` is retrieved and stored

### Requirement: China Macro Data Ingestion
The system MUST ingest Chinese macro-economic indicators from AkShare.

#### Scenario: Fetch China Macro Indicators
- **WHEN** the data pipeline runs
- **THEN** it fetches DR007 (Repo Rate), OMO/MLF (Open Market Operations), SHIBOR (Interbank Rate), M1/M2 Money Supply, and Social Financing
- **AND** normalizes them to a common daily/monthly time series

### Requirement: China Market Data Ingestion
The system MUST ingest China A-Share market indicators from AkShare.

#### Scenario: Fetch China Market Indicators
- **WHEN** the data pipeline runs
- **THEN** it fetches A-Share Turnover, Northbound Fund Flows, Margin Balance, and ETF Volumes (e.g. 510300)

### Requirement: Hong Kong Market Data Ingestion
The system MUST ingest Hong Kong market indicators.

#### Scenario: Fetch HK Indicators
- **WHEN** the data pipeline runs
- **THEN** it fetches Southbound Fund Flows and AH Premium Index from AkShare
- **AND** fetches USD/CNH exchange rate from Yahoo Finance

