import requests
import json
from datetime import datetime, timedelta
from scipy.optimize import newton

URL_PRECIOS_ONS = "https://data912.com/live/arg_corp"
URL_DOLAR = "https://api.argentinadatos.com/v1/cotizaciones/dolares"
CASHFLOW_FILE = "cashflow_ons.json"


# ------------------ UTILIDADES ------------------

def get_mep():
    """
    Obtiene el dólar MEP desde dolarapi.com
    Usa SIEMPRE el valor 'venta' de la casa 'bolsa'
    """
    url = "https://dolarapi.com/v1/dolares"

    try:
        data = requests.get(url, timeout=10).json()

        mep = next(
            d for d in data
            if d.get("casa") == "bolsa" and d.get("venta") is not None
        )

        return float(mep["venta"])

    except Exception as e:
        raise RuntimeError(f"No se pudo obtener dólar MEP desde dolarapi: {e}")



# ------------------ FUNCIÓN PRINCIPAL ------------------

def get_ons_for_api():
    hoy = datetime.now()
    mep = get_mep()

    with open(CASHFLOW_FILE, "r", encoding="utf-8") as f:
        cashflows_data = json.load(f)["ons"]

    precios = requests.get(URL_PRECIOS_ONS, timeout=10).json()

    resultado = []

    for item in precios:
        ticker = item.get("symbol")
        if ticker not in cashflows_data:
            continue

        precio_pesos = float(item.get("c", 0))
        if precio_pesos <= 0:
            continue

        precio_usd = precio_pesos / mep

        flujos = []
        nominal = None

        for f in cashflows_data[ticker]:
            fecha_pago = parse_fecha(f["fecha"])
            if fecha_pago <= hoy:
                continue

            t = (fecha_pago - hoy).days / 365.25
            flujo = float(f["flujo_calc"])

            flujos.append({
                "t": t,
                "date": fecha_pago.strftime("%Y-%m-%d"),
                "flow": flujo
            })

            if nominal is None:
                nominal = float(f.get("capital", 100))

        if not flujos:
            continue

        # -------- TIR --------
        def npv(r):
            return sum(cf["flow"] / ((1 + r) ** cf["t"]) for cf in flujos) - precio_usd

        try:
            tir = newton(npv, 0.15)
        except:
            continue

        if tir < -0.2 or tir > 1.5:
            continue  # limpia TIR absurdas

        # -------- MD --------
        pv_total = sum(cf["flow"] / ((1 + tir) ** cf["t"]) for cf in flujos)
        duration = sum(
            cf["t"] * cf["flow"] / ((1 + tir) ** cf["t"])
            for cf in flujos
        ) / pv_total

        md = duration / (1 + tir)

        # -------- PARIDAD --------
        parity = (precio_usd / nominal) * 100 if nominal else None

        resultado.append({
            "ticker": ticker,
            "price": round(precio_usd, 2),
            "tir": round(tir, 6),           # DECIMAL
            "md": round(md, 2),
            "parity": round(parity, 2) if parity else None,
            "cashflows": [
                {"date": cf["date"], "flow": round(cf["flow"], 2)}
                for cf in flujos
            ]
        })

    return sorted(resultado, key=lambda x: x["md"])
