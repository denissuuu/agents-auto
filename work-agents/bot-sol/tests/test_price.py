from price import get_price


def test_get_price_positive():
    p = get_price("SOLUSDT")
    assert isinstance(p, float) and p > 0, p
    print(f"OK prix={p:.2f}")
