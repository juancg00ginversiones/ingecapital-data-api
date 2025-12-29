# ============================================================
# ESTRUCTURA DE OPCIONES – INGECAPITAL PRO (FINAL)
# ============================================================

import math
import time
import datetime as dt
import yfinance as yf
import pandas as pd

# ============================================================
# CONFIGURACIÓN
# ============================================================

RISK_FREE = 0.0
CONTRACT_MULT = 100

CACHE_TTL = 60 * 10  # 10 minutos

# Universo curado (índices, magnificas, commodities, BTC proxy)
UNIVERSE = [
    "SPY",   # S&P 500
    "QQQ",   # Nasdaq
    "DIA",   # Dow Jones
    "NVDA",
    "AAPL",
    "MSFT",
    "AMZN",
    "META",
    "TSLA",
    "GLD",   # Oro
    "SLV",   # Plata
    "IBIT"   # Bitcoin proxy
]

_CACHE = {
    "ts": 0,
    "data": None
}

# ============================================================
# UTILIDADES
# ============================================================

def clean_iv(iv):
    if iv is None or pd.isna(iv):
        return None
    if iv > 3:
        iv = iv / 100
    if iv < 0.01 or iv > 3:
        return None
    return float(iv)

def days_to_expiry(expiry):
    return (expiry - dt.date.today()).days

def norm_pdf(x):
    return math.exp(-0.5 * x * x) / math.sqrt(2 * math.pi)

def bs_gamma(S, K, T, r, sigma):
    if T <= 0 or sigma is None or sigma <= 0:
        return 0.0
    d1 = (math.log(S / K) + (r + 0.5 * sigma**2) * T) / (sigma * math.sqrt(T))
    return norm_pdf(d1) / (S * sigma * math.sqrt(T))

# ============================================================
# OPCIONES
# ============================================================

def get_options_chain(symbol):
    ticker = yf.Ticker(symbol)
    hist = ticker.history(period="5d")

    if hist.empty or not ticker.options:
        raise ValueError("Sin datos de opciones.")

    spot = float(hist["Close"].iloc[-1])
    expiry = dt.datetime.strptime(ticker.options[0], "%Y-%m-%d").date()
    chain = ticker.option_chain(ticker.options[0])

    rows = []
    for _, r in chain.calls.iterrows():
        rows.append({
            "strike": r["strike"],
            "oi_call": r["openInterest"],
            "oi_put": 0,
            "iv": clean_iv(r["impliedVolatility"])
        })
    for _, r in chain.puts.iterrows():
        rows.append({
            "strike": r["strike"],
            "oi_call": 0,
            "oi_put": r["openInterest"],
            "iv": clean_iv(r["impliedVolatility"])
        })

    df = pd.DataFrame(rows).groupby("strike").sum(numeric_only=True).reset_index()
    return df.sort_values("strike"), spot, expiry

# ============================================================
# CÁLCULO DE NIVELES
# ============================================================

def build_levels(df, spot, expiry):
    dte = days_to_expiry(expiry)
    T = max(dte, 0) / 365
    use_gamma = dte > 1

    df["gex_call"] = 0.0
    df["gex_put"] = 0.0

    for i, r in df.iterrows():
        if use_gamma:
            g = bs_gamma(spot, r["strike"], T, RISK_FREE, r["iv"])
            df.at[i, "gex_call"] = g * r["oi_call"] * CONTRACT_MULT
            df.at[i, "gex_put"] = -g * r["oi_put"] * CONTRACT_MULT
        else:
            df.at[i, "gex_call"] = r["oi_call"]
            df.at[i, "gex_put"] = -r["oi_put"]

    df["gex_net"] = df["gex_call"] + df["gex_put"]

    gamma_flip = None
    for i in range(1, len(df)):
        if df.iloc[i-1]["gex_net"] * df.iloc[i]["gex_net"] < 0:
            gamma_flip = df.iloc[i]["strike"]
            break

    return {
        "spot": float(spot),
        "expiry": expiry.isoformat(),
        "dte": int(dte),
        "analysis_type": "gamma" if use_gamma else "oi_proxy",
        "put_wall": float(df.loc[df["oi_put"].idxmax(), "strike"]),
        "call_wall": float(df.loc[df["oi_call"].idxmax(), "strike"]),
        "gamma_peak": float(df.loc[df["gex_net"].abs().idxmax(), "strike"]),
        "gamma_flip": float(gamma_flip) if gamma_flip else None
    }

# ============================================================
# RESUMEN INTERPRETATIVO (CLAVE)
# ============================================================

def explain_market_structure(levels):
    spot = levels["spot"]
    pw = levels["put_wall"]
    cw = levels["call_wall"]
    gp = levels["gamma_peak"]
    gf = levels["gamma_flip"]
    use_gamma = levels["analysis_type"] == "gamma"

    lines = []
    lines.append("Resumen del mercado de opciones:")

    if use_gamma:
        lines.append("Análisis basado en Gamma Exposure.")
    else:
        lines.append("Análisis basado en Open Interest (vencimiento inmediato).")

    if abs(spot - gp) / spot < 0.01:
        lines.append("El precio se encuentra en zona de equilibrio (Gamma Peak), lo que sugiere lateralización.")
    elif spot < pw:
        lines.append("El precio está por debajo del Put Wall, aumentando el riesgo de aceleración bajista.")
    elif spot > cw:
        lines.append("El precio está por encima del Call Wall, lo que puede generar aceleración alcista.")
    else:
        lines.append("El mercado se encuentra en transición entre niveles clave.")

    if gf:
        if spot < gf:
            lines.append("Por debajo del Gamma Flip se espera mayor volatilidad.")
        else:
            lines.append("Por encima del Gamma Flip el mercado suele comportarse de forma más estable.")

    return " ".join(lines)

# ============================================================
# API PRINCIPAL
# ============================================================

def get_options_structure_for_api():
    now = time.time()
    if _CACHE["data"] is not None and (now - _CACHE["ts"]) < CACHE_TTL:
        return _CACHE["data"]

    data = {}
    for symbol in UNIVERSE:
        try:
            df, spot, expiry = get_options_chain(symbol)
            levels = build_levels(df, spot, expiry)
            levels["summary"] = explain_market_structure(levels)
            data[symbol] = levels
        except Exception as e:
            data[symbol] = {"error": str(e)}

    output = {
        "updated_at": dt.datetime.utcnow().isoformat() + "Z",
        "universe": UNIVERSE,
        "data": data
    }

    _CACHE["data"] = output
    _CACHE["ts"] = now
    return output

