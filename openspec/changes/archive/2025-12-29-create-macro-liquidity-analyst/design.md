# Design: Macro Liquidity AI Analyst

## Context
We are building a tool to replicate "Net Liquidity" analysis, a popular macro framework. The system needs to be robust, modular, and easy to extend with new indicators.

## Goals
- **Modularity**: Separation of concerns between Data, Logic, and UI.
- **Reproducibility**: Analysis should be deterministic based on the data.
- **Extensibility**: Easy to add new tickers (e.g., ETH, Copper) without rewriting the engine.

## Architecture

### 1. Data Pipeline
- **Pattern**: ETL (Extract-Transform-Load) on demand.
- **Source**: FRED (API), Yahoo Finance (Library).
- **Storage**: In-memory Pandas DataFrame for the session; optional local cache for speed.
- **Normalization**: All data resampled to daily frequency, forward-filled to handle holidays/weekends.

### 2. Analytical Engine
- Pure function approach: `Input Data -> Indicators & Signals`.
- No side effects (database writes) required for the MVP.

### 3. LLM Integration
- **Context Injection**: We will pass a compressed JSON summary of the market state to the LLM.
- **Prompt Engineering**: Use a "System Message" to define the Persona (Senior Macro Strategist) and "User Message" for the data.
- **Output**: Markdown formatted text for direct rendering in Streamlit.

## Trade-offs
- **Streamlit vs React**: Choosing Streamlit for speed of development (Python-only) over UI customization.
- **Real-time vs Daily**: Data sources like FRED update daily/weekly. Real-time intraday data is not required for this macro view, simplifying the architecture.

## Risks
- **API Limits**: FRED or Yahoo Finance may rate limit. *Mitigation*: Implement simple file-based caching.
- **LLM Hallucinations**: The LLM might invent correlations. *Mitigation*: Hardcode the numeric data in the prompt and ask the LLM to *interpret* only, not calculate.

