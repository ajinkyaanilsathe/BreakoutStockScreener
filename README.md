# NSE Stock Breakout Screener

A Streamlit web app that scans Indian NSE stocks for technical breakout setups, ranks them by a composite conviction score, and suggests dynamic entry/exit levels per stock.

> **Educational use only. Not financial advice.**

---

## Quick Start

```bash
# Install dependencies (first time only)
pip install -r requirements.txt

# Run the app
streamlit run app.py
```

Opens at `http://localhost:8501`.

First scan: 2–3 min (live data fetch). Subsequent runs within 6 hours use cached data and are much faster.

---

## Features

### 5 App Tabs

| Tab | What it does |
|-----|-------------|
| **Dashboard** | Nifty 50 chart, market regime (Bull/Bear), top 5 picks, UT Bot alerts |
| **Screener** | Full scan across the stock universe with adjustable filters |
| **Stock Analysis** | Candlestick chart (price + RSI + MACD), support/resistance trendlines, signal checklist, score breakdown |
| **Backtest** | 2-year historical simulation — win rate, equity curve, outcome breakdown, peak return analysis |
| **Best Buy** | Conviction-ranked shortlist; hero cards for top 3 picks |

### Sidebar Controls

- Min Score (30–80)
- Min R:R Ratio
- Min Relative Volume
- RSI range
- Min RS Rank (relative strength percentile filter)
- Bull Market Gate toggle (skip all signals when Nifty < 200-MA)

### Export

Every tab has an **Export to Excel** button (.xlsx).

---

## Scoring System (v3)

Composite score out of 100 (can exceed 100 with bonuses):

| Component | Max pts | Key factors |
|-----------|---------|-------------|
| Volume | 25 | Relative volume vs 20-day avg |
| Price Action | 30 | Near 52W high, prev-high break, BB breakout, True VCP |
| Momentum | 25 | RSI zone, MACD bullish, ROC, RS vs Nifty, candlestick |
| Trend | 20 | MA20/50/150, ADX strength, weekly trend confirmation |
| Entry Quality | 20 | Strong close, volume accumulation, sector leading, UT Bot |

---

## Signals (20 total)

Each stock is checked against 20 binary signals. At least 7 must fire for a stock to pass the screener.

| Signal | Description |
|--------|-------------|
| `near_52w_high` | Within 15% of 52-week high |
| `price_above_prev_high` | Closed above previous day's high |
| `volume_surge` | Relative volume ≥ 1.5× 20-day avg |
| `rsi_bullish` | RSI in 50–72 range |
| `macd_bullish` | MACD > signal line + histogram > 0 |
| `above_ma20` | Price above 20-day SMA |
| `above_ma50` | Price above 50-day SMA |
| `adx_strong` | ADX ≥ 20 (trend strength) |
| `bb_breakout` | Close ≥ Bollinger Upper Band |
| `momentum_positive` | 5-day ROC > 1% |
| `above_ma150` | Minervini Stage-2 confirmation |
| `rs_vs_nifty` | 20-day return > Nifty 20-day return |
| `tight_base` | BB squeeze or True VCP |
| `strong_close` | Close in top 35% of day's range |
| `vol_trend_up` | 5-day vol avg > 20-day vol avg |
| `weekly_trend` | Weekly close > weekly MA20 AND weekly RSI > 50 |
| `candle_signal` | Bullish Engulfing / Hammer / Dragonfly Doji / Inside Bar breakout |
| `true_vcp` | 3 contracting price swings + declining volume |
| `sector_leading` | Stock's sector 20-day ROC > Nifty ROC |
| `ut_bot_buy` | Price crossed above ATR trailing stop (1-day confirmed) |

---

## UT Bot (ATR Trailing Stop)

- Trailing stop = 2× ATR(10), tracks price direction
- **Buy signal**: close crosses above the trailing stop — confirmed with 1-day delay to avoid false breakouts
- **Sell signal**: close crosses below the trailing stop — primary dynamic exit
- Used for: entry confirmation, stop-loss level, and trailing exit management

---

## Dynamic Exit Logic

### Stop Loss

Tightest of three levels:
1. UT Bot trailing stop (if tighter than ATR SL)
2. Entry − 2× ATR
3. Entry × (1 − 5%)

### Target

ATR × 3, scaled by setup score:
- Score ≥ 75 → 10% minimum
- Score ≥ 60 → 8% minimum
- Score < 60 → 6% minimum
- Capped at 12% if stock is within 3% of its 52-week high (resistance)

### Hold Period (dynamic per stock)

| Category | Condition | Suggested Hold | Exit Logic |
|----------|-----------|----------------|------------|
| SWING_LONG | Score ≥75 + ADX ≥30 + UT Bot buy | 60–90 days | UT Bot trailing stop |
| SWING_MED | Score ≥60 + ADX ≥22 | 20–45 days | UT Sell or MA20 break |
| MOMENTUM | Score ≥45 | 7–20 days | Cut if volume dries up |
| SHORT_TERM | Score <45 | 3–10 days | Tight stop, quick exit |

---

## Conviction Score (Best Buy)

Ranks screener results by a composite conviction score:

```
Conviction = Base Score
           + UT Bot Buy    (+15)
           + True VCP      (+12)
           + Candle Signal (+8)
           + Weekly Trend  (+7)
           + Sector Leader (+6)
           + R:R bonus     (up to +8;  ≥3.0x → +8, ≥2.0x → +4)
           + RS bonus      (up to +10; rs_rank/100 × 10)
```

Theoretical maximum: 166. Only stocks with Score ≥ 50 and R:R ≥ 1.5 are eligible. Top 10 shown.

---

## Backtest

Simulates the strategy on 2 years of daily data:

- **Entry**: next bar's open after signal fires
- **Exits**: Target hit · UT Sell crossover · Trailing stop (activates at +4% gain, breaks even at +3%) · Stop loss · Time exit (dynamic hold budget)
- **Peak return**: tracks the highest price within 90 trading days of entry to show what was "left on the table"
- Bull market gate respected during backtest (no trades when Nifty < 200-MA on that date)
- UT Sell exit ignored in first 3 days (noise filter)

---

## Project Structure

```
StockBreakout/
├── app.py                  # Streamlit UI — all 5 tabs
├── config.py               # Stock universe + strategy params
├── requirements.txt
├── src/
│   ├── data_fetcher.py     # yfinance fetch + 6-hr pickle cache
│   ├── indicators.py       # All technical indicators
│   ├── screener.py         # Signal detection, scoring, RS rank, sector rotation
│   ├── backtester.py       # Historical simulation
│   └── logger.py
└── .cache/                 # Auto-generated — 6-hr data cache (.pkl files)
```

---

## Configuration (`config.py`)

Key strategy parameters (all adjustable via sidebar at runtime):

| Parameter | Default | Notes |
|-----------|---------|-------|
| `rsi_min` / `rsi_max` | 50 / 72 | Bullish RSI zone |
| `min_rel_volume` | 1.5× | Volume surge threshold |
| `adx_min` | 20 | Trend strength filter |
| `min_score` | 45 | Minimum composite score |
| `min_rr_ratio` | 1.5 | Minimum risk:reward |
| `pct_from_52w_high` | −15% | Max distance from 52W high |
| `min_signal_count` | 7 | Of 20 signals must fire |
| `require_bull_market` | True | Nifty > 200-MA gate |

> **Note:** `_raw_universe` in `config.py` is currently set to a single stock (`"AEQUS"`) for quick testing. To run a full scan, replace it with the full 400+ symbol list (commented out above it in the file).

---

## Data Source

- **Provider**: Yahoo Finance via `yfinance`
- **NSE symbols**: fetched as `SYMBOL.NS` automatically
- **Index**: Nifty 50 as `^NSEI`
- **Cache**: `.cache/` folder, 6-hour TTL, pickle format
- **Sectors tracked**: BANK, IT, PHARMA, AUTO, FMCG, ENERGY, METALS, REALTY, INFRA, FINANCE

---

## Risk Rules

- Stop loss: tightest of UT Stop / 2×ATR / −5%
- Minimum R:R: 1.5×
- Position size: risk ≤ 1–2% of capital per trade
- No trades in bearish market (Nifty < 200-MA) when gate is enabled
