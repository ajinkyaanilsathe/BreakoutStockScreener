_raw_universe = [
    # ── Nifty 50 ──────────────────────────────────────────────────────────────
    "RELIANCE", "TCS", "HDFCBANK", "INFY", "ICICIBANK", "HINDUNILVR", "SBIN",
    "BHARTIARTL", "KOTAKBANK", "LT", "AXISBANK", "ASIANPAINT", "MARUTI",
    "WIPRO", "ULTRACEMCO", "BAJFINANCE", "TITAN", "NESTLEIND", "POWERGRID",
    "HCLTECH", "BAJAJFINSV", "SUNPHARMA", "TECHM", "NTPC", "ONGC",
    "TATAMOTORS", "INDUSINDBK", "M&M", "COALINDIA", "TATASTEEL",
    "ADANIENT", "ADANIPORTS", "DIVISLAB", "DRREDDY", "EICHERMOT",
    "GRASIM", "HEROMOTOCO", "HINDALCO", "ITC", "JSWSTEEL",
    "SBILIFE", "HDFCLIFE", "APOLLOHOSP", "BAJAJ-AUTO", "BPCL",
    "BRITANNIA", "CIPLA", "LTIM", "TATACONSUM", "VEDL",

    # ── Private Banks ─────────────────────────────────────────────────────────
    "YESBANK", "RBLBANK", "DCBBANK", "FEDERALBNK", "IDFCFIRSTB",
    "BANDHANBNK", "CITYUNIONBK", "KARURVYSYA", "SOUTHINDBANK", "KTKBANK",
    "JKBANK", "NAINFINANCE", "EQUITASBNK", "UJJIVANSFB", "SURYODAY",
    "UTKARSHBNK", "ESAFSFB",

    # ── PSU Banks ─────────────────────────────────────────────────────────────
    "CANBK", "BANKBARODA", "UNIONBANK", "INDIANB", "PNB",
    "UCOBANK", "MAHABANK", "CENTRALBK", "IOB", "IDBI",

    # ── NBFCs / Housing Finance ───────────────────────────────────────────────
    "PNBHOUSING", "LICHSGFIN", "MANAPPURAM", "CANFINHOME", "REPCO",
    "AAVAS", "APTUS", "CREDITACC", "SPANDANA", "SHRIRAMFIN",
    "CHOLAFIN", "MUTHOOTFIN", "MUTHOOTMICR", "ABCAPITAL", "BAJAJHLDNG",
    "LICI",

    # ── Capital Markets / Insurance ───────────────────────────────────────────
    "HDFCAMC", "SBICARD", "ANGELONE", "MOTILALOFS", "CDSL",
    "BSE", "CAMS", "KFINTECH", "ISEC", "MFSL",
    "NIACL", "STARHEALTH", "POLICYBZR", "GICRE", "ICICIGI",
    "ICICIPRULI",                          # removed duplicate LICI

    # ── IT & Tech ─────────────────────────────────────────────────────────────
    "MPHASIS", "COFORGE", "PERSISTENT", "LTTS", "KPITTECH",
    "TATAELXSI", "CYIENT", "BIRLASOFT", "MASTEK", "ZENSAR",
    "FIRSTSOURCE", "RATEGAIN", "TATACOMM", "MAPMYINDIA", "INDIAMART",
    "NYKAA", "PAYTM", "TANLA", "ROUTE", "NAZARA",
    "INTELLECT", "RAMCO", "ONMOBILE", "ZOMATO",  # removed MSTECHNOLOGIES
    "DELHIVERY", "INFOEDGE", "NAUKRI",

    # ── Pharma / Healthcare ───────────────────────────────────────────────────
    "LUPIN", "AUROPHARMA", "TORNTPHARM", "ALKEM", "BIOCON",
    "LALPATHLAB", "METROPOLIS", "THYROCARE", "JBCHEPHARM", "GLAND",
    "ERIS", "STRIDES", "ABBOTINDIA", "GLAXO", "PFIZER",
    "SANOFI", "ZYDUSLIFE", "AJANTPHARM", "GRANULES", "NATCOPHARM",
    "IPCALAB", "LAURUS", "SOLARA", "ALEMBICLTD", "SEQUENT",
    "NEULANDLAB", "SUVEN", "HIKAL", "RAINBOW", "FORTIS",
    "MAXHEALTH", "NARAYANA", "ASTERDM", "KIMS", "KRSNAA",
    "CONCORD", "MEDPLUS",                  # removed VIJAYABANK (delisted)

    # ── Auto & Auto Ancillaries ───────────────────────────────────────────────
    "TVSMOTOR", "ASHOKLEY", "ESCORTS", "BALKRISIND", "APOLLOTYRE",
    "CEAT", "MRF", "EXIDEIND", "AMARARAJA", "MINDAIND",
    "TIINDIA", "CRAFTSMAN", "SONACOMS", "ENDURANCE", "SUPRAJIT",
    "BHARATFORG", "WABCOINDIA", "SKF", "TIMKEN", "GREAVESCOT",
    "MOTHERSON", "BOSCHLTD", "SCHAEFFLER", "OLECTRA", "SAMVARDHANA",
    "SWARAJENG", "GABRIEL", "JAMNA", "MINDA", "UCALFUEL",

    # ── FMCG & Consumer ───────────────────────────────────────────────────────
    "PIDILITIND", "BERGEPAINT", "HAVELLS", "DABUR", "MARICO",
    "COLPAL", "GODREJCP", "EMAMILTD", "BAJAJCON", "RADICO",
    "UNITEDBREWERIES", "VBLLTD", "MCDOWELL-N", "JYOTHYLAB", "GILLETTE",
    "PGHH", "CCL", "BATAINDIA", "VGUARD", "RAJESHEXPO",
    "KAJARIACER", "WHIRLPOOL", "ORIENTELEC", "CROMPTON", "SYMPHONY",
    "BLUESTARCO", "AMBER", "KAYNES", "DIXON", "TRENT",
    "DMART", "INDIGO", "JUBLFOOD", "WESTLIFE", "DEVYANI",
    "SAPPHIREZN", "BECTORFOOD",

    # ── Chemicals & Specialty ─────────────────────────────────────────────────
    "DEEPAKNTR", "TATACHEM", "GNFC", "COROMANDEL", "GSFC",
    "CHAMBALFERT", "SRF", "ATUL", "ALKYLAMINE", "FINEORG",
    "VINATI", "GALAXYSURF", "PCBL", "NAVINFLUOR", "AARTIIND",
    "SUDARSCHEM", "CLEAN", "NOCIL", "ROSSARI", "GHCL",
    "BASF", "NEOGEN", "ASAHIINDIA", "FLUOROCHEM", "ANURAS",
    "INSECTICIDES", "RALLIS", "PIIND", "UPL", "SHARDA",
    "DHANUKA", "BAYERCROP", "SUMICHEM",    # removed duplicate TATACHEM

    # ── Metals & Mining ───────────────────────────────────────────────────────
    "NMDC", "SAIL", "HINDCOPPER", "NATIONALUM", "WELCORP",
    "RATNAMANI", "TINPLATE", "JINDALSAW", "HINDZINC", "MOIL",
    "JSPL", "APLAPOLLO", "GRAVITA", "MIDHANI",
    # removed SANDUMA (invalid), VEDL / JSWSTEEL / TATASTEEL (duplicates from Nifty 50)

    # ── Energy / Oil & Gas / Power ────────────────────────────────────────────
    "ADANIGREEN", "ADANITRANS", "TORNTPOWER", "CESC", "MGL",
    "IGL", "PETRONET", "MRPL", "GSPL", "GUJGAS",
    "NHPC", "SJVN", "IREDA", "GIPCL", "JPPOWER",
    "RPOWER", "KALPATPOWR", "ENGINERSIN", "TATAPOWER", "GAIL",
    "IOC",
    # removed BPCL / ONGC / COALINDIA (duplicates from Nifty 50)

    # ── Infrastructure / Construction / Defence ───────────────────────────────
    "NBCC", "NCC", "KEC", "PNCINFRA", "HGINFRA",
    "GRINFRA", "IRCON", "RITES", "BEML", "HAL",
    "BEL", "CONCOR", "COCHINSHIP", "GRSE", "MAZAGON",
    "TITAGARH", "TEXRAIL", "IRFC", "RVNL", "HUDCO",
    "JKIL", "AHLUCONT", "ITD", "KNRCON", "ASHOKA",

    # ── Real Estate ───────────────────────────────────────────────────────────
    "DLF", "GODREJPROP", "OBEROIRLTY", "PHOENIXLTD", "PRESTIGE",
    "BRIGADE", "SOBHA", "MAHLIFE", "SUNTECK", "KOLTEPATIL",
    "IBREALEST", "ANANTRAJ", "ARVSMART", "LODHA", "SIGNATURE",

    # ── Cement ────────────────────────────────────────────────────────────────
    "AMBUJACEM", "ACC", "SHREECEM", "RAMCOCEM",  # removed duplicate ULTRACEMCO
    "JKLAKSHMI", "HEIDELBERGCE", "BIRLACORP", "DALMIACEM", "JKCEMENT",
    "ORIENTCEM", "INDIACEM", "STARCEMENT",

    # ── Textiles & Apparel ────────────────────────────────────────────────────
    "RAYMOND", "ARVIND", "WELSPUNIND", "TRIDENT", "KPRMILL",
    "PAGEIND", "KITEX", "SIYARAM", "VTL", "NITINSPIN",
    "RUPA", "DOLLAR", "DONEAR", "GOKEX", "FILATEX",

    # ── Capital Goods & Engineering ───────────────────────────────────────────
    "THERMAX", "GRINDWELL", "ELGIEQUIP", "AIAENG", "ISGEC",
    "TRIVENI", "KIRLOSBROS", "BHEL", "SIEMENS", "ABB",
    "CUMMINSIND", "POLYCAB", "ASTRAL", "VOLTAS",  # removed duplicate HAVELLS

    # ── Telecom / Media ───────────────────────────────────────────────────────
    "IDEA", "HFCL", "TEJASNET", "RAILTEL", "STLTECH",
    "ZEEL", "SUNTVNET", "TV18BRDCST", "PVRINOX", "DISHTV",
    "SUNTV", "NETWORK18",

    # ── Logistics & Supply Chain ──────────────────────────────────────────────
    "BLUEDART", "GATI", "VRL", "TCIEXP", "MAHLOG",
    "ALLCARGO", "REDINGTON", "MAHSCOOTER", "SHREYAS", "AEGISLOG",

    # ── Hospitality & Travel ──────────────────────────────────────────────────
    "INDHOTEL", "LEMONTREE", "CHALET", "EIH", "MHRIL",
    "WONDERLA", "TAJGVK", "ORIENTHOTEL",

    # ── Paper, Packaging & Miscellaneous ─────────────────────────────────────
    "CENTURYPLY", "GREENPLY", "TPAPERBRD", "UFLEX", "MANORAMA",
    "NESCO", "TEAMLEASE", "QUESS", "SIS", "AWFIS",

    # ── Additional Midcap / Small Cap across sectors ──────────────────────────
    # Banking / Finance
    "AUBANK", "JANA", "UGROCAP", "PAISALO",          # removed duplicate DCBBANK
    "IIFL", "EDELWEISS", "POONAWALLA", "JMFINANCIL", "SUNDARMFIN",
    # IT / Digital
    "HAPPSTMNDS", "LTIMINDTREE", "HEXAWARE", "NEWGEN",  # removed duplicates MPHASIS, TATAELXSI
    "NUCLEUS", "SAKSOFT", "NIITLTD", "3IINFOTECH", "ECLERX",
    "INFIBEAM", "SUBEX",                             # removed MKVENTURES (invalid), MAHINDRA (ambiguous)
    # Pharma / Diagnostics
    "DIVI", "JUBLPHARMA", "SMSPHARMA", "LINCOLN",   # removed duplicate SEQUENT
    "MARKSANS", "GLENMARK", "WOCKPHARMA",            # removed IPCA (wrong ticker), SMSPHARM (typo)
    # Auto
    "LUMAXTECH", "MAHSEAMLES", "SETCO", "HINDMOTORS",  # removed duplicate SUPRAJIT
    "SUBROS", "RACL", "LUMAX",                       # removed MOTHERSUMI (renamed), STEELCAS (invalid)
    # Specialty Chemicals
    "VINDHYATEL", "CHEMPLAST", "JIOFIN", "CARYSIL",  # removed duplicate TATACHEM
    "MEGHMANI", "TRANSPEK", "PAUSHAKLTD", "EXCEL", "BORAX",
    # Consumer / Retail
    "SHOPERSTOP", "VMART", "ABFRL", "VEDANT",        # removed duplicate NYKAA
    "CAMPUS", "METRO", "BATA", "RELAXO", "NILKAMAL",
    # Infra / Capital Goods
    "CRISIL", "CARBORUNIV", "GRAPHITE", "HLEGLAS", "VSTTILLERS",
    # removed duplicate KALPATPOWR, SCHAEFFLER; invalid USHA, BHARAT, WEIR
    # Healthcare / Diagnostics
    "JUPITERHSP", "SYNGENE",
    # removed DRREDDYS (wrong ticker), duplicate GLENMARK, duplicate TORNTPHARM
    # Real Estate / Housing
    "NXTDIGITAL", "INDIAGRID", "POWERMECH", "GREENPANEL",  # removed duplicate CENTURYPLY
    # PSU / Defence
    "GARDENREACH",
    # removed duplicate COCHINSHIP, invalid BHARAT, MISRDHATU (wrong ticker), MURUDCERA (delisted)
]

#For manual check
#_raw_universe = ["HAL",]


# ── Known invalid / problematic NSE tickers ──────────────────────────────────
# Safety net: if any of these are ever re-added to _raw_universe they will be
# logged as ERROR and excluded from the scan automatically.
_INVALID_SYMBOLS: dict[str, str] = {
    "SANDUMA":        "not a recognised NSE ticker",
    "VIJAYABANK":     "merged into Bank of Baroda — delisted",
    "MAHINDRA":       "ambiguous — correct ticker is M&M (already in universe)",
    "MISRDHATU":      "wrong ticker — correct ticker is MIDHANI (already in universe)",
    "MURUDCERA":      "likely delisted / no liquid data",
    "DRREDDYS":       "wrong ticker — correct ticker is DRREDDY (already in universe)",
    "MOTHERSUMI":     "renamed — correct ticker is MOTHERSON (already in universe)",
    "STEELCAS":       "not a recognised NSE ticker",
    "USHA":           "ambiguous — no unique NSE ticker",
    "WEIR":           "not a recognised NSE ticker",
    "IPCA":           "wrong ticker — correct ticker is IPCALAB (already in universe)",
    "MKVENTURES":     "not a recognised NSE ticker",
    "MSTECHNOLOGIES": "not a recognised NSE ticker",
    "SMSPHARM":       "likely duplicate / typo of SMSPHARMA",
    "BHARAT":         "ambiguous — no unique NSE ticker (BHARATFORG / BHARTIARTL?)",
}


def _build_and_validate_universe(raw: list[str]) -> list[str]:
    import sys
    import os
    sys.path.insert(0, os.path.dirname(__file__))
    from src.logger import get_logger
    log = get_logger("config")

    seen: dict[str, int] = {}
    clean: list[str] = []

    for sym in raw:
        # Duplicate check
        if sym in seen:
            seen[sym] += 1
            log.warning("Duplicate symbol removed: %s (appeared %d times)", sym, seen[sym])
            continue
        seen[sym] = 1

        # Invalid symbol check
        if sym in _INVALID_SYMBOLS:
            log.error(
                "Invalid symbol skipped: %-16s — %s",
                sym, _INVALID_SYMBOLS[sym],
            )
            continue

        clean.append(sym)

    log.info(
        "Universe loaded — %d valid symbols (%d duplicates removed, %d invalid skipped)",
        len(clean),
        sum(1 for v in seen.values() if v > 1),
        sum(1 for s in raw if s in _INVALID_SYMBOLS),
    )
    return clean


# Deduplicate, validate, and log any problems
STOCK_UNIVERSE = _build_and_validate_universe(_raw_universe)

MARKET_REGIME_SYMBOL = "^NSEI"   # Nifty 50 index

STRATEGY_PARAMS = {
    "rsi_min": 50,
    "rsi_max": 72,
    "min_rel_volume": 1.5,        # minimum 1.5x 20-day avg volume
    "adx_min": 20,                # trend strength threshold
    "target_pct": 0.06,            # 6% target  (was 11% — too aggressive)
    "stop_loss_pct": 0.05,        # 5% max stop loss
    "atr_sl_multiplier": 2.0,     # stop loss = 2x ATR below entry
    "min_score": 45,              # minimum composite score (0–100)
    "min_rr_ratio": 1.5,          # minimum risk:reward ratio
    "pct_from_52w_high": -15.0,   # within 15% of 52W high (was -5%, too strict)
    "hold_days": 44,              # ~2 months holding period (44 trading days)
    "min_history_days": 60,       # minimum candles required for analysis
    "min_signal_count": 7,        # require at least 7/20 signals to fire (was 9)
    "require_bull_market": True,  # skip all trades when Nifty < 200-MA
}
