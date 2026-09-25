"""Lecture de signal XRP paper-only, sans boucle ni ordre réel."""
from __future__ import annotations

import os
import sys

try:
    from .config import load_config, validate_config
    from .strategy import (
        decide_buy_hold_with_config, decide_sma_with_config, decide_with_config,
    )
except ImportError:
    from config import load_config, validate_config
    from strategy import (
        decide_buy_hold_with_config, decide_sma_with_config, decide_with_config,
    )

BASE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(BASE)
CONFIG_PATH = os.path.join(ROOT, "config", "config.json")


def iterate(config):
    validate_config(config)
    try:
        from price import get_price
    except ImportError:
        from .price import get_price
    symbol = str(config.get("symbol", "XRPEUR")).upper()
    current = float(get_price(symbol))
    # Historique minimal pour le signal; ce mode ne modifie aucun registre.
    history = [current]
    mode = str(config.get("strategy_mode", "sma_rsi")).lower()
    try:
        if mode == "sma_only":
            result = decide_sma_with_config(history, config.get("strategy", {}))
        elif mode == "buy_hold":
            result = decide_buy_hold_with_config(history, config.get("strategy", {}))
        else:
            result = decide_with_config(history, config.get("strategy", {}))
        signal = result["signal"]
        extra = (
            f" | SMA{config.get('strategy', {}).get('fast', 7)}="
            f"{result['sma_fast']:.8f} SMA{config.get('strategy', {}).get('slow', 25)}="
            f"{result['sma_slow']:.8f} RSI={result['rsi']:.2f}"
        )
    except ValueError:
        signal, extra = "HOLD", " | historique insuffisant (warmup)"
    print(
        f"paper=1 symbol={symbol} prix={current:.8f} "
        f"devise_comptabilisation={config.get('quote_currency', 'EUR')} signal={signal}{extra}"
    )
    return signal


def main():
    if "--once" not in sys.argv:
        print("usage: run.py --once (lecture publique, paper-only, aucun ordre réel)")
        return 2
    try:
        iterate(load_config(CONFIG_PATH))
    except Exception as exc:
        print(f"erreur: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
