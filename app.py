import sys
import os
import io
from datetime import date

sys.path.insert(0, os.path.dirname(__file__))

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

from config import STOCK_UNIVERSE, STRATEGY_PARAMS, MARKET_REGIME_SYMBOL
from src.data_fetcher import fetch_market_index, fetch_stock_data
from src.indicators import add_indicators
from src.screener import run_screener, analyze_stock
from src.backtester import run_backtest

# ── page config ───────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="NSE Breakout Screener",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── helpers ───────────────────────────────────────────────────────────────────

def _market_status(nifty_df: pd.DataFrame) -> dict:
    if nifty_df is None or len(nifty_df) < 200:
        return {"regime": "UNKNOWN", "color": "gray", "nifty_price": None, "change_pct": None}
    close = nifty_df["Close"].astype(float)
    ma200 = close.rolling(200).mean()
    latest_price = float(close.iloc[-1])
    latest_ma200 = float(ma200.iloc[-1])
    prev_price = float(close.iloc[-2])
    change_pct = (latest_price - prev_price) / prev_price * 100

    if latest_price > latest_ma200:
        regime, color = "BULLISH", "#00C896"
    else:
        regime, color = "BEARISH", "#FF4B4B"
    return {
        "regime": regime,
        "color": color,
        "nifty_price": latest_price,
        "change_pct": change_pct,
        "ma200": latest_ma200,
    }


def _score_color(score: int) -> str:
    if score >= 70:
        return "#00C896"
    if score >= 50:
        return "#FFA500"
    return "#FF4B4B"


def _build_candlestick(df: pd.DataFrame, symbol: str, sr_data: dict | None = None) -> go.Figure:
    fig = make_subplots(
        rows=3, cols=1,
        shared_xaxes=True,
        row_heights=[0.55, 0.22, 0.23],
        vertical_spacing=0.03,
        subplot_titles=(f"{symbol} — Price & Indicators", "RSI (14)", "MACD"),
    )

    # Candlestick
    fig.add_trace(
        go.Candlestick(
            x=df.index, open=df["Open"], high=df["High"],
            low=df["Low"], close=df["Close"],
            name="Price",
            increasing_line_color="#00C896",
            decreasing_line_color="#FF4B4B",
        ),
        row=1, col=1,
    )

    # Bollinger Bands
    fig.add_trace(go.Scatter(x=df.index, y=df["BB_Upper"], line=dict(color="rgba(100,149,237,0.4)", width=1), name="BB Upper", showlegend=False), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df["BB_Lower"], line=dict(color="rgba(100,149,237,0.4)", width=1), fill="tonexty", fillcolor="rgba(100,149,237,0.07)", name="BB Lower", showlegend=False), row=1, col=1)

    # Moving averages
    for ma, col in [("MA20", "#FFD700"), ("MA50", "#1E90FF"), ("MA200", "#FF69B4")]:
        if ma in df.columns:
            fig.add_trace(go.Scatter(x=df.index, y=df[ma], line=dict(color=col, width=1.2), name=ma), row=1, col=1)

    # Volume bars
    colors = ["#00C896" if c >= o else "#FF4B4B" for c, o in zip(df["Close"], df["Open"])]
    fig.add_trace(go.Bar(x=df.index, y=df["Volume"], marker_color=colors, opacity=0.5, name="Volume", showlegend=False), row=1, col=1)

    # ── Support / Resistance overlays ────────────────────────────────────────
    if sr_data:
        for _, price, strength in sr_data.get("support_levels", []):
            lw = 1.5 if strength >= 2 else 0.9
            fig.add_hline(y=price, line_dash="dash",
                          line_color="rgba(0,200,150,0.45)", line_width=lw,
                          row=1, col=1,
                          annotation_text=f"S {price:,.0f}",
                          annotation_position="right",
                          annotation_font=dict(color="rgba(0,200,150,0.9)", size=9))

        for _, price, strength in sr_data.get("resistance_levels", []):
            lw = 1.5 if strength >= 2 else 0.9
            fig.add_hline(y=price, line_dash="dash",
                          line_color="rgba(255,75,75,0.45)", line_width=lw,
                          row=1, col=1,
                          annotation_text=f"R {price:,.0f}",
                          annotation_position="right",
                          annotation_font=dict(color="rgba(255,75,75,0.9)", size=9))

        sup_x, sup_y = sr_data.get("sup_tl", (None, None))
        if sup_x is not None and len(sup_x) > 1:
            fig.add_trace(go.Scatter(
                x=sup_x, y=sup_y,
                line=dict(color="rgba(0,200,150,0.7)", width=1.5, dash="dot"),
                name="Support TL", showlegend=True,
            ), row=1, col=1)

        res_x, res_y = sr_data.get("res_tl", (None, None))
        if res_x is not None and len(res_x) > 1:
            fig.add_trace(go.Scatter(
                x=res_x, y=res_y,
                line=dict(color="rgba(255,75,75,0.7)", width=1.5, dash="dot"),
                name="Resistance TL", showlegend=True,
            ), row=1, col=1)

    # RSI
    fig.add_trace(go.Scatter(x=df.index, y=df["RSI"], line=dict(color="#FFA500", width=1.5), name="RSI"), row=2, col=1)
    fig.add_hline(y=70, line_dash="dash", line_color="red", opacity=0.5, row=2, col=1)
    fig.add_hline(y=50, line_dash="dash", line_color="gray", opacity=0.4, row=2, col=1)
    fig.add_hline(y=30, line_dash="dash", line_color="green", opacity=0.5, row=2, col=1)

    # MACD
    hist_colors = ["#00C896" if v >= 0 else "#FF4B4B" for v in df["MACD_Hist"].fillna(0)]
    fig.add_trace(go.Bar(x=df.index, y=df["MACD_Hist"], marker_color=hist_colors, name="MACD Hist", showlegend=False), row=3, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df["MACD"], line=dict(color="#1E90FF", width=1.2), name="MACD"), row=3, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df["MACD_Signal"], line=dict(color="#FFA500", width=1.2), name="Signal"), row=3, col=1)

    fig.update_layout(
        height=700,
        template="plotly_dark",
        paper_bgcolor="#0E1117",
        plot_bgcolor="#0E1117",
        showlegend=True,
        legend=dict(orientation="h", y=1.02, x=0),
        xaxis_rangeslider_visible=False,
        margin=dict(l=10, r=10, t=40, b=10),
    )
    fig.update_yaxes(gridcolor="#1E2130", row=1, col=1)
    fig.update_yaxes(gridcolor="#1E2130", row=2, col=1)
    fig.update_yaxes(gridcolor="#1E2130", row=3, col=1)
    return fig


def _build_nifty_chart(nifty_df: pd.DataFrame) -> go.Figure:
    close = nifty_df["Close"].astype(float)
    ma200 = close.rolling(200).mean()
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=nifty_df.index, y=close, line=dict(color="#00C896", width=1.5), name="Nifty 50", fill="tozeroy", fillcolor="rgba(0,200,150,0.08)"))
    fig.add_trace(go.Scatter(x=nifty_df.index, y=ma200, line=dict(color="#FF69B4", width=1.2, dash="dot"), name="200-MA"))
    fig.update_layout(
        height=220, template="plotly_dark",
        paper_bgcolor="#0E1117", plot_bgcolor="#0E1117",
        margin=dict(l=10, r=10, t=10, b=10),
        showlegend=True, legend=dict(orientation="h", y=1.1),
        xaxis=dict(gridcolor="#1E2130"),
        yaxis=dict(gridcolor="#1E2130"),
    )
    return fig


def _compute_sr_trendlines(df: pd.DataFrame, pivot_n: int = 5) -> dict:
    """
    Detect support/resistance levels and trendlines using pivot highs/lows.
    Levels are clustered (within 1.5%) and filtered to ±12% of current price.
    """
    high  = df["High"].astype(float).values
    low   = df["Low"].astype(float).values
    dates = df.index
    cur_p = float(df["Close"].iloc[-1])

    pivot_highs, pivot_lows = [], []
    for i in range(pivot_n, len(high) - pivot_n):
        if high[i] == high[i - pivot_n : i + pivot_n + 1].max():
            pivot_highs.append((i, float(high[i])))
        if low[i] == low[i - pivot_n : i + pivot_n + 1].min():
            pivot_lows.append((i, float(low[i])))

    def _cluster(pivots, tol=0.015, max_dist=0.12):
        if not pivots:
            return []
        s = sorted(pivots, key=lambda x: x[1])
        groups = [[s[0]]]
        for p in s[1:]:
            if abs(p[1] - groups[-1][-1][1]) / groups[-1][-1][1] < tol:
                groups[-1].append(p)
            else:
                groups.append([p])
        out = []
        for g in groups:
            avg_p = sum(x[1] for x in g) / len(g)
            max_i = max(x[0] for x in g)
            if abs(avg_p - cur_p) / cur_p < max_dist:
                out.append((max_i, round(avg_p, 2), len(g)))
        out.sort(key=lambda x: x[0], reverse=True)
        return out[:5]

    def _trendline(pivots, n=4):
        if len(pivots) < 2:
            return None, None
        recent = sorted(pivots, key=lambda x: x[0])[-n:]
        x = np.array([p[0] for p in recent], dtype=float)
        y = np.array([p[1] for p in recent], dtype=float)
        m, b = np.polyfit(x, y, 1)
        i0, i1 = int(recent[0][0]), len(dates) - 1
        xr = np.arange(i0, i1 + 1)
        return dates[xr], m * xr + b

    return {
        "support_levels":    _cluster(pivot_lows),
        "resistance_levels": _cluster(pivot_highs),
        "sup_tl":  _trendline(pivot_lows),
        "res_tl":  _trendline(pivot_highs),
    }


def _conviction_score(r: dict) -> float:
    """Composite best-buy ranking: base score + signal bonuses + RS + R:R."""
    base = float(r.get("score", 0))
    sigs = r.get("signals", {})
    rs   = float(r.get("rs_rank") or 0)
    rr   = float(r.get("rr_ratio", 0))

    bonus = 0.0
    if r.get("ut_bot_buy"):          bonus += 15
    if sigs.get("true_vcp"):         bonus += 12
    if sigs.get("candle_signal"):    bonus += 8
    if sigs.get("weekly_trend"):     bonus += 7
    if sigs.get("sector_leading"):   bonus += 6
    if rr >= 3.0:                    bonus += 8
    elif rr >= 2.0:                  bonus += 4
    bonus += (rs / 100) * 10        # up to +10 for perfect RS rank

    return round(base + bonus, 1)


def _top_catalysts(r: dict) -> str:
    """Return top 3 active signals as a short readable string."""
    sigs = r.get("signals", {})
    cats = []
    if r.get("ut_bot_buy"):              cats.append("UT Bot Buy")
    if sigs.get("true_vcp"):             cats.append("True VCP")
    if sigs.get("candle_signal"):        cats.append("Candle Pattern")
    if sigs.get("weekly_trend"):         cats.append("Weekly Trend")
    if sigs.get("sector_leading"):       cats.append("Leading Sector")
    if sigs.get("near_52w_high"):        cats.append("Near 52W High")
    if sigs.get("volume_surge"):         cats.append("Volume Surge")
    return " · ".join(cats[:3]) if cats else r.get("reasons", "—")


def _to_excel_bytes(sheets: dict) -> bytes:
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        for name, df in sheets.items():
            df.to_excel(writer, sheet_name=name[:31], index=False)
    return buf.getvalue()


def _build_equity_curve(trades_df: pd.DataFrame) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=trades_df["entry_date"].astype(str),
        y=trades_df["cumulative_return"],
        line=dict(color="#00C896", width=2),
        fill="tozeroy",
        fillcolor="rgba(0,200,150,0.1)",
        name="Cumulative Return %",
    ))
    fig.update_layout(
        height=280, template="plotly_dark",
        paper_bgcolor="#0E1117", plot_bgcolor="#0E1117",
        margin=dict(l=10, r=10, t=10, b=10),
        xaxis=dict(gridcolor="#1E2130"),
        yaxis=dict(gridcolor="#1E2130", ticksuffix="%"),
    )
    return fig


# ── sidebar ───────────────────────────────────────────────────────────────────

with st.sidebar:
    st.markdown("## ⚙️ Settings")

    min_score = st.slider("Min Score", 30, 80, STRATEGY_PARAMS["min_score"], step=5)
    min_rr = st.slider("Min R:R Ratio", 1.0, 3.0, STRATEGY_PARAMS["min_rr_ratio"], step=0.1)
    min_rel_vol = st.slider("Min Relative Volume", 1.0, 3.0, STRATEGY_PARAMS["min_rel_volume"], step=0.1)
    rsi_min = st.slider("RSI Min", 40, 60, STRATEGY_PARAMS["rsi_min"])
    rsi_max = st.slider("RSI Max", 65, 80, STRATEGY_PARAMS["rsi_max"])
    min_rs_rank = st.slider("Min RS Rank (0=all, 80=top 20%)", 0, 90, 40, step=10,
                            help="Filter by 6-month relative strength percentile rank vs universe")
    require_bull = st.checkbox(
        "Bull Market Gate (Nifty > 200-MA only)",
        value=True,
        help="Uncheck to scan even when Nifty is below its 200-MA. Useful in sideways/correction phases.",
    )

    st.divider()
    st.markdown("**Stock Universe**")
    st.caption(f"{len(STOCK_UNIVERSE)} NSE symbols (Nifty 50 + Midcap)")

    custom_params = {
        **STRATEGY_PARAMS,
        "min_score": min_score,
        "min_rr_ratio": min_rr,
        "min_rel_volume": min_rel_vol,
        "rsi_min": rsi_min,
        "rsi_max": rsi_max,
        "min_rs_rank": min_rs_rank,
        "require_bull_market": require_bull,
    }

    st.divider()
    st.caption("Data cached for 6 hrs. Prices from NSE via yfinance.")
    st.caption("⚠️ For educational use only. Not financial advice.")

# ── header ────────────────────────────────────────────────────────────────────

st.markdown("# 📈 Indian Stock Breakout Screener")
st.markdown("Scans NSE stocks for technical breakout setups. **Hold period and target are dynamically suggested per stock** based on setup strength.")

nifty_df = fetch_market_index(period="1y")
status = _market_status(nifty_df)

c1, c2, c3, c4 = st.columns(4)
with c1:
    color = status["color"]
    regime = status["regime"]
    st.markdown(f"**Market Regime**")
    st.markdown(f"<span style='color:{color}; font-size:1.4rem; font-weight:700'>{regime}</span>", unsafe_allow_html=True)
with c2:
    if status["nifty_price"]:
        chg = status["change_pct"]
        chg_str = f"+{chg:.2f}%" if chg >= 0 else f"{chg:.2f}%"
        chg_color = "#00C896" if chg >= 0 else "#FF4B4B"
        st.markdown("**Nifty 50**")
        st.markdown(f"<span style='font-size:1.3rem'>{status['nifty_price']:,.0f} <span style='color:{chg_color}'>{chg_str}</span></span>", unsafe_allow_html=True)
with c3:
    if status.get("ma200"):
        vs = status["nifty_price"] - status["ma200"]
        st.markdown("**vs 200-MA**")
        vs_color = "#00C896" if vs >= 0 else "#FF4B4B"
        st.markdown(f"<span style='color:{vs_color}'>{vs:+.0f} pts</span>", unsafe_allow_html=True)
with c4:
    st.markdown("**Universe**")
    st.markdown(f"**{len(STOCK_UNIVERSE)}** NSE stocks")

st.divider()

# ── tabs ──────────────────────────────────────────────────────────────────────

tab1, tab2, tab3, tab4, tab5 = st.tabs(["🏠 Dashboard", "🔍 Screener", "📊 Stock Analysis", "📉 Backtest", "⭐ Best Buy"])

# ─── TAB 1: Dashboard ─────────────────────────────────────────────────────────

with tab1:
    col_l, col_r = st.columns([3, 2])

    with col_l:
        st.subheader("Nifty 50 — 1 Year")
        if nifty_df is not None:
            st.plotly_chart(_build_nifty_chart(nifty_df))
        else:
            st.warning("Could not fetch Nifty 50 data.")

    with col_r:
        st.subheader("How to use this tool")
        st.markdown("""
1. Go to **🔍 Screener** tab → click **Run Screener**
2. Stocks scoring ≥ threshold with good R:R appear in the table
3. Click any stock row then open **📊 Stock Analysis** for the chart
4. Check **entry price · target · stop-loss** before trading
5. **📉 Backtest** shows historical win-rate of the strategy

**Scoring breakdown (v3)**
| Component | Max |
|-----------|-----|
| Volume surge | 25 |
| Price action (52W high / BB / True VCP) | 30+ |
| Momentum (RSI + MACD + RS + Candle) | 25 |
| Trend (MA20/50/150 + ADX + Weekly) | 20 |
| Entry quality (close + vol + sector + UT Bot) | 20 |

**New in v3**
- **Dynamic target**: ATR×3, scaled by score, capped by 52W high
- **Dynamic hold**: 10–90 days suggested per stock
- **UT Sell exit**: trailing stop crossover as primary exit
- **RS Rank filter**: only top performers (configurable)
- **Weekly trend gate**: weekly MA20 + RSI > 50
- **True VCP**: 3 contracting swings + declining volume
- **Candlestick patterns**: Engulfing, Hammer, Inside Bar
- **Sector rotation bonus**: stocks in leading sectors score higher
- Market gate: **no trades when Nifty < 200-MA**

**Risk rules**
- SL: UT_Stop or 2× ATR or –5% (tightest wins)
- Min R:R: 1.5×
- Position size: risk ≤ 1–2% of capital per trade
        """)

    if "screener_results" in st.session_state and st.session_state["screener_results"]:
        st.subheader("Top Picks from Last Scan")
        results = st.session_state["screener_results"]
        top5 = results[:5]
        cols = st.columns(len(top5))
        for col, r in zip(cols, top5):
            with col:
                sc = r["score"]
                sc_color = _score_color(sc)
                hold_label = r.get("hold", {}).get("label", "—")
                rs_rank = r.get("rs_rank")
                rs_str = f"RS {rs_rank:.0f}" if rs_rank is not None else ""
                st.markdown(
                    f"""
                    <div style='background:#1E2130; border-radius:10px; padding:14px; text-align:center; border-left: 3px solid {sc_color}'>
                        <div style='font-size:1.1rem; font-weight:700; color:#FAFAFA'>{r['symbol']}</div>
                        <div style='font-size:1.8rem; font-weight:800; color:{sc_color}'>{sc}</div>
                        <div style='font-size:0.8rem; color:#aaa'>Score {rs_str}</div>
                        <div style='margin-top:8px; font-size:0.9rem'>₹{r['price']:,}</div>
                        <div style='color:#00C896; font-size:0.85rem'>▲ ₹{r['target']:,} ({r['upside_pct']}%)</div>
                        <div style='color:#FF4B4B; font-size:0.85rem'>SL ₹{r['stop_loss']:,}</div>
                        <div style='color:#FFD700; font-size:0.78rem'>Hold: {hold_label}</div>
                        <div style='font-size:0.75rem; color:#aaa; margin-top:4px'>{r['reasons']}</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

        # ── UT Bot Alerts ──────────────────────────────────────────────────────
        st.divider()
        ut_alerts = [r for r in results if r.get("ut_bot_buy")]
        st.subheader(f"🤖 UT Bot Alerts — {len(ut_alerts)} stock{'s' if len(ut_alerts) != 1 else ''} with fresh buy signal")
        st.caption(
            "UT Bot fires a **buy signal** when the closing price crosses **above the ATR trailing stop** for the first time. "
            "These are same-day crossover events — act quickly or wait for the next candle to confirm."
        )

        if ut_alerts:
            ut_cols = st.columns(min(len(ut_alerts), 4))
            for col, r in zip(ut_cols, ut_alerts[:4]):
                with col:
                    sc = r["score"]
                    dist_pct = round((r["price"] - r["ut_stop"]) / r["ut_stop"] * 100, 1)
                    st.markdown(
                        f"""
                        <div style='background:#0D1F17; border-radius:10px; padding:14px; text-align:center;
                                    border: 1.5px solid #00C896; border-left: 4px solid #00C896'>
                            <div style='font-size:0.75rem; color:#00C896; font-weight:700; letter-spacing:1px'>🤖 UT BOT BUY</div>
                            <div style='font-size:1.2rem; font-weight:800; color:#FAFAFA; margin-top:4px'>{r['symbol']}</div>
                            <div style='font-size:1.5rem; font-weight:700; color:#00C896'>{sc}</div>
                            <div style='font-size:0.75rem; color:#aaa'>Score</div>
                            <div style='margin-top:8px; font-size:0.95rem'>₹{r['price']:,}</div>
                            <div style='color:#aaa; font-size:0.8rem'>UT Stop: ₹{r['ut_stop']:,}</div>
                            <div style='color:#FFD700; font-size:0.8rem'>+{dist_pct}% above stop</div>
                            <div style='color:#00C896; font-size:0.85rem; margin-top:4px'>Target ₹{r['target']:,} (+{r['upside_pct']}%)</div>
                            <div style='color:#FF4B4B; font-size:0.8rem'>SL ₹{r['stop_loss']:,}</div>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )
            if len(ut_alerts) > 4:
                st.caption(f"… and {len(ut_alerts) - 4} more. See the full list in the Screener tab (filter by UT Bot column).")
        else:
            st.info("No UT Bot buy crossovers detected in today's scan. UT Bot fires only on the exact day price crosses above the ATR trailing stop.")
    else:
        st.info("Run the Screener to see top picks here.")

# ─── TAB 2: Screener ──────────────────────────────────────────────────────────

with tab2:
    st.subheader("Breakout Screener")
    st.markdown(f"Scanning **{len(STOCK_UNIVERSE)} NSE stocks** · Min score: **{custom_params['min_score']}** · Min R:R: **{custom_params['min_rr_ratio']}x** · Min signals: **{custom_params['min_signal_count']}/15** · Target: **{int(custom_params['target_pct']*100)}%**")

    # Fix 2: show live regime banner
    _regime = st.session_state.get("screener_regime", {})
    if _regime:
        if _regime.get("is_bullish"):
            st.success(f"Market Regime: **BULLISH** — Nifty {_regime['nifty_close']:,} is above 200-MA {_regime['nifty_ma200']:,}. Breakout signals are active.")
        else:
            st.error(f"Market Regime: **BEARISH** — Nifty {_regime['nifty_close']:,} is below 200-MA {_regime['nifty_ma200']:,}. All signals suppressed to avoid trading against the trend.")

    col_btn, col_info = st.columns([1, 3])
    with col_btn:
        run_btn = st.button("▶ Run Screener", type="primary", use_container_width=True)
    with col_info:
        st.caption("First run may take 2–3 min (fetches live data). Subsequent runs use 6-hr cache and are much faster.")

    if run_btn:
        progress_bar = st.progress(0)
        status_txt = st.empty()

        def on_progress(frac, sym):
            progress_bar.progress(frac)
            status_txt.caption(f"Analyzing {sym}…")

        with st.spinner("Scanning stocks…"):
            results, regime = run_screener(STOCK_UNIVERSE, custom_params, progress_cb=on_progress)

        progress_bar.empty()
        status_txt.empty()
        st.session_state["screener_results"] = results
        st.session_state["screener_regime"] = regime
        st.success(f"Scan complete — **{len(results)} breakout candidates** found.")

    results = st.session_state.get("screener_results", [])
    regime = st.session_state.get("screener_regime", {})

    if results:
        rows = []
        for r in results:
            hold = r.get("hold", {})
            bd = r.get("breakout_date")
            bda = r.get("breakout_days_ago")
            bd_str = f"{bd} ({bda}d ago)" if bd and bda is not None else (bd or "—")
            rows.append({
                "Symbol": r["symbol"],
                "Breakout Date": bd_str,
                "Price (₹)": r["price"],
                "Score": r["score"],
                "RS Rank": r.get("rs_rank") or 0.0,
                "Signals": r["signal_count"],
                "UT Bot": "🤖 BUY" if r.get("ut_bot_buy") else "",
                "UT Stop (₹)": r.get("ut_stop", 0.0),
                "Target (₹)": r["target"],
                "Stop Loss (₹)": r["stop_loss"],
                "Upside %": r["upside_pct"],
                "R:R": r["rr_ratio"],
                "Hold": hold.get("label", "—"),
                "Rel Vol": r["rel_volume"],
                "RSI": r["rsi"],
                "ADX": r["adx"],
                "From 52W High": f"{r['pct_from_52w_high']}%",
                "Reasons": r["reasons"],
            })

        df_display = pd.DataFrame(rows)

        def color_score(val):
            if val >= 70: return "color: #00C896; font-weight:700"
            if val >= 50: return "color: #FFA500; font-weight:700"
            return "color: #FF4B4B"

        def color_upside(val):
            return "color: #00C896" if val >= 10 else "color: #FFA500"

        def color_utbot(val):
            return "color: #00C896; font-weight:700" if val else ""

        def color_rs(val):
            if val >= 80: return "color: #00C896; font-weight:700"
            if val >= 60: return "color: #FFA500"
            return "color: #FF4B4B"

        def color_bkdate(val):
            # Fresh breakout (≤10d) = green, stale (>20d) = orange
            if not val or val == "—":
                return "color: #888"
            try:
                days = int(str(val).split("(")[1].split("d")[0])
                if days <= 10: return "color: #00C896; font-weight:700"
                if days <= 20: return "color: #FFA500"
                return "color: #888"
            except Exception:
                return ""

        styled = (
            df_display.style
            .map(color_score, subset=["Score"])
            .map(color_upside, subset=["Upside %"])
            .map(color_utbot, subset=["UT Bot"])
            .map(color_rs, subset=["RS Rank"])
            .map(color_bkdate, subset=["Breakout Date"])
            .format({
                "Price (₹)": "{:,.2f}",
                "UT Stop (₹)": "{:,.2f}",
                "Target (₹)": "{:,.2f}",
                "Stop Loss (₹)": "{:,.2f}",
                "R:R": "{:.2f}",
                "RS Rank": "{:.0f}",
                "Rel Vol": "{:.2f}",
                "RSI": "{:.1f}",
                "ADX": "{:.1f}",
            })
        )
        st.dataframe(styled, height=420)

        _scr_col, _ = st.columns([1, 4])
        with _scr_col:
            st.download_button(
                label="📥 Export to Excel",
                data=_to_excel_bytes({"Screener Results": df_display}),
                file_name=f"screener_{date.today()}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )

        st.divider()
        st.markdown("**Select a stock to open in Stock Analysis →**")
        pick = st.selectbox("Symbol", [r["symbol"] for r in results], key="screener_pick")
        if st.button("Open in Stock Analysis", use_container_width=False):
            st.session_state["analysis_symbol"] = pick
            st.info(f"Switch to the **📊 Stock Analysis** tab to view {pick}.")
    else:
        if "screener_results" in st.session_state:
            _r = st.session_state.get("screener_regime", {})
            if _r and not _r.get("is_bullish") and custom_params.get("require_bull_market", True):
                st.error(
                    "**0 results — Market is BEARISH.** Nifty is below its 200-MA so the Bull Market Gate "
                    "blocked all signals. To scan anyway, **uncheck 'Bull Market Gate'** in the sidebar."
                )
            else:
                st.warning(
                    "No breakout candidates found. Try: "
                    "**lower Min Score** (try 35–40) · "
                    "**lower Min RS Rank** (try 0–30) · "
                    "**uncheck Bull Market Gate** · "
                    "or lower Min R:R to 1.2x"
                )

# ─── TAB 3: Stock Analysis ───────────────────────────────────────────────────

with tab3:
    st.subheader("Individual Stock Analysis")

    default_sym = st.session_state.get("analysis_symbol", STOCK_UNIVERSE[0])
    sym_input = st.text_input(
        "NSE Symbol",
        value=default_sym,
        placeholder="e.g. RELIANCE, TCS, INFY",
        help="Enter any NSE symbol (without .NS suffix)",
    ).upper().strip()

    analyze_btn = st.button("Analyze", type="primary")

    if analyze_btn or ("last_analyzed" in st.session_state and st.session_state.get("last_analyzed") == sym_input):
        st.session_state["last_analyzed"] = sym_input

        with st.spinner(f"Fetching data for {sym_input}…"):
            result = analyze_stock(sym_input, custom_params)

        if result is None:
            st.error(f"Could not fetch or analyze **{sym_input}**. Check the symbol and try again.")
        else:
            df = result["df"].tail(180)   # last 9 months for readability

            # Hold suggestion banner
            hold = result.get("hold", {})
            hold_cat = hold.get("category", "")
            hold_color = {"SWING_LONG": "#00C896", "SWING_MED": "#1E90FF", "MOMENTUM": "#FFA500", "SHORT_TERM": "#FF4B4B"}.get(hold_cat, "#aaa")
            st.markdown(
                f"<div style='background:#1E2130; border-radius:8px; padding:10px 16px; border-left:4px solid {hold_color}; margin-bottom:12px'>"
                f"<span style='color:{hold_color}; font-weight:700'>Suggested Hold: {hold.get('label','—')}</span>"
                f"&nbsp;&nbsp;<span style='color:#aaa; font-size:0.88rem'>{hold.get('exit_logic','')}</span></div>",
                unsafe_allow_html=True,
            )

            # Metrics row
            rs_rank = result.get("rs_rank")
            rs_str = f"{rs_rank:.0f}/100" if rs_rank is not None else "N/A"
            m1, m2, m3, m4, m5, m6, m7 = st.columns(7)
            m1.metric("Price", f"₹{result['price']:,}")
            m2.metric("Target", f"₹{result['target']:,}", f"+{result['upside_pct']}%")
            m3.metric("Stop Loss", f"₹{result['stop_loss']:,}", f"-{round((result['price']-result['stop_loss'])/result['price']*100,1)}%")
            m4.metric("Score", f"{result['score']}")
            m5.metric("R:R Ratio", f"{result['rr_ratio']}x")
            m6.metric("Rel. Volume", f"{result['rel_volume']}x")
            m7.metric("RS Rank", rs_str)
            st.caption(f"Target basis: {result.get('target_label', '')}")

            sr_data = _compute_sr_trendlines(df)
            st.plotly_chart(_build_candlestick(df, sym_input, sr_data=sr_data))

            # Export
            _exp_col, _ = st.columns([1, 4])
            with _exp_col:
                _summary_df = pd.DataFrame([{
                    "Symbol": sym_input,
                    "Price (₹)": result["price"],
                    "Target (₹)": result["target"],
                    "Stop Loss (₹)": result["stop_loss"],
                    "Upside %": result["upside_pct"],
                    "Score": result["score"],
                    "R:R": result["rr_ratio"],
                    "Rel Volume": result["rel_volume"],
                    "RS Rank": result.get("rs_rank", "N/A"),
                    "Hold Suggestion": result.get("hold", {}).get("label", "—"),
                    "UT Bot Buy": "Yes" if result.get("ut_bot_buy") else "No",
                    "Reasons": result["reasons"],
                }])
                _signals_df = pd.DataFrame([
                    {"Signal": k.replace("_", " ").title(), "Active": "Yes" if v else "No"}
                    for k, v in result["signals"].items()
                ])
                st.download_button(
                    label="📥 Export to Excel",
                    data=_to_excel_bytes({
                        "Summary": _summary_df,
                        "Signals": _signals_df,
                        "Price & Indicators": result["df"].reset_index(),
                    }),
                    file_name=f"{sym_input}_analysis_{date.today()}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )

            # Breakout checklist
            col_sigs, col_score = st.columns([2, 1])
            with col_sigs:
                st.markdown("#### Breakout Signal Checklist")
                SIGNAL_LABELS = {
                    # original 10
                    "near_52w_high":         "Near / Above 52-Week High",
                    "price_above_prev_high": "Closed Above Previous Day's High",
                    "volume_surge":          f"Volume ≥ {custom_params['min_rel_volume']}x 20-day Avg",
                    "rsi_bullish":           f"RSI in {custom_params['rsi_min']}–{custom_params['rsi_max']} Zone",
                    "macd_bullish":          "MACD Bullish Crossover",
                    "above_ma20":            "Price Above MA20",
                    "above_ma50":            "Price Above MA50",
                    "adx_strong":            f"ADX ≥ {custom_params['adx_min']} (Strong Trend)",
                    "bb_breakout":           "Above Bollinger Upper Band",
                    "momentum_positive":     "5-Day ROC > 1%",
                    # quality filters
                    "above_ma150":   "Price Above MA150 (Minervini Stage-2)",
                    "rs_vs_nifty":   "Outperforming Nifty 50 (20-day RS)",
                    "tight_base":    "Tight Base / BB Squeeze or True VCP",
                    "strong_close":  "Strong Closing Candle (Top 35% of Range)",
                    "vol_trend_up":  "Volume Accumulation (5d Avg > 20d Avg)",
                    # new v3 signals
                    "weekly_trend":   "Weekly Trend Bullish (W-MA20 + W-RSI > 50)",
                    "candle_signal":  "Bullish Candlestick Pattern (Engulfing / Hammer / Inside Bar)",
                    "true_vcp":       "True VCP — 3 Contracting Swings + Declining Volume",
                    "sector_leading": "Stock in a Leading Sector (Sector ROC > Nifty)",
                    # UT Bot
                    "ut_bot_buy":    "UT Bot Buy — Price Crossed Above ATR Trailing Stop",
                }
                for key, label in SIGNAL_LABELS.items():
                    icon = "✅" if result["signals"].get(key) else "❌"
                    bold = " font-weight:700; color:#00C896" if key == "ut_bot_buy" and result["signals"].get(key) else ""
                    st.markdown(f"<span style='{bold}'>{icon} &nbsp; {label}</span>", unsafe_allow_html=True)

            # UT Bot stop level
            if result.get("ut_bot_buy"):
                st.success(f"🤖 **UT Bot Buy Signal Active** — ATR trailing stop is at **₹{result['ut_stop']:,}**. Price closed above this level today (crossover entry).")
            else:
                st.caption(f"UT Bot trailing stop: ₹{result.get('ut_stop', 0):,.2f} — no crossover today.")

            with col_score:
                st.markdown("#### Score Breakdown")
                breakdown = result["breakdown"]
                for component, pts in breakdown.items():
                    max_pts = {"volume": 25, "price_action": 30, "momentum": 25, "trend": 20, "entry_quality": 20}[component]
                    pct = pts / max_pts
                    bar_color = "#00C896" if pct >= 0.6 else "#FFA500" if pct >= 0.3 else "#FF4B4B"
                    label = component.replace("_", " ").title()
                    st.markdown(
                        f"""<div style='margin-bottom:10px'>
                        <div style='display:flex; justify-content:space-between'><span>{label}</span><span>{pts}/{max_pts}</span></div>
                        <div style='background:#1E2130; border-radius:4px; height:8px'>
                            <div style='background:{bar_color}; width:{int(pct*100)}%; height:8px; border-radius:4px'></div>
                        </div></div>""",
                        unsafe_allow_html=True,
                    )
                st.markdown(f"**Total: {result['score']}/100**")
                st.markdown(f"*{result['reasons']}*")

# ─── TAB 4: Backtest ──────────────────────────────────────────────────────────

with tab4:
    st.subheader("Strategy Backtest (2-Year Historical Simulation)")
    st.markdown(
        "Simulates the breakout strategy on historical data. "
        "Each signal triggers a trade: **exit on +6% target, –5% stop-loss, or after 44 trading days (~2 months)**. "
        "Only trades when **Nifty is above its 200-MA** and **≥6 out of 10 signals** are active."
    )

    sample_size = st.slider("Stocks to sample", 10, min(50, len(STOCK_UNIVERSE)), 25, step=5)
    bt_btn = st.button("▶ Run Backtest", type="primary")

    if bt_btn:
        with st.spinner(f"Backtesting on {sample_size} stocks × 2 years of history…"):
            bt = run_backtest(STOCK_UNIVERSE, custom_params, sample_size=sample_size)
        st.session_state["backtest_result"] = bt

    bt = st.session_state.get("backtest_result")

    if bt:
        b1, b2, b3, b4, b5, b6, b7 = st.columns(7)
        b1.metric("Total Trades", bt["total_trades"])
        b2.metric("Win Rate", f"{bt['win_rate']}%")
        b3.metric("Avg Win", f"+{bt['avg_win']}%")
        b4.metric("Avg Loss", f"{bt['avg_loss']}%")
        b5.metric("Avg Return/Trade", f"{bt['avg_return']}%")
        b6.metric("Expectancy", f"{bt['expectancy']}%")
        b7.metric("Avg Hold", f"{bt.get('avg_hold_days', 0):.0f}d")

        st.divider()

        # Outcome distribution
        col_pie, col_eq = st.columns([1, 2])
        with col_pie:
            st.markdown("#### Outcome Distribution")
            labels = ["Target Hit", "UT Sell Exit", "Trail Stop", "Stop Loss", "Time Exit"]
            values = [bt.get("target_hit", 0), bt.get("ut_sell_exit", 0), bt.get("trail_stop_hit", 0), bt.get("stop_loss_hit", 0), bt.get("time_exit", 0)]
            pie_fig = go.Figure(go.Pie(
                labels=labels, values=values,
                marker_colors=["#00C896", "#00E5FF", "#00BFFF", "#FF4B4B", "#FFA500"],
                hole=0.45,
                textinfo="label+percent",
            ))
            pie_fig.update_layout(
                height=240, template="plotly_dark",
                paper_bgcolor="#0E1117",
                margin=dict(l=10, r=10, t=10, b=10),
                showlegend=False,
            )
            st.plotly_chart(pie_fig)

        with col_eq:
            st.markdown("#### Cumulative Return (Equal-Weight, All Trades)")
            st.plotly_chart(_build_equity_curve(bt["trades"]))

        st.divider()

        # ── Peak Return Analysis ───────────────────────────────────────────
        st.markdown("#### 📈 Peak Return Analysis — What If You Held Longer?")
        st.caption(
            "For every trade, we tracked the highest price the stock reached within 90 trading days "
            "from entry — regardless of when/how the trade was actually exited."
        )

        pk1, pk2, pk3 = st.columns(3)
        pk1.metric(
            "Avg Actual Exit",
            f"{bt['avg_return']:+.2f}%",
            help="Average P&L at the actual exit point (target / SL / time exit)",
        )
        pk2.metric(
            "Avg Peak Return",
            f"{bt['avg_peak_return']:+.2f}%",
            f"+{bt['avg_left_on_table']:.2f}% left on table",
            help="Average highest return the stock reached within 90 days of entry",
        )
        pk3.metric(
            "Avg Days to Peak",
            f"{bt['avg_days_to_peak']:.0f} days",
            help="On average, how many trading days after entry the stock hit its peak",
        )

        # Scatter: actual exit % vs peak % per trade
        tdf = bt["trades"]
        outcome_color_map = {"TARGET_HIT": "#00C896", "UT_SELL": "#00E5FF", "TRAIL_STOP": "#00BFFF", "STOP_LOSS": "#FF4B4B", "TIME_EXIT": "#FFA500"}
        colors = [outcome_color_map.get(o, "#aaa") for o in tdf["outcome"]]

        def _hover(row):
            return (
                f"{row['symbol']}<br>"
                f"Entry: {row['entry_date']}<br>"
                f"Exit: {row['pnl_pct']:+.1f}%<br>"
                f"Peak: {row['peak_return_pct']:+.1f}%<br>"
                f"Days to peak: {int(row['days_to_peak'])}"
            )

        scatter_fig = go.Figure()
        for outcome, color in outcome_color_map.items():
            mask = tdf["outcome"] == outcome
            subset = tdf[mask]
            scatter_fig.add_trace(go.Scatter(
                x=subset["pnl_pct"],
                y=subset["peak_return_pct"],
                mode="markers",
                marker=dict(color=color, size=7, opacity=0.75),
                name=outcome.replace("_", " ").title(),
                text=subset.apply(_hover, axis=1),
                hovertemplate="%{text}<extra></extra>",
            ))

        # Diagonal reference line (peak = actual exit)
        lim = max(tdf["peak_return_pct"].max(), tdf["pnl_pct"].max(), 10)
        scatter_fig.add_trace(go.Scatter(
            x=[-20, lim], y=[-20, lim],
            mode="lines",
            line=dict(color="gray", dash="dot", width=1),
            name="Peak = Exit (no gain from holding)",
            showlegend=True,
        ))

        scatter_fig.update_layout(
            height=380, template="plotly_dark",
            paper_bgcolor="#0E1117", plot_bgcolor="#0E1117",
            xaxis=dict(title="Actual Exit Return %", gridcolor="#1E2130", zeroline=True, zerolinecolor="#444"),
            yaxis=dict(title="Peak Return % (90-day window)", gridcolor="#1E2130", zeroline=True, zerolinecolor="#444"),
            legend=dict(orientation="h", y=1.08),
            margin=dict(l=10, r=10, t=30, b=10),
        )
        st.plotly_chart(scatter_fig)
        st.caption("Points **above the dotted line** = stock had more upside after the exit point. Hover for details.")

        st.divider()

        # ── Trade Log ─────────────────────────────────────────────────────
        st.markdown(f"#### Trade Log *(from {bt['symbols_tested']} stocks)*")
        trades_show = bt["trades"][[
            "symbol", "entry_date", "entry_price", "exit_price",
            "exit_day", "hold_budget", "outcome", "pnl_pct", "peak_return_pct", "days_to_peak", "left_on_table"
        ]].copy()
        trades_show.columns = [
            "Symbol", "Entry Date", "Entry ₹", "Exit ₹",
            "Days Held", "Budget", "Outcome", "P&L %", "Peak %", "Days to Peak", "Left on Table %"
        ]

        def style_outcome(val):
            if val == "TARGET_HIT":  return "color: #00C896; font-weight:700"
            if val == "UT_SELL":     return "color: #00E5FF; font-weight:700"
            if val == "TRAIL_STOP":  return "color: #00BFFF"
            if val == "STOP_LOSS":   return "color: #FF4B4B; font-weight:700"
            return "color: #FFA500"

        def style_pnl(val):
            return "color: #00C896" if val > 0 else "color: #FF4B4B"

        def style_peak(val):
            if val >= 20: return "color: #00C896; font-weight:700"
            if val >= 10: return "color: #00C896"
            if val > 0:   return "color: #aaa"
            return "color: #FF4B4B"

        styled_trades = (
            trades_show.style
            .map(style_outcome, subset=["Outcome"])
            .map(style_pnl, subset=["P&L %"])
            .map(style_peak, subset=["Peak %"])
            .map(style_pnl, subset=["Left on Table %"])
            .format({
                "P&L %": "{:+.2f}%",
                "Peak %": "{:+.2f}%",
                "Left on Table %": "{:+.2f}%",
                "Entry ₹": "{:,.2f}",
                "Exit ₹": "{:,.2f}",
                "Days to Peak": "{:.0f}",
                "Days Held": "{:.0f}",
                "Budget": "{:.0f}d",
            })
        )
        st.dataframe(styled_trades, height=380)

        _bt_col, _ = st.columns([1, 4])
        with _bt_col:
            _bt_summary = pd.DataFrame([{
                "Total Trades": bt["total_trades"],
                "Win Rate %": bt["win_rate"],
                "Avg Win %": bt["avg_win"],
                "Avg Loss %": bt["avg_loss"],
                "Avg Return %": bt["avg_return"],
                "Expectancy %": bt["expectancy"],
                "Target Hit": bt.get("target_hit", 0),
                "UT Sell Exit": bt.get("ut_sell_exit", 0),
                "Trail Stop": bt.get("trail_stop_hit", 0),
                "Stop Loss Hit": bt.get("stop_loss_hit", 0),
                "Time Exit": bt.get("time_exit", 0),
                "Symbols Tested": bt["symbols_tested"],
                "Avg Hold Days": bt.get("avg_hold_days", 0),
                "Avg Peak Return %": bt.get("avg_peak_return", 0),
                "Avg Left on Table %": bt.get("avg_left_on_table", 0),
            }])
            st.download_button(
                label="📥 Export to Excel",
                data=_to_excel_bytes({
                    "Trade Log": trades_show.reset_index(drop=True),
                    "Summary": _bt_summary,
                }),
                file_name=f"backtest_{date.today()}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )

        st.caption(
            "⚠️ Past performance does not guarantee future results. "
            "This backtest does not account for slippage, brokerage, or taxes."
        )
    else:
        st.info("Click **Run Backtest** to simulate the strategy on 2 years of historical data.")

# ─── TAB 5: Best Buy ──────────────────────────────────────────────────────────

with tab5:
    st.subheader("⭐ Best Buy — Top Conviction Picks")
    st.markdown(
        "Curated shortlist from the screener ranked by **conviction score** — "
        "a composite of setup quality, RS rank, UT Bot signal, VCP, weekly trend, and R:R. "
        "Run the **🔍 Screener** first to populate."
    )

    bb_results = st.session_state.get("screener_results", [])

    if not bb_results:
        st.info("No screener results yet. Go to the **🔍 Screener** tab and click **Run Screener**, then come back here.")
    else:
        # Filter and score
        picks = []
        for r in bb_results:
            if r.get("rr_ratio", 0) < 1.5 or r.get("score", 0) < 50:
                continue
            picks.append({**r, "conviction": _conviction_score(r), "catalyst": _top_catalysts(r)})

        picks.sort(key=lambda x: x["conviction"], reverse=True)
        top10 = picks[:10]

        if not top10:
            st.warning("No high-conviction picks (Score ≥ 50 + R:R ≥ 1.5). Try lowering Min Score or Min R:R in the sidebar.")
        else:
            # ── Summary chips ────────────────────────────────────────────────
            avg_cv = sum(p["conviction"] for p in top10) / len(top10)
            avg_rr = sum(p.get("rr_ratio", 0) for p in top10) / len(top10)
            avg_rs = sum(p.get("rs_rank") or 0 for p in top10) / len(top10)
            ut_cnt = sum(1 for p in top10 if p.get("ut_bot_buy"))

            hc1, hc2, hc3, hc4 = st.columns(4)
            hc1.metric("Total Picks", len(picks))
            hc2.metric("Avg Conviction", f"{avg_cv:.0f}")
            hc3.metric("Avg R:R", f"{avg_rr:.1f}x")
            hc4.metric("UT Bot Active", f"{ut_cnt} / {len(top10)}")

            st.divider()

            # ── Top 3 hero cards ─────────────────────────────────────────────
            st.markdown("### Top 3 Picks")
            medals = ["🥇", "🥈", "🥉"]
            hero_cols = st.columns(3)

            HOLD_COLORS = {
                "SWING_LONG": "#00C896", "SWING_MED": "#1E90FF",
                "MOMENTUM": "#FFA500",   "SHORT_TERM": "#FF4B4B",
            }
            MAX_CV = 166.0  # theoretical max conviction score

            for col, r, medal in zip(hero_cols, top10[:3], medals):
                with col:
                    cv       = r["conviction"]
                    cv_pct   = min(int(cv / MAX_CV * 100), 100)
                    bar_col  = "#00C896" if cv_pct >= 65 else "#FFA500" if cv_pct >= 45 else "#FF4B4B"
                    hold     = r.get("hold", {})
                    hc       = HOLD_COLORS.get(hold.get("category", ""), "#aaa")
                    rs       = r.get("rs_rank") or 0
                    risk_pct = round((r["price"] - r["stop_loss"]) / r["price"] * 100, 1)
                    ut_badge = (
                        "<span style='background:#003320;color:#00C896;border:1px solid #00C896;"
                        "border-radius:4px;padding:1px 7px;font-size:0.72rem;font-weight:700'>🤖 UT BUY</span>"
                        if r.get("ut_bot_buy") else ""
                    )

                    st.markdown(f"""
<div style='background:#1A1E2E;border-radius:12px;padding:18px;border:1px solid #2A3050;border-top:3px solid {bar_col}'>
  <div style='display:flex;justify-content:space-between;align-items:center;margin-bottom:4px'>
    <span style='font-size:1rem;color:#aaa'>{medal} Rank #{top10.index(r)+1}</span>
    {ut_badge}
  </div>
  <div style='font-size:1.65rem;font-weight:800;color:#FAFAFA;line-height:1.1'>{r['symbol']}</div>
  <div style='font-size:0.82rem;color:{bar_col};font-weight:700;margin-bottom:12px'>
    Conviction {cv:.0f} &nbsp;·&nbsp; Score {r['score']}
  </div>
  <div style='background:#0E1117;border-radius:6px;padding:10px 12px;margin-bottom:10px'>
    <div style='font-size:1rem;color:#FAFAFA'>₹{r['price']:,} <span style='color:#aaa;font-size:0.8rem'>entry</span></div>
    <div style='color:#00C896;font-size:1rem;font-weight:700'>▲ ₹{r['target']:,}&nbsp;<span style='font-size:0.82rem;font-weight:400'>(+{r['upside_pct']}%)</span></div>
    <div style='color:#FF4B4B;font-size:0.88rem'>▼ SL ₹{r['stop_loss']:,}&nbsp;<span style='font-size:0.8rem'>({risk_pct}% risk)</span></div>
  </div>
  <div style='display:flex;gap:7px;flex-wrap:wrap;margin-bottom:8px'>
    <span style='background:#1E2130;border-radius:4px;padding:2px 8px;font-size:0.78rem;color:#FFD700'>R:R {r['rr_ratio']}x</span>
    <span style='background:#1E2130;border-radius:4px;padding:2px 8px;font-size:0.78rem;color:{hc}'>{hold.get('label','—')}</span>
    <span style='background:#1E2130;border-radius:4px;padding:2px 8px;font-size:0.78rem;color:#FFA500'>RS {rs:.0f}</span>
  </div>
  <div style='font-size:0.78rem;color:#7B8CCC'>{r['catalyst']}</div>
  <div style='background:#1E2130;border-radius:3px;height:5px;margin-top:10px'>
    <div style='background:{bar_col};width:{cv_pct}%;height:5px;border-radius:3px'></div>
  </div>
</div>""", unsafe_allow_html=True)

            st.divider()

            # ── Full ranked table ─────────────────────────────────────────────
            st.markdown(f"### All {len(top10)} Picks — Ranked by Conviction")

            rows = []
            for rank, r in enumerate(top10, 1):
                hold = r.get("hold", {})
                rows.append({
                    "#":           rank,
                    "Symbol":      r["symbol"],
                    "Conviction":  r["conviction"],
                    "Score":       r["score"],
                    "Price (₹)":   r["price"],
                    "Target (₹)":  r["target"],
                    "Upside %":    r["upside_pct"],
                    "SL (₹)":      r["stop_loss"],
                    "R:R":         r["rr_ratio"],
                    "RS Rank":     r.get("rs_rank") or 0.0,
                    "Hold":        hold.get("label", "—"),
                    "UT Bot":      "🤖" if r.get("ut_bot_buy") else "",
                    "Catalyst":    r["catalyst"],
                })

            bb_df = pd.DataFrame(rows)

            def _cv_style(v):
                if v >= 100: return "color:#00C896;font-weight:700"
                if v >= 80:  return "color:#FFA500;font-weight:700"
                return "color:#aaa"

            def _sc_style(v):
                if v >= 70: return "color:#00C896;font-weight:700"
                if v >= 50: return "color:#FFA500;font-weight:700"
                return "color:#FF4B4B"

            def _up_style(v):
                return "color:#00C896" if v >= 10 else "color:#FFA500"

            def _rr_style(v):
                if v >= 2.5: return "color:#00C896;font-weight:700"
                if v >= 1.8: return "color:#FFA500"
                return "color:#aaa"

            def _rs_style(v):
                if v >= 80: return "color:#00C896;font-weight:700"
                if v >= 60: return "color:#FFA500"
                return "color:#FF4B4B"

            styled_bb = (
                bb_df.style
                .map(_cv_style, subset=["Conviction"])
                .map(_sc_style, subset=["Score"])
                .map(_up_style, subset=["Upside %"])
                .map(_rr_style, subset=["R:R"])
                .map(_rs_style, subset=["RS Rank"])
                .format({
                    "Conviction": "{:.0f}",
                    "Price (₹)":  "{:,.2f}",
                    "Target (₹)": "{:,.2f}",
                    "SL (₹)":     "{:,.2f}",
                    "R:R":        "{:.2f}",
                    "RS Rank":    "{:.0f}",
                    "Upside %":   "{:.1f}%",
                })
            )
            st.dataframe(styled_bb, height=420)

            _bb_col, _ = st.columns([1, 4])
            with _bb_col:
                _bb_export = bb_df.copy()
                _bb_export["Conviction Formula"] = (
                    "Score + UT Bot(+15) + VCP(+12) + Candle(+8) + Weekly(+7) + Sector(+6) + R:R bonus(up to +8) + RS bonus(up to +10)"
                )
                st.download_button(
                    label="📥 Export to Excel",
                    data=_to_excel_bytes({"Best Buy Picks": _bb_export}),
                    file_name=f"best_buy_{date.today()}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )

            st.caption(
                "**Conviction** = Score + UT Bot (+15) + True VCP (+12) + Candle Pattern (+8) "
                "+ Weekly Trend (+7) + Sector Leading (+6) + R:R bonus (up to +8) + RS bonus (up to +10). "
                "⚠️ For educational use only. Not financial advice."
            )
