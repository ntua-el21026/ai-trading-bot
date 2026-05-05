"""Broker adapter protocol boundaries.

The protocol includes submit/cancel methods because the execution workflow will eventually need
those boundaries. This milestone does not provide an executable broker path.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from typing import Protocol

from packages.broker.models import (
    BrokerAccountSnapshot,
    BrokerFill,
    BrokerOrder,
    BrokerPosition,
    BrokerProtectiveStop,
    BrokerRestFallbackSnapshot,
    BrokerStreamEvent,
)
from packages.execution.models import ExecutionIntent


class BrokerAdapterNotConfigured(RuntimeError):
    """Raised when a broker adapter boundary is called without a configured safe client."""


class BrokerAdapter(Protocol):
    def account_snapshot(self) -> BrokerAccountSnapshot:
        """Return the latest broker account snapshot."""

    def open_orders(self) -> Sequence[BrokerOrder]:
        """Return currently open broker orders."""

    def order_by_broker_order_id(self, broker_order_id: str) -> BrokerOrder | None:
        """Lookup a broker order by broker-assigned ID."""

    def order_by_client_order_id(self, client_order_id: str) -> BrokerOrder | None:
        """Lookup a broker order by idempotent client order ID."""

    def recent_fills(self) -> Sequence[BrokerFill]:
        """Return recent broker fills for reconciliation."""

    def positions(self) -> Sequence[BrokerPosition]:
        """Return current broker positions."""

    def protective_stops(self, symbol: str | None = None) -> Sequence[BrokerProtectiveStop]:
        """Return protective stop orders, optionally for one symbol."""

    def rest_fallback_snapshot(self) -> BrokerRestFallbackSnapshot:
        """Return a REST fallback snapshot for reconciliation."""

    def submit_order(self, intent: ExecutionIntent) -> BrokerOrder:
        """Submit an entry order. Must only be called by an execution activity."""

    def cancel_order(self, client_order_id: str) -> BrokerOrder:
        """Cancel an order by client order ID. Must only be called by an execution activity."""

    def submit_protective_stop(
        self,
        intent: ExecutionIntent,
        filled_quantity: float,
    ) -> BrokerOrder:
        """Submit a protective stop for filled quantity."""

    def stream_events(self) -> Iterable[BrokerStreamEvent]:
        """Consume mapped broker stream events."""
