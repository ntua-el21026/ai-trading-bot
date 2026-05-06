from __future__ import annotations

import asyncio
import json
from collections.abc import Iterator
from datetime import UTC, date, datetime, timedelta
from uuid import uuid4

import pytest
from pydantic import ValidationError

from apps.workers.app.activities.ledger import (
    LedgerActivityService,
    configure_ledger_activity_service_for_tests,
    get_active_execution_intents,
    get_latest_reconciliation_status,
    get_open_positions,
    get_recent_incidents,
    persist_ai_research_outputs,
    persist_broker_reconciliation,
    persist_data_refresh_result,
    persist_execution_intent,
    persist_fill_event,
    persist_order_event,
    persist_position_snapshot,
    persist_raw_provider_payload,
    persist_report,
    persist_risk_check,
    persist_system_event,
    persist_trade_candidates,
    persist_trade_decision,
    reset_ledger_activity_service_for_tests,
)
from apps.workers.app.activities.models import (
    AIResearchOutputPersistenceRequest,
    BrokerReconciliationPersistenceRequest,
    BrokerReconciliationSnapshotPayload,
    DataRefreshPersistenceRequest,
    ExecutionIntentPersistenceRequest,
    FillAuditPayload,
    FillEventPersistenceRequest,
    LedgerActivityContext,
    LedgerActivityResult,
    LedgerReadRequest,
    OrderAuditPayload,
    OrderEventPersistenceRequest,
    PositionSnapshotPayload,
    PositionSnapshotPersistenceRequest,
    RawProviderPayloadPersistenceRequest,
    ReportPayload,
    ReportPersistenceRequest,
    RiskCheckPayload,
    RiskCheckPersistenceRequest,
    SystemEventPayload,
    SystemEventPersistenceRequest,
    TradeCandidatePayload,
    TradeCandidatePersistenceRequest,
    TradeDecisionPayload,
    TradeDecisionPersistenceRequest,
)
from apps.workers.app.types import ActivityPlaceholderInput, ActivityPlaceholderResult
from packages.ai.fallback import neutral_research_output
from packages.ai.persistence import build_ai_research_persistence_payload
from packages.data.payloads import build_raw_provider_payload, hash_payload
from packages.execution.models import ExecutionIntent
from packages.ledger.connection import connect_in_memory_sqlite
from packages.ledger.repositories import SQLiteLedgerRepository


@pytest.fixture
def repository() -> SQLiteLedgerRepository:
    return SQLiteLedgerRepository(connect_in_memory_sqlite())


@pytest.fixture(autouse=True)
def configured_activity_service(repository: SQLiteLedgerRepository) -> Iterator[None]:
    configure_ledger_activity_service_for_tests(LedgerActivityService(repository))
    yield
    reset_ledger_activity_service_for_tests()


def _context() -> LedgerActivityContext:
    return LedgerActivityContext(
        workflow_name="Milestone13TestWorkflow",
        purpose="unit-test",
        request_id="request-1",
        occurred_at=_now(),
    )


def _now() -> datetime:
    return datetime(2026, 5, 6, 12, 0, tzinfo=UTC)


def _execution_intent() -> ExecutionIntent:
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
        expires_at=_now() + timedelta(hours=2),
        client_order_id_root="strategy-AAPL-buy-20260506-1-abc",
        status="risk_approved",
        temporal_workflow_id="workflow-intent-1",
    )


def _require_ledger_result(
    result: ActivityPlaceholderResult | LedgerActivityResult,
) -> LedgerActivityResult:
    assert isinstance(result, LedgerActivityResult)
    return result


def test_activity_models_validate_symbols_and_timestamps() -> None:
    with pytest.raises(ValidationError):
        TradeCandidatePayload(
            symbol="aapl",
            trading_date=date(2026, 5, 6),
            strategy_version="strategy-v1",
            candidate_status="accepted",
        )
    with pytest.raises(ValidationError):
        FillAuditPayload(
            order_id="order-1",
            symbol="AAPL",
            quantity=1,
            price=180.0,
            filled_at=datetime(2026, 5, 6, 12, 0),
        )


def test_raw_provider_payload_and_data_refresh_activities_persist_local_ledger(
    repository: SQLiteLedgerRepository,
) -> None:
    raw_payload = build_raw_provider_payload(
        provider="fixture",
        endpoint="daily-bars",
        symbol="AAPL",
        payload={"symbol": "AAPL", "close": 180.5},
        fetched_at=_now(),
    )

    raw_result = asyncio.run(
        persist_raw_provider_payload(
            RawProviderPayloadPersistenceRequest(context=_context(), payloads=(raw_payload,))
        )
    )
    refresh_result = asyncio.run(
        persist_data_refresh_result(
            DataRefreshPersistenceRequest(
                context=_context(),
                raw_payloads=(
                    build_raw_provider_payload(
                        provider="fixture",
                        endpoint="quotes",
                        symbol="AAPL",
                        payload={"symbol": "AAPL", "bid": 180.4},
                        fetched_at=_now(),
                    ),
                ),
                summary={"bars": "1"},
            )
        )
    )
    refresh_result = _require_ledger_result(refresh_result)

    assert isinstance(raw_result, LedgerActivityResult)
    assert raw_result.records_written == 1
    assert refresh_result.records_written == 2
    assert repository.get_raw_provider_payload_by_hash(
        provider="fixture",
        endpoint="daily-bars",
        payload_hash=raw_payload.payload_hash,
    ) is not None


def test_ai_execution_decision_candidate_and_risk_activities_persist_records(
    repository: SQLiteLedgerRepository,
) -> None:
    candidate_result = asyncio.run(
        persist_trade_candidates(
            TradeCandidatePersistenceRequest(
                context=_context(),
                candidates=(
                    TradeCandidatePayload(
                        candidate_id="candidate-1",
                        symbol="AAPL",
                        trading_date=date(2026, 5, 6),
                        strategy_version="regime_filtered_breakout_v0_3",
                        candidate_status="accepted",
                        technical_score=75,
                        relative_strength_score=70,
                        reason_payload={"reason_codes": ["trend_filter_passed"]},
                    ),
                ),
            )
        )
    )
    candidate_result = _require_ledger_result(candidate_result)
    output = neutral_research_output(
        symbol="AAPL",
        analysis_at=_now(),
        prompt_version="ai_trade_research_v0_3",
        schema_version="ai_trade_research_schema_v0_3",
        model_version="fixture-model",
        fallback_reason="no_news_found",
    )
    raw_prompt = "Analyze AAPL supplied candidate news only."
    raw_output = json.dumps(output.model_dump(mode="json"), sort_keys=True)
    ai_payload = build_ai_research_persistence_payload(
        symbol="AAPL",
        created_at=_now(),
        raw_prompt=raw_prompt,
        raw_ai_output=raw_output,
        parsed_output=output,
    )
    ai_result = asyncio.run(
        persist_ai_research_outputs(
            AIResearchOutputPersistenceRequest(context=_context(), outputs=(ai_payload,))
        )
    )
    ai_result = _require_ledger_result(ai_result)
    decision_result = asyncio.run(
        persist_trade_decision(
            TradeDecisionPersistenceRequest(
                context=_context(),
                decisions=(
                    TradeDecisionPayload(
                        decision_id="decision-1",
                        candidate_id="candidate-1",
                        symbol="AAPL",
                        decision_status="approved",
                        final_score=70,
                        ai_output_id=ai_result.record_ids[0],
                    ),
                ),
            )
        )
    )
    decision_result = _require_ledger_result(decision_result)
    intent = _execution_intent()
    intent_result = asyncio.run(
        persist_execution_intent(
            ExecutionIntentPersistenceRequest(context=_context(), intents=(intent,))
        )
    )
    intent_result = _require_ledger_result(intent_result)
    risk_result = asyncio.run(
        persist_risk_check(
            RiskCheckPersistenceRequest(
                context=_context(),
                risk_checks=(
                    RiskCheckPayload(
                        risk_check_id="risk-check-1",
                        decision_id="decision-1",
                        execution_intent_id=intent_result.record_ids[0],
                        symbol="AAPL",
                        passed=True,
                        risk_config_version="risk_v0_3",
                        reason_codes=("risk_checks_passed",),
                        input_snapshot={"client_order_id_root": intent.client_order_id_root},
                        result_payload={"approved": True},
                    ),
                ),
            )
        )
    )

    assert candidate_result.record_ids == ("candidate-1",)
    assert ai_result.records_written == 1
    assert hash_payload(raw_prompt) == ai_payload.raw_prompt_hash
    assert decision_result.record_ids == ("decision-1",)
    assert risk_result.record_ids == ("risk-check-1",)
    assert repository.get_execution_intent_by_client_order_id_root(
        intent.client_order_id_root
    ) is not None


def test_order_fill_position_reconciliation_event_and_report_activities(
    repository: SQLiteLedgerRepository,
) -> None:
    order_result = asyncio.run(
        persist_order_event(
            OrderEventPersistenceRequest(
                context=_context(),
                orders=(
                    OrderAuditPayload(
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
                        raw_broker_payload={"source": "fixture"},
                    ),
                ),
            )
        )
    )
    order_result = _require_ledger_result(order_result)
    fill_result = asyncio.run(
        persist_fill_event(
            FillEventPersistenceRequest(
                context=_context(),
                fills=(
                    FillAuditPayload(
                        fill_id="fill-1",
                        order_id="order-1",
                        broker_order_id="broker-order-1",
                        broker_fill_id="broker-fill-1",
                        symbol="AAPL",
                        quantity=1,
                        price=180.4,
                        filled_at=_now(),
                    ),
                ),
            )
        )
    )
    position_result = asyncio.run(
        persist_position_snapshot(
            PositionSnapshotPersistenceRequest(
                context=_context(),
                positions=(
                    PositionSnapshotPayload(
                        symbol="AAPL",
                        quantity=1,
                        average_entry_price=180.4,
                        opened_at=_now(),
                    ),
                ),
            )
        )
    )
    position_result = _require_ledger_result(position_result)
    reconciliation_result = asyncio.run(
        persist_broker_reconciliation(
            BrokerReconciliationPersistenceRequest(
                context=_context(),
                reconciliations=(
                    BrokerReconciliationSnapshotPayload(
                        reconciliation_id="recon-1",
                        temporal_workflow_id="workflow-recon-1",
                        account_snapshot={"equity": 100_000, "environment": "paper"},
                        broker_positions=({"symbol": "AAPL", "quantity": 1},),
                        internal_positions=({"symbol": "AAPL", "quantity": 1},),
                        status="clean",
                        created_at=_now(),
                    ),
                ),
            )
        )
    )
    reconciliation_result = _require_ledger_result(reconciliation_result)
    event_result = asyncio.run(
        persist_system_event(
            SystemEventPersistenceRequest(
                context=_context(),
                events=(
                    SystemEventPayload(
                        event_id="incident-1",
                        event_type="reconciliation_incident",
                        severity="warning",
                        source_component="test",
                        message="Fixture incident persisted.",
                        created_at=_now(),
                    ),
                ),
            )
        )
    )
    event_result = _require_ledger_result(event_result)
    report_result = asyncio.run(
        persist_report(
            ReportPersistenceRequest(
                context=_context(),
                reports=(
                    ReportPayload(
                        report_id="report-1",
                        report_type="daily",
                        report_date=date(2026, 5, 6),
                        status="draft",
                        payload={"orders": 0},
                        markdown="# Daily Report",
                    ),
                ),
            )
        )
    )
    report_result = _require_ledger_result(report_result)

    assert order_result.record_ids == ("order-1",)
    assert fill_result.record_ids == ("fill-1",)
    assert position_result.records_written == 1
    assert reconciliation_result.record_ids == ("recon-1",)
    assert event_result.record_ids == ("incident-1",)
    assert report_result.record_ids == ("report-1",)
    assert repository.get_latest_broker_reconciliation() is not None


def test_ledger_read_activities_use_local_repository() -> None:
    asyncio.run(
        persist_execution_intent(
            ExecutionIntentPersistenceRequest(context=_context(), intents=(_execution_intent(),))
        )
    )
    asyncio.run(
        persist_position_snapshot(
            PositionSnapshotPersistenceRequest(
                context=_context(),
                positions=(
                    PositionSnapshotPayload(
                        symbol="AAPL",
                        quantity=1,
                        average_entry_price=180.4,
                        opened_at=_now(),
                    ),
                ),
            )
        )
    )
    asyncio.run(
        persist_system_event(
            SystemEventPersistenceRequest(
                context=_context(),
                events=(
                    SystemEventPayload(
                        event_id="incident-1",
                        event_type="system_incident",
                        severity="critical",
                        source_component="test",
                        message="Critical fixture incident.",
                        created_at=_now(),
                    ),
                ),
            )
        )
    )
    asyncio.run(
        persist_broker_reconciliation(
            BrokerReconciliationPersistenceRequest(
                context=_context(),
                reconciliations=(
                    BrokerReconciliationSnapshotPayload(
                        reconciliation_id="recon-1",
                        account_snapshot={"equity": 100_000},
                        status="clean",
                        created_at=_now(),
                    ),
                ),
            )
        )
    )
    read_request = LedgerReadRequest(context=_context())

    intents = asyncio.run(get_active_execution_intents(read_request))
    positions = asyncio.run(get_open_positions(read_request))
    incidents = asyncio.run(get_recent_incidents(read_request))
    reconciliation = asyncio.run(get_latest_reconciliation_status(read_request))

    assert intents.status == "read"
    assert positions.status == "read"
    assert incidents.record_ids == ("incident-1",)
    assert reconciliation.details["status"] == "clean"


def test_workflow_placeholder_activity_checkpoint_persists_system_event(
    repository: SQLiteLedgerRepository,
) -> None:
    result = asyncio.run(
        persist_data_refresh_result(
            ActivityPlaceholderInput(
                workflow_name="DailyDataRefreshWorkflow",
                purpose="scheduled",
            )
        )
    )

    assert isinstance(result, ActivityPlaceholderResult)
    assert result.status == "ledger_checkpoint"
    assert result.external_calls_performed is False
    assert result.details["external_calls"] == "none"
    assert repository.list_system_events(limit=1)[0].event_type == "temporal_activity_checkpoint"


def test_ledger_activities_do_not_require_database_url_or_external_calls(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql://example.invalid/should-not-be-used")

    result = asyncio.run(
        persist_report(
            ReportPersistenceRequest(
                context=_context(),
                reports=(ReportPayload(report_type="manual", status="draft"),),
            )
        )
    )
    result = _require_ledger_result(result)

    assert result.records_written == 1
    assert result.external_calls_performed is False
    assert result.details["external_calls"] == "none"
