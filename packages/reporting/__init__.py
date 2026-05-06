"""Local/fake reporting contracts."""

from packages.reporting.generators import (
    default_week_bounds,
    generate_daily_report,
    generate_weekly_report,
)
from packages.reporting.ledger import build_report_input_snapshot, persist_report_generation_result
from packages.reporting.models import (
    DailyReport,
    ReportGenerationResult,
    ReportInputSnapshot,
    ReportIssue,
    ReportMetric,
    ReportSection,
    WeeklyReport,
)
from packages.reporting.renderers import render_report_markdown

__all__ = [
    "DailyReport",
    "ReportGenerationResult",
    "ReportInputSnapshot",
    "ReportIssue",
    "ReportMetric",
    "ReportSection",
    "WeeklyReport",
    "build_report_input_snapshot",
    "default_week_bounds",
    "generate_daily_report",
    "generate_weekly_report",
    "persist_report_generation_result",
    "render_report_markdown",
]
