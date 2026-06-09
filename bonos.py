# ============================================================
# BONOS SOBERANOS – API OPTIMIZADA PARA RENDER (STABLE)
# ============================================================

import datetime as dt
import json
import math
import time
import requests
import pandas as pd
import threading

# ============================================================
# CONFIG
# ============================================================
LIVE_URL      = "https://data912.com/live/arg_bonds"
HIST_URL      = "https://data912.com/historical/bonds/{ticker}"
CASHFLOW_FILE = "cashflow_bonos.json"

CACHE_TTL      = 30    # cache general (segundos)
HIST_CACHE_TTL = 600   # histórico (10 minutos)
CF_CACHE_TTL   = 300   # recarga cashflows cada 5 minutos

# ============================================================
# THREAD-SAFE CACHES
# ============================================================
_CACHE       = {"ts": 0.0, "data": None}
_CACHE_LOCK  = threading.Lock()
_INFLIGHT    = False
_INFLIGHT_EVENT = threading.Event()

_HIST_CACHE       = {}
_HIST_LOCKS       = {}
_HIST_LOCKS_GUARD = threading.Lock()

# Cache para cashflows (se recarga periódicamente)
_CF_CACHE = {"ts": 0.0, "data": None}
_CF_LOCK  = threading.Lock()

# ============================================================
# HELPERS
# ============================================================
def yearfrac(d0, d1):
    return (d1 - d0).days / 365.0

def to_symbol_d(ticker):
    return ticker.upper() + "D"

# ============================================================
# LOAD CASHFLOWS — recarga dinámica cada CF_CACHE_TTL segundos
# ============================================================
def load_cashflows():
    """Carga y parsea cashflow_bonos.json. Cachea por CF_CACHE_TTL segundos."""
    global _CF_CACHE

    now = time.time()
    with _CF_LOCK:
        if _CF_CACHE["data"] is not None and now - _CF_CACHE["ts"] < CF_CACHE_TTL:
            return _CF_CACHE["data"]

        with open(CASHFLOW_FILE, "r", encoding="utf-8") as f:
            raw = json.load(f)["bonos"]

        cashflows = {}
        for t, flows in raw.items():
            lst = []
            for r in flows:
                # Soporta tanto estructura vieja (amort_monto) como nueva (sin amort)
                am = r.get("amort_monto")
                amort_val = float(am) if am is not None else 0.0

                flujo = r.get("flujo_calc")
                if flujo is None or (isinstance(flujo, float) and math.isnan(flujo)):
                    continue  # saltar flujos NaN

                lst.append({
                    "date":  dt.date.fromisoformat(r["fecha"]),
                    "flow":  float(flujo),
                    "amort": amort_val,
                })
            lst.sort(key=lambda x: x["date"])
            if lst:
                cashflows[t.upper()] = lst

        _CF_CACHE = {"ts": now, "data": cashflows}
        print(f"[bonos] Cashflows recargados: {len(cashflows)} tickers")
        return cashflows

def future_cashflows(cashflows, ticker, as_of):
    flows = cashflows.get(ticker, [])
    return [f for f in flows if f["date"] > as_of]

# ============================================================
# FINANCE
# ============================================================
def pv_from_yield(cfs, y, as_of):
    pv = 0.0
    for cf in cfs:
        t = yearfrac(as_of, cf["date"])
        pv += cf["flow"] / ((1 + y) ** t)
    return pv

def solve_ytm(cfs, price, as_of):
    lo, hi = -0.95, 5.0
    for _ in range(100):
        mid = (lo + hi) / 2
        pv  = pv_from_yield(cfs, mid, as_of)
        if abs(pv - price) < 1e-6:
            return mid
        if pv > price:
            lo = mid
        else:
            hi = mid
    return mid

def duration_mod(cfs, y, price, as_of):
    num = 0.0
    for cf in cfs:
        t = yearfrac(as_of, cf["date"])
        num += t * cf["flow"] / ((1 + y) ** t)
    macaulay = num / price
    return macaulay / (1 + y)

# ============================================================
# DATA912
# ============================================================
def fetch_live():
    r = requests.get(LIVE_URL, timeout=15)
    r.raise_for_status()
    return r.json()

def fetch_history_cached(symbol):
    now = time.time()

    with _HIST_LOCKS_GUARD:
        if symbol not in _HIST_LOCKS:
            _HIST_LOCKS[symbol] = threading.Lock()
        lock = _HIST_LOCKS[symbol]

    with lock:
        entry = _HIST_CACHE.get(symbol)
        if entry and now - entry["ts"] < HIST_CACHE_TTL:
            return entry["data"]

        try:
            r = requests.get(HIST_URL.format(ticker=symbol), timeout=20)
            r.raise_for_status()
            df = pd.DataFrame(r.json())
            df["date"] = pd.to_datetime(df["date"]).dt.date
            df = df.sort_values("date").tail(90)
            _HIST_CACHE[symbol] = {"ts": now, "data": df}
            return df
        except Exception:
            if entry:
                return entry["data"]
            raise

# ============================================================
# API FUNCTION (THREAD-SAFE + SINGLE-FLIGHT)
# ============================================================
def get_all_bonds_for_api():
    global _INFLIGHT

    now = time.time()

    with _CACHE_LOCK:
        if _CACHE["data"] is not None and now - _CACHE["ts"] < CACHE_TTL:
            return _CACHE["data"]

        if _INFLIGHT:
            event = _INFLIGHT_EVENT
        else:
            _INFLIGHT = True
            _INFLIGHT_EVENT.clear()
            event = None

    # Follower
    if event is not None:
        event.wait(timeout=30)
        with _CACHE_LOCK:
            if _CACHE["data"] is not None:
                return _CACHE["data"]
            raise RuntimeError("Bond cache: fallo concurrente sin datos previos")

    # Líder
    try:
        # ── Recarga dinámica de cashflows ──
        cashflows = load_cashflows()

        as_of = dt.date.today()
        live  = fetch_live()

        output = []

        for row in live:
            symbol = row["symbol"]
            if not symbol.endswith("D"):
                continue

            ticker = symbol[:-1]
            if ticker not in cashflows:
                continue

            price = float(row["c"])
            cfs   = future_cashflows(cashflows, ticker, as_of)
            if not cfs:
                continue

            # Residual: suma de amortizaciones futuras si las hay,
            # si no (estructura nueva sin amort separado) → 100
            residual_value = sum(f["amort"] for f in cfs)
            if residual_value == 0:
                residual_value = 100.0

            parity = (price / residual_value) * 100

            ytm = solve_ytm(cfs, price, as_of)
            dur = duration_mod(cfs, ytm, price, as_of)

            # Sensibilidad
            sens = []
            for pct in (-0.05, 0.05):
                px = price * (1 + pct)
                y  = solve_ytm(cfs, px, as_of)
                sens.append({"shock": f"price {pct:+.0%}", "ytm": y})

            # Histórico de TIR
            try:
                hist_df = fetch_history_cached(symbol)
                hist = []
                for _, r in hist_df.iterrows():
                    d  = r["date"]
                    px = float(r["c"])
                    fcf = future_cashflows(cashflows, ticker, d)
                    if not fcf:
                        continue
                    try:
                        y = solve_ytm(fcf, px, d)
                        hist.append({"date": d.isoformat(), "ytm": y})
                    except Exception:
                        pass
            except Exception:
                hist = []

            output.append({
                "ticker":         ticker,
                "price":          price,
                "ytm":            ytm,
                "duration":       dur,
                "parity":         parity,
                "residual_value": residual_value,
                "cashflows": [
                    {"date": cf["date"].isoformat(), "flow": cf["flow"]}
                    for cf in cfs
                ],
                "sensitivity": sens,
                "ytm_history": hist,
            })

        with _CACHE_LOCK:
            if output:
                _CACHE["data"] = output
                _CACHE["ts"]   = time.time()

        return output

    finally:
        with _CACHE_LOCK:
            _INFLIGHT = False
            _INFLIGHT_EVENT.set()
