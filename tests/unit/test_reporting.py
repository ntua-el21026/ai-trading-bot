from __future__ import annotations

from datetime import UTC, date, datetime
from typing import cast

from packages.ledger.connection import connect_in_memory_sqlite
from packages.ledger.repositories import SQLiteLedgerRepository
from packages.reporting.generators import (
    default_week_bounds,
    generate_daily_report,
    generate_weekly_report,
)
from packages.reporting.ledger import (
    build_report_input_snapshot,
    persist_report_generation_result,
)
from packages.reporting.models import ReportInputSnapshot, WeeklyReport
from packages.reporting.renderers import render_report_markdown

GENERATED_AT = datetime(2026, 5, 6, 20, 0, tzinfo=UTC)


def _snapshot() -> ReportInputSnapshot:
    return ReportInputSnapshot(
        generated_at=GENERATED_AT,
        environment="paper",
        dry_run=True,
        live_trading_enabled=False,
        autonomous_execution_enabled=False,
        candidates=(
            {
                "symbol": "AAPL",
                "candidate_status": "accepted",
                "technical_score": 80,
            },
        ),
        ai_outputs=(
            {
                "symbol": "AAPL",
                "ai_score": 50,
                "hard_block": False,
                "fallback_reason": "no_news_found",
            },
        ),
        decisions=({"symbol": "AAPL", "decision_status": "rejected"},),
        risk_checks=({"symbol": "AAPL", "passed": False},),
        orders=({"status": "accepted"},),
        fills=({"price": 180.0, "slippage_bps": 4.5},),
        positions=({"symbol": "AAPL", "status": "open"},),
        reconciliations=({"status": "mismatched", "mismatches": [{"type": "position"}]},),
        incidents=({"severity": "critical", "message": "missing stop"},),
        operational_gaps=("real alert delivery is not configured",),
    )


def test_daily_report_generation_from_fixture_snapshot_is_deterministic() -> None:
    result = generate_daily_report(report_date=date(2026, 5, 6), snapshot=_snapshot())

    assert result.external_calls_performed is False
    assert result.report.status == "dry_run"
    assert result.payload["report_type"] == "daily"
    assert "# Daily Trading Report - 2026-05-06" in result.markdown
    assert "- Live Trading: `disabled`" in result.markdown
    assert "This report is operational telemetry only" in result.markdown
    assert "does not claim profitability" in result.markdown


def test_weekly_report_generation_and_markdown_rendering_are_stable() -> None:
    start, end = default_week_bounds(date(2026, 5, 6))
    result = generate_weekly_report(period_start=start, period_end=end, snapshot=_snapshot())
    report = cast(WeeklyReport, result.report)

    assert report.period_start == date(2026, 5, 4)
    assert report.period_end == date(2026, 5, 10)
    assert render_report_markdown(result.report) == result.markdown
    assert "# Weekly Trading Report - 2026-05-04 to 2026-05-10" in result.markdown
    assert "Level 4 readiness remains unsatisfied" in result.markdown


def test_report_persistence_through_ledger_repository() -> None:
    repository = SQLiteLedgerRepository(connect_in_memory_sqlite())
    result = generate_daily_report(report_date=date(2026, 5, 6), snapshot=_snapshot())

    persisted = persist_report_generation_result(repository, result)

    assert persisted.persisted_report_id is not None
    record = repository.get_report(persisted.persisted_report_id)
    assert record is not None
    assert record.report_type == "daily"
    assert record.report_date == date(2026, 5, 6)
    assert record.payload["report_type"] == "daily"
    assert "Daily Trading Report" in (record.markdown or "")


def test_ledger_snapshot_builder_uses_local_repository_without_external_credentials() -> None:
    repository = SQLiteLedgerRepository(connect_in_memory_sqlite())
    repository.insert_system_event(
        event_id="incident-1",
        event_type="protective_stop_incident",
        severity="critical",
        source_component="test",
        message="Missing protective stop",
        created_at=GENERATED_AT,
    )

    snapshot = build_report_input_snapshot(repository, generated_at=GENERATED_AT)

    assert snapshot.live_trading_enabled is False
    assert snapshot.autonomous_execution_enabled is False
    assert snapshot.incidents[0]["event_id"] == "incident-1"
    assert "paper trading operations have not started" in snapshot.operational_gaps
