"""Typed deterministic risk models."""

from __future__ import annotations

from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from packages.data.models import AssetClass

KillSwitchState = Literal[
    "RUNNING",
    "PAUSED_NEW_RISK",
    "PAUSED_ALL_AUTONOMOUS_ACTIONS",
    "FORCE_FLAT_REQUESTED",
    "MANUAL_REVIEW_REQUIRED",
]
RiskCheckSeverity = Literal["info", "warning", "critical"]
RiskOrderSide = Literal["buy"]
Environment = Literal["paper", "live"]


class RiskModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class KillSwitchSnapshot(RiskModel):
    state: KillSwitchState = "RUNNING"
    reason: str = "initialized"
    new_risk_allowed: bool = True
    risk_reducing_exits_allowed: bool = True

    @model_validator(mode="after")
    def validate_state_permissions(self) -> Self:
        if self.state != "RUNNING" and self.new_risk_allowed:
            raise ValueError("non-running kill-switch states cannot allow new risk")
        return self


class RiskCheckResult(RiskModel):
    name: str
    passed: bool
    severity: RiskCheckSeverity = "critical"
    reason_code: str
    details: dict[str, str] = Field(default_factory=dict)


class RiskAssessment(RiskModel):
    symbol: str
    approved: bool
    checks: tuple[RiskCheckResult, ...]

    @property
    def rejection_reasons(self) -> tuple[str, ...]:
        return tuple(check.reason_code for check in self.checks if not check.passed)


class NewRiskOrderInput(RiskModel):
    symbol: str
    asset_class: AssetClass
    side: RiskOrderSide = "buy"
    quantity: int = Field(gt=0)
    entry_price: float = Field(gt=0)
    stop_loss_price: float | None = Field(default=None, gt=0)
    account_equity: float = Field(gt=0)
    cash: float = Field(ge=0)
    current_gross_exposure: float = Field(ge=0)
    current_deployable_capital: float = Field(ge=0)
    current_open_positions: int = Field(ge=0)
    current_sector_exposure_pct: float = Field(ge=0)
    daily_loss_pct: float = Field(ge=0)
    weekly_loss_pct: float = Field(ge=0)
    monthly_loss_pct: float = Field(ge=0)
    data_is_fresh: bool
    market_session_valid: bool | None
    broker_reconciliation_clean: bool | None
    broker_account_environment: Environment | None
    kill_switch: KillSwitchSnapshot
    active_duplicate_intent: bool
    temporal_workflow_consistent: bool | None
    system_health_ok: bool

    @field_validator("symbol")
    @classmethod
    def validate_symbol(cls, symbol: str) -> str:
        if symbol != symbol.upper():
            raise ValueError("symbol must be uppercase")
        return symbol

    @property
    def proposed_order_value(self) -> float:
        return float(self.quantity) * self.entry_price

    @property
    def proposed_risk_amount(self) -> float | None:
        if self.stop_loss_price is None:
            return None
        stop_distance = self.entry_price - self.stop_loss_price
        if stop_distance <= 0:
            return None
        return float(self.quantity) * stop_distance


class PositionSizingInput(RiskModel):
    account_equity: float = Field(gt=0)
    entry_price: float = Field(gt=0)
    stop_price: float = Field(gt=0)
    regime_size_multiplier: float = Field(default=1.0, ge=0, le=1)
    ai_size_multiplier: float = Field(default=1.0, ge=0, le=1)
    execution_quality_multiplier: float = Field(default=1.0, ge=0, le=1)


class PositionSizingResult(RiskModel):
    accepted: bool
    shares: int = Field(ge=0)
    raw_shares: int = Field(ge=0)
    max_value_shares: int = Field(ge=0)
    risk_amount: float = Field(ge=0)
    stop_distance: float = Field(ge=0)
    applied_multiplier: float = Field(ge=0, le=1)
    rejection_reasons: tuple[str, ...] = ()

