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
    Función principal que procesa el panel de Obligaciones Negociables.
    Sigue el mismo formato de nombres que bonos.py
    """
    
    # 1. Obtener el Dólar MEP (importamos la función de tu bonos.py)
    try:
        from bonos import get_dolares_for_api
        data_dolar = get_dolares_for_api()
        # Buscamos el valor del MEP (ajustar según tu estructura de retorno)
        # Típicamente: data_dolar['mep']['value'] o similar
        mep = float(data_dolar.get('mep', {}).get('value', 1300.0))
    except Exception as e:
        print(f"⚠️ No se pudo obtener MEP de bonos.py, usando fallback: {e}")
        mep = 1300.0 # Valor de respaldo

    # 2. Cargar el Cashflow de ONs
    try:
        with open(CASHFLOW_ONS_FILE, "r", encoding="utf-8") as f:
            cashflows = json.load(f)["ons"]
    except Exception as e:
        return {"error": f"No se pudo cargar {CASHFLOW_ONS_FILE}: {e}"}

    # 3. Obtener Precios en vivo
    try:
        response = requests.get(URL_PRECIOS_ONS, timeout=10)
        precios_data = response.json()
    except Exception as e:
        return {"error": f"Error al conectar con data912: {e}"}

    resultados = []
    fecha_hoy = datetime.now()

    # 4. Procesar y Calcular TIR
    for item in precios_data:
        ticker = item.get("symbol")
        
        if ticker in cashflows:
            # Tomamos el precio de cierre "c" y dividimos siempre por dólar
            precio_pesos = float(item.get("c", 0))
            if precio_pesos <= 0: continue
            
            precio_usd = precio_pesos / mep
            
            # Filtrar flujos futuros
            flujos_ticker = cashflows[ticker]
            flujos_futuros = []
            
            for f in flujos_ticker:
                f_pago = datetime.strptime(f["fecha"], "%Y-%m-%d")
                if f_pago > fecha_hoy:
                    # Calculamos fracción de año (Yearfrac)
                    t = (f_pago - fecha_hoy).days / 365.0
                    flujos_futuros.append((t, f["flujo_calc"]))
            
            if not flujos_futuros:
                tir = 0.0
            else:
                # Calcular TIR (Newton-Raphson)
                def npv(rate):
                    return sum(val / (1 + rate)**t for t, val in flujos_futuros) - precio_usd
                
                try:
                    tir = newton(npv, 0.1, maxiter=100) * 100
                except:
                    tir = 0.0

            # Armar objeto de respuesta para la API
            resultados.append({
                "ticker": ticker,
                "tipo": "ON",
                "precio_pesos": round(precio_pesos, 2),
                "precio_usd": round(precio_usd, 2),
                "tir": round(tir, 2),
                "variacion": item.get("pct_change", 0),
                "volumen": item.get("v", 0),
                "ultimo_pago": flujos_ticker[-1]["fecha"] if flujos_ticker else "N/A"
            })

    # Ordenar por TIR de mayor a menor
    return sorted(resultados, key=lambda x: x['tir'], reverse=True)

if __name__ == "__main__":
    # Prueba local
    print(json.dumps(get_ons_for_api()[:5], indent=2))
