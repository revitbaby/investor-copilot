import akshare as ak
import pandas as pd
import datetime
from typing import Dict, Any
from .tushare_client import TushareClient

# SZSE category names changed over time due to market restructuring
_SZSE_A_CATEGORIES = {
    # 2021+: 中小板 merged into 主板
    'post_2021': ['主板A股', '创业板A股'],
    # Pre-2021: separate 中小板 and 创业板
    'pre_2021': ['主板A股', '中小板', '创业板'],
}


def _get_szse_a_market_cap_yi(date_str: str) -> float:
    """Return SZSE A-share total market cap in 亿元 for a given trading date."""
    df = ak.stock_szse_summary(date=date_str)
    cats = set(df['证券类别'].tolist())
    targets = (_SZSE_A_CATEGORIES['post_2021'] if '创业板A股' in cats
               else _SZSE_A_CATEGORIES['pre_2021'])
    total = sum(
        df.loc[df['证券类别'] == c, '总市值'].values[0] / 1e8
        for c in targets if c in cats
    )
    return total


def _get_sse_total_market_cap_yi(date_str: str) -> float:
    """Return SSE total market cap (A+B+STAR) in 亿元. B-share is <0.2%, negligible."""
    df = ak.stock_sse_deal_daily(date=date_str)
    return float(df.loc[df['单日情况'] == '市价总值', '股票'].values[0])


class ChinaMarketClient:
    """
    Client for fetching China/HK market data using AkShare.
    Follows the Macro-Meso-Micro framework.
    """
    def __init__(self):
        self._tushare = TushareClient()

    def get_macro_data(self) -> pd.DataFrame:
        """
        Fetch Macro 'Source' data:
        - DR007 proxy: use repo_rate_query FR007
        - SHIBOR (Interbank Rate)
        """
        print("Fetching China Macro data...")
        macro_data = pd.DataFrame()

        # 1) DR007 proxy via repo_rate_query (FR007 close substitute)
        try:
            repo_df = ak.repo_rate_query()
            if not repo_df.empty:
                repo_df['date'] = pd.to_datetime(repo_df['date'])
                repo_df = repo_df.set_index('date').sort_index()
                # FR007 column -> DR007 proxy
                macro_data['DR007'] = repo_df['FR007']
        except Exception as e:
            print(f"Error fetching DR007 proxy: {e}")

        # 2) SHIBOR curve (columns are named like "O/N-定价", "3M-定价")
        try:
            shibor_df = ak.macro_china_shibor_all()
            if not shibor_df.empty:
                shibor_df['date'] = pd.to_datetime(shibor_df['日期'])
                shibor_df = shibor_df.set_index('date').sort_index()
                rename_map = {
                    'O/N-定价': 'SHIBOR_ON',
                    '1W-定价': 'SHIBOR_1W',
                    '3M-定价': 'SHIBOR_3M'
                }
                cols = [c for c in rename_map if c in shibor_df.columns]
                if cols:
                    shibor_clean = shibor_df[cols].rename(columns=rename_map)
                    macro_data = macro_data.join(shibor_clean, how='outer') if not macro_data.empty else shibor_clean
        except Exception as e:
            print(f"Error fetching SHIBOR: {e}")

        # No stable OMO endpoint in current akshare build; leave empty to avoid hard failure.
        return macro_data

    def get_meso_data(self) -> pd.DataFrame:
        """
        Fetch Meso 'Pipeline' data:
        - M1/M2 Growth Gap
        - Social Financing (new credit)
        """
        print("Fetching China Meso data...")
        meso_data = pd.DataFrame()

        # Money supply (contains M1/M2 YoY)
        try:
            money_df = ak.macro_china_money_supply()
            if not money_df.empty:
                money_df['date'] = pd.to_datetime(money_df['月份'], format='%Y年%m月份', errors='coerce')
                money_df = money_df.set_index('date').sort_index()
                rename_map = {
                    '货币(M1)-同比增长': 'M1_YoY',
                    '货币和准货币(M2)-同比增长': 'M2_YoY'
                }
                cols = [c for c in rename_map if c in money_df.columns]
                money_clean = money_df[cols].rename(columns=rename_map)
                money_clean['M1_M2_Gap'] = money_clean.get('M1_YoY', pd.Series(index=money_clean.index, dtype=float)) - money_clean.get('M2_YoY', pd.Series(index=money_clean.index, dtype=float))
                meso_data = money_clean
        except Exception as e:
            print(f"Error fetching money supply: {e}")

        # Social Financing (incremental)
        try:
            credit_df = ak.macro_china_new_financial_credit()
            if not credit_df.empty:
                credit_df['date'] = pd.to_datetime(credit_df['月份'], format='%Y年%m月份', errors='coerce')
                credit_df = credit_df.set_index('date').sort_index()
                if '当月' in credit_df.columns:
                    soc = credit_df[['当月']].rename(columns={'当月': 'Social_Financing_Increment'})
                    meso_data = meso_data.join(soc, how='outer') if not meso_data.empty else soc
        except Exception as e:
            print(f"Error fetching Social Financing: {e}")

        return meso_data

    def get_micro_data(self) -> pd.DataFrame:
        """
        Fetch Micro 'Water Level' data:
        - A-Share Turnover (index volume proxy)
        - Northbound Flows (via fund flow summary)
        """
        print("Fetching China Micro data...")
        micro_data = pd.DataFrame()

        # 1. Turnover proxy using SH/SZ index volume
        try:
            sh_df = ak.stock_zh_index_daily(symbol="sh000001")
            sz_df = ak.stock_zh_index_daily(symbol="sz399001")
            for df in (sh_df, sz_df):
                df['date'] = pd.to_datetime(df['date'])
                df.set_index('date', inplace=True)
            total_vol = sh_df['volume'].add(sz_df['volume'], fill_value=0)
            micro_data['A_Share_Volume'] = total_vol
            micro_data['SH_Index'] = sh_df['close']
        except Exception as e:
            print(f"Error fetching Index data: {e}")

        # Northbound flows are now sourced from Tushare (get_tushare_data),
        # which covers 2016-present including post-Aug-2024 data.
        return micro_data

    def get_total_market_cap(self) -> pd.DataFrame:
        """
        Fetch A-share total market cap (沪深A股总市值) as a daily time series.

        Strategy (tiered):
          Tier 1 – monthly official baseline (2008–present, one API call):
            ak.macro_china_stock_market_cap() → SH + SZ, end-of-month, interpolated to daily.
          Tier 2 – recent daily precision patch (last ~60 trading days):
            SSE deal_daily + SZSE summary → exact daily values overwrite the interpolated tail.
            SSE format is reliable from ~2022 onward; falls back gracefully on error.

        Returns
        -------
        pd.DataFrame with column 'Total_Market_Cap_Yi' (亿元), DatetimeIndex, daily frequency.
        """
        print("Fetching A-share total market cap...")
        result = pd.Series(dtype=float, name='Total_Market_Cap_Yi')

        # --- Tier 1: monthly baseline ---
        try:
            monthly = ak.macro_china_stock_market_cap()
            monthly['date'] = pd.to_datetime(
                monthly['数据日期'], format='%Y年%m月份', errors='coerce'
            )
            monthly = monthly.dropna(subset=['date']).set_index('date').sort_index()

            sh = pd.to_numeric(monthly['市价总值-上海'], errors='coerce')
            sz = pd.to_numeric(monthly['市价总值-深圳'], errors='coerce')
            # Fill missing SZ with forward-fill (occasional gaps in source)
            monthly_cap = (sh + sz).ffill()
            monthly_cap = monthly_cap.dropna()

            # Resample to daily via linear interpolation
            daily_idx = pd.date_range(monthly_cap.index[0], datetime.date.today(), freq='D')
            result = monthly_cap.reindex(daily_idx).interpolate(method='time')
        except Exception as e:
            print(f"Error fetching monthly market cap baseline: {e}")

        # --- Tier 2: recent daily precision patch ---
        try:
            today = datetime.date.today()
            # Walk back through the last 90 calendar days and collect available trading dates
            patch: dict[pd.Timestamp, float] = {}
            d = today
            consecutive_errors = 0
            while d >= today - datetime.timedelta(days=90):
                date_str = d.strftime('%Y%m%d')
                try:
                    szse_cap = _get_szse_a_market_cap_yi(date_str)
                    sse_cap = _get_sse_total_market_cap_yi(date_str)
                    patch[pd.Timestamp(d)] = szse_cap + sse_cap
                    consecutive_errors = 0
                except Exception:
                    # Non-trading day or format mismatch – skip silently
                    consecutive_errors += 1
                d -= datetime.timedelta(days=1)
                # Stop early if we hit a long gap (e.g., holiday season)
                if consecutive_errors > 14:
                    break

            if patch:
                patch_series = pd.Series(patch, name='Total_Market_Cap_Yi')
                if result.empty:
                    result = patch_series
                else:
                    result.update(patch_series)
        except Exception as e:
            print(f"Error fetching daily market cap patch: {e}")

        df = result.to_frame('Total_Market_Cap_Yi')
        df.index.name = 'date'
        return df

    def get_margin_data(self) -> pd.DataFrame:
        """
        Fetch daily margin balance (融资融券余额) for SH + SZ exchanges.

        Returns
        -------
        pd.DataFrame with columns:
          - 'Margin_Balance_Yi'   : SH + SZ combined 融资融券余额 (亿元)
          - 'Margin_Buy_Yi'       : SH + SZ combined 融资买入额 (亿元)
        DatetimeIndex, daily frequency.
        """
        print("Fetching margin balance data...")
        margin_data = pd.DataFrame()

        for label, fetch_fn in [('SH', ak.macro_china_market_margin_sh),
                                  ('SZ', ak.macro_china_market_margin_sz)]:
            try:
                df = fetch_fn()
                df['date'] = pd.to_datetime(df['日期'], errors='coerce')
                df = df.dropna(subset=['date']).set_index('date').sort_index()
                balance = pd.to_numeric(df['融资融券余额'], errors='coerce') / 1e8
                buy = pd.to_numeric(df['融资买入额'], errors='coerce') / 1e8
                tmp = pd.DataFrame({
                    f'_balance_{label}': balance,
                    f'_buy_{label}': buy,
                })
                margin_data = (margin_data.join(tmp, how='outer')
                               if not margin_data.empty else tmp)
            except Exception as e:
                print(f"Error fetching {label} margin: {e}")

        if margin_data.empty:
            return margin_data

        # Sum SH + SZ; where only one exchange has data, use that alone
        bal_cols = [c for c in margin_data.columns if c.startswith('_balance_')]
        buy_cols = [c for c in margin_data.columns if c.startswith('_buy_')]
        result = pd.DataFrame(index=margin_data.index)
        result['Margin_Balance_Yi'] = margin_data[bal_cols].sum(axis=1, min_count=1)
        result['Margin_Buy_Yi'] = margin_data[buy_cols].sum(axis=1, min_count=1)
        result.index.name = 'date'
        return result

    def get_bond_yield(self) -> pd.DataFrame:
        """
        Fetch China 10-year government bond yield (中债国债收益率曲线 10Y).

        bond_china_yield supports ~12-month windows per call; this method paginates
        annually from 2013 (aligned with Tushare PE history start) to today.

        Returns
        -------
        pd.DataFrame
            Column 'CN_10Y_Yield' (%), DatetimeIndex.
        """
        print("Fetching China 10Y bond yield (paginated)...")
        parts = []
        start_year = 2013
        today = datetime.date.today()

        for year in range(start_year, today.year + 1):
            s = f"{year}0101"
            e = f"{year}1231" if year < today.year else today.strftime("%Y%m%d")
            try:
                raw = ak.bond_china_yield(start_date=s, end_date=e)
                gov = raw[raw["曲线名称"] == "中债国债收益率曲线"].copy()
                if not gov.empty:
                    parts.append(gov[["日期", "10年"]])
            except Exception:
                pass  # Skip years where data is unavailable

        if not parts:
            return pd.DataFrame()

        combined = pd.concat(parts).drop_duplicates(subset="日期")
        combined["date"] = pd.to_datetime(combined["日期"])
        combined = combined.set_index("date").sort_index()
        result = pd.to_numeric(combined["10年"], errors="coerce").rename("CN_10Y_Yield")
        return result.to_frame()

    def get_tushare_data(self) -> pd.DataFrame:
        """
        Fetch Tushare-sourced data:
        - Northbound net inflow (北向资金每日净买额, 亿元)
        - CSI 300 PE TTM (沪深300市盈率)
        - Stock-bond yield spread (股债利差 = 1/PE - 10Y bond yield)

        Falls back gracefully to empty DataFrame if token is missing or calls fail.

        Returns
        -------
        pd.DataFrame with columns:
          - 'Northbound_Net_Inflow' (亿元)
          - 'CSI300_PE_TTM'
          - 'Stock_Bond_Spread' (%, equity earnings yield minus 10Y bond yield)
        DatetimeIndex.
        """
        print("Fetching Tushare data (northbound + CSI300 PE)...")
        result = pd.DataFrame()

        try:
            nb = self._tushare.get_northbound_flow()
            if not nb.empty:
                result = nb

            pe = self._tushare.get_csi300_pe()
            if not pe.empty:
                result = result.join(pe, how="outer") if not result.empty else pe

            # Stock-bond spread needs both PE and bond yield
            if "CSI300_PE_TTM" in result.columns:
                bond = self.get_bond_yield()
                if not bond.empty:
                    result = result.join(bond, how="outer")
                    # Forward-fill bond yield (published on trading days, gaps on weekends)
                    result["CN_10Y_Yield"] = result["CN_10Y_Yield"].ffill()
                    pe_col = pd.to_numeric(result["CSI300_PE_TTM"], errors="coerce")
                    yield_col = pd.to_numeric(result["CN_10Y_Yield"], errors="coerce")
                    result["Stock_Bond_Spread"] = (1 / pe_col * 100) - yield_col

        except Exception as e:
            print(f"Error fetching Tushare data: {e}")

        result.index.name = "date"
        return result

    def get_hk_data(self) -> pd.DataFrame:
        """
        Fetch HK specific data:
        - Southbound Flows (via fund flow summary)
        """
        print("Fetching HK data...")
        hk_data = pd.DataFrame()

        try:
            sb_df = ak.stock_hsgt_hist_em(symbol="南向资金")
            if not sb_df.empty:
                sb_df['date'] = pd.to_datetime(sb_df['日期'])
                sb_df = sb_df.set_index('date').sort_index()
                if '当日成交净买额' in sb_df.columns:
                    hk_data = sb_df[['当日成交净买额']].rename(columns={'当日成交净买额': 'Southbound_Net_Inflow'})
        except Exception as e:
            print(f"Error fetching Southbound flows: {e}")

        # AH Premium placeholder (no stable endpoint in current build)
        return hk_data
