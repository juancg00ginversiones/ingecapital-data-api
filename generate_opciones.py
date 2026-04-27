# ============================================================
# GENERATE OPCIONES — GitHub Actions
# Guarda opciones_data.json en el repo
# ============================================================
import pandas as pd
import yfinance as yf
import datetime as dt
import numpy as np
import json
import warnings
warnings.filterwarnings('ignore')
from scipy.stats import norm

CONTRACT_MULT = 100
RISK_FREE     = 0.04
STRIKE_RANGE  = 0.12

UNIVERSE = [
    {"symbol": "SPY",  "nombre": "S&P 500",      "color": "#4f8ef7"},
    {"symbol": "QQQ",  "nombre": "Nasdaq 100",    "color": "#00ff88"},
    {"symbol": "IWM",  "nombre": "Russell 2000",  "color": "#ffab00"},
    {"symbol": "IBIT", "nombre": "Bitcoin ETF",   "color": "#f7931a"},
]

def bs_gamma(S, K, T, r, sigma):
    if T <= 0 or sigma <= 0: return 0.0
    try:
        d1 = (np.log(S/K) + (r + 0.5*sigma**2)*T) / (sigma*np.sqrt(T))
        return norm.pdf(d1) / (S * sigma * np.sqrt(T))
    except: return 0.0

def bs_delta(S, K, T, r, sigma, opt='call'):
    if T <= 0 or sigma <= 0: return 0.0
    try:
        d1 = (np.log(S/K) + (r + 0.5*sigma**2)*T) / (sigma*np.sqrt(T))
        return norm.cdf(d1) if opt == 'call' else norm.cdf(d1) - 1
    except: return 0.0

def days_to_expiry(expiry_str):
    exp   = dt.datetime.strptime(expiry_str, "%Y-%m-%d")
    delta = (exp - dt.datetime.now()).days
    return max(delta, 1) / 365.0

def get_monthly_expiry(options_list):
    for opt in options_list:
        d = dt.datetime.strptime(opt, "%Y-%m-%d")
        if d.weekday() == 4 and 15 <= d.day <= 21:
            return opt
    return options_list[min(2, len(options_list)-1)]

def get_options_data(ticker_obj, expiry, spot):
    chain = ticker_obj.option_chain(expiry)
    T     = days_to_expiry(expiry)
    calls = chain.calls[['strike','openInterest','impliedVolatility','volume']].copy()
    puts  = chain.puts [['strike','openInterest','impliedVolatility','volume']].copy()
    calls.columns = ['strike','oi_call','iv_call','vol_call']
    puts.columns  = ['strike','oi_put', 'iv_put', 'vol_put']
    df = pd.merge(calls, puts, on='strike', how='outer').fillna(0).sort_values('strike').reset_index(drop=True)
    rows = []
    for _, row in df.iterrows():
        K    = row['strike']
        iv_c = max(row['iv_call'], 0.05)
        iv_p = max(row['iv_put'],  0.05)
        rows.append({
            'gamma_call': bs_gamma(spot, K, T, RISK_FREE, iv_c),
            'gamma_put':  bs_gamma(spot, K, T, RISK_FREE, iv_p),
            'delta_call': bs_delta(spot, K, T, RISK_FREE, iv_c, 'call'),
            'delta_put':  bs_delta(spot, K, T, RISK_FREE, iv_p, 'put'),
        })
    greeks = pd.DataFrame(rows)
    df = pd.concat([df, greeks], axis=1)
    df['gex_call'] =  df['oi_call'] * df['gamma_call'] * spot * CONTRACT_MULT
    df['gex_put']  = -df['oi_put']  * df['gamma_put']  * spot * CONTRACT_MULT
    df['gex_net']  =  df['gex_call'] + df['gex_put']
    return df

def find_levels(df, spot):
    above = df[df['strike'] > spot]
    below = df[df['strike'] < spot]
    call_wall = above.loc[above['oi_call'].idxmax(),'strike'] if not above.empty else df.loc[df['oi_call'].idxmax(),'strike']
    put_wall  = below.loc[below['oi_put'].idxmax(), 'strike'] if not below.empty else df.loc[df['oi_put'].idxmax(), 'strike']
    ds      = df.sort_values('strike')
    cum_gex = ds['gex_net'].cumsum()
    gamma_flip = None
    for i in range(len(cum_gex)-1):
        if cum_gex.iloc[i] * cum_gex.iloc[i+1] < 0:
            s1, s2 = ds['strike'].iloc[i], ds['strike'].iloc[i+1]
            g1, g2 = cum_gex.iloc[i], cum_gex.iloc[i+1]
            gamma_flip = s1 + (s2-s1)*(-g1)/(g2-g1)
            break
    if gamma_flip is None:
        gamma_flip = float(ds.loc[ds['gex_net'].abs().idxmin(),'strike'])
    strikes    = df['strike'].values
    total_loss = [
        (df['oi_call']*np.maximum(S-df['strike'],0)*CONTRACT_MULT +
         df['oi_put'] *np.maximum(df['strike']-S,0)*CONTRACT_MULT).sum()
        for S in strikes
    ]
    max_pain = float(strikes[np.argmin(total_loss)])
    return float(call_wall), float(put_wall), float(gamma_flip), float(max_pain)

def procesar_ticker(cfg):
    symbol = cfg["symbol"]
    print(f"  → {symbol}...")
    try:
        tk   = yf.Ticker(symbol)
        hist = tk.history(period="2d")
        if hist.empty: return None
        spot = float(hist["Close"].iloc[-1])
        all_exp = tk.options
        if not all_exp: return None
        near    = all_exp[0]
        monthly = get_monthly_expiry(all_exp)
        resultado = {
            "symbol":   symbol,
            "nombre":   cfg["nombre"],
            "color":    cfg["color"],
            "spot":     round(spot, 2),
            "expiries": {}
        }
        for label, exp in [("Corto Plazo", near), ("OPEX Mensual", monthly)]:
            if exp in resultado["expiries"]: continue
            df = get_options_data(tk, exp, spot)
            mask = (df['strike'] > spot*(1-STRIKE_RANGE)) & (df['strike'] < spot*(1+STRIKE_RANGE))
            df_f = df[mask].copy()
            if df_f.empty: continue
            cw, pw, gf, mp = find_levels(df_f, spot)
            dte = int(days_to_expiry(exp)*365)
            resultado["expiries"][label] = {
                "expiry":     exp,
                "dte":        dte,
                "call_wall":  round(cw, 1),
                "put_wall":   round(pw, 1),
                "gamma_flip": round(gf, 1),
                "max_pain":   round(mp, 1),
                "regime":     "POSITIVO" if spot > gf else "NEGATIVO",
                "total_gex":  round(df_f['gex_net'].sum()/1e9, 3),
                "strikes":    df_f['strike'].tolist(),
                "oi_calls":   (df_f['oi_call']/1000).round(2).tolist(),
                "oi_puts":    (df_f['oi_put']/1000).round(2).tolist(),
                "gex_net":    (df_f['gex_net']/1e6).round(3).tolist(),
            }
        return resultado
    except Exception as e:
        print(f"    ⚠ {symbol}: {e}")
        return None

def main():
    print("\n📡 Generando opciones_data.json...")
    output = {
        "updated_at": dt.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "universe":   [],
        "data":       {}
    }
    for cfg in UNIVERSE:
        res = procesar_ticker(cfg)
        if res:
            output["data"][cfg["symbol"]] = res
            output["universe"].append(cfg["symbol"])
    with open("opciones_data.json", "w") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f"✅ opciones_data.json — {len(output['universe'])} tickers")

if __name__ == "__main__":
    main()
