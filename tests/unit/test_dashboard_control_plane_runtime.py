from __future__ import annotations

import pytest
from pydantic import ValidationError

from packages.control_plane.models import (
    ControlActionRequest,
    PaperOperationReadinessView,
    ProviderBudgetStatusView,
    TemporalRuntimeStatusView,
)
from packages.control_plane.runtime import (
    DASHBOARD_SMOKE_CONFIRM_VALUE,
    run_dashboard_control_plane_smoke,
    validate_safe_control_actions,
)
from packages.control_plane.service import build_unavailable_dashboard_snapshot


def test_dashboard_runtime_default_builds_fake_local_snapshot_without_side_effects() -> None:
    result = run_dashboard_control_plane_smoke(environ={})

    assert result.gates_loaded is False
    assert result.snapshot_built is True
    assert result.system_state_present is True
    assert result.workflows_present is True
    assert result.kill_switch_state_present is True
    assert result.execution_intents_present is True
    assert result.orders_present is True
    assert result.positions_present is True
    assert result.incidents_present is True
    assert result.reconciliation_present is True
    assert result.candidates_present is True
    assert result.ai_outputs_present is True
    assert result.reports_present is True
    assert result.risk_status_present is True
    assert result.alerting_status_present is True
    assert result.temporal_status_present is True
    assert result.safe_controls_validated is True
    assert result.temporal_dev_signal_checked is False
    assert result.broker_calls_performed is False
    assert result.ai_news_calls_performed is False
    assert result.alert_calls_performed is False
    assert result.schedules_created is False
    assert result.schedules_activated is False
    assert result.deployment_performed is False
    assert result.actual_paper_trading_started is False
    assert result.level4_ready is False


def test_dashboard_runtime_gates_load_for_fake_dispatch_smoke() -> None:
    result = run_dashboard_control_plane_smoke(
        environ={
            "RUN_DASHBOARD_CONTROL_PLANE_SMOKE": "1",
            "DASHBOARD_CONTROL_PLANE_SMOKE_CONFIRM": DASHBOARD_SMOKE_CONFIRM_VALUE,
            "DASHBOARD_CONTROL_PLANE_USE_TEMPORAL_DEV": "true",
            "DASHBOARD_CONTROL_PLANE_USE_MANAGED_DB": "false",
            "DASHBOARD_CONTROL_PLANE_ALLOW_CONTROL_SIGNALS": "false",
        }
    )

    assert result.gates_loaded is True
    assert result.snapshot_built is True
    assert result.safe_controls_validated is True
    assert result.temporal_dev_signal_checked is False
    assert result.broker_calls_performed is False
    assert result.ai_news_calls_performed is False
    assert result.alert_calls_performed is False


def test_dashboard_runtime_refuses_bad_confirmation_or_deployment_request() -> None:
    bad_confirm = run_dashboard_control_plane_smoke(
        environ={
            "RUN_DASHBOARD_CONTROL_PLANE_SMOKE": "1",
            "DASHBOARD_CONTROL_PLANE_SMOKE_CONFIRM": "WRONG",
        }
    )
    deployment = run_dashboard_control_plane_smoke(
        environ={
            "RUN_DASHBOARD_CONTROL_PLANE_SMOKE": "1",
            "DASHBOARD_CONTROL_PLANE_SMOKE_CONFIRM": DASHBOARD_SMOKE_CONFIRM_VALUE,
            "RUN_VERCEL_DASHBOARD_PREVIEW": "1",
            "VERCEL_DASHBOARD_PREVIEW_CONFIRM": "DASHBOARD_ONLY_NO_SECRETS_NO_WORKERS",
        }
    )

    assert bad_confirm.refused is True
    assert "missing_dashboard_control_plane_confirmation" in bad_confirm.refusal_reasons
    assert deployment.refused is True
    assert "deployment_not_allowed_for_milestone_25" in deployment.refusal_reasons
    assert deployment.deployment_performed is False


def test_dashboard_runtime_refuses_managed_db_mode_for_default_smoke() -> None:
    result = run_dashboard_control_plane_smoke(
        environ={
            "RUN_DASHBOARD_CONTROL_PLANE_SMOKE": "1",
            "DASHBOARD_CONTROL_PLANE_SMOKE_CONFIRM": DASHBOARD_SMOKE_CONFIRM_VALUE,
            "DASHBOARD_CONTROL_PLANE_USE_MANAGED_DB": "true",
        }
    )

    assert result.refused is True
    assert "managed_db_dashboard_runtime_not_enabled" in result.refusal_reasons


def test_safe_control_action_validation_uses_fake_dispatcher_only() -> None:
    assert validate_safe_control_actions() is True


@pytest.mark.parametrize(
    "forbidden_action",
    [
        "submit_order",
        "cancel_order",
        "modify_strategy",
        "modify_risk_limits",
        "enable_live_trading",
        "enable_autonomous_execution",
        "natural_language_order",
    ],
)
def test_forbidden_control_actions_are_rejected(forbidden_action: str) -> None:
    with pytest.raises(ValidationError):
        ControlActionRequest.model_validate(
            {
                "action": forbidden_action,
                "requested_by": "operator",
                "requested_at": "2026-05-09T12:00:00Z",
                "reason": "not allowed",
                "idempotency_key": f"forbidden-{forbidden_action}",
            }
        )


def test_runtime_status_models_preserve_safety_boundaries() -> None:
    with pytest.raises(ValidationError, match="schedule"):
        TemporalRuntimeStatusView(schedules_created=True)

    with pytest.raises(ValidationError, match="paper trading"):
        PaperOperationReadinessView(actual_paper_trading_started=True)

    with pytest.raises(ValidationError, match="Level 4"):
        PaperOperationReadinessView(level4_ready=True)

    with pytest.raises(ValidationError, match="used count"):
        ProviderBudgetStatusView(provider="marketaux", daily_limit=1, used=2)


def test_dashboard_snapshot_includes_runtime_status_sections() -> None:
    snapshot = build_unavailable_dashboard_snapshot()

    assert snapshot.ai_quality_state.state == "unavailable"
    assert {budget.provider for budget in snapshot.provider_budget_status} == {
        "marketaux",
        "alpha_vantage",
        "openai",
    }
    assert snapshot.alerting_status.primary_provider == "telegram"
    assert snapshot.alerting_status.real_delivery_enabled is False
    assert snapshot.temporal_runtime_status.schedules_activated is False
    assert snapshot.paper_operation_readiness.actual_paper_trading_started is False
    assert snapshot.paper_operation_readiness.level4_ready is False


def test_dashboard_smoke_sanitized_output_contains_no_secret_values() -> None:
    result = run_dashboard_control_plane_smoke(
        environ={
            "RUN_DASHBOARD_CONTROL_PLANE_SMOKE": "1",
            "DASHBOARD_CONTROL_PLANE_SMOKE_CONFIRM": DASHBOARD_SMOKE_CONFIRM_VALUE,
            "TEMPORAL_API_KEY": "test-temporal-secret",
            "DATABASE_URL": "postgresql://user:secret@example.invalid/db",
        }
    )

    serialized = str(result.to_sanitized_dict())
    assert "test-temporal-secret" not in serialized
    assert "postgresql://" not in serialized
    assert result.secrets_printed is False
