import numpy as np
import pandas as pd


def rsi(series, period=14):
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/period, min_periods=period, adjust=False).mean()

    rs = avg_gain / avg_loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def macd_bias(series):
    ema12 = series.ewm(span=12, adjust=False).mean()
    ema26 = series.ewm(span=26, adjust=False).mean()
    macd_line = ema12 - ema26
    signal = macd_line.ewm(span=9, adjust=False).mean()

    if macd_line.iloc[-1] > signal.iloc[-1]:
        return "MACD: sesgo alcista"
    elif macd_line.iloc[-1] < signal.iloc[-1]:
        return "MACD: sesgo bajista"
    return "MACD: neutro"


def sma(series, window):
    return series.rolling(window).mean()


def volume_analysis(volume):
    sma20 = volume.rolling(20).mean().iloc[-1]
    sma5 = volume.rolling(5).mean().iloc[-1]
    last = volume.iloc[-1]

    if last > sma20 * 1.3:
        level = "alto"
    elif last < sma20 * 0.7:
        level = "bajo"
    else:
        level = "normal"

    trend = "en alza" if sma5 > sma20 else "en baja"
    return level, trend
