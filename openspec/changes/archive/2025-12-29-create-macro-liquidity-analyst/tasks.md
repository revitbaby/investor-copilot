# Implementation Tasks

## 1. Project Setup
- [x] 1.1 Initialize Python project with `uv` as package and venv manager.
- [x] 1.2 configure environment variables (`.env`) for OpenRouter(proxy for Gemini 3 Pro) and FRED API keys.
- [x] 1.3 Update `openspec/project.md` with project details.

## 2. Data Ingestion Layer
- [x] 2.1 Implement `FredClient` to fetch WALCL, RRPONTSYD, WTREGEN, SOFR/FEDFUNDS.
- [x] 2.2 Implement `MarketClient` (yfinance) to fetch SPY, VIX, MOVE, HYG, DXY, Gold, Oil, BTC, US10Y.
- [x] 2.3 Create `DataLoader` service to orchestrate fetching and merging into a single DataFrame (aligned by date).
- [x] 2.4 Add data caching (json/csv) to avoid hitting API limits during development.

## 3. Analytical Engine
- [x] 3.1 Implement `calculate_net_liquidity(df)`: `WALCL - RRPONTSYD - WTREGEN`.
- [x] 3.2 Implement `calculate_changes(df)`: 1w, 2w, 1m deltas and % changes.
- [x] 3.3 Implement signal logic:
    - Net Liquidity MA Cross signals.
    - Volatility divergence (VIX vs MOVE).
- [x] 3.4 Unit tests for calculation logic.

## 4. LLM Agent Integration
- [x] 4.1 Design prompt template for "Macro Strategist" persona.
- [x] 4.2 Implement `MacroAnalyst` class using LangChain/OpenRouter.
- [x] 4.3 Create `generate_report(context_json)` function to output structured Markdown.

## 5. User Interface (Streamlit)
- [x] 5.1 Create main layout with Sidebar (settings) and Main Area.
- [x] 5.2 Implement Plotly chart: Net Liquidity vs SPY (dual axis).
- [x] 5.3 Implement Metric row: Current Net Liq, 1w Change, VIX, DXY.
- [x] 5.4 Connect LLM Agent output to a text display area.
- [x] 5.5 Add manual "Refresh Analysis" button.

## 6. Documentation & Polish
- [x] 6.1 Update README.md with usage instructions.
- [x] 6.2 Verify end-to-end flow with real data.
