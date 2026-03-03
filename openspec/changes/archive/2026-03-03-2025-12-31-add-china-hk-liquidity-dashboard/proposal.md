# Change: Add China/HK Liquidity Dashboard

## Why
The current dashboard focuses primarily on US markets (Net Liquidity, Fed Assets). Investors looking at global markets, specifically China (A-shares) and Hong Kong, lack a dedicated view of liquidity conditions in these regions. The "water level" logic (Macro/Meso/Micro) applies equally well to CN/HK markets but requires different indicators and data sources.

## What Changes
- **New Data Source**: Integrate `AkShare` to fetch Chinese macro and market data.
- **New Indicators**: Implement the 3-layer liquidity framework for China/HK:
    - **Macro**: DR007, OMO/MLF, SHIBOR.
    - **Meso**: M1-M2 Gap, Social Financing.
    - **Micro**: Turnover, Northbound/Southbound Flows, Margin Balance, ETF Volume, AH Premium.
- **New Dashboard Tab**: Add a "China/HK Liquidity" tab to the Streamlit app.
- **New Analysis Logic**: Calculate signals based on these new indicators (e.g., traffic lights for CN liquidity).

## Impact
- **Affected Specs**: `data-ingestion`, `analysis-engine`, `dashboard`.
- **Affected Code**: 
    - `pyproject.toml` (add `akshare`).
    - `src/data/` (new `china_market_client.py`).
    - `src/analysis/engine.py` (new calculations).
    - `src/ui/app.py` (new tab).

