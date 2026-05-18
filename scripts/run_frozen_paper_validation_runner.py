#!/usr/bin/env python3
"""Run the local M47 frozen paper validation runner loop."""

from __future__ import annotations

import argparse
import json
import sys

from packages.paper.validation_runner import (
    FrozenValidationCycleRequest,
    run_frozen_validation_cycle_once,
    run_runner_daemon,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("fake", "real-paper"), default="real-paper")
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--daemon", action="store_true")
    parser.add_argument("--poll-seconds", type=int, default=300)
    parser.add_argument("--timeout-seconds", type=float, default=15.0)
    parser.add_argument("--confirm-paper-only", action="store_true")
    parser.add_argument("--confirm-no-live-trading", action="store_true")
    parser.add_argument("--confirm-no-autonomous-live", action="store_true")
    parser.add_argument("--confirm-no-leverage", action="store_true")
    parser.add_argument("--confirm-live-shorting-disabled", action="store_true")
    parser.add_argument("--confirm-ai-no-broker-authority", action="store_true")
    parser.add_argument("--confirm-no-level4", action="store_true")
    parser.add_argument("--confirm-no-forced-trades", action="store_true")
    return parser.parse_args()


def _request(args: argparse.Namespace) -> FrozenValidationCycleRequest:
    return FrozenValidationCycleRequest(
        mode=args.mode,
        confirm_paper_only=args.confirm_paper_only,
        confirm_no_live_trading=args.confirm_no_live_trading,
        confirm_no_autonomous_live=args.confirm_no_autonomous_live,
        confirm_no_leverage=args.confirm_no_leverage,
        confirm_live_shorting_disabled=args.confirm_live_shorting_disabled,
        confirm_ai_no_broker_authority=args.confirm_ai_no_broker_authority,
        confirm_no_level4=args.confirm_no_level4,
        confirm_no_forced_trades=args.confirm_no_forced_trades,
        timeout_seconds=args.timeout_seconds,
    )


def main() -> int:
    args = parse_args()
    if args.once == args.daemon:
        print("exactly one of --once or --daemon is required", file=sys.stderr)
        return 2
    request = _request(args)
    if args.daemon:
        run_runner_daemon(request, poll_seconds=args.poll_seconds)
        return 0
    result = run_frozen_validation_cycle_once(request)
    print(
        json.dumps(
            {
                "cycle_result": result.packet.cycle_result,
                "due_cycle_detected": result.packet.due_cycle_detected,
                "broker_writes_performed": result.broker_writes_performed,
                "evidence_packet": None
                if result.evidence_path is None
                else str(result.evidence_path),
                "blockers": list(result.packet.blockers),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if result.packet.cycle_result in {"no_trade", "skipped_not_due"} else 1


if __name__ == "__main__":
    sys.exit(main())
