import pandas as pd
import numpy as np

def calculate_net_liquidity(df: pd.DataFrame) -> pd.DataFrame:
    """
    Calculate Net Liquidity = Fed Assets (WALCL) - RRP - TGA.
    Adds 'Net Liquidity' and 'Net Liquidity MA20' columns.
    """
    # Ensure working on a copy to avoid SettingWithCopyWarning
    df = df.copy()
    
    required = ['WALCL', 'RRP', 'TGA']
    if not all(col in df.columns for col in required):
        # If missing, we can't calculate. Return as is or raise.
        # For robustness, check overlap.
        missing = [col for col in required if col not in df.columns]
        # It's possible we are running on China data which doesn't have these.
        # So instead of raising, just return if main cols missing.
        return df
        
    # Formula: Walcl - RRP - TGA
    # Ensure units are consistent. 
    # FRED: WALCL (Millions), RRP (Billions), TGA (Billions) ?
    # Wait, need to check units.
    # WALCL: Millions of Dollars (e.g. 7,000,000 means 7 Trillion) -> 7,000,000 * 1M = 7T? 
    # Actually WALCL is in Millions. 7,000,000 M = 7,000 B = 7 T.
    # RRPONTSYD: Billions of Dollars.
    # WTREGEN: Billions of Dollars.
    
    # We need to normalize to Billions.
    # WALCL / 1000 = Billions.
    
    df['Net Liquidity'] = (df['WALCL'] / 1000) - df['RRP'] - df['TGA']
    
    # Add Moving Average
    df['Net Liquidity MA20'] = df['Net Liquidity'].rolling(window=20).mean()
    
    return df

def calculate_changes(df: pd.DataFrame) -> dict:
    """
    Calculate 1w, 2w, 1m changes for Net Liquidity and key assets.
    Returns a dictionary of metrics for the latest date.
    """
    if df.empty:
        return {}
        
    latest = df.iloc[-1]
    
    def get_change(col, days):
        if col not in df.columns: return 0, 0
        if len(df) <= days: return 0, 0
        
        prev = df[col].iloc[-days] # Approx days ago
        curr = df[col].iloc[-1]
        
        if pd.isna(prev) or pd.isna(curr): return 0, 0
        
        delta = curr - prev
        pct = (delta / prev) * 100 if prev != 0 else 0
        return delta, pct
    
    metrics = {}
    target_cols = ['Net Liquidity', 'SPY', 'VIX', 'DXY', 'BTC', 'MOVE', 'US10Y', 
                   'SH_Index', 'M1_M2_Gap', 'Social_Financing_Increment', 'Northbound_Net_Inflow', 'Southbound_Net_Inflow']
    
    for col in target_cols:
        if col in df.columns:
            d1w, p1w = get_change(col, 7)   # 1 week
            d2w, p2w = get_change(col, 14)  # 2 weeks
            d1m, p1m = get_change(col, 30)  # 1 month
            
            metrics[col] = {
                "current": latest[col],
                "1w_delta": d1w,
                "1w_pct": p1w,
                "2w_delta": d2w,
                "2w_pct": p2w,
                "1m_delta": d1m,
                "1m_pct": p1m
            }
            
    return metrics

def analyze_signals(df: pd.DataFrame) -> dict:
    """
    Generate traffic light signals based on trends and divergence.
    """
    if df.empty:
        return {"Overall": "GRAY", "Reason": "No Data"}
        
    latest = df.iloc[-1]
    signals = {}
    
    # 1. Net Liquidity Trend
    # Green if Price > MA20
    if 'Net Liquidity' in df.columns and 'Net Liquidity MA20' in df.columns:
        net_liq = latest['Net Liquidity']
        ma20 = latest['Net Liquidity MA20']
        
        if pd.isna(ma20):
            liq_trend = "NEUTRAL"
        else:
            liq_trend = "EXPANDING" if net_liq > ma20 else "CONTRACTING"
    else:
        liq_trend = "UNKNOWN"
        
    signals['Liquidity Trend'] = liq_trend
    
    # 2. VIX vs MOVE Divergence
    # Normal: VIX and MOVE move together.
    # Danger: VIX Low (<20), MOVE High (>120) -> Bond market stress not yet in equities.
    vix = latest.get('VIX', 0)
    move = latest.get('MOVE', 0)
    
    divergence = "NORMAL"
    reason = "Normal Volatility"
    
    if vix < 20 and move > 120:
        divergence = "DANGER"
        reason = "Bond Volatility High, Equity Complacent"
    elif vix > 30:
        divergence = "HIGH_VOL"
        reason = "High Equity Volatility"
        
    signals['Volatility Regime'] = divergence
    signals['Volatility Reason'] = reason
    
    # Overall Traffic Light
    # GREEN: Expanding Liq + Normal/Low Vol
    # RED: Contracting Liq OR Danger Vol
    # YELLOW: Mixed
    
    if liq_trend == "EXPANDING" and divergence == "NORMAL":
        signals['Overall'] = "GREEN"
        signals['Overall_Reason'] = "Liquidity Supporting Markets"
    elif liq_trend == "CONTRACTING" or divergence == "DANGER" or divergence == "HIGH_VOL":
        signals['Overall'] = "RED"
        signals['Overall_Reason'] = "Liquidity Drag or Volatility Stress"
        if divergence == "DANGER": signals['Overall_Reason'] += " (Bond Stress)"
    else:
        signals['Overall'] = "YELLOW"
        signals['Overall_Reason'] = "Mixed Signals"
        
    return signals

def analyze_china_signals(df: pd.DataFrame) -> dict:
    """
    Generate traffic light signals for China/HK markets.
    """
    if df.empty:
        return {"Overall": "GRAY", "Reason": "No Data"}

    latest = df.iloc[-1]
    signals = {}
    
    # 1. Macro: M1-M2 Gap (Liquidity Trap)
    # Green: Gap > 0 (Active)
    # Red: Gap < 0 (Trap)
    m1_m2_gap = latest.get('M1_M2_Gap', 0)
    if pd.isna(m1_m2_gap): m1_m2_gap = 0
    
    if m1_m2_gap > 0:
        signals['Macro_Liquidity'] = "ACTIVE"
        signals['Macro_Reason'] = "M1 > M2 (Money Active)"
    else:
        signals['Macro_Liquidity'] = "TRAP"
        signals['Macro_Reason'] = "M1 < M2 (Liquidity Trap)"

    # 2. Southbound Flows (still disclosed daily; northbound stopped Aug 2024)
    sb_flow = latest.get('Southbound_Net_Inflow', 0)
    if pd.isna(sb_flow): sb_flow = 0

    if sb_flow > 0:
        signals['Foreign_Flow'] = "INFLOW"
        signals['Foreign_Reason'] = f"Southbound net buy {sb_flow:.1f}"
    else:
        signals['Foreign_Flow'] = "OUTFLOW"
        signals['Foreign_Reason'] = f"Southbound net sell {sb_flow:.1f}"

    # 3. Overall China Signal
    if signals['Macro_Liquidity'] == "ACTIVE" and signals['Foreign_Flow'] == "INFLOW":
        signals['Overall'] = "GREEN"
        signals['Overall_Reason'] = "Active Money + Southbound Inflow"
    elif signals['Macro_Liquidity'] == "TRAP" and signals['Foreign_Flow'] == "OUTFLOW":
        signals['Overall'] = "RED"
        signals['Overall_Reason'] = "Liquidity Trap + Capital Outflow"
    else:
        signals['Overall'] = "YELLOW"
        signals['Overall_Reason'] = "Mixed Signals"
        
    return signals
