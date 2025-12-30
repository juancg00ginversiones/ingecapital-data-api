import json
import yfinance as yf

from tickers import TICKERS_BY_SECTOR
from indicators import rsi, macd_bias, sma, volume_analysis


def analyze_ticker(ticker):
    df = yf.download(ticker, period="1y", interval="1d", progress=False)
    if df.empty:
        return None

    close = df["Close"].dropna()
    volume = df["Volume"].dropna()

    last = close.iloc[-1]
    prev = close.iloc[-2]

    rsi_val = round(rsi(close).iloc[-1], 2)
    sma21 = sma(close, 21).iloc[-1]
    sma200 = sma(close, 200).iloc[-1]

    sma21_status = "above" if last > sma21 else "below"
    sma200_status = "above" if last > sma200 else "below"

    vol_level, vol_trend = volume_analysis(volume)

    summary = " | ".join([
        "RSI sobrecompra" if rsi_val >= 70 else
        "RSI sobreventa" if rsi_val <= 30 else
        "RSI neutral",
        macd_bias(close),
        f"SMA21 {'encima' if sma21_status=='above' else 'debajo'}",
        f"SMA200 {'encima' if sma200_status=='above' else 'debajo'}",
        f"Volumen {vol_level} {vol_trend}"
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
            "volume": {
                "level": vol_level,
                "trend": vol_trend
            }
        },
        "summary": summary
    }


def run_batch():
    output = {
        "as_of": None,
        "sectors": {}
    }

    for sector, tickers in TICKERS_BY_SECTOR.items():
        output["sectors"][sector] = []

        for ticker in tickers:
            data = analyze_ticker(ticker)
            if data:
                output["sectors"][sector].append(data)
                output["as_of"] = data.get("as_of", None)

    return output


if __name__ == "__main__":
    result = run_batch()
    with open("assets.json", "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    print("✅ assets.json generado correctamente")
