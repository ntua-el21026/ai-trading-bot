"""Daily data refresh workflow skeleton."""

from __future__ import annotations

from temporalio import workflow

from apps.workers.app.queries import GET_ACTIVE_WORKFLOWS, GET_CURRENT_SYSTEM_STATE
from apps.workers.app.types import WorkflowRunInput, WorkflowStatus
from apps.workers.app.workflows._shared import execute_placeholder_activity


@workflow.defn
class DailyDataRefreshWorkflow:
    def __init__(self) -> None:
        self._status = WorkflowStatus("DailyDataRefreshWorkflow", "initialized")

    @workflow.run
    async def run(self, run_input: WorkflowRunInput) -> WorkflowStatus:
        self._status = WorkflowStatus(
            "DailyDataRefreshWorkflow",
            "running",
            {"reason": run_input.reason},
        )
        self._status = await execute_placeholder_activity(
            workflow_name="DailyDataRefreshWorkflow",
            activity_name="refresh_market_data",
            task_queue="market-data-task-queue",
            run_input=run_input,
        )
        return self._status

    @workflow.query(name=GET_CURRENT_SYSTEM_STATE)
    def get_current_system_state(self) -> WorkflowStatus:
        return self._status

    @workflow.query(name=GET_ACTIVE_WORKFLOWS)
    def get_active_workflows(self) -> tuple[str, ...]:
        return ("DailyDataRefreshWorkflow",)
