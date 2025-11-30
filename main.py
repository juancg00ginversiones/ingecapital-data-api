from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional

# ====== ARCHIVOS ORIGINALES ======
from calculadora import calcular_todo, curva_AL, curva_GD
from curvas_opciones import analyze_ticker_for_api, LISTA_TICKERS

# ====== CONTENIDO PRO (memoria) ======
CONTENIDO_PRO = []


# ============================================================
# FASTAPI
# ============================================================
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# HOME
# ============================================================
@app.get("/")
def home():
    return {"status": "API funcionando"}


# ============================================================
# RUTAS ORIGINALES (NO TOCAR)
# ============================================================
@app.get("/bonos")
def bonos():
    return calcular_todo()

@app.get("/curva/al")
def curva_al():
    return curva_AL()

@app.get("/curva/gd")
def curva_gd():
    return curva_GD()


# ============================================================
# OPCIONES
# ============================================================
@app.get("/curvas/opciones/lista")
def lista_opciones():
    return {"tickers": LISTA_TICKERS}


@app.get("/curvas/opciones")
def curvas_opciones(ticker: str = Query(...)):
    t = ticker.upper().strip()
    if t not in LISTA_TICKERS:
        raise HTTPException(
            status_code=400,
            detail=f"Ticker {t} no permitido. Use uno de: {', '.join(LISTA_TICKERS)}"
        )

    try:
        return analyze_ticker_for_api(t)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error interno: {e}")


# ============================================================
# PRO – CONTENIDO (VERSION JSON ESTABLE)
# ============================================================

@app.get("/pro/contenido")
def leer_contenido():
    return CONTENIDO_PRO


@app.post("/pro/contenido")
def agregar_contenido(data: dict):
    """
    Formato JSON esperado:
    {
        "texto": "...",
        "link": "https://x.com/...."
    }
    """
    from datetime import date

    texto = data.get("texto")
    link = data.get("link")

    if not texto:
        raise HTTPException(status_code=400, detail="El campo 'texto' es obligatorio")

    nuevo = {
        "texto": texto,
        "link": link,
        "fecha": date.today().isoformat()
    }

    CONTENIDO_PRO.append(nuevo)
    return {"status": "ok", "added": nuevo}

