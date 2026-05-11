"""Run the Milestone 35D post-session audit path."""

from __future__ import annotations

import argparse
import json
from typing import cast

from packages.paper import (
    M34_RESULT_EVIDENCE_PATH,
    M35D_POST_SESSION_AUDIT_EVIDENCE_PATH,
    PostSessionAuditMode,
    PostSessionAuditRequest,
    PostSessionAuditScenarioId,
    load_preflight_environment,
    run_first_controlled_paper_session_post_session_audit,
    write_post_session_audit_artifact,
)

WARNING = (
    "Milestone 35D post-session audit only. This command performs no broker writes, "
    "does not start a new session, and does not cancel, replace, or flatten orders."
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Audit the first controlled paper-session incident and broker state.",
    )
    parser.add_argument(
        "--mode",
        choices=("fake", "real-read-only"),
        default="fake",
        help=(
            "Fake mode uses local broker fixtures. Real-read-only mode performs gated "
            "Alpaca reads."
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
        "--audit-output",
        default=M35D_POST_SESSION_AUDIT_EVIDENCE_PATH,
        help="Sanitized post-session audit packet path.",
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
    request = PostSessionAuditRequest(
        mode=cast(PostSessionAuditMode, mode),
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
    result = run_first_controlled_paper_session_post_session_audit(
        request,
        environ=load_preflight_environment() if mode == "real-read-only" else {},
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
