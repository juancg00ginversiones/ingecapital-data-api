import json
import os
import requests
from datetime import datetime, timedelta
from scipy.optimize import newton
import threading
import time

# =========================================================
# CONFIG
# =========================================================
URL_PRECIOS_ONS = "https://data912.com/live/arg_corp"
URL_DOLARAPI = "https://dolarapi.com/v1/dolares"
CASHFLOW_FILE = "cashflow_ons.json"

# filtros anti-delirio
TIR_MIN_PCT = -5.0
TIR_MAX_PCT = 150.0

# CACHE CONFIG (solo infraestructura)
ONS_CACHE_TTL = 20 * 60  # 20 minutos
_CACHE_LOCK = threading.Lock()
_CACHE_DATA = None
_CACHE_TS = 0.0
_INFLIGHT = False
_INFLIGHT_EVENT = threading.Event()


# =========================================================
# HELPERS
# =========================================================
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
    MEP desde DolarAPI (casa='bolsa', usar 'venta')
    """
    data = requests.get(URL_DOLARAPI, timeout=10).json()
    mep = next(
        d for d in data
        if d.get("casa") == "bolsa" and d.get("venta") is not None
    )
    return float(mep["venta"])


def cargar_cashflows():
    """
    Soporta:
    { "ons": { "TICKER": [ ... ] } }
    o
    { "TICKER": [ ... ] }
    """
    base_dir = os.path.dirname(os.path.abspath(__file__))
    path = os.path.join(base_dir, CASHFLOW_FILE)

    with open(path, "r", encoding="utf-8") as f:
        raw = json.load(f)

    return raw.get("ons", raw)


# =========================================================
# API PRINCIPAL (CON CACHE + CONCURRENCIA)
# =========================================================
def get_ons_for_api():
    """
    Formato EXACTO para Horizons (clave):
      - ticker
      - price (USD)
      - tir (decimal)
      - md
      - parity (%)
      - cashflows: [{date:'YYYY-MM-DD', flow: number}]
    """

    global _CACHE_DATA, _CACHE_TS, _INFLIGHT

    now_ts = time.time()

    # ---------- 1) Cache fresh ----------
    with _CACHE_LOCK:
        if _CACHE_DATA is not None and (now_ts - _CACHE_TS) <= ONS_CACHE_TTL:
            return _CACHE_DATA

        # ---------- 2) Single-flight ----------
        if _INFLIGHT:
            event = _INFLIGHT_EVENT
        else:
            _INFLIGHT = True
            _INFLIGHT_EVENT.clear()
            event = None

    # ---------- 3) Follower espera ----------
    if event is not None:
        event.wait(timeout=30)
        with _CACHE_LOCK:
            if _CACHE_DATA is not None:
                return _CACHE_DATA
            raise RuntimeError("ONS cache: fallo concurrente sin datos previos")

    # ---------- 4) Líder ejecuta lógica ORIGINAL ----------
    try:
        hoy = datetime.now()
        mep = get_mep_bolsa()
        cashflows = cargar_cashflows()

        precios = requests.get(URL_PRECIOS_ONS, timeout=10).json()
        if not isinstance(precios, list):
            raise RuntimeError("data912 arg_corp no devolvió una lista válida")

        out = []

        for item in precios:
            ticker = item.get("symbol")
            if not ticker or ticker not in cashflows:
                continue

            px_pesos = float(item.get("c") or 0)
            if px_pesos <= 0:
                continue

            price_usd = px_pesos / mep
            flujos_raw = cashflows[ticker]

            futuros = []
            vn_residual = None

            for f in flujos_raw:
                if "fecha" not in f:
                    continue

                fecha_dt = parse_fecha(f["fecha"])
                if fecha_dt <= hoy:
                    continue

                flow = f.get("flujo_calc")
                if flow is None:
                    continue

                t = (fecha_dt - hoy).days / 365.25
                futuros.append({
                    "t": float(t),
                    "date": fecha_dt.strftime("%Y-%m-%d"),
                    "flow": float(flow)
                })

                if vn_residual is None and float(f.get("capital", 0) or 0) > 0:
                    vn_residual = float(f["capital"])

            futuros.sort(key=lambda x: x["t"])

            if len(futuros) < 2:
                continue

            if vn_residual is None or vn_residual <= 0:
                vn_residual = 100.0

            try:
                def npv(r):
                    return sum(cf["flow"] / ((1 + r) ** cf["t"]) for cf in futuros) - price_usd

                tir_dec = newton(npv, 0.15, maxiter=100)
                tir_pct = tir_dec * 100.0
                if tir_pct < TIR_MIN_PCT or tir_pct > TIR_MAX_PCT:
                    continue

                pv_total = sum(cf["flow"] / ((1 + tir_dec) ** cf["t"]) for cf in futuros)
                if pv_total <= 0:
                    continue

                macaulay = sum(
                    cf["t"] * cf["flow"] / ((1 + tir_dec) ** cf["t"])
                    for cf in futuros
                ) / pv_total

                md = macaulay / (1 + tir_dec)
                parity = (price_usd / vn_residual) * 100.0

            except Exception:
                continue

            out.append({
                "ticker": ticker,
                "price": round(price_usd, 2),
                "tir": round(float(tir_dec), 8),
                "md": round(float(md), 2),
                "parity": round(float(parity), 2),
                "cashflows": [
                    {"date": cf["date"], "flow": round(float(cf["flow"]), 2)}
                    for cf in futuros
                ]
            })

        out.sort(key=lambda x: x["md"])

        # ---------- 5) Guardar cache SOLO si es válido ----------
        if out:
            with _CACHE_LOCK:
                _CACHE_DATA = out
                _CACHE_TS = time.time()

        return out

    finally:
        with _CACHE_LOCK:
            _INFLIGHT = False
            _INFLIGHT_EVENT.set()
