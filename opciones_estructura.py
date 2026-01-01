import math
import time
import datetime as dt
from datetime import timezone
import yfinance as yf
import pandas as pd
import numpy as np

# ============================================================
# CONFIGURACIÓN
# ============================================================
RISK_FREE = 0.05  # Tasa libre de riesgo aproximada
CONTRACT_MULT = 100
CACHE_TTL = 60 * 15  # 15 minutos de caché

UNIVERSE = ["SPY", "QQQ", "DIA", "NVDA", "AAPL", "MSFT", "AMZN", "META", "TSLA", "GLD", "SLV", "IBIT"]

_CACHE = {"ts": 0, "data": None}

# ============================================================
# UTILIDADES MATEMÁTICAS
# ============================================================
def clean_iv(iv):
    if iv is None or pd.isna(iv): return None
    if iv > 3: iv /= 100 # Corrección si viene en formato 100%
    return float(iv) if 0.01 <= iv <= 3 else None

def norm_pdf(x):
    return math.exp(-0.5 * x * x) / math.sqrt(2 * math.pi)

def bs_gamma(S, K, T, r, sigma):
    if T <= 0 or not sigma or sigma <= 0: return 0.0
    try:
        d1 = (math.log(S / K) + (r + 0.5 * sigma**2) * T) / (sigma * math.sqrt(T))
        return norm_pdf(d1) / (S * sigma * math.sqrt(T))
    except: return 0.0

# ============================================================
# MOTOR DE EXTRACCIÓN (FILTRO DE LIQUIDEZ)
# ============================================================
def get_best_options_chain(symbol):
    ticker = yf.Ticker(symbol)
    hist = ticker.history(period="2d", auto_adjust=True)
    if hist.empty: raise ValueError("Spot no disponible")
    
    # Manejo de MultiIndex por si yfinance devuelve niveles extra
    if isinstance(hist.columns, pd.MultiIndex):
        hist.columns = hist.columns.get_level_values(0)
    
    spot = float(hist["Close"].iloc[-1])
    options_dates = ticker.options
    if not options_dates: raise ValueError("Sin cadenas de opciones")

    best_chain = None
    best_expiry = None
    max_total_oi = -1

    # Analizamos las primeras 5 fechas para encontrar la más "pesada" (liquidez real)
    for date in options_dates[:5]:
        try:
            temp_chain = ticker.option_chain(date)
            # Sumamos OI de calls y puts para medir relevancia
            calls_oi = temp_chain.calls["openInterest"].sum() if temp_chain.calls is not None else 0
            puts_oi = temp_chain.puts["openInterest"].sum() if temp_chain.puts is not None else 0
            total_oi = calls_oi + puts_oi
            
            if total_oi > max_total_oi:
                max_total_oi = total_oi
                best_chain = temp_chain
                best_expiry = date
        except: continue

    if not best_chain: raise ValueError("No se encontró cadena con liquidez")

    rows = []
    # Procesamiento seguro de datos
    if best_chain.calls is not None:
        for _, r in best_chain.calls.iterrows():
            rows.append({
                "strike": float(r["strike"]), 
                "oi_call": int(r.get("openInterest", 0) or 0), 
                "oi_put": 0, 
                "iv": clean_iv(r.get("impliedVolatility"))
            })
    
    if best_chain.puts is not None:
        for _, r in best_chain.puts.iterrows():
            rows.append({
                "strike": float(r["strike"]), 
                "oi_call": 0, 
                "oi_put": int(r.get("openInterest", 0) or 0), 
                "iv": clean_iv(r.get("impliedVolatility"))
            })

    df = pd.DataFrame(rows).groupby("strike").agg({
        "oi_call": "sum", "oi_put": "sum", "iv": "mean"
    }).reset_index()
    
    return df, spot, dt.datetime.strptime(best_expiry, "%Y-%m-%d").date()

# ============================================================
# LÓGICA DE NIVELES Y RESUMEN
# ============================================================
def explain_market_structure(levels):
    spot, pw, cw, gp, gf = levels["spot"], levels["put_wall"], levels["call_wall"], levels["gamma_peak"], levels["gamma_flip"]
    lines = ["Análisis basado en el vencimiento con mayor liquidez detectado."]

    if abs(spot - gp) / spot < 0.01:
        lines.append("El precio gravita en el Gamma Peak; zona de equilibrio y baja volatilidad.")
    elif spot < pw:
        lines.append("Alerta: Precio bajo el Put Wall. Riesgo de capitulación o soporte extremo.")
    elif spot > cw:
        lines.append("Precio sobre el Call Wall: Posible 'overshoot' o zona de toma de ganancias.")
    else:
        lines.append("Mercado fluyendo entre niveles clave de liquidez.")

    if gf:
        status = "bajista/volátil" if spot < gf else "alcista/estable"
        lines.append(f"El Gamma Flip está en {gf}. El sesgo actual es {status}.")

    return " ".join(lines)

def build_levels(df, spot, expiry):
    dte = (expiry - dt.date.today()).days
    T = max(dte, 0.5) / 365
    use_gamma = dte > 0

    df["gex_net"] = 0.0
    for i, r in df.iterrows():
        if use_gamma and r["iv"]:
            g = bs_gamma(spot, r["strike"], T, RISK_FREE, r["iv"])
            df.at[i, "gex_net"] = (r["oi_call"] - r["oi_put"]) * g * CONTRACT_MULT
        else:
            df.at[i, "gex_net"] = r["oi_call"] - r["oi_put"]

    # Cálculo de Flip (donde la GEX cruza el eje 0)
    gamma_flip = None
    df_s = df.sort_values("strike")
    for i in range(1, len(df_s)):
        if (df_s.iloc[i-1]["gex_net"] * df_s.iloc[i]["gex_net"]) < 0:
            gamma_flip = df_s.iloc[i]["strike"]
            break

    levels = {
        "spot": round(float(spot), 2),
        "expiry": expiry.isoformat(),
        "dte": int(dte),
        "analysis_type": "gamma_exposure" if use_gamma else "open_interest",
        "put_wall": float(df.loc[df["oi_put"].idxmax(), "strike"]),
        "call_wall": float(df.loc[df["oi_call"].idxmax(), "strike"]),
        "gamma_peak": float(df.loc[df["gex_net"].abs().idxmax(), "strike"]),
        "gamma_flip": float(gamma_flip) if gamma_flip else None
    }
    levels["summary"] = explain_market_structure(levels)
    return levels

# ============================================================
# INTERFAZ PARA API
# ============================================================
def get_options_structure_for_api():
    now = time.time()
    if _CACHE["data"] and (now - _CACHE["ts"]) < CACHE_TTL:
        return _CACHE["data"]

    results = {}
    for symbol in UNIVERSE:
        try:
            df, spot, expiry = get_best_options_chain(symbol)
            results[symbol] = build_levels(df, spot, expiry)
        except Exception as e:
            results[symbol] = {"error": f"Error en {symbol}: {str(e)}"}

    output = {
        "updated_at": dt.datetime.now(timezone.utc).isoformat() + "Z",
        "universe": UNIVERSE,
        "data": results
    }

    _CACHE["data"] = output
    _CACHE["ts"] = now
    return output
