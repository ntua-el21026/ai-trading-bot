"""Deterministic idempotency helpers for execution intents and order IDs."""

from __future__ import annotations

import hashlib
import re
from collections.abc import Iterable
from datetime import date

from packages.execution.models import DuplicateIntentKey, ExecutionIntent, ExecutionSide


def short_hash(value: str, length: int = 10) -> str:
    if length <= 0:
        raise ValueError("length must be positive")
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:length]


def build_client_order_id_root(
    *,
    strategy_version: str,
    symbol: str,
    side: ExecutionSide,
    trade_date: date,
    intent_sequence: int,
    decision_id: str,
) -> str:
    if intent_sequence < 0:
        raise ValueError("intent_sequence cannot be negative")
    symbol = symbol.upper()
    base = (
        f"{_normalize_component(strategy_version)}-"
        f"{symbol}-"
        f"{side}-"
        f"{trade_date:%Y%m%d}-"
        f"{intent_sequence}"
    )
    digest = short_hash(f"{base}-{decision_id}")
    return f"{base}-{digest}"


def duplicate_intent_key(intent: ExecutionIntent, trade_date: date) -> DuplicateIntentKey:
    return DuplicateIntentKey(
        symbol=intent.symbol,
        side=intent.side,
        trade_date=trade_date,
        strategy_version=intent.strategy_version,
    )


def has_duplicate_intent(
    candidate: DuplicateIntentKey,
    active_intents: Iterable[ExecutionIntent],
) -> bool:
    return any(
        duplicate_intent_key(intent, candidate.trade_date) == candidate
        and intent.status not in {"cancelled", "expired", "rejected"}
        for intent in active_intents
    )


def _normalize_component(value: str) -> str:
    normalized = re.sub(r"[^A-Za-z0-9_-]+", "-", value.strip())
    normalized = normalized.strip("-").lower()
    if not normalized:
        raise ValueError("idempotency component cannot be empty")
    return normalized

