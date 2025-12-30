## ADDED Requirements
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

