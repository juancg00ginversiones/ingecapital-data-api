import numpy as np
import pandas as pd


# ================= RSI =================
def rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/period, min_periods=period, adjust=False).mean()

    rs = avg_gain / avg_loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


# ================= MACD (SES GO) =================
def macd_bias(series: pd.Series) -> str:
    ema12 = series.ewm(span=12, adjust=False).mean()
    ema26 = series.ewm(span=26, adjust=False).mean()

    macd = ema12 - ema26
    signal = macd.ewm(span=9, adjust=False).mean()

    if macd.iloc[-1] > signal.iloc[-1]:
        return "MACD: sesgo alcista"
    elif macd.iloc[-1] < signal.iloc[-1]:
        return "MACD: sesgo bajista"
    return "MACD: neutro"


# ================= SMA =================
def sma(series: pd.Series, window: int) -> pd.Series:
    return series.rolling(window).mean()


# ================= VOLUMEN SIMPLE (ROBUSTO) =================
def analyze_volume(volume: pd.Series) -> dict:
    """
    Volumen simple vs promedio 20 ruedas.
    SIN intradía, SIN SMA5.
    """

    if volume is None or len(volume) < 20:
        return {
            "level": None,
            "diagnostic": "Volumen: datos insuficientes"
        }

    vol_last = volume.iloc[-1]
    vol_avg = volume.rolling(20).mean().iloc[-1]

    if pd.isna(vol_last) or pd.isna(vol_avg):
        return {
            "level": None,
            "diagnostic": "Volumen: datos insuficientes"
        }

    if vol_last > vol_avg * 1.3:
        level = "alto"
    elif vol_last < vol_avg * 0.7:
        level = "bajo"
    else:
        level = "normal"

    return {
        "level": level,
        "diagnostic": f"Volumen {level} vs promedio"
    }
