## Context

The existing China module (`analyze_china_signals`) is a flat two-signal rule that checks M1-M2 growth spread and northbound fund direction. Two signals are insufficient to distinguish "liquidity easing but ineffective" from "liquidity easing and transmitted to equities," and provide no valuation or leverage-heat context. The US module already operates a full three-layer framework (Net Liquidity Layer → Market Regime Layer → Instant Sentinels) that synthesises a Target Position Envelope. This change brings the China module to structural parity while using A-share-specific signals appropriate for a policy-driven market. Northbound flow data is available and fetchable via Tushare (`pro.moneyflow_hsgt`) and is retained as an active foreign-capital signal in Layer 2.

Key constraints inherited from project context:
- All new data fetchers must follow the `data_cache/` date-keyed caching pattern (ETL-on-demand, no background jobs)
- Tushare is already a dependency; new data APIs must use it rather than adding new data providers
- All UI text must go through `src/utils/i18n.py`
- Unit tests required for all scoring logic

## Goals / Non-Goals

**Goals:**
- Implement Layer 1 (Liquidity Floor), Layer 2 (Market Regime), and Layer 3 (Instant Sentinels) scoring for A-shares
- Add three new indicator time-series (margin ratio, equity-bond spread, deposit ratio) as dashboard cards
- Synthesise a Target Position Envelope for the China module, structurally parallel to the US envelope
- Restore northbound flow as an active Layer 2 signal via Tushare (`pro.moneyflow_hsgt`), replacing the prior AkShare channel
- Display a 12-month regime color-band timeline in the China module dashboard section

**Non-Goals:**
- LLM narrative generation for China regime (addressed in a separate future proposal)
- Individual stock or sector recommendations
- Back-testing regime signal thresholds (requires complete history data pipeline)

## Decisions

### Decision 1: Extend existing China analysis module rather than creating a new service

**Choice**: Add `compute_china_layer1()`, `compute_china_layer2()`, `compute_china_layer3()` functions inside the existing `src/analysis/china_regime.py` (or create that file if not present). Keep all scoring logic as pure functions with typed signatures, matching the pattern used for the US regime engine.

**Alternatives considered**:
- A separate microservice / subprocess: rejected — the project is a single Streamlit app, a service boundary adds operational complexity with no benefit at this scale.
- Monolithic function extending `analyze_china_signals`: rejected — the US module's layered architecture has already proven easier to test and tune; replicating it for China ensures consistency.

**Rationale**: Pure functions are trivially unit-testable; a new dedicated file prevents `analyze_china_signals` from ballooning while keeping the interface contract clear.

---

### Decision 2: Use Tushare as the sole new data provider

**Choice**: All new A-share data (margin balance, CSI 300 PE TTM, 10Y CGB yield, limit-up/down counts, southbound daily net) comes from Tushare Pro APIs. The project already holds a Tushare token.

**Alternatives considered**:
- AkShare: already used for some China macro data. Could be used for margin data but Tushare has more reliable daily margin series.
- Wind API: institutional-grade but requires separate license and different SDK; out of scope.

**Rationale**: Single China data provider dependency keeps credential management simple and avoids library proliferation. Tushare Pro covers all required series with daily update frequency.

---

### Decision 3: Margin ratio, equity-bond spread, and deposit ratio stored as date-indexed pandas Series in `data_cache/`

**Choice**: Each indicator is cached as a separate CSV file under `data_cache/china/` (e.g., `data_cache/china/margin_ratio.csv`, `equity_bond_spread.csv`, `deposit_ratio.csv`). The ETL-on-demand pattern fetches only if today's date is not in the cache.

**Alternatives considered**:
- Single combined CSV: easy but requires re-fetching everything on any column addition.
- In-memory only (no cache): unacceptable — Tushare has strict daily call limits.

**Rationale**: CSV is already used elsewhere for time-series caching; separate files allow independent update schedules (daily vs monthly for deposit ratio).

---

### Decision 4: Layer 3 sentinels use a 3-trading-day hold-down, persisted to `data_cache/china_sentinel_state.json`

**Choice**: Reuse the exact same sentinel state persistence pattern as the US module (`data_cache/sentinel_state.json`) but in a separate file to avoid cross-contamination.

**Rationale**: The US sentinel pattern is already proven and has a clear CLEAR/TRIGGERED/COOLING state machine. Reusing the same structure keeps the codebase consistent and allows shared utility functions for state loading/saving.

---

### Decision 5: A-share regime classifications use four named states instead of a numeric score

**Choice**: Layer 2 outputs one of four named states — `VALUE_BULL`, `SENTIMENT_BULL`, `PANIC_BOTTOM`, `OVERVALUATION_RISK` — based on a combination of equity-bond spread, margin ratio, and QVIX signal thresholds. Each state maps to a Utilization Rate range.

**Alternatives considered**:
- Weighted composite score (like the US L2): The US approach works because VIX/DXY/breadth signals are continuous and direction-symmetric. A-share regime is fundamentally regime-switching, not a linear spectrum; four named states better capture the "policy bull," "leverage bull," "value-bottom," and "bubble risk" paradigms.

**Rationale**: Named states are more interpretable in the dashboard narrative and map cleanly to the investment decision context.

---

### Decision 6: Deposit / Market Cap ratio uses M2 as numerator (not household savings deposit)

**Choice**: Use M2 broad money stock as the numerator (readily available monthly via Tushare macro interface) rather than household savings deposit sub-series which has a longer publication lag.

**Rationale**: M2 is available within ~15 days of month-end via Tushare; household savings deposit requires an additional 30-day wait. M2 is a slightly looser proxy but the direction signal is equivalent for the indicator's purpose.

## Risks / Trade-offs

**[Risk] Tushare daily call quota exhaustion during development / high-traffic use**
→ Mitigation: Strict ETL-on-demand with CSV caching; add explicit rate-limit error handling with a user-visible warning message rather than silent failure.

**[Risk] QVIX (A-share options vol index) data availability via Tushare is limited to certain subscription tiers**
→ Mitigation: Make QVIX a gracefully-degraded signal (score defaults to 0 / neutral) if unavailable; document the subscription requirement. If unavailable, Layer 2 falls back to 3-signal classification.

**[Risk] CSI 300 PE TTM from Tushare has 1-day publication lag, causing equity-bond spread to be T-1**
→ Mitigation: Document the lag clearly in the dashboard data-freshness note. The 1-day lag is acceptable for a daily-frequency indicator.

**[Risk] Limit-up / limit-down daily count API (Tushare `stk_limit`) may not cover all market sessions reliably**
→ Mitigation: Add data-completeness check; if count < 5 (implausibly low for any trading day), treat as missing and set sentinel to CLEAR rather than TRIGGERED.

**[Risk] Adding multiple new Tushare API calls slows down the initial Streamlit load**
→ Mitigation: Load China section lazily (behind a Streamlit expander or tab that only fetches on expansion), matching the existing lazy-load pattern.

## Migration Plan

1. Deploy new data fetchers behind the existing ETL-on-demand pattern — no data migration needed, caches build incrementally
2. The existing `analyze_china_signals()` output is used only in the China dashboard section; replacing it with the new three-layer output is a drop-in change for the UI layer
3. Add new dashboard components to the China module section without modifying existing US module components
4. On first run after deployment, `china_sentinel_state.json` will be initialised fresh (all CLEAR) — acceptable since there is no prior state to preserve

## Open Questions

- **QVIX subscription tier**: Confirm whether the current Tushare token includes `options` or `stk_optiondaily` access required for QVIX. If not, document the fallback path explicitly.
- **Limit-up/down count API**: Verify `pro.stk_limit` returns counts compatible with intraday limit-hit data (A-share limit-up counting convention varies between data providers).
- **DR007 data source**: Currently AkShare is used for DR007 (China macro). Confirm whether to consolidate to Tushare macro interface or keep AkShare for this series to avoid duplicate fetches.
- **Northbound flow channel migration**: Existing codebase uses AkShare for northbound flow. Confirm `pro.moneyflow_hsgt` returns equivalent daily net-buy values and migration does not break historical cache continuity.
