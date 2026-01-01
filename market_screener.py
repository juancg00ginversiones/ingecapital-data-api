from datetime import datetime
from indicators import analyze_ticker
from tickers import TICKERS_BY_SECTOR


def get_market_screener_for_api() -> dict:
    result = {
        "as_of": datetime.utcnow().isoformat(),
        "sectors": {}
    }

    for sector_name, tickers in TICKERS_BY_SECTOR.items():
        sector_data = []

        for ticker in tickers:
            try:
                data = analyze_ticker(ticker)
                sector_data.append(data)
            except Exception as e:
                # Log opcional (Render lo muestra)
                print(f"[MARKET SCREENER ERROR] {ticker}: {e}")
                continue

        result["sectors"][sector_name] = sector_data

    return result
