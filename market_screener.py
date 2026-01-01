from datetime import datetime
from indicators import analyze_ticker


def get_market_screener_for_api() -> dict:
    result = {
        "as_of": datetime.utcnow().isoformat(),
        "sectors": {
            "test": []
        }
    }

    test_tickers = ["AAPL", "NVDA", "AVGO"]

    for ticker in test_tickers:
        try:
            data = analyze_ticker(ticker)
            result["sectors"]["test"].append(data)
        except Exception as e:
            print(f"[TEST ERROR] {ticker}: {e}")

    return result
