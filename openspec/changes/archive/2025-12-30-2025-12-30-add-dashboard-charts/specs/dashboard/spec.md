## ADDED Requirements
### Requirement: Central Bank Visualization
The dashboard MUST display detailed metrics of the Federal Reserve's balance sheet and policy rates.

#### Scenario: View Fed Balance Sheet Components
- **WHEN** the user scrolls to the detailed metrics section
- **THEN** a chart displays the trends of Total Assets (WALCL), Reverse Repo (RRP), and Treasury General Account (TGA)
- **AND** a separate chart displays the Overnight Financing Rate (SOFR)

### Requirement: Market Health Visualization
The dashboard MUST visualize market risk and activity indicators.

#### Scenario: View Market Internals
- **WHEN** the user views the Market Side chart
- **THEN** it displays SPY Trading Volume, Volatility Indices (VIX, MOVE), and High Yield Bond ETFs (HYG, JNK)

### Requirement: Cross-Asset Visualization
The dashboard MUST display key cross-asset correlations.

#### Scenario: View Asset Classes
- **WHEN** the user views the Cross-Asset chart
- **THEN** it displays the performance of USD Index (DXY), Gold, WTI Crude Oil, Bitcoin (BTC), and US 10Y Treasury Yields

### Requirement: Dashboard Layout
The detailed charts MUST be arranged in a 2x2 grid layout.

#### Scenario: 2x2 Grid Layout
- **WHEN** the dashboard renders the detailed charts
- **THEN** they are arranged in two rows and two columns
- **AND** the charts are smaller in size than the main Net Liquidity chart

