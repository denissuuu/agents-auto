"""Fetch XRP/USDT price from Binance public API (stdlib only)."""
import json
import urllib.parse
import urllib.request

API_URL = "https://api.binance.com/api/v3/ticker/price"


def get_price(symbol="XRPUSDT"):
    """Return current price as float for given symbol. Raises RuntimeError on failure."""
    url = f"{API_URL}?{urllib.parse.urlencode({'symbol': symbol})}"
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        raise RuntimeError(f"Erreur fetch prix {symbol}: {e}")
    try:
        price = float(data["price"])
    except (KeyError, TypeError, ValueError) as e:
        raise RuntimeError(f"Reponse inattendue: {data!r} ({e})")
    if price <= 0:
        raise RuntimeError(f"Prix invalide: {price}")
    return price


def main():
    price = get_price()
    print(f"XRP/USDT: {price:.2f}")


if __name__ == "__main__":
    main()
