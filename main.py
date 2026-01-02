import os
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

# ============================================================
# IMPORTS (UNO POR UNO, CLAROS)
# ============================================================
from bonos import get_all_bonds_for_api
from dolares import get_dolares_for_api
from noticias import get_financial_news_for_api
from forecast_cuantitativo import get_forecast_cuantitativo_for_api
from market_screener import get_market_screener_for_api

# Si existe este archivo en tu repo, dejalo
try:
    from Obligacionesnegociables import get_ons_for_api
    HAS_ONS = True
except Exception as e:
    print("[WARN] Obligacionesnegociables no cargado:", e)
    HAS_ONS = False

# ============================================================
# APP
# ============================================================
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

# ============================================================
# HEALTH
# ============================================================
@app.get("/")
def root():
    return {
        "status": "online",
        "message": "API funcionando sin cache"
    }

# ============================================================
# ENDPOINTS
# ============================================================
@app.get("/bonos")
def bonos():
    try:
        return get_all_bonds_for_api()
    except Exception as e:
        print("[ERROR /bonos]", e)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/dolares")
def dolares():
    try:
        return get_dolares_for_api(history_days=365)
    except Exception as e:
        print("[ERROR /dolares]", e)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/noticias")
def noticias():
    try:
        return get_financial_news_for_api()
    except Exception as e:
        print("[ERROR /noticias]", e)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/forecastcuantitativo")
def forecast_cuantitativo():
    try:
        return get_forecast_cuantitativo_for_api()
    except Exception as e:
        print("[ERROR /forecastcuantitativo]", e)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/market/screener")
def market_screener():
    try:
        return get_market_screener_for_api()
    except Exception as e:
        print("[ERROR /market/screener]", e)
        raise HTTPException(status_code=500, detail=str(e))


if HAS_ONS:
    @app.get("/ons")
    def ons():
        try:
            return get_ons_for_api()
        except Exception as e:
            print("[ERROR /ons]", e)
            raise HTTPException(status_code=500, detail=str(e))

# ============================================================
# START
# ============================================================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    uvicorn.run(app, host="0.0.0.0", port=port)
