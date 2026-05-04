import pytest

from packages.strategy.exits import (
    evaluate_exit_conditions,
    fail_fast_exit_triggered,
    initial_stop_price,
    research_initial_stop_price,
    research_trailing_stop_price,
    technical_exit_triggered,
    time_stop_triggered,
    trailing_stop_price,
)


def test_initial_and_trailing_stop_helpers_use_spec_multipliers() -> None:
    assert initial_stop_price(entry_price=100.0, atr_14=3.0) == pytest.approx(94.0)
    assert research_initial_stop_price(entry_price=100.0, atr_14=3.0) == pytest.approx(92.5)
    assert trailing_stop_price(
        old_stop=95.0,
        highest_close_since_entry=110.0,
        atr_14=4.0,
    ) == pytest.approx(100.0)
    assert research_trailing_stop_price(
        old_stop=95.0,
        highest_close_since_entry=110.0,
        atr_14=4.0,
    ) == pytest.approx(98.0)


def test_exit_triggers_are_deterministic_and_non_executing() -> None:
    assert technical_exit_triggered([100.0, 99.0], [100.5, 100.0]) is True
    assert time_stop_triggered(bars_held=20, unrealized_r_multiple=0.49) is True
    assert fail_fast_exit_triggered(
        bars_since_entry=5,
        latest_close=99.0,
        breakout_level=100.0,
    ) is True


def test_evaluate_exit_conditions_returns_reason_codes_only() -> None:
    evaluation = evaluate_exit_conditions(
        closes=[99.5, 99.0],
        ema_10_values=[100.0, 100.0],
        bars_held=20,
        unrealized_r_multiple=0.25,
        bars_since_entry=3,
        breakout_level=100.0,
    )

    assert evaluation.should_exit is True
    assert set(evaluation.reason_codes) == {"technical_exit", "time_stop", "fail_fast_exit"}
