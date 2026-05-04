from datetime import date, timedelta

import pytest

from packages.data.features import (
    average_true_range,
    compute_feature_rows,
    daily_returns,
    exponential_moving_average,
    relative_strength,
    rolling_high,
    simple_moving_average,
    volume_ratio,
)
from packages.data.models import AdjustedDailyBar


def _bars(symbol: str, count: int, start_close: float = 100.0) -> tuple[AdjustedDailyBar, ...]:
    start = date(2024, 1, 1)
    bars: list[AdjustedDailyBar] = []
    for index in range(count):
        close = start_close + index
        bars.append(
            AdjustedDailyBar(
                symbol=symbol,
                date=start + timedelta(days=index),
                open=close,
                high=close + 1.0,
                low=close - 1.0,
                close=close,
                volume=1_000_000 + index,
            )
        )
    return tuple(bars)


def test_basic_rolling_calculations() -> None:
    returns = daily_returns([100.0, 110.0, 99.0])

    assert returns[0] is None
    assert returns[1] == pytest.approx(0.1)
    assert returns[2] == pytest.approx(-0.1)
    assert simple_moving_average([1.0, 2.0, 3.0], 2) == [None, 1.5, 2.5]
    assert rolling_high([1.0, 3.0, 2.0, 5.0], 3) == [None, None, 3.0, 5.0]
    assert volume_ratio([10, 20, 30], [None, 10.0, 15.0]) == [None, 2.0, 2.0]


def test_exponential_moving_average_starts_from_sma_seed() -> None:
    values = [10.0, 11.0, 12.0, 13.0]

    ema = exponential_moving_average(values, 3)

    assert ema[0] is None
    assert ema[1] is None
    assert ema[2] == pytest.approx(11.0)
    assert ema[3] == pytest.approx(12.0)


def test_average_true_range_uses_wilder_smoothing() -> None:
    bars = _bars("SPY", 15)

    atr = average_true_range(bars, 14)

    assert atr[12] is None
    assert atr[13] == pytest.approx(2.0)
    assert atr[14] == pytest.approx(2.0)


def test_relative_strength_calculates_symbol_minus_benchmark_return() -> None:
    symbol = [100.0, 110.0, 121.0]
    benchmark = [100.0, 105.0, 110.0]

    rs = relative_strength(symbol, benchmark, lookback=2)

    assert rs == [None, None, pytest.approx(0.21 - 0.10)]


def test_compute_feature_rows_includes_expected_daily_features() -> None:
    bars = _bars("SPY", 70)
    benchmark = _bars("QQQ", 70, start_close=100.0)

    rows = compute_feature_rows(bars, benchmark_bars=benchmark)
    latest = rows[-1]

    assert len(rows) == 70
    assert latest.sma_50 is not None
    assert latest.ema_10 is not None
    assert latest.atr_14 == pytest.approx(2.0)
    assert latest.atr_percent == pytest.approx(2.0 / latest.close)
    assert latest.volume_sma_20 is not None
    assert latest.volume_ratio_20 is not None
    assert latest.high_20 == pytest.approx(bars[-1].high)
    assert latest.high_55 == pytest.approx(bars[-1].high)
    assert latest.dollar_volume == pytest.approx(bars[-1].close * bars[-1].volume)
    assert latest.rs_63 == pytest.approx(0.0)
