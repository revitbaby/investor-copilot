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

import logging
import os
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import akshare as ak
import pandas as pd

logger = logging.getLogger(__name__)

_CACHE_DIR = Path("data_cache/china")
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


def _upsert_row(cache: pd.DataFrame, ts: pd.Timestamp, row_data: dict) -> pd.DataFrame:
    """Insert or replace a row in the cache DataFrame, keeping sorted by date."""
    new_row = pd.DataFrame([row_data], index=[ts])
    new_row.index.name = "date"
    if cache.empty:
        return new_row
    deduped = cache[~cache.index.isin([ts])]
    return pd.concat([deduped, new_row]).sort_index()


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

    cache = _load_cache("margin_ratio.csv")
    # Margin data is published T+1; fetch the last trading day before query_date
    target_date = _last_weekday_before(query_date)
    target_ts = pd.Timestamp(target_date)
    target_str = target_date.strftime("%Y%m%d")

    if not cache.empty and "Margin_Ratio_Pct" in cache.columns and target_ts in cache.index:
        return cache, False

    try:
        pro = _get_pro()

        # ── Margin balance ──────────────────────────────────────────────────
        # pro.margin ignores exchange= filter and always returns all exchanges.
        # Call once; use rzrqye (combined margin balance per exchange, in 元).
        df_margin = pro.margin(trade_date=target_str, fields="trade_date,rzrqye")
        if df_margin.empty:
            raise ValueError("empty margin response")
        margin_total_yi = (
            pd.to_numeric(df_margin["rzrqye"], errors="coerce").sum() * _YUAN_TO_YI
        )

        # ── Total A-share market cap ────────────────────────────────────────
        # daily_basic returns all A-share stocks; total_mv is in 万元.
        # This covers SSE + SZSE + BSE accurately without index-coverage gaps.
        df_mv = pro.daily_basic(trade_date=target_str, fields="ts_code,total_mv")
        if df_mv.empty:
            raise ValueError("empty daily_basic response")
        total_mv_yi = (
            pd.to_numeric(df_mv["total_mv"], errors="coerce").sum() * _WAN_TO_YI
        )

        if total_mv_yi <= 0 or margin_total_yi <= 0:
            raise ValueError(f"margin={margin_total_yi:.2f}, total_mv={total_mv_yi:.2f}")

        ratio_pct = (margin_total_yi / total_mv_yi) * 100

        cache = _upsert_row(cache, target_ts, {
            "Margin_Balance_Yi": round(margin_total_yi, 2),
            "Total_MV_Yi": round(total_mv_yi, 2),
            "Margin_Ratio_Pct": round(ratio_pct, 4),
        })
        _save_cache("margin_ratio.csv", cache)
        return cache, False

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

    try:
        pro = _get_pro()
        df = pro.index_dailybasic(ts_code="000300.SH", trade_date=target_str,
                                  fields="trade_date,pe_ttm")
        if df.empty:
            raise ValueError("empty response")
        pe = pd.to_numeric(df["pe_ttm"].iloc[0], errors="coerce")
        if pd.isna(pe):
            raise ValueError("pe_ttm is NaN")

        cache = _upsert_row(cache, target_ts, {"CSI300_PE_TTM": float(pe)})
        _save_cache("csi300_pe.csv", cache)
        return float(pe), False

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

    try:
        # Use a 7-day lookback window; bond data is only published on trading days
        start_str = (query_date - timedelta(days=7)).strftime("%Y%m%d")
        end_str = query_date.strftime("%Y%m%d")
        raw = ak.bond_china_yield(start_date=start_str, end_date=end_str)
        gov = raw[raw["曲线名称"] == "中债国债收益率曲线"]
        if gov.empty:
            raise ValueError("no gov bond curve data in last 7 days")

        for _, row in gov.iterrows():
            dt = pd.to_datetime(row["日期"])
            yld = pd.to_numeric(row["10年"], errors="coerce")
            if pd.notna(yld):
                cache = _upsert_row(cache, dt, {"CGB_10Y_Yield": float(yld)})

        _save_cache("cgb10y_yield.csv", cache)

        # Return the most recent value as the "current" yield
        latest_val = cache["CGB_10Y_Yield"].dropna().iloc[-1]
        # Whether we had to use an older date = stale if latest cache date != query_date
        latest_dt = cache["CGB_10Y_Yield"].dropna().index[-1]
        stale = latest_dt.date() < query_date
        return float(latest_val), stale

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
        pro = _get_pro()
        df = pro.stk_limit(trade_date=date_str)
        if not df.empty:
            up_count = int(len(df[df.get("up_limit", pd.Series()).notna()]))
            down_count = int(len(df[df.get("down_limit", pd.Series()).notna()]))
    except Exception as e:
        logger.warning("Tushare stk_limit failed for %s: %s", date_str, e)

    # Fallback: AkShare limit-up pool (涨停池)
    if up_count is None:
        try:
            zt_df = ak.stock_zt_pool_em(date=date_str)
            up_count = len(zt_df) if not zt_df.empty else 0
        except Exception as e:
            logger.warning("AkShare stock_zt_pool_em failed: %s", e)

    # Fallback: AkShare limit-down
    if down_count is None:
        try:
            dt_df = ak.stock_zt_pool_dtgc_em(date=date_str)
            down_count = len(dt_df) if not dt_df.empty else 0
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

    try:
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

        # Compute rolling 5-day cumulative for each date
        df["cumul_5d"] = df["net_yi"].rolling(5, min_periods=1).sum()

        for dt_ts, row in df.iterrows():
            cache = _upsert_row(cache, dt_ts, {
                "Northbound_Net_Yi": round(float(row["net_yi"]), 2) if pd.notna(row["net_yi"]) else None,
                "Northbound_5D_Cumulative_Yi": round(float(row["cumul_5d"]), 2) if pd.notna(row["cumul_5d"]) else None,
            })
        _save_cache("northbound_flow.csv", cache)

        latest = df.iloc[-1]
        return {
            "net_buy_yi": float(latest["net_yi"]) if pd.notna(latest["net_yi"]) else 0.0,
            "cumulative_5d_yi": float(latest["cumul_5d"]) if pd.notna(latest["cumul_5d"]) else 0.0,
        }, False

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

    try:
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

        for dt_ts, row in df.iterrows():
            cache = _upsert_row(cache, dt_ts, {
                "Southbound_Net_Yi": round(float(row["net_yi"]), 2) if pd.notna(row["net_yi"]) else None,
                "Southbound_Sigma_Dev": round(float(row["sigma_dev"]), 4) if pd.notna(row.get("sigma_dev")) else None,
            })
        _save_cache("southbound_flow.csv", cache)

        latest = df.iloc[-1]
        return {
            "net_buy_yi": float(latest["net_yi"]) if pd.notna(latest["net_yi"]) else 0.0,
            "sigma_deviation": float(latest["sigma_dev"]) if pd.notna(latest.get("sigma_dev")) else 0.0,
        }, False

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

    try:
        raw = ak.index_option_50etf_qvix()
        if raw.empty:
            raise ValueError("empty QVIX response")

        raw["date"] = pd.to_datetime(raw["date"])
        raw = raw.set_index("date").sort_index()

        for dt_ts, row in raw.iterrows():
            close = pd.to_numeric(row.get("close"), errors="coerce")
            if pd.notna(close):
                cache = _upsert_row(cache, dt_ts, {"QVIX_Close": float(close)})

        _save_cache("qvix.csv", cache)

        latest_ts = cache["QVIX_Close"].dropna().index[-1]
        latest_val = float(cache.loc[latest_ts, "QVIX_Close"])
        stale = latest_ts.date() < target_date
        return latest_val, stale

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

    try:
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
        latest_month = combined.index[-1].strftime("%Y-%m") if not combined.empty else None
        return combined["M2_Yi"], latest_month, False

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

    try:
        pro = _get_pro()
        start_date = (query_date - timedelta(days=40)).strftime("%Y%m%d")
        end_date = query_date.strftime("%Y%m%d")

        parts = {}
        for ts_code in ("000001.SH", "399001.SZ"):
            # index_daily has the amount field (千元); index_dailybasic does not
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

        for dt_ts in combined.index:
            cache = _upsert_row(cache, dt_ts, {
                "Total_Amount_Yi": round(float(combined[dt_ts]), 2) if pd.notna(combined[dt_ts]) else None,
                "Amount_MA20_Yi": round(float(ma20[dt_ts]), 2) if pd.notna(ma20[dt_ts]) else None,
            })
        _save_cache("total_amount.csv", cache)

        latest_amount = float(combined.iloc[-1]) if pd.notna(combined.iloc[-1]) else None
        latest_ma20 = float(ma20.iloc[-1]) if pd.notna(ma20.iloc[-1]) else None
        return latest_amount, latest_ma20, False

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

    cache = _load_cache("deposit_ratio.csv")
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
