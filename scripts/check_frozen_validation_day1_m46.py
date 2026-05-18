#!/usr/bin/env python3
"""Run the M46 frozen-validation Day-1 audit and write sanitized evidence."""

from __future__ import annotations

import argparse
import json
import sys

from packages.paper.day1_audit import (
    M46_DOC_PATH,
    M46_EVIDENCE_PATH,
    FrozenValidationDay1AuditRequest,
    run_frozen_validation_day1_audit_m46,
    write_frozen_validation_day1_audit_m46_artifact,
    write_frozen_validation_day1_audit_m46_doc,
)
from packages.paper.preflight import load_preflight_environment


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("fake", "real-paper"), default="real-paper")
    parser.add_argument("--m45-evidence", default=None)
    parser.add_argument("--output", default=M46_EVIDENCE_PATH)
    parser.add_argument("--doc-output", default=M46_DOC_PATH)
    parser.add_argument("--confirm-paper-only", action="store_true")
    parser.add_argument("--confirm-no-live-trading", action="store_true")
    parser.add_argument("--confirm-no-autonomous-live", action="store_true")
    parser.add_argument("--confirm-no-leverage", action="store_true")
    parser.add_argument("--confirm-no-level4", action="store_true")
    parser.add_argument("--confirm-no-forced-trades", action="store_true")
    parser.add_argument(
        "--fail-on-no-go",
        action="store_true",
        help="Return a non-zero exit code when the audit result is NO_GO.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    request = FrozenValidationDay1AuditRequest(
        mode=args.mode,
        confirm_paper_only=args.confirm_paper_only,
        confirm_no_live_trading=args.confirm_no_live_trading,
        confirm_no_autonomous_live=args.confirm_no_autonomous_live,
        confirm_no_leverage=args.confirm_no_leverage,
        confirm_no_level4=args.confirm_no_level4,
        confirm_no_forced_trades=args.confirm_no_forced_trades,
        **({} if args.m45_evidence is None else {"m45_evidence_path": args.m45_evidence}),
    )
    result = run_frozen_validation_day1_audit_m46(
        request,
        environ=load_preflight_environment(),
    )
    evidence_path = write_frozen_validation_day1_audit_m46_artifact(result, args.output)
    doc_path = write_frozen_validation_day1_audit_m46_doc(result, args.doc_output)
    packet = result.packet
    print(
        json.dumps(
            {
                "m46_result": packet.m46_result,
                "evidence_packet": str(evidence_path),
                "monitoring_doc": str(doc_path),
                "validation_status": packet.validation_status,
                "validation_window_active": packet.validation_window_active,
                "validation_day_index": packet.validation_day_index,
                "schedule_registry_status": packet.schedule_registry_status,
                "scheduler_execution_status": packet.scheduler_execution_status,
                "broker_open_orders_count": packet.broker_state.open_orders_count,
                "broker_positions_count": packet.broker_state.positions_count,
                "market_data_check_result": packet.market_data_status.latest_check_result,
                "broker_writes_performed_in_m46": packet.broker_writes_performed_in_m46,
                "scheduled_cycle_run_in_m46": packet.scheduled_cycle_run_in_m46,
                "blockers": list(packet.blockers),
            },
            indent=2,
            sort_keys=True,
        )
    )
    if args.fail_on_no_go and packet.m46_result != "GO":
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
