from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from curvas_opciones import analyze_ticker_for_api, LISTA_TICKERS

app = FastAPI()

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

@app.get("/tickers")
def tickers():
    return {"tickers": LISTA_TICKERS}

@app.get("/curvas/opciones")
def curvas_opciones(ticker: str):

    ticker = ticker.upper()

    if ticker not in LISTA_TICKERS:
        raise HTTPException(status_code=400, detail=f"Ticker no permitido: {ticker}")

    # === DEBUG MODE: atrapamos errores paso a paso ===
    try:
        result = analyze_ticker_for_api(ticker)
        return result

    except Exception as e:
        # Log detallado para ver en Render qué está pasando
        return {
            "error": "Exception inside analyze_ticker_for_api",
            "message": str(e),
            "type": type(e).__name__
        }

