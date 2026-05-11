"""
Unit tests for the China A-share regime scoring engine.

Covers Layer 1 scoring, Layer 2 classification, Layer 3 sentinels,
and Envelope synthesis — all pure functions, no external API calls.
"""

from __future__ import annotations

import json
import tempfile
from datetime import date, datetime, timezone
from pathlib import Path

import pytest

from src.analysis.china_regime import (
    # Enums
    ChinaL1Regime,
    ChinaL2Regime,
    SentinelStatus,
    # Data classes
    ChinaEnvelopeResult,
    ChinaInputData,
    ChinaL1Result,
    ChinaL1Signals,
    ChinaL2Result,
    ChinaSentinelState,
    SentinelEntry,
    # Layer 1
    score_dr007_signal,
    score_m1_yoy_signal,
    score_m1_m2_spread_signal,
    score_tsf_signal,
    compute_china_layer1,
    # Layer 2
    classify_equity_bond_signal,
    classify_margin_signal,
    classify_qvix_signal,
    compute_northbound_utilization_adjustment,
    classify_china_regime,
    # Layer 3
    evaluate_limit_up_heat,
    evaluate_limit_down_panic,
    evaluate_zt_dt_ratio,
    evaluate_southbound_surge,
    evaluate_volume_spike,
    evaluate_china_sentinels,
    # Envelope
    compute_china_envelope,
    # State persistence
    load_china_sentinel_state,
    save_china_sentinel_state,
    # Utility
    compute_margin_ratio_distance,
    compute_equity_bond_spread_description,
    get_deposit_ratio_description,
)


# ──────────────────────────────────────────────────────────────────────────────
# Layer 1 Tests (task 3.6)
# ──────────────────────────────────────────────────────────────────────────────

class TestDR007Signal:
    def test_below_omo_loose(self):
        assert score_dr007_signal(1.5, 2.0) == 1

    def test_above_omo_tight(self):
        assert score_dr007_signal(2.5, 2.0) == -1

    def test_equal_neutral(self):
        assert score_dr007_signal(2.0, 2.0) == 0

    def test_none_dr007(self):
        assert score_dr007_signal(None, 2.0) == 0

    def test_none_omo(self):
        assert score_dr007_signal(1.5, None) == 0

    def test_both_none(self):
        assert score_dr007_signal(None, None) == 0


class TestM1YoYSignal:
    def test_positive_accelerating(self):
        assert score_m1_yoy_signal(5.0, 3.0) == 1

    def test_positive_decelerating(self):
        # Still positive but slowing; not accelerating → 0
        assert score_m1_yoy_signal(3.0, 5.0) == 0

    def test_positive_no_prev(self):
        # Positive without prior: treated as accelerating
        assert score_m1_yoy_signal(2.0, None) == 1

    def test_negative_persistent(self):
        assert score_m1_yoy_signal(-2.0, -1.0) == -1

    def test_negative_recovering(self):
        # Still negative but improving
        assert score_m1_yoy_signal(-1.0, -2.0) == 0

    def test_none(self):
        assert score_m1_yoy_signal(None) == 0


class TestM1M2SpreadSignal:
    def test_positive_spread(self):
        assert score_m1_m2_spread_signal(1.0) == 1

    def test_zero_spread(self):
        assert score_m1_m2_spread_signal(0.0) == 1

    def test_widening_negative(self):
        assert score_m1_m2_spread_signal(-3.0, -2.0) == -1

    def test_narrowing_negative(self):
        # Negative but improving → 0
        assert score_m1_m2_spread_signal(-1.0, -3.0) == 0

    def test_none(self):
        assert score_m1_m2_spread_signal(None) == 0


class TestTSFSignal:
    def test_accelerating(self):
        assert score_tsf_signal(12.0, 10.0) == 1

    def test_decelerating(self):
        assert score_tsf_signal(8.0, 10.0) == -1

    def test_no_prev(self):
        assert score_tsf_signal(10.0, None) == 0

    def test_none(self):
        assert score_tsf_signal(None) == 0


class TestComputeChineseLayer1:
    def _all_bull_signals(self) -> ChinaL1Signals:
        return ChinaL1Signals(
            dr007=1.5, omo_rate=2.0,
            m1_yoy=5.0, m1_yoy_prev=3.0,
            m1_m2_spread=1.0,
            tsf_yoy=12.0, tsf_yoy_prev=10.0,
        )

    def _all_bear_signals(self) -> ChinaL1Signals:
        return ChinaL1Signals(
            dr007=2.5, omo_rate=2.0,
            m1_yoy=-2.0, m1_yoy_prev=-1.0,
            m1_m2_spread=-3.0, m1_m2_spread_prev=-2.0,
            tsf_yoy=8.0, tsf_yoy_prev=10.0,
        )

    def test_full_bull_expansionary(self):
        result = compute_china_layer1(self._all_bull_signals())
        assert result.composite == 4
        assert result.regime == ChinaL1Regime.EXPANSIONARY
        assert result.ceiling_pct == 80

    def test_composite_3_still_expansionary(self):
        signals = self._all_bull_signals()
        signals.tsf_yoy_prev = signals.tsf_yoy  # TSF flat → 0
        result = compute_china_layer1(signals)
        assert result.composite == 3
        assert result.regime == ChinaL1Regime.EXPANSIONARY
        assert result.ceiling_pct == 80

    def test_full_bear_contracting(self):
        result = compute_china_layer1(self._all_bear_signals())
        assert result.composite == -4
        assert result.regime == ChinaL1Regime.CONTRACTING
        assert result.ceiling_pct == 40

    def test_composite_minus2_contracting(self):
        signals = ChinaL1Signals(
            dr007=2.5, omo_rate=2.0,       # -1
            m1_yoy=-1.0, m1_yoy_prev=-1.0,  # -1
            m1_m2_spread=0.5,               # +1
            tsf_yoy=10.0, tsf_yoy_prev=10.0, # 0
        )
        result = compute_china_layer1(signals)
        assert result.composite == -1
        assert result.regime == ChinaL1Regime.NEUTRAL

    def test_mixed_neutral(self):
        signals = ChinaL1Signals(
            dr007=1.5, omo_rate=2.0,    # +1
            m1_yoy=-1.0, m1_yoy_prev=-2.0,  # 0 (negative but improving)
            m1_m2_spread=None,           # 0
            tsf_yoy=None,               # 0
        )
        result = compute_china_layer1(signals)
        assert result.composite == 1
        assert result.regime == ChinaL1Regime.NEUTRAL
        assert result.ceiling_pct == 60

    def test_all_missing_data_neutral(self):
        result = compute_china_layer1(ChinaL1Signals())
        assert result.composite == 0
        assert result.regime == ChinaL1Regime.NEUTRAL


# ──────────────────────────────────────────────────────────────────────────────
# Layer 2 Tests (task 4.6)
# ──────────────────────────────────────────────────────────────────────────────

class TestClassifyEquityBondSignal:
    def test_undervalued(self):
        assert classify_equity_bond_signal(3.5) == "UNDERVALUED"

    def test_overvalued(self):
        assert classify_equity_bond_signal(0.5) == "OVERVALUED"

    def test_neutral(self):
        assert classify_equity_bond_signal(2.0) == "NEUTRAL"

    def test_boundary_3pct(self):
        assert classify_equity_bond_signal(3.0) == "NEUTRAL"

    def test_boundary_1pct(self):
        assert classify_equity_bond_signal(1.0) == "NEUTRAL"


class TestClassifyMarginSignal:
    def test_overheated(self):
        assert classify_margin_signal(3.0) == "OVERHEATED"

    def test_cold(self):
        assert classify_margin_signal(1.0) == "COLD"

    def test_normal(self):
        assert classify_margin_signal(2.0) == "NORMAL"


class TestClassifyQvixSignal:
    def test_high(self):
        assert classify_qvix_signal(35.0) == "HIGH"

    def test_low(self):
        assert classify_qvix_signal(12.0) == "LOW"

    def test_normal(self):
        assert classify_qvix_signal(20.0) == "NORMAL"

    def test_none_returns_none(self):
        assert classify_qvix_signal(None) is None


class TestNorthboundAdjustment:
    def test_large_inflow(self):
        assert compute_northbound_utilization_adjustment(30.0) == 0.05

    def test_large_outflow(self):
        assert compute_northbound_utilization_adjustment(-30.0) == -0.05

    def test_small_flow(self):
        assert compute_northbound_utilization_adjustment(10.0) == 0.0

    def test_none(self):
        assert compute_northbound_utilization_adjustment(None) == 0.0

    def test_boundary_20(self):
        assert compute_northbound_utilization_adjustment(20.0) == 0.0

    def test_just_above_20(self):
        assert compute_northbound_utilization_adjustment(20.01) == 0.05


class TestClassifyChinaRegime:
    def test_value_bull(self):
        result = classify_china_regime("UNDERVALUED", "COLD", "LOW", 0.0)
        assert result.regime == ChinaL2Regime.VALUE_BULL
        assert result.utilization_min == 80
        assert result.utilization_max == 100

    def test_panic_bottom(self):
        result = classify_china_regime("UNDERVALUED", "COLD", "HIGH", 0.0)
        assert result.regime == ChinaL2Regime.PANIC_BOTTOM
        assert result.utilization_min == 40
        assert result.utilization_max == 60

    def test_overvaluation_risk(self):
        result = classify_china_regime("OVERVALUED", "OVERHEATED", None, 0.0)
        assert result.regime == ChinaL2Regime.OVERVALUATION_RISK
        assert result.utilization_min == 20

    def test_sentiment_bull(self):
        result = classify_china_regime("NEUTRAL", "OVERHEATED", "NORMAL", 0.0)
        assert result.regime == ChinaL2Regime.SENTIMENT_BULL
        assert result.utilization_min == 60

    def test_neutral_default(self):
        result = classify_china_regime("OVERVALUED", "NORMAL", None, 0.0)
        assert result.regime == ChinaL2Regime.NEUTRAL
        assert result.utilization_min == 50

    def test_northbound_inflow_adjustment(self):
        base = classify_china_regime("UNDERVALUED", "COLD", "LOW", 0.0)
        adjusted = classify_china_regime("UNDERVALUED", "COLD", "LOW", 0.05)
        assert adjusted.utilization_min == min(100, base.utilization_min + 5)
        assert adjusted.utilization_max == min(100, base.utilization_max + 5)

    def test_northbound_outflow_adjustment(self):
        adjusted = classify_china_regime("UNDERVALUED", "COLD", "LOW", -0.05)
        assert adjusted.utilization_min == 75
        assert adjusted.utilization_max == 95

    def test_qvix_missing_fallback_value_bull(self):
        # QVIX=None should not prevent VALUE_BULL classification (treated as not HIGH)
        result = classify_china_regime("UNDERVALUED", "NORMAL", None, 0.0)
        assert result.regime == ChinaL2Regime.VALUE_BULL

    def test_adjustment_capped_at_100(self):
        result = classify_china_regime("UNDERVALUED", "COLD", "LOW", 0.05)
        assert result.utilization_max <= 100

    def test_adjustment_floored_at_0(self):
        result = classify_china_regime("OVERVALUATION_RISK" if False else "OVERVALUED", "OVERHEATED", None, -0.05)
        assert result.utilization_min >= 0


# ──────────────────────────────────────────────────────────────────────────────
# Layer 3 Tests (task 5.7)
# ──────────────────────────────────────────────────────────────────────────────

def _clear_entry(sid: str, name: str = "test") -> SentinelEntry:
    return SentinelEntry(sentinel_id=sid, name=name)


def _triggered_entry(sid: str, name: str = "test", days: int = 0) -> SentinelEntry:
    return SentinelEntry(
        sentinel_id=sid, name=name,
        status=SentinelStatus.TRIGGERED,
        trigger_timestamp=datetime.now(timezone.utc).isoformat(),
        hold_down_days=days,
    )


class TestEvaluateLimitUpHeat:
    def test_trigger_above_200(self):
        result = evaluate_limit_up_heat(250, _clear_entry("luh"))
        assert result.status == SentinelStatus.TRIGGERED

    def test_no_trigger_below_200(self):
        result = evaluate_limit_up_heat(150, _clear_entry("luh"))
        assert result.status == SentinelStatus.CLEAR

    def test_data_anomaly_below_5_stays_clear(self):
        result = evaluate_limit_up_heat(3, _clear_entry("luh"))
        assert result.status == SentinelStatus.CLEAR

    def test_data_anomaly_does_not_trigger(self):
        # Even if currently triggered, count=3 is missing → no further state change trigger
        triggered = _triggered_entry("luh")
        result = evaluate_limit_up_heat(3, triggered)
        # Count treated as missing → advance with trigger=False → increment hold_down
        assert result.hold_down_days == 1

    def test_none_count_does_not_trigger(self):
        result = evaluate_limit_up_heat(None, _clear_entry("luh"))
        assert result.status == SentinelStatus.CLEAR


class TestEvaluateLimitDownPanic:
    def test_trigger_above_50(self):
        result = evaluate_limit_down_panic(60, _clear_entry("ldp"))
        assert result.status == SentinelStatus.TRIGGERED

    def test_no_trigger(self):
        result = evaluate_limit_down_panic(40, _clear_entry("ldp"))
        assert result.status == SentinelStatus.CLEAR

    def test_none_no_trigger(self):
        result = evaluate_limit_down_panic(None, _clear_entry("ldp"))
        assert result.status == SentinelStatus.CLEAR


class TestEvaluateZtDtRatio:
    def test_extreme_high_ratio(self):
        result = evaluate_zt_dt_ratio(100, 5, _clear_entry("zdt"))
        assert result.status == SentinelStatus.TRIGGERED

    def test_extreme_low_ratio(self):
        result = evaluate_zt_dt_ratio(1, 20, _clear_entry("zdt"))
        assert result.status == SentinelStatus.TRIGGERED

    def test_normal_ratio(self):
        result = evaluate_zt_dt_ratio(50, 20, _clear_entry("zdt"))
        assert result.status == SentinelStatus.CLEAR

    def test_zero_dt_no_trigger(self):
        result = evaluate_zt_dt_ratio(100, 0, _clear_entry("zdt"))
        assert result.status == SentinelStatus.CLEAR

    def test_none_values_no_trigger(self):
        result = evaluate_zt_dt_ratio(None, None, _clear_entry("zdt"))
        assert result.status == SentinelStatus.CLEAR


class TestEvaluateSouthboundSurge:
    def test_trigger_on_high_sigma(self):
        result = evaluate_southbound_surge(100, 2.5, _clear_entry("sbs"))
        assert result.status == SentinelStatus.TRIGGERED

    def test_trigger_on_negative_sigma(self):
        result = evaluate_southbound_surge(-50, -2.5, _clear_entry("sbs"))
        assert result.status == SentinelStatus.TRIGGERED

    def test_no_trigger_within_2sigma(self):
        result = evaluate_southbound_surge(10, 1.5, _clear_entry("sbs"))
        assert result.status == SentinelStatus.CLEAR

    def test_none_sigma_no_trigger(self):
        result = evaluate_southbound_surge(None, None, _clear_entry("sbs"))
        assert result.status == SentinelStatus.CLEAR


class TestEvaluateVolumeSpike:
    def test_trigger_above_1_5x_ma20(self):
        result = evaluate_volume_spike(1600, 1000, _clear_entry("vs"))
        assert result.status == SentinelStatus.TRIGGERED

    def test_no_trigger_below_threshold(self):
        result = evaluate_volume_spike(1400, 1000, _clear_entry("vs"))
        assert result.status == SentinelStatus.CLEAR

    def test_none_amount_no_trigger(self):
        result = evaluate_volume_spike(None, 1000, _clear_entry("vs"))
        assert result.status == SentinelStatus.CLEAR

    def test_none_ma20_no_trigger(self):
        result = evaluate_volume_spike(2000, None, _clear_entry("vs"))
        assert result.status == SentinelStatus.CLEAR


class TestHoldDownLogic:
    def test_hold_down_prevents_premature_reset(self):
        entry = _triggered_entry("luh", days=0)
        r1 = evaluate_limit_up_heat(100, entry)  # below threshold
        assert r1.status == SentinelStatus.COOLING
        assert r1.hold_down_days == 1

        r2 = evaluate_limit_up_heat(100, r1)
        assert r2.status == SentinelStatus.COOLING
        assert r2.hold_down_days == 2

        r3 = evaluate_limit_up_heat(100, r2)
        assert r3.status == SentinelStatus.CLEAR
        assert r3.hold_down_days == 0

    def test_retrigger_resets_hold_down(self):
        entry = _triggered_entry("luh", days=2)
        r = evaluate_limit_up_heat(250, entry)
        assert r.status == SentinelStatus.TRIGGERED
        assert r.hold_down_days == 0

    def test_state_persists_across_restarts(self, tmp_path):
        import sys
        from unittest.mock import patch
        state = ChinaSentinelState()
        state.limit_down_panic = _triggered_entry("limit_down_panic", "跌停恐慌", days=1)

        sentinel_file = tmp_path / "sentinel_state.json"
        with patch("src.analysis.china_regime._SENTINEL_STATE_FILE", sentinel_file):
            save_china_sentinel_state(state)
            loaded = load_china_sentinel_state()

        assert loaded.limit_down_panic.status == SentinelStatus.TRIGGERED
        assert loaded.limit_down_panic.hold_down_days == 1


class TestEvaluateChinaSentinels:
    def test_all_clear_by_default(self):
        state = evaluate_china_sentinels(
            limit_up_count=100,
            limit_down_count=20,
            zt_count=50,
            dt_count=20,
            southbound_net_buy=10,
            southbound_sigma_dev=0.5,
            total_amount=1000,
            total_amount_ma20=1000,
            current_state=ChinaSentinelState(),
        )
        assert not state.any_triggered()

    def test_multiple_triggers(self):
        state = evaluate_china_sentinels(
            limit_up_count=250,   # → LIMIT_UP_HEAT
            limit_down_count=60,  # → LIMIT_DOWN_PANIC
            zt_count=None,
            dt_count=None,
            southbound_net_buy=None,
            southbound_sigma_dev=None,
            total_amount=None,
            total_amount_ma20=None,
            current_state=ChinaSentinelState(),
        )
        assert state.triggered_count() == 2
        assert state.limit_up_heat.status == SentinelStatus.TRIGGERED
        assert state.limit_down_panic.status == SentinelStatus.TRIGGERED


# ──────────────────────────────────────────────────────────────────────────────
# Envelope Tests (task 6.2)
# ──────────────────────────────────────────────────────────────────────────────

def _make_l1(composite: int = 2, ceiling: int = 60) -> ChinaL1Result:
    regime = (ChinaL1Regime.EXPANSIONARY if ceiling == 80
              else ChinaL1Regime.CONTRACTING if ceiling == 40
              else ChinaL1Regime.NEUTRAL)
    return ChinaL1Result(
        dr007_score=0, m1_yoy_score=0, m1_m2_spread_score=0, tsf_score=0,
        composite=composite, regime=regime, ceiling_pct=ceiling,
    )


def _make_l2(util_min: int = 80, util_max: int = 100) -> ChinaL2Result:
    return ChinaL2Result(
        equity_bond_signal="UNDERVALUED", margin_signal="NORMAL",
        qvix_signal=None, northbound_adjustment=0.0,
        regime=ChinaL2Regime.VALUE_BULL,
        utilization_min=util_min, utilization_max=util_max,
    )


class TestComputeChinaEnvelope:
    def test_normal_mode_calculation(self):
        l1 = _make_l1(ceiling=60)
        l2 = _make_l2(util_min=80, util_max=100)
        l3 = ChinaSentinelState()
        result = compute_china_envelope(l1, l2, l3)
        assert result.target_min == pytest.approx(48.0)
        assert result.target_max == pytest.approx(60.0)
        assert not result.is_emergency

    def test_full_bull_max_80(self):
        l1 = _make_l1(ceiling=80)
        l2 = _make_l2(util_min=80, util_max=100)
        l3 = ChinaSentinelState()
        result = compute_china_envelope(l1, l2, l3)
        assert result.target_max == pytest.approx(80.0)

    def test_single_sentinel_limit_down_reduces_15pct(self):
        l1 = _make_l1(ceiling=60)
        l2 = _make_l2(util_min=80, util_max=100)
        l3 = ChinaSentinelState()
        l3.limit_down_panic = _triggered_entry("limit_down_panic")
        result = compute_china_envelope(l1, l2, l3)
        assert result.target_max == pytest.approx(60.0 - 15.0)
        assert not result.is_emergency

    def test_single_sentinel_volume_spike_reduces_5pct(self):
        l1 = _make_l1(ceiling=60)
        l2 = _make_l2(util_min=80, util_max=100)
        l3 = ChinaSentinelState()
        l3.volume_spike = _triggered_entry("volume_spike")
        result = compute_china_envelope(l1, l2, l3)
        assert result.target_max == pytest.approx(60.0 - 5.0)

    def test_multi_sentinel_emergency_ceiling_times_50pct(self):
        l1 = _make_l1(ceiling=60)
        l2 = _make_l2(util_min=80, util_max=100)
        l3 = ChinaSentinelState()
        l3.limit_down_panic = _triggered_entry("limit_down_panic")
        l3.southbound_surge = _triggered_entry("southbound_surge")
        result = compute_china_envelope(l1, l2, l3)
        assert result.target_max == pytest.approx(60.0 * 0.5)
        assert result.is_emergency

    def test_spec_example_normal_l1_neutral_l2_value_bull(self):
        # Spec example: L1=NEUTRAL(60%) × L2=VALUE_BULL(80-100%) → 48%–60%
        l1 = _make_l1(ceiling=60)
        l2 = _make_l2(util_min=80, util_max=100)
        l3 = ChinaSentinelState()
        result = compute_china_envelope(l1, l2, l3)
        assert result.target_min == pytest.approx(48.0)
        assert result.target_max == pytest.approx(60.0)


# ──────────────────────────────────────────────────────────────────────────────
# State Persistence Tests
# ──────────────────────────────────────────────────────────────────────────────

class TestSentinelStatePersistence:
    def test_save_and_load_roundtrip(self, tmp_path):
        from unittest.mock import patch
        state = ChinaSentinelState()
        state.limit_up_heat = _triggered_entry("limit_up_heat", "涨停过热", days=1)
        state.volume_spike = SentinelEntry(
            sentinel_id="volume_spike", name="量价异常",
            status=SentinelStatus.COOLING, hold_down_days=2,
        )
        sentinel_file = tmp_path / "test_sentinel_state.json"
        with patch("src.analysis.china_regime._SENTINEL_STATE_FILE", sentinel_file):
            save_china_sentinel_state(state)
            loaded = load_china_sentinel_state()

        assert loaded.limit_up_heat.status == SentinelStatus.TRIGGERED
        assert loaded.limit_up_heat.hold_down_days == 1
        assert loaded.volume_spike.status == SentinelStatus.COOLING
        assert loaded.volume_spike.hold_down_days == 2

    def test_corrupt_file_returns_clear(self, tmp_path):
        from unittest.mock import patch
        sentinel_file = tmp_path / "corrupt_state.json"
        sentinel_file.write_text("{ invalid json }")
        with patch("src.analysis.china_regime._SENTINEL_STATE_FILE", sentinel_file):
            state = load_china_sentinel_state()
        assert not state.any_triggered()

    def test_missing_file_returns_clear(self, tmp_path):
        from unittest.mock import patch
        sentinel_file = tmp_path / "nonexistent.json"
        with patch("src.analysis.china_regime._SENTINEL_STATE_FILE", sentinel_file):
            state = load_china_sentinel_state()
        assert not state.any_triggered()


# ──────────────────────────────────────────────────────────────────────────────
# Utility Function Tests
# ──────────────────────────────────────────────────────────────────────────────

class TestMarginRatioDistance:
    def test_very_far(self):
        result = compute_margin_ratio_distance(1.0, {"peak": 5.0})
        assert result["peak"]["description"] == "很远"

    def test_close(self):
        result = compute_margin_ratio_distance(4.0, {"peak": 5.0})
        assert result["peak"]["description"] == "接近"

    def test_invalid_reference_skipped(self):
        result = compute_margin_ratio_distance(1.0, {"bad": 0.0})
        assert "bad" not in result


class TestEquityBondDescription:
    def test_undervalued_description(self):
        assert "低估" in compute_equity_bond_spread_description(4.0)

    def test_overvalued_description(self):
        assert "高估" in compute_equity_bond_spread_description(0.5)

    def test_neutral_description(self):
        assert compute_equity_bond_spread_description(2.0) == "中性"


class TestDepositRatioDescription:
    def test_high_ratio(self):
        assert "充裕" in get_deposit_ratio_description(6.0)

    def test_medium_ratio(self):
        assert "适中" in get_deposit_ratio_description(4.0)

    def test_low_ratio(self):
        assert "有限" in get_deposit_ratio_description(2.0)
