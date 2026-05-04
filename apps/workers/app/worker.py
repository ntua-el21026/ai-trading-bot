"""Temporal worker bootstrap and task-queue registry."""

from __future__ import annotations

import asyncio

from temporalio.client import Client
from temporalio.worker import Worker

from apps.workers.app.activities.contracts import ACTIVITY_FUNCTIONS
from apps.workers.app.temporal_client import connect_temporal
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
from packages.core.config import TemporalConfig, load_app_config


def task_queue_names(config: TemporalConfig | None = None) -> tuple[str, ...]:
    temporal_config = config or load_app_config().temporal
    queues = temporal_config.task_queues
    return (
        queues.market_data,
        queues.strategy,
        queues.ai_research,
        queues.execution,
        queues.reconciliation,
        queues.reporting,
    )


def workflow_classes_by_task_queue(
    config: TemporalConfig | None = None,
) -> dict[str, tuple[type, ...]]:
    temporal_config = config or load_app_config().temporal
    queues = temporal_config.task_queues
    return {
        queues.market_data: (DailyDataRefreshWorkflow,),
        queues.strategy: (EODSignalWorkflow, DecisionWorkflow),
        queues.ai_research: (AIShortlistResearchWorkflow,),
        queues.execution: (
            ExecutionIntentWorkflow,
            OrderLifecycleWorkflow,
            PositionLifecycleWorkflow,
            KillSwitchWorkflow,
        ),
        queues.reconciliation: (ReconciliationWorkflow,),
        queues.reporting: (ReportingWorkflow,),
    }


def build_worker(
    client: Client,
    *,
    task_queue: str,
    config: TemporalConfig | None = None,
) -> Worker:
    workflows = workflow_classes_by_task_queue(config).get(task_queue)
    if workflows is None:
        allowed = ", ".join(task_queue_names(config))
        raise ValueError(f"unknown Temporal task queue {task_queue!r}; expected one of: {allowed}")

    return Worker(
        client,
        task_queue=task_queue,
        workflows=list(workflows),
        activities=list(ACTIVITY_FUNCTIONS),
    )


async def run_worker(task_queue: str, config: TemporalConfig | None = None) -> None:
    temporal_config = config or load_app_config().temporal
    client = await connect_temporal(temporal_config)
    worker = build_worker(client, task_queue=task_queue, config=temporal_config)
    await worker.run()


def run_worker_sync(task_queue: str, config: TemporalConfig | None = None) -> None:
    asyncio.run(run_worker(task_queue, config))
