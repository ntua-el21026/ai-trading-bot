from apps.workers.app.retry_policies import (
    AI_ACTIVITY,
    BROKER_ORDER_SUBMIT,
    DEFAULT_NON_CRITICAL_ACTIVITY,
    PROTECTIVE_STOP,
    retry_policy_contracts_from_config,
)
from apps.workers.app.worker import task_queue_names, workflow_classes_by_task_queue
from packages.core.config import load_app_config


def test_temporal_config_loads_spec_task_queues() -> None:
    config = load_app_config().temporal

    assert config.address == "localhost:7233"
    assert config.namespace == "autonomous-trading"
    assert task_queue_names(config) == (
        "market-data-task-queue",
        "strategy-task-queue",
        "ai-research-task-queue",
        "execution-task-queue",
        "reconciliation-task-queue",
        "reporting-task-queue",
    )


def test_temporal_task_queue_mapping_uses_dedicated_execution_queues() -> None:
    config = load_app_config().temporal
    mapping = workflow_classes_by_task_queue(config)

    execution_names = {workflow.__name__ for workflow in mapping["execution-task-queue"]}
    reconciliation_names = {workflow.__name__ for workflow in mapping["reconciliation-task-queue"]}
    reporting_names = {workflow.__name__ for workflow in mapping["reporting-task-queue"]}

    assert "OrderLifecycleWorkflow" in execution_names
    assert "PositionLifecycleWorkflow" in execution_names
    assert "KillSwitchWorkflow" in execution_names
    assert reconciliation_names == {"ReconciliationWorkflow"}
    assert reporting_names == {"ReportingWorkflow"}


def test_temporal_retry_policy_contracts_include_spec_safety_placeholders() -> None:
    config = load_app_config().temporal
    policies = retry_policy_contracts_from_config(config)

    assert policies[DEFAULT_NON_CRITICAL_ACTIVITY].policy.maximum_attempts == 3
    assert policies[BROKER_ORDER_SUBMIT].policy.maximum_attempts == 1
    assert policies[BROKER_ORDER_SUBMIT].retry_only_after_idempotency_lookup is True
    assert policies[PROTECTIVE_STOP].policy.maximum_attempts == 3
    assert policies[AI_ACTIVITY].policy.maximum_attempts == 2
    assert policies[AI_ACTIVITY].fallback_on_failure == "neutral"
