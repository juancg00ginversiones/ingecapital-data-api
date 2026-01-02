import os
import uvicorn
import time
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

# --- IMPORTACIÓN MODULAR ---
# Importamos cada función de su respectivo archivo
try:
    from bonos import (
        get_all_bonds_for_api, 
        get_dolares_for_api, 
        get_financial_news_for_api,
        analyze_ticker_for_api
    )
    from Obligacionesnegociables import get_ons_for_api
    
    # Scripts independientes (asegurate que los archivos .py existan)
    import forecastcuantitativo as forecast_script
    # import market_screener as screener_script # Descomentar si tienes el archivo
    # import letras_bonos as letras_script     # Descomentar si tienes el archivo
except ImportError as e:
    print(f"⚠️ Error cargando módulos: {e}")

app = FastAPI(title="Horizons API Pro")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- SISTEMA DE CACHÉ GLOBAL ---
cache_store = {}
TTL = 300 # 5 minutos

def con_cache(key, func, *args, **kwargs):
    now = time.time()
    if key in cache_store:
        entry = cache_store[key]
        if now - entry["ts"] < TTL:
            return entry["data"]
    
    data = func(*args, **kwargs)
    cache_store[key] = {"ts": now, "data": data}
    return data

# --- RUTAS ---

@app.get("/bonos")
def route_bonos():
    return con_cache("bonos", get_all_bonds_for_api)

@app.get("/ons")
def route_ons():
    return con_cache("ons", get_ons_for_api)

@app.get("/dolares")
def route_dolares():
    return con_cache("dolares", get_dolares_for_api, history_days=365)

@app.get("/noticias")
def route_noticias():
    return con_cache("noticias", get_financial_news_for_api)

@app.get("/forecastcuantitativo")
def route_forecast():
    # Usamos la función del script independiente
    return con_cache("forecast", forecast_script.get_forecast_cuantitativo_for_api)

@app.get("/analisis/{ticker}")
def route_analisis(ticker: str):
    # El análisis individual suele no llevar caché para permitir consultas frescas
    return analyze_ticker_for_api(ticker.upper().strip())

@app.get("/")
def health():
    return {"status": "online", "cache_keys": list(cache_store.keys())}

# --- LANZAMIENTO ---
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    uvicorn.run(app, host="0.0.0.0", port=port)
