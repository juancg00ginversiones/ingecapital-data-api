import numpy as np
import pandas as pd
import yfinance as yf


# ============================================================
# RSI (ESTÁNDAR, ESTABLE)
# ============================================================
def rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()

    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.ewm(alpha=1 / period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, adjust=False).mean()

    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))

    return rsi


# ============================================================
# MACD (SES GO)
# ============================================================
def macd_bias(series: pd.Series) -> str:
    ema12 = series.ewm(span=12, adjust=False).mean()
    ema26 = series.ewm(span=26, adjust=False).mean()

    macd = ema12 - ema26
    signal = macd.ewm(span=9, adjust=False).mean()

    macd_last = macd.iloc[-1]
    signal_last = signal.iloc[-1]

    if macd_last > signal_last:
        return "MACD: sesgo alcista"
    elif macd_last < signal_last:
        return "MACD: sesgo bajista"
    return "MACD: neutro"


# ============================================================
# SMA
# ============================================================
def sma(series: pd.Series, window: int) -> pd.Series:
    return series.rolling(window).mean()


# ============================================================
# ANALYZE TICKER (BASELINE ESTABLE)
# ============================================================
def analyze_ticker(ticker: str) -> dict:
    df = yf.download(
        ticker,
        period="1y",
        interval="1d",
        progress=False
    )

    if df.empty:
        raise ValueError("Sin datos de Yahoo Finance")

    close = df["Close"].dropna()

    if len(close) < 2:
        raise ValueError("Datos insuficientes")

    # Última vela disponible (aunque el mercado esté cerrado)
    last = float(close.iloc[-1])
    prev = float(close.iloc[-2])

    daily_change_pct = (last / prev - 1) * 100

    # ------------------------
    # Indicadores (tolerantes)
    # ------------------------
    try:
        rsi_val = float(rsi(close).iloc[-1])
    except Exception:
        rsi_val = None

    try:
        macd_diag = macd_bias(close)
    except Exception:
        macd_diag = "MACD: na"

    try:
        sma21_val = sma(close, 21).iloc[-1]
        sma21_status = "above" if last > sma21_val else "below"
    except Exception:
        sma21_status = "na"

    try:
        sma200_val = sma(close, 200).iloc[-1]
        sma200_status = "above" if last > sma200_val else "below"
    except Exception:
        sma200_status = "na"

    return {
        "ticker": ticker,
        "price": round(last, 2),
        "daily_change_pct": round(daily_change_pct, 2),
        "indicators": {
            "rsi14": {
                "value": None if rsi_val is None else round(rsi_val, 2)
            },
            "macd": {
                "diagnostic": macd_diag
            },
            "sma21": {
                "status": sma21_status
            },
            "sma200": {
                "status": sma200_status
            }
        }
    }
