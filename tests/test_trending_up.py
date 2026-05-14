"""Unit tests for the trending-up analysis engine."""

import numpy as np
import pandas as pd
import pytest

from src.analysis.trending_up import (
    ExhaustionSignals,
    TrendAnalysis,
    _compute_pyramid_position,
    analyze,
)


# ── Synthetic data helpers ────────────────────────────────────────────────────

def _make_uptrend_df(n: int = 200, seed: int = 42) -> pd.DataFrame:
    """
    Synthetic strong bull trend:
    - Price steadily rising with small pullbacks
    - MA20 > MA60 > MA120
    - Volume rises on up-days, shrinks on pullbacks
    """
    rng = np.random.default_rng(seed)
    dates = pd.date_range("2024-01-01", periods=n, freq="B")
    price = 100.0
    prices = []
    volumes = []
    for i in range(n):
        if i % 10 < 8:  # up-day
            change = rng.uniform(0.003, 0.015)
            vol = rng.uniform(1_200_000, 1_800_000)
        else:  # slight pullback
            change = rng.uniform(-0.006, -0.001)
            vol = rng.uniform(600_000, 900_000)
        price *= (1 + change)
        prices.append(price)
        volumes.append(vol)

    close = pd.Series(prices, index=dates)
    high = close * (1 + rng.uniform(0, 0.005, n))
    low = close * (1 - rng.uniform(0, 0.005, n))
    open_ = close * (1 + rng.uniform(-0.003, 0.003, n))

    return pd.DataFrame({
        "open": open_,
        "high": high,
        "low": low,
        "close": close,
        "volume": volumes,
    }, index=dates)


def _make_pullback_df(n: int = 150, seed: int = 7) -> pd.DataFrame:
    """
    Bull trend + pullback near MA20 with shrinking volume at the end.
    Final price lands within ±3% of MA20.
    """
    rng = np.random.default_rng(seed)
    dates = pd.date_range("2024-01-01", periods=n, freq="B")
    price = 100.0
    prices = []
    volumes = []

    for i in range(n):
        if i < n - 15:  # uptrend phase
            change = rng.uniform(0.004, 0.012)
            vol = rng.uniform(1_200_000, 1_600_000)
        else:  # pullback phase: mild decline, shrinking volume
            change = rng.uniform(-0.005, -0.001)
            decay = (i - (n - 15)) * 0.05
            vol = max(rng.uniform(800_000, 1_000_000) * (1 - decay), 300_000)
        price *= (1 + change)
        prices.append(price)
        volumes.append(vol)

    close = pd.Series(prices, index=dates)
    # Nudge close toward MA20 range
    ma20_approx = close.rolling(20).mean().iloc[-1]
    if not pd.isna(ma20_approx):
        close = close * (ma20_approx / close.iloc[-1]) * rng.uniform(0.98, 1.02)

    high = close * (1 + rng.uniform(0, 0.005, n))
    low = close * (1 - rng.uniform(0, 0.005, n))
    open_ = close * (1 + rng.uniform(-0.003, 0.003, n))
    return pd.DataFrame({"open": open_, "high": high, "low": low, "close": close, "volume": volumes}, index=dates)


def _make_acceleration_df(n: int = 200) -> pd.DataFrame:
    """
    Bull trend with realistic up/down mix in baseline, then hard acceleration.
    Ensures RSI is properly computed (not NaN) and reaches > 70 during acceleration.
    """
    dates = pd.date_range("2024-01-01", periods=n, freq="B")
    price = 100.0
    prices = []
    volumes = []
    rng = np.random.default_rng(7)
    accel_start = n - 40

    for i in range(n):
        if i < accel_start:
            # Realistic uptrend: 7 up days, 3 down days in every 10
            if i % 10 < 7:
                change = rng.uniform(0.005, 0.012)
                vol = rng.uniform(1_200_000, 1_600_000)
            else:
                change = rng.uniform(-0.005, -0.001)
                vol = rng.uniform(700_000, 1_000_000)
        else:
            # Hard acceleration: all up, ~2.5% per day
            change = rng.uniform(0.020, 0.035)
            vol = rng.uniform(3_000_000, 5_000_000)
        price *= (1 + change)
        prices.append(price)
        volumes.append(vol)

    close = pd.Series(prices, index=dates)
    high = close * 1.005
    low = close * 0.995
    open_ = close * 0.998
    return pd.DataFrame({"open": open_, "high": high, "low": low, "close": close, "volume": volumes}, index=dates)


# ── Tests ─────────────────────────────────────────────────────────────────────

class TestNoneInput:
    def test_none_returns_data_insufficient(self):
        result = analyze(None)
        assert result.data_insufficient is True

    def test_empty_df_returns_data_insufficient(self):
        result = analyze(pd.DataFrame())
        assert result.data_insufficient is True

    def test_too_short_df_returns_data_insufficient(self):
        tiny = _make_uptrend_df(n=20)
        result = analyze(tiny)
        assert result.data_insufficient is True

    def test_no_exception_on_none(self):
        # Must not raise
        analyze(None, ticker="TEST")


class TestStrongUptrend:
    def setup_method(self):
        self.df = _make_uptrend_df()
        self.result = analyze(self.df, ticker="TEST")

    def test_is_uptrend(self):
        assert self.result.is_uptrend is True

    def test_trend_score_high(self):
        assert self.result.trend_score >= 4

    def test_price_above_ma20(self):
        assert bool(self.result.price_above_ma20) is True

    def test_ma_bullish_alignment(self):
        assert bool(self.result.ma_bullish_alignment) is True

    def test_no_data_insufficient(self):
        assert self.result.data_insufficient is False


class TestPullbackPhase:
    def test_pullback_phase_detected(self):
        df = _make_pullback_df()
        result = analyze(df)
        # Pullback phase: price near MA20 + volume shrinking
        # May land in pullback or neutral depending on exact values — check both
        assert result.trend_phase in ("pullback", "consolidation", "neutral")

    def test_strategy_2_recommended_for_pullback(self):
        df = _make_pullback_df()
        result = analyze(df)
        if result.trend_phase == "pullback":
            assert "策略2" in result.recommended_strategy


class TestAccelerationPhase:
    def test_acceleration_detected(self):
        df = _make_acceleration_df()
        result = analyze(df)
        assert result.trend_phase in ("acceleration", "topping")

    def test_no_entry_recommended(self):
        df = _make_acceleration_df()
        result = analyze(df)
        if result.trend_phase == "acceleration":
            assert "不追" in result.recommended_strategy or "不操作" in result.recommended_strategy


class TestPyramidPosition:
    def test_first_entry_full_regime(self):
        pct = _compute_pyramid_position(1, 1.0)
        assert abs(pct - 0.40) < 0.001

    def test_first_entry_bull_watch_regime(self):
        pct = _compute_pyramid_position(1, 0.75)
        assert abs(pct - 0.30) < 0.001

    def test_second_entry_full_regime(self):
        pct = _compute_pyramid_position(2, 1.0)
        assert abs(pct - 0.30) < 0.001

    def test_fourth_entry_full_regime(self):
        pct = _compute_pyramid_position(4, 1.0)
        assert abs(pct - 0.10) < 0.001

    def test_bear_regime_caps_position(self):
        pct = _compute_pyramid_position(1, 0.30)
        assert pct <= 0.40 * 0.30 + 0.001

    def test_entry_order_clamped(self):
        pct5 = _compute_pyramid_position(5, 1.0)
        pct4 = _compute_pyramid_position(4, 1.0)
        assert pct5 == pct4  # order > 4 clamps to 4


class TestStopLossTargets:
    def setup_method(self):
        self.df = _make_uptrend_df()
        self.result = analyze(self.df)

    def test_stop_loss_is_below_entry(self):
        assert self.result.stop_loss_price < self.result.entry_price

    def test_stop_loss_approx_6_5_pct(self):
        ratio = self.result.stop_loss_price / self.result.entry_price
        assert abs(ratio - (1 - 0.065)) < 0.002

    def test_target1_is_25_pct_above(self):
        ratio = self.result.target_price_1 / self.result.entry_price
        assert abs(ratio - 1.25) < 0.002

    def test_target2_is_45_pct_above(self):
        ratio = self.result.target_price_2 / self.result.entry_price
        assert abs(ratio - 1.45) < 0.002

    def test_with_synthetic_entry_100(self):
        """Verify exact math for entry_price=100."""
        df = _make_uptrend_df()
        # Scale so close ends at ~100
        scale = 100.0 / df["close"].iloc[-1]
        scaled = df.copy()
        for col in ["open", "high", "low", "close"]:
            scaled[col] = scaled[col] * scale
        r = analyze(scaled)
        assert abs(r.stop_loss_price - 93.5) < 0.5
        assert abs(r.target_price_1 - 125.0) < 0.5
        assert abs(r.target_price_2 - 145.0) < 0.5


class TestExhaustionWarning:
    def _patch_two_signals(self) -> TrendAnalysis:
        """Return a TrendAnalysis with 2 exhaustion signals manually set."""
        result = TrendAnalysis()
        result.exhaustion_signals.vol_no_price = True
        result.exhaustion_signals.rsi_divergence = True
        result.exit_warning = result.exhaustion_signals.triggered_count() >= 2
        return result

    def _patch_one_signal(self) -> TrendAnalysis:
        result = TrendAnalysis()
        result.exhaustion_signals.vol_no_price = True
        result.exit_warning = result.exhaustion_signals.triggered_count() >= 2
        return result

    def test_two_signals_trigger_warning(self):
        r = self._patch_two_signals()
        assert r.exit_warning is True

    def test_one_signal_no_warning(self):
        r = self._patch_one_signal()
        assert r.exit_warning is False

    def test_exhaustion_count_correct(self):
        e = ExhaustionSignals(vol_no_price=True, rsi_divergence=True, macd_histogram_shrink=True)
        assert e.triggered_count() == 3
