"""Deterministic rule-based market regime classification."""

from __future__ import annotations

from collections.abc import Sequence
from math import log, sqrt
from statistics import pstdev

from packages.core.config import RegimeConfig
from packages.strategy.models import RegimeClassification, RegimeObservation, RegimeState


def realized_volatility_20(
    closes: Sequence[float],
    *,
    window: int = 20,
    annualization_days: int = 252,
) -> list[float | None]:
    """Compute annualized realized volatility from log returns."""

    if window <= 0:
        raise ValueError("window must be positive")
    if annualization_days <= 0:
        raise ValueError("annualization_days must be positive")

    close_values = [float(close) for close in closes]
    if any(close <= 0 for close in close_values):
        raise ValueError("closes must be positive")

    log_returns = [
        log(close_values[index] / close_values[index - 1])
        for index in range(1, len(close_values))
    ]
    output: list[float | None] = []
    for index in range(len(close_values)):
        if index < window:
            output.append(None)
            continue
        window_returns = log_returns[index - window : index]
        output.append(pstdev(window_returns) * sqrt(float(annualization_days)))
    return output


def classify_regime(
    observations: Sequence[RegimeObservation],
    config: RegimeConfig,
    *,
    previous_state: RegimeState | None = None,
    cooldown_days_remaining: int = 0,
) -> RegimeClassification:
    """Classify the latest proxy observation into RISK_ON, CAUTION, or RISK_OFF."""

    if not observations:
        raise ValueError("at least one regime observation is required")
    sorted_observations = tuple(sorted(observations, key=lambda observation: observation.date))
    latest = sorted_observations[-1]
    if latest.symbol != config.proxy:
        raise ValueError(f"latest regime observation must use proxy {config.proxy}")
    if any(observation.symbol != config.proxy for observation in sorted_observations):
        raise ValueError(f"all regime observations must use proxy {config.proxy}")

    reason_codes: list[str] = []
    missing = _missing_latest_inputs(latest)
    if missing:
        return RegimeClassification(
            state="CAUTION",
            as_of=latest.date,
            proxy=config.proxy,
            new_entries_allowed=False,
            size_multiplier=0.0,
            risk_on_confirmed=False,
            risk_off_confirmed=False,
            cooldown_days_remaining=0,
            reason_codes=tuple(missing),
        )

    risk_on_confirmed = _close_condition_confirmed(
        sorted_observations,
        periods=config.risk_on_confirm_closes,
        multiplier=config.risk_on_above_sma200_multiplier,
        comparison="above",
    )
    risk_off_price_confirmed = _close_condition_confirmed(
        sorted_observations,
        periods=config.risk_off_confirm_closes,
        multiplier=config.risk_off_below_sma200_multiplier,
        comparison="below",
    )
    latest_rv20 = latest.rv20
    if latest_rv20 is None or latest.sma_fast is None or latest.sma_slow is None:
        raise ValueError("missing latest inputs should have been handled before classification")

    risk_on_confirmed = (
        risk_on_confirmed
        and latest_rv20 < config.rv20_risk_on_max
        and latest.sma_fast > latest.sma_slow
    )
    risk_off_confirmed = risk_off_price_confirmed or latest_rv20 > config.rv20_risk_off_min

    if risk_off_confirmed:
        return RegimeClassification(
            state="RISK_OFF",
            as_of=latest.date,
            proxy=config.proxy,
            new_entries_allowed=False,
            size_multiplier=0.0,
            risk_on_confirmed=False,
            risk_off_confirmed=True,
            cooldown_days_remaining=config.risk_off_cooldown_days,
            reason_codes=("risk_off_confirmed",),
        )

    if (
        previous_state == "RISK_OFF"
        and cooldown_days_remaining > 0
        and risk_on_confirmed
    ):
        return RegimeClassification(
            state="CAUTION",
            as_of=latest.date,
            proxy=config.proxy,
            new_entries_allowed=False,
            size_multiplier=0.0,
            risk_on_confirmed=True,
            risk_off_confirmed=False,
            cooldown_days_remaining=cooldown_days_remaining,
            reason_codes=("risk_off_cooldown_active",),
        )

    if risk_on_confirmed:
        return RegimeClassification(
            state="RISK_ON",
            as_of=latest.date,
            proxy=config.proxy,
            new_entries_allowed=True,
            size_multiplier=1.0,
            risk_on_confirmed=True,
            risk_off_confirmed=False,
            cooldown_days_remaining=0,
            reason_codes=("risk_on_confirmed",),
        )

    reason_codes.append("neither_risk_on_nor_risk_off")
    return RegimeClassification(
        state="CAUTION",
        as_of=latest.date,
        proxy=config.proxy,
        new_entries_allowed=True,
        size_multiplier=0.5,
        risk_on_confirmed=False,
        risk_off_confirmed=False,
        cooldown_days_remaining=0,
        reason_codes=tuple(reason_codes),
    )


def _missing_latest_inputs(observation: RegimeObservation) -> tuple[str, ...]:
    missing: list[str] = []
    if observation.sma_fast is None:
        missing.append("missing_sma_fast")
    if observation.sma_slow is None:
        missing.append("missing_sma_slow")
    if observation.rv20 is None:
        missing.append("missing_rv20")
    return tuple(missing)


def _close_condition_confirmed(
    observations: Sequence[RegimeObservation],
    *,
    periods: int,
    multiplier: float,
    comparison: str,
) -> bool:
    if periods <= 0:
        raise ValueError("periods must be positive")
    if len(observations) < periods:
        return False

    recent = observations[-periods:]
    for observation in recent:
        if observation.sma_slow is None:
            return False
        threshold = multiplier * observation.sma_slow
        if comparison == "above" and observation.close <= threshold:
            return False
        if comparison == "below" and observation.close >= threshold:
            return False
    return True

