"""Parse user portfolio CSV into structured Holding objects."""

from __future__ import annotations

import csv
import io
from typing import BinaryIO

import pandas as pd

from .models import Holding

REQUIRED_FIELDS = [
    "ticker", "type", "shares_or_contracts", "cost_basis",
    "current_price", "market_value", "notional_exposure",
    "sector", "conviction", "beta_spx",
]

VALID_CONVICTIONS = {"S", "A", "B", "C", "HEDGE"}
VALID_TYPES = {"stock", "etf", "option_long_call", "option_long_put",
               "option_short_call", "option_short_put"}


def parse_portfolio_csv(file_content: str | bytes | BinaryIO) -> tuple[list[Holding], list[str]]:
    """Parse a CSV into Holding objects.

    Returns (holdings, errors). If errors is non-empty, holdings may be partial.
    """
    errors: list[str] = []

    if isinstance(file_content, bytes):
        file_content = file_content.decode("utf-8")
    if hasattr(file_content, "read"):
        file_content = file_content.read()
        if isinstance(file_content, bytes):
            file_content = file_content.decode("utf-8")

    try:
        df = pd.read_csv(io.StringIO(file_content))
    except Exception as e:
        return [], [f"CSV parse error: {e}"]

    df.columns = [c.strip().lower() for c in df.columns]

    missing = [f for f in REQUIRED_FIELDS if f not in df.columns]
    if missing:
        errors.append(f"Missing required columns: {', '.join(missing)}")
        return [], errors

    holdings: list[Holding] = []
    for idx, row in df.iterrows():
        row_errors: list[str] = []
        line = idx + 2  # 1-indexed + header

        conviction = str(row.get("conviction", "")).strip().upper()
        if conviction not in VALID_CONVICTIONS:
            row_errors.append(f"Row {line}: invalid conviction '{conviction}' (expected {VALID_CONVICTIONS})")

        htype = str(row.get("type", "")).strip().lower()
        if htype not in VALID_TYPES:
            row_errors.append(f"Row {line}: invalid type '{htype}' (expected {VALID_TYPES})")

        for field in ["shares_or_contracts", "cost_basis", "current_price",
                       "market_value", "notional_exposure", "beta_spx"]:
            try:
                float(row[field])
            except (ValueError, TypeError):
                row_errors.append(f"Row {line}: '{field}' must be numeric, got '{row[field]}'")

        if row_errors:
            errors.extend(row_errors)
            continue

        holdings.append(Holding(
            ticker=str(row["ticker"]).strip().upper(),
            type=htype,
            shares_or_contracts=float(row["shares_or_contracts"]),
            cost_basis=float(row["cost_basis"]),
            current_price=float(row["current_price"]),
            market_value=float(row["market_value"]),
            notional_exposure=float(row["notional_exposure"]),
            sector=str(row.get("sector", "")).strip(),
            conviction=conviction,
            beta_spx=float(row["beta_spx"]),
            underlying=str(row.get("underlying", "")).strip(),
            expiry=str(row.get("expiry", "")).strip(),
        ))

    return holdings, errors
