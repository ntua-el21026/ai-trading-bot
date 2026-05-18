#!/usr/bin/env python3
"""Activate and audit the M47 frozen paper validation runner."""

from __future__ import annotations

import argparse
import json
import sys

from packages.paper.preflight import load_preflight_environment
from packages.paper.validation_runner import (
    M47_DOC_PATH,
    M47_EVIDENCE_PATH,
    FrozenValidationRunnerRequest,
    run_frozen_validation_runner_m47,
    write_frozen_validation_runner_m47_artifact,
    write_frozen_validation_runner_m47_doc,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("fake", "real-paper"), default="real-paper")
    parser.add_argument("--operator-approval")
    parser.add_argument("--m45-evidence", default=None)
    parser.add_argument("--m46-evidence", default=None)
    parser.add_argument("--output", default=M47_EVIDENCE_PATH)
    parser.add_argument("--doc-output", default=M47_DOC_PATH)
    parser.add_argument("--poll-seconds", type=int, default=300)
    parser.add_argument("--timeout-seconds", type=float, default=15.0)
    parser.add_argument("--inspect-only", action="store_true")
    parser.add_argument("--skip-due-cycle-check", action="store_true")
    parser.add_argument("--confirm-paper-only", action="store_true")
    parser.add_argument("--confirm-validation-already-started", action="store_true")
    parser.add_argument("--confirm-no-live-trading", action="store_true")
    parser.add_argument("--confirm-no-autonomous-live", action="store_true")
    parser.add_argument("--confirm-no-leverage", action="store_true")
    parser.add_argument("--confirm-live-shorting-disabled", action="store_true")
    parser.add_argument("--confirm-ai-no-broker-authority", action="store_true")
    parser.add_argument("--confirm-no-level4", action="store_true")
    parser.add_argument("--confirm-no-forced-trades", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    request_kwargs = {}
    if args.m45_evidence is not None:
        request_kwargs["m45_evidence_path"] = args.m45_evidence
    if args.m46_evidence is not None:
        request_kwargs["m46_evidence_path"] = args.m46_evidence
    request = FrozenValidationRunnerRequest(
        mode=args.mode,
        operator_approval=args.operator_approval,
        confirm_paper_only=args.confirm_paper_only,
        confirm_validation_already_started=args.confirm_validation_already_started,
        confirm_no_live_trading=args.confirm_no_live_trading,
        confirm_no_autonomous_live=args.confirm_no_autonomous_live,
        confirm_no_leverage=args.confirm_no_leverage,
        confirm_live_shorting_disabled=args.confirm_live_shorting_disabled,
        confirm_ai_no_broker_authority=args.confirm_ai_no_broker_authority,
        confirm_no_level4=args.confirm_no_level4,
        confirm_no_forced_trades=args.confirm_no_forced_trades,
        activate_runner=not args.inspect_only,
        run_due_cycle_check=not args.skip_due_cycle_check,
        poll_seconds=args.poll_seconds,
        timeout_seconds=args.timeout_seconds,
        **request_kwargs,
    )
    result = run_frozen_validation_runner_m47(
        request,
        environ=load_preflight_environment(),
    )
    evidence_path = write_frozen_validation_runner_m47_artifact(result, args.output)
    doc_path = write_frozen_validation_runner_m47_doc(result, args.doc_output)
    packet = result.packet
    print(
        json.dumps(
            {
                "m47_result": packet.m47_result,
                "success": result.success,
                "evidence_packet": str(evidence_path),
                "runner_doc": str(doc_path),
                "validation_status": packet.validation_status,
                "validation_window_active": packet.validation_window_active,
                "validation_day_index": packet.validation_day_index,
                "runner_path_selected": packet.runner_path_selected,
                "runner_status": packet.runner_status,
                "schedule_or_runner_id": packet.schedule_or_runner_id,
                "due_cycle_detected": packet.due_cycle_detected,
                "cycle_ran_in_m47": packet.cycle_ran_in_m47,
                "cycle_result": packet.cycle_result,
                "broker_writes_performed_in_m47": packet.broker_writes_performed_in_m47,
                "broker_writes_reason": packet.broker_writes_reason,
                "broker_open_orders_count": packet.post_activation_broker_state.open_orders_count,
                "broker_positions_count": packet.post_activation_broker_state.positions_count,
                "market_data_check_result": packet.market_data_status.latest_check_result,
                "blockers": list(packet.blockers),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if result.success else 1


if __name__ == "__main__":
    sys.exit(main())
