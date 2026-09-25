import pytest

from portfolio import Portfolio, TradingError


def make_portfolio(**overrides):
    values = dict(
        initial_capital=1000.0,
        max_notional_per_trade=250.0,
        min_notional=1.0,
        allocation_pct=0.20,
        max_position_pct=0.25,
        max_total_exposure_pct=0.50,
        min_cash_reserve=50.0,
        stop_loss_pct=0.10,
        max_daily_loss_pct=0.03,
        max_position_days=30,
        profit_levels=[0.05, 0.10, 0.20],
        profit_fractions=[0.25, 0.25, 0.20],
        trailing_stop_pct=0.08,
    )
    values.update(overrides)
    return Portfolio(**values)


def assert_solvent(portfolio):
    assert portfolio.cash >= -1e-9
    assert portfolio.btc >= -1e-9
    assert portfolio.reserved_cash + portfolio.fee_reserve_cash <= portfolio.cash + 1e-8


def test_repeated_buys_never_exceed_cash_or_position_cap():
    portfolio = make_portfolio(
        initial_capital=300.0,
        min_cash_reserve=10.0,
        max_notional_per_trade=200.0,
        max_position_pct=0.50,
        max_total_exposure_pct=0.50,
        allocation_pct=0.40,
    )
    for index in range(20):
        result = portfolio.buy(1.0 + index * 0.01, volume=1_000_000,
                               timestamp=f"2026-01-01T00:{index:02d}:00+00:00")
        assert_solvent(portfolio)
        if result.executed:
            assert portfolio.cash >= 10.0 - 1e-8
    assert portfolio.btc > 0
    assert portfolio.position_value(1.0) <= 300.0 * 0.50 + 1e-8


def test_insufficient_cash_rejection_does_not_mutate_state():
    portfolio = make_portfolio(
        initial_capital=100.0,
        min_cash_reserve=10.0,
        max_notional_per_trade=80.0,
        max_position_pct=1.0,
        max_total_exposure_pct=1.0,
        allocation_pct=0.80,
    )
    first = portfolio.buy(1.0, timestamp="2026-01-01T00:00:00+00:00")
    assert first.executed
    cash_before, btc_before = portfolio.cash, portfolio.btc
    rejected = portfolio.buy(1.0, quantity=1_000_000,
                             timestamp="2026-01-01T01:00:00+00:00")
    assert not rejected.executed
    assert portfolio.cash == cash_before
    assert portfolio.btc == btc_before
    assert_solvent(portfolio)


def test_reserved_order_cannot_be_double_spent():
    portfolio = make_portfolio(
        initial_capital=100.0,
        min_cash_reserve=10.0,
        max_notional_per_trade=80.0,
        min_notional=20.0,
        max_risk_per_position_pct=0.08,
        max_position_pct=1.0,
        max_total_exposure_pct=1.0,
        allocation_pct=0.80,
    )
    order = portfolio.reserve_buy(1.0, timestamp="2026-01-01T00:00:00+00:00")
    assert order is not None
    second = portfolio.reserve_buy(1.0)
    assert second is None
    fill = portfolio.fill_reserved_buy(order, 1.0)
    assert fill.executed
    assert_solvent(portfolio)


def test_partial_sell_releases_cash_and_keeps_remainder():
    portfolio = make_portfolio()
    buy = portfolio.buy(1.0, timestamp="2026-01-01T00:00:00+00:00")
    assert buy.executed
    cash_before = portfolio.cash
    btc_before = portfolio.btc
    sell = portfolio.sell(1.20, fraction=0.25,
                          timestamp="2026-01-02T00:00:00+00:00")
    assert sell.executed
    assert portfolio.cash > cash_before
    assert 0 < portfolio.btc < btc_before
    assert sell.quantity == pytest.approx(btc_before * 0.25)
    assert_solvent(portfolio)


def test_buy_and_exit_fees_are_recorded():
    portfolio = make_portfolio(fee_rate=0.001, spread=0.002, slippage=0.0)
    buy = portfolio.buy(1.0, quantity=10.0,
                        timestamp="2026-01-01T00:00:00+00:00")
    sell = portfolio.sell(1.1, quantity=10.0,
                          timestamp="2026-01-02T00:00:00+00:00")
    assert buy.fee > 0 and sell.fee > 0
    assert portfolio.total_fees == pytest.approx(buy.fee + sell.fee)
    assert sell.realized_pnl > 0
    assert_solvent(portfolio)


def test_stop_loss_produces_full_fractional_exit():
    portfolio = make_portfolio(stop_loss_pct=0.10)
    assert portfolio.buy(1.0, quantity=10.0,
                         timestamp="2026-01-01T00:00:00+00:00").executed
    instructions = portfolio.plan_exits(0.89, "2026-01-02T00:00:00+00:00")
    assert instructions and instructions[0].reason == "stop_loss"
    result = portfolio.sell(0.89, quantity=instructions[0].quantity,
                            timestamp="2026-01-02T00:00:00+00:00")
    assert result.executed
    assert portfolio.btc == pytest.approx(0.0, abs=1e-8)
    assert_solvent(portfolio)


def test_progressive_targets_and_trailing_are_fractional():
    portfolio = make_portfolio(stop_loss_pct=0.50, max_risk_per_position_pct=0.50)
    assert portfolio.buy(1.0, quantity=100.0,
                         timestamp="2026-01-01T00:00:00+00:00").executed
    first = portfolio.plan_exits(1.06, "2026-01-02T00:00:00+00:00")
    assert first and first[0].reason == "profit_level_1"
    portfolio.sell(1.06, quantity=first[0].quantity,
                   timestamp="2026-01-02T00:00:00+00:00", exit_level=first[0].level)
    second = portfolio.plan_exits(1.11, "2026-01-03T00:00:00+00:00")
    assert second and second[0].reason == "profit_level_2"
    portfolio.sell(1.11, quantity=second[0].quantity,
                   timestamp="2026-01-03T00:00:00+00:00", exit_level=second[0].level)
    third = portfolio.plan_exits(1.21, "2026-01-04T00:00:00+00:00")
    assert third and third[0].reason == "profit_level_3"
    portfolio.sell(1.21, quantity=third[0].quantity,
                   timestamp="2026-01-04T00:00:00+00:00", exit_level=third[0].level)
    assert portfolio.position_state.get("trailing_active") is True
    assert 0 < portfolio.btc < 100
    trailing = portfolio.plan_exits(1.05, "2026-01-05T00:00:00+00:00")
    assert trailing and trailing[0].reason == "trailing_stop"


def test_daily_loss_halts_new_entries_but_allows_exit():
    portfolio = make_portfolio(
        max_daily_loss_pct=0.03, stop_loss_pct=0.50,
        max_risk_per_position_pct=0.20,
    )
    portfolio.buy(1.0, quantity=200.0, timestamp="2026-01-01T00:00:00+00:00")
    portfolio.mark(1.0, "2026-01-01T09:00:00+00:00")
    portfolio.mark(0.80, "2026-01-01T10:00:00+00:00")
    assert portfolio.daily_halted
    blocked = portfolio.buy(0.80, timestamp="2026-01-01T10:01:00+00:00")
    assert not blocked.executed
    # La sortie de risque reste possible même si les nouveaux achats sont bloqués.
    assert portfolio.sell(0.80, fraction=1.0,
                          timestamp="2026-01-01T10:02:00+00:00").executed


def test_kill_switch_blocks_buy_and_requires_explicit_resume():
    portfolio = make_portfolio()
    portfolio.set_kill_switch(True)
    assert not portfolio.buy(1.0, quantity=1.0).executed
    portfolio.resume()
    assert portfolio.buy(1.0, quantity=1.0).executed


def test_serialization_preserves_ledger():
    portfolio = make_portfolio()
    portfolio.buy(1.0, quantity=10.0, timestamp="2026-01-01T00:00:00+00:00")
    portfolio.sell(1.05, quantity=2.0, timestamp="2026-01-02T00:00:00+00:00")
    restored = Portfolio.from_dict(portfolio.to_dict())
    assert restored.cash == pytest.approx(portfolio.cash)
    assert restored.btc == pytest.approx(portfolio.btc)
    assert restored.total_fees == pytest.approx(portfolio.total_fees)
    assert restored.realized_pnl == pytest.approx(portfolio.realized_pnl)
    assert_solvent(restored)
