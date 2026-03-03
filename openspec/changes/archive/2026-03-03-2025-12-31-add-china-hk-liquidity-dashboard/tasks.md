## 1. Data Ingestion
- [x] 1.1 Add `akshare` to `pyproject.toml` and install dependencies.
- [x] 1.2 Create `src/data/china_market_client.py` to fetch data using AkShare.
    - [x] Implement Macro data fetching (DR007, OMO, SHIBOR, M1, M2, Social Financing).
    - [x] Implement Market data fetching (Turnover, Northbound, Margin, ETF).
    - [x] Implement HK specific data fetching (Southbound, AH Premium).
- [x] 1.3 Update `src/data/loader.py` to integrate `ChinaMarketClient`.

## 2. Analysis Engine
- [x] 2.1 Update `src/analysis/engine.py` to calculate CN/HK specific metrics.
    - [x] Calculate M1-M2 Gap.
    - [x] Calculate AH Premium signals.
    - [x] Calculate "Traffic Light" signals for China Liquidity (e.g. M1-M2 > 0 -> Green).

## 3. Dashboard UI
- [x] 3.1 Update `src/ui/app.py` to add a new tab "🇨🇳 China/HK Liquidity".
- [x] 3.2 Implement charts for:
    - [x] Macro: DR007 vs OMO Rate, SHIBOR.
    - [x] Meso: M1-M2 Gap, Social Financing.
    - [x] Micro: A-Share Turnover, Northbound Flows, Margin Balance.
    - [x] HK: AH Premium, Southbound Flows.
- [x] 3.3 Add "Signal Dashboard" for China markets (similar to the US one).
