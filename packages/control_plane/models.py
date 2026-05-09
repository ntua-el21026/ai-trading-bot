"""Dashboard and control-plane read/action contracts.

These models are passive contracts. They do not submit orders, call brokers, call AI providers, or
change runtime state by themselves.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

DashboardDataSource = Literal["fixture", "temporal_query", "database_read_model", "unavailable"]
DashboardSeverity = Literal["info", "warning", "critical"]
ControlActionType = Literal[
    "manual_kill_switch",
    "manual_pause_new_risk",
    "manual_resume_after_review",
    "force_reconciliation",
    "force_report",
    "acknowledge_incident",
]
ControlActionStatus = Literal["accepted", "rejected", "dispatched"]
KillSwitchStateName = Literal[
    "RUNNING",
    "PAUSED_NEW_RISK",
    "PAUSED_ALL_AUTONOMOUS_ACTIONS",
    "FORCE_FLAT_REQUESTED",
    "MANUAL_REVIEW_REQUIRED",
]

ORDER_ENTRY_CONTROL_ACTIONS: frozenset[str] = frozenset(
    {
        "submit_order",
        "create_order",
        "modify_order",
        "cancel_order",
        "submit_protective_stop",
        "natural_language_order",
    }
)


class ControlPlaneModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class SystemStateView(ControlPlaneModel):
    environment: Literal["paper", "live"]
    dry_run: bool
    live_trading_enabled: bool
    autonomous_execution_enabled: bool
    autonomy_level: int = Field(ge=0, le=5)
    kill_switch_enabled: bool
    as_of: datetime
    data_source: DashboardDataSource = "fixture"

    @model_validator(mode="after")
    def validate_state(self) -> Self:
        _require_aware(self.as_of, "as_of")
        if self.environment == "paper" and self.live_trading_enabled:
            raise ValueError("paper dashboard state cannot show live_trading_enabled=true")
        if self.live_trading_enabled and self.dry_run:
            raise ValueError("live trading cannot be enabled while dry_run=true")
        return self


class WorkflowSummaryView(ControlPlaneModel):
    workflow_id: str
    workflow_type: str
    task_queue: str
    status: str
    started_at: datetime | None = None
    last_updated_at: datetime | None = None
    data_source: DashboardDataSource = "fixture"

    @model_validator(mode="after")
    def validate_timestamps(self) -> Self:
        _require_optional_aware(self.started_at, "started_at")
        _require_optional_aware(self.last_updated_at, "last_updated_at")
        return self


class ExecutionIntentView(ControlPlaneModel):
    intent_id: str
    symbol: str
    side: Literal["buy", "sell"]
    quantity: float = Field(gt=0)
    status: str
    expires_at: datetime | None = None
    data_source: DashboardDataSource = "fixture"

    @field_validator("symbol")
    @classmethod
    def validate_symbol(cls, symbol: str) -> str:
        return _uppercase_symbol(symbol)

    @model_validator(mode="after")
    def validate_expires_at(self) -> Self:
        _require_optional_aware(self.expires_at, "expires_at")
        return self


class OrderView(ControlPlaneModel):
    client_order_id: str
    broker_order_id: str | None = None
    symbol: str
    side: Literal["buy", "sell"]
    order_type: str
    status: str
    quantity: float = Field(gt=0)
    filled_quantity: float = Field(default=0, ge=0)
    submitted_at: datetime | None = None
    data_source: DashboardDataSource = "fixture"

    @field_validator("symbol")
    @classmethod
    def validate_symbol(cls, symbol: str) -> str:
        return _uppercase_symbol(symbol)

    @model_validator(mode="after")
    def validate_order(self) -> Self:
        if self.filled_quantity > self.quantity:
            raise ValueError("filled_quantity cannot exceed quantity")
        _require_optional_aware(self.submitted_at, "submitted_at")
        return self


class PositionView(ControlPlaneModel):
    symbol: str
    quantity: float
    avg_entry_price: float = Field(gt=0)
    protective_stop_confirmed: bool
    opened_at: datetime | None = None
    data_source: DashboardDataSource = "fixture"

    @field_validator("symbol")
    @classmethod
    def validate_symbol(cls, symbol: str) -> str:
        return _uppercase_symbol(symbol)

    @model_validator(mode="after")
    def validate_opened_at(self) -> Self:
        _require_optional_aware(self.opened_at, "opened_at")
        return self


class RiskStatusView(ControlPlaneModel):
    new_risk_allowed: bool
    broker_reconciliation_clean: bool
    risk_checks_passing: bool
    current_gross_exposure_pct: float = Field(ge=0, le=1)
    current_deployable_capital_pct: float = Field(ge=0, le=1)
    daily_loss_pct: float
    weekly_loss_pct: float
    monthly_loss_pct: float
    data_source: DashboardDataSource = "fixture"


class ReconciliationStatusView(ControlPlaneModel):
    clean: bool
    last_checked_at: datetime | None = None
    severity: DashboardSeverity = "info"
    mismatch_count: int = Field(ge=0)
    pause_new_risk_recommended: bool = False
    data_source: DashboardDataSource = "fixture"

    @model_validator(mode="after")
    def validate_last_checked_at(self) -> Self:
        _require_optional_aware(self.last_checked_at, "last_checked_at")
        return self


class IncidentView(ControlPlaneModel):
    incident_id: str
    severity: DashboardSeverity
    status: Literal["open", "acknowledged", "resolved"]
    message: str
    created_at: datetime
    acknowledged_at: datetime | None = None
    data_source: DashboardDataSource = "fixture"

    @model_validator(mode="after")
    def validate_timestamps(self) -> Self:
        _require_aware(self.created_at, "created_at")
        _require_optional_aware(self.acknowledged_at, "acknowledged_at")
        return self


class KillSwitchStateView(ControlPlaneModel):
    state: KillSwitchStateName
    new_risk_allowed: bool
    risk_reducing_exits_allowed: bool
    reason: str | None = None
    data_source: DashboardDataSource = "fixture"

    @model_validator(mode="after")
    def validate_permissions(self) -> Self:
        if self.state != "RUNNING" and self.new_risk_allowed:
            raise ValueError("non-running kill-switch states cannot allow new risk")
        if self.state == "PAUSED_ALL_AUTONOMOUS_ACTIONS" and self.risk_reducing_exits_allowed:
            raise ValueError("PAUSED_ALL_AUTONOMOUS_ACTIONS blocks risk-reducing exits")
        return self


class CandidateSignalView(ControlPlaneModel):
    symbol: str
    accepted: bool
    technical_score: float = Field(ge=0, le=100)
    relative_strength_score: float = Field(ge=0, le=100)
    rejection_reasons: tuple[str, ...] = ()
    data_source: DashboardDataSource = "fixture"

    @field_validator("symbol")
    @classmethod
    def validate_symbol(cls, symbol: str) -> str:
        return _uppercase_symbol(symbol)


class AIResearchOutputView(ControlPlaneModel):
    symbol: str
    news_state: str
    ai_score: int = Field(ge=10, le=90)
    hard_block: bool
    fallback: bool
    explanation: str
    data_source: DashboardDataSource = "fixture"

    @field_validator("symbol")
    @classmethod
    def validate_symbol(cls, symbol: str) -> str:
        return _uppercase_symbol(symbol)


class AIQualityStateView(ControlPlaneModel):
    state: Literal[
        "AI_NORMAL",
        "AI_REDUCED_INFLUENCE",
        "AI_NEUTRAL_ONLY",
        "AI_ESCALATION_REQUIRED",
        "unavailable",
    ] = "unavailable"
    schema_validity_rate: float | None = Field(default=None, ge=0, le=1)
    fallback_rate: float | None = Field(default=None, ge=0, le=1)
    provider_coverage_rate: float | None = Field(default=None, ge=0, le=1)
    data_source: DashboardDataSource = "unavailable"


class ProviderBudgetStatusView(ControlPlaneModel):
    provider: str
    daily_limit: int | None = Field(default=None, ge=0)
    used: int | None = Field(default=None, ge=0)
    remaining: int | None = Field(default=None, ge=0)
    status: Literal["ok", "warning", "exceeded", "unavailable"] = "unavailable"
    data_source: DashboardDataSource = "unavailable"

    @model_validator(mode="after")
    def validate_budget_counts(self) -> Self:
        if self.daily_limit is not None and self.used is not None and self.used > self.daily_limit:
            raise ValueError("provider budget used count cannot exceed daily limit")
        if (
            self.daily_limit is not None
            and self.remaining is not None
            and self.remaining > self.daily_limit
        ):
            raise ValueError("provider budget remaining count cannot exceed daily limit")
        return self


class ReportSummaryView(ControlPlaneModel):
    report_id: str
    report_type: Literal["daily", "weekly", "manual"]
    generated_at: datetime
    status: str
    data_source: DashboardDataSource = "fixture"

    @model_validator(mode="after")
    def validate_generated_at(self) -> Self:
        _require_aware(self.generated_at, "generated_at")
        return self


class AlertingStatusView(ControlPlaneModel):
    primary_provider: str = "telegram"
    real_delivery_enabled: bool = False
    fake_adapter_active: bool = True
    last_delivery_status: str = "unavailable"
    data_source: DashboardDataSource = "unavailable"


class TemporalRuntimeStatusView(ControlPlaneModel):
    connected: bool = False
    namespace_present: bool = False
    task_queue: str | None = None
    worker_started: bool = False
    workflow_completed: bool = False
    signal_query_checked: bool = False
    schedules_created: bool = False
    schedules_activated: bool = False
    data_source: DashboardDataSource = "unavailable"

    @model_validator(mode="after")
    def validate_temporal_status(self) -> Self:
        if self.schedules_created or self.schedules_activated:
            raise ValueError("dashboard runtime status cannot report schedule creation/activation")
        return self


class PaperOperationReadinessView(ControlPlaneModel):
    controlled_lifecycle_smoke_complete: bool | None = None
    actual_paper_trading_started: bool = False
    frozen_paper_evidence_available: bool = False
    level4_ready: bool = False
    data_source: DashboardDataSource = "unavailable"

    @model_validator(mode="after")
    def validate_readiness_boundary(self) -> Self:
        if self.actual_paper_trading_started:
            raise ValueError("dashboard dev runtime cannot claim actual paper trading has started")
        if self.level4_ready:
            raise ValueError("dashboard dev runtime cannot claim Level 4 readiness")
        return self


class DashboardSnapshot(ControlPlaneModel):
    system_state: SystemStateView
    kill_switch: KillSwitchStateView
    risk_status: RiskStatusView
    reconciliation_status: ReconciliationStatusView
    active_workflows: tuple[WorkflowSummaryView, ...] = ()
    active_execution_intents: tuple[ExecutionIntentView, ...] = ()
    open_orders: tuple[OrderView, ...] = ()
    open_positions: tuple[PositionView, ...] = ()
    recent_incidents: tuple[IncidentView, ...] = ()
    candidate_signals: tuple[CandidateSignalView, ...] = ()
    ai_outputs: tuple[AIResearchOutputView, ...] = ()
    ai_quality_state: AIQualityStateView = Field(default_factory=AIQualityStateView)
    provider_budget_status: tuple[ProviderBudgetStatusView, ...] = ()
    reports: tuple[ReportSummaryView, ...] = ()
    alerting_status: AlertingStatusView = Field(default_factory=AlertingStatusView)
    temporal_runtime_status: TemporalRuntimeStatusView = Field(
        default_factory=TemporalRuntimeStatusView
    )
    paper_operation_readiness: PaperOperationReadinessView = Field(
        default_factory=PaperOperationReadinessView
    )


class ControlActionRequest(ControlPlaneModel):
    action: ControlActionType
    requested_by: str
    requested_at: datetime
    reason: str
    incident_id: str | None = None
    manual_review_reference: str | None = None
    idempotency_key: str

    @model_validator(mode="after")
    def validate_action(self) -> Self:
        _require_aware(self.requested_at, "requested_at")
        if not self.requested_by.strip():
            raise ValueError("requested_by is required")
        if not self.reason.strip():
            raise ValueError("reason is required")
        if self.action == "acknowledge_incident" and not self.incident_id:
            raise ValueError("acknowledge_incident requires incident_id")
        if self.action != "acknowledge_incident" and self.incident_id:
            raise ValueError("incident_id is only valid for acknowledge_incident")
        if self.action == "manual_resume_after_review" and not self.manual_review_reference:
            raise ValueError("manual_resume_after_review requires manual_review_reference")
        if self.action != "manual_resume_after_review" and self.manual_review_reference:
            raise ValueError("manual_review_reference is only valid for resume after review")
        if self.action in ORDER_ENTRY_CONTROL_ACTIONS:
            raise ValueError("order-entry controls are forbidden")
        return self


class ControlActionReceipt(ControlPlaneModel):
    request: ControlActionRequest
    status: ControlActionStatus
    temporal_signal_name: str
    dispatched_at: datetime | None = None
    message: str
    broker_calls_performed: bool = False
    orders_created: bool = False
    risk_limits_modified: bool = False
    autonomy_level_modified: bool = False

    @model_validator(mode="after")
    def validate_receipt_safety(self) -> Self:
        _require_optional_aware(self.dispatched_at, "dispatched_at")
        if self.broker_calls_performed:
            raise ValueError("control-plane receipts cannot include broker calls")
        if self.orders_created:
            raise ValueError("control-plane receipts cannot create orders")
        if self.risk_limits_modified:
            raise ValueError("control-plane receipts cannot modify risk limits")
        if self.autonomy_level_modified:
            raise ValueError("control-plane receipts cannot modify autonomy level")
        return self


def _uppercase_symbol(symbol: str) -> str:
    if symbol != symbol.upper():
        raise ValueError("symbol must be uppercase")
    return symbol


def _require_aware(timestamp: datetime, field_name: str) -> None:
    if timestamp.tzinfo is None:
        raise ValueError(f"{field_name} must be timezone-aware")


def _require_optional_aware(timestamp: datetime | None, field_name: str) -> None:
    if timestamp is not None:
        _require_aware(timestamp, field_name)
