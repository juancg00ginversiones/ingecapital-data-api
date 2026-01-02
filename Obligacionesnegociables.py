import requests
import json
import os
from datetime import datetime, timedelta
from scipy.optimize import newton

# =========================================================
# CONFIG
# =========================================================
URL_ONS = "https://data912.com/live/arg_corp"
URL_DOLARAPI = "https://dolarapi.com/v1/dolares"
URL_ARGDATOS_HIST = "https://argentinadatos.com/v1/cotizaciones/dolares/bolsa"

CASHFLOW_FILE = "cashflow_ons.json"

TIR_MIN = -5
TIR_MAX = 150

# =========================================================
# UTILIDADES
# =========================================================
def parse_fecha(fecha):
    # Excel serial (int / float)
    if isinstance(fecha, (int, float)):
        return datetime(1899, 12, 30) + timedelta(days=int(fecha))

    # String
    if isinstance(fecha, str):
        s = fecha.strip()
        if s.isdigit():
            return datetime(1899, 12, 30) + timedelta(days=int(s))
        return datetime.strptime(s, "%Y-%m-%d")

    raise ValueError(f"Fecha inválida: {fecha}")


def fetch_json_safe(url):
    r = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
    if r.status_code != 200:
        raise Exception(f"HTTP {r.status_code}")
    txt = r.text.strip()
    if not txt:
        raise Exception("Respuesta vacía")
    return r.json()


def get_mep():
    # --------------------------------------------------
    # 1) DolarAPI (actual)
    # --------------------------------------------------
    try:
        data = fetch_json_safe(URL_DOLARAPI)
        for it in data:
            if (it.get("casa") or "").lower() == "bolsa":
                return float(it["venta"])
    except Exception:
        pass

    # --------------------------------------------------
    # 2) ArgentinaDatos histórico (último real)
    # --------------------------------------------------
    data = fetch_json_safe(URL_ARGDATOS_HIST)
    data_sorted = sorted(
        data,
        key=lambda x: datetime.fromisoformat(x["fecha"].replace("Z", "")),
        reverse=True
    )
    return float(data_sorted[0]["venta"])

# =========================================================
# API PRINCIPAL
# =========================================================
def get_ons_for_api():
    """
    Devuelve Obligaciones Negociables HARD DOLLAR con:
    - precio_usd
    - TIR
    - Modified Duration
    - Cashflows futuros
    """

    # --------------------------------------------------
    # MEP REAL
    # --------------------------------------------------
    mep = get_mep()

    # --------------------------------------------------
    # Cashflows
    # --------------------------------------------------
    base_dir = os.path.dirname(os.path.abspath(__file__))
    cashflow_path = os.path.join(base_dir, CASHFLOW_FILE)

    with open(cashflow_path, "r", encoding="utf-8") as f:
        cashflows = json.load(f)["ons"]

    # --------------------------------------------------
    # Precios ONs
    # --------------------------------------------------
    precios = fetch_json_safe(URL_ONS)

    hoy = datetime.now()
    resultados = []

    # --------------------------------------------------
    # Proceso ON por ON
    # --------------------------------------------------
    for item in precios:
        ticker = item.get("symbol")
        if ticker not in cashflows:
            continue

        px_pesos = float(item.get("c", 0))
        if px_pesos <= 0:
            continue

        px_usd = px_pesos / mep
        flujos = cashflows[ticker]

        futuros = []
        for f in flujos:
            fecha = parse_fecha(f["fecha"])
            if fecha > hoy:
                t = (fecha - hoy).days / 365.25
                futuros.append({
                    "fecha": fecha.strftime("%Y-%m-%d"),
                    "t": round(t, 4),
                    "monto": f["flujo_calc"]
                })

        if not futuros:
            continue

        try:
            def npv(r):
                return sum(cf["monto"] / (1 + r) ** cf["t"] for cf in futuros) - px_usd

            tir_dec = newton(npv, 0.1, maxiter=100)
            tir = tir_dec * 100

            # Filtro ONs inválidas / dollar linked
            if tir < TIR_MIN or tir > TIR_MAX:
                continue

            pv = sum(cf["monto"] / (1 + tir_dec) ** cf["t"] for cf in futuros)
            dur = sum((cf["t"] * cf["monto"]) / (1 + tir_dec) ** cf["t"] for cf in futuros) / pv
            md = dur / (1 + tir_dec)

            resultados.append({
                "ticker": ticker,
                "precio_usd": round(px_usd, 2),
                "tir": round(tir, 2),
                "md": round(md, 2),
                "cashflows": futuros
            })

        except Exception:
            # No converge → se descarta
            continue

    # Orden por TIR descendente
    return sorted(resultados, key=lambda x: x["tir"], reverse=True)
