import requests
import math
from datetime import date, datetime
from typing import Dict, Any, List


# ============================================================
# CONFIG
# ============================================================
URL_NOTES = "https://data912.com/live/arg_notes"
URL_BONDS = "https://data912.com/live/arg_bonds"


# ============================================================
# LISTA CURADA DE INSTRUMENTOS
# source: "notes" | "bonds"
# ============================================================
INSTRUMENTS = {
    # LECAP
    "S16E6": {"expiry": "2026-01-16", "vpv": 119.625, "source": "notes"},
    "S27F6": {"expiry": "2026-02-27", "vpv": 125.842, "source": "notes"},
    "S30A6": {"expiry": "2026-04-30", "vpv": 127.486, "source": "notes"},
    "S29Y6": {"expiry": "2026-05-29", "vpv": 130.661, "source": "notes"},
    "S30O6": {"expiry": "2026-10-30", "vpv": 135.278, "source": "notes"},

    # BONCAP
    "T15D5": {"expiry": "2025-12-15", "vpv": 170.838, "source": "bonds"},
    "T30E6": {"expiry": "2026-01-30", "vpv": 142.222, "source": "bonds"},
    "T13F6": {"expiry": "2026-02-13", "vpv": 144.966, "source": "bonds"},
    "T30J6": {"expiry": "2026-06-30", "vpv": 144.896, "source": "bonds"},
    "T15E7": {"expiry": "2027-01-15", "vpv": 161.104, "source": "bonds"},
}


# ============================================================
# HELPERS
# ============================================================
def parse_date(s: str) -> date:
    y, m, d = s.split("-")
    return date(int(y), int(m), int(d))


def days_to_expiry(expiry: date) -> int:
    return (expiry - date.today()).days


def fetch_json(url: str) -> List[Dict[str, Any]]:
    r = requests.get(url, timeout=15)
    r.raise_for_status()
    return r.json()


def compute_metrics(price: float, vpv: float, days: int):
    rendimiento = (vpv / price) - 1.0
    tna = (1.0 + rendimiento) ** (365.0 / days) - 1.0
    tem = (1.0 + tna) ** (1.0 / 12.0) - 1.0
    return rendimiento, tna, tem


# ============================================================
# CORE ENGINE
# ============================================================
def get_letras_bonos_for_api() -> Dict[str, Any]:
    today = date.today()
    now = datetime.now().isoformat()

    notes_data = fetch_json(URL_NOTES)
    bonds_data = fetch_json(URL_BONDS)

    price_map: Dict[str, float] = {}

    for item in notes_data:
        sym = item.get("symbol")
        if sym in INSTRUMENTS and INSTRUMENTS[sym]["source"] == "notes":
            px = item.get("px_ask")
            if px:
                price_map[sym] = float(px)

    for item in bonds_data:
        sym = item.get("symbol")
        if sym in INSTRUMENTS and INSTRUMENTS[sym]["source"] == "bonds":
            px = item.get("px_ask")
            if px:
                price_map[sym] = float(px)

    rows = []

    for sym, cfg in INSTRUMENTS.items():
        expiry = parse_date(cfg["expiry"])
        days = days_to_expiry(expiry)

        # 🔴 Vencido → se ignora
        if days <= 0:
            continue

        price = price_map.get(sym)

        # 🔴 Sin precio → se ignora
        if not price or price <= 0:
            continue

        rendimiento, tna, tem = compute_metrics(
            price=price,
            vpv=cfg["vpv"],
            days=days
        )

        rows.append({
            "symbol": sym,
            "expiry": cfg["expiry"],
            "days_remaining": days,
            "price": round(price, 6),
            "vpv": round(cfg["vpv"], 6),
            "rendimiento_directo": round(rendimiento, 8),
            "tna": round(tna, 8),
            "tem": round(tem, 8),
        })

    rows.sort(key=lambda x: x["days_remaining"])

    return {
        "ok": True,
        "as_of": now,
        "total": len(rows),
        "items": rows,
    }
