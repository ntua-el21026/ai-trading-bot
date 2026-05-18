#!/usr/bin/env python3
"""Run the explicitly gated M44D paper-only short and scale-in rehearsal."""

from __future__ import annotations

import argparse
import json
import sys

from packages.paper.activation_rehearsal import (
    cli_request_from_args,
    load_runtime_request_environment,
    run_activation_rehearsal_m44d,
    write_activation_rehearsal_m44d_artifacts,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("short", "scale-in", "full"), default="full")
    parser.add_argument("--broker-mode", choices=("fake", "real-paper"), default="real-paper")
    parser.add_argument("--operator-approval")
    parser.add_argument("--short-primary-symbol", default="IWM")
    parser.add_argument("--short-fallback-symbol", default="SPY")
    parser.add_argument("--scale-primary-symbol", default="XLK")
    parser.add_argument("--scale-fallback-symbol", default="XLF")
    parser.add_argument("--short-max-qty", type=int, default=1)
    parser.add_argument("--scale-initial-max-qty", type=int, default=1)
    parser.add_argument("--scale-addon-max-qty", type=int, default=1)
    parser.add_argument("--confirm-paper-endpoint", action="store_true")
    parser.add_argument("--confirm-short-rehearsal-only", action="store_true")
    parser.add_argument("--confirm-scale-in-rehearsal-only", action="store_true")
    parser.add_argument("--confirm-protective-buy-stop-required", action="store_true")
    parser.add_argument("--confirm-additive-sell-stop-required", action="store_true")
    parser.add_argument("--confirm-cleanup-to-flat", action="store_true")
    parser.add_argument("--confirm-no-live-trading", action="store_true")
    parser.add_argument("--confirm-no-autonomous-live", action="store_true")
    parser.add_argument("--confirm-no-schedules", action="store_true")
    parser.add_argument("--confirm-no-leverage", action="store_true")
    parser.add_argument("--confirm-no-frozen-validation-start", action="store_true")
    parser.add_argument("--confirm-level4-not-ready", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    request = cli_request_from_args(args)
    result = run_activation_rehearsal_m44d(
        request,
        environ=load_runtime_request_environment(),
    )
    activation_path, readiness_path = write_activation_rehearsal_m44d_artifacts(result)
    print(
        json.dumps(
            {
                "go_no_go": result.go_no_go,
                "success": result.success,
                "activation_rehearsal_packet": str(activation_path),
                "frozen_readiness_packet": str(readiness_path),
                "broker_writes_performed": result.broker_writes_performed,
                "real_broker_writes_performed": result.real_broker_writes_performed,
                "blockers": result.blockers,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if result.success else 1


if __name__ == "__main__":
    sys.exit(main())
