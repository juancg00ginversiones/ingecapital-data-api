from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware

from market912 import fetch_market912
from docta_services import (
    get_cashflow,
    get_yields_intraday,
    get_yields_historical,
    run_pricer
)

from curvas_opciones import analyze_ticker_for_api, LISTA_TICKERS

app = FastAPI(title="Ingecapital Data API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def home():
    return {"status": "API funcionando OK"}

# =====================
# MARKET DATA
# =====================

@app.get("/market/912")
def market_data():
    return fetch_market912()

# =====================
# DOCTA – BONOS
# =====================

@app.get("/bonds/{ticker}/cashflow")
def cashflow(ticker: str):
    return get_cashflow(ticker.upper())

@app.get("/bonds/{ticker}/yields/intraday")
def yields_intraday(ticker: str):
    return get_yields_intraday(ticker.upper())

@app.get("/bonds/{ticker}/yields/historical")
def yields_historical(ticker: str):
    return get_yields_historical(ticker.upper())

@app.get("/bonds/{ticker}/pricer")
def pricer(
    ticker: str,
    target: str = Query("price"),
    value: float = Query(65)
):
    return run_pricer(ticker.upper(), target, value)

# =====================
# OPCIONES (SE MANTIENE)
# =====================

@app.get("/curvas/opciones/lista")
def lista_opciones():
    return {"tickers": LISTA_TICKERS}

@app.get("/curvas/opciones")
def opciones(ticker: str):
    return analyze_ticker_for_api(ticker.upper())


