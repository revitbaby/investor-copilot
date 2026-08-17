"""
总资产账本（Ledger Facade）行为测试。

唯一被测接缝：Ledger Facade。测试注入构造的 QuoteProvider 与显式日期，
不走网络、不读系统时间。断言业务事实，不断言表结构。
"""

from __future__ import annotations

from datetime import date

import pytest

from src.ledger import Ledger, Quote, StaticQuoteProvider


def make_quotes(prices=None, navs=None, fx=None):
    return StaticQuoteProvider(prices=prices or {}, navs=navs or {}, fx=fx or {})


def fund_payload(**fund_kwargs):
    fund = {
        "code": "016532",
        "name": "某纳指QDII",
        "shares": 1000.0,
        "nav": 1.5,
        "nav_date": "2026-08-09",
        "currency": "CNY",
    }
    fund.update(fund_kwargs)
    return {"schema_version": 1, "funds": [fund]}


class TestStockAndCashValuation:
    """股票/现金录入后，快照给出人民币总估值（多币种折算）。"""

    def test_single_us_stock_valued_in_cny(self, tmp_path):
        ledger = Ledger(db_path=tmp_path / "ledger.db")
        ledger.upsert_stock_holding(
            market="US", symbol="AAPL", name="Apple",
            shares=10, currency="USD", as_of=date(2026, 8, 10),
        )
        snap = ledger.take_snapshot(
            as_of=date(2026, 8, 10),
            quotes=make_quotes(prices={"AAPL": 200.0}, fx={"USD": 7.2}),
        )
        assert snap.total_cny == pytest.approx(10 * 200.0 * 7.2)

    def test_multi_market_multi_currency_total(self, tmp_path):
        ledger = Ledger(db_path=tmp_path / "ledger.db")
        ledger.upsert_stock_holding(
            market="CN", symbol="600519", name="贵州茅台",
            shares=100, currency="CNY", as_of=date(2026, 8, 10),
        )
        ledger.upsert_stock_holding(
            market="HK", symbol="00700", name="腾讯控股",
            shares=200, currency="HKD", as_of=date(2026, 8, 10),
        )
        ledger.upsert_cash_account(
            account="港币现金", currency="HKD", balance=10000.0,
            as_of=date(2026, 8, 10),
        )
        snap = ledger.take_snapshot(
            as_of=date(2026, 8, 10),
            quotes=make_quotes(
                prices={"600519": 1500.0, "00700": 380.0},
                fx={"HKD": 0.92},
            ),
        )
        expected = 100 * 1500.0 + 200 * 380.0 * 0.92 + 10000.0 * 0.92
        assert snap.total_cny == pytest.approx(expected)

    def test_cny_needs_no_fx_rate(self, tmp_path):
        ledger = Ledger(db_path=tmp_path / "ledger.db")
        ledger.upsert_cash_account(
            account="人民币现金", currency="CNY", balance=50000.0,
            as_of=date(2026, 8, 10),
        )
        snap = ledger.take_snapshot(
            as_of=date(2026, 8, 10), quotes=make_quotes(),
        )
        assert snap.total_cny == pytest.approx(50000.0)

    def test_empty_ledger_snapshots_zero(self, tmp_path):
        ledger = Ledger(db_path=tmp_path / "ledger.db")
        snap = ledger.take_snapshot(
            as_of=date(2026, 8, 10), quotes=make_quotes(),
        )
        assert snap.total_cny == pytest.approx(0.0)

    def test_holding_change_leaves_transaction_trail(self, tmp_path):
        ledger = Ledger(db_path=tmp_path / "ledger.db")
        ledger.upsert_stock_holding(
            market="US", symbol="AAPL", name="Apple",
            shares=10, currency="USD", as_of=date(2026, 8, 1),
        )
        ledger.upsert_stock_holding(
            market="US", symbol="AAPL", name="Apple",
            shares=15, currency="USD", as_of=date(2026, 8, 10),
        )
        txns = ledger.list_transactions(symbol="AAPL")
        assert len(txns) == 2
        assert txns[0].delta_shares == pytest.approx(10)
        assert txns[1].delta_shares == pytest.approx(5)
        assert txns[1].shares_after == pytest.approx(15)

    def test_invalid_currency_rejected(self, tmp_path):
        ledger = Ledger(db_path=tmp_path / "ledger.db")
        with pytest.raises(ValueError, match="currency"):
            ledger.upsert_stock_holding(
                market="US", symbol="AAPL", name="Apple",
                shares=10, currency="EUR", as_of=date(2026, 8, 10),
            )

    def test_negative_shares_rejected(self, tmp_path):
        ledger = Ledger(db_path=tmp_path / "ledger.db")
        with pytest.raises(ValueError, match="shares"):
            ledger.upsert_stock_holding(
                market="US", symbol="AAPL", name="Apple",
                shares=-5, currency="USD", as_of=date(2026, 8, 10),
            )


class TestFundImport:
    """Agent 经 ttfund JSON 写入基金持仓与净值（ADR-0014：不写库文件）。"""

    def test_imported_fund_valued_by_imported_nav(self, tmp_path):
        ledger = Ledger(db_path=tmp_path / "ledger.db")
        ledger.import_fund_holdings(fund_payload(), as_of=date(2026, 8, 10))
        snap = ledger.take_snapshot(
            as_of=date(2026, 8, 10), quotes=make_quotes(),
        )
        assert snap.total_cny == pytest.approx(1000.0 * 1.5)
        assert not snap.stale

    def test_fund_import_leaves_transaction_trail(self, tmp_path):
        ledger = Ledger(db_path=tmp_path / "ledger.db")
        ledger.import_fund_holdings(fund_payload(), as_of=date(2026, 8, 10))
        txns = ledger.list_transactions(symbol="016532")
        assert len(txns) == 1
        assert txns[0].delta_shares == pytest.approx(1000.0)

    def test_rejects_wrong_schema_version(self, tmp_path):
        ledger = Ledger(db_path=tmp_path / "ledger.db")
        payload = fund_payload()
        payload["schema_version"] = 99
        with pytest.raises(ValueError, match="schema_version"):
            ledger.import_fund_holdings(payload, as_of=date(2026, 8, 10))

    def test_rejects_missing_required_field(self, tmp_path):
        ledger = Ledger(db_path=tmp_path / "ledger.db")
        payload = fund_payload()
        del payload["funds"][0]["shares"]
        with pytest.raises(ValueError, match="shares"):
            ledger.import_fund_holdings(payload, as_of=date(2026, 8, 10))

    def test_rejects_non_positive_nav(self, tmp_path):
        ledger = Ledger(db_path=tmp_path / "ledger.db")
        with pytest.raises(ValueError, match="nav"):
            ledger.import_fund_holdings(
                fund_payload(nav=0), as_of=date(2026, 8, 10),
            )

    def test_rejects_negative_shares(self, tmp_path):
        ledger = Ledger(db_path=tmp_path / "ledger.db")
        with pytest.raises(ValueError, match="shares"):
            ledger.import_fund_holdings(
                fund_payload(shares=-1), as_of=date(2026, 8, 10),
            )

    def test_stale_when_nav_too_old(self, tmp_path):
        ledger = Ledger(db_path=tmp_path / "ledger.db")
        ledger.import_fund_holdings(
            fund_payload(nav_date="2026-07-01"), as_of=date(2026, 7, 1),
        )
        snap = ledger.take_snapshot(
            as_of=date(2026, 8, 10), quotes=make_quotes(),
        )
        assert snap.total_cny == pytest.approx(1000.0 * 1.5)  # 用最近有效价
        assert snap.stale


class TestFundXRay:
    """X-Ray 穿透后，市场暴露反映真实暴露而非账户表面分类。"""

    def test_qdii_penetrates_to_us_exposure(self, tmp_path):
        ledger = Ledger(db_path=tmp_path / "ledger.db")
        ledger.import_fund_holdings(fund_payload(), as_of=date(2026, 8, 10))
        ledger.record_fund_xray(
            fund_code="016532",
            data_as_of=date(2026, 6, 30),
            buckets={"US_equity": 0.95, "cash": 0.05},
        )
        snap = ledger.take_snapshot(
            as_of=date(2026, 8, 10), quotes=make_quotes(),
        )
        assert snap.market_exposure["US"] == pytest.approx(1500.0 * 0.95)
        assert snap.market_exposure["CASH"] == pytest.approx(1500.0 * 0.05)
        assert "CN" not in snap.market_exposure

    def test_fund_without_xray_counts_as_unpenetrated(self, tmp_path):
        ledger = Ledger(db_path=tmp_path / "ledger.db")
        ledger.import_fund_holdings(fund_payload(), as_of=date(2026, 8, 10))
        snap = ledger.take_snapshot(
            as_of=date(2026, 8, 10), quotes=make_quotes(),
        )
        assert snap.market_exposure["UNPENETRATED"] == pytest.approx(1500.0)

    def test_xray_data_date_visible_in_snapshot(self, tmp_path):
        ledger = Ledger(db_path=tmp_path / "ledger.db")
        ledger.import_fund_holdings(fund_payload(), as_of=date(2026, 8, 10))
        ledger.record_fund_xray(
            fund_code="016532",
            data_as_of=date(2026, 6, 30),
            buckets={"US_equity": 0.95, "cash": 0.05},
        )
        snap = ledger.take_snapshot(
            as_of=date(2026, 8, 10), quotes=make_quotes(),
        )
        fund_pos = next(p for p in snap.positions if p.asset_type == "fund")
        assert fund_pos.xray_as_of == date(2026, 6, 30)

    def test_rejects_weight_sum_out_of_tolerance(self, tmp_path):
        ledger = Ledger(db_path=tmp_path / "ledger.db")
        ledger.import_fund_holdings(fund_payload(), as_of=date(2026, 8, 10))
        with pytest.raises(ValueError, match="权重"):
            ledger.record_fund_xray(
                fund_code="016532",
                data_as_of=date(2026, 6, 30),
                buckets={"US_equity": 0.95, "cash": 0.25},
            )

    def test_rejects_unknown_bucket(self, tmp_path):
        ledger = Ledger(db_path=tmp_path / "ledger.db")
        ledger.import_fund_holdings(fund_payload(), as_of=date(2026, 8, 10))
        with pytest.raises(ValueError, match="bucket"):
            ledger.record_fund_xray(
                fund_code="016532",
                data_as_of=date(2026, 6, 30),
                buckets={"火星_equity": 1.0},
            )

    def test_rejects_xray_for_fund_not_held(self, tmp_path):
        """穿透版本错位：账本里没有的基金不接受穿透结果。"""
        ledger = Ledger(db_path=tmp_path / "ledger.db")
        with pytest.raises(ValueError, match="016532"):
            ledger.record_fund_xray(
                fund_code="016532",
                data_as_of=date(2026, 6, 30),
                buckets={"US_equity": 1.0},
            )

    def test_latest_xray_version_wins(self, tmp_path):
        ledger = Ledger(db_path=tmp_path / "ledger.db")
        ledger.import_fund_holdings(fund_payload(), as_of=date(2026, 8, 10))
        ledger.record_fund_xray(
            fund_code="016532", data_as_of=date(2026, 3, 31),
            buckets={"CN_equity": 1.0},
        )
        ledger.record_fund_xray(
            fund_code="016532", data_as_of=date(2026, 6, 30),
            buckets={"US_equity": 1.0},
        )
        snap = ledger.take_snapshot(
            as_of=date(2026, 8, 10), quotes=make_quotes(),
        )
        assert snap.market_exposure["US"] == pytest.approx(1500.0)
        assert "CN" not in snap.market_exposure


class TestSatelliteRatio:
    """卫星仓真实占比 = Σ(卫星直接持仓 + 卫星基金市值 × 权益暴露) ÷ 总资产。"""

    def test_satellite_stock_counted_at_full_value(self, tmp_path):
        ledger = Ledger(db_path=tmp_path / "ledger.db")
        ledger.upsert_stock_holding(
            market="US", symbol="NVDA", name="英伟达",
            shares=10, currency="USD", as_of=date(2026, 8, 10),
        )
        ledger.upsert_cash_account(
            account="人民币现金", currency="CNY", balance=64000.0,
            as_of=date(2026, 8, 10),
        )
        ledger.set_theme_mapping(
            asset_type="stock", market="US", symbol="NVDA",
            theme="AI 算力", is_satellite=True,
        )
        quotes = make_quotes(prices={"NVDA": 100.0}, fx={"USD": 8.0})
        snap = ledger.take_snapshot(as_of=date(2026, 8, 10), quotes=quotes)
        # NVDA = 10 × 100 × 8 = 8000；总资产 72000
        assert snap.satellite_cny == pytest.approx(8000.0)
        assert snap.satellite_ratio == pytest.approx(8000.0 / 72000.0)

    def test_satellite_fund_counted_times_equity_exposure(self, tmp_path):
        ledger = Ledger(db_path=tmp_path / "ledger.db")
        ledger.import_fund_holdings(fund_payload(), as_of=date(2026, 8, 10))
        ledger.record_fund_xray(
            fund_code="016532", data_as_of=date(2026, 6, 30),
            buckets={"US_equity": 0.8, "bond": 0.15, "cash": 0.05},
        )
        ledger.set_theme_mapping(
            asset_type="fund", market="CN", symbol="016532",
            theme="AI 算力", is_satellite=True,
        )
        snap = ledger.take_snapshot(
            as_of=date(2026, 8, 10), quotes=make_quotes(),
        )
        assert snap.satellite_cny == pytest.approx(1500.0 * 0.8)

    def test_untagged_holdings_not_counted(self, tmp_path):
        ledger = Ledger(db_path=tmp_path / "ledger.db")
        ledger.upsert_stock_holding(
            market="US", symbol="NVDA", name="英伟达",
            shares=10, currency="USD", as_of=date(2026, 8, 10),
        )
        quotes = make_quotes(prices={"NVDA": 100.0}, fx={"USD": 8.0})
        snap = ledger.take_snapshot(as_of=date(2026, 8, 10), quotes=quotes)
        assert snap.satellite_cny == pytest.approx(0.0)

    def test_satellite_fund_without_xray_counted_conservatively(self, tmp_path):
        """未穿透的卫星基金按 100% 计入（风控口径宁高勿低）。"""
        ledger = Ledger(db_path=tmp_path / "ledger.db")
        ledger.import_fund_holdings(fund_payload(), as_of=date(2026, 8, 10))
        ledger.set_theme_mapping(
            asset_type="fund", market="CN", symbol="016532",
            theme="AI 算力", is_satellite=True,
        )
        snap = ledger.take_snapshot(
            as_of=date(2026, 8, 10), quotes=make_quotes(),
        )
        assert snap.satellite_cny == pytest.approx(1500.0)

    def test_status_flags_breach_of_35pct_cap(self, tmp_path):
        ledger = Ledger(db_path=tmp_path / "ledger.db")
        ledger.upsert_stock_holding(
            market="US", symbol="NVDA", name="英伟达",
            shares=10, currency="USD", as_of=date(2026, 8, 10),
        )
        ledger.set_theme_mapping(
            asset_type="stock", market="US", symbol="NVDA",
            theme="AI 算力", is_satellite=True,
        )
        quotes = make_quotes(prices={"NVDA": 100.0}, fx={"USD": 8.0})
        ledger.take_snapshot(as_of=date(2026, 8, 10), quotes=quotes)
        status = ledger.get_satellite_status()
        assert status.ratio == pytest.approx(1.0)
        assert status.cap == pytest.approx(0.35)
        assert status.breached

    def test_theme_tag_without_satellite_flag_not_counted(self, tmp_path):
        ledger = Ledger(db_path=tmp_path / "ledger.db")
        ledger.upsert_stock_holding(
            market="US", symbol="NVDA", name="英伟达",
            shares=10, currency="USD", as_of=date(2026, 8, 10),
        )
        ledger.set_theme_mapping(
            asset_type="stock", market="US", symbol="NVDA",
            theme="AI 算力", is_satellite=False,
        )
        quotes = make_quotes(prices={"NVDA": 100.0}, fx={"USD": 8.0})
        snap = ledger.take_snapshot(as_of=date(2026, 8, 10), quotes=quotes)
        assert snap.satellite_cny == pytest.approx(0.0)

    def test_rejects_mapping_for_unknown_holding(self, tmp_path):
        ledger = Ledger(db_path=tmp_path / "ledger.db")
        with pytest.raises(ValueError, match="NVDA"):
            ledger.set_theme_mapping(
                asset_type="stock", market="US", symbol="NVDA",
                theme="AI 算力", is_satellite=True,
            )

    def test_empty_ledger_satellite_ratio_zero(self, tmp_path):
        ledger = Ledger(db_path=tmp_path / "ledger.db")
        snap = ledger.take_snapshot(
            as_of=date(2026, 8, 10), quotes=make_quotes(),
        )
        assert snap.satellite_ratio == pytest.approx(0.0)
        assert not ledger.get_satellite_status().breached


class TestSnapshotSeries:
    """快照幂等（同周覆盖）、历史序列、目标进度年化（ADR-0003）。"""

    def fund_only_ledger(self, tmp_path, shares=1000.0):
        ledger = Ledger(db_path=tmp_path / "ledger.db")
        ledger.import_fund_holdings(
            fund_payload(shares=shares), as_of=date(2025, 8, 4),
        )
        return ledger

    def test_same_week_snapshot_is_idempotent(self, tmp_path):
        ledger = self.fund_only_ledger(tmp_path)
        ledger.take_snapshot(
            as_of=date(2026, 8, 10),
            quotes=make_quotes(navs={"016532": 1.5}),
        )
        snap2 = ledger.take_snapshot(
            as_of=date(2026, 8, 12),  # 同一 ISO 周
            quotes=make_quotes(navs={"016532": 2.0}),
        )
        history = ledger.get_snapshot_history()
        assert len(history) == 1
        assert snap2.total_cny == pytest.approx(2000.0)
        assert history[0].total_cny == pytest.approx(2000.0)

    def test_history_ordered_across_weeks(self, tmp_path):
        ledger = self.fund_only_ledger(tmp_path)
        ledger.take_snapshot(
            as_of=date(2026, 8, 10), quotes=make_quotes(navs={"016532": 1.5}),
        )
        ledger.take_snapshot(
            as_of=date(2026, 8, 17), quotes=make_quotes(navs={"016532": 1.6}),
        )
        history = ledger.get_snapshot_history()
        assert [s.week_id for s in history] == ["2026-W33", "2026-W34"]
        assert history[1].total_cny == pytest.approx(1600.0)

    def test_goal_progress_annualized_vs_required_line(self, tmp_path):
        """一年 +17.5% → 年化 17.5%，恰好贴在需求线上。"""
        ledger = self.fund_only_ledger(tmp_path)
        ledger.take_snapshot(
            as_of=date(2025, 8, 4), quotes=make_quotes(navs={"016532": 1.0}),
        )
        ledger.take_snapshot(
            as_of=date(2026, 8, 3), quotes=make_quotes(navs={"016532": 1.175}),
        )
        progress = ledger.get_goal_progress()
        assert progress is not None
        assert progress.start_total_cny == pytest.approx(1000.0)
        assert progress.latest_total_cny == pytest.approx(1175.0)
        assert progress.annualized == pytest.approx(0.175, abs=0.005)
        assert progress.required == pytest.approx(0.175)
        assert progress.on_track

    def test_goal_progress_none_with_single_snapshot(self, tmp_path):
        ledger = self.fund_only_ledger(tmp_path)
        ledger.take_snapshot(
            as_of=date(2026, 8, 10), quotes=make_quotes(navs={"016532": 1.5}),
        )
        assert ledger.get_goal_progress() is None

    def test_goal_progress_none_when_empty(self, tmp_path):
        ledger = Ledger(db_path=tmp_path / "ledger.db")
        assert ledger.get_goal_progress() is None

    def test_goal_progress_not_annualized_under_30_days(self, tmp_path):
        ledger = self.fund_only_ledger(tmp_path)
        ledger.take_snapshot(
            as_of=date(2026, 8, 3), quotes=make_quotes(navs={"016532": 1.0}),
        )
        ledger.take_snapshot(
            as_of=date(2026, 8, 24), quotes=make_quotes(navs={"016532": 1.05}),
        )
        progress = ledger.get_goal_progress()
        assert progress is not None
        assert progress.annualized is None  # 起步期不年化，避免伪精度
        assert progress.total_return == pytest.approx(0.05)

    def test_goal_progress_off_track(self, tmp_path):
        ledger = self.fund_only_ledger(tmp_path)
        ledger.take_snapshot(
            as_of=date(2025, 8, 4), quotes=make_quotes(navs={"016532": 1.0}),
        )
        ledger.take_snapshot(
            as_of=date(2026, 8, 3), quotes=make_quotes(navs={"016532": 1.05}),
        )
        progress = ledger.get_goal_progress()
        assert progress is not None
        assert not progress.on_track


def write_baseline(tmp_path, content):
    path = tmp_path / "baseline.yaml"
    path.write_text(content, encoding="utf-8")
    return path


class TestBaselineDeviation:
    """战略配置基准：配置文件 + 未设定状态；偏离视图对照穿透后暴露。"""

    def test_unset_baseline_returns_none(self, tmp_path):
        ledger = Ledger(db_path=tmp_path / "ledger.db")
        ledger.upsert_cash_account(
            account="人民币现金", currency="CNY", balance=100.0,
            as_of=date(2026, 8, 10),
        )
        ledger.take_snapshot(as_of=date(2026, 8, 10), quotes=make_quotes())
        assert ledger.get_baseline_deviation() is None

    def test_missing_baseline_file_treated_as_unset(self, tmp_path):
        ledger = Ledger(
            db_path=tmp_path / "ledger.db",
            baseline_path=tmp_path / "nonexistent.yaml",
        )
        assert ledger.get_baseline_deviation() is None

    def test_within_and_above_range(self, tmp_path):
        baseline = write_baseline(tmp_path, (
            "CN: {min: 0.20, max: 0.40}\n"
            "US: {min: 0.10, max: 0.30}\n"
        ))
        ledger = Ledger(db_path=tmp_path / "ledger.db", baseline_path=baseline)
        ledger.upsert_stock_holding(
            market="CN", symbol="600519", name="贵州茅台",
            shares=1, currency="CNY", as_of=date(2026, 8, 10),
        )
        ledger.upsert_stock_holding(
            market="US", symbol="AAPL", name="Apple",
            shares=1, currency="USD", as_of=date(2026, 8, 10),
        )
        quotes = make_quotes(
            prices={"600519": 300.0, "AAPL": 100.0}, fx={"USD": 7.0},
        )
        ledger.take_snapshot(as_of=date(2026, 8, 10), quotes=quotes)
        # CN=300 (30%), US=700 (70%)
        deviation = {d.market: d for d in ledger.get_baseline_deviation()}
        assert deviation["CN"].status == "within"
        assert deviation["CN"].actual == pytest.approx(0.30)
        assert deviation["US"].status == "above"
        assert deviation["US"].max == pytest.approx(0.30)

    def test_deviation_uses_penetrated_exposure(self, tmp_path):
        baseline = write_baseline(tmp_path, "US: {min: 0.0, max: 0.50}\n")
        ledger = Ledger(db_path=tmp_path / "ledger.db", baseline_path=baseline)
        ledger.import_fund_holdings(fund_payload(), as_of=date(2026, 8, 10))
        ledger.record_fund_xray(
            fund_code="016532", data_as_of=date(2026, 6, 30),
            buckets={"US_equity": 1.0},
        )
        ledger.take_snapshot(as_of=date(2026, 8, 10), quotes=make_quotes())
        deviation = {d.market: d for d in ledger.get_baseline_deviation()}
        assert deviation["US"].actual == pytest.approx(1.0)
        assert deviation["US"].status == "above"


class TestIntegrityCheck:
    """一条命令发现账本质量问题：断档、穿透错位、汇率缺失。"""

    def test_clean_ledger_has_no_issues(self, tmp_path):
        ledger = Ledger(db_path=tmp_path / "ledger.db")
        ledger.import_fund_holdings(fund_payload(), as_of=date(2026, 8, 10))
        ledger.record_fund_xray(
            fund_code="016532", data_as_of=date(2026, 6, 30),
            buckets={"US_equity": 1.0},
        )
        ledger.take_snapshot(as_of=date(2026, 8, 10), quotes=make_quotes())
        assert ledger.validate_integrity() == []

    def test_fund_without_xray_flagged(self, tmp_path):
        ledger = Ledger(db_path=tmp_path / "ledger.db")
        ledger.import_fund_holdings(fund_payload(), as_of=date(2026, 8, 10))
        issues = ledger.validate_integrity()
        assert any("016532" in i for i in issues)

    def test_snapshot_gap_flagged(self, tmp_path):
        ledger = Ledger(db_path=tmp_path / "ledger.db")
        ledger.import_fund_holdings(fund_payload(), as_of=date(2026, 7, 6))
        ledger.record_fund_xray(
            fund_code="016532", data_as_of=date(2026, 6, 30),
            buckets={"US_equity": 1.0},
        )
        quotes = make_quotes(navs={"016532": 1.5})
        ledger.take_snapshot(as_of=date(2026, 7, 6), quotes=quotes)
        ledger.take_snapshot(as_of=date(2026, 8, 10), quotes=quotes)  # 跳 4 周
        issues = ledger.validate_integrity()
        assert any("断档" in i or "gap" in i.lower() for i in issues)

    def test_missing_fx_flagged(self, tmp_path):
        ledger = Ledger(db_path=tmp_path / "ledger.db")
        ledger.upsert_stock_holding(
            market="US", symbol="AAPL", name="Apple",
            shares=1, currency="USD", as_of=date(2026, 8, 10),
        )
        ledger.take_snapshot(
            as_of=date(2026, 8, 10), quotes=make_quotes(prices={"AAPL": 100.0}),
        )
        issues = ledger.validate_integrity()
        assert any("USD" in i and "汇率" in i for i in issues)


class TestPersistenceAcrossInstances:
    """写入必须跨 Facade 实例持久（CLI/job 是独立进程）。"""

    def test_imported_nav_survives_new_instance(self, tmp_path):
        db = tmp_path / "ledger.db"
        Ledger(db_path=db).import_fund_holdings(
            fund_payload(), as_of=date(2026, 8, 10),
        )
        # 新实例（模拟独立 CLI/job 进程）直接可见导入的净值
        snap = Ledger(db_path=db).take_snapshot(
            as_of=date(2026, 8, 10), quotes=make_quotes(),
        )
        assert snap.total_cny == pytest.approx(1500.0)

    def test_holdings_survive_new_instance(self, tmp_path):
        db = tmp_path / "ledger.db"
        Ledger(db_path=db).upsert_cash_account(
            account="人民币现金", currency="CNY", balance=50000.0,
            as_of=date(2026, 8, 10),
        )
        snap = Ledger(db_path=db).take_snapshot(
            as_of=date(2026, 8, 10), quotes=make_quotes(),
        )
        assert snap.total_cny == pytest.approx(50000.0)


class TestAllocationDetail:
    """配置明细只读视图：供用户 review 穿透分类与卫星标签。"""

    def test_detail_joins_snapshot_xray_and_tags(self, tmp_path):
        ledger = Ledger(db_path=tmp_path / "ledger.db")
        ledger.import_fund_holdings(fund_payload(), as_of=date(2026, 8, 10))
        ledger.record_fund_xray(
            fund_code="016532", data_as_of=date(2026, 6, 30),
            buckets={"US_equity": 0.95, "cash": 0.05},
        )
        ledger.set_theme_mapping(
            asset_type="fund", market="CN", symbol="016532",
            theme="AI 算力", is_satellite=True,
        )
        ledger.upsert_cash_account(
            account="人民币现金", currency="CNY", balance=500.0,
            as_of=date(2026, 8, 10),
        )
        ledger.take_snapshot(as_of=date(2026, 8, 10), quotes=make_quotes())
        detail = ledger.get_allocation_detail()
        fund_row = next(d for d in detail if d.symbol == "016532")
        assert fund_row.value_cny == pytest.approx(1500.0)
        assert fund_row.share == pytest.approx(1500.0 / 2000.0)
        assert fund_row.xray_buckets == {"US_equity": 0.95, "cash": 0.05}
        assert fund_row.xray_as_of == date(2026, 6, 30)
        assert fund_row.themes == (("AI 算力", True),)
        cash_row = next(d for d in detail if d.asset_type == "cash")
        assert cash_row.xray_buckets is None
        assert cash_row.themes == ()

    def test_detail_empty_without_snapshot(self, tmp_path):
        ledger = Ledger(db_path=tmp_path / "ledger.db")
        ledger.upsert_cash_account(
            account="人民币现金", currency="CNY", balance=500.0,
            as_of=date(2026, 8, 10),
        )
        assert ledger.get_allocation_detail() == []


class TestBucketBreakdown:
    """基准桶内明细：持仓按穿透口径归入各桶，跨桶基金拆分。"""

    def test_fund_split_across_buckets(self, tmp_path):
        ledger = Ledger(db_path=tmp_path / "ledger.db")
        ledger.import_fund_holdings(fund_payload(), as_of=date(2026, 8, 10))
        ledger.record_fund_xray(
            fund_code="016532", data_as_of=date(2026, 6, 30),
            buckets={"US_equity": 0.6, "CN_equity": 0.3, "cash": 0.1},
        )
        ledger.upsert_stock_holding(
            market="US", symbol="AAPL", name="Apple",
            shares=10, currency="USD", as_of=date(2026, 8, 10),
        )
        ledger.upsert_cash_account(
            account="人民币现金", currency="CNY", balance=100.0,
            as_of=date(2026, 8, 10),
        )
        quotes = make_quotes(prices={"AAPL": 100.0}, fx={"USD": 1.0})
        ledger.take_snapshot(as_of=date(2026, 8, 10), quotes=quotes)
        # 基金 1500：US 900 / CN 450 / CASH 150；AAPL 1000 → US；现金 100 → CASH
        breakdown = ledger.get_bucket_breakdown()
        us = [e for e in breakdown if e.bucket == "US"]
        assert {e.symbol for e in us} == {"016532", "AAPL"}
        fund_entry = next(e for e in us if e.symbol == "016532")
        assert fund_entry.value_cny == pytest.approx(900.0)
        assert fund_entry.bucket_weight == pytest.approx(0.6)
        assert fund_entry.is_split
        direct = next(e for e in us if e.symbol == "AAPL")
        assert direct.value_cny == pytest.approx(1000.0)
        assert not direct.is_split
        cn = [e for e in breakdown if e.bucket == "CN"]
        assert cn[0].value_cny == pytest.approx(450.0)
        cash_syms = {e.symbol for e in breakdown if e.bucket == "CASH"}
        assert cash_syms == {"016532", "人民币现金"}

    def test_unpenetrated_fund_gets_own_bucket(self, tmp_path):
        ledger = Ledger(db_path=tmp_path / "ledger.db")
        ledger.import_fund_holdings(fund_payload(), as_of=date(2026, 8, 10))
        ledger.take_snapshot(as_of=date(2026, 8, 10), quotes=make_quotes())
        breakdown = ledger.get_bucket_breakdown()
        assert breakdown[0].bucket == "UNPENETRATED"
        assert not breakdown[0].is_split

    def test_breakdown_empty_without_snapshot(self, tmp_path):
        ledger = Ledger(db_path=tmp_path / "ledger.db")
        assert ledger.get_bucket_breakdown() == []

    def test_breakdown_consistent_with_market_exposure(self, tmp_path):
        ledger = Ledger(db_path=tmp_path / "ledger.db")
        ledger.import_fund_holdings(fund_payload(), as_of=date(2026, 8, 10))
        ledger.record_fund_xray(
            fund_code="016532", data_as_of=date(2026, 6, 30),
            buckets={"US_equity": 0.6, "CN_equity": 0.3, "cash": 0.1},
        )
        ledger.take_snapshot(as_of=date(2026, 8, 10), quotes=make_quotes())
        snap = ledger.get_latest_snapshot()
        totals: dict[str, float] = {}
        for e in ledger.get_bucket_breakdown():
            totals[e.bucket] = totals.get(e.bucket, 0.0) + e.value_cny
        for bucket, total in totals.items():
            assert total == pytest.approx(snap.market_exposure[bucket])
