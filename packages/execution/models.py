"""Passive execution-core models.

These models describe intent and lifecycle state only. They do not submit broker orders.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from packages.data.models import AssetClass

ExecutionSide = Literal["buy", "sell"]
EntryOrderType = Literal["limit"]
TimeInForce = Literal["day"]
ExecutionIntentStatus = Literal[
    "created",
    "risk_approved",
    "rejected",
    "expired",
    "submitted_to_workflow",
    "cancelled",
]
OrderLifecycleStatus = Literal[
    "created",
    "risk_checked",
    "ready_for_broker_adapter",
    "submitted",
    "acknowledged",
    "partially_filled",
    "filled",
    "protective_stop_pending",
    "protected",
    "cancelled",
    "rejected",
    "expired",
    "manual_review_required",
]


class ExecutionModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ExecutionIntent(ExecutionModel):
    decision_id: UUID
    symbol: str
    side: ExecutionSide
    asset_class: AssetClass
    quantity: int = Field(gt=0)
    entry_order_type: EntryOrderType
    limit_price: float = Field(gt=0)
    stop_loss_price: float | None = Field(default=None, gt=0)
    time_in_force: TimeInForce
    strategy_version: str
    risk_config_version: str
    autonomy_level: int = Field(ge=0, le=5)
    requires_protective_stop: bool
    max_acceptable_slippage_bps: int = Field(ge=0)
    expires_at: datetime
    client_order_id_root: str
    status: ExecutionIntentStatus = "created"
    temporal_workflow_id: str | None = None

    @field_validator("symbol")
    @classmethod
    def validate_symbol(cls, symbol: str) -> str:
        if symbol != symbol.upper():
            raise ValueError("symbol must be uppercase")
        return symbol

    @model_validator(mode="after")
    def validate_execution_intent(self) -> Self:
        if self.asset_class not in {"equity", "etf"}:
            raise ValueError("v0.1 execution intents support equities and ETFs only")
        if self.entry_order_type != "limit":
            raise ValueError("new-risk entries must use limit orders")
        if self.time_in_force != "day":
            raise ValueError("new-risk entries must use day time-in-force")
        if self.expires_at.tzinfo is None:
            raise ValueError("expires_at must be timezone-aware")
        if self.requires_protective_stop:
            if self.stop_loss_price is None:
                raise ValueError("protective stop is required")
            if self.side == "buy" and self.stop_loss_price >= self.limit_price:
                raise ValueError("buy intent stop loss must be below limit price")
        if not self.client_order_id_root:
            raise ValueError("client_order_id_root is required")
        return self


class DuplicateIntentKey(ExecutionModel):
    symbol: str
    side: ExecutionSide
    trade_date: date
    strategy_version: str


class ExecutionRejection(ExecutionModel):
    reason_code: str
    message: str
    severity: Literal["warning", "critical"] = "critical"
    details: dict[str, str] = Field(default_factory=dict)


class OrderLifecycleState(ExecutionModel):
    client_order_id: str
    status: OrderLifecycleStatus = "created"
    history: tuple[OrderLifecycleStatus, ...] = ("created",)


class OrderLifecycleTransitionResult(ExecutionModel):
    accepted: bool
    state: OrderLifecycleState
    rejection: ExecutionRejection | None = None

