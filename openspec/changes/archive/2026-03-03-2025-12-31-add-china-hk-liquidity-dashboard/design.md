## Context
Users need a dashboard to monitor China and Hong Kong market liquidity, following a Macro-Meso-Micro framework. This requires integrating a new data source (`AkShare`) and visualizing specific local indicators.

## Goals
- Provide a clear view of CN/HK liquidity conditions.
- Integrate `AkShare` without disrupting existing US data flows.
- Visualize key indicators like M1-M2 Gap and Northbound flows.

## API Mappings (AkShare)
We will use the following AkShare interfaces (subject to availability and validation):

### Macro (The Source)
- **CN1: DR007**: `macro_china_shibor_all()` (filter for DR007 if available) or `interbank_rate_open_market_operation`. *Fallback*: Use SHIBOR 7D as proxy if DR007 specific series is hard to get reliably via simple API, but prioritize finding DR007.
- **CN2: OMO/MLF**: `macro_china_omo_net_withdrawal()` or `macro_china_omo()`.
- **CN3: SHIBOR**: `macro_china_shibor_all()`.

### Meso (The Pipeline)
- **CN4: M1/M2**: `macro_china_m1()` and `macro_china_m2()`. Calculate Gap = M1 YoY - M2 YoY.
- **CN5: Social Financing**: `macro_china_shrzgm()`.

### Micro (Market Level)
- **CN6: Turnover**: `stock_zh_a_spot_em()` for snapshot, or aggregate index volume.
- **CN7: Northbound**: `stock_hsgt_north_net_flow_in_em()`.
- **CN8: Margin**: `stock_margin_detail_sz_sh()`.
- **CN9: ETF Volume**: `fund_etf_hist_em(symbol="510300")`.

### HK Specifics
- **HK1: USD/CNH**: `yfinance` (`CNH=X`).
- **HK2: Southbound**: `stock_hsgt_south_net_flow_in_em()`.
- **HK3: AH Premium**: `stock_zh_ah_premium()` or index equivalent.
- **HK4: US 10Y**: `yfinance` (`^TNX`).

## Architecture Decisions
- **New Client**: `ChinaMarketClient` in `src/data/china_market_client.py`.
- **Data Loading**: `DataLoader` will instantiate both `MarketClient` (US) and `ChinaMarketClient` (CN) and merge or keep datasets separate as needed for the UI. Given the different timezones and trading hours, keeping them as separate DataFrames in the `DataLoader` state is cleaner.
- **UI Structure**: A separate tab "China/HK" ensures clarity and doesn't clutter the US view.

## Risks
- **AkShare Reliability**: AkShare relies on scraping some sources (EastMoney, Sina). APIs might break. We should add basic error handling and fallbacks (return empty DF if failed) so the whole app doesn't crash.
- **Data Latency**: Some macro data (M1/M2) is monthly and released with lag. The dashboard should handle sparse data gracefully (forward fill or scatter plots).

