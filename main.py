"""
Entry point for the Macro Liquidity AI Analyst Streamlit app.
Run: PYTHONPATH=. uv run streamlit run main.py
"""

import os

import streamlit as st
from dotenv import load_dotenv

from src.ui.app import render_us_dashboard, _cache_mtime, get_market_data, get_sector_etf_data
from src.ui.total_asset_page import render_total_asset_page
from src.utils.i18n import init_i18n, set_language, get_current_language, t

load_dotenv()

st.set_page_config(
    page_title="总资产 — Investor Copilot",
    layout="wide",
    page_icon="🧭",
)

init_i18n()

with st.sidebar:
    view = st.radio(
        "视图",
        options=["总资产", "美股仪表盘"],
        index=0,
    )

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

if view == "总资产":
    st.title(t("ledger_home_title"))
    render_total_asset_page()
else:
    st.title(t("title"))

    with st.sidebar:
        st.header(t("settings"))

        days_back = st.slider(t("lookback"), 90, 1825, 365)
        force_refresh = st.button(t("refresh_data"))

        st.info(f"{t('info_formula')}\n\n{t('info_signals')}")

    if force_refresh:
        for fname in ("macro_data.csv", "sector_etf_data.csv"):
            p = os.path.join("data_cache", fname)
            if os.path.exists(p):
                os.remove(p)
        st.cache_data.clear()
        st.info(t("loading_market_data"))

    render_us_dashboard(days_back)
