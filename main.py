from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from curvas_opciones import analyze_ticker_for_api, LISTA_TICKERS
from bonos import get_all_bonds_for_api
from dolares import get_dolares_for_api
from noticias import get_financial_news_for_api
from opciones_estructura import get_options_structure_for_api
from forecast_cuantitativo import get_forecast_cuantitativo_for_api
from letras_bonos_engine import get_letras_bonos_for_api
from market_screener import get_market_screener_for_api


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

@app.get("/")
def root():
    return {"ok": True, "service": "ingecapital-data-api"}

@app.get("/test")
def test():
    return {"ok": True}

# ================= OPCIONES =================
@app.get("/curvas/opciones/lista")
def lista_opciones():
    return {"tickers": LISTA_TICKERS, "total": len(LISTA_TICKERS)}

@app.get("/curvas/opciones")
def curvas_opciones(ticker: str = Query(...)):
    t = ticker.upper().strip()
    if t not in LISTA_TICKERS:
        raise HTTPException(status_code=400, detail="Ticker no permitido")
    return analyze_ticker_for_api(t)

# ================= BONOS =================
@app.get("/bonos")
def bonos():
    return get_all_bonds_for_api()

# ================= DOLARES =================
@app.get("/dolares")
def dolares():
    return get_dolares_for_api(history_days=365)

# ================= NOTICIAS =================
@app.get("/noticias")
def noticias():
    return get_financial_news_for_api()

# ================= OPCIONES ESTRUCTURA =================
@app.get("/opciones/estructura")
def opciones_estructura():
    return get_options_structure_for_api()

# ================= FORECAST =================
@app.get("/forecastcuantitativo")
def forecast_cuantitativo():
    return get_forecast_cuantitativo_for_api()

# ================= MARKET SCREENER =================
@app.get("/market/screener")
def market_screener():
    return get_market_screener_for_api()
# ================= CALCULADORA LECAPS-BONCAPS =================
@app.get("/letras-bonos")
def letras_bonos():
    return get_letras_bonos_for_api()





