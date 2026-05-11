"""Run the Milestone 35D post-session audit path."""

from __future__ import annotations

import argparse
import json
from typing import cast

from packages.paper import (
    M34_RESULT_EVIDENCE_PATH,
    M35D_POST_SESSION_AUDIT_EVIDENCE_PATH,
    M35E_HOLD_DECISION_EVIDENCE_PATH,
    M35F_INCIDENT_CLOSURE_EVIDENCE_PATH,
    M36_PROTECTED_POSITION_MONITORING_EVIDENCE_PATH,
    MILESTONE_35F_CLEANUP_APPROVAL,
    IncidentClosureRequest,
    OperatorHoldDecision,
    OperatorIncidentClosureDecision,
    PostSessionAuditMode,
    PostSessionAuditRequest,
    PostSessionAuditScenarioId,
    ProtectedPositionMonitoringRequest,
    load_preflight_environment,
    run_first_controlled_paper_session_hold_decision,
    run_first_controlled_paper_session_incident_closure,
    run_first_controlled_paper_session_post_session_audit,
    run_protected_position_monitoring,
    write_hold_decision_artifact,
    write_incident_closure_artifact,
    write_post_session_audit_artifact,
    write_protected_position_monitoring_artifact,
)

WARNING = (
    "Milestone 35D/35E/35F post-session audit and cleanup only. This command does not "
    "start a new session or submit entry orders. M35F writes, when explicitly approved, "
    "are limited to risk-reducing AAPL cleanup."
)
M36_WARNING = (
    "Milestone 36 protected-position monitoring only. This command performs read-only "
    "broker-state verification and cleanup rejection analysis; it submits, cancels, replaces, "
    "and flattens nothing."
)
_M36_MODES = {
    "protected-position-monitor",
    "cleanup-rejection-analysis",
    "monitoring",
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Audit the first controlled paper-session incident and broker state.",
    )
    parser.add_argument(
        "--mode",
        choices=(
            "fake",
            "real-read-only",
            "hold-decision",
            "incident-closure",
            "protected-position-monitor",
            "cleanup-rejection-analysis",
            "monitoring",
        ),
        default="fake",
        help=(
            "Fake mode uses local broker fixtures. Real-read-only and hold-decision "
            "modes perform gated Alpaca reads. Incident-closure performs gated M35F "
            "risk-reducing cleanup. M36 monitoring modes are read-only only."
        ),
    )
    parser.add_argument(
        "--scenario",
        choices=(
            "protected_position",
            "missing_stop",
            "unexpected_order",
            "unexpected_position",
            "flat",
        ),
        default="protected_position",
        help="Fake broker-state scenario.",
    )
    parser.add_argument("--target-symbol", default="AAPL")
    parser.add_argument("--result-packet", default=M34_RESULT_EVIDENCE_PATH)
    parser.add_argument(
        "--post-session-audit-packet",
        default=M35D_POST_SESSION_AUDIT_EVIDENCE_PATH,
        help="Sanitized M35D post-session audit packet path.",
    )
    parser.add_argument(
        "--operator-decision",
        choices=(
            "HOLD_PROTECTED_POSITION_UNTIL_NEXT_REVIEW",
            "OPERATOR_APPROVED_RISK_REDUCING_CLEANUP_AND_INCIDENT_CLOSURE",
        ),
        default=None,
        help="Optional M35E/M35F operator decision to record.",
    )
    parser.add_argument(
        "--cleanup-approval",
        default=None,
        help=f"M35F cleanup approval marker, expected {MILESTONE_35F_CLEANUP_APPROVAL}.",
    )
    parser.add_argument(
        "--cleanup-qty",
        type=float,
        default=None,
        help=(
            "Optional M35F cleanup quantity override for tests; must not exceed current "
            "AAPL long."
        ),
    )
    parser.add_argument(
        "--audit-output",
        default=M35D_POST_SESSION_AUDIT_EVIDENCE_PATH,
        help="Sanitized post-session audit packet path.",
    )
    parser.add_argument(
        "--hold-decision-output",
        default=M35E_HOLD_DECISION_EVIDENCE_PATH,
        help="Sanitized M35E hold decision packet path.",
    )
    parser.add_argument(
        "--incident-closure-output",
        default=M35F_INCIDENT_CLOSURE_EVIDENCE_PATH,
        help="Sanitized M35F incident closure packet path.",
    )
    parser.add_argument(
        "--monitoring-output",
        default=M36_PROTECTED_POSITION_MONITORING_EVIDENCE_PATH,
        help="Sanitized M36 protected-position monitoring packet path.",
    )
    parser.add_argument("--confirm-paper-endpoint", action="store_true")
    parser.add_argument("--confirm-no-broker-writes", action="store_true")
    parser.add_argument("--confirm-risk-reducing-only", action="store_true")
    parser.add_argument("--confirm-no-new-entry", action="store_true")
    parser.add_argument("--confirm-no-live-trading", action="store_true")
    parser.add_argument("--confirm-no-autonomous-live", action="store_true")
    parser.add_argument("--confirm-no-schedules", action="store_true")
    parser.add_argument("--confirm-no-leverage", action="store_true")
    args = parser.parse_args(argv)

    mode = args.mode
    print(M36_WARNING if mode in _M36_MODES else WARNING)
    if mode in _M36_MODES:
        monitoring_request = ProtectedPositionMonitoringRequest(
            mode="real-read-only",
            scenario_id=cast(PostSessionAuditScenarioId, args.scenario),
            result_packet_path=args.result_packet,
            post_session_audit_packet_path=args.post_session_audit_packet,
            hold_decision_packet_path=args.hold_decision_output,
            incident_closure_packet_path=args.incident_closure_output,
            target_symbol=args.target_symbol.upper(),
            confirm_paper_endpoint=args.confirm_paper_endpoint,
            confirm_no_broker_writes=args.confirm_no_broker_writes,
            confirm_no_new_entry=args.confirm_no_new_entry,
            confirm_no_live_trading=args.confirm_no_live_trading,
            confirm_no_autonomous_live=args.confirm_no_autonomous_live,
            confirm_no_schedules=args.confirm_no_schedules,
            confirm_no_leverage=args.confirm_no_leverage,
        )
        monitoring_result = run_protected_position_monitoring(
            monitoring_request,
            environ=load_preflight_environment(),
        )
        written_path = write_protected_position_monitoring_artifact(
            monitoring_result,
            args.monitoring_output,
        )
        packet = monitoring_result.packet
        broker_state = packet.current_broker_state
        summary = {
            "mode": mode,
            "scenario_id": monitoring_result.scenario_id,
            "monitoring_completed": monitoring_result.monitoring_completed,
            "go_no_go": monitoring_result.go_no_go,
            "blockers": monitoring_result.blockers,
            "target_symbol": broker_state.target_symbol,
            "aapl_position_status": packet.aapl_position_status,
            "aapl_protective_stop_status": packet.aapl_protective_stop_status,
            "target_position_quantity": broker_state.target_position_quantity,
            "protective_stop_quantity": broker_state.protective_stop_quantity,
            "protective_stop_order_status": broker_state.protective_stop_order_status,
            "open_orders_summary": packet.open_orders_summary,
            "positions_summary": packet.positions_summary,
            "final_reconciliation_summary": packet.final_reconciliation_summary,
            "broker_state_safe_to_continue_holding": (
                packet.broker_state_safe_to_continue_holding
            ),
            "cleanup_rejection_classification": (
                packet.cleanup_rejection_classification
            ),
            "cleanup_rejection_evidence_sufficient": (
                packet.cleanup_rejection_evidence_sufficient
            ),
            "next_milestone_recommendation": packet.next_milestone_recommendation,
            "broker_writes_performed_in_m36": (
                monitoring_result.broker_writes_performed_in_m36
            ),
            "real_read_only_calls_performed": (
                monitoring_result.real_read_only_calls_performed
            ),
            "live_trading_enabled": monitoring_result.live_trading_enabled,
            "autonomous_live_execution_enabled": (
                monitoring_result.autonomous_live_execution_enabled
            ),
            "schedules_activated": monitoring_result.schedules_activated,
            "leverage_enabled": monitoring_result.leverage_enabled,
            "ai_broker_write_authority": monitoring_result.ai_broker_write_authority,
            "monitoring_packet_path": str(written_path),
            "note": M36_WARNING,
        }
        print(json.dumps(summary, indent=2, sort_keys=True))
        safe_or_flat = packet.broker_state_safe_to_continue_holding or (
            packet.aapl_position_status == "flat" and broker_state.account_reachable
        )
        return 0 if monitoring_result.monitoring_completed and safe_or_flat else 1
    audit_mode = "real-read-only" if mode == "hold-decision" else mode
    if mode == "incident-closure":
        closure_request = IncidentClosureRequest(
            mode="real-read-only",
            scenario_id=cast(PostSessionAuditScenarioId, args.scenario),
            result_packet_path=args.result_packet,
            post_session_audit_packet_path=args.post_session_audit_packet,
            hold_decision_packet_path=args.hold_decision_output,
            target_symbol=args.target_symbol.upper(),
            operator_decision=cast(
                OperatorIncidentClosureDecision | None,
                args.operator_decision,
            ),
            cleanup_approval_marker=args.cleanup_approval,
            requested_cleanup_quantity=args.cleanup_qty,
            confirm_paper_endpoint=args.confirm_paper_endpoint,
            confirm_risk_reducing_only=args.confirm_risk_reducing_only,
            confirm_no_new_entry=args.confirm_no_new_entry,
            confirm_no_live_trading=args.confirm_no_live_trading,
            confirm_no_autonomous_live=args.confirm_no_autonomous_live,
            confirm_no_schedules=args.confirm_no_schedules,
            confirm_no_leverage=args.confirm_no_leverage,
        )
        closure_result = run_first_controlled_paper_session_incident_closure(
            closure_request,
            environ=load_preflight_environment(),
        )
        written_path = write_incident_closure_artifact(
            closure_result,
            args.incident_closure_output,
        )
        closure_packet = closure_result.packet
        initial = closure_packet.initial_broker_state
        final = closure_packet.final_broker_state
        summary = {
            "mode": mode,
            "scenario_id": closure_result.scenario_id,
            "incident_closed": closure_result.incident_closed,
            "go_no_go": closure_result.go_no_go,
            "blockers": closure_result.blockers,
            "cleanup_decision": closure_packet.cleanup_decision,
            "cleanup_performed": closure_result.cleanup_performed,
            "stale_stop_cleanup_performed": closure_result.stale_stop_cleanup_performed,
            "broker_writes_performed_in_this_milestone": (
                closure_result.broker_writes_performed_in_this_milestone
            ),
            "broker_write_operations": [
                write.operation for write in closure_packet.broker_writes if write.attempted
            ],
            "initial_target_position_quantity": initial.target_position_quantity,
            "initial_protective_stop_verified": initial.protective_stop_verified,
            "final_target_position_quantity": final.target_position_quantity,
            "final_open_orders_total": final.open_orders_total,
            "final_positions_total": final.positions_total,
            "final_reconciliation_summary": final.reconciliation_summary,
            "m36_readiness_recommendation": (
                closure_packet.m36_readiness_recommendation
            ),
            "real_read_only_calls_performed": closure_result.real_read_only_calls_performed,
            "live_trading_enabled": closure_result.live_trading_enabled,
            "autonomous_live_execution_enabled": (
                closure_result.autonomous_live_execution_enabled
            ),
            "schedules_activated": closure_result.schedules_activated,
            "leverage_enabled": closure_result.leverage_enabled,
            "ai_broker_write_authority": closure_result.ai_broker_write_authority,
            "incident_closure_packet_path": str(written_path),
            "note": WARNING,
        }
        print(json.dumps(summary, indent=2, sort_keys=True))
        return 0 if closure_result.incident_closed else 1
    if (
        args.operator_decision
        == "OPERATOR_APPROVED_RISK_REDUCING_CLEANUP_AND_INCIDENT_CLOSURE"
    ):
        closure_request = IncidentClosureRequest(
            mode=cast(PostSessionAuditMode, audit_mode),
            scenario_id=cast(PostSessionAuditScenarioId, args.scenario),
            result_packet_path=args.result_packet,
            post_session_audit_packet_path=args.post_session_audit_packet,
            hold_decision_packet_path=args.hold_decision_output,
            target_symbol=args.target_symbol.upper(),
            operator_decision=cast(OperatorIncidentClosureDecision, args.operator_decision),
            cleanup_approval_marker=args.cleanup_approval,
            requested_cleanup_quantity=args.cleanup_qty,
            confirm_paper_endpoint=args.confirm_paper_endpoint,
            confirm_risk_reducing_only=args.confirm_risk_reducing_only,
            confirm_no_new_entry=args.confirm_no_new_entry,
            confirm_no_live_trading=args.confirm_no_live_trading,
            confirm_no_autonomous_live=args.confirm_no_autonomous_live,
            confirm_no_schedules=args.confirm_no_schedules,
            confirm_no_leverage=args.confirm_no_leverage,
        )
        closure_result = run_first_controlled_paper_session_incident_closure(
            closure_request,
            environ=load_preflight_environment() if audit_mode == "real-read-only" else {},
        )
        written_path = write_incident_closure_artifact(
            closure_result,
            args.incident_closure_output,
        )
        closure_packet = closure_result.packet
        final = closure_packet.final_broker_state
        summary = {
            "mode": mode,
            "scenario_id": closure_result.scenario_id,
            "incident_closed": closure_result.incident_closed,
            "go_no_go": closure_result.go_no_go,
            "blockers": closure_result.blockers,
            "cleanup_decision": closure_packet.cleanup_decision,
            "cleanup_performed": closure_result.cleanup_performed,
            "stale_stop_cleanup_performed": closure_result.stale_stop_cleanup_performed,
            "broker_writes_performed_in_this_milestone": (
                closure_result.broker_writes_performed_in_this_milestone
            ),
            "final_target_position_quantity": final.target_position_quantity,
            "final_reconciliation_summary": final.reconciliation_summary,
            "m36_readiness_recommendation": (
                closure_packet.m36_readiness_recommendation
            ),
            "incident_closure_packet_path": str(written_path),
            "note": WARNING,
        }
        print(json.dumps(summary, indent=2, sort_keys=True))
        return 0 if closure_result.incident_closed else 1
    request = PostSessionAuditRequest(
        mode=cast(PostSessionAuditMode, audit_mode),
        scenario_id=cast(PostSessionAuditScenarioId, args.scenario),
        result_packet_path=args.result_packet,
        target_symbol=args.target_symbol.upper(),
        confirm_paper_endpoint=args.confirm_paper_endpoint,
        confirm_no_broker_writes=args.confirm_no_broker_writes,
        confirm_no_live_trading=args.confirm_no_live_trading,
        confirm_no_autonomous_live=args.confirm_no_autonomous_live,
        confirm_no_schedules=args.confirm_no_schedules,
        confirm_no_leverage=args.confirm_no_leverage,
    )
    if mode == "hold-decision" or args.operator_decision is not None:
        if args.operator_decision != "HOLD_PROTECTED_POSITION_UNTIL_NEXT_REVIEW":
            print(
                json.dumps(
                    {
                        "mode": mode,
                        "audit_completed": False,
                        "go_no_go": "no_go",
                        "blockers": ["operator_decision_required"],
                        "broker_writes_performed_in_this_milestone": False,
                        "note": WARNING,
                    },
                    indent=2,
                    sort_keys=True,
                )
            )
            return 1
        hold_result = run_first_controlled_paper_session_hold_decision(
            request,
            operator_decision=cast(OperatorHoldDecision, args.operator_decision),
            post_session_audit_packet_path=args.post_session_audit_packet,
            environ=load_preflight_environment() if audit_mode == "real-read-only" else {},
        )
        written_path = write_hold_decision_artifact(
            hold_result,
            args.hold_decision_output,
        )
        hold_packet = hold_result.packet
        broker_state = hold_packet.current_broker_state
        summary = {
            "mode": mode,
            "scenario_id": hold_result.scenario_id,
            "operator_decision": hold_result.operator_decision,
            "hold_confirmed": hold_result.hold_confirmed,
            "go_no_go": hold_result.go_no_go,
            "blockers": hold_result.blockers,
            "cleanup_hold_recommendation": hold_packet.cleanup_hold_recommendation,
            "target_symbol": broker_state.target_symbol,
            "target_position_quantity": broker_state.target_position_quantity,
            "protective_stop_verified": broker_state.protective_stop_verified,
            "protective_stop_order_status": broker_state.protective_stop_order_status,
            "open_orders_total": broker_state.open_orders_total,
            "positions_total": broker_state.positions_total,
            "reconciliation_summary": broker_state.reconciliation_summary,
            "cleanup_performed": hold_packet.cleanup_performed,
            "flatten_performed": hold_packet.flatten_performed,
            "cancel_performed": hold_packet.cancel_performed,
            "broker_writes_performed_in_this_milestone": (
                hold_result.broker_writes_performed_in_this_milestone
            ),
            "real_read_only_calls_performed": hold_result.real_read_only_calls_performed,
            "live_trading_enabled": hold_result.live_trading_enabled,
            "autonomous_live_execution_enabled": (
                hold_result.autonomous_live_execution_enabled
            ),
            "schedules_activated": hold_result.schedules_activated,
            "leverage_enabled": hold_result.leverage_enabled,
            "ai_broker_write_authority": hold_result.ai_broker_write_authority,
            "hold_decision_packet_path": str(written_path),
            "note": WARNING,
        }
        print(json.dumps(summary, indent=2, sort_keys=True))
        return 0 if hold_result.hold_confirmed else 1

    result = run_first_controlled_paper_session_post_session_audit(
        request,
        environ=load_preflight_environment() if audit_mode == "real-read-only" else {},
    )
    written_path = write_post_session_audit_artifact(result, args.audit_output)
    audit_packet = result.packet
    broker_state = audit_packet.current_broker_state
    summary = {
        "mode": result.mode,
        "scenario_id": result.scenario_id,
        "audit_completed": result.audit_completed,
        "go_no_go": result.go_no_go,
        "blockers": result.blockers,
        "cleanup_hold_decision_recommendation": (
            audit_packet.cleanup_hold_decision_recommendation
        ),
        "target_symbol": broker_state.target_symbol,
        "target_position_quantity": broker_state.target_position_quantity,
        "protective_stop_verified": broker_state.protective_stop_verified,
        "protective_stop_order_status": broker_state.protective_stop_order_status,
        "open_orders_total": broker_state.open_orders_total,
        "positions_total": broker_state.positions_total,
        "reconciliation_summary": broker_state.reconciliation_summary,
        "broker_writes_performed_in_this_milestone": (
            result.broker_writes_performed_in_this_milestone
        ),
        "real_read_only_calls_performed": result.real_read_only_calls_performed,
        "live_trading_enabled": result.live_trading_enabled,
        "autonomous_live_execution_enabled": result.autonomous_live_execution_enabled,
        "schedules_activated": result.schedules_activated,
        "leverage_enabled": result.leverage_enabled,
        "ai_broker_write_authority": result.ai_broker_write_authority,
        "audit_packet_path": str(written_path),
        "note": WARNING,
    }
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if result.audit_completed else 1


if __name__ == "__main__":
    raise SystemExit(main())
