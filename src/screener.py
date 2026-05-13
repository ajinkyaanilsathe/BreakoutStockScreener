from typing import Optional

import pandas as pd

from .data_fetcher import fetch_stock_data, fetch_market_index
from .indicators import add_indicators
from .logger import get_logger

log = get_logger("screener")


# ── sector ETF map (NSE sector indices via yfinance) ─────────────────────────

SECTOR_MAP = {
    "BANK":    ["HDFCBANK", "ICICIBANK", "SBIN", "KOTAKBANK", "AXISBANK", "INDUSINDBK",
                "BANDHANBNK", "FEDERALBNK", "IDFCFIRSTB", "YESBANK", "AUBANK", "RBLBANK"],
    "IT":      ["TCS", "INFY", "WIPRO", "HCLTECH", "TECHM", "MPHASIS", "COFORGE",
                "PERSISTENT", "LTTS", "KPITTECH", "TATAELXSI", "LTIMINDTREE"],
    "PHARMA":  ["SUNPHARMA", "DIVISLAB", "DRREDDY", "CIPLA", "LUPIN", "AUROPHARMA",
                "TORNTPHARM", "ALKEM", "BIOCON", "LAURUS", "GLAND", "ZYDUSLIFE"],
    "AUTO":    ["MARUTI", "TATAMOTORS", "M&M", "EICHERMOT", "BAJAJ-AUTO", "HEROMOTOCO",
                "TVSMOTOR", "ASHOKLEY", "ESCORTS", "BALKRISIND", "APOLLOTYRE"],
    "FMCG":   ["HINDUNILVR", "ITC", "NESTLEIND", "BRITANNIA", "DABUR", "MARICO",
                "COLPAL", "GODREJCP", "EMAMILTD", "TATACONSUM", "PIDILITIND"],
    "ENERGY":  ["RELIANCE", "ONGC", "BPCL", "IOC", "GAIL", "TATAPOWER", "ADANIENT",
                "ADANIGREEN", "ADANIPORTS", "NTPC", "POWERGRID", "COALINDIA"],
    "METALS":  ["TATASTEEL", "JSWSTEEL", "HINDALCO", "VEDL", "SAIL", "NMDC",
                "HINDZINC", "APLAPOLLO", "JSPL", "NATIONALUM"],
    "REALTY":  ["DLF", "GODREJPROP", "OBEROIRLTY", "PHOENIXLTD", "PRESTIGE",
                "BRIGADE", "SOBHA", "LODHA"],
    "INFRA":   ["LT", "NBCC", "NCC", "KEC", "HAL", "BEL", "BEML", "IRFC",
                "RVNL", "CONCOR", "IRCON"],
    "FINANCE": ["BAJFINANCE", "BAJAJFINSV", "CHOLAFIN", "MUTHOOTFIN", "SHRIRAMFIN",
                "HDFCAMC", "SBICARD", "ANGELONE", "CDSL", "MOTILALOFS"],
}

# Reverse lookup: symbol → sector
_SYMBOL_TO_SECTOR: dict[str, str] = {}
for _sec, _syms in SECTOR_MAP.items():
    for _s in _syms:
        _SYMBOL_TO_SECTOR[_s] = _sec


def _build_sector_rs(nifty_20d_return: float) -> dict[str, float]:
    """
    Compute average 20-day ROC per sector (using up to 5 liquid members).
    Returns {sector: avg_roc} — positive means outperforming direction.
    """
    sector_roc: dict[str, float] = {}
    for sector, members in SECTOR_MAP.items():
        rocs = []
        for sym in members[:5]:
            df = fetch_stock_data(sym, period="3mo")
            if df is None or len(df) < 22:
                continue
            close = df["Close"].astype(float)
            roc = float((close.iloc[-1] / close.iloc[-22] - 1) * 100)
            rocs.append(roc)
        if rocs:
            sector_roc[sector] = sum(rocs) / len(rocs)
    return sector_roc


def check_market_regime() -> dict:
    df = fetch_market_index(period="1y")
    if df is None or len(df) < 50:
        log.warning("Could not determine market regime — insufficient Nifty data; defaulting to BULLISH")
        return {"is_bullish": True, "nifty_close": None, "nifty_ma200": None}
    close = df["Close"].astype(float)
    ma200 = close.rolling(200, min_periods=50).mean()
    latest_close = float(close.iloc[-1])
    latest_ma200 = float(ma200.iloc[-1]) if not pd.isna(ma200.iloc[-1]) else None
    is_bullish = (latest_ma200 is None) or (latest_close > latest_ma200)
    regime_label = "BULLISH" if is_bullish else "BEARISH"
    log.info(
        "Market regime: %s — Nifty %.0f %s 200-MA %.0f",
        regime_label, latest_close,
        ">" if is_bullish else "<",
        latest_ma200 or 0,
    )
    return {
        "is_bullish": is_bullish,
        "nifty_close": round(latest_close, 2),
        "nifty_ma200": round(latest_ma200, 2) if latest_ma200 else None,
    }


# ── dynamic target & stop ─────────────────────────────────────────────────────

def _dynamic_target(entry: float, atr: float, score: int, pct_from_52w_high: float) -> tuple[float, str]:
    """
    Returns (target_price, reasoning_label).
    ATR-based target scaled by score, capped when near 52W high resistance.
    """
    # Base: 3x ATR
    atr_target = entry + 3.0 * atr

    # Score multiplier: stronger setup → higher target
    if score >= 75:
        multiplier = 1.10   # 10% min
    elif score >= 60:
        multiplier = 0.08   # 8%
    else:
        multiplier = 0.06   # 6%

    pct_target = entry * (1 + multiplier)

    # Use whichever is larger — but cap at 52W high if close to it
    base_target = max(atr_target, pct_target)

    # If stock is within 3% of 52W high, resistance is near — cap target there
    if pct_from_52w_high >= -3.0:
        # Near 52W high: target slightly beyond it (breakout continuation)
        target = min(base_target, entry * 1.12)
        label = "Near 52W High — ATR target capped at 12%"
    else:
        target = base_target
        label = f"ATR×3 target ({((target/entry - 1)*100):.1f}%)"

    return round(target, 2), label


def _dynamic_sl(entry: float, atr: float, ut_stop: float, stop_loss_pct: float) -> float:
    """
    Pick the tightest valid stop: UT_Stop > ATR-based SL > pct-based hard stop.
    UT_Stop is used when it's above the ATR SL (i.e., tighter, less risk).
    """
    sl_atr = entry - 2.0 * atr
    sl_pct = entry * (1 - stop_loss_pct)
    sl_base = max(sl_atr, sl_pct)  # tighter of ATR vs pct

    # Use UT_Stop if it's above the base SL (tighter stop = less risk)
    if ut_stop > sl_base and ut_stop < entry:
        return round(ut_stop, 2)
    return round(sl_base, 2)


def _hold_suggestion(score: int, adx: float, ut_bot_buy: bool, atr: float, entry: float) -> dict:
    """
    Suggest a dynamic hold timeframe based on setup quality.
    Returns {min_days, max_days, label, exit_logic}.
    """
    atr_pct = atr / entry * 100

    if score >= 75 and adx >= 30 and ut_bot_buy:
        return {
            "min_days": 30,
            "max_days": 90,
            "label": "60–90 days",
            "exit_logic": "Hold with UT Bot trailing stop. Exit on UT Sell crossover or target hit.",
            "category": "SWING_LONG",
        }
    elif score >= 60 and adx >= 22:
        return {
            "min_days": 15,
            "max_days": 45,
            "label": "20–45 days",
            "exit_logic": "Exit on UT Sell signal, MA20 close-below, or target hit.",
            "category": "SWING_MED",
        }
    elif score >= 45:
        return {
            "min_days": 7,
            "max_days": 20,
            "label": "7–20 days",
            "exit_logic": "Momentum trade — cut quickly if volume dries up. Exit by day 20 if flat.",
            "category": "MOMENTUM",
        }
    else:
        return {
            "min_days": 3,
            "max_days": 10,
            "label": "3–10 days",
            "exit_logic": "Short-term speculative. Tight stop, quick cut.",
            "category": "SHORT_TERM",
        }


# ── RS rank across universe ───────────────────────────────────────────────────

def compute_rs_ranks(symbols: list) -> dict[str, float]:
    """
    Returns {symbol: percentile_rank} based on 6-month ROC.
    Top 20% → rank >= 80. Uses cached data — fast on second run.
    """
    rocs: dict[str, float] = {}
    for sym in symbols:
        df = fetch_stock_data(sym, period="1y")
        if df is None or len(df) < 130:
            continue
        close = df["Close"].astype(float)
        roc = float((close.iloc[-1] / close.iloc[-126] - 1) * 100)
        rocs[sym] = roc

    if not rocs:
        return {}

    sorted_syms = sorted(rocs, key=lambda s: rocs[s])
    n = len(sorted_syms)
    ranks = {}
    for idx, sym in enumerate(sorted_syms):
        ranks[sym] = round((idx / (n - 1)) * 100, 1) if n > 1 else 50.0
    return ranks


# ── signal detection ──────────────────────────────────────────────────────────

def _detect_signals(df: pd.DataFrame, params: dict, sector_rs: dict[str, float] | None = None, symbol: str = "") -> dict:
    latest = df.iloc[-1]
    prev = df.iloc[-2]

    # Tight base (original): BB width in lower 40th percentile
    recent_widths = df["BB_Width"].dropna().tail(60)
    tight_base_orig = bool(latest["BB_Width"] <= recent_widths.quantile(0.40)) if len(recent_widths) >= 10 else False

    # True VCP (new)
    true_vcp = bool(latest["VCP"]) if "VCP" in df.columns else False

    # Use true VCP if detected, otherwise fall back to BB squeeze
    tight_base = true_vcp or tight_base_orig

    # Relative Strength vs Nifty
    nifty_roc20 = params.get("nifty_20d_return", 0.0)
    stock_roc20 = float(latest["ROC_20"]) if not pd.isna(latest["ROC_20"]) else 0.0
    rs_vs_nifty = stock_roc20 > nifty_roc20

    # Weekly trend confirmation (new)
    weekly_trend = bool(latest.get("W_Trend", False))

    # Candlestick signal (new)
    candle_signal = bool(latest.get("Candle_Signal", False))

    # Sector rotation bonus (new)
    sector = _SYMBOL_TO_SECTOR.get(symbol, "")
    sector_leading = False
    if sector and sector_rs:
        sector_roc = sector_rs.get(sector, 0.0)
        sector_leading = sector_roc > nifty_roc20

    return {
        # ── original 10 ──────────────────────────────────────────────────
        "near_52w_high":         latest["Pct_From_52W_High"] >= params["pct_from_52w_high"],
        "price_above_prev_high": float(latest["Close"]) > float(prev["High"]),
        "volume_surge":          latest["Rel_Volume"] >= params["min_rel_volume"],
        "rsi_bullish":           params["rsi_min"] <= latest["RSI"] <= params["rsi_max"],
        "macd_bullish":          (latest["MACD"] > latest["MACD_Signal"]) and (latest["MACD_Hist"] > 0),
        "above_ma20":            bool(latest["Close"] > latest["MA20"]),
        "above_ma50":            bool(latest["Close"] > latest["MA50"]),
        "adx_strong":            latest["ADX"] >= params["adx_min"],
        "bb_breakout":           bool(latest["Close"] >= latest["BB_Upper"]),
        "momentum_positive":     latest["ROC_5"] > 1.0,
        # ── quality filters ───────────────────────────────────────────────
        "above_ma150":    bool(latest["Close"] > latest["MA150"]),
        "rs_vs_nifty":    rs_vs_nifty,
        "tight_base":     tight_base,
        "strong_close":   float(latest["Close_Pct_Range"]) > 0.65,
        "vol_trend_up":   float(latest["Vol_Trend"]) > 1.0,
        # ── new enhancements ──────────────────────────────────────────────
        "weekly_trend":   weekly_trend,
        "candle_signal":  candle_signal,
        "true_vcp":       true_vcp,
        "sector_leading": sector_leading,
        # ── UT Bot (confirmed breakout) ──────────────────────────────────
        # Confirmed breakout only: UT_Buy must have fired on YESTERDAY's bar
        # (iloc[-2]) and today's close (the confirmation bar) must still be
        # above the UT_Stop.  Accepting today's crossover (iloc[-1]) is wrong
        # because there is no next bar to confirm it — that is exactly the
        # ARVIND Dec-18 false breakout pattern.
        "ut_bot_buy": (
            len(df) >= 2
            and bool(df["UT_Buy"].iloc[-2])
            and float(latest["Close"]) > float(latest["UT_Stop"])
        ),
    }


def _score(latest: pd.Series, signals: dict) -> tuple[int, dict]:
    score = 0
    breakdown = {}

    # Volume (0–25)
    vol_score = min(25, int((latest["Rel_Volume"] - 1.0) * 18))
    vol_score = max(0, vol_score)
    score += vol_score
    breakdown["volume"] = vol_score

    # Price action (0–30)
    p = 0
    if signals["near_52w_high"]:         p += 12
    if signals["price_above_prev_high"]: p += 8
    if signals["bb_breakout"]:           p += 5
    if signals["true_vcp"]:              p += 8   # true VCP scores more than BB squeeze
    elif signals["tight_base"]:          p += 4
    score += p
    breakdown["price_action"] = p

    # Momentum (0–25)
    m = 0
    if signals["rsi_bullish"]:       m += 7
    if signals["macd_bullish"]:      m += 7
    if signals["momentum_positive"]: m += 4
    if signals["rs_vs_nifty"]:       m += 4
    if signals["candle_signal"]:     m += 3   # candlestick confirmation
    score += m
    breakdown["momentum"] = m

    # Trend (0–20)
    t = 0
    if signals["above_ma20"]:    t += 4
    if signals["above_ma50"]:    t += 4
    if signals["above_ma150"]:   t += 4
    if signals["adx_strong"]:    t += 4
    if signals["weekly_trend"]:  t += 4   # weekly confirmation
    score += t
    breakdown["trend"] = t

    # Entry quality (0–20)
    q = 0
    if signals["strong_close"]:    q += 6
    if signals["vol_trend_up"]:    q += 6
    if signals["sector_leading"]:  q += 4   # sector rotation bonus
    if signals["ut_bot_buy"]:      q += 4   # UT Bot as quality bonus
    score += q
    breakdown["entry_quality"] = q

    return score, breakdown


def _build_reason_text(signals: dict, latest: pd.Series) -> str:
    parts = []
    if signals["near_52w_high"]:
        parts.append(f"Near 52W High ({latest['Pct_From_52W_High']:.1f}%)")
    if signals["volume_surge"]:
        parts.append(f"{latest['Rel_Volume']:.1f}x Volume")
    if signals["bb_breakout"]:
        parts.append("BB Breakout")
    if signals["true_vcp"]:
        parts.append("True VCP")
    if signals["candle_signal"]:
        parts.append("Candle Pattern")
    if signals["weekly_trend"]:
        parts.append("Weekly Bullish")
    if signals["sector_leading"]:
        parts.append("Leading Sector")
    if signals["macd_bullish"]:
        parts.append("MACD Bullish")
    if signals["rsi_bullish"]:
        parts.append(f"RSI {latest['RSI']:.0f}")
    return " | ".join(parts) if parts else "Watchlist"


def analyze_stock(
    symbol: str,
    params: dict,
    sector_rs: dict | None = None,
    rs_rank: float | None = None,
) -> Optional[dict]:
    df = fetch_stock_data(symbol, period="1y")
    if df is None or len(df) < params["min_history_days"]:
        log.warning("%s  SKIP — insufficient data (need %d bars, got %d)",
                    symbol, params["min_history_days"], len(df) if df is not None else 0)
        return None

    df = add_indicators(df, symbol=symbol)
    if df is None:
        log.error("%s  SKIP — indicator calculation returned None", symbol)
        return None

    latest = df.iloc[-1]
    if pd.isna(latest["RSI"]) or pd.isna(latest["MACD"]) or pd.isna(latest["ADX"]):
        log.error("%s  SKIP — NaN in RSI/MACD/ADX on latest bar (indicator pipeline failure)", symbol)
        return None
    if latest["Volume"] == 0:
        log.warning("%s  SKIP — zero volume on latest bar", symbol)
        return None

    signals = _detect_signals(df, params, sector_rs=sector_rs, symbol=symbol)
    score, breakdown = _score(latest, signals)

    entry = float(latest["Close"])
    atr = float(latest["ATR"]) if not pd.isna(latest["ATR"]) else entry * 0.02
    ut_stop = float(latest["UT_Stop"])
    pct_from_52w = float(latest["Pct_From_52W_High"]) if not pd.isna(latest["Pct_From_52W_High"]) else -10.0

    target, target_label = _dynamic_target(entry, atr, score, pct_from_52w)
    stop_loss = _dynamic_sl(entry, atr, ut_stop, params["stop_loss_pct"])

    risk = entry - stop_loss
    reward = target - entry
    rr_ratio = round(reward / risk, 2) if risk > 0 else 0.0

    signal_count = sum(1 for v in signals.values() if v)
    hold = _hold_suggestion(score, float(latest["ADX"]), signals["ut_bot_buy"], atr, entry)

    # Breakout date = the bar that actually crossed above UT_Stop (yesterday,
    # iloc[-2]).  Only meaningful when ut_bot_buy is confirmed.
    if signals["ut_bot_buy"] and len(df) >= 2:
        crossover_bar = df.index[-2]
        breakout_date = crossover_bar.strftime("%d %b '%y")
        breakout_days_ago = (df.index[-1] - crossover_bar).days
    else:
        breakout_date = None
        breakout_days_ago = None

    return {
        "symbol": symbol,
        "price": round(entry, 2),
        "score": score,
        "breakdown": breakdown,
        "signal_count": signal_count,
        "signals": signals,
        "target": target,
        "target_label": target_label,
        "stop_loss": stop_loss,
        "upside_pct": round((target - entry) / entry * 100, 1),
        "rr_ratio": rr_ratio,
        "rel_volume": round(float(latest["Rel_Volume"]), 2),
        "rsi": round(float(latest["RSI"]), 1),
        "adx": round(float(latest["ADX"]), 1),
        "macd_hist": round(float(latest["MACD_Hist"]), 3),
        "pct_from_52w_high": round(pct_from_52w, 1),
        "roc_5d": round(float(latest["ROC_5"]), 1),
        "roc_126d": round(float(latest.get("ROC_126", 0.0)), 1),
        "rs_rank": rs_rank,
        "ut_bot_buy": signals["ut_bot_buy"],
        "ut_stop":    round(ut_stop, 2),
        "breakout_date": breakout_date,
        "breakout_days_ago": breakout_days_ago,
        "hold": hold,
        "reasons": _build_reason_text(signals, latest),
        "df": df,
    }


def run_screener(symbols: list, params: dict, progress_cb=None) -> tuple[list, dict]:
    regime = check_market_regime()
    require_bull = params.get("require_bull_market", True)

    if require_bull and not regime["is_bullish"]:
        log.warning("Screener aborted — market is BEARISH and Bull Market Gate is ON")
        return [], regime

    # Pre-fetch Nifty 20-day return for RS comparison
    nifty_df = fetch_market_index(period="1y")
    if nifty_df is not None and len(nifty_df) >= 22:
        nifty_close = nifty_df["Close"].astype(float)
        nifty_20d_return = float((nifty_close.iloc[-1] / nifty_close.iloc[-22] - 1) * 100)
    else:
        nifty_20d_return = 0.0
    params = {**params, "nifty_20d_return": nifty_20d_return}

    # Phase 1: compute RS ranks for the full universe (uses cache — fast)
    total = len(symbols)
    if progress_cb:
        progress_cb(0.0, "Computing RS Ranks…")
    rs_ranks = compute_rs_ranks(symbols)

    # Phase 2: compute sector RS (uses 5 members per sector from cache)
    if progress_cb:
        progress_cb(0.02, "Computing Sector Strength…")
    sector_rs = _build_sector_rs(nifty_20d_return)

    results = []
    min_signals = params.get("min_signal_count", 9)
    min_rs_rank = params.get("min_rs_rank", 60)

    log.info("─── Screener starting — %d symbols, min_score=%s, min_rr=%.1f, min_signals=%d, min_rs_rank=%d",
             total, params["min_score"], params["min_rr_ratio"], min_signals, min_rs_rank)

    for i, sym in enumerate(symbols):
        if progress_cb:
            progress_cb(0.05 + 0.95 * (i / total), sym)

        rank = rs_ranks.get(sym)
        if rank is not None and rank < min_rs_rank:
            log.debug("%s  SKIP — RS rank %.0f < %.0f", sym, rank, min_rs_rank)
            continue

        result = analyze_stock(sym, params, sector_rs=sector_rs, rs_rank=rank)
        if result is None:
            continue

        if result["signal_count"] < min_signals:
            log.debug("%s  SKIP — signals %d/%d < %d required",
                      sym, result["signal_count"], len(result["signals"]), min_signals)
            continue

        if result["score"] < params["min_score"]:
            log.debug("%s  SKIP — score %d < %d", sym, result["score"], params["min_score"])
            continue

        if result["rr_ratio"] < params["min_rr_ratio"]:
            log.debug("%s  SKIP — R:R %.2f < %.2f", sym, result["rr_ratio"], params["min_rr_ratio"])
            continue

        log.info("%s  PASS  score=%d  signals=%d  R:R=%.2f  RS=%.0f  UT=%s  %s",
                 sym, result["score"], result["signal_count"], result["rr_ratio"],
                 rank or 0, "BUY" if result["ut_bot_buy"] else "---", result["reasons"])
        results.append(result)

    log.info("─── Screener done — %d candidates from %d symbols", len(results), total)
    results.sort(key=lambda x: x["score"], reverse=True)
    return results, regime
