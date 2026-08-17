"""QDII 季报原文解析器测试：基准确诂 = 6 只基金季报手工核对值。

夹具为真实季报 pdftotext 文本的关键章节（tests/fixtures/xray/）。
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from src.ledger.xray_report import (
    XrayReportParseError,
    build_buckets,
    classify_fund_holding,
    parse_region_allocation,
    report_period,
)

FIXTURES = Path(__file__).parent / "fixtures" / "xray"


def load(code: str) -> str:
    return (FIXTURES / f"{code}_q2.txt").read_text(encoding="utf-8")


# 手工核对季报原文后的标准答案（2026Q2）
ORACLE = {
    "005698": {"CN_equity": 0.3661, "HK_equity": 0.2317, "US_equity": 0.2523,
               "other": 0.0101, "cash": 0.1398},
    "100055": {"HK_equity": 0.5031, "US_equity": 0.1785, "CN_equity": 0.1031,
               "other": 0.1455, "cash": 0.0698},
    "539002": {"US_equity": 0.5965, "other": 0.2195, "cash": 0.1840},
    "006373": {"US_equity": 0.7195, "other": 0.0874, "HK_equity": 0.0347,
               "CN_equity": 0.0114, "bond": 0.0696, "cash": 0.0774},
    "012920": {"US_equity": 0.4327, "CN_equity": 0.2854, "HK_equity": 0.0803,
               "other": 0.1241, "cash": 0.0775},
    "008253": {"US_equity": 0.8463, "HK_equity": 0.0257, "other": 0.0031,
               "cash": 0.1249},
}


@pytest.mark.parametrize("code", list(ORACLE))
def test_build_buckets_matches_hand_verified(code):
    buckets, as_of, notes = build_buckets(load(code))
    assert as_of == date(2026, 6, 30)
    expected = ORACLE[code]
    assert set(buckets) == set(expected), f"{code} 桶集合差异: {buckets} vs {expected}"
    for bucket, weight in expected.items():
        assert buckets[bucket] == pytest.approx(weight, abs=0.002), (
            f"{code} {bucket}: 解析 {buckets[bucket]} vs 手工核对 {weight}"
        )
    assert abs(sum(buckets.values()) - 1.0) <= 0.001


def test_region_layouts_row_and_column():
    # 行式（005698）与列式（012920）排版都应正确配对
    row_regions, _, _ = parse_region_allocation(load("005698"))
    assert row_regions["美国"] == pytest.approx(0.1666)
    assert row_regions["中国内地"] == pytest.approx(0.3661)
    col_regions, total, _ = parse_region_allocation(load("012920"))
    assert col_regions["美国"] == pytest.approx(0.4276)
    assert col_regions["韩国"] == pytest.approx(0.0350)
    assert total == pytest.approx(0.9174)


def test_cn_numeral_year_title():
    assert report_period("某某基金（QDII）二0二六年第2季度报告") == date(2026, 6, 30)


def test_no_region_section_raises():
    with pytest.raises(XrayReportParseError, match="地区分布节"):
        parse_region_allocation("5.1 报告期末基金资产组合情况\n无相关内容")


def test_fund_holding_classification():
    assert classify_fund_holding("Direxion Daily Semiconductor Bull 3X ETF") == ("US_equity", None)
    assert classify_fund_holding("iShares MSCI Taiwan ETF BlackRock")[0] == "other"
    assert classify_fund_holding("CSOP SK Hynix Daily 2x Leveraged")[0] == "other"
    bucket, note = classify_fund_holding("某未知海外基金 某公司")
    assert bucket == "other" and note is not None
