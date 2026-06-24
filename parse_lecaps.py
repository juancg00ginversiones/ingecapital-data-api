# ============================================================
# PARSE LECAPS — Lee el PDF del IAMC y genera lecaps_data.json
# Uso: python parse_lecaps.py archivo.pdf
# Resultado: lecaps_data.json listo para subir a GitHub
# ============================================================

import pdfplumber
import json
import re
import sys
import datetime
import math

def limpiar_numero(s):
    if not s: return None
    s = str(s).strip().replace(',', '.').replace('%', '').replace('$', '').strip()
    try: return float(s)
    except: return None

def limpiar_fecha(s):
    if not s: return None
    s = str(s).strip()
    for fmt in ['%d-%b-%y', '%d-%b-%Y', '%d/%m/%Y', '%d/%m/%y']:
        try:
            return datetime.datetime.strptime(s, fmt).strftime('%Y-%m-%d')
        except: pass
    return s

def extraer_seccion(texto, inicio, fin=None):
    idx = texto.find(inicio)
    if idx == -1: return ""
    if fin:
        idx2 = texto.find(fin, idx + len(inicio))
        return texto[idx:idx2] if idx2 != -1 else texto[idx:]
    return texto[idx:]

def calcular_tasas(precio, monto_vto, dias):
    """
    Calcula TEM, TNA, TEA con máxima precisión
    desde precio y monto de vencimiento.
    """
    try:
        if not precio or not monto_vto or not dias:
            return None, None, None
        if precio <= 0 or dias <= 0:
            return None, None, None

        # Rendimiento total del período
        rendimiento = monto_vto / precio - 1.0

        # TEM = rendimiento mensualizado (base 30 días)
        tem = (math.pow(1 + rendimiento, 30.0 / dias) - 1) * 100

        # TNA = rendimiento × (365 / dias) — convención lineal
        tna = rendimiento * (365.0 / dias) * 100

        # TEA = rendimiento anualizado compuesto
        tea = (math.pow(1 + rendimiento, 365.0 / dias) - 1) * 100

        return round(tem, 6), round(tna, 6), round(tea, 6)
    except:
        return None, None, None

def calcular_rendimiento_pct(precio, monto_vto):
    """Rendimiento total del período en %"""
    try:
        if not precio or not monto_vto or precio <= 0:
            return None
        return round((monto_vto / precio - 1) * 100, 6)
    except:
        return None

def parsear_lecaps(texto):
    resultado = []
    seccion = extraer_seccion(texto,
        "LETRAS DEL TESORO CAPITALIZABLES EN PESOS (LECAP)",
        "BONOS DEL TESORO CAPITALIZABLES EN PESOS (BONCAP)")

    patron = r'(S\w+)\s+(\d{2}-\w{3}-\d{2,4})\s+(\d{2}-\w{3}-\d{2,4})\s+(\d+)\s+([\d,.]+)\s+([\d.]+%)\s+\d{2}-\w{3}-\d{2,4}\s+\d{2}-\w{3}-\d{2,4}\s+([\d,.]+)\s+([\d.]+%)\s+([\d.]+%)\s+([\d.]+%)\s+([\d.]+%)\s+([\d,.]+)'

    for m in re.finditer(patron, seccion):
        precio    = limpiar_numero(m.group(7))
        monto_vto = limpiar_numero(m.group(5))
        dias      = int(m.group(4))

        # Recalcular con precisión máxima
        tem, tna, tea = calcular_tasas(precio, monto_vto, dias)
        rendimiento_pct = calcular_rendimiento_pct(precio, monto_vto)

        resultado.append({
            "especie":         m.group(1),
            "tipo":            "LECAP",
            "fecha_emision":   limpiar_fecha(m.group(2)),
            "fecha_pago":      limpiar_fecha(m.group(3)),
            "plazo_dias":      dias,
            "monto_vto":       monto_vto,
            "tasa_licitacion": limpiar_numero(m.group(6)),
            "precio":          precio,
            "rendimiento_pct": rendimiento_pct,
            "tna":             tna,
            "tea":             tea,
            "tem":             tem,
            "dm":              limpiar_numero(m.group(12)),
        })
    return resultado

def parsear_boncaps(texto):
    resultado = []
    seccion = extraer_seccion(texto,
        "BONOS DEL TESORO CAPITALIZABLES EN PESOS (BONCAP)",
        "BONOS DEL TESORO TASA VARIABLE TAMAR Y DUALES")

    patron = r'(T\w+)\s+(\d{2}-\w{3}-\d{2,4})\s+(\d{2}-\w{3}-\d{2,4})\s+(\d+)\s+([\d,.]+)\s+([\d.]+%)\s+\d{2}-\w{3}-\d{2,4}\s+\d{2}-\w{3}-\d{2,4}\s+([\d,.]+)\s+([\d.]+%)\s+([\d.]+%)\s+([\d.]+%)\s+([\d.]+%)\s+([\d,.]+)'

    for m in re.finditer(patron, seccion):
        if m.group(1).startswith('T') and not m.group(1).startswith('TT') and not m.group(1).startswith('TM'):
            precio    = limpiar_numero(m.group(7))
            monto_vto = limpiar_numero(m.group(5))
            dias      = int(m.group(4))

            tem, tna, tea = calcular_tasas(precio, monto_vto, dias)
            rendimiento_pct = calcular_rendimiento_pct(precio, monto_vto)

            resultado.append({
                "especie":         m.group(1),
                "tipo":            "BONCAP",
                "fecha_emision":   limpiar_fecha(m.group(2)),
                "fecha_pago":      limpiar_fecha(m.group(3)),
                "plazo_dias":      dias,
                "monto_vto":       monto_vto,
                "tasa_licitacion": limpiar_numero(m.group(6)),
                "precio":          precio,
                "rendimiento_pct": rendimiento_pct,
                "tna":             tna,
                "tea":             tea,
                "tem":             tem,
                "dm":              limpiar_numero(m.group(12)),
            })
    return resultado

def parsear_cer(texto):
    resultado = []
    seccion = extraer_seccion(texto, "Bonos y Letras Ajustables por CER")

    patron = r'((?:X|TZX|TX)\w+)\s+(\d{2}-\w{3}-\d{2,4})\s+(\d{2}-\w{3}-\d{2,4})\s+([\d,.]+)\s+([\d,.]+)\s+[\d/]+\s+\d{2}-\w{3}-\d{2,4}\s+([\d,.]+)\s+([\d.]+)\s+(-?[\d.]+%)'

    for m in re.finditer(patron, seccion):
        resultado.append({
            "especie":       m.group(1),
            "tipo":          "CER",
            "fecha_emision": limpiar_fecha(m.group(2)),
            "fecha_pago":    limpiar_fecha(m.group(3)),
            "cer_emision":   limpiar_numero(m.group(4)),
            "cer_calculo":   limpiar_numero(m.group(5)),
            "precio":        limpiar_numero(m.group(6)),
            "dm":            limpiar_numero(m.group(7)),
            "tir":           limpiar_numero(m.group(8)),
        })
    return resultado

def parsear_tamar(texto):
    resultado = []
    seccion = extraer_seccion(texto, "BONOS TAMAR", "BONOS DUALES")

    patron = r'(M\w+|TMF\w+)\s+(\d{2}-\w{3}-\d{2,4})\s+(\d{2}-\w{3}-\d{2,4})\s+(\d+)\s+([\d.]+%)\s+([\d.]+%)\s+([\d,.]+)\s+\d{2}-\w{3}-\d{2,4}\s+\d{2}-\w{3}-\d{2,4}\s+([\d,.]+)\s+([\d,.]+)'

    for m in re.finditer(patron, seccion):
        spread_raw  = limpiar_numero(m.group(5))   # spread sobre TAMAR en %
        tem_tamar   = limpiar_numero(m.group(6))   # TEM estimada con TAMAR actual
        precio      = limpiar_numero(m.group(8))
        dias        = int(m.group(4))

        # Estimar TNA y TEA desde tem_tamar si está disponible
        tna_est, tea_est = None, None
        if tem_tamar and dias:
            try:
                tna_est = round(tem_tamar * (365.0 / 30), 6)
                tea_est = round((math.pow(1 + tem_tamar / 100, 365.0 / 30) - 1) * 100, 6)
            except:
                pass

        resultado.append({
            "especie":       m.group(1),
            "tipo":          "TAMAR",
            "fecha_emision": limpiar_fecha(m.group(2)),
            "fecha_pago":    limpiar_fecha(m.group(3)),
            "plazo_dias":    dias,
            "spread":        spread_raw,
            "tem_tamar":     tem_tamar,
            "tna":           tna_est,
            "tea":           tea_est,
            "monto_vto":     limpiar_numero(m.group(7)),
            "precio":        precio,
            "dm":            limpiar_numero(m.group(9)),
        })
    return resultado

def main():
    pdf_path = sys.argv[1] if len(sys.argv) > 1 else "lecaps.pdf"

    print(f"📄 Leyendo {pdf_path}...")

    texto_completo = ""
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            t = page.extract_text()
            if t: texto_completo += t + "\n"

    print("🔍 Parseando secciones...")

    lecaps  = parsear_lecaps(texto_completo)
    boncaps = parsear_boncaps(texto_completo)
    cer     = parsear_cer(texto_completo)
    tamar   = parsear_tamar(texto_completo)

    # Detectar fecha del informe
    fecha_match = re.search(r'(\d{2}/\d{2}/\d{4})', texto_completo)
    fecha_informe = fecha_match.group(1) if fecha_match else datetime.date.today().strftime('%d/%m/%Y')

    output = {
        "updated_at":    datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "fecha_informe": fecha_informe,
        "resumen": {
            "lecaps":  len(lecaps),
            "boncaps": len(boncaps),
            "cer":     len(cer),
            "tamar":   len(tamar),
        },
        "lecaps":  lecaps,
        "boncaps": boncaps,
        "cer":     cer,
        "tamar":   tamar,
        "todos":   lecaps + boncaps + cer + tamar,
    }

    with open("lecaps_data.json", "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\n✅ lecaps_data.json generado:")
    print(f"   LECAPs:  {len(lecaps)}")
    print(f"   BONCAPs: {len(boncaps)}")
    print(f"   CER:     {len(cer)}")
    print(f"   TAMAR:   {len(tamar)}")
    print(f"   Total:   {len(lecaps)+len(boncaps)+len(cer)+len(tamar)} instrumentos")

    # Mostrar ejemplo de precisión
    if lecaps:
        ej = lecaps[0]
        print(f"\n📊 Ejemplo de precisión ({ej['especie']}):")
        print(f"   Precio: {ej['precio']} | Monto vto: {ej['monto_vto']} | Días: {ej['plazo_dias']}")
        print(f"   TEM: {ej['tem']}% | TNA: {ej['tna']}% | TEA: {ej['tea']}%")

if __name__ == "__main__":
    main()
