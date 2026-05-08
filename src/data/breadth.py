"""Compute S5FI market breadth approximation from sector ETFs."""

from __future__ import annotations

import pandas as pd
import numpy as np
import logging

logger = logging.getLogger(__name__)

SECTOR_ETFS = ["XLK", "XLF", "XLV", "XLY", "XLC", "XLI", "XLP", "XLE", "XLRE", "XLU", "XLB"]


def compute_s5fi(
    sector_data: pd.DataFrame,
    sector_weights: dict[str, float],
    fallback_value: float = 50.0,
) -> float:
    """Approximate S&P 500 market breadth using sector ETF positions vs 50DMA.

    Each sector ETF is scored 1 (above 50DMA) or 0 (below), then weighted by
    its approximate S&P 500 sector weight.

    Returns a value between 0 and 100, or ``fallback_value`` on failure.
    """
    try:
        if sector_data.empty:
            return fallback_value

        total_weight = 0.0
        weighted_score = 0.0

        for etf in SECTOR_ETFS:
            if etf not in sector_data.columns:
                continue

            series = sector_data[etf].dropna()
            if len(series) < 50:
                continue

            ma50 = series.rolling(window=50).mean()
            latest_price = series.iloc[-1]
            latest_ma50 = ma50.iloc[-1]

            if pd.isna(latest_ma50):
                continue

            weight = sector_weights.get(etf, 0.0)
            above = 1.0 if latest_price > latest_ma50 else 0.0
            weighted_score += above * weight
            total_weight += weight

        if total_weight == 0:
            return fallback_value

        return (weighted_score / total_weight) * 100.0

    except Exception:
        logger.warning("S5FI computation failed, returning fallback %s", fallback_value, exc_info=True)
        return fallback_value
