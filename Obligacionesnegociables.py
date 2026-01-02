import requests
import json
import pandas as pd
import numpy as np
from datetime import datetime
from scipy.optimize import newton

# --- CONFIGURACIÓN ---
URL_PRECIOS_ONS = "https://data912.com/live/arg_corp"
CASHFLOW_ONS_FILE = "cashflow_ons.json"

def get_ons_for_api():
    """
    Calcula el panel 'Calculadora Pro' para ONs.
    Retorna: TIR, MD, Paridad, Precio USD/Pesos y Próximo Pago.
    """
    
    # 1. Obtener Dólar MEP (Importamos desde tu bonos.py)
    try:
        from bonos import get_dolares_for_api
        dolares = get_dolares_for_api()
        # Buscamos el valor del MEP en tu estructura habitual
        mep = float(dolares.get('mep', {}).get('value', 1350.0))
    except Exception as e:
        print(f"⚠️ Error obteniendo MEP: {e}")
        mep = 1350.0

    # 2. Cargar Flujos de Fondos
    try:
        with os.path.join(os.getcwd(), CASHFLOW_ONS_FILE) as path:
             with open(CASHFLOW_ONS_FILE, "r", encoding="utf-8") as f:
                cashflows = json.load(f)["ons"]
    except:
        # Fallback por si la ruta falla en Render
        try:
            with open(CASHFLOW_ONS_FILE, "r", encoding="utf-8") as f:
                cashflows = json.load(f)["ons"]
        except Exception as e:
            return {"error": f"No se encontró {CASHFLOW_ONS_FILE}: {e}"}

    # 3. Obtener Precios Live de data912
    try:
        res = requests.get(URL_PRECIOS_ONS, timeout=10)
        precios_data = res.json()
    except Exception as e:
        return {"error": f"Error data912: {e}"}

    resultados = []
    hoy = datetime.now()

    # 4. Procesamiento por Ticker
    for item in precios_data:
        ticker = item.get("symbol")
        if ticker not in cashflows:
            continue

        p_pesos = float(item.get("c", 0))
        if p_pesos <= 0: continue
        
        # Conversión a Dólar
        p_usd = p_pesos / mep

        # Filtrar flujos futuros para TIR y Duration
        flujos_ticker = cashflows[ticker]
        futuros = []
        valor_nominal_residual = 0
        proximo_pago = "N/A"

        for f in flujos_ticker:
            f_fecha = datetime.strptime(f["fecha"], "%Y-%m-%d")
            if f_fecha > hoy:
                t = (f_fecha - hoy).days / 365.25
                futuros.append({"t": t, "monto": f["flujo_calc"]})
                if proximo_pago == "N/A":
                    proximo_pago = f["fecha"]
                if valor_nominal_residual == 0:
                    valor_nominal_residual = f["capital"]

        if not futuros: continue

        # --- CÁLCULOS FINANCIEROS ---
        try:
            def npv(r):
                return sum(f["monto"] / (1 + r)**f["t"] for f in futuros) - p_usd
            
            tir_dec = newton(npv, 0.1, maxiter=100)
            tir = round(tir_dec * 100, 2)
            
            # Modified Duration
            pv_total = sum(f["monto"] / (1 + tir_dec)**f["t"] for f in futuros)
            m_dur = sum((f["t"] * f["monto"]) / (1 + tir_dec)**f["t"] for f in futuros) / pv_total
            md = round(m_dur / (1 + tir_dec), 2)
            
            # Paridad
            paridad = round((p_usd / valor_nominal_residual) * 100, 2) if valor_nominal_residual > 0 else 0
        except:
            tir, md, paridad = 0.0, 0.0, 0.0

        resultados.append({
            "ticker": ticker,
            "precio_pesos": round(p_pesos, 2),
            "precio_usd": round(p_usd, 2),
            "tir": tir,
            "md": md,
            "paridad": paridad,
            "proximo_pago": proximo_pago,
            "variacion": item.get("pct_change", 0),
            "volumen": item.get("v", 0),
            "valor_nominal_residual": valor_nominal_residual
        })

    return sorted(resultados, key=lambda x: x['tir'], reverse=True)
