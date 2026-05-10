from __future__ import annotations

import pytest

from packages.ledger.connection import connect_in_memory_sqlite
from packages.ledger.repositories import SQLiteLedgerRepository
from packages.paper import (
    MILESTONE_30_FAKE_OPERATOR_APPROVAL,
    MILESTONE_30_REAL_OPERATOR_APPROVAL,
    RealSessionResult,
    default_first_session_input,
    default_real_session_gate_config,
    run_first_controlled_paper_session_check,
    run_real_first_controlled_paper_session_gate,
)
from packages.paper.real_gate import RealSessionScenarioId
from scripts.check_first_controlled_paper_session import main as m29_script_main
from scripts.run_first_controlled_paper_session import main as real_gate_script_main


def _repository() -> SQLiteLedgerRepository:
    return SQLiteLedgerRepository(connect_in_memory_sqlite())


def _run_fake_real_gate(
    scenario_id: str = "happy_path",
) -> tuple[RealSessionResult, SQLiteLedgerRepository]:
    repository = _repository()
    config = default_real_session_gate_config(
        scenario_id,
        mode="fake",
        operator_approval_marker=MILESTONE_30_FAKE_OPERATOR_APPROVAL,
    )
    result = run_real_first_controlled_paper_session_gate(config, repository=repository)
    return result, repository


def _run_real_refusal(
    scenario_id: str,
    *,
    allow_real_writes: bool = True,
    operator_approval_marker: str | None = MILESTONE_30_REAL_OPERATOR_APPROVAL,
) -> RealSessionResult:
    config = default_real_session_gate_config(
        scenario_id,
        mode="real-gated",
        operator_approval_marker=operator_approval_marker,
    ).model_copy(update={"allow_real_alpaca_paper_writes": allow_real_writes})
    return run_real_first_controlled_paper_session_gate(config)


def test_default_real_session_path_refuses_before_preflight_or_write() -> None:
    result = run_real_first_controlled_paper_session_gate()

    assert result.success is False
    assert result.refused is True
    assert result.preflight is None
    assert result.first_session_evidence is None
    assert result.real_broker_writes_attempted is False
    assert result.external_calls_attempted is False
    assert "operator_approval_missing" in result.refusal_reasons


def test_fake_mode_with_all_gates_reaches_fake_order_simulation_only() -> None:
    result, repository = _run_fake_real_gate()

    assert result.success is True
    assert result.refused is False
    assert result.unsafe is False
    assert result.actual_paper_trading_started is False
    assert result.real_broker_orders_submitted is False
    assert result.real_broker_writes_attempted is False
    assert result.external_calls_attempted is False
    assert result.schedules_activated is False
    assert result.live_trading_enabled is False
    assert result.autonomous_live_execution_enabled is False
    assert result.leverage_enabled is False
    assert result.ai_broker_write_authority is False
    assert result.real_gate_evidence.real_write_gates_evaluated is True
    assert result.real_gate_evidence.real_write_gates_passed is True
    assert result.real_gate_evidence.broker_adapter_mode == "fake"
    assert result.real_gate_evidence.broker_endpoint_mode == "paper"
    assert result.real_gate_evidence.preflight_evidence_id is not None
    assert result.real_gate_evidence.reconciliation_evidence_id is not None
    assert result.real_gate_evidence.protective_stop_plan_id == "first-session-stop-plan"
    assert result.real_gate_evidence.cleanup_policy_id is not None
    assert result.real_gate_evidence.external_calls_attempted is False
    assert result.real_gate_evidence.real_broker_writes_attempted is False
    assert result.real_gate_evidence.ai_broker_write_authority is False
    assert result.first_session_evidence is not None
    assert result.first_session_evidence.order_id is not None
    assert result.first_session_evidence.client_order_id is not None
    assert result.first_session_evidence.fill_id is not None
    assert result.first_session_evidence.protective_stop_order_id is not None
    assert len(repository.list_orders()) == 2


def test_real_gated_all_gates_present_still_defers_execution_in_milestone_30() -> None:
    config = default_real_session_gate_config(
        "happy_path",
        mode="real-gated",
        operator_approval_marker=MILESTONE_30_REAL_OPERATOR_APPROVAL,
    ).model_copy(update={"allow_real_alpaca_paper_writes": True})

    result = run_real_first_controlled_paper_session_gate(config)

    assert result.success is False
    assert result.refused is True
    assert result.ready_for_future_real_execution is True
    assert result.first_session_evidence is None
    assert result.real_broker_writes_attempted is False
    assert "real_session_execution_deferred_milestone_30" in result.refusal_reasons


@pytest.mark.parametrize(
    ("scenario_id", "expected_reason", "allow_real_writes"),
    (
        ("missing_operator_approval", "operator_approval_missing", True),
        (
            "missing_real_write_gate",
            "real_broker_writes_not_explicitly_allowed",
            False,
        ),
        ("live_endpoint_rejected", "live_endpoint_detected", True),
        ("paper_endpoint_not_proven", "paper_endpoint_not_proven", True),
        ("live_trading_enabled", "live_trading_enabled", True),
        (
            "autonomous_live_execution_enabled",
            "autonomous_live_execution_enabled",
            True,
        ),
        ("schedules_active", "schedules_active_or_expected", True),
        ("leverage_rejected", "leverage_not_allowed", True),
        ("gross_exposure_rejected", "gross_exposure_exceeds_1x", True),
        ("short_rejected", "short_side_forbidden", True),
        ("unsupported_asset_rejected", "unsupported_asset_class:crypto", True),
        ("unsupported_order_type_rejected", "unsupported_order_type", True),
        (
            "dirty_reconciliation_blocks",
            "pre_run_reconciliation_not_clean",
            True,
        ),
        ("kill_switch_blocks", "kill_switch_blocks_new_risk", True),
        ("blocking_incident_blocks", "unresolved_blocking_incident", True),
        ("duplicate_intent_blocks", "active_duplicate_intent", True),
        ("missing_execution_intent", "execution_intent_required", True),
        ("missing_idempotency_key", "idempotency_key_required", True),
        ("missing_protective_stop_plan", "protective_stop_plan_required", True),
        ("missing_cleanup_policy", "cleanup_policy_required", True),
        (
            "missing_evidence_persistence",
            "evidence_persistence_target_required",
            True,
        ),
        ("ambiguous_broker_state", "ambiguous_broker_state", True),
        ("ai_broker_write_request_rejected", "ai_broker_write_forbidden", True),
    ),
)
def test_real_gated_refusal_cases_block_before_order_simulation(
    scenario_id: RealSessionScenarioId,
    expected_reason: str,
    allow_real_writes: bool,
) -> None:
    operator_approval = (
        None
        if scenario_id == "missing_operator_approval"
        else MILESTONE_30_REAL_OPERATOR_APPROVAL
    )
    result = _run_real_refusal(
        scenario_id,
        allow_real_writes=allow_real_writes,
        operator_approval_marker=operator_approval,
    )

    assert result.success is False
    assert result.refused is True
    assert result.unsafe is False
    assert expected_reason in result.refusal_reasons
    assert result.first_session_evidence is None
    assert result.real_broker_orders_submitted is False
    assert result.real_broker_writes_attempted is False
    assert result.external_calls_attempted is False


def test_missing_protective_stop_verification_after_fake_fill_is_critical_unsafe() -> None:
    result, repository = _run_fake_real_gate("missing_stop_incident")

    assert result.success is False
    assert result.refused is False
    assert result.unsafe is True
    assert result.first_session_evidence is not None
    assert result.first_session_evidence.fill_id == "fill-missing_protective_stop"
    assert result.first_session_evidence.protective_stop_order_id is None
    assert result.first_session_evidence.stop_verification_result == "not_verified"
    assert any(incident.reason_code == "missing_protective_stop" for incident in result.incidents)
    assert any(incident.severity == "critical" for incident in result.incidents)
    assert len(repository.list_recent_incidents()) >= 1
    assert result.real_broker_writes_attempted is False


def test_real_gate_evidence_contains_required_readiness_fields() -> None:
    result, _repository = _run_fake_real_gate()
    evidence = result.real_gate_evidence

    assert evidence.real_write_gates_evaluated is True
    assert evidence.real_write_gates_passed is True
    assert evidence.broker_adapter_mode == "fake"
    assert evidence.broker_endpoint_mode == "paper"
    assert evidence.preflight_evidence_id is not None
    assert evidence.reconciliation_evidence_id is not None
    assert evidence.protective_stop_plan_id == "first-session-stop-plan"
    assert evidence.cleanup_policy_id is not None
    assert evidence.refusal_reason_ids == ()
    assert evidence.alert_mode == "fake"
    assert evidence.ledger_persistence_mode == "local_sqlite"
    assert evidence.external_calls_attempted is False
    assert evidence.real_broker_writes_attempted is False
    assert evidence.real_broker_orders_submitted is False
    assert evidence.ai_broker_write_authority is False
    gate_names = {gate.gate_name for gate in evidence.gate_evaluations}
    assert "real_write_permission" in gate_names
    assert "ai_has_no_broker_authority" in gate_names


def test_ai_news_output_cannot_trigger_broker_write_directly() -> None:
    result = _run_real_refusal("ai_broker_write_request_rejected", allow_real_writes=True)

    assert result.success is False
    assert result.refused is True
    assert "ai_broker_write_forbidden" in result.refusal_reasons
    assert result.ai_broker_write_authority is False
    assert result.real_broker_writes_attempted is False


def test_milestone_30_script_default_refuses_and_fake_mode_can_pass(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert real_gate_script_main([]) == 1
    default_output = capsys.readouterr().out
    assert "Actual paper trading has not started" in default_output
    assert '"refused": true' in default_output
    assert '"real_broker_writes_attempted": false' in default_output

    assert (
        real_gate_script_main(
            [
                "--mode",
                "fake",
                "--scenario",
                "happy_path",
                "--operator-approval",
                MILESTONE_30_FAKE_OPERATOR_APPROVAL,
            ],
        )
        == 0
    )
    happy_output = capsys.readouterr().out
    assert '"success": true' in happy_output
    assert '"real_broker_orders_submitted": false' in happy_output


def test_milestone_30_script_returns_nonzero_for_refusal_scenario(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert (
        real_gate_script_main(
            [
                "--mode",
                "fake",
                "--scenario",
                "live_endpoint_rejected",
                "--operator-approval",
                MILESTONE_30_FAKE_OPERATOR_APPROVAL,
            ],
        )
        == 1
    )
    output = capsys.readouterr().out
    assert '"refused": true' in output
    assert '"external_calls_attempted": false' in output


def test_milestone_29_fake_local_script_still_works(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert m29_script_main(["--scenario", "happy_path"]) == 0
    assert '"success": true' in capsys.readouterr().out

    result = run_first_controlled_paper_session_check(
        default_first_session_input("happy_path"),
        repository=_repository(),
    )
    assert result.success is True
    assert result.real_broker_writes_attempted is False
