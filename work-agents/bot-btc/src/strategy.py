"""Signaux d'entrée simples, sans LLM, calculés uniquement sur l'historique fourni."""
try:
    from .indicators import sma, rsi
except ImportError:
    from indicators import sma, rsi

FAST = 7
SLOW = 25
RSI_N = 14


def decide(prices, fast=FAST, slow=SLOW, rsi_n=RSI_N):
    """Retourne un signal SMA/RSI; ne jamais passer une bougie future."""
    sma_fast = sma(prices, fast)
    sma_slow = sma(prices, slow)
    rsi_val = rsi(prices, rsi_n)
    if sma_fast > sma_slow and rsi_val < 70:
        signal = "BUY"
    elif sma_fast < sma_slow and rsi_val > 30:
        signal = "SELL"
    else:
        signal = "HOLD"
    return {
        "signal": signal,
        "sma_fast": sma_fast,
        "sma_slow": sma_slow,
        "rsi": rsi_val,
    }


def decide_sma_only(prices, fast=FAST, slow=SLOW):
    """Comparateur explicite sans RSI ni LLM."""
    sma_fast = sma(prices, fast)
    sma_slow = sma(prices, slow)
    signal = "BUY" if sma_fast > sma_slow else "SELL" if sma_fast < sma_slow else "HOLD"
    return {"signal": signal, "sma_fast": sma_fast, "sma_slow": sma_slow}


def decide_with_config(prices, strategy_config=None):
    """Applique les périodes configurables de la stratégie d'entrée."""
    strategy_config = strategy_config or {}
    return decide(
        prices,
        fast=int(strategy_config.get("fast", FAST)),
        slow=int(strategy_config.get("slow", SLOW)),
        rsi_n=int(strategy_config.get("rsi", RSI_N)),
    )


def decide_sma_with_config(prices, strategy_config=None):
    strategy_config = strategy_config or {}
    return decide_sma_only(
        prices,
        fast=int(strategy_config.get("fast", FAST)),
        slow=int(strategy_config.get("slow", SLOW)),
    )


def decide_buy_hold(prices, fast=FAST, slow=SLOW):
    """Signal achat-et-gardé : achète en tendance haussière, ne vend jamais.

    La seule sortie est la protection stop-loss gérée par le portefeuille ;
    aucune vente de signal, de cible, de durée ou de trailing.
    """
    sma_fast = sma(prices, fast)
    sma_slow = sma(prices, slow)
    signal = "BUY" if sma_fast > sma_slow else "HOLD"
    return {"signal": signal, "sma_fast": sma_fast, "sma_slow": sma_slow}


def decide_buy_hold_with_config(prices, strategy_config=None):
    strategy_config = strategy_config or {}
    return decide_buy_hold(
        prices,
        fast=int(strategy_config.get("fast", FAST)),
        slow=int(strategy_config.get("slow", SLOW)),
    )
