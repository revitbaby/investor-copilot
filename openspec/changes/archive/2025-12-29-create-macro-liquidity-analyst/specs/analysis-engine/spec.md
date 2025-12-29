## ADDED Requirements

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

