"""Side-effect activity placeholders for Temporal workflow skeletons.

These functions intentionally perform no broker, AI, news, database, alert, or network calls.
Future milestones should replace placeholders with real activity implementations behind the same
workflow boundary.
"""

from __future__ import annotations

from temporalio import activity

from apps.workers.app.types import ActivityPlaceholderInput, ActivityPlaceholderResult


def _placeholder_result(
    activity_name: str,
    payload: ActivityPlaceholderInput,
) -> ActivityPlaceholderResult:
    return ActivityPlaceholderResult(
        activity_name=activity_name,
        details={
            "workflow_name": payload.workflow_name,
            "purpose": payload.purpose,
            "external_calls": "none",
        },
    )


@activity.defn(name="record_workflow_checkpoint")
async def record_workflow_checkpoint(
    payload: ActivityPlaceholderInput,
) -> ActivityPlaceholderResult:
    return _placeholder_result("record_workflow_checkpoint", payload)


@activity.defn(name="refresh_market_data")
async def refresh_market_data(payload: ActivityPlaceholderInput) -> ActivityPlaceholderResult:
    return _placeholder_result("refresh_market_data", payload)


@activity.defn(name="build_eod_signals")
async def build_eod_signals(payload: ActivityPlaceholderInput) -> ActivityPlaceholderResult:
    return _placeholder_result("build_eod_signals", payload)


@activity.defn(name="research_ai_shortlist")
async def research_ai_shortlist(payload: ActivityPlaceholderInput) -> ActivityPlaceholderResult:
    return _placeholder_result("research_ai_shortlist", payload)


@activity.defn(name="build_trade_decisions")
async def build_trade_decisions(payload: ActivityPlaceholderInput) -> ActivityPlaceholderResult:
    return _placeholder_result("build_trade_decisions", payload)


@activity.defn(name="build_execution_intents")
async def build_execution_intents(payload: ActivityPlaceholderInput) -> ActivityPlaceholderResult:
    return _placeholder_result("build_execution_intents", payload)


@activity.defn(name="submit_order_placeholder")
async def submit_order_placeholder(payload: ActivityPlaceholderInput) -> ActivityPlaceholderResult:
    return _placeholder_result("submit_order_placeholder", payload)


@activity.defn(name="monitor_position_placeholder")
async def monitor_position_placeholder(
    payload: ActivityPlaceholderInput,
) -> ActivityPlaceholderResult:
    return _placeholder_result("monitor_position_placeholder", payload)


@activity.defn(name="reconcile_broker_state")
async def reconcile_broker_state(payload: ActivityPlaceholderInput) -> ActivityPlaceholderResult:
    return _placeholder_result("reconcile_broker_state", payload)


@activity.defn(name="fetch_broker_reconciliation_snapshot")
async def fetch_broker_reconciliation_snapshot(
    payload: ActivityPlaceholderInput,
) -> ActivityPlaceholderResult:
    return _placeholder_result("fetch_broker_reconciliation_snapshot", payload)


@activity.defn(name="fetch_internal_ledger_snapshot")
async def fetch_internal_ledger_snapshot(
    payload: ActivityPlaceholderInput,
) -> ActivityPlaceholderResult:
    return _placeholder_result("fetch_internal_ledger_snapshot", payload)


@activity.defn(name="compare_reconciliation_snapshots")
async def compare_reconciliation_snapshots(
    payload: ActivityPlaceholderInput,
) -> ActivityPlaceholderResult:
    return _placeholder_result("compare_reconciliation_snapshots", payload)


@activity.defn(name="apply_kill_switch_state")
async def apply_kill_switch_state(payload: ActivityPlaceholderInput) -> ActivityPlaceholderResult:
    return _placeholder_result("apply_kill_switch_state", payload)


@activity.defn(name="generate_report")
async def generate_report(payload: ActivityPlaceholderInput) -> ActivityPlaceholderResult:
    return _placeholder_result("generate_report", payload)


ACTIVITY_FUNCTIONS = (
    record_workflow_checkpoint,
    refresh_market_data,
    build_eod_signals,
    research_ai_shortlist,
    build_trade_decisions,
    build_execution_intents,
    submit_order_placeholder,
    monitor_position_placeholder,
    reconcile_broker_state,
    fetch_broker_reconciliation_snapshot,
    fetch_internal_ledger_snapshot,
    compare_reconciliation_snapshots,
    apply_kill_switch_state,
    generate_report,
)
