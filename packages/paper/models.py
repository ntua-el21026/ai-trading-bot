"""Typed fake/local paper dry-run orchestration models."""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from packages.control_plane.models import DashboardSnapshot

DryRunFailureMode = Literal[
    "none",
    "risk_rejection",
    "invalid_ai_output_neutral",
    "duplicate_active_intent",
    "broker_ambiguity",
    "partial_fill",
    "missing_protective_stop",
    "reconciliation_mismatch",
    "kill_switch_pause_new_risk",
    "stale_data",
]
DryRunStepStatus = Literal["passed", "failed", "skipped"]


class DryRunModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class DryRunScenario(DryRunModel):
    scenario_id: str
    name: str
    failure_mode: DryRunFailureMode = "none"
    symbol: str = "AAPL"
    asset_class: Literal["equity", "etf"] = "equity"
    trade_date: date
    quantity: int = Field(gt=0)
    filled_quantity: int = Field(gt=0)
    limit_price: float = Field(gt=0)
    stop_loss_price: float = Field(gt=0)
    account_equity: float = Field(gt=0)
    cash: float = Field(ge=0)
    technical_score: float = Field(ge=0, le=100)
    relative_strength_score: float = Field(ge=0, le=100)

    @model_validator(mode="after")
    def validate_scenario(self) -> Self:
        if self.symbol != self.symbol.upper():
            raise ValueError("dry-run scenario symbol must be uppercase")
        if self.stop_loss_price >= self.limit_price:
            raise ValueError("dry-run stop loss must be below limit price")
        if self.filled_quantity > self.quantity:
            raise ValueError("filled_quantity cannot exceed quantity")
        return self


class DryRunConfig(DryRunModel):
    broker_mode: Literal["fake"] = "fake"
    ai_provider_mode: Literal["neutral", "fake_invalid"] = "neutral"
    alert_mode: Literal["fake"] = "fake"
    ledger_mode: Literal["local_sqlite"] = "local_sqlite"
    simulate_autonomous_permission_for_risk_gate: bool = True
    require_safe_runtime_flags: bool = True


class DryRunInput(DryRunModel):
    scenario: DryRunScenario
    config: DryRunConfig = Field(default_factory=DryRunConfig)
    started_at: datetime
    completed_at: datetime

    @model_validator(mode="after")
    def validate_timestamps(self) -> Self:
        _require_aware(self.started_at, "started_at")
        _require_aware(self.completed_at, "completed_at")
        if self.completed_at < self.started_at:
            raise ValueError("completed_at cannot be before started_at")
        return self


class DryRunStepResult(DryRunModel):
    name: str
    status: DryRunStepStatus
    reason_code: str
    details: dict[str, str] = Field(default_factory=dict)


class DryRunSafetyFlags(DryRunModel):
    live_trading_enabled: bool
    autonomous_execution_enabled: bool
    allow_live_orders: bool
    fake_broker_used: bool = True
    fake_alert_adapter_used: bool = True
    neutral_or_fake_ai_used: bool = True
    local_ledger_used: bool = True
    external_calls_performed: bool = False
    real_broker_calls_performed: bool = False
    real_ai_news_calls_performed: bool = False
    real_alerts_sent: bool = False
    real_orders_submitted: bool = False
    managed_database_used: bool = False
    actual_paper_trading_started: bool = False

    @property
    def safe(self) -> bool:
        return (
            not self.live_trading_enabled
            and not self.autonomous_execution_enabled
            and not self.allow_live_orders
            and self.fake_broker_used
            and self.fake_alert_adapter_used
            and self.neutral_or_fake_ai_used
            and self.local_ledger_used
            and not self.external_calls_performed
            and not self.real_broker_calls_performed
            and not self.real_ai_news_calls_performed
            and not self.real_alerts_sent
            and not self.real_orders_submitted
            and not self.managed_database_used
            and not self.actual_paper_trading_started
        )


class DryRunEvidence(DryRunModel):
    model_config = ConfigDict(extra="forbid", frozen=False)

    persisted_entity_ids: dict[str, tuple[str, ...]] = Field(default_factory=dict)
    execution_intent_id: str | None = None
    client_order_id: str | None = None
    fake_broker_order_id: str | None = None
    fake_broker_order_status: str | None = None
    fake_broker_order_request_count: int = Field(default=0, ge=0)
    fake_fill_status: str | None = None
    filled_quantity: float | None = Field(default=None, ge=0)
    protective_stop_client_order_id: str | None = None
    protective_stop_verified: bool = False
    reconciliation_status: str | None = None
    reconciliation_mismatch_types: tuple[str, ...] = ()
    alert_count: int = Field(default=0, ge=0)
    alert_titles: tuple[str, ...] = ()
    report_id: str | None = None
    dashboard_snapshot_status: str | None = None


class DryRunResult(DryRunModel):
    scenario_id: str
    scenario_name: str
    failure_mode: DryRunFailureMode
    started_at: datetime
    completed_at: datetime
    steps: tuple[DryRunStepResult, ...]
    evidence: DryRunEvidence
    safety_flags: DryRunSafetyFlags
    passed: bool
    failure_reasons: tuple[str, ...] = ()
    dashboard_snapshot: DashboardSnapshot | None = None
    note: str = (
        "This is a fake/local dry run. No broker orders are submitted and no external "
        "calls are made."
    )

    @model_validator(mode="after")
    def validate_result_timestamps(self) -> Self:
        _require_aware(self.started_at, "started_at")
        _require_aware(self.completed_at, "completed_at")
        return self


def _require_aware(value: datetime, field_name: str) -> None:
    if value.tzinfo is None:
        raise ValueError(f"{field_name} must be timezone-aware")
