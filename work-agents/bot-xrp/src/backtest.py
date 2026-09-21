"""Backtest strategie SMA7/25+RSI sur klines Binance (stdlib uniquement)."""
import json
import os
import sys
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from strategy import decide

KLINES_URL = "https://api.binance.com/api/v3/klines?symbol=XRPUSDT&interval=1h&limit=100"
START_CASH = 1000.0
FEE = 0.001


def fetch_closes():
    with urllib.request.urlopen(KLINES_URL, timeout=15) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return [float(k[4]) for k in data]


def main():
    closes = fetch_closes()
    cash, xrp = START_CASH, 0.0
    buy_price, trades, wins = 0.0, 0, 0
    for i in range(25, len(closes) + 1):
        try:
            sig = decide(closes[:i])["signal"]
        except ValueError:
            continue
        p = closes[i - 1]
        if sig == "BUY" and cash > 0:
            xrp = cash * (1 - FEE) / p
            cash = 0.0
            buy_price = p
            trades += 1
        elif sig == "SELL" and xrp > 0:
            cash = xrp * p * (1 - FEE)
            xrp = 0.0
            trades += 1
            if p > buy_price:
                wins += 1
    end_val = cash + xrp * closes[-1]
    ret = (end_val - START_CASH) / START_CASH * 100
    bh = (closes[-1] - closes[0]) / closes[0] * 100
    print({"trades": trades, "win": wins, "return%": round(ret, 2), "buy&hold%": round(bh, 2)})


if __name__ == "__main__":
    main()
