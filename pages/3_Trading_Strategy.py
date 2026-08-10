"""
交易策略 — 仓位建议与选股分析
"""

import streamlit as st
from dotenv import load_dotenv

from src.ui.app import render_trading_strategy
from src.utils.i18n import init_i18n, set_language, get_current_language, t

load_dotenv()

st.set_page_config(
    page_title="交易策略 — Macro Liquidity",
    layout="wide",
    page_icon="📈",
)

init_i18n()

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

render_trading_strategy()
