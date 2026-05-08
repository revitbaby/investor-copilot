"""Tests for regime config loading and merging."""

import os
import tempfile
from pathlib import Path

import pytest
import yaml

from src.regime.config import load_config, _deep_merge, RegimeConfig


def test_deep_merge_basic():
    base = {"a": 1, "b": {"c": 2, "d": 3}}
    override = {"b": {"c": 99}, "e": 5}
    result = _deep_merge(base, override)
    assert result == {"a": 1, "b": {"c": 99, "d": 3}, "e": 5}


def test_load_default_config():
    cfg = load_config()
    assert isinstance(cfg, RegimeConfig)
    assert cfg.layer1.ceiling_map.expansionary == 100
    assert cfg.layer1.ceiling_map.severe == 40
    assert cfg.layer1.net_liquidity.lookback_weeks == 3
    assert cfg.layer1.rrp.high_threshold_billions == 200.0
    assert cfg.layer3.vix_spike.forced_ceiling_pct == 20
    assert cfg.layer3.move_spike.forced_ceiling_pct is None
    assert len(cfg.breadth.sector_weights) == 11
    assert abs(sum(cfg.breadth.sector_weights.values()) - 1.0) < 0.01


def test_load_with_override():
    override_content = {"layer1": {"ceiling_map": {"expansionary": 95}}}
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        yaml.dump(override_content, f)
        override_path = f.name

    try:
        cfg = load_config(overrides_path=override_path)
        assert cfg.layer1.ceiling_map.expansionary == 95
        assert cfg.layer1.ceiling_map.severe == 40  # not overridden
    finally:
        os.unlink(override_path)


def test_load_missing_defaults_raises():
    with pytest.raises(FileNotFoundError):
        load_config(defaults_path="/nonexistent/path.yaml")


def test_layer2_indicators_have_weights():
    cfg = load_config()
    assert "spx_vs_50dma" in cfg.layer2.indicators
    assert cfg.layer2.indicators["spx_vs_50dma"].weight == 1.5
    assert cfg.layer2.indicators["dxy_trend"].weight == 0.5


def test_position_advisor_matrix():
    cfg = load_config()
    matrix = cfg.position_advisor.conviction_regime_matrix
    assert matrix["S"]["strong_risk_on"] == 25
    assert matrix["C"]["risk_off"] == 0
    assert matrix["B"]["strong_risk_off"] == 0
