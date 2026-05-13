import random
from typing import Optional

import numpy as np
import pandas as pd

from .data_fetcher import fetch_stock_data
from .indicators import add_indicators
from .logger import get_logger
from .screener import _dynamic_target, _dynamic_sl

log = get_logger("backtester")


def _build_nifty_regime(period: str = "2y") -> dict:
    nifty_df = fetch_stock_data("^NSEI", period=period)
    if nifty_df is None or nifty_df.empty:
        return {}
    close = nifty_df["Close"].astype(float)
    ma200 = close.rolling(200, min_periods=50).mean()
    regime = {}
    for dt, c, ma in zip(nifty_df.index, close, ma200):
        key = str(dt.date())
        regime[key] = bool(c > ma) if not pd.isna(ma) else True
    return regime


def _count_signals(df: pd.DataFrame, i: int, params: dict, nifty_roc20: dict | None = None) -> int:
    row = df.iloc[i]
    prev = df.iloc[i - 1]

    if pd.isna(row["RSI"]) or pd.isna(row["MACD"]) or pd.isna(row["ADX"]):
        return 0

    recent_widths = df["BB_Width"].dropna().iloc[max(0, i - 60):i]
    tight_base = bool(row["BB_Width"] <= recent_widths.quantile(0.40)) if len(recent_widths) >= 10 else False
    true_vcp = bool(row.get("VCP", False))

    date_str = str(df.index[i].date())
    nifty_roc = nifty_roc20.get(date_str, 0.0) if nifty_roc20 else 0.0
    stock_roc20 = float(row["ROC_20"]) if not pd.isna(row["ROC_20"]) else 0.0

    checks = [
        row["Rel_Volume"] >= params["min_rel_volume"],
        float(row["Close"]) > float(prev["High"]),
        params["rsi_min"] <= row["RSI"] <= params["rsi_max"],
        bool(row["MACD"] > row["MACD_Signal"]) and bool(row["MACD_Hist"] > 0),
        bool(row["Close"] > row["MA20"]),
        bool(row["Close"] > row["MA50"]),
        row["Pct_From_52W_High"] >= params["pct_from_52w_high"],
        row["ADX"] >= params["adx_min"],
        bool(row["Close"] >= row["BB_Upper"]),
        bool(row["ROC_5"] > 1.0),
        bool(row["Close"] > row["MA150"]),
        stock_roc20 > nifty_roc,
        tight_base or true_vcp,
        float(row["Close_Pct_Range"]) > 0.65 if not pd.isna(row["Close_Pct_Range"]) else False,
        float(row["Vol_Trend"]) > 1.0 if not pd.isna(row["Vol_Trend"]) else False,
        # new signals
        bool(row.get("W_Trend", False)),
        bool(row.get("Candle_Signal", False)),
    ]
    return sum(checks)


def _dynamic_hold_days(score: int, adx: float, ut_bot_buy: bool) -> int:
    """Maximum days to hold before forced exit — mirrors screener hold suggestion."""
    if score >= 75 and adx >= 30 and ut_bot_buy:
        return 90
    elif score >= 60 and adx >= 22:
        return 45
    elif score >= 45:
        return 20
    else:
        return 10


def backtest_symbol(symbol: str, params: dict, nifty_regime: dict, nifty_roc20: dict | None = None) -> Optional[list]:
    df = fetch_stock_data(symbol, period="2y")
    if df is None or len(df) < 200:
        log.warning("%s  SKIP — insufficient data for backtest (need 200 bars, got %d)",
                    symbol, len(df) if df is not None else 0)
        return None

    df = add_indicators(df)
    if df is None:
        log.error("%s  SKIP — indicator calculation failed during backtest", symbol)
        return None

    sl_pct = params["stop_loss_pct"]
    min_signals = params.get("min_signal_count", 6)
    require_bull = params.get("require_bull_market", True)
    peak_window = 90
    trades = []

    for i in range(61, len(df) - peak_window - 2):
        date_str = str(df.index[i].date())
        if require_bull and not nifty_regime.get(date_str, True):
            continue

        if _count_signals(df, i, params, nifty_roc20) < min_signals:
            continue

        row = df.iloc[i]
        entry = float(df.iloc[i + 1]["Open"])
        if entry <= 0:
            continue

        # Dynamic target and SL at signal bar
        atr = float(row["ATR"]) if not pd.isna(row["ATR"]) else entry * 0.02
        ut_stop_val = float(row["UT_Stop"])
        score_approx = min(100, _count_signals(df, i, params, nifty_roc20) * 6)
        pct_52w = float(row["Pct_From_52W_High"]) if not pd.isna(row["Pct_From_52W_High"]) else -10.0
        adx_val = float(row["ADX"]) if not pd.isna(row["ADX"]) else 0.0
        ut_bot = bool(row["UT_Buy"])

        target_price, _ = _dynamic_target(entry, atr, score_approx, pct_52w)
        sl_price = _dynamic_sl(entry, atr, ut_stop_val, sl_pct)

        # Dynamic hold: based on setup quality
        hold = _dynamic_hold_days(score_approx, adx_val, ut_bot)

        outcome = "TIME_EXIT"
        exit_price = float(df.iloc[min(i + hold, len(df) - 1)]["Close"])
        exit_day = hold

        highest_close = entry
        trail_active = False

        for j in range(1, hold + 1):
            if i + j >= len(df):
                break

            day_high  = float(df.iloc[i + j]["High"])
            day_low   = float(df.iloc[i + j]["Low"])
            day_close = float(df.iloc[i + j]["Close"])

            if day_high > highest_close:
                highest_close = day_high

            gain_pct = (highest_close - entry) / entry * 100
            if gain_pct >= 4.0:
                trail_active = True
                sl_price = max(sl_price, highest_close * 0.98)
            elif gain_pct >= 3.0:
                sl_price = max(sl_price, entry)

            # UT Sell exit — primary dynamic exit
            ut_sell = bool(df.iloc[i + j].get("UT_Sell", False))
            if ut_sell and j >= 3:  # ignore UT Sell in first 3 days (noise)
                exit_price = day_close
                exit_day = j
                outcome = "UT_SELL"
                break

            if day_high >= target_price:
                exit_price = target_price
                exit_day = j
                outcome = "TARGET_HIT"
                break
            elif day_low <= sl_price:
                exit_price = sl_price
                exit_day = j
                outcome = "TRAIL_STOP" if trail_active else "STOP_LOSS"
                break

        pnl_pct = (exit_price - entry) / entry * 100

        # Peak return within 90-day window
        peak_price = entry
        days_to_peak = 0
        for k in range(1, min(peak_window + 1, len(df) - i - 1)):
            day_high = float(df.iloc[i + k]["High"])
            if day_high > peak_price:
                peak_price = day_high
                days_to_peak = k

        peak_return_pct = round((peak_price - entry) / entry * 100, 2)
        left_on_table = round(peak_return_pct - pnl_pct, 2)

        trades.append({
            "symbol": symbol,
            "entry_date": df.index[i + 1].date(),
            "entry_price": round(entry, 2),
            "exit_price": round(exit_price, 2),
            "exit_day": exit_day,
            "hold_budget": hold,
            "outcome": outcome,
            "pnl_pct": round(pnl_pct, 2),
            "peak_return_pct": peak_return_pct,
            "days_to_peak": days_to_peak,
            "left_on_table": left_on_table,
        })

    return trades


def run_backtest(symbols: list, params: dict, sample_size: int = 30) -> Optional[dict]:
    log.info("─── Backtest starting — sampling %d of %d symbols, 2-year window", sample_size, len(symbols))

    nifty_regime = _build_nifty_regime(period="2y")
    if not nifty_regime:
        log.error("Could not build Nifty regime map — backtest regime filter will default to BULLISH everywhere")

    nifty_df = fetch_stock_data("^NSEI", period="2y")
    nifty_roc20: dict = {}
    if nifty_df is not None:
        nifty_close = nifty_df["Close"].astype(float)
        nifty_roc_series = nifty_close.pct_change(20) * 100
        for dt, val in zip(nifty_df.index, nifty_roc_series):
            nifty_roc20[str(dt.date())] = float(val) if not pd.isna(val) else 0.0
    else:
        log.error("Could not fetch Nifty 50 data for backtest RS comparison")

    sample = random.sample(symbols, min(sample_size, len(symbols)))
    all_trades: list[dict] = []

    for sym in sample:
        try:
            trades = backtest_symbol(sym, params, nifty_regime, nifty_roc20)
            if trades:
                log.info("%s  backtest complete — %d trades found", sym, len(trades))
                all_trades.extend(trades)
        except Exception as exc:
            log.error("%s  backtest failed — %s: %s", sym, type(exc).__name__, exc)

    if not all_trades:
        log.warning("Backtest produced 0 trades — check signal thresholds or market regime filter")
        return None

    df = pd.DataFrame(all_trades).sort_values("entry_date")

    winners = df[df["pnl_pct"] > 0]
    losers = df[df["pnl_pct"] <= 0]

    win_rate = len(winners) / len(df) * 100
    avg_win = winners["pnl_pct"].mean() if len(winners) else 0.0
    avg_loss = losers["pnl_pct"].mean() if len(losers) else 0.0
    avg_return = df["pnl_pct"].mean()
    expectancy = (win_rate / 100 * avg_win) + ((1 - win_rate / 100) * avg_loss)

    df["cumulative_return"] = df["pnl_pct"].cumsum()

    outcome_counts = df["outcome"].value_counts().to_dict()

    avg_peak = df["peak_return_pct"].mean()
    avg_left = df["left_on_table"].mean()
    avg_days_to_peak = df["days_to_peak"].mean()
    avg_hold = df["exit_day"].mean()

    result = {
        "trades": df,
        "total_trades": len(df),
        "win_rate": round(win_rate, 1),
        "avg_win": round(avg_win, 2),
        "avg_loss": round(avg_loss, 2),
        "avg_return": round(avg_return, 2),
        "expectancy": round(expectancy, 2),
        "target_hit":     outcome_counts.get("TARGET_HIT", 0),
        "stop_loss_hit":  outcome_counts.get("STOP_LOSS", 0),
        "trail_stop_hit": outcome_counts.get("TRAIL_STOP", 0),
        "ut_sell_exit":   outcome_counts.get("UT_SELL", 0),
        "time_exit":      outcome_counts.get("TIME_EXIT", 0),
        "symbols_tested": len(sample),
        "bull_market_only": params.get("require_bull_market", True),
        "avg_peak_return":    round(avg_peak, 2),
        "avg_left_on_table":  round(avg_left, 2),
        "avg_days_to_peak":   round(avg_days_to_peak, 1),
        "avg_hold_days":      round(avg_hold, 1),
    }

    log.info(
        "─── Backtest complete — %d trades / %d symbols | win rate %.1f%% | avg return %.2f%% | expectancy %.2f%%",
        result["total_trades"], result["symbols_tested"],
        result["win_rate"], result["avg_return"], result["expectancy"],
    )
    return result
