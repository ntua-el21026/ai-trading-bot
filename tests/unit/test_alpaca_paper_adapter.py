from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

import pytest

from packages.broker.alpaca import AlpacaClientError, AlpacaPaperAdapter
from packages.broker.fakes import (
    DEFAULT_AS_OF,
    FakeAlpacaClient,
    build_fake_alpaca_paper_adapter,
    dummy_paper_credentials,
)
from packages.broker.models import BrokerSnapshot
from packages.core.config import SystemConfig, load_app_config
from packages.execution.models import ExecutionIntent
from packages.reconciliation.models import (
    InternalAccountSnapshot,
    InternalLedgerSnapshot,
    InternalOrder,
)
from packages.reconciliation.service import compare_broker_and_internal


def _intent(**updates: object) -> ExecutionIntent:
    data: dict[str, object] = {
        "decision_id": UUID("00000000-0000-4000-8000-000000000001"),
        "symbol": "AAPL",
        "side": "buy",
        "asset_class": "equity",
        "quantity": 10,
        "entry_order_type": "limit",
        "limit_price": 180.5,
        "stop_loss_price": 174.2,
        "time_in_force": "day",
        "strategy_version": "regime_filtered_breakout_v0_3",
        "risk_config_version": "risk_v0_3",
        "autonomy_level": 2,
        "requires_protective_stop": True,
        "max_acceptable_slippage_bps": 25,
        "expires_at": datetime(2026, 5, 4, 15, 0, tzinfo=UTC),
        "client_order_id_root": "strategy-AAPL-buy-20260504-1-abc123",
        "status": "risk_approved",
        "temporal_workflow_id": "workflow-entry-1",
    }
    data.update(updates)
    return ExecutionIntent.model_validate(data)


def _order_payload(**updates: object) -> dict[str, object]:
    data: dict[str, object] = {
        "id": "broker-order-1",
        "client_order_id": "strategy-AAPL-buy-20260504-1-abc123",
        "symbol": "AAPL",
        "side": "buy",
        "asset_class": "equity",
        "qty": "10",
        "filled_qty": "0",
        "type": "limit",
        "time_in_force": "day",
        "status": "accepted",
        "limit_price": "180.50",
        "submitted_at": "2026-05-04T14:00:00Z",
        "updated_at": "2026-05-04T14:00:00Z",
    }
    data.update(updates)
    return data


def test_adapter_refuses_live_mode_non_paper_and_missing_runtime_credentials() -> None:
    config = load_app_config()
    live_system = SystemConfig.model_validate(config.system.model_dump() | {"environment": "live"})
    live_execution = config.execution.model_copy(update={"allow_live_orders": True})

    with pytest.raises(RuntimeError, match="only supports paper mode"):
        AlpacaPaperAdapter(
            system_config=live_system,
            execution_config=config.execution,
            client=FakeAlpacaClient(),
            run_mode="test",
        )
    with pytest.raises(RuntimeError, match="allow_live_orders"):
        AlpacaPaperAdapter(
            system_config=config.system,
            execution_config=live_execution,
            client=FakeAlpacaClient(),
            run_mode="test",
        )
    with pytest.raises(RuntimeError, match="credentials are required"):
        AlpacaPaperAdapter(
            system_config=config.system,
            execution_config=config.execution,
            client=FakeAlpacaClient(),
        )


def test_adapter_accepts_runtime_mode_only_with_paper_credentials_and_client() -> None:
    config = load_app_config()

    adapter = AlpacaPaperAdapter(
        system_config=config.system,
        execution_config=config.execution,
        client=FakeAlpacaClient(),
        credentials=dummy_paper_credentials(),
    )

    assert adapter.account_snapshot().environment == "paper"


def test_fake_client_maps_account_order_fill_position_and_trade_update() -> None:
    fill = {
        "id": "fill-1",
        "order_id": "broker-order-1",
        "client_order_id": "strategy-AAPL-buy-20260504-1-abc123",
        "symbol": "AAPL",
        "side": "buy",
        "qty": "4",
        "price": "180.25",
        "transaction_time": "2026-05-04T14:12:30Z",
    }
    position = {
        "symbol": "AAPL",
        "asset_class": "equity",
        "qty": "4",
        "avg_entry_price": "180.25",
        "market_value": "721.00",
        "opened_at": "2026-05-04T14:12:30Z",
    }
    trade_update = {
        "event": "partial_fill",
        "timestamp": "2026-05-04T14:12:30Z",
        "price": "180.25",
        "qty": "4",
        "order": _order_payload(status="partially_filled", filled_qty="4"),
    }
    adapter = build_fake_alpaca_paper_adapter(
        client=FakeAlpacaClient(
            orders=(_order_payload(status="partially_filled", filled_qty="4"),),
            fills=(fill,),
            positions=(position,),
            trade_updates=(trade_update,),
        )
    )

    assert adapter.account_snapshot().account_id == "paper-account"
    assert adapter.open_orders()[0].filled_quantity == 4.0
    assert adapter.recent_fills()[0].broker_fill_id == "fill-1"
    assert adapter.positions()[0].quantity == 4.0
    assert tuple(adapter.stream_events())[0].event_type == "partial_fill"


def test_submit_paper_entry_order_builds_limit_day_request_without_extended_hours() -> None:
    client = FakeAlpacaClient()
    adapter = build_fake_alpaca_paper_adapter(client=client)

    result = adapter.submit_entry_order(_intent())

    assert result.status == "succeeded"
    assert client.submitted_order_requests == [
        {
            "symbol": "AAPL",
            "side": "buy",
            "type": "limit",
            "time_in_force": "day",
            "qty": "10",
            "limit_price": "180.5",
            "client_order_id": "strategy-AAPL-buy-20260504-1-abc123",
            "extended_hours": False,
        }
    ]


def test_submit_paper_entry_order_rejects_market_entry_contract() -> None:
    adapter = build_fake_alpaca_paper_adapter(client=FakeAlpacaClient())
    invalid_intent = _intent().model_copy(update={"entry_order_type": "market"})

    result = adapter.submit_entry_order(invalid_intent)

    assert result.status == "failed"
    assert result.error is not None
    assert result.error.code == "unsupported_order_type"


def test_submit_paper_entry_uses_idempotency_lookup_before_retry() -> None:
    client = FakeAlpacaClient(orders=(_order_payload(),))
    adapter = build_fake_alpaca_paper_adapter(client=client)

    result = adapter.submit_entry_order(_intent())

    assert result.status == "succeeded"
    assert result.idempotency_reused is True
    assert client.submitted_order_requests == []


def test_ambiguous_submit_response_returns_structured_pause_result() -> None:
    client = FakeAlpacaClient(
        submit_error=AlpacaClientError(
            "broker_timeout",
            "paper broker submit timed out after request write",
            retryable=True,
            ambiguous=True,
            pause_new_risk=True,
        )
    )
    adapter = build_fake_alpaca_paper_adapter(client=client)

    result = adapter.submit_entry_order(_intent())

    assert result.status == "ambiguous"
    assert result.error is not None
    assert result.error.code == "broker_timeout"
    assert result.error.pause_new_risk is True


def test_partial_fill_reports_required_protective_stop_quantity() -> None:
    adapter = build_fake_alpaca_paper_adapter(
        client=FakeAlpacaClient(next_submit_status="partially_filled", next_submit_filled_qty=4)
    )

    result = adapter.submit_entry_order(_intent())

    assert result.status == "succeeded"
    assert result.order is not None
    assert result.order.status == "partially_filled"
    assert result.protective_stop_required_quantity == 4.0


def test_cancel_paper_order_and_submit_verify_protective_stop_use_fake_client() -> None:
    client = FakeAlpacaClient(orders=(_order_payload(),))
    adapter = build_fake_alpaca_paper_adapter(client=client)

    cancel_result = adapter.cancel_order("strategy-AAPL-buy-20260504-1-abc123")
    stop_result = adapter.submit_protective_stop(_intent(), filled_quantity=4)
    verify_result = adapter.verify_protective_stop(
        symbol="AAPL",
        required_quantity=4,
        client_order_id="strategy-AAPL-buy-20260504-1-abc123-stop",
    )

    assert cancel_result.status == "succeeded"
    assert client.cancelled_broker_order_ids == ["broker-order-1"]
    assert stop_result.status == "succeeded"
    assert client.submitted_order_requests[-1] == {
        "symbol": "AAPL",
        "side": "sell",
        "type": "stop",
        "time_in_force": "gtc",
        "qty": "4",
        "stop_price": "174.2",
        "client_order_id": "strategy-AAPL-buy-20260504-1-abc123-stop",
        "extended_hours": False,
    }
    assert verify_result.protected is True


def test_verify_protective_stop_fails_structurally_when_stop_missing() -> None:
    adapter = build_fake_alpaca_paper_adapter(client=FakeAlpacaClient())

    result = adapter.verify_protective_stop(symbol="AAPL", required_quantity=4)

    assert result.status == "failed"
    assert result.protected is False
    assert result.error is not None
    assert result.error.code == "missing_protective_stop"


def test_stream_disconnect_and_rest_fallback_unavailable_are_structured() -> None:
    adapter = build_fake_alpaca_paper_adapter(
        client=FakeAlpacaClient(
            stream_error=AlpacaClientError("stream_disconnect", "stream disconnected"),
            rest_error=AlpacaClientError("rest_fallback_unavailable", "REST fallback unavailable"),
        )
    )

    stream_result = adapter.stream_connection_result()
    rest_result = adapter.rest_fallback_status()

    assert stream_result.connected is False
    assert stream_result.error is not None
    assert stream_result.error.code == "stream_disconnect"
    assert rest_result.available is False
    assert rest_result.error is not None
    assert rest_result.error.code == "rest_fallback_unavailable"


def test_fake_broker_snapshot_feeds_reconciliation_clean_and_mismatch_paths() -> None:
    adapter = build_fake_alpaca_paper_adapter(client=FakeAlpacaClient(orders=(_order_payload(),)))
    broker_snapshot = BrokerSnapshot(
        account=adapter.account_snapshot(),
        open_orders=adapter.open_orders(),
        as_of=DEFAULT_AS_OF,
    )
    internal_account = InternalAccountSnapshot(equity=100_000.0, cash=90_000.0, as_of=DEFAULT_AS_OF)
    internal_order = InternalOrder(
        order_id="internal-order-1",
        client_order_id="strategy-AAPL-buy-20260504-1-abc123",
        symbol="AAPL",
        side="buy",
        quantity=10,
        status="open",
        broker_order_id="broker-order-1",
    )

    clean = compare_broker_and_internal(
        broker_snapshot=broker_snapshot,
        internal_snapshot=InternalLedgerSnapshot(
            account=internal_account,
            orders=(internal_order,),
            as_of=DEFAULT_AS_OF,
        ),
        as_of=DEFAULT_AS_OF,
        protective_stop_config=load_app_config().protective_stop,
    )
    mismatch = compare_broker_and_internal(
        broker_snapshot=broker_snapshot,
        internal_snapshot=InternalLedgerSnapshot(account=internal_account, as_of=DEFAULT_AS_OF),
        as_of=DEFAULT_AS_OF,
        protective_stop_config=load_app_config().protective_stop,
    )

    assert clean.clean is True
    assert "unknown_open_broker_order" in {
        item.mismatch_type for item in mismatch.mismatches
    }
