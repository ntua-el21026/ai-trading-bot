"""Deterministic exit helper calculations.

These helpers only calculate exit conditions and stop levels. They do not submit, modify, or cancel
orders.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import cast

from packages.strategy.models import ExitEvaluation


def initial_stop_price(
    *,
    entry_price: float,
    atr_14: float,
    multiplier: float = 2.0,
) -> float:
    _validate_positive(entry_price, "entry_price")
    _validate_non_negative(atr_14, "atr_14")
    _validate_positive(multiplier, "multiplier")
    return entry_price - (multiplier * atr_14)


def research_initial_stop_price(*, entry_price: float, atr_14: float) -> float:
    return initial_stop_price(entry_price=entry_price, atr_14=atr_14, multiplier=2.5)


def trailing_stop_price(
    *,
    old_stop: float,
    highest_close_since_entry: float,
    atr_14: float,
    multiplier: float = 2.5,
) -> float:
    _validate_positive(old_stop, "old_stop")
    _validate_positive(highest_close_since_entry, "highest_close_since_entry")
    _validate_non_negative(atr_14, "atr_14")
    _validate_positive(multiplier, "multiplier")
    return max(old_stop, highest_close_since_entry - (multiplier * atr_14))


def research_trailing_stop_price(
    *,
    old_stop: float,
    highest_close_since_entry: float,
    atr_14: float,
) -> float:
    return trailing_stop_price(
        old_stop=old_stop,
        highest_close_since_entry=highest_close_since_entry,
        atr_14=atr_14,
        multiplier=3.0,
    )


def technical_exit_triggered(
    closes: Sequence[float],
    ema_10_values: Sequence[float | None],
    *,
    confirm_closes: int = 2,
) -> bool:
    if confirm_closes <= 0:
        raise ValueError("confirm_closes must be positive")
    if len(closes) != len(ema_10_values):
        raise ValueError("closes and EMA values must have matching lengths")
    if len(closes) < confirm_closes:
        return False

    recent_closes = closes[-confirm_closes:]
    recent_emas = ema_10_values[-confirm_closes:]
    if any(ema is None for ema in recent_emas):
        return False
    confirmed_emas = cast(Sequence[float], recent_emas)
    return all(close < ema for close, ema in zip(recent_closes, confirmed_emas, strict=True))


def time_stop_triggered(
    *,
    bars_held: int,
    unrealized_r_multiple: float,
    time_stop_days: int = 20,
    min_r_multiple: float = 0.5,
) -> bool:
    if bars_held < 0:
        raise ValueError("bars_held cannot be negative")
    if time_stop_days <= 0:
        raise ValueError("time_stop_days must be positive")
    return bars_held >= time_stop_days and unrealized_r_multiple < min_r_multiple


def fail_fast_exit_triggered(
    *,
    bars_since_entry: int,
    latest_close: float,
    breakout_level: float,
    fail_fast_days: int = 5,
) -> bool:
    if bars_since_entry < 0:
        raise ValueError("bars_since_entry cannot be negative")
    _validate_positive(latest_close, "latest_close")
    _validate_positive(breakout_level, "breakout_level")
    if fail_fast_days <= 0:
        raise ValueError("fail_fast_days must be positive")
    return bars_since_entry <= fail_fast_days and latest_close < breakout_level


def evaluate_exit_conditions(
    *,
    closes: Sequence[float],
    ema_10_values: Sequence[float | None],
    bars_held: int,
    unrealized_r_multiple: float,
    bars_since_entry: int,
    breakout_level: float,
    technical_confirm_closes: int = 2,
    time_stop_days: int = 20,
    fail_fast_days: int = 5,
) -> ExitEvaluation:
    latest_close = closes[-1] if closes else 0.0
    reasons: list[str] = []
    if technical_exit_triggered(
        closes,
        ema_10_values,
        confirm_closes=technical_confirm_closes,
    ):
        reasons.append("technical_exit")
    if time_stop_triggered(
        bars_held=bars_held,
        unrealized_r_multiple=unrealized_r_multiple,
        time_stop_days=time_stop_days,
    ):
        reasons.append("time_stop")
    if fail_fast_exit_triggered(
        bars_since_entry=bars_since_entry,
        latest_close=latest_close,
        breakout_level=breakout_level,
        fail_fast_days=fail_fast_days,
    ):
        reasons.append("fail_fast_exit")
    return ExitEvaluation(should_exit=bool(reasons), reason_codes=tuple(reasons))


def _validate_positive(value: float, name: str) -> None:
    if value <= 0:
        raise ValueError(f"{name} must be positive")


def _validate_non_negative(value: float, name: str) -> None:
    if value < 0:
        raise ValueError(f"{name} cannot be negative")
