"""Streamlit / Plotly UI components for the China A-share regime scoring engine."""

from __future__ import annotations

from datetime import date

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src.analysis.china_regime import (
    ChinaEnvelopeResult,
    ChinaL2Regime,
    ChinaRegimeResult,
    ChinaSentinelState,
    SentinelStatus,
    compute_equity_bond_spread_description,
    compute_margin_ratio_distance,
    get_deposit_ratio_description,
)
from src.data.china_market_fetcher import MARGIN_RATIO_REFERENCES
from src.utils.i18n import t

# Regime color palette
_REGIME_COLORS = {
    "VALUE_BULL": "#15803d",        # dark green
    "SENTIMENT_BULL": "#86efac",    # light green
    "NEUTRAL": "#ca8a04",           # yellow
    "PANIC_BOTTOM": "#ea580c",      # orange
    "OVERVALUATION_RISK": "#dc2626", # red
}

_L1_COLORS = {
    "EXPANSIONARY": "#15803d",
    "NEUTRAL": "#ca8a04",
    "CONTRACTING": "#dc2626",
}


def _score_badge(score: int) -> str:
    if score > 0:
        return f"<span style='color:#15803d;font-weight:bold'>+{score}</span>"
    if score < 0:
        return f"<span style='color:#dc2626;font-weight:bold'>{score}</span>"
    return f"<span style='color:#64748b'>0</span>"


def _signal_color(signal: str) -> str:
    bullish = {"UNDERVALUED", "COLD", "LOW", "EXPANSIONARY", "VALUE_BULL", "SENTIMENT_BULL"}
    bearish = {"OVERVALUED", "OVERHEATED", "HIGH", "CONTRACTING",
               "OVERVALUATION_RISK"}
    if signal in bullish:
        return "#15803d"
    if signal in bearish:
        return "#dc2626"
    return "#ca8a04"


# ── Task 9.1: Margin Ratio Card ───────────────────────────────────────────────

def render_margin_ratio_card(
    margin_df: pd.DataFrame | None,
    language: str = "en",
) -> None:
    """Render a Plotly line chart of the margin ratio with 2015/2021 reference lines."""
    st.subheader(t("cn_margin_ratio_card"))

    if margin_df is None or margin_df.empty or "Margin_Ratio_Pct" not in margin_df.columns:
        st.info("No margin ratio data available.")
        return

    series = margin_df["Margin_Ratio_Pct"].dropna()
    if series.empty:
        st.info("No margin ratio data available.")
        return

    latest = float(series.iloc[-1])
    distance_info = compute_margin_ratio_distance(latest, MARGIN_RATIO_REFERENCES)

    col_chart, col_metric = st.columns([3, 1])
    with col_chart:
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=series.index, y=series,
            name=t("cn_margin_ratio_card"),
            line=dict(color="#1f77b4", width=1.8),
            fill="tozeroy", fillcolor="rgba(31,119,180,0.06)",
        ))
        for ref_name, ref_val in MARGIN_RATIO_REFERENCES.items():
            label = "2015 Peak" if "2015" in ref_name else "2021 Peak"
            fig.add_hline(
                y=ref_val, line_dash="dash", line_color="#d62728", line_width=1,
                annotation_text=f"{label} {ref_val}%",
                annotation_position="top right",
                annotation_font_size=10,
            )
        fig.update_layout(
            margin=dict(l=20, r=20, t=30, b=20), height=260,
            yaxis=dict(title="%"),
            hovermode="x unified",
            showlegend=False,
        )
        st.plotly_chart(fig, use_container_width=True)

    with col_metric:
        st.metric(t("cn_margin_ratio_card"), f"{latest:.2f}%")
        for ref_name, info in distance_info.items():
            label = "vs 2015" if "2015" in ref_name else "vs 2021"
            desc_key = {
                "很远": "cn_distance_very_far",
                "较远": "cn_distance_far",
                "较近": "cn_distance_close",
                "接近": "cn_distance_very_close",
            }.get(info["description"], "cn_distance_far")
            st.caption(f"{label}: {t(desc_key)} ({info['pct_of_peak']:.0f}%)")


# ── Task 9.2: Equity-Bond Spread Card ────────────────────────────────────────

_EQUITY_BOND_REFS = {
    "2008 crisis": 8.0,
    "2014 low": 2.0,
    "2022 bottom": 4.5,
}


def render_equity_bond_spread_card(
    spread_df: pd.DataFrame | None,
    language: str = "en",
) -> None:
    """Render equity-bond spread chart with historical reference levels."""
    st.subheader(t("cn_equity_bond_card"))

    if spread_df is None or spread_df.empty or "Equity_Bond_Spread" not in spread_df.columns:
        st.info("No equity-bond spread data available.")
        return

    series = spread_df["Equity_Bond_Spread"].dropna()
    if series.empty:
        st.info("No equity-bond spread data available.")
        return

    latest = float(series.iloc[-1])
    description = compute_equity_bond_spread_description(latest)

    col_chart, col_metric = st.columns([3, 1])
    with col_chart:
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=series.index, y=series,
            name=t("cn_equity_bond_card"),
            line=dict(color="#ff7f0e", width=1.8),
            fill="tozeroy", fillcolor="rgba(255,127,14,0.06)",
        ))
        for ref_label, ref_val in _EQUITY_BOND_REFS.items():
            fig.add_hline(
                y=ref_val, line_dash="dot", line_color="#9467bd", line_width=1,
                annotation_text=f"{ref_label} {ref_val:.1f}%",
                annotation_position="top right",
                annotation_font_size=10,
            )
        fig.add_hline(y=3.0, line_dash="dash", line_color="#15803d", line_width=1.5,
                      annotation_text="UNDERVALUED >3%", annotation_position="bottom right")
        fig.add_hline(y=1.0, line_dash="dash", line_color="#dc2626", line_width=1.5,
                      annotation_text="OVERVALUED <1%", annotation_position="top right")
        fig.update_layout(
            margin=dict(l=20, r=20, t=30, b=20), height=260,
            yaxis=dict(title="%"),
            hovermode="x unified",
            showlegend=False,
        )
        st.plotly_chart(fig, use_container_width=True)

    with col_metric:
        color = _signal_color(
            "UNDERVALUED" if latest > 3.0 else ("OVERVALUED" if latest < 1.0 else "NEUTRAL")
        )
        st.markdown(
            f"<div style='font-size:22px;font-weight:bold;color:{color}'>{latest:.2f}%</div>",
            unsafe_allow_html=True,
        )
        st.caption(description)


# ── Task 9.3: Deposit Ratio Card ──────────────────────────────────────────────

_DEPOSIT_RATIO_REFS = {"历史低": 2.5, "历史高": 6.0}


def render_deposit_ratio_card(
    deposit_df: pd.DataFrame | None,
    language: str = "en",
) -> None:
    """Render monthly deposit/market-cap ratio as a scatter chart."""
    st.subheader(t("cn_deposit_ratio_card"))

    if deposit_df is None or deposit_df.empty or "Deposit_Ratio" not in deposit_df.columns:
        st.info("No deposit ratio data available.")
        return

    series = deposit_df["Deposit_Ratio"].dropna()
    if series.empty:
        st.info("No deposit ratio data available.")
        return

    latest = float(series.iloc[-1])
    description = get_deposit_ratio_description(latest)

    col_chart, col_metric = st.columns([3, 1])
    with col_chart:
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=series.index, y=series,
            mode="markers+lines",
            name=t("cn_deposit_ratio_card"),
            marker=dict(color="#2ca02c", size=5),
            line=dict(color="#2ca02c", width=1.2),
        ))
        for ref_label, ref_val in _DEPOSIT_RATIO_REFS.items():
            fig.add_hline(
                y=ref_val, line_dash="dot", line_color="#aaaaaa", line_width=1,
                annotation_text=ref_label, annotation_position="right",
                annotation_font_size=10,
            )
        fig.update_layout(
            margin=dict(l=20, r=20, t=30, b=20), height=260,
            yaxis=dict(title="ratio"),
            hovermode="x unified",
            showlegend=False,
        )
        st.plotly_chart(fig, use_container_width=True)

    with col_metric:
        st.metric(t("cn_deposit_ratio_card"), f"{latest:.2f}x")
        st.caption(description)


# ── Task 9.4: Data Freshness Note ─────────────────────────────────────────────

def render_data_freshness_note(
    data_dates: dict[str, str],
    is_stale: bool = False,
    language: str = "en",
) -> None:
    """Render a small caption below the indicator cards showing data dates."""
    parts = [f"{k}: {v}" for k, v in data_dates.items() if v]
    note = t("cn_data_freshness_note").format(date=", ".join(parts))
    st.caption(note)
    if is_stale:
        st.warning(t("cn_data_stale_note"))


# ── Task 9.5: China Scoring Table ─────────────────────────────────────────────

def render_china_scoring_table(
    regime_result: ChinaRegimeResult,
    language: str = "en",
) -> None:
    """Render the three-layer scoring table with color-coded signal indicators."""
    l1 = regime_result.layer1
    l2 = regime_result.layer2
    l3 = regime_result.layer3

    st.subheader(t("cn_regime_header"))

    # ── Layer 1 ──
    with st.expander(f"{t('cn_regime_l1_title')} — {t('cn_regime_' + l1.regime.value)} | Ceiling {l1.ceiling_pct}%", expanded=True):
        rows = [
            {"Signal": "DR007 vs OMO", "Score": l1.dr007_score,
             "Interpretation": "宽松" if l1.dr007_score > 0 else ("偏紧" if l1.dr007_score < 0 else "中性")},
            {"Signal": "M1 YoY", "Score": l1.m1_yoy_score,
             "Interpretation": "改善" if l1.m1_yoy_score > 0 else ("恶化" if l1.m1_yoy_score < 0 else "中性")},
            {"Signal": "M1-M2 Spread", "Score": l1.m1_m2_spread_score,
             "Interpretation": "收窄" if l1.m1_m2_spread_score > 0 else ("扩大" if l1.m1_m2_spread_score < 0 else "中性")},
            {"Signal": "TSF YoY", "Score": l1.tsf_score,
             "Interpretation": "加速" if l1.tsf_score > 0 else ("减速" if l1.tsf_score < 0 else "中性")},
        ]
        score_md = " + ".join(
            f"({r['Score']:+d})" for r in rows
        ) + f" = **{l1.composite:+d}**"
        st.markdown(f"Composite Score: {score_md}")

        for row in rows:
            badge = _score_badge(row["Score"])
            color = _l1_score_color(row["Score"])
            st.markdown(
                f"<div style='display:flex;gap:16px;align-items:center;padding:3px 0'>"
                f"<span style='width:140px'>{row['Signal']}</span>"
                f"<span>{badge}</span>"
                f"<span style='color:{color};font-size:13px'>{row['Interpretation']}</span>"
                f"</div>",
                unsafe_allow_html=True,
            )

    # ── Layer 2 ──
    regime_color = _REGIME_COLORS.get(l2.regime.value, "#64748b")
    regime_label = t(f"cn_regime_{l2.regime.value}")
    with st.expander(
        f"{t('cn_regime_l2_title')} — "
        f"{regime_label} | Utilization {l2.utilization_min}%–{l2.utilization_max}%",
        expanded=True,
    ):
        signals = [
            ("Stock-Bond Spread", l2.equity_bond_signal),
            ("Margin Ratio", l2.margin_signal),
            ("QVIX", l2.qvix_signal or "N/A"),
            ("Northbound Adj", f"{l2.northbound_adjustment:+.0%}"),
        ]
        for label, val in signals:
            color = _signal_color(str(val))
            st.markdown(
                f"<div style='display:flex;gap:16px;padding:3px 0'>"
                f"<span style='width:160px'>{label}</span>"
                f"<span style='color:{color};font-weight:bold'>{val}</span>"
                f"</div>",
                unsafe_allow_html=True,
            )
        st.markdown(
            f"<div style='margin-top:8px;padding:6px 12px;border-radius:6px;"
            f"background:{regime_color}22;color:{regime_color};font-weight:bold'>"
            f"{regime_label}</div>",
            unsafe_allow_html=True,
        )

    # ── Layer 3 ──
    triggered = [(sid, e) for sid, e in l3.all_entries() if e.status != SentinelStatus.CLEAR]
    l3_label = f"⚠ {len(triggered)} triggered" if triggered else "✅ All Clear"
    with st.expander(f"{t('cn_regime_l3_title')} — {l3_label}", expanded=bool(triggered)):
        for sid, entry in l3.all_entries():
            name_key = f"cn_sentinel_{sid}"
            name = t(name_key)
            if entry.status == SentinelStatus.CLEAR:
                st.markdown(
                    f"<div style='color:#64748b;padding:2px 0'>✅ {name}</div>",
                    unsafe_allow_html=True,
                )
            elif entry.status == SentinelStatus.TRIGGERED:
                st.markdown(
                    f"<div style='color:#dc2626;font-weight:bold;padding:2px 0'>"
                    f"🔴 {name} — {t('cn_sentinel_banner_triggered')}</div>",
                    unsafe_allow_html=True,
                )
            else:
                st.markdown(
                    f"<div style='color:#ea580c;padding:2px 0'>"
                    f"🟠 {name} — {t('cn_sentinel_banner_cooling')} "
                    f"({entry.hold_down_days}/3d)</div>",
                    unsafe_allow_html=True,
                )


def _l1_score_color(score: int) -> str:
    if score > 0:
        return "#15803d"
    if score < 0:
        return "#dc2626"
    return "#64748b"


# ── Task 9.6: Envelope Gauge ──────────────────────────────────────────────────

def render_china_envelope_gauge(
    envelope: ChinaEnvelopeResult,
    language: str = "en",
) -> None:
    """Render a horizontal bar gauge for the Target Position Envelope."""
    t_min = envelope.target_min
    t_max = envelope.target_max
    emergency = envelope.is_emergency

    if emergency:
        band_color = "rgba(239,68,68,0.5)"
    elif t_max > 60:
        band_color = "rgba(34,197,94,0.4)"
    elif t_max > 40:
        band_color = "rgba(234,179,8,0.4)"
    else:
        band_color = "rgba(249,115,22,0.4)"

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=[100], y=[""], orientation="h",
        marker=dict(color="rgba(200,200,200,0.15)"),
        showlegend=False, hoverinfo="skip",
    ))
    fig.add_shape(
        type="rect", x0=t_min, x1=t_max, y0=-0.4, y1=0.4,
        fillcolor=band_color,
        line=dict(width=2, color=band_color.replace("0.4", "0.8").replace("0.5", "0.9")),
    )
    fig.add_annotation(
        x=(t_min + t_max) / 2, y=0,
        text=f"<b>{t_min:.0f}%–{t_max:.0f}%</b>",
        showarrow=False, font=dict(size=16, color="#1e293b"),
    )

    title = t("cn_envelope_gauge_title")
    if emergency:
        title += " 🚨 EMERGENCY"

    fig.update_layout(
        title=dict(text=title, font=dict(size=14)),
        xaxis=dict(range=[0, 100], ticksuffix="%", showgrid=True),
        yaxis=dict(showticklabels=False),
        height=120,
        margin=dict(l=20, r=20, t=50, b=20),
    )
    st.plotly_chart(fig, use_container_width=True)

    if envelope.derivation:
        st.caption(envelope.derivation)


# ── Task 9.7: Sentinel Warning Banner ────────────────────────────────────────

def render_china_sentinel_banner(
    l3_state: ChinaSentinelState,
    language: str = "en",
) -> None:
    """Render orange/red warning banner when any sentinel is triggered; no-op if all clear."""
    triggered = [(sid, e) for sid, e in l3_state.all_entries()
                 if e.status != SentinelStatus.CLEAR]
    if not triggered:
        return

    is_emergency = len(triggered) >= 2
    bg_color = "#dc2626" if is_emergency else "#ea580c"

    lines = [f"⚡ **{t('cn_sentinel_banner_title')}**"]
    for sid, entry in triggered:
        name_key = f"cn_sentinel_{sid}"
        name = t(name_key)
        status_label = (t("cn_sentinel_banner_triggered")
                        if entry.status == SentinelStatus.TRIGGERED
                        else t("cn_sentinel_banner_cooling"))
        ts_text = f" | {entry.trigger_timestamp}" if entry.trigger_timestamp else ""
        lines.append(f"• {name}: **{status_label}**{ts_text}")

    if is_emergency:
        lines.append("⚠ Multiple sentinels triggered — Emergency position reduction active")

    banner_html = "<br>".join(lines)
    st.markdown(
        f"""<div style="background-color:{bg_color};color:white;padding:12px 20px;
        border-radius:8px;margin-bottom:16px;font-size:14px;">
        {banner_html}</div>""",
        unsafe_allow_html=True,
    )


# ── Task 9.8: Regime Timeline ─────────────────────────────────────────────────

def render_china_regime_timeline(
    history_df: pd.DataFrame | None,
    language: str = "en",
) -> None:
    """Render a 12-month A-share regime color-band timeline."""
    st.subheader(t("cn_regime_timeline_title"))

    if history_df is None or history_df.empty:
        st.info(t("cn_regime_timeline_empty"))
        return

    try:
        df = history_df.copy()
        df["date"] = pd.to_datetime(df["date"])
        df = df.sort_values("date")
        cutoff = df["date"].max() - pd.Timedelta(days=365)
        df = df[df["date"] >= cutoff]
        if df.empty:
            st.info(t("cn_regime_timeline_empty"))
            return
    except Exception as e:
        st.warning(f"Error loading regime history: {e}")
        return

    fig = go.Figure()
    for _, row in df.iterrows():
        regime = str(row.get("L2_regime", "NEUTRAL"))
        color = _REGIME_COLORS.get(regime, "#94a3b8")
        fig.add_vrect(
            x0=row["date"] - pd.Timedelta(hours=12),
            x1=row["date"] + pd.Timedelta(hours=12),
            fillcolor=color, opacity=0.7,
            line_width=0,
        )

    if "target_min" in df.columns and "target_max" in df.columns:
        fig.add_trace(go.Scatter(
            x=df["date"], y=df["target_max"],
            mode="lines", name="Target Max %",
            line=dict(color="white", width=1.5),
            yaxis="y2",
        ))
        fig.add_trace(go.Scatter(
            x=df["date"], y=df["target_min"],
            mode="lines", name="Target Min %",
            line=dict(color="rgba(255,255,255,0.5)", width=1, dash="dot"),
            yaxis="y2",
        ))

    # Legend annotations
    for regime_val, color in _REGIME_COLORS.items():
        label = t(f"cn_regime_{regime_val}")
        fig.add_trace(go.Scatter(
            x=[None], y=[None], mode="markers",
            marker=dict(color=color, size=12, symbol="square"),
            name=label, showlegend=True,
        ))

    fig.update_layout(
        height=200,
        margin=dict(l=20, r=20, t=30, b=20),
        xaxis=dict(showgrid=False),
        yaxis=dict(showticklabels=False, showgrid=False),
        yaxis2=dict(overlaying="y", side="right", showgrid=False,
                    title="Target %", range=[0, 100]),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        hovermode="x unified",
    )
    st.plotly_chart(fig, use_container_width=True)


# ── Task 9.9: Update northbound chart with disclosure notice ─────────────────

def northbound_disclosure_notice() -> str:
    """Return the disclosure-stopped notice text for use in chart titles."""
    return t("cn_northbound_disclosure_stopped")
