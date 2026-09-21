"""Stratégie simple SMA7 vs SMA25 + filtre RSI. Pure fonction."""
try:
    from .indicators import sma, rsi
except ImportError:
    from indicators import sma, rsi

FAST = 7
SLOW = 25
RSI_N = 14


def decide(prices):
    """Retourne {signal, sma_fast, sma_slow, rsi}."""
    sma_fast = sma(prices, FAST)
    sma_slow = sma(prices, SLOW)
    rsi_val = rsi(prices, RSI_N)
    if sma_fast > sma_slow and rsi_val < 70:
        signal = "BUY"
    elif sma_fast < sma_slow and rsi_val > 30:
        signal = "SELL"
    else:
        signal = "HOLD"
    return {"signal": signal, "sma_fast": sma_fast, "sma_slow": sma_slow, "rsi": rsi_val}
