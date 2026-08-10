"""
中国 / 港股 — A 股体制评分引擎与宏观流动性仪表盘
"""

import os

import streamlit as st
from dotenv import load_dotenv

from src.ui.app import render_china_dashboard, _cache_mtime
from src.utils.i18n import init_i18n, set_language, get_current_language, t

load_dotenv()

st.set_page_config(
    page_title="中国/港股 — Macro Liquidity",
    layout="wide",
    page_icon="🇨🇳",
)

init_i18n()

st.title(t("title") + " — " + t("tab_china"))

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

    days_back = st.slider(t("lookback"), 90, 1825, 365)
    force_refresh = st.button(t("refresh_data"))

    st.info(f"{t('info_formula')}\n\n{t('info_signals')}")

if force_refresh:
    import datetime as _dt
    for fname in ("china_data.csv",):
        p = os.path.join("data_cache", fname)
        if os.path.exists(p):
            os.remove(p)
    st.cache_data.clear()
    # 清除 session_state 中今日的体制缓存，使进度弹窗在下次渲染时重新出现
    regime_cache_key = f"china_regime_{_dt.date.today()}"
    st.session_state.pop(regime_cache_key, None)

render_china_dashboard(days_back)
