"""账本 CLI 写入壳（ADR-0014：Agent 经此写账本，不碰数据库文件）。

用法（repo 根目录）：
    uv run python -m src.ledger.cli import-funds --file holdings.json
    uv run python -m src.ledger.cli upsert-stock --market US --symbol AAPL \
        --name Apple --shares 10 --currency USD
    uv run python -m src.ledger.cli upsert-cash --account 港币现金 \
        --currency HKD --balance 10000
    uv run python -m src.ledger.cli xray --fund 016532 --data-as-of 2026-06-30 \
        --buckets '{"US_equity": 0.95, "cash": 0.05}'
    uv run python -m src.ledger.cli tag --asset-type stock --market US \
        --symbol NVDA --theme "AI 算力" --satellite
    uv run python -m src.ledger.cli validate

全部输出 JSON 到 stdout；校验失败打印错误到 stderr 并以 exit 2 退出。
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

from .core import Ledger

DEFAULT_DB_PATH = "data_cache/ledger.db"
DEFAULT_BASELINE_PATH = "config/baseline.yaml"


def _read_json_arg(value: str | None, file: str | None) -> dict:
    if file:
        return json.loads(Path(file).read_text(encoding="utf-8"))
    if value:
        return json.loads(value)
    raise ValueError("需要 --json 或 --file 之一")


def _parse_date(value: str | None) -> date:
    # CLI 壳允许读系统时钟；内核永远收显式日期
    return date.fromisoformat(value) if value else date.today()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ledger", description="总资产账本写入接口")
    parser.add_argument("--db", default=DEFAULT_DB_PATH, help="SQLite 路径")
    parser.add_argument("--baseline", default=DEFAULT_BASELINE_PATH, help="基准配置路径")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("import-funds", help="导入 ttfund 基金持仓 JSON")
    p.add_argument("--json", help="JSON 字符串")
    p.add_argument("--file", help="JSON 文件路径")
    p.add_argument("--as-of", help="YYYY-MM-DD，默认今天")

    p = sub.add_parser("upsert-stock", help="录入/更新股票持仓")
    p.add_argument("--market", required=True, choices=["CN", "HK", "US"])
    p.add_argument("--symbol", required=True)
    p.add_argument("--name", required=True)
    p.add_argument("--shares", required=True, type=float)
    p.add_argument("--currency", required=True, choices=["CNY", "HKD", "USD"])
    p.add_argument("--cost-basis", type=float)
    p.add_argument("--as-of")

    p = sub.add_parser("upsert-cash", help="登记/更新现金账户")
    p.add_argument("--account", required=True)
    p.add_argument("--currency", required=True, choices=["CNY", "HKD", "USD"])
    p.add_argument("--balance", required=True, type=float)
    p.add_argument("--as-of")

    p = sub.add_parser("xray", help="记录基金 X-Ray 穿透结果")
    p.add_argument("--fund", required=True)
    p.add_argument("--data-as-of", required=True, help="穿透数据日期 YYYY-MM-DD")
    p.add_argument("--buckets", required=True,
                   help='JSON，如 {"US_equity": 0.95, "cash": 0.05}')

    p = sub.add_parser("tag", help="主线标签（手工打标）")
    p.add_argument("--asset-type", required=True, choices=["stock", "fund"])
    p.add_argument("--market", required=True, choices=["CN", "HK", "US"])
    p.add_argument("--symbol", required=True)
    p.add_argument("--theme", required=True)
    p.add_argument("--satellite", action="store_true", help="标记为卫星仓")

    sub.add_parser("validate", help="账本完整性校验")
    sub.add_parser("review", help="配置明细（市值/占比/穿透桶/主线标签，只读）")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    ledger = Ledger(db_path=args.db, baseline_path=args.baseline)
    try:
        if args.command == "import-funds":
            payload = _read_json_arg(args.json, args.file)
            count = ledger.import_fund_holdings(payload, as_of=_parse_date(args.as_of))
            result = {"ok": True, "imported": count}
        elif args.command == "upsert-stock":
            ledger.upsert_stock_holding(
                market=args.market, symbol=args.symbol, name=args.name,
                shares=args.shares, currency=args.currency,
                cost_basis=args.cost_basis, as_of=_parse_date(args.as_of),
            )
            result = {"ok": True, "symbol": args.symbol, "shares": args.shares}
        elif args.command == "upsert-cash":
            ledger.upsert_cash_account(
                account=args.account, currency=args.currency,
                balance=args.balance, as_of=_parse_date(args.as_of),
            )
            result = {"ok": True, "account": args.account, "balance": args.balance}
        elif args.command == "xray":
            ledger.record_fund_xray(
                fund_code=args.fund,
                data_as_of=date.fromisoformat(args.data_as_of),
                buckets=json.loads(args.buckets),
            )
            result = {"ok": True, "fund": args.fund, "data_as_of": args.data_as_of}
        elif args.command == "tag":
            ledger.set_theme_mapping(
                asset_type=args.asset_type, market=args.market,
                symbol=args.symbol, theme=args.theme,
                is_satellite=args.satellite,
            )
            result = {"ok": True, "symbol": args.symbol, "theme": args.theme}
        elif args.command == "validate":
            result = {"ok": True, "issues": ledger.validate_integrity()}
        elif args.command == "review":
            result = {"ok": True, "holdings": [
                {
                    "asset_type": d.asset_type, "market": d.market,
                    "symbol": d.symbol, "name": d.name,
                    "value_cny": round(d.value_cny, 2),
                    "share": round(d.share, 4),
                    "xray_buckets": d.xray_buckets,
                    "xray_as_of": d.xray_as_of.isoformat() if d.xray_as_of else None,
                    "themes": [
                        {"theme": th, "is_satellite": sat}
                        for th, sat in d.themes
                    ],
                }
                for d in ledger.get_allocation_detail()
            ]}
        else:  # pragma: no cover - argparse 已保证
            raise ValueError(f"未知命令 {args.command}")
    except (ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False),
              file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
