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
GLOSARIO FINANCIERO ARGENTINO:
- LECAP: Letra del Tesoro capitalizable en pesos. Tasa fija, corto plazo. El interés se cobra al vencimiento junto al capital.
- BONCAP: Bono del Tesoro capitalizable en pesos. Similar a LECAP pero de mayor plazo (más de 1 año).
- Bono CER: Ajusta por inflación (índice CER). TIR negativa = rinde por debajo de la inflación esperada. Cobertura inflacionaria.
- TAMAR: Tasa variable referenciada al promedio de tasas de plazos fijos bancarios. Rinde más si sube la tasa.
- Bono Dual: Paga el mayor entre tasa fija y TAMAR. Mejor de dos mundos.
- TEM: Tasa Efectiva Mensual. Rendimiento real por mes.
- TEA: Tasa Efectiva Anual. Rendimiento real por año incluyendo capitalización.
- TNA: Tasa Nominal Anual. Sin capitalización, solo referencial.
- TIR: Tasa Interna de Retorno. Rendimiento esperado si se mantiene el bono al vencimiento.
- Duration (DM): Sensibilidad del precio del bono a cambios en tasas. A mayor duration, mayor riesgo de tasa.
- Dólar MEP (Bolsa): Compra bono en pesos, lo vendés en dólares dentro del mercado local. 100% legal, sin límite.
- Dólar CCL (Cable): Igual que MEP pero los dólares quedan en cuenta del exterior.
- Dólar Blue: Mercado informal. Ilegal pero muy usado como referencia.
- Carry Trade: Estrategia de invertir en pesos (LECAPs) apostando a que el dólar no sube más que el rendimiento en $.
- Caución: Préstamo a cortísimo plazo (1-7 días) garantizado con títulos. Muy seguro y líquido.
- CEDEAR: Certificado que permite invertir en acciones extranjeras (NVDA, AAPL) desde Argentina en pesos.
- Acción AR: Acción de empresa argentina que cotiza en BYMA (Bolsa argentina).
- ADR: Certificado de empresa argentina que cotiza en bolsas de EE.UU. (GGAL, YPF, etc.)
- ON (Obligación Negociable): Bono emitido por empresa privada argentina. Le prestás a una empresa.
- FCI: Fondo Común de Inversión. Patrimonio administrado por profesionales. Ideal para principiantes.
- Merval: Principal índice bursátil argentino.
- S&P 500: Índice de las 500 empresas más grandes de EE.UU.
- Gamma Flip: Nivel de precio del SPY donde cambia el régimen de volatilidad. Por encima = mercado calmo. Por debajo = caos.
- Call Wall: Nivel con mayor concentración de calls. Actúa como resistencia fuerte.
- Put Wall: Nivel con mayor concentración de puts. Actúa como soporte fuerte.
- RSI: Indicador técnico 0-100. Encima de 70 = sobrecomprado. Debajo de 30 = sobrevendido.
- MACD: Indicador de momentum. Cruce de medias móviles para detectar cambios de tendencia.
- Riesgo País: Spread en puntos básicos sobre bonos del Tesoro USA. Mide riesgo de default soberano.
- IPC: Índice de Precios al Consumidor. Mide la inflación mensual.
- BCRA: Banco Central de la República Argentina.
- YTD: Year to Date. Rendimiento desde el 1 de enero hasta hoy.
- Paridad: Para bonos, relación entre precio de mercado y valor nominal. Bajo 100% = cotiza bajo la par.
- Valor Técnico: Capital residual + intereses corridos de un bono. Su valor contable.
- Interés Compuesto: Interés sobre capital + intereses acumulados. Efecto bola de nieve.
- Diversificación: Distribuir el capital en distintos activos para reducir el riesgo.
- Volatilidad: Variación del precio de un activo. Mayor volatilidad = mayor riesgo y oportunidad.
- Liquidez: Facilidad para convertir un activo en efectivo sin perder valor.
"""

FUNCIONALIDADES = """
FUNCIONALIDADES DE INGECAPITAL:

VERSIÓN GRATUITA (para todos):
1. Cotizaciones en Detalle: Precios en tiempo real de acciones AR, CEDEARs, bonos, ONs, letras y acciones USA
2. Calculadora de Cauciones: Calcula resultados de cauciones a distintos plazos
3. Renta Fija en Pesos: LECAPs, BONCAPs, CER, TAMAR — rendimientos, tasas y ganancia proyectada
4. Carry Trade LECAPs: Tabla con rendimiento en USD para distintos escenarios de tipo de cambio
5. Tasas de Plazo Fijo: Comparativa TNA de principales bancos argentinos
6. Variables Macro: Inflación, Riesgo País, datos macro Argentina y USA
7. Dólar y Mercado Cambiario: Blue/MEP/CCL/Oficial con histórico de 365 días
8. Cartera de Retiro: Proyección de jubilación con interés compuesto
9. Chat de IA: Asistente con datos del mercado en tiempo real

VERSIÓN PRO (gratis para clientes JCG):
1. Forecast Cuantitativo: Modelos predictivos con fan charts para SPY, QQQ, BTC y más
2. Mapa de Mercado Global: Heat map de sectores y rendimientos
3. Market Screener Técnico: Scanner con RSI, MACD, SMAs por sector en tiempo real
4. Fondos de Inversión: Explorador de FCI argentinos
5. Portafolios Sugeridos: Carteras temáticas por perfil de riesgo
6. Niveles de Opciones: Put/Call Walls, Gamma Flip, Max Pain para SPY, QQQ, IWM, IBIT
7. Calculadora de Bonos Pro: TIR, flujo de fondos, sensibilidad
8. Calculadora de ONs: TIR, Duration y Paridad
9. Mi Cartera: Portfolio personal con precios actuales y rendimiento
10. Dashboard JCG: Plataforma avanzada con liquidez global e indicadores técnicos

CÓMO ACCEDER A PRO: Siendo cliente de JCG Inversiones (sin costo adicional)
DASHBOARD JCG: $10/mes o $100/año — incluye revisión mensual de cartera con asesor
"""

SYSTEM_PROMPT_BASE = f"""Sos el asistente virtual de IngeCapital, la plataforma financiera de JCG Inversiones.

PERSONALIDAD:
- Hablás en español argentino casual y directo (vos, tenés, andás)
- Sos copado, claro y didáctico — explicás sin tecnicismos innecesarios
- Usás emojis con criterio, no en exceso
- Cuando no sabés algo, lo decís honestamente
- Siempre terminás con un gancho hacia el asesoramiento de JCG
- Hacés preguntas de seguimiento cuando la consulta es vaga

MISIÓN:
1. Explicar conceptos financieros de forma simple con ejemplos argentinos concretos
2. Dar panorama del mercado usando los datos reales disponibles en el contexto
3. Orientar sobre las herramientas de la plataforma IngeCapital
4. Derivar a JCG para decisiones de inversión personalizadas

REGLAS IMPORTANTES:
- NUNCA recomendés comprar o vender un instrumento específico
- Si te preguntan qué comprar → explicá las opciones y sus características, luego derivá a JCG
- Si hay datos de mercado en el contexto → úsalos en la respuesta con los valores reales
- Si no tenés el dato exacto → decilo honestamente y sugerí consultar con JCG
- Máximo 3 párrafos por respuesta — sé conciso y directo
- Cuando alguien pregunta algo vago → primero dá el panorama con los datos disponibles, luego preguntá si quieren profundizar

CONTACTO JCG INVERSIONES:
- WhatsApp: https://wa.me/5491169787999
- Instagram: @jcg_strategic  
- Web: jcginversiones.com

{GLOSARIO}

{FUNCIONALIDADES}"""


def armar_contexto(context: dict) -> str:
    if not context:
        return ""

    lines = ["\n📊 DATOS DEL MERCADO EN TIEMPO REAL:\n"]

    # Dólares
    if context.get("dolar"):
        d = context["dolar"]
        lines.append("💵 Tipos de cambio:")
        if d.get("mep"):     lines.append(f"  • Dólar MEP:     ${float(d['mep']):,.0f}")
        if d.get("blue"):    lines.append(f"  • Dólar Blue:    ${float(d['blue']):,.0f}")
        if d.get("ccl"):     lines.append(f"  • Dólar CCL:     ${float(d['ccl']):,.0f}")
        if d.get("oficial"): lines.append(f"  • Dólar Oficial: ${float(d['oficial']):,.0f}")

    # LECAPs
    if context.get("lecaps"):
        lines.append("\n📋 LECAPs vigentes:")
        for l in context["lecaps"]:
            lines.append(
                f"  • {l.get('especie','?')} | "
                f"Precio: ${l.get('precio','?')} | "
                f"TEM: {l.get('tem','?')}% | "
                f"TEA: {l.get('tea','?')}% | "
                f"Vence: {l.get('fecha_pago','?')} | "
                f"Días: {l.get('dm','?')}"
            )

    # BONCAPs
    if context.get("boncaps"):
        lines.append("\n📋 BONCAPs vigentes:")
        for b in context["boncaps"]:
            lines.append(
                f"  • {b.get('especie','?')} | "
                f"Precio: ${b.get('precio','?')} | "
                f"TEM: {b.get('tem','?')}% | "
                f"Vence: {b.get('fecha_pago','?')}"
            )

    # CER
    if context.get("cer"):
        lines.append("\n📋 Bonos CER vigentes:")
        for c in context["cer"]:
            tir = c.get('tir', '?')
            try:
                signo = "+" if float(tir) > 0 else ""
            except:
                signo = ""
            lines.append(
                f"  • {c.get('especie','?')} | "
                f"Precio: ${c.get('precio','?')} | "
                f"TIR: {signo}{tir}% | "
                f"Vence: {c.get('fecha_pago','?')}"
            )

    # TAMAR
    if context.get("tamar"):
        lines.append("\n📋 Bonos TAMAR:")
        for t in context["tamar"]:
            lines.append(
                f"  • {t.get('especie','?')} | "
                f"Precio: ${t.get('precio','?')} | "
                f"Spread: {t.get('spread','?')}% | "
                f"Vence: {t.get('fecha_pago','?')}"
            )

    # Screener
    if context.get("screener") and isinstance(context["screener"], dict):
        s = context["screener"]

        if s.get("adrs_arg"):
            lines.append("\n📈 ADRs argentinos (USD):")
            for x in s["adrs_arg"][:8]:
                chg = x.get('change', 0)
                try:
                    signo = "+" if float(chg) >= 0 else ""
                    lines.append(f"  • {x['ticker']}: ${x['price']} ({signo}{chg}%)")
                except:
                    lines.append(f"  • {x.get('ticker','?')}: ${x.get('price','?')}")

        if s.get("mega_tech"):
            lines.append("\n📈 Mega tecnología USA (USD):")
            for x in s["mega_tech"][:8]:
                chg = x.get('change', 0)
                try:
                    signo = "+" if float(chg) >= 0 else ""
                    lines.append(f"  • {x['ticker']}: ${x['price']} ({signo}{chg}%)")
                except:
                    lines.append(f"  • {x.get('ticker','?')}: ${x.get('price','?')}")

        if s.get("etfs_usa"):
            lines.append("\n📈 ETFs USA:")
            for x in s["etfs_usa"]:
                chg = x.get('change', 0)
                try:
                    signo = "+" if float(chg) >= 0 else ""
                    lines.append(f"  • {x['ticker']}: ${x['price']} ({signo}{chg}%)")
                except:
                    lines.append(f"  • {x.get('ticker','?')}: ${x.get('price','?')}")

    # Opciones
    if context.get("opciones") and isinstance(context["opciones"], dict):
        lines.append("\n⚡ Niveles de opciones:")
        for ticker, data in context["opciones"].items():
            if data and isinstance(data, dict):
                lines.append(
                    f"  • {ticker}: Spot ${data.get('spot','?')} | "
                    f"Call Wall: ${data.get('call_wall','?')} | "
                    f"Put Wall: ${data.get('put_wall','?')} | "
                    f"Gamma Flip: ${data.get('gamma_flip','?')} | "
                    f"Régimen: {data.get('regime','?')}"
                )

    return "\n".join(lines)


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

        # Armar contexto
        context_text = armar_contexto(request.context or {})

        system_with_context = SYSTEM_PROMPT_BASE
        if context_text:
            system_with_context += f"\n\n{context_text}"

        # Armar mensajes para Groq
        groq_messages = [{"role": "system", "content": system_with_context}]
        for msg in request.messages[-10:]:
            groq_messages.append({
                "role":    msg.role,
                "content": msg.content
            })

        # Llamar a Groq
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {groq_api_key}",
                    "Content-Type":  "application/json"
                },
                json={
                    "model":       "llama-3.3-70b-versatile",
                    "messages":    groq_messages,
                    "max_tokens":  600,
                    "temperature": 0.7,
                }
            )

        if response.status_code != 200:
            raise HTTPException(
                status_code=500,
                detail=f"Error de Groq: {response.text}"
            )

        data  = response.json()
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
