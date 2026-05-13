"""Passive internal ledger and reconciliation incident models."""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from packages.broker.models import BrokerSnapshot

InternalOrderStatus = Literal["open", "filled", "cancelled", "rejected", "expired"]
ReconciliationMismatchType = Literal[
    "broker_position_without_internal_position",
    "internal_position_without_broker_position",
    "missing_protective_stop",
    "short_protective_stop_missing",
    "orphan_protective_stop_without_position",
    "oversubscribed_protective_stop_quantity",
    "signed_qty_inconsistent",
    "stream_rest_divergence",
    "duplicate_open_entry_orders",
    "unexpected_short_position",
    "fill_not_recorded_internal",
    "unknown_open_broker_order",
    "quantity_mismatch",
    "avg_entry_price_mismatch",
    "account_equity_mismatch",
    "temporal_workflow_state_inconsistent",
    "stale_broker_snapshot",
    "stale_internal_snapshot",
    "unsupported_broker_asset_class",
]
IncidentSeverity = Literal["info", "warning", "critical"]
IncidentActionRecommendation = Literal[
    "none",
    "investigate",
    "pause_new_risk",
    "manual_review_required",
    "flatten_if_safe",
]


class ReconciliationModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class InternalAccountSnapshot(ReconciliationModel):
    equity: float = Field(gt=0)
    cash: float = Field(ge=0)
    as_of: datetime

    @model_validator(mode="after")
    def validate_as_of(self) -> Self:
        if self.as_of.tzinfo is None:
            raise ValueError("as_of must be timezone-aware")
        return self


class InternalOrder(ReconciliationModel):
    order_id: str
    client_order_id: str
    symbol: str
    side: Literal["buy", "sell"]
    quantity: float = Field(gt=0)
    filled_quantity: float = Field(default=0.0, ge=0)
    status: InternalOrderStatus
    broker_order_id: str | None = None
    temporal_workflow_id: str | None = None
    is_entry_order: bool = True

    @field_validator("symbol")
    @classmethod
    def validate_symbol(cls, symbol: str) -> str:
        if symbol != symbol.upper():
            raise ValueError("symbol must be uppercase")
        return symbol

    @model_validator(mode="after")
    def validate_fill_quantity(self) -> Self:
        if self.filled_quantity > self.quantity:
            raise ValueError("filled_quantity cannot exceed quantity")
        return self


class InternalFill(ReconciliationModel):
    broker_order_id: str
    client_order_id: str
    symbol: str
    quantity: float = Field(gt=0)
    price: float = Field(gt=0)
    filled_at: datetime

    @field_validator("symbol")
    @classmethod
    def validate_symbol(cls, symbol: str) -> str:
        if symbol != symbol.upper():
            raise ValueError("symbol must be uppercase")
        return symbol

    @model_validator(mode="after")
    def validate_filled_at(self) -> Self:
        if self.filled_at.tzinfo is None:
            raise ValueError("filled_at must be timezone-aware")
        return self


class InternalPosition(ReconciliationModel):
    symbol: str
    quantity: float = Field(gt=0)
    avg_entry_price: float = Field(gt=0)
    opened_at: datetime | None = None
    protective_stop_client_order_id: str | None = None
    temporal_workflow_id: str | None = None

    @field_validator("symbol")
    @classmethod
    def validate_symbol(cls, symbol: str) -> str:
        if symbol != symbol.upper():
            raise ValueError("symbol must be uppercase")
        return symbol

    @model_validator(mode="after")
    def validate_opened_at(self) -> Self:
        if self.opened_at is not None and self.opened_at.tzinfo is None:
            raise ValueError("opened_at must be timezone-aware")
        return self


class InternalLedgerSnapshot(ReconciliationModel):
    account: InternalAccountSnapshot
    orders: tuple[InternalOrder, ...] = ()
    fills: tuple[InternalFill, ...] = ()
    positions: tuple[InternalPosition, ...] = ()
    order_workflow_status_by_client_order_id: dict[str, str] = Field(default_factory=dict)
    position_workflow_status_by_symbol: dict[str, str] = Field(default_factory=dict)
    as_of: datetime

    @model_validator(mode="after")
    def validate_as_of(self) -> Self:
        if self.as_of.tzinfo is None:
            raise ValueError("as_of must be timezone-aware")
        return self


class ReconciliationMismatch(ReconciliationModel):
    mismatch_type: ReconciliationMismatchType
    severity: IncidentSeverity
    symbol: str | None = None
    client_order_id: str | None = None
    broker_order_id: str | None = None
    message: str
    details: dict[str, str] = Field(default_factory=dict)


class ReconciliationIncident(ReconciliationModel):
    incident_key: str
    severity: IncidentSeverity
    recommended_action: IncidentActionRecommendation
    pause_new_risk: bool
    risk_reducing_exits_allowed: bool = True
    reason_code: ReconciliationMismatchType
    message: str
    details: dict[str, str] = Field(default_factory=dict)


class ReconciliationResult(ReconciliationModel):
    broker_snapshot: BrokerSnapshot
    internal_snapshot: InternalLedgerSnapshot
    mismatches: tuple[ReconciliationMismatch, ...]
    incidents: tuple[ReconciliationIncident, ...]

    @property
    def clean(self) -> bool:
        return not self.mismatches

    @property
    def broker_reconciliation_clean(self) -> bool:
        return self.clean

    @property
    def pause_new_risk_recommended(self) -> bool:
        return any(incident.pause_new_risk for incident in self.incidents)
