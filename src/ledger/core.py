"""总资产账本 Facade —— 唯一读写接缝（ADR-0014/0017）。

所有写入口径（Agent 基金 JSON、手工股票/现金）与读出口径（总估值、
市场暴露、卫星占比、目标进度、基准偏离）都收敛在本类。注入 QuoteProvider
与显式日期，内核不触网、不读系统时钟。
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field, replace
from datetime import date, timedelta
from pathlib import Path

import yaml

from .db import connect
from .quotes import Quote, QuoteProvider

VALID_MARKETS = ("CN", "HK", "US")
VALID_CURRENCIES = ("CNY", "HKD", "USD")

SATELLITE_CAP = 0.35  # ADR-0018（supersede ADR-0002 的 25% 条款）
GOAL_REQUIRED_ANNUALIZED = 0.175  # ADR-0003：10 年 5 倍
XRAY_WEIGHT_TOLERANCE = 0.02
PRICE_STALE_DAYS = 7  # 报价超过 7 天未更新视为不新鲜（沿用 stale 模式）

# X-Ray 桶 → 市场暴露分类；权益桶用于卫星仓穿透口径
XRAY_EQUITY_BUCKETS = {"CN_equity": "CN", "HK_equity": "HK", "US_equity": "US"}
XRAY_NON_EQUITY_BUCKETS = {"bond", "cash", "other"}
XRAY_VALID_BUCKETS = set(XRAY_EQUITY_BUCKETS) | XRAY_NON_EQUITY_BUCKETS

FUND_JSON_SCHEMA_VERSION = 1  # ttfund 写入契约版本（开放项钉死点）


@dataclass(frozen=True)
class Transaction:
    occurred_on: date
    symbol: str
    delta_shares: float
    shares_after: float
    note: str


@dataclass(frozen=True)
class PositionValue:
    asset_type: str
    market: str
    symbol: str
    name: str
    quantity: float
    currency: str
    price: float
    value_cny: float
    stale: bool
    xray_as_of: date | None = None  # 基金穿透数据日期（季报滞后可见）


@dataclass(frozen=True)
class Snapshot:
    week_id: str
    as_of: date
    total_cny: float
    stale: bool
    positions: tuple[PositionValue, ...] = ()
    market_exposure: dict[str, float] = field(default_factory=dict)
    satellite_cny: float = 0.0
    satellite_ratio: float = 0.0


@dataclass(frozen=True)
class SatelliteStatus:
    """穿透后卫星仓占比对 35% 上限的距离（ADR-0018）。"""

    satellite_cny: float
    total_cny: float
    ratio: float
    cap: float
    breached: bool


@dataclass(frozen=True)
class GoalProgress:
    """目标进度：起点以来真实年化 vs 17.5% 需求线（ADR-0003）。

    annualized 为 None 表示起步期（< 30 天）不年化，避免伪精度。
    """

    start_date: date
    start_total_cny: float
    latest_date: date
    latest_total_cny: float
    total_return: float
    annualized: float | None
    required: float
    on_track: bool


MIN_ANNUALIZATION_DAYS = 30


@dataclass(frozen=True)
class BaselineDeviation:
    """某市场实际占比 vs 战略配置基准区间（ADR-0001/0003）。"""

    market: str
    actual: float
    min: float
    max: float
    status: str  # "within" | "above" | "below"


@dataclass(frozen=True)
class HoldingDetail:
    """单持仓明细：最新快照市值 + X-Ray 桶 + 主线标签（review 视图用）。"""

    asset_type: str
    market: str
    symbol: str
    name: str
    value_cny: float
    share: float  # 占总资产比例
    xray_buckets: dict[str, float] | None
    xray_as_of: date | None
    themes: tuple[tuple[str, bool], ...]  # (主线名, 是否卫星)


@dataclass(frozen=True)
class BucketEntry:
    """基准桶内的一条归属明细（跨桶基金拆分后按桶各计一条）。"""

    bucket: str  # CN/HK/US/CASH/BOND/OTHER/UNPENETRATED
    asset_type: str
    market: str
    symbol: str
    name: str
    value_cny: float  # 归入该桶的市值（拆分后口径）
    bucket_weight: float  # 该基金归入此桶的权重；直接持仓为 1.0
    is_split: bool  # 是否为跨桶基金的拆分条目


def _week_id(d: date) -> str:
    iso = d.isocalendar()
    return f"{iso.year}-W{iso.week:02d}"


class Ledger:
    def __init__(self, db_path: str | Path, baseline_path: str | Path | None = None) -> None:
        self._conn = connect(db_path)
        self._baseline_path = Path(baseline_path) if baseline_path else None

    # ------------------------------------------------------------------
    # 写路径：手工股票 / 现金
    # ------------------------------------------------------------------

    def upsert_stock_holding(
        self,
        market: str,
        symbol: str,
        name: str,
        shares: float,
        currency: str,
        as_of: date,
        cost_basis: float | None = None,
    ) -> None:
        if market not in VALID_MARKETS:
            raise ValueError(f"非法 market: {market!r}（允许 {VALID_MARKETS}）")
        self._validate_currency(currency)
        self._validate_quantity(shares, "shares")
        self._upsert_holding(
            asset_type="stock", market=market, symbol=symbol, name=name,
            quantity=shares, currency=currency, cost_basis=cost_basis,
            as_of=as_of, note="manual stock entry",
        )

    def upsert_cash_account(
        self,
        account: str,
        currency: str,
        balance: float,
        as_of: date,
    ) -> None:
        self._validate_currency(currency)
        self._validate_quantity(balance, "balance")
        self._upsert_holding(
            asset_type="cash", market="CASH", symbol=account, name=account,
            quantity=balance, currency=currency, cost_basis=None,
            as_of=as_of, note="cash balance update",
        )

    def _upsert_holding(
        self,
        asset_type: str,
        market: str,
        symbol: str,
        name: str,
        quantity: float,
        currency: str,
        cost_basis: float | None,
        as_of: date,
        note: str,
    ) -> None:
        with self._conn:
            row = self._conn.execute(
                "SELECT id, quantity FROM holdings"
                " WHERE asset_type = ? AND market = ? AND symbol = ?",
                (asset_type, market, symbol),
            ).fetchone()
            if row is None:
                cur = self._conn.execute(
                    "INSERT INTO holdings"
                    " (asset_type, market, symbol, name, quantity, currency,"
                    "  cost_basis, updated_on)"
                    " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (asset_type, market, symbol, name, quantity, currency,
                     cost_basis, as_of.isoformat()),
                )
                holding_id, previous = cur.lastrowid, 0.0
            else:
                holding_id, previous = row["id"], row["quantity"]
                self._conn.execute(
                    "UPDATE holdings SET quantity = ?, name = ?,"
                    " cost_basis = COALESCE(?, cost_basis), updated_on = ?"
                    " WHERE id = ?",
                    (quantity, name, cost_basis, as_of.isoformat(), holding_id),
                )
            delta = quantity - previous
            if delta != 0 or row is None:
                self._conn.execute(
                    "INSERT INTO transactions"
                    " (holding_id, occurred_on, delta_quantity, quantity_after, note)"
                    " VALUES (?, ?, ?, ?, ?)",
                    (holding_id, as_of.isoformat(), delta, quantity, note),
                )

    def list_transactions(self, symbol: str | None = None) -> list[Transaction]:
        sql = (
            "SELECT t.occurred_on, h.symbol, t.delta_quantity,"
            "       t.quantity_after, t.note"
            " FROM transactions t JOIN holdings h ON h.id = t.holding_id"
        )
        params: tuple = ()
        if symbol is not None:
            sql += " WHERE h.symbol = ?"
            params = (symbol,)
        sql += " ORDER BY t.id"
        rows = self._conn.execute(sql, params).fetchall()
        return [
            Transaction(
                occurred_on=date.fromisoformat(r["occurred_on"]),
                symbol=r["symbol"],
                delta_shares=r["delta_quantity"],
                shares_after=r["quantity_after"],
                note=r["note"],
            )
            for r in rows
        ]

    # ------------------------------------------------------------------
    # 写路径：主线映射（手工打标，ADR-0002；自动推断 P2 之后）
    # ------------------------------------------------------------------

    def set_theme_mapping(
        self,
        asset_type: str,
        market: str,
        symbol: str,
        theme: str,
        is_satellite: bool,
    ) -> None:
        if asset_type not in ("stock", "fund"):
            raise ValueError(f"主线映射只支持 stock/fund，收到 {asset_type!r}")
        held = self._conn.execute(
            "SELECT 1 FROM holdings"
            " WHERE asset_type = ? AND market = ? AND symbol = ?",
            (asset_type, market, symbol),
        ).fetchone()
        if held is None:
            raise ValueError(
                f"主线映射错位：账本中不存在 {asset_type} {symbol}，拒绝写入"
            )
        with self._conn:
            self._conn.execute(
                "INSERT INTO theme_map (asset_type, market, symbol, theme, is_satellite)"
                " VALUES (?, ?, ?, ?, ?)"
                " ON CONFLICT (asset_type, market, symbol, theme) DO UPDATE SET"
                " is_satellite = excluded.is_satellite",
                (asset_type, market, symbol, theme, int(is_satellite)),
            )

    def _is_satellite(self, asset_type: str, market: str, symbol: str) -> bool:
        row = self._conn.execute(
            "SELECT 1 FROM theme_map"
            " WHERE asset_type = ? AND market = ? AND symbol = ? AND is_satellite = 1",
            (asset_type, market, symbol),
        ).fetchone()
        return row is not None

    # ------------------------------------------------------------------
    # 写路径：Agent 基金 JSON（ttfund Skill 输出，ADR-0012/0014）
    # ------------------------------------------------------------------

    def import_fund_holdings(self, payload: dict, as_of: date) -> int:
        """导入 ttfund JSON：{schema_version, funds: [{code, name, shares,
        nav, nav_date?, currency?, market?}]}。返回导入基金数。"""
        version = payload.get("schema_version")
        if version != FUND_JSON_SCHEMA_VERSION:
            raise ValueError(
                f"不支持的 schema_version: {version!r}"
                f"（当前契约版本 {FUND_JSON_SCHEMA_VERSION}）"
            )
        funds = payload.get("funds")
        if not isinstance(funds, list):
            raise ValueError("payload.funds 必须是列表")
        for fund in funds:
            self._import_one_fund(fund, as_of)
        return len(funds)

    def _import_one_fund(self, fund: dict, as_of: date) -> None:
        code = self._require_str(fund, "code")
        name = self._require_str(fund, "name")
        shares = self._require_number(fund, "shares")
        nav = self._require_number(fund, "nav")
        if shares < 0:
            raise ValueError(f"基金 {code} shares 不可为负: {shares}")
        if nav <= 0:
            raise ValueError(f"基金 {code} nav 可疑（<= 0）: {nav}")
        currency = fund.get("currency", "CNY")
        self._validate_currency(currency)
        market = fund.get("market", "CN")
        if market not in VALID_MARKETS:
            raise ValueError(f"基金 {code} 非法 market: {market!r}")
        nav_date = (
            date.fromisoformat(fund["nav_date"])
            if fund.get("nav_date") else as_of
        )
        self._upsert_holding(
            asset_type="fund", market=market, symbol=code, name=name,
            quantity=shares, currency=currency, cost_basis=None,
            as_of=as_of, note="ttfund import",
        )
        self._remember_price("fund", code, Quote(nav, nav_date), currency)

    def record_fund_xray(
        self, fund_code: str, data_as_of: date, buckets: dict[str, float]
    ) -> None:
        """记录某基金某期季报的穿透结果（同基金同日期覆盖）。"""
        held = self._conn.execute(
            "SELECT 1 FROM holdings WHERE asset_type = 'fund' AND symbol = ?",
            (fund_code,),
        ).fetchone()
        if held is None:
            raise ValueError(
                f"穿透版本错位：账本中不存在基金 {fund_code}，拒绝写入"
            )
        if not buckets:
            raise ValueError("buckets 不可为空")
        for bucket, weight in buckets.items():
            if bucket not in XRAY_VALID_BUCKETS:
                raise ValueError(
                    f"未知 bucket: {bucket!r}（允许 {sorted(XRAY_VALID_BUCKETS)}）"
                )
            if weight < 0:
                raise ValueError(f"bucket {bucket} 权重不可为负: {weight}")
        total = sum(buckets.values())
        if abs(total - 1.0) > XRAY_WEIGHT_TOLERANCE:
            raise ValueError(
                f"穿透权重求和 {total:.4f} 越界"
                f"（容差 ±{XRAY_WEIGHT_TOLERANCE}）"
            )
        with self._conn:
            self._conn.execute(
                "DELETE FROM fund_xray WHERE fund_code = ? AND data_as_of = ?",
                (fund_code, data_as_of.isoformat()),
            )
            self._conn.executemany(
                "INSERT INTO fund_xray (fund_code, data_as_of, bucket, weight)"
                " VALUES (?, ?, ?, ?)",
                [
                    (fund_code, data_as_of.isoformat(), bucket, weight)
                    for bucket, weight in buckets.items()
                ],
            )

    def _latest_xray(self, fund_code: str) -> tuple[dict[str, float], date] | None:
        rows = self._conn.execute(
            "SELECT data_as_of, bucket, weight FROM fund_xray"
            " WHERE fund_code = ?"
            " ORDER BY data_as_of DESC",
            (fund_code,),
        ).fetchall()
        if not rows:
            return None
        latest = rows[0]["data_as_of"]
        buckets = {r["bucket"]: r["weight"] for r in rows if r["data_as_of"] == latest}
        return buckets, date.fromisoformat(latest)

    @staticmethod
    def _require_str(fund: dict, field_name: str) -> str:
        value = fund.get(field_name)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"基金记录缺少必填字段 {field_name}")
        return value.strip()

    @staticmethod
    def _require_number(fund: dict, field_name: str) -> float:
        value = fund.get(field_name)
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            raise ValueError(f"基金记录缺少必填字段 {field_name}")
        return float(value)

    # ------------------------------------------------------------------
    # 快照
    # ------------------------------------------------------------------

    def take_snapshot(self, as_of: date, quotes: QuoteProvider) -> Snapshot:
        holdings = self._conn.execute(
            "SELECT * FROM holdings ORDER BY id"
        ).fetchall()
        positions: list[PositionValue] = []
        any_stale = False
        for h in holdings:
            pos = self._value_holding(h, as_of, quotes)
            if pos.asset_type == "fund":
                xray = self._latest_xray(pos.symbol)
                if xray is not None:
                    pos = replace(pos, xray_as_of=xray[1])
            positions.append(pos)
            any_stale = any_stale or pos.stale

        total = sum(p.value_cny for p in positions)
        exposure: dict[str, float] = {}
        for p in positions:
            for category, value in self._exposure_split(p).items():
                exposure[category] = exposure.get(category, 0.0) + value

        satellite = sum(
            self._satellite_value(p)
            for p in positions
            if self._is_satellite(p.asset_type, p.market, p.symbol)
        )
        ratio = satellite / total if total > 0 else 0.0

        snap = Snapshot(
            week_id=_week_id(as_of),
            as_of=as_of,
            total_cny=total,
            stale=any_stale,
            positions=tuple(positions),
            market_exposure=exposure,
            satellite_cny=satellite,
            satellite_ratio=ratio,
        )
        self._persist_snapshot(snap)
        return snap

    def _satellite_value(self, p: PositionValue) -> float:
        """卫星口径市值：基金按权益暴露折算，未穿透基金保守按全额计。"""
        if p.asset_type != "fund":
            return p.value_cny
        xray = self._latest_xray(p.symbol)
        if xray is None:
            return p.value_cny
        buckets, _ = xray
        equity = sum(w for b, w in buckets.items() if b in XRAY_EQUITY_BUCKETS)
        return p.value_cny * equity

    def _exposure_split(self, p: PositionValue) -> dict[str, float]:
        """持仓市值 → 穿透后暴露分类（CN/HK/US/CASH/BOND/OTHER/UNPENETRATED）。"""
        if p.asset_type == "fund":
            xray = self._latest_xray(p.symbol)
            if xray is None:
                return {"UNPENETRATED": p.value_cny}
            buckets, _ = xray
            return {
                XRAY_EQUITY_BUCKETS.get(b, b.upper()): p.value_cny * w
                for b, w in buckets.items()
            }
        if p.asset_type == "cash":
            return {"CASH": p.value_cny}
        return {p.market: p.value_cny}

    def _value_holding(
        self, h: sqlite3.Row, as_of: date, quotes: QuoteProvider
    ) -> PositionValue:
        quote = self._lookup_quote(h, as_of, quotes)
        if quote is None:
            quote = self._last_price(h["asset_type"], h["symbol"])
        if quote is None:
            # 无报价且无历史价：计 0 并标记 stale（快照不断档）
            return PositionValue(
                asset_type=h["asset_type"], market=h["market"],
                symbol=h["symbol"], name=h["name"], quantity=h["quantity"],
                currency=h["currency"], price=0.0, value_cny=0.0, stale=True,
            )
        stale = quote.stale or (as_of - quote.quoted_on).days > PRICE_STALE_DAYS
        if not quote.stale:
            self._remember_price(h["asset_type"], h["symbol"], quote, h["currency"])

        fx = self._lookup_fx(h["currency"], as_of, quotes)
        if fx is not None:
            fx_rate = fx
            self._remember_price("fx", h["currency"], Quote(fx, as_of), "CNY")
        else:
            last_fx = self._last_price("fx", h["currency"])
            fx_rate = last_fx.price if last_fx else 0.0
            if last_fx is None or (as_of - last_fx.quoted_on).days > PRICE_STALE_DAYS:
                stale = True
        return PositionValue(
            asset_type=h["asset_type"], market=h["market"],
            symbol=h["symbol"], name=h["name"], quantity=h["quantity"],
            currency=h["currency"], price=quote.price,
            value_cny=h["quantity"] * quote.price * fx_rate, stale=stale,
        )

    def _lookup_quote(
        self, h: sqlite3.Row, as_of: date, quotes: QuoteProvider
    ) -> Quote | None:
        if h["asset_type"] == "cash":
            return Quote(price=1.0, quoted_on=as_of)
        if h["asset_type"] == "fund":
            return quotes.get_fund_nav(h["symbol"], as_of)
        return quotes.get_stock_price(h["symbol"], h["market"], as_of)

    def _lookup_fx(
        self, currency: str, as_of: date, quotes: QuoteProvider
    ) -> float | None:
        if currency == "CNY":
            return 1.0
        return quotes.get_fx_rate(currency, as_of)

    def _remember_price(
        self, asset_type: str, symbol: str, quote: Quote, currency: str
    ) -> None:
        # 注意：调用方不得在外层再包事务（本方法自提交，保证跨进程持久）
        with self._conn:
            self._conn.execute(
                "INSERT INTO last_prices (asset_type, symbol, price, currency, quoted_on)"
                " VALUES (?, ?, ?, ?, ?)"
                " ON CONFLICT (asset_type, symbol) DO UPDATE SET"
                " price = excluded.price, quoted_on = excluded.quoted_on",
                (asset_type, symbol, quote.price, currency,
                 quote.quoted_on.isoformat()),
            )

    def _last_price(self, asset_type: str, symbol: str) -> Quote | None:
        row = self._conn.execute(
            "SELECT price, quoted_on FROM last_prices"
            " WHERE asset_type = ? AND symbol = ?",
            (asset_type, symbol),
        ).fetchone()
        if row is None:
            return None
        return Quote(
            price=row["price"],
            quoted_on=date.fromisoformat(row["quoted_on"]),
        )

    def _persist_snapshot(self, snap: Snapshot) -> None:
        payload = {
            "positions": [
                {
                    "asset_type": p.asset_type, "market": p.market,
                    "symbol": p.symbol, "name": p.name, "quantity": p.quantity,
                    "currency": p.currency, "price": p.price,
                    "value_cny": p.value_cny, "stale": p.stale,
                    "xray_as_of": p.xray_as_of.isoformat() if p.xray_as_of else None,
                }
                for p in snap.positions
            ],
            "market_exposure": snap.market_exposure,
            "satellite_cny": snap.satellite_cny,
            "satellite_ratio": snap.satellite_ratio,
        }
        with self._conn:
            self._conn.execute(
                "INSERT INTO snapshots (week_id, as_of, total_cny, stale, payload)"
                " VALUES (?, ?, ?, ?, ?)"
                " ON CONFLICT (week_id) DO UPDATE SET"
                " as_of = excluded.as_of, total_cny = excluded.total_cny,"
                " stale = excluded.stale, payload = excluded.payload",
                (snap.week_id, snap.as_of.isoformat(), snap.total_cny,
                 int(snap.stale), json.dumps(payload, ensure_ascii=False)),
            )

    # ------------------------------------------------------------------
    # 读路径：最新快照 / 卫星状态（Streamlit 只读层消费）
    # ------------------------------------------------------------------

    def get_latest_snapshot(self) -> Snapshot | None:
        row = self._conn.execute(
            "SELECT * FROM snapshots ORDER BY as_of DESC LIMIT 1"
        ).fetchone()
        return self._snapshot_from_row(row) if row else None

    def get_snapshot_history(self) -> list[Snapshot]:
        rows = self._conn.execute(
            "SELECT * FROM snapshots ORDER BY as_of"
        ).fetchall()
        return [self._snapshot_from_row(r) for r in rows]

    def get_goal_progress(self) -> GoalProgress | None:
        """起点（首个快照）以来的真实年化 vs 17.5% 需求线。快照不足返回 None。"""
        history = self.get_snapshot_history()
        if len(history) < 2:
            return None
        start, latest = history[0], history[-1]
        if start.total_cny <= 0:
            return None
        total_return = latest.total_cny / start.total_cny - 1.0
        days = (latest.as_of - start.as_of).days
        if days >= MIN_ANNUALIZATION_DAYS:
            annualized: float | None = (1.0 + total_return) ** (365.25 / days) - 1.0
        else:
            annualized = None
        return GoalProgress(
            start_date=start.as_of,
            start_total_cny=start.total_cny,
            latest_date=latest.as_of,
            latest_total_cny=latest.total_cny,
            total_return=total_return,
            annualized=annualized,
            required=GOAL_REQUIRED_ANNUALIZED,
            on_track=annualized is not None and annualized >= GOAL_REQUIRED_ANNUALIZED,
        )

    def get_satellite_status(self) -> SatelliteStatus:
        snap = self.get_latest_snapshot()
        if snap is None:
            return SatelliteStatus(0.0, 0.0, 0.0, SATELLITE_CAP, breached=False)
        return SatelliteStatus(
            satellite_cny=snap.satellite_cny,
            total_cny=snap.total_cny,
            ratio=snap.satellite_ratio,
            cap=SATELLITE_CAP,
            breached=snap.satellite_ratio > SATELLITE_CAP,
        )

    @staticmethod
    def _snapshot_from_row(row: sqlite3.Row) -> Snapshot:
        payload = json.loads(row["payload"])
        positions = tuple(
            PositionValue(
                asset_type=p["asset_type"], market=p["market"],
                symbol=p["symbol"], name=p["name"], quantity=p["quantity"],
                currency=p["currency"], price=p["price"],
                value_cny=p["value_cny"], stale=p["stale"],
                xray_as_of=(
                    date.fromisoformat(p["xray_as_of"]) if p.get("xray_as_of") else None
                ),
            )
            for p in payload.get("positions", [])
        )
        return Snapshot(
            week_id=row["week_id"],
            as_of=date.fromisoformat(row["as_of"]),
            total_cny=row["total_cny"],
            stale=bool(row["stale"]),
            positions=positions,
            market_exposure=payload.get("market_exposure", {}),
            satellite_cny=payload.get("satellite_cny", 0.0),
            satellite_ratio=payload.get("satellite_ratio", 0.0),
        )

    # ------------------------------------------------------------------
    # 读路径：配置明细（review 穿透分类与卫星标签）
    # ------------------------------------------------------------------

    def get_allocation_detail(self) -> list[HoldingDetail]:
        """最新快照的逐持仓明细，join X-Ray 与主线映射。无快照返回空。"""
        snap = self.get_latest_snapshot()
        if snap is None:
            return []
        detail = []
        for p in snap.positions:
            xray = (
                self._latest_xray(p.symbol) if p.asset_type == "fund" else None
            )
            tags = tuple(
                (r["theme"], bool(r["is_satellite"]))
                for r in self._conn.execute(
                    "SELECT theme, is_satellite FROM theme_map"
                    " WHERE asset_type = ? AND market = ? AND symbol = ?"
                    " ORDER BY theme",
                    (p.asset_type, p.market, p.symbol),
                )
            )
            detail.append(HoldingDetail(
                asset_type=p.asset_type, market=p.market, symbol=p.symbol,
                name=p.name, value_cny=p.value_cny,
                share=p.value_cny / snap.total_cny if snap.total_cny > 0 else 0.0,
                xray_buckets=xray[0] if xray else None,
                xray_as_of=xray[1] if xray else None,
                themes=tags,
            ))
        return detail

    def get_bucket_breakdown(self) -> list[BucketEntry]:
        """最新快照按穿透口径归入基准桶的逐条明细；跨桶基金按权重拆分。"""
        snap = self.get_latest_snapshot()
        if snap is None:
            return []
        entries: list[BucketEntry] = []
        for p in snap.positions:
            if p.asset_type == "fund":
                xray = self._latest_xray(p.symbol)
                if xray is None:
                    entries.append(BucketEntry(
                        bucket="UNPENETRATED", asset_type=p.asset_type,
                        market=p.market, symbol=p.symbol, name=p.name,
                        value_cny=p.value_cny, bucket_weight=1.0, is_split=False,
                    ))
                    continue
                buckets, _ = xray
                is_split = len([w for w in buckets.values() if w > 0]) > 1
                for bucket, weight in buckets.items():
                    if weight <= 0:
                        continue
                    entries.append(BucketEntry(
                        bucket=XRAY_EQUITY_BUCKETS.get(bucket, bucket.upper()),
                        asset_type=p.asset_type, market=p.market,
                        symbol=p.symbol, name=p.name,
                        value_cny=p.value_cny * weight,
                        bucket_weight=weight, is_split=is_split,
                    ))
            elif p.asset_type == "cash":
                entries.append(BucketEntry(
                    bucket="CASH", asset_type=p.asset_type, market=p.market,
                    symbol=p.symbol, name=p.name, value_cny=p.value_cny,
                    bucket_weight=1.0, is_split=False,
                ))
            else:
                entries.append(BucketEntry(
                    bucket=p.market, asset_type=p.asset_type, market=p.market,
                    symbol=p.symbol, name=p.name, value_cny=p.value_cny,
                    bucket_weight=1.0, is_split=False,
                ))
        return entries

    # ------------------------------------------------------------------
    # 读路径：基准偏离（配置文件，支持未设定）
    # ------------------------------------------------------------------

    def _load_baseline(self) -> dict[str, dict[str, float]] | None:
        if self._baseline_path is None or not self._baseline_path.exists():
            return None
        data = yaml.safe_load(self._baseline_path.read_text(encoding="utf-8"))
        if not data:
            return None
        baseline = {}
        for market, rng in data.items():
            baseline[str(market)] = {
                "min": float(rng["min"]), "max": float(rng["max"]),
            }
        return baseline

    def get_baseline_deviation(self) -> list[BaselineDeviation] | None:
        """各市场实际占比 vs 基准区间；基准未设定或无快照时返回 None。"""
        baseline = self._load_baseline()
        snap = self.get_latest_snapshot()
        if baseline is None or snap is None or snap.total_cny <= 0:
            return None
        deviations = []
        for market, rng in baseline.items():
            actual = snap.market_exposure.get(market, 0.0) / snap.total_cny
            if actual > rng["max"]:
                status = "above"
            elif actual < rng["min"]:
                status = "below"
            else:
                status = "within"
            deviations.append(BaselineDeviation(
                market=market, actual=actual,
                min=rng["min"], max=rng["max"], status=status,
            ))
        return deviations

    # ------------------------------------------------------------------
    # 完整性校验（spec 故事 20：断档 / 穿透错位 / 汇率缺失）
    # ------------------------------------------------------------------

    def validate_integrity(self) -> list[str]:
        issues: list[str] = []
        issues.extend(self._check_snapshot_gaps())
        issues.extend(self._check_xray_coverage())
        issues.extend(self._check_fx_coverage())
        return issues

    def _check_snapshot_gaps(self) -> list[str]:
        weeks = [
            r["week_id"] for r in self._conn.execute(
                "SELECT DISTINCT week_id FROM snapshots ORDER BY week_id"
            )
        ]
        if len(weeks) < 2:
            return []
        present = set(weeks)
        first = date.fromisocalendar(*map(int, (weeks[0][0:4], weeks[0][6:8], 1)))
        last = date.fromisocalendar(*map(int, (weeks[-1][0:4], weeks[-1][6:8], 1)))
        missing = []
        cursor = first
        while cursor <= last:
            if _week_id(cursor) not in present:
                missing.append(_week_id(cursor))
            cursor += timedelta(weeks=1)
        if missing:
            return [f"快照断档：缺失 {len(missing)} 周（{', '.join(missing[:5])}…）"]
        return []

    def _check_xray_coverage(self) -> list[str]:
        rows = self._conn.execute(
            "SELECT symbol FROM holdings"
            " WHERE asset_type = 'fund' AND quantity > 0"
            " AND symbol NOT IN (SELECT DISTINCT fund_code FROM fund_xray)"
        ).fetchall()
        return [
            f"基金 {r['symbol']} 在持但缺少 X-Ray 穿透（暴露计入未穿透）"
            for r in rows
        ]

    def _check_fx_coverage(self) -> list[str]:
        rows = self._conn.execute(
            "SELECT DISTINCT currency FROM holdings"
            " WHERE currency != 'CNY' AND quantity > 0"
            " AND currency NOT IN"
            " (SELECT symbol FROM last_prices WHERE asset_type = 'fx')"
        ).fetchall()
        return [f"汇率缺失：{r['currency']} 从未成功取价" for r in rows]

    # ------------------------------------------------------------------
    # 校验
    # ------------------------------------------------------------------

    @staticmethod
    def _validate_currency(currency: str) -> None:
        if currency not in VALID_CURRENCIES:
            raise ValueError(
                f"非法 currency: {currency!r}（允许 {VALID_CURRENCIES}）"
            )

    @staticmethod
    def _validate_quantity(value: float, field_name: str) -> None:
        if value < 0:
            raise ValueError(f"{field_name} 不可为负: {value}")
