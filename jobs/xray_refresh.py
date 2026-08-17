"""X-Ray 例行刷新 job：QDII 季报原文 → 桶提案 →（可选）经门面落库。

    uv run python -m jobs.xray_refresh            # 干跑：打印各基金桶提案与备注
    uv run python -m jobs.xray_refresh --write    # 经 Ledger Facade 校验后落库

口径（SOP）：QDII 以季报「地区分布」节为准（强制披露）；非 QDII/联接基金
无该节 → 跳过并保留现值，由 Agent 仪式层用前十外推法兜底（ttfund 通道）。
数字全程不经过 LLM——解析器确定性产出，Facade 做容差校验（ADR-0014）。
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path

from src.ledger import Ledger
from src.ledger.xray_report import XrayReportParseError, build_buckets

DEFAULT_DB_PATH = "data_cache/ledger.db"
_JJGG_API = "https://api.fund.eastmoney.com/f10/JJGG?callback=&fundcode={code}&pageIndex=1&pageSize=10&type=3"
_PDF_URL = "https://pdf.dfcfw.com/pdf/H2_{report_id}_1.pdf"
_UA = {"User-Agent": "Mozilla/5.0", "Referer": "https://fundf10.eastmoney.com/"}


def _http_get(url: str) -> bytes:
    req = urllib.request.Request(url, headers=_UA)
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read()


def find_latest_quarterly_report(fund_code: str) -> tuple[str, str] | None:
    """返回 (report_id, title)；无季报返回 None。"""
    data = json.loads(_http_get(_JJGG_API.format(code=fund_code)))
    for item in data.get("Data") or []:
        if "季度报告" in item.get("TITLE", ""):
            return item["ID"], item["TITLE"]
    return None


def download_report_text(report_id: str, workdir: Path) -> str:
    pdf = workdir / f"{report_id}.pdf"
    pdf.write_bytes(_http_get(_PDF_URL.format(report_id=report_id)))
    subprocess.run(
        ["pdftotext", str(pdf), str(pdf.with_suffix(".txt"))],
        check=True, capture_output=True,
    )
    return pdf.with_suffix(".txt").read_text(encoding="utf-8", errors="replace")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="QDII 季报原文 X-Ray 刷新")
    parser.add_argument("--db", default=DEFAULT_DB_PATH)
    parser.add_argument("--write", action="store_true", help="经门面校验后落库")
    parser.add_argument("--fund", help="只处理指定基金代码")
    args = parser.parse_args(argv)

    ledger = Ledger(db_path=args.db)
    funds = [
        (h["symbol"], h["name"]) for h in ledger._conn.execute(
            "SELECT symbol, name FROM holdings"
            " WHERE asset_type = 'fund' AND quantity > 0 ORDER BY symbol"
        )
        if args.fund is None or h["symbol"] == args.fund
    ]
    failures = 0
    with tempfile.TemporaryDirectory() as tmp:
        for code, name in funds:
            try:
                found = find_latest_quarterly_report(code)
                if found is None:
                    print(f"⏭  {code} {name}：无季报公告，保留现值")
                    continue
                report_id, title = found
                text = download_report_text(report_id, Path(tmp))
                buckets, as_of, notes = build_buckets(text)
            except (XrayReportParseError, subprocess.CalledProcessError,
                    json.JSONDecodeError, OSError) as exc:
                print(f"⏭  {code} {name}：{exc}（非 QDII 或排版未覆盖，保留现值）")
                continue
            print(f"📄 {code} {name}\n   {title}（{as_of}）")
            print(f"   {json.dumps(buckets, ensure_ascii=False)}")
            for note in notes:
                print(f"   ⚠️  {note}")
            if args.write:
                try:
                    ledger.record_fund_xray(code, as_of, buckets)
                    print("   ✅ 已落库")
                except ValueError as exc:
                    failures += 1
                    print(f"   ❌ 门面拒绝：{exc}")
    if not args.write:
        print("\n干跑模式：以上仅为提案，加 --write 经门面校验后落库。")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
