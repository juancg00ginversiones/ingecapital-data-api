import requests
import json
import os
from datetime import datetime, timedelta
from scipy.optimize import newton

# ================= CONFIG =================

URL_PRECIOS_ONS = "https://data912.com/live/arg_corp"
CASHFLOW_FILE = "cashflow_ons.json"

# =========================================


def cargar_cashflows():
    with open(CASHFLOW_FILE, "r", encoding="utf-8") as f:
        return json.load(f)["ons"]


def get_mep_usd():
    """
    Dólar MEP robusto:
    - Intenta data912
    - Fallback ArgentinaDatos histórico
    """
    try:
        r = requests.get("https://data912.com/live/mep", timeout=10)
        data = r.json()
        for item in data:
            if item.get("ticker") == "AL30":
                return float(item["ask"])
    except:
        pass

    # Fallback histórico
    r = requests.get("https://api.argentinadatos.com/v1/cotizaciones/dolares", timeout=10)
    data = r.json()
    bolsa = next(d for d in data if d["casa"] == "Bolsa")
    return float(bolsa["venta"])


def get_ons_for_api():
    hoy = datetime.now()
    mep = get_mep_usd()
    cashflows = cargar_cashflows()

    try:
        precios = requests.get(URL_PRECIOS_ONS, timeout=10).json()
    except Exception as e:
        return {"error": f"Error data912: {e}"}

    resultados = []

    for item in precios:
        ticker = item.get("symbol")
        if ticker not in cashflows:
            continue

        precio_pesos = float(item.get("c", 0))
        if precio_pesos <= 0:
            continue

        precio_usd = precio_pesos / mep

        flujos = []
        cashflow_ui = []
        valor_nominal_residual = None

        for f in cashflows[ticker]:
            fecha_raw = f["fecha"]

            # Soporte fechas Excel
            if isinstance(fecha_raw, int) or fecha_raw.isdigit():
                fecha = datetime(1899, 12, 30) + timedelta(days=int(fecha_raw))
            else:
                fecha = datetime.strptime(fecha_raw, "%Y-%m-%d")

            if fecha <= hoy:
                continue

            t = (fecha - hoy).days / 365.25
            monto = float(f["flujo_calc"])

            flujos.append((t, monto))
            cashflow_ui.append({
                "fecha": fecha.strftime("%d/%m/%Y"),
                "flujo_usd": round(monto, 2)
            })

            if valor_nominal_residual is None and f.get("capital", 0) > 0:
                valor_nominal_residual = float(f["capital"])

        if not flujos or valor_nominal_residual is None:
            continue

        # ================= FINANZAS =================

        try:
            def npv(r):
                return sum(m / (1 + r) ** t for t, m in flujos) - precio_usd

            tir_dec = newton(npv, 0.10, maxiter=100)
            tir = round(tir_dec * 100, 2)

            pv_total = sum(m / (1 + tir_dec) ** t for t, m in flujos)
            md = sum(t * m / (1 + tir_dec) ** t for t, m in flujos) / pv_total
            md = round(md / (1 + tir_dec), 2)

            paridad = round((precio_usd / valor_nominal_residual) * 100, 2)

        except Exception:
            continue

        resultados.append({
            "ticker": ticker,
            "precio_usd": round(precio_usd, 2),
            "tir": tir,
            "md": md,
            "paridad": paridad,
            "valor_nominal_residual": valor_nominal_residual,
            "cashflow": cashflow_ui
        })

    # Ordenar por Duration (menor a mayor)
    return sorted(resultados, key=lambda x: x["md"])
