"""Fetch XRP/EUR price from Binance public API (stdlib only).

Aucune clé, aucun endpoint d'ordres : simple lecture du ticker public.
"""
import json
import urllib.parse
import urllib.request

API_URL = "https://api.binance.com/api/v3/ticker/price"


def get_price(symbol="XRPEUR"):
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
    symbol = "XRPEUR"
    price = get_price(symbol)
    base, quote = symbol[:-3], symbol[-3:]
    print(f"{base}/{quote}: {price:.4f} {quote}")


if __name__ == "__main__":
    main()