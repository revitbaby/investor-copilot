## Why

The China module's regime scoring (`analyze_china_signals`) currently relies on only two dimensions — M1-M2 growth spread and northbound flow direction. Two signals are insufficient to distinguish "liquidity easing but ineffective" from "liquidity easing and transmitted to equities," and provide no valuation or leverage-heat context. Meanwhile the US module already has a full three-layer framework (Net Liquidity → Market Regime → Instant Sentinels). This asymmetry means China regime output is unreliable for allocation decisions. Northbound flow data remains fetchable via Tushare and should be retained as an active Layer 2 foreign-capital signal rather than discarded.

## What Changes

- **Add three new A-share macro indicators**: Margin Balance / Market Cap ratio (杠杆热度), Equity-Bond Yield Spread (股债利差), and Deposit / Market Cap ratio (存款市值比) — each displayed as a time-series chart with historical bull-market reference levels
- **Implement three-layer A-share regime framework**:
  - Layer 1 (Liquidity Floor): DR007 deviation from OMO, M1 YoY, M1-M2 spread, TSF growth → outputs Position Ceiling
  - Layer 2 (Market Regime): Equity-bond spread, margin ratio, QVIX, major-fund net-flow, northbound flow direction → classifies into four A-share regimes (Value Bull, Sentiment Bull, Panic Bottom, Overvaluation Risk) → outputs Utilization Rate
  - Layer 3 (Instant Sentinels): Limit-up count, limit-down count, ZT/DT ratio, consecutive-limit-up heat, southbound-flow anomaly, turnover surge → triggers warning banner and position override
- **Synthesize Target Position Envelope** from all three layers with sentinel override logic
- **Add dashboard components**: three indicator cards with charts, regime scoring table (Layer 1/2/3), position envelope gauge, sentinel warning banner, 12-month regime timeline
- **Restore northbound flow as active Layer 2 signal** via Tushare (replacing the prior AkShare channel that stopped real-time disclosure)

## Capabilities

### New Capabilities

- `china-margin-data`: Fetch and compute daily Margin Balance / Market Cap ratio (融资融券余额 ÷ A股总市值) from Tushare, with historical bull-market watermarks
- `china-equity-bond-spread`: Compute daily Equity-Bond Yield Spread (CSI 300 earnings yield − 10Y CGB yield) from Tushare PE data and Wind/Tushare bond yield
- `china-deposit-ratio`: Compute monthly Deposit / Market Cap ratio (M2 or 居民储蓄 ÷ A股总市值) with monthly-frequency chart

### Modified Capabilities

- `regime-scoring`: Extend China regime scoring from a 2-signal flat rule to a three-layer framework (Layer 1 Ceiling × Layer 2 Utilization × Layer 3 Sentinel Override); add four A-share regime classifications; add Target Position Envelope synthesis
- `data-ingestion`: Add new Tushare data fetchers for margin balance, CSI 300 PE (TTM), 10Y CGB yield, limit-up/down daily counts, southbound-flow daily net, northbound flow daily net (via Tushare, replacing prior AkShare channel)
- `analysis-engine`: Add Layer 1 / Layer 2 / Layer 3 scoring functions for the A-share framework; add sentinel trigger logic with persistence (3-day hold-down)
- `dashboard`: Add China module components — three indicator chart cards, regime scoring table, position envelope gauge, sentinel warning banner, 12-month regime color-band timeline

## Impact

- `src/data/tushare_fetcher.py` (or new `src/data/china_market_fetcher.py`): new data-fetch functions for margin, PE, bond yield, limit-up/down, southbound flow
- `src/analysis/china_regime.py` (new or extended): Layer 1/2/3 scoring and envelope synthesis
- `src/ui/china_dashboard.py` (or existing dashboard module): new Streamlit chart components
- Tushare API dependency already present; confirm required data interfaces (pro.margin, index_dailybasic, cn_bond_price / macro interface, stk_limit, moneyflow_hsgt for northbound flow)
- Caching: new Tushare fetchers must follow existing `data_cache/` pattern (date-keyed JSON/parquet)
- i18n: all new UI labels must be added to `src/utils/i18n.py` (Chinese + English)
