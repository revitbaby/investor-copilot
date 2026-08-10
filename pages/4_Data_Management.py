"""
数据管理 — 缓存状态、同步记录与手动刷新
"""

import json
from datetime import date as date_type, datetime, timezone, timedelta
from pathlib import Path

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

from src.utils.i18n import init_i18n, set_language, get_current_language, t

load_dotenv()


def _inject_mobile_table_styles() -> None:
    """Inject CSS so dataframes scroll horizontally on small screens."""
    st.markdown(
        "<style>.stDataFrame { overflow-x: auto !important; }</style>",
        unsafe_allow_html=True,
    )


st.set_page_config(
    page_title="Data Management — Macro Liquidity",
    layout="wide",
    page_icon="🗄️",
)

init_i18n()
_inject_mobile_table_styles()

# 北京时间 UTC+8
_CST = timezone(timedelta(hours=8))

# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------
with st.sidebar:
    st.header(t("settings"))

    lang_options = {"English": "en", "中文": "zh"}
    current_lang = get_current_language()
    current_index = 0 if current_lang == "en" else 1

    selected_lang_label = st.radio(
        "Language / 语言",
        options=list(lang_options.keys()),
        index=current_index,
        horizontal=True,
    )

    if lang_options[selected_lang_label] != current_lang:
        set_language(lang_options[selected_lang_label])
        st.rerun()

# ---------------------------------------------------------------------------
# File registry: (sync_log key, display name, is_monthly)
# ---------------------------------------------------------------------------
CHINA_FILES: list[tuple[str, str, bool]] = [
    ("china/margin_ratio.csv",       "两融余额市值比 (Margin Ratio)",    False),
    ("china/csi300_pe.csv",          "沪深300 PE-TTM",                  False),
    ("china/cgb10y_yield.csv",       "10年国债收益率 (CGB 10Y)",         False),
    ("china/equity_bond_spread.csv", "股债利差 (EBS)",                   False),
    ("china/limit_counts.csv",       "涨停/跌停家数 (Limit Counts)",     False),
    ("china/northbound_flow.csv",    "北向资金净流入 (Northbound)",       False),
    ("china/southbound_flow.csv",    "南向资金净流入 (Southbound)",       False),
    ("china/qvix.csv",               "QVIX (50ETF 期权波动率)",           False),
    ("china/m2_monthly.csv",         "M2 货币供应量 (月频)",              True),
    ("china/total_amount.csv",       "A 股成交额 (Total Amount)",        False),
]

US_FILES: list[tuple[str, str, bool]] = [
    ("macro_data.csv",      "美联储宏观数据 (FRED / Yahoo)",    False),
    ("sector_etf_data.csv", "行业 ETF 数据 (Sector ETFs)",     False),
    ("china_data.csv",      "中国宏观数据 (AkShare/Tushare)",  False),
]

# ---------------------------------------------------------------------------
# Fetcher registry — lazy-imported to keep page startup fast
# ---------------------------------------------------------------------------

def _build_china_fetchers(today: date_type) -> list[tuple[str, str, object]]:
    from src.data.china_market_fetcher import (
        fetch_margin_ratio, fetch_csi300_pe, fetch_cgb10y_yield,
        fetch_equity_bond_spread, fetch_limit_counts, fetch_northbound_flow,
        fetch_southbound_flow, fetch_qvix, fetch_m2_monthly,
        fetch_market_total_amount,
    )
    return [
        ("china/margin_ratio.csv",       "两融余额市值比",   lambda: fetch_margin_ratio(today)),
        ("china/csi300_pe.csv",          "沪深300 PE-TTM",   lambda: fetch_csi300_pe(today)),
        ("china/cgb10y_yield.csv",       "10年国债收益率",    lambda: fetch_cgb10y_yield(today)),
        ("china/equity_bond_spread.csv", "股债利差 (EBS)",    lambda: fetch_equity_bond_spread(today)),
        ("china/limit_counts.csv",       "涨停/跌停家数",     lambda: fetch_limit_counts(today)),
        ("china/northbound_flow.csv",    "北向资金净流入",     lambda: fetch_northbound_flow(today)),
        ("china/southbound_flow.csv",    "南向资金净流入",     lambda: fetch_southbound_flow(today)),
        ("china/qvix.csv",               "QVIX 期权波动率",   lambda: fetch_qvix(today)),
        ("china/m2_monthly.csv",         "M2 货币供应量",      lambda: fetch_m2_monthly()),
        ("china/total_amount.csv",       "A 股成交额",         lambda: fetch_market_total_amount(today)),
    ]


def _build_us_fetchers() -> list[tuple[str, str, object]]:
    from src.data.loader import DataLoader
    loader = DataLoader()
    return [
        ("macro_data.csv",      "美联储宏观数据", lambda: loader.fetch_all_data(365)),
        ("sector_etf_data.csv", "行业 ETF 数据",  lambda: loader.fetch_sector_etf_data(365)),
        ("china_data.csv",      "中国宏观数据",   lambda: loader.fetch_china_data(365)),
    ]

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_sync_log() -> dict:
    p = Path("data_cache/sync_log.json")
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _last_expected_data_date() -> date_type:
    """Return the most recent weekday strictly before today (T-1 for A-share T+1 lag)."""
    d = date_type.today() - timedelta(days=1)
    while d.weekday() >= 5:  # Sat=5, Sun=6
        d -= timedelta(days=1)
    return d


def _classify_status(record: dict | None, is_monthly: bool) -> str:
    if record is None:
        return t("dm_status_unknown")
    if record.get("status") == "error":
        return t("dm_status_error")
    if is_monthly:
        return t("dm_status_monthly")
    try:
        sync_time = datetime.fromisoformat(record["last_sync_utc"]).replace(tzinfo=timezone.utc)
        synced_today = sync_time.date() == datetime.now(timezone.utc).date()

        if not synced_today:
            return t("dm_status_delayed")

        # Synced today: verify that the actual data is within the expected T+1 window.
        # If data_date < last weekday before today, the API returned stale data despite
        # a successful sync (e.g. northbound disclosure stopped Aug 2024).
        data_date_str = record.get("last_data_date")
        if not data_date_str:
            return t("dm_status_fresh")

        data_date = date_type.fromisoformat(data_date_str[:10])
        expected_min = _last_expected_data_date()
        if data_date >= expected_min:
            return t("dm_status_fresh")

        lag_days = (date_type.today() - data_date).days
        return t("dm_status_synced_stale").format(n=lag_days)

    except Exception:
        return t("dm_status_unknown")


def _csv_last_date(key: str) -> str | None:
    csv_path = Path("data_cache") / key
    if not csv_path.exists():
        return None
    try:
        df = pd.read_csv(csv_path, index_col=0, parse_dates=True)
        return str(df.index[-1])[:10] if not df.empty else None
    except Exception:
        return None


def _build_rows(
    files: list[tuple[str, str, bool]],
    sync_log: dict,
    syncing_key: str | None = None,
) -> list[dict]:
    rows = []
    for key, display_name, is_monthly in files:
        record = sync_log.get(key)
        last_sync = duration = "—"
        data_date: str | None = None

        # Show spinner on the row currently being fetched
        if key == syncing_key:
            status = "⏳ " + (t("loading_market_data") if t("loading_market_data") != "loading_market_data" else "Syncing...")
            last_sync = "—"
        elif record:
            try:
                dt = datetime.fromisoformat(record["last_sync_utc"]).replace(tzinfo=timezone.utc)
                last_sync = dt.astimezone(_CST).strftime("%m-%d %H:%M")
            except Exception:
                pass
            data_date = record.get("last_data_date")
            dur = record.get("duration_s")
            if dur is not None:
                duration = f"{dur:.1f}s" + (" ⚡" if dur > 30 else "")
            status = _classify_status(record, is_monthly)
        else:
            data_date = _csv_last_date(key)
            if data_date is None:
                status = t("dm_status_unknown")
            elif is_monthly:
                status = t("dm_status_monthly")
            elif data_date >= (datetime.now(timezone.utc).date() - timedelta(days=3)).strftime("%Y-%m-%d"):
                status = t("dm_status_fresh")
            else:
                status = t("dm_status_delayed")
            last_sync = "— (cache hit)"

        rows.append({
            t("dm_col_dataset"):   display_name,
            t("dm_col_last_sync"): last_sync,
            t("dm_col_data_date"): data_date or "—",
            t("dm_col_duration"):  duration,
            t("dm_col_status"):    status,
        })
    return rows


def _render_table(
    files: list[tuple[str, str, bool]],
    sync_log: dict,
    syncing_key: str | None = None,
) -> None:
    rows = _build_rows(files, sync_log, syncing_key)
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)


def _render_all_tables(
    sync_log: dict,
    syncing_key: str | None = None,
) -> None:
    st.subheader(t("dm_china_section"))
    _render_table(CHINA_FILES, sync_log, syncing_key)
    st.caption(t("dm_backfill_note"))
    st.divider()
    st.subheader(t("dm_us_section"))
    _render_table(US_FILES, sync_log, syncing_key)

# ---------------------------------------------------------------------------
# Live refresh — triggered when dm_do_refresh is in session_state
# ---------------------------------------------------------------------------

def _do_refresh() -> None:
    today = date_type.today()

    # Delete all cached CSVs so fetchers re-pull
    for fname in ("macro_data.csv", "sector_etf_data.csv", "china_data.csv"):
        p = Path("data_cache") / fname
        if p.exists():
            p.unlink()
    for china_file in Path("data_cache/china").glob("*.csv"):
        china_file.unlink()

    # Invalidate process-level and session-level caches
    st.cache_data.clear()
    st.session_state.pop(f"china_regime_{today}", None)

    sync_log = _load_sync_log()
    table_ph = st.empty()

    china_fetchers = _build_china_fetchers(today)
    us_fetchers = _build_us_fetchers()
    all_fetchers = china_fetchers + us_fetchers

    with st.status("🔄 正在逐项刷新数据源...", expanded=True) as status:
        for key, display_name, fetcher_fn in all_fetchers:
            status.write(f"⏳ **{display_name}**")
            # Show "正在同步" on this row before fetch starts
            with table_ph.container():
                _render_all_tables(sync_log, syncing_key=key)
            try:
                fetcher_fn()
            except Exception as e:
                status.write(f"  ❌ 失败: {e}")
            # Reload log and refresh table with completed result
            sync_log = _load_sync_log()
            with table_ph.container():
                _render_all_tables(sync_log, syncing_key=None)

        status.update(label="✅ 全部数据刷新完成", state="complete", expanded=False)

    st.session_state.pop("dm_do_refresh", None)
    st.rerun()

# ---------------------------------------------------------------------------
# Page body
# ---------------------------------------------------------------------------

st.title(t("dm_page_title"))
st.caption(t("dm_subtitle"))
st.divider()

# If a refresh was triggered, enter the live-refresh flow immediately
if st.session_state.get("dm_do_refresh"):
    _do_refresh()
    st.stop()

# --- Normal display ---
sync_log = _load_sync_log()
_render_all_tables(sync_log)

st.divider()

# ---------------------------------------------------------------------------
# Action buttons
# ---------------------------------------------------------------------------
col_refresh, col_clear, _ = st.columns([1, 1, 4])

with col_refresh:
    if st.button(t("dm_btn_refresh_all"), type="primary"):
        st.session_state["dm_confirm_refresh"] = True

with col_clear:
    if st.button(t("dm_btn_clear_today")):
        st.session_state["dm_confirm_clear"] = True

# --- Confirmation: Refresh All ---
if st.session_state.get("dm_confirm_refresh"):
    st.warning(t("dm_confirm_refresh"))
    yes_col, no_col, _ = st.columns([1, 1, 6])
    with yes_col:
        if st.button("✅ Yes / 确认", key="dm_refresh_yes"):
            st.session_state["dm_do_refresh"] = True
            st.session_state.pop("dm_confirm_refresh", None)
            st.rerun()
    with no_col:
        if st.button("❌ No / 取消", key="dm_refresh_no"):
            st.session_state.pop("dm_confirm_refresh", None)
            st.rerun()

# --- Confirmation: Clear Today ---
if st.session_state.get("dm_confirm_clear"):
    st.info(t("dm_confirm_clear"))
    yes_col2, no_col2, _ = st.columns([1, 1, 6])
    with yes_col2:
        if st.button("✅ Yes / 确认", key="dm_clear_yes"):
            today_str = date_type.today().strftime("%Y-%m-%d")
            for china_file in Path("data_cache/china").glob("*.csv"):
                try:
                    df_c = pd.read_csv(china_file, index_col=0, parse_dates=True)
                    if not df_c.empty and str(df_c.index[-1])[:10] == today_str:
                        df_c.iloc[:-1].to_csv(china_file)
                except Exception:
                    pass
            st.cache_data.clear()
            st.session_state.pop("dm_confirm_clear", None)
            st.rerun()
    with no_col2:
        if st.button("❌ No / 取消", key="dm_clear_no"):
            st.session_state.pop("dm_confirm_clear", None)
            st.rerun()
