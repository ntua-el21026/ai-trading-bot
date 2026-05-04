"""Deterministic position sizing helpers."""

from __future__ import annotations

from math import floor

from packages.core.config import RiskLevelConfig
from packages.risk.models import PositionSizingInput, PositionSizingResult


def calculate_position_size(
    sizing_input: PositionSizingInput,
    risk_config: RiskLevelConfig,
) -> PositionSizingResult:
    risk_amount = sizing_input.account_equity * risk_config.max_risk_per_trade_pct
    stop_distance = sizing_input.entry_price - sizing_input.stop_price
    applied_multiplier = (
        sizing_input.regime_size_multiplier
        * sizing_input.ai_size_multiplier
        * sizing_input.execution_quality_multiplier
    )

    if stop_distance <= 0:
        return PositionSizingResult(
            accepted=False,
            shares=0,
            raw_shares=0,
            max_value_shares=0,
            risk_amount=risk_amount,
            stop_distance=0.0,
            applied_multiplier=applied_multiplier,
            rejection_reasons=("invalid_stop_distance",),
        )

    raw_shares = floor(risk_amount / stop_distance)
    max_value_shares = floor(
        (sizing_input.account_equity * risk_config.max_position_size_pct)
        / sizing_input.entry_price
    )
    shares_before_multipliers = min(raw_shares, max_value_shares)
    shares = floor(float(shares_before_multipliers) * applied_multiplier)
    if shares < 1:
        return PositionSizingResult(
            accepted=False,
            shares=0,
            raw_shares=raw_shares,
            max_value_shares=max_value_shares,
            risk_amount=risk_amount,
            stop_distance=stop_distance,
            applied_multiplier=applied_multiplier,
            rejection_reasons=("position_size_below_one_share",),
        )
    return PositionSizingResult(
        accepted=True,
        shares=shares,
        raw_shares=raw_shares,
        max_value_shares=max_value_shares,
        risk_amount=risk_amount,
        stop_distance=stop_distance,
        applied_multiplier=applied_multiplier,
    )

