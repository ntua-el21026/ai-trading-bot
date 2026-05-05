from __future__ import annotations

import asyncio

from apps.workers.app.activities.contracts import ACTIVITY_FUNCTIONS, refresh_market_data
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


def test_manual_kill_switch_uses_spec_defined_paused_state() -> None:
    workflow = KillSwitchWorkflow()

    workflow.manual_kill_switch("operator_requested")
    state = workflow.get_kill_switch_state()

    assert state.state == "PAUSED_NEW_RISK"
    assert state.new_risk_allowed is False
    assert state.risk_reducing_exits_allowed is True
