# ============================================================
# COTIZACIONES – ACCIONES, CEDEARS, LETRAS, USA
# Fuente: data912.com  |  Cache thread-safe por categoría
# ============================================================

import time
import threading
import requests

# ============================================================
# CONFIG
# ============================================================
BASE_URL = "https://data912.com/live"

ENDPOINTS = {
    "acciones":  f"{BASE_URL}/arg_stocks",
    "cedears":   f"{BASE_URL}/arg_cedears",
    "letras":    f"{BASE_URL}/arg_notes",
    "ons":       f"{BASE_URL}/arg_corp",
    "usa":       f"{BASE_URL}/usa_stocks",
}

CACHE_TTL = 60 * 5   # 5 minutos — cotizaciones cambian seguido

# ============================================================
# CACHES INDIVIDUALES POR CATEGORÍA
# ============================================================
_CACHES = {k: {"ts": 0.0, "data": None} for k in ENDPOINTS}
_LOCKS  = {k: threading.Lock() for k in ENDPOINTS}
_INFLIGHT       = {k: False for k in ENDPOINTS}
_INFLIGHT_EVENTS = {k: threading.Event() for k in ENDPOINTS}

# ============================================================
# FETCH INTERNO
# ============================================================
def _fetch(categoria: str):
    url = ENDPOINTS[categoria]
    r = requests.get(url, timeout=15)
    r.raise_for_status()
    raw = r.json()

    result = []
    for item in raw:
        symbol = item.get("symbol", "")
        price  = item.get("px_ask") or item.get("price") or 0
        change = item.get("pct_change") or item.get("change_pct") or 0
        volume = item.get("nom_volume") or item.get("volume") or 0

        try: price  = float(price)
        except: price = 0.0
        try: change = float(change)
        except: change = 0.0
        try: volume = float(volume)
        except: volume = 0.0

        if symbol:
            result.append({
                "symbol":     symbol,
                "price":      round(price, 2),
                "pct_change": round(change, 2),
                "volume":     round(volume, 0),
            })

    result.sort(key=lambda x: x["symbol"])
    return result

# ============================================================
# FUNCIÓN PÚBLICA CON CACHE + CONCURRENCIA
# ============================================================
def get_cotizaciones(categoria: str):
    if categoria not in ENDPOINTS:
        raise ValueError(f"Categoría '{categoria}' no válida.")

    now   = time.time()
    lock  = _LOCKS[categoria]
    cache = _CACHES[categoria]

    with lock:
        # Cache vigente → devolver directo
        if cache["data"] is not None and (now - cache["ts"]) < CACHE_TTL:
            return cache["data"]

        # Ya hay un fetch en vuelo → esperar
        if _INFLIGHT[categoria]:
            event = _INFLIGHT_EVENTS[categoria]
        else:
            _INFLIGHT[categoria] = True
            _INFLIGHT_EVENTS[categoria].clear()
            event = None

    # Follower: esperar al leader
    if event is not None:
        event.wait(timeout=20)
        with lock:
            if cache["data"] is not None:
                return cache["data"]
        return []

    # Leader: hacer el fetch
    try:
        data = _fetch(categoria)
        with lock:
            cache["ts"]   = time.time()
            cache["data"] = data
        return data
    except Exception as e:
        print(f"[ERROR cotizaciones/{categoria}]", repr(e))
        with lock:
            # Devolver cache viejo si existe, o lista vacía
            return cache["data"] or []
    finally:
        with lock:
            _INFLIGHT[categoria] = False
        _INFLIGHT_EVENTS[categoria].set()
