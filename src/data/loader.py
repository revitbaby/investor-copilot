import pandas as pd
import os
from datetime import datetime, timedelta
from .fred_client import FredClient
from .market_client import MarketClient

class DataLoader:
    def __init__(self, data_dir: str = "data_cache"):
        self.fred_client = FredClient()
        self.market_client = MarketClient()
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
            print("Fetching new data...")
            fred_df = self.fred_client.get_liquidity_data(start_date=start_date)
            market_df = self.market_client.get_market_data(period=period)
            
            # Merge
            # Align on index (Date)
            # FRED data (daily/filled) and Market data (trading days)
            combined_df = pd.concat([fred_df, market_df], axis=1)
            
            # Forward fill to propagate last known values (handling holidays/weekends alignment)
            combined_df = combined_df.ffill()
            
            # Drop rows with NaN (likely at the start if one series is shorter)
            combined_df = combined_df.dropna()
            
            # Optional: Filter to requested days_back
            cutoff_date = datetime.now() - timedelta(days=days_back)
            combined_df = combined_df[combined_df.index >= cutoff_date]
            
            # Save to cache
            combined_df.to_csv(cache_file)
            
            return combined_df
            
        except Exception as e:
            print(f"Error in data loading: {e}")
            if os.path.exists(cache_file):
                print("Falling back to old cache...")
                return pd.read_csv(cache_file, index_col=0, parse_dates=True)
            raise e

