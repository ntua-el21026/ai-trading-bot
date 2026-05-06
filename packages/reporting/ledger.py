"""Reporting helpers backed by the local ledger repository."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from packages.ledger.repositories import SQLiteLedgerRepository
from packages.reporting.models import ReportGenerationResult, ReportInputSnapshot


def build_report_input_snapshot(
    repository: SQLiteLedgerRepository,
    *,
    generated_at: datetime,
    environment: Literal["paper", "live"] = "paper",
    dry_run: bool = True,
    live_trading_enabled: bool = False,
    autonomous_execution_enabled: bool = False,
) -> ReportInputSnapshot:
    return ReportInputSnapshot(
        generated_at=generated_at,
        environment=environment,
        dry_run=dry_run,
        live_trading_enabled=live_trading_enabled,
        autonomous_execution_enabled=autonomous_execution_enabled,
        candidates=tuple(
            record.model_dump(mode="json") for record in repository.list_trade_candidates(limit=500)
        ),
        ai_outputs=tuple(
            record.model_dump(mode="json")
            for record in repository.list_ai_research_outputs(limit=500)
        ),
        decisions=tuple(
            record.model_dump(mode="json") for record in repository.list_trade_decisions(limit=500)
        ),
        risk_checks=tuple(
            record.model_dump(mode="json")
            for record in repository.list_recent_risk_checks(limit=500)
        ),
        execution_intents=tuple(
            record.model_dump(mode="json")
            for record in repository.list_active_execution_intents(limit=500)
        ),
        orders=tuple(
            record.model_dump(mode="json") for record in repository.list_orders(limit=500)
        ),
        fills=tuple(record.model_dump(mode="json") for record in repository.list_fills(limit=500)),
        positions=tuple(
            record.model_dump(mode="json") for record in repository.list_open_positions(limit=500)
        ),
        reconciliations=tuple(
            record.model_dump(mode="json")
            for record in repository.list_broker_reconciliations(limit=100)
        ),
        incidents=tuple(
            record.model_dump(mode="json") for record in repository.list_recent_incidents(limit=100)
        ),
        reports=tuple(
            record.model_dump(mode="json") for record in repository.list_reports(limit=100)
        ),
        operational_gaps=(
            "real alert delivery is not configured",
            "real dashboard deployment is pending",
            "paper trading operations have not started",
        ),
    )


def persist_report_generation_result(
    repository: SQLiteLedgerRepository,
    result: ReportGenerationResult,
) -> ReportGenerationResult:
    report = result.report
    if report.report_type == "daily":
        record = repository.insert_report(
            report_type=report.report_type,
            status=report.status,
            payload=result.payload,
            markdown=result.markdown,
            report_date=report.report_date,
            created_at=report.generated_at,
        )
    else:
        record = repository.insert_report(
            report_type=report.report_type,
            status=report.status,
            payload=result.payload,
            markdown=result.markdown,
            period_start=report.period_start,
            period_end=report.period_end,
            created_at=report.generated_at,
        )
    return result.model_copy(update={"persisted_report_id": record.report_id})
