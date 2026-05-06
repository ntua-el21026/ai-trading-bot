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


def _report_title(report: DailyReport | WeeklyReport) -> str:
    if isinstance(report, DailyReport):
        return f"# Daily Trading Report - {report.report_date.isoformat()}"
    return (
        "# Weekly Trading Report - "
        f"{report.period_start.isoformat()} to {report.period_end.isoformat()}"
    )


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
