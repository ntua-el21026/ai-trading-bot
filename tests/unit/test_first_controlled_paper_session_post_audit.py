from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, cast

from packages.broker.alpaca import ALPACA_PAPER_BASE_URL, AlpacaPaperAdapter
from packages.broker.fakes import DEFAULT_AS_OF, FakeAlpacaClient
from packages.core.config import load_app_config
from packages.paper import (
    M34_RESULT_EVIDENCE_PATH,
    M35D_POST_SESSION_AUDIT_EVIDENCE_PATH,
    M35E_HOLD_DECISION_EVIDENCE_PATH,
    M35F_INCIDENT_CLOSURE_EVIDENCE_PATH,
    M36_PROTECTED_POSITION_MONITORING_EVIDENCE_PATH,
    MILESTONE_35F_CLEANUP_APPROVAL,
    MILESTONE_37_CORRECTED_CLEANUP_APPROVAL,
    CorrectedCleanupRequest,
    IncidentClosureRequest,
    PostSessionAuditMode,
    PostSessionAuditRequest,
    ProtectedPositionMonitoringRequest,
    audit_m35c_result_packet,
    audit_m35d_post_session_audit_packet,
    audit_m35e_hold_decision_packet,
    audit_m35f_incident_closure_packet,
    audit_m36_protected_position_monitoring_packet,
    classify_cleanup_rejection,
    default_first_paper_session_execution_request,
    run_corrected_aapl_cleanup,
    run_first_controlled_paper_session_hold_decision,
    run_first_controlled_paper_session_incident_closure,
    run_first_controlled_paper_session_post_session_audit,
    run_protected_position_monitoring,
    write_corrected_cleanup_artifact,
    write_hold_decision_artifact,
    write_incident_closure_artifact,
    write_post_session_audit_artifact,
    write_protected_position_monitoring_artifact,
)
from packages.paper.execution import (
    MILESTONE_34_FAKE_OPERATOR_APPROVAL,
    _run_adapter_execution,
)


def test_m35c_result_packet_auditor_detects_safe_incident_status() -> None:
    audit, packet = audit_m35c_result_packet(M34_RESULT_EVIDENCE_PATH)

    assert packet is not None
    assert audit.parseable is True
    assert audit.milestone == "35C"
    assert audit.status == "incident"
    assert audit.actual_paper_trading_started is True
    assert audit.real_broker_orders_submitted is True
    assert audit.target_symbol == "AAPL"
    assert audit.entry_order_status == "filled"
    assert audit.fill_status == "filled"
    assert audit.filled_quantity == 1.0
    assert audit.fill_client_order_id_missing_incident_detected is True
    assert audit.recovery_stop_verified is True
    assert audit.post_session_no_go is True
    assert audit.blockers == ()


def test_fake_post_session_audit_recommends_hold_and_blocks_repetition() -> None:
    result = run_first_controlled_paper_session_post_session_audit(
        PostSessionAuditRequest(mode="fake", scenario_id="protected_position")
    )

    assert result.audit_completed is True
    assert result.go_no_go == "no_go"
    assert result.packet.cleanup_hold_decision_recommendation == (
        "HOLD_PROTECTED_POSITION_UNTIL_NEXT_REVIEW"
    )
    assert result.packet.current_broker_state.target_position_quantity == 1.0
    assert result.packet.current_broker_state.protective_stop_verified is True
    assert result.packet.current_broker_state.reconciliation_summary == (
        "protected_position_reconciled_for_hold"
    )
    assert result.broker_writes_performed_in_this_milestone is False
    assert result.packet.repeated_session_go_no_go == "no_go"


def test_m35d_post_session_audit_packet_parser_validates_hold_recommendation() -> None:
    audit = audit_m35d_post_session_audit_packet(M35D_POST_SESSION_AUDIT_EVIDENCE_PATH)

    assert audit.parseable is True
    assert audit.milestone == "35D"
    assert audit.audit_completed is True
    assert audit.recommendation == "HOLD_PROTECTED_POSITION_UNTIL_NEXT_REVIEW"
    assert audit.repeated_session_go_no_go == "no_go"
    assert audit.broker_writes_performed_in_m35d is False
    assert audit.protected_position_verified is True
    assert audit.blockers == ()


def test_hold_decision_packet_records_operator_decision_and_blocks_repetition() -> None:
    result = run_first_controlled_paper_session_hold_decision(
        PostSessionAuditRequest(mode="fake", scenario_id="protected_position")
    )

    assert result.hold_confirmed is True
    assert result.go_no_go == "no_go"
    assert result.operator_decision == "HOLD_PROTECTED_POSITION_UNTIL_NEXT_REVIEW"
    assert result.packet.operator_decision == "HOLD_PROTECTED_POSITION_UNTIL_NEXT_REVIEW"
    assert result.packet.cleanup_hold_recommendation == "CONTINUE_HOLD_UNTIL_NEXT_REVIEW"
    assert result.packet.repeated_session_go_no_go == "no_go"
    assert result.packet.frozen_validation_started is False
    assert result.packet.cleanup_performed is False
    assert result.packet.flatten_performed is False
    assert result.packet.cancel_performed is False
    assert result.packet.broker_writes_performed_in_this_milestone is False
    assert "repeated_sessions_blocked_until_later_audit_decision" in result.blockers


def test_hold_decision_missing_stop_is_no_go_and_requests_stop_repair() -> None:
    result = run_first_controlled_paper_session_hold_decision(
        PostSessionAuditRequest(mode="fake", scenario_id="missing_stop")
    )

    assert result.hold_confirmed is False
    assert result.go_no_go == "no_go"
    assert result.packet.cleanup_hold_recommendation == "REQUEST_OPERATOR_APPROVED_STOP_REPAIR"
    assert "aapl_protective_stop_not_verified" in result.blockers
    assert result.packet.broker_writes_performed_in_this_milestone is False


def test_hold_decision_unexpected_position_is_no_go() -> None:
    result = run_first_controlled_paper_session_hold_decision(
        PostSessionAuditRequest(mode="fake", scenario_id="unexpected_position")
    )

    assert result.hold_confirmed is False
    assert result.packet.cleanup_hold_recommendation == "MANUAL_BROKER_REVIEW_REQUIRED"
    assert "unexpected_positions_present" in result.blockers
    assert result.packet.broker_writes_performed_in_this_milestone is False


def test_hold_decision_unexpected_order_is_no_go() -> None:
    result = run_first_controlled_paper_session_hold_decision(
        PostSessionAuditRequest(mode="fake", scenario_id="unexpected_order")
    )

    assert result.hold_confirmed is False
    assert result.packet.cleanup_hold_recommendation == "MANUAL_BROKER_REVIEW_REQUIRED"
    assert "unexpected_open_orders_present" in result.blockers
    assert result.packet.broker_writes_performed_in_this_milestone is False


def test_hold_decision_packet_excludes_secret_values(tmp_path: Path) -> None:
    result = run_first_controlled_paper_session_hold_decision(
        PostSessionAuditRequest(mode="fake", scenario_id="protected_position")
    )
    path = write_hold_decision_artifact(result, tmp_path / "hold.json")
    payload = path.read_text(encoding="utf-8")

    assert "paper-secret" not in payload
    assert "paper-key" not in payload
    assert "postgres://" not in payload
    assert "sk-" not in payload
    hold_payload = json.loads(payload)["hold_decision"]
    assert hold_payload["operator_decision"] == "HOLD_PROTECTED_POSITION_UNTIL_NEXT_REVIEW"
    assert hold_payload["broker_writes_performed_in_this_milestone"] is False


def test_m35e_hold_decision_packet_parser_validates_hold_decision() -> None:
    audit = audit_m35e_hold_decision_packet(M35E_HOLD_DECISION_EVIDENCE_PATH)

    assert audit.parseable is True
    assert audit.milestone == "35E"
    assert audit.operator_decision == "HOLD_PROTECTED_POSITION_UNTIL_NEXT_REVIEW"
    assert audit.hold_confirmed is True
    assert audit.repeated_session_go_no_go == "no_go"
    assert audit.broker_writes_performed_in_m35e is False
    assert audit.protected_position_verified is True
    assert audit.blockers == ()


def test_m35f_incident_closure_packet_parser_validates_cleanup_rejection() -> None:
    audit = audit_m35f_incident_closure_packet(M35F_INCIDENT_CLOSURE_EVIDENCE_PATH)

    assert audit.parseable is True
    assert audit.milestone == "35F"
    assert audit.cleanup_attempted is True
    assert audit.cleanup_rejected_invalid_order_request is True
    assert audit.cleanup_sell_status == "failed:invalid_order_request"
    assert audit.cleanup_sell_broker_order_id_created is False
    assert audit.initial_protected_position_verified is True
    assert audit.final_protected_position_verified is True
    assert audit.repeated_session_go_no_go == "no_go"
    assert audit.blockers == ()


def test_monitoring_mode_parses_all_prior_evidence_and_reports_protected_hold() -> None:
    result = run_protected_position_monitoring(
        ProtectedPositionMonitoringRequest(mode="fake", scenario_id="protected_position")
    )

    assert result.monitoring_completed is True
    assert result.go_no_go == "no_go"
    assert result.packet.m35c_result_audit.parseable is True
    assert result.packet.m35d_post_session_audit.parseable is True
    assert result.packet.m35e_hold_decision_audit.parseable is True
    assert result.packet.m35f_incident_closure_audit.parseable is True
    assert result.packet.aapl_position_status == "open"
    assert result.packet.aapl_protective_stop_status == "open_verified"
    assert result.packet.broker_state_safe_to_continue_holding is True
    assert result.packet.current_broker_state.protective_stop_matches_position_quantity is True
    assert result.packet.open_orders_summary == "expected_protective_stop_only"
    assert result.packet.positions_summary == "expected_aapl_position_only"
    assert result.packet.repeated_session_go_no_go == "no_go"
    assert "repeated_sessions_blocked_pending_aapl_position_resolution" in result.blockers


def test_monitoring_mode_real_read_only_stub_never_calls_write_methods() -> None:
    client = _ReadOnlyGuardClient()

    def factory(*_args: Any, **_kwargs: Any) -> _ReadOnlyGuardClient:
        return client

    result = run_protected_position_monitoring(
        ProtectedPositionMonitoringRequest(
            mode="real-read-only",
            scenario_id="protected_position",
            confirm_paper_endpoint=True,
            confirm_no_broker_writes=True,
            confirm_no_new_entry=True,
            confirm_no_live_trading=True,
            confirm_no_autonomous_live=True,
            confirm_no_schedules=True,
            confirm_no_leverage=True,
        ),
        environ=_safe_broker_env(),
        client_factory=factory,
    )

    assert result.monitoring_completed is True
    assert result.real_read_only_calls_performed is True
    assert result.broker_writes_performed_in_m36 is False
    assert result.packet.broker_writes_performed_in_m36 is False
    assert client.submit_order_calls == 0
    assert client.cancel_order_calls == 0
    assert result.packet.cleanup_rejection_classification == "LIKELY_EXISTING_STOP_BLOCKED_SELL"


def test_monitoring_mode_reports_clean_state_when_aapl_flat_and_stop_gone() -> None:
    result = run_protected_position_monitoring(
        ProtectedPositionMonitoringRequest(mode="fake", scenario_id="flat")
    )

    assert result.monitoring_completed is True
    assert result.packet.aapl_position_status == "flat"
    assert result.packet.aapl_protective_stop_status == "not_open_or_not_found"
    assert result.packet.open_orders_summary == "no_open_orders"
    assert result.packet.positions_summary == "no_positions"
    assert result.packet.final_reconciliation_summary == "flat_no_open_position"
    assert result.packet.next_milestone_recommendation == (
        "DECLARE_POSITION_ALREADY_FLAT_PENDING_INCIDENT_CLOSURE_VERIFICATION"
    )
    assert result.packet.broker_writes_performed_in_m36 is False


def test_monitoring_mode_reports_critical_no_go_when_stop_missing() -> None:
    result = run_protected_position_monitoring(
        ProtectedPositionMonitoringRequest(mode="fake", scenario_id="missing_stop")
    )

    assert result.monitoring_completed is True
    assert result.packet.aapl_position_status == "open"
    assert result.packet.aapl_protective_stop_status == "missing_or_unverified"
    assert result.packet.broker_state_safe_to_continue_holding is False
    assert "critical_protective_stop_missing_or_unverified_while_position_open" in result.blockers
    assert result.packet.next_milestone_recommendation == "REQUEST_MANUAL_BROKER_REVIEW"


def test_monitoring_mode_detects_unexpected_open_orders() -> None:
    result = run_protected_position_monitoring(
        ProtectedPositionMonitoringRequest(mode="fake", scenario_id="unexpected_order")
    )

    assert result.packet.open_orders_summary == "unexpected_open_orders_present"
    assert "unexpected_open_orders_present" in result.blockers
    assert result.packet.next_milestone_recommendation == "REQUEST_MANUAL_BROKER_REVIEW"


def test_monitoring_mode_detects_unexpected_positions() -> None:
    result = run_protected_position_monitoring(
        ProtectedPositionMonitoringRequest(mode="fake", scenario_id="unexpected_position")
    )

    assert result.packet.positions_summary == "unexpected_positions_present"
    assert "unexpected_positions_present" in result.blockers
    assert result.packet.next_milestone_recommendation == "REQUEST_MANUAL_BROKER_REVIEW"


def test_cleanup_rejection_classification_handles_invalid_order_request() -> None:
    result = run_protected_position_monitoring(
        ProtectedPositionMonitoringRequest(mode="fake", scenario_id="protected_position")
    )

    assert result.packet.cleanup_rejection_classification == "LIKELY_EXISTING_STOP_BLOCKED_SELL"
    assert result.packet.cleanup_rejection_evidence_sufficient is True
    assert "open session-created sell stop" in result.packet.cleanup_rejection_explanation


def test_cleanup_rejection_classification_can_return_insufficient_evidence(tmp_path: Path) -> None:
    missing_audit = audit_m35f_incident_closure_packet(tmp_path / "missing-m35f.json")
    protected = run_protected_position_monitoring(
        ProtectedPositionMonitoringRequest(mode="fake", scenario_id="protected_position")
    )

    analysis = classify_cleanup_rejection(missing_audit, protected.packet.current_broker_state)

    assert analysis.classification == "INSUFFICIENT_EVIDENCE"
    assert analysis.evidence_sufficient is False


def test_monitoring_packet_contains_required_fields_and_excludes_secret_values(
    tmp_path: Path,
) -> None:
    result = run_protected_position_monitoring(
        ProtectedPositionMonitoringRequest(mode="fake", scenario_id="protected_position")
    )
    path = write_protected_position_monitoring_artifact(result, tmp_path / "m36.json")
    payload_text = path.read_text(encoding="utf-8")
    payload = json.loads(payload_text)
    packet = payload["protected_position_monitoring"]

    assert payload["milestone"] == "36"
    assert packet["m35c_result_packet_reference"] == M34_RESULT_EVIDENCE_PATH
    assert packet["m35d_post_session_audit_packet_reference"] == (
        M35D_POST_SESSION_AUDIT_EVIDENCE_PATH
    )
    assert packet["m35e_hold_decision_packet_reference"] == M35E_HOLD_DECISION_EVIDENCE_PATH
    assert packet["m35f_incident_closure_packet_reference"] == (
        M35F_INCIDENT_CLOSURE_EVIDENCE_PATH
    )
    assert packet["broker_writes_performed_in_m36"] is False
    assert packet["frozen_validation_started"] is False
    assert packet["level4_ready"] is False
    assert packet["live_trading_enabled"] is False
    assert packet["autonomous_live_execution_enabled"] is False
    assert packet["leverage_enabled"] is False
    assert "paper-secret" not in payload_text
    assert "paper-key" not in payload_text
    assert "postgres://" not in payload_text
    assert "sk-" not in payload_text


def test_m36_monitoring_packet_parser_validates_corrected_cleanup_recommendation() -> None:
    audit = audit_m36_protected_position_monitoring_packet(
        M36_PROTECTED_POSITION_MONITORING_EVIDENCE_PATH
    )

    assert audit.parseable is True
    assert audit.milestone == "36"
    assert audit.monitoring_completed is True
    assert audit.cleanup_rejection_classification == "LIKELY_EXISTING_STOP_BLOCKED_SELL"
    assert audit.protected_position_verified is True
    assert audit.broker_writes_performed_in_m36 is False
    assert audit.next_milestone_recommendation == (
        "REQUEST_OPERATOR_APPROVED_CORRECTED_CLEANUP_MILESTONE"
    )
    assert audit.blockers == ()


def test_corrected_cleanup_refuses_without_cleanup_approval_marker() -> None:
    result = run_corrected_aapl_cleanup(
        _m37_request("protected_position", cleanup_approval_marker=None)
    )

    assert result.incident_closed is False
    assert result.packet.broker_writes == ()
    assert "cleanup_approval_marker_required" in result.blockers


def test_corrected_cleanup_parses_m36_monitoring_packet() -> None:
    result = run_corrected_aapl_cleanup(_m37_request("flat"))

    assert result.packet.m36_monitoring_audit.parseable is True
    assert result.packet.m36_monitoring_audit.cleanup_rejection_classification == (
        "LIKELY_EXISTING_STOP_BLOCKED_SELL"
    )


def test_corrected_cleanup_refuses_non_aapl_target() -> None:
    result = run_corrected_aapl_cleanup(_m37_request("protected_position", target_symbol="MSFT"))

    assert result.incident_closed is False
    assert result.packet.broker_writes == ()
    assert "target_symbol_must_be_aapl" in result.blockers


def test_corrected_cleanup_refuses_ambiguous_broker_state() -> None:
    result = run_corrected_aapl_cleanup(_m37_request("missing_stop"))

    assert result.incident_closed is False
    assert result.packet.broker_writes == ()
    assert "protective_stop_missing_or_unverified" in result.blockers


def test_corrected_cleanup_refuses_unexpected_orders() -> None:
    result = run_corrected_aapl_cleanup(_m37_request("unexpected_order"))

    assert result.incident_closed is False
    assert result.packet.broker_writes == ()
    assert "unexpected_open_orders_present" in result.blockers


def test_corrected_cleanup_refuses_unexpected_positions() -> None:
    result = run_corrected_aapl_cleanup(_m37_request("unexpected_position"))

    assert result.incident_closed is False
    assert result.packet.broker_writes == ()
    assert "unexpected_positions_present" in result.blockers


def test_corrected_cleanup_cancels_expected_stop_then_sells_in_fake_flow() -> None:
    result = run_corrected_aapl_cleanup(_m37_request("protected_position"))

    assert result.incident_closed is True
    assert result.stop_cancellation_performed is True
    assert result.cleanup_sell_performed is True
    assert result.emergency_reprotection_performed is False
    assert result.broker_writes_performed_in_m37 is False
    assert [write.operation for write in result.packet.broker_writes] == [
        "cancel_session_protective_stop",
        "submit_cleanup_sell",
    ]
    assert result.packet.broker_writes[0].client_order_id == (
        "first-session-AAPL-safety-stop-20000101T000000Z-00000003-stop"
    )
    assert result.packet.final_broker_state.target_position_open is False
    assert result.packet.final_broker_state.open_orders_total == 0
    assert result.packet.next_milestone_recommendation == (
        "M38_REPEATED_CONTROLLED_SESSION_REVIEW_MAY_BE_CONSIDERED"
    )


def test_corrected_cleanup_does_not_cancel_stop_if_position_not_open_and_stop_gone() -> None:
    result = run_corrected_aapl_cleanup(_m37_request("flat"))

    assert result.incident_closed is True
    assert result.stop_cancellation_performed is False
    assert result.cleanup_sell_performed is False
    assert result.packet.broker_writes == ()


def test_corrected_cleanup_cancels_stale_stop_only_when_position_flat() -> None:
    client = _corrected_cleanup_client(positions=())

    def factory(*_args: Any, **_kwargs: Any) -> FakeAlpacaClient:
        return client

    result = run_corrected_aapl_cleanup(
        _m37_request(
            "protected_position",
            mode="real-read-only",
            confirm_all=True,
        ),
        environ=_safe_broker_env(),
        client_factory=factory,
    )

    assert result.incident_closed is True
    assert result.stop_cancellation_performed is False
    assert result.cleanup_sell_performed is False
    assert [write.operation for write in result.packet.broker_writes] == [
        "cancel_stale_protective_stop"
    ]
    assert client.cancelled_broker_order_ids == ["00000000-0000-4000-8000-900000000008"]


def test_corrected_cleanup_sell_quantity_never_exceeds_current_long_quantity() -> None:
    result = run_corrected_aapl_cleanup(_m37_request("protected_position"))
    sell = next(
        write
        for write in result.packet.broker_writes
        if write.operation == "submit_cleanup_sell"
    )

    assert sell.quantity == 1.0
    assert sell.quantity <= result.packet.pre_cleanup_broker_state.target_position_quantity


def test_corrected_cleanup_cannot_create_short_when_already_flat() -> None:
    result = run_corrected_aapl_cleanup(_m37_request("flat"))

    assert result.cleanup_sell_performed is False
    assert all(write.operation != "submit_cleanup_sell" for write in result.packet.broker_writes)


def test_corrected_cleanup_emergency_reprotects_if_sell_fails_after_stop_cancel() -> None:
    client = _corrected_cleanup_client(
        submit_outcomes=(("rejected", 0.0), ("accepted", 0.0)),
    )

    def factory(*_args: Any, **_kwargs: Any) -> FakeAlpacaClient:
        return client

    result = run_corrected_aapl_cleanup(
        _m37_request(
            "protected_position",
            mode="real-read-only",
            confirm_all=True,
        ),
        environ=_safe_broker_env(),
        client_factory=factory,
        sleeper=lambda _seconds: None,
        clock=_advancing_clock(),
    )

    assert result.incident_closed is False
    assert result.stop_cancellation_performed is True
    assert result.cleanup_sell_performed is True
    assert result.emergency_reprotection_performed is True
    assert result.packet.incident_closure_status == "safe_reprotected_incident"
    assert result.packet.final_broker_state.target_position_open is True
    assert result.packet.final_broker_state.protective_stop_verified is True
    assert result.packet.repeated_session_go_no_go == "no_go"


def test_corrected_cleanup_packet_contains_required_fields_and_excludes_secret_values(
    tmp_path: Path,
) -> None:
    result = run_corrected_aapl_cleanup(_m37_request("protected_position"))
    path = write_corrected_cleanup_artifact(result, tmp_path / "m37.json")
    payload_text = path.read_text(encoding="utf-8")
    payload = json.loads(payload_text)
    packet = payload["corrected_cleanup"]

    assert payload["milestone"] == "37"
    assert packet["m36_monitoring_packet_reference"] == (
        M36_PROTECTED_POSITION_MONITORING_EVIDENCE_PATH
    )
    assert packet["broker_writes_performed_in_m37"] is False
    assert packet["frozen_validation_started"] is False
    assert packet["level4_ready"] is False
    assert packet["live_trading_enabled"] is False
    assert packet["autonomous_live_execution_enabled"] is False
    assert packet["leverage_enabled"] is False
    assert "paper-secret" not in payload_text
    assert "paper-key" not in payload_text
    assert "postgres://" not in payload_text
    assert "sk-" not in payload_text


def test_incident_closure_validates_m35c_m35d_and_m35e_evidence() -> None:
    result = run_first_controlled_paper_session_incident_closure(
        _closure_request("flat")
    )

    assert result.packet.m35c_result_audit.parseable is True
    assert result.packet.m35d_post_session_audit.parseable is True
    assert result.packet.m35e_hold_decision_audit.parseable is True
    assert result.packet.cleanup_decision == (
        "OPERATOR_APPROVED_RISK_REDUCING_CLEANUP_AND_INCIDENT_CLOSURE"
    )


def test_incident_closure_refuses_without_cleanup_approval_marker() -> None:
    result = run_first_controlled_paper_session_incident_closure(
        _closure_request("protected_position", cleanup_approval_marker=None)
    )

    assert result.incident_closed is False
    assert result.packet.broker_writes == ()
    assert result.broker_writes_performed_in_this_milestone is False
    assert "cleanup_approval_marker_required" in result.blockers


def test_incident_closure_already_flat_without_stale_stop_performs_no_writes() -> None:
    result = run_first_controlled_paper_session_incident_closure(_closure_request("flat"))

    assert result.incident_closed is True
    assert result.cleanup_performed is False
    assert result.stale_stop_cleanup_performed is False
    assert result.packet.final_broker_state.target_position_open is False
    assert result.packet.final_broker_state.open_orders_total == 0
    assert result.packet.m36_readiness_recommendation == (
        "M36_SECOND_CONTROLLED_SESSION_MAY_BE_CONSIDERED"
    )


def test_incident_closure_refuses_ambiguous_broker_state() -> None:
    result = run_first_controlled_paper_session_incident_closure(
        _closure_request("unexpected_order")
    )

    assert result.incident_closed is False
    assert result.packet.broker_writes == ()
    assert "unexpected_open_orders_present" in result.blockers
    assert result.packet.m36_readiness_recommendation == "MANUAL_BROKER_REVIEW_REQUIRED"


def test_incident_closure_refuses_non_aapl_target() -> None:
    result = run_first_controlled_paper_session_incident_closure(
        _closure_request("protected_position", target_symbol="MSFT")
    )

    assert result.incident_closed is False
    assert result.packet.broker_writes == ()
    assert "target_symbol_must_be_aapl" in result.blockers


def test_incident_closure_refuses_excess_cleanup_quantity() -> None:
    result = run_first_controlled_paper_session_incident_closure(
        _closure_request("protected_position", requested_cleanup_quantity=2.0)
    )

    assert result.incident_closed is False
    assert result.packet.broker_writes == ()
    assert "cleanup_quantity_exceeds_current_aapl_long_quantity" in result.blockers


def test_incident_closure_refuses_cleanup_that_could_create_short() -> None:
    result = run_first_controlled_paper_session_incident_closure(
        _closure_request("flat", requested_cleanup_quantity=1.0)
    )

    assert result.incident_closed is False
    assert result.packet.broker_writes == ()
    assert "cleanup_quantity_would_create_short" in result.blockers


def test_incident_closure_submits_risk_reducing_sell_and_cancels_stale_stop() -> None:
    result = run_first_controlled_paper_session_incident_closure(
        _closure_request("protected_position")
    )

    assert result.incident_closed is True
    assert result.cleanup_performed is True
    assert result.stale_stop_cleanup_performed is True
    assert result.broker_writes_performed_in_this_milestone is False
    assert [write.operation for write in result.packet.broker_writes] == [
        "submit_cleanup_sell",
        "cancel_stale_protective_stop",
    ]
    sell = result.packet.broker_writes[0]
    assert sell.symbol == "AAPL"
    assert sell.side == "sell"
    assert sell.quantity == 1.0
    assert sell.order_type == "market"
    assert sell.fake_only is True
    assert result.packet.final_broker_state.target_position_open is False
    assert result.packet.final_broker_state.open_orders_total == 0


def test_incident_closure_does_not_cancel_stop_while_position_open() -> None:
    client = _UnfilledCleanupClient()

    def factory(*_args: Any, **_kwargs: Any) -> _UnfilledCleanupClient:
        return client

    result = run_first_controlled_paper_session_incident_closure(
        _closure_request(
            "protected_position",
            mode="real-read-only",
            confirm_paper_endpoint=True,
            confirm_risk_reducing_only=True,
            confirm_no_new_entry=True,
            confirm_no_live_trading=True,
            confirm_no_autonomous_live=True,
            confirm_no_schedules=True,
            confirm_no_leverage=True,
        ),
        environ=_safe_broker_env(),
        client_factory=factory,
        sleeper=lambda _seconds: None,
        clock=_advancing_clock(),
    )

    assert result.incident_closed is False
    assert result.cleanup_performed is True
    assert result.stale_stop_cleanup_performed is False
    assert "cleanup_sell_not_filled" in result.blockers
    assert client.submit_order_calls == 1
    assert client.cancel_order_calls == 0


def test_incident_closure_missing_stop_requires_manual_review() -> None:
    result = run_first_controlled_paper_session_incident_closure(
        _closure_request("missing_stop")
    )

    assert result.incident_closed is False
    assert result.packet.broker_writes == ()
    assert "protective_stop_missing_or_unverified" in result.blockers
    assert result.packet.m36_readiness_recommendation == "MANUAL_BROKER_REVIEW_REQUIRED"


def test_incident_closure_packet_excludes_secret_values(tmp_path: Path) -> None:
    result = run_first_controlled_paper_session_incident_closure(
        _closure_request("protected_position")
    )
    path = write_incident_closure_artifact(result, tmp_path / "closure.json")
    payload = path.read_text(encoding="utf-8")

    assert "paper-secret" not in payload
    assert "paper-key" not in payload
    assert "postgres://" not in payload
    assert "sk-" not in payload
    closure_payload = json.loads(payload)["incident_closure"]
    assert closure_payload["incident_closed"] is True
    assert closure_payload["frozen_validation_started"] is False


def test_fake_post_session_audit_missing_stop_requests_stop_repair() -> None:
    result = run_first_controlled_paper_session_post_session_audit(
        PostSessionAuditRequest(mode="fake", scenario_id="missing_stop")
    )

    assert result.audit_completed is True
    assert result.packet.cleanup_hold_decision_recommendation == (
        "REQUEST_OPERATOR_APPROVED_STOP_REPAIR"
    )
    assert result.packet.current_broker_state.target_position_open is True
    assert result.packet.current_broker_state.protective_stop_verified is False
    assert "protective_stop_missing_or_unverified" in result.blockers


def test_post_session_audit_packet_excludes_secret_values(tmp_path: Path) -> None:
    result = run_first_controlled_paper_session_post_session_audit(
        PostSessionAuditRequest(mode="fake", scenario_id="protected_position")
    )
    path = write_post_session_audit_artifact(result, tmp_path / "audit.json")
    payload = path.read_text(encoding="utf-8")

    assert "paper-secret" not in payload
    assert "paper-key" not in payload
    assert "postgres://" not in payload
    assert "sk-" not in payload
    audit_payload = json.loads(payload)["post_session_audit"]
    assert audit_payload["broker_writes_performed_in_this_milestone"] is False


def test_real_read_only_post_audit_stub_never_calls_write_methods() -> None:
    client = _ReadOnlyGuardClient()

    def factory(*_args: Any, **_kwargs: Any) -> _ReadOnlyGuardClient:
        return client

    result = run_first_controlled_paper_session_post_session_audit(
        PostSessionAuditRequest(
            mode="real-read-only",
            scenario_id="protected_position",
            confirm_paper_endpoint=True,
            confirm_no_broker_writes=True,
            confirm_no_live_trading=True,
            confirm_no_autonomous_live=True,
            confirm_no_schedules=True,
            confirm_no_leverage=True,
        ),
        environ={
            "ALPACA_API_KEY": "placeholder-key",
            "ALPACA_SECRET_KEY": "placeholder-secret",
            "ALPACA_BASE_URL": ALPACA_PAPER_BASE_URL,
            "RUN_ALPACA_PAPER_SMOKE": "1",
            "ALPACA_PAPER_SMOKE_CONFIRM": "READ_ONLY_PAPER_ACCOUNT",
        },
        client_factory=factory,
    )

    assert result.audit_completed is True
    assert result.real_read_only_calls_performed is True
    assert result.broker_writes_performed_in_this_milestone is False
    assert client.submit_order_calls == 0
    assert client.cancel_order_calls == 0
    assert result.packet.current_broker_state.protective_stop_verified is True


def test_real_read_only_hold_decision_stub_never_calls_write_methods() -> None:
    client = _ReadOnlyGuardClient()

    def factory(*_args: Any, **_kwargs: Any) -> _ReadOnlyGuardClient:
        return client

    result = run_first_controlled_paper_session_hold_decision(
        PostSessionAuditRequest(
            mode="real-read-only",
            scenario_id="protected_position",
            confirm_paper_endpoint=True,
            confirm_no_broker_writes=True,
            confirm_no_live_trading=True,
            confirm_no_autonomous_live=True,
            confirm_no_schedules=True,
            confirm_no_leverage=True,
        ),
        environ={
            "ALPACA_API_KEY": "placeholder-key",
            "ALPACA_SECRET_KEY": "placeholder-secret",
            "ALPACA_BASE_URL": ALPACA_PAPER_BASE_URL,
            "RUN_ALPACA_PAPER_SMOKE": "1",
            "ALPACA_PAPER_SMOKE_CONFIRM": "READ_ONLY_PAPER_ACCOUNT",
        },
        client_factory=factory,
    )

    assert result.hold_confirmed is True
    assert result.go_no_go == "no_go"
    assert result.real_read_only_calls_performed is True
    assert result.broker_writes_performed_in_this_milestone is False
    assert client.submit_order_calls == 0
    assert client.cancel_order_calls == 0
    assert result.packet.cleanup_hold_recommendation == "CONTINUE_HOLD_UNTIL_NEXT_REVIEW"
    assert result.packet.current_broker_state.protective_stop_verified is True
    assert result.packet.frozen_validation_started is False


def test_execution_path_continues_to_stop_when_fill_metadata_is_malformed() -> None:
    app_config = load_app_config()
    request = default_first_paper_session_execution_request(
        "happy_path",
        mode="fake-real-paper",
        operator_approval_marker=MILESTONE_34_FAKE_OPERATOR_APPROVAL,
        target_symbol="AAPL",
        max_quantity=1,
        max_notional_usd=350.0,
        limit_price=330.0,
    )
    client = _MalformedFillClient(
        submit_outcomes=(("filled", 1.0), ("accepted", 0.0)),
        mutate_positions_on_submit=True,
    )
    adapter = AlpacaPaperAdapter(
        system_config=app_config.system,
        execution_config=app_config.execution,
        client=client,
        credentials=None,
        run_mode="test",
    )

    result = _run_adapter_execution(
        request=request,
        app_config=app_config,
        adapter=adapter,
        client=client,
        real_broker=False,
        real_external_calls_performed=False,
        sleeper=lambda _seconds: None,
        clock=lambda: 0.0,
    )

    assert result.status == "incident"
    assert "fill_metadata_unavailable_recent_fills_unparseable" in result.result_packet.incidents
    assert result.result_packet.protective_stop_verification_result == "verified"
    assert result.real_broker_writes_attempted is False
    assert [order["type"] for order in client.submitted_order_requests] == ["limit", "stop"]


def _closure_request(
    scenario_id: str,
    *,
    mode: str = "fake",
    target_symbol: str = "AAPL",
    cleanup_approval_marker: str | None = MILESTONE_35F_CLEANUP_APPROVAL,
    requested_cleanup_quantity: float | None = None,
    confirm_paper_endpoint: bool = False,
    confirm_risk_reducing_only: bool = False,
    confirm_no_new_entry: bool = False,
    confirm_no_live_trading: bool = False,
    confirm_no_autonomous_live: bool = False,
    confirm_no_schedules: bool = False,
    confirm_no_leverage: bool = False,
) -> IncidentClosureRequest:
    return IncidentClosureRequest(
        mode=cast(PostSessionAuditMode, mode),
        scenario_id=cast(Any, scenario_id),
        target_symbol=target_symbol,
        operator_decision=(
            "OPERATOR_APPROVED_RISK_REDUCING_CLEANUP_AND_INCIDENT_CLOSURE"
        ),
        cleanup_approval_marker=cleanup_approval_marker,
        requested_cleanup_quantity=requested_cleanup_quantity,
        confirm_paper_endpoint=confirm_paper_endpoint,
        confirm_risk_reducing_only=confirm_risk_reducing_only,
        confirm_no_new_entry=confirm_no_new_entry,
        confirm_no_live_trading=confirm_no_live_trading,
        confirm_no_autonomous_live=confirm_no_autonomous_live,
        confirm_no_schedules=confirm_no_schedules,
        confirm_no_leverage=confirm_no_leverage,
        cleanup_timeout_seconds=0.01,
    )


def _m37_request(
    scenario_id: str,
    *,
    mode: str = "fake",
    target_symbol: str = "AAPL",
    cleanup_approval_marker: str | None = MILESTONE_37_CORRECTED_CLEANUP_APPROVAL,
    confirm_all: bool = False,
) -> CorrectedCleanupRequest:
    return CorrectedCleanupRequest(
        mode=cast(PostSessionAuditMode, mode),
        scenario_id=cast(Any, scenario_id),
        target_symbol=target_symbol,
        operator_decision=(
            "OPERATOR_APPROVED_CORRECTED_AAPL_CLEANUP_AND_INCIDENT_CLOSURE"
        ),
        cleanup_approval_marker=cleanup_approval_marker,
        confirm_paper_endpoint=confirm_all,
        confirm_risk_reducing_only=confirm_all,
        confirm_cancel_session_stop_before_sell=confirm_all,
        confirm_emergency_reprotect_if_sell_fails=confirm_all,
        confirm_no_new_entry=confirm_all,
        confirm_no_buy_orders=confirm_all,
        confirm_no_live_trading=confirm_all,
        confirm_no_autonomous_live=confirm_all,
        confirm_no_schedules=confirm_all,
        confirm_no_leverage=confirm_all,
        cleanup_timeout_seconds=0.01,
    )


def _corrected_cleanup_client(
    *,
    positions: Sequence[Mapping[str, Any]] | None = None,
    submit_outcomes: Sequence[tuple[str, float]] = (("filled", 1.0),),
) -> FakeAlpacaClient:
    return FakeAlpacaClient(
        orders=(
            _order_payload(
                broker_order_id="00000000-0000-4000-8000-900000000006",
                client_order_id="first-session-AAPL-20000101T000000Z-00000001",
                order_type="limit",
                status="filled",
                side="buy",
                filled_qty="1",
            ),
            _order_payload(
                broker_order_id="00000000-0000-4000-8000-900000000008",
                client_order_id=(
                    "first-session-AAPL-safety-stop-20000101T000000Z-00000003-stop"
                ),
                order_type="stop",
                status="new",
                side="sell",
                stop_price="165",
            ),
        ),
        positions=(
            positions
            if positions is not None
            else (
                {
                    "symbol": "AAPL",
                    "asset_class": "equity",
                    "qty": "1",
                    "avg_entry_price": "290.94",
                    "market_value": "290.94",
                    "opened_at": DEFAULT_AS_OF.isoformat().replace("+00:00", "Z"),
                },
            )
        ),
        submit_outcomes=submit_outcomes,
        mutate_positions_on_submit=True,
    )


def _safe_broker_env() -> dict[str, str]:
    return {
        "ALPACA_API_KEY": "placeholder-key",
        "ALPACA_SECRET_KEY": "placeholder-secret",
        "ALPACA_BASE_URL": ALPACA_PAPER_BASE_URL,
        "RUN_ALPACA_PAPER_SMOKE": "1",
        "ALPACA_PAPER_SMOKE_CONFIRM": "READ_ONLY_PAPER_ACCOUNT",
    }


def _advancing_clock() -> Any:
    current = {"value": 0.0}

    def tick() -> float:
        current["value"] += 0.02
        return current["value"]

    return tick


class _MalformedFillClient(FakeAlpacaClient):
    def list_fills(self) -> Sequence[Mapping[str, Any]]:
        return (
            {
                "order_id": "paper-order-1",
                "symbol": "AAPL",
                "side": "buy",
                "qty": "1",
                "transaction_time": DEFAULT_AS_OF.isoformat().replace("+00:00", "Z"),
            },
        )


class _ReadOnlyGuardClient:
    def __init__(self) -> None:
        self.submit_order_calls = 0
        self.cancel_order_calls = 0
        self._orders = {
            "00000000-0000-4000-8000-900000000006": _order_payload(
                broker_order_id="00000000-0000-4000-8000-900000000006",
                client_order_id="first-session-AAPL-20000101T000000Z-00000001",
                order_type="limit",
                status="filled",
                side="buy",
                filled_qty="1",
            ),
            "00000000-0000-4000-8000-900000000008": _order_payload(
                broker_order_id="00000000-0000-4000-8000-900000000008",
                client_order_id="first-session-AAPL-safety-stop-20000101T000000Z-00000003-stop",
                order_type="stop",
                status="new",
                side="sell",
                stop_price="165",
            ),
        }

    def get_account(self) -> Mapping[str, Any]:
        return {
            "id": "redacted-test-account",
            "equity": "100000",
            "cash": "90000",
            "buying_power": "180000",
            "currency": "USD",
            "as_of": DEFAULT_AS_OF.isoformat().replace("+00:00", "Z"),
        }

    def list_open_orders(self) -> Sequence[Mapping[str, Any]]:
        return (self._orders["00000000-0000-4000-8000-900000000008"],)

    def get_order_by_id(self, broker_order_id: str) -> Mapping[str, Any] | None:
        return self._orders.get(broker_order_id)

    def get_order_by_client_order_id(self, client_order_id: str) -> Mapping[str, Any] | None:
        for order in self._orders.values():
            if order["client_order_id"] == client_order_id:
                return order
        return None

    def submit_order(self, _request: Mapping[str, Any]) -> Mapping[str, Any]:
        self.submit_order_calls += 1
        raise AssertionError("post-session audit must not submit orders")

    def cancel_order(self, _broker_order_id: str) -> Mapping[str, Any]:
        self.cancel_order_calls += 1
        raise AssertionError("post-session audit must not cancel orders")

    def list_fills(self) -> Sequence[Mapping[str, Any]]:
        return ()

    def list_positions(self) -> Sequence[Mapping[str, Any]]:
        return (
            {
                "symbol": "AAPL",
                "asset_class": "equity",
                "qty": "1",
                "avg_entry_price": "290.94",
                "market_value": "290.94",
                "opened_at": DEFAULT_AS_OF.isoformat().replace("+00:00", "Z"),
            },
        )

    def get_position(self, _symbol: str) -> Mapping[str, Any] | None:
        return self.list_positions()[0]

    def consume_trade_updates(self) -> Sequence[Mapping[str, Any]]:
        return ()

    def get_clock(self) -> Mapping[str, Any]:
        return {
            "is_open": True,
            "timestamp": DEFAULT_AS_OF.isoformat().replace("+00:00", "Z"),
            "next_open": DEFAULT_AS_OF.isoformat().replace("+00:00", "Z"),
            "next_close": DEFAULT_AS_OF.replace(hour=21, minute=0)
            .isoformat()
            .replace("+00:00", "Z"),
        }


class _UnfilledCleanupClient(_ReadOnlyGuardClient):
    def list_open_orders(self) -> Sequence[Mapping[str, Any]]:
        return tuple(
            dict(order)
            for order in self._orders.values()
            if str(order.get("status")) in {"new", "accepted", "pending_new", "partially_filled"}
        )

    def submit_order(self, request: Mapping[str, Any]) -> Mapping[str, Any]:
        self.submit_order_calls += 1
        assert request["symbol"] == "AAPL"
        assert request["side"] == "sell"
        assert request["type"] == "market"
        order = {
            "id": "cleanup-order",
            "client_order_id": request["client_order_id"],
            "symbol": request["symbol"],
            "side": request["side"],
            "asset_class": "equity",
            "qty": request["qty"],
            "filled_qty": "0",
            "type": request["type"],
            "time_in_force": request["time_in_force"],
            "status": "accepted",
            "submitted_at": DEFAULT_AS_OF.isoformat().replace("+00:00", "Z"),
        }
        self._orders["cleanup-order"] = dict(order)
        return order


def _order_payload(
    *,
    broker_order_id: str,
    client_order_id: str,
    order_type: str,
    status: str,
    side: str,
    filled_qty: str = "0",
    stop_price: str | None = None,
) -> dict[str, Any]:
    payload = {
        "id": broker_order_id,
        "client_order_id": client_order_id,
        "symbol": "AAPL",
        "side": side,
        "asset_class": "equity",
        "qty": "1",
        "filled_qty": filled_qty,
        "type": order_type,
        "time_in_force": "gtc" if order_type == "stop" else "day",
        "status": status,
        "submitted_at": DEFAULT_AS_OF.isoformat().replace("+00:00", "Z"),
    }
    if order_type == "limit":
        payload["limit_price"] = "330"
    if stop_price is not None:
        payload["stop_price"] = stop_price
    return payload
