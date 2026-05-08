"""Layer 2: Market Regime Scoring.

Evaluates 8 market indicators with configurable weights and outputs a Utilization Rate range.
"""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd

from .config import Layer2Config, L2IndicatorConfig
from .models import IndicatorResult, L2Regime, Layer2Result

logger = logging.getLogger(__name__)

_REGIME_COLORS = {
    L2Regime.STRONG_RISK_ON: "#22c55e",
    L2Regime.RISK_ON: "#86efac",
    L2Regime.NEUTRAL: "#9ca3af",
    L2Regime.RISK_OFF: "#f97316",
    L2Regime.STRONG_RISK_OFF: "#ef4444",
}


def _get_cfg(cfg: Layer2Config, key: str) -> L2IndicatorConfig:
    return cfg.indicators.get(key, L2IndicatorConfig())


def score_spx_vs_50dma(df: pd.DataFrame, cfg: Layer2Config) -> IndicatorResult:
    """L2-1: SPX position relative to its 50DMA."""
    ic = _get_cfg(cfg, "spx_vs_50dma")
    try:
        if "SPX" not in df.columns:
            raise ValueError("SPX column missing")
        spx = df["SPX"].dropna()
        if len(spx) < 50:
            raise ValueError("Insufficient SPX data")
        ma50 = spx.rolling(50).mean().iloc[-1]
        current = spx.iloc[-1]
        pct_diff = ((current - ma50) / ma50) * 100
        above = ic.params.get("above_threshold_pct", 1.0)
        below = ic.params.get("below_threshold_pct", -1.0)

        if pct_diff > above:
            score, hit = 1, f"SPX {pct_diff:+.1f}% above 50DMA (>{above}%)"
        elif pct_diff < below:
            score, hit = -1, f"SPX {pct_diff:+.1f}% below 50DMA (<{below}%)"
        else:
            score, hit = 0, f"SPX {pct_diff:+.1f}% vs 50DMA (within ±{above}%)"

        display = f"{current:,.1f} (vs 50DMA {pct_diff:+.1f}%)"
    except Exception as e:
        logger.warning("L2-1 SPX vs 50DMA failed: %s", e)
        score, display, hit, current = 0, "N/A", "Data unavailable", None

    return IndicatorResult("SPX vs 50DMA", current, display, hit, score, ic.weight)


def score_market_breadth(s5fi: float, cfg: Layer2Config) -> IndicatorResult:
    """L2-2: Market breadth from pre-computed S5FI value."""
    ic = _get_cfg(cfg, "market_breadth")
    risk_on = ic.params.get("risk_on_threshold", 60.0)
    risk_off = ic.params.get("risk_off_threshold", 40.0)

    if s5fi > risk_on:
        score, hit = 1, f"S5FI {s5fi:.0f}% > {risk_on}%"
    elif s5fi < risk_off:
        score, hit = -1, f"S5FI {s5fi:.0f}% < {risk_off}%"
    else:
        score, hit = 0, f"S5FI {s5fi:.0f}% (between {risk_off}%–{risk_on}%)"

    return IndicatorResult("Market Breadth (S5FI)", s5fi, f"{s5fi:.0f}%", hit, score, ic.weight)


def score_vix_level(df: pd.DataFrame, cfg: Layer2Config) -> IndicatorResult:
    """L2-3: Absolute VIX level."""
    ic = _get_cfg(cfg, "vix_level")
    try:
        current = df["VIX"].dropna().iloc[-1]
        low = ic.params.get("low_threshold", 18.0)
        high = ic.params.get("high_threshold", 25.0)

        if current < low:
            score, hit = 1, f"VIX {current:.1f} < {low}"
        elif current > high:
            score, hit = -1, f"VIX {current:.1f} > {high}"
        else:
            score, hit = 0, f"VIX {current:.1f} ({low}–{high})"

        display = f"{current:.1f}"
    except Exception as e:
        logger.warning("L2-3 VIX Level failed: %s", e)
        score, display, hit, current = 0, "N/A", "Data unavailable", None

    return IndicatorResult("VIX Level", current, display, hit, score, ic.weight)


def score_vix_trend(df: pd.DataFrame, cfg: Layer2Config) -> IndicatorResult:
    """L2-4: VIX 10-day change rate."""
    ic = _get_cfg(cfg, "vix_trend")
    try:
        vix = df["VIX"].dropna()
        lookback = int(ic.params.get("lookback_days", 10))
        if len(vix) < lookback + 1:
            raise ValueError("Insufficient VIX data")
        current = vix.iloc[-1]
        past = vix.iloc[-lookback - 1]
        change_pct = ((current - past) / past) * 100 if past != 0 else 0

        falling = ic.params.get("falling_threshold_pct", -10.0)
        rising = ic.params.get("rising_threshold_pct", 10.0)

        if change_pct < falling:
            score, hit = 1, f"VIX 10d change {change_pct:+.1f}% (falling)"
        elif change_pct > rising:
            score, hit = -1, f"VIX 10d change {change_pct:+.1f}% (rising)"
        else:
            score, hit = 0, f"VIX 10d change {change_pct:+.1f}%"

        display = f"{current:.1f} ({change_pct:+.1f}% / 10d)"
    except Exception as e:
        logger.warning("L2-4 VIX Trend failed: %s", e)
        score, display, hit, current = 0, "N/A", "Data unavailable", None

    return IndicatorResult("VIX Trend (10D)", current, display, hit, score, ic.weight)


def score_move_index(df: pd.DataFrame, cfg: Layer2Config) -> IndicatorResult:
    """L2-5: MOVE Index level."""
    ic = _get_cfg(cfg, "move_index")
    try:
        current = df["MOVE"].dropna().iloc[-1]
        low = ic.params.get("low_threshold", 85.0)
        high = ic.params.get("high_threshold", 110.0)

        if current < low:
            score, hit = 1, f"MOVE {current:.0f} < {low}"
        elif current > high:
            score, hit = -1, f"MOVE {current:.0f} > {high}"
        else:
            score, hit = 0, f"MOVE {current:.0f} ({low}–{high})"

        display = f"{current:.0f}"
    except Exception as e:
        logger.warning("L2-5 MOVE Index failed: %s", e)
        score, display, hit, current = 0, "N/A", "Data unavailable", None

    return IndicatorResult("MOVE Index", current, display, hit, score, ic.weight)


def score_credit_health(df: pd.DataFrame, cfg: Layer2Config) -> IndicatorResult:
    """L2-6: JNK 20DMA 5-day slope direction."""
    ic = _get_cfg(cfg, "credit_health")
    try:
        jnk = df["JNK"].dropna()
        slope_days = int(ic.params.get("jnk_20dma_slope_days", 5))
        if len(jnk) < 25:
            raise ValueError("Insufficient JNK data")

        ma20 = jnk.rolling(20).mean().dropna()
        if len(ma20) < slope_days + 1:
            raise ValueError("Insufficient JNK 20DMA data")

        slope = ma20.iloc[-1] - ma20.iloc[-slope_days - 1]
        current = jnk.iloc[-1]

        if slope > 0:
            score, hit = 1, f"JNK 20DMA slope positive ({slope:+.2f})"
        elif slope < 0:
            score, hit = -1, f"JNK 20DMA slope negative ({slope:+.2f})"
        else:
            score, hit = 0, "JNK 20DMA flat"

        display = f"{current:.2f} (slope {slope:+.2f})"
    except Exception as e:
        logger.warning("L2-6 Credit Health failed: %s", e)
        score, display, hit, current = 0, "N/A", "Data unavailable", None

    return IndicatorResult("Credit Health (JNK)", current, display, hit, score, ic.weight)


def score_gold_spx_correlation(df: pd.DataFrame, cfg: Layer2Config) -> IndicatorResult:
    """L2-7: 30-day rolling correlation between Gold and SPX."""
    ic = _get_cfg(cfg, "gold_spx_correlation")
    try:
        lookback = int(ic.params.get("lookback_days", 30))
        gold = df["GOLD"].dropna()
        spx_col = "SPX" if "SPX" in df.columns else "SPY"
        spx = df[spx_col].dropna()

        aligned = pd.concat([gold, spx], axis=1).dropna()
        if len(aligned) < lookback:
            raise ValueError("Insufficient data for correlation")

        corr = aligned.iloc[-lookback:].corr().iloc[0, 1]
        normal_thr = ic.params.get("normal_threshold", 0.2)
        high_thr = ic.params.get("high_threshold", 0.4)

        if corr < normal_thr:
            score, hit = 1, f"Gold-SPX corr {corr:.2f} < {normal_thr} (normal divergence)"
        elif corr > high_thr:
            score, hit = -1, f"Gold-SPX corr {corr:.2f} > {high_thr} (safe-haven co-move)"
        else:
            score, hit = 0, f"Gold-SPX corr {corr:.2f} ({normal_thr}–{high_thr})"

        display = f"{corr:.2f}"
    except Exception as e:
        logger.warning("L2-7 Gold-SPX Correlation failed: %s", e)
        score, display, hit, corr = 0, "N/A", "Data unavailable", None

    return IndicatorResult("Gold-SPX Correlation", corr, display, hit, score, ic.weight)


def score_dxy_trend(df: pd.DataFrame, cfg: Layer2Config) -> IndicatorResult:
    """L2-8: DXY monthly change with non-linear scoring (extreme either way = -1)."""
    ic = _get_cfg(cfg, "dxy_trend")
    try:
        dxy = df["DXY"].dropna()
        lookback = int(ic.params.get("lookback_days", 21))
        if len(dxy) < lookback + 1:
            raise ValueError("Insufficient DXY data")

        current = dxy.iloc[-1]
        past = dxy.iloc[-lookback - 1]
        change_pct = ((current - past) / past) * 100 if past != 0 else 0

        strong_up = ic.params.get("strong_up_threshold_pct", 2.0)
        strong_down = ic.params.get("strong_down_threshold_pct", -3.0)
        mild_down = ic.params.get("mild_down_threshold_pct", -1.0)

        if change_pct > strong_up:
            score, hit = -1, f"DXY +{change_pct:.1f}% (extreme strength, liquidity tightening)"
        elif change_pct < strong_down:
            score, hit = -1, f"DXY {change_pct:.1f}% (extreme weakness, confidence crisis)"
        elif change_pct < mild_down:
            score, hit = 1, f"DXY {change_pct:.1f}% (moderate decline, benign)"
        else:
            score, hit = 0, f"DXY {change_pct:+.1f}% (within normal range)"

        display = f"{current:.1f} ({change_pct:+.1f}% / {lookback}d)"
    except Exception as e:
        logger.warning("L2-8 DXY Trend failed: %s", e)
        score, display, hit, current = 0, "N/A", "Data unavailable", None

    return IndicatorResult("DXY Trend", current, display, hit, score, ic.weight)


def compute_layer2(df: pd.DataFrame, s5fi: float, cfg: Layer2Config) -> Layer2Result:
    """Run all L2 indicators and compute regime + utilization range."""
    indicators = [
        score_spx_vs_50dma(df, cfg),
        score_market_breadth(s5fi, cfg),
        score_vix_level(df, cfg),
        score_vix_trend(df, cfg),
        score_move_index(df, cfg),
        score_credit_health(df, cfg),
        score_gold_spx_correlation(df, cfg),
        score_dxy_trend(df, cfg),
    ]

    weighted_composite = sum(i.weighted_score for i in indicators)

    um = cfg.utilization_map
    if weighted_composite >= 5.0:
        regime = L2Regime.STRONG_RISK_ON
        key = "strong_risk_on"
    elif weighted_composite >= 2.0:
        regime = L2Regime.RISK_ON
        key = "risk_on"
    elif weighted_composite > -2.0:
        regime = L2Regime.NEUTRAL
        key = "neutral"
    elif weighted_composite > -5.0:
        regime = L2Regime.RISK_OFF
        key = "risk_off"
    else:
        regime = L2Regime.STRONG_RISK_OFF
        key = "strong_risk_off"

    util_range = um.get(key)
    if util_range:
        util_min, util_max = util_range.min, util_range.max
    else:
        util_min, util_max = 50, 65

    return Layer2Result(
        indicators=indicators,
        weighted_composite=round(weighted_composite, 1),
        regime=regime,
        utilization_min=util_min,
        utilization_max=util_max,
        color=_REGIME_COLORS[regime],
    )
