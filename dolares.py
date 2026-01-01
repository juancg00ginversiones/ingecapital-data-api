import time
import datetime as dt
import requests

CURRENT_URL = "https://dolarapi.com/v1/dolares"
HIST_URL = "https://api.argentinadatos.com/v1/cotizaciones/dolares/"

CACHE_TTL = 60
HIST_CACHE_TTL = 600

_CACHE = {"ts": 0, "data": None}
_HIST_CACHE = {"ts": 0, "data": None}

CASA_LABEL = {
    "oficial": "Dólar Oficial",
    "blue": "Dólar Blue",
    "tarjeta": "Dólar Tarjeta",
    "contadoconliqui": "Dólar CCL",
    "bolsa": "Dólar MEP",
    "mayorista": "Dólar Mayorista",
    "cripto": "Dólar Cripto",
}

CASAS_ORDER = ["oficial", "blue", "tarjeta", "contadoconliqui", "bolsa", "mayorista", "cripto"]

def _safe_get_json(url: str, timeout: int = 15):
    r = requests.get(url, timeout=timeout)
    r.raise_for_status()
    return r.json()

def _fetch_history_cached():
    now = time.time()
    if _HIST_CACHE["data"] is not None and (now - _HIST_CACHE["ts"]) < HIST_CACHE_TTL:
        return _HIST_CACHE["data"]

    hist = _safe_get_json(HIST_URL, timeout=25)
    by_casa = {}
    for row in hist:
        casa = str(row.get("casa", "")).strip().lower()
        if not casa: continue
        
        try:
            d = dt.date.fromisoformat(row.get("fecha"))
            compra = float(row.get("compra")) if row.get("compra") else None
            venta = float(row.get("venta")) if row.get("venta") else None
            by_casa.setdefault(casa, []).append({"date": d, "compra": compra, "venta": venta})
        except: continue

    for casa in by_casa:
        by_casa[casa].sort(key=lambda x: x["date"])

    _HIST_CACHE["data"] = by_casa
    _HIST_CACHE["ts"] = now
    return by_casa

def get_dolares_for_api(history_days: int = 365):
    now = time.time()
    if _CACHE["data"] is not None and (now - _CACHE["ts"]) < CACHE_TTL:
        return _CACHE["data"]

    # 1. Obtener precios actuales
    current_raw = _safe_get_json(CURRENT_URL)
    current_dict = {str(r["casa"]).lower(): r for r in current_raw}
    
    # 2. Obtener histórico
    hist_by_casa = _fetch_history_cached()
    cutoff = dt.date.today() - dt.timedelta(days=history_days)

    out = {
        "updated_at": dt.datetime.utcnow().isoformat() + "Z",
        "current": [],
        "history": {},
    }

    for casa in CASAS_ORDER:
        if casa not in current_dict: continue
        
        raw_item = current_dict[casa]
        v_actual = float(raw_item.get("venta") or 0)
        c_actual = float(raw_item.get("compra") or 0)
        
        # --- LÓGICA DE VARIACIÓN PARA HORIZONS ---
        # Comparamos el precio "en vivo" contra el último cierre del histórico
        series = hist_by_casa.get(casa, [])
        venta_pct = 0.0
        
        if series:
            # Buscamos el último valor disponible en el histórico
            ultimo_hist = series[-1]
            v_anterior = ultimo_hist["venta"] if ultimo_hist["venta"] else ultimo_hist["compra"]
            
            if v_anterior and v_anterior > 0:
                venta_pct = ((v_actual / v_anterior) - 1) * 100

        # Formateamos exactamente como lo pide tu React
        out["current"].append({
            "casa": casa,
            "label": CASA_LABEL.get(casa, raw_item.get("nombre", casa)),
            "compra": c_actual,
            "venta": v_actual,
            "fechaActualizacion": raw_item.get("fechaActualizacion"),
            "variation": {
                "venta_pct": round(venta_pct, 2) # <--- Aquí es donde React lo lee
            }
        })

        # --- HISTORIAL ---
        trimmed = [p for p in series if p["date"] >= cutoff]
        out["history"][casa] = [
            {"date": p["date"].isoformat(), "compra": p["compra"], "venta": p["venta"]}
            for p in trimmed
        ]

    _CACHE["data"] = out
    _CACHE["ts"] = now
    return out
