import warnings
warnings.filterwarnings("ignore")

import math
import datetime as dt
from typing import List, Dict, Any, Tuple, Optional

import requests
import pandas as pd
import yfinance as yf

MESES_HORIZONTE = 6

# =============================================
# Helpers
# =============================================
def clean_iv(iv: Any) -> Optional[float]:
    if iv is None:
        return None
    try:
        val = float(iv)
    except:
        return None
    if val > 3:  # si viene en %
        val = val / 100
    if val < 0.01 or val > 3:
        return None
    return val

def pick_monthly_expiries(expiries: List[dt.date], n: int = MESES_HORIZONTE) -> List[dt.date]:
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

def _df_to_records(df: Optional[pd.DataFrame], date_cols=("expiry",)) -> List[dict]:
    if df is None or df.empty:
        return []
    df2 = df.copy()
    for col in date_cols:
        if col in df2.columns:
            df2[col] = df2[col].astype(str)
    return df2.to_dict(orient="records")

# =============================================
# Obtener opciones de YFinance
# =============================================
def yfin_get_raw_chains(ticker: str):
    t = yf.Ticker(ticker)

    try:
        expiries_raw = t.options
    except Exception:
        return None, None, [], None

    if not expiries_raw:
        return None, None, [], None

    hist = t.history(period="1d")
    if hist.empty:
        return None, None, [], None

    spot = float(hist["Close"].iloc[0])

    expiries = []
    for e in expiries_raw:
        try:
            expiries.append(dt.datetime.strptime(e, "%Y-%m-%d").date())
        except:
            continue

    expiries = pick_monthly_expiries(expiries, MESES_HORIZONTE)

    calls_rows, puts_rows = [], []

    for exp in expiries:
        exp_str = exp.strftime("%Y-%m-%d")
        try:
            chain = t.option_chain(exp_str)
        except:
            continue

        for _, row in chain.calls.iterrows():
            calls_rows.append({
                "expiry": exp,
                "strike": float(row["strike"]),
                "iv_call": clean_iv(row.get("impliedVolatility")),
                "bid_call": float(row["bid"]) if row["bid"] == row["bid"] else None,
                "ask_call": float(row["ask"]) if row["ask"] == row["ask"] else None,
            })

        for _, row in chain.puts.iterrows():
            puts_rows.append({
                "expiry": exp,
                "strike": float(row["strike"]),
                "iv_put": clean_iv(row.get("impliedVolatility")),
                "bid_put": float(row["bid"]) if row["bid"] == row["bid"] else None,
                "ask_put": float(row["ask"]) if row["ask"] == row["ask"] else None,
            })

    return (
        pd.DataFrame(calls_rows),
        pd.DataFrame(puts_rows),
        expiries,
        spot
    )

# =============================================
# Fusionar calls + puts
# =============================================
def fuse_calls_puts(calls_df, puts_df, spot, expiries):
    merged = pd.merge(calls_df, puts_df, on=["expiry", "strike"], how="outer")
    rows = []

    for _, row in merged.iterrows():
        iv_c = clean_iv(row.get("iv_call"))
        iv_p = clean_iv(row.get("iv_put"))

        if iv_c is None and iv_p is None:
            iv_f = None
        elif iv_c is None:
            iv_f = iv_p
        elif iv_p is None:
            iv_f = iv_c
        else:
            bc, ac = row.get("bid_call"), row.get("ask_call")
            bp, ap = row.get("bid_put"), row.get("ask_put")

            sc = ac - bc if (ac and bc and ac > bc) else 1
            sp = ap - bp if (ap and bp and ap > bp) else 1

            wc, wp = 1 / sc, 1 / sp
            iv_f = (iv_c * wc + iv_p * wp) / (wc + wp)

        rows.append({
            "expiry": row["expiry"],
            "strike": row["strike"],
            "iv": iv_f,
            "spot": spot
        })

    df = pd.DataFrame(rows)
    return df[df["expiry"].isin(expiries)]

# =============================================
# Encontrar Central por vencimiento
# =============================================
def summarize_yfin_fused(df, expiries, spot):
    rows = []
    for exp in expiries:
        sub = df[df["expiry"] == exp].dropna(subset=["iv"])
        if sub.empty: continue
        central_row = sub.loc[sub["iv"].idxmin()]
        rows.append({
            "expiry": exp,
            "spot": spot,
            "central_strike": float(central_row["strike"]),
        })
    return pd.DataFrame(rows)

# =============================================
# Construir forward curve
# =============================================
def build_forward_table(df, summary):
    rows = []
    today = dt.date.today()
    for _, row in summary.iterrows():
        exp = row["expiry"]
        spot = row["spot"]
        central = row["central_strike"]

        sub = df[df["expiry"] == exp].dropna(subset=["iv"])
        if sub.empty: continue

        dte = (exp - today).days
        if dte <= 0: continue

        sub["dist"] = (sub["strike"] - central).abs()
        atm_slice = sub.sort_values("dist").head(10)
        atm_iv = atm_slice["iv"].median()

        if atm_iv is None:
            em = None
        else:
            em = central * atm_iv * math.sqrt(dte / 365)

        rows.append({
            "expiry": exp,
            "central": central,
            "spot": spot,
            "dte": dte,
            "atm_iv": atm_iv,
            "expected_move": em,
            "em_up": None if em is None else central + em,
            "em_down": None if em is None else central - em,
            "pct_vs_spot": (central / spot - 1) * 100
        })

    return pd.DataFrame(rows)

# =============================================
# Tendencia + volatilidad resumen
# =============================================
def analyze_forward(forward_df):
    if forward_df.empty or len(forward_df) < 2:
        return {"tendencia": "NEUTRAL", "volatilidad": "DESCONOCIDA"}

    first = forward_df.iloc[0]["central"]
    last = forward_df.iloc[-1]["central"]
    total_change = (last / first - 1) * 100

    if total_change > 3:
        tendencia = "ALCISTA"
    elif total_change < -3:
        tendencia = "BAJISTA"
    else:
        tendencia = "NEUTRAL"

    em_rel = (forward_df["expected_move"] / forward_df["central"]).dropna()
    if em_rel.empty:
        vola = "DESCONOCIDA"
    else:
        avg = em_rel.mean() * 100
        if avg < 2: vola = "BAJA"
        elif avg < 5: vola = "MEDIA"
        else: vola = "ALTA"

    return {
        "tendencia": tendencia,
        "volatilidad": vola,
        "cambio_pct": total_change
    }

# =============================================
# FUNCIÓN PRINCIPAL PARA LA API
# =============================================
def analyze_ticker_for_api(ticker: str):
    calls, puts, expiries, spot = yfin_get_raw_chains(ticker)
    if calls is None:
        return {"error": f"No se pudo obtener opciones para {ticker}"}

    fused = fuse_calls_puts(calls, puts, spot, expiries)
    summary = summarize_yfin_fused(fused, expiries, spot)
    forward = build_forward_table(fused, summary)
    analysis = analyze_forward(forward)

    return {
        "ticker": ticker,
        "spot": spot,
        "forward_curve": _df_to_records(forward),
        "resumen": analysis,
    }

