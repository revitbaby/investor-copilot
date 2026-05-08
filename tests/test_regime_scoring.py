"""Tests for the regime scoring engine: L1, L2, L3, envelope, and integration."""

import json
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from src.regime.config import load_config
from src.regime.layer1 import compute_layer1
from src.regime.layer2 import compute_layer2
from src.regime.layer3 import compute_layer3, _save_state, _load_state
from src.regime.envelope import compute_envelope
from src.regime.models import (
    L1Regime, L2Regime, SentinelStatus, EnvelopeMode,
    Layer1Result, Layer2Result, Layer3Result, SentinelState, RegimeResult,
)
from src.portfolio.models import Holding
from src.portfolio.advisor import compute_advisory
from src.data.breadth import compute_s5fi


@pytest.fixture
def config():
    return load_config()


def _make_df(days=100, **overrides):
    """Create a minimal DataFrame with required columns for scoring."""
    dates = pd.date_range(end=datetime.now(), periods=days, freq="B")
    data = {
        "WALCL": np.linspace(7_000_000, 7_100_000, days),  # millions
        "RRP": np.full(days, 300.0),   # billions
        "TGA": np.full(days, 500.0),   # billions
        "SOFR": np.full(days, 4.5),
        "Net Liquidity": np.linspace(5800, 5900, days),
        "Net Liquidity MA20": np.linspace(5790, 5890, days),
        "SPX": np.linspace(5000, 5200, days),
        "SPY": np.linspace(500, 520, days),
        "VIX": np.full(days, 15.0),
        "MOVE": np.full(days, 80.0),
        "JNK": np.linspace(90, 92, days),
        "HYG": np.linspace(70, 72, days),
        "DXY": np.full(days, 104.0),
        "GOLD": np.linspace(1900, 2000, days),
    }
    data.update(overrides)
    return pd.DataFrame(data, index=dates)


# ============================================================
# Layer 1 Tests
# ============================================================

class TestLayer1:
    def test_all_positive_expansionary(self, config):
        """AC-1: All L1 indicators +1 → composite ≥ 3 → EXPANSIONARY → 100%."""
        days = 100
        dates = pd.date_range(end=datetime.now(), periods=days, freq="B")

        # Net Liquidity: steadily rising — weekly 20DMA must rise >0.5%/wk for 3+ weeks
        # Use exponential growth to ensure weekly changes exceed threshold
        nl = 5000 * np.exp(np.linspace(0, 0.10, days))
        nl_ma20 = pd.Series(nl).rolling(20).mean().values

        # TGA: dropping significantly (>5% over 21 days)
        tga_base = 600.0
        tga = np.concatenate([
            np.full(days - 21, tga_base),
            np.linspace(tga_base, tga_base * 0.90, 21),  # 10% drop
        ])

        # RRP: above $200B
        rrp = np.full(days, 250.0)

        # SOFR: rate cut ≥10bp over 63 days
        sofr = np.concatenate([np.full(37, 5.0), np.full(63, 4.85)])

        df = pd.DataFrame({
            "Net Liquidity": nl,
            "Net Liquidity MA20": nl_ma20,
            "TGA": tga,
            "RRP": rrp,
            "SOFR": sofr,
        }, index=dates)

        result = compute_layer1(df, config.layer1)
        assert len(result.indicators) == 4
        assert result.composite >= 3
        assert result.regime == L1Regime.EXPANSIONARY
        assert result.ceiling_pct == 100

    def test_all_negative_severe(self, config):
        """AC-2: All L1 indicators -1 → composite ≤ -2 → SEVERE_CONTRACTION → 40%."""
        days = 100
        dates = pd.date_range(end=datetime.now(), periods=days, freq="B")

        nl = np.linspace(6000, 5000, days)
        nl_ma20 = pd.Series(nl).rolling(20).mean().values
        tga = np.linspace(400, 600, days)
        rrp = np.full(days, 30.0)
        sofr = np.concatenate([np.full(37, 4.0), np.full(63, 4.5)])

        df = pd.DataFrame({
            "Net Liquidity": nl,
            "Net Liquidity MA20": nl_ma20,
            "TGA": tga,
            "RRP": rrp,
            "SOFR": sofr,
        }, index=dates)

        result = compute_layer1(df, config.layer1)
        assert result.composite <= -2
        assert result.regime == L1Regime.SEVERE_CONTRACTION
        assert result.ceiling_pct == 40

    def test_exactly_four_indicators(self, config):
        """AC-3: L1 must have exactly 4 indicator results."""
        df = _make_df()
        result = compute_layer1(df, config.layer1)
        assert len(result.indicators) == 4

    def test_single_indicator_failure_neutral(self, config):
        """Missing column defaults to score 0."""
        df = _make_df()
        df = df.drop(columns=["RRP"])
        result = compute_layer1(df, config.layer1)
        rrp_ind = [i for i in result.indicators if i.name == "RRP Buffer"][0]
        assert rrp_ind.score == 0


# ============================================================
# Layer 3 Tests
# ============================================================

class TestLayer3:
    def test_vix_spike_triggers(self, config):
        """AC-4: VIX > 35 triggers sentinel."""
        df = _make_df(VIX=np.full(100, 37.0))

        with tempfile.TemporaryDirectory() as tmpdir:
            state_path = Path(tmpdir) / "sentinel.json"
            result = compute_layer3(df, config.layer3, state_path=state_path)

        vix_s = [s for s in result.sentinels if s.sentinel_id == "vix_spike"][0]
        assert vix_s.status == SentinelStatus.TRIGGERED
        assert vix_s.forced_ceiling_pct == 20

    def test_vix_spike_no_premature_reset(self, config):
        """AC-5: VIX < 25 for only 1 day should NOT reset."""
        with tempfile.TemporaryDirectory() as tmpdir:
            state_path = Path(tmpdir) / "sentinel.json"

            # First: trigger
            df1 = _make_df(VIX=np.full(100, 37.0))
            compute_layer3(df1, config.layer3, state_path=state_path)

            # Second: VIX drops below 25 for 1 day
            df2 = _make_df(VIX=np.full(100, 20.0))
            result = compute_layer3(df2, config.layer3, state_path=state_path)

        vix_s = [s for s in result.sentinels if s.sentinel_id == "vix_spike"][0]
        assert vix_s.status != SentinelStatus.CLEAR  # should still be triggered/cooling

    def test_vix_spike_resets_after_consecutive_days(self, config):
        """AC-6: VIX < 25 for 3 consecutive days → reset to CLEAR."""
        with tempfile.TemporaryDirectory() as tmpdir:
            state_path = Path(tmpdir) / "sentinel.json"

            # Trigger
            df_trigger = _make_df(VIX=np.full(100, 37.0))
            compute_layer3(df_trigger, config.layer3, state_path=state_path)

            # 3 consecutive days below reset threshold
            for _ in range(3):
                df_reset = _make_df(VIX=np.full(100, 20.0))
                result = compute_layer3(df_reset, config.layer3, state_path=state_path)

        vix_s = [s for s in result.sentinels if s.sentinel_id == "vix_spike"][0]
        assert vix_s.status == SentinelStatus.CLEAR

    def test_multi_sentinel_min_ceiling(self, config):
        """AC-7: Multiple sentinels → take minimum forced_ceiling."""
        with tempfile.TemporaryDirectory() as tmpdir:
            state_path = Path(tmpdir) / "sentinel.json"

            # Trigger both VIX spike and credit break
            vix_data = np.full(100, 37.0)
            jnk_data = np.concatenate([np.full(99, 95.0), [92.0]])  # -3.2% last day
            hyg_data = np.concatenate([np.full(99, 75.0), [72.0]])

            df = _make_df(VIX=vix_data, JNK=jnk_data, HYG=hyg_data)
            result = compute_layer3(df, config.layer3, state_path=state_path)

        assert result.override_ceiling_pct == 20
        triggered = [s for s in result.sentinels if s.status != SentinelStatus.CLEAR]
        assert len(triggered) >= 2

    def test_corrupted_state_resets_clear(self, config):
        """Corrupted state file → all sentinels CLEAR."""
        with tempfile.TemporaryDirectory() as tmpdir:
            state_path = Path(tmpdir) / "sentinel.json"
            state_path.write_text("INVALID JSON {{{")

            df = _make_df()
            result = compute_layer3(df, config.layer3, state_path=state_path)

        for s in result.sentinels:
            assert s.status == SentinelStatus.CLEAR


# ============================================================
# Envelope Tests
# ============================================================

class TestEnvelope:
    def test_normal_mode_contracting_risk_on(self):
        """AC-8: CONTRACTING(60%) × RISK_ON(70-85%) = 42%-51%."""
        l1 = Layer1Result([], 0, L1Regime.CONTRACTING, 60, "#f97316")
        l2 = Layer2Result([], 3.0, L2Regime.RISK_ON, 70, 85, "#86efac")
        l3 = Layer3Result([], False, None, False)
        env = compute_envelope(l1, l2, l3)
        assert env.mode == EnvelopeMode.NORMAL
        assert abs(env.target_min - 42.0) < 1
        assert abs(env.target_max - 51.0) < 1

    def test_emergency_override(self):
        """AC-9: L3 override=20% → target_max=20% regardless of L1/L2."""
        l1 = Layer1Result([], 4, L1Regime.EXPANSIONARY, 100, "#22c55e")
        l2 = Layer2Result([], 7.0, L2Regime.STRONG_RISK_ON, 90, 100, "#22c55e")
        sentinel = SentinelState("vix_spike", "VIX Spike", SentinelStatus.TRIGGERED, 20)
        l3 = Layer3Result([sentinel], True, 20, False)
        env = compute_envelope(l1, l2, l3)
        assert env.mode == EnvelopeMode.EMERGENCY
        assert env.target_max == 20.0

    def test_full_bullish(self):
        """AC-10: EXPANSIONARY + STRONG_RISK_ON + Clear → target_max ≥ 90%."""
        l1 = Layer1Result([], 4, L1Regime.EXPANSIONARY, 100, "#22c55e")
        l2 = Layer2Result([], 6.0, L2Regime.STRONG_RISK_ON, 90, 100, "#22c55e")
        l3 = Layer3Result([], False, None, False)
        env = compute_envelope(l1, l2, l3)
        assert env.target_max >= 90.0


# ============================================================
# S5FI Breadth Tests
# ============================================================

class TestS5FI:
    def test_all_above_50dma(self):
        """All ETFs above 50DMA → S5FI = 100."""
        dates = pd.date_range(end=datetime.now(), periods=60, freq="B")
        data = {etf: np.linspace(100, 120, 60) for etf in
                ["XLK", "XLF", "XLV", "XLY", "XLC", "XLI", "XLP", "XLE", "XLRE", "XLU", "XLB"]}
        df = pd.DataFrame(data, index=dates)
        weights = {etf: 1/11 for etf in data}
        result = compute_s5fi(df, weights)
        assert result == 100.0

    def test_all_below_50dma(self):
        """All ETFs below 50DMA → S5FI = 0."""
        dates = pd.date_range(end=datetime.now(), periods=60, freq="B")
        data = {etf: np.linspace(120, 80, 60) for etf in
                ["XLK", "XLF", "XLV", "XLY", "XLC", "XLI", "XLP", "XLE", "XLRE", "XLU", "XLB"]}
        df = pd.DataFrame(data, index=dates)
        weights = {etf: 1/11 for etf in data}
        result = compute_s5fi(df, weights)
        assert result == 0.0

    def test_fallback_on_empty(self):
        """Empty df → fallback value."""
        result = compute_s5fi(pd.DataFrame(), {}, 50.0)
        assert result == 50.0


# ============================================================
# Position Advisor Tests
# ============================================================

class TestPositionAdvisor:
    def _make_regime(self, l1_regime=L1Regime.NEUTRAL, l2_regime=L2Regime.NEUTRAL):
        l1 = Layer1Result([], 1, l1_regime, 80, "#eab308")
        l2 = Layer2Result([], 0, l2_regime, 50, 65, "#9ca3af")
        l3 = Layer3Result([], False, None, False)
        env = compute_envelope(l1, l2, l3)
        return RegimeResult(layer1=l1, layer2=l2, layer3=l3, envelope=env)

    def test_hedge_excluded(self, config):
        """AC-13: Hedge holdings excluded from risk exposure."""
        regime = self._make_regime()
        holdings = [
            Holding("NVDA", "stock", 100, 100, 150, 15000, 15000, "Tech", "A", 1.5),
            Holding("SPY_PUT", "option_long_put", 10, 5, 8, 800, 5000, "Hedge", "Hedge", -0.3),
        ]

        result = compute_advisory(holdings, 100000, 10000, regime, config.position_advisor)
        assert result.current_exposure_pct == 15.0

    def test_c_conviction_risk_off_close(self, config):
        """AC-11: C conviction in RISK_OFF → limit 0% → CLOSE."""
        regime = self._make_regime(l2_regime=L2Regime.RISK_OFF)
        holdings = [
            Holding("MEME", "stock", 100, 10, 12, 1200, 1200, "Spec", "C", 2.0),
        ]

        result = compute_advisory(holdings, 100000, 90000, regime, config.position_advisor)
        advice = result.holdings_advice[0]
        assert advice.action.value == "CLOSE"

    def test_trim_priority_conviction_order(self, config):
        """AC-12: C-conviction before S-conviction in trim priority."""
        regime = self._make_regime()
        holdings = [
            Holding("HIGH", "stock", 100, 100, 150, 15000, 15000, "Tech", "S", 1.2),
            Holding("LOW", "stock", 100, 50, 60, 6000, 6000, "Spec", "C", 1.8),
        ]

        result = compute_advisory(holdings, 100000, 10000, regime, config.position_advisor)
        non_hedge = [a for a in result.holdings_advice if a.conviction != "Hedge"]
        c_priority = next(a.priority for a in non_hedge if a.conviction == "C")
        s_priority = next(a.priority for a in non_hedge if a.conviction == "S")
        assert c_priority < s_priority

    def test_overweight_detection(self, config):
        """AC-14: 70% exposure, target_max 51% → overweight."""
        l1 = Layer1Result([], 0, L1Regime.CONTRACTING, 60, "#f97316")
        l2 = Layer2Result([], 3.0, L2Regime.RISK_ON, 70, 85, "#86efac")
        l3 = Layer3Result([], False, None, False)
        env = compute_envelope(l1, l2, l3)
        regime = RegimeResult(layer1=l1, layer2=l2, layer3=l3, envelope=env)

        holdings = [
            Holding("AAPL", "stock", 500, 100, 140, 70000, 70000, "Tech", "S", 1.1),
        ]

        result = compute_advisory(holdings, 100000, 30000, regime, config.position_advisor)
        assert result.is_overweight
        assert result.excess_dollars > 0
