import json

from price import get_price


class _FakeResponse:
    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self):
        return json.dumps({"price": "1.2345"}).encode("utf-8")


def test_get_price_positive_without_network(monkeypatch):
    monkeypatch.setattr(
        "price.urllib.request.urlopen", lambda *_args, **_kwargs: _FakeResponse()
    )
    value = get_price("BTCEUR")
    assert isinstance(value, float) and value > 0, value
