import pandas as pd
import pytest
from src.analysis.engine import calculate_net_liquidity, calculate_changes, analyze_signals

def test_calculate_net_liquidity():
    data = {
        'WALCL': [8000000, 8100000], # Millions -> 8000 B
        'RRP': [2000, 2100], # Billions
        'TGA': [500, 400]    # Billions
    }
    df = pd.DataFrame(data)
    result = calculate_net_liquidity(df)
    
    # Row 0: 8000 - 2000 - 500 = 5500
    assert result['Net Liquidity'].iloc[0] == 5500.0
    # Row 1: 8100 - 2100 - 400 = 5600
    assert result['Net Liquidity'].iloc[1] == 5600.0

def test_analyze_signals_green():
    # Construct a DF where Net Liq > MA20
    # We need to simulate the structure expected by analyze_signals
    # It checks latest row
    df = pd.DataFrame({
        'Net Liquidity': [5100],
        'Net Liquidity MA20': [5000],
        'VIX': [15],
        'MOVE': [100]
    })
    signals = analyze_signals(df)
    assert signals['Overall'] == 'GREEN'

def test_analyze_signals_red_divergence():
    df = pd.DataFrame({
        'Net Liquidity': [5100],
        'Net Liquidity MA20': [5000], # Bullish Liq
        'VIX': [15],
        'MOVE': [130] # Bearish Vol Divergence
    })
    signals = analyze_signals(df)
    assert signals['Overall'] == 'RED' # DANGER overrides

