"""Position Advisor: generate per-holding action recommendations."""

from __future__ import annotations

from src.regime.config import PositionAdvisorConfig
from src.regime.models import (
    EnvelopeResult, L1Regime, L2Regime, Layer1Result, Layer2Result,
    Layer3Result, PositionAction, RegimeResult, SentinelStatus,
)
from .models import AdvisoryResult, Holding, PositionAdvice

_CONVICTION_ORDER = {"C": 0, "B": 1, "A": 2, "S": 3}
_L2_REGIME_KEY = {
    L2Regime.STRONG_RISK_ON: "strong_risk_on",
    L2Regime.RISK_ON: "risk_on",
    L2Regime.NEUTRAL: "neutral",
    L2Regime.RISK_OFF: "risk_off",
    L2Regime.STRONG_RISK_OFF: "strong_risk_off",
}


def _get_position_limit(conviction: str, l2_regime: L2Regime,
                         matrix: dict[str, dict[str, int]]) -> float:
    """Look up max position % from the conviction-regime matrix."""
    regime_key = _L2_REGIME_KEY.get(l2_regime, "neutral")
    conv_map = matrix.get(conviction.upper(), {})
    return float(conv_map.get(regime_key, 10))


def _sort_for_trim(holdings: list[Holding]) -> list[Holding]:
    """Sort holdings by trim priority: conviction ASC → beta DESC → gain DESC."""
    return sorted(
        holdings,
        key=lambda h: (
            _CONVICTION_ORDER.get(h.conviction.upper(), 0),
            -h.beta_spx,
            -h.unrealized_gain_pct,
        ),
    )


def compute_advisory(
    holdings: list[Holding],
    total_value: float,
    cash: float,
    regime_result: RegimeResult,
    config: PositionAdvisorConfig,
) -> AdvisoryResult:
    """Generate per-holding action recommendations based on regime scoring."""
    l1 = regime_result.layer1
    l2 = regime_result.layer2
    l3 = regime_result.layer3
    envelope = regime_result.envelope

    target_min = envelope.target_min
    target_max = envelope.target_max

    # Collect active rules
    active_rules: list[str] = []

    # Risk exposure: exclude Hedge holdings
    non_hedge = [h for h in holdings if not h.is_hedge]
    hedge_holdings = [h for h in holdings if h.is_hedge]
    risk_exposure = sum(h.notional_exposure for h in non_hedge)
    current_pct = (risk_exposure / total_value * 100) if total_value > 0 else 0.0

    is_overweight = current_pct > target_max
    excess_dollars = max(0, risk_exposure - total_value * target_max / 100)

    # Regime-specific rules
    severe_s_only = l1.regime == L1Regime.SEVERE_CONTRACTION
    if severe_s_only:
        active_rules.append("SEVERE CONTRACTION: only S-conviction holdings retained")

    contracting = l1.regime in (L1Regime.CONTRACTING, L1Regime.SEVERE_CONTRACTION)
    options_limit_pct = (config.options_notional_limit_contracting_pct if contracting
                         else config.options_notional_limit_normal_pct)
    if contracting:
        active_rules.append(f"Liquidity contracting: options notional ≤ {options_limit_pct}%")
        active_rules.append("Liquidity contracting: no leverage/margin")

    freeze = l3.freeze_active
    if freeze:
        active_rules.append("MOVE Spike: FREEZE — no new positions allowed")

    any_l3_forced = l3.any_triggered and l3.override_ceiling_pct is not None
    if any_l3_forced:
        active_rules.append(f"L3 Emergency: position ceiling overridden to {l3.override_ceiling_pct}%")

    # Compute per-holding limits and actions
    matrix = config.conviction_regime_matrix
    advice_list: list[PositionAdvice] = []

    # Sorted for trim priority
    sorted_non_hedge = _sort_for_trim(non_hedge)

    for h in sorted_non_hedge:
        h_pct = (h.notional_exposure / total_value * 100) if total_value > 0 else 0.0
        limit = _get_position_limit(h.conviction, l2.regime, matrix)

        # Severe contraction: only S retained
        if severe_s_only and h.conviction.upper() != "S":
            limit = 0.0

        # Options notional cap
        if h.is_option:
            total_options = sum(x.notional_exposure for x in non_hedge if x.is_option)
            options_pct = (total_options / total_value * 100) if total_value > 0 else 0.0
            if options_pct > options_limit_pct:
                limit = min(limit, 0.0)

        if limit == 0.0:
            action = PositionAction.CLOSE
            target_pct = 0.0
            adj = -h.market_value
            reason = f"Limit 0% ({h.conviction} in {l2.regime.value})"
            if severe_s_only and h.conviction.upper() != "S":
                reason = f"SEVERE CONTRACTION: non-S ({h.conviction}) must close"
        elif h_pct > limit:
            action = PositionAction.TRIM
            target_pct = limit
            adj = -h.market_value * (1 - limit / h_pct) if h_pct > 0 else 0
            reason = f"Over limit: {h_pct:.1f}% > {limit}%"
        elif is_overweight:
            action = PositionAction.HOLD
            target_pct = h_pct
            adj = 0.0
            reason = "Portfolio overweight, hold current"
        elif current_pct < target_min and h_pct < limit:
            action = PositionAction.ADD
            target_pct = min(limit, h_pct + (target_min - current_pct))
            adj = total_value * (target_pct - h_pct) / 100
            reason = f"Underweight: can add to {target_pct:.1f}%"
        else:
            action = PositionAction.HOLD
            target_pct = h_pct
            adj = 0.0
            reason = "Within target range"

        advice_list.append(PositionAdvice(
            priority=0,  # set below
            ticker=h.ticker,
            conviction=h.conviction,
            current_pct=round(h_pct, 2),
            target_pct=round(target_pct, 2),
            action=action,
            adjustment_dollars=round(adj, 2),
            reason=reason,
        ))

    # Add hedge holdings as HOLD with no priority
    for h in hedge_holdings:
        h_pct = (h.notional_exposure / total_value * 100) if total_value > 0 else 0.0
        advice_list.append(PositionAdvice(
            priority=999,
            ticker=h.ticker,
            conviction="Hedge",
            current_pct=round(h_pct, 2),
            target_pct=round(h_pct, 2),
            action=PositionAction.HOLD,
            adjustment_dollars=0.0,
            reason="Hedge — excluded from risk exposure",
        ))

    # Assign priority numbers: CLOSE first, then TRIM, then HOLD, then ADD
    action_order = {PositionAction.CLOSE: 0, PositionAction.TRIM: 1,
                    PositionAction.HOLD: 2, PositionAction.ADD: 3}
    advice_list.sort(key=lambda a: (action_order.get(a.action, 9),
                                     _CONVICTION_ORDER.get(a.conviction.upper(), 5)))
    for i, a in enumerate(advice_list):
        a.priority = i + 1

    return AdvisoryResult(
        holdings_advice=advice_list,
        current_exposure_pct=round(current_pct, 2),
        target_min_pct=round(target_min, 2),
        target_max_pct=round(target_max, 2),
        is_overweight=is_overweight,
        excess_dollars=round(excess_dollars, 2),
        active_rules=active_rules,
        total_value=total_value,
        cash=cash,
    )
