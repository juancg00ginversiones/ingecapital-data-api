import os
import uvicorn
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

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
# HEALTH
# ============================================================
@app.get("/")
def root():
    return {
        "ok": True,
        "service": "ingecapital-data-api",
        "mode": "no-cache"
    }

@app.get("/test")
def test():
    return {
        "ok": True,
        "message": "Endpoint /test funcionando correctamente",
        "service": "ingecapital-data-api"
    }

# ============================================================
# BONOS SOBERANOS
# ============================================================
@app.get("/bonos")
def bonos():
    try:
        from bonos import get_all_bonds_for_api
        return get_all_bonds_for_api()
    except Exception as e:
        print("[ERROR /bonos]", repr(e))
        raise HTTPException(status_code=500, detail=f"Error interno en bonos: {str(e)}")

# ============================================================
# OBLIGACIONES NEGOCIABLES (ONs)
# ============================================================
@app.get("/ons")
def ons():
    try:
        from Obligacionesnegociables import get_ons_for_api
        return get_ons_for_api()
    except Exception as e:
        print("[ERROR /ons]", repr(e))
        raise HTTPException(status_code=500, detail=f"Error interno en ons: {str(e)}")

# ============================================================
# DÓLARES
# ============================================================
@app.get("/dolares")
def dolares(history_days: int = 365):
    try:
        from dolares import get_dolares_for_api
        return get_dolares_for_api(history_days=history_days)
    except Exception as e:
        print("[ERROR /dolares]", repr(e))
        raise HTTPException(status_code=500, detail=f"Error interno en dolares: {str(e)}")

# ============================================================
# NOTICIAS
# ============================================================
@app.get("/noticias")
def noticias():
    try:
        from noticias import get_financial_news_for_api
        return get_financial_news_for_api()
    except Exception as e:
        print("[ERROR /noticias]", repr(e))
        raise HTTPException(status_code=500, detail=f"Error interno en noticias: {str(e)}")

# ============================================================
# FORECAST CUANTITATIVO
# ============================================================
@app.get("/forecastcuantitativo")
def forecast_cuantitativo():
    try:
        from forecast_cuantitativo import get_forecast_cuantitativo_for_api
        return get_forecast_cuantitativo_for_api()
    except Exception as e:
        print("[ERROR /forecastcuantitativo]", repr(e))
        raise HTTPException(status_code=500, detail=f"Error interno en forecastcuantitativo: {str(e)}")

# ============================================================
# MARKET SCREENER (heatmap / sectores)
# ============================================================
@app.get("/market/screener")
def market_screener():
    try:
        from market_screener import get_market_screener_for_api
        return get_market_screener_for_api()
    except Exception as e:
        print("[ERROR /market/screener]", repr(e))
        raise HTTPException(status_code=500, detail=f"Error interno en market/screener: {str(e)}")

# ============================================================
# CURVAS / OPCIONES (DERIBIT + YFIN)
# ============================================================
@app.get("/curvas/opciones/lista")
def lista_opciones():
    try:
        from curvas_opciones import LISTA_TICKERS
        return {"tickers": LISTA_TICKERS, "total": len(LISTA_TICKERS)}
    except Exception as e:
        print("[ERROR /curvas/opciones/lista]", repr(e))
        raise HTTPException(status_code=500, detail=f"Error interno en curvas/opciones/lista: {str(e)}")

@app.get("/curvas/opciones")
def curvas_opciones(ticker: str = Query(..., description="Ticker permitido")):
    try:
        from curvas_opciones import analyze_ticker_for_api, LISTA_TICKERS

        t = ticker.upper().strip()
        if t not in LISTA_TICKERS:
            raise HTTPException(
                status_code=400,
                detail=f"Ticker '{t}' no permitido. Use uno de: {', '.join(LISTA_TICKERS)}"
            )

        return analyze_ticker_for_api(t)

    except HTTPException:
        raise
    except Exception as e:
        print("[ERROR /curvas/opciones]", repr(e))
        raise HTTPException(status_code=500, detail=f"Error interno en curvas/opciones: {str(e)}")

# ============================================================
# OPCIONES - ESTRUCTURA DE MERCADO (gamma, iv, etc.)
# ============================================================
@app.get("/opciones/estructura")
def opciones_estructura():
    try:
        from opciones_estructura import get_options_structure_for_api
        return get_options_structure_for_api()
    except Exception as e:
        print("[ERROR /opciones/estructura]", repr(e))
        raise HTTPException(status_code=500, detail=f"Error interno en opciones/estructura: {str(e)}")

# ============================================================
# LECAPS / BONCAP - CALCULADORA (letras_bonos_engine)
# ============================================================
@app.get("/letras-bonos")
def letras_bonos():
    try:
        from letras_bonos_engine import get_letras_bonos_for_api
        return get_letras_bonos_for_api()
    except Exception as e:
        print("[ERROR /letras-bonos]", repr(e))
        raise HTTPException(status_code=500, detail=f"Error interno en letras-bonos: {str(e)}")

# ============================================================
# BANDA LECAPS (lecap_band_engine)
# ============================================================
@app.get("/lecap-band")
def lecap_band(
    inflacion_mensual: float = Query(0.0, description="Inflación mensual proyectada (ej: 0.03 para 3%)")
):
    """
    Devuelve:
    - banda proyectada (para graficar en Horizons)
    - puntos de lecaps
    - tabla de breakevens y escenarios
    """
    try:
        from lecap_band_engine import get_lecap_band_for_api
        # Si tu engine acepta parámetro, pasalo; si no, lo ignora o lo adaptamos después.
        return get_lecap_band_for_api(inflacion_mensual=inflacion_mensual)
    except TypeError:
        # fallback si la función no acepta el parámetro todavía
        try:
            from lecap_band_engine import get_lecap_band_for_api
            return get_lecap_band_for_api()
        except Exception as e:
            print("[ERROR /lecap-band fallback]", repr(e))
            raise HTTPException(status_code=500, detail=f"Error interno en lecap-band: {str(e)}")
    except Exception as e:
        print("[ERROR /lecap-band]", repr(e))
        raise HTTPException(status_code=500, detail=f"Error interno en lecap-band: {str(e)}")

# ============================================================
# START
# ============================================================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    uvicorn.run(app, host="0.0.0.0", port=port)

