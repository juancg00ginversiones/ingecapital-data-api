from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from calculadora import calcular_todo, curva_AL, curva_GD
from curvas_opciones import analyze_ticker_for_api, LISTA_TICKERS

app = FastAPI()

# ============================
# CORS
# ============================
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def home():
    return {"status": "API funcionando"}


# ============================
# BONOS (YA FUNCIONA)
# ============================
@app.get("/bonos")
def bonos():
    return calcular_todo()

@app.get("/curva/al")
def curva_al():
    return curva_AL()

@app.get("/curva/gd")
def curva_gd():
    return curva_GD()


# ============================
# OPCIONES: LISTA DE TICKERS
# ============================
@app.get("/curvas/opciones/lista")
def lista_opciones():
    return {"tickers": LISTA_TICKERS}


# ============================
# OPCIONES: ANALISIS (DEBUG)
# ============================
@app.get("/curvas/opciones")
def curvas_opciones(ticker: str = Query(...)):
    t = ticker.upper().strip()

    if t not in LISTA_TICKERS:
        raise HTTPException(
            status_code=400,
            detail=f"Ticker '{t}' no permitido. Use uno de: {', '.join(LISTA_TICKERS)}"
        )

    # Ahora analyze_ticker_for_api NUNCA levanta excepción
    result = analyze_ticker_for_api(t)
    return result
