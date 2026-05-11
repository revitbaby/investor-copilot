import os
import pandas as pd
import tushare as ts
from datetime import date

_WAN_TO_YI = 1e-4  # 万元 → 亿元


def _init_pro():
    token = os.getenv("TUSHARE_API_KEY", "")
    if not token:
        raise EnvironmentError("TUSHARE_API_KEY not set")
    ts.set_token(token)
    return ts.pro_api()


class TushareClient:
    """
    Tushare Pro data client.
    Provides northbound fund flow and CSI 300 valuation history.
    Requires TUSHARE_API_KEY in environment.
    """

    def __init__(self):
        self._pro = None

    def _get_pro(self):
        if self._pro is None:
            self._pro = _init_pro()
        return self._pro

    def get_northbound_flow(self) -> pd.DataFrame:
        """
        Fetch full northbound (北向资金) daily net-buy history via moneyflow_hsgt.

        The free-tier API caps each call at ~300 rows, so we paginate annually
        from 2016 to today to retrieve the complete history.

        Returns
        -------
        pd.DataFrame
            Column 'Northbound_Net_Inflow' (亿元, positive = net buy), DatetimeIndex.
        """
        pro = self._get_pro()
        today = date.today()
        parts = []
        for year in range(2016, today.year + 1):
            s = f"{year}0101"
            e = f"{year}1231" if year < today.year else today.strftime("%Y%m%d")
            try:
                chunk = pro.moneyflow_hsgt(
                    start_date=s, end_date=e, fields="trade_date,north_money"
                )
                if not chunk.empty:
                    parts.append(chunk)
            except Exception:
                pass

        if not parts:
            return pd.DataFrame()

        raw = pd.concat(parts).drop_duplicates(subset="trade_date")
        raw["date"] = pd.to_datetime(raw["trade_date"])
        raw = raw.set_index("date").sort_index()
        raw["Northbound_Net_Inflow"] = (
            pd.to_numeric(raw["north_money"], errors="coerce") * _WAN_TO_YI
        )
        return raw[["Northbound_Net_Inflow"]]

    def get_csi300_pe(self) -> pd.DataFrame:
        """
        Fetch full CSI 300 daily PE TTM history, paginating to overcome the 3000-row limit.

        Returns
        -------
        pd.DataFrame
            Column 'CSI300_PE_TTM', DatetimeIndex.
        """
        pro = self._get_pro()
        today = date.today().strftime("%Y%m%d")

        # Two calls cover 2005–present (each call returns up to 3000 trading days ≈ 12 yrs)
        segments = [("20050101", "20160101"), ("20160101", today)]
        parts = []
        for start, end in segments:
            chunk = pro.index_dailybasic(
                ts_code="000300.SH",
                start_date=start,
                end_date=end,
                fields="trade_date,pe_ttm",
            )
            if not chunk.empty:
                parts.append(chunk)

        if not parts:
            return pd.DataFrame()

        raw = pd.concat(parts).drop_duplicates(subset="trade_date")
        raw["date"] = pd.to_datetime(raw["trade_date"])
        raw = raw.set_index("date").sort_index()
        raw["CSI300_PE_TTM"] = pd.to_numeric(raw["pe_ttm"], errors="coerce")
        return raw[["CSI300_PE_TTM"]]
