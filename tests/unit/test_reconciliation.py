from datetime import UTC, datetime, timedelta

from packages.broker.models import (
    BrokerAccountSnapshot,
    BrokerFill,
    BrokerOrder,
    BrokerOrderPurpose,
    BrokerOrderStatus,
    BrokerPosition,
    BrokerProtectiveStop,
    BrokerSnapshot,
)
from packages.core.config import load_app_config
from packages.reconciliation.models import (
    InternalAccountSnapshot,
    InternalFill,
    InternalLedgerSnapshot,
    InternalOrder,
    InternalOrderStatus,
    InternalPosition,
    ReconciliationResult,
)
from packages.reconciliation.service import compare_broker_and_internal

AS_OF = datetime(2026, 5, 4, 14, 30, tzinfo=UTC)


def _account(equity: float = 100_000.0) -> BrokerAccountSnapshot:
    return BrokerAccountSnapshot(
        account_id="paper-account",
        environment="paper",
        equity=equity,
        cash=90_000.0,
        as_of=AS_OF,
    )


def _internal_account(equity: float = 100_000.0) -> InternalAccountSnapshot:
    return InternalAccountSnapshot(equity=equity, cash=90_000.0, as_of=AS_OF)


def _broker_order(
    client_order_id: str = "entry-AAPL-1",
    *,
    symbol: str = "AAPL",
    broker_order_id: str = "broker-entry-1",
    status: BrokerOrderStatus = "accepted",
    purpose: BrokerOrderPurpose = "entry",
) -> BrokerOrder:
    return BrokerOrder(
        broker_order_id=broker_order_id,
        client_order_id=client_order_id,
        symbol=symbol,
        side="buy",
        asset_class="equity",
        quantity=10.0,
        filled_quantity=0.0,
        order_type="limit",
        time_in_force="day",
        status=status,
        limit_price=100.0,
        purpose=purpose,
    )


def _internal_order(
    client_order_id: str = "entry-AAPL-1",
    *,
    symbol: str = "AAPL",
    broker_order_id: str = "broker-entry-1",
    status: InternalOrderStatus = "open",
) -> InternalOrder:
    return InternalOrder(
        order_id=f"internal-{client_order_id}",
        client_order_id=client_order_id,
        symbol=symbol,
        side="buy",
        quantity=10.0,
        filled_quantity=0.0,
        status=status,
        broker_order_id=broker_order_id,
        temporal_workflow_id=f"workflow-{client_order_id}",
        is_entry_order=True,
    )


def _position(symbol: str = "AAPL", quantity: float = 10.0) -> BrokerPosition:
    return BrokerPosition(
        symbol=symbol,
        asset_class="equity",
        quantity=quantity,
        avg_entry_price=100.0,
        opened_at=AS_OF - timedelta(seconds=10),
    )


def _internal_position(symbol: str = "AAPL", quantity: float = 10.0) -> InternalPosition:
    return InternalPosition(
        symbol=symbol,
        quantity=quantity,
        avg_entry_price=100.0,
        opened_at=AS_OF - timedelta(seconds=10),
        protective_stop_client_order_id=f"stop-{symbol}-1",
        temporal_workflow_id=f"position-{symbol}",
    )


def _stop(
    symbol: str = "AAPL",
    quantity: float = 10.0,
    confirmed: bool = True,
) -> BrokerProtectiveStop:
    return BrokerProtectiveStop(
        broker_order_id=f"broker-stop-{symbol}",
        client_order_id=f"stop-{symbol}-1",
        symbol=symbol,
        quantity=quantity,
        stop_price=95.0,
        status="accepted",
        confirmed=confirmed,
        submitted_at=AS_OF - timedelta(seconds=8),
    )


def _fill() -> BrokerFill:
    return BrokerFill(
        broker_order_id="broker-entry-1",
        client_order_id="entry-AAPL-1",
        symbol="AAPL",
        side="buy",
        quantity=10.0,
        price=100.0,
        filled_at=AS_OF - timedelta(seconds=10),
    )


def _internal_fill() -> InternalFill:
    return InternalFill(
        broker_order_id="broker-entry-1",
        client_order_id="entry-AAPL-1",
        symbol="AAPL",
        quantity=10.0,
        price=100.0,
        filled_at=AS_OF - timedelta(seconds=10),
    )


def _broker_snapshot(**updates: object) -> BrokerSnapshot:
    data = {
        "account": _account(),
        "open_orders": (),
        "recent_fills": (_fill(),),
        "positions": (_position(),),
        "protective_stops": (_stop(),),
        "as_of": AS_OF,
    }
    data.update(updates)
    return BrokerSnapshot.model_validate(data)


def _internal_snapshot(**updates: object) -> InternalLedgerSnapshot:
    data = {
        "account": _internal_account(),
        "orders": (_internal_order(status="filled"),),
        "fills": (_internal_fill(),),
        "positions": (_internal_position(),),
        "as_of": AS_OF,
    }
    data.update(updates)
    return InternalLedgerSnapshot.model_validate(data)


def _reconcile(
    broker_snapshot: BrokerSnapshot,
    internal_snapshot: InternalLedgerSnapshot,
) -> ReconciliationResult:
    return compare_broker_and_internal(
        broker_snapshot=broker_snapshot,
        internal_snapshot=internal_snapshot,
        as_of=AS_OF,
        protective_stop_config=load_app_config().protective_stop,
    )


def test_reconciliation_clean_state_has_risk_check_input_true() -> None:
    result = _reconcile(_broker_snapshot(), _internal_snapshot())

    assert result.clean is True
    assert result.broker_reconciliation_clean is True
    assert result.pause_new_risk_recommended is False


def test_reconciliation_detects_broker_position_without_internal_position() -> None:
    result = _reconcile(_broker_snapshot(), _internal_snapshot(positions=()))

    assert "broker_position_without_internal_position" in _types(result)
    assert result.pause_new_risk_recommended is True


def test_reconciliation_detects_internal_position_without_broker_position() -> None:
    result = _reconcile(_broker_snapshot(positions=()), _internal_snapshot())

    assert "internal_position_without_broker_position" in _types(result)
    assert result.pause_new_risk_recommended is True


def test_missing_protective_stop_recommends_pause_or_flatten_by_age() -> None:
    critical_position = _position()
    flatten_position = BrokerPosition(
        symbol="AAPL",
        asset_class="equity",
        quantity=10.0,
        avg_entry_price=100.0,
        opened_at=AS_OF - timedelta(seconds=61),
    )

    critical = _reconcile(
        _broker_snapshot(positions=(critical_position,), protective_stops=()),
        _internal_snapshot(),
    )
    flatten = _reconcile(
        _broker_snapshot(positions=(flatten_position,), protective_stops=()),
        _internal_snapshot(
            positions=(
                InternalPosition(
                    symbol="AAPL",
                    quantity=10.0,
                    avg_entry_price=100.0,
                    opened_at=AS_OF - timedelta(seconds=61),
                ),
            )
        ),
    )

    assert "missing_protective_stop" in _types(critical)
    assert critical.incidents[0].recommended_action == "investigate"
    assert flatten.incidents[0].recommended_action == "flatten_if_safe"
    assert flatten.pause_new_risk_recommended is True


def test_missing_protective_stop_with_unknown_age_pauses_without_flattening() -> None:
    result = _reconcile(
        _broker_snapshot(
            positions=(
                BrokerPosition(
                    symbol="AAPL",
                    asset_class="equity",
                    quantity=10.0,
                    avg_entry_price=100.0,
                ),
            ),
            protective_stops=(),
        ),
        _internal_snapshot(
            positions=(
                InternalPosition(
                    symbol="AAPL",
                    quantity=10.0,
                    avg_entry_price=100.0,
                ),
            )
        ),
    )

    assert "missing_protective_stop" in _types(result)
    assert result.incidents[0].recommended_action == "pause_new_risk"
    assert result.pause_new_risk_recommended is True


def test_reconciliation_detects_duplicate_and_unknown_open_orders() -> None:
    result = _reconcile(
        _broker_snapshot(
            open_orders=(
                _broker_order("entry-AAPL-1", broker_order_id="broker-entry-1"),
                _broker_order("entry-AAPL-2", broker_order_id="broker-entry-2"),
            )
        ),
        _internal_snapshot(orders=(_internal_order("entry-AAPL-1"),)),
    )

    assert "duplicate_open_entry_orders" in _types(result)
    assert "unknown_open_broker_order" in _types(result)
    assert result.pause_new_risk_recommended is True


def test_reconciliation_detects_short_fill_quantity_price_account_and_stale_mismatches() -> None:
    result = _reconcile(
        _broker_snapshot(
            account=_account(102_000.0),
            recent_fills=(_fill(),),
            positions=(
                BrokerPosition(
                    symbol="AAPL",
                    asset_class="equity",
                    quantity=-10.0,
                    avg_entry_price=105.0,
                    opened_at=AS_OF - timedelta(seconds=10),
                ),
            ),
            as_of=AS_OF - timedelta(seconds=120),
        ),
        _internal_snapshot(fills=(), as_of=AS_OF - timedelta(seconds=120)),
    )

    mismatch_types = _types(result)
    assert "account_equity_mismatch" in mismatch_types
    assert "fill_not_recorded_internal" in mismatch_types
    assert "unexpected_short_position" in mismatch_types
    assert "quantity_mismatch" in mismatch_types
    assert "avg_entry_price_mismatch" in mismatch_types
    assert "stale_broker_snapshot" in mismatch_types
    assert "stale_internal_snapshot" in mismatch_types


def test_reconciliation_detects_unsupported_broker_asset_class() -> None:
    result = _reconcile(
        _broker_snapshot(
            positions=(
                BrokerPosition(
                    symbol="AAPL",
                    asset_class="crypto",
                    quantity=10.0,
                    avg_entry_price=100.0,
                    opened_at=AS_OF - timedelta(seconds=10),
                ),
            )
        ),
        _internal_snapshot(),
    )

    assert "unsupported_broker_asset_class" in _types(result)
    assert result.pause_new_risk_recommended is True


def test_reconciliation_detects_temporal_workflow_state_inconsistency() -> None:
    result = _reconcile(
        _broker_snapshot(open_orders=(_broker_order(),), recent_fills=(), positions=()),
        _internal_snapshot(
            account=_internal_account(),
            orders=(_internal_order(),),
            fills=(),
            positions=(),
            order_workflow_status_by_client_order_id={"entry-AAPL-1": "completed"},
        ),
    )

    assert "temporal_workflow_state_inconsistent" in _types(result)


def _types(result: ReconciliationResult) -> set[str]:
    return {mismatch.mismatch_type for mismatch in result.mismatches}
