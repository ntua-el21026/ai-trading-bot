"""AI shortlist research workflow skeleton."""

from __future__ import annotations

from temporalio import workflow

from apps.workers.app.queries import GET_CURRENT_SYSTEM_STATE
from apps.workers.app.retry_policies import AI_ACTIVITY_RETRY
from apps.workers.app.types import WorkflowRunInput, WorkflowStatus
from apps.workers.app.workflows._shared import execute_placeholder_activity


@workflow.defn
class AIShortlistResearchWorkflow:
    def __init__(self) -> None:
        self._status = WorkflowStatus("AIShortlistResearchWorkflow", "initialized")

    @workflow.run
    async def run(self, run_input: WorkflowRunInput) -> WorkflowStatus:
        self._status = await execute_placeholder_activity(
            workflow_name="AIShortlistResearchWorkflow",
            activity_name="research_ai_shortlist",
            task_queue="ai-research-task-queue",
            run_input=run_input,
            retry_contract=AI_ACTIVITY_RETRY,
        )
        return self._status

    @workflow.query(name=GET_CURRENT_SYSTEM_STATE)
    def get_current_system_state(self) -> WorkflowStatus:
        return self._status
