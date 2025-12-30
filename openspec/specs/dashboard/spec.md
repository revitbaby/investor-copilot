# dashboard Specification

## Purpose
TBD - created by archiving change create-macro-liquidity-analyst. Update Purpose after archive.
## Requirements
### Requirement: Interactive Visualization
The dashboard MUST visualize Net Liquidity against the S&P 500.

#### Scenario: Liquidity Correlation Chart
- **WHEN** the user views the main dashboard
- **THEN** a dual-axis line chart displays Net Liquidity (Left Axis) and SPY Price (Right Axis) over the selected timeframe

### Requirement: AI Report Display
The dashboard MUST display the generated AI analysis in the user's selected language.

#### Scenario: View Analyst Report
- **WHEN** the analysis is complete
- **THEN** the Markdown report is rendered in a dedicated section
- **AND** the content is written in the currently selected language
- **AND** key metrics (Current Level, 1w Change) are shown in a summary view with localized labels

### Requirement: Language Selection
The dashboard MUST provide a mechanism for users to select their preferred interface language.

#### Scenario: Switch Language
- **WHEN** the user selects "Chinese" from the language selector
- **THEN** all static UI text updates to Chinese immediately
- **AND** the selection persists for the session

### Requirement: Report History
The dashboard MUST allow users to view previously generated analysis reports.

#### Scenario: View Past Report
- **WHEN** the user selects a past date from the report history selector
- **THEN** the system loads and displays the cached report for that date and current language
- **AND** hides the "Generate" button

### Requirement: Report Persistence
The dashboard MUST cache generated reports to prevent redundant API calls.

#### Scenario: Load Cached Report
- **WHEN** the dashboard loads
- **IF** a report exists for the current date and language
- **THEN** it is displayed automatically
- **AND** a "Regenerate" button is available

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

