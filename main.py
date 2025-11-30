from fastapi import FastAPI, Form
from fastapi.middleware.cors import CORSMiddleware
from curvas_opciones import analyze_ticker_for_api
from typing import Optional

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# HOME
@app.get("/")
def home():
    return {"status": "ok", "message": "API INGECAPITAL funcionando"}

# TICKERS DISPONIBLES
@app.get("/tickers")
def tickers():
    return ["SPY","QQQ","DIA","IWM","VIX","VXN","AAPL","MSFT","GOOGL","AMZN","META","NVDA","TSLA","BTC","ETH","TLT","IEF"]

# OPCIONES – CURVA FORWARD
@app.get("/curvas/opciones")
def curvas_opciones(ticker: str):
    return analyze_ticker_for_api(ticker.upper())

# =====================================
# PRO — CONTENIDO (JSON basado)
# =====================================
CONTENIDO_PRO = []

@app.get("/pro/contenido")
def leer_contenido():
    return CONTENIDO_PRO

@app.post("/pro/contenido")
def agregar_contenido(
    titulo: str = Form(...),
    texto: str = Form(...),
    imagen_url: Optional[str] = Form(None),
    fecha: Optional[str] = Form(None)
):
    from datetime import date

    if not fecha:
        fecha = date.today().isoformat()

    nuevo = {
        "titulo": titulo,
        "texto": texto,
        "imagen_url": imagen_url,
        "fecha": fecha
    }

    CONTENIDO_PRO.append(nuevo)
    return {"status": "ok", "added": nuevo}

