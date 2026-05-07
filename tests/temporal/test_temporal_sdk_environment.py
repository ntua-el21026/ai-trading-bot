from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

import pytest
from temporalio import activity
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Replayer, Worker

from apps.workers.app.activities.contracts import ACTIVITY_FUNCTIONS
from apps.workers.app.queries import (
    GET_CURRENT_SYSTEM_STATE,
    GET_KILL_SWITCH_STATE,
    GET_LAST_RECONCILIATION_STATUS,
)
from apps.workers.app.signals import (
    ACKNOWLEDGE_INCIDENT,
    FORCE_RECONCILIATION,
    FORCE_REPORT,
    MANUAL_KILL_SWITCH,
    MANUAL_PAUSE_NEW_RISK,
    MANUAL_RESUME_AFTER_REVIEW,
)
from apps.workers.app.types import (
    ActivityPlaceholderInput,
    ActivityPlaceholderResult,
    KillSwitchState,
    WorkflowRunInput,
    WorkflowStatus,
)
from apps.workers.app.worker import build_worker, task_queue_names, workflow_classes_by_task_queue
from apps.workers.app.workflows.ai_shortlist_research import AIShortlistResearchWorkflow
from apps.workers.app.workflows.daily_data_refresh import DailyDataRefreshWorkflow
from apps.workers.app.workflows.decision import DecisionWorkflow
from apps.workers.app.workflows.eod_signal import EODSignalWorkflow
from apps.workers.app.workflows.execution_intent import ExecutionIntentWorkflow
from apps.workers.app.workflows.kill_switch import KillSwitchWorkflow
from apps.workers.app.workflows.order_lifecycle import OrderLifecycleWorkflow
from apps.workers.app.workflows.position_lifecycle import PositionLifecycleWorkflow
from apps.workers.app.workflows.reconciliation import ReconciliationWorkflow
from apps.workers.app.workflows.reporting import ReportingWorkflow

WorkflowRun = Callable[[Any, WorkflowRunInput], Awaitable[WorkflowStatus]]


@dataclass(frozen=True)
class WorkflowExecutionSpec:
    workflow_class: type
    run_method: WorkflowRun
    task_queue: str
    expected_activity: str


WORKFLOW_EXECUTION_SPECS = (
    WorkflowExecutionSpec(
        DailyDataRefreshWorkflow,
        DailyDataRefreshWorkflow.run,
        "market-data-task-queue",
        "persist_data_refresh_result",
    ),
    WorkflowExecutionSpec(
        EODSignalWorkflow,
        EODSignalWorkflow.run,
        "strategy-task-queue",
        "persist_trade_candidates",
    ),
    WorkflowExecutionSpec(
        DecisionWorkflow,
        DecisionWorkflow.run,
        "strategy-task-queue",
        "persist_trade_decision",
    ),
    WorkflowExecutionSpec(
        AIShortlistResearchWorkflow,
        AIShortlistResearchWorkflow.run,
        "ai-research-task-queue",
        "persist_ai_research_outputs",
    ),
    WorkflowExecutionSpec(
        ExecutionIntentWorkflow,
        ExecutionIntentWorkflow.run,
        "execution-task-queue",
        "persist_execution_intent",
    ),
    WorkflowExecutionSpec(
        OrderLifecycleWorkflow,
        OrderLifecycleWorkflow.run,
        "execution-task-queue",
        "persist_order_event",
    ),
    WorkflowExecutionSpec(
        PositionLifecycleWorkflow,
        PositionLifecycleWorkflow.run,
        "execution-task-queue",
        "persist_position_snapshot",
    ),
    WorkflowExecutionSpec(
        KillSwitchWorkflow,
        KillSwitchWorkflow.run,
        "execution-task-queue",
        "persist_system_event",
    ),
    WorkflowExecutionSpec(
        ReconciliationWorkflow,
        ReconciliationWorkflow.run,
        "reconciliation-task-queue",
        "persist_broker_reconciliation",
    ),
    WorkflowExecutionSpec(
        ReportingWorkflow,
        ReportingWorkflow.run,
        "reporting-task-queue",
        "generate_daily_report",
    ),
)


def test_temporal_sdk_environment_executes_registered_workflow_skeletons() -> None:
    asyncio.run(_execute_registered_workflow_skeletons())


def test_temporal_sdk_environment_handles_signals_and_queries() -> None:
    asyncio.run(_exercise_signals_and_queries())


def test_temporal_replayer_replays_test_environment_history() -> None:
    asyncio.run(_replay_kill_switch_history())


def test_worker_registration_matches_configured_task_queues() -> None:
    assert task_queue_names() == (
        "market-data-task-queue",
        "strategy-task-queue",
        "ai-research-task-queue",
        "execution-task-queue",
        "reconciliation-task-queue",
        "reporting-task-queue",
    )

    mapping = workflow_classes_by_task_queue()

    assert mapping["market-data-task-queue"] == (DailyDataRefreshWorkflow,)
    assert mapping["strategy-task-queue"] == (EODSignalWorkflow, DecisionWorkflow)
    assert mapping["ai-research-task-queue"] == (AIShortlistResearchWorkflow,)
    assert mapping["execution-task-queue"] == (
        ExecutionIntentWorkflow,
        OrderLifecycleWorkflow,
        PositionLifecycleWorkflow,
        KillSwitchWorkflow,
    )
    assert mapping["reconciliation-task-queue"] == (ReconciliationWorkflow,)
    assert mapping["reporting-task-queue"] == (ReportingWorkflow,)


async def _execute_registered_workflow_skeletons() -> None:
    async with await _start_temporal_test_environment() as env:
        for task_queue in task_queue_names():
            async with build_worker(env.client, task_queue=task_queue):
                for spec in _specs_for_task_queue(task_queue):
                    result = await env.client.execute_workflow(
                        spec.run_method,
                        WorkflowRunInput(reason="milestone-19-sdk-test"),
                        id=f"milestone-19-{spec.workflow_class.__name__}",
                        task_queue=task_queue,
                    )

                    assert result.workflow_name == spec.workflow_class.__name__
                    assert result.status == "completed"
                    assert result.details["activity"] == spec.expected_activity
                    assert result.details["external_calls_performed"] == "false"


async def _exercise_signals_and_queries() -> None:
    async with await _start_temporal_test_environment() as env:
        await _exercise_kill_switch_signals(env)
        await _exercise_reconciliation_signal(env)
        await _exercise_reporting_signal(env)


async def _exercise_kill_switch_signals(env: WorkflowEnvironment) -> None:
    release_activity = asyncio.Event()
    delayed_activity = _delayed_placeholder_activity("persist_system_event", release_activity)

    async with Worker(
        env.client,
        task_queue="execution-task-queue",
        workflows=[KillSwitchWorkflow],
        activities=[delayed_activity],
    ):
        handle = await env.client.start_workflow(
            KillSwitchWorkflow.run,
            WorkflowRunInput(reason="signal-query-test"),
            id="milestone-19-kill-switch-signal-query",
            task_queue="execution-task-queue",
        )

        await handle.signal(MANUAL_KILL_SWITCH, "operator_requested")
        kill_state = _kill_switch_state(await handle.query(GET_KILL_SWITCH_STATE))
        assert kill_state.state == "PAUSED_NEW_RISK"
        assert kill_state.new_risk_allowed is False

        await handle.signal(MANUAL_PAUSE_NEW_RISK, "risk_review")
        kill_state = _kill_switch_state(await handle.query(GET_KILL_SWITCH_STATE))
        assert kill_state.reason == "risk_review"

        await handle.signal(MANUAL_RESUME_AFTER_REVIEW, "review_complete")
        kill_state = _kill_switch_state(await handle.query(GET_KILL_SWITCH_STATE))
        assert kill_state.state == "RUNNING"
        assert kill_state.new_risk_allowed is True

        await handle.signal(FORCE_RECONCILIATION, "operator_requested")
        status = _workflow_status(await handle.query(GET_CURRENT_SYSTEM_STATE))
        assert status.status == "force_reconciliation_requested"

        await handle.signal(FORCE_REPORT, "operator_requested")
        status = _workflow_status(await handle.query(GET_CURRENT_SYSTEM_STATE))
        assert status.status == "force_report_requested"

        await handle.signal(ACKNOWLEDGE_INCIDENT, "incident-001")
        status = _workflow_status(await handle.query(GET_CURRENT_SYSTEM_STATE))
        assert status.status == "incident_acknowledged"
        assert status.details["incident_id"] == "incident-001"

        release_activity.set()
        result = await handle.result()
        assert result.status == "completed"


async def _exercise_reconciliation_signal(env: WorkflowEnvironment) -> None:
    release_activity = asyncio.Event()
    delayed_activity = _delayed_placeholder_activity(
        "persist_broker_reconciliation",
        release_activity,
    )

    async with Worker(
        env.client,
        task_queue="reconciliation-task-queue",
        workflows=[ReconciliationWorkflow],
        activities=[delayed_activity],
    ):
        handle = await env.client.start_workflow(
            ReconciliationWorkflow.run,
            WorkflowRunInput(reason="signal-query-test"),
            id="milestone-19-reconciliation-signal-query",
            task_queue="reconciliation-task-queue",
        )

        await handle.signal(FORCE_RECONCILIATION, "operator_requested")
        status = _workflow_status(await handle.query(GET_LAST_RECONCILIATION_STATUS))
        assert status.status == "force_requested"

        release_activity.set()
        result = await handle.result()
        assert result.status == "completed"


async def _exercise_reporting_signal(env: WorkflowEnvironment) -> None:
    release_activity = asyncio.Event()
    delayed_activity = _delayed_placeholder_activity("generate_daily_report", release_activity)

    async with Worker(
        env.client,
        task_queue="reporting-task-queue",
        workflows=[ReportingWorkflow],
        activities=[delayed_activity],
    ):
        handle = await env.client.start_workflow(
            ReportingWorkflow.run,
            WorkflowRunInput(reason="signal-query-test"),
            id="milestone-19-reporting-signal-query",
            task_queue="reporting-task-queue",
        )

        await handle.signal(FORCE_REPORT, "operator_requested")
        status = _workflow_status(await handle.query(GET_CURRENT_SYSTEM_STATE))
        assert status.status == "force_requested"

        release_activity.set()
        result = await handle.result()
        assert result.status == "completed"


async def _replay_kill_switch_history() -> None:
    async with await _start_temporal_test_environment() as env:
        async with Worker(
            env.client,
            task_queue="execution-task-queue",
            workflows=[KillSwitchWorkflow],
            activities=list(ACTIVITY_FUNCTIONS),
        ):
            handle = await env.client.start_workflow(
                KillSwitchWorkflow.run,
                WorkflowRunInput(reason="replay-test"),
                id="milestone-19-kill-switch-replay",
                task_queue="execution-task-queue",
            )
            result = await handle.result()
            assert result.status == "completed"
            history = await handle.fetch_history()

    replay_result = await Replayer(workflows=[KillSwitchWorkflow]).replay_workflow(history)

    assert replay_result.replay_failure is None


async def _start_temporal_test_environment() -> WorkflowEnvironment:
    try:
        return await WorkflowEnvironment.start_time_skipping()
    except (OSError, RuntimeError) as exc:
        pytest.skip(f"Temporal SDK test server is unavailable: {exc}")


def _specs_for_task_queue(task_queue: str) -> tuple[WorkflowExecutionSpec, ...]:
    return tuple(spec for spec in WORKFLOW_EXECUTION_SPECS if spec.task_queue == task_queue)


def _workflow_status(value: WorkflowStatus | dict[str, Any]) -> WorkflowStatus:
    if isinstance(value, WorkflowStatus):
        return value
    return WorkflowStatus(
        workflow_name=str(value["workflow_name"]),
        status=str(value["status"]),
        details={str(key): str(item) for key, item in dict(value.get("details", {})).items()},
    )


def _kill_switch_state(value: KillSwitchState | dict[str, Any]) -> KillSwitchState:
    if isinstance(value, KillSwitchState):
        return value
    return KillSwitchState(**value)


def _delayed_placeholder_activity(
    activity_name: str,
    release_activity: asyncio.Event,
) -> Callable[[ActivityPlaceholderInput], Awaitable[ActivityPlaceholderResult]]:
    @activity.defn(name=activity_name)
    async def delayed_activity(payload: ActivityPlaceholderInput) -> ActivityPlaceholderResult:
        await release_activity.wait()
        return ActivityPlaceholderResult(
            activity_name=activity_name,
            status="fake_activity_completed",
            external_calls_performed=False,
            details={
                "workflow_name": payload.workflow_name,
                "purpose": payload.purpose,
                "external_calls": "none",
            },
        )

    return delayed_activity
