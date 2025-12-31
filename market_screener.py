import yfinance as yf
from datetime import datetime
from typing import Optional

from tickers import TICKERS_BY_SECTOR
from indicators import rsi, macd_bias, sma


# ============================================================
# ANALISIS POR TICKER (ROBUSTO – SIN VOLUMEN)
# ============================================================
def analyze_ticker(ticker: str) -> Optional[dict]:
    try:
        df = yf.download(
            ticker,
            period="1y",
            interval="1d",
            auto_adjust=False,
            progress=False
        )

        if df is None or df.empty or "Close" not in df.columns:
            return None

        close = df["Close"].dropna()

        if len(close) < 120:
            return None

        last = close.iloc[-1].item()
        prev = close.iloc[-2].item()

        rsi_val = rsi(close).iloc[-1].item()
        sma21 = sma(close, 21).iloc[-1].item()

        sma200 = None
        if len(close) >= 200:
            sma200 = sma(close, 200).iloc[-1].item()

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

        summary = " | ".join(summary_parts)

        return {
            "ticker": ticker,
            "price": round(last, 2),
            "daily_change_pct": round(((last - prev) / prev) * 100, 2),
            "indicators": {
                "rsi14": {"value": round(rsi_val, 2)},
                "macd": {"diagnostic": macd_bias(close)},
                "sma21": {"status": "above" if last > sma21 else "below"},
                "sma200": (
                    {"status": "above" if last > sma200 else "below"}
                    if sma200 is not None else None
                )
            },
            "summary": summary
        }

    except Exception as e:
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


