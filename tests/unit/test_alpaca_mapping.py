from datetime import UTC, datetime

from packages.broker.alpaca import map_alpaca_trade_update
from packages.data.payloads import hash_payload


def test_alpaca_trade_update_maps_partial_fill_to_internal_event() -> None:
    payload = {
        "event": "partial_fill",
        "timestamp": "2026-05-04T14:12:30Z",
        "price": "180.25",
        "qty": "4",
        "order": {
            "id": "broker-order-1",
            "client_order_id": "strategy-AAPL-buy-20260504-1-abc123",
            "symbol": "AAPL",
            "side": "buy",
            "asset_class": "equity",
            "qty": "10",
            "filled_qty": "4",
            "type": "limit",
            "time_in_force": "day",
            "status": "partially_filled",
            "limit_price": "180.50",
            "submitted_at": "2026-05-04T14:00:00Z",
            "updated_at": "2026-05-04T14:12:30Z",
        },
    }

    event = map_alpaca_trade_update(payload)

    assert event.event_type == "partial_fill"
    assert event.event_at == datetime(2026, 5, 4, 14, 12, 30, tzinfo=UTC)
    assert event.raw_payload_hash == hash_payload(payload)
    assert event.broker_order.broker_order_id == "broker-order-1"
    assert event.broker_order.client_order_id == "strategy-AAPL-buy-20260504-1-abc123"
    assert event.broker_order.status == "partially_filled"
    assert event.fill is not None
    assert event.fill.quantity == 4.0
    assert event.fill.price == 180.25


def test_alpaca_trade_update_maps_canceled_spelling_to_cancelled_event() -> None:
    payload = {
        "event": "canceled",
        "timestamp": "2026-05-04T15:00:00Z",
        "order": {
            "id": "broker-order-2",
            "client_order_id": "strategy-AAPL-buy-20260504-2-def456",
            "symbol": "AAPL",
            "side": "buy",
            "asset_class": "equity",
            "qty": "10",
            "filled_qty": "0",
            "type": "limit",
            "time_in_force": "day",
            "status": "canceled",
            "limit_price": "180.50",
        },
    }

    event = map_alpaca_trade_update(payload)

    assert event.event_type == "cancelled"
    assert event.broker_order.status == "cancelled"
