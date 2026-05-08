"""Regime Scoring Engine orchestrator.

Runs L1 → L2 → L3 → Envelope and persists regime history.
"""

from __future__ import annotations

import csv
import logging
from datetime import datetime
from pathlib import Path

import pandas as pd

from .config import RegimeConfig, load_config
from .envelope import compute_envelope
from .layer1 import compute_layer1
from .layer2 import compute_layer2
from .layer3 import compute_layer3
from .models import RegimeResult
from ..data.breadth import compute_s5fi

logger = logging.getLogger(__name__)

_HISTORY_FILE = Path("data_cache/regime_history.csv")
_HISTORY_COLS = ["date", "l1_regime", "l1_ceiling", "l2_regime", "l2_util_min", "l2_util_max",
                 "l3_triggered", "l3_override", "target_min", "target_max", "mode", "spx_close"]


class RegimeEngine:
    """Top-level orchestrator for the three-layer regime scoring engine."""

    def __init__(self, config: RegimeConfig | None = None):
        self.config = config or load_config()

    def run(self, df: pd.DataFrame, sector_df: pd.DataFrame | None = None) -> RegimeResult:
        """Execute full scoring pipeline and return structured result."""
        # S5FI breadth
        if sector_df is not None and not sector_df.empty:
            s5fi = compute_s5fi(sector_df, self.config.breadth.sector_weights,
                                self.config.breadth.fallback_value)
        else:
            s5fi = self.config.breadth.fallback_value

        l1 = compute_layer1(df, self.config.layer1)
        l2 = compute_layer2(df, s5fi, self.config.layer2)
        l3 = compute_layer3(df, self.config.layer3, s5fi)
        envelope = compute_envelope(l1, l2, l3)

        result = RegimeResult(layer1=l1, layer2=l2, layer3=l3, envelope=envelope)
        self._append_history(result, df)
        return result

    def _append_history(self, result: RegimeResult, df: pd.DataFrame) -> None:
        """Append today's scoring snapshot to the history CSV."""
        try:
            today = datetime.now().strftime("%Y-%m-%d")
            spx_close = None
            for col in ("SPX", "SPY"):
                if col in df.columns:
                    val = df[col].dropna()
                    if not val.empty:
                        spx_close = round(float(val.iloc[-1]), 2)
                        break

            triggered_names = [s.name for s in result.layer3.sentinels
                               if s.status.value != "CLEAR"]

            row = {
                "date": today,
                "l1_regime": result.layer1.regime.value,
                "l1_ceiling": result.layer1.ceiling_pct,
                "l2_regime": result.layer2.regime.value,
                "l2_util_min": result.layer2.utilization_min,
                "l2_util_max": result.layer2.utilization_max,
                "l3_triggered": "|".join(triggered_names) if triggered_names else "",
                "l3_override": result.layer3.override_ceiling_pct or "",
                "target_min": result.envelope.target_min,
                "target_max": result.envelope.target_max,
                "mode": result.envelope.mode.value,
                "spx_close": spx_close or "",
            }

            path = _HISTORY_FILE
            path.parent.mkdir(parents=True, exist_ok=True)
            write_header = not path.exists()

            with open(path, "a", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=_HISTORY_COLS)
                if write_header:
                    writer.writeheader()
                writer.writerow(row)

        except Exception:
            logger.warning("Failed to append regime history", exc_info=True)
