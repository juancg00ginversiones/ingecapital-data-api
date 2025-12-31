import numpy as np
import pandas as pd


# ================= RSI =================
def rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()

    rs = avg_gain / avg_loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


# ================= MACD (SES GO) =================
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


# ================= SMA =================
def sma(series: pd.Series, window: int) -> pd.Series:
    return series.rolling(window).mean()
