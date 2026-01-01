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

def get_dolares_data():
    global _DOLARES_CACHE
    now = time.time()

    if _DOLARES_CACHE["data"] and (now - _DOLARES_CACHE["ts"]) < CACHE_TTL:
        return _DOLARES_CACHE["data"]

    try:
        # 1. Traemos el precio "Minuto a Minuto"
        res_now = requests.get(URL_ACTUAL)
        current_data = res_now.json()

        # 2. Traemos todo el historial
        res_hist = requests.get(URL_HISTORICO)
        hist_data = res_hist.json()
        df_hist = pd.DataFrame(hist_data)
        df_hist['fecha'] = pd.to_datetime(df_hist['fecha']).dt.date

        # 3. Procesamos cada tipo de dólar
        results = []
        hoy = dt.date.today()

        for item in current_data:
            casa = item['casa']
            v_actual = float(item['venta'])
            
            # --- LÓGICA DE COMPARACIÓN VS AYER ---
            # Filtramos el historial para esta 'casa' y que NO sea la fecha de hoy
            hist_casa = df_hist[(df_hist['casa'] == casa) & (df_hist['fecha'] < hoy)]
            
            # Ordenamos por fecha y tomamos el último registro disponible (Ayer o el último hábil)
            hist_casa = hist_casa.sort_values(by='fecha', ascending=False)
            
            venta_pct = 0.0
            v_anterior = None

            if not hist_casa.empty:
                v_anterior = float(hist_casa.iloc[0]['venta'])
                if v_anterior > 0:
                    venta_pct = ((v_actual / v_anterior) - 1) * 100

            results.append({
                "nombre": item['nombre'],
                "casa": casa,
                "compra": item['compra'],
                "venta": v_actual,
                "fecha_actualizacion": item['fechaActualizacion'],
                "variation": {
                    "venta_pct": round(venta_pct, 2),
                    "v_anterior": v_anterior  # Para debug
                }
            })

        output = {
            "updated_at": dt.datetime.now(timezone.utc).isoformat(),
            "dolares": results
        }

        _DOLARES_CACHE["data"] = output
        _DOLARES_CACHE["ts"] = now
        return output

    except Exception as e:
        print(f"Error en dolares_processor: {e}")
        return _DOLARES_CACHE["data"] if _DOLARES_CACHE["data"] else {"error": str(e)}
    _CACHE["data"] = out
    _CACHE["ts"] = now
    return out
