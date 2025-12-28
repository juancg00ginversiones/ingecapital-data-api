# ============================================================
# BONOS SOBERANOS ARGENTINOS – MOTOR PARA API
# ============================================================

import datetime as dt
import json
import math
import requests
import pandas as pd

# ============================================================
# CONFIG
# ============================================================
LIVE_URL = "https://data912.com/live/arg_bonds"
HIST_URL = "https://data912.com/historical/bonds/{ticker}"
CASHFLOW_FILE = "cashflow_bonos.json"


# ============================================================
# HELPERS
# ============================================================
def to_symbol_d(ticker: str) -> str:
    return ticker.upper() + "D"

def yearfrac(d0, d1):
    return (d1 - d0).days / 365.0


# ============================================================
# LOAD CASHFLOWS
# ============================================================
def load_cashflows():
    with open(CASHFLOW_FILE, "r", encoding="utf-8") as f:
        raw = json.load(f)

    if "bonos" not in raw:
        raise ValueError("cashflow_bonos.json debe tener clave 'bonos'")

    out = {}
    for ticker, flows in raw["bonos"].items():
        lst = []
        for r in flows:
            lst.append({
                "date": dt.date.fromisoformat(r["fecha"]),
                "flow": float(r["flujo_calc"])
            })
        lst.sort(key=lambda x: x["date"])
        out[ticker.upper()] = lst

    return out


CASHFLOWS = load_cashflows()


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
    for _ in range(200):
        mid = (lo + hi) / 2
        pv = pv_from_yield(cfs, mid, as_of)
        if abs(pv - price) < 1e-8:
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
def fetch_live_prices():
    r = requests.get(LIVE_URL, timeout=20)
    r.raise_for_status()
    return r.json()


def fetch_history(symbol_d):
    r = requests.get(HIST_URL.format(ticker=symbol_d), timeout=30)
    r.raise_for_status()
    df = pd.DataFrame(r.json())
    df["date"] = pd.to_datetime(df["date"]).dt.date
    return df.sort_values("date")


# ============================================================
# MAIN API FUNCTION
# ============================================================
def get_all_bonds_for_api():
    as_of = dt.date.today()
    live = fetch_live_prices()

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

        # Sensibilidad
        sens = []
        for pct in [-0.05, 0.05]:
            px = price * (1 + pct)
            y = solve_ytm(cfs, px, as_of)
            sens.append({
                "shock": f"price {pct:+.0%}",
                "ytm": y
            })

        # Histórico TIR (últimos 90 días)
        hist = fetch_history(symbol).tail(90)
        hist_ytm = []
        for _, r in hist.iterrows():
            d = r["date"]
            px = float(r["c"])
            fcf = future_cashflows(ticker, d)
            if not fcf:
                continue
            try:
                y = solve_ytm(fcf, px, d)
                hist_ytm.append({
                    "date": d.isoformat(),
                    "ytm": y
                })
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
            "ytm_history": hist_ytm
        })

    return output
