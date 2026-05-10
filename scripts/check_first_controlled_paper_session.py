"""Run the fake/local first controlled paper-session wiring harness.

This script never calls broker, AI/news, alert, market-data, Temporal Cloud, managed database, or
deployment services. It does not submit, cancel, replace, or flatten real orders.
"""

from __future__ import annotations

import argparse
import json
import sys

from packages.paper import (
    FIRST_SESSION_APPROVAL_MARKER,
    FIRST_SESSION_SAFE_MODE,
    FIRST_SESSION_SCENARIO_IDS,
    default_first_session_input,
    run_first_controlled_paper_session_check,
)

WARNING = (
    "Fake/local first-session wiring only. Actual paper trading has not started; "
    "no real broker orders are submitted."
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run a fake/local first controlled paper-session wiring scenario.",
    )
    parser.add_argument(
        "--scenario",
        choices=FIRST_SESSION_SCENARIO_IDS,
        default="happy_path",
        help="Fake/local first-session scenario ID.",
    )
    parser.add_argument(
        "--mode",
        default=FIRST_SESSION_SAFE_MODE,
        help="Only fake-local mode is supported.",
    )
    parser.add_argument(
        "--operator-approval-marker",
        default=FIRST_SESSION_APPROVAL_MARKER,
        help="Fake/local operator approval marker. Do not pass secrets.",
    )
    args = parser.parse_args(argv)

    if args.mode != FIRST_SESSION_SAFE_MODE:
        print("Refusing non-fake first-session mode.", file=sys.stderr)
        return 2

    print(WARNING)
    run_input = default_first_session_input(
        args.scenario,
        operator_approval_marker=args.operator_approval_marker,
    )
    result = run_first_controlled_paper_session_check(run_input)
    summary = {
        "scenario_id": result.scenario_id,
        "success": result.success,
        "refused": result.refused,
        "unsafe": result.unsafe,
        "paper_operations_started": result.paper_operations_started,
        "actual_paper_trading_started": result.actual_paper_trading_started,
        "real_broker_writes_attempted": result.real_broker_writes_attempted,
        "external_calls_attempted": result.external_calls_attempted,
        "schedules_activated": result.schedules_activated,
        "live_trading_enabled": result.live_trading_enabled,
        "autonomous_live_execution_enabled": result.autonomous_live_execution_enabled,
        "level4_ready": result.level4_ready,
        "evidence_package_id": result.evidence_package.evidence_package_id,
        "session_id": result.evidence_package.session_id,
        "report_id": result.evidence_package.report_id,
        "dashboard_snapshot_status": result.evidence_package.dashboard_snapshot_status,
        "incident_ids": result.evidence_package.incident_ids,
        "refusal_reasons": result.refusal_reasons,
        "note": result.note,
    }
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if result.success else 1


if __name__ == "__main__":
    raise SystemExit(main())
