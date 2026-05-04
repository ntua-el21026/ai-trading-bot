"""Execution intent workflow skeleton."""

from __future__ import annotations

from temporalio import workflow

from apps.workers.app.queries import GET_ACTIVE_EXECUTION_INTENTS, GET_CURRENT_SYSTEM_STATE
from apps.workers.app.types import WorkflowRunInput, WorkflowStatus
from apps.workers.app.workflows._shared import execute_placeholder_activity


@workflow.defn
class ExecutionIntentWorkflow:
    def __init__(self) -> None:
        self._status = WorkflowStatus("ExecutionIntentWorkflow", "initialized")
        self._active_execution_intents: tuple[str, ...] = ()

    @workflow.run
    async def run(self, run_input: WorkflowRunInput) -> WorkflowStatus:
        self._status = await execute_placeholder_activity(
            workflow_name="ExecutionIntentWorkflow",
            activity_name="build_execution_intents",
            task_queue="execution-task-queue",
            run_input=run_input,
        )
        return self._status

    @workflow.query(name=GET_CURRENT_SYSTEM_STATE)
    def get_current_system_state(self) -> WorkflowStatus:
        return self._status

    @workflow.query(name=GET_ACTIVE_EXECUTION_INTENTS)
    def get_active_execution_intents(self) -> tuple[str, ...]:
        return self._active_execution_intents
