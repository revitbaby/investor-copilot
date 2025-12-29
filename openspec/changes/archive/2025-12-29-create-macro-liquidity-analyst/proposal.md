# Change: Create Macro Liquidity AI Analyst

## Why
Macro traders and investors need a real-time, automated way to assess "Net Liquidity" and its impact on asset prices. Currently, this requires manual data gathering from FRED and Yahoo Finance and complex spreadsheet calculations. An AI-powered analyst can automate this, providing real-time "traffic light" signals and narrative explanations, helping users decide between "risk-on" and "risk-off" modes.

## What Changes
This proposal implements the "Macro Liquidity AI Analyst", a Streamlit-based Python application.

### Core Features
- **Data Ingestion**: Automated pipelines for FRED (Central Bank) and yfinance (Market/Cross-Asset) data.
- **Analytical Engine**: 
  - Calculates "Net Liquidity" (Fed Assets - RRP - TGA).
  - Computes volatility signals (VIX vs MOVE) and trends.
- **LLM Agent**:
  - Gemini 3 Pro powered "Macro Strategist" persona.
  - Generates Red/Yellow/Green market status reports.
- **UI**: Interactive Streamlit dashboard with Net Liquidity vs SPY charts.

### Tech Stack
- **Language**: Python 3.10+
- **Framework**: Streamlit
- **Libraries**: pandas, yfinance, fredapi, plotly, langchain, Gemini 3 Pro(through OpenRouter)

## Impact
- **New Capabilities**:
  - `data-ingestion`: Fetching and normalizing macro data.
  - `analysis-engine`: Financial math for liquidity and trends.
  - `llm-agent`: Context-aware market commentary generation.
  - `dashboard`: Visualization and user interaction.
- **Affected Systems**: This is a greenfield project; no existing systems are affected.

