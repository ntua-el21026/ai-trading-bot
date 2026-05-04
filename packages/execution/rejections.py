"""Structured execution rejection helpers."""

from __future__ import annotations

from packages.execution.models import ExecutionRejection


def execution_rejection(
    reason_code: str,
    message: str,
    *,
    details: dict[str, str] | None = None,
) -> ExecutionRejection:
    return ExecutionRejection(
        reason_code=reason_code,
        message=message,
        details=details or {},
    )

