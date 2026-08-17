"""报价提供者接缝：测试注入静态数据，生产实现组装现有取数层。

汇率语义：1 单位外币 = fx 人民币（如 USD → 7.2）。CNY 恒为 1.0。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Protocol


@dataclass(frozen=True)
class Quote:
    """一次有效报价。stale=True 表示最近有效价而非当日价。"""

    price: float
    quoted_on: date
    stale: bool = False


class QuoteProvider(Protocol):
    """账本估值所需的全部外部报价。缺失返回 None，由账本决定降级策略。"""

    def get_stock_price(self, symbol: str, market: str, as_of: date) -> Quote | None: ...

    def get_fund_nav(self, fund_code: str, as_of: date) -> Quote | None: ...

    def get_fx_rate(self, currency: str, as_of: date) -> float | None: ...


class StaticQuoteProvider:
    """测试与脚本用的静态报价源。"""

    def __init__(
        self,
        prices: dict[str, float | Quote] | None = None,
        navs: dict[str, float | Quote] | None = None,
        fx: dict[str, float] | None = None,
    ) -> None:
        self._prices = prices or {}
        self._navs = navs or {}
        self._fx = fx or {}

    @staticmethod
    def _to_quote(value: float | Quote, as_of: date) -> Quote:
        if isinstance(value, Quote):
            return value
        return Quote(price=value, quoted_on=as_of)

    def get_stock_price(self, symbol: str, market: str, as_of: date) -> Quote | None:
        value = self._prices.get(symbol)
        return None if value is None else self._to_quote(value, as_of)

    def get_fund_nav(self, fund_code: str, as_of: date) -> Quote | None:
        value = self._navs.get(fund_code)
        return None if value is None else self._to_quote(value, as_of)

    def get_fx_rate(self, currency: str, as_of: date) -> float | None:
        return self._fx.get(currency)
