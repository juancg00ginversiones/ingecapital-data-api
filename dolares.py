import requests
import pandas as pd
import time
import datetime as dt
from datetime import timezone
import threading

# ============================================================
# CONFIGURACIÓN Y CACHÉ
# ============================================================
URL_ACTUAL = "https://dolarapi.com/v1/dolares"
URL_HISTORICO = "https://api.argentinadatos.com/v1/cotizaciones/dolares"
CACHE_TTL = 60 * 15  # 15 minutos

_DOLARES_CACHE = {"ts": 0.0, "data": None}

# Infra concurrencia
_CACHE_LOCK = threading.Lock()
_INFLIGHT = False
_INFLIGHT_EVENT = threading.Event()

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


# ============================================================
# API
# ============================================================
def get_dolares_for_api(history_days: int = 365):
    global _INFLIGHT

    now = time.time()

    # ---------- 1) Cache fresh ----------
    with _CACHE_LOCK:
        if _DOLARES_CACHE["data"] is not None and (now - _DOLARES_CACHE["ts"]) < CACHE_TTL:
            return _DOLARES_CACHE["data"]

        if _INFLIGHT:
            event = _INFLIGHT_EVENT
        else:
            _INFLIGHT = True
            _INFLIGHT_EVENT.clear()
            event = None

    # ---------- 2) Follower ----------
    if event is not None:
        event.wait(timeout=30)
        with _CACHE_LOCK:
            if _DOLARES_CACHE["data"] is not None:
                return _DOLARES_CACHE["data"]
            return {"error": "Datos no disponibles"}

    # ---------- 3) Líder (lógica ORIGINAL intacta) ----------
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

            hist_casa = df_hist[(df_hist['casa'] == casa) & (df_hist['fecha'] < hoy)]
            hist_casa = hist_casa.sort_values(by='fecha', ascending=False)

            venta_pct = 0.0
            if not hist_casa.empty:
                v_anterior = float(hist_casa.iloc[0]['venta'] or hist_casa.iloc[0]['compra'] or 0)
                if v_anterior > 0:
                    venta_pct = ((v_actual / v_anterior) - 1) * 100

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

        # Guardar cache SOLO si es válido
        with _CACHE_LOCK:
            _DOLARES_CACHE["data"] = output
            _DOLARES_CACHE["ts"] = time.time()

        return output

    except Exception as e:
        print(f"Error en dolares.py: {e}")
        with _CACHE_LOCK:
            return _DOLARES_CACHE["data"] if _DOLARES_CACHE["data"] else {"error": str(e)}

    finally:
        with _CACHE_LOCK:
            _INFLIGHT = False
            _INFLIGHT_EVENT.set()
