# Change: Add Detailed Market & Liquidity Charts

## Why
The current dashboard provides a high-level view of Net Liquidity vs S&P 500 but lacks granular visibility into the components of liquidity (Fed Balance Sheet details), policy rates, and broader market health (volatility, credit spreads, cross-asset correlations). Users need these details to form a complete macro view.

## What Changes
- **Dashboard UI**:
  - Adds a new 2x2 chart grid below the main chart.
  - **Chart 1 (Central Bank)**: Fed Assets (WALCL), Reverse Repo (RRP), Treasury Account (TGA).
  - **Chart 2 (Rates)**: Overnight Rate (SOFR).
  - **Chart 3 (Market Health)**: SPY Volume, VIX, MOVE, HYG/JNK Ratio or Prices.
  - **Chart 4 (Cross-Asset)**: DXY, Gold, Oil, Bitcoin, US 10Y Yield.
- **Data Ingestion**:
  - Adds `SOFR` to FRED client.
  - Adds `JNK` (High Yield Bond ETF) to Market client.
  - Adds `Volume` data fetching for SPY.

## Impact
- **Specs**: `dashboard`, `data-ingestion`
- **Code**: `src/ui/app.py`, `src/data/fred_client.py`, `src/data/market_client.py`, `src/data/loader.py`

