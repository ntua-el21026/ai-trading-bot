"""Shared deterministic helpers for skeleton workflows."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from temporalio import workflow

from apps.workers.app.retry_policies import DEFAULT_ACTIVITY_RETRY, RetryPolicyContract
from apps.workers.app.types import (
    ActivityPlaceholderInput,
    ActivityPlaceholderResult,
    WorkflowRunInput,
    WorkflowStatus,
)


def _activity_placeholder_result(
    value: ActivityPlaceholderResult | dict[str, Any],
) -> ActivityPlaceholderResult:
    if isinstance(value, ActivityPlaceholderResult):
        return value
    if isinstance(value, dict):
        details = value.get("details", {})
        if not isinstance(details, dict):
            details = {}
        external_calls_performed = value.get("external_calls_performed", False)
        if isinstance(external_calls_performed, str):
            external_calls_performed = external_calls_performed.lower() == "true"
        return ActivityPlaceholderResult(
            activity_name=str(value["activity_name"]),
            status=str(value.get("status", "placeholder")),
            external_calls_performed=bool(external_calls_performed),
            details={str(key): str(item) for key, item in details.items()},
        )
    raise TypeError(f"unexpected activity placeholder result type: {type(value).__name__}")


async def execute_placeholder_activity(
    *,
    workflow_name: str,
    activity_name: str,
    task_queue: str,
    run_input: WorkflowRunInput,
    retry_contract: RetryPolicyContract = DEFAULT_ACTIVITY_RETRY,
    timeout_minutes: int = 5,
) -> WorkflowStatus:
    result = _activity_placeholder_result(
        await workflow.execute_activity(
            activity_name,
            ActivityPlaceholderInput(workflow_name=workflow_name, purpose=run_input.reason),
            start_to_close_timeout=timedelta(minutes=timeout_minutes),
            retry_policy=retry_contract.policy,
            task_queue=task_queue,
        )
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
