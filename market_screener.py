from datetime import datetime
from indicators import analyze_ticker
from tickers import TICKERS_BY_SECTOR
import threading
import time

# ============================================================
# CACHE / CONCURRENCIA (infraestructura)
# ============================================================
SCREENER_CACHE_TTL = 300  # 5 minutos

_CACHE = {"ts": 0.0, "data": None}
_CACHE_LOCK = threading.Lock()
_INFLIGHT = False
_INFLIGHT_EVENT = threading.Event()


def get_market_screener_for_api() -> dict:
    global _INFLIGHT

    now = time.time()

    # ---------- 1) Cache fresh ----------
    with _CACHE_LOCK:
        if _CACHE["data"] is not None and (now - _CACHE["ts"]) <= SCREENER_CACHE_TTL:
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
                "as_of": datetime.utcnow().isoformat(),
                "sectors": {}
            }

    # ---------- 3) Líder (lógica ORIGINAL intacta) ----------
    try:
        result = {
            "as_of": datetime.utcnow().isoformat(),
            "sectors": {}
        }

        for sector_name, tickers in TICKERS_BY_SECTOR.items():
            sector_data = []

            for ticker in tickers:
                try:
                    data = analyze_ticker(ticker)
                    sector_data.append(data)
                except Exception as e:
                    print(f"[SCREENER] {ticker} skipped: {e}")
                    continue

            result["sectors"][sector_name] = sector_data

        # Guardar cache SOLO si es válido
        with _CACHE_LOCK:
            _CACHE["data"] = result
            _CACHE["ts"] = time.time()

        return result

    except Exception:
        with _CACHE_LOCK:
            if _CACHE["data"] is not None:
                return _CACHE["data"]
        raise

    finally:
        with _CACHE_LOCK:
            _INFLIGHT = False
            _INFLIGHT_EVENT.set()
