"""Temporal workflow skeleton registry."""

from apps.workers.app.workflows.ai_shortlist_research import AIShortlistResearchWorkflow
from apps.workers.app.workflows.daily_data_refresh import DailyDataRefreshWorkflow
from apps.workers.app.workflows.decision import DecisionWorkflow
from apps.workers.app.workflows.eod_signal import EODSignalWorkflow
from apps.workers.app.workflows.execution_intent import ExecutionIntentWorkflow
from apps.workers.app.workflows.kill_switch import KillSwitchWorkflow
from apps.workers.app.workflows.order_lifecycle import OrderLifecycleWorkflow
from apps.workers.app.workflows.position_lifecycle import PositionLifecycleWorkflow
from apps.workers.app.workflows.reconciliation import ReconciliationWorkflow
from apps.workers.app.workflows.reporting import ReportingWorkflow

WORKFLOW_CLASSES = (
    DailyDataRefreshWorkflow,
    EODSignalWorkflow,
    AIShortlistResearchWorkflow,
    DecisionWorkflow,
    ExecutionIntentWorkflow,
    OrderLifecycleWorkflow,
    PositionLifecycleWorkflow,
    ReconciliationWorkflow,
    KillSwitchWorkflow,
    ReportingWorkflow,
)

__all__ = [
    "AIShortlistResearchWorkflow",
    "DailyDataRefreshWorkflow",
    "DecisionWorkflow",
    "EODSignalWorkflow",
    "ExecutionIntentWorkflow",
    "KillSwitchWorkflow",
    "OrderLifecycleWorkflow",
    "PositionLifecycleWorkflow",
    "ReconciliationWorkflow",
    "ReportingWorkflow",
    "WORKFLOW_CLASSES",
]
