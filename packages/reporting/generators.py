"""Pure report generation from supplied ledger/read-model snapshots."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from packages.reporting.models import (
    DailyReport,
    ReportGenerationResult,
    ReportInputSnapshot,
    ReportIssue,
    ReportMetric,
    ReportSection,
    ReportStatus,
    WeeklyReport,
)
from packages.reporting.renderers import render_report_markdown


def generate_daily_report(
    *,
    report_date: date,
    snapshot: ReportInputSnapshot,
) -> ReportGenerationResult:
    status = _status(snapshot)
    sections = (
        _workflow_summary(snapshot),
        _candidates_signals(snapshot),
        _ai_summary(snapshot),
        _decisions_rejections(snapshot),
        _execution_intents(snapshot),
        _orders_fills_positions(snapshot),
        _protective_stops(snapshot),
        _reconciliation_status(snapshot),
        _incidents_system_events(snapshot),
        _risk_exposure(snapshot),
        _slippage_fill_diagnostics(snapshot),
        _open_follow_ups(snapshot),
    )
    report = DailyReport(
        report_date=report_date,
        generated_at=snapshot.generated_at,
        status=status,
        sections=sections,
        open_follow_ups=tuple(issue for section in sections for issue in section.issues),
    )
    return _result(report)


def generate_weekly_report(
    *,
    period_start: date,
    period_end: date,
    snapshot: ReportInputSnapshot,
) -> ReportGenerationResult:
    status = _status(snapshot)
    sections = (
        _paper_trades_summary(snapshot),
        _closed_trade_count(snapshot),
        _weekly_open_positions(snapshot),
        _execution_diagnostics(snapshot),
        _stop_placement_success(snapshot),
        _mismatch_rate(snapshot),
        _ai_schema_validity(snapshot),
        _incidents_by_severity(snapshot),
        _failed_checks_rejections(snapshot),
        _operational_issues(snapshot),
        _unresolved_gaps(snapshot),
    )
    report = WeeklyReport(
        period_start=period_start,
        period_end=period_end,
        generated_at=snapshot.generated_at,
        status=status,
        sections=sections,
        open_follow_ups=tuple(issue for section in sections for issue in section.issues),
    )
    return _result(report)


def default_week_bounds(report_date: date) -> tuple[date, date]:
    start = report_date - timedelta(days=report_date.weekday())
    return start, start + timedelta(days=6)


def _result(report: DailyReport | WeeklyReport) -> ReportGenerationResult:
    payload = report.model_dump(mode="json")
    return ReportGenerationResult(
        report=report,
        markdown=render_report_markdown(report),
        payload=payload,
        external_calls_performed=False,
    )


def _status(snapshot: ReportInputSnapshot) -> ReportStatus:
    if snapshot.dry_run:
        return "dry_run"
    if snapshot.environment == "paper":
        return "paper"
    if not snapshot.live_trading_enabled:
        return "live_disabled"
    return "not_operational"


def _workflow_summary(snapshot: ReportInputSnapshot) -> ReportSection:
    return _section(
        "Workflow Summary",
        metrics=(
            _metric("workflow_count", len(snapshot.workflow_statuses)),
            _metric("environment", snapshot.environment),
            _metric("dry_run", snapshot.dry_run),
            _metric("live_trading_enabled", snapshot.live_trading_enabled, status="disabled"),
            _metric("autonomous_execution_enabled", snapshot.autonomous_execution_enabled),
        ),
    )


def _candidates_signals(snapshot: ReportInputSnapshot) -> ReportSection:
    accepted = sum(1 for item in snapshot.candidates if _status_value(item) in {"accepted", "open"})
    return _section(
        "Candidates And Signals",
        metrics=(
            _metric("candidate_count", len(snapshot.candidates)),
            _metric("accepted_candidate_count", accepted),
        ),
    )


def _ai_summary(snapshot: ReportInputSnapshot) -> ReportSection:
    fallback_count = sum(
        1 for item in snapshot.ai_outputs if item.get("fallback_reason") not in {None, ""}
    )
    valid_count = len(snapshot.ai_outputs) - fallback_count
    return _section(
        "AI Summary And Schema Stats",
        metrics=(
            _metric("ai_output_count", len(snapshot.ai_outputs)),
            _metric("fallback_count", fallback_count),
            _metric("schema_validity_rate", _rate(valid_count, len(snapshot.ai_outputs))),
        ),
    )


def _decisions_rejections(snapshot: ReportInputSnapshot) -> ReportSection:
    rejected = sum(1 for item in snapshot.decisions if "reject" in _status_value(item))
    return _section(
        "Decisions And Rejections",
        metrics=(
            _metric("decision_count", len(snapshot.decisions)),
            _metric("rejection_count", rejected),
        ),
    )


def _execution_intents(snapshot: ReportInputSnapshot) -> ReportSection:
    return _section(
        "Execution Intents",
        metrics=(
            _metric("execution_intent_count", len(snapshot.execution_intents)),
            _metric("active_intent_count", len(snapshot.execution_intents)),
        ),
    )


def _orders_fills_positions(snapshot: ReportInputSnapshot) -> ReportSection:
    return _section(
        "Orders, Fills, And Positions",
        metrics=(
            _metric("order_count", len(snapshot.orders)),
            _metric("fill_count", len(snapshot.fills)),
            _metric("open_position_count", len(snapshot.positions)),
        ),
    )


def _protective_stops(snapshot: ReportInputSnapshot) -> ReportSection:
    positions = len(snapshot.positions)
    protected = sum(1 for item in snapshot.positions if item.get("protective_stop_order_id"))
    issues: tuple[ReportIssue, ...] = ()
    if positions and protected < positions:
        issues = (
            ReportIssue(
                severity="warning",
                message="One or more open positions lack confirmed protective stop references",
                follow_up="Verify broker stream and REST fallback before any new risk",
            ),
        )
    return _section(
        "Protective Stops",
        metrics=(
            _metric("open_position_count", positions),
            _metric("positions_with_stop_reference", protected),
            _metric("stop_reference_rate", _rate(protected, positions)),
        ),
        issues=issues,
    )


def _reconciliation_status(snapshot: ReportInputSnapshot) -> ReportSection:
    latest = snapshot.reconciliations[0] if snapshot.reconciliations else {}
    mismatches = latest.get("mismatches", ())
    mismatch_count = len(mismatches) if isinstance(mismatches, list) else 0
    issues = (
        _missing_evidence_issues("No reconciliation evidence is available.") if not latest else ()
    )
    return _section(
        "Reconciliation Status",
        metrics=(
            _metric("reconciliation_count", len(snapshot.reconciliations)),
            _metric("latest_status", latest.get("status")),
            _metric("latest_mismatch_count", mismatch_count),
        ),
        issues=issues,
    )


def _incidents_system_events(snapshot: ReportInputSnapshot) -> ReportSection:
    critical = sum(1 for item in snapshot.incidents if item.get("severity") == "critical")
    warning = sum(1 for item in snapshot.incidents if item.get("severity") == "warning")
    return _section(
        "Incidents And System Events",
        metrics=(
            _metric("incident_count", len(snapshot.incidents)),
            _metric("critical_incident_count", critical),
            _metric("warning_incident_count", warning),
        ),
    )


def _risk_exposure(snapshot: ReportInputSnapshot) -> ReportSection:
    return _section(
        "Risk And Exposure",
        metrics=(
            _metric("new_risk_allowed", snapshot.risk_payload.get("new_risk_allowed")),
            _metric("gross_exposure_pct", snapshot.risk_payload.get("gross_exposure_pct")),
            _metric("daily_loss_pct", snapshot.risk_payload.get("daily_loss_pct")),
        ),
    )


def _slippage_fill_diagnostics(snapshot: ReportInputSnapshot) -> ReportSection:
    slippage_values = [
        value
        for item in snapshot.fills
        if isinstance((value := item.get("slippage_bps")), int | float)
    ]
    avg_slippage = (
        None if not slippage_values else round(sum(slippage_values) / len(slippage_values), 4)
    )
    return _section(
        "Slippage And Fill Diagnostics",
        metrics=(
            _metric("fill_count", len(snapshot.fills)),
            _metric("average_slippage_bps", avg_slippage),
        ),
    )


def _open_follow_ups(snapshot: ReportInputSnapshot) -> ReportSection:
    issues = tuple(
        ReportIssue(severity="warning", message=gap, follow_up="Resolve before paper evidence")
        for gap in snapshot.operational_gaps
    )
    if not issues:
        issues = _missing_evidence_issues("Paper trading evidence is missing.")
    return _section("Open Follow-Ups", issues=issues)


def _paper_trades_summary(snapshot: ReportInputSnapshot) -> ReportSection:
    return _section(
        "Paper Trades Summary",
        metrics=(
            _metric("order_count", len(snapshot.orders)),
            _metric("fill_count", len(snapshot.fills)),
            _metric("reporting_note", "paper trading operations have not started"),
        ),
    )


def _closed_trade_count(snapshot: ReportInputSnapshot) -> ReportSection:
    closed = sum(1 for item in snapshot.positions if _status_value(item) == "closed")
    return _section("Closed Trade Count", metrics=(_metric("closed_trade_count", closed),))


def _weekly_open_positions(snapshot: ReportInputSnapshot) -> ReportSection:
    open_positions = sum(1 for item in snapshot.positions if _status_value(item) != "closed")
    return _section("Open Positions", metrics=(_metric("open_position_count", open_positions),))


def _execution_diagnostics(snapshot: ReportInputSnapshot) -> ReportSection:
    rejected_orders = sum(1 for item in snapshot.orders if _status_value(item) == "rejected")
    return _section(
        "Execution Diagnostics",
        metrics=(
            _metric("intent_count", len(snapshot.execution_intents)),
            _metric("order_count", len(snapshot.orders)),
            _metric("rejected_order_count", rejected_orders),
        ),
    )


def _stop_placement_success(snapshot: ReportInputSnapshot) -> ReportSection:
    positions = len(snapshot.positions)
    protected = sum(1 for item in snapshot.positions if item.get("protective_stop_order_id"))
    issues = (
        _missing_evidence_issues("No stop-placement paper evidence is available.")
        if not positions
        else ()
    )
    return _section(
        "Stop Placement Success",
        metrics=(_metric("stop_placement_success_rate", _rate(protected, positions)),),
        issues=issues,
    )


def _mismatch_rate(snapshot: ReportInputSnapshot) -> ReportSection:
    latest = snapshot.reconciliations[0] if snapshot.reconciliations else {}
    mismatches = latest.get("mismatches", ())
    mismatch_count = len(mismatches) if isinstance(mismatches, list) else 0
    return _section("Mismatch Rate", metrics=(_metric("latest_mismatch_count", mismatch_count),))


def _ai_schema_validity(snapshot: ReportInputSnapshot) -> ReportSection:
    invalid = sum(
        1 for item in snapshot.ai_outputs if item.get("fallback_reason") == "schema_violation"
    )
    valid_count = len(snapshot.ai_outputs) - invalid
    return _section(
        "AI Schema Validity Rate",
        metrics=(
            _metric("ai_schema_validity_rate", _rate(valid_count, len(snapshot.ai_outputs))),
        ),
    )


def _incidents_by_severity(snapshot: ReportInputSnapshot) -> ReportSection:
    return _section(
        "Incidents By Severity",
        metrics=(
            _metric(
                "critical",
                sum(1 for item in snapshot.incidents if item.get("severity") == "critical"),
            ),
            _metric(
                "warning",
                sum(1 for item in snapshot.incidents if item.get("severity") == "warning"),
            ),
            _metric(
                "info",
                sum(1 for item in snapshot.incidents if item.get("severity") == "info"),
            ),
        ),
    )


def _failed_checks_rejections(snapshot: ReportInputSnapshot) -> ReportSection:
    failed = sum(1 for item in snapshot.risk_checks if item.get("passed") is False)
    rejected = sum(1 for item in snapshot.decisions if "reject" in _status_value(item))
    return _section(
        "Failed Checks And Rejections",
        metrics=(_metric("failed_risk_check_count", failed), _metric("rejection_count", rejected)),
    )


def _operational_issues(snapshot: ReportInputSnapshot) -> ReportSection:
    return _section(
        "Operational Issues",
        metrics=(_metric("operational_gap_count", len(snapshot.operational_gaps)),),
        issues=tuple(
            ReportIssue(severity="warning", message=gap, follow_up="Track before paper run")
            for gap in snapshot.operational_gaps
        ),
    )


def _unresolved_gaps(snapshot: ReportInputSnapshot) -> ReportSection:
    return _section(
        "Unresolved Gaps",
        issues=(
            ReportIssue(
                severity="warning",
                message="Level 4 readiness remains unsatisfied",
                follow_up="Collect frozen paper, alerting, dashboard, and integration evidence",
            ),
        ),
    )


def _section(
    title: str,
    *,
    metrics: tuple[ReportMetric, ...] = (),
    issues: tuple[ReportIssue, ...] = (),
    payload: dict[str, Any] | None = None,
) -> ReportSection:
    status = "missing_evidence" if issues else "not_operational"
    return ReportSection(
        title=title,
        status=status,
        metrics=metrics,
        issues=issues,
        payload=payload or {},
    )


def _metric(
    name: str,
    value: str | int | float | bool | None,
    *,
    unit: str | None = None,
    status: str | None = None,
) -> ReportMetric:
    return ReportMetric(name=name, value=value, unit=unit, status=status)


def _status_value(item: dict[str, Any]) -> str:
    return str(
        item.get("status")
        or item.get("candidate_status")
        or item.get("decision_status")
        or ""
    ).lower()


def _rate(numerator: int, denominator: int) -> str:
    if denominator == 0:
        return "missing evidence"
    return f"{(numerator / denominator) * 100:.2f}%"


def _missing_evidence_issues(message: str) -> tuple[ReportIssue, ...]:
    return (
        ReportIssue(
            severity="warning",
            message=message,
            follow_up="Do not treat this report as paper or live readiness evidence",
        ),
    )
