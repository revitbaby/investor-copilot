import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from src.data.loader import DataLoader
from src.analysis.engine import calculate_net_liquidity, calculate_changes, analyze_signals
from src.llm.analyst import MacroAnalyst
from src.llm.report_manager import ReportManager
from src.utils.i18n import init_i18n, set_language, t, get_current_language
from datetime import datetime
from dotenv import load_dotenv

# Load env vars
load_dotenv()

st.set_page_config(page_title="Macro Liquidity AI Analyst", layout="wide")

# Initialize i18n
init_i18n()

st.title(t("title"))

# Sidebar
with st.sidebar:
    st.header(t("settings"))
    
    # Language Selector
    lang_options = {"English": "en", "中文": "zh"}
    # Reverse map for display
    current_lang = get_current_language()
    current_index = 0 if current_lang == "en" else 1
    
    selected_lang_label = st.radio(
        "Language / 语言", 
        options=list(lang_options.keys()), 
        index=current_index,
        horizontal=True
    )
    
    if lang_options[selected_lang_label] != current_lang:
        set_language(lang_options[selected_lang_label])
        st.rerun()

    days_back = st.slider(t("lookback"), 90, 1825, 365)
    force_refresh = st.button(t("refresh_data"))
    
    st.info(f"{t('info_formula')}\n\n{t('info_signals')}")

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

with st.spinner(t("loading_data")):
    try:
        df = get_market_data(days_back, refresh_state)
    except Exception as e:
        st.error(f"{t('error_loading')}: {e}")
        st.stop()
    
if df.empty:
    st.error(t("no_data"))
    st.stop()

# Analysis
# These are fast, no need to cache aggressively unless data is huge.
try:
    df = calculate_net_liquidity(df)
    signals = analyze_signals(df)
    changes = calculate_changes(df)
except Exception as e:
    st.error(f"{t('error_analysis')}: {e}")
    st.stop()

# Dashboard Layout

# 1. Metrics
st.subheader(t("market_snapshot"))
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
    t("net_liquidity"), 
    f"${net_liq.get('current', 0)/1000:.2f}T", 
    fmt_delta(net_liq.get('1w_pct', 0), True)
)
col2.metric(
    t("sp500"), 
    f"{spy.get('current', 0):.2f}", 
    fmt_delta(spy.get('1w_pct', 0), True)
)
col3.metric(
    t("vix"), 
    f"{vix.get('current', 0):.2f}", 
    fmt_delta(vix.get('1w_delta', 0), False),
    delta_color="inverse" # VIX up is usually bad
)
col4.metric(
    t("dxy"), 
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

st.markdown(f"### {t('market_status')}: {emoji} {status_color}")
st.markdown(f"**{t('signal')}:** {signals.get('Overall_Reason', 'N/A')} | **{t('liq_trend')}:** {signals.get('Liquidity Trend')} | **{t('vol')}:** {signals.get('Volatility Regime')}")

# 3. Chart
st.subheader(t("liquidity_vs_market"))
fig = go.Figure()

# Left Axis: Net Liquidity
fig.add_trace(go.Scatter(
    x=df.index, 
    y=df['Net Liquidity'],
    name=t("chart_net_liq"),
    line=dict(color='blue', width=2)
))

# Right Axis: SPY
fig.add_trace(go.Scatter(
    x=df.index, 
    y=df['SPY'],
    name=t("chart_sp500"),
    line=dict(color='orange', width=2),
    yaxis="y2"
))

fig.update_layout(
    yaxis=dict(title=t("net_liq_axis"), showgrid=True),
    yaxis2=dict(title=t("sp500_axis"), overlaying="y", side="right", showgrid=False),
    hovermode="x unified",
    legend=dict(x=0, y=1.1, orientation="h"),
    height=500
)

st.plotly_chart(fig, use_container_width=True)

# 4. AI Report
st.divider()
st.subheader(t("ai_analysis"))

# Report History Logic
report_manager = ReportManager()
available_reports = report_manager.list_available_reports()

# Report Selector
report_dates = sorted(list(set(r["date"] for r in available_reports)), reverse=True)
today_str = datetime.now().strftime("%Y-%m-%d")

# Add today if not present (so we can select it to generate)
if today_str not in report_dates:
    report_dates.insert(0, today_str)

selected_date = st.selectbox("Report Date / 报告日期", options=report_dates, index=0)
current_lang = get_current_language()

# Check if report exists for selected date/lang
cached_report = report_manager.load_report(selected_date, current_lang)

if cached_report:
    st.markdown(cached_report["content"])
    st.caption(f"Generated at: {cached_report.get('timestamp', 'Unknown')}")
    
    # Allow regeneration only if it's today
    if selected_date == today_str:
        if st.button(t("generate_report") + " (Regenerate)"):
            with st.spinner(t("generating_spinner")):
                analyst = MacroAnalyst()
                context = {
                    "signals": signals,
                    "metrics": changes,
                    "latest_values": df.iloc[-1].to_dict()
                }
                report = analyst.generate_report(context, language=current_lang)
                # Save to cache
                report_manager.save_report(today_str, current_lang, report, context)
                st.rerun()

else:
    if selected_date == today_str:
        if st.button(t("generate_report")):
            with st.spinner(t("generating_spinner")):
                analyst = MacroAnalyst()
                context = {
                    "signals": signals,
                    "metrics": changes,
                    "latest_values": df.iloc[-1].to_dict()
                }
                report = analyst.generate_report(context, language=current_lang)
                # Save to cache
                report_manager.save_report(today_str, current_lang, report, context)
                st.rerun()
    else:
        st.info("No report available for this date/language.")

