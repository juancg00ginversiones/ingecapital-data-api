# ============================================================
# FORECAST TRADING CUANTITATIVO – INGECAPITAL PRO (FINAL)
# ============================================================

import time
import datetime as dt

# ============================================================
# CONFIG
# ============================================================

CACHE_TTL = 60 * 30  # 30 minutos
N_SIM = 1500
TRADING_DAYS = 252

UNIVERSE = {
    "indices": ["SPY", "QQQ"],
    "magnificas": ["AAPL", "MSFT", "NVDA", "AMZN", "META"],
    "crypto": ["BTC-USD", "ETH-USD"]
}

_CACHE = {
    "ts": 0,
    "data": None
}

# ============================================================
# LAZY IMPORTS (CLAVE PARA RENDER)
# ============================================================

def _imports():
    import math
    import numpy as np
    import yfinance as yf
    return math, np, yf

# ============================================================
# DATA
# ============================================================

def _download_prices(ticker):
    _, _, yf = _imports()

    end = dt.date.today()
    start = end - dt.timedelta(days=365 * 3)

    data = yf.download(
        ticker,
        start=start,
        end=end,
        progress=False,
        threads=False
    )

    if data is None or data.empty:
        raise ValueError("No hay datos históricos")

    # FIX DEFINITIVO yfinance (Adj Close no siempre existe)
    if "Adj Close" in data.columns:
        return data["Adj Close"]
    elif "Close" in data.columns:
        return data["Close"]
    else:
        raise ValueError("No se encontró columna de precios válida (Close/Adj Close)")

def _log_returns(series):
    import numpy as np
    return np.log(series / series.shift(1)).dropna()

# ============================================================
# MODELO
# ============================================================

def _simulate_gbm(spot, mu, sigma, days, n_sim):
    math, np, _ = _imports()

    dt_step = 1 / TRADING_DAYS

    shocks = np.random.normal(
        (mu - 0.5 * sigma**2) * dt_step,
        sigma * math.sqrt(dt_step),
        (n_sim, days)
    )

    return spot * np.exp(np.cumsum(shocks, axis=1))

def _percentiles(paths):
    import numpy as np
    return {
        "p5": float(np.percentile(paths[:, -1], 5)),
        "p50": float(np.percentile(paths[:, -1], 50)),
        "p95": float(np.percentile(paths[:, -1], 95))
    }

# ============================================================
# FORECAST POR ACTIVO
# ============================================================

def _forecast_asset(ticker):
    prices = _download_prices(ticker)
    spot = float(prices.iloc[-1])

    rets = _log_returns(prices)
    mu = float(rets.mean() * TRADING_DAYS)
    sigma = float(rets.std() * (TRADING_DAYS ** 0.5))

    # -------- LARGO PLAZO --------
    daily = {}
    for d in (5, 20, 60):
        paths = _simulate_gbm(spot, mu, sigma, d, N_SIM)
        daily[f"{d}d"] = _percentiles(paths)

    # -------- PROBABILIDADES --------
    one_day = _simulate_gbm(spot, mu, sigma, 1, N_SIM)[:, -1]

    p_up = float((one_day > spot).mean())
    p_up_5 = float((one_day > spot * 1.05).mean())
    p_down_5 = float((one_day < spot * 0.95).mean())

    table = {
        "P(subir)": round(p_up, 3),
        "P(+5%)": round(p_up_5, 3),
        "P(-5%)": round(p_down_5, 3)
    }

    if p_up > 0.55:
        semaphore = {"status": "FAVORABLE", "text": "Sesgo probabilístico positivo."}
    elif p_up < 0.45:
        semaphore = {"status": "DESFAVORABLE", "text": "Sesgo probabilístico negativo."}
    else:
        semaphore = {"status": "NEUTRAL", "text": "Balance de riesgos equilibrado."}

    # -------- CORTO PLAZO --------
    short = {}
    for d in (2, 5):
        paths = _simulate_gbm(spot, mu, sigma, d, N_SIM)
        short[f"{d}d"] = _percentiles(paths)

    return {
        "spot": spot,
        "daily": {
            "horizons": daily,
            "table": table,
            "semaphore": semaphore
        },
        "short": short
    }

# ============================================================
# API PUBLICA
# ============================================================

def get_forecast_cuantitativo_for_api():
    now = time.time()

    # Cache
    if _CACHE["data"] is not None and (now - _CACHE["ts"]) < CACHE_TTL:
        return _CACHE["data"]

    data = {}

    for group, tickers in UNIVERSE.items():
        for t in tickers:
            try:
                data[t] = _forecast_asset(t)
            except Exception as e:
                data[t] = {"error": str(e)}

    # Universe plano (frontend-friendly)
    universe_flat = []
    for tickers in UNIVERSE.values():
        universe_flat.extend(tickers)

    output = {
        "updated_at": dt.datetime.utcnow().isoformat() + "Z",
        "universe": UNIVERSE,               # categorizado (para UI por secciones)
        "universe_flat": universe_flat,     # plano (para loops simples/sort)
        "data": data
    }

    _CACHE["data"] = output
    _CACHE["ts"] = now
    return output
