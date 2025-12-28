# ============================================================
# BONOS SOBERANOS – API OPTIMIZADA PARA RENDER
# ============================================================

import datetime as dt
import json
import math
import time
import requests
import pandas as pd

# ============================================================
# CONFIG
# ============================================================
LIVE_URL = "https://data912.com/live/arg_bonds"
HIST_URL = "https://data912.com/historical/bonds/{ticker}"
CASHFLOW_FILE = "cashflow_bonos.json"

CACHE_TTL = 30          # cache general (segundos)
HIST_CACHE_TTL = 600    # histórico (10 minutos)

# ============================================================
# CACHES
# ============================================================
_CACHE = {"ts": 0, "data": None}
_HIST_CACHE = {}  # ticker -> {ts, data}

# ============================================================
# HELPERS
# ============================================================
def yearfrac(d0, d1):
    return (d1 - d0).days / 365.0

def to_symbol_d(ticker):
    return ticker.upper() + "D"

# ============================================================
# LOAD CASHFLOWS (solo una vez)
# ============================================================
with open(CASHFLOW_FILE, "r", encoding="utf-8") as f:
    RAW_CF = json.load(f)["bonos"]

CASHFLOWS = {}
for t, flows in RAW_CF.items():
    lst = []
    for r in flows:
        lst.append({
            "date": dt.date.fromisoformat(r["fecha"]),
            "flow": float(r["flujo_calc"])
        })
    lst.sort(key=lambda x: x["date"])
    CASHFLOWS[t.upper()] = lst

def future_cashflows(ticker, as_of):
    return [f for f in CASHFLOWS[ticker] if f["date"] > as_of]

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
        pv = pv_from_yield(cfs, mid, as_of)
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
    if symbol in _HIST_CACHE and now - _HIST_CACHE[symbol]["ts"] < HIST_CACHE_TTL:
        return _HIST_CACHE[symbol]["data"]

    r = requests.get(HIST_URL.format(ticker=symbol), timeout=20)
    r.raise_for_status()
    df = pd.DataFrame(r.json())
    df["date"] = pd.to_datetime(df["date"]).dt.date
    df = df.sort_values("date").tail(90)

    _HIST_CACHE[symbol] = {"ts": now, "data": df}
    return df

# ============================================================
# API FUNCTION
# ============================================================
def get_all_bonds_for_api():
    now = time.time()
    if _CACHE["data"] is not None and now - _CACHE["ts"] < CACHE_TTL:
        return _CACHE["data"]

    as_of = dt.date.today()
    live = fetch_live()

    output = []

    for row in live:
        symbol = row["symbol"]
        if not symbol.endswith("D"):
            continue

        ticker = symbol[:-1]
        if ticker not in CASHFLOWS:
            continue

        price = float(row["c"])
        cfs = future_cashflows(ticker, as_of)
        if not cfs:
            continue

        ytm = solve_ytm(cfs, price, as_of)
        dur = duration_mod(cfs, ytm, price, as_of)

        # Sensibilidad (simple)
        sens = []
        for pct in (-0.05, 0.05):
            px = price * (1 + pct)
            y = solve_ytm(cfs, px, as_of)
            sens.append({"shock": f"price {pct:+.0%}", "ytm": y})

        # Histórico TIR (cacheado)
        hist_df = fetch_history_cached(symbol)
        hist = []
        for _, r in hist_df.iterrows():
            d = r["date"]
            px = float(r["c"])
            fcf = future_cashflows(ticker, d)
            if not fcf:
                continue
            try:
                y = solve_ytm(fcf, px, d)
                hist.append({"date": d.isoformat(), "ytm": y})
            except:
                pass

        output.append({
            "ticker": ticker,
            "price": price,
            "ytm": ytm,
            "duration": dur,
            "parity": price,
            "cashflows": [
                {"date": cf["date"].isoformat(), "flow": cf["flow"]}
                for cf in cfs
            ],
            "sensitivity": sens,
            "ytm_history": hist
        })

    _CACHE["data"] = output
    _CACHE["ts"] = now
    return output
