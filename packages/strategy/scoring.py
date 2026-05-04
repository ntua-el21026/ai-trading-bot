"""Deterministic strategy scoring helpers."""

from __future__ import annotations


def technical_score(
    *,
    trend_passed: bool,
    breakout_passed: bool,
    volume_passed: bool,
    volatility_passed: bool,
) -> float:
    """Compute the spec-weighted technical score from pass/fail components."""

    return (
        0.35 * _binary_score(trend_passed)
        + 0.35 * _binary_score(breakout_passed)
        + 0.15 * _binary_score(volume_passed)
        + 0.15 * _binary_score(volatility_passed)
    )


def relative_strength_score(rs_63: float | None, percentile: float | None = None) -> float:
    """Map RS63 or an available percentile hook to a bounded 0-100 score."""

    if percentile is not None:
        return _clip(percentile, 0.0, 100.0)
    if rs_63 is None:
        return 0.0
    return _clip(50.0 + (rs_63 * 100.0), 0.0, 100.0)


def _binary_score(value: bool) -> float:
    return 100.0 if value else 0.0


def _clip(value: float, lower: float, upper: float) -> float:
    return max(lower, min(upper, value))

