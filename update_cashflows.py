"""
update_cashflows.py
===================
Genera cashflow_bonos.json y cashflow_ons.json a partir del config.json
de arisbdar/rendimientos-ar + precios en tiempo real de data912.com.

Compatible 100% con bonos.py del backend (Render).

Ejecutar desde GitHub Actions (ingecapital-data-api) diariamente.
"""

import json
import datetime as dt
import requests

CONFIG_URL = "https://raw.githubusercontent.com/arisbdar/rendimientos-ar/main/public/config.json"
LIVE_URL   = "https://data912.com/live/arg_bonds"

# ─── HELPERS FINANCIEROS ──────────────────────────────────────────────────────

def yearfrac(d0, d1):
    return (d1 - d0).days / 365.0

def solve_ytm(cfs, price, as_of):
    lo, hi = -0.95, 5.0
    for _ in range(100):
        mid = (lo + hi) / 2
        pv  = sum(cf["flow"] / ((1 + mid) ** yearfrac(as_of, cf["date"])) for cf in cfs)
        if abs(pv - price) < 1e-6:
            return mid
        if pv > price:
            lo = mid
        else:
            hi = mid
    return mid

def duration_mod(cfs, y, price, as_of):
    num = sum(
        yearfrac(as_of, cf["date"]) * cf["flow"] / ((1 + y) ** yearfrac(as_of, cf["date"]))
        for cf in cfs
    )
    return (num / price) / (1 + y)

# ─── FETCH ────────────────────────────────────────────────────────────────────

def fetch_config():
    print("→ Descargando config.json (arisbdar)...")
    r = requests.get(CONFIG_URL, timeout=15)
    r.raise_for_status()
    return r.json()

def fetch_precios():
    print("→ Descargando precios live (data912.com)...")
    r = requests.get(LIVE_URL, timeout=15)
    r.raise_for_status()
    return {row["symbol"]: float(row["c"]) for row in r.json()}

# ─── PROCESAR FLUJOS ─────────────────────────────────────────────────────────

def parse_flujos(flujos_raw, as_of):
    """Filtra flujos futuros y convierte fecha a date."""
    return [
        {
            "date": dt.date.fromisoformat(f["fecha"]),
            "flow": float(f["monto"]),
        }
        for f in flujos_raw
        if dt.date.fromisoformat(f["fecha"]) > as_of
    ]

def calcular(cfs, precio, as_of):
    ytm = solve_ytm(cfs, precio, as_of)
    dur = duration_mod(cfs, ytm, precio, as_of)
    return ytm, dur

def flujos_a_json(cfs, ytm, dur, precio, residual, nombre=None):
    """Arma la lista de flujos en formato compatible con bonos.py."""
    rows = []
    for cf in cfs:
        row = {
            "fecha":         cf["date"].isoformat(),
            "flujo_calc":    round(cf["flow"], 6),
        }
        rows.append(row)
    # Colgamos los campos calculados en el primer elemento (bonos.py no los usa
    # directamente de aquí, pero sirven para debug y para el endpoint /bonds)
    if rows:
        rows[0]["_meta"] = {
            "ytm":      round(ytm, 6),
            "duration": round(dur, 4),
            "precio":   precio,
            "residual": round(residual, 4),
            "parity":   round((precio / residual) * 100, 4) if residual > 0 else None,
        }
        if nombre:
            rows[0]["_meta"]["nombre"] = nombre
    return rows

# ─── SOBERANOS ────────────────────────────────────────────────────────────────

def procesar_soberanos(config, precios, as_of):
    print("\n─── Bonos Soberanos ───")
    out = {}

    for ticker, data in config["soberanos"].items():
        precio = precios.get(ticker + "D")
        if precio is None:
            print(f"  ⚠  {ticker}: sin precio en data912")
            continue

        cfs = parse_flujos(data["flujos"], as_of)
        if not cfs:
            print(f"  ⚠  {ticker}: sin flujos futuros")
            continue

        # Residual: suma de flujos futuros, capeado en 100
        # (para bonos con amortización parcial ya realizada, la suma
        #  de flujos restantes refleja el capital pendiente)
        residual = min(sum(cf["flow"] for cf in cfs), 100.0)

        try:
            ytm, dur = calcular(cfs, precio, as_of)
        except Exception as e:
            print(f"  ⚠  {ticker}: error TIR → {e}")
            continue

        out[ticker] = flujos_a_json(cfs, ytm, dur, precio, residual)
        print(f"  ✅ {ticker:6s} | precio={precio:6.2f} | TIR={ytm*100:5.2f}% | Dur={dur:.2f}a | {len(cfs)} flujos")

    return out

# ─── ONs ──────────────────────────────────────────────────────────────────────

def procesar_ons(config, precios, as_of):
    print("\n─── ONs Corporativas ───")
    out = {}

    for ticker, data in config["ons"].items():
        ticker_d912 = data.get("ticker_d912", ticker + "D")
        precio      = precios.get(ticker_d912)
        nombre      = data.get("nombre", ticker)

        if precio is None:
            print(f"  ⚠  {ticker} ({nombre}): sin precio en data912")
            continue

        cfs = parse_flujos(data["flujos"], as_of)
        if not cfs:
            print(f"  ⚠  {ticker}: sin flujos futuros")
            continue

        # ONs son en su mayoría bullet o con amortizaciones parciales.
        # Sin información separada de amort/interés, usamos residual=100.
        residual = 100.0

        try:
            ytm, dur = calcular(cfs, precio, as_of)
        except Exception as e:
            print(f"  ⚠  {ticker}: error TIR → {e}")
            continue

        out[ticker] = flujos_a_json(cfs, ytm, dur, precio, residual, nombre=nombre)
        print(f"  ✅ {ticker:6s} ({nombre:25s}) | precio={precio:6.2f} | TIR={ytm*100:5.2f}% | Dur={dur:.2f}a")

    return out

# ─── MAIN ─────────────────────────────────────────────────────────────────────

def main():
    as_of = dt.date.today()
    print(f"╔══════════════════════════════════════╗")
    print(f"  update_cashflows.py  |  {as_of}  ")
    print(f"╚══════════════════════════════════════╝\n")

    config  = fetch_config()
    precios = fetch_precios()

    bonos = procesar_soberanos(config, precios, as_of)
    ons   = procesar_ons(config, precios, as_of)

    # ── Guardar cashflow_bonos.json ──
    with open("cashflow_bonos.json", "w", encoding="utf-8") as f:
        json.dump({"_updated": as_of.isoformat(), "bonos": bonos}, f, ensure_ascii=False, indent=2)

    # ── Guardar cashflow_ons.json ──
    with open("cashflow_ons.json", "w", encoding="utf-8") as f:
        json.dump({"_updated": as_of.isoformat(), "ons": ons}, f, ensure_ascii=False, indent=2)

    print(f"\n{'─'*45}")
    print(f"  cashflow_bonos.json → {len(bonos):2d} bonos soberanos")
    print(f"  cashflow_ons.json   → {len(ons):2d} ONs corporativas")
    print(f"{'─'*45}")


if __name__ == "__main__":
    main()
