from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from uuid import uuid4

from apps.api.app.control_plane import read_ledger_dashboard_snapshot
from packages.control_plane.service import LedgerDashboardReadModelProvider
from packages.execution.models import ExecutionIntent
from packages.ledger.connection import connect_in_memory_sqlite
from packages.ledger.repositories import SQLiteLedgerRepository

NOW = datetime(2026, 5, 6, 12, 0, tzinfo=UTC)


def _repo() -> SQLiteLedgerRepository:
    return SQLiteLedgerRepository(connect_in_memory_sqlite())


def _intent() -> ExecutionIntent:
    return ExecutionIntent(
        decision_id=uuid4(),
        symbol="AAPL",
        side="buy",
        asset_class="equity",
        quantity=2,
        entry_order_type="limit",
        limit_price=180.5,
        stop_loss_price=174.0,
        time_in_force="day",
        strategy_version="strategy_v0_3",
        risk_config_version="risk_v0_3",
        autonomy_level=2,
        requires_protective_stop=True,
        max_acceptable_slippage_bps=25,
        expires_at=NOW + timedelta(hours=2),
        client_order_id_root="strategy-AAPL-buy-20260506-1",
        temporal_workflow_id="workflow-intent-1",
        status="risk_approved",
    )


def test_ledger_dashboard_read_model_returns_safe_empty_statuses() -> None:
    snapshot = LedgerDashboardReadModelProvider(_repo(), as_of=NOW).snapshot()

    assert snapshot.system_state.data_source == "database_read_model"
    assert snapshot.system_state.live_trading_enabled is False
    assert snapshot.system_state.autonomous_execution_enabled is False
    assert snapshot.kill_switch.new_risk_allowed is False
    assert snapshot.risk_status.new_risk_allowed is False
    assert snapshot.reconciliation_status.clean is False
    assert snapshot.reconciliation_status.pause_new_risk_recommended is True
    assert snapshot.active_execution_intents == ()
    assert snapshot.reports == ()


def test_ledger_dashboard_read_model_reads_repository_records() -> None:
    repository = _repo()
    repository.insert_execution_intent(_intent(), execution_intent_id="intent-1")
    repository.insert_order(
        order_id="order-1",
        client_order_id="client-order-1",
        broker_order_id="broker-order-1",
        symbol="AAPL",
        side="buy",
        order_type="limit",
        time_in_force="day",
        quantity=2,
        status="accepted",
        raw_broker_payload={"filled_quantity": 1},
        created_at=NOW,
    )
    repository.insert_order(
        order_id="stop-order-1",
        client_order_id="stop-client-order-1",
        broker_order_id="broker-stop-order-1",
        symbol="AAPL",
        side="sell",
        order_type="stop",
        time_in_force="gtc",
        quantity=1,
        stop_price=174.0,
        status="submitted",
        created_at=NOW,
    )
    repository.upsert_position(
        symbol="AAPL",
        quantity=1,
        average_entry_price=180.4,
        protective_stop_order_id="stop-order-1",
        opened_at=NOW,
    )
    repository.insert_broker_reconciliation_snapshot(
        reconciliation_id="recon-1",
        temporal_workflow_id="workflow-recon-1",
        account_snapshot={"equity": 100000},
        broker_positions=[],
        internal_positions=[],
        broker_orders=[],
        internal_orders=[],
        mismatches=[],
        status="clean",
        created_at=NOW,
    )
    repository.insert_system_event(
        event_id="incident-1",
        event_type="worker_incident",
        severity="warning",
        source_component="worker",
        message="Worker unavailable",
        created_at=NOW,
    )
    repository.insert_report(
        report_id="report-1",
        report_type="daily",
        report_date=date(2026, 5, 6),
        status="dry_run",
        payload={"report_type": "daily"},
        markdown="# Daily",
        created_at=NOW,
    )

    snapshot = LedgerDashboardReadModelProvider(repository, as_of=NOW).snapshot()

    assert snapshot.reconciliation_status.clean is True
    assert snapshot.active_execution_intents[0].intent_id == "intent-1"
    assert snapshot.open_orders[0].client_order_id == "client-order-1"
    assert snapshot.open_orders[0].filled_quantity == 1
    assert snapshot.open_positions[0].protective_stop_confirmed is True
    assert snapshot.recent_incidents[0].incident_id == "incident-1"
    assert snapshot.reports[0].report_id == "report-1"


def test_api_helper_reads_ledger_dashboard_snapshot_without_provider_side_effects() -> None:
    snapshot = read_ledger_dashboard_snapshot(_repo())

    assert snapshot.system_state.data_source == "database_read_model"
    assert snapshot.system_state.live_trading_enabled is False
    assert snapshot.risk_status.new_risk_allowed is False
