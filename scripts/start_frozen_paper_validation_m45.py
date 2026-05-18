#!/usr/bin/env python3
"""Start the M45 long+short+scale-in frozen paper validation if all gates pass."""

from __future__ import annotations

import argparse
import json
import sys

from packages.paper.preflight import load_preflight_environment
from packages.paper.validation_start import (
    FrozenPaperValidationStartRequest,
    run_frozen_paper_validation_start_m45,
    write_frozen_paper_validation_start_m45_artifact,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("fake", "real-paper"), default="real-paper")
    parser.add_argument("--operator-approval")
    parser.add_argument("--confirm-paper-only", action="store_true")
    parser.add_argument("--confirm-flat-baseline", action="store_true")
    parser.add_argument("--confirm-tiingo-eod-primary-signal-data", action="store_true")
    parser.add_argument("--confirm-paper-shorts-enabled", action="store_true")
    parser.add_argument("--confirm-live-shorting-disabled", action="store_true")
    parser.add_argument("--confirm-long-scale-ins-enabled", action="store_true")
    parser.add_argument("--confirm-short-scale-ins-disabled", action="store_true")
    parser.add_argument("--confirm-no-live-trading", action="store_true")
    parser.add_argument("--confirm-no-autonomous-live", action="store_true")
    parser.add_argument("--confirm-no-leverage", action="store_true")
    parser.add_argument("--confirm-ai-negative-only", action="store_true")
    parser.add_argument("--confirm-no-forced-trades", action="store_true")
    parser.add_argument("--confirm-level4-not-ready", action="store_true")
    parser.add_argument("--output")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    request = FrozenPaperValidationStartRequest(
        mode=args.mode,
        operator_approval=args.operator_approval,
        confirm_paper_only=args.confirm_paper_only,
        confirm_flat_baseline=args.confirm_flat_baseline,
        confirm_tiingo_eod_primary_signal_data=args.confirm_tiingo_eod_primary_signal_data,
        confirm_paper_shorts_enabled=args.confirm_paper_shorts_enabled,
        confirm_live_shorting_disabled=args.confirm_live_shorting_disabled,
        confirm_long_scale_ins_enabled=args.confirm_long_scale_ins_enabled,
        confirm_short_scale_ins_disabled=args.confirm_short_scale_ins_disabled,
        confirm_no_live_trading=args.confirm_no_live_trading,
        confirm_no_autonomous_live=args.confirm_no_autonomous_live,
        confirm_no_leverage=args.confirm_no_leverage,
        confirm_ai_negative_only=args.confirm_ai_negative_only,
        confirm_no_forced_trades=args.confirm_no_forced_trades,
        confirm_level4_not_ready=args.confirm_level4_not_ready,
    )
    result = run_frozen_paper_validation_start_m45(
        request,
        environ=load_preflight_environment(),
    )
    if args.output:
        output = write_frozen_paper_validation_start_m45_artifact(result, args.output)
    else:
        output = write_frozen_paper_validation_start_m45_artifact(result)
    print(
        json.dumps(
            {
                "go_no_go": result.go_no_go,
                "success": result.success,
                "validation_status": result.packet.validation_status,
                "validation_start_timestamp_utc": (
                    None
                    if result.packet.validation_start_timestamp_utc is None
                    else result.packet.validation_start_timestamp_utc.isoformat()
                ),
                "validation_end_target_timestamp_utc": (
                    None
                    if result.packet.validation_end_target_timestamp_utc is None
                    else result.packet.validation_end_target_timestamp_utc.isoformat()
                ),
                "evidence_packet": str(output),
                "schedule_activated": result.schedule_activated,
                "schedule_final_state": result.packet.schedule.schedule_final_state,
                "broker_writes_performed": result.broker_writes_performed,
                "blockers": result.blockers,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if result.success else 1


if __name__ == "__main__":
    sys.exit(main())
