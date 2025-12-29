import os
import pandas as pd
from fredapi import Fred
from dotenv import load_dotenv

load_dotenv()

class FredClient:
    def __init__(self):
        self.api_key = os.getenv("FRED_API_KEY")
        # Allow instantiation without key if not calling API (e.g. for testing mocks), 
        # but warn or fail when method called.
        if self.api_key:
            self.fred = Fred(api_key=self.api_key)
        else:
            self.fred = None
            print("Warning: FRED_API_KEY not found. FredClient will fail to fetch data.")

    def get_series(self, series_id: str, start_date: str = None) -> pd.Series:
        """Fetch a series from FRED."""
        if not self.fred:
            raise ValueError("FRED_API_KEY not configured.")
        return self.fred.get_series(series_id, observation_start=start_date)

    def get_liquidity_data(self, start_date: str = None) -> pd.DataFrame:
        """Fetch key liquidity components: WALCL, RRPONTSYD, WTREGEN."""
        # F1: Fed Total Assets (WALCL) - Weekly
        # F2: Reverse Repo (RRPONTSYD) - Daily
        # F3: TGA (WTREGEN) - Daily
        # F4: SOFR (SOFR) or Fed Funds (FEDFUNDS) - Daily/Monthly
        
        print("Fetching FRED data...")
        walcl = self.get_series("WALCL", start_date)
        rrp = self.get_series("RRPONTSYD", start_date)
        tga = self.get_series("WTREGEN", start_date)
        
        # Create a DataFrame with all series
        # We use outer join to keep all dates initially
        df = pd.DataFrame({
            "WALCL": walcl,
            "RRP": rrp,
            "TGA": tga
        })
        
        # Resample to daily and forward fill to handle weekly data (WALCL)
        # WALCL is reported on Wednesdays. We forward fill it to the next Tuesday.
        df = df.resample('D').ffill()
        
        return df

