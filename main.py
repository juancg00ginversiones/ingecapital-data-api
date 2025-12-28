from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# ============================
# IMPORTS EXISTENTES (NO TOCAR)
# ============================
from calculadora import calcular_todo, curva_AL, curva_GD
from curvas_opciones import analyze_ticker_for_api, LISTA_TICKERS

app = FastAPI(title="INGECAPITAL DATA API")

# ============================
# CORS (igual que antes)
# ============================
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================
# ENDPOINT BASE
# ============================
@app.get("/")
def home():
    return {
        "ok": True,
        "service": "ingecapital-data-api"
    }

# ============================
# TEST (NUEVO – NO ROMPE NADA)
# ============================
@app.get("/test")
def test():
    return {
        "ok": True,
        "message": "Endpoint /test funcionando correctamente",
        "service": "ingecapital-data-api"
    }

# ============================
# BONOS (IGUAL QUE ANTES)
# ============================
@app.get("/bonos")
def bonos():
    return calcular_todo()

# ============================
# CURVAS (IGUAL QUE ANTES)
# ============================
@app.get("/curva/al")
def curva_al():
    return curva_AL()

@app.get("/curva/gd")
def curva_gd():
    return curva_GD()

# =======================================
# LISTA OFICIAL DE TICKERS (OPCIONES)
# =======================================
@app.get("/curvas/opciones/lista")
def lista_opciones():
    return {
        "tickers": LISTA_TICKERS
    }

# =======================================
# ANALISIS DE OPCIONES POR TICKER
# =======================================
@app.get("/curvas/opciones")
def curvas_opciones(ticker: str = Query(..., description="Ticker permitido")):
    t = ticker.upper().strip()

    if t not in LISTA_TICKERS:
        raise HTTPException(
            status_code=400,
            detail=f"Ticker '{t}' no permitido. Use uno de: {', '.join(LISTA_TICKERS)}"
        )

    try:
        result = analyze_ticker_for_api(t)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail="Error interno en el análisis de opciones"
        )

# ===================================================
# CONTENIDO PRO (IGUAL QUE TENÍAS)
# ===================================================
contenidos = []

class Contenido(BaseModel):
    texto: str
    link: str

@app.post("/pro/contenido")
def crear_contenido(item: Contenido):
    contenidos.append(item)
    return {
        "status": "ok",
        "mensaje": "Contenido guardado",
        "data": item
    }

@app.get("/pro/contenido")
def leer_contenidos():
    return {
        "contenidos": contenidos
    }


