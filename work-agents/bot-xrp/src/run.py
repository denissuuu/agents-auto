"""Point d'entrée: lit config, fetch prix, décide, affiche. --once = 1 itération."""
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import price

try:
    from strategy import decide
except ImportError:
    from .strategy import decide

BASE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(BASE)
CONFIG_PATH = os.path.join(ROOT, "config", "config.json")
_history = []


def load_config():
    with open(CONFIG_PATH, encoding="utf-8") as f:
        return json.load(f)


def iterate(cfg):
    symbol = cfg.get("symbol", "XRPUSDT")
    p = price.get_price(symbol)
    _history.append(p)
    try:
        res = decide(list(_history))
        sig = res["signal"]
        extra = f" | SMA7={res['sma_fast']:.2f} SMA25={res['sma_slow']:.2f} RSI={res['rsi']:.2f}"
    except ValueError:
        sig = "HOLD"
        extra = " | historique insuffisant (warmup)"
    print(f"prix={p:.2f} {symbol} signal={sig}{extra}")
    return sig


def main():
    once = "--once" in sys.argv
    cfg = load_config()
    if once:
        iterate(cfg)
        return
    poll = int(cfg.get("poll_interval_sec", 60))
    while True:
        try:
            iterate(cfg)
        except Exception as e:
            print(f"erreur: {e}", file=sys.stderr)
        time.sleep(poll)


if __name__ == "__main__":
    main()
