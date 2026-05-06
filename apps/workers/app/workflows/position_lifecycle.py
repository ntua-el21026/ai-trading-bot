"""Position lifecycle workflow skeleton."""

from __future__ import annotations

from temporalio import workflow

from apps.workers.app.queries import GET_CURRENT_SYSTEM_STATE, GET_OPEN_POSITION_LIFECYCLES
from apps.workers.app.retry_policies import PROTECTIVE_STOP_RETRY
from apps.workers.app.types import WorkflowRunInput, WorkflowStatus
from apps.workers.app.workflows._shared import execute_placeholder_activity


@workflow.defn
class PositionLifecycleWorkflow:
    def __init__(self) -> None:
        self._status = WorkflowStatus("PositionLifecycleWorkflow", "initialized")
        self._open_position_lifecycles: tuple[str, ...] = ()

    @workflow.run
    async def run(self, run_input: WorkflowRunInput) -> WorkflowStatus:
        self._status = await execute_placeholder_activity(
            workflow_name="PositionLifecycleWorkflow",
            activity_name="persist_position_snapshot",
            task_queue="execution-task-queue",
            run_input=run_input,
            retry_contract=PROTECTIVE_STOP_RETRY,
        )
        return self._status

    @workflow.query(name=GET_CURRENT_SYSTEM_STATE)
    def get_current_system_state(self) -> WorkflowStatus:
        return self._status

    @workflow.query(name=GET_OPEN_POSITION_LIFECYCLES)
    def get_open_position_lifecycles(self) -> tuple[str, ...]:
        return self._open_position_lifecycles
