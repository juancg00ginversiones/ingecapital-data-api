import requests
import json
import pandas as pd
import numpy as np
from datetime import datetime
from scipy.optimize import newton

# CONFIGURACIÓN
URL_PRECIOS_ONS = "https://data912.com/live/arg_corp"
# Aquí asumo que ya tenés una función o endpoint para el MEP
URL_API_DOLAR = "https://tu-api-datosargentina.com/api/dolar" 

def obtener_dolar_mep():
    try:
        # Usamos tu lógica de la API de datosargentina
        r = requests.get(URL_API_DOLAR)
        data = r.json()
        # Ajustar según la estructura de tu JSON de dólar
        return float(data['blue']['value_sell']) # Ejemplo: si usas blue o mep
    except Exception as e:
        print(f"Error obteniendo dólar: {e}")
        return 1300.0  # Valor de respaldo (fallback)

def calcular_tir_on(precio_usd, flujos):
    fecha_hoy = datetime.now()
    flujos_futuros = []
    
    for f in flujos:
        fecha_pago = datetime.strptime(f['fecha'], '%Y-%m-%d')
        # Solo tomamos flujos que no vencieron
        if fecha_pago > fecha_hoy:
            dias = (fecha_pago - fecha_hoy).days
            flujos_futuros.append([dias / 365.25, f['flujo_calc']])
    
    if not flujos_futuros or precio_usd <= 0:
        return 0.0

    # Función de Valor Presente Neto
    def npv(rate):
        return sum(f[1] / (1 + rate)**f[0] for f in flujos_futuros) - precio_usd

    try:
        # Buscamos la tasa que hace el NPV = 0
        return newton(npv, 0.1) * 100
    except:
        return 0.0

def procesar_panel_ons():
    # 1. Cargamos el cashflow completo que generamos en Colab
    try:
        with open('cashflow_ons.json', 'r') as f:
            cash_data = json.load(f)
            cashflows = cash_data['ons']
    except FileNotFoundError:
        print("Error: No se encontró cashflow_ons.json")
        return []

    # 2. Obtenemos precios de data912 y el dólar actual
    try:
        res = requests.get(URL_PRECIOS_ONS)
        precios_data = res.json()
        mep = obtener_dolar_mep()
        print(f"Cotización Dólar utilizada: ${mep}")
    except Exception as e:
        print(f"Error de conexión: {e}")
        return []

    resultados = []

    # 3. Mapeo y Cálculo
    for item in precios_data:
        ticker = item['symbol']
        
        # Filtramos: Solo si el ticker existe en nuestro JSON de flujos
        if ticker in cashflows:
            # SIEMPRE dividimos por dólar como pediste
            precio_pesos = float(item['c']) 
            precio_usd = precio_pesos / mep
            
            # Calculamos TIR con el precio ya convertido
            tir = calcular_tir_on(precio_usd, cashflows[ticker])
            
            # Calculamos la duración (opcional, similar a DM en bonos)
            # tir_decimal = tir / 100
            
            resultados.append({
                "ticker": ticker,
                "precio_pesos": precio_pesos,
                "precio_usd": round(precio_usd, 2),
                "tir": round(tir, 2),
                "variacion": item['pct_change'],
                "actualizado": datetime.now().strftime("%H:%M:%S")
            })

    return resultados

if __name__ == "__main__":
    panel_final = procesar_panel_ons()
    # Esto es lo que devolvería tu API para el frontend
    print(json.dumps(panel_final, indent=2))
