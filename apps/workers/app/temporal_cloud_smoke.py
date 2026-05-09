"""Explicitly gated Temporal Cloud dev runtime smoke harness."""

from __future__ import annotations

import asyncio
import os
from collections.abc import Callable, Coroutine, Mapping
from contextlib import AsyncExitStack
from dataclasses import dataclass
from typing import Any
from uuid import uuid4

from temporalio import activity
from temporalio.worker import Worker

from apps.workers.app.queries import GET_CURRENT_SYSTEM_STATE, GET_KILL_SWITCH_STATE
from apps.workers.app.signals import MANUAL_PAUSE_NEW_RISK
from apps.workers.app.temporal_client import (
    TemporalCloudSmokeSettings,
    connect_temporal_cloud_dev,
)
from apps.workers.app.types import (
    ActivityPlaceholderInput,
    ActivityPlaceholderResult,
    WorkflowRunInput,
)
from apps.workers.app.workflows.kill_switch import KillSwitchWorkflow
from packages.core.config import TemporalConfig, load_app_config


@dataclass(frozen=True)
class TemporalCloudSmokeResult:
    gates_loaded: bool = False
    temporal_address_present: bool = False
    temporal_namespace_present: bool = False
    temporal_api_key_present: bool = False
    connected_to_temporal_cloud: bool = False
    namespace: str | None = None
    task_queue: str = "reporting-task-queue"
    worker_started: bool = False
    workflow_started: bool = False
    workflow_completed: bool = False
    signal_query_checked: bool = False
    schedules_created: bool = False
    schedules_activated: bool = False
    external_broker_calls: bool = False
    external_ai_news_calls: bool = False
    external_alert_calls: bool = False
    secrets_printed: bool = False
    actual_paper_trading_started: bool = False
    level4_ready: bool = False
    refused: bool = False
    refusal_reasons: tuple[str, ...] = ()
    failure_codes: tuple[str, ...] = ()

    def to_sanitized_dict(self) -> dict[str, object]:
        return {
            "gates_loaded": self.gates_loaded,
            "temporal_address_present": self.temporal_address_present,
            "temporal_namespace_present": self.temporal_namespace_present,
            "temporal_api_key_present": self.temporal_api_key_present,
            "connected_to_temporal_cloud": self.connected_to_temporal_cloud,
            "namespace": self.namespace,
            "task_queue": self.task_queue,
            "worker_started": self.worker_started,
            "workflow_started": self.workflow_started,
            "workflow_completed": self.workflow_completed,
            "signal_query_checked": self.signal_query_checked,
            "schedules_created": self.schedules_created,
            "schedules_activated": self.schedules_activated,
            "external_broker_calls": self.external_broker_calls,
            "external_ai_news_calls": self.external_ai_news_calls,
            "external_alert_calls": self.external_alert_calls,
            "secrets_printed": self.secrets_printed,
            "actual_paper_trading_started": self.actual_paper_trading_started,
            "level4_ready": self.level4_ready,
            "refused": self.refused,
            "refusal_reasons": list(self.refusal_reasons),
            "failure_codes": list(self.failure_codes),
        }


TemporalCloudSmokeExecutor = Callable[
    [TemporalCloudSmokeSettings, TemporalConfig],
    Coroutine[Any, Any, TemporalCloudSmokeResult],
]


@activity.defn(name="persist_system_event")
async def temporal_cloud_smoke_persist_system_event(
    payload: ActivityPlaceholderInput,
) -> ActivityPlaceholderResult:
    """Fake smoke-only activity; performs no ledger, broker, AI/news, or alert side effects."""

    await asyncio.sleep(0.25)
    return ActivityPlaceholderResult(
        activity_name="persist_system_event",
        status="temporal_cloud_smoke_placeholder",
        external_calls_performed=False,
        details={
            "workflow_name": payload.workflow_name,
            "purpose": payload.purpose,
            "external_calls": "none",
        },
    )


def run_temporal_cloud_smoke(
    *,
    environ: Mapping[str, str] | None = None,
    config: TemporalConfig | None = None,
    executor: TemporalCloudSmokeExecutor | None = None,
) -> TemporalCloudSmokeResult:
    temporal_config = config or load_app_config().temporal
    env = os.environ if environ is None else environ
    settings = TemporalCloudSmokeSettings.from_env(env, temporal_config)

    if not settings.gates_loaded:
        return TemporalCloudSmokeResult(
            gates_loaded=False,
            temporal_address_present=bool(settings.address),
            temporal_namespace_present=bool(settings.namespace),
            temporal_api_key_present=bool(settings.api_key),
            namespace=settings.namespace,
            task_queue=settings.task_queue,
            refused=True,
            refusal_reasons=settings.refusal_reasons,
        )

    selected_executor = executor or execute_temporal_cloud_smoke
    try:
        return asyncio.run(selected_executor(settings, temporal_config))
    except Exception:
        return TemporalCloudSmokeResult(
            gates_loaded=True,
            temporal_address_present=bool(settings.address),
            temporal_namespace_present=bool(settings.namespace),
            temporal_api_key_present=bool(settings.api_key),
            namespace=settings.namespace,
            task_queue=settings.task_queue,
            refused=True,
            failure_codes=("temporal_cloud_smoke_failed",),
        )


async def execute_temporal_cloud_smoke(
    settings: TemporalCloudSmokeSettings,
    config: TemporalConfig,
) -> TemporalCloudSmokeResult:
    client = await connect_temporal_cloud_dev(settings)
    execution_task_queue = config.task_queues.execution
    workflow_id = f"temporal-cloud-smoke-{uuid4().hex[:16]}"

    async with AsyncExitStack() as stack:
        if settings.task_queue == execution_task_queue:
            await stack.enter_async_context(
                Worker(
                    client,
                    task_queue=settings.task_queue,
                    workflows=[KillSwitchWorkflow],
                    activities=[temporal_cloud_smoke_persist_system_event],
                )
            )
        else:
            await stack.enter_async_context(
                Worker(
                    client,
                    task_queue=settings.task_queue,
                    workflows=[KillSwitchWorkflow],
                    activities=[],
                )
            )
            await stack.enter_async_context(
                Worker(
                    client,
                    task_queue=execution_task_queue,
                    workflows=[KillSwitchWorkflow],
                    activities=[temporal_cloud_smoke_persist_system_event],
                )
            )

        handle = await client.start_workflow(
            KillSwitchWorkflow.run,
            WorkflowRunInput(reason="temporal-cloud-smoke"),
            id=workflow_id,
            task_queue=settings.task_queue,
        )
        await handle.signal(MANUAL_PAUSE_NEW_RISK, "temporal_cloud_smoke")
        kill_state = await handle.query(GET_KILL_SWITCH_STATE)
        current_state = await handle.query(GET_CURRENT_SYSTEM_STATE)
        result = await handle.result()

    return TemporalCloudSmokeResult(
        gates_loaded=True,
        temporal_address_present=bool(settings.address),
        temporal_namespace_present=bool(settings.namespace),
        temporal_api_key_present=bool(settings.api_key),
        connected_to_temporal_cloud=True,
        namespace=settings.namespace,
        task_queue=settings.task_queue,
        worker_started=True,
        workflow_started=True,
        workflow_completed=result.status == "completed",
        signal_query_checked=bool(kill_state) and bool(current_state),
    )
