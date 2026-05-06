"""Report contracts for local/fake operational reporting."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

ReportType = Literal["daily", "weekly"]
ReportStatus = Literal["not_operational", "dry_run", "paper", "live_disabled"]
ReportIssueSeverity = Literal["info", "warning", "critical"]


class ReportingModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ReportMetric(ReportingModel):
    name: str
    value: str | int | float | bool | None
    unit: str | None = None
    status: str | None = None


class ReportIssue(ReportingModel):
    severity: ReportIssueSeverity
    message: str
    follow_up: str | None = None
    related_entity_id: str | None = None


class ReportSection(ReportingModel):
    title: str
    status: str = "not_operational"
    metrics: tuple[ReportMetric, ...] = ()
    issues: tuple[ReportIssue, ...] = ()
    payload: dict[str, Any] = Field(default_factory=dict)


class ReportInputSnapshot(ReportingModel):
    generated_at: datetime
    environment: Literal["paper", "live"] = "paper"
    dry_run: bool = True
    live_trading_enabled: bool = False
    autonomous_execution_enabled: bool = False
    workflow_statuses: tuple[dict[str, Any], ...] = ()
    candidates: tuple[dict[str, Any], ...] = ()
    ai_outputs: tuple[dict[str, Any], ...] = ()
    decisions: tuple[dict[str, Any], ...] = ()
    risk_checks: tuple[dict[str, Any], ...] = ()
    execution_intents: tuple[dict[str, Any], ...] = ()
    orders: tuple[dict[str, Any], ...] = ()
    fills: tuple[dict[str, Any], ...] = ()
    positions: tuple[dict[str, Any], ...] = ()
    reconciliations: tuple[dict[str, Any], ...] = ()
    incidents: tuple[dict[str, Any], ...] = ()
    reports: tuple[dict[str, Any], ...] = ()
    risk_payload: dict[str, Any] = Field(default_factory=dict)
    operational_gaps: tuple[str, ...] = ()

    @model_validator(mode="after")
    def validate_snapshot(self) -> Self:
        _require_aware(self.generated_at, "generated_at")
        if self.environment == "paper" and self.live_trading_enabled:
            raise ValueError("paper reports cannot show live_trading_enabled=true")
        return self


class DailyReport(ReportingModel):
    report_type: Literal["daily"] = "daily"
    report_date: date
    generated_at: datetime
    status: ReportStatus
    sections: tuple[ReportSection, ...]
    open_follow_ups: tuple[ReportIssue, ...] = ()

    @model_validator(mode="after")
    def validate_generated_at(self) -> Self:
        _require_aware(self.generated_at, "generated_at")
        return self


class WeeklyReport(ReportingModel):
    report_type: Literal["weekly"] = "weekly"
    period_start: date
    period_end: date
    generated_at: datetime
    status: ReportStatus
    sections: tuple[ReportSection, ...]
    open_follow_ups: tuple[ReportIssue, ...] = ()

    @model_validator(mode="after")
    def validate_weekly_report(self) -> Self:
        _require_aware(self.generated_at, "generated_at")
        if self.period_end < self.period_start:
            raise ValueError("period_end cannot be before period_start")
        return self


class ReportGenerationResult(ReportingModel):
    report: DailyReport | WeeklyReport
    markdown: str
    payload: dict[str, Any]
    persisted_report_id: str | None = None
    external_calls_performed: bool = False

    @field_validator("markdown")
    @classmethod
    def validate_markdown(cls, markdown: str) -> str:
        if not markdown.strip():
            raise ValueError("markdown report cannot be empty")
        return markdown


def _require_aware(value: datetime, field_name: str) -> None:
    if value.tzinfo is None:
        raise ValueError(f"{field_name} must be timezone-aware")
