"""Run one supervised paper-only scheduled workflow equivalent for M42."""

from __future__ import annotations

import argparse
import json

from packages.paper import (
    M42_SUPERVISED_SCHEDULED_PAPER_RUN_EVIDENCE_PATH,
    MILESTONE_42_REAL_OPERATOR_APPROVAL,
    SupervisedScheduledPaperRunRequest,
    load_preflight_environment,
    run_supervised_scheduled_paper_once,
    write_supervised_scheduled_paper_run_artifact,
)

WARNING = (
    "Milestone 42 supervised scheduled paper run. This command may run exactly one "
    "temporary supervised paper-only workflow equivalent after all gates pass, and it "
    "must leave no recurring schedule active."
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run one supervised scheduled paper run and write sanitized evidence.",
    )
    parser.add_argument("--mode", choices=("real-paper", "fake"), default="real-paper")
    parser.add_argument("--scenario", default="happy_path")
    parser.add_argument("--operator-approval", default=None)
    parser.add_argument("--primary-target-symbol", default="XLK")
    parser.add_argument("--primary-max-qty", type=int, default=1)
    parser.add_argument("--primary-max-notional", type=float, default=300.0)
    parser.add_argument("--primary-limit-price", type=float, default=300.0)
    parser.add_argument("--fallback-target-symbol", default="XLF")
    parser.add_argument("--fallback-max-qty", type=int, default=1)
    parser.add_argument("--fallback-max-notional", type=float, default=100.0)
    parser.add_argument("--fallback-limit-price", type=float, default=100.0)
    parser.add_argument(
        "--m41-readiness-packet",
        default="docs/evidence/supervised_scheduled_paper_readiness_m41.json",
    )
    parser.add_argument(
        "--output",
        default=M42_SUPERVISED_SCHEDULED_PAPER_RUN_EVIDENCE_PATH,
        help="Sanitized M42 evidence packet path.",
    )
    parser.add_argument("--confirm-paper-endpoint", action="store_true")
    parser.add_argument("--confirm-temporary-supervised-schedule-only", action="store_true")
    parser.add_argument("--confirm-disable-after-one-run", action="store_true")
    parser.add_argument("--confirm-no-live-trading", action="store_true")
    parser.add_argument("--confirm-no-autonomous-live", action="store_true")
    parser.add_argument("--confirm-no-unattended-operation", action="store_true")
    parser.add_argument("--confirm-no-leverage", action="store_true")
    parser.add_argument("--confirm-protective-stop-required", action="store_true")
    parser.add_argument("--confirm-cleanup-policy", action="store_true")
    args = parser.parse_args(argv)

    print(WARNING)
    request = SupervisedScheduledPaperRunRequest(
        mode=args.mode,
        operator_approval_marker=args.operator_approval,
        primary_target_symbol=args.primary_target_symbol.upper(),
        primary_max_quantity=args.primary_max_qty,
        primary_max_notional_usd=args.primary_max_notional,
        primary_limit_price=args.primary_limit_price,
        fallback_target_symbol=args.fallback_target_symbol.upper(),
        fallback_max_quantity=args.fallback_max_qty,
        fallback_max_notional_usd=args.fallback_max_notional,
        fallback_limit_price=args.fallback_limit_price,
        execution_scenario_id=args.scenario,
        m41_readiness_packet_path=args.m41_readiness_packet,
        confirm_paper_endpoint=args.confirm_paper_endpoint,
        confirm_temporary_supervised_schedule_only=(
            args.confirm_temporary_supervised_schedule_only
        ),
        confirm_disable_after_one_run=args.confirm_disable_after_one_run,
        confirm_no_live_trading=args.confirm_no_live_trading,
        confirm_no_autonomous_live=args.confirm_no_autonomous_live,
        confirm_no_unattended_operation=args.confirm_no_unattended_operation,
        confirm_no_leverage=args.confirm_no_leverage,
        confirm_protective_stop_required=args.confirm_protective_stop_required,
        confirm_cleanup_policy=args.confirm_cleanup_policy,
    )
    result = run_supervised_scheduled_paper_once(
        request,
        environ=load_preflight_environment() if args.mode == "real-paper" else {},
    )
    written_path = write_supervised_scheduled_paper_run_artifact(result, args.output)
    packet = result.packet
    post_state = packet.post_run_broker_state
    summary = {
        "mode": result.mode,
        "status": result.status,
        "success": result.success,
        "refused": result.refused,
        "unsafe": result.unsafe,
        "blockers": result.blockers,
        "selected_target_symbol": packet.selected_target_symbol,
        "no_go_reason": packet.no_go_reason,
        "entry_order_status": packet.entry_order_status,
        "fill_status": packet.fill_status,
        "protective_stop_verification_result": packet.protective_stop_verification_result,
        "normal_stop_path_succeeded": packet.normal_stop_path_succeeded,
        "recovery_stop_path_used": packet.recovery_stop_path_used,
        "final_reconciliation": packet.final_reconciliation,
        "post_run_open_orders_total": None if post_state is None else post_state.open_orders_total,
        "post_run_positions_total": None if post_state is None else post_state.positions_total,
        "broker_writes_performed": result.broker_writes_performed,
        "real_read_only_calls_performed": result.real_read_only_calls_performed,
        "schedule_workflow_created_or_activated": (
            result.schedule_workflow_created_or_activated
        ),
        "schedule_workflow_remains_active": result.schedule_workflow_remains_active,
        "schedule_workflow_creation_status": packet.schedule_workflow_creation_status,
        "schedule_workflow_activation_status": packet.schedule_workflow_activation_status,
        "schedule_workflow_run_status": packet.schedule_workflow_run_status,
        "schedule_workflow_deactivation_status": packet.schedule_workflow_deactivation_status,
        "schedules_activated_final_state": packet.schedules_activated_final_state,
        "frozen_validation_started": result.frozen_validation_started,
        "level4_ready": result.level4_ready,
        "live_trading_enabled": result.live_trading_enabled,
        "autonomous_live_execution_enabled": result.autonomous_live_execution_enabled,
        "unattended_operation_enabled": result.unattended_operation_enabled,
        "leverage_enabled": result.leverage_enabled,
        "ai_broker_write_authority": result.ai_broker_write_authority,
        "freeze_readiness_recommendation": packet.freeze_readiness_recommendation,
        "m42_packet_path": str(written_path),
        "approval_marker_expected": MILESTONE_42_REAL_OPERATOR_APPROVAL,
    }
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if result.success else 1


if __name__ == "__main__":
    raise SystemExit(main())

