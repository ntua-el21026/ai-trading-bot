"""Alerting contracts for fake-safe notification dispatch."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

AlertSeverity = Literal["info", "warning", "critical"]
AlertChannel = Literal["fake", "telegram", "email"]
AlertCategory = Literal[
    "order_notification",
    "fill_notification",
    "exit_notification",
    "protective_stop_warning",
    "protective_stop_critical",
    "missing_protective_stop",
    "reconciliation_mismatch",
    "duplicate_order_or_intent",
    "stale_data",
    "invalid_ai_payload",
    "repeated_invalid_ai_payloads",
    "kill_switch_activation",
    "worker_unavailable",
    "broker_ambiguity",
    "report_generated",
    "manual_control_action",
]
AlertDispatchStatus = Literal["sent", "captured", "failed_closed"]


class AlertModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class AlertMessage(AlertModel):
    category: AlertCategory
    severity: AlertSeverity
    title: str
    body: str
    source_component: str
    created_at: datetime
    related_entity_type: str | None = None
    related_entity_id: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)

    @field_validator("title", "body", "source_component")
    @classmethod
    def validate_non_empty(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("alert text fields cannot be blank")
        return value

    @model_validator(mode="after")
    def validate_created_at(self) -> Self:
        if self.created_at.tzinfo is None:
            raise ValueError("created_at must be timezone-aware")
        return self


class AlertDispatchRequest(AlertModel):
    message: AlertMessage
    channels: tuple[AlertChannel, ...]

    @model_validator(mode="after")
    def validate_channels(self) -> Self:
        if not self.channels:
            raise ValueError("at least one alert channel is required")
        return self


class AlertDispatchResult(AlertModel):
    status: AlertDispatchStatus
    channel: AlertChannel
    message: AlertMessage
    external_calls_performed: bool = False
    provider_message_id: str | None = None
    error_message: str | None = None

    @model_validator(mode="after")
    def validate_dispatch_result(self) -> Self:
        if self.status == "failed_closed" and not self.error_message:
            raise ValueError("failed-closed alert dispatch requires error_message")
        if self.external_calls_performed and self.channel == "fake":
            raise ValueError("fake alert adapter cannot perform external calls")
        return self
