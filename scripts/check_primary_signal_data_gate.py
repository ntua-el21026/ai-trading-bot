#!/usr/bin/env python
"""Run the M44B non-IEX primary signal data gate."""

from __future__ import annotations

import argparse
import json

from packages.data.primary_signal_gate import (
    FROZEN_READINESS_M44B_EVIDENCE_PATH,
    FROZEN_READINESS_M44C_EVIDENCE_PATH,
    M44B_NON_IEX_DATA_GATE_WAIVER_APPROVAL,
    PRIMARY_SIGNAL_DATA_GATE_M44B_EVIDENCE_PATH,
    PRIMARY_SIGNAL_DATA_GATE_M44C_EVIDENCE_PATH,
    PrimarySignalDataGateRequest,
    build_frozen_readiness_m44b_packet,
    build_frozen_readiness_m44c_packet,
    run_primary_signal_data_gate,
    write_frozen_readiness_m44b_artifact,
    write_frozen_readiness_m44c_artifact,
    write_primary_signal_data_gate_artifact,
    write_primary_signal_data_gate_m44c_artifact,
)
from packages.paper.preflight import load_preflight_environment


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Milestone 44B primary signal data gate. This command performs read-only "
            "market-data verification or records an explicit waiver; it never performs "
            "broker writes, activates schedules, or starts frozen validation."
        )
    )
    parser.add_argument("--mode", choices=("verify", "waive"), required=True)
    parser.add_argument("--provider")
    parser.add_argument("--feed", choices=("sip", "iex", "delayed_sip", "eod", "other"))
    parser.add_argument("--symbols", default="")
    parser.add_argument("--operator-approval")
    parser.add_argument("--waiver-reason", default="")
    parser.add_argument("--output")
    parser.add_argument("--readiness-output")
    parser.add_argument("--confirm-read-only", action="store_true")
    parser.add_argument("--confirm-no-broker-writes", action="store_true")
    parser.add_argument("--confirm-no-schedules", action="store_true")
    parser.add_argument("--confirm-no-frozen-validation-start", action="store_true")
    return parser


def main() -> int:
    args = _parser().parse_args()
    symbols = tuple(symbol.strip().upper() for symbol in args.symbols.split(",") if symbol.strip())
    request = PrimarySignalDataGateRequest(
        mode=args.mode,
        provider=args.provider,
        feed=args.feed,
        symbols=symbols,
        operator_approval=args.operator_approval,
        waiver_reason=args.waiver_reason,
        confirm_read_only=args.confirm_read_only,
        confirm_no_broker_writes=args.confirm_no_broker_writes,
        confirm_no_schedules=args.confirm_no_schedules,
        confirm_no_frozen_validation_start=args.confirm_no_frozen_validation_start,
    )
    result = run_primary_signal_data_gate(
        request,
        environ=load_preflight_environment(),
    )
    is_m44c_tiingo = (
        result.packet.configured_primary_signal_provider == "tiingo"
        and result.packet.configured_primary_signal_feed == "eod"
        and args.mode == "verify"
    )
    if is_m44c_tiingo:
        output = args.output or PRIMARY_SIGNAL_DATA_GATE_M44C_EVIDENCE_PATH
        readiness_output = args.readiness_output or FROZEN_READINESS_M44C_EVIDENCE_PATH
        gate_path = write_primary_signal_data_gate_m44c_artifact(result, output)
        readiness_m44c = build_frozen_readiness_m44c_packet(
            result.packet,
            m44c_gate_packet_path=str(gate_path),
        )
        readiness_path = write_frozen_readiness_m44c_artifact(readiness_m44c, readiness_output)
        readiness_go_no_go = readiness_m44c.go_no_go
        m45_readiness = readiness_m44c.packet.m45_readiness
        readiness_blockers = readiness_m44c.blockers
    else:
        output = args.output or PRIMARY_SIGNAL_DATA_GATE_M44B_EVIDENCE_PATH
        readiness_output = args.readiness_output or FROZEN_READINESS_M44B_EVIDENCE_PATH
        gate_path = write_primary_signal_data_gate_artifact(result, output)
        readiness_m44b = build_frozen_readiness_m44b_packet(
            result.packet,
            gate_packet_path=str(gate_path),
        )
        readiness_path = write_frozen_readiness_m44b_artifact(readiness_m44b, readiness_output)
        readiness_go_no_go = readiness_m44b.go_no_go
        m45_readiness = readiness_m44b.packet.m45_readiness
        readiness_blockers = readiness_m44b.blockers
    print(
        json.dumps(
            {
                "mode": result.packet.mode,
                "primary_signal_data_gate_packet_path": str(gate_path),
                "refreshed_readiness_packet_path": str(readiness_path),
                "non_iex_primary_signal_data_verified": (
                    result.packet.non_iex_primary_signal_data_verified
                ),
                "non_iex_primary_signal_data_waived": (
                    result.packet.non_iex_primary_signal_data_waived
                ),
                "data_check_performed": result.packet.data_check_performed,
                "data_check_result": result.packet.data_check_result,
                "m45_readiness": m45_readiness,
                "go_no_go": readiness_go_no_go,
                "blockers": list(readiness_blockers),
                "broker_writes_performed": False,
                "schedules_activated": False,
                "frozen_validation_started": False,
                "waiver_marker_required": (
                    M44B_NON_IEX_DATA_GATE_WAIVER_APPROVAL if args.mode == "waive" else None
                ),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if readiness_go_no_go == "go" else 1


if __name__ == "__main__":
    raise SystemExit(main())
