# ============================================================
# FORECAST TRADING CUANTITATIVO – INGECAPITAL PRO (V3 FINAL)
# - Histórico SPOT último mes + forecast corto/largo + fan chart + tablas
# - Fix robusto para yfinance (Series vs DataFrame / MultiIndex)
# ============================================================

import time
import datetime as dt

# ============================================================
# CONFIG
# ============================================================

CACHE_TTL = 60 * 30          # 30 minutos
N_SIM = 2000                # simulaciones (ajustar si querés más velocidad)
TRADING_DAYS = 252

# Histórico a mostrar (último mes aprox: 21 ruedas)
MONTH_POINTS = 21

# Horizontes
SHORT_HORIZONS = [2, 5]          # corto plazo
LONG_HORIZONS = [5, 20, 60]      # largo plazo

UNIVERSE = {
    "indices": ["SPY", "QQQ"],
    "magnificas": ["AAPL", "MSFT", "NVDA", "AMZN", "META"],
    "crypto": ["BTC-USD", "ETH-USD"]
}

_CACHE = {"ts": 0, "data": None}

# ============================================================
# LAZY IMPORTS
# ============================================================

def _imports():
    import math
    import numpy as np
    import pandas as pd
    import yfinance as yf
    return math, np, pd, yf

# ============================================================
# HELPERS
# ============================================================

def _ensure_series_1d(x):
    """
    yfinance a veces devuelve DataFrame de 1 columna.
    Esto lo convierte a Serie 1D siempre.
    """
    _, _, pd, _ = _imports()

    if isinstance(x, pd.DataFrame):
        if x.shape[1] == 1:
            return x.iloc[:, 0]
        # Si viniera con MultiIndex raro, intentamos aplastar:
        return x.squeeze(axis=1)
    return x

def _download_prices(ticker: str):
    """
    Descarga precios (Serie 1D), robusto ante MultiIndex/DF 1-col.
    """
    _, _, pd, yf = _imports()

    end = dt.date.today()
    start = end - dt.timedelta(days=365 * 3)

    df = yf.download(
        ticker,
        start=start,
        end=end,
        progress=False,
        threads=False
    )

    if df is None or df.empty:
        raise ValueError("No hay datos históricos")

    # Close / Adj Close robusto
    if "Adj Close" in df.columns:
        s = df["Adj Close"]
    elif "Close" in df.columns:
        s = df["Close"]
    else:
        raise ValueError("No se encontró columna Close/Adj Close")

    s = _ensure_series_1d(s)
    s = s.dropna()

    if not hasattr(s, "iloc") or s.empty:
        raise ValueError("Serie de precios vacía")

    # Asegurar index datetime
    if not isinstance(s.index, pd.DatetimeIndex):
        s.index = pd.to_datetime(s.index)

    return s

def _log_returns(price_series):
    _, np, _, _ = _imports()
    r = np.log(price_series / price_series.shift(1)).dropna()
    return r

# ============================================================
# SIMULACIÓN + FAN CHART
# ============================================================

def _simulate_gbm_paths(spot, mu, sigma, days, n_sim):
    """
    Paths: (n_sim, days+1) incluyendo spot en t=0
    """
    math, np, _, _ = _imports()

    dt_step = 1 / TRADING_DAYS
    shocks = np.random.normal(
        (mu - 0.5 * sigma**2) * dt_step,
        sigma * math.sqrt(dt_step),
        (n_sim, days)
    )

    growth = np.exp(np.cumsum(shocks, axis=1))
    growth = np.concatenate([np.ones((n_sim, 1)), growth], axis=1)  # t0
    return spot * growth

def _fan_series(paths):
    """
    Percentiles en cada paso temporal.
    """
    _, np, _, _ = _imports()
    p5 = np.percentile(paths, 5, axis=0)
    p50 = np.percentile(paths, 50, axis=0)
    p95 = np.percentile(paths, 95, axis=0)
    return {
        "p5": [float(x) for x in p5],
        "p50": [float(x) for x in p50],
        "p95": [float(x) for x in p95],
    }

def _probs_end(paths, spot):
    """
    Probabilidades al final del horizonte.
    """
    _, np, _, _ = _imports()
    end_vals = paths[:, -1]
    return {
        "P(subir)": round(float((end_vals > spot).mean()), 4),
        "P(+5%)": round(float((end_vals > spot * 1.05).mean()), 4),
        "P(-5%)": round(float((end_vals < spot * 0.95).mean()), 4),
    }

def _risk_label(sigma_annual):
    if sigma_annual < 0.18:
        return {"level": "BAJO", "text": "Volatilidad histórica baja/moderada."}
    if sigma_annual < 0.30:
        return {"level": "MEDIO", "text": "Volatilidad histórica media."}
    return {"level": "ALTO", "text": "Volatilidad histórica elevada."}

# ============================================================
# PAYLOAD POR ACTIVO
# ============================================================

def _build_asset_payload(ticker: str):
    prices = _download_prices(ticker)

    # Último mes (aprox 21 ruedas)
    hist_month = prices.iloc[-MONTH_POINTS:]
    hist_month = _ensure_series_1d(hist_month)

    # Spot T0
    spot_val = hist_month.iloc[-1]
    # spot_val puede venir como 1-element array/serie si hay rareza -> normalizamos:
    if hasattr(spot_val, "__len__") and not isinstance(spot_val, (str, bytes)) and not isinstance(spot_val, float):
        try:
            spot_val = spot_val.iloc[0]  # por si fuera Series 1 elem
        except Exception:
            pass
    spot = float(spot_val)

    # Parámetros GBM
    rets = _log_returns(prices)
    mu = float(rets.mean() * TRADING_DAYS)
    sigma = float(rets.std() * (TRADING_DAYS ** 0.5))

    risk = _risk_label(sigma)

    # Short + Long forecasts (fan chart por día + tabla probs)
    short_term = {"horizons": {}, "table": {}}
    for d in SHORT_HORIZONS:
        paths = _simulate_gbm_paths(spot, mu, sigma, d, N_SIM)
        short_term["horizons"][f"{d}d"] = {
            "days": list(range(0, d + 1)),
            "fan": _fan_series(paths),
        }
        short_term["table"][f"{d}d"] = _probs_end(paths, spot)

    long_term = {"horizons": {}, "table": {}}
    for d in LONG_HORIZONS:
        paths = _simulate_gbm_paths(spot, mu, sigma, d, N_SIM)
        long_term["horizons"][f"{d}d"] = {
            "days": list(range(0, d + 1)),
            "fan": _fan_series(paths),
        }
        long_term["table"][f"{d}d"] = _probs_end(paths, spot)

    # Semáforo (tomamos P(subir) a 5d si existe)
    ref = "5d" if "5d" in short_term["table"] else "2d"
    p_up = short_term["table"][ref]["P(subir)"]
    if p_up > 0.55:
        semaphore = {"status": "FAVORABLE", "text": "Sesgo probabilístico alcista (corto plazo)."}
    elif p_up < 0.45:
        semaphore = {"status": "DESFAVORABLE", "text": "Sesgo probabilístico bajista (corto plazo)."}
    else:
        semaphore = {"status": "NEUTRAL", "text": "Balance de probabilidades relativamente equilibrado."}

    return {
        "ticker": ticker,
        "updated_at": dt.datetime.utcnow().isoformat() + "Z",
        "spot": spot,

        # Histórico del último mes para que el gráfico “venga con contexto”
        "history_month": {
            "dates": [d.strftime("%Y-%m-%d") for d in hist_month.index],
            "prices": [float(x) for x in hist_month.values],
        },

        # Forecasts
        "short_term": short_term,
        "long_term": long_term,

        # Labels
        "risk": risk,
        "semaphore": semaphore,
    }

# ============================================================
# API PUBLICA
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
        "data": data,
    }

    _CACHE["data"] = output
    _CACHE["ts"] = now
    return output

