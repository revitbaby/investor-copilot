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
The dashboard MUST display the generated AI analysis.

#### Scenario: View Analyst Report
- **WHEN** the analysis is complete
- **THEN** the Markdown report is rendered in a dedicated section
- **AND** key metrics (Current Level, 1w Change) are shown in a summary view

