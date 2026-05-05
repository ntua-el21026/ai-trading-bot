from __future__ import annotations

import asyncio

from apps.workers.app.activities.contracts import (
    ACTIVITY_FUNCTIONS,
    compare_reconciliation_snapshots,
    fetch_broker_reconciliation_snapshot,
    fetch_candidate_news,
    fetch_internal_ledger_snapshot,
    refresh_market_data,
    run_ai_trade_research,
    store_ai_research_payload,
    validate_ai_research_output,
)
from apps.workers.app.queries import QUERY_NAMES
from apps.workers.app.signals import SIGNAL_NAMES
from apps.workers.app.types import ActivityPlaceholderInput, ActivityPlaceholderResult
from apps.workers.app.workflows import WORKFLOW_CLASSES
from apps.workers.app.workflows.kill_switch import KillSwitchWorkflow


def test_required_workflow_skeletons_are_registered() -> None:
    workflow_names = {workflow.__name__ for workflow in WORKFLOW_CLASSES}

    assert workflow_names == {
        "DailyDataRefreshWorkflow",
        "EODSignalWorkflow",
        "AIShortlistResearchWorkflow",
        "DecisionWorkflow",
        "ExecutionIntentWorkflow",
        "OrderLifecycleWorkflow",
        "PositionLifecycleWorkflow",
        "ReconciliationWorkflow",
        "KillSwitchWorkflow",
        "ReportingWorkflow",
    }


def test_required_signal_and_query_contracts_are_present() -> None:
    assert set(SIGNAL_NAMES) == {
        "manual_kill_switch",
        "manual_pause_new_risk",
        "manual_resume_after_review",
        "force_reconciliation",
        "force_report",
        "approve_level_change",
        "acknowledge_incident",
    }
    assert set(QUERY_NAMES) == {
        "get_current_system_state",
        "get_active_workflows",
        "get_active_execution_intents",
        "get_open_order_lifecycles",
        "get_open_position_lifecycles",
        "get_recent_incidents",
        "get_last_reconciliation_status",
        "get_kill_switch_state",
    }


def test_activity_contracts_are_placeholders_without_external_calls() -> None:
    activity_names = {activity.__name__ for activity in ACTIVITY_FUNCTIONS}

    assert "refresh_market_data" in activity_names
    assert "submit_order_placeholder" in activity_names
    assert "fetch_candidate_news" in activity_names
    assert "run_ai_trade_research" in activity_names
    assert "validate_ai_research_output" in activity_names
    assert "store_ai_research_payload" in activity_names
    assert "fetch_broker_reconciliation_snapshot" in activity_names
    assert "fetch_internal_ledger_snapshot" in activity_names
    assert "compare_reconciliation_snapshots" in activity_names
    result = asyncio.run(
        refresh_market_data(
            ActivityPlaceholderInput(
                workflow_name="DailyDataRefreshWorkflow",
                purpose="contract-test",
            ),
        )
    )

    assert isinstance(result, ActivityPlaceholderResult)
    assert result.status == "placeholder"
    assert result.external_calls_performed is False
    assert result.details["external_calls"] == "none"


def test_reconciliation_activity_contracts_are_placeholders_without_external_calls() -> None:
    payload = ActivityPlaceholderInput(
        workflow_name="ReconciliationWorkflow",
        purpose="contract-test",
    )

    results = asyncio.run(_run_reconciliation_activity_placeholders(payload))

    assert [result.activity_name for result in results] == [
        "fetch_broker_reconciliation_snapshot",
        "fetch_internal_ledger_snapshot",
        "compare_reconciliation_snapshots",
    ]
    assert all(result.external_calls_performed is False for result in results)
    assert all(result.details["external_calls"] == "none" for result in results)


def test_ai_activity_contracts_are_placeholders_without_external_calls() -> None:
    payload = ActivityPlaceholderInput(
        workflow_name="AIShortlistResearchWorkflow",
        purpose="contract-test",
    )

    results = asyncio.run(_run_ai_activity_placeholders(payload))

    assert [result.activity_name for result in results] == [
        "fetch_candidate_news",
        "run_ai_trade_research",
        "validate_ai_research_output",
        "store_ai_research_payload",
    ]
    assert all(result.external_calls_performed is False for result in results)
    assert all(result.details["external_calls"] == "none" for result in results)


async def _run_ai_activity_placeholders(
    payload: ActivityPlaceholderInput,
) -> tuple[
    ActivityPlaceholderResult,
    ActivityPlaceholderResult,
    ActivityPlaceholderResult,
    ActivityPlaceholderResult,
]:
    news, research, validation, storage = await asyncio.gather(
        fetch_candidate_news(payload),
        run_ai_trade_research(payload),
        validate_ai_research_output(payload),
        store_ai_research_payload(payload),
    )
    return news, research, validation, storage


async def _run_reconciliation_activity_placeholders(
    payload: ActivityPlaceholderInput,
) -> tuple[ActivityPlaceholderResult, ActivityPlaceholderResult, ActivityPlaceholderResult]:
    broker_snapshot, internal_snapshot, comparison = await asyncio.gather(
        fetch_broker_reconciliation_snapshot(payload),
        fetch_internal_ledger_snapshot(payload),
        compare_reconciliation_snapshots(payload),
    )
    return broker_snapshot, internal_snapshot, comparison


def test_manual_kill_switch_uses_spec_defined_paused_state() -> None:
    workflow = KillSwitchWorkflow()

    workflow.manual_kill_switch("operator_requested")
    state = workflow.get_kill_switch_state()

    assert state.state == "PAUSED_NEW_RISK"
    assert state.new_risk_allowed is False
    assert state.risk_reducing_exits_allowed is True
