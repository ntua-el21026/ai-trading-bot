from __future__ import annotations

import asyncio
from pathlib import Path

from apps.workers.app.activities.contracts import (
    ACTIVITY_FUNCTIONS,
    compare_reconciliation_snapshots,
    fetch_broker_reconciliation_snapshot,
    fetch_candidate_news,
    fetch_internal_ledger_snapshot,
    run_ai_trade_research,
    store_ai_research_payload,
    validate_ai_research_output,
)
from apps.workers.app.activities.ledger import persist_data_refresh_result
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


def test_activity_contracts_include_ledger_boundaries_without_external_calls() -> None:
    activity_names = {activity.__name__ for activity in ACTIVITY_FUNCTIONS}

    assert "persist_data_refresh_result" in activity_names
    assert "persist_trade_candidates" in activity_names
    assert "persist_ai_research_outputs" in activity_names
    assert "persist_trade_decision" in activity_names
    assert "persist_execution_intent" in activity_names
    assert "persist_order_event" in activity_names
    assert "persist_position_snapshot" in activity_names
    assert "persist_broker_reconciliation" in activity_names
    assert "persist_system_event" in activity_names
    assert "persist_report" in activity_names
    assert "get_broker_account_snapshot" in activity_names
    assert "get_broker_orders_snapshot" in activity_names
    assert "get_broker_positions_snapshot" in activity_names
    assert "get_broker_fills_snapshot" in activity_names
    assert "lookup_broker_order_by_client_order_id" in activity_names
    assert "lookup_broker_order_by_broker_order_id" in activity_names
    assert "submit_paper_entry_order" in activity_names
    assert "cancel_paper_order" in activity_names
    assert "submit_paper_protective_stop" in activity_names
    assert "verify_paper_protective_stop" in activity_names
    assert "map_trade_update_event" in activity_names
    assert "generate_daily_report" in activity_names
    assert "generate_weekly_report" in activity_names
    assert "dispatch_alert" in activity_names
    assert "dispatch_incident_alert" in activity_names
    assert "dispatch_report_alert" in activity_names
    assert "build_dashboard_snapshot" in activity_names
    assert "fetch_candidate_news" in activity_names
    assert "fetch_shortlist_news" in activity_names
    assert "fetch_marketaux_news" in activity_names
    assert "fetch_alpha_vantage_news" in activity_names
    assert "run_ai_trade_research" in activity_names
    assert "run_openai_web_fallback" in activity_names
    assert "validate_ai_research_output" in activity_names
    assert "store_ai_research_payload" in activity_names
    assert "persist_news_payloads" in activity_names
    assert "persist_ai_research_output" in activity_names
    assert "generate_ai_calibration_report" in activity_names
    assert "fetch_broker_reconciliation_snapshot" in activity_names
    assert "fetch_internal_ledger_snapshot" in activity_names
    assert "compare_reconciliation_snapshots" in activity_names
    result = asyncio.run(
        persist_data_refresh_result(
            ActivityPlaceholderInput(
                workflow_name="DailyDataRefreshWorkflow",
                purpose="contract-test",
            ),
        )
    )

    assert isinstance(result, ActivityPlaceholderResult)
    assert result.status == "ledger_checkpoint"
    assert result.external_calls_performed is False
    assert result.details["external_calls"] == "none"


def test_workflow_skeletons_call_ledger_activity_boundaries() -> None:
    expected_activity_by_file = {
        "daily_data_refresh.py": "persist_data_refresh_result",
        "eod_signal.py": "persist_trade_candidates",
        "ai_shortlist_research.py": "persist_ai_research_outputs",
        "decision.py": "persist_trade_decision",
        "execution_intent.py": "persist_execution_intent",
        "order_lifecycle.py": "persist_order_event",
        "position_lifecycle.py": "persist_position_snapshot",
        "reconciliation.py": "persist_broker_reconciliation",
        "kill_switch.py": "persist_system_event",
        "reporting.py": "generate_daily_report",
    }
    workflow_dir = Path("apps/workers/app/workflows")

    for filename, activity_name in expected_activity_by_file.items():
        source = (workflow_dir / filename).read_text(encoding="utf-8")
        assert f'activity_name="{activity_name}"' in source


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


def test_workflow_modules_do_not_directly_import_side_effect_providers() -> None:
    workflow_dir = Path("apps/workers/app/workflows")
    prohibited_tokens = (
        "packages.broker",
        "packages.ai",
        "requests",
        "httpx",
        "openai",
        "anthropic",
        "alpaca.",
        "AlpacaClient",
        "alpaca_trade_api",
        "alpaca.trading",
        "packages.ledger",
        "packages.alerting",
        "telegram",
        "sqlite3",
        "DATABASE_URL",
        "os.environ",
        "datetime.now",
        "random.",
    )

    violations: list[str] = []
    for path in sorted(workflow_dir.glob("*.py")):
        source = path.read_text(encoding="utf-8")
        for token in prohibited_tokens:
            if token in source:
                violations.append(f"{path}:{token}")

    assert violations == []
