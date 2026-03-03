import akshare as ak
import pandas as pd
import datetime
from typing import Dict, Any

class ChinaMarketClient:
    """
    Client for fetching China/HK market data using AkShare.
    Follows the Macro-Meso-Micro framework.
    """
    def __init__(self):
        # AkShare doesn't require init, but we can store config if needed
        pass

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

        # 2. Northbound flows (historical daily)
        try:
            nb_df = ak.stock_hsgt_hist_em(symbol="北向资金")
            if not nb_df.empty:
                nb_df['date'] = pd.to_datetime(nb_df['日期'])
                nb_df = nb_df.set_index('date').sort_index()
                if '当日成交净买额' in nb_df.columns:
                    nb_col = nb_df[['当日成交净买额']].rename(columns={'当日成交净买额': 'Northbound_Net_Inflow'})
                    micro_data = micro_data.join(nb_col, how='outer') if not micro_data.empty else nb_col
        except Exception as e:
            print(f"Error fetching Northbound flows: {e}")

        return micro_data

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
