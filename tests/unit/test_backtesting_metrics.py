from datetime import date, timedelta

import pytest

from packages.backtesting.engine import run_backtest
from packages.backtesting.metrics import max_drawdown, profit_factor, total_return
from packages.backtesting.models import BacktestInput, BacktestSignal, EquityPoint
from packages.data.models import AdjustedDailyBar


def _bars(symbol: str, closes: tuple[float, ...]) -> tuple[AdjustedDailyBar, ...]:
    start = date(2024, 1, 1)
    bars: list[AdjustedDailyBar] = []
    for index, close in enumerate(closes):
        bars.append(
            AdjustedDailyBar(
                symbol=symbol,
                date=start + timedelta(days=index),
                open=close,
                high=close + 1.0,
                low=close - 1.0,
                close=close,
                volume=1_000_000,
            )
        )
    return tuple(bars)


def test_metric_helpers_compute_return_and_drawdown() -> None:
    curve = (
        EquityPoint(date=date(2024, 1, 1), equity=100.0, cash=100.0, gross_exposure=0.0),
        EquityPoint(date=date(2024, 1, 2), equity=120.0, cash=120.0, gross_exposure=0.0),
        EquityPoint(date=date(2024, 1, 3), equity=90.0, cash=90.0, gross_exposure=0.0),
    )

    assert total_return(curve) == pytest.approx(-0.10)
    assert max_drawdown(curve) == pytest.approx(-0.25)


def test_backtest_engine_uses_explicit_signals_without_broker_logic() -> None:
    bars = _bars("SPY", (100.0, 105.0, 110.0))
    request = BacktestInput(
        name="fixture",
        initial_cash=10_000.0,
        bars_by_symbol={"SPY": bars},
        signals=(
            BacktestSignal(symbol="SPY", date=bars[0].date, action="buy", quantity=10),
            BacktestSignal(symbol="SPY", date=bars[2].date, action="sell", quantity=10),
        ),
    )

    result = run_backtest(request)

    assert len(result.trades) == 1
    assert result.trades[0].pnl == pytest.approx(100.0)
    assert result.metrics.trade_count == 1
    assert result.metrics.win_rate == pytest.approx(1.0)
    assert result.validation_note.endswith("not proof of profitability.")


def test_profit_factor_returns_none_when_there_are_no_losses() -> None:
    bars = _bars("SPY", (100.0, 105.0, 110.0))
    result = run_backtest(
        BacktestInput(
            name="fixture",
            initial_cash=10_000.0,
            bars_by_symbol={"SPY": bars},
            signals=(
                BacktestSignal(symbol="SPY", date=bars[0].date, action="buy", quantity=10),
                BacktestSignal(symbol="SPY", date=bars[2].date, action="sell", quantity=10),
            ),
        )
    )

    assert profit_factor(result.trades) is None

