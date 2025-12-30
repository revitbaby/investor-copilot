# Project Context

## Purpose
The **Macro Liquidity AI Analyst** is a tool for macro traders and investors to assess "Net Liquidity" in real-time. It automates data fetching from FRED and Yahoo Finance, calculates key liquidity metrics, and uses an LLM (Gemini 3 Pro via OpenRouter) to generate market status reports ("Traffic Light" signals) and investment narratives.

## Tech Stack
- **Language**: Python 3.10+
- **Package Manager**: uv
- **Framework**: Streamlit
- **Data**: pandas, yfinance, fredapi
- **Visualization**: plotly
- **LLM**: langchain, langchain-openai (OpenRouter/Gemini)

## Project Conventions

### Code Style
- Follow PEP 8.
- Use type hints for function arguments and return values.
- Docstrings for all public functions and classes.

### Architecture Patterns
- **ETL on Demand**: Data is fetched and processed when the user requests it (or cached).
- **Pure Functions**: Analysis logic should be separate from side effects.
- **Streamlit**: Used for the UI, with a sidebar for settings and main area for charts/reports.
- **Report Caching**: All LLM-generated reports MUST be cached locally by date and language (e.g., `data_cache/reports/YYYY-MM-DD_lang.json`) to minimize costs and ensure consistency. This pattern MUST be followed for all future AI features.

### Internationalization (i18n)
- **Languages**: Must support English (default) and Chinese (Simplified).
- **UI Text**: All static user-facing text MUST use `src/utils/i18n.py` and be wrapped in `t("key")`.
- **LLM Output**: Agents MUST accept a `language` parameter and generate reports in the user's selected language.
- **State**: Language preference is persisted in `st.session_state["language"]`.

### Testing Strategy
- Unit tests for the Analytical Engine (math/logic).
- End-to-end verification via manual testing in Streamlit (for now).

### Git Workflow
- Feature branches.
- Commit messages should be descriptive.

## Domain Context
- **Net Liquidity**: Defined as `Fed Total Assets - RRP - TGA`.
- **Traffic Light System**: Green (Bullish/Liquidity Expansion), Yellow (Neutral), Red (Bearish/Liquidity Contraction).
- **Cross-Asset Correlations**: Relationships between Net Liq, SPY, VIX, MOVE, DXY, Gold, etc.

## Important Constraints
- **API Limits**: FRED and Yahoo Finance have rate limits. Caching is essential.
- **LLM Cost/Latency**: Optimize context window usage.

## External Dependencies
- **FRED API**: For Central Bank data (WALCL, RRPONTSYD, WTREGEN).
- **Yahoo Finance**: For Market data (SPY, VIX, etc.).
- **OpenRouter**: For accessing Gemini 3 Pro.
