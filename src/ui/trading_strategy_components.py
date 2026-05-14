"""
UI components for the Trading Strategy page.

All render_* functions use Streamlit and follow the existing i18n pattern.
"""

from __future__ import annotations

from datetime import date
from typing import Optional

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src.analysis.trending_up import TrendAnalysis, analyze
from src.portfolio.stock_pool import (
    StockPoolItem,
    add_item,
    delete_item,
    load_stock_pool,
    save_stock_pool,
    update_item,
)
from src.utils.i18n import get_current_language, t

_STOCK_POOL_PATH = "data_cache/stock_pool.json"

# ── Regime label → position multiplier ──────────────────────────────────────
_REGIME_MULTIPLIERS = {
    "BULL": 1.0,
    "BULL_WATCH": 0.75,
    "NEUTRAL": 0.85,
    "BEAR": 0.30,
    "RISK_OFF": 0.30,
    "EXPANSIONARY": 1.0,
    "VALUE_BULL": 1.0,
    "SENTIMENT_BULL": 0.85,
    "OVERVALUATION_RISK": 0.60,
    "PANIC_BOTTOM": 0.90,
    "CONTRACTING": 0.60,
}

_REGIME_COLORS = {
    1.0: "green",
    0.90: "green",
    0.85: "orange",
    0.75: "orange",
    0.60: "orange",
    0.30: "red",
}


def _get_multiplier_color(mult: float) -> str:
    for threshold, color in sorted(_REGIME_COLORS.items(), reverse=True):
        if mult >= threshold:
            return color
    return "red"


def _extract_regime_label(regime_obj) -> str:
    """Extract string label from various regime result types."""
    if regime_obj is None:
        return "UNKNOWN"
    for attr in ("envelope", "label", "regime_label"):
        val = getattr(regime_obj, attr, None)
        if val is not None:
            if hasattr(val, "label"):
                return str(val.label)
            return str(val)
    return "UNKNOWN"


# ── 6.1 Regime banner ────────────────────────────────────────────────────────

def render_regime_banner(lang: str = "zh") -> dict[str, float]:
    """
    Reads session_state regime results, renders a banner, returns {market: multiplier}.
    """
    us_regime = st.session_state.get("us_regime_result")
    cn_regime = st.session_state.get("china_regime_result")

    multipliers: dict[str, float] = {}

    if us_regime is None and cn_regime is None:
        st.info(t("trading_regime_load_hint"))
        return {"A股": 1.0, "美股": 1.0}

    cols = st.columns(2 if us_regime and cn_regime else 1)

    def _render_one(col, market_key: str, label: str, regime_obj):
        regime_str = _extract_regime_label(regime_obj)
        mult = _REGIME_MULTIPLIERS.get(regime_str, 0.85)
        multipliers[market_key] = mult
        color = _get_multiplier_color(mult)
        limit_pct = int(mult * 100)
        with col:
            st.markdown(
                f"**{market_key}** 体制：`{regime_str}`  "
                f"→ {t('trading_regime_pos_limit')} :{color}[**{limit_pct}%**]"
            )
        return mult

    if us_regime:
        _render_one(cols[0], "美股", "US", us_regime)
    if cn_regime:
        idx = 1 if us_regime else 0
        _render_one(cols[idx], "A股", "CN", cn_regime)

    if "A股" not in multipliers:
        multipliers["A股"] = 1.0
    if "美股" not in multipliers:
        multipliers["美股"] = 1.0
    multipliers["港股"] = multipliers.get("A股", 1.0)

    return multipliers


# ── 6.2 Pool filters ──────────────────────────────────────────────────────────

def render_stock_pool_filters(items: list[StockPoolItem]) -> list[StockPoolItem]:
    """Four-dimension filter: market / strategy_type / sector / status."""
    markets = [t("stock_pool_all")] + sorted(set(i.market for i in items))
    strategies = [t("stock_pool_all")] + sorted(set(i.strategy_type for i in items))
    sectors = [t("stock_pool_all")] + sorted(set(i.sector for i in items) - {""})
    statuses = [t("stock_pool_all")] + sorted(set(i.status for i in items))

    c1, c2, c3, c4 = st.columns(4)
    sel_market = c1.selectbox(t("stock_pool_filter_market"), markets, key="filter_market")
    sel_strategy = c2.selectbox(t("stock_pool_filter_strategy"), strategies, key="filter_strategy")
    sel_sector = c3.selectbox(t("stock_pool_filter_sector"), sectors, key="filter_sector")
    sel_status = c4.selectbox(t("stock_pool_filter_status"), statuses, key="filter_status")

    all_label = t("stock_pool_all")
    result = items
    if sel_market != all_label:
        result = [i for i in result if i.market == sel_market]
    if sel_strategy != all_label:
        result = [i for i in result if i.strategy_type == sel_strategy]
    if sel_sector != all_label:
        result = [i for i in result if i.sector == sel_sector]
    if sel_status != all_label:
        result = [i for i in result if i.status == sel_status]
    return result


# ── 6.3 Add / edit form ───────────────────────────────────────────────────────

_MARKET_OPTIONS = ["A股", "美股", "港股"]
_STRATEGY_OPTIONS = ["trending_up", "value", "oscillation"]
_STATUS_OPTIONS = ["watching", "holding"]

_STATUS_LABELS = {"watching": "观察", "holding": "持有"}
_STRATEGY_LABELS = {"trending_up": "单边上涨", "value": "价值投资", "oscillation": "震荡策略"}

# Sector options by market
_ASHARE_SECTORS = [
    "电子", "计算机", "通信", "医药生物", "食品饮料", "电力设备", "汽车",
    "银行", "非银金融", "房地产", "建筑材料", "建筑装饰", "机械设备",
    "基础化工", "钢铁", "有色金属", "煤炭", "石油石化", "农林牧渔",
    "轻工制造", "纺织服饰", "家用电器", "传媒", "社会服务", "综合", "美容护理",
]
_US_SECTORS = [
    "Information Technology", "Health Care", "Financials", "Consumer Discretionary",
    "Communication Services", "Industrials", "Consumer Staples", "Energy",
    "Utilities", "Real Estate", "Materials",
]
_HK_SECTORS = [
    "科技", "金融", "地产建筑", "消费", "医疗保健", "能源", "工业", "公用事业", "综合",
]
_SECTOR_BY_MARKET = {"A股": _ASHARE_SECTORS, "美股": _US_SECTORS, "港股": _HK_SECTORS}


def render_add_edit_form(
    items: list[StockPoolItem],
    editing_item: Optional[StockPoolItem] = None,
) -> StockPoolItem | None:
    """
    Add/edit expander. Returns submitted StockPoolItem or None.
    Field changes trigger only the outer @st.fragment rerun (trading page only),
    not a full app rerun — so US/China dashboards are unaffected.
    """
    label = t("edit_stock") if editing_item else t("add_stock")
    pfx = f"form_{'edit_' + editing_item.ticker if editing_item else 'add'}"

    defaults = editing_item or StockPoolItem(
        ticker="", name="", market="A股", sector="",
        strategy_type="trending_up", status="watching",
    )

    with st.expander(f"{'✏️' if editing_item else '+'} {label}", expanded=editing_item is not None):
        c1, c2 = st.columns(2)
        ticker = c1.text_input(
            t("ticker_label"), value=defaults.ticker,
            disabled=editing_item is not None, key=f"{pfx}_ticker",
        )
        name = c2.text_input(t("name_label"), value=defaults.name, key=f"{pfx}_name")

        c3, c4 = st.columns(2)
        market = c3.selectbox(
            t("market_label"), _MARKET_OPTIONS,
            index=_MARKET_OPTIONS.index(defaults.market) if defaults.market in _MARKET_OPTIONS else 0,
            disabled=editing_item is not None,
            key=f"{pfx}_market",
        )
        status = c4.selectbox(
            t("status_label"), _STATUS_OPTIONS,
            index=_STATUS_OPTIONS.index(defaults.status) if defaults.status in _STATUS_OPTIONS else 0,
            format_func=lambda x: _STATUS_LABELS.get(x, x),
            key=f"{pfx}_status",
        )

        # Sector options react to the current market selection within the fragment rerun
        current_market = st.session_state.get(f"{pfx}_market", defaults.market)
        sector_opts = _SECTOR_BY_MARKET.get(current_market, _ASHARE_SECTORS)
        if defaults.sector and defaults.sector not in sector_opts:
            sector_opts = [defaults.sector] + sector_opts
        sector_idx = sector_opts.index(defaults.sector) if defaults.sector in sector_opts else 0

        c5, c6 = st.columns(2)
        sector = c5.selectbox(
            t("sector_label"), sector_opts, index=sector_idx, key=f"{pfx}_sector",
        )
        strategy = c6.selectbox(
            t("strategy_label"), _STRATEGY_OPTIONS,
            index=_STRATEGY_OPTIONS.index(defaults.strategy_type) if defaults.strategy_type in _STRATEGY_OPTIONS else 0,
            format_func=lambda x: _STRATEGY_LABELS.get(x, x),
            key=f"{pfx}_strategy",
        )

        c7, c8 = st.columns(2)
        cost_basis = c7.number_input(
            t("cost_basis_label"), value=float(defaults.cost_basis or 0.0),
            min_value=0.0, step=0.01, key=f"{pfx}_cost",
        )
        shares = c8.number_input(
            t("shares_label"), value=float(defaults.shares or 0.0),
            min_value=0.0, step=1.0, key=f"{pfx}_shares",
        )
        notes = st.text_area(t("notes_label"), value=defaults.notes, height=60, key=f"{pfx}_notes")

        if st.button(t("save_stock"), key=f"{pfx}_submit"):
            ticker_clean = ticker.strip().upper()
            name_clean = name.strip()
            if not ticker_clean:
                st.error(t("ticker_required_error"))
                return None
            if not name_clean:
                st.error(t("name_required_error"))
                return None
            if editing_item is None and any(i.ticker.upper() == ticker_clean for i in items):
                st.error(t("ticker_duplicate_error"))
                return None
            return StockPoolItem(
                ticker=ticker_clean,
                name=name_clean,
                market=market,
                sector=sector,
                strategy_type=strategy,
                status=status,
                cost_basis=cost_basis if cost_basis > 0 else None,
                shares=shares if shares > 0 else None,
                notes=notes.strip(),
                added_date=defaults.added_date if editing_item else date.today().isoformat(),
            )

    return None


# ── 6.4 Stock pool table ──────────────────────────────────────────────────────

_PHASE_DISPLAY = {
    "breakout": "⬆ 突破买入",
    "pullback": "⬇ 回踩买入",
    "consolidation": "◼ 整固观望",
    "acceleration": "⚠ 勿追加速",
    "topping": "🔴 衰竭减仓",
    "neutral": "— 观望",
    "unknown": "— 待分析",
}

_STRATEGY_DISPLAY = {
    "trending_up": "单边上涨",
    "value": "价值",
    "oscillation": "震荡",
}


def render_stock_pool_table(
    items: list[StockPoolItem],
    analysis_map: dict[str, TrendAnalysis],
) -> str | None:
    """
    Renders pool as a table. Returns selected ticker or None.
    """
    if not items:
        return None

    rows = []
    for item in items:
        analysis = analysis_map.get(item.ticker)
        if analysis and not analysis.data_insufficient and item.strategy_type == "trending_up" and item.market != "港股":
            score = analysis.trend_score
            signal = _PHASE_DISPLAY.get(analysis.trend_phase, "—")
            score_bar = "▓" * score + "░" * (6 - score)
            trend_col = f"{score_bar} {score}/6"
        elif item.market == "港股":
            trend_col = "—"
            signal = t("hk_data_pending")
        elif item.strategy_type != "trending_up":
            trend_col = "—"
            signal = t("strategy_coming_soon")
        elif analysis and analysis.data_insufficient:
            trend_col = "❌ 数据不足"
            signal = "—"
        else:
            trend_col = "⏳ 加载中"
            signal = "—"

        rows.append({
            "标的": item.ticker,
            "名称": item.name,
            "市场": item.market,
            "行业": item.sector or "—",
            "策略": _STRATEGY_DISPLAY.get(item.strategy_type, item.strategy_type),
            "状态": "持有" if item.status == "holding" else "观察",
            "趋势强度": trend_col,
            "当前信号": signal,
        })

    df_display = pd.DataFrame(rows)
    st.dataframe(df_display, use_container_width=True, hide_index=True)

    # Selectbox for detail
    tickers = [i.ticker for i in items]
    selected = st.selectbox(
        t("stock_detail_title"),
        ["— 请选择标的 —"] + tickers,
        key="selected_ticker",
    )
    return selected if selected != "— 请选择标的 —" else None


# ── 6.5 Trend checklist ───────────────────────────────────────────────────────

def render_trend_checklist(analysis: TrendAnalysis, lang: str = "zh"):
    st.markdown(f"**{t('trend_checklist_title')}**")
    checks = [
        (analysis.price_above_ma20, "价格在 MA20 上方"),
        (analysis.ma_bullish_alignment, "MA20 > MA60 > MA120（多头排列）"),
        (analysis.adx_strong, "ADX > 25（趋势强劲）"),
        (analysis.higher_lows, "回调低点逐次抬高"),
        (analysis.pullback_volume_shrink, "回调时成交量萎缩"),
        (analysis.rsi_healthy, "RSI 在 40-70（趋势健康）"),
    ]
    for flag, desc in checks:
        icon = "✅" if flag else "❌"
        st.markdown(f"{icon} {desc}")

    score = analysis.trend_score
    color = "green" if score >= 5 else ("orange" if score >= 3 else "red")
    st.markdown(f"**{t('trend_score_label')}**：:{color}[**{score}/6**]")


# ── 6.6 Phase card ────────────────────────────────────────────────────────────

_PHASE_LABELS_ZH = {
    "breakout": "突破期",
    "pullback": "回踩期",
    "consolidation": "整固期",
    "acceleration": "加速期",
    "topping": "衰竭期",
    "neutral": "趋势不明",
    "unknown": "待分析",
}


def render_phase_card(analysis: TrendAnalysis, lang: str = "zh"):
    st.markdown(f"**{t('trend_phase_title')}**")
    phase_label = _PHASE_LABELS_ZH.get(analysis.trend_phase, analysis.trend_phase)

    if analysis.trend_phase == "acceleration":
        st.warning(f"⚠️ **{phase_label}** — {analysis.strategy_detail}")
    elif analysis.trend_phase == "topping":
        st.error(f"🔴 **{phase_label}** — {analysis.strategy_detail}")
    elif analysis.trend_phase in ("breakout", "pullback"):
        st.success(f"✅ **{phase_label}** — {analysis.recommended_strategy}")
        st.caption(analysis.strategy_detail)
    else:
        st.info(f"ℹ️ **{phase_label}** — {analysis.strategy_detail}")


# ── 6.7 Pyramid position calculator ──────────────────────────────────────────

def render_pyramid_calculator(
    analysis: TrendAnalysis,
    regime_multipliers: dict[str, float],
    ticker: str,
    lang: str = "zh",
):
    st.markdown(f"**{t('pyramid_calc_title')}**")

    item_market = st.session_state.get(f"market_{ticker}", "A股")
    mult = regime_multipliers.get(item_market, 1.0)

    if mult < 0.5:
        st.error(f"⚠️ 当前 {item_market} 体制仓位上限 {int(mult*100)}%，谨慎操作")
    elif mult < 0.9:
        st.warning(f"⚠️ 当前 {item_market} 体制仓位上限 {int(mult*100)}%")

    total_capital = st.number_input(
        t("pyramid_total_capital"),
        value=100000.0,
        min_value=1000.0,
        step=10000.0,
        key=f"capital_{ticker}",
    )
    order_options = [
        t("pyramid_entry_order_1"),
        t("pyramid_entry_order_2"),
        t("pyramid_entry_order_3"),
        t("pyramid_entry_order_4"),
    ]
    order_idx = st.selectbox(
        t("pyramid_entry_order"),
        range(len(order_options)),
        format_func=lambda x: order_options[x],
        key=f"entry_order_{ticker}",
    )
    entry_order = order_idx + 1

    from src.analysis.trending_up import _compute_pyramid_position
    pos_pct = _compute_pyramid_position(entry_order, mult)
    buy_amount = total_capital * pos_pct

    c1, c2, c3, c4 = st.columns(4)
    c1.metric(t("pyramid_buy_amount"), f"¥{buy_amount:,.0f}", f"{pos_pct*100:.0f}%")
    c2.metric(t("pyramid_stop_loss"), f"{analysis.stop_loss_price:.2f}", f"-{6.5:.1f}%")
    c3.metric(t("pyramid_target_1"), f"{analysis.target_price_1:.2f}", "+25%")
    c4.metric(t("pyramid_target_2"), f"{analysis.target_price_2:.2f}", "+45%")


# ── 6.8 Candlestick chart ─────────────────────────────────────────────────────

def render_candlestick_chart(
    df: pd.DataFrame,
    indicators: dict,
    ticker: str,
):
    n_days = st.slider(t("chart_days_slider"), 60, 250, 120, step=10, key=f"chart_days_{ticker}")
    plot_df = df.tail(n_days)
    ind_tail = {k: v.tail(n_days) if isinstance(v, pd.Series) else v for k, v in indicators.items()}

    if plot_df.empty:
        st.warning(t("insufficient_data"))
        return

    fig = go.Figure()

    # Candlestick
    fig.add_trace(go.Candlestick(
        x=plot_df.index,
        open=plot_df["open"], high=plot_df["high"],
        low=plot_df["low"], close=plot_df["close"],
        name=ticker,
        increasing_line_color="#ef5350",
        decreasing_line_color="#26a69a",
    ))

    # MA lines
    ma_styles = [("ma20", "#1f77b4", "MA20"), ("ma60", "#ff7f0e", "MA60"), ("ma120", "#2ca02c", "MA120")]
    for key, color, label in ma_styles:
        if key in ind_tail and not ind_tail[key].dropna().empty:
            fig.add_trace(go.Scatter(
                x=ind_tail[key].index, y=ind_tail[key],
                name=label, line=dict(color=color, width=1.5),
            ))

    # Volume bar (secondary axis)
    if "volume" in plot_df.columns:
        fig.add_trace(go.Bar(
            x=plot_df.index, y=plot_df["volume"],
            name="成交量", yaxis="y2",
            marker_color="#aec7e8", opacity=0.3,
        ))

    fig.update_layout(
        height=480,
        margin=dict(l=20, r=20, t=40, b=20),
        xaxis_rangeslider_visible=False,
        yaxis=dict(title="价格"),
        yaxis2=dict(overlaying="y", side="right", showgrid=False, showticklabels=False),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        hovermode="x unified",
    )
    st.plotly_chart(fig, use_container_width=True)


# ── 6.9 Indicator subcharts ───────────────────────────────────────────────────

def render_indicator_subcharts(df: pd.DataFrame, indicators: dict, ticker: str, n_days: int = 120):
    with st.expander(t("indicator_subcharts"), expanded=False):
        ind = {k: v.tail(n_days) if isinstance(v, pd.Series) else v for k, v in indicators.items()}
        idx = df.tail(n_days).index

        cols = st.columns(3)

        # RSI
        with cols[0]:
            fig_rsi = go.Figure()
            if "rsi" in ind:
                fig_rsi.add_trace(go.Scatter(x=ind["rsi"].index, y=ind["rsi"], name="RSI(14)", line=dict(color="#9467bd")))
            fig_rsi.add_hline(y=70, line_dash="dash", line_color="red", line_width=1)
            fig_rsi.add_hline(y=30, line_dash="dash", line_color="green", line_width=1)
            fig_rsi.add_hline(y=50, line_dash="dot", line_color="grey", line_width=1)
            fig_rsi.update_layout(height=200, margin=dict(l=10, r=10, t=30, b=10), title="RSI(14)")
            st.plotly_chart(fig_rsi, use_container_width=True)

        # MACD
        with cols[1]:
            fig_macd = go.Figure()
            if "macd" in ind:
                fig_macd.add_trace(go.Scatter(x=ind["macd"].index, y=ind["macd"], name="MACD", line=dict(color="#1f77b4")))
            if "macd_signal" in ind:
                fig_macd.add_trace(go.Scatter(x=ind["macd_signal"].index, y=ind["macd_signal"], name="Signal", line=dict(color="#ff7f0e")))
            if "macd_histogram" in ind:
                hist = ind["macd_histogram"]
                colors = ["#ef5350" if v >= 0 else "#26a69a" for v in hist.fillna(0)]
                fig_macd.add_trace(go.Bar(x=hist.index, y=hist, name="Histogram", marker_color=colors, opacity=0.7))
            fig_macd.update_layout(height=200, margin=dict(l=10, r=10, t=30, b=10), title="MACD(12,26,9)")
            st.plotly_chart(fig_macd, use_container_width=True)

        # ADX
        with cols[2]:
            fig_adx = go.Figure()
            if "adx" in ind:
                fig_adx.add_trace(go.Scatter(x=ind["adx"].index, y=ind["adx"], name="ADX(14)", line=dict(color="#d62728")))
            fig_adx.add_hline(y=25, line_dash="dash", line_color="orange", line_width=1,
                              annotation_text="25", annotation_position="right")
            fig_adx.add_hline(y=40, line_dash="dash", line_color="red", line_width=1,
                              annotation_text="40", annotation_position="right")
            fig_adx.update_layout(height=200, margin=dict(l=10, r=10, t=30, b=10), title="ADX(14)")
            st.plotly_chart(fig_adx, use_container_width=True)


# ── 6.10 Trade plan generator ─────────────────────────────────────────────────

def render_trade_plan(
    analysis: TrendAnalysis,
    ticker: str,
    item: StockPoolItem,
    regime_multipliers: dict[str, float],
    lang: str = "zh",
):
    if st.button(t("generate_trade_plan"), key=f"gen_plan_{ticker}"):
        mult = regime_multipliers.get(item.market, 1.0)
        plan = _build_trade_plan_text(analysis, ticker, item, mult)
        st.text_area(t("trade_plan_title"), value=plan, height=500, key=f"plan_text_{ticker}")


def _build_trade_plan_text(
    a: TrendAnalysis,
    ticker: str,
    item: StockPoolItem,
    regime_multiplier: float,
) -> str:
    phase_zh = _PHASE_LABELS_ZH.get(a.trend_phase, a.trend_phase)
    pos_pcts = [round(p * regime_multiplier * 100) for p in [0.40, 0.30, 0.20, 0.10]]

    checks = {
        "均线多头排列": "✅" if a.ma_bullish_alignment else "❌",
        "ADX>25": "✅" if a.adx_strong else "❌",
        "趋势明确": "✅" if a.is_uptrend else "❌",
    }
    checklist = "\n  ".join(f"{v} {k}" for k, v in checks.items())

    return f"""
═══════════════════════════════════════════════════
        单边上涨行情交易计划 — {ticker} ({item.name})
═══════════════════════════════════════════════════
生成日期：{date.today().isoformat()}
市场：{item.market}  行业：{item.sector or '未分类'}
当前趋势阶段：{phase_zh}
宏观体制仓位系数：{int(regime_multiplier * 100)}%

【标的确认】
  {checklist}
  趋势得分：{a.trend_score}/6 {'✅' if a.is_uptrend else '❌'}

【参考入场价】
  当前价格：{a.entry_price:.2f}
  推荐策略：{a.recommended_strategy}

【仓位分配（含体制系数调整）】
  首仓   {pos_pcts[0]}%  → 突破确认/首次回踩均线
  加仓1  {pos_pcts[1]}%  → 第二次回踩均线
  加仓2  {pos_pcts[2]}%  → 第三次回踩均线
  加仓3  {pos_pcts[3]}%  → 谨慎象征性加仓

【止损规则】
  首仓止损：{a.stop_loss_price:.2f}（-6.5%）
  趋势确立后：移动止损至成本价（保本）
  整体止损：跌破MA20收盘确认后离场

【止盈规则】
  目标1（+25%）：{a.target_price_1:.2f} → 减仓 1/4
  目标2（+45%）：{a.target_price_2:.2f} → 再减仓 1/4
  剩余仓位：移动止损（最高价回撤10%）跟踪持有

【纪律红线】
  ✗ 单笔亏损不超过总资金3%
  ✗ 价格偏离MA20超15%时不追入
  ✗ 社交媒体全民热议时不加仓
  ✗ 连续3根大阳线后不追入

【衰竭预警】
  {'⚠️ 当前已触发衰竭信号，请提高警惕' if a.exit_warning else '暂无衰竭信号'}
═══════════════════════════════════════════════════
""".strip()


# ── 6.11 Exhaustion warning ───────────────────────────────────────────────────

_EXHAUSTION_LABELS = {
    "vol_no_price": "天量滞涨（量创新高但价不创高）",
    "rsi_divergence": "RSI顶背离（价格新高但RSI未创高）",
    "macd_histogram_shrink": "MACD柱状体持续缩短（连续3日）",
    "steep_slope_acceleration": "上涨斜率突然变陡（近5日>均速3倍）",
    "gap_up_long_upper_shadow": "跳空高开后长上影线",
    "below_ma20_no_recovery": "跌破MA20后反抽未能收回",
    "adx_peak_reversal": "ADX从高位（>40）拐头下降",
}


def render_exhaustion_warning(analysis: TrendAnalysis, lang: str = "zh"):
    e = analysis.exhaustion_signals
    triggered = {k: v for k, v in vars(e).items() if v is True}

    if not triggered:
        return

    if analysis.exit_warning:
        st.error(f"🔴 **{t('exhaustion_warning_title')}**：已触发 {len(triggered)} 项衰竭信号，建议考虑减仓")
    else:
        st.warning(f"⚠️ **{t('exhaustion_warning_title')}**：触发 {len(triggered)} 项信号，请关注")

    for key in triggered:
        label = _EXHAUSTION_LABELS.get(key, key)
        st.markdown(f"  • {label}")


# ── Main page entry point ─────────────────────────────────────────────────────

@st.fragment
def render_trading_strategy_page():
    """
    Main render function called from app.py tab3.

    Decorated as @st.fragment so that any widget interaction within this page
    (filter changes, stock selection, form fields, sliders) only reruns this
    fragment — the US and China dashboards with their many Plotly charts are
    NOT re-rendered, eliminating the ~2-5s lag on every interaction.
    """
    lang = get_current_language()

    st.subheader(t("stock_pool_title"))

    # Regime banner
    with st.container():
        st.markdown(f"##### {t('trading_regime_banner')}")
        regime_multipliers = render_regime_banner(lang)

    st.divider()

    # Load stock pool from session_state or JSON
    if "stock_pool" not in st.session_state:
        st.session_state["stock_pool"] = load_stock_pool(_STOCK_POOL_PATH)

    items: list[StockPoolItem] = st.session_state["stock_pool"]

    # Store market per ticker for pyramid calculator lookup
    for item in items:
        st.session_state[f"market_{item.ticker}"] = item.market

    # Add form
    new_item = render_add_edit_form(items)
    if new_item is not None:
        updated, error = add_item(items, new_item)
        if error:
            st.error(t(error))
        else:
            save_stock_pool(updated, _STOCK_POOL_PATH)
            st.session_state["stock_pool"] = updated
            st.rerun()

    if not items:
        st.info(t("stock_pool_empty"))
        return

    # Filter
    filtered = render_stock_pool_filters(items)
    if not filtered:
        st.info(t("stock_pool_no_results"))
        return

    # Fetch analysis for visible trending_up items
    today_str = date.today().isoformat()
    analysis_map: dict[str, TrendAnalysis] = {}

    for item in filtered:
        if item.strategy_type == "trending_up" and item.market != "港股":
            cache_key = f"analysis_{item.ticker}_{today_str}"
            df_key = f"df_{item.ticker}_{today_str}"
            if cache_key not in st.session_state:
                from src.data.stock_daily_fetcher import fetch_daily_bars
                with st.spinner(f"正在获取 {item.ticker} 数据..."):
                    df, stale = fetch_daily_bars(item)
                st.session_state[df_key] = df  # cache df to avoid re-reading CSV on every rerun
                if df is not None and not df.empty:
                    result = analyze(df, ticker=item.ticker)
                else:
                    result = TrendAnalysis(ticker=item.ticker, data_insufficient=True)
                st.session_state[cache_key] = result
            analysis_map[item.ticker] = st.session_state[cache_key]

    # Table
    selected_ticker = render_stock_pool_table(filtered, analysis_map)

    # Detail panel
    if selected_ticker:
        selected_item = next((i for i in filtered if i.ticker == selected_ticker), None)
        if selected_item is None:
            return

        st.divider()
        st.subheader(f"📊 {selected_ticker} — {selected_item.name}")

        # Edit / delete / refresh controls
        col_edit, col_del, col_refresh, col_del_confirm = st.columns([1, 1, 1, 3])
        with col_edit:
            if st.button(t("edit_stock"), key=f"btn_edit_{selected_ticker}"):
                st.session_state[f"editing_{selected_ticker}"] = True
        with col_del:
            do_delete = st.button(t("delete_stock"), key=f"btn_del_{selected_ticker}")
        with col_refresh:
            if st.button("🔄 刷新数据", key=f"btn_refresh_{selected_ticker}"):
                today_str_r = date.today().isoformat()
                st.session_state.pop(f"analysis_{selected_ticker}_{today_str_r}", None)
                st.session_state.pop(f"df_{selected_ticker}_{today_str_r}", None)
                st.rerun()
        with col_del_confirm:
            confirm = st.checkbox(t("confirm_delete"), key=f"confirm_del_{selected_ticker}")

        if do_delete:
            if confirm:
                updated = delete_item(items, selected_ticker)
                save_stock_pool(updated, _STOCK_POOL_PATH)
                st.session_state["stock_pool"] = updated
                st.rerun()
            else:
                st.warning("请先勾选确认删除")

        if st.session_state.get(f"editing_{selected_ticker}"):
            edited = render_add_edit_form(items, editing_item=selected_item)
            if edited is not None:
                updated = update_item(items, edited)
                save_stock_pool(updated, _STOCK_POOL_PATH)
                st.session_state["stock_pool"] = updated
                st.session_state.pop(f"editing_{selected_ticker}", None)
                st.rerun()

        # HK placeholder
        if selected_item.market == "港股":
            st.info(t("hk_data_pending"))
            return

        # Non-trending_up placeholder
        if selected_item.strategy_type != "trending_up":
            st.info(t("strategy_coming_soon"))
            return

        analysis = analysis_map.get(selected_ticker)
        if analysis is None or analysis.data_insufficient:
            st.warning(t("insufficient_data"))
            return

        # Detail layout
        col_check, col_phase, col_calc = st.columns(3)
        with col_check:
            render_trend_checklist(analysis, lang)
        with col_phase:
            render_phase_card(analysis, lang)
        with col_calc:
            render_pyramid_calculator(analysis, regime_multipliers, selected_ticker, lang)

        # Exhaustion warning (if any)
        render_exhaustion_warning(analysis, lang)

        # Charts — use session_state df to avoid re-reading CSV on every rerun
        df_key = f"df_{selected_ticker}_{today_str}"
        df_for_chart = st.session_state.get(df_key)
        if df_for_chart is None:
            from src.data.stock_daily_fetcher import fetch_daily_bars
            df_for_chart, _ = fetch_daily_bars(selected_item)
            st.session_state[df_key] = df_for_chart
        if df_for_chart is not None and not df_for_chart.empty:
            render_candlestick_chart(df_for_chart, analysis.indicators, selected_ticker)
            render_indicator_subcharts(df_for_chart, analysis.indicators, selected_ticker)

        # Trade plan
        render_trade_plan(analysis, selected_ticker, selected_item, regime_multipliers, lang)
