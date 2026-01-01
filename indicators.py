import numpy as np
import pandas as pd
import yfinance as yf


# ============================================================
# RSI (WILDER CLÁSICO – CONSISTENTE CON TRADINGVIEW)
# ============================================================
def rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()

    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    rsi_series = pd.Series(index=series.index, dtype=float)

    # Primer promedio (SMA)
    avg_gain = gain.rolling(period, min_periods=period).mean()
    avg_loss = loss.rolling(period, min_periods=period).mean()

    # Valor inicial
    for i in range(len(series)):
        if i < period:
            rsi_series.iloc[i] = np.nan
        elif i == period:
            rs = avg_gain.iloc[i] / avg_loss.iloc[i] if avg_loss.iloc[i] != 0 else np.nan
            rsi_series.iloc[i] = 100 - (100 / (1 + rs))
        else:
            avg_gain.iloc[i] = (avg_gain.iloc[i - 1] * (period - 1) + gain.iloc[i]) / period
            avg_loss.iloc[i] = (avg_loss.iloc[i - 1] * (period - 1) + loss.iloc[i]) / period
            rs = avg_gain.iloc[i] / avg_loss.iloc[i] if avg_loss.iloc[i] != 0 else np.nan
            rsi_series.iloc[i] = 100 - (100 / (1 + rs))

    return rsi_series


# ============================================================
# MACD – SOLO SESGO (ALCISTA / BAJISTA)
# ============================================================

def macd_bias(series: pd.Series) -> str:
    ema12 = series.ewm(span=12, adjust=False).mean()
    ema26 = series.ewm(span=26, adjust=False).mean()

    macd = ema12 - ema26
    signal = macd.ewm(span=9, adjust=False).mean()

    macd_last = macd.iloc[-1].item()
    signal_last = signal.iloc[-1].item()

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
# ANALYZE TICKER (USADO POR MARKET SCREENER)
# ============================================================

def analyze_ticker(ticker: str) -> dict:
    """
    Devuelve:
    - precio
    - variación diaria %
    - RSI(14)
    - sesgo MACD
    - SMA21 / SMA200 (above / below)
    """

    df = yf.download(
        ticker,
        period="1y",
        interval="1d",
        progress=False,
        auto_adjust=False   # 👈 CLAVE PARA RSI CORRECTO
    )

    if df.empty or len(df) < 50:
        raise ValueError("Datos insuficientes")

    close = df["Close"]

    last = float(close.iloc[-1].item())
    prev = float(close.iloc[-2].item())
    daily_change_pct = round((last / prev - 1) * 100, 2)

    # ================= INDICADORES =================

    rsi_val = float(rsi(close).iloc[-1].item())
    sma21 = float(sma(close, 21).iloc[-1].item())
    sma200 = float(sma(close, 200).iloc[-1].item())

    macd_diag = macd_bias(close)

    return {
        "ticker": ticker,
        "price": round(last, 2),
        "daily_change_pct": daily_change_pct,
        "indicators": {
            "rsi14": {
                "value": round(rsi_val, 2)
            },
            "macd": {
                "diagnostic": macd_diag
            },
            "sma21": {
                "status": "above" if last > sma21 else "below"
            },
            "sma200": {
                "status": "above" if last > sma200 else "below"
            }
        }
    }

