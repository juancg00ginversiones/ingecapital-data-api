import yfinance as yf
from datetime import datetime

from tickers import TICKERS_BY_SECTOR
from indicators import (
    rsi,
    macd_bias,
    sma,
    analyze_volume,
    get_session_progress
)


def analyze_ticker(ticker: str, session_type: str) -> dict | None:
    try:
        df = yf.download(ticker, period="1y", interval="1d", progress=False)
        if df.empty:
            return None

        close = df["Close"].dropna()
        volume = df["Volume"].dropna()

        if len(close) < 210:
            return None

        last = close.iloc[-1]
        prev = close.iloc[-2]

        # RSI
        rsi_val = round(float(rsi(close).iloc[-1]), 2)

        # Medias
        sma21 = sma(close, 21).iloc[-1]
        sma200 = sma(close, 200).iloc[-1]

        sma21_status = "above" if last > sma21 else "below"
        sma200_status = "above" if last > sma200 else "below"

        # Volumen contextual
        session_progress = (
            get_session_progress() if session_type == "open" else None
        )

        volume_info = analyze_volume(
            volume,
            session_type=session_type,
            session_progress=session_progress
        )

        summary = " | ".join([
            "RSI sobrecompra" if rsi_val >= 70 else
            "RSI sobreventa" if rsi_val <= 30 else
            "RSI neutral",
            macd_bias(close),
            f"SMA21 {'encima' if sma21_status == 'above' else 'debajo'}",
            f"SMA200 {'encima' if sma200_status == 'above' else 'debajo'}",
            volume_info["diagnostic"]
        ])

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
                    "status": sma21_status
                },
                "sma200": {
                    "status": sma200_status
                },
                "volume": volume_info
            },
            "summary": summary
        }

    except Exception:
        return None


def get_market_screener_for_api() -> dict:
    """
    Devuelve screener técnico batch agrupado por sector.
    Se actualiza según session_type:
    - open  → rueda abierta
    - close → cierre
    """

    now = datetime.now()
    session_type = "open" if now.hour < 17 else "close"

    output = {
        "as_of": now.isoformat(),
        "session_type": session_type,
        "sectors": {}
    }

    for sector, tickers in TICKERS_BY_SECTOR.items():
        output["sectors"][sector] = []

        for ticker in tickers:
            data = analyze_ticker(ticker, session_type)
            if data:
                output["sectors"][sector].append(data)

    return output
