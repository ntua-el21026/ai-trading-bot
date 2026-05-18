#!/usr/bin/env python3
"""Audit M47B durable/off-PC frozen paper validation runner readiness."""

from __future__ import annotations

import argparse
import json
import sys

from packages.paper.durable_runner import (
    M47B_DOC_PATH,
    M47B_EVIDENCE_PATH,
    DurableRunnerM47BRequest,
    run_durable_runner_m47b,
    write_durable_runner_m47b_artifact,
    write_durable_runner_m47b_doc,
)
from packages.paper.preflight import load_preflight_environment


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("fake", "real-paper"), default="real-paper")
    parser.add_argument("--operator-approval")
    parser.add_argument("--output", default=M47B_EVIDENCE_PATH)
    parser.add_argument("--doc-output", default=M47B_DOC_PATH)
    parser.add_argument("--m45-evidence", default=None)
    parser.add_argument("--m46-evidence", default=None)
    parser.add_argument("--m47-evidence", default=None)
    parser.add_argument("--heartbeat-path", default=None)
    parser.add_argument("--max-heartbeat-age-seconds", type=int, default=900)
    parser.add_argument("--temporal-schedule-active", action="store_true")
    parser.add_argument("--worker-registration-confirmed", action="store_true")
    parser.add_argument("--confirm-paper-only", action="store_true")
    parser.add_argument("--confirm-validation-already-started", action="store_true")
    parser.add_argument("--confirm-no-live-trading", action="store_true")
    parser.add_argument("--confirm-no-autonomous-live", action="store_true")
    parser.add_argument("--confirm-no-leverage", action="store_true")
    parser.add_argument("--confirm-live-shorting-disabled", action="store_true")
    parser.add_argument("--confirm-ai-no-broker-authority", action="store_true")
    parser.add_argument("--confirm-no-level4", action="store_true")
    parser.add_argument("--confirm-no-forced-trades", action="store_true")
    parser.add_argument("--confirm-no-vercel-execution-worker", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    request_kwargs = {}
    if args.m45_evidence is not None:
        request_kwargs["m45_evidence_path"] = args.m45_evidence
    if args.m46_evidence is not None:
        request_kwargs["m46_evidence_path"] = args.m46_evidence
    if args.m47_evidence is not None:
        request_kwargs["m47_evidence_path"] = args.m47_evidence
    if args.heartbeat_path is not None:
        request_kwargs["heartbeat_path"] = args.heartbeat_path
    request = DurableRunnerM47BRequest(
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
        confirm_no_vercel_execution_worker=args.confirm_no_vercel_execution_worker,
        max_heartbeat_age_seconds=args.max_heartbeat_age_seconds,
        temporal_schedule_active=args.temporal_schedule_active,
        worker_registration_confirmed=(
            True if args.worker_registration_confirmed else "unknown"
        ),
        **request_kwargs,
    )
    result = run_durable_runner_m47b(
        request,
        environ=load_preflight_environment(),
    )
    evidence_path = write_durable_runner_m47b_artifact(result, args.output)
    doc_path = write_durable_runner_m47b_doc(result, args.doc_output)
    packet = result.packet
    print(
        json.dumps(
            {
                "off_pc_operation_result": packet.off_pc_operation_result,
                "preparation_result": packet.preparation_result,
                "evidence_packet": str(evidence_path),
                "runner_doc": str(doc_path),
                "selected_durable_path": packet.selected_durable_path,
                "durable_runner_status": packet.durable_runner_status,
                "validation_status": packet.validation_status,
                "validation_window_active": packet.validation_window_active,
                "validation_day_index": packet.validation_day_index,
                "heartbeat_status": packet.heartbeat_status,
                "temporal_schedule_created": packet.temporal_schedule_created,
                "worker_registration_confirmed": packet.worker_registration_confirmed,
                "vercel_execution_worker_detected": packet.vercel_execution_worker_detected,
                "broker_open_orders_count": packet.broker_state.open_orders_count,
                "broker_positions_count": packet.broker_state.positions_count,
                "market_data_check_result": packet.market_data_status.latest_check_result,
                "broker_writes_performed_in_m47b": packet.broker_writes_performed_in_m47b,
                "blockers": list(packet.blockers),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if packet.preparation_result == "GO" else 1


if __name__ == "__main__":
    sys.exit(main())
