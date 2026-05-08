"""Load and validate regime scoring configuration from YAML."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


_DEFAULT_CONFIG_PATH = Path(__file__).resolve().parents[2] / "config" / "regime_defaults.yaml"
_OVERRIDE_CONFIG_PATH = Path(__file__).resolve().parents[2] / "config" / "regime_overrides.yaml"


def _deep_merge(base: dict, override: dict) -> dict:
    """Recursively merge *override* into *base* (override wins)."""
    merged = base.copy()
    for key, val in override.items():
        if key in merged and isinstance(merged[key], dict) and isinstance(val, dict):
            merged[key] = _deep_merge(merged[key], val)
        else:
            merged[key] = val
    return merged


# ---------------------------------------------------------------------------
# Typed sub-configs
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class NetLiquidityConfig:
    lookback_weeks: int = 3
    rising_threshold_pct_per_week: float = 0.5
    falling_threshold_pct_per_week: float = -0.5


@dataclass(frozen=True)
class TGAConfig:
    lookback_days: int = 21
    rising_threshold_pct: float = 5.0
    falling_threshold_pct: float = -5.0


@dataclass(frozen=True)
class RRPConfig:
    high_threshold_billions: float = 200.0
    low_threshold_billions: float = 50.0


@dataclass(frozen=True)
class PolicyRateConfig:
    lookback_days: int = 63
    cut_threshold_bp: float = 10.0
    hike_threshold_bp: float = 10.0


@dataclass(frozen=True)
class CeilingMap:
    expansionary: int = 100
    neutral: int = 80
    contracting: int = 60
    severe: int = 40


@dataclass(frozen=True)
class Layer1Config:
    net_liquidity: NetLiquidityConfig = field(default_factory=NetLiquidityConfig)
    tga: TGAConfig = field(default_factory=TGAConfig)
    rrp: RRPConfig = field(default_factory=RRPConfig)
    policy_rate: PolicyRateConfig = field(default_factory=PolicyRateConfig)
    ceiling_map: CeilingMap = field(default_factory=CeilingMap)


@dataclass(frozen=True)
class L2IndicatorConfig:
    weight: float = 1.0
    # Remaining fields are indicator-specific; stored as raw dict
    params: dict = field(default_factory=dict)


@dataclass(frozen=True)
class UtilizationRange:
    min: int = 0
    max: int = 100


@dataclass(frozen=True)
class Layer2Config:
    indicators: dict[str, L2IndicatorConfig] = field(default_factory=dict)
    utilization_map: dict[str, UtilizationRange] = field(default_factory=dict)


@dataclass(frozen=True)
class SentinelConfig:
    trigger_level: float | None = None
    trigger_return_pct: float | None = None
    trigger_vix: float | None = None
    forced_ceiling_pct: int | None = None
    reset_below: float | None = None
    reset_vix_below: float | None = None
    reset_breadth_above: float | None = None
    reset_consecutive_days: int = 3
    reset_positive_days: int | None = None
    params: dict = field(default_factory=dict)


@dataclass(frozen=True)
class Layer3Config:
    vix_spike: SentinelConfig = field(default_factory=SentinelConfig)
    credit_break: SentinelConfig = field(default_factory=SentinelConfig)
    move_spike: SentinelConfig = field(default_factory=SentinelConfig)
    trend_break: SentinelConfig = field(default_factory=SentinelConfig)


@dataclass(frozen=True)
class PositionAdvisorConfig:
    conviction_regime_matrix: dict[str, dict[str, int]] = field(default_factory=dict)
    options_notional_limit_contracting_pct: int = 10
    options_notional_limit_normal_pct: int = 25


@dataclass(frozen=True)
class BreadthConfig:
    sector_weights: dict[str, float] = field(default_factory=dict)
    fallback_value: float = 50.0


@dataclass(frozen=True)
class RegimeConfig:
    layer1: Layer1Config = field(default_factory=Layer1Config)
    layer2: Layer2Config = field(default_factory=Layer2Config)
    layer3: Layer3Config = field(default_factory=Layer3Config)
    position_advisor: PositionAdvisorConfig = field(default_factory=PositionAdvisorConfig)
    breadth: BreadthConfig = field(default_factory=BreadthConfig)


# ---------------------------------------------------------------------------
# Builder
# ---------------------------------------------------------------------------

def _build_layer1(raw: dict) -> Layer1Config:
    return Layer1Config(
        net_liquidity=NetLiquidityConfig(**raw.get("net_liquidity", {})),
        tga=TGAConfig(**raw.get("tga", {})),
        rrp=RRPConfig(**raw.get("rrp", {})),
        policy_rate=PolicyRateConfig(**raw.get("policy_rate", {})),
        ceiling_map=CeilingMap(**raw.get("ceiling_map", {})),
    )


def _build_layer2(raw: dict) -> Layer2Config:
    indicators = {}
    for name, vals in raw.get("indicators", {}).items():
        w = vals.pop("weight", 1.0) if isinstance(vals, dict) else 1.0
        indicators[name] = L2IndicatorConfig(weight=w, params=vals if isinstance(vals, dict) else {})

    util_map = {}
    for name, vals in raw.get("utilization_map", {}).items():
        util_map[name] = UtilizationRange(**vals)

    return Layer2Config(indicators=indicators, utilization_map=util_map)


def _build_sentinel(raw: dict) -> SentinelConfig:
    known = {f.name for f in SentinelConfig.__dataclass_fields__.values()}
    params = {k: v for k, v in raw.items() if k not in known}
    direct = {k: v for k, v in raw.items() if k in known}
    return SentinelConfig(**direct, params=params)


def _build_layer3(raw: dict) -> Layer3Config:
    return Layer3Config(
        vix_spike=_build_sentinel(raw.get("vix_spike", {})),
        credit_break=_build_sentinel(raw.get("credit_break", {})),
        move_spike=_build_sentinel(raw.get("move_spike", {})),
        trend_break=_build_sentinel(raw.get("trend_break", {})),
    )


def _build_position_advisor(raw: dict) -> PositionAdvisorConfig:
    return PositionAdvisorConfig(
        conviction_regime_matrix=raw.get("conviction_regime_matrix", {}),
        options_notional_limit_contracting_pct=raw.get("options_notional_limit_contracting_pct", 10),
        options_notional_limit_normal_pct=raw.get("options_notional_limit_normal_pct", 25),
    )


def _build_breadth(raw: dict) -> BreadthConfig:
    return BreadthConfig(
        sector_weights=raw.get("sector_weights", {}),
        fallback_value=raw.get("fallback_value", 50.0),
    )


def load_config(
    defaults_path: str | Path | None = None,
    overrides_path: str | Path | None = None,
) -> RegimeConfig:
    """Load configuration from YAML, merging overrides on top of defaults.

    Raises ``FileNotFoundError`` if the defaults file is missing.
    """
    defaults_path = Path(defaults_path) if defaults_path else _DEFAULT_CONFIG_PATH
    overrides_path = Path(overrides_path) if overrides_path else _OVERRIDE_CONFIG_PATH

    if not defaults_path.exists():
        raise FileNotFoundError(f"Default config not found: {defaults_path}")

    with open(defaults_path) as f:
        raw: dict[str, Any] = yaml.safe_load(f) or {}

    if overrides_path.exists():
        with open(overrides_path) as f:
            overrides: dict[str, Any] = yaml.safe_load(f) or {}
        raw = _deep_merge(raw, overrides)

    return RegimeConfig(
        layer1=_build_layer1(raw.get("layer1", {})),
        layer2=_build_layer2(raw.get("layer2", {})),
        layer3=_build_layer3(raw.get("layer3", {})),
        position_advisor=_build_position_advisor(raw.get("position_advisor", {})),
        breadth=_build_breadth(raw.get("breadth", {})),
    )
