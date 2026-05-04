"""Passive order lifecycle transition validation.

This module validates local state transitions only. It does not call a broker or submit orders.
"""

from __future__ import annotations

from packages.execution.models import (
    ExecutionRejection,
    OrderLifecycleState,
    OrderLifecycleStatus,
    OrderLifecycleTransitionResult,
)

ALLOWED_TRANSITIONS: dict[OrderLifecycleStatus, frozenset[OrderLifecycleStatus]] = {
    "created": frozenset({"risk_checked", "rejected", "expired", "cancelled"}),
    "risk_checked": frozenset({"ready_for_broker_adapter", "rejected", "expired", "cancelled"}),
    "ready_for_broker_adapter": frozenset({"submitted", "rejected", "expired", "cancelled"}),
    "submitted": frozenset({"acknowledged", "rejected", "manual_review_required"}),
    "acknowledged": frozenset(
        {"partially_filled", "filled", "cancelled", "manual_review_required"}
    ),
    "partially_filled": frozenset(
        {"filled", "protective_stop_pending", "cancelled", "manual_review_required"}
    ),
    "filled": frozenset({"protective_stop_pending", "manual_review_required"}),
    "protective_stop_pending": frozenset({"protected", "manual_review_required"}),
    "protected": frozenset({"cancelled", "manual_review_required"}),
    "cancelled": frozenset(),
    "rejected": frozenset(),
    "expired": frozenset(),
    "manual_review_required": frozenset({"cancelled"}),
}


def transition_order_lifecycle(
    state: OrderLifecycleState,
    next_status: OrderLifecycleStatus,
) -> OrderLifecycleTransitionResult:
    allowed = ALLOWED_TRANSITIONS[state.status]
    if next_status not in allowed:
        return OrderLifecycleTransitionResult(
            accepted=False,
            state=state,
            rejection=ExecutionRejection(
                reason_code="invalid_order_lifecycle_transition",
                message=f"cannot transition {state.status} to {next_status}",
                details={"current_status": state.status, "next_status": next_status},
            ),
        )
    next_state = OrderLifecycleState(
        client_order_id=state.client_order_id,
        status=next_status,
        history=(*state.history, next_status),
    )
    return OrderLifecycleTransitionResult(accepted=True, state=next_state)
