# ============================================================
# NOTICIAS FINANCIERAS – FILTRO AVANZADO (NEWSDATA.IO)
# ============================================================

import time
import requests
import datetime as dt

# ============================================================
# CONFIG
# ============================================================

NEWSDATA_API_KEY = "pub_fd353114f8294f019b96757767cd82e8"
NEWS_URL = "https://newsdata.io/api/1/news"

CACHE_TTL = 12 * 60 * 60  # 12 horas
MAX_NEWS = 8

# Keywords financieros (OR lógico)
FINANCIAL_KEYWORDS = (
    "banco central OR reserva federal OR fed OR inflación OR tasas OR "
    "acciones OR mercado bursátil OR wall street OR s&p OR nasdaq OR "
    "sp500 OR qqq OR dow jones OR dólar OR bonos OR deuda OR "
    "oro OR plata OR petróleo OR nvidia OR tesla OR apple OR microsoft OR "
    "trump"
)

_CACHE = {
    "ts": 0,
    "data": None
}

# ============================================================
# FETCH
# ============================================================

def _fetch_news():
    params = {
        "apikey": NEWSDATA_API_KEY,
        "language": "es",
        "q": FINANCIAL_KEYWORDS,
        "category": "business",
        "size": MAX_NEWS
    }

    r = requests.get(NEWS_URL, params=params, timeout=20)
    r.raise_for_status()
    return r.json()

# ============================================================
# API FUNCTION
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
        "filter": "financiero / mercado (macro, acciones, commodities)",
        "refresh_policy": "cada 12 horas",
        "news": news
    }

    _CACHE["data"] = output
    _CACHE["ts"] = now
    return output
