import numpy as np
import pandas as pd
import yfinance as yf


# ============================================================
# RSI (14) – Wilder / TradingView compatible
# ============================================================
def rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()

    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)

    avg_gain = gain.ewm(
        alpha=1 / period,
        min_periods=period,
        adjust=False
    ).mean()

    avg_loss = loss.ewm(
        alpha=1 / period,
        min_periods=period,
        adjust=False
    ).mean()

    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))

    return rsi


# ============================================================
# MACD – Sesgo (no valores numéricos)
# ============================================================
def macd_bias(series: pd.Series) -> str:
    ema12 = series.ewm(span=12, adjust=False).mean()
    ema26 = series.ewm(span=26, adjust=False).mean()

    macd = ema12 - ema26
    signal = macd.ewm(span=9, adjust=False).mean()

    macd_last = float(macd.iloc[-1])
    signal_last = float(signal.iloc[-1])

    if macd_last > signal_last:
        return "MACD: sesgo alcista"
    elif macd_last < signal_last:
        return "MACD: sesgo bajista"
    else:
        return "MACD: neutro"


# ============================================================
# SMA
# ============================================================
def sma(series: pd.Series, window: int) -> pd.Series:
    return series.rolling(window).mean()


# ============================================================
# Análisis completo por ticker (para Market Screener / Heatmap)
# ============================================================
def analyze_ticker(ticker: str) -> dict:
    df = yf.download(
        ticker,
        period="6mo",
        interval="1d",
        progress=False,
        auto_adjust=False
    )

    if df.empty or df["Close"].dropna().shape[0] < 20:
        raise ValueError("Histórico insuficiente")

    close = df["Close"].dropna()

    # Última vela cerrada (clave para mercado cerrado)
    last = float(close.iloc[-1])
    prev = float(close.iloc[-2])

    daily_change_pct = (last / prev - 1) * 100

    # RSI
    rsi_series = rsi(close, 14)
    rsi_val = float(rsi_series.iloc[-1])

    # MACD
    macd_diag = macd_bias(close)

    # SMAs
    sma21 = sma(close, 21)
    sma200 = sma(close, 200)

    sma21_status = (
        "above" if last > float(sma21.iloc[-1])
        else "below"
        if not pd.isna(sma21.iloc[-1])
        else "na"
    )

    sma200_status = (
        "above" if last > float(sma200.iloc[-1])
        else "below"
        if not pd.isna(sma200.iloc[-1])
        else "na"
    )

    return {
        "ticker": ticker,
        "price": round(last, 2),
        "daily_change_pct": round(daily_change_pct, 2),
        "indicators": {
            "rsi14": {
                "value": round(rsi_val, 2)
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
