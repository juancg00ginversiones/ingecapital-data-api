# ============================================================
# DÓLARES (ACTUAL + HISTÓRICO + VARIACIÓN) – MOTOR PARA API
# ============================================================

import time
import datetime as dt
import requests

# ---- Fuentes ----
# Cotización actual (rápido)
CURRENT_URL = "https://dolarapi.com/v1/dolares"

# Histórico (devuelve serie por casa en formato: {casa, compra, venta, fecha})
HIST_URL = "https://api.argentinadatos.com/v1/cotizaciones/dolares/"

# ---- Cache ----
CACHE_TTL = 60          # 60s para "current + variación"
HIST_CACHE_TTL = 600    # 10 min para histórico (más pesado)

_CACHE = {"ts": 0, "data": None}
_HIST_CACHE = {"ts": 0, "data": None}

# ---- Mapeo nombres (por si querés forzar labels) ----
CASA_LABEL = {
    "oficial": "Dólar Oficial",
    "blue": "Dólar Blue",
    "tarjeta": "Dólar Tarjeta",
    "contadoconliqui": "Dólar CCL",
    "bolsa": "Dólar MEP",
    "mayorista": "Dólar Mayorista",
    "cripto": "Dólar Cripto",
}

# Casas que queremos mostrar sí o sí (orden)
CASAS_ORDER = ["oficial", "blue", "tarjeta", "contadoconliqui", "bolsa", "mayorista", "cripto"]


def _safe_get_json(url: str, timeout: int = 15):
    r = requests.get(url, timeout=timeout)
    r.raise_for_status()
    return r.json()


def _fetch_current():
    # Devuelve lista de objetos {casa, compra, venta, fechaActualizacion, ...}
    data = _safe_get_json(CURRENT_URL, timeout=15)
    # normalizamos: index por casa
    by_casa = {}
    for row in data:
        casa = str(row.get("casa", "")).strip().lower()
        if not casa:
            continue
        by_casa[casa] = {
            "casa": casa,
            "label": CASA_LABEL.get(casa, row.get("nombre", casa)),
            "compra": float(row.get("compra")) if row.get("compra") is not None else None,
            "venta": float(row.get("venta")) if row.get("venta") is not None else None,
            "fechaActualizacion": row.get("fechaActualizacion"),
        }
    return by_casa


def _fetch_history_cached():
    now = time.time()
    if _HIST_CACHE["data"] is not None and (now - _HIST_CACHE["ts"]) < HIST_CACHE_TTL:
        return _HIST_CACHE["data"]

    # Devuelve lista histórica: {casa, compra, venta, fecha}
    hist = _safe_get_json(HIST_URL, timeout=25)

    # Normalizamos a dict casa -> lista ordenada por fecha
    by_casa = {}
    for row in hist:
        casa = str(row.get("casa", "")).strip().lower()
        fecha = row.get("fecha")
        if not casa or not fecha:
            continue
        try:
            d = dt.date.fromisoformat(fecha)
        except Exception:
            continue

        compra = row.get("compra")
        venta = row.get("venta")
        try:
            compra = float(compra) if compra is not None else None
            venta = float(venta) if venta is not None else None
        except Exception:
            continue

        by_casa.setdefault(casa, []).append({"date": d, "compra": compra, "venta": venta})

    for casa in by_casa:
        by_casa[casa].sort(key=lambda x: x["date"])

    _HIST_CACHE["data"] = by_casa
    _HIST_CACHE["ts"] = now
    return by_casa


def _compute_variation_from_history(hist_series):
    """
    Variación diaria: compara último dato vs dato anterior (últimas 2 fechas distintas).
    Devuelve % para compra y venta, y delta absoluto.
    """
    if not hist_series or len(hist_series) < 2:
        return None

    # Tomo últimos dos puntos con valores válidos de venta (si falta venta, uso compra)
    last = None
    prev = None

    for p in reversed(hist_series):
        if p.get("venta") is not None or p.get("compra") is not None:
            last = p
            break
    if last is None:
        return None

    for p in reversed(hist_series):
        if p["date"] < last["date"] and (p.get("venta") is not None or p.get("compra") is not None):
            prev = p
            break
    if prev is None:
        return None

    def pct(a, b):
        if a is None or b is None or b == 0:
            return None
        return (a / b - 1.0) * 100.0

    # Preferimos venta; si no hay, usamos compra
    last_venta = last.get("venta") if last.get("venta") is not None else last.get("compra")
    prev_venta = prev.get("venta") if prev.get("venta") is not None else prev.get("compra")

    last_compra = last.get("compra")
    prev_compra = prev.get("compra")

    return {
        "date_last": last["date"].isoformat(),
        "date_prev": prev["date"].isoformat(),
        "venta_pct": pct(last_venta, prev_venta),
        "venta_abs": (last_venta - prev_venta) if (last_venta is not None and prev_venta is not None) else None,
        "compra_pct": pct(last_compra, prev_compra),
        "compra_abs": (last_compra - prev_compra) if (last_compra is not None and prev_compra is not None) else None,
    }


def get_dolares_for_api(history_days: int = 365):
    """
    Salida pensada para Horizons:
    - current: cotización actual por casa
    - variation: variación vs dato previo (desde histórico)
    - history: series por casa (últimos N días)
    """
    now = time.time()
    if _CACHE["data"] is not None and (now - _CACHE["ts"]) < CACHE_TTL:
        return _CACHE["data"]

    current = _fetch_current()
    hist_by_casa = _fetch_history_cached()

    cutoff = dt.date.today() - dt.timedelta(days=history_days)

    out = {
        "updated_at": dt.datetime.utcnow().isoformat() + "Z",
        "source": {
            "current": CURRENT_URL,
            "history": HIST_URL,
        },
        "current": [],
        "history": {},
    }

    # Armamos current ordenado + variación
    for casa in CASAS_ORDER:
        if casa not in current:
            continue

        hist_series = hist_by_casa.get(casa, [])
        variation = _compute_variation_from_history(hist_series)

        out["current"].append({
            **current[casa],
            "variation": variation,  # incluye % y abs + fechas
        })

    # Armamos history (solo venta por defecto, más liviano para gráficos)
    for casa in CASAS_ORDER:
        series = hist_by_casa.get(casa, [])
        if not series:
            continue

        trimmed = [p for p in series if p["date"] >= cutoff]
        out["history"][casa] = [
            {"date": p["date"].isoformat(), "compra": p["compra"], "venta": p["venta"]}
            for p in trimmed
        ]

    _CACHE["data"] = out
    _CACHE["ts"] = now
    return out
