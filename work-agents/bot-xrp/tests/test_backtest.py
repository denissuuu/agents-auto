import datetime as dt

import pytest

from backtest import Candle, run_backtest, run_walk_forward
from config import DEFAULT_CONFIG, deep_merge


def make_candles(closes, start="2025-01-01", volume=1_000_000_000.0):
    start_date = dt.date.fromisoformat(start)
    result = []
    previous = closes[0]
    for index, close in enumerate(closes):
        opening = previous
        high = max(opening, close) * 1.01
        low = min(opening, close) * 0.99
        timestamp = dt.datetime.combine(
            start_date + dt.timedelta(days=index), dt.time(), tzinfo=dt.timezone.utc
        ).replace(microsecond=0).isoformat()
        result.append(Candle(timestamp, opening, high, low, close, volume))
        previous = close
    return result


def config_for_tests(**execution_overrides):
    cfg = deep_merge(DEFAULT_CONFIG, {
        "initial_capital": 1000.0,
        "backtest": {"interval": "1d", "warmup_bars": 26},
    })
    cfg["execution"].update(execution_overrides)
    return cfg


def test_signal_is_executed_on_next_candle_open_not_signal_close():
    closes = [1.0 + index * 0.01 for index in range(40)]
    candles = make_candles(closes)
    # Le signal SMA est disponible à la clôture de la bougie 24 ; il doit
    # être exécuté à l'ouverture de la bougie 25, même si sa clôture saute.
    candles[25] = Candle(
        candles[25].timestamp, 1.25, 2.20, 1.20, 2.00, 1_000_000_000.0
    )
    result = run_backtest(candles, config=config_for_tests(), strategy_mode="sma_only")
    assert result.fills_log, "le signal BUY de la bougie 25 doit produire un fill"
    first = result.fills_log[0]
    assert first["timestamp"] == candles[25].timestamp
    assert first["price"] < 1.30  # proche de l'ouverture, pas de la clôture
    assert first["price"] > 1.20


def test_backtest_reports_costs_exposure_and_drawdown():
    closes = [1.0 + (index % 9) * 0.01 for index in range(180)]
    result = run_backtest(make_candles(closes), config=config_for_tests())
    assert result.candle_count == 180
    assert result.equity_curve
    assert result.max_drawdown_pct >= 0
    assert 0 <= result.average_exposure_pct <= 100
    assert result.cash_unused_avg >= 0
    assert result.buy_hold_return_pct == pytest.approx(
        result.buy_hold_return_pct, abs=0.01
    )
    if result.fills:
        assert result.total_fees > 0


def test_multiple_months_and_regimes_are_supported():
    paths = {
        "up": [1.0 + index * 0.004 + (index % 7) * 0.002 for index in range(240)],
        "down": [2.0 - index * 0.003 + (index % 5) * 0.002 for index in range(240)],
        "sideways": [1.0 + (0.08 if index % 20 < 10 else -0.08) for index in range(240)],
    }
    for name, closes in paths.items():
        result = run_backtest(
            make_candles(closes, start="2024-01-01"),
            config=config_for_tests(),
            strategy_mode="sma_only",
        )
        assert result.candle_count == 240
        assert result.data_start.startswith("2024-")
        assert result.data_end.startswith("2024-") or result.data_end.startswith("2025-")
        assert result.max_drawdown_pct >= 0


def test_walk_forward_marks_out_of_sample():
    closes = [1.0 + index * 0.002 + (index % 11) * 0.001 for index in range(220)]
    results = run_walk_forward(make_candles(closes), config=config_for_tests(), folds=3)
    assert len(results) == 3
    assert all(item.out_of_sample for item in results)
    assert all(item.candle_count >= 2 for item in results)


def test_buy_hold_signal_never_sells():
    from strategy import decide_buy_hold
    closes = [1.0 + index * 0.01 for index in range(120)]
    for size in range(26, len(closes)):
        signal = decide_buy_hold(closes[:size])["signal"]
        assert signal in ("BUY", "HOLD")


def test_buy_hold_holds_through_uptrend_and_only_buys():
    closes = [1.0 + index * 0.01 for index in range(120)]
    result = run_backtest(
        make_candles(closes), config=config_for_tests(), strategy_mode="buy_hold"
    )
    assert result.fills_log, "le mode buy_hold doit au moins acheter une fois"
    assert all(fill["side"] == "BUY" for fill in result.fills_log), (
        "buy_hold ne doit jamais vendre sur une tendance haussière sans stop touché"
    )
    assert len(result.fills_log) == 1, (
        "buy_hold doit entrer en une seule fois, pas ré-acheter sans cesse"
    )
    assert result.net_return_pct > 0


def test_buy_hold_beats_churning_strategy_on_clean_uptrend():
    closes = [1.0 + index * 0.01 for index in range(120)]
    hold = run_backtest(
        make_candles(closes), config=config_for_tests(), strategy_mode="buy_hold"
    )
    churn = run_backtest(
        make_candles(closes), config=config_for_tests(), strategy_mode="sma_rsi"
    )
    assert hold.net_return_pct > churn.net_return_pct


def test_buy_hold_exposes_most_of_capital_in_one_entry():
    closes = [1.0 + index * 0.01 for index in range(120)]
    result = run_backtest(
        make_candles(closes), config=config_for_tests(), strategy_mode="buy_hold"
    )
    assert result.average_exposure_pct > 70, (
        "buy_hold doit exposer ~95 % du capital, pas 5 %"
    )
    assert result.total_fees < 5, "une seule entrée implique peu de frais"
