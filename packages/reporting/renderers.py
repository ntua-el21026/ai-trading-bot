"""Deterministic report renderers."""

from __future__ import annotations

from packages.reporting.models import (
    DailyReport,
    ReportIssue,
    ReportMetric,
    ReportSection,
    WeeklyReport,
)


def render_report_markdown(report: DailyReport | WeeklyReport) -> str:
    lines: list[str] = [_report_title(report), ""]
    lines.extend(
        [
            f"- Status: `{report.status}`",
            f"- Generated At: `{report.generated_at.isoformat()}`",
            "- Live Trading: `disabled`",
            "- Paper Operations Evidence: `missing`",
            "",
        ]
    )
    for section in report.sections:
        lines.extend(_render_section(section))
    if report.open_follow_ups:
        lines.extend(["## Open Follow-Ups", ""])
        for issue in report.open_follow_ups:
            lines.append(_render_issue(issue))
        lines.append("")
    lines.append("This report is operational telemetry only. It does not claim profitability.")
    return "\n".join(lines).rstrip() + "\n"


def render_daily_report_telegram_summary(report: DailyReport) -> str:
    approved = _metric_value(report, "Candidates And Signals", "accepted_candidate_count")
    open_positions = _metric_value(
        report,
        "Orders, Fills, And Positions",
        "open_position_count",
    )
    return "\n".join(
        (
            f"Daily Report - {_environment_label(report.status)}",
            f"Candidates: {_metric_value(report, 'Candidates And Signals', 'candidate_count')}",
            f"Approved: {approved}",
            f"Rejected: {_metric_value(report, 'Decisions And Rejections', 'rejection_count')}",
            f"Open positions: {open_positions}",
            "Closed today: missing",
            "Wins/Losses: missing",
            "Daily PnL: missing",
            f"Incidents: {_metric_value(report, 'Incidents And System Events', 'incident_count')}",
            f"Reconciliation: {_metric_value(report, 'Reconciliation Status', 'latest_status')}",
        )
    )


def render_weekly_report_telegram_summary(report: WeeklyReport) -> str:
    closed_trades = _metric_value(report, "Closed Trade Count", "closed_trade_count")
    stop_success = _metric_value(
        report,
        "Stop Placement Success",
        "stop_placement_success_rate",
    )
    ai_schema_validity = _metric_value(
        report,
        "AI Schema Validity Rate",
        "ai_schema_validity_rate",
    )
    return "\n".join(
        (
            f"Weekly Report - {_environment_label(report.status)}",
            f"Closed trades: {closed_trades}",
            "Wins/Losses: missing",
            "Win rate: missing",
            "Net PnL: missing",
            "Avg R: missing",
            f"Stop success: {stop_success}",
            f"Broker mismatches: {_metric_value(report, 'Mismatch Rate', 'latest_mismatch_count')}",
            f"AI schema validity: {ai_schema_validity}",
        )
    )


def _report_title(report: DailyReport | WeeklyReport) -> str:
    if isinstance(report, DailyReport):
        return f"# Daily Trading Report - {report.report_date.isoformat()}"
    return (
        "# Weekly Trading Report - "
        f"{report.period_start.isoformat()} to {report.period_end.isoformat()}"
    )


def _metric_value(
    report: DailyReport | WeeklyReport,
    section_title: str,
    metric_name: str,
) -> str:
    for section in report.sections:
        if section.title != section_title:
            continue
        for metric in section.metrics:
            if metric.name == metric_name:
                if metric.value is None:
                    return "missing"
                return str(metric.value)
    return "missing"


def _environment_label(status: str) -> str:
    if status == "dry_run":
        return "Dry Run"
    return status.replace("_", " ").title()


def _render_section(section: ReportSection) -> list[str]:
    lines = [f"## {section.title}", "", f"- Status: `{section.status}`"]
    for metric in section.metrics:
        lines.append(_render_metric(metric))
    for issue in section.issues:
        lines.append(_render_issue(issue))
    lines.append("")
    return lines


def _render_metric(metric: ReportMetric) -> str:
    value = "`missing`" if metric.value is None else f"`{metric.value}`"
    unit = "" if metric.unit is None else f" {metric.unit}"
    status = "" if metric.status is None else f" ({metric.status})"
    return f"- {metric.name}: {value}{unit}{status}"


def _render_issue(issue: ReportIssue) -> str:
    follow_up = "" if issue.follow_up is None else f" Follow-up: {issue.follow_up}"
    related = "" if issue.related_entity_id is None else f" Related: `{issue.related_entity_id}`."
    return f"- [{issue.severity}] {issue.message}.{related}{follow_up}"
