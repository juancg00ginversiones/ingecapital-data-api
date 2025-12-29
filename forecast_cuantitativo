# ============================================================
# FORECAST CUANTITATIVO – INGECAPITAL PRO
# ============================================================

import time
import math
import datetime as dt
import numpy as np
import yfinance as yf

# ============================================================
# CONFIG
# ============================================================

CACHE_TTL = 60 * 30  # 30 minutos

N_SIM = 2000
TRADING_DAYS = 252

# Universo fijo
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
# UTILIDADES
# ============================================================

def download_prices(ticker, years=3):
    end = dt.date.today()
    start = end - dt.timedelta(days=365 * years)
    data = yf.download(ticker, start=start, end=end, progress=False)
    if data.empty:
        raise ValueError("No hay datos")
    return data["Adj Close"]

def log_returns(series):
    return np.log(series / series.shift(1)).dropna()

def simulate_gbm(spot, mu, sigma, days, n_sim):
    dt_step = 1 / TRADING_DAYS
    shocks = np.random.normal(
        (mu - 0.5 * sigma**2) * dt_step,
        sigma * math.sqrt(dt_step),
        (n_sim, days)
    )
    paths = spot * np.exp(np.cumsum(shocks, axis=1))
    return paths

def percentiles(paths):
    return {
        "p5": float(np.percentile(paths[:, -1], 5)),
        "p50": float(np.percentile(paths[:, -1], 50)),
        "p95": float(np.percentile(paths[:, -1], 95))
    }

# ============================================================
# FORECAST POR ACTIVO
# ============================================================

def forecast_asset(ticker):
    prices = download_prices(ticker)
    spot = float(prices.iloc[-1])

    rets = log_returns(prices)
    mu = rets.mean() * TRADING_DAYS
    sigma = rets.std() * math.sqrt(TRADING_DAYS)

    # -------- DAILY --------
    daily = {}
    for d in [5, 20, 60]:
        paths = simulate_gbm(spot, mu, sigma, d, N_SIM)
        daily[f"{d}d"] = percentiles(paths)

    # Probabilidades
    one_day = simulate_gbm(spot, mu, sigma, 1, N_SIM)[:, -1]
    prob_up = float(np.mean(one_day > spot))
    prob_up_5 = float(np.mean(one_day > spot * 1.05))
    prob_down_5 = float(np.mean(one_day < spot * 0.95))

    table = {
        "P(subir)": round(prob_up, 3),
        "P(+5%)": round(prob_up_5, 3),
        "P(-5%)": round(prob_down_5, 3)
    }

    # Semáforo simple
    if prob_up > 0.55:
        semaphore = {
            "status": "FAVORABLE",
            "text": "Sesgo probabilístico positivo."
        }
    elif prob_up < 0.45:
        semaphore = {
            "status": "DESFAVORABLE",
            "text": "Sesgo probabilístico negativo."
        }
    else:
        semaphore = {
            "status": "NEUTRAL",
            "text": "Balance de riesgos equilibrado."
        }

    # -------- SHORT --------
    short = {}
    for d in [2, 5]:
        paths = simulate_gbm(spot, mu, sigma, d, N_SIM)
        short[f"{d}d"] = percentiles(paths)

    combined = {
        "status": "HABILITADO",
        "text": "Forecast cuantitativo disponible."
    }

    return {
        "spot": spot,
        "daily": {
            "horizons": daily,
            "table": table,
            "semaphore": semaphore
        },
        "short": short,
        "combined": combined
    }

# ============================================================
# API
# ============================================================

def get_forecast_cuantitativo_for_api():
    now = time.time()
    if _CACHE["data"] is not None and (now - _CACHE["ts"]) < CACHE_TTL:
        return _CACHE["data"]

    data = {}

    for group, tickers in UNIVERSE.items():
        for t in tickers:
            try:
                data[t] = forecast_asset(t)
            except Exception as e:
                data[t] = {"error": str(e)}

    output = {
        "updated_at": dt.datetime.utcnow().isoformat() + "Z",
        "universe": UNIVERSE,
        "data": data
    }

    _CACHE["data"] = output
    _CACHE["ts"] = now
    return output
