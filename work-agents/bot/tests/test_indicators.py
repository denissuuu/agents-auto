from indicators import sma, rsi


def test_sma_basic():
    assert sma([1, 2, 3, 4], 2) == 3.5


def test_rsi_rising_is_100():
    assert rsi([1, 1, 2, 2, 3, 3], n=2) == 100.0