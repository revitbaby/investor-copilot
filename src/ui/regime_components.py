"""Streamlit UI components for the regime scoring engine."""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src.regime.models import (
    EnvelopeMode, L1Regime, L2Regime, RegimeResult, SentinelStatus,
)
from src.portfolio.models import AdvisoryResult
from src.regime.models import PositionAction
from src.llm.regime_narrator import NarrativeResult
from src.utils.i18n import t


def render_l3_alert_banner(result: RegimeResult) -> None:
    """Render sticky red alert banner when any L3 sentinel is triggered/cooling."""
    active = [s for s in result.layer3.sentinels if s.status != SentinelStatus.CLEAR]
    if not active:
        return

    active.sort(key=lambda s: s.forced_ceiling_pct if s.forced_ceiling_pct is not None else 999)

    lines = []
    for s in active:
        ceiling_text = f"{t('regime_forced_ceiling')}: {s.forced_ceiling_pct}%" if s.forced_ceiling_pct is not None else t("regime_freeze_active")
        status_label = t("regime_triggered") if s.status == SentinelStatus.TRIGGERED else t("regime_cooling")
        ts_text = f" | {t('regime_trigger_time')}: {s.trigger_timestamp}" if s.trigger_timestamp else ""
        lines.append(f"⚡ **LAYER 3 ALERT: {s.name} {status_label}** — {ceiling_text}{ts_text}")
        if s.status == SentinelStatus.COOLING:
            lines.append(f"   ⏳ {t('regime_reset_progress')}: {s.display_value}")

    banner_html = "<br>".join(lines)
    st.markdown(
        f"""<div style="background-color:#ef4444;color:white;padding:12px 20px;
        border-radius:8px;margin-bottom:16px;font-size:14px;">
        {banner_html}</div>""",
        unsafe_allow_html=True,
    )


def render_regime_gauge(result: RegimeResult, current_position_pct: float | None = None) -> None:
    """Render the horizontal bar gauge showing target position envelope."""
    envelope = result.envelope
    t_min = envelope.target_min
    t_max = envelope.target_max

    if t_max > 70:
        band_color = "rgba(34,197,94,0.4)"
    elif t_max > 50:
        band_color = "rgba(234,179,8,0.4)"
    elif t_max > 30:
        band_color = "rgba(249,115,22,0.4)"
    else:
        band_color = "rgba(239,68,68,0.4)"

    if envelope.mode == EnvelopeMode.EMERGENCY:
        band_color = "rgba(239,68,68,0.5)"

    fig = go.Figure()

    fig.add_trace(go.Bar(
        x=[100], y=[""], orientation="h",
        marker=dict(color="rgba(200,200,200,0.15)"),
        showlegend=False, hoverinfo="skip",
    ))

    fig.add_shape(
        type="rect", x0=t_min, x1=t_max, y0=-0.4, y1=0.4,
        fillcolor=band_color, line=dict(width=2, color=band_color.replace("0.4", "0.8")),
    )

    fig.add_annotation(
        x=(t_min + t_max) / 2, y=0,
        text=f"<b>{t_min:.0f}%–{t_max:.0f}%</b>",
        showarrow=False, font=dict(size=14, color="#333"),
    )

    if current_position_pct is not None:
        if current_position_pct > t_max:
            marker_color = "#ef4444"
            diff = current_position_pct - t_max
            label = f"⚠️ {t('regime_overweight')} {diff:.0f}pp"
        elif current_position_pct < t_min:
            marker_color = "#3b82f6"
            diff = t_min - current_position_pct
            label = f"ℹ️ {t('regime_underweight')} {diff:.0f}pp"
        else:
            marker_color = "#22c55e"
            label = f"✅ {t('regime_in_range')}"

        fig.add_annotation(
            x=current_position_pct, y=0.35,
            text="▼", showarrow=False,
            font=dict(size=20, color=marker_color),
        )
        fig.add_annotation(
            x=current_position_pct, y=-0.35,
            text=f"<b>{current_position_pct:.0f}%</b> {label}",
            showarrow=False, font=dict(size=11, color=marker_color),
        )

    for tick in [0, 20, 40, 60, 80, 100]:
        fig.add_annotation(
            x=tick, y=-0.5, text=f"{tick}%",
            showarrow=False, font=dict(size=10, color="#666"),
        )

    fig.update_layout(
        xaxis=dict(range=[0, 100], showticklabels=False, showgrid=False, zeroline=False),
        yaxis=dict(showticklabels=False, showgrid=False, zeroline=False, range=[-0.6, 0.6]),
        height=120, margin=dict(l=10, r=10, t=10, b=10),
        plot_bgcolor="white", paper_bgcolor="white",
    )
    st.plotly_chart(fig, use_container_width=True)

    # Derivation text
    st.caption(envelope.derivation.replace("\n", " | "))


def render_l1_scoring_table(result: RegimeResult, narrative: NarrativeResult | None = None) -> None:
    """Render Layer 1 scoring table card."""
    l1 = result.layer1

    badge_html = (
        f'<span style="background:{l1.color};color:white;padding:4px 10px;'
        f'border-radius:4px;font-size:13px;">'
        f'{l1.regime.value} | Ceiling: {l1.ceiling_pct}%</span>'
    )
    st.markdown(f"#### LAYER 1: {t('regime_l1_title')} {badge_html}", unsafe_allow_html=True)

    score_map = {1: "🟩 +1", 0: "⬜ 0", -1: "🟥 -1"}
    rows = []
    for ind in l1.indicators:
        rows.append({
            t("regime_indicator"): ind.name,
            t("regime_current_value"): ind.display_value,
            t("regime_threshold_hit"): ind.threshold_hit,
            t("regime_score"): score_map.get(ind.score, str(ind.score)),
        })

    df = pd.DataFrame(rows)
    st.dataframe(df, use_container_width=True, hide_index=True)

    st.markdown(
        f'<div style="background:{l1.color}22;padding:8px 12px;border-radius:4px;'
        f'font-weight:bold;">COMPOSITE: {l1.composite}</div>',
        unsafe_allow_html=True,
    )

    if narrative and narrative.l1_summary:
        st.markdown(f"*{narrative.l1_summary}*")


def render_l2_scoring_table(result: RegimeResult, narrative: NarrativeResult | None = None) -> None:
    """Render Layer 2 scoring table card with score bar."""
    l2 = result.layer2

    badge_html = (
        f'<span style="background:{l2.color};color:white;padding:4px 10px;'
        f'border-radius:4px;font-size:13px;">'
        f'{l2.regime.value} | Util: {l2.utilization_min}%–{l2.utilization_max}%</span>'
    )
    st.markdown(f"#### LAYER 2: {t('regime_l2_title')} {badge_html}", unsafe_allow_html=True)

    score_map = {1: "🟩 +1", 0: "⬜ 0", -1: "🟥 -1"}
    rows = []
    for ind in l2.indicators:
        rows.append({
            t("regime_indicator"): ind.name,
            t("regime_current_value"): ind.display_value,
            t("regime_threshold_hit"): ind.threshold_hit,
            t("regime_score"): score_map.get(ind.score, str(ind.score)),
            t("regime_weight"): f"{ind.weight:.1f}",
            t("regime_weighted_score"): f"{ind.weighted_score:+.1f}",
        })

    df = pd.DataFrame(rows)
    st.dataframe(df, use_container_width=True, hide_index=True)

    st.markdown(
        f'<div style="background:{l2.color}22;padding:8px 12px;border-radius:4px;'
        f'font-weight:bold;">WEIGHTED COMPOSITE: {l2.weighted_composite}</div>',
        unsafe_allow_html=True,
    )

    # Score Bar micro-visualization
    score = l2.weighted_composite
    fig = go.Figure()

    fig.add_trace(go.Bar(
        x=[16], y=[""], orientation="h",
        marker=dict(color="rgba(200,200,200,0.15)"),
        showlegend=False, hoverinfo="skip",
        base=-8,
    ))

    for boundary in [-5, -2, 2, 5]:
        fig.add_shape(type="line", x0=boundary, x1=boundary, y0=-0.4, y1=0.4,
                      line=dict(color="#aaa", width=1, dash="dash"))

    fig.add_annotation(x=score, y=0, text="▲", showarrow=False,
                       font=dict(size=18, color=l2.color))

    fig.update_layout(
        xaxis=dict(range=[-8, 8], showticklabels=True, dtick=2, showgrid=False),
        yaxis=dict(showticklabels=False, showgrid=False, range=[-0.5, 0.5]),
        height=70, margin=dict(l=10, r=10, t=5, b=20),
        plot_bgcolor="white", paper_bgcolor="white",
    )
    st.plotly_chart(fig, use_container_width=True)

    if narrative and narrative.l2_summary:
        st.markdown(f"*{narrative.l2_summary}*")


def render_l3_sentinel_row(result: RegimeResult, narrative: NarrativeResult | None = None) -> None:
    """Render compact sentinel status row."""
    sentinels = result.layer3.sentinels
    active_count = sum(1 for s in sentinels if s.status != SentinelStatus.CLEAR)

    if active_count > 0:
        header = f"**LAYER 3: {t('regime_l3_title')}** — {active_count} {t('regime_triggered')} 🚨"
    else:
        header = f"**LAYER 3: {t('regime_l3_title')}** — All Clear ✅"
    st.markdown(header)

    cols = st.columns(len(sentinels))
    for col, s in zip(cols, sentinels):
        with col:
            if s.status == SentinelStatus.CLEAR:
                bg, icon = "#dcfce7", "✅"
                text = s.display_value if s.display_value else t("regime_clear")
            elif s.status == SentinelStatus.TRIGGERED:
                bg, icon = "#fee2e2", "🚨"
                text = s.display_value
            else:  # COOLING
                bg, icon = "#fef9c3", "⏳"
                text = s.display_value

            st.markdown(
                f'<div style="background:{bg};padding:8px;border-radius:6px;text-align:center;font-size:12px;">'
                f'<b>{icon} {s.name}</b><br>{text}</div>',
                unsafe_allow_html=True,
            )

    if narrative and narrative.l3_summary and active_count > 0:
        st.markdown(f"*{narrative.l3_summary}*")


def render_position_advisory(advisory: AdvisoryResult | None, narrative: NarrativeResult | None = None) -> None:
    """Render position advisory card or upload prompt."""
    st.subheader(t("regime_position_advisory"))

    if advisory is None:
        st.info(f"📁 {t('regime_upload_prompt')}")
        return

    # Summary metrics
    col1, col2, col3, col4 = st.columns(4)
    col1.metric(t("regime_current_exposure"), f"{advisory.current_exposure_pct:.1f}%")
    col2.metric(t("regime_target_range"), f"{advisory.target_min_pct:.0f}%–{advisory.target_max_pct:.0f}%")

    if advisory.is_overweight:
        col3.metric(t("regime_status"), f"⚠️ {t('regime_overweight')}")
        col4.metric(t("regime_adjustment"), f"-${advisory.excess_dollars:,.0f}")
    else:
        col3.metric(t("regime_status"), f"✅ {t('regime_in_range')}")
        col4.metric(t("regime_adjustment"), "$0")

    # Holdings table
    action_colors = {
        PositionAction.CLOSE: "#fee2e2",
        PositionAction.TRIM: "#ffedd5",
        PositionAction.HOLD: "#f3f4f6",
        PositionAction.ADD: "#dcfce7",
    }

    rows = []
    for a in advisory.holdings_advice:
        rows.append({
            "#": a.priority,
            "Ticker": a.ticker,
            "Conviction": a.conviction,
            f"{t('regime_current_pct')}": f"{a.current_pct:.1f}%",
            f"{t('regime_target_pct')}": f"{a.target_pct:.1f}%",
            t("regime_action"): a.action.value,
            f"{t('regime_adj_dollars')}": f"${a.adjustment_dollars:+,.0f}",
            t("regime_reason"): a.reason,
        })

    if rows:
        df = pd.DataFrame(rows)
        st.dataframe(df, use_container_width=True, hide_index=True)

    # Active rules
    if advisory.active_rules:
        with st.expander(t("regime_active_rules"), expanded=True):
            for rule in advisory.active_rules:
                st.markdown(f"- {rule}")

    if narrative and narrative.position_narrative:
        st.markdown(f"*{narrative.position_narrative}*")


def render_regime_timeline(history_df: pd.DataFrame | None) -> None:
    """Render 12-month regime timeline with stacked rows."""
    with st.expander(f"📈 {t('regime_timeline')}", expanded=False):
        if history_df is None or history_df.empty:
            st.info(t("regime_timeline_empty"))
            return

        history_df = history_df.copy()
        if "date" in history_df.columns:
            history_df["date"] = pd.to_datetime(history_df["date"])
            history_df = history_df.set_index("date")

        fig = go.Figure()

        # Target envelope area
        if "target_min" in history_df.columns and "target_max" in history_df.columns:
            fig.add_trace(go.Scatter(
                x=history_df.index, y=history_df["target_max"],
                mode="lines", line=dict(width=0), showlegend=False,
            ))
            fig.add_trace(go.Scatter(
                x=history_df.index, y=history_df["target_min"],
                mode="lines", line=dict(width=0), fill="tonexty",
                fillcolor="rgba(59,130,246,0.2)",
                name=t("regime_target_envelope"),
            ))

        # SPX overlay
        if "spx_close" in history_df.columns:
            spx = pd.to_numeric(history_df["spx_close"], errors="coerce")
            fig.add_trace(go.Scatter(
                x=history_df.index, y=spx,
                mode="lines", name="SPX",
                line=dict(color="rgba(0,0,0,0.3)", width=1),
                yaxis="y2",
            ))

        fig.update_layout(
            height=300,
            margin=dict(l=20, r=20, t=30, b=20),
            yaxis=dict(title=t("regime_target_pct"), range=[0, 100]),
            yaxis2=dict(overlaying="y", side="right", showgrid=False, title="SPX"),
            hovermode="x unified",
            legend=dict(orientation="h", y=1.1),
        )
        st.plotly_chart(fig, use_container_width=True)
