"""Typed models for deterministic regime, strategy, and exit decisions."""

from __future__ import annotations

from datetime import date
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

RegimeState = Literal["RISK_ON", "CAUTION", "RISK_OFF"]
StrategyMode = Literal["live", "research"]
BreakoutLookback = Literal[20, 55]
EarningsBlackoutStatus = Literal["clear", "blackout", "unknown"]


class StrategyModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class RegimeObservation(StrategyModel):
    symbol: str
    date: date
    close: float = Field(gt=0)
    sma_fast: float | None = Field(default=None, gt=0)
    sma_slow: float | None = Field(default=None, gt=0)
    rv20: float | None = Field(default=None, ge=0)

    @field_validator("symbol")
    @classmethod
    def validate_symbol(cls, symbol: str) -> str:
        if symbol != symbol.upper():
            raise ValueError("symbol must be uppercase")
        return symbol


class RegimeClassification(StrategyModel):
    state: RegimeState
    as_of: date
    proxy: str
    new_entries_allowed: bool
    size_multiplier: float = Field(ge=0, le=1)
    risk_on_confirmed: bool
    risk_off_confirmed: bool
    cooldown_days_remaining: int = Field(ge=0)
    reason_codes: tuple[str, ...]


class EarningsBlackoutEvaluation(StrategyModel):
    status: EarningsBlackoutStatus
    as_of: date
    earnings_date: date | None = None
    allow_entries: bool
    allow_exits: bool = True
    reason_codes: tuple[str, ...]


class CandidateEvaluation(StrategyModel):
    symbol: str
    date: date
    mode: StrategyMode
    accepted: bool
    side: Literal["long"] = "long"
    breakout_lookback: BreakoutLookback | None = None
    breakout_level: float | None = Field(default=None, gt=0)
    technical_score: float = Field(ge=0, le=100)
    relative_strength_score: float = Field(ge=0, le=100)
    reason_codes: tuple[str, ...] = ()
    rejection_reasons: tuple[str, ...] = ()

    @model_validator(mode="after")
    def validate_candidate_consistency(self) -> Self:
        if self.accepted and self.rejection_reasons:
            raise ValueError("accepted candidates cannot include rejection reasons")
        if self.accepted and self.breakout_lookback is None:
            raise ValueError("accepted candidates must include breakout lookback")
        return self


class ExitEvaluation(StrategyModel):
    should_exit: bool
    reason_codes: tuple[str, ...]

