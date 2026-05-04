"""End-of-day signal workflow skeleton."""

from __future__ import annotations

from temporalio import workflow

from apps.workers.app.queries import GET_CURRENT_SYSTEM_STATE
from apps.workers.app.types import WorkflowRunInput, WorkflowStatus
from apps.workers.app.workflows._shared import execute_placeholder_activity


@workflow.defn
class EODSignalWorkflow:
    def __init__(self) -> None:
        self._status = WorkflowStatus("EODSignalWorkflow", "initialized")

    @workflow.run
    async def run(self, run_input: WorkflowRunInput) -> WorkflowStatus:
        self._status = await execute_placeholder_activity(
            workflow_name="EODSignalWorkflow",
            activity_name="build_eod_signals",
            task_queue="strategy-task-queue",
            run_input=run_input,
        )
        return self._status

    @workflow.query(name=GET_CURRENT_SYSTEM_STATE)
    def get_current_system_state(self) -> WorkflowStatus:
        return self._status
