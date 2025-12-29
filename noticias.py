# ============================================================
# NOTICIAS FINANCIERAS – BACKEND INGECAPITAL (NEWSDATA.IO)
# ============================================================

import time
import requests
import datetime as dt

# ============================================================
# CONFIGURACIÓN
# ============================================================

NEWSDATA_API_KEY = "pub_fd353114f8294f019b96757767cd82e8"
NEWS_URL = "https://newsdata.io/api/1/news"

# Cache: 12 horas → máx 2 consultas por día
CACHE_TTL = 12 * 60 * 60  # segundos

# Cantidad de noticias a entregar a Horizons
MAX_NEWS = 8

_CACHE = {
    "ts": 0,
    "data": None
}

# ============================================================
# FETCH DESDE NEWSDATA
# ============================================================

def _fetch_news():
    params = {
        "apikey": NEWSDATA_API_KEY,
        "language": "es",
        "country": "ar",
        "category": "business",
        "size": MAX_NEWS
    }

    r = requests.get(NEWS_URL, params=params, timeout=20)
    r.raise_for_status()
    return r.json()

# ============================================================
# FUNCIÓN PRINCIPAL PARA EL API
# ============================================================

def get_financial_news_for_api():
    now = time.time()

    # Cache
    if _CACHE["data"] is not None and (now - _CACHE["ts"]) < CACHE_TTL:
        return _CACHE["data"]

    raw = _fetch_news()

    news = []
    for a in raw.get("results", []):
        news.append({
            "title": a.get("title"),
            "source": a.get("source_id"),
            "published_at": a.get("pubDate"),
            "snippet": a.get("description"),
            "url": a.get("link"),
            "country": a.get("country"),
            "category": a.get("category")
        })

    output = {
        "updated_at": dt.datetime.utcnow().isoformat() + "Z",
        "provider": "newsdata.io",
        "refresh_policy": "cada 12 horas",
        "news": news
    }

    _CACHE["data"] = output
    _CACHE["ts"] = now
    return output

