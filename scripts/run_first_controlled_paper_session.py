"""Run the real-gated first controlled paper-session wiring check.

Milestone 30 does not execute the real first controlled paper session. This script defaults to a
safe refusal and supports fake/stub mode only for local wiring verification.
"""

from __future__ import annotations

import argparse
import json

from packages.paper import (
    MILESTONE_30_FAKE_OPERATOR_APPROVAL,
    REAL_SESSION_SCENARIO_IDS,
    default_real_session_gate_config,
    run_real_first_controlled_paper_session_gate,
)

WARNING = (
    "Milestone 30 real-gate wiring only. Actual paper trading has not started; "
    "no real broker orders are submitted."
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run the first controlled paper-session real-gate wiring path.",
    )
    parser.add_argument(
        "--mode",
        choices=("real-gated", "fake"),
        default="real-gated",
        help="Default real-gated mode refuses unless every future real-session gate is present.",
    )
    parser.add_argument(
        "--scenario",
        choices=REAL_SESSION_SCENARIO_IDS,
        default="happy_path",
        help="Real-gate or fake/stub scenario ID.",
    )
    parser.add_argument(
        "--operator-approval",
        default=None,
        help=(
            "Operator approval marker. For fake/stub success use "
            f"{MILESTONE_30_FAKE_OPERATOR_APPROVAL}. Do not pass secrets."
        ),
    )
    args = parser.parse_args(argv)

    print(WARNING)
    gate_config = default_real_session_gate_config(
        args.scenario,
        mode=args.mode,
        operator_approval_marker=args.operator_approval,
    )
    result = run_real_first_controlled_paper_session_gate(gate_config)
    summary = {
        "scenario_id": result.scenario_id,
        "mode": result.mode,
        "success": result.success,
        "refused": result.refused,
        "unsafe": result.unsafe,
        "ready_for_future_real_execution": result.ready_for_future_real_execution,
        "actual_paper_trading_started": result.actual_paper_trading_started,
        "real_broker_orders_submitted": result.real_broker_orders_submitted,
        "real_broker_writes_attempted": result.real_broker_writes_attempted,
        "external_calls_attempted": result.external_calls_attempted,
        "schedules_activated": result.schedules_activated,
        "live_trading_enabled": result.live_trading_enabled,
        "autonomous_live_execution_enabled": result.autonomous_live_execution_enabled,
        "level4_ready": result.level4_ready,
        "leverage_enabled": result.leverage_enabled,
        "ai_broker_write_authority": result.ai_broker_write_authority,
        "broker_adapter_mode": result.real_gate_evidence.broker_adapter_mode,
        "broker_endpoint_mode": result.real_gate_evidence.broker_endpoint_mode,
        "real_write_gates_evaluated": result.real_gate_evidence.real_write_gates_evaluated,
        "real_write_gates_passed": result.real_gate_evidence.real_write_gates_passed,
        "preflight_evidence_id": result.real_gate_evidence.preflight_evidence_id,
        "refusal_reasons": result.refusal_reasons,
        "incident_ids": (
            ()
            if result.first_session_evidence is None
            else result.first_session_evidence.incident_ids
        ),
        "evidence_package_id": (
            None
            if result.first_session_evidence is None
            else result.first_session_evidence.evidence_package_id
        ),
        "report_id": (
            None
            if result.first_session_evidence is None
            else result.first_session_evidence.report_id
        ),
        "note": result.note,
    }
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if result.success else 1


if __name__ == "__main__":
    raise SystemExit(main())
