import time
from typing import Optional

import pandas as pd
import streamlit as st
import yfinance as yf

from .logger import get_logger

log = get_logger("data_fetcher")

_CACHE_TTL = 6 * 3600  # 6 hours


@st.cache_data(ttl=_CACHE_TTL, show_spinner=False)
def fetch_stock_data(symbol: str, period: str = "1y") -> Optional[pd.DataFrame]:
    ticker_sym = f"{symbol}.NS" if not symbol.startswith("^") else symbol
    log.info("%s  fetching from yfinance (%s)…", symbol, period)
    try:
        ticker = yf.Ticker(ticker_sym)
        df = ticker.history(period=period, auto_adjust=True, timeout=15)
        if df is None or df.empty:
            log.warning("%s  SKIP — yfinance returned empty data", symbol)
            return None
        drop_cols = [c for c in df.columns if c in ("Dividends", "Stock Splits", "Capital Gains")]
        df = df.drop(columns=drop_cols, errors="ignore")
        required = {"Open", "High", "Low", "Close", "Volume"}
        if not required.issubset(df.columns):
            log.error("%s  SKIP — missing OHLCV columns: %s", symbol, required - set(df.columns))
            return None
        for col in required:
            df[col] = pd.to_numeric(df[col], errors="coerce")
        df = df.dropna(subset=list(required))
        if len(df) < 30:
            log.warning("%s  SKIP — only %d rows after cleaning (need ≥30)", symbol, len(df))
            return None
        log.info("%s  OK — %d bars fetched", symbol, len(df))
        return df
    except Exception as exc:
        log.error("%s  FETCH ERROR — %s: %s", symbol, type(exc).__name__, exc)
        return None


def fetch_multiple(symbols: list, period: str = "1y", delay: float = 0.1) -> dict:
    results = {}
    for sym in symbols:
        results[sym] = fetch_stock_data(sym, period=period)
        time.sleep(delay)
    return results


def fetch_market_index(period: str = "1y") -> Optional[pd.DataFrame]:
    return fetch_stock_data("^NSEI", period=period)
