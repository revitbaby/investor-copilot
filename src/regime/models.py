"""Shared data models for the regime scoring engine."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class L1Regime(str, Enum):
    EXPANSIONARY = "EXPANSIONARY"
    NEUTRAL = "NEUTRAL"
    CONTRACTING = "CONTRACTING"
    SEVERE_CONTRACTION = "SEVERE_CONTRACTION"


class L2Regime(str, Enum):
    STRONG_RISK_ON = "STRONG_RISK_ON"
    RISK_ON = "RISK_ON"
    NEUTRAL = "NEUTRAL"
    RISK_OFF = "RISK_OFF"
    STRONG_RISK_OFF = "STRONG_RISK_OFF"


class SentinelStatus(str, Enum):
    CLEAR = "CLEAR"
    TRIGGERED = "TRIGGERED"
    COOLING = "COOLING"


class EnvelopeMode(str, Enum):
    NORMAL = "NORMAL"
    EMERGENCY = "EMERGENCY"


class PositionAction(str, Enum):
    CLOSE = "CLOSE"
    TRIM = "TRIM"
    HOLD = "HOLD"
    ADD = "ADD"


@dataclass
class IndicatorResult:
    name: str
    raw_value: Any
    display_value: str
    threshold_hit: str
    score: int  # +1, 0, -1
    weight: float = 1.0

    @property
    def weighted_score(self) -> float:
        return self.score * self.weight


@dataclass
class Layer1Result:
    indicators: list[IndicatorResult]
    composite: int
    regime: L1Regime
    ceiling_pct: int
    color: str

    def to_dict(self) -> dict:
        return {
            "indicators": [
                {"name": i.name, "raw_value": i.raw_value, "display_value": i.display_value,
                 "threshold_hit": i.threshold_hit, "score": i.score}
                for i in self.indicators
            ],
            "composite": self.composite,
            "regime": self.regime.value,
            "ceiling_pct": self.ceiling_pct,
            "color": self.color,
        }


@dataclass
class Layer2Result:
    indicators: list[IndicatorResult]
    weighted_composite: float
    regime: L2Regime
    utilization_min: int
    utilization_max: int
    color: str

    def to_dict(self) -> dict:
        return {
            "indicators": [
                {"name": i.name, "raw_value": i.raw_value, "display_value": i.display_value,
                 "threshold_hit": i.threshold_hit, "score": i.score, "weight": i.weight,
                 "weighted_score": i.weighted_score}
                for i in self.indicators
            ],
            "weighted_composite": self.weighted_composite,
            "regime": self.regime.value,
            "utilization_min": self.utilization_min,
            "utilization_max": self.utilization_max,
            "color": self.color,
        }


@dataclass
class SentinelState:
    sentinel_id: str
    name: str
    status: SentinelStatus = SentinelStatus.CLEAR
    forced_ceiling_pct: int | None = None
    trigger_timestamp: str | None = None
    cooling_days: int = 0
    current_value: Any = None
    display_value: str = ""

    def to_dict(self) -> dict:
        return {
            "sentinel_id": self.sentinel_id,
            "name": self.name,
            "status": self.status.value,
            "forced_ceiling_pct": self.forced_ceiling_pct,
            "trigger_timestamp": self.trigger_timestamp,
            "cooling_days": self.cooling_days,
            "current_value": self.current_value,
            "display_value": self.display_value,
        }


@dataclass
class Layer3Result:
    sentinels: list[SentinelState]
    any_triggered: bool
    override_ceiling_pct: int | None = None
    freeze_active: bool = False

    def to_dict(self) -> dict:
        return {
            "sentinels": [s.to_dict() for s in self.sentinels],
            "any_triggered": self.any_triggered,
            "override_ceiling_pct": self.override_ceiling_pct,
            "freeze_active": self.freeze_active,
        }


@dataclass
class EnvelopeResult:
    target_min: float
    target_max: float
    mode: EnvelopeMode
    derivation: str
    l1_ceiling: int = 0
    l2_util_min: int = 0
    l2_util_max: int = 0

    def to_dict(self) -> dict:
        return {
            "target_min": round(self.target_min, 1),
            "target_max": round(self.target_max, 1),
            "mode": self.mode.value,
            "derivation": self.derivation,
        }


@dataclass
class RegimeResult:
    layer1: Layer1Result
    layer2: Layer2Result
    layer3: Layer3Result
    envelope: EnvelopeResult

    def to_dict(self) -> dict:
        return {
            "layer1": self.layer1.to_dict(),
            "layer2": self.layer2.to_dict(),
            "layer3": self.layer3.to_dict(),
            "envelope": self.envelope.to_dict(),
        }
