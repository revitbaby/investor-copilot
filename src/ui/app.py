import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from src.data.loader import DataLoader
from src.analysis.engine import calculate_net_liquidity, calculate_changes, analyze_signals
from src.llm.analyst import MacroAnalyst
from dotenv import load_dotenv

# Load env vars
load_dotenv()

st.set_page_config(page_title="Macro Liquidity AI Analyst", layout="wide")

st.title("Macro Liquidity AI Analyst")

# Sidebar
with st.sidebar:
    st.header("Settings")
    days_back = st.slider("Lookback Period (Days)", 90, 1825, 365)
    force_refresh = st.button("Refresh Data")
    
    st.info("""
    **Net Liquidity Formula:**
    Fed Balance Sheet - Reverse Repo - TGA
    
    **Signals:**
    Green: Rising Liq + Stable Vol
    Red: Falling Liq OR High Bond Vol (MOVE)
    """)

# Main Logic
# We use a simple function to handle loading. 
# st.cache_data handles caching the result of this function.
# If force_refresh is True, we can clear cache or just call loader with cache=False 
# but st.cache_data might return the old value if inputs match.
# Better pattern: Use a session state counter or similar to invalidate, 
# or just rely on loader's cache and skip st.cache_data for the fetching part if we want control.
# Actually, loader has disk cache. st.cache_data is memory cache.
# Let's trust loader's disk cache for persistence, and use st.cache_data for speed.

@st.cache_data(ttl=3600)
def get_market_data(days, _refresh_trigger):
    # _refresh_trigger is a dummy arg to force re-run if needed, 
    # but actually force_refresh button just triggers re-run of script.
    # To bypass cache, we can use clear_cache on button press or just pass a timestamp.
    loader = DataLoader()
    # We pass use_cache=False if we strictly want to hit APIs, 
    # but usually we want to use disk cache if valid.
    # The 'force_refresh' button in sidebar implies "fetch from API".
    return loader.fetch_all_data(days_back=days, use_cache=not _refresh_trigger)

# Refresh logic
refresh_state = False
if force_refresh:
    refresh_state = True
    st.cache_data.clear()

with st.spinner("Loading Market Data..."):
    try:
        df = get_market_data(days_back, refresh_state)
    except Exception as e:
        st.error(f"Error loading data: {e}")
        st.stop()
    
if df.empty:
    st.error("No data loaded. Please check API keys and connectivity.")
    st.stop()

# Analysis
# These are fast, no need to cache aggressively unless data is huge.
try:
    df = calculate_net_liquidity(df)
    signals = analyze_signals(df)
    changes = calculate_changes(df)
except Exception as e:
    st.error(f"Error in analysis: {e}")
    st.stop()

# Dashboard Layout

# 1. Metrics
st.subheader("Market Snapshot")
col1, col2, col3, col4 = st.columns(4)

net_liq = changes.get('Net Liquidity', {})
spy = changes.get('SPY', {})
vix = changes.get('VIX', {})
dxy = changes.get('DXY', {})

# Helpers
def fmt_delta(val, is_pct=False):
    suffix = "%" if is_pct else ""
    return f"{val:+.2f}{suffix}"

col1.metric(
    "Net Liquidity", 
    f"${net_liq.get('current', 0)/1000:.2f}T", 
    fmt_delta(net_liq.get('1w_pct', 0), True)
)
col2.metric(
    "S&P 500", 
    f"{spy.get('current', 0):.2f}", 
    fmt_delta(spy.get('1w_pct', 0), True)
)
col3.metric(
    "VIX", 
    f"{vix.get('current', 0):.2f}", 
    fmt_delta(vix.get('1w_delta', 0), False),
    delta_color="inverse" # VIX up is usually bad
)
col4.metric(
    "DXY", 
    f"{dxy.get('current', 0):.2f}", 
    fmt_delta(dxy.get('1w_pct', 0), True),
    delta_color="inverse" # DXY up often tightens conditions
)

# 2. Status
st.divider()
status_color = signals.get('Overall', 'GRAY')
# Map GREEN/RED to Streamlit colors or Emoji
color_map = {
    "GREEN": "🟢",
    "YELLOW": "🟡",
    "RED": "🔴",
    "GRAY": "⚪"
}
emoji = color_map.get(status_color, "⚪")

st.markdown(f"### Market Status: {emoji} {status_color}")
st.markdown(f"**Signal:** {signals.get('Overall_Reason', 'N/A')} | **Liq Trend:** {signals.get('Liquidity Trend')} | **Vol:** {signals.get('Volatility Regime')}")

# 3. Chart
st.subheader("Liquidity vs Market")
fig = go.Figure()

# Left Axis: Net Liquidity
fig.add_trace(go.Scatter(
    x=df.index, 
    y=df['Net Liquidity'],
    name="Net Liquidity (B)",
    line=dict(color='blue', width=2)
))

# Right Axis: SPY
fig.add_trace(go.Scatter(
    x=df.index, 
    y=df['SPY'],
    name="S&P 500",
    line=dict(color='orange', width=2),
    yaxis="y2"
))

fig.update_layout(
    yaxis=dict(title="Net Liquidity (Billions)", showgrid=True),
    yaxis2=dict(title="S&P 500 Price", overlaying="y", side="right", showgrid=False),
    hovermode="x unified",
    legend=dict(x=0, y=1.1, orientation="h"),
    height=500
)

st.plotly_chart(fig, use_container_width=True)

# 4. AI Report
st.divider()
st.subheader("AI Macro Strategist Analysis")

if st.button("Generate AI Report"):
    with st.spinner("Consulting the Macro Strategist (Gemini 3 Pro)..."):
        analyst = MacroAnalyst()
        # Context preparation
        context = {
            "signals": signals,
            "metrics": changes,
            # Pass last 5 rows of data for trend context if needed, or just latest
            "latest_values": df.iloc[-1].to_dict()
        }
        report = analyst.generate_report(context)
        st.markdown(report)

