import numpy as np
import pandas as pd
from datetime import datetime, time


# ============================================================
# RSI
# ============================================================
def rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/period, min_periods=period, adjust=False).mean()

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
# VOLUMEN INTELIGENTE (OPEN / CLOSE)
# ============================================================
def analyze_volume(
    volume: pd.Series,
    session_type: str = "close",
    session_progress: float | None = None
) -> dict:
    """
    Analiza volumen de forma contextual.

    session_type:
      - "open"  → rueda abierta
      - "close" → cierre diario

    session_progress:
      - porcentaje de rueda transcurrida (0.0 – 1.0)
      - solo requerido si session_type == "open"
    """

    if len(volume) < 25:
        return {
            "level": None,
            "trend": None,
            "session": session_type,
            "diagnostic": "Volumen: datos insuficientes"
        }

    vol_last = volume.iloc[-1]
    vol_sma20 = volume.rolling(20).mean().iloc[-1]
    vol_sma5 = volume.rolling(5).mean().iloc[-1]

    # --------------------------------------------------------
    # Tendencia (válida en ambos casos)
    # --------------------------------------------------------
    trend = "en alza" if vol_sma5 > vol_sma20 else "en baja"

    # --------------------------------------------------------
    # CIERRE DE RUEDA
    # --------------------------------------------------------
    if session_type == "close":
        if vol_last > vol_sma20 * 1.3:
            level = "alto"
        elif vol_last < vol_sma20 * 0.7:
            level = "bajo"
        else:
            level = "normal"

        diagnostic = f"Volumen {level} {trend} en el día"

    # --------------------------------------------------------
    # RUEDA ABIERTA
    # --------------------------------------------------------
    elif session_type == "open":
        if session_progress is None:
            raise ValueError("session_progress es requerido cuando session_type='open'")

        expected_volume = vol_sma20 * session_progress

        ratio = vol_last / expected_volume if expected_volume > 0 else 0

        if ratio > 1.2:
            level = "alto"
        elif ratio < 0.8:
            level = "bajo"
        else:
            level = "normal"

        diagnostic = f"Volumen {level} {trend} para esta altura de la rueda"

    else:
        raise ValueError("session_type debe ser 'open' o 'close'")

    return {
        "level": level,
        "trend": trend,
        "session": session_type,
        "diagnostic": diagnostic
    }


# ============================================================
# HELPER: SESSION PROGRESS (AUTOMÁTICO)
# ============================================================
def get_session_progress(
    now: datetime | None = None,
    market_open: time = time(11, 0),
    market_close: time = time(17, 0)
) -> float:
    """
    Devuelve porcentaje de rueda transcurrida (0–1).
    Horarios default: mercado argentino (aprox).
    """

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
