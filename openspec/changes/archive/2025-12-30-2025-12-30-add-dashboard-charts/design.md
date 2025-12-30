## Context
Users want a deeper dive into the drivers of "Net Liquidity" and broader market context without leaving the app. The current single chart is insufficient for detailed analysis.

## Goals
- Display granular components of the Fed's balance sheet.
- Show key risk gauges (VIX, MOVE, Credit).
- Show cross-asset correlations (Gold, BTC, Oil, DXY).
- Maintain a clean, readable layout (2x2 grid).

## Decisions
- **Chart Library**: Continue using Plotly (via `st.plotly_chart`) for interactivity.
- **Data normalization**: 
    - For "Cross-Asset" and "Market Health" charts where scales vary wildly (e.g., BTC at 90k vs DXY at 100), we may need to default to "Percentage Change from Start Date" or dual axes. 
    - *Decision*: Implementation should try to group similar scales or use secondary axes where reasonable. For the proposal, we specify the data content; exact axis logic is an implementation detail but "normalization" (rebase to 100 or % change) is recommended for the Cross-Asset chart.
- **SPY Volume**: Will be added as a bar chart overlay or subplot on the Market Health chart, or a separate trace if using dual axes.
- **HYG/JNK**: Can be shown as a ratio (Credit Risk appetite) or raw prices. The request asks for "HYG/JNK", implying potentially both or the ratio. *Decision*: Fetch both, display both or ratio based on clarity during implementation.

## Risks
- **Performance**: Fetching more data (Volume, JNK, SOFR) adds slightly to load time. 
- **Clutter**: 4 complex charts in a grid might be cramped on smaller screens. Plotly's responsiveness helps, but we should minimize legends.

## Migration
- No database migration needed (cache is file-based). Old caches might miss the new columns (SOFR, JNK, Volume).
- **Strategy**: Invalidate cache (recommend user click "Refresh Data") or handle missing columns gracefully by fetching fresh if columns are missing.

