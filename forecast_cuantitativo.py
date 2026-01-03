# ============================================================
# FORECAST TRADING CUANTITATIVO – INGECAPITAL PRO (STABLE)
# ============================================================
import time
import datetime as dt
import math
import numpy as np
import pandas as pd
import yfinance as yf
import threading

# ================= CONFIG =================
CACHE_TTL = 60 * 60        # 1 hora
N_SIM = 500
TRADING_DAYS = 252
MONTH_POINTS = 21

SHORT_HORIZONS = [2, 5]
LONG_HORIZONS = [5, 20, 60]

UNIVERSE = {
    "indices": ["SPY", "QQQ"],
    "magnificas": ["AAPL", "MSFT", "NVDA", "AMZN", "META"],
    "crypto": ["BTC-USD", "ETH-USD"]
}

_CACHE = {"ts": 0.0, "data": None}

# Infra concurrencia
_CACHE_LOCK = threading.Lock()
_INFLIGHT = False
_INFLIGHT_EVENT = threading.Event()


# ================= HELPERS =================
def _ensure_series(x):
    if isinstance(x, pd.DataFrame):
        return x.iloc[:, 0]
    return x

def _download_prices(ticker):
    df = yf.download(ticker, period="2y", progress=False, threads=False)
    if df.empty:
        raise ValueError("Sin datos")

    col = "Adj Close" if "Adj Close" in df.columns else "Close"
    s = _ensure_series(df[col]).dropna()
    return s

def _log_returns(prices):
    return np.log(prices / prices.shift(1)).dropna()


# ================= SIMULACION =================
def _gbm_paths(spot, mu, sigma, days):
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
    final_points = paths[:, -1]
    return {
        "p5": float(np.percentile(final_points, 5)),
        "p50": float(np.percentile(final_points, 50)),
        "p95": float(np.percentile(final_points, 95)),
    }

def _probs(paths, spot):
    end = paths[:, -1]
    return {
        "prob_up": round(float((end > spot).mean()) * 100, 2),
        "prob_gt_5": round(float((end > spot * 1.05).mean()) * 100, 2),
        "prob_lt_minus_5": round(float((end < spot * 0.95).mean()) * 100, 2),
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
        "spot": round(spot, 2),
        "history_month": {
            "dates": [d.strftime("%Y-%m-%d") for d in hist.index],
            "prices": [round(float(v), 2) for v in hist.values]
        },
        "short_term": short,
        "long_term": long
    }


# ================= API ENDPOINT (THREAD-SAFE) =================
def get_forecast_cuantitativo_for_api():
    global _INFLIGHT

    now = time.time()

    # ---------- Cache fresh ----------
    with _CACHE_LOCK:
        if _CACHE["data"] is not None and (now - _CACHE["ts"]) < CACHE_TTL:
            return _CACHE["data"]

        if _INFLIGHT:
            event = _INFLIGHT_EVENT
        else:
            _INFLIGHT = True
            _INFLIGHT_EVENT.clear()
            event = None

    # ---------- Follower ----------
    if event is not None:
        event.wait(timeout=120)
        with _CACHE_LOCK:
            if _CACHE["data"] is not None:
                return _CACHE["data"]
            return {"error": "Datos no disponibles"}

    # ---------- Líder ----------
    try:
        data = {}
        for group in UNIVERSE.values():
            for t in group:
                try:
                    data[t] = _build_payload(t)
                except Exception as e:
                    print(f"Error en {t}: {e}")
                    continue

        universe_flat = sorted(list(data.keys()))

        output = {
            "updated_at": dt.datetime.now(dt.timezone.utc).isoformat() + "Z",
            "universe": UNIVERSE,
            "universe_flat": universe_flat,
            "data": data
        }

        with _CACHE_LOCK:
            if output:
                _CACHE["data"] = output
                _CACHE["ts"] = time.time()

        return output

    except Exception as e:
        with _CACHE_LOCK:
            if _CACHE["data"] is not None:
                return _CACHE["data"]
        raise

    finally:
        with _CACHE_LOCK:
            _INFLIGHT = False
            _INFLIGHT_EVENT.set()

