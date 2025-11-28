import pandas as pd
import numpy as np
import requests
from datetime import date
import math


# ============================================================
# FUNCIONES DE SANITIZACIÓN PARA JSON
# ============================================================
def clean_value(v):
    """
    Convierte valores problemáticos (NaN, inf, tipos raros) en algo JSON-safe.
    """
    if v is None:
        return None

    # numpy types -> python
    if isinstance(v, (np.floating, np.float64, np.float32)):
        v = float(v)
    if isinstance(v, (np.integer, np.int64, np.int32)):
        v = int(v)

    if isinstance(v, float):
        if math.isnan(v) or math.isinf(v):
            return None
        return float(v)

    if isinstance(v, (int, str, bool)):
        return v

    # cualquier otra cosa (por ej. NA de pandas) -> string
    try:
        return str(v)
    except Exception:
        return None


def limpiar_resultados(lista_dicts):
    """
    Recorre toda la lista de resultados y limpia cada valor para que sea JSON válido.
    """
    salida = []
    for item in lista_dicts:
        nuevo = {}
        for k, v in item.items():
            nuevo[k] = clean_value(v)
        salida.append(nuevo)
    return salida


# ============================================================
# 1) CARGAR EXCEL Y ARMAR FLUJOS POR TICKER
# ============================================================
def cargar_excel():
    # El Excel debe estar en el mismo directorio que calculadora.py
    RUTA_EXCEL = "BONOS Y ONS data.xlsx"

    df = pd.read_excel(RUTA_EXCEL)
    df["payment_date"] = pd.to_datetime(df["payment_date"])

    flujos = {}

    for _, row in df.iterrows():
        ticker = str(row["ticker"]).strip()

        if ticker not in flujos:
            flujos[ticker] = []

        flujos[ticker].append({
            "fecha": row["payment_date"].date(),
            "flujo": float(row["cash_flow"])
        })

    # Ordenar flujos por fecha
    for t in flujos:
        flujos[t] = sorted(flujos[t], key=lambda x: x["fecha"])

    return df, flujos


# ============================================================
# 2) CONSULTAR API 912
# ============================================================
def cargar_api():
    URL_BONOS = "https://data912.com/live/arg_bonds"
    URL_ONS   = "https://data912.com/live/arg_corp"

    precios = {}

    def leer(url):
        try:
            data = requests.get(url).json()
            for x in data:
                sym = x.get("symbol")
                price = x.get("c")
                pct = x.get("pct_change") if x.get("pct_change") is not None else x.get("dp")

                if sym and price is not None:
                    precios[sym] = {
                        "precio": float(price),
                        "pct_change": float(pct) if pct is not None else 0.0
                    }
        except Exception:
            # Si falla la API, simplemente no carga nada de ese endpoint
            pass

    leer(URL_BONOS)
    leer(URL_ONS)

    return precios


# ============================================================
# 3) XNPV / XIRR / DURATION
# ============================================================
def xnpv(rate, cashflows, dates):
    if rate is None or rate <= -1:
        return np.nan

    t0 = dates[0]
    total = 0.0

    for cf, d in zip(cashflows, dates):
        t = (d - t0).days / 365.0
        total += cf / ((1.0 + rate) ** t)

    return total


def xirr(cfs, dates, lo=-0.99, hi=5.0, tol=1e-8):
    def f(r): 
        return xnpv(r, cfs, dates)

    f_lo = f(lo)
    f_hi = f(hi)

    # Si no hay cambio de signo, devolvemos None
    if math.isnan(f_lo) or math.isnan(f_hi) or f_lo * f_hi > 0:
        return None

    for _ in range(200):
        mid = (lo + hi) / 2.0
        fm = f(mid)

        if math.isnan(fm):
            return None

        if abs(fm) < tol:
            return mid

        if f_lo * fm > 0:
            lo = mid
            f_lo = fm
        else:
            hi = mid
            f_hi = fm

    return mid


def duration_macaulay(r, cf_fut, dates_fut, T0):
    if r is None:
        return None

    pv_total = 0.0
    acc = 0.0

    for cf, d in zip(cf_fut, dates_fut):
        t = (d - T0).days / 365.0
        pv = cf / ((1.0 + r) ** t)
        pv_total += pv
        acc += t * pv

    if pv_total == 0:
        return None

    return acc / pv_total


def duration_modificada(d_mac, r):
    if d_mac is None or r is None:
        return None
    return d_mac / (1.0 + r)


# ============================================================
# 4) FUNCIÓN PRINCIPAL — CALCULAR TODOS LOS BONOS
# ============================================================
def calcular_todo():
    df, flujos = cargar_excel()
    precios = cargar_api()

    T0 = date.today()
    RESULTADOS = []

    for ticker, lista in flujos.items():
        if ticker not in precios:
            continue

        precio = precios[ticker]["precio"]
        pct = precios[ticker]["pct_change"]

        # Flujos FUTUROS (solo desde HOY hacia adelante)
        fut = [c for c in lista if c["fecha"] > T0]
        if not fut:
            continue

        cfs = [-precio] + [c["flujo"] for c in fut]
        dates = [T0] + [c["fecha"] for c in fut]

        # Cálculos
        tir = xirr(cfs, dates)
        d_mac = duration_macaulay(
            tir,
            [c["flujo"] for c in fut],
            [c["fecha"] for c in fut],
            T0
        )
        d_mod = duration_modificada(d_mac, tir)

        valor_nominal = fut[-1]["flujo"] if fut else None
        paridad = (precio / valor_nominal * 100.0) if valor_nominal else None

        # Tipo (categoría del Excel)
        try:
            tipo = df[df["ticker"] == ticker]["type"].iloc[0]
        except Exception:
            tipo = None

        # Clasificación de curva (AL / GD / otros)
        if ticker.startswith("AL"):
            curva = "AL"
        elif ticker.startswith("GD"):
            curva = "GD"
        else:
            curva = None

        RESULTADOS.append({
            "ticker": ticker,
            "type": tipo,
            "curva": curva,
            "precio": precio,
            "pct_change": pct,
            "tir_pct": (tir * 100.0) if tir is not None else None,
            "paridad": paridad,
            "duration_mod": d_mod,
        })

    # MUY IMPORTANTE: limpiar todos los valores para que JSON no tenga NaN
    return limpiar_resultados(RESULTADOS)


# ============================================================
# 5) CURVAS AL / GD
# ============================================================
def curva_AL():
    data = calcular_todo()
    al = [x for x in data if x.get("curva") == "AL"]
    return al


def curva_GD():
    data = calcular_todo()
    gd = [x for x in data if x.get("curva") == "GD"]
    return gd
