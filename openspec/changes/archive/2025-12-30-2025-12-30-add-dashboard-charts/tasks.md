## 1. Data Layer
- [x] 1.1 Update `FredClient` in `src/data/fred_client.py` to fetch `SOFR` data.
- [x] 1.2 Update `MarketClient` in `src/data/market_client.py` to include `JNK` in tickers.
- [x] 1.3 Update `MarketClient.get_market_data` to extract and return Volume data for SPY (and potentially others if needed, but specifically SPY for now).
- [x] 1.4 Update `DataLoader` in `src/data/loader.py` to ensure new fields are propagated to the main DataFrame.

## 2. Visualization
- [x] 2.1 Create helper function in `src/ui/app.py` to build common Plotly chart styles (minimalist, shared x-axis).
- [x] 2.2 Implement Chart 1: Central Bank Liquidity (WALCL, RRP, TGA) with multiple y-axes if scales differ significantly, or normalized.
- [x] 2.3 Implement Chart 2: Policy Rates (SOFR).
- [x] 2.4 Implement Chart 3: Market Internal (SPY Volume, VIX, MOVE, HYG, JNK). *Note: Consider splitting axes or using subplots for Volume vs Indices.*
- [x] 2.5 Implement Chart 4: Cross Asset (DXY, Gold, Oil, BTC, US10Y). *Note: Likely requires normalization or percentage change view for meaningful comparison on one chart.*
- [x] 2.6 Integrate charts into a 2x2 layout using `st.columns` inside a container.

## 3. Validation
- [x] 3.1 Verify data fetching works for all new series.
- [x] 3.2 Verify charts render correctly in Light/Dark mode.
- [x] 3.3 Check performance impact of rendering 4 additional Plotly charts.
