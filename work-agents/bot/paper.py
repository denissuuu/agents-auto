"""Paper trading simule (aucun argent reel). Usage: paper.py --once."""
import datetime
import json
import os
import sys
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import price
from strategy import decide
from explain import explain

BASE = os.path.dirname(os.path.abspath(__file__))
PORTFOLIO = os.path.join(BASE, "paper_portfolio.json")
LOG = os.path.join(BASE, "paper.log")
TRADES = os.path.join(BASE, "trades.log")
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


def get_last_signal():
    if not os.path.exists(LOG):
        return None
    try:
        with open(LOG, encoding="utf-8") as f:
            lines = [ln.strip() for ln in f if ln.strip()]
        if not lines:
            return None
        last = lines[-1]
        for tok in last.split():
            if tok.startswith("signal="):
                return tok.split("=", 1)[1]
    except OSError:
        return None
    return None


def step():
    pf = load_portfolio()
    p = price.get_price("BTCUSDT")
    hist = get_context() + [p]
    try:
        dec = decide(hist)
        sig = dec["signal"]
        sma_fast, sma_slow, rsi_val = dec["sma_fast"], dec["sma_slow"], dec["rsi"]
    except ValueError:
        sig, sma_fast, sma_slow, rsi_val = "HOLD", 0.0, 0.0, 50.0
    prev = get_last_signal()
    executed = False
    if sig == "BUY" and pf["cash"] > 0:
        pf["btc"] = pf["cash"] * (1 - FEE) / p
        pf["cash"] = 0.0
        pf["trades"] += 1
        executed = True
    elif sig == "SELL" and pf["btc"] > 0:
        pf["cash"] = pf["btc"] * p * (1 - FEE)
        pf["btc"] = 0.0
        pf["trades"] += 1
        executed = True
    save_portfolio(pf)
    val = pf["cash"] + pf["btc"] * p
    line = f"{datetime.datetime.now().isoformat(timespec='seconds')} prix={p:.2f} signal={sig} SMA7={sma_fast:.2f} SMA25={sma_slow:.2f} RSI={rsi_val:.2f} cash={pf['cash']:.2f} btc={pf['btc']:.6f} valeur={val:.2f}\n"
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(line)
    print(line.strip())
    if executed or (prev is not None and sig != prev):
        txt = explain(sig, sma_fast, sma_slow, rsi_val, p, executed=executed)
        bloc = f"[{datetime.datetime.now().isoformat(timespec='seconds')}] signal={sig} prix={p:.2f} trade={'oui' if executed else 'non'}\n{txt}\n\n"
        with open(TRADES, "a", encoding="utf-8") as f:
            f.write(bloc)
        print(bloc.strip())


def main():
    if "--once" in sys.argv:
        step()
    else:
        print("usage: paper.py --once (simulation, aucun ordre reel)")


if __name__ == "__main__":
    main()
