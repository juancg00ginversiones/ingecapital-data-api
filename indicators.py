def analyze_ticker(ticker: str) -> dict:
    df = yf.download(
        ticker,
        period="6mo",
        interval="1d",
        progress=False,
        auto_adjust=False
    )

    if df.empty or df["Close"].dropna().shape[0] < 2:
        raise ValueError("Sin datos de precio")

    close = df["Close"].dropna()

    last = float(close.iloc[-1])
    prev = float(close.iloc[-2])
    daily_change_pct = (last / prev - 1) * 100

    # RSI
    rsi_val = None
    try:
        rsi_series = rsi(close, 14)
        if not pd.isna(rsi_series.iloc[-1]):
            rsi_val = round(float(rsi_series.iloc[-1]), 2)
    except:
        pass

    # MACD
    try:
        macd_diag = macd_bias(close)
    except:
        macd_diag = "MACD: na"

    # SMA21
    try:
        sma21_val = sma(close, 21).iloc[-1]
        sma21_status = "above" if last > float(sma21_val) else "below"
    except:
        sma21_status = "na"

    # SMA200
    try:
        sma200_val = sma(close, 200).iloc[-1]
        sma200_status = "above" if last > float(sma200_val) else "below"
    except:
        sma200_status = "na"

    return {
        "ticker": ticker,
        "price": round(last, 2),
        "daily_change_pct": round(daily_change_pct, 2),
        "indicators": {
            "rsi14": {"value": rsi_val},
            "macd": {"diagnostic": macd_diag},
            "sma21": {"status": sma21_status},
            "sma200": {"status": sma200_status}
        }
    }
