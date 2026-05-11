"""Run the Milestone 31 first-session read-only preflight authorization check."""

from __future__ import annotations

import argparse
import json

from packages.paper import (
    MILESTONE_31_FAKE_OPERATOR_APPROVAL,
    MILESTONE_31_READ_ONLY_OPERATOR_APPROVAL,
    MILESTONE_32_READ_ONLY_OPERATOR_APPROVAL,
    MILESTONE_33_READ_ONLY_OPERATOR_APPROVAL,
    PREFLIGHT_SCENARIO_IDS,
    default_first_session_preflight_request,
    load_preflight_environment,
    run_first_controlled_paper_session_preflight,
    write_launch_packet_artifact,
)

WARNING = (
    "Milestone 31/32/33 read-only preflight only. Actual paper trading has not started; "
    "no broker writes are performed."
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run the first controlled paper-session preflight authorization packet.",
    )
    parser.add_argument(
        "--mode",
        choices=("fake", "real-read-only"),
        default="fake",
        help="Fake mode is local only. Real-read-only mode requires explicit gates.",
    )
    parser.add_argument(
        "--scenario",
        choices=PREFLIGHT_SCENARIO_IDS,
        default="happy_path",
        help="Preflight scenario ID.",
    )
    parser.add_argument(
        "--operator-approval",
        default=None,
        help=(
            "Operator marker. Fake success uses "
            f"{MILESTONE_31_FAKE_OPERATOR_APPROVAL}; read-only uses "
            f"{MILESTONE_31_READ_ONLY_OPERATOR_APPROVAL} or "
            f"{MILESTONE_32_READ_ONLY_OPERATOR_APPROVAL} or "
            f"{MILESTONE_33_READ_ONLY_OPERATOR_APPROVAL}. Do not pass secrets."
        ),
    )
    parser.add_argument(
        "--packet-output",
        default=None,
        help="Optional sanitized launch packet JSON output path. Do not pass a secrets path.",
    )
    parser.add_argument("--target-symbol", default=None)
    parser.add_argument(
        "--target-symbol-allowlist",
        default=None,
        help="Optional comma-separated target allowlist for the launch packet.",
    )
    parser.add_argument("--confirm-paper-endpoint", action="store_true")
    parser.add_argument("--confirm-no-broker-writes", action="store_true")
    parser.add_argument("--confirm-no-live-trading", action="store_true")
    parser.add_argument("--confirm-no-autonomous-live", action="store_true")
    parser.add_argument("--confirm-no-schedules", action="store_true")
    parser.add_argument("--confirm-no-leverage", action="store_true")
    args = parser.parse_args(argv)

    print(WARNING)
    request = default_first_session_preflight_request(
        args.scenario,
        mode=args.mode,
        operator_approval_marker=args.operator_approval,
        target_symbol=None if args.target_symbol is None else args.target_symbol.upper(),
        target_symbol_allowlist=(
            None
            if args.target_symbol_allowlist is None
            else tuple(
                symbol.strip().upper()
                for symbol in args.target_symbol_allowlist.split(",")
                if symbol.strip()
            )
        ),
        confirm_paper_endpoint=(
            True if args.mode == "fake" else args.confirm_paper_endpoint
        ),
        confirm_no_broker_writes=(
            True if args.mode == "fake" else args.confirm_no_broker_writes
        ),
        confirm_no_live_trading=(
            True if args.mode == "fake" else args.confirm_no_live_trading
        ),
        confirm_no_autonomous_live=(
            True if args.mode == "fake" else args.confirm_no_autonomous_live
        ),
        confirm_no_schedules=True if args.mode == "fake" else args.confirm_no_schedules,
        confirm_no_leverage=True if args.mode == "fake" else args.confirm_no_leverage,
    )
    result = run_first_controlled_paper_session_preflight(
        request,
        environ=load_preflight_environment() if args.mode == "real-read-only" else {},
    )
    packet_path = None
    if args.packet_output:
        packet_path = str(write_launch_packet_artifact(result, args.packet_output))
    packet = result.packet
    summary = {
        "scenario_id": result.scenario_id,
        "mode": result.mode,
        "success": result.success,
        "refused": result.refused,
        "go_no_go_decision": result.go_no_go_decision,
        "blockers": result.blockers,
        "authorization_packet_id": packet.authorization_packet_id,
        "authorization_packet_path": packet_path,
        "actual_paper_trading_started": result.actual_paper_trading_started,
        "real_broker_orders_submitted": result.real_broker_orders_submitted,
        "real_broker_writes_attempted": result.real_broker_writes_attempted,
        "broker_write_methods_called": result.broker_write_methods_called,
        "read_only_broker_calls_performed": result.read_only_broker_calls_performed,
        "real_read_only_alpaca_calls_performed": result.real_read_only_alpaca_calls_performed,
        "provider_ai_telegram_vercel_temporal_calls_performed": (
            result.provider_ai_telegram_vercel_temporal_calls_performed
        ),
        "schedules_activated": result.schedules_activated,
        "live_trading_enabled": result.live_trading_enabled,
        "autonomous_live_execution_enabled": result.autonomous_live_execution_enabled,
        "leverage_enabled": result.leverage_enabled,
        "ai_broker_write_authority": result.ai_broker_write_authority,
        "level4_ready": result.level4_ready,
        "broker_endpoint_mode": packet.broker_endpoint_mode,
        "paper_endpoint_proven": packet.paper_endpoint_proof.paper_endpoint_proven,
        "live_endpoint_rejected": packet.live_endpoint_rejection_proof.live_endpoint_rejected,
        "account_status_summary": packet.account_status_summary.status_summary,
        "clock_session_summary": packet.clock_session_summary.status_summary,
        "open_orders_summary": packet.open_orders_summary.status_summary,
        "positions_summary": packet.positions_summary.status_summary,
        "target_symbol": packet.target_symbol_cleanliness.target_symbol,
        "target_symbol_allowlist": packet.target_symbol_allowlist,
        "target_symbol_clean": packet.target_symbol_cleanliness.clean,
        "cleanup_policy_mode": packet.cleanup_policy_decision.mode,
        "evidence_persistence_mode": packet.evidence_persistence_decision.mode,
        "note": result.note,
    }
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if result.success else 1


if __name__ == "__main__":
    raise SystemExit(main())
