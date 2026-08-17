"""生产 QuoteProvider：组装现有取数层（ADR-0012，jobs 专用）。

- 股票价格：复用 `src/data/stock_daily_fetcher.fetch_daily_bars`
  （ETL-on-demand，A 股 Tushare / 美股 yfinance；港股暂不支持 → None 走降级）
- 汇率：yfinance `USDCNY=X` / `HKDCNY=X`（开放项的钉死实现）
- 基金净值：永远返回 None —— 基金净值只经 ttfund 写入路径进账本，
  内核自动降级到最近导入净值（ADR-0012：不把天天基金重实现为 Python 客户端）

import 边界（ADR-0017）：只依赖 src/data，不依赖 src/ui / src/portfolio。
"""

from __future__ import annotations

import logging
from datetime import date
from types import SimpleNamespace

from ..data.stock_daily_fetcher import fetch_daily_bars
from .quotes import Quote

logger = logging.getLogger(__name__)

_MARKET_LABEL = {"CN": "A股", "US": "美股", "HK": "港股"}
_FX_TICKER = {"USD": "USDCNY=X", "HKD": "HKDCNY=X"}


class MarketQuoteProvider:
    """现有取数层 → QuoteProvider 协议的适配器。"""

    def get_stock_price(self, symbol: str, market: str, as_of: date) -> Quote | None:
        if market == "HK":
            # stock_daily_fetcher 不支持港股；yfinance 兜底（0700.HK 形式）
            return self._yf_last_close(f"{symbol.lstrip('0').zfill(4)}.HK")
        label = _MARKET_LABEL.get(market)
        if label is None:
            return None
        # duck-typed StockPoolItem，避免 import src/portfolio（边界规则）
        item = SimpleNamespace(ticker=self._cn_ticker(symbol) if market == "CN" else symbol,
                               market=label)
        try:
            df, stale = fetch_daily_bars(item)
        except Exception as exc:  # 取数失败不崩溃，走最近有效价
            logger.warning("fetch_daily_bars failed for %s: %s", symbol, exc)
            return None
        if df is None or df.empty:
            return None
        return Quote(
            price=float(df["close"].iloc[-1]),
            quoted_on=df.index[-1].date(),
            stale=stale,
        )

    @staticmethod
    def _cn_ticker(symbol: str) -> str:
        """裸 6 位代码补 Tushare 交易所后缀（60/68→SH，其余→SZ）；已带后缀原样返回。"""
        if "." in symbol or "_" in symbol:
            return symbol
        return f"{symbol}.SH" if symbol[:2] in ("60", "68") else f"{symbol}.SZ"

    @staticmethod
    def _yf_last_close(ticker: str) -> Quote | None:
        try:
            import yfinance as yf

            data = yf.download(
                ticker, period="5d", progress=False,
                auto_adjust=False, multi_level_index=False,
            )
        except Exception as exc:
            logger.warning("yfinance fetch failed for %s: %s", ticker, exc)
            return None
        if data is None or data.empty:
            return None
        return Quote(
            price=float(data["Close"].iloc[-1]),
            quoted_on=data.index[-1].date(),
        )

    def get_fund_nav(self, fund_code: str, as_of: date) -> Quote | None:
        return None  # 基金净值只来自 ttfund 写入路径

    def get_fx_rate(self, currency: str, as_of: date) -> float | None:
        ticker = _FX_TICKER.get(currency)
        if ticker is None:
            return None
        try:
            import yfinance as yf

            data = yf.download(
                ticker, period="5d", progress=False,
                auto_adjust=False, multi_level_index=False,
            )
        except Exception as exc:
            logger.warning("yfinance fx fetch failed for %s: %s", ticker, exc)
            return None
        if data is None or data.empty:
            return None
        return float(data["Close"].iloc[-1])
