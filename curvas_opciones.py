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
# HELPERS
# ============================================================

def clean_iv(iv: Any) -> Optional[float]:
    if iv is None or (isinstance(iv, float) and math.isnan(iv)):
        return None
    try:
        val = float(iv)
    except Exception:
        return None
    if val > 3:
        val = val / 100.0
    if val < 0.01 or val > 3.0:
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


def _df_to_records(df: Optional[pd.DataFrame], date_cols: Tuple[str, ...] = ("expiry",)) -> List[Dict[str, Any]]:
    if df is None or df.empty:
        return []
    out = df.copy()
    for col in date_cols:
        if col in out.columns:
            out[col] = out[col].astype(str)
    return out.to_dict(orient="records")


# ============================================================
# BTC – DERIBIT
# ============================================================

def fetch_deribit_btc() -> pd.DataFrame:
    url = f"{DERIBIT_BASE}/public/get_book_summary_by_currency"
    r = requests.get(url, params={"currency": "BTC", "kind": "option"})
    r.raise_for_status()
    data = r.json()["result"]

    rows = []
    for opt in data:
        name = opt["instrument_name"]  # BTC-29NOV24-65000-C
        parts = name.split("-")
        try:
            expiry = dt.datetime.strptime(parts[1], "%d%b%y").date()
        except Exception:
            continue

        rows.append({
            "expiry": expiry,
            "strike": float(parts[2]),
            "iv": clean_iv(opt.get("mark_iv")),
            "spot": opt.get("underlying_price"),
        })

    return pd.DataFrame(rows)


def summarize_deribit(df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame]:
    if df is None or df.empty:
        return pd.DataFrame(), pd.DataFrame()

    expiries = pick_monthly_expiries(list(df["expiry"].unique()), MESES_HORIZONTE)
    df2 = df[df["expiry"].isin(expiries)].copy()

    spot_series = df2["spot"].dropna()
    spot = float(spot_series.mean()) if not spot_series.empty else None

    rows = []
    for exp in expiries:
        sub = df2[df2["expiry"] == exp].dropna(subset=["iv"])
        if sub.empty:
            continue
        central = sub.loc[sub["iv"].idxmin()]
        rows.append({
            "expiry": exp,
            "spot": spot,
            "central_strike": float(central["strike"]),
        })

    return df2, pd.DataFrame(rows)


# ============================================================
# YFINANCE
# ============================================================

def yfin_get_raw_chains(underlying: str):
    tk = yf.Ticker(underlying)
    try:
        expiries_raw = tk.options
    except Exception:
        return None, None, [], None

    if not expiries_raw:
        return None, None, [], None

    hist = tk.history(period="1d")
    if hist.empty:
        return None, None, [], None

    spot = float(hist["Close"].iloc[0])

    expiries = []
    for e in expiries_raw:
        try:
            expiries.append(dt.datetime.strptime(e, "%Y-%m-%d").date())
        except Exception:
            continue

    expiries = pick_monthly_expiries(expiries)

    calls_rows, puts_rows = [], []

    for exp in expiries:
        exp_str = exp.strftime("%Y-%m-%d")
        try:
            chain = tk.option_chain(exp_str)
        except Exception:
            continue

        for _, r in chain.calls.iterrows():
            calls_rows.append({
                "expiry": exp,
                "strike": float(r["strike"]),
                "iv_call": clean_iv(r.get("impliedVolatility")),
                "bid_call": float(r["bid"]) if not math.isnan(r["bid"]) else None,
                "ask_call": float(r["ask"]) if not math.isnan(r["ask"]) else None,
            })

        for _, r in chain.puts.iterrows():
            puts_rows.append({
                "expiry": exp,
                "strike": float(r["strike"]),
                "iv_put": clean_iv(r.get("impliedVolatility")),
                "bid_put": float(r["bid"]) if not math.isnan(r["bid"]) else None,
                "ask_put": float(r["ask"]) if not math.isnan(r["ask"]) else None,
            })

    return pd.DataFrame(calls_rows), pd.DataFrame(puts_rows), expiries, spot


# ============================================================
# FUSIÓN CALL + PUT
# ============================================================

def fuse_calls_puts(calls_df: pd.DataFrame, puts_df: pd.DataFrame, spot: float, expiries: List[dt.date]) -> pd.DataFrame:
    merged = pd.merge(calls_df, puts_df, on=["expiry", "strike"], how="outer")

    out = []
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

            sp_c = ask_c - bid_c if (ask_c and bid_c and ask_c > bid_c) else 1
            sp_p = ask_p - bid_p if (ask_p and bid_p and ask_p > bid_p) else 1

            w_c = 1/sp_c
            w_p = 1/sp_p

            iv_f = (iv_c*w_c + iv_p*w_p) / (w_c + w_p)

        out.append({
            "expiry": exp,
            "strike": strike,
            "iv": iv_f,
            "spot": spot,
        })

    df = pd.DataFrame(out)
    return df[df["expiry"].isin(expiries)]


# ============================================================
# FORWARD TABLE
# ============================================================

def build_forward_table(df: pd.DataFrame, summary: pd.DataFrame) -> pd.DataFrame:
    out = []
    today = dt.date.today()

    for _, row in summary.iterrows():
        exp = row["expiry"]
        spot = float(row["spot"])
        central = float(row["central_strike"])

        sub = df[df["expiry"] == exp].dropna(subset=["iv"])
        if sub.empty:
            continue

        dte = (exp - today).days
        if dte <= 0:
            continue

        sub2 = sub.copy()
        sub2["dist"] = abs(sub2["strike"] - central)
        atm_slice = sub2.sort_values("dist").head(10)
        atm_iv = atm_slice["iv"].median()

        if pd.isna(atm_iv):
            em = None
        else:
            em = central * atm_iv * math.sqrt(dte/365)

        pct = (central/spot - 1)*100 if spot else None

        out.append({
            "expiry": exp,
            "spot": spot,
            "central_strike": central,
            "pct_vs_spot": pct,
            "atm_iv": float(atm_iv) if atm_iv else None,
            "days_to_expiry": dte,
            "expected_move": float(em) if em else None,
            "em_up": float(central+em) if em else None,
            "em_down": float(central-em) if em else None,
        })

    return pd.DataFrame(out).sort_values("expiry")


# ============================================================
# ANALYSIS
# ============================================================

def analyze_forward(df: pd.DataFrame):
    if df.empty or len(df) < 2:
        return "Sin datos suficientes", "NEUTRAL", 0.0, "DESCONOCIDA"

    first = df.iloc[0]
    last = df.iloc[-1]

    total_change = (last["central_strike"]/first["central_strike"] - 1)*100

    if total_change > 3:
        trend = "ALCISTA"
    elif total_change < -3:
        trend = "BAJISTA"
    else:
        trend = "NEUTRAL"

    em_rel = df.apply(
        lambda r: r["expected_move"]/r["central_strike"] if (r["expected_move"] and r["central_strike"]) else None,
        axis=1
    ).dropna()

    if em_rel.empty:
        vol_label = "DESCONOCIDA"
    else:
        avg = em_rel.mean()*100
        if avg < 2:
            vol_label = "BAJA"
        elif avg < 5:
            vol_label = "MEDIA"
        else:
            vol_label = "ALTA"

    # texto
    lines = [
        "===== ANÁLISIS AUTOMÁTICO =====",
        f"Tendencia implícita: {trend}",
        f"Cambio total centrales: {total_change:+.2f}%",
        f"Volatilidad implícita (EM): {vol_label}",
        "",
        "Detalle por vencimiento:"
    ]

    for _, r in df.iterrows():
        lines.append(
            f"{r['expiry']}: central {r['central_strike']:.2f} | Δ vs spot {r['pct_vs_spot']:+.2f}% | EM {r['expected_move']}"
        )

    return "\n".join(lines), trend, float(total_change), vol_label


# ============================================================
# MAIN FUNCTION FOR API
# ============================================================

def analyze_ticker_for_api(ticker: str) -> Dict[str, Any]:
    t = ticker.upper().strip()

    # BTC via Deribit
    if t == "BTC":
        raw = fetch_deribit_btc()
        chain, summary = summarize_deribit(raw)
        forward = build_forward_table(chain, summary)
        analysis_text, trend, change, vol = analyze_forward(forward)

        return {
            "ticker": t,
            "source": "deribit",
            "spot": float(summary["spot"].iloc[0]),
            "forward_points": _df_to_records(forward),
            "analysis": {
                "text": analysis_text,
                "trend": trend,
                "total_change_pct": change,
                "vol_label": vol,
            },
        }

    # Resto via YFinance
    calls, puts, expiries, spot = yfin_get_raw_chains(t)
    if calls is None or puts is None:
        raise ValueError(f"No se encontraron opciones para {t}")

    fused = fuse_calls_puts(calls, puts, spot, expiries)
    summary = summarize_yfin_fused(fused, expiries, spot)
    forward = build_forward_table(fused, summary)

    analysis_text, trend, change, vol = analyze_forward(forward)

    return {
        "ticker": t,
        "source": "yfinance",
        "spot": float(spot),
        "forward_points": _df_to_records(forward),
        "analysis": {
            "text": analysis_text,
            "trend": trend,
            "total_change_pct": change,
            "vol_label": vol,
        },
    }

