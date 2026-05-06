"""Reporting workflow skeleton."""

from __future__ import annotations

from temporalio import workflow

from apps.workers.app.queries import GET_CURRENT_SYSTEM_STATE
from apps.workers.app.signals import FORCE_REPORT
from apps.workers.app.types import WorkflowRunInput, WorkflowStatus
from apps.workers.app.workflows._shared import execute_placeholder_activity


@workflow.defn
class ReportingWorkflow:
    def __init__(self) -> None:
        self._force_requested = False
        self._status = WorkflowStatus("ReportingWorkflow", "initialized")

    @workflow.run
    async def run(self, run_input: WorkflowRunInput) -> WorkflowStatus:
        self._status = await execute_placeholder_activity(
            workflow_name="ReportingWorkflow",
            activity_name="persist_report",
            task_queue="reporting-task-queue",
            run_input=run_input,
        )
        return self._status

    @workflow.signal(name=FORCE_REPORT)
    def force_report(self, reason: str = "manual") -> None:
        self._force_requested = True
        self._status = WorkflowStatus("ReportingWorkflow", "force_requested", {"reason": reason})

    @workflow.query(name=GET_CURRENT_SYSTEM_STATE)
    def get_current_system_state(self) -> WorkflowStatus:
        return self._status
