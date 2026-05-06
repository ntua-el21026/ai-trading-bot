"""Typed request/response contracts for safe ledger-backed activities."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from packages.ai.persistence import AIResearchPersistencePayload
from packages.data.models import RawProviderPayload
from packages.execution.models import ExecutionIntent

LedgerActivityStatus = Literal["persisted", "noop", "read"]


class ActivityModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class LedgerActivityContext(ActivityModel):
    workflow_name: str
    purpose: str
    request_id: str | None = None
    occurred_at: datetime | None = None

    @model_validator(mode="after")
    def validate_occurred_at(self) -> Self:
        _require_optional_aware(self.occurred_at, "occurred_at")
        return self


class LedgerActivityResult(ActivityModel):
    activity_name: str
    status: LedgerActivityStatus
    records_written: int = Field(ge=0)
    record_ids: tuple[str, ...] = ()
    external_calls_performed: bool = False
    details: dict[str, str] = Field(default_factory=dict)


class RawProviderPayloadPersistenceRequest(ActivityModel):
    context: LedgerActivityContext
    payloads: tuple[RawProviderPayload, ...]


class DataRefreshPersistenceRequest(ActivityModel):
    context: LedgerActivityContext
    raw_payloads: tuple[RawProviderPayload, ...] = ()
    summary: dict[str, str] = Field(default_factory=dict)


class TradeCandidatePayload(ActivityModel):
    symbol: str
    trading_date: date
    strategy_version: str
    candidate_status: str
    candidate_id: str | None = None
    technical_score: float | None = Field(default=None, ge=0, le=100)
    relative_strength_score: float | None = Field(default=None, ge=0, le=100)
    score_payload: dict[str, Any] = Field(default_factory=dict)
    reason_payload: dict[str, Any] = Field(default_factory=dict)
    rejection_reasons: tuple[str, ...] = ()
    source_features_daily_id: str | None = None
    created_at: datetime | None = None

    @field_validator("symbol")
    @classmethod
    def validate_symbol(cls, symbol: str) -> str:
        return _uppercase_symbol(symbol)

    @model_validator(mode="after")
    def validate_created_at(self) -> Self:
        _require_optional_aware(self.created_at, "created_at")
        return self


class TradeCandidatePersistenceRequest(ActivityModel):
    context: LedgerActivityContext
    candidates: tuple[TradeCandidatePayload, ...]


class AIResearchOutputPersistenceRequest(ActivityModel):
    context: LedgerActivityContext
    outputs: tuple[AIResearchPersistencePayload, ...]


class TradeDecisionPayload(ActivityModel):
    symbol: str
    decision_status: str
    decision_id: str | None = None
    candidate_id: str | None = None
    final_score: float | None = Field(default=None, ge=0, le=100)
    deterministic_decision_payload: dict[str, Any] = Field(default_factory=dict)
    ai_output_id: str | None = None
    created_at: datetime | None = None

    @field_validator("symbol")
    @classmethod
    def validate_symbol(cls, symbol: str) -> str:
        return _uppercase_symbol(symbol)

    @model_validator(mode="after")
    def validate_created_at(self) -> Self:
        _require_optional_aware(self.created_at, "created_at")
        return self


class TradeDecisionPersistenceRequest(ActivityModel):
    context: LedgerActivityContext
    decisions: tuple[TradeDecisionPayload, ...]


class RiskCheckPayload(ActivityModel):
    symbol: str
    passed: bool
    risk_config_version: str
    risk_check_id: str | None = None
    decision_id: str | None = None
    execution_intent_id: str | None = None
    reason_codes: tuple[str, ...] = ()
    input_snapshot: dict[str, Any] = Field(default_factory=dict)
    result_payload: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime | None = None

    @field_validator("symbol")
    @classmethod
    def validate_symbol(cls, symbol: str) -> str:
        return _uppercase_symbol(symbol)

    @model_validator(mode="after")
    def validate_created_at(self) -> Self:
        _require_optional_aware(self.created_at, "created_at")
        return self


class RiskCheckPersistenceRequest(ActivityModel):
    context: LedgerActivityContext
    risk_checks: tuple[RiskCheckPayload, ...]


class ExecutionIntentPersistenceRequest(ActivityModel):
    context: LedgerActivityContext
    intents: tuple[ExecutionIntent, ...]


class OrderAuditPayload(ActivityModel):
    client_order_id: str
    symbol: str
    side: Literal["buy", "sell"]
    order_type: str
    time_in_force: str
    quantity: float = Field(gt=0)
    status: str
    execution_intent_id: str | None = None
    broker_order_id: str | None = None
    limit_price: float | None = Field(default=None, gt=0)
    stop_price: float | None = Field(default=None, gt=0)
    raw_broker_payload: dict[str, Any] = Field(default_factory=dict)
    order_id: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    @field_validator("symbol")
    @classmethod
    def validate_symbol(cls, symbol: str) -> str:
        return _uppercase_symbol(symbol)

    @model_validator(mode="after")
    def validate_timestamps(self) -> Self:
        _require_optional_aware(self.created_at, "created_at")
        _require_optional_aware(self.updated_at, "updated_at")
        return self


class OrderEventPersistenceRequest(ActivityModel):
    context: LedgerActivityContext
    orders: tuple[OrderAuditPayload, ...]


class FillAuditPayload(ActivityModel):
    order_id: str
    symbol: str
    quantity: float = Field(gt=0)
    price: float = Field(gt=0)
    filled_at: datetime
    broker_order_id: str | None = None
    broker_fill_id: str | None = None
    raw_broker_payload: dict[str, Any] = Field(default_factory=dict)
    fill_id: str | None = None
    created_at: datetime | None = None

    @field_validator("symbol")
    @classmethod
    def validate_symbol(cls, symbol: str) -> str:
        return _uppercase_symbol(symbol)

    @model_validator(mode="after")
    def validate_timestamps(self) -> Self:
        _require_aware(self.filled_at, "filled_at")
        _require_optional_aware(self.created_at, "created_at")
        return self


class FillEventPersistenceRequest(ActivityModel):
    context: LedgerActivityContext
    fills: tuple[FillAuditPayload, ...]


class PositionSnapshotPayload(ActivityModel):
    symbol: str
    quantity: float
    average_entry_price: float = Field(gt=0)
    status: str = "open"
    protective_stop_order_id: str | None = None
    opened_at: datetime | None = None
    closed_at: datetime | None = None
    raw_source_payload: dict[str, Any] = Field(default_factory=dict)

    @field_validator("symbol")
    @classmethod
    def validate_symbol(cls, symbol: str) -> str:
        return _uppercase_symbol(symbol)

    @model_validator(mode="after")
    def validate_timestamps(self) -> Self:
        _require_optional_aware(self.opened_at, "opened_at")
        _require_optional_aware(self.closed_at, "closed_at")
        return self


class PositionSnapshotPersistenceRequest(ActivityModel):
    context: LedgerActivityContext
    positions: tuple[PositionSnapshotPayload, ...]


class BrokerReconciliationSnapshotPayload(ActivityModel):
    account_snapshot: dict[str, Any]
    broker_positions: tuple[Any, ...] = ()
    internal_positions: tuple[Any, ...] = ()
    broker_orders: tuple[Any, ...] = ()
    internal_orders: tuple[Any, ...] = ()
    mismatches: tuple[Any, ...] = ()
    status: str
    temporal_workflow_id: str | None = None
    reconciliation_id: str | None = None
    created_at: datetime | None = None

    @model_validator(mode="after")
    def validate_created_at(self) -> Self:
        _require_optional_aware(self.created_at, "created_at")
        return self


class BrokerReconciliationPersistenceRequest(ActivityModel):
    context: LedgerActivityContext
    reconciliations: tuple[BrokerReconciliationSnapshotPayload, ...]


class SystemEventPayload(ActivityModel):
    event_type: str
    severity: Literal["info", "warning", "critical"]
    source_component: str
    message: str
    related_entity_type: str | None = None
    related_entity_id: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    event_id: str | None = None
    created_at: datetime | None = None
    acknowledged_at: datetime | None = None

    @model_validator(mode="after")
    def validate_timestamps(self) -> Self:
        _require_optional_aware(self.created_at, "created_at")
        _require_optional_aware(self.acknowledged_at, "acknowledged_at")
        return self


class SystemEventPersistenceRequest(ActivityModel):
    context: LedgerActivityContext
    events: tuple[SystemEventPayload, ...]


class ReportPayload(ActivityModel):
    report_type: str
    status: str
    payload: dict[str, Any] = Field(default_factory=dict)
    markdown: str | None = None
    report_date: date | None = None
    period_start: date | None = None
    period_end: date | None = None
    report_id: str | None = None
    created_at: datetime | None = None

    @model_validator(mode="after")
    def validate_created_at(self) -> Self:
        _require_optional_aware(self.created_at, "created_at")
        return self


class ReportPersistenceRequest(ActivityModel):
    context: LedgerActivityContext
    reports: tuple[ReportPayload, ...]


class LedgerReadRequest(ActivityModel):
    context: LedgerActivityContext
    limit: int = Field(default=100, gt=0, le=500)


def _uppercase_symbol(symbol: str) -> str:
    if symbol != symbol.upper():
        raise ValueError("symbol must be uppercase")
    return symbol


def _require_aware(value: datetime, field_name: str) -> None:
    if value.tzinfo is None:
        raise ValueError(f"{field_name} must be timezone-aware")


def _require_optional_aware(value: datetime | None, field_name: str) -> None:
    if value is not None:
        _require_aware(value, field_name)
