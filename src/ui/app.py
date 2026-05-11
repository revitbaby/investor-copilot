import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from pathlib import Path
from src.data.loader import DataLoader
from src.analysis.engine import calculate_net_liquidity, calculate_changes, analyze_signals, analyze_china_signals
from src.analysis.china_regime import (
    ChinaInputData,
    ChinaRegimeResult,
    compute_china_regime,
    save_china_sentinel_state,
    write_china_regime_snapshot,
)
from src.data.china_market_fetcher import (
    fetch_margin_ratio,
    fetch_csi300_pe,
    fetch_cgb10y_yield,
    fetch_equity_bond_spread,
    fetch_index_close,
    fetch_limit_counts,
    fetch_northbound_flow,
    fetch_southbound_flow,
    fetch_m2_monthly,
    fetch_market_total_amount,
    fetch_deposit_ratio,
    fetch_qvix,
)
from src.llm.analyst import MacroAnalyst
from src.llm.report_manager import ReportManager
from src.llm.regime_narrator import generate_regime_narrative, NarrativeResult
from src.regime.engine import RegimeEngine
from src.regime.models import RegimeResult
from src.portfolio.parser import parse_portfolio_csv
from src.portfolio.advisor import compute_advisory
from src.portfolio.models import AdvisoryResult
from src.ui.regime_components import (
    render_l3_alert_banner, render_regime_gauge,
    render_l1_scoring_table, render_l2_scoring_table,
    render_l3_sentinel_row, render_position_advisory,
    render_regime_timeline,
)
from src.ui.china_regime_components import (
    render_china_sentinel_banner,
    render_margin_ratio_card,
    render_equity_bond_spread_card,
    render_deposit_ratio_card,
    render_data_freshness_note,
    render_china_scoring_table,
    render_china_envelope_gauge,
    render_china_regime_timeline,
    northbound_disclosure_notice,
)
from src.utils.i18n import init_i18n, set_language, t, get_current_language
from datetime import datetime, date
from dotenv import load_dotenv
import os

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

# Data Loading Functions
def _cache_mtime(filename: str) -> float:
    """Return file mtime so @st.cache_data re-fetches when the CSV changes."""
    path = os.path.join("data_cache", filename)
    return os.path.getmtime(path) if os.path.exists(path) else 0.0

@st.cache_data(ttl=3600)
def get_market_data(days, cache_mtime: float = 0.0):
    loader = DataLoader()
    return loader.fetch_all_data(days_back=days, use_cache=True)

@st.cache_data(ttl=3600)
def get_sector_etf_data(days, cache_mtime: float = 0.0):
    loader = DataLoader()
    return loader.fetch_sector_etf_data(days_back=days, use_cache=True)

@st.cache_data(ttl=3600)
def get_china_data(days, cache_mtime: float = 0.0):
    loader = DataLoader()
    return loader.fetch_china_data(days_back=days, use_cache=True)

# Refresh logic: when user clicks refresh, delete today's cache files so a fresh
# fetch is triggered, then clear Streamlit's in-memory cache.
if force_refresh:
    for fname in ("macro_data.csv", "sector_etf_data.csv", "china_data.csv"):
        p = os.path.join("data_cache", fname)
        if os.path.exists(p):
            os.remove(p)
    st.cache_data.clear()

# Helper for consistent sub-charts
def create_sub_chart(data, columns, title, right_axis_columns=None, normalize=False):
    fig = go.Figure()
    
    # Prepare data
    plot_data = data.copy()
    if normalize:
        # Rebase to % change from start
        first_valid = plot_data.first_valid_index()
        if first_valid:
            plot_data = plot_data.apply(lambda x: (x / x.loc[first_valid] - 1) * 100)
    
    # Color sequence
    colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd', '#8c564b', '#e377c2', '#7f7f7f', '#bcbd22', '#17becf']
    color_idx = 0

    # Left Axis
    for col in columns:
        if col in plot_data.columns:
            label = t(col.lower()) if t(col.lower()) != col.lower() else col
            fig.add_trace(go.Scatter(
                x=plot_data.index, y=plot_data[col], name=label,
                line=dict(width=1.5, color=colors[color_idx % len(colors)])
            ))
            color_idx += 1
            
    # Right Axis
    if right_axis_columns:
        for col in right_axis_columns:
            if col in plot_data.columns:
                label = t(col.lower()) if t(col.lower()) != col.lower() else col
                fig.add_trace(go.Scatter(
                    x=plot_data.index, y=plot_data[col], name=label,
                    yaxis="y2",
                    line=dict(width=1.5, dash='dot', color=colors[color_idx % len(colors)])
                ))
                color_idx += 1

    layout_args = dict(
        title=dict(text=title, font=dict(size=14)),
        margin=dict(l=20, r=20, t=60, b=20),
        height=300,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        hovermode="x unified"
    )
    
    if right_axis_columns:
        layout_args['yaxis2'] = dict(overlaying="y", side="right", showgrid=False)
        
    fig.update_layout(**layout_args)
    return fig

def render_us_dashboard(days_back):
    with st.spinner(t("loading_data")):
        try:
            df = get_market_data(days_back, _cache_mtime("macro_data.csv"))
        except Exception as e:
            st.error(f"{t('error_loading')}: {e}")
            return

    if df.empty:
        st.error(t("no_data"))
        return

    # Fetch sector ETF data for S5FI
    try:
        sector_df = get_sector_etf_data(days_back, _cache_mtime("sector_etf_data.csv"))
    except Exception:
        sector_df = pd.DataFrame()

    # Analysis
    try:
        df = calculate_net_liquidity(df)
        signals = analyze_signals(df)
        changes = calculate_changes(df)
    except Exception as e:
        st.error(f"{t('error_analysis')}: {e}")
        return

    # --- Regime Scoring Engine ---
    regime_result: RegimeResult | None = None
    narrative: NarrativeResult | None = None
    advisory: AdvisoryResult | None = None

    try:
        engine = RegimeEngine()
        regime_result = engine.run(df, sector_df)
    except Exception as e:
        st.warning(f"Regime scoring engine error: {e}")

    if regime_result:
        # L3 Alert Banner (conditional)
        render_l3_alert_banner(regime_result)

        # Regime Gauge (hero)
        st.subheader(f"🎯 {t('regime_scoring_header')}")

        # Portfolio upload
        current_position_pct = None
        uploaded_file = st.file_uploader(
            t("regime_upload_prompt"), type=["csv"],
            key="portfolio_csv", label_visibility="collapsed",
        )
        if uploaded_file is not None:
            holdings, errors = parse_portfolio_csv(uploaded_file.getvalue())
            if errors:
                for err in errors:
                    st.error(err)
            elif holdings:
                total_value = st.number_input("Total Account Value ($)", value=100000.0, key="total_val")
                cash = st.number_input("Cash ($)", value=10000.0, key="cash_val")
                advisory = compute_advisory(
                    holdings, total_value, cash, regime_result,
                    engine.config.position_advisor,
                )
                current_position_pct = advisory.current_exposure_pct

        render_regime_gauge(regime_result, current_position_pct)

        # L1 + L2 two-column layout
        col_l1, col_l2 = st.columns(2)

        # Generate regime narrative (lazy, only on first load)
        narrative_key = f"regime_narrative_{datetime.now().strftime('%Y-%m-%d')}"
        if narrative_key not in st.session_state:
            try:
                regime_data = regime_result.to_dict()
                advisory_data = advisory.to_dict() if advisory else None
                raw_data = {
                    "signals": signals,
                    "metrics": changes,
                }
                narrative = generate_regime_narrative(
                    regime_data, advisory_data, raw_data,
                    language=get_current_language(),
                )
                st.session_state[narrative_key] = narrative
            except Exception:
                narrative = NarrativeResult()
                st.session_state[narrative_key] = narrative
        else:
            narrative = st.session_state[narrative_key]

        with col_l1:
            render_l1_scoring_table(regime_result, narrative)

        with col_l2:
            render_l2_scoring_table(regime_result, narrative)

        # L3 Sentinel Row
        render_l3_sentinel_row(regime_result, narrative)

        # Position Advisory
        render_position_advisory(advisory, narrative)

        # Regime Timeline
        history_path = Path("data_cache/regime_history.csv")
        if history_path.exists():
            try:
                history_df = pd.read_csv(history_path)
            except Exception:
                history_df = None
        else:
            history_df = None
        render_regime_timeline(history_df)

        st.divider()

    # --- Existing Dashboard Content Below ---
    # 1. Metrics
    st.subheader(t("market_snapshot"))
    col1, col2, col3, col4 = st.columns(4)

    net_liq = changes.get('Net Liquidity', {})
    spy = changes.get('SPY', {})
    vix = changes.get('VIX', {})
    dxy = changes.get('DXY', {})

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
        delta_color="inverse"
    )
    col4.metric(
        t("dxy"), 
        f"{dxy.get('current', 0):.2f}", 
        fmt_delta(dxy.get('1w_pct', 0), True),
        delta_color="inverse"
    )

    # 2. Status
    st.divider()
    status_color = signals.get('Overall', 'GRAY')
    color_map = {"GREEN": "🟢", "YELLOW": "🟡", "RED": "🔴", "GRAY": "⚪"}
    emoji = color_map.get(status_color, "⚪")

    st.markdown(f"### {t('market_status')}: {emoji} {status_color}")
    st.markdown(f"**{t('signal')}:** {signals.get('Overall_Reason', 'N/A')} | **{t('liq_trend')}:** {signals.get('Liquidity Trend')} | **{t('vol')}:** {signals.get('Volatility Regime')}")

    # 3. Chart
    st.subheader(t("liquidity_vs_market"))
    fig = go.Figure()

    fig.add_trace(go.Scatter(x=df.index, y=df['Net Liquidity'], name=t("chart_net_liq"), line=dict(color='blue', width=2)))
    fig.add_trace(go.Scatter(x=df.index, y=df['SPY'], name=t("chart_sp500"), line=dict(color='orange', width=2), yaxis="y2"))

    fig.update_layout(
        yaxis=dict(title=t("net_liq_axis"), showgrid=True),
        yaxis2=dict(title=t("sp500_axis"), overlaying="y", side="right", showgrid=False),
        hovermode="x unified",
        legend=dict(x=0, y=1.1, orientation="h"),
        height=500
    )
    st.plotly_chart(fig, use_container_width=True)

    # 3.1 Detailed Charts
    st.divider()
    col1, col2 = st.columns(2)
    col3, col4 = st.columns(2)

    with col1:
        left = ['WALCL']
        right = ['RRP', 'TGA']
        fig1 = create_sub_chart(df, left, t("chart_cb_liq"), right_axis_columns=right)
        st.plotly_chart(fig1, use_container_width=True)

    with col2:
        fig2 = create_sub_chart(df, ['SOFR'], t("chart_rates"))
        st.plotly_chart(fig2, use_container_width=True)

    with col3:
        fig3 = go.Figure()
        if 'VIX' in df.columns: fig3.add_trace(go.Scatter(x=df.index, y=df['VIX'], name="VIX", line=dict(color='#d62728')))
        if 'MOVE' in df.columns: fig3.add_trace(go.Scatter(x=df.index, y=df['MOVE'], name="MOVE", line=dict(color='#9467bd')))
        if 'JNK' in df.columns: fig3.add_trace(go.Scatter(x=df.index, y=df['JNK'], name="JNK", yaxis="y2", line=dict(dash='dot', color='#1f77b4')))
        if 'SPY_Volume' in df.columns:
            fig3.add_trace(go.Bar(x=df.index, y=df['SPY_Volume'], name=t("volume"), yaxis="y3", marker_color='grey', opacity=0.2))
        
        fig3.update_layout(
            title=dict(text=t("chart_market_health"), font=dict(size=14)),
            margin=dict(l=20, r=20, t=60, b=20),
            height=300,
            legend=dict(orientation="h", y=1.1),
            yaxis=dict(title="Vol"),
            yaxis2=dict(overlaying="y", side="right", showgrid=False, title="JNK"),
            yaxis3=dict(overlaying="y", side="right", showgrid=False, showticklabels=False),
            hovermode="x unified"
        )
        st.plotly_chart(fig3, use_container_width=True)

    with col4:
        assets = ['DXY', 'GOLD', 'OIL', 'BTC', 'US10Y']
        assets = [c for c in assets if c in df.columns]
        fig4 = create_sub_chart(df, assets, t("chart_cross_asset") + " (%)", normalize=True)
        st.plotly_chart(fig4, use_container_width=True)

    # 4. AI Report (with regime narrative integration)
    render_ai_report(df, signals, changes, market="us", narrative=narrative)

def _fetch_china_regime_data(today: date) -> tuple[ChinaRegimeResult | None, dict]:
    """
    Fetch all new indicators and run compute_china_regime.
    Returns (regime_result, data_dates_dict).
    Catches all exceptions — UI should degrade gracefully on failure.
    """
    data_dates: dict[str, str] = {}
    any_stale = False

    try:
        # ── New indicator fetchers ────────────────────────────────────────
        margin_df, m_stale = fetch_margin_ratio(today)
        equity_bond_spread, eb_stale = fetch_equity_bond_spread(today)
        _, dep_month, dep_stale = fetch_deposit_ratio(today)
        limit_data, lim_stale = fetch_limit_counts(today)
        nb_data, nb_stale = fetch_northbound_flow(today)
        sb_data, sb_stale = fetch_southbound_flow(today)
        total_amount, amount_ma20, amt_stale = fetch_market_total_amount(today)
        qvix_val, qvix_stale = fetch_qvix(today)

        any_stale = any([m_stale, eb_stale, dep_stale, lim_stale, nb_stale, sb_stale, amt_stale, qvix_stale])

        if dep_month:
            data_dates["M2/Deposit"] = dep_month
        data_dates["Market"] = today.strftime("%Y-%m-%d")

        # Extract scalar values from fetched data
        latest_margin_pct: float | None = None
        if margin_df is not None and not margin_df.empty and "Margin_Ratio_Pct" in margin_df.columns:
            series = margin_df["Margin_Ratio_Pct"].dropna()
            if not series.empty:
                latest_margin_pct = float(series.iloc[-1])

        # ── Existing China data for L1 signals ───────────────────────────
        # Pull M1/M2/TSF from the existing combined china_data cache
        loader = DataLoader()
        china_df = loader.fetch_china_data(days_back=90, use_cache=True)
        m1_yoy = m1_yoy_prev = None
        m1_m2_spread = m1_m2_spread_prev = None
        tsf_yoy = tsf_yoy_prev = None
        dr007 = omo_rate = None
        if not china_df.empty:
            if "M1_YoY" in china_df.columns:
                m1_vals = china_df["M1_YoY"].dropna()
                if len(m1_vals) >= 1:
                    m1_yoy = float(m1_vals.iloc[-1])
                if len(m1_vals) >= 2:
                    m1_yoy_prev = float(m1_vals.iloc[-2])
            if "M1_M2_Gap" in china_df.columns:
                gap_vals = china_df["M1_M2_Gap"].dropna()
                if len(gap_vals) >= 1:
                    m1_m2_spread = float(gap_vals.iloc[-1])
                if len(gap_vals) >= 2:
                    m1_m2_spread_prev = float(gap_vals.iloc[-2])
            if "DR007" in china_df.columns:
                dr007_vals = china_df["DR007"].dropna()
                if not dr007_vals.empty:
                    dr007 = float(dr007_vals.iloc[-1])
            # OMO 7-day rate ≈ 1.5–2.0% (hardcode current PBoC rate as fallback)
            omo_rate = 1.5  # current 7-day OMO rate

        # ── Assemble input data ────────────────────────────────────────
        input_data = ChinaInputData(
            dr007=dr007,
            omo_rate=omo_rate,
            m1_yoy=m1_yoy,
            m1_yoy_prev=m1_yoy_prev,
            m1_m2_spread=m1_m2_spread,
            m1_m2_spread_prev=m1_m2_spread_prev,
            tsf_yoy=tsf_yoy,
            tsf_yoy_prev=tsf_yoy_prev,
            equity_bond_spread=equity_bond_spread,
            margin_ratio_pct=latest_margin_pct,
            qvix=qvix_val,
            northbound_5d_cumulative=nb_data["cumulative_5d_yi"] if nb_data else None,
            limit_up_count=limit_data["up_count"] if limit_data else None,
            limit_down_count=limit_data["down_count"] if limit_data else None,
            zt_count=limit_data["up_count"] if limit_data else None,
            dt_count=limit_data["down_count"] if limit_data else None,
            southbound_net_buy=sb_data["net_buy_yi"] if sb_data else None,
            southbound_sigma_dev=sb_data["sigma_deviation"] if sb_data else None,
            total_amount=total_amount,
            total_amount_ma20=amount_ma20,
            data_date=today,
        )

        regime_result = compute_china_regime(input_data)

        # Persist history snapshot
        try:
            write_china_regime_snapshot(
                snapshot_date=today,
                l1_result=regime_result.layer1,
                l2_result=regime_result.layer2,
                l3_state=regime_result.layer3,
                envelope=regime_result.envelope,
                csi300_close=None,
            )
        except Exception as e:
            st.warning(f"Failed to write regime history snapshot: {e}")

        return regime_result, data_dates

    except Exception as e:
        st.warning(f"China regime computation failed: {e}")
        return None, data_dates


def render_china_dashboard(days_back):
    with st.spinner(t("loading_data")):
        try:
            df = get_china_data(days_back, _cache_mtime("china_data.csv"))
        except Exception as e:
            st.error(f"{t('error_loading')}: {e}")
            return

    if df.empty:
        st.error(t("no_data"))
        return

    # Analysis (existing)
    try:
        signals = analyze_china_signals(df)
        changes = calculate_changes(df)
    except Exception as e:
        st.error(f"{t('error_analysis')}: {e}")
        return

    current_lang = get_current_language()
    today = date.today()

    # ── New: China Regime Scoring Engine ─────────────────────────────────────
    china_regime_result: ChinaRegimeResult | None = None
    regime_cache_key = f"china_regime_{today.strftime('%Y-%m-%d')}"
    if regime_cache_key not in st.session_state:
        with st.spinner("Computing A-share regime..."):
            china_regime_result, data_dates = _fetch_china_regime_data(today)
            st.session_state[regime_cache_key] = china_regime_result
            st.session_state[f"{regime_cache_key}_dates"] = data_dates
    else:
        china_regime_result = st.session_state[regime_cache_key]
        data_dates = st.session_state.get(f"{regime_cache_key}_dates", {})

    # Store for future LLM integration (task 10.6)
    if china_regime_result is not None:
        st.session_state["china_regime_result"] = china_regime_result

    # ── L3 Sentinel Warning Banner (task 10.2) ────────────────────────────────
    if china_regime_result is not None:
        render_china_sentinel_banner(china_regime_result.layer3, current_lang)

    # ── Three indicator cards — shared controls ────────────────────────────────
    from src.utils.i18n import t as _t
    col_idx_ctrl, col_period_ctrl = st.columns([1, 1])
    with col_idx_ctrl:
        index_label = st.radio(
            _t("cn_index_overlay_label"),
            [_t("cn_index_hs300"), _t("cn_index_gem")],
            horizontal=True,
            key="cn_index_choice",
        )
    with col_period_ctrl:
        period_choice = st.radio(
            _t("cn_period_label"),
            ["1Y", "3Y", "5Y", "10Y", "15Y"],
            index=1,
            horizontal=True,
            key="cn_period_choice",
        )

    idx_symbol = "sh000300" if index_label == _t("cn_index_hs300") else "sz399006"
    index_series, _ = fetch_index_close(idx_symbol, start_date=date(2015, 1, 1))
    if index_series is not None:
        index_series.name = index_label

    # ── Three indicator cards (task 10.3) ─────────────────────────────────────
    try:
        margin_df, _ = fetch_margin_ratio(today)
        eb_df, _ = fetch_equity_bond_spread(today)
        dep_df, _, _ = fetch_deposit_ratio(today)
        from src.data.china_market_fetcher import _load_cache
        margin_history = _load_cache("margin_ratio.csv")
        eb_history = _load_cache("equity_bond_spread.csv")
        dep_history = _load_cache("deposit_ratio.csv")
    except Exception:
        margin_history = eb_history = dep_history = None

    col_m, col_eb, col_dep = st.columns(3)
    with col_m:
        render_margin_ratio_card(margin_history, index_series, period_choice, current_lang)
    with col_eb:
        render_equity_bond_spread_card(eb_history, index_series, period_choice, current_lang)
    with col_dep:
        render_deposit_ratio_card(dep_history, index_series, period_choice, current_lang)

    if data_dates:
        render_data_freshness_note(data_dates, language=current_lang)

    # ── Scoring table + Envelope gauge (task 10.4) ────────────────────────────
    if china_regime_result is not None:
        st.divider()
        col_scoring, col_gauge = st.columns([2, 1])
        with col_scoring:
            render_china_scoring_table(china_regime_result, current_lang)
        with col_gauge:
            render_china_envelope_gauge(china_regime_result.envelope, current_lang)

    # 1. Metrics
    st.subheader(t("market_snapshot") + " (China)")
    col1, col2, col3, col4 = st.columns(4)
    
    m1_m2 = changes.get('M1_M2_Gap', {})
    soc_fin = changes.get('Social_Financing_Increment', {})
    nb_flow = changes.get('Northbound_Net_Inflow', {})
    sh_idx = changes.get('SH_Index', {})

    def fmt_delta(val, is_pct=False):
        suffix = "%" if is_pct else ""
        return f"{val:+.2f}{suffix}"

    sb_flow = changes.get('Southbound_Net_Inflow', {})

    col1.metric(t("m1_m2_gap"), f"{m1_m2.get('current', 0):.2f}%", fmt_delta(m1_m2.get('1m_delta', 0), True))
    col2.metric(t("soc_fin"), f"{soc_fin.get('current', 0):.0f}", fmt_delta(soc_fin.get('1m_pct', 0), True))
    col3.metric(t("southbound"), f"{sb_flow.get('current', 0):.1f}", fmt_delta(sb_flow.get('1w_delta', 0), False))
    col4.metric("SH Index", f"{sh_idx.get('current', 0):.0f}", fmt_delta(sh_idx.get('1w_pct', 0), True))

    # 2. Status
    st.divider()
    status_color = signals.get('Overall', 'GRAY')
    color_map = {"GREEN": "🟢", "YELLOW": "🟡", "RED": "🔴", "GRAY": "⚪"}
    emoji = color_map.get(status_color, "⚪")

    st.markdown(f"### {t('market_status')}: {emoji} {status_color}")
    st.markdown(f"**{t('signal')}:** {signals.get('Overall_Reason', 'N/A')} | **{t('macro_liq')}:** {signals.get('Macro_Liquidity')} | **{t('foreign_flow')}:** {signals.get('Foreign_Flow')}")

    # 3. Charts
    st.subheader(t("cn_macro"))
    col1, col2 = st.columns(2)
    with col1:
        # Macro: DR007 + SHIBOR
        fig1 = go.Figure()
        for col_name, label, color in [
            ('DR007', 'DR007 (FR007)', '#d62728'),
            ('SHIBOR_3M', 'SHIBOR 3M', '#1f77b4'),
            ('SHIBOR_ON', 'SHIBOR O/N', '#2ca02c'),
        ]:
            if col_name in df.columns:
                fig1.add_trace(go.Scatter(x=df.index, y=df[col_name], name=label, line=dict(width=1.5, color=color)))
        fig1.update_layout(
            title=dict(text=t("cn_macro") + " - Rates", font=dict(size=14)),
            margin=dict(l=20, r=20, t=60, b=20), height=300,
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            hovermode="x unified"
        )
        st.plotly_chart(fig1, use_container_width=True)
        
    with col2:
        # Meso: M1, M2 Gap
        fig2 = go.Figure()
        if 'M1_YoY' in df.columns:
            fig2.add_trace(go.Scatter(x=df.index, y=df['M1_YoY'], name="M1 YoY", line=dict(color='#ff7f0e')))
        if 'M2_YoY' in df.columns:
            fig2.add_trace(go.Scatter(x=df.index, y=df['M2_YoY'], name="M2 YoY", line=dict(color='#1f77b4')))
        if 'M1_M2_Gap' in df.columns:
            fig2.add_trace(go.Bar(x=df.index, y=df['M1_M2_Gap'], name=t("m1_m2_gap"), marker_color='grey', opacity=0.3))
        fig2.update_layout(
            title=dict(text=t("cn_meso"), font=dict(size=14)),
            margin=dict(l=20, r=20, t=60, b=20), height=300,
            hovermode="x unified"
        )
        st.plotly_chart(fig2, use_container_width=True)

    st.subheader(t("cn_micro"))
    col3, col4 = st.columns(2)
    with col3:
        fig3 = go.Figure()
        if 'Northbound_Net_Inflow' in df.columns:
            nb = df['Northbound_Net_Inflow'].dropna()
            if not nb.empty:
                colors = ['#d62728' if v < 0 else '#2ca02c' for v in nb]
                fig3.add_trace(go.Bar(x=nb.index, y=nb, name=t("northbound"), marker_color=colors))
        # Task 9.9: Add disclosure-stopped notice to title
        nb_title = t("northbound") + " (亿元, via Tushare)<br>" + \
            f"<span style='color:orange;font-size:11px'>{northbound_disclosure_notice()}</span>"
        fig3.update_layout(
            title=dict(text=nb_title, font=dict(size=14)),
            margin=dict(l=20, r=20, t=70, b=20), height=310,
            hovermode="x unified"
        )
        st.plotly_chart(fig3, use_container_width=True)
    with col4:
        fig4 = go.Figure()
        if 'A_Share_Volume' in df.columns:
            fig4.add_trace(go.Bar(x=df.index, y=df['A_Share_Volume'], name=t("turnover"), marker_color='#1f77b4', opacity=0.6))
        if 'SH_Index' in df.columns:
            fig4.add_trace(go.Scatter(x=df.index, y=df['SH_Index'], name="SH Index", yaxis="y2", line=dict(color='#ff7f0e', width=1.5)))
        fig4.update_layout(
            title=dict(text=t("turnover") + " & SH Index", font=dict(size=14)),
            margin=dict(l=20, r=20, t=60, b=20), height=300,
            yaxis2=dict(overlaying="y", side="right", showgrid=False),
            hovermode="x unified"
        )
        st.plotly_chart(fig4, use_container_width=True)

    # Stock-bond spread row
    if 'Stock_Bond_Spread' in df.columns or 'CSI300_PE_TTM' in df.columns:
        st.subheader(t("stock_bond_spread") + " & " + t("csi300_pe"))
        col_sbs, col_pe = st.columns(2)
        with col_sbs:
            fig_sbs = go.Figure()
            if 'Stock_Bond_Spread' in df.columns:
                sbs = df['Stock_Bond_Spread'].dropna()
                fig_sbs.add_trace(go.Scatter(
                    x=sbs.index, y=sbs,
                    name=t("stock_bond_spread"),
                    line=dict(color='#ff7f0e', width=1.5),
                    fill='tozeroy', fillcolor='rgba(255,127,14,0.08)'
                ))
                # Reference line at 0
                fig_sbs.add_hline(y=0, line_dash="dash", line_color="grey", line_width=1)
                # Reference line at historical mean
                mean_val = sbs.mean()
                fig_sbs.add_hline(
                    y=mean_val, line_dash="dot", line_color="#1f77b4", line_width=1,
                    annotation_text=f"均值 {mean_val:.2f}%",
                    annotation_position="bottom right"
                )
            if 'SH_Index' in df.columns:
                fig_sbs.add_trace(go.Scatter(
                    x=df.index, y=df['SH_Index'].dropna(),
                    name="SH Index", yaxis="y2",
                    line=dict(color='#aec7e8', width=1), opacity=0.5
                ))
            fig_sbs.update_layout(
                title=dict(text=t("stock_bond_spread") + " (%) = 1/PE - 10Y债", font=dict(size=14)),
                margin=dict(l=20, r=20, t=60, b=20), height=320,
                yaxis=dict(title="%"),
                yaxis2=dict(overlaying="y", side="right", showgrid=False),
                hovermode="x unified",
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            )
            st.plotly_chart(fig_sbs, use_container_width=True)
        with col_pe:
            fig_pe = go.Figure()
            if 'CSI300_PE_TTM' in df.columns:
                pe = df['CSI300_PE_TTM'].dropna()
                fig_pe.add_trace(go.Scatter(
                    x=pe.index, y=pe,
                    name=t("csi300_pe"),
                    line=dict(color='#9467bd', width=1.5)
                ))
                mean_pe = pe.mean()
                fig_pe.add_hline(
                    y=mean_pe, line_dash="dot", line_color="#1f77b4", line_width=1,
                    annotation_text=f"均值 {mean_pe:.1f}x",
                    annotation_position="bottom right"
                )
            if 'CN_10Y_Yield' in df.columns:
                fig_pe.add_trace(go.Scatter(
                    x=df.index, y=df['CN_10Y_Yield'].dropna(),
                    name="10Y Yield (%)", yaxis="y2",
                    line=dict(color='#d62728', width=1, dash='dot')
                ))
            fig_pe.update_layout(
                title=dict(text=t("csi300_pe") + " & 10Y国债", font=dict(size=14)),
                margin=dict(l=20, r=20, t=60, b=20), height=320,
                yaxis=dict(title="PE (x)"),
                yaxis2=dict(overlaying="y", side="right", showgrid=False, title="%"),
                hovermode="x unified",
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            )
            st.plotly_chart(fig_pe, use_container_width=True)

    st.subheader(t("hk_market"))
    col5, col6 = st.columns(2)
    with col5:
        fig5 = go.Figure()
        if 'Southbound_Net_Inflow' in df.columns:
            sb = df['Southbound_Net_Inflow'].dropna()
            colors = ['#d62728' if v < 0 else '#2ca02c' for v in sb]
            fig5.add_trace(go.Bar(x=sb.index, y=sb, name=t("southbound"), marker_color=colors))
        fig5.update_layout(
            title=dict(text=t("southbound"), font=dict(size=14)),
            margin=dict(l=20, r=20, t=60, b=20), height=300,
            hovermode="x unified"
        )
        st.plotly_chart(fig5, use_container_width=True)

    # ── Regime Timeline (task 10.5) ───────────────────────────────────────────
    st.divider()
    history_path = Path("data_cache/china_regime_history.csv")
    if history_path.exists():
        try:
            china_history_df = pd.read_csv(history_path)
        except Exception:
            china_history_df = None
    else:
        china_history_df = None
    render_china_regime_timeline(china_history_df, current_lang)

    # AI Report for China
    render_ai_report(df, signals, changes, market="china")

def render_ai_report(df, signals, changes, market="us", narrative: NarrativeResult | None = None):
    st.divider()
    st.subheader(t("ai_analysis"))

    # If regime narrative succeeded, show executive summary and playbook from it
    if narrative and narrative.success and market == "us":
        if narrative.executive_summary:
            st.markdown("### Executive Summary")
            st.markdown(narrative.executive_summary)
        if narrative.investment_playbook:
            st.markdown("### Investment Playbook")
            st.markdown(narrative.investment_playbook)
        st.divider()

    report_manager = ReportManager()
    available_reports = report_manager.list_available_reports()
    report_dates = sorted(list(set(r["date"] for r in available_reports)), reverse=True)
    today_str = datetime.now().strftime("%Y-%m-%d")
    if today_str not in report_dates:
        report_dates.insert(0, today_str)

    selected_date = st.selectbox("Report Date / 报告日期", options=report_dates, index=0, key=f"report_date_{market}")
    current_lang = get_current_language()
    report_lang_key = f"{current_lang}_{market}"
    cached_report = report_manager.load_report(selected_date, report_lang_key)

    if cached_report:
        st.markdown(cached_report["content"])
        st.caption(f"Generated at: {cached_report.get('timestamp', 'Unknown')}")
        if selected_date == today_str and st.button(t("generate_report") + " (Regenerate)", key=f"regen_{market}"):
             generate_and_display_report(df, signals, changes, report_manager, today_str, report_lang_key, market)
    else:
        if selected_date == today_str:
            if st.button(t("generate_report"), key=f"gen_{market}"):
                 generate_and_display_report(df, signals, changes, report_manager, today_str, report_lang_key, market)
        else:
            st.info("No report available.")

def generate_and_display_report(df, signals, changes, report_manager, today_str, lang_key, market="us"):
    with st.spinner(t("generating_spinner")):
        analyst = MacroAnalyst()
        base_lang = lang_key.split("_")[0]
        context = {
            "signals": signals,
            "metrics": changes,
            "latest_values": df.iloc[-1].to_dict(),
            "market": market
        }
        report = analyst.generate_report(context, language=base_lang)
        report_manager.save_report(today_str, lang_key, report, context)
        st.rerun()

# Main Tabs
tab1, tab2 = st.tabs([t("tab_global"), t("tab_china")])

with tab1:
    render_us_dashboard(days_back)

with tab2:
    render_china_dashboard(days_back)
