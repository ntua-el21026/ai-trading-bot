"""Run the gated first controlled paper-session paths."""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from typing import cast

from packages.paper import (
    FIRST_PAPER_SESSION_SCENARIO_IDS,
    M34_RESULT_EVIDENCE_PATH,
    M39_CLEAN_CONTROLLED_SESSION_EVIDENCE_PATH,
    M40_READ_ONLY_PREFLIGHT_EVIDENCE_PATH,
    M40_REPEATED_CONTROLLED_BATCH_EVIDENCE_PATH,
    MILESTONE_30_FAKE_OPERATOR_APPROVAL,
    MILESTONE_34_FAKE_OPERATOR_APPROVAL,
    MILESTONE_34_REAL_OPERATOR_APPROVAL,
    MILESTONE_35_REAL_OPERATOR_APPROVAL,
    MILESTONE_35B_REAL_OPERATOR_APPROVAL,
    MILESTONE_35C_REAL_OPERATOR_APPROVAL,
    MILESTONE_39_REAL_OPERATOR_APPROVAL,
    MILESTONE_40_REAL_OPERATOR_APPROVAL,
    REAL_SESSION_SCENARIO_IDS,
    FirstPaperSessionMode,
    audit_first_session_symbol_universe,
    default_first_paper_session_execution_request,
    default_real_session_gate_config,
    load_preflight_environment,
    run_first_controlled_paper_session_execution,
    run_real_first_controlled_paper_session_gate,
    write_clean_controlled_session_m39_artifact,
    write_first_controlled_paper_session_result_artifact,
    write_repeated_controlled_batch_m40_artifact,
)

WARNING = (
    "First controlled paper-session command. Real Alpaca paper writes are allowed only in "
    "explicitly approved real-paper milestones after every explicit gate passes."
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run the first controlled paper-session real-gate wiring path.",
    )
    parser.add_argument(
        "--mode",
        choices=(
            "real-gated",
            "fake",
            "real-paper",
            "fake-real-paper",
            "audit-symbol-universe",
        ),
        default="real-gated",
        help="Default real-gated mode refuses. Real-paper milestones require explicit gates.",
    )
    parser.add_argument(
        "--scenario",
        choices=tuple(
            dict.fromkeys((*REAL_SESSION_SCENARIO_IDS, *FIRST_PAPER_SESSION_SCENARIO_IDS))
        ),
        default="happy_path",
        help="Real-gate, M34 real-paper, or fake/stub scenario ID.",
    )
    parser.add_argument(
        "--operator-approval",
        default=None,
        help=(
            "Operator approval marker. For fake/stub success use "
            f"{MILESTONE_30_FAKE_OPERATOR_APPROVAL}; for M34 fake-real-paper use "
            f"{MILESTONE_34_FAKE_OPERATOR_APPROVAL}; for M34 real-paper use "
            f"{MILESTONE_34_REAL_OPERATOR_APPROVAL}; for M35 real-paper use "
            f"{MILESTONE_35_REAL_OPERATOR_APPROVAL}; for M35B real-paper use "
            f"{MILESTONE_35B_REAL_OPERATOR_APPROVAL}; for M35C real-paper use "
            f"{MILESTONE_35C_REAL_OPERATOR_APPROVAL}; for M39 real-paper use "
            f"{MILESTONE_39_REAL_OPERATOR_APPROVAL}; for M40 real-paper use "
            f"{MILESTONE_40_REAL_OPERATOR_APPROVAL}. Do not pass secrets."
        ),
    )
    parser.add_argument("--target-symbol", default=None)
    parser.add_argument("--max-qty", type=int, default=None)
    parser.add_argument("--max-notional", type=float, default=None)
    parser.add_argument("--limit-price", type=float, default=None)
    parser.add_argument("--confirm-paper-endpoint", action="store_true")
    parser.add_argument("--confirm-real-paper-writes", action="store_true")
    parser.add_argument("--confirm-no-live-trading", action="store_true")
    parser.add_argument("--confirm-no-autonomous-live", action="store_true")
    parser.add_argument("--confirm-no-schedules", action="store_true")
    parser.add_argument("--confirm-no-leverage", action="store_true")
    parser.add_argument("--confirm-first-session-only", action="store_true")
    parser.add_argument("--confirm-protective-stop-required", action="store_true")
    parser.add_argument("--confirm-cleanup-policy", action="store_true")
    parser.add_argument(
        "--result-output",
        default=None,
        help="Optional sanitized result packet path. Real-paper defaults to docs/evidence.",
    )
    args = parser.parse_args(argv)

    print(WARNING)
    if args.mode == "audit-symbol-universe":
        audit = audit_first_session_symbol_universe()
        summary = {
            "mode": args.mode,
            "success": audit.success,
            "allowed_symbols": audit.allowed_symbols,
            "first_session_max_quantity": audit.first_session_max_quantity,
            "first_session_absolute_max_notional_usd": (
                audit.first_session_absolute_max_notional_usd
            ),
            "accepted_symbols": [
                record.symbol
                for record in audit.records
                if record.accepted_by_first_session_envelope_logic
            ],
            "rejected_symbols": [
                {
                    "symbol": record.symbol,
                    "reason_codes": record.reason_codes,
                }
                for record in audit.records
                if not record.accepted_by_first_session_envelope_logic
            ],
            "actual_paper_trading_started": audit.actual_paper_trading_started,
            "real_broker_writes_attempted": audit.real_broker_writes_attempted,
            "external_calls_attempted": audit.external_calls_attempted,
            "schedules_activated": audit.schedules_activated,
            "live_trading_enabled": audit.live_trading_enabled,
            "autonomous_live_execution_enabled": audit.autonomous_live_execution_enabled,
            "leverage_enabled": audit.leverage_enabled,
            "level4_ready": audit.level4_ready,
        }
        print(json.dumps(summary, indent=2, sort_keys=True))
        return 0 if audit.success else 1

    if args.mode in {"real-paper", "fake-real-paper"}:
        execution_mode = cast(FirstPaperSessionMode, args.mode)
        execution_request = default_first_paper_session_execution_request(
            args.scenario,
            mode=execution_mode,
            operator_approval_marker=args.operator_approval,
            target_symbol=None if args.target_symbol is None else args.target_symbol.upper(),
            max_quantity=args.max_qty,
            max_notional_usd=args.max_notional,
            limit_price=args.limit_price,
            confirm_paper_endpoint=(
                True if execution_mode == "fake-real-paper" else args.confirm_paper_endpoint
            ),
            confirm_real_paper_writes=(
                True if execution_mode == "fake-real-paper" else args.confirm_real_paper_writes
            ),
            confirm_no_live_trading=(
                True if execution_mode == "fake-real-paper" else args.confirm_no_live_trading
            ),
            confirm_no_autonomous_live=(
                True if execution_mode == "fake-real-paper" else args.confirm_no_autonomous_live
            ),
            confirm_no_schedules=(
                True if execution_mode == "fake-real-paper" else args.confirm_no_schedules
            ),
            confirm_no_leverage=(
                True if execution_mode == "fake-real-paper" else args.confirm_no_leverage
            ),
            confirm_first_session_only=(
                True if execution_mode == "fake-real-paper" else args.confirm_first_session_only
            ),
            confirm_protective_stop_required=(
                True
                if execution_mode == "fake-real-paper"
                else args.confirm_protective_stop_required
            ),
            confirm_cleanup_policy=(
                True if execution_mode == "fake-real-paper" else args.confirm_cleanup_policy
            ),
        )
        if execution_mode == "real-paper":
            updates: dict[str, object] = {"started_at": datetime.now(UTC)}
            if args.operator_approval == MILESTONE_40_REAL_OPERATOR_APPROVAL:
                updates["launch_packet_path"] = M40_READ_ONLY_PREFLIGHT_EVIDENCE_PATH
            execution_request = execution_request.model_copy(update=updates)
        execution_result = run_first_controlled_paper_session_execution(
            execution_request,
            environ=(
                load_preflight_environment()
                if execution_mode == "real-paper"
                else {}
            ),
        )
        result_path = args.result_output
        if result_path is None and execution_mode == "real-paper":
            result_path = (
                M40_REPEATED_CONTROLLED_BATCH_EVIDENCE_PATH
                if args.operator_approval == MILESTONE_40_REAL_OPERATOR_APPROVAL
                else M39_CLEAN_CONTROLLED_SESSION_EVIDENCE_PATH
                if args.operator_approval == MILESTONE_39_REAL_OPERATOR_APPROVAL
                else M34_RESULT_EVIDENCE_PATH
            )
        written_path = None
        if result_path:
            if args.operator_approval == MILESTONE_40_REAL_OPERATOR_APPROVAL:
                written_path = str(
                    write_repeated_controlled_batch_m40_artifact(
                        execution_result,
                        result_path,
                    )
                )
            elif args.operator_approval == MILESTONE_39_REAL_OPERATOR_APPROVAL:
                written_path = str(
                    write_clean_controlled_session_m39_artifact(
                        execution_result,
                        result_path,
                    )
                )
            else:
                written_path = str(
                    write_first_controlled_paper_session_result_artifact(
                        execution_result,
                        result_path,
                    )
                )
        packet = execution_result.result_packet
        post_state = packet.post_run_broker_state
        summary = {
            "scenario_id": execution_result.scenario_id,
            "mode": execution_result.mode,
            "status": execution_result.status,
            "success": execution_result.success,
            "refused": execution_result.refused,
            "unsafe": execution_result.unsafe,
            "blockers": execution_result.blockers,
            "target_symbol": packet.target_symbol,
            "max_qty": packet.order_envelope.max_quantity,
            "max_notional": packet.order_envelope.max_notional_usd,
            "limit_price": packet.order_envelope.limit_price,
            "estimated_entry_notional_usd": packet.estimated_entry_notional_usd,
            "first_session_absolute_max_notional_usd": (
                packet.first_session_absolute_max_notional_usd
            ),
            "order_envelope_validation_result": (
                packet.order_envelope_validation_result
            ),
            "order_envelope_rejection_reasons": (
                packet.order_envelope_rejection_reasons
            ),
            "symbol_allowlist_decision": packet.symbol_allowlist_decision,
            "entry_order_status": packet.entry_order_status,
            "fill_status": packet.fill_status,
            "filled_quantity": packet.filled_quantity,
            "protective_stop_verification_result": (
                packet.protective_stop_verification_result
            ),
            "normal_stop_path_succeeded": packet.normal_stop_path_succeeded,
            "recovery_stop_path_used": packet.recovery_stop_path_used,
            "cleanup_actions": packet.cleanup_actions,
            "post_run_open_order_count": (
                None if post_state is None else post_state.open_order_count
            ),
            "post_run_position_count": (
                None if post_state is None else post_state.position_count
            ),
            "post_run_target_symbol_position_quantity": (
                None if post_state is None else post_state.target_symbol_position_quantity
            ),
            "post_run_reconciliation_result": packet.post_run_reconciliation_result,
            "actual_paper_trading_started": execution_result.actual_paper_trading_started,
            "real_broker_orders_submitted": execution_result.real_broker_orders_submitted,
            "real_broker_writes_attempted": execution_result.real_broker_writes_attempted,
            "real_read_only_alpaca_calls_performed": (
                execution_result.real_read_only_alpaca_calls_performed
            ),
            "provider_ai_telegram_vercel_temporal_calls": (
                execution_result.provider_ai_telegram_vercel_temporal_calls
            ),
            "schedules_activated": execution_result.schedules_activated,
            "live_trading_enabled": execution_result.live_trading_enabled,
            "autonomous_live_execution_enabled": (
                execution_result.autonomous_live_execution_enabled
            ),
            "leverage_enabled": execution_result.leverage_enabled,
            "ai_broker_write_authority": execution_result.ai_broker_write_authority,
            "level4_ready": execution_result.level4_ready,
            "post_session_go_no_go": execution_result.post_session_go_no_go,
            "result_packet_id": packet.result_packet_id,
            "result_packet_path": written_path,
            "note": execution_result.note,
        }
        print(json.dumps(summary, indent=2, sort_keys=True))
        return 0 if execution_result.success else 1

    gate_config = default_real_session_gate_config(
        args.scenario,
        mode=args.mode,
        operator_approval_marker=args.operator_approval,
    )
    gate_result = run_real_first_controlled_paper_session_gate(gate_config)
    summary = {
        "scenario_id": gate_result.scenario_id,
        "mode": gate_result.mode,
        "success": gate_result.success,
        "refused": gate_result.refused,
        "unsafe": gate_result.unsafe,
        "ready_for_future_real_execution": gate_result.ready_for_future_real_execution,
        "actual_paper_trading_started": gate_result.actual_paper_trading_started,
        "real_broker_orders_submitted": gate_result.real_broker_orders_submitted,
        "real_broker_writes_attempted": gate_result.real_broker_writes_attempted,
        "external_calls_attempted": gate_result.external_calls_attempted,
        "schedules_activated": gate_result.schedules_activated,
        "live_trading_enabled": gate_result.live_trading_enabled,
        "autonomous_live_execution_enabled": gate_result.autonomous_live_execution_enabled,
        "level4_ready": gate_result.level4_ready,
        "leverage_enabled": gate_result.leverage_enabled,
        "ai_broker_write_authority": gate_result.ai_broker_write_authority,
        "broker_adapter_mode": gate_result.real_gate_evidence.broker_adapter_mode,
        "broker_endpoint_mode": gate_result.real_gate_evidence.broker_endpoint_mode,
        "real_write_gates_evaluated": (
            gate_result.real_gate_evidence.real_write_gates_evaluated
        ),
        "real_write_gates_passed": gate_result.real_gate_evidence.real_write_gates_passed,
        "preflight_evidence_id": gate_result.real_gate_evidence.preflight_evidence_id,
        "refusal_reasons": gate_result.refusal_reasons,
        "incident_ids": (
            ()
            if gate_result.first_session_evidence is None
            else gate_result.first_session_evidence.incident_ids
        ),
        "evidence_package_id": (
            None
            if gate_result.first_session_evidence is None
            else gate_result.first_session_evidence.evidence_package_id
        ),
        "report_id": (
            None
            if gate_result.first_session_evidence is None
            else gate_result.first_session_evidence.report_id
        ),
        "note": gate_result.note,
    }
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if gate_result.success else 1


if __name__ == "__main__":
    raise SystemExit(main())
