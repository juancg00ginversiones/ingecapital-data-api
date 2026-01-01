import math
import time
import datetime as dt
from datetime import timezone
import yfinance as yf
import pandas as pd
import numpy as np

# CONFIGURACIÓN
RISK_FREE = 0.0
CONTRACT_MULT = 100
CACHE_TTL = 60 * 10 

UNIVERSE = ["SPY", "QQQ", "DIA", "NVDA", "AAPL", "MSFT", "AMZN", "META", "TSLA", "GLD", "SLV", "IBIT"]

_CACHE = {"ts": 0, "data": None}

def clean_iv(iv):
    if iv is None or pd.isna(iv): return None
    if iv > 3: iv /= 100
    return float(iv) if 0.01 <= iv <= 3 else None

def norm_pdf(x):
    return math.exp(-0.5 * x * x) / math.sqrt(2 * math.pi)

def bs_gamma(S, K, T, r, sigma):
    if T <= 0 or not sigma or sigma <= 0: return 0.0
    d1 = (math.log(S / K) + (r + 0.5 * sigma**2) * T) / (sigma * math.sqrt(T))
    return norm_pdf(d1) / (S * sigma * math.sqrt(T))

def get_options_chain(symbol):
    ticker = yf.Ticker(symbol)
    hist = ticker.history(period="2d", auto_adjust=True)
    if hist.empty: raise ValueError("Sin precio spot")
    
    spot = float(hist["Close"].iloc[-1])
    options_dates = ticker.options
    if not options_dates: raise ValueError("Sin opciones")

    chain = None
    expiry_date = None
    # Buscamos en las primeras 3 fechas hasta encontrar una con datos
    for date in options_dates[:3]:
        try:
            temp_chain = ticker.option_chain(date)
            if temp_chain.calls is not None and not temp_chain.calls.empty:
                chain = temp_chain
                expiry_date = date
                break
        except: continue

    if not chain: raise ValueError("Cadena vacía")

    rows = []
    # Procesamiento seguro de Calls
    if chain.calls is not None:
        for _, r in chain.calls.iterrows():
            rows.append({"strike": r["strike"], "oi_call": r.get("openInterest", 0) or 0, "oi_put": 0, "iv": clean_iv(r.get("impliedVolatility"))})
    # Procesamiento seguro de Puts
    if chain.puts is not None:
        for _, r in chain.puts.iterrows():
            rows.append({"strike": r["strike"], "oi_call": 0, "oi_put": r.get("openInterest", 0) or 0, "iv": clean_iv(r.get("impliedVolatility"))})

    df = pd.DataFrame(rows).groupby("strike").agg({"oi_call": "sum", "oi_put": "sum", "iv": "mean"}).reset_index()
    return df, spot, dt.datetime.strptime(expiry_date, "%Y-%m-%d").date()

def build_levels(df, spot, expiry):
    dte = (expiry - dt.date.today()).days
    T = max(dte, 0.5) / 365
    use_gamma = dte > 1

    df["gex_net"] = 0.0
    for i, r in df.iterrows():
        if use_gamma and r["iv"]:
            g = bs_gamma(spot, r["strike"], T, RISK_FREE, r["iv"])
            df.at[i, "gex_net"] = (r["oi_call"] - r["oi_put"]) * g * CONTRACT_MULT
        else:
            df.at[i, "gex_net"] = r["oi_call"] - r["oi_put"]

    gamma_flip = None
    df_s = df.sort_values("strike")
    for i in range(1, len(df_s)):
        if df_s.iloc[i-1]["gex_net"] * df_s.iloc[i]["gex_net"] < 0:
            gamma_flip = df_s.iloc[i]["strike"]
            break

    return {
        "spot": round(spot, 2),
        "expiry": expiry.isoformat(),
        "dte": dte,
        "put_wall": float(df.loc[df["oi_put"].idxmax(), "strike"]),
        "call_wall": float(df.loc[df["oi_call"].idxmax(), "strike"]),
        "gamma_flip": float(gamma_flip) if gamma_flip else None
    }

def get_options_structure_for_api():
    now = time.time()
    if _CACHE["data"] and (now - _CACHE["ts"]) < CACHE_TTL: return _CACHE["data"]

    data = {}
    for symbol in UNIVERSE:
        try:
            df, spot, expiry = get_options_chain(symbol)
            data[symbol] = build_levels(df, spot, expiry)
        except Exception as e:
            data[symbol] = {"error": str(e)}

    _CACHE["data"] = {"updated_at": dt.datetime.now(timezone.utc).isoformat(), "data": data}
    _CACHE["ts"] = now
    return _CACHE["data"]
