# analysis-engine Specification

## Purpose
TBD - created by archiving change create-macro-liquidity-analyst. Update Purpose after archive.
## Requirements
### Requirement: Net Liquidity Calculation
The system MUST calculate Net Liquidity using the standard formula.

#### Scenario: Calculate Net Liquidity
- **WHEN** raw Central Bank data is available
- **THEN** Net Liquidity is computed as `WALCL - RRPONTSYD - WTREGEN` (in Billions/Trillions)

### Requirement: Trend Analysis
The system MUST identify trends based on moving averages and rate of change.

#### Scenario: Liquidity Trend Detection
- **WHEN** Net Liquidity is below its 20-day moving average
- **THEN** the system flags the trend as "Contracting"

### Requirement: Volatility Divergence
The system MUST detect divergence between equity volatility and bond volatility.

#### Scenario: VIX/MOVE Divergence
- **WHEN** VIX is low (<20) BUT MOVE Index is high (>120)
- **THEN** a "Bond Market Stress" warning signal is generated

### Requirement: China Macro Analysis
The system MUST calculate key Chinese macroeconomic signals.

#### Scenario: Calculate M1-M2 Gap
- **WHEN** M1 and M2 YoY data is available
- **THEN** the system calculates `Gap = M1_Growth - M2_Growth`
- **AND** interprets a positive gap as "Active Liquidity" and negative as "Liquidity Trap"

### Requirement: China Market Signals
The system MUST generate signals based on A-Share market activity.

#### Scenario: Turnover Signal
- **WHEN** A-Share daily turnover is evaluated
- **THEN** compare against thresholds (<600B: Low, >1T: Active, >2T: Overheated)

#### Scenario: Northbound Flow Signal
- **WHEN** Northbound fund flow is positive
- **THEN** signal "Foreign Inflow"

### Requirement: Hong Kong Valuation Analysis
The system MUST analyze the relative valuation of AH shares.

#### Scenario: AH Premium Analysis
- **WHEN** AH Premium Index is > 150
- **THEN** signal "H-Shares Undervalued" (High Premium)

