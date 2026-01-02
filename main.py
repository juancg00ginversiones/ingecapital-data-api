import os
import uvicorn
import time
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

# --- IMPORTACIÓN UNIFICADA ---
try:
    from bonos import (
        get_all_bonds_for_api, 
        get_dolares_for_api, 
        get_financial_news_for_api,
        analyze_ticker_for_api,
        get_options_structure_for_api,
        get_forecast_cuantitativo_for_api,
        get_market_screener_for_api,
        get_letras_bonos_for_api
    )
    # Importamos la función de ONs con el nuevo nombre
    from Obligacionesnegociables import get_ons_for_api
except ImportError as e:
    print(f"⚠️ Error de importación: {e}")

app = FastAPI(title="Horizons API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- SISTEMA DE CACHÉ ---
cache_store = {}
CACHE_TTL = 300 

def con_cache(key, func, *args, **kwargs):
    now = time.time()
    if key in cache_store:
        entry = cache_store[key]
        if now - entry["ts"] < CACHE_TTL:
            return entry["data"]
    data = func(*args, **kwargs)
    cache_store[key] = {"ts": now, "data": data}
    return data

# --- RUTAS TOTALMENTE SIMÉTRICAS ---

@app.get("/bonos")
def route_bonos():
    return con_cache("bonos", get_all_bonds_for_api)

@app.get("/ons")
def route_ons():
    # Ahora sí, nombrada igual que las demás
    return con_cache("ons", get_ons_for_api)

@app.get("/dolares")
def route_dolares():
    return con_cache("dolares", get_dolares_for_api, history_days=365)

@app.get("/noticias")
def route_noticias():
    return con_cache("noticias", get_financial_news_for_api)

@app.get("/forecastcuantitativo")
def route_forecast():
    return con_cache("forecast", get_forecast_cuantitativo_for_api)

@app.get("/market/screener")
def route_screener():
    return con_cache("screener", get_market_screener_for_api)

@app.get("/letras-bonos")
def route_letras():
    return con_cache("letras", get_letras_bonos_for_api)

@app.get("/opciones/estructura")
def route_opciones():
    return con_cache("opciones", get_options_structure_for_api)

# Análisis individual (sin caché largo por ser dinámico)
@app.get("/analisis/{ticker}")
def route_analisis(ticker: str):
    return analyze_ticker_for_api(ticker.upper().strip())

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    uvicorn.run(app, host="0.0.0.0", port=port)
