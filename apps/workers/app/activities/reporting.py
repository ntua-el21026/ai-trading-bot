"""Reporting, alerting, and dashboard read-model Temporal activity contracts."""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator
from temporalio import activity

from apps.workers.app.types import ActivityPlaceholderInput
from packages.alerting.models import AlertMessage
from packages.alerting.routing import AlertRouter
from packages.control_plane.service import LedgerDashboardReadModelProvider
from packages.ledger.connection import connect_in_memory_sqlite
from packages.ledger.repositories import SQLiteLedgerRepository
from packages.reporting.generators import default_week_bounds
from packages.reporting.generators import generate_daily_report as build_daily_report
from packages.reporting.generators import generate_weekly_report as build_weekly_report
from packages.reporting.ledger import (
    build_report_input_snapshot,
    persist_report_generation_result,
)

ReportingActivityStatus = Literal["generated", "dispatched", "read"]


class ReportingActivityModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ReportingActivityContext(ReportingActivityModel):
    workflow_name: str
    purpose: str
    request_id: str | None = None
    occurred_at: datetime | None = None

    @model_validator(mode="after")
    def validate_occurred_at(self) -> Self:
        if self.occurred_at is not None and self.occurred_at.tzinfo is None:
            raise ValueError("occurred_at must be timezone-aware")
        return self


class ReportingActivityResult(ReportingActivityModel):
    activity_name: str
    status: ReportingActivityStatus
    external_calls_performed: bool = False
    records_written: int = Field(default=0, ge=0)
    record_ids: tuple[str, ...] = ()
    payload: dict[str, Any] = Field(default_factory=dict)
    details: dict[str, str] = Field(default_factory=dict)


class GenerateDailyReportRequest(ReportingActivityModel):
    context: ReportingActivityContext
    report_date: date | None = None
    persist: bool = True


class GenerateWeeklyReportRequest(ReportingActivityModel):
    context: ReportingActivityContext
    period_start: date | None = None
    period_end: date | None = None
    persist: bool = True


class DispatchAlertRequest(ReportingActivityModel):
    context: ReportingActivityContext
    message: AlertMessage


class BuildDashboardSnapshotRequest(ReportingActivityModel):
    context: ReportingActivityContext


class ReportingActivityService:
    def __init__(
        self,
        repository: SQLiteLedgerRepository,
        *,
        alert_router: AlertRouter | None = None,
    ) -> None:
        self._repository = repository
        self._alert_router = alert_router or AlertRouter()

    def generate_daily_report(
        self,
        request: GenerateDailyReportRequest | ActivityPlaceholderInput,
    ) -> ReportingActivityResult:
        request = _daily_request(request)
        generated_at = request.context.occurred_at or _utc_now()
        snapshot = build_report_input_snapshot(self._repository, generated_at=generated_at)
        result = build_daily_report(
            report_date=request.report_date or generated_at.date(),
            snapshot=snapshot,
        )
        if request.persist:
            result = persist_report_generation_result(self._repository, result)
        return _result(
            "generate_daily_report",
            request.context,
            "generated",
            records_written=1 if result.persisted_report_id else 0,
            record_ids=(
                () if result.persisted_report_id is None else (result.persisted_report_id,)
            ),
            payload={
                "report": result.payload,
                "markdown": result.markdown,
                "persisted_report_id": result.persisted_report_id,
            },
        )

    def generate_weekly_report(
        self,
        request: GenerateWeeklyReportRequest,
    ) -> ReportingActivityResult:
        generated_at = request.context.occurred_at or _utc_now()
        start, end = (
            (request.period_start, request.period_end)
            if request.period_start is not None and request.period_end is not None
            else default_week_bounds(generated_at.date())
        )
        snapshot = build_report_input_snapshot(self._repository, generated_at=generated_at)
        result = build_weekly_report(period_start=start, period_end=end, snapshot=snapshot)
        if request.persist:
            result = persist_report_generation_result(self._repository, result)
        return _result(
            "generate_weekly_report",
            request.context,
            "generated",
            records_written=1 if result.persisted_report_id else 0,
            record_ids=(
                () if result.persisted_report_id is None else (result.persisted_report_id,)
            ),
            payload={
                "report": result.payload,
                "markdown": result.markdown,
                "persisted_report_id": result.persisted_report_id,
            },
        )

    def dispatch_alert(
        self,
        activity_name: str,
        request: DispatchAlertRequest,
    ) -> ReportingActivityResult:
        dispatch_results = self._alert_router.dispatch(request.message)
        return _result(
            activity_name,
            request.context,
            "dispatched",
            payload={
                "dispatch_results": [
                    result.model_dump(mode="json") for result in dispatch_results
                ]
            },
        )

    def build_dashboard_snapshot(
        self,
        request: BuildDashboardSnapshotRequest,
    ) -> ReportingActivityResult:
        snapshot = LedgerDashboardReadModelProvider(self._repository).snapshot()
        return _result(
            "build_dashboard_snapshot",
            request.context,
            "read",
            payload={"dashboard_snapshot": snapshot.model_dump(mode="json")},
        )


def build_in_memory_reporting_activity_service() -> ReportingActivityService:
    return ReportingActivityService(SQLiteLedgerRepository(connect_in_memory_sqlite()))


_reporting_activity_service = build_in_memory_reporting_activity_service()


def configure_reporting_activity_service_for_tests(service: ReportingActivityService) -> None:
    global _reporting_activity_service
    _reporting_activity_service = service


def reset_reporting_activity_service_for_tests() -> None:
    configure_reporting_activity_service_for_tests(build_in_memory_reporting_activity_service())


@activity.defn(name="generate_daily_report")
async def generate_daily_report(
    payload: GenerateDailyReportRequest | ActivityPlaceholderInput,
) -> ReportingActivityResult:
    return _reporting_activity_service.generate_daily_report(payload)


@activity.defn(name="generate_weekly_report")
async def generate_weekly_report(payload: GenerateWeeklyReportRequest) -> ReportingActivityResult:
    return _reporting_activity_service.generate_weekly_report(payload)


@activity.defn(name="dispatch_alert")
async def dispatch_alert(payload: DispatchAlertRequest) -> ReportingActivityResult:
    return _reporting_activity_service.dispatch_alert("dispatch_alert", payload)


@activity.defn(name="dispatch_incident_alert")
async def dispatch_incident_alert(payload: DispatchAlertRequest) -> ReportingActivityResult:
    return _reporting_activity_service.dispatch_alert("dispatch_incident_alert", payload)


@activity.defn(name="dispatch_report_alert")
async def dispatch_report_alert(payload: DispatchAlertRequest) -> ReportingActivityResult:
    return _reporting_activity_service.dispatch_alert("dispatch_report_alert", payload)


@activity.defn(name="build_dashboard_snapshot")
async def build_dashboard_snapshot(
    payload: BuildDashboardSnapshotRequest,
) -> ReportingActivityResult:
    return _reporting_activity_service.build_dashboard_snapshot(payload)


REPORTING_ACTIVITY_FUNCTIONS = (
    generate_daily_report,
    generate_weekly_report,
    dispatch_alert,
    dispatch_incident_alert,
    dispatch_report_alert,
    build_dashboard_snapshot,
)


def _result(
    activity_name: str,
    context: ReportingActivityContext,
    status: ReportingActivityStatus,
    *,
    records_written: int = 0,
    record_ids: tuple[str, ...] = (),
    payload: dict[str, Any] | None = None,
) -> ReportingActivityResult:
    return ReportingActivityResult(
        activity_name=activity_name,
        status=status,
        external_calls_performed=False,
        records_written=records_written,
        record_ids=record_ids,
        payload=payload or {},
        details={
            "workflow_name": context.workflow_name,
            "purpose": context.purpose,
            "external_calls": "none",
        },
    )


def _daily_request(
    payload: GenerateDailyReportRequest | ActivityPlaceholderInput,
) -> GenerateDailyReportRequest:
    if isinstance(payload, GenerateDailyReportRequest):
        return payload
    return GenerateDailyReportRequest(
        context=ReportingActivityContext(
            workflow_name=payload.workflow_name,
            purpose=payload.purpose,
        )
    )


def _utc_now() -> datetime:
    return datetime.now(UTC)
