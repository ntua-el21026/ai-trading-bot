from __future__ import annotations

import pytest

from packages.ledger.connection import connect_in_memory_sqlite
from packages.ledger.repositories import SQLiteLedgerRepository
from packages.paper import (
    FIRST_SESSION_APPROVAL_MARKER,
    FirstSessionResult,
    default_first_session_input,
    run_first_controlled_paper_session_check,
)
from scripts.check_first_controlled_paper_session import main as script_main


def _repository() -> SQLiteLedgerRepository:
    return SQLiteLedgerRepository(connect_in_memory_sqlite())


def _run(
    scenario_id: str = "happy_path",
) -> tuple[FirstSessionResult, SQLiteLedgerRepository]:
    repository = _repository()
    result = run_first_controlled_paper_session_check(
        default_first_session_input(scenario_id),
        repository=repository,
    )
    return result, repository


def test_happy_path_wires_full_fake_local_first_session_evidence_chain() -> None:
    result, repository = _run("happy_path")

    assert result.success is True
    assert result.refused is False
    assert result.unsafe is False
    assert result.paper_operations_started is False
    assert result.actual_paper_trading_started is False
    assert result.real_broker_writes_attempted is False
    assert result.external_calls_attempted is False
    assert result.schedules_activated is False
    assert result.live_trading_enabled is False
    assert result.autonomous_live_execution_enabled is False
    assert result.level4_ready is False
    assert result.safety_flags.safe is True
    assert result.safety_flags.fake_broker_used is True
    assert result.safety_flags.fake_alert_adapter_used is True
    assert result.safety_flags.neutral_ai_news_used is True
    assert result.safety_flags.real_broker_writes_attempted is False

    evidence = result.evidence_package
    assert evidence.session_id == "first-controlled-paper-session-happy_path"
    assert evidence.timestamp.tzinfo is not None
    assert evidence.operator_approval_marker == FIRST_SESSION_APPROVAL_MARKER
    assert evidence.commit_hash
    assert evidence.spec_version == "Autonomous_AI_Trading_Bot_SPEC_v0.3.md"
    assert evidence.config_safety_snapshot["secrets"]["DATABASE_URL"] == (
        "<redacted-not-inspected>"
    )
    assert evidence.paper_endpoint_proof.accepted is True
    assert evidence.paper_endpoint_proof.external_call_performed is False
    assert evidence.live_endpoint_rejection_proof.accepted is False
    assert evidence.no_schedule_assertion is True
    assert evidence.no_leverage_assertion is True
    assert evidence.pre_run_reconciliation_id is not None
    assert evidence.pre_run_reconciliation_result == "clean"
    assert evidence.candidate_id == "candidate-happy_path"
    assert evidence.ai_news_output_id == "ai-output-happy_path"
    assert evidence.ai_news_fallback_marker == "neutral_fallback_no_provider_call"
    assert evidence.decision_id is not None
    assert evidence.risk_check_id == "risk-check-happy_path"
    assert evidence.execution_intent_id == "intent-happy_path"
    assert evidence.order_id is not None
    assert evidence.broker_order_id == "paper-order-1"
    assert evidence.client_order_id is not None
    assert evidence.fill_id == "fill-happy_path"
    assert evidence.broker_fill_id == "fake-fill-happy_path"
    assert evidence.protective_stop_order_id is not None
    assert evidence.protective_stop_client_order_id is not None
    assert evidence.stop_verification_result == "verified"
    assert evidence.post_run_reconciliation_id == "reconciliation-happy_path"
    assert evidence.post_run_reconciliation_result == "clean"
    assert evidence.report_id is not None
    assert evidence.dashboard_snapshot_status == "database_read_model"
    assert evidence.alert_delivery_summary.mode == "fake"
    assert evidence.alert_delivery_summary.fake_delivery_count >= 1
    assert evidence.alert_delivery_summary.real_delivery_count == 0
    assert evidence.alert_delivery_summary.external_calls_performed is False

    assert len(repository.list_trade_candidates()) == 1
    assert len(repository.list_ai_research_outputs()) == 1
    assert len(repository.list_trade_decisions()) == 1
    assert len(repository.list_recent_risk_checks()) == 1
    assert len(repository.list_active_execution_intents()) == 1
    assert len(repository.list_orders()) == 2
    assert len(repository.list_fills()) == 1
    assert len(repository.list_broker_reconciliations()) == 2
    assert len(repository.list_reports()) >= 2
    assert repository.get_report(evidence.report_id) is not None


def test_default_run_makes_no_external_calls_or_real_broker_writes() -> None:
    result, repository = _run()

    assert result.success is True
    assert result.safety_flags.external_calls_attempted is False
    assert result.safety_flags.real_broker_writes_attempted is False
    assert result.safety_flags.managed_database_used is False
    assert result.safety_flags.temporal_cloud_connected is False
    assert result.safety_flags.real_alerts_sent is False
    assert repository.list_orders()


@pytest.mark.parametrize(
    ("scenario_id", "expected_reason"),
    (
        ("missing_operator_approval", "operator_approval_missing"),
        ("live_endpoint_rejected", "live_endpoint_forbidden"),
        ("dirty_reconciliation_blocks", "pre_run_reconciliation_not_clean"),
        ("missing_execution_intent", "execution_intent_required"),
        ("short_rejected", "short_side_forbidden"),
        ("leverage_rejected", "leverage_not_allowed"),
        ("unsupported_asset_rejected", "unsupported_asset_class"),
    ),
)
def test_refusal_scenarios_block_before_order_simulation(
    scenario_id: str,
    expected_reason: str,
) -> None:
    result, repository = _run(scenario_id)

    assert result.success is False
    assert result.refused is True
    assert result.unsafe is False
    assert expected_reason in result.refusal_reasons
    assert result.evidence_package.order_id is None
    assert result.evidence_package.broker_order_id is None
    assert result.evidence_package.client_order_id is None
    assert result.evidence_package.fill_id is None
    assert result.evidence_package.protective_stop_order_id is None
    assert result.evidence_package.alert_delivery_summary.external_calls_performed is False
    assert repository.list_orders() == ()
    assert repository.list_fills() == ()


@pytest.mark.parametrize(
    ("scenario_id", "expected_reason"),
    (
        ("kill_switch_blocks", "kill_switch_paused_new_risk"),
        ("duplicate_intent_blocks", "active_duplicate_intent"),
    ),
)
def test_risk_gate_refusals_block_fake_order_submit(
    scenario_id: str,
    expected_reason: str,
) -> None:
    result, repository = _run(scenario_id)

    assert result.success is False
    assert result.refused is True
    assert expected_reason in result.refusal_reasons
    assert result.evidence_package.execution_intent_id is None
    assert result.evidence_package.order_id is None
    assert result.evidence_package.broker_order_id is None
    assert repository.list_orders() == ()
    assert repository.list_fills() == ()


def test_missing_protective_stop_after_fill_creates_critical_unsafe_result() -> None:
    result, repository = _run("missing_stop_incident")

    assert result.success is False
    assert result.refused is False
    assert result.unsafe is True
    assert result.evidence_package.execution_intent_id == "intent-missing_protective_stop"
    assert result.evidence_package.broker_order_id == "paper-order-1"
    assert result.evidence_package.fill_id == "fill-missing_protective_stop"
    assert result.evidence_package.protective_stop_order_id is None
    assert result.evidence_package.stop_verification_result == "not_verified"
    assert any(incident.reason_code == "missing_protective_stop" for incident in result.incidents)
    assert any(incident.severity == "critical" for incident in result.incidents)
    assert len(repository.list_recent_incidents()) >= 1


def test_partial_fill_uses_stop_for_filled_quantity() -> None:
    result, repository = _run("partial_fill")

    assert result.success is True
    assert result.evidence_package.fill_id == "fill-partial_fill"
    assert result.evidence_package.protective_stop_order_id is not None
    stop_orders = [
        order for order in repository.list_orders() if order.client_order_id.endswith("-stop")
    ]
    assert len(stop_orders) == 1
    assert stop_orders[0].quantity == 4.0


def test_script_returns_zero_for_happy_path_and_nonzero_for_unsafe_scenarios(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert script_main(["--scenario", "happy_path"]) == 0
    happy_output = capsys.readouterr().out
    assert "Actual paper trading has not started" in happy_output
    assert '"success": true' in happy_output

    assert script_main(["--scenario", "kill_switch_blocks"]) == 1
    refusal_output = capsys.readouterr().out
    assert '"refused": true' in refusal_output

    assert script_main(["--scenario", "missing_stop_incident"]) == 1
    unsafe_output = capsys.readouterr().out
    assert '"unsafe": true' in unsafe_output


def test_script_refuses_non_fake_mode(capsys: pytest.CaptureFixture[str]) -> None:
    assert script_main(["--mode", "real-paper"]) == 2
    assert "Refusing non-fake first-session mode." in capsys.readouterr().err
