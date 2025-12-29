# ============================================================
# FORECAST TRADING CUANTITATIVO – INGECAPITAL PRO (RENDER SAFE)
# ============================================================

import time
import datetime as dt

# ================= CONFIG =================
CACHE_TTL = 60 * 60        # 1 hora
N_SIM = 600                # ↓ CLAVE: evita timeout
TRADING_DAYS = 252
MONTH_POINTS = 21

SHORT_HORIZONS = [2, 5]
LONG_HORIZONS = [5, 20, 60]

UNIVERSE = {
    "indices": ["SPY", "QQQ"],
    "magnificas": ["AAPL", "MSFT", "NVDA", "AMZN", "META"],
    "crypto": ["BTC-USD", "ETH-USD"]
}

_CACHE = {"ts": 0, "data": None}

# ================= IMPORTS =================
def _imports():
    import math
    import numpy as np
    import pandas as pd
    import yfinance as yf
    return math, np, pd, yf

# ================= HELPERS =================
def _ensure_series(x):
    _, _, pd, _ = _imports()
    if isinstance(x, pd.DataFrame):
        return x.iloc[:, 0]
    return x

def _download_prices(ticker):
    _, _, pd, yf = _imports()

    df = yf.download(
        ticker,
        period="3y",
        progress=False,
        threads=False
    )

    if df.empty:
        raise ValueError("Sin datos")

    col = "Adj Close" if "Adj Close" in df.columns else "Close"
    s = _ensure_series(df[col]).dropna()

    if not isinstance(s.index, pd.DatetimeIndex):
        s.index = pd.to_datetime(s.index)

    return s

def _log_returns(prices):
    _, np, _, _ = _imports()
    return np.log(prices / prices.shift(1)).dropna()

# ================= SIMULACION =================
def _gbm_paths(spot, mu, sigma, days):
    math, np, _, _ = _imports()

    dt_step = 1 / TRADING_DAYS
    shocks = np.random.normal(
        (mu - 0.5 * sigma**2) * dt_step,
        sigma * math.sqrt(dt_step),
        (N_SIM, days)
    )

    growth = np.exp(shocks.cumsum(axis=1))
    growth = np.hstack([np.ones((N_SIM, 1)), growth])
    return spot * growth

def _fan(paths):
    _, np, _, _ = _imports()
    return {
        "p5": paths.mean(axis=0).tolist(),
        "p50": np.percentile(paths, 50, axis=0).tolist(),
        "p95": np.percentile(paths, 95, axis=0).tolist(),
    }

def _probs(paths, spot):
    end = paths[:, -1]
    return {
        "P(subir)": round(float((end > spot).mean()), 3),
        "P(+5%)": round(float((end > spot * 1.05).mean()), 3),
        "P(-5%)": round(float((end < spot * 0.95).mean()), 3),
    }

# ================= PAYLOAD =================
def _build_payload(ticker):
    prices = _download_prices(ticker)

    hist = prices.iloc[-MONTH_POINTS:]
    spot = float(hist.iloc[-1])

    rets = _log_returns(prices)
    mu = float(rets.mean() * TRADING_DAYS)
    sigma = float(rets.std() * (TRADING_DAYS ** 0.5))

    short = {"horizons": {}, "table": {}}
    for d in SHORT_HORIZONS:
        paths = _gbm_paths(spot, mu, sigma, d)
        short["horizons"][f"{d}d"] = {"fan": _fan(paths)}
        short["table"][f"{d}d"] = _probs(paths, spot)

    long = {"horizons": {}, "table": {}}
    for d in LONG_HORIZONS:
        paths = _gbm_paths(spot, mu, sigma, d)
        long["horizons"][f"{d}d"] = {"fan": _fan(paths)}
        long["table"][f"{d}d"] = _probs(paths, spot)

    return {
        "ticker": ticker,
        "spot": spot,
        "history_month": {
            "dates": [d.strftime("%Y-%m-%d") for d in hist.index],
            "prices": hist.values.tolist()
        },
        "short_term": short,
        "long_term": long
    }

# ================= API =================
def get_forecast_cuantitativo_for_api():
    now = time.time()
    if _CACHE["data"] and now - _CACHE["ts"] < CACHE_TTL:
        return _CACHE["data"]

    data = {}
    for group in UNIVERSE.values():
        for t in group:
            try:
                data[t] = _build_payload(t)
            except Exception as e:
                data[t] = {"ticker": t, "error": str(e)}

    universe_flat = sorted({t for g in UNIVERSE.values() for t in g})

    output = {
        "updated_at": dt.datetime.utcnow().isoformat() + "Z",
        "universe": UNIVERSE,
        "universe_flat": universe_flat,
        "data": data
    }

    _CACHE["data"] = output
    _CACHE["ts"] = now
    return output

