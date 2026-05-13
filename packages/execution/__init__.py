"""Passive execution-core contracts and helpers."""

from packages.execution.execution_intent import create_execution_intent, intent_is_expired
from packages.execution.idempotency import (
    build_client_order_id_root,
    duplicate_intent_key,
    has_duplicate_intent,
    short_hash,
)
from packages.execution.models import (
    DuplicateIntentKey,
    ExecutionIntent,
    ExecutionRejection,
    OrderLifecycleState,
    OrderLifecycleTransitionResult,
)
from packages.execution.order_lifecycle import transition_order_lifecycle
from packages.execution.rejections import execution_rejection
from packages.execution.scale_in import (
    AggregateProtectionCheck,
    EntryActionRole,
    OpenOrderRole,
    OpenOrderRoleClassification,
    ScaleInCandidate,
    ScaleInEligibilityResult,
    ScaleInEvidence,
    ScaleInIncident,
    ScaleInStopAction,
    ScaleInStopOutcome,
    SymbolExposureState,
    build_add_on_stop_action,
    check_aggregate_protection,
    classify_open_order_role,
    classify_symbol_open_orders,
    create_scale_in_execution_intent,
    evaluate_add_on_stop_outcome,
    evaluate_scale_in_eligibility,
    scale_in_evidence_from_result,
)

__all__ = [
    "DuplicateIntentKey",
    "ExecutionIntent",
    "ExecutionRejection",
    "AggregateProtectionCheck",
    "EntryActionRole",
    "OpenOrderRole",
    "OpenOrderRoleClassification",
    "OrderLifecycleState",
    "OrderLifecycleTransitionResult",
    "ScaleInCandidate",
    "ScaleInEligibilityResult",
    "ScaleInEvidence",
    "ScaleInIncident",
    "ScaleInStopAction",
    "ScaleInStopOutcome",
    "SymbolExposureState",
    "build_client_order_id_root",
    "build_add_on_stop_action",
    "check_aggregate_protection",
    "classify_open_order_role",
    "classify_symbol_open_orders",
    "create_execution_intent",
    "create_scale_in_execution_intent",
    "duplicate_intent_key",
    "execution_rejection",
    "evaluate_add_on_stop_outcome",
    "evaluate_scale_in_eligibility",
    "has_duplicate_intent",
    "intent_is_expired",
    "scale_in_evidence_from_result",
    "short_hash",
    "transition_order_lifecycle",
]
