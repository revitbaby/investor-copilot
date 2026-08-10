import pandas as pd
import os
from datetime import datetime, timedelta
from .fred_client import FredClient
from .market_client import MarketClient
from .china_market_client import ChinaMarketClient
from .china_market_fetcher import _record_sync

class DataLoader:
    def __init__(self, data_dir: str = "data_cache"):
        self.fred_client = FredClient()
        self.market_client = MarketClient()
        self.china_client = ChinaMarketClient()
        self.data_dir = data_dir
        if not os.path.exists(data_dir):
            os.makedirs(data_dir)
            
    def fetch_all_data(self, days_back: int = 365, use_cache: bool = True) -> pd.DataFrame:
        cache_file = os.path.join(self.data_dir, "macro_data.csv")
        today = datetime.now().strftime("%Y-%m-%d")
        
        # Check cache
        if use_cache and os.path.exists(cache_file):
            file_time = datetime.fromtimestamp(os.path.getmtime(cache_file)).strftime("%Y-%m-%d")
            if file_time == today:
                print("Loading from cache...")
                df = pd.read_csv(cache_file, index_col=0, parse_dates=True)
                return df
        
        # Calculate start date for FRED
        start_date = (datetime.now() - timedelta(days=days_back + 30)).strftime("%Y-%m-%d") # Extra buffer
        
        # Determine period for Yahoo
        period = "1y"
        if days_back > 365: period = "2y"
        if days_back > 730: period = "5y"
        if days_back > 1825: period = "max"
        
        try:
            with _record_sync("macro_data.csv"):
                print("Fetching new data...")
                fred_df = self.fred_client.get_liquidity_data(start_date=start_date)
                market_df = self.market_client.get_market_data(period=period)

                combined_df = pd.concat([fred_df, market_df], axis=1)
                combined_df = combined_df.ffill()
                combined_df = combined_df.dropna()

                cutoff_date = datetime.now() - timedelta(days=days_back)
                combined_df = combined_df[combined_df.index >= cutoff_date]

                combined_df.to_csv(cache_file)

            return combined_df
            
        except Exception as e:
            print(f"Error in data loading: {e}")
            if os.path.exists(cache_file):
                print("Falling back to old cache...")
                return pd.read_csv(cache_file, index_col=0, parse_dates=True)
            raise e

    def fetch_sector_etf_data(self, days_back: int = 365, use_cache: bool = True) -> pd.DataFrame:
        """Fetch sector ETF data for S5FI market breadth approximation."""
        cache_file = os.path.join(self.data_dir, "sector_etf_data.csv")
        today = datetime.now().strftime("%Y-%m-%d")

        if use_cache and os.path.exists(cache_file):
            file_time = datetime.fromtimestamp(os.path.getmtime(cache_file)).strftime("%Y-%m-%d")
            if file_time == today:
                print("Loading sector ETF data from cache...")
                return pd.read_csv(cache_file, index_col=0, parse_dates=True)

        period = "1y"
        if days_back > 365: period = "2y"
        if days_back > 730: period = "5y"

        try:
            with _record_sync("sector_etf_data.csv"):
                df = self.market_client.get_sector_etf_data(period=period)
                if not df.empty:
                    df.to_csv(cache_file)
            return df
        except Exception as e:
            print(f"Error fetching sector ETF data: {e}")
            if os.path.exists(cache_file):
                return pd.read_csv(cache_file, index_col=0, parse_dates=True)
            return pd.DataFrame()

    def fetch_china_data(self, days_back: int = 365, use_cache: bool = True) -> pd.DataFrame:
        """
        Fetch all China/HK related data and merge into a single DataFrame.
        """
        cache_file = os.path.join(self.data_dir, "china_data.csv")
        today = datetime.now().strftime("%Y-%m-%d")
        
        # Check cache — use file if modified within the last 24 hours.
        # Daily financial data has T+1 lag; a 24-hour window avoids a full
        # API refetch every morning while still refreshing once per day.
        if use_cache and os.path.exists(cache_file):
            file_age_hours = (datetime.now() - datetime.fromtimestamp(os.path.getmtime(cache_file))).total_seconds() / 3600
            if file_age_hours < 24:
                print("Loading China data from cache...")
                df = pd.read_csv(cache_file, index_col=0, parse_dates=True)
                cutoff = datetime.now() - timedelta(days=days_back)
                return df[df.index >= cutoff]

        try:
            with _record_sync("china_data.csv"):
                print("Fetching China data (parallel)...")
                from concurrent.futures import ThreadPoolExecutor, as_completed
                tasks = {
                    "macro":   self.china_client.get_macro_data,
                    "meso":    self.china_client.get_meso_data,
                    "micro":   self.china_client.get_micro_data,
                    "hk":      self.china_client.get_hk_data,
                    "tushare": self.china_client.get_tushare_data,
                }
                results: dict[str, pd.DataFrame] = {}
                with ThreadPoolExecutor(max_workers=5) as executor:
                    future_to_key = {executor.submit(fn): key for key, fn in tasks.items()}
                    for future in as_completed(future_to_key):
                        key = future_to_key[future]
                        try:
                            results[key] = future.result()
                        except Exception as e:
                            print(f"Error fetching {key}: {e}")
                            results[key] = pd.DataFrame()
                macro   = results.get("macro",   pd.DataFrame())
                meso    = results.get("meso",    pd.DataFrame())
                micro   = results.get("micro",   pd.DataFrame())
                hk      = results.get("hk",      pd.DataFrame())
                tushare = results.get("tushare", pd.DataFrame())

                dfs = [macro, meso, micro, hk, tushare]
                combined_df = pd.DataFrame()

                for df in dfs:
                    if not df.empty:
                        if combined_df.empty:
                            combined_df = df
                        else:
                            combined_df = combined_df.join(df, how='outer')

                combined_df = combined_df.sort_index()

                ffill_cols = [
                    'M1_YoY', 'M2_YoY', 'M1_M2_Gap', 'Social_Financing_Increment',
                    'CN_10Y_Yield', 'CSI300_PE_TTM', 'Stock_Bond_Spread',
                ]
                cols_to_fill = [c for c in ffill_cols if c in combined_df.columns]
                if cols_to_fill:
                    combined_df[cols_to_fill] = combined_df[cols_to_fill].ffill()

                combined_df.to_csv(cache_file)

            cutoff = datetime.now() - timedelta(days=days_back)
            combined_df = combined_df[combined_df.index >= cutoff]

            return combined_df
            
        except Exception as e:
            print(f"Error in China data loading: {e}")
            if os.path.exists(cache_file):
                print("Falling back to old China cache...")
                return pd.read_csv(cache_file, index_col=0, parse_dates=True)
            return pd.DataFrame()
