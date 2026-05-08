"""Layer 1: Liquidity Foundation Scoring.

Evaluates 4 macro liquidity indicators and outputs a Position Ceiling.
"""

from __future__ import annotations

import logging
from typing import Any

import numpy as np
import pandas as pd

from .config import Layer1Config
from .models import IndicatorResult, L1Regime, Layer1Result

logger = logging.getLogger(__name__)

_REGIME_COLORS = {
    L1Regime.EXPANSIONARY: "#22c55e",
    L1Regime.NEUTRAL: "#eab308",
    L1Regime.CONTRACTING: "#f97316",
    L1Regime.SEVERE_CONTRACTION: "#ef4444",
}


def score_net_liquidity_trend(df: pd.DataFrame, cfg: Layer1Config) -> IndicatorResult:
    """L1-1: Score the 20DMA trend of Net Liquidity over consecutive weeks."""
    try:
        if "Net Liquidity" not in df.columns:
            raise ValueError("Net Liquidity column missing")

        nl = df["Net Liquidity"].dropna()
        if len(nl) < 25:
            raise ValueError("Insufficient data for 20DMA")

        ma20 = nl.rolling(window=20).mean().dropna()
        latest_nl = nl.iloc[-1]
        latest_ma20 = ma20.iloc[-1]
        deviation_pct = ((latest_nl - latest_ma20) / latest_ma20) * 100

        n_weeks = cfg.net_liquidity.lookback_weeks
        rising_thr = cfg.net_liquidity.rising_threshold_pct_per_week
        falling_thr = cfg.net_liquidity.falling_threshold_pct_per_week

        weekly_ma = ma20.resample("W-FRI").last().dropna()
        if len(weekly_ma) < n_weeks + 1:
            score = 0
            threshold_hit = "Insufficient weekly data"
        else:
            recent = weekly_ma.iloc[-(n_weeks + 1):]
            weekly_changes = recent.pct_change().dropna() * 100
            if len(weekly_changes) >= n_weeks and all(c > rising_thr for c in weekly_changes):
                score = 1
                threshold_hit = f"20DMA rising ≥{n_weeks} weeks (>{rising_thr}%/wk)"
            elif len(weekly_changes) >= n_weeks and all(c < falling_thr for c in weekly_changes):
                score = -1
                threshold_hit = f"20DMA falling ≥{n_weeks} weeks (<{falling_thr}%/wk)"
            else:
                score = 0
                threshold_hit = "20DMA within neutral range"

        display = f"{latest_nl:,.0f}B (vs 20DMA {deviation_pct:+.1f}%)"
    except Exception as e:
        logger.warning("L1-1 Net Liquidity Trend scoring failed: %s", e)
        score, display, threshold_hit, latest_nl = 0, "N/A", "Data unavailable", None

    return IndicatorResult(
        name="Net Liquidity Trend", raw_value=latest_nl,
        display_value=display, threshold_hit=threshold_hit, score=score,
    )


def score_tga_trend(df: pd.DataFrame, cfg: Layer1Config) -> IndicatorResult:
    """L1-2: Score TGA balance change (direction inverted: TGA down = bullish)."""
    try:
        if "TGA" not in df.columns:
            raise ValueError("TGA column missing")

        tga = df["TGA"].dropna()
        lookback = cfg.tga.lookback_days
        if len(tga) < lookback:
            raise ValueError("Insufficient TGA data")

        current = tga.iloc[-1]
        past = tga.iloc[-lookback]
        change_pct = ((current - past) / past) * 100 if past != 0 else 0

        # Inverted: TGA decrease = liquidity release = bullish
        if change_pct < cfg.tga.falling_threshold_pct:
            score = 1
            threshold_hit = f"TGA down {change_pct:.1f}% (releasing liquidity)"
        elif change_pct > cfg.tga.rising_threshold_pct:
            score = -1
            threshold_hit = f"TGA up {change_pct:.1f}% (absorbing liquidity)"
        else:
            score = 0
            threshold_hit = f"TGA change {change_pct:.1f}% (within ±{cfg.tga.rising_threshold_pct}%)"

        display = f"${current:,.0f}B ({change_pct:+.1f}% / {lookback}d)"
    except Exception as e:
        logger.warning("L1-2 TGA Trend scoring failed: %s", e)
        score, display, threshold_hit, current = 0, "N/A", "Data unavailable", None

    return IndicatorResult(
        name="TGA Trend", raw_value=current,
        display_value=display, threshold_hit=threshold_hit, score=score,
    )


def score_rrp_buffer(df: pd.DataFrame, cfg: Layer1Config) -> IndicatorResult:
    """L1-3: Score RRP absolute level (high = buffer available = bullish)."""
    try:
        if "RRP" not in df.columns:
            raise ValueError("RRP column missing")

        current = df["RRP"].dropna().iloc[-1]
        high = cfg.rrp.high_threshold_billions
        low = cfg.rrp.low_threshold_billions

        if current > high:
            score = 1
            threshold_hit = f"RRP ${current:.0f}B > ${high:.0f}B (buffer ample)"
        elif current < low:
            score = -1
            threshold_hit = f"RRP ${current:.0f}B < ${low:.0f}B (buffer depleted)"
        else:
            score = 0
            threshold_hit = f"RRP ${current:.0f}B (between ${low:.0f}B–${high:.0f}B)"

        display = f"${current:,.0f}B"
    except Exception as e:
        logger.warning("L1-3 RRP Buffer scoring failed: %s", e)
        score, display, threshold_hit, current = 0, "N/A", "Data unavailable", None

    return IndicatorResult(
        name="RRP Buffer", raw_value=current,
        display_value=display, threshold_hit=threshold_hit, score=score,
    )


def score_policy_rate_direction(df: pd.DataFrame, cfg: Layer1Config) -> IndicatorResult:
    """L1-4: Score policy rate change over lookback period."""
    try:
        if "SOFR" not in df.columns:
            raise ValueError("SOFR column missing")

        sofr = df["SOFR"].dropna()
        lookback = cfg.policy_rate.lookback_days
        if len(sofr) < lookback:
            raise ValueError("Insufficient SOFR data")

        current = sofr.iloc[-1]
        past = sofr.iloc[-lookback]
        change_bp = (current - past) * 100  # SOFR is in %, convert to bp

        cut_thr = cfg.policy_rate.cut_threshold_bp
        hike_thr = cfg.policy_rate.hike_threshold_bp

        if change_bp <= -cut_thr:
            score = 1
            threshold_hit = f"Rate cut {change_bp:.0f}bp (≥{cut_thr}bp cut)"
        elif change_bp >= hike_thr:
            score = -1
            threshold_hit = f"Rate hike +{change_bp:.0f}bp (≥{hike_thr}bp hike)"
        else:
            score = 0
            threshold_hit = f"Rate change {change_bp:+.0f}bp (within ±{cut_thr}bp)"

        display = f"{current:.2f}% ({change_bp:+.0f}bp / {lookback}d)"
    except Exception as e:
        logger.warning("L1-4 Policy Rate scoring failed: %s", e)
        score, display, threshold_hit, current = 0, "N/A", "Data unavailable", None

    return IndicatorResult(
        name="Policy Rate Direction", raw_value=current,
        display_value=display, threshold_hit=threshold_hit, score=score,
    )


def compute_layer1(df: pd.DataFrame, cfg: Layer1Config) -> Layer1Result:
    """Run all L1 indicators and compute regime + ceiling."""
    indicators = [
        score_net_liquidity_trend(df, cfg),
        score_tga_trend(df, cfg),
        score_rrp_buffer(df, cfg),
        score_policy_rate_direction(df, cfg),
    ]

    composite = sum(i.score for i in indicators)

    cm = cfg.ceiling_map
    if composite >= 3:
        regime, ceiling = L1Regime.EXPANSIONARY, cm.expansionary
    elif composite >= 1:
        regime, ceiling = L1Regime.NEUTRAL, cm.neutral
    elif composite >= -1:
        regime, ceiling = L1Regime.CONTRACTING, cm.contracting
    else:
        regime, ceiling = L1Regime.SEVERE_CONTRACTION, cm.severe

    return Layer1Result(
        indicators=indicators,
        composite=composite,
        regime=regime,
        ceiling_pct=ceiling,
        color=_REGIME_COLORS[regime],
    )
