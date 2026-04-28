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

def parsear_lecaps(texto):
    resultado = []
    seccion = extraer_seccion(texto, 
        "LETRAS DEL TESORO CAPITALIZABLES EN PESOS (LECAP)",
        "BONOS DEL TESORO CAPITALIZABLES EN PESOS (BONCAP)")
    
    patron = r'(S\w+)\s+(\d{2}-\w{3}-\d{2,4})\s+(\d{2}-\w{3}-\d{2,4})\s+(\d+)\s+([\d,.]+)\s+([\d.]+%)\s+\d{2}-\w{3}-\d{2,4}\s+\d{2}-\w{3}-\d{2,4}\s+([\d,.]+)\s+([\d.]+%)\s+([\d.]+%)\s+([\d.]+%)\s+([\d.]+%)\s+([\d,.]+)'
    
    for m in re.finditer(patron, seccion):
        resultado.append({
            "especie":        m.group(1),
            "tipo":           "LECAP",
            "fecha_emision":  limpiar_fecha(m.group(2)),
            "fecha_pago":     limpiar_fecha(m.group(3)),
            "plazo_dias":     int(m.group(4)),
            "monto_vto":      limpiar_numero(m.group(5)),
            "tasa_licitacion":limpiar_numero(m.group(6)),
            "precio":         limpiar_numero(m.group(7)),
            "rendimiento_pct":limpiar_numero(m.group(8)),
            "tna":            limpiar_numero(m.group(9)),
            "tea":            limpiar_numero(m.group(10)),
            "tem":            limpiar_numero(m.group(11)),
            "dm":             limpiar_numero(m.group(12)),
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
            resultado.append({
                "especie":        m.group(1),
                "tipo":           "BONCAP",
                "fecha_emision":  limpiar_fecha(m.group(2)),
                "fecha_pago":     limpiar_fecha(m.group(3)),
                "plazo_dias":     int(m.group(4)),
                "monto_vto":      limpiar_numero(m.group(5)),
                "tasa_licitacion":limpiar_numero(m.group(6)),
                "precio":         limpiar_numero(m.group(7)),
                "rendimiento_pct":limpiar_numero(m.group(8)),
                "tna":            limpiar_numero(m.group(9)),
                "tea":            limpiar_numero(m.group(10)),
                "tem":            limpiar_numero(m.group(11)),
                "dm":             limpiar_numero(m.group(12)),
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
        resultado.append({
            "especie":       m.group(1),
            "tipo":          "TAMAR",
            "fecha_emision": limpiar_fecha(m.group(2)),
            "fecha_pago":    limpiar_fecha(m.group(3)),
            "plazo_dias":    int(m.group(4)),
            "spread":        limpiar_numero(m.group(5)),
            "tem_tamar":     limpiar_numero(m.group(6)),
            "monto_vto":     limpiar_numero(m.group(7)),
            "precio":        limpiar_numero(m.group(8)),
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
        "updated_at":   datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
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
        # Todos juntos para búsqueda fácil
        "todos": lecaps + boncaps + cer + tamar,
    }
    
    with open("lecaps_data.json", "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    
    print(f"\n✅ lecaps_data.json generado:")
    print(f"   LECAPs:  {len(lecaps)}")
    print(f"   BONCAPs: {len(boncaps)}")
    print(f"   CER:     {len(cer)}")
    print(f"   TAMAR:   {len(tamar)}")
    print(f"   Total:   {len(lecaps)+len(boncaps)+len(cer)+len(tamar)} instrumentos")

if __name__ == "__main__":
    main()
