import os
import uvicorn
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional

app = FastAPI(title="INGECAPITAL DATA API", version="1.0")

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
    return {"ok": True, "service": "ingecapital-data-api", "mode": "no-cache"}

@app.head("/")
def root_head():
    return {}

@app.get("/test")
def test():
    return {"ok": True, "message": "Endpoint /test funcionando", "service": "ingecapital-data-api"}

# ============================================================
# BONOS
# ============================================================
@app.get("/bonos")
def bonos():
    try:
        from bonos import get_all_bonds_for_api
        return get_all_bonds_for_api()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error interno en bonos: {str(e)}")

# ============================================================
# ONs
# ============================================================
@app.get("/ons")
def ons():
    try:
        from Obligacionesnegociables import get_ons_for_api
        return get_ons_for_api()
    except Exception as e:
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
        raise HTTPException(status_code=500, detail=f"Error interno en noticias: {str(e)}")

# ============================================================
# FORECAST
# ============================================================
@app.get("/forecastcuantitativo")
def forecast_cuantitativo():
    try:
        from forecast_cuantitativo import get_forecast_cuantitativo_for_api
        return get_forecast_cuantitativo_for_api()
    except Exception as e:
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
        raise HTTPException(status_code=500, detail=f"Error interno: {str(e)}")

@app.get("/curvas/opciones")
def curvas_opciones(ticker: str = Query(...)):
    try:
        from curvas_opciones import analyze_ticker_for_api, LISTA_TICKERS
        t = ticker.upper().strip()
        if t not in LISTA_TICKERS:
            raise HTTPException(status_code=400, detail=f"Ticker '{t}' no permitido.")
        return analyze_ticker_for_api(t)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error interno: {str(e)}")

# ============================================================
# OPCIONES ESTRUCTURA
# ============================================================
@app.get("/opciones/estructura")
def opciones_estructura():
    try:
        from opciones_estructura import get_options_structure_for_api
        return get_options_structure_for_api()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error interno: {str(e)}")

# ============================================================
# LECAPS
# ============================================================
@app.get("/letras-bonos")
def letras_bonos():
    try:
        from letras_bonos_engine import get_letras_bonos_for_api
        return get_letras_bonos_for_api()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error interno: {str(e)}")

@app.get("/lecap-band")
def lecap_band(inflacion_mensual: float = Query(0.0)):
    try:
        from lecap_band_engine import get_lecap_band_for_api
        return get_lecap_band_for_api(inflacion_mensual=inflacion_mensual)
    except TypeError:
        try:
            from lecap_band_engine import get_lecap_band_for_api
            return get_lecap_band_for_api()
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error interno: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error interno: {str(e)}")

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
        raise HTTPException(status_code=500, detail=f"Error interno: {str(e)}")

# ============================================================
# CHATBOT — Groq + Llama 3.3
# ============================================================

GLOSARIO = """
GLOSARIO FINANCIERO COMPLETO:
- Acción: Parte del capital de una empresa. Al comprarla, sos dueño de una porción de la compañía.
- ADR: Certificado que permite comprar acciones de empresas extranjeras en bolsas de EE.UU.
- Análisis Técnico: Estudia gráficos de precios para predecir movimientos del mercado.
- Análisis Fundamental: Evalúa la salud financiera de una empresa para determinar si está cara o barata.
- Apalancamiento: Usar deuda para financiar inversiones, amplificando ganancias y pérdidas.
- Bear Market: Período de caída sostenida de precios (más del 20%). Pesimismo en el mercado.
- BONCAP: Bono del Tesoro capitalizable en pesos, similar a la LECAP pero de mayor plazo.
- Bono: Instrumento de deuda. Al comprarlo le prestás dinero al emisor a cambio de intereses.
- Bono Bullet: Paga intereses periódicamente y devuelve todo el capital al vencimiento.
- Bull Market: Período de suba sostenida de precios. Optimismo en el mercado.
- Cartera: Conjunto de inversiones de una persona. Diversificarla reduce el riesgo.
- Cauciones: Préstamos a muy corto plazo (1-7 días) garantizados con títulos. Muy seguras.
- CEDEAR: Certificado que permite invertir en acciones extranjeras (Apple, Google, Tesla) desde Argentina en pesos.
- CER: Índice que ajusta instrumentos según la inflación. Protege el poder adquisitivo.
- Cuenta Comitente: Cuenta de inversión necesaria para operar en el mercado de capitales.
- Diversificar: Distribuir el dinero en diferentes activos para reducir el riesgo.
- Dividendos: Parte de las ganancias que una empresa reparte entre sus accionistas.
- Dólar Blue: Tipo de cambio informal, no oficial.
- Dólar MEP (Bolsa): Compra un bono en pesos y lo vendés en dólares. 100% legal.
- Dólar CCL (Cable): Permite transferir dólares al exterior mediante compra/venta de bonos. Legal.
- Dólar Linked: Instrumentos en pesos atados al tipo de cambio oficial. Cobertura ante devaluación.
- Duration: Medida de sensibilidad de un bono a cambios en las tasas de interés. A mayor duration, mayor riesgo de tasa.
- EBITDA: Ganancia antes de intereses, impuestos, depreciaciones y amortizaciones.
- ETF: Fondo que cotiza en bolsa como una acción y replica un índice como el S&P 500.
- Futuros: Contrato para comprar/vender un activo a precio y fecha futuros. Cobertura o especulación.
- Gamma Flip: Nivel de precio donde cambia el régimen de volatilidad del mercado de opciones.
- Inflación: Aumento generalizado de precios. Erosiona el poder adquisitivo del dinero.
- Interés Compuesto: Interés sobre el capital más intereses acumulados. Efecto 'bola de nieve'.
- IPC: Índice de Precios al Consumidor. Principal medida de la inflación.
- LECAP: Letra del Tesoro capitalizable en pesos. Instrumento de corto plazo, tasa fija.
- Liquidez: Facilidad para convertir un activo en efectivo sin perder valor.
- Merval: Principal índice bursátil de Argentina.
- Obligaciones Negociables (ONs): Bonos emitidos por empresas privadas. Le prestás a una empresa.
- Opciones: Contratos que dan el derecho (no obligación) de comprar/vender un activo a cierto precio.
- Paridad: Relación entre precio de mercado de un bono y su valor técnico. Bajo 100% = bajo la par.
- Put Wall: Nivel con mayor concentración de puts. Actúa como soporte fuerte del mercado.
- Call Wall: Nivel con mayor concentración de calls. Actúa como resistencia fuerte del mercado.
- Renta Fija: Inversión con flujos conocidos de antemano (bonos, plazos fijos).
- Renta Variable: Inversión con rentabilidad incierta (acciones). Mayor riesgo, mayor potencial.
- RSI: Indicador técnico de 0 a 100. Por encima de 70 sobrecomprado, por debajo de 30 sobrevendido.
- MACD: Indicador de momentum. Cruce de medias móviles para detectar cambios de tendencia.
- S&P 500: Índice de las 500 empresas más grandes de EE.UU. Termómetro del mercado global.
- Spread: Diferencia entre precio de compra y venta. También diferencial de tasas entre bonos.
- TAMAR: Tasa de referencia variable argentina, promedio de tasas de plazos fijos bancarios.
- TEA: Tasa Efectiva Anual. Mide el rendimiento real en un año incluyendo capitalización.
- TEM: Tasa Efectiva Mensual.
- TIR (YTM): Tasa Interna de Retorno. Rentabilidad esperada de un bono si se mantiene al vencimiento.
- TNA: Tasa Nominal Anual. No incluye capitalización.
- Títulos Públicos: Deuda emitida por el gobierno nacional, provincial o municipal.
- UVA: Unidad ajustada por inflación (CER). Usada en créditos y depósitos.
- VAN: Valor Actual Neto. Si es positivo, la inversión es rentable.
- Valor Técnico: Para un bono, es el valor residual más intereses corridos.
"""

FUNCIONALIDADES_PLATAFORMA = """
FUNCIONALIDADES DE INGECAPITAL:

VERSIÓN GRATUITA (para todos):
- Cotizaciones en Detalle: Precios en tiempo real de acciones AR, CEDEARs, bonos, ONs, letras y acciones USA
- Calculadora de Cauciones: Calcula resultados de operar cauciones
- Renta Fija en Pesos: LECAPs, BONCAPs, Bonos CER, TAMAR - rendimientos y tasas actualizadas
- Curva de LECAPs: Visualización de tasas vs vencimientos y proyección de banda cambiaria
- Tasas de Plazo Fijo: Comparativa de TNA de principales bancos argentinos
- Variables Macro: Inflación, Riesgo País, datos macroeconómicos de Argentina y USA
- Dólar y Mercado Cambiario: Cotizaciones en tiempo real del Blue, MEP, CCL, Oficial con histórico
- Cartera de Retiro: Proyección de jubilación e interés compuesto

VERSIÓN PRO (exclusiva para clientes JCG):
- Forecast Cuantitativo: Modelos predictivos con fan charts para SPY, QQQ, BTC, acciones y más
- Mapa de Mercado Global: Heat map de sectores y rendimientos por categoría
- Market Screener Técnico: Scanner con RSI, SMAs y variaciones por sector en tiempo real
- Fondos de Inversión: Explorador de FCI clasificados por objetivo, riesgo y horizonte
- Portafolios Sugeridos: Carteras temáticas por perfil de riesgo
- Niveles de Opciones: Put/Call Walls, Gamma Flip, Max Pain para SPY, QQQ, IWM, IBIT
- Calculadora de Bonos Pro: TIR histórica, flujo de fondos, análisis de sensibilidad
- Calculadora de ONs: TIR, Duration y Paridad de Obligaciones Negociables
- Calculadora de Opciones: Black-Scholes y análisis de griegas
- Análisis de Futuros: Curvas forward y proyecciones macro USA
- Mi Cartera: Portfolio personal con seguimiento de posiciones y rendimientos
- Dashboard JCG Inversiones: Plataforma de análisis con liquidez global, indicadores técnicos y señales
"""

SYSTEM_PROMPT = f"""Sos el asistente virtual de IngeCapital, la plataforma financiera de JCG Inversiones.

TU PERSONALIDAD:
- Hablás en español argentino casual pero profesional (usá "vos", "tenés", "andás")
- Sos copado, directo y claro — nada de respuestas aburridas o robóticas
- Usás emojis con criterio para hacer las respuestas más amigables
- Sos educativo: explicás conceptos de forma simple antes del detalle técnico
- NUNCA das recomendaciones de inversión específicas — eso es trabajo del equipo de JCG
- Siempre terminás con un gancho hacia el asesoramiento personalizado de JCG

TU MISIÓN:
1. Dar un panorama actual del mercado usando los datos disponibles
2. Explicar conceptos financieros de forma clara y didáctica
3. Orientar sobre las herramientas de la plataforma
4. Derivar al equipo de JCG para decisiones de inversión

CONTACTO JCG INVERSIONES:
- Web: jcginversiones.com
- Instagram: @jcg_strategic (https://www.instagram.com/jcg_strategic/)
- WhatsApp: +54 11 6978-7999 (https://wa.me/5491169787999)
- Para asesoramiento personalizado: https://wa.me/5491169787999?text=Hola%2C%20quiero%20asesoramiento%20de%20inversión

REGLAS IMPORTANTES:
- Máximo 3 párrafos por respuesta, sé conciso
- Si te preguntan qué instrumento comprar: explicá las opciones, sus características, y derivá a JCG
- Si te preguntan sobre la plataforma: explicá la funcionalidad y cómo acceder
- Si te preguntan un concepto: explicalo con un ejemplo concreto argentino
- Si no sabés algo: decilo honestamente y sugerí consultar con JCG

{GLOSARIO}

{FUNCIONALIDADES_PLATAFORMA}
"""

class ChatMessage(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    messages: List[ChatMessage]
    context: Optional[dict] = None

@app.post("/chat")
async def chat(request: ChatRequest):
    try:
        import httpx

        groq_api_key = os.environ.get("GROQ_API_KEY")
        if not groq_api_key:
            raise HTTPException(status_code=500, detail="GROQ_API_KEY no configurada")

        # Armar contexto de mercado
        context_text = ""
        if request.context:
            d = request.context
            if d.get("dolar"):
                mep  = d["dolar"].get("mep", "N/D")
                blue = d["dolar"].get("blue", "N/D")
                context_text += f"\n📊 DATOS DEL MERCADO HOY:\n- Dólar MEP: ${mep}\n- Dólar Blue: ${blue}\n"
            if d.get("lecaps"):
                context_text += "\n📋 LECAPs vigentes:\n"
                for l in d["lecaps"]:
                    context_text += f"  • {l.get('especie','?')} — Precio: ${l.get('precio','?')} | TEM: {l.get('tem','?')}% | TEA: {l.get('tea','?')}% | Vence: {l.get('fecha_pago','?')}\n"
            if d.get("boncaps"):
                context_text += "\n📋 BONCAPs vigentes:\n"
                for b in d["boncaps"]:
                    context_text += f"  • {b.get('especie','?')} — Precio: ${b.get('precio','?')} | TEM: {b.get('tem','?')}% | Vence: {b.get('fecha_pago','?')}\n"
            if d.get("screener"):
                context_text += f"\n📈 Screener de mercado disponible con datos técnicos de múltiples sectores.\n"
            if d.get("opciones"):
                context_text += f"\n⚡ Datos de opciones disponibles: Put Wall, Call Wall, Gamma Flip para índices USA.\n"

        system_with_context = SYSTEM_PROMPT
        if context_text:
            system_with_context += f"\n\nDATA EN TIEMPO REAL DISPONIBLE PARA ESTA CONSULTA:{context_text}"

        # Armar mensajes
        groq_messages = [{"role": "system", "content": system_with_context}]
        for msg in request.messages[-10:]:
            groq_messages.append({"role": msg.role, "content": msg.content})

        # Llamar a Groq
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
                    "max_tokens": 600,
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
