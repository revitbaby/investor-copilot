"""
China A-share market data fetchers with ETL-on-demand CSV caching.

Each fetcher:
1. Checks the CSV cache; returns cached value if today's entry exists
2. Fetches from Tushare (primary) or AkShare (fallback) on cache miss
3. Appends new data to the cache CSV
4. On API failure returns the last-known-good value with data_stale=True

Cache files live under data_cache/china/.
"""

from __future__ import annotations

import concurrent.futures
import json
import logging
import os
import time
from contextlib import contextmanager
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Callable, Generator, Literal

import akshare as ak
import pandas as pd

logger = logging.getLogger(__name__)

_CACHE_DIR = Path("data_cache/china")
_SYNC_LOG_PATH = Path("data_cache/sync_log.json")
_WAN_TO_YI = 1e-4    # 万元 → 亿元
_YUAN_TO_YI = 1e-8   # 元   → 亿元 (pro.margin rzrqye/rzye/rqye are in 元)
_QIAN_TO_YI = 1e-5   # 千元 → 亿元 (used for index_daily amount field)

# Historical reference levels for margin ratio (% of total A-share market cap).
# 2015 peak: ~2.27万亿元 margin / ~70万亿元 total market cap ≈ 3.3%
# 2021 peak: ~1.9万亿元 / ~68万亿元 ≈ 2.8%
MARGIN_RATIO_REFERENCES = {
    "2015_peak": 3.3,
    "2021_peak": 2.8,
}

# Earliest date for historical backfill (2015 is sufficient for all indicators)
HISTORY_START = date(2015, 1, 1)


def _ensure_cache_dir() -> None:
    _CACHE_DIR.mkdir(parents=True, exist_ok=True)


def _last_weekday(d: date) -> date:
    """Return d if it is a weekday, otherwise the most recent prior weekday."""
    while d.weekday() >= 5:  # 5=Sat, 6=Sun
        d -= timedelta(days=1)
    return d


def _last_weekday_before(d: date) -> date:
    """Return the most recent weekday strictly before d (for T-1 publication-lag queries)."""
    d = d - timedelta(days=1)
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    return d


def _load_cache(filename: str) -> pd.DataFrame:
    path = _CACHE_DIR / filename
    if path.exists():
        try:
            df = pd.read_csv(path, index_col=0, parse_dates=True)
            df.index.name = "date"
            return df
        except Exception as e:
            logger.warning("Failed to load cache %s: %s", filename, e)
    return pd.DataFrame()


def _save_cache(filename: str, df: pd.DataFrame) -> None:
    _ensure_cache_dir()
    df.to_csv(_CACHE_DIR / filename)


_API_TIMEOUT_S = 25


def _run_with_timeout(fn: Callable, timeout_s: int = _API_TIMEOUT_S):
    """Execute fn() in a daemon thread with a hard timeout.

    Raises concurrent.futures.TimeoutError when the call exceeds timeout_s.
    The worker thread is daemon so it won't block process exit even if it hangs.
    """
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(fn)
        return future.result(timeout=timeout_s)


def _get_pro():
    import tushare as ts
    token = os.getenv("TUSHARE_API_KEY", "")
    if not token:
        raise EnvironmentError("TUSHARE_API_KEY not set")
    ts.set_token(token)
    return ts.pro_api()


def _last_known(df: pd.DataFrame, col: str) -> tuple[Any, bool]:
    """Return (last non-null value, data_stale=True). Returns (None, True) on empty."""
    if df.empty or col not in df.columns:
        return None, True
    series = df[col].dropna()
    if series.empty:
        return None, True
    return series.iloc[-1], True


def _update_sync_log(filename: str, duration_s: float, status: str) -> None:
    """Write a sync record to data_cache/sync_log.json (create-or-update per key).

    filename: relative key like 'china/margin_ratio.csv' or 'macro_data.csv'.
    Reads the corresponding CSV's last index row to populate last_data_date.
    """
    try:
        log: dict = json.loads(_SYNC_LOG_PATH.read_text()) if _SYNC_LOG_PATH.exists() else {}
    except Exception:
        log = {}

    last_data_date: str | None = None
    try:
        csv_path = Path("data_cache") / filename
        if csv_path.exists():
            df_tail = pd.read_csv(csv_path, index_col=0, parse_dates=True)
            if not df_tail.empty:
                last_idx = df_tail.index[-1]
                last_data_date = last_idx.strftime("%Y-%m-%d") if hasattr(last_idx, "strftime") else str(last_idx)[:10]
    except Exception:
        pass

    log[filename] = {
        "last_sync_utc": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S"),
        "duration_s": round(duration_s, 2),
        "status": status,
        "last_data_date": last_data_date,
    }

    try:
        _SYNC_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        _SYNC_LOG_PATH.write_text(json.dumps(log, ensure_ascii=False, indent=2))
    except Exception as e:
        logger.warning("_update_sync_log: failed to write: %s", e)


@contextmanager
def _record_sync(filename: str) -> Generator[None, None, None]:
    """Context manager: time an API fetch and write result to sync_log.json.

    Only wrap the API call branch (not CSV cache-hit paths) so that
    last_sync_utc reflects actual network round-trips.
    """
    t0 = time.perf_counter()
    exc_occurred = False
    try:
        yield
    except Exception:
        exc_occurred = True
        raise
    finally:
        duration_s = time.perf_counter() - t0
        _update_sync_log(filename, duration_s, "error" if exc_occurred else "success")


def _upsert_row(cache: pd.DataFrame, ts: pd.Timestamp, row_data: dict) -> pd.DataFrame:
    """Insert or replace a row in the cache DataFrame, keeping sorted by date."""
    new_row = pd.DataFrame([row_data], index=[ts])
    new_row.index.name = "date"
    if cache.empty:
        return new_row
    deduped = cache[~cache.index.isin([ts])]
    return pd.concat([deduped, new_row]).sort_index()


# ── Historical Backfill Helpers ───────────────────────────────────────────────

def _clean_corrupted_mv_cache() -> bool:
    """Detect and remove corrupted entries from total_mv_daily.csv.

    The previous implementation of _backfill_total_mv_daily used date-range
    queries (pro.daily_basic(start_date=..., end_date=...)) which hit Tushare's
    ~8000-row per-call limit. With ~5000 stocks × 20 trading days = 100k rows per
    month, only ~8% of stocks were returned, making the summed total_mv severely
    underestimated (sometimes by 8–10×).

    Detection: any entry whose Total_MV_Yi is < 70% of its year's median is
    considered corrupted. Also clears margin_ratio.csv and deposit_ratio.csv
    so they are rebuilt from corrected data.

    Returns True if any corruption was found and cleaned.
    """
    cache = _load_cache("total_mv_daily.csv")
    if cache.empty or "Total_MV_Yi" not in cache.columns:
        return False

    years = cache.index.year
    year_medians = cache.groupby(years)["Total_MV_Yi"].median()

    corrupted = pd.Series(False, index=cache.index)
    for yr, med in year_medians.items():
        corrupted |= (years == yr) & (cache["Total_MV_Yi"] < med * 0.7)

    n_corrupted = int(corrupted.sum())
    if n_corrupted == 0:
        return False

    logger.info(
        "_clean_corrupted_mv_cache: removing %d corrupted entries "
        "(date-range row-limit artifact; year-median detection)",
        n_corrupted,
    )
    _save_cache("total_mv_daily.csv", cache[~corrupted])

    # Clear downstream caches that use total_mv as denominator
    for fname in ("margin_ratio.csv", "deposit_ratio.csv"):
        fpath = _CACHE_DIR / fname
        if fpath.exists():
            fpath.unlink()
            logger.info("_clean_corrupted_mv_cache: cleared %s for rebuild", fname)

    return True


def _backfill_total_mv_daily(start_date: date, end_date: date) -> None:
    """Backfill daily total A-share market cap (万元→亿元) to total_mv_daily.csv.

    Uses pro.trade_cal to get month-end trading dates, then queries each date
    individually via pro.daily_basic(trade_date=...). Single-date queries return
    all listed stocks with no row-count truncation, unlike date-range queries
    which hit Tushare's ~8000-row limit and produce underestimated sums.
    """
    cache = _load_cache("total_mv_daily.csv")
    pro = _get_pro()

    start_str = start_date.strftime("%Y%m%d")
    end_str = end_date.strftime("%Y%m%d")

    try:
        cal = pro.trade_cal(
            exchange="SSE",
            start_date=start_str,
            end_date=end_str,
            is_open="1",
            fields="cal_date",
        )
    except Exception as e:
        logger.warning("_backfill_total_mv_daily: trade_cal failed: %s", e)
        return

    if cal.empty:
        logger.warning("_backfill_total_mv_daily: trade_cal returned empty")
        return

    # Keep only the last trading day of each month (sufficient for monthly indicators;
    # daily fetch_margin_ratio fills in recent daily values automatically).
    cal_series = pd.to_datetime(cal["cal_date"])
    month_end_dates = cal_series.groupby(cal_series.dt.to_period("M")).max()

    dates_to_fetch = [
        d.strftime("%Y%m%d")
        for d in month_end_dates
        if pd.Timestamp(d) not in cache.index
    ]

    if not dates_to_fetch:
        logger.info("_backfill_total_mv_daily: cache already complete, nothing to fetch")
        return

    logger.info("_backfill_total_mv_daily: fetching %d month-end dates", len(dates_to_fetch))

    for i, date_str in enumerate(dates_to_fetch):
        dt_ts = pd.Timestamp(date_str)
        try:
            df = pro.daily_basic(trade_date=date_str, fields="ts_code,total_mv")
            if df.empty:
                logger.warning("_backfill_total_mv_daily: empty response for %s", date_str)
            else:
                total_mv_yi = (
                    pd.to_numeric(df["total_mv"], errors="coerce").sum() * _WAN_TO_YI
                )
                if total_mv_yi > 0:
                    cache = _upsert_row(cache, dt_ts, {"Total_MV_Yi": round(total_mv_yi, 2)})
        except Exception as e:
            logger.warning("_backfill_total_mv_daily: failed for %s: %s", date_str, e)

        if (i + 1) % 20 == 0:
            _save_cache("total_mv_daily.csv", cache)
            logger.info(
                "_backfill_total_mv_daily: progress %d/%d", i + 1, len(dates_to_fetch)
            )

        if i < len(dates_to_fetch) - 1:
            time.sleep(0.2)  # stay within Tushare rate limits

    _save_cache("total_mv_daily.csv", cache)
    logger.info("_backfill_total_mv_daily: done, %d total dates in cache", len(cache))


def _backfill_margin_ratio(start_date: date) -> None:
    """Batch-fetch full margin ratio history using pro.margin + total_mv_daily.csv.

    pro.margin() has a ~4000-row per-call limit and returns the MOST RECENT rows
    when the range exceeds the limit. For 2015–present that's ~5500+ rows, so a
    single call silently drops the older years. Fix: query year-by-year so each
    batch stays well under the limit (~488 rows/year with SSE+SZSE).
    """
    today = date.today()
    pro = _get_pro()

    frames = []
    for year in range(start_date.year, today.year + 1):
        yr_start = max(date(year, 1, 1), start_date).strftime("%Y%m%d")
        yr_end = min(date(year, 12, 31), today).strftime("%Y%m%d")
        try:
            df_yr = pro.margin(
                start_date=yr_start,
                end_date=yr_end,
                fields="trade_date,rzrqye",
            )
            if not df_yr.empty:
                frames.append(df_yr)
            logger.info("_backfill_margin_ratio: fetched %d rows for %d", len(df_yr), year)
        except Exception as e:
            logger.warning("_backfill_margin_ratio: pro.margin failed for %d: %s", year, e)

    if not frames:
        return

    df_margin = pd.concat(frames, ignore_index=True)
    df_margin["rzrqye_num"] = pd.to_numeric(df_margin["rzrqye"], errors="coerce")
    daily_margin = (
        df_margin.groupby("trade_date")["rzrqye_num"]
        .sum()
        * _YUAN_TO_YI
    )

    total_mv_cache = _load_cache("total_mv_daily.csv")
    cache = _load_cache("margin_ratio.csv")

    for dt_str, margin_yi in daily_margin.items():
        dt_ts = pd.Timestamp(str(dt_str))
        if pd.isna(margin_yi) or margin_yi <= 0:
            continue
        if total_mv_cache.empty or "Total_MV_Yi" not in total_mv_cache.columns:
            continue
        if dt_ts not in total_mv_cache.index:
            continue
        mv = total_mv_cache.loc[dt_ts, "Total_MV_Yi"]
        if pd.isna(mv) or float(mv) <= 0:
            continue
        total_mv_yi = float(mv)
        ratio_pct = (margin_yi / total_mv_yi) * 100
        cache = _upsert_row(cache, dt_ts, {
            "Margin_Balance_Yi": round(margin_yi, 2),
            "Total_MV_Yi": round(total_mv_yi, 2),
            "Margin_Ratio_Pct": round(ratio_pct, 4),
        })

    _save_cache("margin_ratio.csv", cache)
    logger.info("_backfill_margin_ratio: wrote %d rows", len(cache))


def _backfill_equity_bond_spread(start_date: date) -> None:
    """Batch-fetch CSI300 PE TTM and 10Y bond yield history, compute spread.

    ak.bond_china_yield has a hard limit: end_date - start_date must be < 1 year.
    Wider ranges silently return empty data. Fix: query year-by-year and concat.
    """
    today = date.today()
    pro = _get_pro()
    start_str = start_date.strftime("%Y%m%d")
    end_str = today.strftime("%Y%m%d")

    # CSI300 PE batch — index_dailybasic has no row-count truncation issue
    try:
        df_pe = pro.index_dailybasic(
            ts_code="000300.SH",
            start_date=start_str,
            end_date=end_str,
            fields="trade_date,pe_ttm",
        )
    except Exception as e:
        logger.warning("_backfill_equity_bond_spread: pe_ttm batch failed: %s", e)
        return

    if df_pe.empty:
        return

    df_pe["date"] = pd.to_datetime(df_pe["trade_date"])
    df_pe = df_pe.set_index("date").sort_index()
    df_pe["pe_ttm"] = pd.to_numeric(df_pe["pe_ttm"], errors="coerce")

    # 10Y bond yield — must query year-by-year; single call > 1 year returns empty
    bond_frames = []
    for year in range(start_date.year, today.year + 1):
        yr_start = max(date(year, 1, 1), start_date).strftime("%Y%m%d")
        yr_end = min(date(year, 12, 31), today).strftime("%Y%m%d")
        try:
            raw_yr = ak.bond_china_yield(start_date=yr_start, end_date=yr_end)
            gov_yr = raw_yr[raw_yr["曲线名称"] == "中债国债收益率曲线"].copy()
            if not gov_yr.empty:
                bond_frames.append(gov_yr)
        except Exception as e:
            logger.warning("_backfill_equity_bond_spread: bond yield %d failed: %s", year, e)

    if not bond_frames:
        logger.warning("_backfill_equity_bond_spread: no bond yield data fetched")
        return

    gov = pd.concat(bond_frames, ignore_index=True)
    gov["date"] = pd.to_datetime(gov["日期"])
    gov = gov.set_index("date").sort_index()
    gov["yield_10y"] = pd.to_numeric(gov["10年"], errors="coerce")

    # Update sub-caches
    pe_cache = _load_cache("csi300_pe.csv")
    for dt_ts, row in df_pe.iterrows():
        if pd.notna(row["pe_ttm"]):
            pe_cache = _upsert_row(pe_cache, dt_ts, {"CSI300_PE_TTM": float(row["pe_ttm"])})
    _save_cache("csi300_pe.csv", pe_cache)

    yield_cache = _load_cache("cgb10y_yield.csv")
    for dt_ts, row in gov.iterrows():
        if pd.notna(row["yield_10y"]):
            yield_cache = _upsert_row(yield_cache, dt_ts, {"CGB_10Y_Yield": float(row["yield_10y"])})
    _save_cache("cgb10y_yield.csv", yield_cache)

    # Compute spread on date-aligned intersection
    spread_cache = _load_cache("equity_bond_spread.csv")
    combined = df_pe[["pe_ttm"]].join(gov[["yield_10y"]], how="inner")
    for dt_ts, row in combined.iterrows():
        pe = row["pe_ttm"]
        yld = row["yield_10y"]
        if pd.notna(pe) and pd.notna(yld) and pe > 0:
            spread = (1.0 / pe) * 100.0 - yld
            spread_cache = _upsert_row(spread_cache, dt_ts, {"Equity_Bond_Spread": round(spread, 4)})

    _save_cache("equity_bond_spread.csv", spread_cache)
    logger.info("_backfill_equity_bond_spread: wrote %d rows", len(spread_cache))


def _backfill_deposit_ratio(start_date: date) -> None:
    """Compute monthly deposit ratio from cached M2 + total_mv_daily.csv (no extra API calls)."""
    m2_cache = _load_cache("m2_monthly.csv")
    if m2_cache.empty or "M2_Yi" not in m2_cache.columns:
        logger.warning("_backfill_deposit_ratio: no M2 data in cache")
        return

    m2_series = m2_cache["M2_Yi"].dropna()
    m2_filtered = m2_series[m2_series.index >= pd.Timestamp(start_date)]

    total_mv_cache = _load_cache("total_mv_daily.csv")
    if total_mv_cache.empty or "Total_MV_Yi" not in total_mv_cache.columns:
        logger.warning("_backfill_deposit_ratio: no total_mv_daily data")
        return

    # Resample total_mv to month-end (last trading day of each month)
    total_mv_monthly = total_mv_cache["Total_MV_Yi"].dropna().resample("ME").last()

    deposit_cache = _load_cache("deposit_ratio.csv")

    # Align by calendar period (M2 index is typically month-start)
    m2_by_period = {pd.Period(dt, "M"): val for dt, val in m2_filtered.items()}
    mv_by_period = {pd.Period(dt, "M"): val for dt, val in total_mv_monthly.items()}

    for period in sorted(set(m2_by_period.keys()) & set(mv_by_period.keys())):
        m2_val = m2_by_period[period]
        mv_val = mv_by_period[period]
        if pd.isna(m2_val) or pd.isna(mv_val) or float(mv_val) <= 0:
            continue
        ratio = float(m2_val) / float(mv_val)
        month_ts = pd.Timestamp(period.to_timestamp())
        deposit_cache = _upsert_row(deposit_cache, month_ts, {
            "M2_Yi": round(float(m2_val), 2),
            "Total_MV_Yi": round(float(mv_val), 2),
            "Deposit_Ratio": round(ratio, 4),
            "Data_Month": str(period),
        })

    _save_cache("deposit_ratio.csv", deposit_cache)
    logger.info("_backfill_deposit_ratio: wrote %d rows", len(deposit_cache))


# ── Margin Ratio ──────────────────────────────────────────────────────────────

def fetch_margin_ratio(query_date: date | None = None) -> tuple[pd.DataFrame | None, bool]:
    """
    Fetch daily margin balance / total A-share market cap ratio (%).

    Uses Tushare pro.margin (SSE + SZSE) for margin balance and
    pro.index_dailybasic (000001.SH + 399001.SZ) for total market cap.
    Margin data has a T-1 publication lag; the returned DataFrame includes
    a 'Margin_Ratio_Pct' column.

    Returns (history_df, data_stale).
    """
    if query_date is None:
        query_date = date.today()

    # Clean any corrupted total_mv entries before loading the cache
    corrupted_cleaned = _clean_corrupted_mv_cache()

    cache = _load_cache("margin_ratio.csv")

    # First-load or post-cleanup backfill: ensure history from HISTORY_START
    if corrupted_cleaned or cache.empty or cache.index.min() > pd.Timestamp(HISTORY_START):
        try:
            _backfill_total_mv_daily(HISTORY_START, query_date)
            _backfill_margin_ratio(HISTORY_START)
            cache = _load_cache("margin_ratio.csv")
        except Exception as e:
            logger.warning("fetch_margin_ratio: backfill failed: %s", e)

    # Margin data is published T+1; fetch the last trading day before query_date
    target_date = _last_weekday_before(query_date)
    target_ts = pd.Timestamp(target_date)
    target_str = target_date.strftime("%Y%m%d")

    if not cache.empty and "Margin_Ratio_Pct" in cache.columns and target_ts in cache.index:
        return cache, False

    def _do_api():
        with _record_sync("china/margin_ratio.csv"):
            pro = _get_pro()
            df_margin = pro.margin(trade_date=target_str, fields="trade_date,rzrqye")
            if df_margin.empty:
                raise ValueError("empty margin response")
            margin_total_yi = (
                pd.to_numeric(df_margin["rzrqye"], errors="coerce").sum() * _YUAN_TO_YI
            )
            df_mv = pro.daily_basic(trade_date=target_str, fields="ts_code,total_mv")
            if df_mv.empty:
                raise ValueError("empty daily_basic response")
            total_mv_yi = (
                pd.to_numeric(df_mv["total_mv"], errors="coerce").sum() * _WAN_TO_YI
            )
            if total_mv_yi <= 0 or margin_total_yi <= 0:
                raise ValueError(f"margin={margin_total_yi:.2f}, total_mv={total_mv_yi:.2f}")
            ratio_pct = (margin_total_yi / total_mv_yi) * 100
            updated = _upsert_row(cache, target_ts, {
                "Margin_Balance_Yi": round(margin_total_yi, 2),
                "Total_MV_Yi": round(total_mv_yi, 2),
                "Margin_Ratio_Pct": round(ratio_pct, 4),
            })
            _save_cache("margin_ratio.csv", updated)
            return updated

    try:
        fresh_cache = _run_with_timeout(_do_api)
        return fresh_cache, False
    except concurrent.futures.TimeoutError:
        logger.warning("API timeout for fetch_margin_ratio, using stale cache")
        return (cache if not cache.empty else None), True
    except Exception as e:
        logger.warning("fetch_margin_ratio failed for %s: %s", target_date, e)
        return (cache if not cache.empty else None), True


# ── CSI 300 PE TTM ────────────────────────────────────────────────────────────

def fetch_csi300_pe(query_date: date | None = None) -> tuple[float | None, bool]:
    """
    Fetch CSI 300 PE TTM (T-1 lag) via Tushare pro.index_dailybasic.

    Returns (pe_ttm, data_stale).
    """
    if query_date is None:
        query_date = date.today()

    cache = _load_cache("csi300_pe.csv")
    target_date = _last_weekday_before(query_date)
    target_ts = pd.Timestamp(target_date)
    target_str = target_date.strftime("%Y%m%d")

    if not cache.empty and "CSI300_PE_TTM" in cache.columns and target_ts in cache.index:
        val = cache.loc[target_ts, "CSI300_PE_TTM"]
        return (float(val) if pd.notna(val) else None), False

    def _do_api():
        with _record_sync("china/csi300_pe.csv"):
            pro = _get_pro()
            df = pro.index_dailybasic(ts_code="000300.SH", trade_date=target_str,
                                      fields="trade_date,pe_ttm")
            if df.empty:
                raise ValueError("empty response")
            pe = pd.to_numeric(df["pe_ttm"].iloc[0], errors="coerce")
            if pd.isna(pe):
                raise ValueError("pe_ttm is NaN")
            updated = _upsert_row(cache, target_ts, {"CSI300_PE_TTM": float(pe)})
            _save_cache("csi300_pe.csv", updated)
            return float(pe)

    try:
        pe = _run_with_timeout(_do_api)
        return pe, False
    except concurrent.futures.TimeoutError:
        logger.warning("API timeout for fetch_csi300_pe, using stale cache")
        val, _ = _last_known(cache, "CSI300_PE_TTM")
        return (float(val) if val is not None else None), True
    except Exception as e:
        logger.warning("fetch_csi300_pe failed for %s: %s", target_date, e)
        val, _ = _last_known(cache, "CSI300_PE_TTM")
        return (float(val) if val is not None else None), True


# ── CGB 10Y Yield ─────────────────────────────────────────────────────────────

def fetch_cgb10y_yield(query_date: date | None = None) -> tuple[float | None, bool]:
    """
    Fetch 10-year China Government Bond yield (%) via AkShare bond_china_yield.

    Returns (yield_pct, data_stale).
    """
    if query_date is None:
        query_date = date.today()

    cache = _load_cache("cgb10y_yield.csv")
    target_ts = pd.Timestamp(query_date)

    if not cache.empty and "CGB_10Y_Yield" in cache.columns and target_ts in cache.index:
        val = cache.loc[target_ts, "CGB_10Y_Yield"]
        return (float(val) if pd.notna(val) else None), False

    def _do_api():
        start_str = (query_date - timedelta(days=7)).strftime("%Y%m%d")
        end_str = query_date.strftime("%Y%m%d")
        with _record_sync("china/cgb10y_yield.csv"):
            raw = ak.bond_china_yield(start_date=start_str, end_date=end_str)
            gov = raw[raw["曲线名称"] == "中债国债收益率曲线"]
            if gov.empty:
                raise ValueError("no gov bond curve data in last 7 days")
            updated = cache.copy()
            for _, row in gov.iterrows():
                dt = pd.to_datetime(row["日期"])
                yld = pd.to_numeric(row["10年"], errors="coerce")
                if pd.notna(yld):
                    updated = _upsert_row(updated, dt, {"CGB_10Y_Yield": float(yld)})
            _save_cache("cgb10y_yield.csv", updated)
            return updated

    try:
        fresh_cache = _run_with_timeout(_do_api)
        latest_val = fresh_cache["CGB_10Y_Yield"].dropna().iloc[-1]
        latest_dt = fresh_cache["CGB_10Y_Yield"].dropna().index[-1]
        stale = latest_dt.date() < query_date
        return float(latest_val), stale
    except concurrent.futures.TimeoutError:
        logger.warning("API timeout for fetch_cgb10y_yield, using stale cache")
        val, _ = _last_known(cache, "CGB_10Y_Yield")
        return (float(val) if val is not None else None), True
    except Exception as e:
        logger.warning("fetch_cgb10y_yield failed for %s: %s", query_date, e)
        val, _ = _last_known(cache, "CGB_10Y_Yield")
        return (float(val) if val is not None else None), True


# ── Equity-Bond Spread ────────────────────────────────────────────────────────

def fetch_equity_bond_spread(query_date: date | None = None) -> tuple[float | None, bool]:
    """
    Compute equity-bond spread = (1 / CSI300_PE_TTM) * 100 - CGB_10Y_Yield.

    PE TTM uses T-1 lag. Returns (spread_pct, data_stale).
    """
    if query_date is None:
        query_date = date.today()

    cache = _load_cache("equity_bond_spread.csv")

    # First-load backfill
    if cache.empty or cache.index.min() > pd.Timestamp(HISTORY_START):
        try:
            _backfill_equity_bond_spread(HISTORY_START)
            cache = _load_cache("equity_bond_spread.csv")
        except Exception as e:
            logger.warning("fetch_equity_bond_spread: backfill failed: %s", e)

    target_ts = pd.Timestamp(query_date)

    if not cache.empty and "Equity_Bond_Spread" in cache.columns and target_ts in cache.index:
        val = cache.loc[target_ts, "Equity_Bond_Spread"]
        return (float(val) if pd.notna(val) else None), False

    pe, pe_stale = fetch_csi300_pe(query_date)
    yield_val, yield_stale = fetch_cgb10y_yield(query_date)

    if pe is None or yield_val is None or pe <= 0:
        val, _ = _last_known(cache, "Equity_Bond_Spread")
        return (float(val) if val is not None else None), True

    spread = (1.0 / pe) * 100.0 - yield_val
    data_stale = pe_stale or yield_stale

    cache = _upsert_row(cache, target_ts, {"Equity_Bond_Spread": round(spread, 4)})
    with _record_sync("china/equity_bond_spread.csv"):
        _save_cache("equity_bond_spread.csv", cache)
    return float(spread), data_stale


# ── Limit Counts ──────────────────────────────────────────────────────────────

def fetch_limit_counts(query_date: date | None = None) -> tuple[dict | None, bool]:
    """
    Fetch daily limit-up (涨停) and limit-down (跌停) counts.

    Tries Tushare pro.stk_limit first; falls back to AkShare stock_zt_pool_em.
    Applies completeness check: count < 5 is treated as missing data.

    Returns ({"up_count", "down_count", "zt_dt_ratio"}, data_stale).
    """
    if query_date is None:
        query_date = date.today()

    cache = _load_cache("limit_counts.csv")
    target_ts = pd.Timestamp(query_date)
    date_str = query_date.strftime("%Y%m%d")

    if not cache.empty and "LimitUp_Count" in cache.columns and target_ts in cache.index:
        row = cache.loc[target_ts]
        up = int(row.get("LimitUp_Count", 0))
        dn = int(row.get("LimitDown_Count", 0))
        ratio = float(row.get("ZT_DT_Ratio", 0)) if pd.notna(row.get("ZT_DT_Ratio")) else None
        return {"up_count": up, "down_count": dn, "zt_dt_ratio": ratio}, False

    up_count, down_count = None, None

    # Primary: Tushare pro.stk_limit
    try:
        def _tushare_stk_limit():
            pro = _get_pro()
            return pro.stk_limit(trade_date=date_str)
        df = _run_with_timeout(_tushare_stk_limit)
        if not df.empty:
            up_count = int(len(df[df.get("up_limit", pd.Series()).notna()]))
            down_count = int(len(df[df.get("down_limit", pd.Series()).notna()]))
    except concurrent.futures.TimeoutError:
        logger.warning("API timeout for fetch_limit_counts (stk_limit), using stale cache")
    except Exception as e:
        logger.warning("Tushare stk_limit failed for %s: %s", date_str, e)

    # Fallback: AkShare limit-up pool (涨停池)
    if up_count is None:
        try:
            def _akshare_zt():
                return ak.stock_zt_pool_em(date=date_str)
            zt_df = _run_with_timeout(_akshare_zt)
            up_count = len(zt_df) if not zt_df.empty else 0
        except concurrent.futures.TimeoutError:
            logger.warning("API timeout for fetch_limit_counts (zt_pool), using stale cache")
        except Exception as e:
            logger.warning("AkShare stock_zt_pool_em failed: %s", e)

    # Fallback: AkShare limit-down
    if down_count is None:
        try:
            def _akshare_dt():
                return ak.stock_zt_pool_dtgc_em(date=date_str)
            dt_df = _run_with_timeout(_akshare_dt)
            down_count = len(dt_df) if not dt_df.empty else 0
        except concurrent.futures.TimeoutError:
            logger.warning("API timeout for fetch_limit_counts (dtgc_pool), using stale cache")
        except Exception as e:
            logger.warning("AkShare stock_zt_pool_dtgc_em failed: %s", e)

    if up_count is None or down_count is None:
        logger.warning("fetch_limit_counts: all sources failed for %s", date_str)
        if not cache.empty and "LimitUp_Count" in cache.columns:
            last = cache[["LimitUp_Count", "LimitDown_Count", "ZT_DT_Ratio"]].dropna().iloc[-1]
            return {
                "up_count": int(last["LimitUp_Count"]),
                "down_count": int(last["LimitDown_Count"]),
                "zt_dt_ratio": float(last["ZT_DT_Ratio"]) if pd.notna(last.get("ZT_DT_Ratio")) else None,
            }, True
        return None, True

    # Completeness check
    if up_count < 5:
        logger.warning("limit_up count < 5 (%d) for %s — treating as missing", up_count, date_str)
        up_count = None

    zt_dt_ratio = (up_count / down_count) if (up_count is not None and down_count > 0) else None

    cache = _upsert_row(cache, target_ts, {
        "LimitUp_Count": up_count,
        "LimitDown_Count": down_count,
        "ZT_DT_Ratio": zt_dt_ratio,
    })
    with _record_sync("china/limit_counts.csv"):
        _save_cache("limit_counts.csv", cache)
    return {"up_count": up_count, "down_count": down_count, "zt_dt_ratio": zt_dt_ratio}, False


# ── Northbound Flow ───────────────────────────────────────────────────────────

def fetch_northbound_flow(query_date: date | None = None) -> tuple[dict | None, bool]:
    """
    Fetch northbound (北向资金) net buy via Tushare pro.moneyflow_hsgt.
    Replaces the prior AkShare northbound channel.

    Returns ({"net_buy_yi", "cumulative_5d_yi"}, data_stale).
    net_buy_yi and cumulative_5d_yi are in 亿元.
    """
    if query_date is None:
        query_date = date.today()

    cache = _load_cache("northbound_flow.csv")
    target_ts = pd.Timestamp(query_date)

    if not cache.empty and "Northbound_Net_Yi" in cache.columns and target_ts in cache.index:
        row = cache.loc[target_ts]
        return {
            "net_buy_yi": float(row.get("Northbound_Net_Yi", 0)),
            "cumulative_5d_yi": float(row.get("Northbound_5D_Cumulative_Yi", 0)),
        }, False

    def _do_api():
        with _record_sync("china/northbound_flow.csv"):
            pro = _get_pro()
            start_date = (query_date - timedelta(days=20)).strftime("%Y%m%d")
            end_date = query_date.strftime("%Y%m%d")
            df = pro.moneyflow_hsgt(start_date=start_date, end_date=end_date,
                                    fields="trade_date,north_money")
            if df.empty:
                raise ValueError("empty northbound response")
            df["date"] = pd.to_datetime(df["trade_date"])
            df = df.set_index("date").sort_index()
            df["net_yi"] = pd.to_numeric(df["north_money"], errors="coerce") * _WAN_TO_YI
            df["cumul_5d"] = df["net_yi"].rolling(5, min_periods=1).sum()
            updated = cache.copy()
            for dt_ts, row in df.iterrows():
                updated = _upsert_row(updated, dt_ts, {
                    "Northbound_Net_Yi": round(float(row["net_yi"]), 2) if pd.notna(row["net_yi"]) else None,
                    "Northbound_5D_Cumulative_Yi": round(float(row["cumul_5d"]), 2) if pd.notna(row["cumul_5d"]) else None,
                })
            _save_cache("northbound_flow.csv", updated)
            latest = df.iloc[-1]
            return {
                "net_buy_yi": float(latest["net_yi"]) if pd.notna(latest["net_yi"]) else 0.0,
                "cumulative_5d_yi": float(latest["cumul_5d"]) if pd.notna(latest["cumul_5d"]) else 0.0,
            }

    try:
        return _run_with_timeout(_do_api), False
    except concurrent.futures.TimeoutError:
        logger.warning("API timeout for fetch_northbound_flow, using stale cache")
        if not cache.empty and "Northbound_Net_Yi" in cache.columns:
            last = cache[["Northbound_Net_Yi", "Northbound_5D_Cumulative_Yi"]].dropna(subset=["Northbound_Net_Yi"]).iloc[-1]
            return {"net_buy_yi": float(last["Northbound_Net_Yi"]), "cumulative_5d_yi": float(last.get("Northbound_5D_Cumulative_Yi", 0))}, True
        return None, True
    except Exception as e:
        logger.warning("fetch_northbound_flow failed for %s: %s", query_date, e)
        if not cache.empty and "Northbound_Net_Yi" in cache.columns:
            last = cache[["Northbound_Net_Yi", "Northbound_5D_Cumulative_Yi"]].dropna(subset=["Northbound_Net_Yi"]).iloc[-1]
            return {
                "net_buy_yi": float(last["Northbound_Net_Yi"]),
                "cumulative_5d_yi": float(last.get("Northbound_5D_Cumulative_Yi", 0)),
            }, True
        return None, True


# ── Southbound Flow ────────────────────────────────────────────────────────────

def fetch_southbound_flow(query_date: date | None = None) -> tuple[dict | None, bool]:
    """
    Fetch southbound (南向资金, 港股通) daily net buy + sigma deviation.

    Uses Tushare pro.moneyflow_hsgt south_money field.
    Returns ({"net_buy_yi", "sigma_deviation"}, data_stale).
    """
    if query_date is None:
        query_date = date.today()

    cache = _load_cache("southbound_flow.csv")
    target_ts = pd.Timestamp(query_date)

    if not cache.empty and "Southbound_Net_Yi" in cache.columns and target_ts in cache.index:
        row = cache.loc[target_ts]
        return {
            "net_buy_yi": float(row.get("Southbound_Net_Yi", 0)),
            "sigma_deviation": float(row.get("Southbound_Sigma_Dev", 0)),
        }, False

    def _do_api():
        with _record_sync("china/southbound_flow.csv"):
            pro = _get_pro()
            start_date = (query_date - timedelta(days=60)).strftime("%Y%m%d")
            end_date = query_date.strftime("%Y%m%d")
            df = pro.moneyflow_hsgt(start_date=start_date, end_date=end_date,
                                    fields="trade_date,south_money")
            if df.empty:
                raise ValueError("empty southbound response")
            df["date"] = pd.to_datetime(df["trade_date"])
            df = df.set_index("date").sort_index()
            df["net_yi"] = pd.to_numeric(df["south_money"], errors="coerce") * _WAN_TO_YI
            df["ma20"] = df["net_yi"].rolling(20, min_periods=5).mean()
            df["std20"] = df["net_yi"].rolling(20, min_periods=5).std()
            df["sigma_dev"] = (df["net_yi"] - df["ma20"]) / df["std20"].replace(0, float("nan"))
            updated = cache.copy()
            for dt_ts, row in df.iterrows():
                updated = _upsert_row(updated, dt_ts, {
                    "Southbound_Net_Yi": round(float(row["net_yi"]), 2) if pd.notna(row["net_yi"]) else None,
                    "Southbound_Sigma_Dev": round(float(row["sigma_dev"]), 4) if pd.notna(row.get("sigma_dev")) else None,
                })
            _save_cache("southbound_flow.csv", updated)
            latest = df.iloc[-1]
            return {
                "net_buy_yi": float(latest["net_yi"]) if pd.notna(latest["net_yi"]) else 0.0,
                "sigma_deviation": float(latest["sigma_dev"]) if pd.notna(latest.get("sigma_dev")) else 0.0,
            }

    try:
        return _run_with_timeout(_do_api), False
    except concurrent.futures.TimeoutError:
        logger.warning("API timeout for fetch_southbound_flow, using stale cache")
        if not cache.empty and "Southbound_Net_Yi" in cache.columns:
            last = cache[["Southbound_Net_Yi", "Southbound_Sigma_Dev"]].dropna(subset=["Southbound_Net_Yi"]).iloc[-1]
            return {"net_buy_yi": float(last["Southbound_Net_Yi"]), "sigma_deviation": float(last.get("Southbound_Sigma_Dev", 0))}, True
        return None, True
    except Exception as e:
        logger.warning("fetch_southbound_flow failed for %s: %s", query_date, e)
        if not cache.empty and "Southbound_Net_Yi" in cache.columns:
            last = cache[["Southbound_Net_Yi", "Southbound_Sigma_Dev"]].dropna(subset=["Southbound_Net_Yi"]).iloc[-1]
            return {
                "net_buy_yi": float(last["Southbound_Net_Yi"]),
                "sigma_deviation": float(last.get("Southbound_Sigma_Dev", 0)),
            }, True
        return None, True


# ── QVIX (50ETF Implied Volatility Index) ────────────────────────────────────

def fetch_qvix(query_date: date | None = None) -> tuple[float | None, bool]:
    """
    Fetch the latest QVIX (中国波动率指数) from AkShare index_option_50etf_qvix.

    Returns (qvix_close, data_stale).
    data_stale=True when the latest available data predates the query_date
    (e.g. during holiday gaps or AkShare data lag).
    """
    if query_date is None:
        query_date = date.today()

    cache = _load_cache("qvix.csv")
    target_date = _last_weekday_before(query_date)
    target_ts = pd.Timestamp(target_date)

    if not cache.empty and "QVIX_Close" in cache.columns and target_ts in cache.index:
        val = cache.loc[target_ts, "QVIX_Close"]
        return (float(val) if pd.notna(val) else None), False

    def _do_api():
        with _record_sync("china/qvix.csv"):
            raw = ak.index_option_50etf_qvix()
            if raw.empty:
                raise ValueError("empty QVIX response")
            raw["date"] = pd.to_datetime(raw["date"])
            raw = raw.set_index("date").sort_index()
            updated = cache.copy()
            for dt_ts, row in raw.iterrows():
                close = pd.to_numeric(row.get("close"), errors="coerce")
                if pd.notna(close):
                    updated = _upsert_row(updated, dt_ts, {"QVIX_Close": float(close)})
            _save_cache("qvix.csv", updated)
            return updated

    try:
        fresh_cache = _run_with_timeout(_do_api)
        latest_ts = fresh_cache["QVIX_Close"].dropna().index[-1]
        latest_val = float(fresh_cache.loc[latest_ts, "QVIX_Close"])
        stale = latest_ts.date() < target_date
        return latest_val, stale
    except concurrent.futures.TimeoutError:
        logger.warning("API timeout for fetch_qvix, using stale cache")
        val, _ = _last_known(cache, "QVIX_Close")
        return (float(val) if val is not None else None), True
    except Exception as e:
        logger.warning("fetch_qvix failed for %s: %s", query_date, e)
        val, _ = _last_known(cache, "QVIX_Close")
        return (float(val) if val is not None else None), True


# ── M2 Monthly ────────────────────────────────────────────────────────────────

def fetch_m2_monthly() -> tuple[pd.Series | None, str | None, bool]:
    """
    Fetch monthly M2 broad money stock (亿元) via Tushare pro.cn_m.

    Returns (series_Yi, data_month_str, data_stale).
    If current month not yet published, returns last known value + data_month indicator.
    """
    cache = _load_cache("m2_monthly.csv")

    def _do_api():
        with _record_sync("china/m2_monthly.csv"):
            pro = _get_pro()
            df = pro.cn_m(fields="month,m2,m2_yoy")
            if df.empty:
                raise ValueError("empty M2 response")
            df["date"] = pd.to_datetime(df["month"].astype(str), format="%Y%m")
            df = df.set_index("date").sort_index()
            df["M2_Yi"] = pd.to_numeric(df["m2"], errors="coerce")
            df["M2_YoY"] = pd.to_numeric(df["m2_yoy"], errors="coerce")
            result = df[["M2_Yi", "M2_YoY"]].dropna(subset=["M2_Yi"])
            if not cache.empty:
                combined = pd.concat([cache, result[~result.index.isin(cache.index)]]).sort_index()
            else:
                combined = result
            _save_cache("m2_monthly.csv", combined)
            return combined

    try:
        combined = _run_with_timeout(_do_api)
        latest_month = combined.index[-1].strftime("%Y-%m") if not combined.empty else None
        return combined["M2_Yi"], latest_month, False
    except concurrent.futures.TimeoutError:
        logger.warning("API timeout for fetch_m2_monthly, using stale cache")
        if not cache.empty and "M2_Yi" in cache.columns:
            return cache["M2_Yi"].dropna(), cache.index[-1].strftime("%Y-%m"), True
        return None, None, True
    except Exception as e:
        logger.warning("fetch_m2_monthly failed: %s", e)
        if not cache.empty and "M2_Yi" in cache.columns:
            series = cache["M2_Yi"].dropna()
            latest_month = cache.index[-1].strftime("%Y-%m") if not cache.empty else None
            return series, latest_month, True
        return None, None, True


# ── Market Total Amount ────────────────────────────────────────────────────────

def fetch_market_total_amount(query_date: date | None = None) -> tuple[float | None, float | None, bool]:
    """
    Fetch total A-share daily turnover (全市场成交额, 亿元) via Tushare.

    Sums amount from 000001.SH and 399001.SZ index_dailybasic.
    Returns (amount_yi, ma20_yi, data_stale).
    """
    if query_date is None:
        query_date = date.today()

    cache = _load_cache("total_amount.csv")
    target_ts = pd.Timestamp(query_date)

    if not cache.empty and "Total_Amount_Yi" in cache.columns and target_ts in cache.index:
        row = cache.loc[target_ts]
        amount = float(row["Total_Amount_Yi"]) if pd.notna(row.get("Total_Amount_Yi")) else None
        ma20 = float(row["Amount_MA20_Yi"]) if pd.notna(row.get("Amount_MA20_Yi")) else None
        return amount, ma20, False

    def _do_api():
        with _record_sync("china/total_amount.csv"):
            pro = _get_pro()
            start_date = (query_date - timedelta(days=40)).strftime("%Y%m%d")
            end_date = query_date.strftime("%Y%m%d")
            parts = {}
            for ts_code in ("000001.SH", "399001.SZ"):
                df = pro.index_daily(ts_code=ts_code, start_date=start_date, end_date=end_date,
                                     fields="trade_date,amount")
                if not df.empty and "amount" in df.columns:
                    df["date"] = pd.to_datetime(df["trade_date"])
                    df = df.set_index("date").sort_index()
                    parts[ts_code] = pd.to_numeric(df["amount"], errors="coerce") * _QIAN_TO_YI
            if not parts:
                raise ValueError("no amount data from any index")
            combined = pd.concat(parts.values(), axis=1).sum(axis=1)
            combined.name = "Total_Amount_Yi"
            ma20 = combined.rolling(20, min_periods=1).mean()
            updated = cache.copy()
            for dt_ts in combined.index:
                updated = _upsert_row(updated, dt_ts, {
                    "Total_Amount_Yi": round(float(combined[dt_ts]), 2) if pd.notna(combined[dt_ts]) else None,
                    "Amount_MA20_Yi": round(float(ma20[dt_ts]), 2) if pd.notna(ma20[dt_ts]) else None,
                })
            _save_cache("total_amount.csv", updated)
            return float(combined.iloc[-1]) if pd.notna(combined.iloc[-1]) else None, float(ma20.iloc[-1]) if pd.notna(ma20.iloc[-1]) else None

    try:
        latest_amount, latest_ma20 = _run_with_timeout(_do_api)
        return latest_amount, latest_ma20, False
    except concurrent.futures.TimeoutError:
        logger.warning("API timeout for fetch_market_total_amount, using stale cache")
        if not cache.empty and "Total_Amount_Yi" in cache.columns:
            last = cache[["Total_Amount_Yi", "Amount_MA20_Yi"]].dropna(subset=["Total_Amount_Yi"]).iloc[-1]
            return float(last["Total_Amount_Yi"]), float(last.get("Amount_MA20_Yi", 0)) or None, True
        return None, None, True
    except Exception as e:
        logger.warning("fetch_market_total_amount failed for %s: %s", query_date, e)
        if not cache.empty and "Total_Amount_Yi" in cache.columns:
            last = cache[["Total_Amount_Yi", "Amount_MA20_Yi"]].dropna(subset=["Total_Amount_Yi"]).iloc[-1]
            return float(last["Total_Amount_Yi"]), float(last.get("Amount_MA20_Yi", 0)) or None, True
        return None, None, True


# ── Deposit Ratio ─────────────────────────────────────────────────────────────

def fetch_deposit_ratio(query_date: date | None = None) -> tuple[float | None, str | None, bool]:
    """
    Compute M2 / A-share total market cap ratio (monthly frequency).

    Returns (ratio, data_month_str, data_stale).
    """
    if query_date is None:
        query_date = date.today()

    # _clean_corrupted_mv_cache already called by fetch_margin_ratio on the same load;
    # check independently here in case fetch_deposit_ratio is called first.
    corrupted_cleaned = _clean_corrupted_mv_cache()

    cache = _load_cache("deposit_ratio.csv")

    # First-load or post-cleanup backfill (M2 already cached; only needs total_mv_daily)
    if corrupted_cleaned or cache.empty or cache.index.min() > pd.Timestamp(HISTORY_START):
        try:
            _backfill_total_mv_daily(HISTORY_START, query_date)
            _backfill_deposit_ratio(HISTORY_START)
            cache = _load_cache("deposit_ratio.csv")
        except Exception as e:
            logger.warning("fetch_deposit_ratio: backfill failed: %s", e)

    month_str = query_date.strftime("%Y-%m")

    if not cache.empty and "Deposit_Ratio" in cache.columns:
        monthly = cache[cache.index.to_period("M") == pd.Period(month_str)]
        if not monthly.empty:
            val = monthly["Deposit_Ratio"].iloc[-1]
            return (float(val) if pd.notna(val) else None), month_str, False

    try:
        m2_series, data_month, m2_stale = fetch_m2_monthly()
        if m2_series is None or m2_series.empty:
            raise ValueError("no M2 data")

        pro = _get_pro()
        # Use last confirmed trading day to avoid empty results pre-market-close
        date_str = _last_weekday_before(query_date).strftime("%Y%m%d")

        # Same approach as fetch_margin_ratio: sum all A-share total_mv from
        # daily_basic (万元); index_dailybasic component indices underestimate
        # SZSE coverage.
        df_mv = pro.daily_basic(trade_date=date_str, fields="ts_code,total_mv")
        if df_mv.empty:
            raise ValueError("empty daily_basic response for market cap")
        total_mv_yi = (
            pd.to_numeric(df_mv["total_mv"], errors="coerce").sum() * _WAN_TO_YI
        )

        if total_mv_yi <= 0:
            raise ValueError("invalid total market cap")

        latest_m2 = float(m2_series.iloc[-1])
        ratio = latest_m2 / total_mv_yi

        month_ts = pd.Timestamp(query_date.replace(day=1))
        cache = _upsert_row(cache, month_ts, {
            "M2_Yi": latest_m2,
            "Total_MV_Yi": round(total_mv_yi, 2),
            "Deposit_Ratio": round(ratio, 4),
            "Data_Month": data_month,
        })
        _save_cache("deposit_ratio.csv", cache)
        return ratio, data_month, m2_stale

    except Exception as e:
        logger.warning("fetch_deposit_ratio failed: %s", e)
        if not cache.empty and "Deposit_Ratio" in cache.columns:
            last = cache["Deposit_Ratio"].dropna()
            if not last.empty:
                return float(last.iloc[-1]), month_str, True
        return None, None, True


# ── Index Close Prices ────────────────────────────────────────────────────────

def fetch_index_close(
    symbol: Literal["sh000300", "sz399006"],
    start_date: date | None = None,
) -> tuple[pd.Series | None, bool]:
    """
    Fetch daily close prices for a market index via AkShare.

    symbol: "sh000300" (沪深300) or "sz399006" (创业板指)
    Returns (pd.Series with DatetimeIndex of close prices, data_stale).
    ETL-on-demand: serves from cache if today's data exists, otherwise fetches full history.
    """
    _cache_file_map: dict[str, str] = {
        "sh000300": "index_hs300_daily.csv",
        "sz399006": "index_gem_daily.csv",
    }
    cache_file = _cache_file_map.get(symbol)
    if cache_file is None:
        logger.warning("fetch_index_close: unknown symbol %s", symbol)
        return None, True

    cache = _load_cache(cache_file)
    col = "Close"
    target_ts = pd.Timestamp(_last_weekday_before(date.today()))

    if not cache.empty and col in cache.columns and target_ts in cache.index:
        series = cache[col].dropna()
        if start_date is not None:
            series = series[series.index >= pd.Timestamp(start_date)]
        return series, False

    try:
        raw = ak.stock_zh_index_daily(symbol=symbol)
        if raw.empty:
            raise ValueError("empty response")

        raw["date"] = pd.to_datetime(raw["date"])
        raw = raw.set_index("date").sort_index()
        raw[col] = pd.to_numeric(raw["close"], errors="coerce")
        result = raw[[col]].dropna()
        _save_cache(cache_file, result)

        series = result[col].dropna()
        if start_date is not None:
            series = series[series.index >= pd.Timestamp(start_date)]
        return series, False

    except Exception as e:
        logger.warning("fetch_index_close(%s) failed: %s", symbol, e)
        if not cache.empty and col in cache.columns:
            series = cache[col].dropna()
            if start_date is not None:
                series = series[series.index >= pd.Timestamp(start_date)]
            return series, True
        return None, True
