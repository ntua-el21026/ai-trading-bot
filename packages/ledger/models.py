"""Typed audit-ledger records returned by repository implementations."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

JsonPayload = dict[str, Any] | list[Any] | str | int | float | bool | None


class LedgerModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class RawProviderPayloadRecord(LedgerModel):
    raw_provider_payload_id: str
    provider: str
    endpoint: str
    symbol: str | None
    payload_hash: str
    raw_payload: JsonPayload
    content_type: str
    received_at: datetime


class AIResearchOutputRecord(LedgerModel):
    output_id: str
    symbol: str
    prompt_version: str
    schema_version: str
    model_version: str
    raw_prompt: str
    raw_prompt_hash: str
    raw_output: str | None
    raw_output_hash: str | None
    parsed_output: dict[str, Any]
    ai_score: int = Field(ge=10, le=90)
    hard_block: bool
    fallback_reason: str
    citations: tuple[str, ...]
    canonical_urls: tuple[str, ...]
    created_at: datetime


class ExecutionIntentRecord(LedgerModel):
    execution_intent_id: str
    temporal_workflow_id: str | None
    decision_id: str
    client_order_id_root: str
    symbol: str
    side: Literal["buy", "sell"]
    asset_class: Literal["equity", "etf"]
    quantity: int = Field(gt=0)
    entry_order_type: Literal["limit"]
    limit_price: float = Field(gt=0)
    stop_loss_price: float | None = Field(default=None, gt=0)
    time_in_force: Literal["day"]
    strategy_version: str
    risk_config_version: str
    autonomy_level: int = Field(ge=0, le=5)
    requires_protective_stop: bool
    max_acceptable_slippage_bps: int = Field(ge=0)
    status: str
    payload: dict[str, Any]
    expires_at: datetime
    created_at: datetime


class OrderRecord(LedgerModel):
    order_id: str
    execution_intent_id: str | None
    broker_order_id: str | None
    client_order_id: str
    symbol: str
    side: Literal["buy", "sell"]
    order_type: str
    time_in_force: str
    quantity: float = Field(gt=0)
    limit_price: float | None = Field(default=None, gt=0)
    stop_price: float | None = Field(default=None, gt=0)
    status: str
    raw_broker_payload: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class FillRecord(LedgerModel):
    fill_id: str
    order_id: str
    broker_order_id: str | None
    broker_fill_id: str | None
    symbol: str
    quantity: float = Field(gt=0)
    price: float = Field(gt=0)
    filled_at: datetime
    raw_broker_payload: dict[str, Any]
    created_at: datetime


class PositionRecord(LedgerModel):
    position_id: str
    symbol: str
    quantity: float
    average_entry_price: float = Field(gt=0)
    status: str
    protective_stop_order_id: str | None
    opened_at: datetime | None
    closed_at: datetime | None
    raw_source_payload: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class BrokerReconciliationRecord(LedgerModel):
    reconciliation_id: str
    temporal_workflow_id: str | None
    account_snapshot: dict[str, Any]
    broker_positions: list[Any]
    internal_positions: list[Any]
    broker_orders: list[Any]
    internal_orders: list[Any]
    mismatches: list[Any]
    status: str
    created_at: datetime


class SystemEventRecord(LedgerModel):
    event_id: str
    event_type: str
    severity: Literal["info", "warning", "critical"]
    source_component: str
    related_entity_type: str | None
    related_entity_id: str | None
    message: str
    payload: dict[str, Any]
    created_at: datetime
    acknowledged_at: datetime | None


class ReportRecord(LedgerModel):
    report_id: str
    report_type: str
    report_date: date | None
    period_start: date | None
    period_end: date | None
    status: str
    payload: dict[str, Any]
    markdown: str | None
    created_at: datetime
