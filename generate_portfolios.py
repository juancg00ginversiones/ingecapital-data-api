# ============================================================
# GENERATE PORTFOLIOS — GitHub Actions
# Metodología: GBM con reversión a media de largo plazo
# Rendimiento histórico real año a año incluido
# Output: portfolios_data.json
# ============================================================

import json
import datetime
import numpy as np
import pandas as pd
import yfinance as yf
import warnings
warnings.filterwarnings("ignore")

# ============================================================
# CARTERAS — 15 portafolios temáticos
# ============================================================
PORTFOLIOS = [
    {
        "id": 1,
        "title": "Lo Esencial — Must Have",
        "risk": "Moderado",
        "risk_level": "moderado",
        "description": "Los activos que todo inversor debería tener: los principales índices de EE.UU., Oro y Bitcoin. La base de cualquier cartera diversificada.",
        "assets": [
            {"name": "SPY",  "value": 25},
            {"name": "QQQ",  "value": 20},
            {"name": "IWM",  "value": 10},
            {"name": "DIA",  "value": 5},
            {"name": "GLD",  "value": 20},
            {"name": "IBIT", "value": 20},
        ]
    },
    {
        "id": 2,
        "title": "Tecnología Mega Cap",
        "risk": "Moderado",
        "risk_level": "moderado",
        "description": "Las empresas tecnológicas más grandes del mundo con flujos de caja robustos y posiciones dominantes de mercado.",
        "assets": [
            {"name": "NVDA",  "value": 15},
            {"name": "AAPL",  "value": 15},
            {"name": "MSFT",  "value": 15},
            {"name": "GOOGL", "value": 10},
            {"name": "AMZN",  "value": 10},
            {"name": "META",  "value": 10},
            {"name": "AVGO",  "value": 10},
            {"name": "TSM",   "value": 10},
            {"name": "ORCL",  "value": 5},
        ]
    },
    {
        "id": 3,
        "title": "IA & Semiconductores",
        "risk": "Agresivo",
        "risk_level": "agresivo",
        "description": "El hardware que hace posible la revolución de la IA: semiconductores, foundries y equipamiento crítico.",
        "assets": [
            {"name": "NVDA", "value": 20},
            {"name": "TSM",  "value": 15},
            {"name": "AVGO", "value": 15},
            {"name": "ASML", "value": 10},
            {"name": "AMD",  "value": 15},
            {"name": "AMAT", "value": 10},
            {"name": "LRCX", "value": 10},
            {"name": "MU",   "value": 5},
        ]
    },
    {
        "id": 4,
        "title": "Software & Cloud",
        "risk": "Moderado",
        "risk_level": "moderado",
        "description": "Líderes en software empresarial, cloud computing e inteligencia artificial aplicada. Márgenes altos y recurrencia de ingresos.",
        "assets": [
            {"name": "MSFT", "value": 25},
            {"name": "CRM",  "value": 20},
            {"name": "NOW",  "value": 20},
            {"name": "ORCL", "value": 15},
            {"name": "PLTR", "value": 20},
        ]
    },
    {
        "id": 5,
        "title": "Tecnología Disruptiva",
        "risk": "Agresivo",
        "risk_level": "agresivo",
        "description": "Sectores de alto crecimiento: ciberseguridad, energía nuclear para data centers y análisis de datos.",
        "assets": [
            {"name": "URA",  "value": 20},
            {"name": "PANW", "value": 25},
            {"name": "OKLO", "value": 15},
            {"name": "CIBR", "value": 20},
            {"name": "PLTR", "value": 20},
        ]
    },
    {
        "id": 6,
        "title": "Data Centers & Energía IA",
        "risk": "Agresivo",
        "risk_level": "agresivo",
        "description": "La infraestructura física que alimenta la IA: data centers y generación de energía limpia para el cómputo masivo.",
        "assets": [
            {"name": "VST",  "value": 30},
            {"name": "CEG",  "value": 30},
            {"name": "OKLO", "value": 20},
            {"name": "COIN", "value": 20},
        ]
    },
    {
        "id": 7,
        "title": "Dividendos & Valor",
        "risk": "Conservador",
        "risk_level": "conservador",
        "description": "Empresas con historial probado de dividendos crecientes durante décadas. Preservación de capital con ingresos pasivos consistentes.",
        "assets": [
            {"name": "KO",   "value": 15},
            {"name": "JNJ",  "value": 15},
            {"name": "PG",   "value": 15},
            {"name": "MCD",  "value": 10},
            {"name": "WMT",  "value": 10},
            {"name": "V",    "value": 10},
            {"name": "JPM",  "value": 10},
            {"name": "ABBV", "value": 15},
        ]
    },
    {
        "id": 8,
        "title": "Defensivo Clásico",
        "risk": "Conservador",
        "risk_level": "conservador",
        "description": "Empresas consolidadas de consumo masivo y salud con baja volatilidad. Ideal para preservación de capital en mercados turbulentos.",
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
        "id": 9,
        "title": "Salud & Farma Líderes",
        "risk": "Moderado",
        "risk_level": "moderado",
        "description": "Las farmacéuticas más grandes del mundo, con líderes en tratamientos GLP-1, oncología y biotecnología avanzada.",
        "assets": [
            {"name": "LLY",  "value": 20},
            {"name": "JNJ",  "value": 20},
            {"name": "ABBV", "value": 20},
            {"name": "UNH",  "value": 20},
            {"name": "NVO",  "value": 20},
        ]
    },
    {
        "id": 10,
        "title": "Cripto Equities",
        "risk": "Muy Agresivo",
        "risk_level": "muy_agresivo",
        "description": "Exposición directa e indirecta al ecosistema cripto via ETFs Spot y empresas del sector.",
        "assets": [
            {"name": "IBIT", "value": 35},
            {"name": "ETHA", "value": 25},
            {"name": "COIN", "value": 20},
            {"name": "MSTR", "value": 20},
        ]
    },
    {
        "id": 11,
        "title": "Argentina Blue Chips",
        "risk": "Agresivo",
        "risk_level": "agresivo",
        "description": "Las empresas más representativas del Merval. Energía, bancos y utilities con alto potencial ante la normalización macro.",
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
        "id": 12,
        "title": "Metales & Mineras",
        "risk": "Moderado",
        "risk_level": "moderado",
        "description": "Cobertura contra inflación y devaluación global via oro, plata y mineras productoras.",
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
        "id": 13,
        "title": "Brasil Select",
        "risk": "Agresivo",
        "risk_level": "agresivo",
        "description": "Oportunidades en la economía más grande de LATAM: fintech digital, materias primas y banca tradicional.",
        "assets": [
            {"name": "EWZ",  "value": 30},
            {"name": "NU",   "value": 20},
            {"name": "XP",   "value": 15},
            {"name": "BBD",  "value": 15},
            {"name": "VALE", "value": 20},
        ]
    },
    {
        "id": 14,
        "title": "LATAM & Emergentes",
        "risk": "Agresivo",
        "risk_level": "agresivo",
        "description": "Exposición diversificada a mercados emergentes con foco en LATAM y Asia. Alto potencial de crecimiento a largo plazo.",
        "assets": [
            {"name": "EWZ",  "value": 25},
            {"name": "FXI",  "value": 20},
            {"name": "BABA", "value": 20},
            {"name": "NU",   "value": 20},
            {"name": "BBD",  "value": 15},
        ]
    },
    {
        "id": 15,
        "title": "China Tech & Consumer",
        "risk": "Agresivo",
        "risk_level": "agresivo",
        "description": "Exposición al gigante asiático con valuaciones históricamente bajas en tecnología y consumo digital.",
        "assets": [
            {"name": "FXI",  "value": 40},
            {"name": "BABA", "value": 30},
            {"name": "NTES", "value": 30},
        ]
    },
]

# ============================================================
# BENCHMARKS DE LARGO PLAZO (rendimiento anual real histórico)
# Fuente: evidencia empírica de mercados globales
# ============================================================
BENCHMARK_MU = {
    "conservador":  0.05,   # 5% anual real
    "moderado":     0.07,   # 7% anual real
    "agresivo":     0.09,   # 9% anual real
    "muy_agresivo": 0.11,   # 11% anual real
}

MU_CAP = 0.20  # cap máximo de mu ajustado = 20% anual

# ============================================================
# HELPERS
# ============================================================

def to_scalar(x):
    if x is None:
        return None
    if isinstance(x, pd.Series):
        return float(x.iloc[0]) if len(x) > 0 else None
    if isinstance(x, np.ndarray):
        return float(x.ravel()[0]) if x.size > 0 else None
    return float(x)

def flatten_series(series):
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

def download_prices(tickers, years=5):
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
        print(f"\n⚠️  No disponibles: {failed}")

    return prices

# ============================================================
# RENDIMIENTO YTD
# ============================================================

def calc_ytd_return(assets, prices):
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

    return weighted_return if total_weight >= 0.5 else None

# ============================================================
# RENDIMIENTO POR PERÍODO
# ============================================================

def calc_portfolio_returns(assets, prices, period_days):
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

    return weighted_return if total_weight >= 0.5 else None

# ============================================================
# HISTORIAL AÑO A AÑO
# ============================================================

def calc_yearly_returns(assets, prices):
    """Calcula el rendimiento real de la cartera por año calendario"""
    current_year = datetime.date.today().year
    results = {}

    for year in range(current_year - 3, current_year):
        start_date = datetime.date(year, 1, 1)
        end_date   = datetime.date(year, 12, 31)

        weighted_return = 0.0
        total_weight    = 0.0

        for a in assets:
            ticker = a["name"]
            weight = a["value"] / 100.0
            if ticker not in prices:
                continue
            series = flatten_series(prices[ticker])
            series.index = pd.to_datetime(series.index)

            past  = series[series.index.date <= start_date]
            fut   = series[series.index.date <= end_date]
            if past.empty or fut.empty:
                continue

            price_start = to_scalar(past.iloc[-1])
            price_end   = to_scalar(fut.iloc[-1])
            if price_start is None or price_end is None or price_start <= 0:
                continue

            ret = (price_end / price_start) - 1.0
            weighted_return += ret * weight
            total_weight    += weight

        if total_weight >= 0.5:
            results[str(year)] = round(weighted_return * 100, 2)

    return results

# ============================================================
# VOLATILIDAD Y SHARPE
# ============================================================

def calc_portfolio_metrics(assets, prices, window_days=750):
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

# ============================================================
# PROYECCIÓN GBM CON REVERSIÓN A MEDIA DE LARGO PLAZO
# ============================================================

def gbm_mean_reversion_projection(
    assets, prices, risk_level,
    horizon_days=252, n_sims=5000, window_days=750
):
    """
    GBM con reversión a media de largo plazo.
    
    Metodología:
    - mu_cartera = rendimiento histórico anualizado (ventana 750 días)
    - mu_largo_plazo = benchmark según perfil de riesgo (5-11% anual)
    - mu_ajustado = 0.40 × mu_cartera + 0.60 × mu_largo_plazo
    - mu_final = min(mu_ajustado, MU_CAP=20% anual)
    - sigma = volatilidad histórica real de la cartera
    
    Esta metodología modera el sesgo de extrapolación del GBM puro
    y es similar a la usada por fondos de largo plazo (ej: factor models).
    """
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

    # ── MU AJUSTADO ──────────────────────────────────────────
    mu_historico   = float(portfolio_returns.mean()) * 252  # anualizado
    mu_largo_plazo = BENCHMARK_MU.get(risk_level, 0.07)

    # Mezcla 40/60
    mu_ajustado = 0.40 * mu_historico + 0.60 * mu_largo_plazo

    # Cap de 20% anual
    mu_final = min(mu_ajustado, MU_CAP)

    # Convertir a diario
    mu_diario = mu_final / 252

    # ── SIGMA REAL ───────────────────────────────────────────
    sigma = float(portfolio_returns.std())

    if sigma <= 0 or not np.isfinite(mu_diario):
        return None

    # ── SIMULACIÓN GBM ───────────────────────────────────────
    np.random.seed(42)
    Z       = np.random.normal(size=(n_sims, horizon_days))
    log_inc = (mu_diario - 0.5 * sigma**2) + sigma * Z

    terminal = (np.exp(log_inc.cumsum(axis=1)[:, -1]) - 1.0) * 100

    # Fan chart mensual (12 puntos)
    fan_data = []
    for mes in range(1, 13):
        t     = min(mes * 21, horizon_days)
        ret_t = (np.exp(log_inc[:, :t].cumsum(axis=1)[:, -1]) - 1.0) * 100
        fan_data.append({
            "mes":  mes,
            "pesimista": round(float(np.percentile(ret_t, 25)), 2),
            "base":     round(float(np.percentile(ret_t, 50)), 2),
            "optimista": round(float(np.percentile(ret_t, 75)), 2),
        })

    return {
        "horizonte":      "1 año",
        "metodologia":    f"GBM reversión a media — mu_hist: {mu_historico*100:.1f}% · mu_LP: {mu_largo_plazo*100:.0f}% · mu_final: {mu_final*100:.1f}% · sigma_anual: {sigma*np.sqrt(252)*100:.1f}%",
        "mu_historico":   round(mu_historico * 100, 2),
        "mu_largo_plazo": round(mu_largo_plazo * 100, 2),
        "mu_final":       round(mu_final * 100, 2),
        "pesimista": round(float(np.percentile(terminal, 25)), 2),
        "base":     round(float(np.percentile(terminal, 50)), 2),
        "optimista": round(float(np.percentile(terminal, 75)), 2),
        "fan":            fan_data,
    }

# ============================================================
# MAIN
# ============================================================

def main():
    print("🚀 Iniciando generación de portfolios_data.json...\n")
    print("📐 Metodología: GBM con reversión a media de largo plazo\n")

    all_tickers = get_all_tickers(PORTFOLIOS)
    print(f"📊 Total tickers únicos: {len(all_tickers)}\n")

    prices = download_prices(all_tickers, years=5)
    print(f"\n✅ Precios descargados: {len(prices)}/{len(all_tickers)} tickers\n")

    print("📈 Calculando métricas por portafolio...\n")

    portfolios_output = []

    for p in PORTFOLIOS:
        print(f"  [{p['id']:02d}] {p['title']}...")

        assets     = p["assets"]
        risk_level = p["risk_level"]

        ytd        = calc_ytd_return(assets, prices)
        r1y        = calc_portfolio_returns(assets, prices, period_days=252)
        r3y        = calc_portfolio_returns(assets, prices, period_days=756)
        yearly     = calc_yearly_returns(assets, prices)
        vol, sharpe = calc_portfolio_metrics(assets, prices, window_days=750)
        proyeccion  = gbm_mean_reversion_projection(
            assets, prices, risk_level,
            horizon_days=252, n_sims=5000, window_days=750
        )

        portfolio_data = {
            "id":          p["id"],
            "title":       p["title"],
            "risk":        p["risk"],
            "rendimientos": {
                "ytd": round(ytd * 100, 2) if ytd is not None else None,
                "1y":  round(r1y * 100, 2) if r1y is not None else None,
                "3y":  round(r3y * 100, 2) if r3y is not None else None,
            },
            "historial_anual": yearly,
            "metricas": {
                "volatilidad_anual": vol,
                "sharpe_ratio":      sharpe,
            },
            "proyeccion_1y": proyeccion,
        }

        def fmt(v, suffix="%"):
            return f"{v:+.1f}{suffix}" if v is not None else "N/D"

        p50 = proyeccion["p50"] if proyeccion else None
        print(
            f"       YTD: {fmt(portfolio_data['rendimientos']['ytd'])} | "
            f"1Y: {fmt(portfolio_data['rendimientos']['1y'])} | "
            f"3Y: {fmt(portfolio_data['rendimientos']['3y'])} | "
            f"Vol: {fmt(vol)} | Sharpe: {fmt(sharpe, '')} | "
            f"P50 proj: {fmt(p50)}"
        )
        if yearly:
            print(f"       Historial: {yearly}")

        portfolios_output.append(portfolio_data)

    output = {
        "updated_at": datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "fecha":      datetime.date.today().isoformat(),
        "metodologia": (
            "Rendimientos históricos reales en USD via yfinance (5 años de historia). "
            "Proyección GBM con reversión a media de largo plazo: "
            "mu_final = min(0.40 × mu_histórico + 0.60 × mu_largo_plazo, 20% anual). "
            "Benchmarks: Conservador 5%, Moderado 7%, Agresivo 9%, Muy Agresivo 11%. "
            "Volatilidad calculada con ventana de 750 días de trading. "
            "Sharpe ratio con tasa libre de riesgo 4.5% (T-Bills USA)."
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
