"""
Trending-up strategy analysis engine.

Pure function interface:
    analyze(df, entry_order=1, regime_multiplier=1.0) -> TrendAnalysis

All logic is stateless. Input: OHLCV DataFrame (date index, ≥120 rows recommended).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import pandas as pd

# ── Base pyramid position fractions (entry order 1..4) ──────────────────────
_PYRAMID_BASE = [0.40, 0.30, 0.20, 0.10]

# ── Stop-loss / take-profit constants ────────────────────────────────────────
_INITIAL_STOP_LOSS_PCT = 0.065  # 6.5% initial stop
_TARGET_1_PCT = 0.25            # +25%
_TARGET_2_PCT = 0.45            # +45%
_TRAILING_STOP_PROFIT_MED = 0.30   # profit ≥ 30% → trail at 10%
_TRAILING_STOP_PROFIT_HIGH = 0.50  # profit ≥ 50% → trail at 12%
_TRAILING_STOP_PCT_MED = 0.10
_TRAILING_STOP_PCT_HIGH = 0.12

# ── Trend phase thresholds ────────────────────────────────────────────────────
_BREAKOUT_VOL_MULTIPLIER = 1.5
_PULLBACK_MA_BAND = 0.03          # ±3% of MA20
_PULLBACK_VOL_SHRINK = 0.80       # < 80% of MA20 volume
_ACCELERATION_DIST = 0.15         # > 15% above MA20
_CONSOLIDATION_RANGE = 0.05       # max 5% high-low range
_CONSOLIDATION_DAYS = 5           # at least 5 days
_TOPPING_VOL_LOOKBACK = 20

# ── Exhaustion signal constants ───────────────────────────────────────────────
_ADX_HIGH_THRESHOLD = 40
_STEEP_SLOPE_MULTIPLIER = 3.0


@dataclass
class ExhaustionSignals:
    vol_no_price: bool = False        # 天量滞涨
    rsi_divergence: bool = False      # RSI顶背离
    macd_histogram_shrink: bool = False  # MACD柱持续缩短
    steep_slope_acceleration: bool = False
    gap_up_long_upper_shadow: bool = False
    below_ma20_no_recovery: bool = False
    adx_peak_reversal: bool = False
    sector_peers_weaker: Optional[bool] = None   # cannot auto-detect
    fundamental_negative: Optional[bool] = None  # cannot auto-detect

    def triggered_count(self) -> int:
        flags = [
            self.vol_no_price, self.rsi_divergence, self.macd_histogram_shrink,
            self.steep_slope_acceleration, self.gap_up_long_upper_shadow,
            self.below_ma20_no_recovery, self.adx_peak_reversal,
        ]
        return sum(1 for f in flags if f)


@dataclass
class TrendAnalysis:
    # Inputs echo
    ticker: str = ""
    entry_price: float = 0.0

    # Trend confirmation (6 items)
    price_above_ma20: bool = False
    ma_bullish_alignment: bool = False
    adx_strong: bool = False
    higher_lows: bool = False
    pullback_volume_shrink: bool = False
    rsi_healthy: bool = False
    trend_score: int = 0
    is_uptrend: bool = False

    # Phase & strategy
    trend_phase: str = "unknown"
    recommended_strategy: str = ""
    strategy_detail: str = ""

    # Price targets
    stop_loss_price: float = 0.0
    target_price_1: float = 0.0
    target_price_2: float = 0.0
    trailing_stop_pct: float = _INITIAL_STOP_LOSS_PCT

    # Position sizing
    suggested_position_pct: float = 0.0

    # Exhaustion
    exhaustion_signals: ExhaustionSignals = field(default_factory=ExhaustionSignals)
    exit_warning: bool = False

    # Metadata
    data_insufficient: bool = False
    indicators: dict = field(default_factory=dict)


# ── Indicator helpers ─────────────────────────────────────────────────────────

def _compute_mas(df: pd.DataFrame) -> dict:
    close = df["close"]
    return {
        "ma20": close.rolling(20).mean(),
        "ma60": close.rolling(60).mean(),
        "ma120": close.rolling(120).mean(),
        "vol_ma20": df["volume"].rolling(20).mean(),
    }


def _compute_adx(df: pd.DataFrame) -> pd.Series:
    """ADX(14) computed from scratch to avoid pandas_ta compatibility issues."""
    try:
        import pandas_ta as ta
        adx_df = ta.adx(df["high"], df["low"], df["close"], length=14)
        if adx_df is not None and "ADX_14" in adx_df.columns:
            return adx_df["ADX_14"]
    except Exception:
        pass
    # Manual fallback
    return _adx_manual(df, 14)


def _adx_manual(df: pd.DataFrame, period: int = 14) -> pd.Series:
    high = df["high"]
    low = df["low"]
    close = df["close"]
    tr = pd.concat([
        high - low,
        (high - close.shift(1)).abs(),
        (low - close.shift(1)).abs(),
    ], axis=1).max(axis=1)
    dm_pos = (high - high.shift(1)).where((high - high.shift(1)) > (low.shift(1) - low), 0.0).clip(lower=0)
    dm_neg = (low.shift(1) - low).where((low.shift(1) - low) > (high - high.shift(1)), 0.0).clip(lower=0)
    atr = tr.ewm(alpha=1 / period, adjust=False).mean()
    di_pos = 100 * dm_pos.ewm(alpha=1 / period, adjust=False).mean() / atr.replace(0, np.nan)
    di_neg = 100 * dm_neg.ewm(alpha=1 / period, adjust=False).mean() / atr.replace(0, np.nan)
    dx = 100 * (di_pos - di_neg).abs() / (di_pos + di_neg).replace(0, np.nan)
    adx = dx.ewm(alpha=1 / period, adjust=False).mean()
    return adx


def _compute_rsi(df: pd.DataFrame, period: int = 14) -> pd.Series:
    delta = df["close"].diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / period, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1 / period, adjust=False).mean()
    rs = gain / loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def _compute_macd(df: pd.DataFrame) -> dict:
    close = df["close"]
    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    macd_line = ema12 - ema26
    signal_line = macd_line.ewm(span=9, adjust=False).mean()
    histogram = macd_line - signal_line
    return {"macd": macd_line, "signal": signal_line, "histogram": histogram}


def _compute_kdj(df: pd.DataFrame, n: int = 9, m1: int = 3, m2: int = 3) -> dict:
    low_n = df["low"].rolling(n).min()
    high_n = df["high"].rolling(n).max()
    rsv = (df["close"] - low_n) / (high_n - low_n).replace(0, np.nan) * 100
    k = rsv.ewm(alpha=1 / m1, adjust=False).mean()
    d = k.ewm(alpha=1 / m2, adjust=False).mean()
    j = 3 * k - 2 * d
    return {"k": k, "d": d, "j": j}


def _compute_volume_ratio(df: pd.DataFrame, vol_ma20: pd.Series) -> pd.Series:
    return df["volume"] / vol_ma20.replace(0, np.nan)


# ── Trend confirmation ────────────────────────────────────────────────────────

def _check_trend_confirmation(df: pd.DataFrame, ind: dict) -> dict:
    close = df["close"]
    last = close.iloc[-1]

    ma20_last = ind["ma20"].iloc[-1]
    ma60_last = ind["ma60"].iloc[-1]
    ma120_last = ind["ma120"].iloc[-1]
    adx_last = ind["adx"].iloc[-1] if not pd.isna(ind["adx"].iloc[-1]) else 0
    rsi_last = ind["rsi"].iloc[-1] if not pd.isna(ind["rsi"].iloc[-1]) else 50
    vol_ratio = ind["vol_ratio"].iloc[-1] if not pd.isna(ind["vol_ratio"].iloc[-1]) else 1.0

    price_above_ma20 = last > ma20_last if not pd.isna(ma20_last) else False
    ma_bullish_alignment = (
        not pd.isna(ma20_last) and not pd.isna(ma60_last) and not pd.isna(ma120_last)
        and ma20_last > ma60_last > ma120_last
    )
    adx_strong = adx_last > 25
    rsi_healthy = 40 <= rsi_last <= 70

    # Higher lows: check last 3 local lows in past 60 bars
    higher_lows = _check_higher_lows(df.tail(60))

    # Pullback volume shrink: recent pullback had volume < MA20 vol
    pullback_volume_shrink = _check_pullback_vol_shrink(df, ind["vol_ma20"])

    flags = [price_above_ma20, ma_bullish_alignment, adx_strong, higher_lows, pullback_volume_shrink, rsi_healthy]
    trend_score = sum(1 for f in flags if f)
    is_uptrend = trend_score >= 4

    return {
        "price_above_ma20": price_above_ma20,
        "ma_bullish_alignment": ma_bullish_alignment,
        "adx_strong": adx_strong,
        "higher_lows": higher_lows,
        "pullback_volume_shrink": pullback_volume_shrink,
        "rsi_healthy": rsi_healthy,
        "trend_score": trend_score,
        "is_uptrend": is_uptrend,
    }


def _check_higher_lows(df: pd.DataFrame) -> bool:
    """Detect if last 3 local lows are successively higher."""
    lows = df["low"]
    local_lows = []
    for i in range(1, len(lows) - 1):
        if lows.iloc[i] < lows.iloc[i - 1] and lows.iloc[i] < lows.iloc[i + 1]:
            local_lows.append(lows.iloc[i])
        if len(local_lows) >= 3:
            break
    if len(local_lows) < 3:
        return False
    return local_lows[-1] > local_lows[-2] > local_lows[-3]


def _check_pullback_vol_shrink(df: pd.DataFrame, vol_ma20: pd.Series) -> bool:
    """True if during the most recent pullback, volume shrank below 80% of MA20."""
    close = df["close"]
    if len(close) < 5:
        return False
    # Find last local low (pullback bottom) in past 20 bars
    tail = close.tail(20)
    min_idx = tail.idxmin()
    loc = df.index.get_loc(min_idx)
    if loc < 0:
        return False
    pullback_vol = df["volume"].iloc[loc]
    ma20_vol = vol_ma20.iloc[loc]
    if pd.isna(ma20_vol) or ma20_vol == 0:
        return False
    return pullback_vol < ma20_vol * _PULLBACK_VOL_SHRINK


# ── Trend phase ───────────────────────────────────────────────────────────────

def _determine_trend_phase(df: pd.DataFrame, ind: dict) -> tuple[str, str, str]:
    """Returns (phase_key, strategy_name, strategy_detail)."""
    close = df["close"]
    last = close.iloc[-1]
    ma20 = ind["ma20"].iloc[-1]
    rsi = ind["rsi"].iloc[-1] if not pd.isna(ind["rsi"].iloc[-1]) else 50
    vol_ratio = ind["vol_ratio"].iloc[-1] if not pd.isna(ind["vol_ratio"].iloc[-1]) else 1.0
    adx = ind["adx"]

    # Priority 1: topping
    if _is_topping(df, ind):
        return "topping", "策略4：不操作", "出现天量滞涨或RSI顶背离，趋势可能衰竭，暂停新仓，准备减仓。"

    # Priority 2: acceleration
    if not pd.isna(ma20) and ma20 > 0:
        dist_pct = (last - ma20) / ma20
        if dist_pct > _ACCELERATION_DIST and rsi > 70:
            return "acceleration", "策略4：不追", (
                "⚠️ 当前处于加速段（价格偏离MA20超15%且RSI>70），绝对不追入。"
                "等待下次回踩MA20机会。"
            )

    # Priority 3: pullback
    if not pd.isna(ma20) and ma20 > 0:
        dist_pct = abs(last - ma20) / ma20
        if dist_pct <= _PULLBACK_MA_BAND and vol_ratio < _PULLBACK_VOL_SHRINK:
            return "pullback", "策略2：回踩均线买入 ★", (
                "价格回踩MA20获得支撑，成交量萎缩，是趋势行情中最优买点。"
                "等待止跌信号（十字星/锤子线/吞没形态）确认后建仓。"
            )

    # Priority 4: breakout
    if _is_breakout(df, ind):
        return "breakout", "策略1：突破买入", (
            "底部盘整后放量突破关键阻力位，可建初仓。"
            "成交量需超过MA20均量的1.5倍以上。"
        )

    # Priority 5: consolidation
    if _is_consolidation(df.tail(20)):
        return "consolidation", "策略3：缩量平台突破", (
            "上涨后出现横盘整固，成交量逐步萎缩。"
            "等待向上放量突破平台高点时入场。"
        )

    return "neutral", "观望", "趋势特征不明确，暂不操作。"


def _is_topping(df: pd.DataFrame, ind: dict) -> bool:
    if len(df) < _TOPPING_VOL_LOOKBACK:
        return False
    close = df["close"]
    volume = df["volume"]
    # 天量滞涨: volume hits 20-day high but price doesn't hit 20-day high
    recent = df.tail(_TOPPING_VOL_LOOKBACK)
    vol_new_high = volume.iloc[-1] >= recent["volume"].max() * 0.98
    price_new_high = close.iloc[-1] >= recent["close"].max() * 0.98
    if vol_new_high and not price_new_high:
        return True
    # RSI divergence: price higher but RSI lower (last 10 bars vs prev 10 bars)
    rsi = ind["rsi"]
    if len(rsi) >= 20:
        price_rising = close.iloc[-1] > close.iloc[-11]
        rsi_falling = rsi.iloc[-1] < rsi.iloc[-11]
        if price_rising and rsi_falling and rsi.iloc[-1] > 60:
            return True
    return False


def _is_breakout(df: pd.DataFrame, ind: dict) -> bool:
    if len(df) < 25:
        return False
    close = df["close"]
    volume = df["volume"]
    # Price breaks 20-day high on volume
    high_20 = close.tail(21).iloc[:-1].max()
    vol_ratio = ind["vol_ratio"].iloc[-1]
    return close.iloc[-1] > high_20 and (not pd.isna(vol_ratio)) and vol_ratio >= _BREAKOUT_VOL_MULTIPLIER


def _is_consolidation(df: pd.DataFrame) -> bool:
    if len(df) < _CONSOLIDATION_DAYS:
        return False
    tail = df.tail(_CONSOLIDATION_DAYS)
    price_range = (tail["high"].max() - tail["low"].min()) / tail["close"].mean()
    return price_range <= _CONSOLIDATION_RANGE


# ── Pyramid position ──────────────────────────────────────────────────────────

def _compute_pyramid_position(entry_order: int, regime_multiplier: float) -> float:
    idx = min(max(entry_order, 1), 4) - 1
    base = _PYRAMID_BASE[idx]
    return round(base * regime_multiplier, 4)


# ── Exhaustion signals ────────────────────────────────────────────────────────

def _check_exhaustion_signals(df: pd.DataFrame, ind: dict) -> ExhaustionSignals:
    signals = ExhaustionSignals()
    if len(df) < 20:
        return signals

    close = df["close"]
    volume = df["volume"]
    high = df["high"]
    open_ = df["open"]
    ma20 = ind["ma20"]
    adx = ind["adx"]
    rsi = ind["rsi"]
    hist = ind["macd"]["histogram"]

    # 1. Vol no price (天量滞涨)
    recent = df.tail(_TOPPING_VOL_LOOKBACK)
    vol_high = volume.iloc[-1] >= recent["volume"].max() * 0.98
    price_high = close.iloc[-1] >= recent["close"].max() * 0.98
    signals.vol_no_price = vol_high and not price_high

    # 2. RSI divergence
    if len(rsi) >= 15:
        price_up = close.iloc[-1] > close.iloc[-8]
        rsi_down = rsi.iloc[-1] < rsi.iloc[-8]
        signals.rsi_divergence = price_up and rsi_down and rsi.iloc[-1] > 55

    # 3. MACD histogram shrinking 3 consecutive bars
    if len(hist) >= 4:
        last3 = hist.iloc[-3:]
        if all(last3 > 0):  # all positive (bullish side)
            signals.macd_histogram_shrink = hist.iloc[-3] > hist.iloc[-2] > hist.iloc[-1]

    # 4. Steep slope acceleration
    if len(close) >= 25:
        daily_avg_20 = abs(float(close.iloc[-21]) - float(close.iloc[-1])) / 20 / float(close.iloc[-21])
        recent_5_daily = abs(float(close.iloc[-1]) - float(close.iloc[-6])) / 5 / float(close.iloc[-6])
        if daily_avg_20 > 0:
            signals.steep_slope_acceleration = recent_5_daily > daily_avg_20 * _STEEP_SLOPE_MULTIPLIER

    # 5. Gap up + long upper shadow
    gap_up = open_.iloc[-1] > close.iloc[-2] * 1.005
    body = abs(close.iloc[-1] - open_.iloc[-1])
    upper_shadow = high.iloc[-1] - max(close.iloc[-1], open_.iloc[-1])
    signals.gap_up_long_upper_shadow = gap_up and (upper_shadow > body * 2) if body > 0 else False

    # 6. Below MA20 no recovery (last bar)
    ma20_last = ma20.iloc[-1]
    if not pd.isna(ma20_last):
        below_ma20 = close.iloc[-1] < ma20_last
        prev_above = close.iloc[-2] >= ma20.iloc[-2] if not pd.isna(ma20.iloc[-2]) else True
        signals.below_ma20_no_recovery = below_ma20 and prev_above

    # 7. ADX peak reversal
    if len(adx) >= 5:
        adx_vals = adx.dropna()
        if len(adx_vals) >= 5:
            peak = adx_vals.iloc[-5:].max()
            signals.adx_peak_reversal = peak > _ADX_HIGH_THRESHOLD and adx_vals.iloc[-1] < peak * 0.95

    return signals


# ── Trailing stop ─────────────────────────────────────────────────────────────

def _trailing_stop_pct(entry_price: float, current_price: float) -> float:
    if entry_price <= 0:
        return _INITIAL_STOP_LOSS_PCT
    profit_pct = (current_price - entry_price) / entry_price
    if profit_pct >= _TRAILING_STOP_PROFIT_HIGH:
        return _TRAILING_STOP_PCT_HIGH
    if profit_pct >= _TRAILING_STOP_PROFIT_MED:
        return _TRAILING_STOP_PCT_MED
    return _INITIAL_STOP_LOSS_PCT


# ── Public API ────────────────────────────────────────────────────────────────

def analyze(
    df: pd.DataFrame | None,
    ticker: str = "",
    entry_order: int = 1,
    regime_multiplier: float = 1.0,
) -> TrendAnalysis:
    """
    Main entry point. Pure function — no I/O side effects.

    Args:
        df: OHLCV DataFrame with date index. Needs ≥120 rows for full analysis.
        ticker: Display name.
        entry_order: 1–4 pyramid entry sequence.
        regime_multiplier: Position ceiling from macro regime (0–1).

    Returns:
        TrendAnalysis dataclass.
    """
    if df is None or df.empty or len(df) < 30:
        return TrendAnalysis(ticker=ticker, data_insufficient=True)

    data_insufficient = len(df) < 120

    # Compute indicators
    mas = _compute_mas(df)
    adx_series = _compute_adx(df)
    rsi_series = _compute_rsi(df)
    macd_dict = _compute_macd(df)
    kdj_dict = _compute_kdj(df)
    vol_ratio = _compute_volume_ratio(df, mas["vol_ma20"])

    ind = {
        **mas,
        "adx": adx_series,
        "rsi": rsi_series,
        "macd": macd_dict,
        "kdj": kdj_dict,
        "vol_ratio": vol_ratio,
    }

    # Trend confirmation
    confirm = _check_trend_confirmation(df, ind)

    # Phase
    trend_phase, strategy_name, strategy_detail = _determine_trend_phase(df, ind)

    # Prices
    entry_price = float(df["close"].iloc[-1])
    stop_loss = round(entry_price * (1 - _INITIAL_STOP_LOSS_PCT), 2)
    target1 = round(entry_price * (1 + _TARGET_1_PCT), 2)
    target2 = round(entry_price * (1 + _TARGET_2_PCT), 2)
    trail_stop = _trailing_stop_pct(entry_price, entry_price)

    # Position
    suggested_pos = _compute_pyramid_position(entry_order, regime_multiplier)

    # Exhaustion
    exhaustion = _check_exhaustion_signals(df, ind)
    exit_warning = exhaustion.triggered_count() >= 2

    # Pack indicators for charting (serializable values)
    indicators_export = {
        "ma20": mas["ma20"],
        "ma60": mas["ma60"],
        "ma120": mas["ma120"],
        "vol_ma20": mas["vol_ma20"],
        "adx": adx_series,
        "rsi": rsi_series,
        "macd": macd_dict["macd"],
        "macd_signal": macd_dict["signal"],
        "macd_histogram": macd_dict["histogram"],
        "kdj_k": kdj_dict["k"],
        "kdj_d": kdj_dict["d"],
        "vol_ratio": vol_ratio,
    }

    return TrendAnalysis(
        ticker=ticker,
        entry_price=entry_price,
        price_above_ma20=confirm["price_above_ma20"],
        ma_bullish_alignment=confirm["ma_bullish_alignment"],
        adx_strong=confirm["adx_strong"],
        higher_lows=confirm["higher_lows"],
        pullback_volume_shrink=confirm["pullback_volume_shrink"],
        rsi_healthy=confirm["rsi_healthy"],
        trend_score=confirm["trend_score"],
        is_uptrend=confirm["is_uptrend"],
        trend_phase=trend_phase,
        recommended_strategy=strategy_name,
        strategy_detail=strategy_detail,
        stop_loss_price=stop_loss,
        target_price_1=target1,
        target_price_2=target2,
        trailing_stop_pct=trail_stop,
        suggested_position_pct=suggested_pos,
        exhaustion_signals=exhaustion,
        exit_warning=exit_warning,
        data_insufficient=data_insufficient,
        indicators=indicators_export,
    )
