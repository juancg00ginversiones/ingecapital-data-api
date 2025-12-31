import requests
from datetime import date, datetime
from typing import Dict, Any, List


# ============================================================
# CONFIG
# ============================================================
URL_NOTES = "https://data912.com/live/arg_notes"
URL_MEP = "https://data912.com/live/mep"

# Escenarios de dólar (en pesos) alrededor del dólar actual
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
    r = requests.get(url, timeout=20)
    r.raise_for_status()
    return r.json()


def fetch_dolar_al30_from_mep() -> float:
    """
    Dólar actual = AL30 ask tomado desde https://data912.com/live/mep

    Ejemplo de item:
    {
      "ticker": "AL30",
      "bid": ...,
      "ask": 1481.1083,
      ...
    }
    """
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

    # --- dólar actual (AL30 ask desde /live/mep) ---
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

        # Rendimiento en pesos
        rendimiento = (vpv / price) - 1.0

        # Breakeven USD = 0
        # D_BE = D_hoy * (VPV / Precio)
        break_even = dolar_hoy * (vpv / price)

        # Escenarios: retorno USD (%) = (D_BE / D_scenario) - 1
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

    return {
        "ok": True,
        "as_of": now,
        "dolar_hoy": round(dolar_hoy, 2),
        "dolar_source": "AL30 ask (data912 /live/mep)",
        "escenarios_dolar": escenarios_dolar,
        "lecaps": lecaps_out
    }
