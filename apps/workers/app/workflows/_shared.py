"""Shared deterministic helpers for skeleton workflows."""

from __future__ import annotations

from datetime import timedelta
from typing import cast

from temporalio import workflow

from apps.workers.app.retry_policies import DEFAULT_ACTIVITY_RETRY, RetryPolicyContract
from apps.workers.app.types import (
    ActivityPlaceholderInput,
    ActivityPlaceholderResult,
    WorkflowRunInput,
    WorkflowStatus,
)


async def execute_placeholder_activity(
    *,
    workflow_name: str,
    activity_name: str,
    task_queue: str,
    run_input: WorkflowRunInput,
    retry_contract: RetryPolicyContract = DEFAULT_ACTIVITY_RETRY,
    timeout_minutes: int = 5,
) -> WorkflowStatus:
    result = cast(
        ActivityPlaceholderResult,
        await workflow.execute_activity(
            activity_name,
            ActivityPlaceholderInput(workflow_name=workflow_name, purpose=run_input.reason),
            start_to_close_timeout=timedelta(minutes=timeout_minutes),
            retry_policy=retry_contract.policy,
            task_queue=task_queue,
        ),
    )
    return WorkflowStatus(
        workflow_name=workflow_name,
        status="completed",
        details={
            "activity": result.activity_name,
            "activity_status": result.status,
            "external_calls_performed": str(result.external_calls_performed).lower(),
        },
    )
