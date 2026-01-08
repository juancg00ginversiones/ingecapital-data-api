import numpy as np
import pandas as pd
import yfinance as yf
import threading
import time

# ============================================================
# CACHE / CONCURRENCIA (infraestructura)
# ============================================================
ANALYZE_TTL = 300  # 5 minutos

_ANALYZE_CACHE = {}        # ticker -> {"ts": float, "data": dict}
_ANALYZE_LOCKS = {}        # ticker -> Lock
_ANALYZE_EVENTS = {}       # ticker -> Event
_ANALYZE_INFLIGHT = set()
_ANALYZE_GUARD = threading.Lock()


def _get_lock_and_event(ticker: str):
    with _ANALYZE_GUARD:
        if ticker not in _ANALYZE_LOCKS:
            _ANALYZE_LOCKS[ticker] = threading.Lock()
        if ticker not in _ANALYZE_EVENTS:
            _ANALYZE_EVENTS[ticker] = threading.Event()
            _ANALYZE_EVENTS[ticker].set()
        return _ANALYZE_LOCKS[ticker], _ANALYZE_EVENTS[ticker]


# ============================================================
# INDICATORS (NO TOCAR)
# ============================================================
def rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)

    avg_gain = gain.ewm(
        alpha=1/period,
        min_periods=period,
        adjust=False
    ).mean()

    avg_loss = loss.ewm(
        alpha=1/period,
        min_periods=period,
        adjust=False
    ).mean()

    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))



def macd_bias(series: pd.Series) -> str:
    series = series.dropna()
    if len(series) < 35:
        return "MACD: insuf. datos"

    ema12 = series.ewm(span=12, adjust=False).mean()
    ema26 = series.ewm(span=26, adjust=False).mean()
    macd = ema12 - ema26
    signal = macd.ewm(span=9, adjust=False).mean()

    if pd.isna(macd.iloc[-1]) or pd.isna(signal.iloc[-1]):
        return "MACD: na"

    return "MACD: sesgo alcista" if macd.iloc[-1] > signal.iloc[-1] else "MACD: sesgo bajista"


def sma(series: pd.Series, window: int) -> pd.Series:
    return series.rolling(window=window).mean()


# ============================================================
# API / ENGINE (PROTEGIDO)
# ============================================================
def analyze_ticker(ticker: str) -> dict:
    ticker = ticker.upper()
    now = time.time()

    # ---------- Cache fresh ----------
    entry = _ANALYZE_CACHE.get(ticker)
    if entry is not None and (now - entry["ts"]) <= ANALYZE_TTL:
        return entry["data"]

    lock, ev = _get_lock_and_event(ticker)

    # ---------- Single-flight ----------
    with lock:
        entry2 = _ANALYZE_CACHE.get(ticker)
        if entry2 is not None and (time.time() - entry2["ts"]) <= ANALYZE_TTL:
            return entry2["data"]

        if ticker in _ANALYZE_INFLIGHT:
            follower_event = ev
        else:
            _ANALYZE_INFLIGHT.add(ticker)
            ev.clear()
            follower_event = None

    if follower_event is not None:
        follower_event.wait(timeout=30)
        entry3 = _ANALYZE_CACHE.get(ticker)
        if entry3 is not None:
            return entry3["data"]
        raise RuntimeError("Ticker sin datos (concurrencia)")

    # ---------- Líder (lógica ORIGINAL intacta) ----------
    try:
        df = yf.download(
            ticker,
            period="18mo",
            interval="1d",
            progress=False,
            auto_adjust=True
        )

        if df.empty:
            raise ValueError("Sin datos")

        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        close = df["Close"].dropna()
        if len(close) < 2:
            raise ValueError("Datos insuficientes")

        last = float(close.iloc[-1])
        prev = float(close.iloc[-2])
        daily_change_pct = (last / prev - 1) * 100

        rsi_series = rsi(close)
        rsi_val = rsi_series.iloc[-1]

        macd_diag = macd_bias(close)

        def get_sma_status(val_close, series, window):
            line = series.rolling(window=window).mean()
            last_sma = line.iloc[-1]
            if pd.isna(last_sma):
                return "na"
            return "above" if val_close > last_sma else "below"

        result = {
            "ticker": ticker,
            "price": round(last, 2),
            "daily_change_pct": round(daily_change_pct, 2),
            "indicators": {
                "rsi14": {"value": round(float(rsi_val), 2) if not pd.isna(rsi_val) else None},
                "macd": {"diagnostic": macd_diag},
                "sma21": {"status": get_sma_status(last, close, 21)},
                "sma200": {"status": get_sma_status(last, close, 200)}
            }
        }

        # Guardar cache SOLO si es válido
        _ANALYZE_CACHE[ticker] = {"ts": time.time(), "data": result}
        return result

    except Exception:
        entry_stale = _ANALYZE_CACHE.get(ticker)
        if entry_stale is not None:
            return entry_stale["data"]
        raise

    finally:
        with lock:
            if ticker in _ANALYZE_INFLIGHT:
                _ANALYZE_INFLIGHT.remove(ticker)
            ev.set()

