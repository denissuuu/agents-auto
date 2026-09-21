"""Explications simples en francais pour chaque signal. Stdlib uniquement."""


def explain(signal, sma_fast, sma_slow, rsi, prix, executed=True):
    try:
        sf = float(sma_fast)
    except (TypeError, ValueError):
        sf = 0.0
    try:
        ss = float(sma_slow)
    except (TypeError, ValueError):
        ss = 0.0
    try:
        r = float(rsi)
    except (TypeError, ValueError):
        r = 50.0
    try:
        p = float(prix)
    except (TypeError, ValueError):
        p = 0.0
    ecart = sf - ss
    if signal == "BUY":
        if executed:
            return (
                f"J'achete a {p:.2f} car la moyenne 7h ({sf:.0f}) depasse "
                f"la 25h ({ss:.0f}) de +{ecart:.0f} et le score stress {r:.0f} "
                f"n'est pas surchauffe (<70)."
            )
        return (
            f"Signal BUY mais deja tout en XRP, j'attends. "
            f"Moyenne 7h ({sf:.0f}) au-dessus de la 25h ({ss:.0f}), "
            f"stress {r:.0f} (<70)."
        )
    if signal == "SELL":
        if executed:
            return (
                f"Je vends a {p:.2f} car la moyenne 7h ({sf:.0f}) passe "
                f"sous la 25h ({ss:.0f}) de {ecart:.0f} et le stress {r:.0f} "
                f"reste au-dessus de 30."
            )
        return (
            f"Signal SELL mais rien en XRP, je ne fais rien. "
            f"Moyenne 7h ({sf:.0f}) sous la 25h ({ss:.0f}), stress {r:.0f}."
        )
    return (
        f"Je garde ma position a {p:.2f} : moyennes 7h ({sf:.0f}) et 25h ({ss:.0f}) "
        f"proches (ecart {ecart:+.0f}) ou stress {r:.0f} neutre."
    )
