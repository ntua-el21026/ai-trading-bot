"""Raw provider payload hashing and persistence contracts."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from typing import Protocol

from packages.data.models import RawProviderPayload


class RawPayloadRepository(Protocol):
    """Persistence boundary for raw provider payloads.

    Implementations are intentionally deferred until database infrastructure exists.
    """

    def save(self, payload: RawProviderPayload) -> RawProviderPayload:
        """Persist a raw payload record and return the stored representation."""


def payload_bytes(payload: object) -> bytes:
    if isinstance(payload, bytes):
        return payload
    if isinstance(payload, str):
        return payload.encode("utf-8")
    if isinstance(payload, Mapping | Sequence):
        return json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        ).encode("utf-8")
    return json.dumps(payload, sort_keys=True, default=str).encode("utf-8")


def payload_text(payload: object) -> str:
    return payload_bytes(payload).decode("utf-8")


def hash_payload(payload: object) -> str:
    return hashlib.sha256(payload_bytes(payload)).hexdigest()


def build_raw_provider_payload(
    *,
    provider: str,
    endpoint: str,
    payload: object,
    fetched_at: datetime | None = None,
    symbol: str | None = None,
    content_type: str = "application/json",
) -> RawProviderPayload:
    raw_bytes = payload_bytes(payload)
    timestamp = fetched_at or datetime.now(UTC)
    return RawProviderPayload(
        provider=provider,
        endpoint=endpoint,
        fetched_at=timestamp,
        payload_hash=hashlib.sha256(raw_bytes).hexdigest(),
        payload_size_bytes=len(raw_bytes),
        raw_payload=raw_bytes.decode("utf-8"),
        symbol=symbol,
        content_type=content_type,
    )
