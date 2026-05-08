"""Data models for the position advisor."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from src.regime.models import PositionAction


@dataclass
class Holding:
    ticker: str
    type: str
    shares_or_contracts: float
    cost_basis: float
    current_price: float
    market_value: float
    notional_exposure: float
    sector: str
    conviction: str  # S, A, B, C, Hedge
    beta_spx: float
    underlying: str = ""
    expiry: str = ""

    @property
    def unrealized_gain_pct(self) -> float:
        if self.cost_basis == 0:
            return 0.0
        return ((self.current_price - self.cost_basis) / self.cost_basis) * 100

    @property
    def is_hedge(self) -> bool:
        return self.conviction.upper() == "HEDGE"

    @property
    def is_option(self) -> bool:
        return "option" in self.type.lower()


@dataclass
class PositionAdvice:
    priority: int
    ticker: str
    conviction: str
    current_pct: float
    target_pct: float
    action: PositionAction
    adjustment_dollars: float
    reason: str

    def to_dict(self) -> dict:
        return {
            "priority": self.priority,
            "ticker": self.ticker,
            "conviction": self.conviction,
            "current_pct": round(self.current_pct, 2),
            "target_pct": round(self.target_pct, 2),
            "action": self.action.value,
            "adjustment_dollars": round(self.adjustment_dollars, 2),
            "reason": self.reason,
        }


@dataclass
class AdvisoryResult:
    holdings_advice: list[PositionAdvice]
    current_exposure_pct: float
    target_min_pct: float
    target_max_pct: float
    is_overweight: bool
    excess_dollars: float
    active_rules: list[str]
    total_value: float
    cash: float

    def to_dict(self) -> dict:
        return {
            "holdings": [h.to_dict() for h in self.holdings_advice],
            "current_exposure_pct": round(self.current_exposure_pct, 2),
            "target_min_pct": round(self.target_min_pct, 2),
            "target_max_pct": round(self.target_max_pct, 2),
            "is_overweight": self.is_overweight,
            "excess_dollars": round(self.excess_dollars, 2),
            "active_rules": self.active_rules,
        }
