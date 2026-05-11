"""Run the Milestone 35D post-session audit path."""

from __future__ import annotations

import argparse
import json
from typing import cast

from packages.paper import (
    M34_RESULT_EVIDENCE_PATH,
    M35D_POST_SESSION_AUDIT_EVIDENCE_PATH,
    M35E_HOLD_DECISION_EVIDENCE_PATH,
    OperatorHoldDecision,
    PostSessionAuditMode,
    PostSessionAuditRequest,
    PostSessionAuditScenarioId,
    load_preflight_environment,
    run_first_controlled_paper_session_hold_decision,
    run_first_controlled_paper_session_post_session_audit,
    write_hold_decision_artifact,
    write_post_session_audit_artifact,
)

WARNING = (
    "Milestone 35D/35E post-session audit only. This command performs no broker writes, "
    "does not start a new session, and does not cancel, replace, or flatten orders."
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Audit the first controlled paper-session incident and broker state.",
    )
    parser.add_argument(
        "--mode",
        choices=("fake", "real-read-only", "hold-decision"),
        default="fake",
        help=(
            "Fake mode uses local broker fixtures. Real-read-only and hold-decision "
            "modes perform gated Alpaca reads."
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
        choices=("HOLD_PROTECTED_POSITION_UNTIL_NEXT_REVIEW",),
        default=None,
        help="Optional M35E operator hold decision to record.",
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
    parser.add_argument("--confirm-paper-endpoint", action="store_true")
    parser.add_argument("--confirm-no-broker-writes", action="store_true")
    parser.add_argument("--confirm-no-live-trading", action="store_true")
    parser.add_argument("--confirm-no-autonomous-live", action="store_true")
    parser.add_argument("--confirm-no-schedules", action="store_true")
    parser.add_argument("--confirm-no-leverage", action="store_true")
    args = parser.parse_args(argv)

    print(WARNING)
    mode = args.mode
    audit_mode = "real-read-only" if mode == "hold-decision" else mode
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
        packet = hold_result.packet
        broker_state = packet.current_broker_state
        summary = {
            "mode": mode,
            "scenario_id": hold_result.scenario_id,
            "operator_decision": hold_result.operator_decision,
            "hold_confirmed": hold_result.hold_confirmed,
            "go_no_go": hold_result.go_no_go,
            "blockers": hold_result.blockers,
            "cleanup_hold_recommendation": packet.cleanup_hold_recommendation,
            "target_symbol": broker_state.target_symbol,
            "target_position_quantity": broker_state.target_position_quantity,
            "protective_stop_verified": broker_state.protective_stop_verified,
            "protective_stop_order_status": broker_state.protective_stop_order_status,
            "open_orders_total": broker_state.open_orders_total,
            "positions_total": broker_state.positions_total,
            "reconciliation_summary": broker_state.reconciliation_summary,
            "cleanup_performed": packet.cleanup_performed,
            "flatten_performed": packet.flatten_performed,
            "cancel_performed": packet.cancel_performed,
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
    packet = result.packet
    broker_state = packet.current_broker_state
    summary = {
        "mode": result.mode,
        "scenario_id": result.scenario_id,
        "audit_completed": result.audit_completed,
        "go_no_go": result.go_no_go,
        "blockers": result.blockers,
        "cleanup_hold_decision_recommendation": (
            packet.cleanup_hold_decision_recommendation
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
