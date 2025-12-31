import numpy as np
import pandas as pd
from datetime import datetime, time
from typing import Optional


# ============================================================
# RSI
# ============================================================
def rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()

    rs = avg_gain / avg_loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


# ============================================================
# MACD (SOLO SESGO)
# ============================================================
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


# ============================================================
# SMA
# ============================================================
def sma(series: pd.Series, window: int) -> pd.Series:
    return series.rolling(window).mean()


# ============================================================
# SESSION PROGRESS (RUEDA ABIERTA)
# ============================================================
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

    total_seconds = (
        datetime.combine(now.date(), market_close) -
        datetime.combine(now.date(), market_open)
    ).total_seconds()

    elapsed_seconds = (
        datetime.combine(now.date(), now.time()) -
        datetime.combine(now.date(), market_open)
    ).total_seconds()

    return max(0.0, min(1.0, elapsed_seconds / total_seconds))


# ============================================================
# ANALISIS DE VOLUMEN (CORREGIDO)
# ============================================================
def analyze_volume(
    volume: pd.Series,
    session_type: str,
    session_progress: Optional[float]
) -> dict:
    """
    Analiza volumen considerando:
    - cierre de rueda
    - rueda abierta (volumen esperado)
    """

    if volume is None or len(volume) < 25:
        return {
            "level": None,
            "trend": None,
            "session": session_type,
            "diagnostic": "Volumen: datos insuficientes"
        }

    # Series de medias
    sma20_series = volume.rolling(20).mean()
    sma5_series = volume.rolling(5).mean()

    # Últimos valores (ESCALARES)
    sma20_last = sma20_series.iloc[-1]
    sma5_last = sma5_series.iloc[-1]
    vol_last = volume.iloc[-1]

    # Protección contra NaN
    if pd.isna(sma20_last) or pd.isna(sma5_last):
        return {
            "level": None,
            "trend": None,
            "session": session_type,
            "diagnostic": "Volumen: datos insuficientes"
        }

    # Tendencia (YA NO ES SERIES vs SERIES)
    trend = "en alza" if sma5_last > sma20_last else "en baja"

    # ========================================================
    # CIERRE DE RUEDA
    # ========================================================
    if session_type == "close":
        if vol_last > sma20_last * 1.3:
            level = "alto"
        elif vol_last < sma20_last * 0.7:
            level = "bajo"
        else:
            level = "normal"

        diagnostic = f"Volumen {level} {trend} en el día"

    # ========================================================
    # RUEDA ABIERTA
    # ========================================================
    else:
        if session_progress is None:
            session_progress = 0.0

        expected_volume = sma20_last * session_progress

        if expected_volume <= 0:
            level = "normal"
        else:
            ratio = vol_last / expected_volume
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
