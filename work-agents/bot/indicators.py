"""Indicateurs techniques (stdlib uniquement)."""


def sma(values, n):
    """Moyenne mobile simple des n dernières valeurs."""
    if not values:
        raise ValueError("sma: liste vide")
    if n <= 0:
        raise ValueError("sma: n doit être > 0")
    if len(values) < n:
        raise ValueError(f"sma: pas assez de données ({len(values)} < {n})")
    return sum(values[-n:]) / n


def rsi(prices, n=14):
    """RSI simplifié (moyenne gains/pertes, style Wilder simplifié)."""
    if not prices:
        raise ValueError("rsi: liste vide")
    if n <= 0:
        raise ValueError("rsi: n doit être > 0")
    if len(prices) < n + 1:
        raise ValueError(f"rsi: pas assez de données ({len(prices)} < {n + 1})")
    gains = 0.0
    losses = 0.0
    for i in range(len(prices) - n, len(prices)):
        diff = prices[i] - prices[i - 1]
        if diff > 0:
            gains += diff
        else:
            losses -= diff
    if losses == 0:
        return 100.0 if gains > 0 else 50.0
    rs = (gains / n) / (losses / n)
    return 100.0 - (100.0 / (1.0 + rs))
