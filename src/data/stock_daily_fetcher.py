"""
Daily bar fetcher for individual stocks with ETL-on-demand CSV caching.

Supports A-share (Tushare) and US stocks (yfinance). HK stocks return
(None, stale=True) as a placeholder until a data source is integrated.

Cache: data_cache/stocks/{safe_ticker}/daily.csv
       columns: date, open, high, low, close, volume  (date is index)
"""

from __future__ import annotations

import logging
import os
import time
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

from src.portfolio.stock_pool import StockPoolItem

logger = logging.getLogger(__name__)

_CACHE_BASE = Path("data_cache/stocks")
_FETCH_DAYS = 500  # initial fetch window


def safe_ticker(ticker: str) -> str:
    """Convert ticker to filesystem-safe name (e.g., '600519.SH' → '600519_SH')."""
    return ticker.replace(".", "_").replace("/", "_").upper()


def _cache_path(ticker: str) -> Path:
    return _CACHE_BASE / safe_ticker(ticker) / "daily.csv"


def _load_daily_cache(ticker: str) -> pd.DataFrame | None:
    """Load cached daily bars. Returns None if file missing or unreadable."""
    path = _cache_path(ticker)
    if not path.exists():
        return None
    try:
        df = pd.read_csv(path, index_col="date", parse_dates=True)
        df.index = pd.to_datetime(df.index)
        df = df.sort_index()
        for col in ["open", "high", "low", "close", "volume"]:
            if col not in df.columns:
                return None
        return df
    except Exception as e:
        logger.warning(f"Failed to load daily cache for {ticker}: {e}")
        return None


def _save_daily_cache(ticker: str, df: pd.DataFrame) -> None:
    path = _cache_path(ticker)
    path.parent.mkdir(parents=True, exist_ok=True)
    df.index.name = "date"
    df.to_csv(path)


def _last_weekday(d: date) -> date:
    """Return d itself if a weekday, else go back to most recent weekday."""
    while d.weekday() >= 5:  # 5=Sat, 6=Sun
        d -= timedelta(days=1)
    return d


def _is_cache_fresh(df: pd.DataFrame) -> bool:
    """True if the cache covers up to T-1 (last weekday)."""
    if df is None or df.empty:
        return False
    t_minus_1 = _last_weekday(date.today() - timedelta(days=1))
    last_cached = df.index[-1].date()
    return last_cached >= t_minus_1


def _normalize_ashare_ticker(ticker: str) -> str:
    """Convert underscore-separated A-share ticker to dot form (e.g., 300308_SZ → 300308.SZ)."""
    import re
    if "_" in ticker and "." not in ticker:
        # Match pattern like 600519_SH / 300308_SZ / 688001_SH
        m = re.match(r"^(\d+)_([A-Z]+)$", ticker.upper())
        if m:
            return f"{m.group(1)}.{m.group(2)}"
    return ticker


def _fetch_ashare_daily(ticker: str, start_date: str, end_date: str) -> pd.DataFrame | None:
    """Fetch A-share daily bars via Tushare pro.daily()."""
    try:
        import tushare as ts
        import os
        token = os.environ.get("TUSHARE_API_KEY", "")
        pro = ts.pro_api(token)
        time.sleep(0.3)
        ts_code = _normalize_ashare_ticker(ticker)
        raw = pro.daily(ts_code=ts_code, start_date=start_date, end_date=end_date)
        if raw is None or raw.empty:
            return None
        raw = raw.rename(columns={"trade_date": "date", "vol": "volume"})
        raw["date"] = pd.to_datetime(raw["date"])
        raw = raw.set_index("date")[["open", "high", "low", "close", "volume"]]
        raw = raw.sort_index()
        raw = raw.astype(float)
        return raw
    except Exception as e:
        logger.warning(f"Tushare fetch failed for {ticker}: {e}")
        return None


def _fetch_us_daily(ticker: str, start_date: str, end_date: str) -> pd.DataFrame | None:
    """Fetch US stock daily bars via yfinance."""
    try:
        import yfinance as yf
        raw = yf.download(ticker, start=start_date, end=end_date, progress=False, auto_adjust=True, multi_level_index=False)
        if raw is None or raw.empty:
            return None
        # Flatten columns: handle both plain strings and MultiIndex tuples
        if hasattr(raw.columns, "levels"):
            raw.columns = [c[0].lower() if isinstance(c, tuple) else c.lower() for c in raw.columns]
        else:
            raw.columns = [c.lower() for c in raw.columns]
        raw.index = pd.to_datetime(raw.index)
        raw.index.name = "date"
        cols = [c for c in ["open", "high", "low", "close", "volume"] if c in raw.columns]
        raw = raw[cols].sort_index()
        raw = raw.astype(float)
        return raw
    except Exception as e:
        logger.warning(f"yfinance fetch failed for {ticker}: {e}")
        return None


def fetch_daily_bars(item: StockPoolItem) -> tuple[pd.DataFrame | None, bool]:
    """
    ETL-on-demand main entry point.

    Returns (df, stale):
      - df=None, stale=True  → no data available (HK, or total failure)
      - df, stale=False      → fresh data
      - df, stale=True       → data returned but may be outdated
    """
    if item.market == "港股":
        return None, True

    cached = _load_daily_cache(item.ticker)

    if cached is not None and _is_cache_fresh(cached):
        return cached, False

    # Determine fetch range
    if cached is not None and not cached.empty:
        last_date = cached.index[-1].date()
        start = (last_date + timedelta(days=1)).strftime("%Y%m%d")
    else:
        start = (date.today() - timedelta(days=_FETCH_DAYS)).strftime("%Y%m%d")

    end = date.today().strftime("%Y%m%d")

    if item.market == "A股":
        new_df = _fetch_ashare_daily(item.ticker, start, end)
    elif item.market == "美股":
        start_iso = (date.today() - timedelta(days=_FETCH_DAYS)).strftime("%Y-%m-%d") if cached is None else \
            (cached.index[-1].date() + timedelta(days=1)).strftime("%Y-%m-%d")
        end_iso = date.today().strftime("%Y-%m-%d")
        new_df = _fetch_us_daily(item.ticker, start_iso, end_iso)
    else:
        return None, True

    if new_df is None or new_df.empty:
        # API failed — return stale cache if available
        return cached, True

    if cached is not None and not cached.empty:
        combined = pd.concat([cached, new_df])
        combined = combined[~combined.index.duplicated(keep="last")].sort_index()
    else:
        combined = new_df

    try:
        _save_daily_cache(item.ticker, combined)
    except Exception as e:
        logger.warning(f"Failed to save daily cache for {item.ticker}: {e}")

    return combined, False
