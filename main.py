import os
import time
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# ============================================================
# IMPORTS CORRECTOS
# ============================================================
from bonos import get_all_bonds_for_api
from dolares import get_dolares_for_api
from noticias import get_financial_news_for_api
from forecast_cuantitativo import get_forecast_cuantitativo_for_api
from market_screener import get_market_screener_for_api
from Obligacionesnegociables import get_ons_for_api

# ============================================================
# APP
# ============================================================
app = FastAPI(
    title="INGECAPITAL DATA API",
    version="1.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================================
# CACHE SIMPLE EN MEMORIA
# ============================================================
cache_store = {}
TTL = 300  # 5 minutos

def with_cache(key, func, *args, **kwargs):
    now = time.time()
    if key in cache_store:
        entry = cache_store[key]
        if now - entry["ts"] < TTL:
            return entry["data"]

    data = func(*args, **kwargs)
    cache_store[key] = {"ts": now, "data": data}
    return data

# ============================================================
# ROUTES
# ============================================================

@app.get("/")
def health():
    return {
        "status": "online",
        "cached_endpoints": list(cache_store.keys())
    }

@app.get("/bonos")
def bonos():
    return with_cache("bonos", get_all_bonds_for_api)

@app.get("/ons")
def ons():
    return with_cache("ons", get_ons_for_api)

@app.get("/dolares")
def dolares():
    return with_cache("dolares", get_dolares_for_api, history_days=365)

@app.get("/not

