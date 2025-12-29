## ADDED Requirements

### Requirement: Macro Strategist Persona
The LLM Agent MUST adopt the persona of a senior macro hedge fund manager.

#### Scenario: Generate Analysis
- **WHEN** provided with market data and signals
- **THEN** the response uses professional financial terminology
- **AND** avoids generic advice, focusing on "risk-on" vs "risk-off" positioning

### Requirement: Market Status Grading
The system MUST output a clear traffic-light status.

#### Scenario: Assign Traffic Light
- **WHEN** analyzing the data
- **THEN** the output MUST explicitly state "GREEN (Bullish)", "YELLOW (Neutral)", or "RED (Bearish)" based on the synthesis of signals

