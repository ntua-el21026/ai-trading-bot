from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from packages.core.config import load_app_config
from packages.paper.readiness import (
    PaperOperationsReadinessEvidence,
    build_repository_readiness_evidence,
    config_safety_invariants_hold,
    evaluate_paper_operations_readiness,
)
from scripts.check_paper_operations_readiness import run_paper_operations_readiness_check


def complete_evidence() -> PaperOperationsReadinessEvidence:
    return PaperOperationsReadinessEvidence(
        config_safety=True,
        database_migration_schema_crud_evidence=True,
        managed_db_runtime_explicitly_gated=True,
        temporal_local_tests_evidence=True,
        temporal_cloud_dev_smoke_evidence=True,
        alpaca_readonly_smoke_evidence=True,
        alpaca_lifecycle_smoke_evidence=True,
        ai_news_layer_implemented=True,
        marketaux_alpha_vantage_smoke_evidence=True,
        openai_structured_smoke_evidence=True,
        openai_web_fallback_disabled_by_default=True,
        telegram_harness_implemented=True,
        telegram_smoke_evidence=True,
        alert_real_delivery_disabled_by_default=True,
        email_resend_deferred=True,
        dashboard_runtime_smoke_evidence=True,
        vercel_preview_deployment_evidence=True,
        dashboard_no_secrets_exposed=True,
        dashboard_no_order_entry_ui=True,
        dashboard_no_workers_on_vercel=True,
    )


def test_readiness_model_success_path_with_fixture_evidence() -> None:
    result = evaluate_paper_operations_readiness(complete_evidence())

    assert result.ready_for_first_controlled_paper_session is True
    assert result.hard_failures == ()
    assert result.missing_required_evidence == ()
    assert result.paper_operations_started is False
    assert result.frozen_paper_evidence is False
    assert result.level4_ready is False


def test_missing_21b_evidence_reports_not_ready() -> None:
    evidence = complete_evidence().model_copy(update={"alpaca_lifecycle_smoke_evidence": False})

    result = evaluate_paper_operations_readiness(evidence)

    assert result.ready_for_first_controlled_paper_session is False
    assert "broker_evidence" in result.missing_required_evidence


def test_missing_temporal_cloud_evidence_reports_not_ready() -> None:
    evidence = complete_evidence().model_copy(update={"temporal_cloud_dev_smoke_evidence": False})

    result = evaluate_paper_operations_readiness(evidence)

    assert result.ready_for_first_controlled_paper_session is False
    assert "temporal_evidence" in result.missing_required_evidence


def test_missing_dashboard_preview_evidence_reports_not_ready() -> None:
    evidence = complete_evidence().model_copy(update={"vercel_preview_deployment_evidence": False})

    result = evaluate_paper_operations_readiness(evidence)

    assert result.ready_for_first_controlled_paper_session is False
    assert "dashboard_evidence" in result.missing_required_evidence


def test_live_trading_enabled_reports_hard_failure() -> None:
    app_config = load_app_config()
    unsafe_config = app_config.model_copy(
        update={"system": app_config.system.model_copy(update={"live_trading_enabled": True})}
    )
    evidence = complete_evidence().model_copy(
        update={"config_safety": config_safety_invariants_hold(unsafe_config)}
    )

    result = evaluate_paper_operations_readiness(evidence)

    assert result.ready_for_first_controlled_paper_session is False
    assert "config_safety" in result.hard_failures


def test_autonomous_execution_enabled_reports_hard_failure() -> None:
    app_config = load_app_config()
    unsafe_config = app_config.model_copy(
        update={
            "system": app_config.system.model_copy(update={"autonomous_execution_enabled": True})
        }
    )
    evidence = complete_evidence().model_copy(
        update={"config_safety": config_safety_invariants_hold(unsafe_config)}
    )

    result = evaluate_paper_operations_readiness(evidence)

    assert result.ready_for_first_controlled_paper_session is False
    assert "config_safety" in result.hard_failures


def test_schedules_activated_reports_hard_failure() -> None:
    evidence = complete_evidence().model_copy(update={"schedules_activated": True})

    result = evaluate_paper_operations_readiness(evidence)

    assert result.ready_for_first_controlled_paper_session is False
    assert "schedules_not_activated" in result.hard_failures


def test_actual_paper_trading_started_is_rejected() -> None:
    payload = complete_evidence().model_dump()
    payload["actual_paper_trading_started"] = True
    with pytest.raises(ValidationError, match="actual paper trading"):
        PaperOperationsReadinessEvidence.model_validate(payload)


def test_level4_ready_is_rejected() -> None:
    payload = complete_evidence().model_dump()
    payload["level4_ready"] = True
    with pytest.raises(ValidationError, match="Level 4"):
        PaperOperationsReadinessEvidence.model_validate(payload)


def test_script_default_behavior_does_not_call_external_services() -> None:
    result = run_paper_operations_readiness_check()

    assert result["external_calls_performed"] is False
    assert result["broker_writes_attempted"] is False
    assert result["ai_news_calls_performed"] is False
    assert result["real_alerts_sent"] is False
    assert result["schedules_activated"] is False
    assert result["deployment_performed"] is False


def test_sanitized_output_contains_no_secrets() -> None:
    result = evaluate_paper_operations_readiness(complete_evidence())

    serialized = json.dumps(result.to_sanitized_dict())

    assert "paper-secret" not in serialized
    assert "DATABASE_URL=" not in serialized
    assert "TELEGRAM_BOT_TOKEN" not in serialized


def test_repository_evidence_current_status_is_ready_for_future_session() -> None:
    evidence = build_repository_readiness_evidence(
        dashboard_runtime_smoke_evidence=True,
        vercel_preview_guardrails_evidence=True,
    )
    result = evaluate_paper_operations_readiness(evidence)

    assert result.ready_for_first_controlled_paper_session is True
    assert result.level4_ready is False
