import streamlit as st

TRANSLATIONS = {
    "en": {
        "title": "Macro Liquidity AI Analyst",
        "settings": "Settings",
        "lookback": "Lookback Period (Days)",
        "refresh_data": "Refresh Data",
        "info_formula": "**Net Liquidity Formula:**\nFed Balance Sheet - Reverse Repo - TGA",
        "info_signals": "**Signals:**\nGreen: Rising Liq + Stable Vol\nRed: Falling Liq OR High Bond Vol (MOVE)",
        "market_snapshot": "Market Snapshot",
        "net_liquidity": "Net Liquidity",
        "sp500": "S&P 500",
        "vix": "VIX",
        "dxy": "DXY",
        "market_status": "Market Status",
        "signal": "Signal",
        "liq_trend": "Liq Trend",
        "vol": "Vol",
        "liquidity_vs_market": "Liquidity vs Market",
        "ai_analysis": "AI Macro Strategist Analysis",
        "generate_report": "Generate AI Report",
        "generating_spinner": "Consulting the Macro Strategist (Gemini 3 Pro)...",
        "loading_data": "Loading Market Data...",
        "error_loading": "Error loading data",
        "no_data": "No data loaded. Please check API keys and connectivity.",
        "error_analysis": "Error in analysis",
        "chart_net_liq": "Net Liquidity (B)",
        "chart_sp500": "S&P 500",
        "net_liq_axis": "Net Liquidity (Billions)",
        "sp500_axis": "S&P 500 Price",
        "chart_cb_liq": "Central Bank Liquidity",
        "chart_rates": "Policy Rates",
        "chart_market_health": "Market Health",
        "chart_cross_asset": "Cross Asset Correlation",
        "walcl": "Fed Assets",
        "rrp": "Reverse Repo (RRP)",
        "tga": "Treasury Account (TGA)",
        "sofr": "SOFR",
        "volume": "Volume",
    },
    "zh": {
        "title": "宏观流动性 AI 分析师",
        "settings": "设置",
        "lookback": "回顾周期 (天)",
        "refresh_data": "刷新数据",
        "info_formula": "**净流动性公式:**\n美联储资产负债表 - 逆回购 (RRP) - 财政部账户 (TGA)",
        "info_signals": "**信号:**\n绿色: 流动性上升 + 波动率稳定\n红色: 流动性下降 或 债券波动率高 (MOVE)",
        "market_snapshot": "市场快照",
        "net_liquidity": "净流动性",
        "sp500": "标普 500",
        "vix": "VIX (恐慌指数)",
        "dxy": "美元指数 (DXY)",
        "market_status": "市场状态",
        "signal": "信号",
        "liq_trend": "流动性趋势",
        "vol": "波动率",
        "liquidity_vs_market": "流动性 vs 市场走势",
        "ai_analysis": "AI 宏观策略师分析",
        "generate_report": "生成 AI 报告",
        "generating_spinner": "正在咨询宏观策略师 (Gemini 3 Pro)...",
        "loading_data": "正在加载市场数据...",
        "error_loading": "加载数据出错",
        "no_data": "未加载到数据。请检查 API 密钥和网络连接。",
        "error_analysis": "分析过程中出错",
        "chart_net_liq": "净流动性 (十亿)",
        "chart_sp500": "标普 500",
        "net_liq_axis": "净流动性 (十亿美元)",
        "sp500_axis": "标普 500 价格",
        "chart_cb_liq": "央行流动性",
        "chart_rates": "政策利率",
        "chart_market_health": "市场健康度",
        "chart_cross_asset": "跨资产相关性",
        "walcl": "美联储资产",
        "rrp": "逆回购 (RRP)",
        "tga": "财政部账户 (TGA)",
        "sofr": "隔夜利率 (SOFR)",
        "volume": "标普 500 成交量",
    }
}

def init_i18n():
    """Initialize session state for language."""
    if "language" not in st.session_state:
        st.session_state["language"] = "en"

def set_language(lang):
    """Set the current language."""
    st.session_state["language"] = lang

def get_current_language():
    """Get the current language code."""
    return st.session_state.get("language", "en")

def t(key):
    """Translate a key based on the current session language."""
    lang = get_current_language()
    return TRANSLATIONS.get(lang, TRANSLATIONS["en"]).get(key, key)

