"""Target Position Envelope computation.

Combines L1 Ceiling × L2 Utilization in normal mode, or applies L3 override.
"""

from __future__ import annotations

from .models import EnvelopeMode, EnvelopeResult, Layer1Result, Layer2Result, Layer3Result


def compute_envelope(l1: Layer1Result, l2: Layer2Result, l3: Layer3Result) -> EnvelopeResult:
    """Compute the Target Position Envelope from the three layers."""
    if l3.any_triggered and l3.override_ceiling_pct is not None:
        target_min = 0.0
        target_max = float(l3.override_ceiling_pct)
        mode = EnvelopeMode.EMERGENCY
        derivation = (
            f"🚨 L3 Emergency Override: position ceiling {l3.override_ceiling_pct}% "
            f"(ignoring L1/L2)"
        )
    else:
        ceiling = l1.ceiling_pct
        util_min = l2.utilization_min
        util_max = l2.utilization_max

        target_min = ceiling * util_min / 100.0
        target_max = ceiling * util_max / 100.0
        mode = EnvelopeMode.NORMAL
        derivation = (
            f"L1 Ceiling ({l1.regime.value}): {ceiling}% × "
            f"L2 Utilization ({l2.regime.value}): {util_min}%–{util_max}% = "
            f"{target_min:.0f}%–{target_max:.0f}%"
        )

    sentinel_summary_parts = []
    for s in l3.sentinels:
        if s.status.value != "CLEAR":
            sentinel_summary_parts.append(f"{s.name}: {s.status.value}")
    if not sentinel_summary_parts:
        sentinel_summary = "L3 Sentinels: All Clear ✅"
    else:
        sentinel_summary = "L3: " + ", ".join(sentinel_summary_parts)

    derivation += f"\n{sentinel_summary}"

    return EnvelopeResult(
        target_min=round(target_min, 1),
        target_max=round(target_max, 1),
        mode=mode,
        derivation=derivation,
        l1_ceiling=l1.ceiling_pct,
        l2_util_min=l2.utilization_min,
        l2_util_max=l2.utilization_max,
    )
