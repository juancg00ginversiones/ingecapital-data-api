from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

# ============================================================
# IMPORT CURVAS OPCIONES (EXISTENTE – NO SE TOCA)
# ============================================================
from curvas_opciones import analyze_ticker_for_api, LISTA_TICKERS

# ============================================================
# IMPORT BONOS (NUEVO)
# ============================================================
from bonos import get_all_bonds_for_api
# ============================================================
# IMPORT DOLARES
# ============================================================
from dolares import get_dolares_for_api
# ============================================================
# IMPORT NOTICIAS
# ============================================================
from noticias import get_financial_news_for_api
# ============================================================
app = FastAPI(
    title="INGECAPITAL DATA API",
    version="1.0"
)

# ============================================================
# CORS
# ============================================================
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================================
# HEALTH CHECK
# ============================================================
@app.get("/")
def root():
    return {
        "ok": True,
        "service": "ingecapital-data-api"
    }

@app.get("/test")
def test():
    return {
        "ok": True,
        "message": "Endpoint /test funcionando correctamente",
        "service": "ingecapital-data-api"
    }

# ============================================================
# CURVAS DE OPCIONES (EXISTENTE – NO SE TOCA)
# ============================================================
@app.get("/curvas/opciones/lista")
def lista_opciones():
    return {
        "tickers": LISTA_TICKERS,
        "total": len(LISTA_TICKERS)
    }

@app.get("/curvas/opciones")
def curvas_opciones(
    ticker: str = Query(..., description="Ticker permitido")
):
    t = ticker.upper().strip()

    if t not in LISTA_TICKERS:
        raise HTTPException(
            status_code=400,
            detail=f"Ticker '{t}' no permitido. Use uno de: {', '.join(LISTA_TICKERS)}"
        )

    try:
        return analyze_ticker_for_api(t)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error interno en curvas_opciones: {str(e)}"
        )

# ============================================================
# BONOS SOBERANOS (NUEVO – HORIZONS)
# ============================================================
@app.get("/bonos")
def bonos():
    """
    Devuelve TODOS los bonos soberanos con:
    - precio actual
    - TIR (YTM)
    - duration
    - paridad
    - flujo de fondos
    - sensibilidad
    - TIR histórica
    """
    try:
        return get_all_bonds_for_api()
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error interno en bonos: {str(e)}"
        )

@app.get("/dolares")
def dolares():
    try:
        return get_dolares_for_api(history_days=365)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error interno en dolares: {str(e)}")
@app.get("/noticias")
def noticias():
    try:
        return get_financial_news_for_api()
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error interno en noticias: {str(e)}"
        )

