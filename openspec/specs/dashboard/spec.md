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

