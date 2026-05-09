"""Temporal client bootstrap."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Self

from temporalio.client import Client

from packages.core.config import TemporalConfig, load_app_config

TEMPORAL_CLOUD_SMOKE_RUN_ENV = "RUN_TEMPORAL_CLOUD_SMOKE"
TEMPORAL_CLOUD_SMOKE_CONFIRM_ENV = "TEMPORAL_CLOUD_SMOKE_CONFIRM"
TEMPORAL_CLOUD_SMOKE_CONFIRM_VALUE = "CONNECT_DEV_NAMESPACE_ONLY"
TEMPORAL_CLOUD_SMOKE_TASK_QUEUE_ENV = "TEMPORAL_CLOUD_SMOKE_TASK_QUEUE"
TEMPORAL_CLOUD_SMOKE_WORKFLOW_ENV = "TEMPORAL_CLOUD_SMOKE_WORKFLOW"

TEMPORAL_ADDRESS_ENV = "TEMPORAL_ADDRESS"
TEMPORAL_NAMESPACE_ENV = "TEMPORAL_NAMESPACE"
TEMPORAL_API_KEY_ENV = "TEMPORAL_API_KEY"


@dataclass(frozen=True)
class TemporalCloudSmokeSettings:
    """Internal, redacted-by-default Temporal Cloud smoke settings."""

    address: str | None
    namespace: str | None
    api_key: str | None = field(default=None, repr=False, compare=False)
    task_queue: str = "reporting-task-queue"
    workflow: str = "KillSwitchWorkflow"
    gates_loaded: bool = False
    refusal_reasons: tuple[str, ...] = ()

    @classmethod
    def from_env(
        cls,
        environ: Mapping[str, str] | None = None,
        config: TemporalConfig | None = None,
    ) -> Self:
        env = os.environ if environ is None else environ
        temporal_config = config or load_app_config().temporal

        task_queue = (
            env.get(TEMPORAL_CLOUD_SMOKE_TASK_QUEUE_ENV)
            or temporal_config.task_queues.reporting
        )
        workflow = env.get(TEMPORAL_CLOUD_SMOKE_WORKFLOW_ENV) or "KillSwitchWorkflow"
        address = env.get(TEMPORAL_ADDRESS_ENV)
        namespace = env.get(TEMPORAL_NAMESPACE_ENV)
        api_key = env.get(TEMPORAL_API_KEY_ENV)

        reasons: list[str] = []
        if env.get(TEMPORAL_CLOUD_SMOKE_RUN_ENV) != "1":
            reasons.append("missing_run_gate")
        if env.get(TEMPORAL_CLOUD_SMOKE_CONFIRM_ENV) != TEMPORAL_CLOUD_SMOKE_CONFIRM_VALUE:
            reasons.append("missing_confirmation_gate")
        if not address:
            reasons.append("missing_temporal_address")
        if not namespace:
            reasons.append("missing_temporal_namespace")
        if not api_key:
            reasons.append("missing_temporal_api_key")
        if workflow != "KillSwitchWorkflow":
            reasons.append("unsupported_smoke_workflow")
        if task_queue not in {
            temporal_config.task_queues.market_data,
            temporal_config.task_queues.strategy,
            temporal_config.task_queues.ai_research,
            temporal_config.task_queues.execution,
            temporal_config.task_queues.reconciliation,
            temporal_config.task_queues.reporting,
        }:
            reasons.append("unknown_task_queue")

        return cls(
            address=address,
            namespace=namespace,
            api_key=api_key,
            task_queue=task_queue,
            workflow=workflow,
            gates_loaded=not reasons,
            refusal_reasons=tuple(reasons),
        )

    def sanitized(self) -> dict[str, Any]:
        """Return a safe status summary without host or secret values."""

        return {
            "gates_loaded": self.gates_loaded,
            "temporal_address_present": bool(self.address),
            "temporal_namespace_present": bool(self.namespace),
            "temporal_api_key_present": bool(self.api_key),
            "namespace": self.namespace if self.namespace else None,
            "task_queue": self.task_queue,
            "workflow": self.workflow,
            "refusal_reasons": list(self.refusal_reasons),
        }


def temporal_cloud_connect_kwargs(
    settings: TemporalCloudSmokeSettings,
) -> tuple[str, dict[str, Any]]:
    """Build Temporal Cloud connection kwargs without logging secrets."""

    if not settings.address or not settings.namespace or not settings.api_key:
        raise ValueError("Temporal Cloud address, namespace, and API key are required")
    return (
        settings.address,
        {
            "namespace": settings.namespace,
            "api_key": settings.api_key,
            "tls": True,
        },
    )


async def connect_temporal(
    config: TemporalConfig | None = None,
    *,
    address: str | None = None,
    namespace: str | None = None,
    api_key: str | None = None,
    tls: bool | None = None,
) -> Client:
    """Connect to Temporal using typed config.

    This helper performs network I/O only when explicitly called by a worker or operational script.
    Workflow modules must not import or call this helper.
    """

    temporal_config = config or load_app_config().temporal
    return await Client.connect(
        address or temporal_config.address,
        namespace=namespace or temporal_config.namespace,
        api_key=api_key,
        tls=tls,
    )


async def connect_temporal_cloud_dev(settings: TemporalCloudSmokeSettings) -> Client:
    """Connect to an explicitly gated Temporal Cloud dev namespace."""

    target_host, kwargs = temporal_cloud_connect_kwargs(settings)
    return await Client.connect(target_host, **kwargs)
