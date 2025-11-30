import warnings
warnings.filterwarnings("ignore")

import math
import datetime as dt
from typing import List, Dict, Any, Tuple, Optional

import requests
import pandas as pd
import yfinance as yf


# ============================================================
# CONFIG
# ============================================================
MESES_HORIZONTE = 6
DERIBIT_BASE = "https://www.deribit.com/api/v2"

LISTA_TICKERS = [
    "SPY", "QQQ", "IWM", "DIA",
    "AAPL", "MSFT", "GOOGL", "AMZN", "META", "NVDA", "TSLA",
    "TLT", "IEF",
    "BTC", "ETH"
]


# ============================================================
# HELPERS
# ============================================================
def clean_iv(iv):
    if iv is None:
        return None
    try:
        v = float(iv)
    except:
        return None

    if v > 3:
        v /= 100.0
    if v < 0.01 or v > 3:
        return None
    return v


def pick_monthly_expiries(expiries, n=MESES_HORIZONTE):
    expiries = sorted(set(expiries))
    today = dt.date.today()
    monthly = {}

    for e in expiries:
        if e <= today:
            continue
        key = e.strftime("%Y-%m")
        if key not in monthly:
            monthly[key] = e
        if len(monthly) >= n:
            break

    return list(monthly.values())


# ============================================================
# DERIBIT (BTC)
# ============================================================
def fetch_deribit_btc():
    url = f"{DERIBIT_BASE}/public/get_book_summary_by_currency"
    r = requests.get(url, params={"currency": "BTC", "kind": "option"})
    r.raise_for_status()
    data = r.json()["result"]

    rows = []
    for opt in data:
        name = opt["instrument_name"]  # BTC-29NOV24-65000-C
        parts = name.split("-")
        expiry = dt.datetime.strptime(parts[1], "%d%b%y").date()
        strike = float(parts[2])
        iv = clean_iv(opt.get("mark_iv"))
        spot = opt.get("underlying_price")

        rows.append({
            "expiry": expiry,
            "strike": strike,
            "iv": iv,
            "spot": spot
        })

    return pd.DataFrame(rows)


def summarize_deribit(df):
    expiries = pick_monthly_expiries(df["expiry"].unique())
    df2 = df[df["expiry"].isin(expiries)]

    spot = df2["spot"].dropna().mean()

    rows = []
    for e in expiries:
        subset = df2[df2["expiry"] == e].dropna(subset=["iv"])
        if subset.empty:
            continue
        cs = subset.loc[subset["iv"].idxmin()]["strike"]
        rows.append({
            "expiry": e,
            "spot": spot,
            "central_strike": cs
        })

    return df2, pd.DataFrame(rows)


# ============================================================
# YFINANCE OPTIONS
# ============================================================
def yfin_get_raw_chains(ticker):
    tk = yf.Ticker(ticker)

    try:
        y_expiries = tk.options
    except:
        return None, None, [], None

    hist = tk.history(period="1d")
    if hist.empty:
        return None, None, [], None

    spot = float(hist["Close"].iloc[0])

    expiries = []
    for e in y_expiries:
        try:
            expiries.append(dt.datetime.strptime(e, "%Y-%m-%d").date())
        except:
            pass

    expiries = pick_monthly_expiries(expiries)

    call_rows = []
    put_rows = []

    for exp in expiries:
        try:
            chain = tk.option_chain(exp.strftime("%Y-%m-%d"))
        except:
            continue

        for _, row in chain.calls.iterrows():
            call_rows.append({
                "expiry": exp,
                "strike": row["strike"],
                "iv_call": clean_iv(row["impliedVolatility"]),
                "bid_call": row["bid"],
                "ask_call": row["ask"]
            })

        for _, row in chain.puts.iterrows():
            put_rows.append({
                "expiry": exp,
                "strike": row["strike"],
                "iv_put": clean_iv(row["impliedVolatility"]),
                "bid_put": row["bid"],
                "ask_put": row["ask"]
            })

    return pd.DataFrame(call_rows), pd.DataFrame(put_rows), expiries, spot


# ============================================================
# FUSIÓN CALL + PUT
# ============================================================
def fuse_calls_puts(calls, puts, spot, expiries):
    merged = pd.merge(calls, puts, on=["expiry", "strike"], how="outer")

    rows = []
    for _, row in merged.iterrows():
        iv_c = clean_iv(row.get("iv_call"))
        iv_p = clean_iv(row.get("iv_put"))

        if iv_c is None and iv_p is None:
            iv = None
        elif iv_c is None:
            iv = iv_p
        elif iv_p is None:
            iv = iv_c
        else:
            # ponderación por spread
            bc, ac = row.get("bid_call"), row.get("ask_call")
            bp, ap = row.get("bid_put"), row.get("ask_put")

            spread_c = ac - bc if ac and bc and ac > bc else 1
            spread_p = ap - bp if ap and bp and ap > bp else 1

            w_c = 1 / spread_c
            w_p = 1 / spread_p

            iv = (iv_c * w_c + iv_p * w_p) / (w_c + w_p)

        rows.append({
            "expiry": row["expiry"],
            "strike": row["strike"],
            "iv": iv,
            "spot": spot
        })

    df = pd.DataFrame(rows)
    return df[df["expiry"].isin(expiries)]


# ============================================================
# SUMMARY YFINANCE
# ============================================================
def summarize_yfin(df, expiries, spot):
    rows = []
    for e in expiries:
        sub = df[df["expiry"] == e].dropna(subset=["iv"])
        if sub.empty:
            continue
        cs = sub.loc[sub["iv"].idxmin()]["strike"]
        rows.append({
            "expiry": e,
            "spot": spot,
            "central_strike": cs
        })

    return pd.DataFrame(rows)


# ============================================================
# FORWARD CURVE
# ============================================================
def build_forward_table(df, summary):
    rows = []
    today = dt.date.today()

    for _, r in summary.iterrows():
        exp = r["expiry"]
        central = float(r["central_strike"])
        spot = float(r["spot"])

        sub = df[df["expiry"] == exp].dropna(subset=["iv"])
        if sub.empty:
            continue

        dte = (exp - today).days
        if dte <= 0:
            continue

        sub2 = sub.copy()
        sub2["dist"] = (sub2["strike"] - central).abs()
        atm_iv = sub2.sort_values("dist").head(10)["iv"].median()

        if pd.isna(atm_iv):
            em = None
        else:
            em = central * atm_iv * math.sqrt(dte / 365)

        rows.append({
            "expiry": exp.strftime("%Y-%m-%d"),
            "central": central,
            "em_up": None if em is None else central + em,
            "em_down": None if em is None else central - em,
            "expected_move": em,
            "pct_vs_spot": (central / spot - 1) * 100
        })

    return pd.DataFrame(rows)


# ============================================================
# ANALYSIS
# ============================================================
def analyze_forward(df):
    if df.empty or len(df) < 2:
        return "NEUTRAL", 0.0, "DESCONOCIDA"

    first = df.iloc[0]
    last = df.iloc[-1]

    total_change = (last["central"] / first["central"] - 1) * 100

    if total_change > 3:
        trend = "ALCISTA"
    elif total_change < -3:
        trend = "BAJISTA"
    else:
        trend = "NEUTRAL"

    try:
        em_rel = (df["expected_move"] / df["central"]).fillna(0)
        avg = em_rel.mean() * 100

        if avg < 1:
            vol = "BAJA"
        elif avg < 5:
            vol = "MEDIA"
        else:
            vol = "ALTA"
    except:
        vol = "DESCONOCIDA"

    return trend, total_change, vol


# ============================================================
# API MAIN
# ============================================================
def analyze_ticker_for_api(ticker: str):
    ticker = ticker.upper()

    if ticker == "BTC":
        raw = fetch_deribit_btc()
        chain, summary = summarize_deribit(raw)
    else:
        calls, puts, expiries, spot = yfin_get_raw_chains(ticker)
        if calls is None:
            raise ValueError("Ticker sin datos")
        chain = fuse_calls_puts(calls, puts, spot, expiries)
        summary = summarize_yfin(chain, expiries, spot)

    forward = build_forward_table(chain, summary)
    trend, total_change, vol = analyze_forward(forward)

    return {
        "ticker": ticker,
        "spot": float(chain["spot"].dropna().iloc[0]),
        "forward_curve": forward.to_dict(orient="records"),
        "analysis": {
            "trend": trend,
            "total_change_pct": total_change,
            "volatility": vol
        }
    }
