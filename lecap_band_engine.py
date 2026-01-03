import requests
from datetime import date, datetime
from typing import Dict, Any, List
import threading
import time


# ============================================================
# CONFIG
# ============================================================
URL_NOTES = "https://data912.com/live/arg_notes"
URL_MEP = "https://data912.com/live/mep"

DOLAR_OFFSETS = [-200, -100, 0, 100, 200]

# Cache (infra)
CACHE_TTL = 300  # 5 minutos


# ============================================================
# LECAPS
# ============================================================
LECAPS = {
    "S16E6": {"expiry": "2026-01-16", "vpv": 119.625},
    "S27F6": {"expiry": "2026-02-27", "vpv": 125.842},
    "S30A6": {"expiry": "2026-04-30", "vpv": 127.486},
    "S29Y6": {"expiry": "2026-05-29", "vpv": 130.661},
    "S30O6": {"expiry": "2026-10-30", "vpv": 135.278},
}


# ============================================================
# CACHE / CONCURRENCIA
# ============================================================
_CACHE = {"ts": 0.0, "data": None}
_CACHE_LOCK = threading.Lock()
_INFLIGHT = False
_INFLIGHT_EVENT = threading.Event()


# ============================================================
# HELPERS (NO TOCAR)
# ============================================================
def parse_date(s: str) -> date:
    y, m, d = s.split("-")
    return date(int(y), int(m), int(d))


def days_to_expiry(expiry: date) -> int:
    return (expiry - date.today()).days


def to_timestamp(d: date) -> int:
    return int(datetime(d.year, d.month, d.day).timestamp() * 1000)


def fetch_json(url: str):
    r = requests.get(url, timeout=20)
    r.raise_for_status()
    return r.json()


def fetch_dolar_al30_from_mep() -> float:
    mep = fetch_json(URL_MEP)

    if not isinstance(mep, list):
        raise ValueError("Respuesta inesperada en /live/mep (no es lista).")

    for item in mep:
        if item.get("ticker") == "AL30":
            ask = item.get("ask")
            if ask is None:
                raise ValueError("AL30 encontrado en /live/mep pero sin campo 'ask'.")
            return float(ask)

    raise ValueError("No se encontró ticker 'AL30' en /live/mep.")


# ============================================================
# API (THREAD-SAFE + CACHE)
# ============================================================
def get_lecap_band_for_api() -> Dict[str, Any]:
    global _INFLIGHT

    now_ts = time.time()

    # ---------- 1) Cache fresh ----------
    with _CACHE_LOCK:
        if _CACHE["data"] is not None and (now_ts - _CACHE["ts"]) < CACHE_TTL:
            return _CACHE["data"]

        if _INFLIGHT:
            event = _INFLIGHT_EVENT
        else:
            _INFLIGHT = True
            _INFLIGHT_EVENT.clear()
            event = None

    # ---------- 2) Follower ----------
    if event is not None:
        event.wait(timeout=30)
        with _CACHE_LOCK:
            if _CACHE["data"] is not None:
                return _CACHE["data"]
            return {
                "ok": False,
                "error": "Datos no disponibles"
            }

    # ---------- 3) Líder (lógica ORIGINAL intacta) ----------
    try:
        now = datetime.now().isoformat()

        notes = fetch_json(URL_NOTES)
        prices = {
            i["symbol"]: float(i["px_ask"])
            for i in notes
            if i.get("symbol") in LECAPS and i.get("px_ask")
        }

        dolar_hoy = fetch_dolar_al30_from_mep()
        escenarios_dolar = [round(dolar_hoy + x, 2) for x in DOLAR_OFFSETS]

        lecaps_out = []

        for sym, cfg in LECAPS.items():
            price = prices.get(sym)
            if not price or price <= 0:
                continue

            expiry = parse_date(cfg["expiry"])
            days = days_to_expiry(expiry)
            if days <= 0:
                continue

            vpv = float(cfg["vpv"])

            rendimiento = (vpv / price) - 1.0
            break_even = dolar_hoy * (vpv / price)

            escenarios = {}
            for d in escenarios_dolar:
                escenarios[str(d)] = round((break_even / d - 1.0) * 100.0, 2)

            lecaps_out.append({
                "symbol": sym,
                "expiry": cfg["expiry"],
                "days_remaining": days,
                "price": round(price, 6),
                "vpv": round(vpv, 6),
                "rendimiento_directo": round(rendimiento, 6),
                "break_even": round(break_even, 2),
                "chart_point": {
                    "x": to_timestamp(expiry),
                    "y": round(break_even, 2)
                },
                "escenarios": escenarios
            })

        lecaps_out.sort(key=lambda x: x["days_remaining"])

        output = {
            "ok": True,
            "as_of": now,
            "dolar_hoy": round(dolar_hoy, 2),
            "dolar_source": "AL30 ask (data912 /live/mep)",
            "escenarios_dolar": escenarios_dolar,
            "lecaps": lecaps_out
        }

        # Guardar cache SOLO si es válido
        with _CACHE_LOCK:
            _CACHE["data"] = output
            _CACHE["ts"] = time.time()

        return output

    except Exception:
        with _CACHE_LOCK:
            if _CACHE["data"] is not None:
                return _CACHE["data"]
        raise

    finally:
        with _CACHE_LOCK:
            _INFLIGHT = False
            _INFLIGHT_EVENT.set()
