import requests
from datetime import date, datetime
from typing import Dict, Any, List


# ============================================================
# CONFIG
# ============================================================
URL_NOTES = "https://data912.com/live/arg_notes"
URL_BONDS = "https://data912.com/live/arg_bonds"

# Escenarios de dólar (en pesos)
DOLAR_OFFSETS = [-200, -100, 0, 100, 200]


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
# HELPERS
# ============================================================
def parse_date(s: str) -> date:
    y, m, d = s.split("-")
    return date(int(y), int(m), int(d))


def days_to_expiry(expiry: date) -> int:
    return (expiry - date.today()).days


def to_timestamp(d: date) -> int:
    return int(datetime(d.year, d.month, d.day).timestamp() * 1000)


def fetch_json(url: str):
    r = requests.get(url, timeout=15)
    r.raise_for_status()
    return r.json()


def fetch_dolar_al30() -> float:
    """
    Toma el dólar implícito desde AL30 (ask).
    """
    bonds = fetch_json(URL_BONDS)

    for item in bonds:
        if item.get("ticker") == "AL30" and item.get("ask"):
            return float(item["ask"])

    raise ValueError("No se encontró AL30 con campo 'ask'")


# ============================================================
# CORE
# ============================================================
def get_lecap_band_for_api() -> Dict[str, Any]:
    now = datetime.now().isoformat()

    # --- precios LECAPs ---
    notes = fetch_json(URL_NOTES)
    prices = {
        i["symbol"]: float(i["px_ask"])
        for i in notes
        if i.get("symbol") in LECAPS and i.get("px_ask")
    }

    # --- dólar hoy (AL30 ask) ---
    dolar_hoy = fetch_dolar_al30()

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

        # rendimiento en pesos
        rendimiento = (cfg["vpv"] / price) - 1.0

        # breakeven USD = 0
        break_even = dolar_hoy * (cfg["vpv"] / price)

        # escenarios USD (SIGNO CORRECTO)
        escenarios = {}
        for d in escenarios_dolar:
            escenarios[str(d)] = round((break_even / d - 1.0) * 100.0, 2)

        lecaps_out.append({
            "symbol": sym,
            "expiry": cfg["expiry"],
            "days_remaining": days,
            "price": round(price, 6),
            "vpv": cfg["vpv"],
            "rendimiento_directo": round(rendimiento, 6),
            "break_even": round(break_even, 2),
            "chart_point": {
                "x": to_timestamp(expiry),
                "y": round(break_even, 2)
            },
            "escenarios": escenarios
        })

    lecaps_out.sort(key=lambda x: x["days_remaining"])

    return {
        "ok": True,
        "as_of": now,
        "dolar_hoy": round(dolar_hoy, 2),
        "dolar_source": "AL30 ask (data912)",
        "escenarios_dolar": escenarios_dolar,
        "lecaps": lecaps_out
    }
