"""Paper trading simule (aucun argent reel). Usage: paper.py --once."""
import datetime
import json
import os
import sys
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import price
from strategy import decide

BASE = os.path.dirname(os.path.abspath(__file__))
PORTFOLIO = os.path.join(BASE, "paper_portfolio.json")
LOG = os.path.join(BASE, "paper.log")
KLINES_URL = "https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=1h&limit=30"
FEE = 0.001


def load_portfolio():
    if os.path.exists(PORTFOLIO):
        with open(PORTFOLIO, encoding="utf-8") as f:
            return json.load(f)
    return {"cash": 1000.0, "btc": 0.0, "trades": 0}


def save_portfolio(pf):
    with open(PORTFOLIO, "w", encoding="utf-8") as f:
        json.dump(pf, f, indent=2)


def get_context():
    with urllib.request.urlopen(KLINES_URL, timeout=15) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return [float(k[4]) for k in data]


def step():
    pf = load_portfolio()
    p = price.get_price("BTCUSDT")
    hist = get_context() + [p]
    try:
        sig = decide(hist)["signal"]
    except ValueError:
        sig = "HOLD"
    if sig == "BUY" and pf["cash"] > 0:
        pf["btc"] = pf["cash"] * (1 - FEE) / p
        pf["cash"] = 0.0
        pf["trades"] += 1
    elif sig == "SELL" and pf["btc"] > 0:
        pf["cash"] = pf["btc"] * p * (1 - FEE)
        pf["btc"] = 0.0
        pf["trades"] += 1
    save_portfolio(pf)
    val = pf["cash"] + pf["btc"] * p
    line = f"{datetime.datetime.now().isoformat(timespec='seconds')} prix={p:.2f} signal={sig} cash={pf['cash']:.2f} btc={pf['btc']:.6f} valeur={val:.2f}\n"
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(line)
    print(line.strip())


def main():
    if "--once" in sys.argv:
        step()
    else:
        print("usage: paper.py --once (simulation, aucun ordre reel)")


if __name__ == "__main__":
    main()
