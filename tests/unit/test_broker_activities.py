from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from uuid import UUID

from apps.workers.app.activities.broker import (
    BrokerActivityContext,
    BrokerActivityRequest,
    BrokerActivityService,
    BrokerLookupByClientOrderIdRequest,
    MapTradeUpdateEventRequest,
    SubmitPaperEntryOrderRequest,
    configure_broker_activity_service_for_tests,
    get_broker_account_snapshot,
    lookup_broker_order_by_client_order_id,
    map_trade_update_event,
    reset_broker_activity_service_for_tests,
    submit_paper_entry_order,
)
from packages.broker.fakes import FakeAlpacaClient, build_fake_alpaca_paper_adapter
from packages.execution.models import ExecutionIntent


def _context() -> BrokerActivityContext:
    return BrokerActivityContext(workflow_name="OrderLifecycleWorkflow", purpose="contract-test")


def _intent() -> ExecutionIntent:
    return ExecutionIntent(
        decision_id=UUID("00000000-0000-4000-8000-000000000001"),
        symbol="AAPL",
        side="buy",
        asset_class="equity",
        quantity=10,
        entry_order_type="limit",
        limit_price=180.5,
        stop_loss_price=174.2,
        time_in_force="day",
        strategy_version="regime_filtered_breakout_v0_3",
        risk_config_version="risk_v0_3",
        autonomy_level=2,
        requires_protective_stop=True,
        max_acceptable_slippage_bps=25,
        expires_at=datetime(2026, 5, 4, 15, 0, tzinfo=UTC),
        client_order_id_root="strategy-AAPL-buy-20260504-1-abc123",
        status="risk_approved",
        temporal_workflow_id="workflow-entry-1",
    )


def test_broker_account_activity_uses_fake_adapter_without_credentials_or_external_calls() -> None:
    result = asyncio.run(get_broker_account_snapshot(BrokerActivityRequest(context=_context())))

    assert result.status == "succeeded"
    assert result.external_calls_performed is False
    assert result.details["external_calls"] == "none"
    assert result.payload["account"]["environment"] == "paper"


def test_submit_paper_entry_activity_uses_injected_fake_adapter() -> None:
    client = FakeAlpacaClient()
    service = BrokerActivityService(
        build_fake_alpaca_paper_adapter(client=client),
        external_calls_performed=False,
    )
    configure_broker_activity_service_for_tests(service)
    try:
        result = asyncio.run(
            submit_paper_entry_order(
                SubmitPaperEntryOrderRequest(context=_context(), intent=_intent())
            )
        )
    finally:
        reset_broker_activity_service_for_tests()

    assert result.status == "succeeded"
    assert result.external_calls_performed is False
    assert client.submitted_order_requests[0]["client_order_id"] == (
        "strategy-AAPL-buy-20260504-1-abc123"
    )


def test_lookup_broker_order_activity_returns_structured_not_found() -> None:
    result = asyncio.run(
        lookup_broker_order_by_client_order_id(
            BrokerLookupByClientOrderIdRequest(
                context=_context(),
                client_order_id="missing-client-order",
            )
        )
    )

    assert result.status == "not_found"
    assert result.error is not None
    assert result.error.code == "order_not_found"
    assert result.external_calls_performed is False


def test_map_trade_update_activity_is_pure_mapping_boundary() -> None:
    payload = {
        "event": "fill",
        "timestamp": "2026-05-04T14:12:30Z",
        "price": "180.25",
        "qty": "10",
        "order": {
            "id": "broker-order-1",
            "client_order_id": "strategy-AAPL-buy-20260504-1-abc123",
            "symbol": "AAPL",
            "side": "buy",
            "asset_class": "equity",
            "qty": "10",
            "filled_qty": "10",
            "type": "limit",
            "time_in_force": "day",
            "status": "filled",
            "limit_price": "180.50",
        },
    }

    result = asyncio.run(
        map_trade_update_event(MapTradeUpdateEventRequest(context=_context(), payload=payload))
    )

    assert result.status == "succeeded"
    assert result.external_calls_performed is False
    assert result.payload["event"]["event_type"] == "fill"
