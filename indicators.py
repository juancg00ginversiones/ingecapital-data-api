import numpy as np
import pandas as pd
from datetime import datetime, time
from typing import Optional


def rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/period, min_periods=period, adjust=False).mean()

    rs = avg_gain / avg_loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def macd_bias(series: pd.Series) -> str:
    ema12 = series.ewm(span=12, adjust=False).mean()
    ema26 = series.ewm(span=26, adjust=False).mean()

    macd_line = ema12 - ema26
    signal = macd_line.ewm(span=9, adjust=False).mean()

    if macd_line.iloc[-1] > signal.iloc[-1]:
        return "MACD: sesgo alcista"
    elif macd_line.iloc[-1] < signal.iloc[-1]:
        return "MACD: sesgo bajista"
    return "MACD: neutro"


def sma(series: pd.Series, window: int) -> pd.Series:
    return series.rolling(window).mean()


def get_session_progress(
    now: Optional[datetime] = None,
    market_open: time = time(11, 0),
    market_close: time = time(17, 0)
) -> float:
    if now is None:
        now = datetime.now()

    if now.time() <= market_open:
        return 0.0
    if now.time() >= market_close:
        return 1.0

    total = (
        datetime.combine(now.date(), market_close) -
        datetime.combine(now.date(), market_open)
    ).total_seconds()

    elapsed = (
        datetime.combine(now.date(), now.time()) -
        datetime.combine(now.date(), market_open)
    ).total_seconds()

    return max(0.0, min(1.0, elapsed / total))


def analyze_volume(
    volume: pd.Series,
    session_type: str,
    session_progress: Optional[float]
) -> dict:

    if len(volume) < 25:
        return {
            "level": None,
            "trend": None,
            "session": session_type,
            "diagnostic": "Volumen insuficiente"
        }

    last = volume.iloc[-1]
    sma20 = volume.rolling(20).mean().iloc[-1]
    sma5 = volume.rolling(5).mean().iloc[-1]

    trend = "en alza" if sma5 > sma20 else "en baja"

    if session_type == "close":
        if last > sma20 * 1.3:
            level = "alto"
        elif last < sma20 * 0.7:
            level = "bajo"
        else:
            level = "normal"
        diagnostic = f"Volumen {level} {trend} en el día"

    else:
        expected = sma20 * (session_progress or 0)
        ratio = last / expected if expected > 0 else 0

        if ratio > 1.2:
            level = "alto"
        elif ratio < 0.8:
            level = "bajo"
        else:
            level = "normal"

        diagnostic = f"Volumen {level} {trend} para esta altura de la rueda"

    return {
        "level": level,
        "trend": trend,
        "session": session_type,
        "diagnostic": diagnostic
    }
