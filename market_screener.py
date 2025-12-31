import datetime
import time
import traceback

from indicators import analyze_ticker
from tickers import TICKERS_BY_SECTOR

# ============================================================
# CONFIG
# ============================================================

CACHE_TTL_SECONDS = 20 * 60  # 20 minutos

_MARKET_SCREENER_CACHE = {
    "timestamp": None,
    "data": None
}

# ============================================================
# INTERNAL
# ============================================================

def _is_cache_valid():
    if _MARKET_SCREENER_CACHE["timestamp"] is None:
        return False

    age = time.time() - _MARKET_SCREENER_CACHE["timestamp"]
    return age < CACHE_TTL_SECONDS


def _build_market_screener():
    """
    Construye el market screener completo (lento).
    Se llama SOLO cuando el cache expira.
    """

    result = {
        "as_of": datetime.datetime.utcnow().isoformat(),
        "sectors": {}
    }

    for sector, tickers in TICKERS_BY_SECTOR.items():
        sector_data = []

        for ticker in tickers:
            try:
                data = analyze_ticker(ticker)
                if data:
                    sector_data.append(data)
            except Exception as e:
                print(f"[ERROR] {ticker}: {e}")
                traceback.print_exc()
                continue

        result["sectors"][sector] = sector_data

    return result


# ============================================================
# PUBLIC API
# ============================================================

def get_market_screener_for_api():
    """
    Endpoint principal consumido por Horizons.
    Usa cache en memoria (20 minutos).
    """

    if _is_cache_valid():
        return _MARKET_SCREENER_CACHE["data"]

    # Cache vencido → recalcular
    data = _build_market_screener()

    _MARKET_SCREENER_CACHE["timestamp"] = time.time()
    _MARKET_SCREENER_CACHE["data"] = data

    return data


