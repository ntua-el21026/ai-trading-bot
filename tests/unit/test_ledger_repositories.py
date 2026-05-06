from __future__ import annotations

import json
import sqlite3
from datetime import UTC, date, datetime, timedelta
from uuid import uuid4

import pytest

from packages.ai.fallback import neutral_research_output
from packages.ai.persistence import build_ai_research_persistence_payload
from packages.core.config import load_app_config
from packages.data.payloads import build_raw_provider_payload, hash_payload
from packages.execution.models import ExecutionIntent
from packages.ledger.connection import connect_in_memory_sqlite
from packages.ledger.repositories import SQLiteLedgerRepository


def _repo() -> SQLiteLedgerRepository:
    return SQLiteLedgerRepository(connect_in_memory_sqlite())


def _analysis_time() -> datetime:
    return datetime(2026, 5, 5, 12, 0, tzinfo=UTC)


def _execution_intent(
    *,
    client_order_id_root: str = "strategy-AAPL-buy-20260505-1-abc",
) -> ExecutionIntent:
    return ExecutionIntent(
        decision_id=uuid4(),
        symbol="AAPL",
        side="buy",
        asset_class="equity",
        quantity=3,
        entry_order_type="limit",
        limit_price=180.50,
        stop_loss_price=174.20,
        time_in_force="day",
        strategy_version="regime_filtered_breakout_v0_3",
        risk_config_version="risk_v0_3",
        autonomy_level=2,
        requires_protective_stop=True,
        max_acceptable_slippage_bps=25,
        expires_at=_analysis_time() + timedelta(hours=2),
        client_order_id_root=client_order_id_root,
        status="risk_approved",
        temporal_workflow_id="workflow-intent-1",
    )


def test_raw_provider_payload_persistence_and_hash_uniqueness() -> None:
    repository = _repo()
    payload = build_raw_provider_payload(
        provider="fixture",
        endpoint="daily-bars",
        symbol="AAPL",
        payload={"symbol": "AAPL", "close": 180.5},
        fetched_at=_analysis_time(),
    )

    record = repository.insert_raw_provider_payload(payload)
    lookup = repository.get_raw_provider_payload_by_hash(
        provider="fixture",
        endpoint="daily-bars",
        payload_hash=payload.payload_hash,
    )

    assert lookup == record
    assert record.raw_payload == {"close": 180.5, "symbol": "AAPL"}
    assert record.payload_hash == payload.payload_hash
    with pytest.raises(sqlite3.IntegrityError):
        repository.insert_raw_provider_payload(payload)


def test_ai_research_output_persistence_preserves_hashes_and_payloads() -> None:
    repository = _repo()
    output = neutral_research_output(
        symbol="AAPL",
        analysis_at=_analysis_time(),
        prompt_version="ai_trade_research_v0_3",
        schema_version="ai_trade_research_schema_v0_3",
        model_version="fixture-model",
        fallback_reason="no_news_found",
    )
    raw_prompt = "Analyze AAPL supplied candidate news only."
    raw_output = json.dumps(output.model_dump(mode="json"), sort_keys=True)
    payload = build_ai_research_persistence_payload(
        symbol="AAPL",
        created_at=_analysis_time(),
        raw_prompt=raw_prompt,
        raw_ai_output=raw_output,
        parsed_output=output,
    )

    record = repository.insert_ai_research_output(payload, output_id="ai-output-1")
    lookup = repository.get_ai_research_output("ai-output-1")

    assert lookup == record
    assert record.raw_prompt_hash == hash_payload(raw_prompt)
    assert record.raw_output_hash == hash_payload(raw_output)
    assert record.parsed_output["ai_score"] == 50
    assert record.fallback_reason == "no_news_found"


def test_execution_intent_persistence_and_client_order_root_uniqueness() -> None:
    repository = _repo()
    intent = _execution_intent()

    record = repository.insert_execution_intent(intent, execution_intent_id="intent-1")

    assert repository.get_execution_intent_by_id("intent-1") == record
    assert repository.get_execution_intent_by_client_order_id_root(
        intent.client_order_id_root
    ) == record
    assert record.payload["client_order_id_root"] == intent.client_order_id_root
    with pytest.raises(sqlite3.IntegrityError):
        repository.insert_execution_intent(intent, execution_intent_id="intent-2")


def test_order_and_fill_persistence_enforce_idempotency_constraints() -> None:
    repository = _repo()
    order = repository.insert_order(
        order_id="order-1",
        broker_order_id="broker-order-1",
        client_order_id="client-order-1",
        symbol="AAPL",
        side="buy",
        order_type="limit",
        time_in_force="day",
        quantity=3,
        limit_price=180.5,
        status="accepted",
        raw_broker_payload={"id": "broker-order-1"},
    )

    assert repository.get_order_by_client_order_id("client-order-1") == order
    with pytest.raises(sqlite3.IntegrityError):
        repository.insert_order(
            order_id="order-duplicate",
            client_order_id="client-order-1",
            symbol="AAPL",
            side="buy",
            order_type="limit",
            time_in_force="day",
            quantity=3,
            status="accepted",
        )

    fill = repository.insert_fill(
        fill_id="fill-1",
        order_id=order.order_id,
        broker_order_id="broker-order-1",
        broker_fill_id="broker-fill-1",
        symbol="AAPL",
        quantity=1,
        price=180.4,
        filled_at=_analysis_time(),
        raw_broker_payload={"fill": "broker-fill-1"},
    )
    assert fill.broker_fill_id == "broker-fill-1"
    with pytest.raises(sqlite3.IntegrityError):
        repository.insert_fill(
            fill_id="fill-duplicate",
            order_id=order.order_id,
            broker_fill_id="broker-fill-1",
            symbol="AAPL",
            quantity=1,
            price=180.4,
            filled_at=_analysis_time(),
        )

    another = repository.insert_order(
        order_id="order-2",
        client_order_id="client-order-2",
        symbol="MSFT",
        side="buy",
        order_type="limit",
        time_in_force="day",
        quantity=2,
        status="accepted",
    )
    assert another.client_order_id == "client-order-2"


def test_position_upsert_and_lookup() -> None:
    repository = _repo()

    first = repository.upsert_position(
        symbol="AAPL",
        quantity=3,
        average_entry_price=180.5,
        opened_at=_analysis_time(),
        raw_source_payload={"source": "fixture"},
    )
    second = repository.upsert_position(
        symbol="AAPL",
        quantity=4,
        average_entry_price=181.0,
        opened_at=_analysis_time(),
        raw_source_payload={"source": "updated"},
    )

    assert second.position_id == first.position_id
    assert second.quantity == 4
    assert repository.get_open_position("AAPL") == second


def test_broker_reconciliation_system_event_and_report_persistence() -> None:
    repository = _repo()

    reconciliation = repository.insert_broker_reconciliation_snapshot(
        reconciliation_id="recon-1",
        temporal_workflow_id="workflow-recon-1",
        account_snapshot={"equity": 100_000, "environment": "paper"},
        broker_positions=[{"symbol": "AAPL", "quantity": 3}],
        internal_positions=[{"symbol": "AAPL", "quantity": 3}],
        broker_orders=[],
        internal_orders=[],
        mismatches=[],
        status="clean",
        created_at=_analysis_time(),
    )
    assert repository.get_latest_broker_reconciliation() == reconciliation

    event = repository.insert_system_event(
        event_id="event-1",
        event_type="reconciliation_completed",
        severity="info",
        source_component="ledger_test",
        related_entity_type="broker_reconciliation",
        related_entity_id=reconciliation.reconciliation_id,
        message="Reconciliation snapshot persisted.",
        payload={"clean": True},
        created_at=_analysis_time(),
    )
    assert repository.list_system_events() == (event,)

    report = repository.insert_report(
        report_id="report-1",
        report_type="daily",
        report_date=date(2026, 5, 5),
        status="draft",
        payload={"orders": 0},
        markdown="# Daily Report",
        created_at=_analysis_time(),
    )
    assert repository.get_report("report-1") == report


def test_local_ledger_does_not_require_managed_database_or_change_safety_flags(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql://example.invalid/should-not-be-used")
    repository = _repo()

    assert repository.get_latest_broker_reconciliation() is None
    config = load_app_config()
    assert config.system.live_trading_enabled is False
    assert config.system.autonomous_execution_enabled is False
    assert config.execution.allow_live_orders is False
