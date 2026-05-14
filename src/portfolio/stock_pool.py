"""Stock pool persistence and CRUD operations."""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import asdict, dataclass, field
from datetime import date
from typing import Optional


@dataclass
class StockPoolItem:
    ticker: str
    name: str
    market: str          # "A股" | "美股" | "港股"
    sector: str
    strategy_type: str   # "trending_up" | "value" | "oscillation"
    status: str          # "watching" | "holding"
    cost_basis: Optional[float] = None
    shares: Optional[float] = None
    notes: str = ""
    added_date: str = field(default_factory=lambda: date.today().isoformat())

    def __post_init__(self):
        self.ticker = self.ticker.upper()


def load_stock_pool(path: str) -> list[StockPoolItem]:
    """Load stock pool from JSON. Returns empty list if file missing or corrupt."""
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return [StockPoolItem(**item) for item in data]
    except Exception:
        return []


def save_stock_pool(items: list[StockPoolItem], path: str) -> None:
    """Atomically serialize and write the stock pool JSON."""
    os.makedirs(os.path.dirname(path) if os.path.dirname(path) else ".", exist_ok=True)
    payload = json.dumps([asdict(item) for item in items], ensure_ascii=False, indent=2)
    dir_ = os.path.dirname(os.path.abspath(path))
    fd, tmp = tempfile.mkstemp(dir=dir_, suffix=".json.tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(payload)
        os.replace(tmp, path)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def add_item(items: list[StockPoolItem], new_item: StockPoolItem) -> tuple[list[StockPoolItem], str | None]:
    """Add item; returns (updated_list, error_msg). Error if ticker already exists."""
    ticker_upper = new_item.ticker.upper()
    for existing in items:
        if existing.ticker.upper() == ticker_upper:
            return items, "ticker_duplicate_error"
    return items + [new_item], None


def update_item(items: list[StockPoolItem], updated: StockPoolItem) -> list[StockPoolItem]:
    """Replace item with same ticker. No-op if not found."""
    return [updated if i.ticker.upper() == updated.ticker.upper() else i for i in items]


def delete_item(items: list[StockPoolItem], ticker: str) -> list[StockPoolItem]:
    """Remove item by ticker (case-insensitive)."""
    ticker_upper = ticker.upper()
    return [i for i in items if i.ticker.upper() != ticker_upper]
