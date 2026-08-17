"""周度快照 job（ADR-0012 headless 入口，ADR-0007 周度快照）。

    uv run python -m jobs.weekly_snapshot [--as-of YYYY-MM-DD] [--db PATH]

职责仅限组装：现有取数层 → MarketQuoteProvider → Ledger Facade 打快照。
不含业务逻辑；由 Agent 仪式层或本地调度器触发。
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date

from dotenv import load_dotenv

from src.ledger import Ledger
from src.ledger.market_quotes import MarketQuoteProvider

DEFAULT_DB_PATH = "data_cache/ledger.db"
DEFAULT_BASELINE_PATH = "config/baseline.yaml"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="总资产账本周度快照")
    parser.add_argument("--as-of", help="快照日期 YYYY-MM-DD，默认今天")
    parser.add_argument("--db", default=DEFAULT_DB_PATH)
    parser.add_argument("--baseline", default=DEFAULT_BASELINE_PATH)
    args = parser.parse_args(argv)

    as_of = date.fromisoformat(args.as_of) if args.as_of else date.today()
    load_dotenv()
    ledger = Ledger(db_path=args.db, baseline_path=args.baseline)
    snap = ledger.take_snapshot(as_of=as_of, quotes=MarketQuoteProvider())
    print(json.dumps({
        "ok": True,
        "week_id": snap.week_id,
        "as_of": snap.as_of.isoformat(),
        "total_cny": round(snap.total_cny, 2),
        "stale": snap.stale,
        "market_exposure": {k: round(v, 2) for k, v in snap.market_exposure.items()},
        "satellite_ratio": round(snap.satellite_ratio, 4),
        "integrity_issues": ledger.validate_integrity(),
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
