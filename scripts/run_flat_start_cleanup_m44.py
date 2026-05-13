#!/usr/bin/env python
"""Run M44 flat-start cleanup and write sanitized readiness evidence."""

from __future__ import annotations

import argparse
import json

from packages.paper.frozen_readiness import (
    FLAT_START_CLEANUP_M44_EVIDENCE_PATH,
    FROZEN_READINESS_M44_EVIDENCE_PATH,
    FlatStartCleanupRequest,
    build_frozen_readiness_m44_packet,
    run_flat_start_cleanup_m44,
    write_flat_start_cleanup_artifact,
    write_frozen_readiness_m44_artifact,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Milestone 44 flat-start cleanup only. This command never starts frozen "
            "validation and may write only risk-reducing AAPL/MSFT/XLK paper cleanup."
        )
    )
    parser.add_argument("--mode", choices=("fake", "real-paper"), default="real-paper")
    parser.add_argument("--operator-approval", required=True)
    parser.add_argument("--symbols", default="AAPL,MSFT,XLK")
    parser.add_argument("--output", default=FLAT_START_CLEANUP_M44_EVIDENCE_PATH)
    parser.add_argument("--readiness-output", default=FROZEN_READINESS_M44_EVIDENCE_PATH)
    parser.add_argument("--confirm-paper-endpoint", action="store_true")
    parser.add_argument("--confirm-risk-reducing-only", action="store_true")
    parser.add_argument("--confirm-cancel-session-stop-before-sell", action="store_true")
    parser.add_argument("--confirm-emergency-reprotect-if-sell-fails", action="store_true")
    parser.add_argument("--confirm-no-new-entry", action="store_true")
    parser.add_argument("--confirm-no-buy-orders", action="store_true")
    parser.add_argument("--confirm-no-short-orders", action="store_true")
    parser.add_argument("--confirm-no-live-trading", action="store_true")
    parser.add_argument("--confirm-no-autonomous-live", action="store_true")
    parser.add_argument("--confirm-no-schedules", action="store_true")
    parser.add_argument("--confirm-no-leverage", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    symbols = tuple(item.strip().upper() for item in args.symbols.split(",") if item.strip())
    request = FlatStartCleanupRequest(
        mode=args.mode,
        operator_approval=args.operator_approval,
        symbols=symbols,
        confirm_paper_endpoint=args.confirm_paper_endpoint,
        confirm_risk_reducing_only=args.confirm_risk_reducing_only,
        confirm_cancel_session_stop_before_sell=args.confirm_cancel_session_stop_before_sell,
        confirm_emergency_reprotect_if_sell_fails=(
            args.confirm_emergency_reprotect_if_sell_fails
        ),
        confirm_no_new_entry=args.confirm_no_new_entry,
        confirm_no_buy_orders=args.confirm_no_buy_orders,
        confirm_no_short_orders=args.confirm_no_short_orders,
        confirm_no_live_trading=args.confirm_no_live_trading,
        confirm_no_autonomous_live=args.confirm_no_autonomous_live,
        confirm_no_schedules=args.confirm_no_schedules,
        confirm_no_leverage=args.confirm_no_leverage,
    )
    result = run_flat_start_cleanup_m44(request)
    cleanup_path = write_flat_start_cleanup_artifact(result, args.output)
    readiness = build_frozen_readiness_m44_packet(flat_cleanup_packet_path=cleanup_path)
    readiness_path = write_frozen_readiness_m44_artifact(readiness, args.readiness_output)
    summary = {
        "success": result.success,
        "go_no_go": result.go_no_go,
        "cleanup_packet_path": str(cleanup_path),
        "frozen_readiness_packet_path": str(readiness_path),
        "flat_start_achieved": result.packet.m45_flat_start_ready,
        "m45_readiness": readiness.m45_readiness,
        "blockers": readiness.blockers,
        "broker_writes_performed": result.broker_writes_performed,
        "real_broker_writes_performed": result.real_broker_writes_performed,
        "short_orders_performed": result.packet.short_orders_performed,
        "frozen_validation_started": result.packet.frozen_validation_started,
        "schedules_activated": result.packet.schedules_activated,
    }
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if result.success else 1


if __name__ == "__main__":
    raise SystemExit(main())
