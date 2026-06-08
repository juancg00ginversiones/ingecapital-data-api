# ============================================================
# GENERATE PORTFOLIOS — GitHub Actions
# Calcula rendimientos históricos y proyección GBM
# para los 10 portafolios sugeridos de IngeCapital
# Output: portfolios_data.json
# ============================================================

import json
import datetime
import numpy as np
import pandas as pd
import yfinance as yf
import warnings
warnings.filterwarnings("ignore")

PORTFOLIOS = [
    {
        "id": 1,
        "title": "Tecnología Mega Cap",
        "risk": "Moderado",
        "assets": [
            {"name": "NVDA", "value": 15},
            {"name": "AAPL", "value": 15},
            {"name": "MSFT", "value": 15},
            {"name": "GOOGL", "value": 10},
            {"name": "AMZN", "value": 10},
            {"name": "META", "value": 10},
            {"name": "AVGO", "value": 10},
            {"name": "TSM",  "value": 10},
            {"name": "ORCL", "value": 5},
        ]
    },
    {
        "id": 2,
        "title": "IA Infraestructura",
        "risk": "Agresivo",
        "assets": [
            {"name": "NVDA", "value": 20},
            {"name": "TSM",  "value": 15},
            {"name": "AVGO", "value": 15},
            {"name": "ASML", "value": 10},
            {"name": "AMD",  "value": 10},
            {"name": "AMAT", "value": 10},
            {"name": "LRCX", "value": 10},
            {"name": "MU",   "value": 10},
        ]
    },
    {
        "id": 3,
        "title": "Tecnología Disruptiva",
        "risk": "Agresivo",
        "assets": [
            {"name": "URA",  "value": 20},
            {"name": "PANW", "value": 20},
            {"name": "OKLO", "value": 15},
            {"name": "CIBR", "value": 25},
            {"name": "PLTR", "value": 20},
        ]
    },
    {
        "id": 4,
        "title": "Defensivo Clásico",
        "risk": "Conservador",
        "assets": [
            {"name": "WMT",  "value": 12.5},
            {"name": "COST", "value": 12.5},
            {"name": "KO",   "value": 12.5},
            {"name": "MCD",  "value": 12.5},
            {"name": "JNJ",  "value": 12.5},
            {"name": "LLY",  "value": 12.5},
            {"name": "UNH",  "value": 12.5},
            {"name": "ABBV", "value": 12.5},
        ]
    },
    {
        "id": 5,
        "title": "Salud & Farma Líderes",
        "risk": "Moderado",
        "assets": [
            {"name": "LLY",  "value": 20},
            {"name": "JNJ",  "value": 20},
            {"name": "ABBV", "value": 20},
            {"name": "UNH",  "value": 20},
            {"name": "NVO",  "value": 20},
        ]
    },
    {
        "id": 6,
        "title": "Cripto Equities",
        "risk": "Muy Agresivo",
        "assets": [
            {"name": "IBIT", "value": 35},
            {"name": "ETHA", "value": 25},
            {"name": "COIN", "value": 20},
            {"name": "MSTR", "value": 20},
        ]
    },
    {
        "id": 7,
        "title": "Argentina Blue Chips",
        "risk": "Agresivo",
        "assets": [
            {"name": "GGAL", "value": 20},
            {"name": "BMA",  "value": 15},
            {"name": "EDN",  "value": 15},
            {"name": "CEPU", "value": 20},
            {"name": "LOMA", "value": 15},
            {"name": "VALE", "value": 15},
        ]
    },
    {
        "id": 8,
        "title": "Metales & Mineras",
        "risk": "Moderado",
        "assets": [
            {"name": "GLD",  "value": 20},
            {"name": "SLV",  "value": 15},
            {"name": "GOLD", "value": 20},
            {"name": "HMY",  "value": 15},
            {"name": "KGC",  "value": 15},
            {"name": "PAAS", "value": 15},
        ]
    },
    {
        "id": 9,
        "title": "Brasil Select",
        "risk": "Agresivo",
        "assets": [
            {"name": "EWZ",  "value": 30},
            {"name": "NU",   "value": 20},
            {"name": "XP",   "value": 15},
            {"name": "BBD",  "value": 15},
            {"name": "VALE", "value": 20},
        ]
    },
    {
        "id": 10,
        "title": "China Tech & Consumer",
        "risk": "Agresivo",
        "assets": [
            {"name": "FXI",  "value": 40},
            {"name": "BABA", "value": 30},
            {"name": "NTES", "value": 30},
        ]
    }
]

# ============================================================
# HELPERS
# ============================================================

def to_scalar(x):
    """Convierte cualquier tipo a float escalar de forma segura"""
    if x is None:
        return None
    if isinstance(x, pd.Series):
        return float(x.iloc[0]) if len(x) > 0 else None
    if isinstance(x, (np.ndarray,)):
        return float(x.ravel()[0]) if x.size > 0 else None
    return float(x)

def flatten_series(series):
    """
    Asegura que la serie sea 1D con valores escalares.
    Resuelve el MultiIndex que genera yfinance a veces.
    """
    if isinstance(series, pd.DataFrame):
        series = series.iloc[:, 0]
    if isinstance(series.index, pd.MultiIndex):
        series = series.droplevel(level=1)
    series = series.squeeze()
    return series.dropna()

def get_all_tickers(portfolios):
    tickers = set()
    for p in portfolios:
        for a in p["assets"]:
            tickers.add(a["name"])
    return list(tickers)

# ============================================================
# DESCARGA DE PRECIOS
# ============================================================

def download_prices(tickers, years=4):
    print(f"📥 Descargando precios para {len(tickers)} tickers...")
    end   = datetime.date.today()
    start = end - datetime.timedelta(days=years * 365)

    prices = {}
    failed = []

    for ticker in tickers:
        try:
            raw = yf.download(
                ticker,
                start=start,
                end=end,
                interval="1d",
                auto_adjust=True,
                progress=False
            )
            if raw is None or raw.empty:
                failed.append(ticker)
                print(f"  ⚠️  {ticker}: sin datos")
                continue

            # Extraer Close de forma robusta
            if isinstance(raw.columns, pd.MultiIndex):
                close = raw["Close"][ticker]
            else:
                close = raw["Close"]

            close = flatten_series(close)

            if len(close) < 100:
                failed.append(ticker)
                print(f"  ⚠️  {ticker}: datos insuficientes ({len(close)} días)")
                continue

            prices[ticker] = close
            print(f"  ✅ {ticker}: {len(close)} días")

        except Exception as e:
            failed.append(ticker)
            print(f"  ❌ {ticker}: {e}")

    if failed:
        print(f"\n⚠️  Tickers no disponibles: {failed}")

    return prices

# ============================================================
# CÁLCULO DE RENDIMIENTOS
# ============================================================

def calc_ytd_return(assets, prices):
    """Rendimiento YTD (desde 1 de enero del año actual)"""
    year_start = datetime.date(datetime.date.today().year, 1, 1)

    weighted_return = 0.0
    total_weight    = 0.0

    for a in assets:
        ticker = a["name"]
        weight = a["value"] / 100.0

        if ticker not in prices:
            continue

        series = flatten_series(prices[ticker])
        series.index = pd.to_datetime(series.index)

        past = series[series.index.date <= year_start]
        if past.empty:
            continue

        price_start = to_scalar(past.iloc[-1])
        price_now   = to_scalar(series.iloc[-1])

        if price_start is None or price_now is None or price_start <= 0:
            continue

        ret = (price_now / price_start) - 1.0
        weighted_return += ret * weight
        total_weight    += weight

    if total_weight < 0.5:
        return None
    return weighted_return

def calc_portfolio_returns(assets, prices, period_days):
    """Rendimiento de la cartera en los últimos period_days días hábiles"""
    weighted_return = 0.0
    total_weight    = 0.0

    for a in assets:
        ticker = a["name"]
        weight = a["value"] / 100.0

        if ticker not in prices:
            continue

        series = flatten_series(prices[ticker])

        if len(series) < period_days:
            continue

        price_now  = to_scalar(series.iloc[-1])
        price_then = to_scalar(series.iloc[-period_days])

        if price_now is None or price_then is None or price_then <= 0:
            continue

        ret = (price_now / price_then) - 1.0
        weighted_return += ret * weight
        total_weight    += weight

    if total_weight < 0.5:
        return None
    return weighted_return

def calc_portfolio_metrics(assets, prices, window_days=750):
    """Volatilidad anualizada y Sharpe ratio"""
    all_series = {}
    for a in assets:
        ticker = a["name"]
        if ticker in prices and len(prices[ticker]) > window_days // 2:
            all_series[ticker] = flatten_series(prices[ticker])

    if not all_series:
        return None, None

    df = pd.DataFrame(all_series).dropna()
    if len(df) < 100:
        return None, None

    df = df.iloc[-window_days:]
    daily_returns = df.pct_change().dropna()

    weights      = []
    tickers_used = []
    for a in assets:
        if a["name"] in daily_returns.columns:
            weights.append(a["value"] / 100.0)
            tickers_used.append(a["name"])

    if not weights:
        return None, None

    total_w = sum(weights)
    weights = [w / total_w for w in weights]

    portfolio_returns = daily_returns[tickers_used].dot(weights)

    vol_anual = float(portfolio_returns.std() * np.sqrt(252) * 100)
    ret_anual = float(portfolio_returns.mean() * 252 * 100)
    rf        = 4.5
    sharpe    = (ret_anual - rf) / vol_anual if vol_anual > 0 else 0.0

    return round(vol_anual, 2), round(sharpe, 2)

def gbm_projection(assets, prices, horizon_days=252, n_sims=5000, window_days=750):
    """Proyección GBM a 1 año — retorna percentiles y fan chart mensual"""
    all_series = {}
    for a in assets:
        ticker = a["name"]
        if ticker in prices and len(prices[ticker]) > window_days // 2:
            all_series[ticker] = flatten_series(prices[ticker])

    if not all_series:
        return None

    df = pd.DataFrame(all_series).dropna()
    if len(df) < 200:
        return None

    df = df.iloc[-window_days:]
    daily_returns = df.pct_change().dropna()

    weights      = []
    tickers_used = []
    for a in assets:
        if a["name"] in daily_returns.columns:
            weights.append(a["value"] / 100.0)
            tickers_used.append(a["name"])

    if not weights:
        return None

    total_w     = sum(weights)
    weights_arr = np.array([w / total_w for w in weights])

    portfolio_returns = daily_returns[tickers_used].dot(weights_arr)

    mu    = float(portfolio_returns.mean())
    sigma = float(portfolio_returns.std())

    if sigma <= 0 or not np.isfinite(mu) or not np.isfinite(sigma):
        return None

    np.random.seed(42)
    Z       = np.random.normal(size=(n_sims, horizon_days))
    log_inc = (mu - 0.5 * sigma**2) + sigma * Z

    terminal = (np.exp(log_inc.cumsum(axis=1)[:, -1]) - 1.0) * 100

    # Fan chart mensual
    fan_data = []
    for mes in range(1, 13):
        t = min(mes * 21, horizon_days)
        ret_t = (np.exp(log_inc[:, :t].cumsum(axis=1)[:, -1]) - 1.0) * 100
        fan_data.append({
            "mes":  mes,
            "p5":   round(float(np.percentile(ret_t, 5)), 2),
            "p25":  round(float(np.percentile(ret_t, 25)), 2),
            "p50":  round(float(np.percentile(ret_t, 50)), 2),
            "p75":  round(float(np.percentile(ret_t, 75)), 2),
            "p95":  round(float(np.percentile(ret_t, 95)), 2),
        })

    return {
        "horizonte":    "1 año",
        "metodologia":  "GBM — ventana 750 días (~3 años)",
        "p5":           round(float(np.percentile(terminal, 5)), 2),
        "p25":          round(float(np.percentile(terminal, 25)), 2),
        "p50":          round(float(np.percentile(terminal, 50)), 2),
        "p75":          round(float(np.percentile(terminal, 75)), 2),
        "p95":          round(float(np.percentile(terminal, 95)), 2),
        "fan":          fan_data,
    }

# ============================================================
# MAIN
# ============================================================

def main():
    print("🚀 Iniciando generación de portfolios_data.json...\n")

    all_tickers = get_all_tickers(PORTFOLIOS)
    print(f"📊 Total tickers únicos: {len(all_tickers)}\n")

    prices = download_prices(all_tickers, years=4)
    print(f"\n✅ Precios descargados: {len(prices)}/{len(all_tickers)} tickers\n")

    print("📈 Calculando métricas por portafolio...\n")

    portfolios_output = []

    for p in PORTFOLIOS:
        print(f"  Procesando: {p['title']}...")

        assets = p["assets"]

        ytd = calc_ytd_return(assets, prices)
        r1y = calc_portfolio_returns(assets, prices, period_days=252)
        r3y = calc_portfolio_returns(assets, prices, period_days=756)
        vol, sharpe   = calc_portfolio_metrics(assets, prices, window_days=750)
        proyeccion    = gbm_projection(assets, prices, horizon_days=252,
                                       n_sims=5000, window_days=750)

        portfolio_data = {
            "id":    p["id"],
            "title": p["title"],
            "risk":  p["risk"],
            "rendimientos": {
                "ytd": round(ytd * 100, 2) if ytd is not None else None,
                "1y":  round(r1y * 100, 2) if r1y is not None else None,
                "3y":  round(r3y * 100, 2) if r3y is not None else None,
            },
            "metricas": {
                "volatilidad_anual": vol,
                "sharpe_ratio":      sharpe,
            },
            "proyeccion_1y": proyeccion,
        }

        def fmt(v, suffix="%"):
            return f"{v:+.1f}{suffix}" if v is not None else "N/D"

        print(
            f"    YTD: {fmt(portfolio_data['rendimientos']['ytd'])} | "
            f"1Y: {fmt(portfolio_data['rendimientos']['1y'])} | "
            f"3Y: {fmt(portfolio_data['rendimientos']['3y'])} | "
            f"Vol: {fmt(vol)} | "
            f"Sharpe: {fmt(sharpe, '')} | "
            f"P50: {fmt(proyeccion['p50'] if proyeccion else None)}"
        )

        portfolios_output.append(portfolio_data)

    output = {
        "updated_at":  datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "fecha":       datetime.date.today().isoformat(),
        "metodologia": (
            "Rendimientos históricos reales via yfinance. "
            "Proyección GBM con ventana de 750 días de trading (~3 años). "
            "Sharpe ratio calculado con tasa libre de riesgo 4.5% (T-Bills USA). "
            "Los rendimientos son en USD."
        ),
        "disclaimer": (
            "Rendimientos pasados no garantizan resultados futuros. "
            "Esto es información educativa, no asesoramiento de inversión."
        ),
        "portfolios": portfolios_output,
    }

    with open("portfolios_data.json", "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\n✅ portfolios_data.json generado con {len(portfolios_output)} portafolios")
    print(f"📅 Fecha: {output['fecha']}")

if __name__ == "__main__":
    main()
