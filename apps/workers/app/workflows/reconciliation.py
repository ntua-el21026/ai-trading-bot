"""Broker reconciliation workflow skeleton."""

from __future__ import annotations

from temporalio import workflow

from apps.workers.app.queries import (
    GET_CURRENT_SYSTEM_STATE,
    GET_LAST_RECONCILIATION_STATUS,
    GET_RECENT_INCIDENTS,
)
from apps.workers.app.signals import FORCE_RECONCILIATION
from apps.workers.app.types import WorkflowRunInput, WorkflowStatus
from apps.workers.app.workflows._shared import execute_placeholder_activity


@workflow.defn
class ReconciliationWorkflow:
    def __init__(self) -> None:
        self._force_requested = False
        self._recent_incidents: tuple[str, ...] = ()
        self._status = WorkflowStatus("ReconciliationWorkflow", "initialized")

    @workflow.run
    async def run(self, run_input: WorkflowRunInput) -> WorkflowStatus:
        self._status = await execute_placeholder_activity(
            workflow_name="ReconciliationWorkflow",
            activity_name="reconcile_broker_state",
            task_queue="reconciliation-task-queue",
            run_input=run_input,
        )
        return self._status

    @workflow.signal(name=FORCE_RECONCILIATION)
    def force_reconciliation(self, reason: str = "manual") -> None:
        self._force_requested = True
        self._status = WorkflowStatus(
            "ReconciliationWorkflow",
            "force_requested",
            {"reason": reason},
        )

    @workflow.query(name=GET_CURRENT_SYSTEM_STATE)
    def get_current_system_state(self) -> WorkflowStatus:
        return self._status

    @workflow.query(name=GET_LAST_RECONCILIATION_STATUS)
    def get_last_reconciliation_status(self) -> WorkflowStatus:
        return self._status

    @workflow.query(name=GET_RECENT_INCIDENTS)
    def get_recent_incidents(self) -> tuple[str, ...]:
        return self._recent_incidents
