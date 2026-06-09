import json
import os
import math
import requests
from datetime import datetime, timedelta
from scipy.optimize import newton
import threading
import time

# =========================================================
# CONFIG
# =========================================================
URL_PRECIOS_ONS = "https://data912.com/live/arg_corp"
URL_DOLARAPI    = "https://dolarapi.com/v1/dolares"
CASHFLOW_FILE   = "cashflow_ons.json"

TIR_MIN_PCT = -5.0
TIR_MAX_PCT = 150.0

ONS_CACHE_TTL = 20 * 60   # 20 minutos — cache de resultados
CF_CACHE_TTL  =  5 * 60   # 5 minutos  — recarga cashflows

_CACHE_LOCK  = threading.Lock()
_CACHE_DATA  = None
_CACHE_TS    = 0.0
_INFLIGHT    = False
_INFLIGHT_EVENT = threading.Event()

_CF_LOCK  = threading.Lock()
_CF_CACHE = {"ts": 0.0, "data": None}

# =========================================================
# HELPERS
# =========================================================
def parse_fecha(value):
    """Soporta ISO 'YYYY-MM-DD', Excel serial int/float/string."""
    if isinstance(value, (int, float)):
        return datetime(1899, 12, 30) + timedelta(days=int(value))
    if isinstance(value, str):
        s = value.strip()
        if s.isdigit():
            return datetime(1899, 12, 30) + timedelta(days=int(s))
        return datetime.strptime(s, "%Y-%m-%d")
    raise ValueError(f"Fecha inválida: {value}")


def get_mep_bolsa():
    data = requests.get(URL_DOLARAPI, timeout=10).json()
    mep  = next(
        d for d in data
        if d.get("casa") == "bolsa" and d.get("venta") is not None
    )
    return float(mep["venta"])


# =========================================================
# CARGA DINÁMICA DE CASHFLOWS (recarga cada CF_CACHE_TTL)
# =========================================================
def cargar_cashflows():
    """
    Recarga cashflow_ons.json cada 5 minutos para detectar
    tickers nuevos sin necesitar redeploy en Render.

    Soporta estructura nueva:  {"_updated":..., "ons": {"AERB": [...], ...}}
    y estructura vieja:        {"ons": {"AERBO": [...], ...}}
    """
    global _CF_CACHE

    now = time.time()
    with _CF_LOCK:
        if _CF_CACHE["data"] is not None and now - _CF_CACHE["ts"] < CF_CACHE_TTL:
            return _CF_CACHE["data"]

        base_dir = os.path.dirname(os.path.abspath(__file__))
        path     = os.path.join(base_dir, CASHFLOW_FILE)

        with open(path, "r", encoding="utf-8") as f:
            raw = json.load(f)

        ons_raw = raw.get("ons", raw)

        # ── Normalizar tickers ──────────────────────────────────────
        # El JSON nuevo tiene "AERB", data912 devuelve "AERBO" o "AERBD"
        # Creamos un índice que acepta ambas variantes:
        #   AERB  → datos
        #   AERBO → datos (alias con O)
        #   AERBD → datos (alias con D)
        cashflows = {}
        for ticker, flows in ons_raw.items():
            # Filtrar flujos inválidos
            clean = []
            for r in flows:
                if "fecha" not in r:
                    continue
                flujo = r.get("flujo_calc")
                if flujo is None:
                    continue
                if isinstance(flujo, float) and math.isnan(flujo):
                    continue
                clean.append(r)

            if not clean:
                continue

            t = ticker.upper()
            cashflows[t] = clean

            # Alias con O (ej: AERB → AERBO)
            if not t.endswith("O") and not t.endswith("D"):
                cashflows[t + "O"] = clean
                cashflows[t + "D"] = clean
            elif t.endswith("O"):
                cashflows[t[:-1]]       = clean
                cashflows[t[:-1] + "D"] = clean
            elif t.endswith("D"):
                cashflows[t[:-1]]       = clean
                cashflows[t[:-1] + "O"] = clean

        _CF_CACHE = {"ts": now, "data": cashflows}
        print(f"[ONs] Cashflows recargados: {len(ons_raw)} tickers base")
        return cashflows


# =========================================================
# API PRINCIPAL (CACHE + SINGLE-FLIGHT)
# =========================================================
def get_ons_for_api():
    """
    Retorna lista de ONs con:
      ticker, price (USD), tir (decimal), md, parity (%), cashflows
    """
    global _CACHE_DATA, _CACHE_TS, _INFLIGHT

    now_ts = time.time()

    with _CACHE_LOCK:
        if _CACHE_DATA is not None and (now_ts - _CACHE_TS) <= ONS_CACHE_TTL:
            return _CACHE_DATA
        if _INFLIGHT:
            event = _INFLIGHT_EVENT
        else:
            _INFLIGHT = True
            _INFLIGHT_EVENT.clear()
            event = None

    # Follower
    if event is not None:
        event.wait(timeout=30)
        with _CACHE_LOCK:
            if _CACHE_DATA is not None:
                return _CACHE_DATA
            raise RuntimeError("ONS cache: fallo concurrente sin datos previos")

    # Líder
    try:
        hoy       = datetime.now()
        mep       = get_mep_bolsa()
        cashflows = cargar_cashflows()   # ← recarga dinámica

        precios = requests.get(URL_PRECIOS_ONS, timeout=10).json()
        if not isinstance(precios, list):
            raise RuntimeError("data912 arg_corp no devolvió lista válida")

        out = []

        for item in precios:
            ticker = item.get("symbol", "").upper()
            if not ticker:
                continue

            # Buscar en cashflows con cualquier variante del ticker
            flows_raw = cashflows.get(ticker)
            if flows_raw is None:
                continue

            px_pesos = float(item.get("c") or 0)
            if px_pesos <= 0:
                continue

            price_usd = px_pesos / mep

            # Construir flujos futuros
            futuros      = []
            vn_residual  = None

            for r in flows_raw:
                fecha_dt = parse_fecha(r["fecha"])
                if fecha_dt <= hoy:
                    continue

                flow = r.get("flujo_calc")
                if flow is None or (isinstance(flow, float) and math.isnan(flow)):
                    continue

                t = (fecha_dt - hoy).days / 365.25
                futuros.append({
                    "t":    float(t),
                    "date": fecha_dt.strftime("%Y-%m-%d"),
                    "flow": float(flow),
                })

                if vn_residual is None and float(r.get("capital", 0) or 0) > 0:
                    vn_residual = float(r["capital"])

            futuros.sort(key=lambda x: x["t"])

            if len(futuros) < 1:
                continue

            if vn_residual is None or vn_residual <= 0:
                vn_residual = 100.0

            try:
                def npv(r, _futuros=futuros, _p=price_usd):
                    return sum(
                        cf["flow"] / ((1 + r) ** cf["t"]) for cf in _futuros
                    ) - _p

                tir_dec = newton(npv, 0.15, maxiter=100)
                tir_pct = tir_dec * 100.0

                if tir_pct < TIR_MIN_PCT or tir_pct > TIR_MAX_PCT:
                    continue

                pv_total = sum(
                    cf["flow"] / ((1 + tir_dec) ** cf["t"]) for cf in futuros
                )
                if pv_total <= 0:
                    continue

                macaulay = sum(
                    cf["t"] * cf["flow"] / ((1 + tir_dec) ** cf["t"])
                    for cf in futuros
                ) / pv_total

                md     = macaulay / (1 + tir_dec)
                parity = (price_usd / vn_residual) * 100.0

            except Exception:
                continue

            # Ticker limpio para mostrar (sin la D final si la tiene)
            display_ticker = ticker
            if display_ticker.endswith("D") and len(display_ticker) > 2:
                display_ticker = display_ticker[:-1]

            out.append({
                "ticker":    display_ticker,
                "price":     round(price_usd, 2),
                "tir":       round(float(tir_dec), 8),
                "md":        round(float(md), 2),
                "parity":    round(float(parity), 2),
                "cashflows": [
                    {"date": cf["date"], "flow": round(float(cf["flow"]), 2)}
                    for cf in futuros
                ],
            })

        out.sort(key=lambda x: x["md"])

        if out:
            with _CACHE_LOCK:
                _CACHE_DATA = out
                _CACHE_TS   = time.time()

        return out

    finally:
        with _CACHE_LOCK:
            _INFLIGHT = False
            _INFLIGHT_EVENT.set()
