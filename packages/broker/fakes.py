"""Fake Alpaca client and adapter helpers for local tests.

The fake client is in-memory only and never opens sockets or reads credentials.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from datetime import UTC, datetime
from typing import Any

from packages.broker.alpaca import (
    AlpacaClientError,
    AlpacaPaperAdapter,
    AlpacaPaperCredentials,
)
from packages.core.config import ExecutionConfig, SystemConfig, load_app_config

DEFAULT_AS_OF = datetime(2026, 5, 4, 14, 30, tzinfo=UTC)


class FakeAlpacaClient:
    """In-memory Alpaca-like client for adapter and activity tests."""

    def __init__(
        self,
        *,
        account: Mapping[str, Any] | None = None,
        orders: Sequence[Mapping[str, Any]] = (),
        fills: Sequence[Mapping[str, Any]] = (),
        positions: Sequence[Mapping[str, Any]] = (),
        trade_updates: Sequence[Mapping[str, Any]] = (),
        submit_error: AlpacaClientError | None = None,
        cancel_error: AlpacaClientError | None = None,
        stream_error: AlpacaClientError | None = None,
        rest_error: AlpacaClientError | None = None,
        next_submit_status: str = "accepted",
        next_submit_filled_qty: float = 0.0,
        submit_outcomes: Sequence[tuple[str, float]] = (),
        mutate_positions_on_submit: bool = False,
    ) -> None:
        self.account_payload = dict(account or _default_account())
        self.orders_by_id = {str(order["id"]): dict(order) for order in orders}
        self.orders_by_client_order_id = {
            str(order["client_order_id"]): dict(order) for order in orders
        }
        self.fills = [dict(fill) for fill in fills]
        self.positions_by_symbol = {
            str(position["symbol"]).upper(): dict(position) for position in positions
        }
        self.trade_updates = tuple(dict(event) for event in trade_updates)
        self.submit_error = submit_error
        self.cancel_error = cancel_error
        self.stream_error = stream_error
        self.rest_error = rest_error
        self.next_submit_status = next_submit_status
        self.next_submit_filled_qty = next_submit_filled_qty
        self.submit_outcomes = list(submit_outcomes)
        self.mutate_positions_on_submit = mutate_positions_on_submit
        self.submitted_order_requests: list[dict[str, Any]] = []
        self.cancelled_broker_order_ids: list[str] = []

    def get_account(self) -> Mapping[str, Any]:
        if self.rest_error is not None:
            raise self.rest_error
        return dict(self.account_payload)

    def list_open_orders(self) -> Sequence[Mapping[str, Any]]:
        if self.rest_error is not None:
            raise self.rest_error
        return tuple(
            dict(order)
            for order in self.orders_by_id.values()
            if str(order.get("status")) in {"new", "accepted", "pending_new", "partially_filled"}
        )

    def get_order_by_id(self, broker_order_id: str) -> Mapping[str, Any] | None:
        return _copy_optional(self.orders_by_id.get(broker_order_id))

    def get_order_by_client_order_id(self, client_order_id: str) -> Mapping[str, Any] | None:
        return _copy_optional(self.orders_by_client_order_id.get(client_order_id))

    def submit_order(self, request: Mapping[str, Any]) -> Mapping[str, Any]:
        if self.submit_error is not None:
            raise self.submit_error
        client_order_id = str(request["client_order_id"])
        if client_order_id in self.orders_by_client_order_id:
            raise AlpacaClientError(
                "duplicate_client_order_id",
                "client_order_id already exists in fake paper broker state",
                ambiguous=True,
                pause_new_risk=True,
                details={"client_order_id": client_order_id},
            )

        self.submitted_order_requests.append(dict(request))
        submit_status = self.next_submit_status
        submit_filled_qty = self.next_submit_filled_qty
        if self.submit_outcomes:
            submit_status, submit_filled_qty = self.submit_outcomes.pop(0)
        broker_order_id = f"paper-order-{len(self.orders_by_id) + 1}"
        submitted_at = DEFAULT_AS_OF.isoformat().replace("+00:00", "Z")
        order = {
            "id": broker_order_id,
            "client_order_id": client_order_id,
            "symbol": request["symbol"],
            "side": request["side"],
            "asset_class": "equity",
            "qty": request["qty"],
            "filled_qty": str(submit_filled_qty),
            "type": request["type"],
            "time_in_force": request["time_in_force"],
            "status": submit_status,
            "limit_price": request.get("limit_price"),
            "stop_price": request.get("stop_price"),
            "submitted_at": submitted_at,
            "updated_at": submitted_at,
        }
        self.orders_by_id[broker_order_id] = dict(order)
        self.orders_by_client_order_id[client_order_id] = dict(order)
        if self.mutate_positions_on_submit and submit_filled_qty > 0:
            self._apply_filled_order(order, filled_quantity=submit_filled_qty)
        return dict(order)

    def cancel_order(self, broker_order_id: str) -> Mapping[str, Any]:
        if self.cancel_error is not None:
            raise self.cancel_error
        order = self.orders_by_id.get(broker_order_id)
        if order is None:
            raise AlpacaClientError(
                "order_not_found",
                "broker order was not found for cancellation",
                details={"broker_order_id": broker_order_id},
            )
        self.cancelled_broker_order_ids.append(broker_order_id)
        cancelled = dict(order) | {
            "status": "cancelled",
            "updated_at": DEFAULT_AS_OF.isoformat().replace("+00:00", "Z"),
        }
        self.orders_by_id[broker_order_id] = dict(cancelled)
        self.orders_by_client_order_id[str(cancelled["client_order_id"])] = dict(cancelled)
        return cancelled

    def list_fills(self) -> Sequence[Mapping[str, Any]]:
        if self.rest_error is not None:
            raise self.rest_error
        return tuple(dict(fill) for fill in self.fills)

    def list_positions(self) -> Sequence[Mapping[str, Any]]:
        if self.rest_error is not None:
            raise self.rest_error
        return tuple(dict(position) for position in self.positions_by_symbol.values())

    def get_position(self, symbol: str) -> Mapping[str, Any] | None:
        return _copy_optional(self.positions_by_symbol.get(symbol.upper()))

    def consume_trade_updates(self) -> Iterable[Mapping[str, Any]]:
        if self.stream_error is not None:
            raise self.stream_error
        return tuple(dict(event) for event in self.trade_updates)

    def get_clock(self) -> Mapping[str, Any]:
        return {
            "is_open": True,
            "timestamp": DEFAULT_AS_OF.isoformat().replace("+00:00", "Z"),
            "next_open": DEFAULT_AS_OF.isoformat().replace("+00:00", "Z"),
            "next_close": DEFAULT_AS_OF.replace(hour=21, minute=0).isoformat().replace(
                "+00:00",
                "Z",
            ),
        }

    def _apply_filled_order(
        self,
        order: Mapping[str, Any],
        *,
        filled_quantity: float,
    ) -> None:
        symbol = str(order["symbol"]).upper()
        side = str(order["side"])
        price = float(order.get("limit_price") or order.get("stop_price") or 1.0)
        fill_id = f"paper-fill-{len(self.fills) + 1}"
        filled_at = DEFAULT_AS_OF.isoformat().replace("+00:00", "Z")
        self.fills.append(
            {
                "id": fill_id,
                "order_id": order["id"],
                "client_order_id": order["client_order_id"],
                "symbol": symbol,
                "side": side,
                "qty": str(filled_quantity),
                "price": str(price),
                "transaction_time": filled_at,
            }
        )
        existing = self.positions_by_symbol.get(symbol)
        if side == "buy":
            existing_quantity = 0.0 if existing is None else float(existing["qty"])
            existing_value = (
                0.0 if existing is None else existing_quantity * float(existing["avg_entry_price"])
            )
            new_quantity = existing_quantity + filled_quantity
            average_entry_price = (existing_value + filled_quantity * price) / new_quantity
            self.positions_by_symbol[symbol] = {
                "symbol": symbol,
                "asset_class": "equity",
                "qty": str(new_quantity),
                "avg_entry_price": str(average_entry_price),
                "market_value": str(new_quantity * price),
                "opened_at": filled_at,
            }
            return
        if existing is None:
            return
        remaining_quantity = float(existing["qty"]) - filled_quantity
        if remaining_quantity <= 1e-9:
            self.positions_by_symbol.pop(symbol, None)
            return
        self.positions_by_symbol[symbol] = dict(existing) | {
            "qty": str(remaining_quantity),
            "market_value": str(remaining_quantity * float(existing["avg_entry_price"])),
        }


def build_fake_alpaca_paper_adapter(
    *,
    client: FakeAlpacaClient | None = None,
    system_config: SystemConfig | None = None,
    execution_config: ExecutionConfig | None = None,
) -> AlpacaPaperAdapter:
    app_config = load_app_config()
    return AlpacaPaperAdapter(
        system_config=system_config or app_config.system,
        execution_config=execution_config or app_config.execution,
        client=client or FakeAlpacaClient(),
        run_mode="test",
    )


def dummy_paper_credentials() -> AlpacaPaperCredentials:
    return AlpacaPaperCredentials(
        api_key="paper-key-placeholder",
        secret_key="paper-secret-placeholder",
    )


def _default_account() -> dict[str, Any]:
    return {
        "id": "paper-account",
        "equity": "100000",
        "cash": "90000",
        "buying_power": "180000",
        "currency": "USD",
        "as_of": DEFAULT_AS_OF.isoformat().replace("+00:00", "Z"),
    }


def _copy_optional(value: dict[str, Any] | None) -> dict[str, Any] | None:
    return None if value is None else dict(value)
