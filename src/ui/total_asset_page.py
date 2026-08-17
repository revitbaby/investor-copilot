"""总资产首页（ADR-0015 IA 第 1 页，P0）。

只读渲染 Ledger Facade 的聚合输出——本页没有任何写入口径、
不触网、不放任何市场行情图。按序回答三个问题：
(a) 我偏离基准了吗（基准未设定 → 展示真实暴露并引导定基准）
(b) 卫星仓穿透后真实占比超没超 35%（ADR-0018）
(c) 目标进度（真实年化 vs 17.5% 需求线）

可视化三规则（ADR-0015）：区间画色带、图上标"我"、红色只给需要动作的事。
"""

from __future__ import annotations

import plotly.graph_objects as go
import streamlit as st

from src.ledger import Ledger
from src.utils.i18n import t

DEFAULT_DB_PATH = "data_cache/ledger.db"
DEFAULT_BASELINE_PATH = "config/baseline.yaml"

_EXPOSURE_ORDER = ("CN", "HK", "US", "CASH", "BOND", "OTHER", "UNPENETRATED")


def _market_label(key: str) -> str:
    if key == "UNPENETRATED":
        return t("ledger_unpenetrated")
    return t(f"ledger_mkt_{key}")

_OK_COLOR = "#2e7d32"
_ACTION_COLOR = "#c62828"  # 红色只给需要动作的事
_BAND_COLOR = "rgba(46, 125, 50, 0.15)"


def render_total_asset_page(
    db_path: str = DEFAULT_DB_PATH,
    baseline_path: str = DEFAULT_BASELINE_PATH,
) -> None:
    ledger = Ledger(db_path=db_path, baseline_path=baseline_path)
    snap = ledger.get_latest_snapshot()
    if snap is None:
        st.info(t("ledger_empty"))
        return

    if snap.stale:
        st.warning(t("ledger_stale_warning"))

    st.metric(t("ledger_total_value"), f"¥{snap.total_cny:,.0f}")
    st.caption(f"{snap.as_of.isoformat()} · {snap.week_id}")

    _render_baseline_question(ledger, snap)
    _render_satellite_question(ledger)
    _render_goal_question(ledger)
    _render_detail(ledger)
    _render_integrity(ledger)


def _render_detail(ledger: Ledger) -> None:
    """逐持仓明细：市值/占比/穿透桶/主线标签，供 review 与分类调整。"""
    detail = ledger.get_allocation_detail()
    if not detail:
        return
    with st.expander(f"📋 {t('ledger_detail_title')}（{len(detail)} 项）"):
        rows = []
        for d in sorted(detail, key=lambda x: -x.value_cny):
            if d.xray_buckets:
                xray = "，".join(
                    f"{_bucket_label(b)} {w:.0%}"
                    for b, w in sorted(d.xray_buckets.items(), key=lambda x: -x[1])
                    if w >= 0.005
                )
                if d.xray_as_of:
                    xray += f"（截至 {d.xray_as_of.isoformat()}）"
            else:
                xray = "—"
            tags = "，".join(
                f"{th}{'🛰' if sat else ''}" for th, sat in d.themes
            ) or "—"
            rows.append({
                t("ledger_col_name"): d.name or d.symbol,
                t("ledger_col_type"): t(f"ledger_type_{d.asset_type}"),
                t("ledger_col_value"): round(d.value_cny),
                t("ledger_col_share"): f"{d.share:.1%}",
                t("ledger_col_xray"): xray,
                t("ledger_col_theme"): tags,
            })
        st.dataframe(rows, use_container_width=True, hide_index=True)
        st.caption(t("ledger_detail_hint"))


def _bucket_label(bucket: str) -> str:
    return t(f"ledger_bucket_{bucket}")


def _render_baseline_question(ledger: Ledger, snap) -> None:
    st.subheader(t("ledger_q1_title"))
    deviation = ledger.get_baseline_deviation()
    if deviation is None:
        st.info(t("ledger_baseline_unset"))
        _render_exposure_bars(snap)
    else:
        st.plotly_chart(_deviation_figure(deviation), use_container_width=True)
    _render_bucket_detail(ledger, snap)
    by_date: dict[str, int] = {}
    for p in snap.positions:
        if p.asset_type == "fund" and p.xray_as_of is not None and p.quantity > 0:
            key = p.xray_as_of.isoformat()
            by_date[key] = by_date.get(key, 0) + 1
    if by_date:
        parts = "、".join(f"{d}（{n} 只）" for d, n in sorted(by_date.items()))
        st.caption(t("ledger_xray_asof_summary").format(parts=parts))


def _render_bucket_detail(ledger: Ledger, snap) -> None:
    """基准桶内明细：跨桶基金拆分归集，指导调仓。纯信息色（非动作信号）。"""
    entries = [e for e in ledger.get_bucket_breakdown() if e.value_cny >= 0.01]
    if not entries or snap.total_cny <= 0:
        return
    bucket_order = {b: i for i, b in enumerate(_EXPOSURE_ORDER)}
    entries.sort(key=lambda e: (bucket_order.get(e.bucket, 99), -e.value_cny))
    rows = []
    current_bucket = None
    for e in entries:
        show_bucket = e.bucket != current_bucket
        current_bucket = e.bucket
        if e.is_split:
            note = t("ledger_split_note").format(weight=f"{e.bucket_weight:.0%}")
        else:
            note = ""
        rows.append({
            t("ledger_col_bucket"): _market_label(e.bucket) if show_bucket else "",
            t("ledger_col_name"): e.name or e.symbol,
            t("ledger_col_value"): round(e.value_cny),
            t("ledger_col_share"): f"{e.value_cny / snap.total_cny:.1%}",
            t("ledger_col_note"): note,
        })
    st.markdown(f"**{t('ledger_bucket_detail_title')}**")
    st.dataframe(rows, use_container_width=True, hide_index=True)


def _render_exposure_bars(snap) -> None:
    """基准未设定时的真实暴露视图（信息色，不用红）。"""
    st.markdown(f"**{t('ledger_actual_exposure')}**")
    if snap.total_cny <= 0:
        return
    keys = [k for k in _EXPOSURE_ORDER if k in snap.market_exposure]
    shares = [snap.market_exposure[k] / snap.total_cny for k in keys]
    fig = go.Figure(go.Bar(
        x=[s * 100 for s in shares],
        y=[_market_label(k) for k in keys],
        orientation="h",
        marker_color="#546e7a",
        text=[f"{s:.1%}" for s in shares],
        textposition="outside",
    ))
    fig.update_layout(
        height=60 * len(keys) + 80, margin=dict(l=10, r=40, t=10, b=10),
        xaxis=dict(range=[0, 100], ticksuffix="%"),
        showlegend=False,
    )
    st.plotly_chart(fig, use_container_width=True)


def _deviation_figure(deviation) -> go.Figure:
    """基准区间画色带 + "我"标实际值；越界才用红。"""
    fig = go.Figure()
    for i, d in enumerate(deviation):
        fig.add_shape(
            type="rect", x0=d.min * 100, x1=d.max * 100, y0=i - 0.4, y1=i + 0.4,
            fillcolor=_BAND_COLOR, line_width=0,
        )
        outside = d.status != "within"
        fig.add_trace(go.Scatter(
            x=[d.actual * 100], y=[i],
            mode="markers+text",
            marker=dict(
                symbol="triangle-down", size=16,
                color=_ACTION_COLOR if outside else _OK_COLOR,
            ),
            text=[f"{t('ledger_me_marker')} {d.actual:.1%}"],
            textposition="top center",
            showlegend=False,
        ))
    fig.update_layout(
        height=90 * len(deviation) + 60,
        margin=dict(l=10, r=10, t=10, b=10),
        xaxis=dict(ticksuffix="%", rangemode="tozero"),
        yaxis=dict(
            tickmode="array",
            tickvals=list(range(len(deviation))),
            ticktext=[_market_label(d.market) for d in deviation],
            autorange="reversed",
        ),
        showlegend=False,
    )
    return fig


def _render_satellite_question(ledger: Ledger) -> None:
    st.subheader(t("ledger_q2_title"))
    status = ledger.get_satellite_status()
    col1, col2 = st.columns(2)
    col1.metric(t("ledger_satellite_ratio"), f"{status.ratio:.1%}",
                help=t("ledger_penetrated_help"))
    col2.metric(t("ledger_cap"), f"{status.cap:.0%}")
    if status.breached:
        st.error(t("ledger_satellite_breach").format(
            over=f"{(status.ratio - status.cap):.1%}",
            amount=f"{status.satellite_cny - status.cap * status.total_cny:,.0f}",
        ))
    else:
        st.success(t("ledger_satellite_ok").format(
            headroom=f"{(status.cap - status.ratio):.1%}"
        ))


def _render_goal_question(ledger: Ledger) -> None:
    st.subheader(t("ledger_q3_title"))
    progress = ledger.get_goal_progress()
    if progress is None:
        st.info(t("ledger_goal_not_enough_data"))
        return
    if progress.annualized is None:
        st.info(t("ledger_goal_early"))
        st.metric(t("ledger_cumulative"), f"{progress.total_return:+.1%}")
        return
    col1, col2, col3 = st.columns(3)
    col1.metric(t("ledger_real_annualized"), f"{progress.annualized:+.1%}")
    col2.metric(t("ledger_required_line"), f"{progress.required:.1%}")
    col3.metric(t("ledger_cumulative"), f"{progress.total_return:+.1%}")
    if not progress.on_track:
        st.error(t("ledger_off_track").format(
            gap=f"{(progress.required - progress.annualized):.1%}"
        ))


def _render_integrity(ledger: Ledger) -> None:
    issues = ledger.validate_integrity()
    if issues:
        with st.expander(f"⚠️ {t('ledger_integrity_issues')}（{len(issues)}）"):
            for issue in issues:
                st.write(f"- {issue}")
