"""Kill-switch workflow skeleton."""

from __future__ import annotations

from temporalio import workflow

from apps.workers.app.queries import GET_CURRENT_SYSTEM_STATE, GET_KILL_SWITCH_STATE
from apps.workers.app.signals import (
    ACKNOWLEDGE_INCIDENT,
    APPROVE_LEVEL_CHANGE,
    FORCE_RECONCILIATION,
    FORCE_REPORT,
    MANUAL_KILL_SWITCH,
    MANUAL_PAUSE_NEW_RISK,
    MANUAL_RESUME_AFTER_REVIEW,
)
from apps.workers.app.types import KillSwitchState, WorkflowRunInput, WorkflowStatus
from apps.workers.app.workflows._shared import execute_placeholder_activity


@workflow.defn
class KillSwitchWorkflow:
    def __init__(self) -> None:
        self._kill_switch_state = KillSwitchState()
        self._status = WorkflowStatus("KillSwitchWorkflow", "initialized")
        self._acknowledged_incidents: tuple[str, ...] = ()

    @workflow.run
    async def run(self, run_input: WorkflowRunInput) -> WorkflowStatus:
        self._status = await execute_placeholder_activity(
            workflow_name="KillSwitchWorkflow",
            activity_name="persist_system_event",
            task_queue="execution-task-queue",
            run_input=run_input,
        )
        return self._status

    @workflow.signal(name=MANUAL_KILL_SWITCH)
    def manual_kill_switch(self, reason: str = "manual") -> None:
        self._kill_switch_state = KillSwitchState(
            state="PAUSED_NEW_RISK",
            new_risk_allowed=False,
            risk_reducing_exits_allowed=True,
            reason=reason,
        )
        self._status = WorkflowStatus(
            "KillSwitchWorkflow",
            "kill_switch_active",
            {"reason": reason},
        )

    @workflow.signal(name=MANUAL_PAUSE_NEW_RISK)
    def manual_pause_new_risk(self, reason: str = "manual") -> None:
        self._kill_switch_state = KillSwitchState(
            state="PAUSED_NEW_RISK",
            new_risk_allowed=False,
            risk_reducing_exits_allowed=True,
            reason=reason,
        )
        self._status = WorkflowStatus("KillSwitchWorkflow", "paused_new_risk", {"reason": reason})

    @workflow.signal(name=MANUAL_RESUME_AFTER_REVIEW)
    def manual_resume_after_review(self, reason: str = "manual_review_complete") -> None:
        self._kill_switch_state = KillSwitchState(
            state="RUNNING",
            new_risk_allowed=True,
            risk_reducing_exits_allowed=True,
            reason=reason,
        )
        self._status = WorkflowStatus("KillSwitchWorkflow", "running", {"reason": reason})

    @workflow.signal(name=FORCE_RECONCILIATION)
    def force_reconciliation(self, reason: str = "manual") -> None:
        self._status = WorkflowStatus(
            "KillSwitchWorkflow",
            "force_reconciliation_requested",
            {"reason": reason},
        )

    @workflow.signal(name=FORCE_REPORT)
    def force_report(self, reason: str = "manual") -> None:
        self._status = WorkflowStatus(
            "KillSwitchWorkflow",
            "force_report_requested",
            {"reason": reason},
        )

    @workflow.signal(name=APPROVE_LEVEL_CHANGE)
    def approve_level_change(self, reason: str = "manual_approval") -> None:
        self._status = WorkflowStatus(
            "KillSwitchWorkflow",
            "level_change_approval_recorded",
            {"reason": reason},
        )

    @workflow.signal(name=ACKNOWLEDGE_INCIDENT)
    def acknowledge_incident(self, incident_id: str) -> None:
        self._acknowledged_incidents = (*self._acknowledged_incidents, incident_id)
        self._status = WorkflowStatus(
            "KillSwitchWorkflow",
            "incident_acknowledged",
            {"incident_id": incident_id},
        )

    @workflow.query(name=GET_CURRENT_SYSTEM_STATE)
    def get_current_system_state(self) -> WorkflowStatus:
        return self._status

    @workflow.query(name=GET_KILL_SWITCH_STATE)
    def get_kill_switch_state(self) -> KillSwitchState:
        return self._kill_switch_state
