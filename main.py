import os
import uvicorn
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional

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

@app.head("/")
def root_head():
    return {}

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
# MARKET SCREENER
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
# CURVAS / OPCIONES
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
            raise HTTPException(status_code=400, detail=f"Ticker '{t}' no permitido.")
        return analyze_ticker_for_api(t)
    except HTTPException:
        raise
    except Exception as e:
        print("[ERROR /curvas/opciones]", repr(e))
        raise HTTPException(status_code=500, detail=f"Error interno en curvas/opciones: {str(e)}")

# ============================================================
# OPCIONES - ESTRUCTURA DE MERCADO
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
# LECAPS / BONCAP
# ============================================================
@app.get("/letras-bonos")
def letras_bonos():
    try:
        from letras_bonos_engine import get_letras_bonos_for_api
        return get_letras_bonos_for_api()
    except Exception as e:
        print("[ERROR /letras-bonos]", repr(e))
        raise HTTPException(status_code=500, detail=f"Error interno en letras-bonos: {str(e)}")

@app.get("/lecap-band")
def lecap_band(
    inflacion_mensual: float = Query(0.0, description="Inflación mensual proyectada")
):
    try:
        from lecap_band_engine import get_lecap_band_for_api
        return get_lecap_band_for_api(inflacion_mensual=inflacion_mensual)
    except TypeError:
        try:
            from lecap_band_engine import get_lecap_band_for_api
            return get_lecap_band_for_api()
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error interno en lecap-band: {str(e)}")
    except Exception as e:
        print("[ERROR /lecap-band]", repr(e))
        raise HTTPException(status_code=500, detail=f"Error interno en lecap-band: {str(e)}")

# ============================================================
# COTIZACIONES
# ============================================================
@app.get("/cotizaciones/{categoria}")
def cotizaciones(categoria: str):
    try:
        from cotizaciones import get_cotizaciones
        return get_cotizaciones(categoria)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        print(f"[ERROR /cotizaciones/{categoria}]", repr(e))
        raise HTTPException(status_code=500, detail=f"Error interno: {str(e)}")

# ============================================================
# CHATBOT — Groq + Llama 3.3
# ============================================================
class ChatMessage(BaseModel):
    role: str  # "user" o "assistant"
    content: str

class ChatRequest(BaseModel):
    messages: List[ChatMessage]
    context: Optional[dict] = None  # datos del mercado que manda el frontend

@app.post("/chat")
async def chat(request: ChatRequest):
    try:
        import httpx

        groq_api_key = os.environ.get("GROQ_API_KEY")
        if not groq_api_key:
            raise HTTPException(status_code=500, detail="GROQ_API_KEY no configurada")

        # Armar contexto con datos del mercado
        context_text = ""
        if request.context:
            if request.context.get("dolar"):
                dolar = request.context["dolar"]
                context_text += f"\nDatos actuales del dólar: {dolar}"
            if request.context.get("lecaps"):
                context_text += f"\nLECAPs disponibles: {request.context['lecaps']}"
            if request.context.get("bonos"):
                context_text += f"\nBonos disponibles: {request.context['bonos']}"

        system_prompt = f"""Sos el asistente financiero de IngeCapital, una plataforma de análisis de inversiones argentina.

Tu rol es ayudar a inversores argentinos con análisis de mercado, instrumentos financieros y estrategias de inversión.

DATOS DEL MERCADO EN TIEMPO REAL:
{context_text if context_text else "No hay datos de mercado disponibles en este momento."}

INSTRUCCIONES:
- Respondé siempre en español argentino (usá "vos", "tenés", etc.)
- Sé conciso y claro — máximo 3 párrafos por respuesta
- Cuando hables de rendimientos, siempre aclará que no es asesoramiento financiero
- Si te preguntan por datos específicos de mercado, usá los datos del contexto cuando estén disponibles
- Si no tenés el dato exacto, decilo honestamente
- Para instrumentos argentinos: LECAPs, BONCAPs, bonos CER, dólar MEP/CCL/Blue, CEDEARs, acciones del Merval
- Usá emojis con moderación para hacer las respuestas más amigables
- Si la pregunta es muy técnica, explicá de forma simple primero y luego el detalle

Plataforma: IngeCapital Pro | Asesor: JCG Inversiones"""

        # Armar mensajes para Groq
        groq_messages = [{"role": "system", "content": system_prompt}]
        for msg in request.messages[-10:]:  # Últimos 10 mensajes para no exceder contexto
            groq_messages.append({"role": msg.role, "content": msg.content})

        # Llamar a Groq API
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {groq_api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "llama-3.3-70b-versatile",
                    "messages": groq_messages,
                    "max_tokens": 500,
                    "temperature": 0.7,
                }
            )

        if response.status_code != 200:
            raise HTTPException(status_code=500, detail=f"Error de Groq: {response.text}")

        data = response.json()
        reply = data["choices"][0]["message"]["content"]

        return {"reply": reply, "model": "llama-3.3-70b"}

    except HTTPException:
        raise
    except Exception as e:
        print("[ERROR /chat]", repr(e))
        raise HTTPException(status_code=500, detail=f"Error en chat: {str(e)}")

# ============================================================
# START
# ============================================================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    uvicorn.run(app, host="0.0.0.0", port=port)
