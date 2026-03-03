## ADDED Requirements
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

