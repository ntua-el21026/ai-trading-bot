"""Temporal retry-policy contracts aligned with the latest spec."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import TYPE_CHECKING

from temporalio.common import RetryPolicy

if TYPE_CHECKING:
    from packages.core.config import RetryDefaults, TemporalConfig


@dataclass(frozen=True)
class RetryPolicyContract:
    name: str
    policy: RetryPolicy
    retry_only_after_idempotency_lookup: bool = False
    fallback_on_failure: str | None = None


DEFAULT_NON_CRITICAL_ACTIVITY = "default_non_critical_activity"
BROKER_ORDER_SUBMIT = "broker_order_submit"
PROTECTIVE_STOP = "protective_stop"
AI_ACTIVITY = "ai_activity"


def build_default_activity_retry(retry_defaults: RetryDefaults) -> RetryPolicyContract:
    return RetryPolicyContract(
        name=DEFAULT_NON_CRITICAL_ACTIVITY,
        policy=RetryPolicy(
            initial_interval=timedelta(seconds=retry_defaults.initial_interval_seconds),
            backoff_coefficient=retry_defaults.backoff_coefficient,
            maximum_interval=timedelta(seconds=retry_defaults.maximum_interval_seconds),
            maximum_attempts=retry_defaults.maximum_attempts,
        ),
    )


DEFAULT_ACTIVITY_RETRY = RetryPolicyContract(
    name=DEFAULT_NON_CRITICAL_ACTIVITY,
    policy=RetryPolicy(
        initial_interval=timedelta(seconds=5),
        backoff_coefficient=2.0,
        maximum_interval=timedelta(seconds=60),
        maximum_attempts=3,
    ),
)

BROKER_ORDER_SUBMIT_RETRY = RetryPolicyContract(
    name=BROKER_ORDER_SUBMIT,
    policy=RetryPolicy(maximum_attempts=1),
    retry_only_after_idempotency_lookup=True,
)

PROTECTIVE_STOP_RETRY = RetryPolicyContract(
    name=PROTECTIVE_STOP,
    policy=RetryPolicy(
        initial_interval=timedelta(seconds=2),
        backoff_coefficient=2.0,
        maximum_interval=timedelta(seconds=10),
        maximum_attempts=3,
    ),
)

AI_ACTIVITY_RETRY = RetryPolicyContract(
    name=AI_ACTIVITY,
    policy=RetryPolicy(maximum_attempts=2),
    fallback_on_failure="neutral",
)


def retry_policy_contracts_from_config(
    config: TemporalConfig,
) -> dict[str, RetryPolicyContract]:
    return {
        DEFAULT_NON_CRITICAL_ACTIVITY: build_default_activity_retry(config.retry_defaults),
        BROKER_ORDER_SUBMIT: BROKER_ORDER_SUBMIT_RETRY,
        PROTECTIVE_STOP: PROTECTIVE_STOP_RETRY,
        AI_ACTIVITY: AI_ACTIVITY_RETRY,
    }
