# ============================================================
# NOTICIAS FINANCIERAS – BACKEND INGECAPITAL (ESTABLE)
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

# Noticias a entregar a Horizons
MAX_NEWS = 8

_CACHE = {
    "ts": 0,
    "data": None
}

# ============================================================
# FETCH DESDE NEWSDATA (ESTABLE)
# ============================================================

def _fetch_news():
    params = {
        "apikey": NEWSDATA_API_KEY,
        "language": "es",
        "country": "ar",        # 🔴 CLAVE PARA EVITAR 422
        "category": "business",
        "size": 20              # traemos más y filtramos luego
    }

    r = requests.get(NEWS_URL, params=params, timeout=20)
    r.raise_for_status()
    return r.json()


# ============================================================
# FILTRO FINANCIERO LOCAL (SEGURO)
# ============================================================

FINANCIAL_TERMS = [
    "banco central", "fed", "reserva federal", "inflación", "tasas",
    "acciones", "mercado", "wall street", "nasdaq", "s&p", "sp500",
    "bonos", "deuda", "dólar", "oro", "plata", "petróleo",
    "nvidia", "tesla", "apple", "microsoft", "trump"
]

def _is_financial(article: dict) -> bool:
    text = f"{article.get('title','')} {article.get('description','')}".lower()
    return any(term in text for term in FINANCIAL_TERMS)

# ============================================================
# API FUNCTION
# ============================================================

def get_financial_news_for_api():
    now = time.time()

    # Cache
    if _CACHE["data"] is not None and (now - _CACHE["ts"]) < CACHE_TTL:
        return _CACHE["data"]

    raw = _fetch_news()

    filtered = []
    for a in raw.get("results", []):
        if _is_financial(a):
            filtered.append({
                "title": a.get("title"),
                "source": a.get("source_id"),
                "published_at": a.get("pubDate"),
                "snippet": a.get("description"),
                "url": a.get("link"),
                "country": a.get("country"),
                "category": a.get("category")
            })
        if len(filtered) >= MAX_NEWS:
            break

    output = {
        "updated_at": dt.datetime.utcnow().isoformat() + "Z",
        "provider": "newsdata.io",
        "filter": "business + filtro financiero local",
        "refresh_policy": "cada 12 horas",
        "news": filtered
    }

    _CACHE["data"] = output
    _CACHE["ts"] = now
    return output

