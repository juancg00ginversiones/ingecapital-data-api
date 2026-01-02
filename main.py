import time
import logging
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime, timezone

# --- IMPORTACIÓN DE TUS SCRIPTS ---
# Asegurate de que los archivos .py estén en la misma carpeta
try:
    from bonos import get_all_bonds_for_api
    from curva_opciones import analyze_ticker_for_api
    from dolares import get_dolares_for_api
    from forecastcuantitativo import get_forecast_cuantitativo_for_api
    from indicators import analyze_ticker
    from lecap_band_engine import get_lecap_band_for_api
    from letras_bonos import get_letras_bonos_for_api
    # Agregamos los que faltaban según tu archivo:
    # from noticias import get_financial_news_for_api
    # from market_screener import get_market_screener_for_api
except ImportError as e:
    print(f"⚠️ Error importando scripts: {e}")

app = FastAPI(title="IngeCapital Pro API - FULL PROTECTED")

# Configuración CORS para que Horizons pueda leer la API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================================
# SISTEMA DE CACHÉ MAESTRO
# ============================================================
_MASTER_CACHE = {
    "bonos": {"data": None, "ts": 0, "ttl": 60},
    "dolares": {"data": None, "ts": 0, "ttl": 300},
    "forecast": {"data": None, "ts": 0, "ttl": 1800},
    "letras": {"data": None, "ts": 0, "ttl": 60},
    "lecap_band": {"data": None, "ts": 0, "ttl": 60},
    "noticias": {"data": None, "ts": 0, "ttl": 900},
    "screener": {"data": None, "ts": 0, "ttl": 600},
    "opciones_ticker": {} # Caché dinámica por ticker
}

def get_protected_data(key, fetch_func, *args, **kwargs):
    now = time.time()
    item = _MASTER_CACHE.get(key)
    
    if item and item["data"] and (now - item["ts"] < item["ttl"]):
        return item["data"]
    
    try:
        data = fetch_func(*args, **kwargs)
        if item is not None:
            _MASTER_CACHE[key]["data"] = data
            _MASTER_CACHE[key]["ts"] = now
        return data
    except Exception as e:
        logging.error(f"Error en {key}: {e}")
        if item and item["data"]: return item["data"] # Devolvemos stale data si falla
        raise HTTPException(status_code=500, detail=str(e))

# ============================================================
# ENDPOINTS DEFINITIVOS
# ============================================================

@app.get("/bonos")
def route_bonos():
    return get_protected_data("bonos", get_all_bonds_for_api)

@app.get("/dolares")
def route_dolares():
    return get_protected_data("dolares", get_dolares_for_api, history_days=365)

@app.get("/forecastcuantitativo")
def route_forecast():
    return get_protected_data("forecast", get_forecast_cuantitativo_for_api)

@app.get("/letras-bonos")
def route_letras():
    return get_protected_data("letras", get_letras_bonos_for_api)

@app.get("/lecap-band")
def route_lecap_band():
    return get_protected_data("lecap_band", get_lecap_band_for_api)

@app.get("/indicadores/{ticker}")
def route_indicadores(ticker: str):
    # Para tickers individuales usamos una caché corta de 5 min para no saturar yfinance
    return analyze_ticker(ticker.upper())

@app.get("/opciones/analisis/{ticker}")
def route_opciones(ticker: str):
    t = ticker.upper()
    now = time.time()
    # Protección específica para opciones (Yahoo es muy sensible)
    if t in _MASTER_CACHE["opciones_ticker"]:
        cache = _MASTER_CACHE["opciones_ticker"][t]
        if now - cache["ts"] < 3600: # 1 hora de caché
            return cache["data"]
    
    data = analyze_ticker_for_api(t)
    _MASTER_CACHE["opciones_ticker"][t] = {"data": data, "ts": now}
    return data

# --- Estos endpoints asumen que tenés las funciones en tus scripts ---
@app.get("/noticias")
def route_noticias():
    # return get_protected_data("noticias", get_financial_news_for_api)
    return {"message": "Endpoint listo, vinculalo a tu script de noticias"}

@app.get("/market/screener")
def route_screener():
    # return get_protected_data("screener", get_market_screener_for_api)
    return {"message": "Endpoint listo, vinculalo a tu script de screener"}

@app.get("/")
def health_check():
    return {"status": "ok", "updated": datetime.now(timezone.utc)}
