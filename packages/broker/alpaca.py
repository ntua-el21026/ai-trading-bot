"""Alpaca paper-mode adapter skeleton and trade update mapping.

No Alpaca SDK dependency is required for Milestone 06. The adapter refuses live mode and raises
until a later milestone supplies an explicitly configured paper client inside Temporal activities.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from datetime import UTC, datetime
from typing import Any, cast, get_args

from packages.broker.adapters import BrokerAdapterNotConfigured
from packages.broker.models import (
    BrokerAccountSnapshot,
    BrokerFill,
    BrokerOrder,
    BrokerOrderStatus,
    BrokerOrderType,
    BrokerPosition,
    BrokerProtectiveStop,
    BrokerRestFallbackSnapshot,
    BrokerSide,
    BrokerStreamEvent,
    BrokerStreamEventType,
    BrokerTimeInForce,
)
from packages.core.config import ExecutionConfig, SystemConfig
from packages.data.models import AssetClass
from packages.data.payloads import hash_payload
from packages.execution.models import ExecutionIntent

ALPACA_EVENT_TYPE_MAP: dict[str, BrokerStreamEventType] = {
    "new": "order_acknowledged",
    "accepted": "order_acknowledged",
    "pending_new": "order_acknowledged",
    "partial_fill": "partial_fill",
    "fill": "fill",
    "canceled": "cancelled",
    "cancelled": "cancelled",
    "rejected": "rejected",
    "expired": "expired",
    "replaced": "replaced",
}


class AlpacaPaperAdapter:
    """Safe paper-mode boundary.

    The class exists to enforce configuration gates and define the future adapter shape. It does
    not perform network I/O or submit orders in this milestone.
    """

    def __init__(
        self,
        *,
        system_config: SystemConfig,
        execution_config: ExecutionConfig,
        client: object | None = None,
    ) -> None:
        if system_config.environment != "paper":
            raise BrokerAdapterNotConfigured("AlpacaPaperAdapter only supports paper mode")
        if system_config.live_trading_enabled or execution_config.allow_live_orders:
            raise BrokerAdapterNotConfigured("live order flags must remain disabled")
        self._client = client

    def account_snapshot(self) -> BrokerAccountSnapshot:
        raise BrokerAdapterNotConfigured("Alpaca paper client is not configured")

    def open_orders(self) -> Sequence[BrokerOrder]:
        raise BrokerAdapterNotConfigured("Alpaca paper client is not configured")

    def order_by_broker_order_id(self, broker_order_id: str) -> BrokerOrder | None:
        raise BrokerAdapterNotConfigured("Alpaca paper client is not configured")

    def order_by_client_order_id(self, client_order_id: str) -> BrokerOrder | None:
        raise BrokerAdapterNotConfigured("Alpaca paper client is not configured")

    def recent_fills(self) -> Sequence[BrokerFill]:
        raise BrokerAdapterNotConfigured("Alpaca paper client is not configured")

    def positions(self) -> Sequence[BrokerPosition]:
        raise BrokerAdapterNotConfigured("Alpaca paper client is not configured")

    def protective_stops(self, symbol: str | None = None) -> Sequence[BrokerProtectiveStop]:
        raise BrokerAdapterNotConfigured("Alpaca paper client is not configured")

    def rest_fallback_snapshot(self) -> BrokerRestFallbackSnapshot:
        raise BrokerAdapterNotConfigured("Alpaca paper client is not configured")

    def submit_order(self, intent: ExecutionIntent) -> BrokerOrder:
        raise BrokerAdapterNotConfigured("order submission is not implemented in Milestone 06")

    def cancel_order(self, client_order_id: str) -> BrokerOrder:
        raise BrokerAdapterNotConfigured("order cancellation is not implemented in Milestone 06")

    def submit_protective_stop(
        self,
        intent: ExecutionIntent,
        filled_quantity: float,
    ) -> BrokerOrder:
        raise BrokerAdapterNotConfigured("stop submission is not implemented in Milestone 06")

    def stream_events(self) -> Iterable[BrokerStreamEvent]:
        raise BrokerAdapterNotConfigured("stream consumption is not implemented in Milestone 06")


def map_alpaca_trade_update(payload: Mapping[str, Any]) -> BrokerStreamEvent:
    """Map one Alpaca trade_updates payload into normalized broker stream contracts."""

    order_payload = _mapping(payload.get("order"))
    event_name = str(payload.get("event", "unknown"))
    event_type = ALPACA_EVENT_TYPE_MAP.get(event_name, "unknown")
    event_at = _datetime(payload.get("timestamp") or payload.get("at"))
    raw_hash = hash_payload(payload)
    broker_order = _map_order(order_payload, raw_hash)
    fill = (
        _map_fill(payload, broker_order, event_at, raw_hash)
        if event_type in {"fill", "partial_fill"}
        else None
    )
    return BrokerStreamEvent(
        event_type=event_type,
        broker_order=broker_order,
        fill=fill,
        event_at=event_at,
        raw_payload_hash=raw_hash,
    )


def _map_order(order_payload: Mapping[str, Any], raw_payload_hash: str) -> BrokerOrder:
    order_type = _order_type(order_payload.get("order_type") or order_payload.get("type"))
    status = _order_status(order_payload.get("status"))
    return BrokerOrder(
        broker_order_id=str(order_payload["id"]),
        client_order_id=str(order_payload["client_order_id"]),
        symbol=str(order_payload["symbol"]).upper(),
        side=_side(order_payload.get("side")),
        asset_class=_asset_class(order_payload.get("asset_class")),
        quantity=float(order_payload["qty"]),
        filled_quantity=float(order_payload.get("filled_qty") or 0.0),
        order_type=order_type,
        time_in_force=_time_in_force(order_payload.get("time_in_force")),
        status=status,
        submitted_at=_optional_datetime(order_payload.get("submitted_at")),
        updated_at=_optional_datetime(order_payload.get("updated_at")),
        limit_price=_optional_float(order_payload.get("limit_price")),
        stop_price=_optional_float(order_payload.get("stop_price")),
        purpose="protective_stop" if order_type in {"stop", "stop_limit"} else "entry",
        raw_payload_hash=raw_payload_hash,
    )


def _map_fill(
    payload: Mapping[str, Any],
    broker_order: BrokerOrder,
    event_at: datetime,
    raw_payload_hash: str,
) -> BrokerFill:
    fill_price = _optional_float(payload.get("price")) or broker_order.limit_price
    if fill_price is None:
        fill_price = _optional_float(_mapping(payload.get("order")).get("filled_avg_price"))
    if fill_price is None:
        raise ValueError("fill trade_update payload must include price or filled_avg_price")
    return BrokerFill(
        broker_order_id=broker_order.broker_order_id,
        client_order_id=broker_order.client_order_id,
        symbol=broker_order.symbol,
        side=broker_order.side,
        quantity=float(payload.get("qty") or broker_order.filled_quantity),
        price=fill_price,
        filled_at=event_at,
        raw_payload_hash=raw_payload_hash,
    )


def _mapping(value: object) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError("Alpaca trade update payload must contain an order mapping")
    return cast(Mapping[str, Any], value)


def _datetime(value: object) -> datetime:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            raise ValueError("datetime values must be timezone-aware")
        return value
    if not isinstance(value, str):
        raise ValueError("timestamp value is required")
    normalized = value.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed


def _optional_datetime(value: object) -> datetime | None:
    if value in (None, ""):
        return None
    return _datetime(value)


def _optional_float(value: object) -> float | None:
    if value in (None, ""):
        return None
    if not isinstance(value, str | int | float):
        raise ValueError(f"expected numeric value, got {type(value).__name__}")
    return float(value)


def _side(value: object) -> BrokerSide:
    if value not in {"buy", "sell"}:
        raise ValueError(f"unsupported Alpaca side: {value}")
    return cast(BrokerSide, value)


def _order_type(value: object) -> BrokerOrderType:
    if value not in {"market", "limit", "stop", "stop_limit"}:
        raise ValueError(f"unsupported Alpaca order type: {value}")
    return cast(BrokerOrderType, value)


def _time_in_force(value: object) -> BrokerTimeInForce:
    if value not in {"day", "gtc", "ioc", "fok"}:
        raise ValueError(f"unsupported Alpaca time in force: {value}")
    return cast(BrokerTimeInForce, value)


def _order_status(value: object) -> BrokerOrderStatus:
    normalized = "cancelled" if value == "canceled" else str(value or "unknown")
    if normalized not in get_args(BrokerOrderStatus):
        return "unknown"
    return cast(BrokerOrderStatus, normalized)


def _asset_class(value: object) -> AssetClass:
    normalized = "etf" if value == "us_equity_etf" else str(value or "equity")
    if normalized not in get_args(AssetClass):
        return "other"
    return cast(AssetClass, normalized)
