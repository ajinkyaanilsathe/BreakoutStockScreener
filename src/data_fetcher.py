import os
import pickle
import time
from datetime import datetime, timedelta
from typing import Optional

import pandas as pd
import yfinance as yf

from .logger import get_logger

log = get_logger("data_fetcher")

CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".cache")
CACHE_TTL_HOURS = 6


def _cache_path(symbol: str, period: str) -> str:
    os.makedirs(CACHE_DIR, exist_ok=True)
    safe = symbol.replace("/", "_").replace("^", "IDX_")
    return os.path.join(CACHE_DIR, f"{safe}_{period}.pkl")


def _is_cache_fresh(path: str) -> bool:
    if not os.path.exists(path):
        return False
    age = datetime.now() - datetime.fromtimestamp(os.path.getmtime(path))
    return age < timedelta(hours=CACHE_TTL_HOURS)


def _load_cache(path: str) -> Optional[pd.DataFrame]:
    try:
        with open(path, "rb") as f:
            return pickle.load(f)
    except Exception:
        return None


def _save_cache(path: str, df: pd.DataFrame) -> None:
    try:
        with open(path, "wb") as f:
            pickle.dump(df, f)
    except Exception:
        pass


def fetch_stock_data(
    symbol: str, period: str = "1y", use_cache: bool = True
) -> Optional[pd.DataFrame]:
    path = _cache_path(symbol, period)
    if use_cache and _is_cache_fresh(path):
        log.debug("%s  cache HIT (%s)", symbol, period)
        return _load_cache(path)

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
        if use_cache:
            _save_cache(path, df)
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
