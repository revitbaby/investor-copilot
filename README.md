# Macro Liquidity AI Analyst

An AI-powered dashboard for macro traders to analyze "Net Liquidity" and its impact on asset prices.

## Features

- **Automated Data Ingestion**: Fetches Central Bank data (FRED) and Market data (Yahoo Finance).
- **Net Liquidity Engine**: Calculates `Fed Assets - RRP - TGA` and tracks trends.
- **Traffic Light Signals**: Green/Yellow/Red market status based on liquidity and volatility (VIX vs MOVE).
- **AI Strategist**: Generates professional macro commentary using Gemini 3 Pro (via OpenRouter).
- **Interactive Dashboard**: Streamlit-based UI with Plotly charts.

## Setup

1. **Install dependencies**:
   ```bash
   uv sync
   ```
   Or if not using `uv`:
   ```bash
   pip install -r pyproject.toml # (requires extracting dependencies)
   ```

2. **Configure Environment**:
   Copy `example.env` to `.env` and fill in your keys.
   ```bash
   cp example.env .env
   ```
   - `FRED_API_KEY`: Get from [FRED](https://fred.stlouisfed.org/docs/api/api_key.html).
   - `OPENAI_API_KEY`: OpenRouter API Key.
   - `LLM_MODEL`: (Optional) Model ID, defaults to `google/gemini-2.0-flash-exp:free`.

3. **Run the App**:
   ```bash
   PYTHONPATH=. uv run streamlit run src/ui/app.py
   ```

## Architecture

- `src/data`: Clients for FRED and Yahoo Finance.
- `src/analysis`: Logic for Net Liquidity and Signals.
- `src/llm`: LangChain integration with OpenRouter.
- `src/ui`: Streamlit application.

## License

MIT
