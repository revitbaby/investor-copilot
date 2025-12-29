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

