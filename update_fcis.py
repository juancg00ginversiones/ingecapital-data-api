"""
update_fcis.py
==============
Genera fcis_data.json con datos en vivo de FCIs de Balanz e IOL.
Fuente: api.argentinadatos.com
Corre en GitHub Actions junto con los demás scripts.
"""

import json
import datetime as dt
import requests

# ─── FUENTES ─────────────────────────────────────────────────────────────────
URL_MM_HOY   = "https://api.argentinadatos.com/v1/finanzas/fci/mercadoDinero/ultimo"
URL_MIX_HOY  = "https://api.argentinadatos.com/v1/finanzas/fci/rentaMixta/ultimo"
URL_RF_HOY   = "https://api.argentinadatos.com/v1/finanzas/fci/rentaFija/ultimo"
URL_RV_HOY   = "https://api.argentinadatos.com/v1/finanzas/fci/rentaVariable/ultimo"
URL_MM_AYER  = "https://api.argentinadatos.com/v1/finanzas/fci/mercadoDinero/penultimo"
URL_MIX_AYER = "https://api.argentinadatos.com/v1/finanzas/fci/rentaMixta/penultimo"
URL_RF_AYER  = "https://api.argentinadatos.com/v1/finanzas/fci/rentaFija/penultimo"
URL_RV_AYER  = "https://api.argentinadatos.com/v1/finanzas/fci/rentaVariable/penultimo"

# ─── CATÁLOGO CURADO ─────────────────────────────────────────────────────────
# api_match: substring a buscar en el nombre de la API
# clase: clase preferida a mostrar

FONDOS_CURADOS = [
    # ── BALANZ PESOS ──
    {"broker": "Balanz", "nombre": "Money Market",        "categoria": "Money Market $",   "moneda": "ARS", "rescate": "T+0", "riesgo": "Conservador", "api_match": "Balanz Capital Money Market",         "clase": "B"},
    {"broker": "Balanz", "nombre": "Lecaps",               "categoria": "Renta Fija $",     "moneda": "ARS", "rescate": "T+0", "riesgo": "Conservador", "api_match": "Balanz Lecaps",                       "clase": "A"},
    {"broker": "Balanz", "nombre": "Ahorro Corto Plazo",   "categoria": "Renta Fija $",     "moneda": "ARS", "rescate": "T+1", "riesgo": "Conservador", "api_match": "Balanz Capital Ahorro",               "clase": "A"},
    {"broker": "Balanz", "nombre": "Crédito Privado CP",   "categoria": "Renta Fija $",     "moneda": "ARS", "rescate": "T+1", "riesgo": "Moderado",    "api_match": "Balanz Credito Privado",              "clase": "A"},
    {"broker": "Balanz", "nombre": "ONs (Perf. III)",      "categoria": "Renta Fija $",     "moneda": "ARS", "rescate": "T+1", "riesgo": "Moderado",    "api_match": "Balanz Performance III",              "clase": "A"},
    {"broker": "Balanz", "nombre": "Institucional",        "categoria": "Renta Fija $",     "moneda": "ARS", "rescate": "T+1", "riesgo": "Moderado",    "api_match": "Balanz Institucional",                "clase": "A"},
    {"broker": "Balanz", "nombre": "Opportunity",          "categoria": "Renta Fija $",     "moneda": "ARS", "rescate": "T+0", "riesgo": "Moderado",    "api_match": "Balanz Opportunity",                  "clase": "A"},
    {"broker": "Balanz", "nombre": "Long Pesos",           "categoria": "Renta Fija $",     "moneda": "ARS", "rescate": "T+1", "riesgo": "Audaz",       "api_match": "Balanz Long Pesos",                   "clase": "A"},
    {"broker": "Balanz", "nombre": "Renta Fija Pesos",     "categoria": "Renta Fija $",     "moneda": "ARS", "rescate": "T+1", "riesgo": "Audaz",       "api_match": "Balanz Capital Renta Fija",            "clase": "A"},
    {"broker": "Balanz", "nombre": "Renta Mixta",          "categoria": "Renta Mixta",      "moneda": "ARS", "rescate": "T+1", "riesgo": "Moderado",    "api_match": "Balanz Excalibur Regisseur",           "clase": "B"},
    # ── BALANZ USD ──
    {"broker": "Balanz", "nombre": "Dólar Corto Plazo",    "categoria": "Renta Fija USD",   "moneda": "USD", "rescate": "T+1", "riesgo": "Conservador", "api_match": "Balanz Capital Estrategia I USD",      "clase": "A"},
    {"broker": "Balanz", "nombre": "Corporativo USD",      "categoria": "Renta Fija USD",   "moneda": "USD", "rescate": "T+1", "riesgo": "Moderado",    "api_match": "Balanz Ahorro en Dolares",             "clase": "A"},
    {"broker": "Balanz", "nombre": "Soberano USD",         "categoria": "Renta Fija USD",   "moneda": "USD", "rescate": "T+1", "riesgo": "Audaz",       "api_match": "Balanz Capital Renta Fija en Dolares", "clase": "A"},
    {"broker": "Balanz", "nombre": "Latam (sin Arg)",      "categoria": "Renta Fija USD",   "moneda": "USD", "rescate": "T+2", "riesgo": "Moderado",    "api_match": "Balanz Capital Sudamericano",          "clase": "A"},
    # ── IOL ──
    {"broker": "IOL",    "nombre": "Consultatio MM",            "categoria": "Money Market $", "moneda": "ARS", "rescate": "T+0", "riesgo": "Conservador", "api_match": "Consultatio Renta Nacional",        "clase": "B"},
    {"broker": "IOL",    "nombre": "Consultatio Ahorro Plus",   "categoria": "Renta Fija $",   "moneda": "ARS", "rescate": "T+1", "riesgo": "Conservador", "api_match": "Consultatio Ahorro Plus Argentina", "clase": "B"},
    {"broker": "IOL",    "nombre": "Consultatio Renta Local",   "categoria": "Renta Fija $",   "moneda": "ARS", "rescate": "T+1", "riesgo": "Moderado",    "api_match": "Consultatio Renta Local",          "clase": "B"},
    {"broker": "IOL",    "nombre": "Consultatio Estratégico",   "categoria": "Renta Mixta",    "moneda": "ARS", "rescate": "T+1", "riesgo": "Moderado",    "api_match": "Consultatio Multimercado I",       "clase": "C"},
    {"broker": "IOL",    "nombre": "Consultatio Retorno Total", "categoria": "Renta Mixta",    "moneda": "ARS", "rescate": "T+1", "riesgo": "Audaz",       "api_match": "Consultatio Retorno Total",        "clase": ""},
    {"broker": "IOL",    "nombre": "SBS Patrimonio",            "categoria": "Renta Fija $",   "moneda": "ARS", "rescate": "T+1", "riesgo": "Moderado",    "api_match": "SBS Patrimonio",                   "clase": "B"},
    {"broker": "IOL",    "nombre": "IOL Portafolio Potenciado", "categoria": "Renta Mixta",    "moneda": "ARS", "rescate": "T+1", "riesgo": "Moderado",    "api_match": "IOL Portafolio Potenciado",        "clase": "A"},
    {"broker": "IOL",    "nombre": "IOL Cash Management",       "categoria": "Renta Fija $",   "moneda": "ARS", "rescate": "T+1", "riesgo": "Conservador", "api_match": "IOL Cash Management",              "clase": "A"},
    {"broker": "IOL",    "nombre": "IOL Dólar Ahorro Plus",     "categoria": "Renta Fija USD", "moneda": "USD", "rescate": "T+1", "riesgo": "Conservador", "api_match": "IOL Dolar Ahorro Plus",            "clase": "D"},
]

# ─── HELPERS ─────────────────────────────────────────────────────────────────

def fetch_api(url):
    r = requests.get(url, timeout=15)
    r.raise_for_status()
    return r.json()

def match_fondo(catalogo, datos_hoy, datos_ayer):
    """Busca el fondo en la API por substring de nombre y clase preferida."""
    api_match = catalogo["api_match"].lower()
    clase     = catalogo["clase"].lower()

    candidatos = [
        f for f in datos_hoy
        if f.get("fondo") and api_match in f["fondo"].lower()
    ]
    if not candidatos:
        return None

    # Preferir la clase indicada
    clase_exacta = [
        f for f in candidatos
        if f"clase {clase}" in f["fondo"].lower()
    ]
    pool = clase_exacta if clase_exacta else candidatos

    # De ese pool, el de mayor patrimonio con datos válidos
    con_datos = [f for f in pool if f.get("vcp") and f.get("patrimonio", 0) > 0]
    elegido   = max(con_datos, key=lambda f: f["patrimonio"]) if con_datos else pool[0]

    # Buscar mismo fondo en datos de ayer para calcular TNA
    nombre_elegido = elegido["fondo"].lower()
    ayer_match = next(
        (f for f in datos_ayer if f.get("fondo") and f["fondo"].lower() == nombre_elegido),
        None
    )

    vcp_hoy  = elegido.get("vcp")
    vcp_ayer = ayer_match.get("vcp") if ayer_match else None

    tna = None
    if vcp_hoy and vcp_ayer and vcp_ayer > 0:
        # Calcular días reales entre las dos fechas para no distorsionar la TNA
        fecha_hoy  = elegido.get("fecha")
        fecha_ayer = ayer_match.get("fecha") if ayer_match else None
        if fecha_hoy and fecha_ayer:
            try:
                d_hoy  = dt.date.fromisoformat(fecha_hoy)
                d_ayer = dt.date.fromisoformat(fecha_ayer)
                dias   = (d_hoy - d_ayer).days
            except Exception:
                dias = 1
        else:
            dias = 1

        # Solo calcular TNA si las fechas son consecutivas o muy cercanas (máx 5 días)
        # Si son muy lejanas (fin de semana largo, feriados seguidos) no tiene sentido
        if 1 <= dias <= 5:
            tna_raw = ((vcp_hoy / vcp_ayer) - 1) / dias * 365 * 100
            # Filtrar valores absurdos: TNA válida entre -50% y 500%
            if -50 <= tna_raw <= 500:
                tna = round(tna_raw, 2)

    return {
        "nombre_api": elegido["fondo"],
        "fecha":      elegido.get("fecha"),
        "vcp":        vcp_hoy,
        "patrimonio": elegido.get("patrimonio"),
        "tna":        tna,
    }

# ─── MAIN ─────────────────────────────────────────────────────────────────────

def main():
    today = dt.date.today().isoformat()
    print(f"=== update_fcis.py | {today} ===\n")

    print("→ Descargando datos de argentinadatos.com...")
    mm_hoy   = fetch_api(URL_MM_HOY)
    mix_hoy  = fetch_api(URL_MIX_HOY)
    rf_hoy   = fetch_api(URL_RF_HOY)
    rv_hoy   = fetch_api(URL_RV_HOY)
    mm_ayer  = fetch_api(URL_MM_AYER)
    mix_ayer = fetch_api(URL_MIX_AYER)
    rf_ayer  = fetch_api(URL_RF_AYER)
    rv_ayer  = fetch_api(URL_RV_AYER)

    datos_hoy  = mm_hoy  + mix_hoy  + rf_hoy  + rv_hoy
    datos_ayer = mm_ayer + mix_ayer + rf_ayer + rv_ayer
    print(f"   Fondos disponibles hoy:  {len(datos_hoy)}")
    print(f"   Fondos disponibles ayer: {len(datos_ayer)}")

    print("\n→ Procesando catálogo curado...")
    output = []
    ok = 0
    sin_datos = 0

    for cat in FONDOS_CURADOS:
        resultado = match_fondo(cat, datos_hoy, datos_ayer)

        fondo_out = {
            "broker":    cat["broker"],
            "nombre":    cat["nombre"],
            "categoria": cat["categoria"],
            "moneda":    cat["moneda"],
            "rescate":   cat["rescate"],
            "riesgo":    cat["riesgo"],
        }

        if resultado:
            fondo_out.update(resultado)
            tna_str = f"{resultado['tna']:.2f}%" if resultado['tna'] else "N/D"
            print(f"  ✅ [{cat['broker']:6s}] {cat['nombre']:25s} | TNA: {tna_str:8s} | VCP: {resultado['vcp']}")
            ok += 1
        else:
            fondo_out.update({"nombre_api": None, "fecha": None, "vcp": None, "patrimonio": None, "tna": None})
            print(f"  ⚠️  [{cat['broker']:6s}] {cat['nombre']:25s} | Sin match en API")
            sin_datos += 1

        output.append(fondo_out)

    result = {
        "_updated": today,
        "_fuente":  "api.argentinadatos.com",
        "fondos":   output,
    }

    with open("fcis_data.json", "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"\n{'─'*45}")
    print(f"  fcis_data.json → {ok} fondos con datos, {sin_datos} sin match")
    print(f"{'─'*45}")


if __name__ == "__main__":
    main()
