## ADDED Requirements
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

