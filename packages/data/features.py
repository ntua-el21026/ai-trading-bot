"""Deterministic daily/swing feature calculations."""

from __future__ import annotations

from collections.abc import Sequence

from packages.data.models import AdjustedDailyBar, FeatureRow


def daily_returns(closes: Sequence[float]) -> list[float | None]:
    values = _as_float_list(closes)
    returns: list[float | None] = [None]
    for index in range(1, len(values)):
        previous = values[index - 1]
        returns.append((values[index] / previous) - 1.0)
    return returns


def simple_moving_average(values: Sequence[float], window: int) -> list[float | None]:
    _validate_window(window)
    series = _as_float_list(values)
    output: list[float | None] = []
    running_sum = 0.0
    for index, value in enumerate(series):
        running_sum += value
        if index >= window:
            running_sum -= series[index - window]
        output.append(running_sum / window if index >= window - 1 else None)
    return output


def exponential_moving_average(values: Sequence[float], window: int) -> list[float | None]:
    _validate_window(window)
    series = _as_float_list(values)
    output: list[float | None] = [None] * len(series)
    if len(series) < window:
        return output

    alpha = 2.0 / (window + 1.0)
    ema = sum(series[:window]) / window
    output[window - 1] = ema
    for index in range(window, len(series)):
        ema = (series[index] * alpha) + (ema * (1.0 - alpha))
        output[index] = ema
    return output


def rolling_high(values: Sequence[float], window: int) -> list[float | None]:
    _validate_window(window)
    series = _as_float_list(values)
    return [
        max(series[index - window + 1 : index + 1]) if index >= window - 1 else None
        for index in range(len(series))
    ]


def rolling_dollar_volume(bars: Sequence[AdjustedDailyBar]) -> list[float]:
    return [bar.close * float(bar.volume) for bar in bars]


def true_ranges(bars: Sequence[AdjustedDailyBar]) -> list[float]:
    ranges: list[float] = []
    previous_close: float | None = None
    for bar in bars:
        if previous_close is None:
            true_range = bar.high - bar.low
        else:
            true_range = max(
                bar.high - bar.low,
                abs(bar.high - previous_close),
                abs(bar.low - previous_close),
            )
        ranges.append(true_range)
        previous_close = bar.close
    return ranges


def average_true_range(
    bars: Sequence[AdjustedDailyBar],
    window: int = 14,
) -> list[float | None]:
    _validate_window(window)
    ranges = true_ranges(bars)
    output: list[float | None] = [None] * len(ranges)
    if len(ranges) < window:
        return output

    atr = sum(ranges[:window]) / window
    output[window - 1] = atr
    for index in range(window, len(ranges)):
        atr = ((atr * (window - 1)) + ranges[index]) / window
        output[index] = atr
    return output


def atr_percent(
    atr_values: Sequence[float | None],
    closes: Sequence[float],
) -> list[float | None]:
    close_values = _as_float_list(closes)
    if len(atr_values) != len(close_values):
        raise ValueError("ATR and close series lengths must match")
    return [
        None if atr is None else atr / close_values[index]
        for index, atr in enumerate(atr_values)
    ]


def volume_ratio(
    volumes: Sequence[int],
    volume_average: Sequence[float | None],
) -> list[float | None]:
    if len(volumes) != len(volume_average):
        raise ValueError("volume and average series lengths must match")
    ratios: list[float | None] = []
    for index, average in enumerate(volume_average):
        if average is None or average == 0:
            ratios.append(None)
        else:
            ratios.append(float(volumes[index]) / average)
    return ratios


def relative_strength(
    closes: Sequence[float],
    benchmark_closes: Sequence[float],
    lookback: int = 63,
) -> list[float | None]:
    _validate_window(lookback)
    close_values = _as_float_list(closes)
    benchmark_values = _as_float_list(benchmark_closes)
    if len(close_values) != len(benchmark_values):
        raise ValueError("symbol and benchmark close series lengths must match")

    output: list[float | None] = []
    for index, close in enumerate(close_values):
        if index < lookback:
            output.append(None)
            continue
        symbol_return = (close / close_values[index - lookback]) - 1.0
        benchmark_return = (benchmark_values[index] / benchmark_values[index - lookback]) - 1.0
        output.append(symbol_return - benchmark_return)
    return output


def compute_feature_rows(
    bars: Sequence[AdjustedDailyBar],
    *,
    benchmark_bars: Sequence[AdjustedDailyBar] | None = None,
    atr_window: int = 14,
) -> tuple[FeatureRow, ...]:
    if not bars:
        return ()

    sorted_bars = tuple(sorted(bars, key=lambda bar: bar.date))
    symbol = sorted_bars[0].symbol
    if any(bar.symbol != symbol for bar in sorted_bars):
        raise ValueError("feature rows must be computed for one symbol at a time")

    closes = [bar.close for bar in sorted_bars]
    highs = [bar.high for bar in sorted_bars]
    volumes = [bar.volume for bar in sorted_bars]
    returns = daily_returns(closes)
    sma_50 = simple_moving_average(closes, 50)
    sma_200 = simple_moving_average(closes, 200)
    ema_10 = exponential_moving_average(closes, 10)
    atr_14 = average_true_range(sorted_bars, atr_window)
    atr_pct = atr_percent(atr_14, closes)
    volume_sma_20 = simple_moving_average([float(volume) for volume in volumes], 20)
    volume_ratio_20 = volume_ratio(volumes, volume_sma_20)
    high_20 = rolling_high(highs, 20)
    high_55 = rolling_high(highs, 55)
    dollar_volume = rolling_dollar_volume(sorted_bars)
    rs_63 = _aligned_relative_strength(sorted_bars, benchmark_bars)

    rows: list[FeatureRow] = []
    for index, bar in enumerate(sorted_bars):
        rows.append(
            FeatureRow(
                symbol=bar.symbol,
                date=bar.date,
                close=bar.close,
                return_1d=returns[index],
                sma_50=sma_50[index],
                sma_200=sma_200[index],
                ema_10=ema_10[index],
                atr_14=atr_14[index],
                atr_percent=atr_pct[index],
                volume_sma_20=volume_sma_20[index],
                volume_ratio_20=volume_ratio_20[index],
                high_20=high_20[index],
                high_55=high_55[index],
                dollar_volume=dollar_volume[index],
                rs_63=rs_63[index],
                source_bar_payload_hash=bar.payload_hash,
            )
        )
    return tuple(rows)


def _aligned_relative_strength(
    bars: Sequence[AdjustedDailyBar],
    benchmark_bars: Sequence[AdjustedDailyBar] | None,
) -> list[float | None]:
    if benchmark_bars is None:
        return [None] * len(bars)
    sorted_benchmark = tuple(sorted(benchmark_bars, key=lambda bar: bar.date))
    bar_dates = [bar.date for bar in bars]
    benchmark_dates = [bar.date for bar in sorted_benchmark]
    if bar_dates != benchmark_dates:
        raise ValueError("benchmark bars must align exactly by date")
    return relative_strength(
        [bar.close for bar in bars],
        [bar.close for bar in sorted_benchmark],
        63,
    )


def _validate_window(window: int) -> None:
    if window <= 0:
        raise ValueError("window must be positive")


def _as_float_list(values: Sequence[float | int]) -> list[float]:
    return [float(value) for value in values]

