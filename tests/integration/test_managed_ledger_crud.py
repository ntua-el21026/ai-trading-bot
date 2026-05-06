from __future__ import annotations

import json
import os
from datetime import UTC, date, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from psycopg import errors

from packages.ai.fallback import neutral_research_output
from packages.ai.persistence import build_ai_research_persistence_payload
from packages.data.payloads import build_raw_provider_payload, hash_payload
from packages.execution.models import ExecutionIntent
from packages.ledger.postgres_repository import PostgresLedgerRepository
from packages.ledger.runtime import (
    LedgerDatabaseConfig,
    check_postgres_ledger_schema,
    connect_runtime_postgres,
    require_managed_db_tests_enabled,
)


class _RollbackManagedCrud(Exception):
    """Internal sentinel used to roll back all managed CRUD fixture records."""


@pytest.mark.integration
@pytest.mark.skipif(
    os.environ.get("RUN_MANAGED_DB_TESTS") != "1" or not os.environ.get("DATABASE_URL"),
    reason="managed CRUD checks require RUN_MANAGED_DB_TESTS=1 and DATABASE_URL",
)
def test_managed_postgres_repository_crud_uses_isolated_rollback_records() -> None:
    require_managed_db_tests_enabled()
    config = LedgerDatabaseConfig.from_env()
    run_id = uuid4().hex
    observed_report_id: str | None = None

    with connect_runtime_postgres(config) as connection:
        schema = check_postgres_ledger_schema(connection)
        assert schema.ok

        try:
            with connection.transaction():
                repository = PostgresLedgerRepository(connection)
                now = datetime(2026, 5, 5, 12, 0, tzinfo=UTC)

                payload = build_raw_provider_payload(
                    provider="managed-crud-fixture",
                    endpoint=f"daily-bars-{run_id}",
                    symbol="AAPL",
                    payload={"run_id": run_id, "symbol": "AAPL", "close": 180.5},
                    fetched_at=now,
                )
                raw_record = repository.insert_raw_provider_payload(payload)
                assert repository.get_raw_provider_payload_by_hash(
                    provider=payload.provider,
                    endpoint=payload.endpoint,
                    payload_hash=payload.payload_hash,
                ) == raw_record
                assert isinstance(raw_record.raw_payload, dict)
                assert raw_record.raw_payload["run_id"] == run_id
                with pytest.raises(errors.UniqueViolation):
                    with connection.transaction():
                        repository.insert_raw_provider_payload(payload)

                ai_output = neutral_research_output(
                    symbol="AAPL",
                    analysis_at=now,
                    prompt_version="ai_trade_research_v0_3",
                    schema_version="ai_trade_research_schema_v0_3",
                    model_version="fixture-model",
                    fallback_reason="no_news_found",
                )
                raw_prompt = f"Analyze AAPL supplied candidate news only. run_id={run_id}"
                raw_ai_output = json.dumps(ai_output.model_dump(mode="json"), sort_keys=True)
                ai_payload = build_ai_research_persistence_payload(
                    symbol="AAPL",
                    created_at=now,
                    raw_prompt=raw_prompt,
                    raw_ai_output=raw_ai_output,
                    parsed_output=ai_output,
                )
                ai_record = repository.insert_ai_research_output(
                    ai_payload,
                    output_id=str(uuid4()),
                )
                assert repository.get_ai_research_output(ai_record.output_id) == ai_record
                assert ai_record.raw_prompt_hash == hash_payload(raw_prompt)
                assert ai_record.raw_output_hash == hash_payload(raw_ai_output)

                candidate = repository.insert_trade_candidate(
                    candidate_id=str(uuid4()),
                    symbol="AAPL",
                    trading_date=date(2026, 5, 5),
                    strategy_version="regime_filtered_breakout_v0_3",
                    candidate_status="accepted",
                    technical_score=75.0,
                    relative_strength_score=70.0,
                    score_payload={"run_id": run_id},
                    reason_payload={"fixture": True},
                )
                decision = repository.insert_trade_decision(
                    decision_id=str(uuid4()),
                    candidate_id=candidate.candidate_id,
                    symbol="AAPL",
                    decision_status="approved",
                    final_score=72.5,
                    deterministic_decision_payload={"run_id": run_id},
                    ai_output_id=ai_record.output_id,
                    created_at=now,
                )

                client_order_root = f"managed-crud-AAPL-buy-{run_id}"
                intent = _execution_intent(
                    decision_id=UUID(decision.decision_id),
                    client_order_id_root=client_order_root,
                    now=now,
                )
                intent_record = repository.insert_execution_intent(
                    intent,
                    execution_intent_id=str(uuid4()),
                )
                assert repository.get_execution_intent_by_id(
                    intent_record.execution_intent_id
                ) == intent_record
                assert repository.get_execution_intent_by_client_order_id_root(
                    client_order_root
                ) == intent_record
                with pytest.raises(errors.UniqueViolation):
                    with connection.transaction():
                        repository.insert_execution_intent(
                            intent,
                            execution_intent_id=str(uuid4()),
                        )

                risk_check = repository.insert_risk_check(
                    risk_check_id=str(uuid4()),
                    decision_id=decision.decision_id,
                    execution_intent_id=intent_record.execution_intent_id,
                    symbol="AAPL",
                    passed=True,
                    reason_codes=(),
                    risk_config_version="risk_v0_3",
                    input_snapshot={"run_id": run_id},
                    result_payload={"passed": True},
                    created_at=now,
                )
                assert risk_check.passed is True

                order = repository.insert_order(
                    order_id=str(uuid4()),
                    execution_intent_id=intent_record.execution_intent_id,
                    broker_order_id=f"broker-order-{run_id}",
                    client_order_id=f"client-order-{run_id}",
                    symbol="AAPL",
                    side="buy",
                    order_type="limit",
                    time_in_force="day",
                    quantity=3,
                    limit_price=180.5,
                    status="accepted",
                    raw_broker_payload={"run_id": run_id},
                    created_at=now,
                    updated_at=now,
                )
                assert repository.get_order_by_client_order_id(order.client_order_id) == order
                with pytest.raises(errors.UniqueViolation):
                    with connection.transaction():
                        repository.insert_order(
                            order_id=str(uuid4()),
                            client_order_id=order.client_order_id,
                            symbol="AAPL",
                            side="buy",
                            order_type="limit",
                            time_in_force="day",
                            quantity=3,
                            status="accepted",
                        )

                fill = repository.insert_fill(
                    fill_id=str(uuid4()),
                    order_id=order.order_id,
                    broker_order_id=order.broker_order_id,
                    broker_fill_id=f"broker-fill-{run_id}",
                    symbol="AAPL",
                    quantity=1,
                    price=180.4,
                    filled_at=now,
                    raw_broker_payload={"run_id": run_id},
                    created_at=now,
                )
                assert fill.broker_fill_id == f"broker-fill-{run_id}"
                with pytest.raises(errors.UniqueViolation):
                    with connection.transaction():
                        repository.insert_fill(
                            fill_id=str(uuid4()),
                            order_id=order.order_id,
                            broker_fill_id=fill.broker_fill_id,
                            symbol="AAPL",
                            quantity=1,
                            price=180.4,
                            filled_at=now,
                        )

                first_position = repository.upsert_position(
                    symbol=f"ZZZ{run_id[:6].upper()}",
                    quantity=1,
                    average_entry_price=180.4,
                    opened_at=now,
                    raw_source_payload={"run_id": run_id},
                )
                second_position = repository.upsert_position(
                    symbol=first_position.symbol,
                    quantity=2,
                    average_entry_price=181.0,
                    opened_at=now,
                    raw_source_payload={"run_id": run_id, "updated": True},
                )
                assert second_position.position_id == first_position.position_id
                assert repository.get_open_position(first_position.symbol) == second_position

                reconciliation = repository.insert_broker_reconciliation_snapshot(
                    reconciliation_id=str(uuid4()),
                    temporal_workflow_id=f"managed-crud-recon-{run_id}",
                    account_snapshot={"run_id": run_id, "equity": 100000},
                    broker_positions=[{"symbol": first_position.symbol, "quantity": 2}],
                    internal_positions=[second_position.model_dump(mode="json")],
                    broker_orders=[],
                    internal_orders=[],
                    mismatches=[],
                    status="clean",
                    created_at=now,
                )
                assert repository.get_latest_broker_reconciliation() == reconciliation

                event = repository.insert_system_event(
                    event_id=str(uuid4()),
                    event_type="managed_crud_incident_fixture",
                    severity="warning",
                    source_component="managed_db_crud_test",
                    related_entity_type="execution_intent",
                    related_entity_id=intent_record.execution_intent_id,
                    message="Managed CRUD fixture event.",
                    payload={"run_id": run_id},
                    created_at=now,
                )
                assert event in repository.list_system_events(limit=25)
                assert event in repository.list_recent_incidents(limit=25)

                report = repository.insert_report(
                    report_id=str(uuid4()),
                    report_type="daily",
                    report_date=date(2026, 5, 5),
                    status="draft",
                    payload={"run_id": run_id},
                    markdown="# Managed CRUD Fixture",
                    created_at=now,
                )
                observed_report_id = report.report_id
                assert repository.get_report(report.report_id) == report

                raise _RollbackManagedCrud
        except _RollbackManagedCrud:
            pass

        if observed_report_id is not None:
            with connection.transaction():
                repository = PostgresLedgerRepository(connection)
                assert repository.get_report(observed_report_id) is None


def _execution_intent(
    *,
    decision_id: UUID,
    client_order_id_root: str,
    now: datetime,
) -> ExecutionIntent:
    return ExecutionIntent(
        decision_id=decision_id,
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
        expires_at=now + timedelta(hours=2),
        client_order_id_root=client_order_id_root,
        status="risk_approved",
        temporal_workflow_id="managed-crud-workflow",
    )
