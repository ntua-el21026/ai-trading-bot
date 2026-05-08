from __future__ import annotations

import asyncio
from collections.abc import Iterator
from datetime import UTC, date, datetime

import pytest

from apps.workers.app.activities.reporting import (
    BuildDashboardSnapshotRequest,
    DispatchAlertRequest,
    GenerateDailyReportRequest,
    ReportingActivityContext,
    ReportingActivityResult,
    ReportingActivityService,
    build_dashboard_snapshot,
    configure_reporting_activity_service_for_tests,
    dispatch_alert,
    dispatch_incident_alert,
    dispatch_report_alert,
    generate_daily_report,
    reset_reporting_activity_service_for_tests,
)
from apps.workers.app.types import ActivityPlaceholderInput
from packages.alerting.adapters import FakeAlertAdapter
from packages.alerting.models import AlertMessage
from packages.alerting.routing import AlertRouter
from packages.ledger.connection import connect_in_memory_sqlite
from packages.ledger.repositories import SQLiteLedgerRepository

NOW = datetime(2026, 5, 6, 12, 0, tzinfo=UTC)


@pytest.fixture
def repository() -> SQLiteLedgerRepository:
    return SQLiteLedgerRepository(connect_in_memory_sqlite())


@pytest.fixture
def fake_alert_adapter() -> FakeAlertAdapter:
    return FakeAlertAdapter()


@pytest.fixture(autouse=True)
def configured_reporting_service(
    repository: SQLiteLedgerRepository,
    fake_alert_adapter: FakeAlertAdapter,
) -> Iterator[None]:
    service = ReportingActivityService(
        repository,
        alert_router=AlertRouter(adapters=(fake_alert_adapter,)),
    )
    configure_reporting_activity_service_for_tests(service)
    yield
    reset_reporting_activity_service_for_tests()


def _context() -> ReportingActivityContext:
    return ReportingActivityContext(
        workflow_name="ReportingWorkflow",
        purpose="unit-test",
        request_id="request-1",
        occurred_at=NOW,
    )


def _alert() -> AlertMessage:
    return AlertMessage(
        category="report_generated",
        severity="info",
        title="Daily report generated",
        body="A dry-run report was generated.",
        source_component="reporting_activity",
        created_at=NOW,
        related_entity_type="report",
        related_entity_id="report-1",
    )


def test_generate_daily_report_activity_persists_report(
    repository: SQLiteLedgerRepository,
) -> None:
    result = asyncio.run(
        generate_daily_report(
            GenerateDailyReportRequest(
                context=_context(),
                report_date=date(2026, 5, 6),
            )
        )
    )

    assert result.status == "generated"
    assert result.external_calls_performed is False
    assert result.records_written == 1
    assert result.record_ids
    assert repository.get_report(result.record_ids[0]) is not None
    assert result.payload["report"]["report_type"] == "daily"
    assert "Daily Report - Dry Run" in result.payload["telegram_summary"]


def test_generate_daily_report_activity_accepts_placeholder_workflow_input() -> None:
    result = asyncio.run(
        generate_daily_report(
            ActivityPlaceholderInput(
                workflow_name="ReportingWorkflow",
                purpose="scheduled",
            )
        )
    )

    assert result.activity_name == "generate_daily_report"
    assert result.status == "generated"
    assert result.details["external_calls"] == "none"


def test_alert_dispatch_activities_capture_messages_without_external_delivery(
    fake_alert_adapter: FakeAlertAdapter,
) -> None:
    request = DispatchAlertRequest(context=_context(), message=_alert())

    results = asyncio.run(
        _dispatch_all(request),
    )

    assert [result.activity_name for result in results] == [
        "dispatch_alert",
        "dispatch_incident_alert",
        "dispatch_report_alert",
    ]
    assert all(result.status == "dispatched" for result in results)
    assert all(result.external_calls_performed is False for result in results)
    assert len(fake_alert_adapter.messages) == 3


def test_build_dashboard_snapshot_activity_reads_ledger_only() -> None:
    result = asyncio.run(
        build_dashboard_snapshot(BuildDashboardSnapshotRequest(context=_context()))
    )

    assert result.status == "read"
    assert result.external_calls_performed is False
    dashboard = result.payload["dashboard_snapshot"]
    assert dashboard["system_state"]["data_source"] == "database_read_model"
    assert dashboard["system_state"]["live_trading_enabled"] is False
    assert dashboard["risk_status"]["new_risk_allowed"] is False


async def _dispatch_all(
    request: DispatchAlertRequest,
) -> tuple[ReportingActivityResult, ReportingActivityResult, ReportingActivityResult]:
    return await asyncio.gather(
        dispatch_alert(request),
        dispatch_incident_alert(request),
        dispatch_report_alert(request),
    )
