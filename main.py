from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Tus módulos internos
from calculadora import calcular_todo, curva_AL, curva_GD
from curvas_opciones import analyze_ticker_for_api, LISTA_TICKERS
from contenido_pro import agregar_contenido_pro, obtener_contenido_pro

# ============================================
# MODELO PARA CONTENIDO PRO
# ============================================
class ContenidoPRO(BaseModel):
    titulo: str
    texto: str
    imagen_url: str | None = None
    fecha: str | None = None


# ============================================
# INICIAR APP
# ============================================
app = FastAPI()

# ============================================
# CORS ESTABLE PARA HTML LOCAL
# ============================================
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "*",
        "null",
        "file://"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================
# ENDPOINT PRINCIPAL
# ============================================
@app.get("/")
def home():
    return {"status": "API funcionando"}

# ============================================
# ENDPOINTS BONOS
# ============================================
@app.get("/bonos")
def bonos():
    return calcular_todo()

@app.get("/curva/al")
def curva_al():
    return curva_AL()

@app.get("/curva/gd")
def curva_gd():
    return curva_GD()

# ============================================
# CURVAS DE OPCIONES
# ============================================
@app.get("/tickers")
def tickers():
    return {"tickers": LISTA_TICKERS}

@app.get("/curvas/opciones")
def curvas_opciones(ticker: str):
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
        raise HTTPException(status_code=500, detail=f"Error interno: {str(e)}")

# ============================================
# CONTENIDO PRO (GET)
# ============================================
@app.get("/pro/contenido")
def contenido_pro_listado():
    return obtener_contenido_pro()

# ============================================
# CONTENIDO PRO (POST JSON)
# ============================================
@app.post("/pro/contenido")
def contenido_pro_agregar_endpoint(payload: ContenidoPRO):
    try:
        agregar_contenido_pro(
            payload.titulo,
            payload.texto,
            payload.imagen_url,
            payload.fecha
        )
        return {"status": "ok", "mensaje": "Contenido agregado correctamente"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al agregar contenido PRO: {str(e)}")

