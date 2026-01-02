import os
import json
import requests
from datetime import datetime, timedelta
from scipy.optimize import newton

# =========================================================
# CONFIG
# =========================================================
URL_ONS = "https://data912.com/live/arg_corp"
URL_DOLARAPI = "https://dolarapi.com/v1/dolares"
URL_ARGDATOS_HIST_BOLSA = "https://argentinadatos.com/v1/cotizaciones/dolares/bolsa"

CASHFLOW_FILE = "cashflow_ons.json"

# Filtro de TIR (en % anual) para evitar delirios / dollar-linked / data basura
TIR_MIN_PCT = -5.0
TIR_MAX_PCT = 50.0

# =========================================================
# HELPERS
# =========================================================
def _fetch_json_safe(url: str, timeout: int = 10):
    r = requests.get(url, timeout=timeout, headers={"User-Agent": "Mozilla/5.0"})
    if r.status_code != 200:
        raise Exception(f"{url} -> HTTP {r.status_code}")
    txt = r.text.strip()
    if not txt:
        raise Exception(f"{url} -> respuesta vacía")
    return r.json()


def parse_fecha(value):
    """
    Acepta:
    - 'YYYY-MM-DD'
    - Excel serial: 45831
    - Excel serial como string: '45831'
    """
    if isinstance(value, (int, float)):
        return datetime(1899, 12, 30) + timedelta(days=int(value))

    if isinstance(value, str):
        s = value.strip()
        if s.isdigit():
            return datetime(1899, 12, 30) + timedelta(days=int(s))
        return datetime.strptime(s, "%Y-%m-%d")

    raise ValueError(f"Fecha inválida: {value}")


def get_mep_bolsa():
    """
    Obtiene MEP real (sin inventar):
    1) DolarAPI /v1/dolares casa=bolsa
    2) ArgentinaDatos histórico /bolsa (último valor por fecha)
    """
    # 1) DolarAPI
    try:
        data = _fetch_json_safe(URL_DOLARAPI)
        if isinstance(data, list):
            for it in data:
                if (it.get("casa") or "").lower() == "bolsa":
                    venta = it.get("venta")
                    if venta is not None:
                        return float(venta)
    except Exception:
        pass

    # 2) ArgentinaDatos histórico (último dato real)
    data = _fetch_json_safe(URL_ARGDATOS_HIST_BOLSA)
    if not isinstance(data, list) or not data:
        raise RuntimeError("ArgentinaDatos histórico devolvió vacío")

    def _dt(x):
        # 'fecha' viene ISO, a veces con Z
        return datetime.fromisoformat(x["fecha"].replace("Z", ""))

    data_sorted = sorted(
        [x for x in data if x.get("venta") is not None and x.get("fecha")],
        key=_dt,
        reverse=True
    )
    if not data_sorted:
        raise RuntimeError("ArgentinaDatos histórico no tiene registros válidos")

    return float(data_sorted[0]["venta"])


# =========================================================
# API
# =========================================================
def get_ons_for_api():
    """
    Devuelve una lista de ONs (hard dollar "probables") en formato EXACTO para Horizons:

    [
      {
        "ticker": "AERBO",
        "price": 92.35,          # PRECIO EN USD
        "tir": 0.0842,           # DECIMAL (0.0842 = 8.42%)
        "md": 1.87,
        "cashflows": [
          {"date": "2026-03-15", "flow": 2.5},
          {"date": "2026-09-15", "flow": 102.5}
        ]
      },
      ...
    ]

    Nota: filtramos instrumentos con TIR delirante o no convergente.
    """

    # --- MEP real (Bolsa)
    mep = get_mep_bolsa()

    # --- Cashflows
    base_dir = os.path.dirname(os.path.abspath(__file__))
    cashflow_path = os.path.join(base_dir, CASHFLOW_FILE)

    with open(cashflow_path, "r", encoding="utf-8") as f:
        cashflows_all = json.load(f)

    # Soporta dos formatos:
    # { "ons": { "AERBO": [ ... ], ... } }
    # o directamente { "AERBO": [ ... ], ... }
    cashflows = cashflows_all.get("ons", cashflows_all)

    # --- Precios (data912)
    precios = _fetch_json_safe(URL_ONS)
    if not isinstance(precios, list):
        raise RuntimeError("data912 arg_corp no devolvió lista")

    hoy = datetime.now()
    out = []

    for item in precios:
        ticker = item.get("symbol")
        if not ticker or ticker not in cashflows:
            continue

        px_pesos = float(item.get("c") or 0)
        if px_pesos <= 0:
            continue

        # Precio USD usando MEP Bolsa
        px_usd = px_pesos / mep

        # Cashflows futuros
        flujos_ticker = cashflows[ticker]
        futuros = []
        for cf in flujos_ticker:
            # cf debe tener: "fecha" y "flujo_calc"
            if "fecha" not in cf:
                continue
            fecha_dt = parse_fecha(cf["fecha"])
            if fecha_dt <= hoy:
                continue

            flow = cf.get("flujo_calc")
            if flow is None:
                continue

            futuros.append({
                "date": fecha_dt.strftime("%Y-%m-%d"),
                "t": (fecha_dt - hoy).days / 365.25,
                "flow": float(flow)
            })

        # orden por fecha
        futuros.sort(key=lambda x: x["t"])

        # Necesitamos al menos 2 flujos para que la TIR tenga sentido
        if len(futuros) < 2:
            continue

        # --- Calcular TIR (decimal)
        try:
            def npv(r):
                return sum(cf["flow"] / (1 + r) ** cf["t"] for cf in futuros) - px_usd

            tir_dec = newton(npv, 0.1, maxiter=100)  # devuelve decimal (ej 0.0842)
            tir_pct = tir_dec * 100.0

            # Filtro anti-delirio
            if tir_pct < TIR_MIN_PCT or tir_pct > TIR_MAX_PCT:
                continue

            # Modified Duration
            pv_total = sum(cf["flow"] / (1 + tir_dec) ** cf["t"] for cf in futuros)
            if pv_total <= 0:
                continue

            macaulay = sum(
                (cf["t"] * cf["flow"]) / (1 + tir_dec) ** cf["t"]
                for cf in futuros
            ) / pv_total

            md = macaulay / (1 + tir_dec)

            # Formato EXACTO para Horizons: cashflows con {date, flow}
            cashflows_api = [{"date": cf["date"], "flow": round(cf["flow"], 6)} for cf in futuros]

            out.append({
                "ticker": ticker,
                "price": round(px_usd, 4),
                "tir": round(float(tir_dec), 8),   # DECIMAL
                "md": round(float(md), 4),
                "cashflows": cashflows_api
            })

        except Exception:
            # No converge / data mala → descartar
            continue

    # Orden final: por Modified Duration (menor a mayor), como pediste
    out.sort(key=lambda x: x["md"])
    return out
