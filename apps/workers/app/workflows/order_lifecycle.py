"""Order lifecycle workflow skeleton."""

from __future__ import annotations

from temporalio import workflow

from apps.workers.app.queries import GET_CURRENT_SYSTEM_STATE, GET_OPEN_ORDER_LIFECYCLES
from apps.workers.app.retry_policies import BROKER_ORDER_SUBMIT_RETRY
from apps.workers.app.types import WorkflowRunInput, WorkflowStatus
from apps.workers.app.workflows._shared import execute_placeholder_activity


@workflow.defn
class OrderLifecycleWorkflow:
    def __init__(self) -> None:
        self._status = WorkflowStatus("OrderLifecycleWorkflow", "initialized")
        self._open_order_lifecycles: tuple[str, ...] = ()

    @workflow.run
    async def run(self, run_input: WorkflowRunInput) -> WorkflowStatus:
        self._status = await execute_placeholder_activity(
            workflow_name="OrderLifecycleWorkflow",
            activity_name="persist_order_event",
            task_queue="execution-task-queue",
            run_input=run_input,
            retry_contract=BROKER_ORDER_SUBMIT_RETRY,
        )
        return self._status

    @workflow.query(name=GET_CURRENT_SYSTEM_STATE)
    def get_current_system_state(self) -> WorkflowStatus:
        return self._status

    @workflow.query(name=GET_OPEN_ORDER_LIFECYCLES)
    def get_open_order_lifecycles(self) -> tuple[str, ...]:
        return self._open_order_lifecycles
