import yfinance as yf
from datetime import datetime
from typing import Optional

from tickers import TICKERS_BY_SECTOR
from indicators import rsi, macd_bias, sma, analyze_volume


# ============================================================
# ANALISIS POR TICKER (ROBUSTO)
# ============================================================
def analyze_ticker(ticker: str) -> Optional[dict]:
    try:
        df = yf.download(
            ticker,
            period="1y",
            interval="1d",
            progress=False
        )

        # Validaciones básicas
        if df is None or df.empty:
            return None

        if "Close" not in df.columns:
            return None

        close = df["Close"].dropna()

        if len(close) < 120:  # <-- CLAVE: no exigir 1 año completo
            return None

        volume = df["Volume"].dropna() if "Volume" in df.columns else None

        last = close.iloc[-1]
        prev = close.iloc[-2]

        # ================= INDICADORES =================
        rsi_val = round(float(rsi(close).iloc[-1]), 2)

        sma21 = sma(close, 21).iloc[-1]
        sma200 = sma(close, 200).iloc[-1] if len(close) >= 200 else None

        volume_info = analyze_volume(volume)

        # ================= SUMMARY =================
        summary_parts = [
            "RSI sobrecompra" if rsi_val >= 70 else
            "RSI sobreventa" if rsi_val <= 30 else
            "RSI neutral",
            macd_bias(close),
            f"SMA21 {'encima' if last > sma21 else 'debajo'}"
        ]

        if sma200 is not None:
            summary_parts.append(
                f"SMA200 {'encima' if last > sma200 else 'debajo'}"
            )

        summary_parts.append(volume_info["diagnostic"])

        summary = " | ".join(summary_parts)

        return {
            "ticker": ticker,
            "price": round(float(last), 2),
            "daily_change_pct": round(((last - prev) / prev) * 100, 2),
            "indicators": {
                "rsi14": {
                    "value": rsi_val
                },
                "macd": {
                    "diagnostic": macd_bias(close)
                },
                "sma21": {
                    "status": "above" if last > sma21 else "below"
                },
                "sma200": (
                    {"status": "above" if last > sma200 else "below"}
                    if sma200 is not None else None
                ),
                "volume": volume_info
            },
            "summary": summary
        }

    except Exception as e:
        # MUY IMPORTANTE: nunca romper el batch
        print(f"[ERROR] {ticker}: {e}")
        return None


# ============================================================
# ENDPOINT BATCH
# ============================================================
def get_market_screener_for_api() -> dict:
    output = {
        "as_of": datetime.now().isoformat(),
        "sectors": {}
    }

    for sector, tickers in TICKERS_BY_SECTOR.items():
        output["sectors"][sector] = []

        for ticker in tickers:
            data = analyze_ticker(ticker)
            if data:
                output["sectors"][sector].append(data)

    return output
