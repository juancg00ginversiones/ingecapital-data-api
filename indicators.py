import numpy as np
import pandas as pd
import yfinance as yf

def rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = (delta.where(delta > 0, 0))
    loss = (-delta.where(delta < 0, 0))
    # Usamos adjust=False para emular exactamente a TradingView/Wilder
    avg_gain = gain.ewm(alpha=1/period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/period, adjust=False).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

def macd_bias(series: pd.Series) -> str:
    # Eliminamos NaNs previos para que el cálculo sea limpio
    series = series.dropna()
    if len(series) < 35: # 26 periodos + margen para la señal
        return "MACD: insuf. datos"
    
    ema12 = series.ewm(span=12, adjust=False).mean()
    ema26 = series.ewm(span=26, adjust=False).mean()
    macd = ema12 - ema26
    signal = macd.ewm(span=9, adjust=False).mean()
    
    # Validamos que los últimos valores no sean NaN
    if pd.isna(macd.iloc[-1]) or pd.isna(signal.iloc[-1]):
        return "MACD: na"

    return "MACD: sesgo alcista" if macd.iloc[-1] > signal.iloc[-1] else "MACD: sesgo bajista"

def sma(series: pd.Series, window: int) -> pd.Series:
    return series.rolling(window=window).mean()

def analyze_ticker(ticker: str) -> dict:
    # IMPORTANTE: Descargamos un poco más de 1 año para asegurar que la SMA200 tenga datos suficientes
    df = yf.download(ticker, period="18mo", interval="1d", progress=False, auto_adjust=True)

    if df.empty:
        raise ValueError("Sin datos")

    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    # Limpieza crucial: eliminamos cualquier fila con NaNs en el precio de cierre
    close = df["Close"].dropna()

    if len(close) < 2:
        raise ValueError("Datos insuficientes")

    last = float(close.iloc[-1])
    prev = float(close.iloc[-2])
    daily_change_pct = (last / prev - 1) * 100

    # --- RSI ---
    rsi_series = rsi(close)
    rsi_val = rsi_series.iloc[-1]

    # --- MACD ---
    macd_diag = macd_bias(close)

    # --- SMAs con validación de NaN ---
    def get_sma_status(val_close, series, window):
        line = series.rolling(window=window).mean()
        last_sma = line.iloc[-1]
        if pd.isna(last_sma):
            return "na"
        return "above" if val_close > last_sma else "below"

    return {
        "ticker": ticker,
        "price": round(last, 2),
        "daily_change_pct": round(daily_change_pct, 2),
        "indicators": {
            "rsi14": {"value": round(float(rsi_val), 2) if not pd.isna(rsi_val) else None},
            "macd": {"diagnostic": macd_diag},
            "sma21": {"status": get_sma_status(last, close, 21)},
            "sma200": {"status": get_sma_status(last, close, 200)}
        }
    }
