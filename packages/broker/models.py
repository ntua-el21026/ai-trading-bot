"""Normalized broker-side contracts.

These models are passive data contracts. They do not open network connections or submit orders.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from packages.data.models import AssetClass

REST_FALLBACK_INTERVAL_SECONDS = 30

BrokerEnvironment = Literal["paper", "live"]
BrokerSide = Literal["buy", "sell"]
BrokerOrderType = Literal["market", "limit", "stop", "stop_limit"]
BrokerTimeInForce = Literal["day", "gtc", "ioc", "fok"]
BrokerOrderStatus = Literal[
    "new",
    "accepted",
    "pending_new",
    "partially_filled",
    "filled",
    "pending_cancel",
    "cancelled",
    "expired",
    "rejected",
    "replaced",
    "stopped",
    "unknown",
]
BrokerOrderPurpose = Literal["entry", "protective_stop", "risk_reducing_exit", "unknown"]
BrokerStreamEventType = Literal[
    "order_acknowledged",
    "partial_fill",
    "fill",
    "cancelled",
    "rejected",
    "expired",
    "replaced",
    "unknown",
]
BrokerErrorCode = Literal[
    "missing_credentials",
    "non_paper_environment",
    "attempted_live_mode",
    "order_not_found",
    "duplicate_client_order_id",
    "broker_timeout",
    "ambiguous_broker_state",
    "rejected_order",
    "partial_fill",
    "missing_protective_stop",
    "stream_disconnect",
    "rest_fallback_unavailable",
    "unsupported_order_type",
    "invalid_order_request",
    "client_not_configured",
]
BrokerOperationStatus = Literal["succeeded", "failed", "ambiguous", "not_found", "noop"]

OPEN_ORDER_STATUSES: frozenset[BrokerOrderStatus] = frozenset(
    {"new", "accepted", "pending_new", "partially_filled", "pending_cancel", "replaced"}
)
SUPPORTED_BROKER_ASSET_CLASSES: frozenset[AssetClass] = frozenset({"equity", "etf"})


class BrokerModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class BrokerAccountSnapshot(BrokerModel):
    account_id: str
    environment: BrokerEnvironment
    equity: float = Field(gt=0)
    cash: float = Field(ge=0)
    buying_power: float | None = Field(default=None, ge=0)
    currency: str = "USD"
    as_of: datetime
    raw_payload_hash: str | None = None

    @field_validator("currency")
    @classmethod
    def validate_currency(cls, currency: str) -> str:
        if currency != currency.upper():
            raise ValueError("currency must be uppercase")
        return currency

    @model_validator(mode="after")
    def validate_timestamp(self) -> Self:
        if self.as_of.tzinfo is None:
            raise ValueError("as_of must be timezone-aware")
        return self


class BrokerOrder(BrokerModel):
    broker_order_id: str
    client_order_id: str
    symbol: str
    side: BrokerSide
    asset_class: AssetClass
    quantity: float = Field(gt=0)
    filled_quantity: float = Field(default=0.0, ge=0)
    order_type: BrokerOrderType
    time_in_force: BrokerTimeInForce
    status: BrokerOrderStatus
    submitted_at: datetime | None = None
    updated_at: datetime | None = None
    limit_price: float | None = Field(default=None, gt=0)
    stop_price: float | None = Field(default=None, gt=0)
    purpose: BrokerOrderPurpose = "unknown"
    raw_payload_hash: str | None = None

    @field_validator("symbol")
    @classmethod
    def validate_symbol(cls, symbol: str) -> str:
        if symbol != symbol.upper():
            raise ValueError("symbol must be uppercase")
        return symbol

    @model_validator(mode="after")
    def validate_order(self) -> Self:
        if self.filled_quantity > self.quantity:
            raise ValueError("filled_quantity cannot exceed quantity")
        for field_name in ("submitted_at", "updated_at"):
            timestamp = getattr(self, field_name)
            if timestamp is not None and timestamp.tzinfo is None:
                raise ValueError(f"{field_name} must be timezone-aware")
        if self.order_type in {"stop", "stop_limit"} and self.stop_price is None:
            raise ValueError("stop orders require stop_price")
        return self

    @property
    def is_open(self) -> bool:
        return self.status in OPEN_ORDER_STATUSES


class BrokerFill(BrokerModel):
    broker_order_id: str
    client_order_id: str
    symbol: str
    side: BrokerSide
    quantity: float = Field(gt=0)
    price: float = Field(gt=0)
    filled_at: datetime
    broker_fill_id: str | None = None
    raw_payload_hash: str | None = None

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


class BrokerPosition(BrokerModel):
    symbol: str
    asset_class: AssetClass
    quantity: float
    avg_entry_price: float = Field(gt=0)
    market_value: float | None = None
    opened_at: datetime | None = None
    raw_payload_hash: str | None = None

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


class BrokerProtectiveStop(BrokerModel):
    broker_order_id: str
    client_order_id: str
    symbol: str
    quantity: float = Field(gt=0)
    stop_price: float = Field(gt=0)
    status: BrokerOrderStatus
    confirmed: bool
    submitted_at: datetime | None = None
    updated_at: datetime | None = None
    raw_payload_hash: str | None = None

    @field_validator("symbol")
    @classmethod
    def validate_symbol(cls, symbol: str) -> str:
        if symbol != symbol.upper():
            raise ValueError("symbol must be uppercase")
        return symbol

    @model_validator(mode="after")
    def validate_stop_timestamps(self) -> Self:
        for field_name in ("submitted_at", "updated_at"):
            timestamp = getattr(self, field_name)
            if timestamp is not None and timestamp.tzinfo is None:
                raise ValueError(f"{field_name} must be timezone-aware")
        return self

    @property
    def is_open(self) -> bool:
        return self.status in OPEN_ORDER_STATUSES


class BrokerStreamEvent(BrokerModel):
    event_type: BrokerStreamEventType
    broker_order: BrokerOrder
    fill: BrokerFill | None = None
    event_at: datetime
    raw_payload_hash: str

    @model_validator(mode="after")
    def validate_event_at(self) -> Self:
        if self.event_at.tzinfo is None:
            raise ValueError("event_at must be timezone-aware")
        if self.event_type in {"partial_fill", "fill"} and self.fill is None:
            raise ValueError("fill events require fill details")
        return self


class BrokerSnapshot(BrokerModel):
    account: BrokerAccountSnapshot
    open_orders: tuple[BrokerOrder, ...] = ()
    recent_fills: tuple[BrokerFill, ...] = ()
    positions: tuple[BrokerPosition, ...] = ()
    protective_stops: tuple[BrokerProtectiveStop, ...] = ()
    as_of: datetime
    source: Literal["stream", "rest_fallback", "fixture"] = "fixture"

    @model_validator(mode="after")
    def validate_snapshot_timestamp(self) -> Self:
        if self.as_of.tzinfo is None:
            raise ValueError("as_of must be timezone-aware")
        return self


class BrokerRestFallbackSnapshot(BrokerSnapshot):
    source: Literal["rest_fallback"] = "rest_fallback"
    poll_interval_seconds: int = REST_FALLBACK_INTERVAL_SECONDS

    @model_validator(mode="after")
    def validate_poll_interval(self) -> Self:
        if self.poll_interval_seconds != REST_FALLBACK_INTERVAL_SECONDS:
            raise ValueError("REST fallback polling interval must be 30 seconds")
        return self


class BrokerOperationError(BrokerModel):
    code: BrokerErrorCode
    message: str
    retryable: bool = False
    ambiguous: bool = False
    pause_new_risk: bool = False
    details: dict[str, str] = Field(default_factory=dict)


class BrokerOrderOperationResult(BrokerModel):
    operation: str
    status: BrokerOperationStatus
    order: BrokerOrder | None = None
    error: BrokerOperationError | None = None
    idempotency_reused: bool = False
    protective_stop_required_quantity: float | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    def validate_order_result(self) -> Self:
        if self.status == "succeeded" and self.order is None:
            raise ValueError("successful broker order operation requires order")
        if self.status in {"failed", "ambiguous", "not_found"} and self.error is None:
            raise ValueError("failed broker order operation requires structured error")
        if self.error is not None and self.status == "succeeded":
            raise ValueError("successful broker order operation cannot include error")
        return self


class BrokerProtectiveStopVerificationResult(BrokerModel):
    symbol: str
    required_quantity: float = Field(gt=0)
    protected: bool
    stop: BrokerProtectiveStop | None = None
    status: BrokerOperationStatus
    error: BrokerOperationError | None = None

    @field_validator("symbol")
    @classmethod
    def validate_symbol(cls, symbol: str) -> str:
        if symbol != symbol.upper():
            raise ValueError("symbol must be uppercase")
        return symbol

    @model_validator(mode="after")
    def validate_stop_result(self) -> Self:
        if self.protected and self.stop is None:
            raise ValueError("protected result requires stop")
        if not self.protected and self.error is None:
            raise ValueError("unprotected result requires structured error")
        return self


class BrokerStreamConnectionResult(BrokerModel):
    connected: bool
    events: tuple[BrokerStreamEvent, ...] = ()
    error: BrokerOperationError | None = None

    @model_validator(mode="after")
    def validate_stream_result(self) -> Self:
        if not self.connected and self.error is None:
            raise ValueError("disconnected stream result requires structured error")
        return self


class BrokerRestFallbackStatus(BrokerModel):
    available: bool
    poll_interval_seconds: int = REST_FALLBACK_INTERVAL_SECONDS
    error: BrokerOperationError | None = None

    @model_validator(mode="after")
    def validate_fallback_status(self) -> Self:
        if self.poll_interval_seconds != REST_FALLBACK_INTERVAL_SECONDS:
            raise ValueError("REST fallback polling interval must be 30 seconds")
        if not self.available and self.error is None:
            raise ValueError("unavailable REST fallback requires structured error")
        return self
