from typing import Optional

import numpy as np
import pandas as pd

from .logger import get_logger

log = get_logger("indicators")


# ── helpers ──────────────────────────────────────────────────────────────────

def _sma(series: pd.Series, n: int) -> pd.Series:
    return series.rolling(window=n, min_periods=1).mean()


def _ema(series: pd.Series, n: int) -> pd.Series:
    return series.ewm(span=n, adjust=False).mean()


def _rsi(series: pd.Series, n: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = (-delta).clip(lower=0)
    avg_gain = gain.ewm(alpha=1 / n, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / n, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def _macd(series: pd.Series):
    ema12 = _ema(series, 12)
    ema26 = _ema(series, 26)
    macd_line = ema12 - ema26
    signal = _ema(macd_line, 9)
    hist = macd_line - signal
    return macd_line, signal, hist


def _bollinger(series: pd.Series, n: int = 20, k: float = 2.0):
    mid = _sma(series, n)
    std = series.rolling(window=n, min_periods=1).std()
    upper = mid + k * std
    lower = mid - k * std
    width = (upper - lower) / mid.replace(0, np.nan)
    return upper, mid, lower, width


def _atr(high: pd.Series, low: pd.Series, close: pd.Series, n: int = 14) -> pd.Series:
    prev_close = close.shift(1)
    tr = pd.concat(
        [high - low, (high - prev_close).abs(), (low - prev_close).abs()], axis=1
    ).max(axis=1)
    return tr.ewm(alpha=1 / n, adjust=False).mean()


def _adx(high: pd.Series, low: pd.Series, close: pd.Series, n: int = 14) -> pd.Series:
    up_move = high.diff()
    down_move = (-low.diff())
    plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
    minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)
    atr = _atr(high, low, close, n)
    plus_di = 100 * pd.Series(plus_dm, index=close.index).ewm(alpha=1 / n, adjust=False).mean() / atr.replace(0, np.nan)
    minus_di = 100 * pd.Series(minus_dm, index=close.index).ewm(alpha=1 / n, adjust=False).mean() / atr.replace(0, np.nan)
    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)
    adx = dx.ewm(alpha=1 / n, adjust=False).mean()
    return adx


# ── candlestick patterns ──────────────────────────────────────────────────────

def _bullish_engulfing(open_: pd.Series, high: pd.Series, low: pd.Series, close: pd.Series) -> pd.Series:
    """Previous candle bearish, current candle bullish and fully engulfs previous body."""
    prev_bearish = close.shift(1) < open_.shift(1)
    curr_bullish = close > open_
    engulfs = (close > open_.shift(1)) & (open_ < close.shift(1))
    return (prev_bearish & curr_bullish & engulfs).astype(bool)


def _hammer(open_: pd.Series, high: pd.Series, low: pd.Series, close: pd.Series) -> pd.Series:
    """Small body at top, long lower shadow >= 2x body, minimal upper shadow."""
    body = (close - open_).abs()
    lower_shadow = pd.concat([open_, close], axis=1).min(axis=1) - low
    upper_shadow = high - pd.concat([open_, close], axis=1).max(axis=1)
    day_range = (high - low).replace(0, np.nan)
    small_body = body < day_range * 0.35
    long_lower = lower_shadow >= body * 2.0
    short_upper = upper_shadow <= body * 0.5
    return (small_body & long_lower & short_upper).astype(bool)


def _dragonfly_doji(open_: pd.Series, high: pd.Series, low: pd.Series, close: pd.Series) -> pd.Series:
    """Open ≈ Close (tiny body), long lower shadow, almost no upper shadow."""
    body = (close - open_).abs()
    day_range = (high - low).replace(0, np.nan)
    doji_body = body <= day_range * 0.1
    lower_shadow = pd.concat([open_, close], axis=1).min(axis=1) - low
    upper_shadow = high - pd.concat([open_, close], axis=1).max(axis=1)
    long_lower = lower_shadow >= day_range * 0.6
    tiny_upper = upper_shadow <= day_range * 0.1
    return (doji_body & long_lower & tiny_upper).astype(bool)


def _inside_bar_breakout(open_: pd.Series, high: pd.Series, low: pd.Series, close: pd.Series) -> pd.Series:
    """Current day closes above the high of an inside bar (previous candle was inside the one before)."""
    inside = (high.shift(1) <= high.shift(2)) & (low.shift(1) >= low.shift(2))
    breakout = close > high.shift(1)
    return (inside & breakout).astype(bool)


# ── true VCP (Volatility Contraction Pattern) ────────────────────────────────

def _detect_vcp(high: pd.Series, low: pd.Series, volume: pd.Series, lookback: int = 60) -> pd.Series:
    """
    Detects a proper VCP: at least 3 price contractions (each swing smaller than
    the previous) with declining volume across contractions, in the last `lookback` bars.
    Returns a boolean Series — True on bars where a valid VCP is present.
    """
    n = len(high)
    result = np.zeros(n, dtype=bool)

    h = high.to_numpy()
    l = low.to_numpy()
    v = volume.to_numpy()

    for i in range(lookback, n):
        window_h = h[i - lookback:i + 1]
        window_l = l[i - lookback:i + 1]
        window_v = v[i - lookback:i + 1]

        # Find local swing highs (peak if higher than 3 bars on each side)
        swings = []
        for j in range(3, len(window_h) - 3):
            if window_h[j] == max(window_h[j - 3:j + 4]):
                swing_range = window_h[j] - min(window_l[max(0, j - 3):j + 4])
                avg_vol = window_v[max(0, j - 2):j + 3].mean()
                swings.append((j, swing_range, avg_vol))

        if len(swings) < 3:
            continue

        # Check last 3 swings are contracting in range and volume
        last3 = swings[-3:]
        ranges = [s[1] for s in last3]
        vols = [s[2] for s in last3]

        contracting_range = ranges[0] > ranges[1] > ranges[2]
        contracting_vol = vols[0] > vols[2]  # overall volume declining

        if contracting_range and contracting_vol:
            result[i] = True

    return pd.Series(result, index=high.index)


# ── weekly indicators (resampled from daily) ──────────────────────────────────

def _add_weekly_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """
    Resample daily OHLCV to weekly, compute weekly MA20 and RSI, then
    forward-fill back onto the daily index.
    """
    weekly = df[["Open", "High", "Low", "Close", "Volume"]].resample("W").agg({
        "Open": "first",
        "High": "max",
        "Low": "min",
        "Close": "last",
        "Volume": "sum",
    }).dropna()

    if len(weekly) < 5:
        df["W_MA20"] = np.nan
        df["W_RSI"] = np.nan
        df["W_Trend"] = False
        return df

    weekly["W_MA20"] = _sma(weekly["Close"], 20)
    weekly["W_RSI"] = _rsi(weekly["Close"], 14)

    # Forward-fill weekly values onto daily index
    df = df.copy()
    df["W_MA20"] = weekly["W_MA20"].reindex(df.index, method="ffill")
    df["W_RSI"] = weekly["W_RSI"].reindex(df.index, method="ffill")
    # Weekly trend: close above weekly MA20 AND weekly RSI > 50
    w_trend = ((weekly["Close"] > weekly["W_MA20"]) & (weekly["W_RSI"] > 50))
    df["W_Trend"] = w_trend.reindex(df.index, method="ffill").fillna(False).astype(bool)

    return df


# ── main ─────────────────────────────────────────────────────────────────────

def add_indicators(df: pd.DataFrame, symbol: str = "?") -> Optional[pd.DataFrame]:
    if df is None or len(df) < 50:
        log.warning("%s  SKIP indicators — insufficient rows (%s)", symbol, len(df) if df is not None else 0)
        return None

    try:
        df = df.copy()
        close  = df["Close"].astype(float)
        high   = df["High"].astype(float)
        low    = df["Low"].astype(float)
        open_  = df["Open"].astype(float)
        volume = df["Volume"].astype(float)

        df["RSI"] = _rsi(close, 14)
        df["MACD"], df["MACD_Signal"], df["MACD_Hist"] = _macd(close)
        df["BB_Upper"], df["BB_Mid"], df["BB_Lower"], df["BB_Width"] = _bollinger(close, 20)

        df["MA20"]  = _sma(close, 20)
        df["MA50"]  = _sma(close, 50)
        df["MA150"] = _sma(close, 150)
        df["MA200"] = _sma(close, 200)
        df["EMA21"] = _ema(close, 21)

        df["ADX"] = _adx(high, low, close, 14)
        df["ATR"] = _atr(high, low, close, 14)

        df["Vol_MA20"]  = _sma(volume, 20)
        df["Rel_Volume"] = volume / df["Vol_MA20"].replace(0, np.nan)

        df["High_52W"] = high.rolling(252, min_periods=60).max()
        df["Low_52W"]  = low.rolling(252, min_periods=60).min()
        df["Pct_From_52W_High"] = (close - df["High_52W"]) / df["High_52W"].replace(0, np.nan) * 100

        df["ROC_5"]   = close.pct_change(5)   * 100
        df["ROC_10"]  = close.pct_change(10)  * 100
        df["ROC_20"]  = close.pct_change(20)  * 100
        df["ROC_126"] = close.pct_change(126) * 100

        day_range = (high - low).replace(0, np.nan)
        df["Close_Pct_Range"] = (close - low) / day_range

        df["Vol_MA5"]   = _sma(volume, 5)
        df["Vol_Trend"] = df["Vol_MA5"] / df["Vol_MA20"].replace(0, np.nan)

        # ── UT Bot trailing stop ──────────────────────────────────────────
        n_loss  = 2.0 * _atr(high, low, close, 10)
        ut_stop = np.zeros(len(close))
        c_arr   = close.to_numpy()
        nl_arr  = n_loss.to_numpy()

        for i in range(1, len(c_arr)):
            prev     = ut_stop[i - 1]
            src, prev_src = c_arr[i], c_arr[i - 1]
            nl       = nl_arr[i]
            if src > prev and prev_src > prev:
                ut_stop[i] = max(prev, src - nl)
            elif src < prev and prev_src < prev:
                ut_stop[i] = min(prev, src + nl)
            elif src > prev:
                ut_stop[i] = src - nl
            else:
                ut_stop[i] = src + nl

        df["UT_Stop"] = ut_stop
        df["UT_Buy"]  = (close > df["UT_Stop"]) & (close.shift(1) <= df["UT_Stop"].shift(1))
        df["UT_Sell"] = (close < df["UT_Stop"]) & (close.shift(1) >= df["UT_Stop"].shift(1))

        # ── Candlestick patterns ──────────────────────────────────────────
        df["Pat_Engulfing"]   = _bullish_engulfing(open_, high, low, close)
        df["Pat_Hammer"]      = _hammer(open_, high, low, close)
        df["Pat_Doji"]        = _dragonfly_doji(open_, high, low, close)
        df["Pat_InsideBreak"] = _inside_bar_breakout(open_, high, low, close)

        df["Candle_Signal"] = (
            df["Pat_Engulfing"] | df["Pat_Hammer"] |
            df["Pat_Doji"]      | df["Pat_InsideBreak"] |
            df["Pat_Engulfing"].shift(1).fillna(False) |
            df["Pat_Hammer"].shift(1).fillna(False)
        ).astype(bool)

        # ── True VCP ─────────────────────────────────────────────────────
        df["VCP"] = _detect_vcp(high, low, volume, lookback=60)

        # ── Weekly indicators ─────────────────────────────────────────────
        df = _add_weekly_indicators(df)

        log.info("%s  indicators OK (%d rows)", symbol, len(df))
        return df

    except Exception as exc:
        log.error("%s  INDICATOR ERROR — %s: %s", symbol, type(exc).__name__, exc)
        return None
