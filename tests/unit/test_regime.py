from datetime import date, timedelta

import pytest

from packages.core.config import load_app_config
from packages.strategy.models import RegimeObservation
from packages.strategy.regime import classify_regime, realized_volatility_20


def _observation(
    index: int,
    *,
    close: float,
    sma_fast: float = 105.0,
    sma_slow: float = 100.0,
    rv20: float = 0.20,
) -> RegimeObservation:
    return RegimeObservation(
        symbol="SPY",
        date=date(2024, 1, 1) + timedelta(days=index),
        close=close,
        sma_fast=sma_fast,
        sma_slow=sma_slow,
        rv20=rv20,
    )


def test_classify_regime_risk_on_after_confirmed_closes() -> None:
    config = load_app_config().regime
    observations = tuple(_observation(index, close=103.0) for index in range(3))

    result = classify_regime(observations, config)

    assert result.state == "RISK_ON"
    assert result.new_entries_allowed is True
    assert result.size_multiplier == pytest.approx(1.0)
    assert "risk_on_confirmed" in result.reason_codes


def test_classify_regime_risk_off_on_confirmed_price_break() -> None:
    config = load_app_config().regime
    observations = tuple(_observation(index, close=98.0) for index in range(2))

    result = classify_regime(observations, config)

    assert result.state == "RISK_OFF"
    assert result.new_entries_allowed is False
    assert result.cooldown_days_remaining == config.risk_off_cooldown_days


def test_classify_regime_risk_off_on_high_realized_volatility() -> None:
    config = load_app_config().regime
    observations = (
        _observation(0, close=100.0, rv20=0.20),
        _observation(1, close=100.0, rv20=0.36),
    )

    result = classify_regime(observations, config)

    assert result.state == "RISK_OFF"
    assert result.risk_off_confirmed is True


def test_classify_regime_caution_when_inputs_missing() -> None:
    config = load_app_config().regime
    observations = (
        RegimeObservation(
            symbol="SPY",
            date=date(2024, 1, 1),
            close=100.0,
            sma_fast=None,
            sma_slow=100.0,
            rv20=0.2,
        ),
    )

    result = classify_regime(observations, config)

    assert result.state == "CAUTION"
    assert result.new_entries_allowed is False
    assert "missing_sma_fast" in result.reason_codes


def test_realized_volatility_20_uses_log_returns() -> None:
    closes = [100.0] * 21

    rv20 = realized_volatility_20(closes)

    assert rv20[19] is None
    assert rv20[20] == pytest.approx(0.0)

