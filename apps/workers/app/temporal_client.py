"""Temporal client bootstrap."""

from __future__ import annotations

from temporalio.client import Client

from packages.core.config import TemporalConfig, load_app_config


async def connect_temporal(
    config: TemporalConfig | None = None,
    *,
    address: str | None = None,
) -> Client:
    """Connect to Temporal using typed config.

    This helper performs network I/O only when explicitly called by a worker or operational script.
    Workflow modules must not import or call this helper.
    """

    temporal_config = config or load_app_config().temporal
    return await Client.connect(
        address or temporal_config.address,
        namespace=temporal_config.namespace,
    )
