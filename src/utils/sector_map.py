"""
Static sector mapping for stock pool tickers.

SECTOR_MAP_ZH: Shenwan Level-1 industry names (Chinese mode)
SECTOR_MAP_EN: GICS sector names (English mode)
"""

from __future__ import annotations

from src.utils.i18n import t

# Shenwan Level-1 industry (申万一级行业) for A-shares, GICS for US/HK stocks
SECTOR_MAP_ZH: dict[str, str] = {
    # US stocks — 使用 GICS 中文对照
    "SNDK": "信息技术",
    "AMD": "信息技术",
    "MU": "信息技术",
    "QCOM": "信息技术",
    "LITE": "信息技术",
    "NVDA": "信息技术",
    "ARM": "信息技术",
    "AVGO": "信息技术",
    "MRVL": "信息技术",
    "STX": "信息技术",
    "TSEM": "信息技术",
    "BE": "公用事业",
    "NVT": "工业",
    "GOOG": "通信服务",
    "CRWV": "信息技术",
    # A-shares — 申万一级行业
    "300308_SZ": "通信",
    "688008_SH": "电子",
}

SECTOR_MAP_EN: dict[str, str] = {
    # US stocks — GICS standard names
    "SNDK": "Semiconductors",
    "AMD": "Semiconductors",
    "MU": "Semiconductors",
    "QCOM": "Semiconductors",
    "LITE": "Technology Hardware",
    "NVDA": "Semiconductors",
    "ARM": "Semiconductors",
    "AVGO": "Semiconductors",
    "MRVL": "Semiconductors",
    "STX": "Technology Hardware",
    "TSEM": "Semiconductors",
    "BE": "Utilities",
    "NVT": "Industrials",
    "GOOG": "Communication Services",
    "CRWV": "Information Technology",
    # A-shares — Shenwan English equivalent
    "300308_SZ": "Telecommunications",
    "688008_SH": "Electronics",
}


def get_sector(ticker: str, lang: str) -> str:
    """Return the standardized sector name for a ticker in the given language.

    Falls back to t("sector_unknown") when the ticker is not in the mapping.
    """
    mapping = SECTOR_MAP_ZH if lang == "zh" else SECTOR_MAP_EN
    return mapping.get(ticker, t("sector_unknown"))
