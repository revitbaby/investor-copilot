import yfinance as yf
import pandas as pd

class MarketClient:
    def __init__(self):
        self.tickers = {
            "SPY": "SPY",
            "VIX": "^VIX",
            "MOVE": "^MOVE", 
            "HYG": "HYG",
            "DXY": "DX-Y.NYB",
            "GOLD": "GC=F",
            "OIL": "CL=F",
            "BTC": "BTC-USD",
            "US10Y": "^TNX" 
        }
    
    def get_market_data(self, period: str = "1y") -> pd.DataFrame:
        """Fetch market data for all configured tickers."""
        print("Fetching Market data from Yahoo Finance...")
        ticker_list = list(self.tickers.values())
        
        # Download data
        # auto_adjust=False: We get 'Close' and 'Adj Close'. 
        # using 'Close' for everything is simpler for mixing indices and ETFs in this context,
        # though 'Adj Close' is better for SPY returns. 
        # Given we want price levels for charts (SPY), Close is fine.
        try:
            data = yf.download(ticker_list, period=period, progress=False, auto_adjust=False)
        except Exception as e:
            print(f"Error downloading data: {e}")
            return pd.DataFrame()

        if data.empty:
            return pd.DataFrame()

        # Extract Close prices
        # yfinance returns a MultiIndex (Price, Ticker) if multiple tickers
        if isinstance(data.columns, pd.MultiIndex):
            try:
                df = data['Close'].copy()
            except KeyError:
                # Fallback if 'Close' is missing (unlikely)
                df = data.xs('Close', level=0, axis=1).copy()
        else:
            # Single ticker case (unlikely but safe to handle)
            df = pd.DataFrame(data['Close'])
            # If single, columns might not be the ticker name, need to check
            # Usually yf.download for single ticker returns just the OHLCV columns
            # We need to map it to the single ticker we requested
            df.columns = ticker_list

        # Rename columns from Ticker to Friendly Name
        # self.tickers is Friendly -> Ticker
        ticker_to_friendly = {v: k for k, v in self.tickers.items()}
        
        # Rename
        df = df.rename(columns=ticker_to_friendly)
        
        # Drop timezone if present to align with FRED (usually tz-naive)
        if df.index.tz is not None:
            df.index = df.index.tz_localize(None)
            
        return df

