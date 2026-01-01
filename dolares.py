import requests
import pandas as pd
import time
import datetime as dt
from datetime import timezone

# ============================================================
# CONFIGURACIÓN Y CACHÉ
# ============================================================
URL_ACTUAL = "https://dolarapi.com/v1/dolares"
URL_HISTORICO = "https://api.argentinadatos.com/v1/cotizaciones/dolares"
CACHE_TTL = 60 * 15  # 15 minutos

_DOLARES_CACHE = {"ts": 0, "data": None}

CASA_LABEL = {
    "oficial": "Dólar Oficial",
    "blue": "Dólar Blue",
    "tarjeta": "Dólar Tarjeta",
    "contadoconliqui": "Dólar CCL",
    "bolsa": "Dólar MEP",
    "mayorista": "Dólar Mayorista",
    "cripto": "Dólar Cripto",
}

CASAS_ORDER = ["oficial", "blue", "tarjeta", "contadoconliqui", "bolsa", "mayorista", "cripto"]

# Cambiamos el nombre a get_dolares_for_api para que main.py no de error
def get_dolares_for_api(history_days: int = 365):
    global _DOLARES_CACHE
    now = time.time()

    if _DOLARES_CACHE["data"] and (now - _DOLARES_CACHE["ts"]) < CACHE_TTL:
        return _DOLARES_CACHE["data"]

    try:
        # 1. Precio Actual
        res_now = requests.get(URL_ACTUAL, timeout=15)
        current_raw = res_now.json()
        current_dict = {str(item['casa']).lower(): item for item in current_raw}

        # 2. Historial
        res_hist = requests.get(URL_HISTORICO, timeout=25)
        hist_data = res_hist.json()
        df_hist = pd.DataFrame(hist_data)
        df_hist['fecha'] = pd.to_datetime(df_hist['fecha']).dt.date
        
        cutoff = dt.date.today() - dt.timedelta(days=history_days)
        hoy = dt.date.today()

        final_current = []
        final_history = {}

        # 3. Procesar por Casa (Ordenado)
        for casa in CASAS_ORDER:
            if casa not in current_dict:
                continue
            
            item = current_dict[casa]
            v_actual = float(item.get('venta') or 0)
            
            # Comparación vs Ayer
            hist_casa = df_hist[(df_hist['casa'] == casa) & (df_hist['fecha'] < hoy)]
            hist_casa = hist_casa.sort_values(by='fecha', ascending=False)
            
            venta_pct = 0.0
            if not hist_casa.empty:
                v_anterior = float(hist_casa.iloc[0]['venta'] or hist_casa.iloc[0]['compra'] or 0)
                if v_anterior > 0:
                    venta_pct = ((v_actual / v_anterior) - 1) * 100

            # Estructura para la lista "current" de Horizons
            final_current.append({
                "casa": casa,
                "label": CASA_LABEL.get(casa, item.get('nombre', casa)),
                "compra": item.get('compra'),
                "venta": v_actual,
                "fechaActualizacion": item.get('fechaActualizacion'),
                "variation": {
                    "venta_pct": round(venta_pct, 2)
                }
            })

            # Estructura para el objeto "history" de Horizons (Gráficos)
            serie_casa = df_hist[df_hist['casa'] == casa]
            serie_casa = serie_casa[serie_casa['fecha'] >= cutoff].sort_values('fecha')
            
            final_history[casa] = [
                {"date": p['fecha'].isoformat(), "compra": p['compra'], "venta": p['venta']}
                for _, p in serie_casa.iterrows()
            ]

        output = {
            "updated_at": dt.datetime.now(timezone.utc).isoformat() + "Z",
            "current": final_current,
            "history": final_history
        }

        _DOLARES_CACHE["data"] = output
        _DOLARES_CACHE["ts"] = now
        return output

    except Exception as e:
        print(f"Error en dolares.py: {e}")
        return _DOLARES_CACHE["data"] if _DOLARES_CACHE["data"] else {"error": str(e)}
