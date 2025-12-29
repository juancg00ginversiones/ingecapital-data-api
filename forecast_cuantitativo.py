# ============================================================
# FORECAST TRADING CUANTITATIVO – INGECAPITAL PRO (V2)
# - Incluye histórico de spot + fan chart por día + tablas completas
# ============================================================

import time
import datetime as dt

# ============================================================
# CONFIG
# ============================================================

CACHE_TTL = 60 * 30          # 30 minutos
N_SIM = 2000                # simulaciones (subir/bajar según performance)
TRADING_DAYS = 252

# Histórico para “contexto visual” (días calendario hacia atrás)
HISTORY_CAL_DAYS = 180      # ~6 meses (ajustable)
# Cuánto histórico mostramos en el gráfico (puntos)
HISTORY_MAX_POINTS = 90     # limitar para que sea liviano

# Horizontes
SHORT_HORIZONS = [2, 5]         # corto plazo
LONG_HORIZONS = [5, 20, 60]     # largo plazo

UNIVERSE = {
    "indices": ["SPY", "QQQ"],
    "magnificas": ["AAPL", "MSFT", "NVDA", "AMZN", "META"],
    "crypto": ["BTC-USD", "ETH-USD"]
}

_CACHE = {"ts": 0, "data": None}

# ============================================================
# LAZY IMPORTS (seguro para Render)
# ============================================================

def _imports():
    import math
    import numpy as np
    import yfinance as yf
    return math, np, yf

# ============================================================
# DATA HELPERS
# ============================================================

def _download_prices(ticker: str):
    """
    Descarga precios diarios. Devuelve una Serie de precios (Close / Adj Close).
    """
    _, _, yf = _imports()

    end = dt.date.today()
    start = end - dt.timedelta(days=max(365 * 3, HISTORY_CAL_DAYS + 30))

    df = yf.download(
        ticker,
        start=start,
        end=end,
        progress=False,
        threads=False
    )

    if df is None or df.empty:
        raise ValueError("No hay datos históricos")

    # yfinance: Adj Close no siempre existe
    if "Adj Close" in df.columns:
        s = df["Adj Close"]
    elif "Close" in df.columns:
        s = df["Close"]
    else:
        raise ValueError("No se encontró columna de precios válida (Close/Adj Close)")

    s = s.dropna()
    if s.empty:
        raise ValueError("Serie de precios vacía")

    return s

def _log_returns(price_series):
    import numpy as np
    return np.log(price_series / price_series.shift(1)).dropna()

def _trim_history(series, max_points: int):
    if len(series) <= max_points:
        return series
    return series.iloc[-max_points:]

# ============================================================
# MODEL HELPERS
# ============================================================

def _simulate_gbm_paths(spot, mu, sigma, days, n_sim):
    """
    Devuelve paths: shape (n_sim, days+1) incluyendo spot al inicio.
    """
    math, np, _ = _imports()
    dt_step = 1 / TRADING_DAYS

    # shocks para days pasos
    shocks = np.random.normal(
        (mu - 0.5 * sigma**2) * dt_step,
        sigma * math.sqrt(dt_step),
        (n_sim, days)
    )

    # acumulado y prepend spot
    growth = np.exp(np.cumsum(shocks, axis=1))
    # insertar 1.0 como t=0
    growth = np.concatenate([np.ones((n_sim, 1)), growth], axis=1)
    return spot * growth

def _fan_series(paths):
    """
    Calcula percentiles para cada paso del tiempo.
    paths: (n_sim, T) donde T = days+1
    Devuelve dict con arrays p5/p50/p95 (listas float).
    """
    _, np, _ = _imports()
    p5 = np.percentile(paths, 5, axis=0)
    p50 = np.percentile(paths, 50, axis=0)
    p95 = np.percentile(paths, 95, axis=0)
    return {
        "p5": [float(x) for x in p5],
        "p50": [float(x) for x in p50],
        "p95": [float(x) for x in p95],
    }

def _probs_at_horizon(paths, spot):
    """
    Probabilidades al final del horizonte (último punto del path).
    """
    _, np, _ = _imports()
    end_vals = paths[:, -1]
    p_up = float((end_vals > spot).mean())
    p_up_5 = float((end_vals > spot * 1.05).mean())
    p_down_5 = float((end_vals < spot * 0.95).mean())
    return {
        "P(subir)": round(p_up, 4),
        "P(+5%)": round(p_up_5, 4),
        "P(-5%)": round(p_down_5, 4)
    }

def _risk_label(mu, sigma):
    """
    Etiqueta simple de riesgo basada en volatilidad anualizada.
    """
    # sigma ya está anualizada
    if sigma < 0.18:
        return {"level": "BAJO", "text": "Volatilidad histórica baja/moderada."}
    if sigma < 0.30:
        return {"level": "MEDIO", "text": "Volatilidad histórica media."}
    return {"level": "ALTO", "text": "Volatilidad histórica elevada."}

# ============================================================
# FORECAST POR ACTIVO (API CONTRACT)
# ============================================================

def _build_asset_payload(ticker: str):
    prices = _download_prices(ticker)

    # histórico visible (para el gráfico “como venía”)
    hist = prices.iloc[-HISTORY_CAL_DAYS:]  # recorte por días de calendario aproximado
    hist = _trim_history(hist, HISTORY_MAX_POINTS)

    spot = float(prices.iloc[-1])

    rets = _log_returns(prices)
    mu = float(rets.mean() * TRADING_DAYS)
    sigma = float(rets.std() * (TRADING_DAYS ** 0.5))

    risk = _risk_label(mu, sigma)

    # ---------- SHORT ----------
    short = {"horizons": {}, "table": {}}
    for d in SHORT_HORIZONS:
        paths = _simulate_gbm_paths(spot, mu, sigma, d, N_SIM)
        short["horizons"][f"{d}d"] = {
            "days": list(range(0, d + 1)),
            "fan": _fan_series(paths)
        }
        short["table"][f"{d}d"] = _probs_at_horizon(paths, spot)

    # ---------- LONG ----------
    long = {"horizons": {}, "table": {}}
    for d in LONG_HORIZONS:
        paths = _simulate_gbm_paths(spot, mu, sigma, d, N_SIM)
        long["horizons"][f"{d}d"] = {
            "days": list(range(0, d + 1)),
            "fan": _fan_series(paths)
        }
        long["table"][f"{d}d"] = _probs_at_horizon(paths, spot)

    # Semáforo simple (por prob. 5d si existe, si no 2d)
    ref_key = "5d" if "5d" in short["table"] else "2d"
    p_up_ref = short["table"][ref_key]["P(subir)"]
    if p_up_ref > 0.55:
        semaphore = {"status": "FAVORABLE", "text": "Sesgo probabilístico alcista en el corto plazo."}
    elif p_up_ref < 0.45:
        semaphore = {"status": "DESFAVORABLE", "text": "Sesgo probabilístico bajista en el corto plazo."}
    else:
        semaphore = {"status": "NEUTRAL", "text": "Balance de probabilidades relativamente equilibrado."}

    return {
        "ticker": ticker,
        "spot": spot,
        "risk": risk,
        "updated_at": dt.datetime.utcnow().isoformat() + "Z",

        # Histórico para “cómo venía”
        "history": {
            "dates": [d.strftime("%Y-%m-%d") for d in hist.index],
            "prices": [float(x) for x in hist.values]
        },

        # Proyecciones separadas
        "short_term": short,
        "long_term": long,

        # señales
        "semaphore": semaphore
    }

# ============================================================
# API PUBLICA (TODOS LOS ACTIVOS)
# ============================================================

def get_forecast_cuantitativo_for_api():
    now = time.time()
    if _CACHE["data"] is not None and (now - _CACHE["ts"]) < CACHE_TTL:
        return _CACHE["data"]

    data = {}
    for group, tickers in UNIVERSE.items():
        for t in tickers:
            try:
                data[t] = _build_asset_payload(t)
            except Exception as e:
                data[t] = {"ticker": t, "error": str(e)}

    universe_flat = []
    for tickers in UNIVERSE.values():
        universe_flat.extend(tickers)

    output = {
        "updated_at": dt.datetime.utcnow().isoformat() + "Z",
        "universe": UNIVERSE,
        "universe_flat": sorted(universe_flat),
        "data": data
    }

    _CACHE["data"] = output
    _CACHE["ts"] = now
    return output

