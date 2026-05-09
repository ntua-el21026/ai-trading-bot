from __future__ import annotations

from apps.workers.app.temporal_client import (
    TEMPORAL_CLOUD_SMOKE_CONFIRM_VALUE,
    TemporalCloudSmokeSettings,
    temporal_cloud_connect_kwargs,
)
from apps.workers.app.temporal_cloud_smoke import (
    TemporalCloudSmokeResult,
    run_temporal_cloud_smoke,
)
from packages.core.config import load_app_config


def test_temporal_cloud_smoke_refuses_without_gates() -> None:
    result = run_temporal_cloud_smoke(environ={})

    assert result.refused is True
    assert result.gates_loaded is False
    assert result.connected_to_temporal_cloud is False
    assert result.schedules_created is False
    assert result.schedules_activated is False
    assert "missing_run_gate" in result.refusal_reasons
    assert "missing_confirmation_gate" in result.refusal_reasons


def test_temporal_cloud_smoke_refuses_without_confirmation() -> None:
    result = run_temporal_cloud_smoke(
        environ={
            "RUN_TEMPORAL_CLOUD_SMOKE": "1",
            "TEMPORAL_ADDRESS": "dev.temporal.example:7233",
            "TEMPORAL_NAMESPACE": "dev-namespace",
            "TEMPORAL_API_KEY": "test-temporal-key",
        }
    )

    assert result.refused is True
    assert result.gates_loaded is False
    assert "missing_confirmation_gate" in result.refusal_reasons
    assert result.connected_to_temporal_cloud is False


def test_temporal_cloud_smoke_refuses_without_required_connection_vars() -> None:
    result = run_temporal_cloud_smoke(
        environ={
            "RUN_TEMPORAL_CLOUD_SMOKE": "1",
            "TEMPORAL_CLOUD_SMOKE_CONFIRM": TEMPORAL_CLOUD_SMOKE_CONFIRM_VALUE,
        }
    )

    assert result.refused is True
    assert "missing_temporal_address" in result.refusal_reasons
    assert "missing_temporal_namespace" in result.refusal_reasons
    assert "missing_temporal_api_key" in result.refusal_reasons


def test_temporal_cloud_smoke_uses_selected_task_queue_with_fake_executor() -> None:
    async def fake_executor(
        settings: TemporalCloudSmokeSettings,
        _config: object,
    ) -> TemporalCloudSmokeResult:
        return TemporalCloudSmokeResult(
            gates_loaded=True,
            temporal_address_present=bool(settings.address),
            temporal_namespace_present=bool(settings.namespace),
            temporal_api_key_present=bool(settings.api_key),
            connected_to_temporal_cloud=True,
            namespace=settings.namespace,
            task_queue=settings.task_queue,
            worker_started=True,
            workflow_started=True,
            workflow_completed=True,
            signal_query_checked=True,
        )

    result = run_temporal_cloud_smoke(
        environ={
            "RUN_TEMPORAL_CLOUD_SMOKE": "1",
            "TEMPORAL_CLOUD_SMOKE_CONFIRM": TEMPORAL_CLOUD_SMOKE_CONFIRM_VALUE,
            "TEMPORAL_ADDRESS": "dev.temporal.example:7233",
            "TEMPORAL_NAMESPACE": "dev-namespace",
            "TEMPORAL_API_KEY": "test-temporal-key",
            "TEMPORAL_CLOUD_SMOKE_TASK_QUEUE": "reporting-task-queue",
            "TEMPORAL_CLOUD_SMOKE_WORKFLOW": "KillSwitchWorkflow",
        },
        executor=fake_executor,
    )

    assert result.gates_loaded is True
    assert result.connected_to_temporal_cloud is True
    assert result.task_queue == "reporting-task-queue"
    assert result.workflow_completed is True
    assert result.signal_query_checked is True
    assert result.schedules_created is False
    assert result.schedules_activated is False


def test_temporal_cloud_smoke_refuses_unknown_task_queue() -> None:
    result = run_temporal_cloud_smoke(
        environ={
            "RUN_TEMPORAL_CLOUD_SMOKE": "1",
            "TEMPORAL_CLOUD_SMOKE_CONFIRM": TEMPORAL_CLOUD_SMOKE_CONFIRM_VALUE,
            "TEMPORAL_ADDRESS": "dev.temporal.example:7233",
            "TEMPORAL_NAMESPACE": "dev-namespace",
            "TEMPORAL_API_KEY": "test-temporal-key",
            "TEMPORAL_CLOUD_SMOKE_TASK_QUEUE": "unknown-task-queue",
        }
    )

    assert result.refused is True
    assert "unknown_task_queue" in result.refusal_reasons


def test_temporal_cloud_smoke_refuses_unsupported_workflow() -> None:
    result = run_temporal_cloud_smoke(
        environ={
            "RUN_TEMPORAL_CLOUD_SMOKE": "1",
            "TEMPORAL_CLOUD_SMOKE_CONFIRM": TEMPORAL_CLOUD_SMOKE_CONFIRM_VALUE,
            "TEMPORAL_ADDRESS": "dev.temporal.example:7233",
            "TEMPORAL_NAMESPACE": "dev-namespace",
            "TEMPORAL_API_KEY": "test-temporal-key",
            "TEMPORAL_CLOUD_SMOKE_WORKFLOW": "OrderLifecycleWorkflow",
        }
    )

    assert result.refused is True
    assert "unsupported_smoke_workflow" in result.refusal_reasons


def test_temporal_cloud_connect_kwargs_enable_tls_and_api_key_without_sanitizing_values() -> None:
    settings = TemporalCloudSmokeSettings.from_env(
        {
            "RUN_TEMPORAL_CLOUD_SMOKE": "1",
            "TEMPORAL_CLOUD_SMOKE_CONFIRM": TEMPORAL_CLOUD_SMOKE_CONFIRM_VALUE,
            "TEMPORAL_ADDRESS": "dev.temporal.example:7233",
            "TEMPORAL_NAMESPACE": "dev-namespace",
            "TEMPORAL_API_KEY": "test-temporal-key",
        },
        load_app_config().temporal,
    )

    target_host, kwargs = temporal_cloud_connect_kwargs(settings)
    sanitized = settings.sanitized()

    assert target_host == "dev.temporal.example:7233"
    assert kwargs == {
        "namespace": "dev-namespace",
        "api_key": "test-temporal-key",
        "tls": True,
    }
    assert "test-temporal-key" not in repr(settings)
    assert "test-temporal-key" not in str(sanitized)
    assert sanitized["temporal_api_key_present"] is True


def test_temporal_cloud_smoke_sanitized_result_contains_no_secret_values() -> None:
    result = run_temporal_cloud_smoke(
        environ={
            "RUN_TEMPORAL_CLOUD_SMOKE": "1",
            "TEMPORAL_CLOUD_SMOKE_CONFIRM": TEMPORAL_CLOUD_SMOKE_CONFIRM_VALUE,
            "TEMPORAL_ADDRESS": "dev.temporal.example:7233",
            "TEMPORAL_NAMESPACE": "dev-namespace",
            "TEMPORAL_API_KEY": "test-temporal-key",
            "TEMPORAL_CLOUD_SMOKE_WORKFLOW": "OrderLifecycleWorkflow",
        }
    )

    sanitized = result.to_sanitized_dict()
    assert "test-temporal-key" not in str(sanitized)
    assert sanitized["temporal_api_key_present"] is True
    assert result.external_broker_calls is False
    assert result.external_ai_news_calls is False
    assert result.external_alert_calls is False
