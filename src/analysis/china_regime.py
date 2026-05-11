"""
China A-share three-layer regime scoring engine.

Layer 1 (Liquidity Floor): DR007 deviation · M1 YoY · M1-M2 spread · TSF growth
  → Position Ceiling 80% / 60% / 40%

Layer 2 (Market Regime): equity-bond spread · margin ratio · QVIX · northbound flow
  → Four named states: VALUE_BULL · SENTIMENT_BULL · PANIC_BOTTOM · OVERVALUATION_RISK · NEUTRAL
  → Utilization Rate range

Layer 3 (Instant Sentinels): limit-up/down counts · ZT/DT ratio · southbound surge · volume spike
  → 3-trading-day hold-down · persisted to data_cache/china_sentinel_state.json

Envelope: Layer1 Ceiling × Layer2 Utilization, modified by Layer3 overrides.
"""

from __future__ import annotations

import json
import logging
from copy import copy
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Literal

import pandas as pd

logger = logging.getLogger(__name__)

_SENTINEL_STATE_FILE = Path("data_cache/china_sentinel_state.json")
_REGIME_HISTORY_FILE = Path("data_cache/china_regime_history.csv")

_HOLD_DOWN_DAYS = 3

# Historical bull-market anchor points for chart annotations.
# Values sourced from reference app screenshots (2026-05 snapshot).
# Format: label → (date_str, indicator_value)
MARGIN_RATIO_ANCHORS: dict[str, tuple[str, float]] = {
    "2015年牛市": ("2015-06-30", 3.33),
    "2021年牛市": ("2021-03-09", 1.98),
}
EQUITY_BOND_ANCHORS: dict[str, tuple[str, float]] = {
    "2008年牛市": ("2008-01-14", -2.22),
    "2015年牛市": ("2015-06-15",  1.81),
    "2021年牛市": ("2021-02-18",  2.63),
}
DEPOSIT_RATIO_ANCHORS: dict[str, tuple[str, float]] = {
    "2015年牛市": ("2015-06-15", 2.307),
    "2021年牛市": ("2021-01-21", 2.538),
}


# ── Enums ─────────────────────────────────────────────────────────────────────

class ChinaL1Regime(str, Enum):
    EXPANSIONARY = "EXPANSIONARY"
    NEUTRAL = "NEUTRAL"
    CONTRACTING = "CONTRACTING"


class ChinaL2Regime(str, Enum):
    VALUE_BULL = "VALUE_BULL"
    SENTIMENT_BULL = "SENTIMENT_BULL"
    PANIC_BOTTOM = "PANIC_BOTTOM"
    OVERVALUATION_RISK = "OVERVALUATION_RISK"
    NEUTRAL = "NEUTRAL"


class SentinelStatus(str, Enum):
    CLEAR = "CLEAR"
    TRIGGERED = "TRIGGERED"
    COOLING = "COOLING"


# ── Data classes ──────────────────────────────────────────────────────────────

@dataclass
class ChinaL1Signals:
    dr007: float | None = None
    omo_rate: float | None = None
    m1_yoy: float | None = None
    m1_yoy_prev: float | None = None
    m1_m2_spread: float | None = None
    m1_m2_spread_prev: float | None = None
    tsf_yoy: float | None = None
    tsf_yoy_prev: float | None = None


@dataclass
class ChinaL1Result:
    dr007_score: int
    m1_yoy_score: int
    m1_m2_spread_score: int
    tsf_score: int
    composite: int
    regime: ChinaL1Regime
    ceiling_pct: int

    def to_dict(self) -> dict:
        return {
            "dr007_score": self.dr007_score,
            "m1_yoy_score": self.m1_yoy_score,
            "m1_m2_spread_score": self.m1_m2_spread_score,
            "tsf_score": self.tsf_score,
            "composite": self.composite,
            "regime": self.regime.value,
            "ceiling_pct": self.ceiling_pct,
        }


@dataclass
class ChinaL2Result:
    equity_bond_signal: str
    margin_signal: str
    qvix_signal: str | None
    northbound_adjustment: float
    regime: ChinaL2Regime
    utilization_min: int
    utilization_max: int

    def to_dict(self) -> dict:
        return {
            "equity_bond_signal": self.equity_bond_signal,
            "margin_signal": self.margin_signal,
            "qvix_signal": self.qvix_signal,
            "northbound_adjustment": self.northbound_adjustment,
            "regime": self.regime.value,
            "utilization_min": self.utilization_min,
            "utilization_max": self.utilization_max,
        }


@dataclass
class SentinelEntry:
    sentinel_id: str
    name: str
    status: SentinelStatus = SentinelStatus.CLEAR
    trigger_timestamp: str | None = None
    hold_down_days: int = 0

    def to_dict(self) -> dict:
        return {
            "sentinel_id": self.sentinel_id,
            "name": self.name,
            "status": self.status.value,
            "trigger_timestamp": self.trigger_timestamp,
            "hold_down_days": self.hold_down_days,
        }

    @classmethod
    def from_dict(cls, d: dict) -> SentinelEntry:
        try:
            status = SentinelStatus(d.get("status", "CLEAR"))
        except ValueError:
            status = SentinelStatus.CLEAR
        return cls(
            sentinel_id=d.get("sentinel_id", ""),
            name=d.get("name", ""),
            status=status,
            trigger_timestamp=d.get("trigger_timestamp"),
            hold_down_days=int(d.get("hold_down_days", 0)),
        )


@dataclass
class ChinaSentinelState:
    limit_up_heat: SentinelEntry = field(
        default_factory=lambda: SentinelEntry("limit_up_heat", "涨停过热"))
    limit_down_panic: SentinelEntry = field(
        default_factory=lambda: SentinelEntry("limit_down_panic", "跌停恐慌"))
    zt_dt_extreme: SentinelEntry = field(
        default_factory=lambda: SentinelEntry("zt_dt_extreme", "ZT/DT极端"))
    southbound_surge: SentinelEntry = field(
        default_factory=lambda: SentinelEntry("southbound_surge", "南向异动"))
    volume_spike: SentinelEntry = field(
        default_factory=lambda: SentinelEntry("volume_spike", "量价异常"))

    def all_entries(self) -> list[tuple[str, SentinelEntry]]:
        return [
            ("limit_up_heat", self.limit_up_heat),
            ("limit_down_panic", self.limit_down_panic),
            ("zt_dt_extreme", self.zt_dt_extreme),
            ("southbound_surge", self.southbound_surge),
            ("volume_spike", self.volume_spike),
        ]

    def any_triggered(self) -> bool:
        return any(e.status != SentinelStatus.CLEAR for _, e in self.all_entries())

    def triggered_count(self) -> int:
        return sum(1 for _, e in self.all_entries() if e.status != SentinelStatus.CLEAR)

    def triggered_ids(self) -> list[str]:
        return [sid for sid, e in self.all_entries() if e.status != SentinelStatus.CLEAR]

    def to_dict(self) -> dict:
        return {sid: entry.to_dict() for sid, entry in self.all_entries()}


@dataclass
class ChinaEnvelopeResult:
    target_min: float
    target_max: float
    is_emergency: bool
    derivation: str
    l1_ceiling: int
    l2_util_min: int
    l2_util_max: int

    def to_dict(self) -> dict:
        return {
            "target_min": round(self.target_min, 1),
            "target_max": round(self.target_max, 1),
            "is_emergency": self.is_emergency,
            "derivation": self.derivation,
            "l1_ceiling": self.l1_ceiling,
        }


@dataclass
class ChinaRegimeResult:
    layer1: ChinaL1Result
    layer2: ChinaL2Result
    layer3: ChinaSentinelState
    envelope: ChinaEnvelopeResult
    data_date: date | None = None

    def to_dict(self) -> dict:
        return {
            "layer1": self.layer1.to_dict(),
            "layer2": self.layer2.to_dict(),
            "layer3": self.layer3.to_dict(),
            "envelope": self.envelope.to_dict(),
            "data_date": str(self.data_date) if self.data_date else None,
        }


@dataclass
class ChinaInputData:
    """All input data needed to run compute_china_regime."""
    # Layer 1
    dr007: float | None = None
    omo_rate: float | None = None
    m1_yoy: float | None = None
    m1_yoy_prev: float | None = None
    m1_m2_spread: float | None = None
    m1_m2_spread_prev: float | None = None
    tsf_yoy: float | None = None
    tsf_yoy_prev: float | None = None
    # Layer 2
    csi300_pe_ttm: float | None = None
    cgb10y_yield: float | None = None
    equity_bond_spread: float | None = None
    margin_ratio_pct: float | None = None
    qvix: float | None = None
    northbound_5d_cumulative: float | None = None
    # Layer 3
    limit_up_count: int | None = None
    limit_down_count: int | None = None
    zt_count: int | None = None
    dt_count: int | None = None
    southbound_net_buy: float | None = None
    southbound_sigma_dev: float | None = None
    total_amount: float | None = None
    total_amount_ma20: float | None = None
    # Metadata
    data_date: date | None = None
    csi300_close: float | None = None


# ── Layer 1: Liquidity Floor Scoring ─────────────────────────────────────────

def score_dr007_signal(dr007: float | None, omo_rate: float | None) -> int:
    """DR007 below OMO → +1 (loose), above OMO → -1 (tight), equal/missing → 0."""
    if dr007 is None or omo_rate is None:
        return 0
    if dr007 < omo_rate:
        return 1
    if dr007 > omo_rate:
        return -1
    return 0


def score_m1_yoy_signal(m1_yoy: float | None, m1_yoy_prev: float | None = None) -> int:
    """M1 YoY positive and accelerating → +1; persistent/worsening negative → -1; else 0."""
    if m1_yoy is None:
        return 0
    if m1_yoy > 0 and (m1_yoy_prev is None or m1_yoy > m1_yoy_prev):
        return 1
    # Only -1 when negative AND worsening (not improving toward zero)
    if m1_yoy < 0 and m1_yoy_prev is not None and m1_yoy_prev < 0 and m1_yoy <= m1_yoy_prev:
        return -1
    return 0


def score_m1_m2_spread_signal(spread: float | None, spread_prev: float | None = None) -> int:
    """M1-M2 spread turning positive or narrowing → +1; persistent negative and widening → -1."""
    if spread is None:
        return 0
    if spread >= 0:
        return 1
    if spread < 0 and spread_prev is not None and spread < spread_prev:
        return -1
    return 0


def score_tsf_signal(tsf_yoy: float | None, tsf_yoy_prev: float | None = None) -> int:
    """TSF YoY accelerating → +1; decelerating → -1; missing → 0."""
    if tsf_yoy is None:
        return 0
    if tsf_yoy_prev is not None:
        if tsf_yoy > tsf_yoy_prev:
            return 1
        if tsf_yoy < tsf_yoy_prev:
            return -1
    return 0


def compute_china_layer1(signals: ChinaL1Signals) -> ChinaL1Result:
    """Compute Layer 1 composite and derive Position Ceiling."""
    dr007_score = score_dr007_signal(signals.dr007, signals.omo_rate)
    m1_yoy_score = score_m1_yoy_signal(signals.m1_yoy, signals.m1_yoy_prev)
    m1_m2_score = score_m1_m2_spread_signal(signals.m1_m2_spread, signals.m1_m2_spread_prev)
    tsf_score = score_tsf_signal(signals.tsf_yoy, signals.tsf_yoy_prev)

    composite = dr007_score + m1_yoy_score + m1_m2_score + tsf_score

    if composite >= 3:
        regime = ChinaL1Regime.EXPANSIONARY
        ceiling_pct = 80
    elif composite <= -2:
        regime = ChinaL1Regime.CONTRACTING
        ceiling_pct = 40
    else:
        regime = ChinaL1Regime.NEUTRAL
        ceiling_pct = 60

    return ChinaL1Result(
        dr007_score=dr007_score,
        m1_yoy_score=m1_yoy_score,
        m1_m2_spread_score=m1_m2_score,
        tsf_score=tsf_score,
        composite=composite,
        regime=regime,
        ceiling_pct=ceiling_pct,
    )


# ── Layer 2: Market Regime Classification ────────────────────────────────────

def classify_equity_bond_signal(
    spread_pct: float,
) -> Literal["UNDERVALUED", "NEUTRAL", "OVERVALUED"]:
    """Classify equity-bond yield spread. >3% → UNDERVALUED; <1% → OVERVALUED."""
    if spread_pct > 3.0:
        return "UNDERVALUED"
    if spread_pct < 1.0:
        return "OVERVALUED"
    return "NEUTRAL"


def classify_margin_signal(
    ratio_pct: float,
) -> Literal["OVERHEATED", "NORMAL", "COLD"]:
    """Classify margin balance / market cap ratio. >2.5% → OVERHEATED; <1.5% → COLD."""
    if ratio_pct > 2.5:
        return "OVERHEATED"
    if ratio_pct < 1.5:
        return "COLD"
    return "NORMAL"


def classify_qvix_signal(
    qvix: float | None,
) -> Literal["HIGH", "NORMAL", "LOW"] | None:
    """Classify QVIX. >30 → HIGH; <15 → LOW; None → None (graceful degradation)."""
    if qvix is None:
        return None
    if qvix > 30:
        return "HIGH"
    if qvix < 15:
        return "LOW"
    return "NORMAL"


def compute_northbound_utilization_adjustment(
    northbound_5d_cumulative: float | None,
) -> float:
    """
    Northbound 5-day cumulative net flow → utilization rate adjustment.
    >20 亿 → +0.05; <-20 亿 → -0.05; else 0.
    """
    if northbound_5d_cumulative is None:
        return 0.0
    if northbound_5d_cumulative > 20.0:
        return 0.05
    if northbound_5d_cumulative < -20.0:
        return -0.05
    return 0.0


def classify_china_regime(
    equity_bond_signal: str,
    margin_signal: str,
    qvix_signal: str | None,
    northbound_adjustment: float,
) -> ChinaL2Result:
    """
    Classify A-share market into one of five named regime states.

    Priority order:
      1. PANIC_BOTTOM: undervalued + high volatility (left-side opportunity)
      2. VALUE_BULL: undervalued + normal/cold leverage + QVIX not high
      3. OVERVALUATION_RISK: overvalued + overheated leverage
      4. SENTIMENT_BULL: not-overvalued + overheated leverage + QVIX not high
      5. NEUTRAL: default
    """
    if equity_bond_signal == "UNDERVALUED" and qvix_signal == "HIGH":
        regime = ChinaL2Regime.PANIC_BOTTOM
        util_min, util_max = 40, 60

    elif (equity_bond_signal == "UNDERVALUED"
          and margin_signal in ("NORMAL", "COLD")
          and qvix_signal != "HIGH"):
        regime = ChinaL2Regime.VALUE_BULL
        util_min, util_max = 80, 100

    elif (equity_bond_signal == "OVERVALUED"
          and margin_signal == "OVERHEATED"):
        regime = ChinaL2Regime.OVERVALUATION_RISK
        util_min, util_max = 20, 40

    elif (equity_bond_signal in ("UNDERVALUED", "NEUTRAL")
          and margin_signal == "OVERHEATED"
          and qvix_signal != "HIGH"):
        regime = ChinaL2Regime.SENTIMENT_BULL
        util_min, util_max = 60, 80

    else:
        regime = ChinaL2Regime.NEUTRAL
        util_min, util_max = 50, 70

    adj = int(northbound_adjustment * 100)
    util_min = max(0, min(100, util_min + adj))
    util_max = max(0, min(100, util_max + adj))

    return ChinaL2Result(
        equity_bond_signal=equity_bond_signal,
        margin_signal=margin_signal,
        qvix_signal=qvix_signal,
        northbound_adjustment=northbound_adjustment,
        regime=regime,
        utilization_min=util_min,
        utilization_max=util_max,
    )


# ── Layer 3: Instant Sentinels ────────────────────────────────────────────────

def _advance_sentinel(entry: SentinelEntry, trigger_condition: bool) -> SentinelEntry:
    """
    Generic 3-state sentinel state machine.

    CLEAR  → trigger_condition=True  → TRIGGERED (reset hold_down to 0)
    TRIGGERED/COOLING → trigger_condition=True  → TRIGGERED (restart hold_down)
    TRIGGERED/COOLING → trigger_condition=False → increment hold_down_days
                        if hold_down_days >= 3 → CLEAR
                        else → COOLING
    """
    e = copy(entry)

    if e.status == SentinelStatus.CLEAR:
        if trigger_condition:
            e.status = SentinelStatus.TRIGGERED
            e.trigger_timestamp = datetime.now(timezone.utc).isoformat()
            e.hold_down_days = 0
    else:  # TRIGGERED or COOLING
        if trigger_condition:
            e.status = SentinelStatus.TRIGGERED
            e.hold_down_days = 0
        else:
            e.hold_down_days += 1
            if e.hold_down_days >= _HOLD_DOWN_DAYS:
                e.status = SentinelStatus.CLEAR
                e.trigger_timestamp = None
                e.hold_down_days = 0
            else:
                e.status = SentinelStatus.COOLING

    return e


def evaluate_limit_up_heat(count: int | None, state: SentinelEntry) -> SentinelEntry:
    """count > 200 → TRIGGERED; count < 5 (data anomaly) → keep current; 3-day hold-down."""
    if count is not None and count < 5:
        logger.warning("limit_up_heat: implausibly low count %d — treating as missing", count)
        count = None
    trigger = count is not None and count > 200
    return _advance_sentinel(state, trigger)


def evaluate_limit_down_panic(count: int | None, state: SentinelEntry) -> SentinelEntry:
    """count > 50 → TRIGGERED; count < 5 (data anomaly) → keep current; 3-day hold-down."""
    if count is not None and count < 5:
        logger.warning("limit_down_panic: implausibly low count %d — treating as missing", count)
        count = None
    trigger = count is not None and count > 50
    return _advance_sentinel(state, trigger)


def evaluate_zt_dt_ratio(
    zt: int | None, dt: int | None, state: SentinelEntry
) -> SentinelEntry:
    """ZT/DT ratio > 10 or < 0.2 → TRIGGERED; dt=0 or missing → no trigger."""
    if zt is None or dt is None or dt == 0:
        return _advance_sentinel(state, False)
    ratio = zt / dt
    return _advance_sentinel(state, ratio > 10 or ratio < 0.2)


def evaluate_southbound_surge(
    net_buy: float | None,
    sigma_dev: float | None,
    state: SentinelEntry,
) -> SentinelEntry:
    """|σ deviation| > 2 → TRIGGERED; missing sigma → no trigger."""
    if sigma_dev is None:
        return _advance_sentinel(state, False)
    return _advance_sentinel(state, abs(sigma_dev) > 2.0)


def evaluate_volume_spike(
    amount: float | None,
    ma20: float | None,
    state: SentinelEntry,
) -> SentinelEntry:
    """amount > ma20 × 1.5 → TRIGGERED; missing data → no trigger."""
    if amount is None or ma20 is None or ma20 <= 0:
        return _advance_sentinel(state, False)
    return _advance_sentinel(state, amount > ma20 * 1.5)


def evaluate_china_sentinels(
    limit_up_count: int | None,
    limit_down_count: int | None,
    zt_count: int | None,
    dt_count: int | None,
    southbound_net_buy: float | None,
    southbound_sigma_dev: float | None,
    total_amount: float | None,
    total_amount_ma20: float | None,
    current_state: ChinaSentinelState,
) -> ChinaSentinelState:
    """Evaluate all 5 A-share sentinels and return updated state."""
    return ChinaSentinelState(
        limit_up_heat=evaluate_limit_up_heat(limit_up_count, current_state.limit_up_heat),
        limit_down_panic=evaluate_limit_down_panic(limit_down_count, current_state.limit_down_panic),
        zt_dt_extreme=evaluate_zt_dt_ratio(zt_count, dt_count, current_state.zt_dt_extreme),
        southbound_surge=evaluate_southbound_surge(southbound_net_buy, southbound_sigma_dev, current_state.southbound_surge),
        volume_spike=evaluate_volume_spike(total_amount, total_amount_ma20, current_state.volume_spike),
    )


# ── State Persistence ─────────────────────────────────────────────────────────

def load_china_sentinel_state() -> ChinaSentinelState:
    """Load sentinel state from JSON; return all-CLEAR on missing or corrupted file."""
    try:
        if _SENTINEL_STATE_FILE.exists():
            with open(_SENTINEL_STATE_FILE) as f:
                data = json.load(f)
            if isinstance(data, dict):
                state = ChinaSentinelState()
                defaults = {sid: entry for sid, entry in state.all_entries()}
                for sid in ("limit_up_heat", "limit_down_panic", "zt_dt_extreme",
                            "southbound_surge", "volume_spike"):
                    if sid in data:
                        entry_data = dict(data[sid])
                        entry_data.setdefault("sentinel_id", sid)
                        entry_data.setdefault("name", defaults[sid].name)
                        setattr(state, sid, SentinelEntry.from_dict(entry_data))
                return state
    except Exception:
        logger.warning("China sentinel state file corrupted; resetting to CLEAR", exc_info=True)
    return ChinaSentinelState()


def save_china_sentinel_state(state: ChinaSentinelState) -> None:
    """Persist sentinel state to JSON."""
    _SENTINEL_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(_SENTINEL_STATE_FILE, "w") as f:
        json.dump(state.to_dict(), f, indent=2, ensure_ascii=False)


# ── Envelope Synthesis ────────────────────────────────────────────────────────

_SENTINEL_REDUCTIONS: dict[str, float] = {
    "limit_up_heat": 0.10,
    "limit_down_panic": 0.15,
    "zt_dt_extreme": 0.10,
    "southbound_surge": 0.10,
    "volume_spike": 0.05,
}


def compute_china_envelope(
    l1_result: ChinaL1Result,
    l2_result: ChinaL2Result,
    l3_state: ChinaSentinelState,
) -> ChinaEnvelopeResult:
    """
    Synthesize Target Position Envelope.

    Normal:  Ceiling × Utilization range
    1 sentinel: subtract sentinel-specific reduction (10–15%)
    ≥2 sentinels: force to Ceiling × 50% (emergency mode)
    """
    ceiling_frac = l1_result.ceiling_pct / 100.0
    base_min = ceiling_frac * l2_result.utilization_min
    base_max = ceiling_frac * l2_result.utilization_max

    triggered = [(sid, e) for sid, e in l3_state.all_entries()
                 if e.status != SentinelStatus.CLEAR]

    if len(triggered) >= 2:
        forced = ceiling_frac * 0.5 * 100.0
        return ChinaEnvelopeResult(
            target_min=0.0,
            target_max=round(forced, 1),
            is_emergency=True,
            derivation=(
                f"Emergency: {len(triggered)} sentinels triggered"
                f" → Ceiling({l1_result.ceiling_pct}%)×50%"
            ),
            l1_ceiling=l1_result.ceiling_pct,
            l2_util_min=l2_result.utilization_min,
            l2_util_max=l2_result.utilization_max,
        )

    if len(triggered) == 1:
        sid, _ = triggered[0]
        reduction = _SENTINEL_REDUCTIONS.get(sid, 0.10)
        reduction_pct = reduction * 100.0
        return ChinaEnvelopeResult(
            target_min=round(max(0.0, base_min - reduction_pct), 1),
            target_max=round(max(0.0, base_max - reduction_pct), 1),
            is_emergency=False,
            derivation=f"Single sentinel {sid}: -{int(reduction_pct)}%",
            l1_ceiling=l1_result.ceiling_pct,
            l2_util_min=l2_result.utilization_min,
            l2_util_max=l2_result.utilization_max,
        )

    return ChinaEnvelopeResult(
        target_min=round(base_min, 1),
        target_max=round(base_max, 1),
        is_emergency=False,
        derivation=(
            f"L1 {l1_result.regime.value}({l1_result.ceiling_pct}%)"
            f" × L2 {l2_result.regime.value}"
            f"({l2_result.utilization_min}%–{l2_result.utilization_max}%)"
        ),
        l1_ceiling=l1_result.ceiling_pct,
        l2_util_min=l2_result.utilization_min,
        l2_util_max=l2_result.utilization_max,
    )


# ── Main Orchestrator ─────────────────────────────────────────────────────────

def compute_china_regime(data: ChinaInputData) -> ChinaRegimeResult:
    """
    Run the full three-layer A-share regime pipeline.

    Loads and saves sentinel state automatically.
    Does NOT write the history snapshot; callers should call
    write_china_regime_snapshot() after receiving the result.
    """
    # Layer 1
    l1_signals = ChinaL1Signals(
        dr007=data.dr007,
        omo_rate=data.omo_rate,
        m1_yoy=data.m1_yoy,
        m1_yoy_prev=data.m1_yoy_prev,
        m1_m2_spread=data.m1_m2_spread,
        m1_m2_spread_prev=data.m1_m2_spread_prev,
        tsf_yoy=data.tsf_yoy,
        tsf_yoy_prev=data.tsf_yoy_prev,
    )
    l1_result = compute_china_layer1(l1_signals)

    # Layer 2
    if data.equity_bond_spread is not None:
        eq_bond_signal = classify_equity_bond_signal(data.equity_bond_spread)
    elif (data.csi300_pe_ttm is not None
          and data.cgb10y_yield is not None
          and data.csi300_pe_ttm > 0):
        spread = (1.0 / data.csi300_pe_ttm * 100.0) - data.cgb10y_yield
        eq_bond_signal = classify_equity_bond_signal(spread)
    else:
        logger.warning("compute_china_regime: no equity-bond spread data, defaulting to NEUTRAL")
        eq_bond_signal = "NEUTRAL"

    margin_signal = (classify_margin_signal(data.margin_ratio_pct)
                     if data.margin_ratio_pct is not None else "NORMAL")
    qvix_signal = classify_qvix_signal(data.qvix)
    if qvix_signal is None:
        logger.warning("QVIX unavailable; L2 using 2-signal fallback")
    nb_adj = compute_northbound_utilization_adjustment(data.northbound_5d_cumulative)
    l2_result = classify_china_regime(eq_bond_signal, margin_signal, qvix_signal, nb_adj)

    # Layer 3
    current_l3 = load_china_sentinel_state()
    l3_state = evaluate_china_sentinels(
        limit_up_count=data.limit_up_count,
        limit_down_count=data.limit_down_count,
        zt_count=data.zt_count,
        dt_count=data.dt_count,
        southbound_net_buy=data.southbound_net_buy,
        southbound_sigma_dev=data.southbound_sigma_dev,
        total_amount=data.total_amount,
        total_amount_ma20=data.total_amount_ma20,
        current_state=current_l3,
    )
    save_china_sentinel_state(l3_state)

    envelope = compute_china_envelope(l1_result, l2_result, l3_state)

    return ChinaRegimeResult(
        layer1=l1_result,
        layer2=l2_result,
        layer3=l3_state,
        envelope=envelope,
        data_date=data.data_date,
    )


# ── History Persistence ───────────────────────────────────────────────────────

def write_china_regime_snapshot(
    snapshot_date: date,
    l1_result: ChinaL1Result,
    l2_result: ChinaL2Result,
    l3_state: ChinaSentinelState,
    envelope: ChinaEnvelopeResult,
    csi300_close: float | None = None,
) -> None:
    """Append a daily regime snapshot to data_cache/china_regime_history.csv."""
    triggered_ids = "|".join(l3_state.triggered_ids())
    row = pd.DataFrame([{
        "date": str(snapshot_date),
        "L1_regime": l1_result.regime.value,
        "L2_regime": l2_result.regime.value,
        "L3_active_sentinels": triggered_ids,
        "target_min": round(envelope.target_min, 1),
        "target_max": round(envelope.target_max, 1),
        "csi300_close": csi300_close,
    }])

    if _REGIME_HISTORY_FILE.exists():
        try:
            history = pd.read_csv(_REGIME_HISTORY_FILE)
            history = history[history["date"] != str(snapshot_date)]
            history = pd.concat([history, row], ignore_index=True)
        except Exception:
            history = row
    else:
        history = row

    _REGIME_HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    history.to_csv(_REGIME_HISTORY_FILE, index=False)


# ── Utility Description Functions ─────────────────────────────────────────────

def compute_margin_ratio_distance(current: float, references: dict) -> dict:
    """
    Compute proximity to historical reference levels (e.g. 2015/2021 peaks).

    Returns dict keyed by reference name with pct_of_peak and description.
    Description: 很远 (<40%) / 较远 (40–60%) / 较近 (60–80%) / 接近 (≥80%).
    """
    results = {}
    for ref_name, ref_val in references.items():
        if ref_val <= 0:
            continue
        pct = (current / ref_val) * 100
        if pct < 40:
            desc = "很远"
        elif pct < 60:
            desc = "较远"
        elif pct < 80:
            desc = "较近"
        else:
            desc = "接近"
        results[ref_name] = {
            "current": current,
            "reference": ref_val,
            "pct_of_peak": round(pct, 1),
            "description": desc,
        }
    return results


def compute_equity_bond_spread_description(spread: float) -> str:
    """Return Chinese valuation interpretation text for the equity-bond spread."""
    if spread > 3.0:
        return "A 股低估，配置价值高"
    if spread < 1.0:
        return "A 股相对高估"
    return "中性"


def get_deposit_ratio_description(ratio: float) -> str:
    """Return Chinese potential fund-flow description for the deposit/market-cap ratio."""
    if ratio > 5.0:
        return "储蓄存款相对市值较高，潜在入市资金充裕"
    if ratio > 3.0:
        return "储蓄存款市值比适中，有一定入市资金储备"
    return "储蓄存款相对市值较低，潜在入市资金有限"
