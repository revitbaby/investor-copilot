"""
Unit tests verifying that china_market_fetcher functions handle API timeouts
gracefully: they return stale cached values (or None) without raising exceptions.
"""

from __future__ import annotations

import concurrent.futures
from datetime import date
from unittest.mock import patch, MagicMock

import pandas as pd
import pytest

from src.data.china_market_fetcher import (
    fetch_csi300_pe,
    fetch_cgb10y_yield,
    fetch_northbound_flow,
    fetch_southbound_flow,
    fetch_qvix,
    fetch_m2_monthly,
    fetch_market_total_amount,
)


def _make_cache_df(col: str, value: float, idx_date: str = "2026-05-20") -> pd.DataFrame:
    df = pd.DataFrame({col: [value]}, index=pd.to_datetime([idx_date]))
    df.index.name = "date"
    return df


class TestTimeoutDegradation:
    """All tests mock _run_with_timeout to raise TimeoutError, then verify stale fallback."""

    def test_fetch_csi300_pe_timeout_returns_stale(self, tmp_path):
        cache_df = _make_cache_df("CSI300_PE_TTM", 14.5)
        with (
            patch("src.data.china_market_fetcher._load_cache", return_value=pd.DataFrame()),
            patch("src.data.china_market_fetcher._run_with_timeout",
                  side_effect=concurrent.futures.TimeoutError),
            patch("src.data.china_market_fetcher._last_known", return_value=(14.5, True)),
        ):
            val, stale = fetch_csi300_pe(date(2026, 5, 25))
        assert stale is True
        assert val == pytest.approx(14.5)

    def test_fetch_csi300_pe_timeout_no_cache_returns_none(self):
        with (
            patch("src.data.china_market_fetcher._load_cache", return_value=pd.DataFrame()),
            patch("src.data.china_market_fetcher._run_with_timeout",
                  side_effect=concurrent.futures.TimeoutError),
            patch("src.data.china_market_fetcher._last_known", return_value=(None, True)),
        ):
            val, stale = fetch_csi300_pe(date(2026, 5, 25))
        assert stale is True
        assert val is None

    def test_fetch_qvix_timeout_returns_stale(self):
        with (
            patch("src.data.china_market_fetcher._load_cache", return_value=pd.DataFrame()),
            patch("src.data.china_market_fetcher._run_with_timeout",
                  side_effect=concurrent.futures.TimeoutError),
            patch("src.data.china_market_fetcher._last_known", return_value=(22.3, True)),
        ):
            val, stale = fetch_qvix(date(2026, 5, 25))
        assert stale is True
        assert val == pytest.approx(22.3)

    def test_fetch_northbound_flow_timeout_returns_stale(self):
        cache_df = pd.DataFrame(
            {"Northbound_Net_Yi": [5.2], "Northbound_5D_Cumulative_Yi": [25.0]},
            index=pd.to_datetime(["2026-05-20"]),
        )
        cache_df.index.name = "date"
        with (
            patch("src.data.china_market_fetcher._load_cache", return_value=cache_df),
            patch("src.data.china_market_fetcher._run_with_timeout",
                  side_effect=concurrent.futures.TimeoutError),
        ):
            result, stale = fetch_northbound_flow(date(2026, 5, 25))
        assert stale is True
        assert result is not None
        assert result["net_buy_yi"] == pytest.approx(5.2)

    def test_fetch_northbound_flow_timeout_no_cache_returns_none(self):
        with (
            patch("src.data.china_market_fetcher._load_cache", return_value=pd.DataFrame()),
            patch("src.data.china_market_fetcher._run_with_timeout",
                  side_effect=concurrent.futures.TimeoutError),
        ):
            result, stale = fetch_northbound_flow(date(2026, 5, 25))
        assert stale is True
        assert result is None

    def test_fetch_m2_monthly_timeout_returns_stale(self):
        cache_df = pd.DataFrame(
            {"M2_Yi": [3000000.0]},
            index=pd.to_datetime(["2026-04-01"]),
        )
        cache_df.index.name = "date"
        with (
            patch("src.data.china_market_fetcher._load_cache", return_value=cache_df),
            patch("src.data.china_market_fetcher._run_with_timeout",
                  side_effect=concurrent.futures.TimeoutError),
        ):
            series, month, stale = fetch_m2_monthly()
        assert stale is True
        assert series is not None
        assert month == "2026-04"

    def test_fetch_market_total_amount_timeout_returns_stale(self):
        cache_df = pd.DataFrame(
            {"Total_Amount_Yi": [12000.0], "Amount_MA20_Yi": [11000.0]},
            index=pd.to_datetime(["2026-05-20"]),
        )
        cache_df.index.name = "date"
        with (
            patch("src.data.china_market_fetcher._load_cache", return_value=cache_df),
            patch("src.data.china_market_fetcher._run_with_timeout",
                  side_effect=concurrent.futures.TimeoutError),
        ):
            amount, ma20, stale = fetch_market_total_amount(date(2026, 5, 25))
        assert stale is True
        assert amount == pytest.approx(12000.0)
        assert ma20 == pytest.approx(11000.0)
