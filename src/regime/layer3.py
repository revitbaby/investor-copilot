"""Layer 3: Instant Risk Sentinels.

Binary circuit breakers with asymmetric trigger/reset logic and state persistence.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from .config import Layer3Config
from .models import Layer3Result, SentinelState, SentinelStatus

logger = logging.getLogger(__name__)

_STATE_FILE = Path("data_cache/sentinel_state.json")


def _load_state(path: Path | None = None) -> dict[str, dict]:
    """Load sentinel state from disk. Returns empty dict on any error."""
    path = path or _STATE_FILE
    try:
        if path.exists():
            with open(path) as f:
                data = json.load(f)
            if isinstance(data, dict):
                return data
    except Exception:
        logger.warning("Sentinel state file corrupted, resetting to CLEAR", exc_info=True)
    return {}


def _save_state(sentinels: list[SentinelState], path: Path | None = None) -> None:
    path = path or _STATE_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {}
    for s in sentinels:
        data[s.sentinel_id] = {
            "status": s.status.value,
            "trigger_timestamp": s.trigger_timestamp,
            "cooling_days": s.cooling_days,
        }
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


def _restore_sentinel(sentinel_id: str, saved: dict[str, dict]) -> tuple[SentinelStatus, str | None, int]:
    """Restore a single sentinel's persistent state."""
    entry = saved.get(sentinel_id, {})
    try:
        status = SentinelStatus(entry.get("status", "CLEAR"))
    except ValueError:
        status = SentinelStatus.CLEAR
    return (
        status,
        entry.get("trigger_timestamp"),
        int(entry.get("cooling_days", 0)),
    )


# ---------------------------------------------------------------------------
# Individual sentinel evaluation
# ---------------------------------------------------------------------------

def _eval_vix_spike(df: pd.DataFrame, cfg: Layer3Config, saved: dict) -> SentinelState:
    sid = "vix_spike"
    sc = cfg.vix_spike
    status, trigger_ts, cooling_days = _restore_sentinel(sid, saved)
    forced = sc.forced_ceiling_pct

    try:
        vix = df["VIX"].dropna().iloc[-1]
    except Exception:
        vix = None

    if vix is None:
        return SentinelState(sid, "VIX Spike", status, forced if status != SentinelStatus.CLEAR else None,
                             trigger_ts, cooling_days, vix, "N/A")

    trigger_level = sc.trigger_level or 35.0
    reset_below = sc.reset_below or 25.0
    reset_days = sc.reset_consecutive_days

    if status == SentinelStatus.CLEAR:
        if vix > trigger_level:
            status = SentinelStatus.TRIGGERED
            trigger_ts = datetime.now(timezone.utc).isoformat()
            cooling_days = 0
    elif status in (SentinelStatus.TRIGGERED, SentinelStatus.COOLING):
        if vix <= trigger_level:
            status = SentinelStatus.COOLING
        else:
            status = SentinelStatus.TRIGGERED
            cooling_days = 0

        if vix < reset_below:
            cooling_days += 1
            if cooling_days >= reset_days:
                status = SentinelStatus.CLEAR
                trigger_ts = None
                cooling_days = 0
        else:
            cooling_days = 0

    active_ceiling = forced if status != SentinelStatus.CLEAR else None
    display = f"VIX {vix:.1f}" + (f" (cooling {cooling_days}/{reset_days}d)" if status == SentinelStatus.COOLING else "")
    return SentinelState(sid, "VIX Spike", status, active_ceiling, trigger_ts, cooling_days, vix, display)


def _eval_credit_break(df: pd.DataFrame, cfg: Layer3Config, saved: dict) -> SentinelState:
    sid = "credit_break"
    sc = cfg.credit_break
    status, trigger_ts, cooling_days = _restore_sentinel(sid, saved)
    forced = sc.forced_ceiling_pct

    try:
        jnk_ret, hyg_ret = None, None
        if "JNK" in df.columns:
            jnk = df["JNK"].dropna()
            if len(jnk) >= 2:
                jnk_ret = (jnk.iloc[-1] / jnk.iloc[-2] - 1) * 100
        if "HYG" in df.columns:
            hyg = df["HYG"].dropna()
            if len(hyg) >= 2:
                hyg_ret = (hyg.iloc[-1] / hyg.iloc[-2] - 1) * 100
    except Exception:
        jnk_ret, hyg_ret = None, None

    trigger_thr = sc.trigger_return_pct or -1.5
    reset_positive = sc.reset_positive_days or 5

    worst_ret = None
    if jnk_ret is not None and hyg_ret is not None:
        worst_ret = min(jnk_ret, hyg_ret)
    elif jnk_ret is not None:
        worst_ret = jnk_ret
    elif hyg_ret is not None:
        worst_ret = hyg_ret

    if worst_ret is None:
        return SentinelState(sid, "Credit Break", status, forced if status != SentinelStatus.CLEAR else None,
                             trigger_ts, cooling_days, None, "N/A")

    if status == SentinelStatus.CLEAR:
        if worst_ret < trigger_thr:
            status = SentinelStatus.TRIGGERED
            trigger_ts = datetime.now(timezone.utc).isoformat()
            cooling_days = 0
    elif status in (SentinelStatus.TRIGGERED, SentinelStatus.COOLING):
        if worst_ret < trigger_thr:
            status = SentinelStatus.TRIGGERED
            cooling_days = 0
        else:
            status = SentinelStatus.COOLING

        # Reset requires both JNK and HYG positive for consecutive days
        both_positive = True
        if jnk_ret is not None and jnk_ret <= 0:
            both_positive = False
        if hyg_ret is not None and hyg_ret <= 0:
            both_positive = False

        if both_positive:
            cooling_days += 1
            if cooling_days >= reset_positive:
                status = SentinelStatus.CLEAR
                trigger_ts = None
                cooling_days = 0
        else:
            cooling_days = 0

    active_ceiling = forced if status != SentinelStatus.CLEAR else None
    display = f"JNK {jnk_ret:+.2f}%" if jnk_ret is not None else "N/A"
    if status == SentinelStatus.COOLING:
        display += f" (cooling {cooling_days}/{reset_positive}d)"
    return SentinelState(sid, "Credit Break", status, active_ceiling, trigger_ts, cooling_days, worst_ret, display)


def _eval_move_spike(df: pd.DataFrame, cfg: Layer3Config, saved: dict) -> SentinelState:
    sid = "move_spike"
    sc = cfg.move_spike
    status, trigger_ts, cooling_days = _restore_sentinel(sid, saved)

    try:
        move = df["MOVE"].dropna().iloc[-1]
    except Exception:
        move = None

    if move is None:
        return SentinelState(sid, "Bond Vol Spike", status, None, trigger_ts, cooling_days, None, "N/A")

    trigger_level = sc.trigger_level or 130.0
    reset_below = sc.reset_below or 110.0
    reset_days = sc.reset_consecutive_days

    if status == SentinelStatus.CLEAR:
        if move > trigger_level:
            status = SentinelStatus.TRIGGERED
            trigger_ts = datetime.now(timezone.utc).isoformat()
            cooling_days = 0
    elif status in (SentinelStatus.TRIGGERED, SentinelStatus.COOLING):
        if move <= trigger_level:
            status = SentinelStatus.COOLING
        else:
            status = SentinelStatus.TRIGGERED
            cooling_days = 0

        if move < reset_below:
            cooling_days += 1
            if cooling_days >= reset_days:
                status = SentinelStatus.CLEAR
                trigger_ts = None
                cooling_days = 0
        else:
            cooling_days = 0

    # MOVE spike has no forced_ceiling; it's a freeze (no new positions)
    active_ceiling = None  # always None for MOVE
    display = f"MOVE {move:.0f}"
    if status == SentinelStatus.COOLING:
        display += f" (cooling {cooling_days}/{reset_days}d)"
    return SentinelState(sid, "Bond Vol Spike", status, active_ceiling, trigger_ts, cooling_days, move, display)


def _eval_trend_break(df: pd.DataFrame, cfg: Layer3Config, saved: dict, s5fi: float = 50.0) -> SentinelState:
    sid = "trend_break"
    sc = cfg.trend_break
    status, trigger_ts, cooling_days = _restore_sentinel(sid, saved)
    forced = sc.forced_ceiling_pct

    try:
        spx_col = "SPX" if "SPX" in df.columns else "SPY"
        spx = df[spx_col].dropna()
        vix_s = df["VIX"].dropna()
        if len(spx) < 50:
            raise ValueError("Insufficient SPX data")
        spx_ma50 = spx.rolling(50).mean().iloc[-1]
        spx_latest = spx.iloc[-1]
        vix_latest = vix_s.iloc[-1]
    except Exception:
        return SentinelState(sid, "Trend Break", status, forced if status != SentinelStatus.CLEAR else None,
                             trigger_ts, cooling_days, None, "N/A")

    trigger_vix = sc.trigger_vix or 25.0
    reset_vix = sc.reset_vix_below or 22.0
    reset_breadth = sc.reset_breadth_above or 50.0
    reset_days = sc.reset_consecutive_days

    below_ma50 = spx_latest < spx_ma50

    if status == SentinelStatus.CLEAR:
        if below_ma50 and vix_latest > trigger_vix:
            status = SentinelStatus.TRIGGERED
            trigger_ts = datetime.now(timezone.utc).isoformat()
            cooling_days = 0
    elif status in (SentinelStatus.TRIGGERED, SentinelStatus.COOLING):
        if below_ma50 and vix_latest > trigger_vix:
            status = SentinelStatus.TRIGGERED
            cooling_days = 0
        else:
            status = SentinelStatus.COOLING

        # Reset: SPX > 50DMA AND VIX < reset_vix AND S5FI > reset_breadth, all for N days
        all_reset = (spx_latest > spx_ma50) and (vix_latest < reset_vix) and (s5fi > reset_breadth)
        if all_reset:
            cooling_days += 1
            if cooling_days >= reset_days:
                status = SentinelStatus.CLEAR
                trigger_ts = None
                cooling_days = 0
        else:
            cooling_days = 0

    active_ceiling = forced if status != SentinelStatus.CLEAR else None
    display = f"SPX {'below' if below_ma50 else 'above'} 50DMA, VIX {vix_latest:.1f}"
    if status == SentinelStatus.COOLING:
        display += f" (cooling {cooling_days}/{reset_days}d)"
    return SentinelState(sid, "Trend Break", status, active_ceiling, trigger_ts, cooling_days, vix_latest, display)


def compute_layer3(
    df: pd.DataFrame,
    cfg: Layer3Config,
    s5fi: float = 50.0,
    state_path: Path | None = None,
) -> Layer3Result:
    """Evaluate all sentinels, persist state, and compute override ceiling."""
    saved = _load_state(state_path)

    sentinels = [
        _eval_vix_spike(df, cfg, saved),
        _eval_credit_break(df, cfg, saved),
        _eval_move_spike(df, cfg, saved),
        _eval_trend_break(df, cfg, saved, s5fi),
    ]

    _save_state(sentinels, state_path)

    any_triggered = any(s.status != SentinelStatus.CLEAR for s in sentinels)

    ceilings = [s.forced_ceiling_pct for s in sentinels
                if s.status != SentinelStatus.CLEAR and s.forced_ceiling_pct is not None]
    override = min(ceilings) if ceilings else None

    freeze = any(
        s.sentinel_id == "move_spike" and s.status != SentinelStatus.CLEAR
        for s in sentinels
    )

    return Layer3Result(
        sentinels=sentinels,
        any_triggered=any_triggered,
        override_ceiling_pct=override,
        freeze_active=freeze,
    )
