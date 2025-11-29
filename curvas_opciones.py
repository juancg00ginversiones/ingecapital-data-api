import warnings
warnings.filterwarnings("ignore")

import math
import datetime as dt
from typing import List, Dict, Any, Tuple, Optional

import requests
import pandas as pd
import yfinance as yf

# ============================================================
# CONFIGURACIÓN
# ============================================================

DERIBIT_BASE = "https://www.deribit.com/api/v2"
MESES_HORIZONTE = 6   # meses hacia adelante a analizar

# Lista oficial de tickers permitidos para Horizons
LISTA_TICKERS: List[str] = [
    # Índices
    "SPY", "QQQ", "IWM", "DIA",
    # Volatilidad
    "VIX", "VXN",
    # Magnificent 7
    "AAPL", "MSFT", "GOOGL", "AMZN", "META", "NVDA", "TSLA",
    # Crypto
    "BTC", "ETH",
    # Bonos / tasas
    "TLT", "IEF",
]


# ============================================================
# HELPERS GENERALES
# ============================================================

def clean_iv(iv: Any) -> Optional[float]:
    """
    Normaliza IV y filtra valores absurdos.
    - Si viene >3, se asume que está en % (ej: 50 -> 0.50)
    - Filtra valores muy bajos o muy altos (ruido).
    """
    if iv is None or (isinstance(iv, float) and math.isnan(iv)):
        return None

    try:
        val = float(iv)
    except (TypeError, ValueError):
        return None

    if val > 3.0:
        val = val / 100.0

    if val < 0.01 or val > 3.0:
        return None

    return val


def pick_monthly_expiries(expiries: List[dt.date], n: int = MESES_HORIZONTE) -> List[dt.date]:
    """
    Elige hasta 'n' vencimientos, máximo uno por mes hacia adelante.
    """
    expiries = sorted(set(expiries))
    today = dt.date.today()
    monthly = {}

    for exp in expiries:
        if exp <= today:
            continue
        key = exp.strftime("%Y-%m")
        if key not in monthly:
            monthly[key] = exp
        if len(monthly) >= n:
            break

    return list(monthly.values())


def _df_to_records(df: Optional[pd.DataFrame], date_cols: Tuple[str, ...] = ("expiry",)) -> List[Dict[str, Any]]:
    """
    Convierte un DataFrame en lista de dicts serializable a JSON.
    Convierte columnas de fechas a strings ISO (YYYY-MM-DD).
    """
    if df is None or df.empty:
        return []

    out = df.copy()
    for col in date_cols:
        if col in out.columns:
            out[col] = out[col].astype(str)

    return out.to_dict(orient="records")


# ============================================================
# DERIBIT (BTC)
# ============================================================

def fetch_deribit_btc() -> pd.DataFrame:
    """
    Obtiene opciones BTC de Deribit (toda la cadena).
    """
    url = f"{DERIBIT_BASE}/public/get_book_summary_by_currency"
    r = requests.get(url, params={"currency": "BTC", "kind": "option"})
    r.raise_for_status()
    data = r.json()["result"]

    rows = []
    for opt in data:
        name = opt["instrument_name"]           # BTC-29NOV24-65000-C
        parts = name.split("-")
        # Formato: DDMMMYY, ej: 29NOV24
        try:
            expiry = dt.datetime.strptime(parts[1], "%d%b%y").date()
        except Exception:
            continue

        strike = float(parts[2])
        iv = clean_iv(opt.get("mark_iv"))
        spot = opt.get("underlying_price")

        rows.append({
            "expiry": expiry,
            "strike": strike,
            "iv": iv,
            "spot": spot,
        })

    return pd.DataFrame(rows)


def summarize_deribit(df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Filtra a 1 vencimiento por mes y calcula el strike "central"
    (mínima IV) por vencimiento.
    Devuelve:
      - df_filtrado (solo expiries elegidos)
      - df_summary (una fila por expiry, con spot y central_strike)
    """
    if df is None or df.empty:
        return pd.DataFrame(), pd.DataFrame()

    expiries_unique = [e for e in df["expiry"].unique()]
    expiries = pick_monthly_expiries(expiries_unique, MESES_HORIZONTE)

    df2 = df[df["expiry"].isin(expiries)].copy()

    spot_series = df2["spot"].dropna()
    if spot_series.empty:
        spot = None
    else:
        spot = float(spot_series.mean())

    rows = []
    for exp in expiries:
        sub = df2[df2["expiry"] == exp].dropna(subset=["iv"])
        if sub.empty:
            continue

        central_row = sub.loc[sub["iv"].idxmin()]
        rows.append({
            "expiry": exp,
            "spot": spot,
            "central_strike": float(central_row["strike"]),
        })

    return df2, pd.DataFrame(rows)


# ============================================================
# YFINANCE (CALLS + PUTS)
# ============================================================

def yfin_get_raw_chains(underlying: str) -> Tuple[Optional[pd.DataFrame], Optional[pd.DataFrame], List[dt.date], Optional[float]]:
    """
    Obtiene cadenas de opciones de YFinance (calls y puts) para un ticker.
    Devuelve:
      - DataFrame de calls
      - DataFrame de puts
      - lista de expiries considerados
      - spot
    """
    ticker = yf.Ticker(underlying)

    try:
        y_expiries = ticker.options
    except Exception:
        return None, None, [], None

    if not y_expiries:
        return None, None, [], None

    hist = ticker.history(period="1d")
    if hist.empty:
        return None, None, [], None

    spot = float(hist["Close"].iloc[0])

    all_expiries = []
    for e in y_expiries:
        try:
            d = dt.datetime.strptime(e, "%Y-%m-%d").date()
            all_expiries.append(d)
        except Exception:
            continue

    expiries = pick_monthly_expiries(all_expiries, MESES_HORIZONTE)

    calls_rows = []
    puts_rows = []

    for exp in expiries:
        exp_str = exp.strftime("%Y-%m-%d")
        try:
            chain = ticker.option_chain(exp_str)
        except Exception:
            continue

        # Calls
        for _, row in chain.calls.iterrows():
            calls_rows.append({
                "expiry": exp,
                "strike": float(row["strike"]),
                "iv_call": clean_iv(row.get("impliedVolatility")),
                "bid_call": float(row["bid"]) if not math.isnan(row["bid"]) else None,
                "ask_call": float(row["ask"]) if not math.isnan(row["ask"]) else None,
            })

        # Puts
        for _, row in chain.puts.iterrows():
            puts_rows.append({
                "expiry": exp,
                "strike": float(row["strike"]),
                "iv_put": clean_iv(row.get("impliedVolatility")),
                "bid_put": float(row["bid"]) if not math.isnan(row["bid"]) else None,
                "ask_put": float(row["ask"]) if not math.isnan(row["ask"]) else None,
            })

    calls_df = pd.DataFrame(calls_rows)
    puts_df = pd.DataFrame(puts_rows)

    return calls_df, puts_df, expiries, spot


# ============================================================
# FUSIÓN CALL + PUT
# ============================================================

def fuse_calls_puts(calls_df: pd.DataFrame, puts_df: pd.DataFrame, spot: float, expiries: List[dt.date]) -> pd.DataFrame:
    """
    Combina calls y puts en una única IV "fusionada" por strike/expiry.
    """
    merged = pd.merge(calls_df, puts_df, on=["expiry", "strike"], how="outer")

    rows = []
    for _, row in merged.iterrows():
        exp = row["expiry"]
        strike = float(row["strike"])

        iv_c = clean_iv(row.get("iv_call"))
        iv_p = clean_iv(row.get("iv_put"))

        if iv_c is None and iv_p is None:
            iv_f = None
        elif iv_c is None:
            iv_f = iv_p
        elif iv_p is None:
            iv_f = iv_c
        else:
            bid_c, ask_c = row.get("bid_call"), row.get("ask_call")
            bid_p, ask_p = row.get("bid_put"), row.get("ask_put")

            spread_c = ask_c - bid_c if (ask_c is not None and bid_c is not None and ask_c > bid_c) else 1.0
            spread_p = ask_p - bid_p if (ask_p is not None and bid_p is not None and ask_p > bid_p) else 1.0

            w_c = 1.0 / spread_c
            w_p = 1.0 / spread_p

            iv_f = (iv_c * w_c + iv_p * w_p) / (w_c + w_p)

        rows.append({
            "expiry": exp,
            "strike": strike,
            "iv": iv_f,
            "spot": spot,
        })

    df_fused = pd.DataFrame(rows)
    return df_fused[df_fused["expiry"].isin(expiries)]


def summarize_yfin_fused(df: pd.DataFrame, expiries: List[dt.date], spot: float) -> pd.DataFrame:
    """
    A partir del df fusionado, calcula un strike "central" por vencimiento
    (el de menor IV).
    """
    rows = []
    for exp in expiries:
        sub = df[df["expiry"] == exp].dropna(subset=["iv"])
        if sub.empty:
            continue

        central_row = sub.loc[sub["iv"].idxmin()]
        rows.append({
            "expiry": exp,
            "spot": float(spot),
            "central_strike": float(central_row["strike"]),
        })

    return pd.DataFrame(rows)


# ============================================================
# FORWARD CURVE (CENTRAL + EXPECTED MOVE)
# ============================================================

def build_forward_table(df: pd.DataFrame, summary: pd.DataFrame) -> pd.DataFrame:
    """
    A partir de:
      - df: cadena (expiry, strike, iv, spot)
      - summary: central_strike por expiry
    construye la tabla forward con:
      - spot
      - central_strike
      - % vs spot
      - IV ATM
      - expected move
      - bandas superior/inferior
    """
