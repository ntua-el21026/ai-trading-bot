"""Safe ledger-backed Temporal activity implementations.

The default activity service uses in-memory SQLite so local workers and tests do not require
managed database credentials. Real Postgres/Supabase wiring remains a later milestone.
"""

from __future__ import annotations

from datetime import UTC, datetime

from temporalio import activity

from apps.workers.app.activities.models import (
    AIResearchOutputPersistenceRequest,
    BrokerReconciliationPersistenceRequest,
    DataRefreshPersistenceRequest,
    ExecutionIntentPersistenceRequest,
    FillEventPersistenceRequest,
    LedgerActivityResult,
    LedgerReadRequest,
    OrderEventPersistenceRequest,
    PositionSnapshotPersistenceRequest,
    RawProviderPayloadPersistenceRequest,
    ReportPersistenceRequest,
    RiskCheckPersistenceRequest,
    SystemEventPersistenceRequest,
    TradeCandidatePersistenceRequest,
    TradeDecisionPersistenceRequest,
)
from apps.workers.app.types import ActivityPlaceholderInput, ActivityPlaceholderResult
from packages.ledger.connection import connect_in_memory_sqlite
from packages.ledger.repositories import SQLiteLedgerRepository


class LedgerActivityService:
    """Repository-backed activity service with no broker/provider/network behavior."""

    def __init__(self, repository: SQLiteLedgerRepository) -> None:
        self._repository = repository

    def persist_workflow_checkpoint(
        self,
        *,
        activity_name: str,
        payload: ActivityPlaceholderInput,
    ) -> ActivityPlaceholderResult:
        event = self._repository.insert_system_event(
            event_type="temporal_activity_checkpoint",
            severity="info",
            source_component=payload.workflow_name,
            related_entity_type="temporal_activity",
            related_entity_id=activity_name,
            message=f"{activity_name} completed through safe ledger activity boundary.",
            payload={
                "purpose": payload.purpose,
                "external_calls_performed": False,
                "managed_database_called": False,
            },
            created_at=_utc_now(),
        )
        return ActivityPlaceholderResult(
            activity_name=activity_name,
            status="ledger_checkpoint",
            external_calls_performed=False,
            details={
                "workflow_name": payload.workflow_name,
                "purpose": payload.purpose,
                "side_effects": "local_ledger_only",
                "external_calls": "none",
                "system_event_id": event.event_id,
            },
        )

    def persist_raw_provider_payloads(
        self,
        request: RawProviderPayloadPersistenceRequest,
    ) -> LedgerActivityResult:
        record_ids = tuple(
            self._repository.insert_raw_provider_payload(payload).raw_provider_payload_id
            for payload in request.payloads
        )
        return _result("persist_raw_provider_payload", record_ids)

    def persist_data_refresh_result(
        self,
        request: DataRefreshPersistenceRequest,
    ) -> LedgerActivityResult:
        raw_payload_ids = tuple(
            self._repository.insert_raw_provider_payload(payload).raw_provider_payload_id
            for payload in request.raw_payloads
        )
        event = self._repository.insert_system_event(
            event_type="data_refresh_persisted",
            severity="info",
            source_component=request.context.workflow_name,
            message="Data refresh payloads persisted through ledger activity.",
            payload={
                "purpose": request.context.purpose,
                "request_id": request.context.request_id,
                "raw_payload_count": len(raw_payload_ids),
                **request.summary,
            },
            created_at=request.context.occurred_at or _utc_now(),
        )
        return _result("persist_data_refresh_result", (*raw_payload_ids, event.event_id))

    def persist_trade_candidates(
        self,
        request: TradeCandidatePersistenceRequest,
    ) -> LedgerActivityResult:
        record_ids = tuple(
            self._repository.insert_trade_candidate(
                candidate_id=candidate.candidate_id,
                symbol=candidate.symbol,
                trading_date=candidate.trading_date,
                strategy_version=candidate.strategy_version,
                candidate_status=candidate.candidate_status,
                technical_score=candidate.technical_score,
                relative_strength_score=candidate.relative_strength_score,
                score_payload=candidate.score_payload,
                reason_payload=candidate.reason_payload,
                rejection_reasons=candidate.rejection_reasons,
                source_features_daily_id=candidate.source_features_daily_id,
                created_at=candidate.created_at,
            ).candidate_id
            for candidate in request.candidates
        )
        return _result("persist_trade_candidates", record_ids)

    def persist_ai_research_outputs(
        self,
        request: AIResearchOutputPersistenceRequest,
    ) -> LedgerActivityResult:
        record_ids = tuple(
            self._repository.insert_ai_research_output(output).output_id
            for output in request.outputs
        )
        return _result("persist_ai_research_outputs", record_ids)

    def persist_trade_decision(
        self,
        request: TradeDecisionPersistenceRequest,
    ) -> LedgerActivityResult:
        record_ids = tuple(
            self._repository.insert_trade_decision(
                decision_id=decision.decision_id,
                candidate_id=decision.candidate_id,
                symbol=decision.symbol,
                decision_status=decision.decision_status,
                final_score=decision.final_score,
                deterministic_decision_payload=decision.deterministic_decision_payload,
                ai_output_id=decision.ai_output_id,
                created_at=decision.created_at,
            ).decision_id
            for decision in request.decisions
        )
        return _result("persist_trade_decision", record_ids)

    def persist_risk_check(self, request: RiskCheckPersistenceRequest) -> LedgerActivityResult:
        record_ids = tuple(
            self._repository.insert_risk_check(
                risk_check_id=risk_check.risk_check_id,
                decision_id=risk_check.decision_id,
                execution_intent_id=risk_check.execution_intent_id,
                symbol=risk_check.symbol,
                passed=risk_check.passed,
                reason_codes=risk_check.reason_codes,
                risk_config_version=risk_check.risk_config_version,
                input_snapshot=risk_check.input_snapshot,
                result_payload=risk_check.result_payload,
                created_at=risk_check.created_at,
            ).risk_check_id
            for risk_check in request.risk_checks
        )
        return _result("persist_risk_check", record_ids)

    def persist_execution_intents(
        self,
        request: ExecutionIntentPersistenceRequest,
    ) -> LedgerActivityResult:
        record_ids = tuple(
            self._repository.insert_execution_intent(intent).execution_intent_id
            for intent in request.intents
        )
        return _result("persist_execution_intent", record_ids)

    def persist_order_events(self, request: OrderEventPersistenceRequest) -> LedgerActivityResult:
        record_ids = tuple(
            self._repository.insert_order(
                order_id=order.order_id,
                execution_intent_id=order.execution_intent_id,
                broker_order_id=order.broker_order_id,
                client_order_id=order.client_order_id,
                symbol=order.symbol,
                side=order.side,
                order_type=order.order_type,
                time_in_force=order.time_in_force,
                quantity=order.quantity,
                limit_price=order.limit_price,
                stop_price=order.stop_price,
                status=order.status,
                raw_broker_payload=order.raw_broker_payload,
                created_at=order.created_at,
                updated_at=order.updated_at,
            ).order_id
            for order in request.orders
        )
        return _result("persist_order_event", record_ids)

    def persist_fill_events(self, request: FillEventPersistenceRequest) -> LedgerActivityResult:
        record_ids = tuple(
            self._repository.insert_fill(
                fill_id=fill.fill_id,
                order_id=fill.order_id,
                broker_order_id=fill.broker_order_id,
                broker_fill_id=fill.broker_fill_id,
                symbol=fill.symbol,
                quantity=fill.quantity,
                price=fill.price,
                filled_at=fill.filled_at,
                raw_broker_payload=fill.raw_broker_payload,
                created_at=fill.created_at,
            ).fill_id
            for fill in request.fills
        )
        return _result("persist_fill_event", record_ids)

    def persist_position_snapshots(
        self,
        request: PositionSnapshotPersistenceRequest,
    ) -> LedgerActivityResult:
        record_ids = tuple(
            self._repository.upsert_position(
                symbol=position.symbol,
                quantity=position.quantity,
                average_entry_price=position.average_entry_price,
                status=position.status,
                protective_stop_order_id=position.protective_stop_order_id,
                opened_at=position.opened_at,
                closed_at=position.closed_at,
                raw_source_payload=position.raw_source_payload,
            ).position_id
            for position in request.positions
        )
        return _result("persist_position_snapshot", record_ids)

    def persist_broker_reconciliations(
        self,
        request: BrokerReconciliationPersistenceRequest,
    ) -> LedgerActivityResult:
        record_ids = tuple(
            self._repository.insert_broker_reconciliation_snapshot(
                reconciliation_id=reconciliation.reconciliation_id,
                temporal_workflow_id=reconciliation.temporal_workflow_id,
                account_snapshot=reconciliation.account_snapshot,
                broker_positions=reconciliation.broker_positions,
                internal_positions=reconciliation.internal_positions,
                broker_orders=reconciliation.broker_orders,
                internal_orders=reconciliation.internal_orders,
                mismatches=reconciliation.mismatches,
                status=reconciliation.status,
                created_at=reconciliation.created_at,
            ).reconciliation_id
            for reconciliation in request.reconciliations
        )
        return _result("persist_broker_reconciliation", record_ids)

    def persist_system_events(self, request: SystemEventPersistenceRequest) -> LedgerActivityResult:
        record_ids = tuple(
            self._repository.insert_system_event(
                event_id=event.event_id,
                event_type=event.event_type,
                severity=event.severity,
                source_component=event.source_component,
                related_entity_type=event.related_entity_type,
                related_entity_id=event.related_entity_id,
                message=event.message,
                payload=event.payload,
                created_at=event.created_at,
                acknowledged_at=event.acknowledged_at,
            ).event_id
            for event in request.events
        )
        return _result("persist_system_event", record_ids)

    def persist_reports(self, request: ReportPersistenceRequest) -> LedgerActivityResult:
        record_ids = tuple(
            self._repository.insert_report(
                report_id=report.report_id,
                report_type=report.report_type,
                report_date=report.report_date,
                period_start=report.period_start,
                period_end=report.period_end,
                status=report.status,
                payload=report.payload,
                markdown=report.markdown,
                created_at=report.created_at,
            ).report_id
            for report in request.reports
        )
        return _result("persist_report", record_ids)

    def get_latest_reconciliation_status(
        self,
        request: LedgerReadRequest,
    ) -> LedgerActivityResult:
        record = self._repository.get_latest_broker_reconciliation()
        if record is None:
            return _read_result("get_latest_reconciliation_status", (), {"status": "missing"})
        return _read_result(
            "get_latest_reconciliation_status",
            (record.reconciliation_id,),
            {
                "status": record.status,
                "created_at": record.created_at.isoformat(),
                "workflow_name": request.context.workflow_name,
            },
        )

    def get_active_execution_intents(self, request: LedgerReadRequest) -> LedgerActivityResult:
        records = self._repository.list_active_execution_intents(limit=request.limit)
        return _read_result(
            "get_active_execution_intents",
            tuple(record.execution_intent_id for record in records),
            {"count": str(len(records))},
        )

    def get_open_positions(self, request: LedgerReadRequest) -> LedgerActivityResult:
        records = self._repository.list_open_positions(limit=request.limit)
        return _read_result(
            "get_open_positions",
            tuple(record.position_id for record in records),
            {"count": str(len(records))},
        )

    def get_recent_incidents(self, request: LedgerReadRequest) -> LedgerActivityResult:
        records = self._repository.list_recent_incidents(limit=request.limit)
        return _read_result(
            "get_recent_incidents",
            tuple(record.event_id for record in records),
            {"count": str(len(records))},
        )


def build_in_memory_ledger_activity_service() -> LedgerActivityService:
    return LedgerActivityService(SQLiteLedgerRepository(connect_in_memory_sqlite()))


_ledger_activity_service = build_in_memory_ledger_activity_service()


def configure_ledger_activity_service_for_tests(service: LedgerActivityService) -> None:
    global _ledger_activity_service
    _ledger_activity_service = service


def reset_ledger_activity_service_for_tests() -> None:
    configure_ledger_activity_service_for_tests(build_in_memory_ledger_activity_service())


@activity.defn(name="persist_raw_provider_payload")
async def persist_raw_provider_payload(
    payload: RawProviderPayloadPersistenceRequest,
) -> LedgerActivityResult:
    return _ledger_activity_service.persist_raw_provider_payloads(payload)


@activity.defn(name="persist_data_refresh_result")
async def persist_data_refresh_result(
    payload: ActivityPlaceholderInput | DataRefreshPersistenceRequest,
) -> ActivityPlaceholderResult | LedgerActivityResult:
    if isinstance(payload, ActivityPlaceholderInput):
        return _ledger_activity_service.persist_workflow_checkpoint(
            activity_name="persist_data_refresh_result",
            payload=payload,
        )
    return _ledger_activity_service.persist_data_refresh_result(payload)


@activity.defn(name="persist_trade_candidates")
async def persist_trade_candidates(
    payload: ActivityPlaceholderInput | TradeCandidatePersistenceRequest,
) -> ActivityPlaceholderResult | LedgerActivityResult:
    if isinstance(payload, ActivityPlaceholderInput):
        return _ledger_activity_service.persist_workflow_checkpoint(
            activity_name="persist_trade_candidates",
            payload=payload,
        )
    return _ledger_activity_service.persist_trade_candidates(payload)


@activity.defn(name="persist_ai_research_outputs")
async def persist_ai_research_outputs(
    payload: ActivityPlaceholderInput | AIResearchOutputPersistenceRequest,
) -> ActivityPlaceholderResult | LedgerActivityResult:
    if isinstance(payload, ActivityPlaceholderInput):
        return _ledger_activity_service.persist_workflow_checkpoint(
            activity_name="persist_ai_research_outputs",
            payload=payload,
        )
    return _ledger_activity_service.persist_ai_research_outputs(payload)


@activity.defn(name="persist_trade_decision")
async def persist_trade_decision(
    payload: ActivityPlaceholderInput | TradeDecisionPersistenceRequest,
) -> ActivityPlaceholderResult | LedgerActivityResult:
    if isinstance(payload, ActivityPlaceholderInput):
        return _ledger_activity_service.persist_workflow_checkpoint(
            activity_name="persist_trade_decision",
            payload=payload,
        )
    return _ledger_activity_service.persist_trade_decision(payload)


@activity.defn(name="persist_risk_check")
async def persist_risk_check(
    payload: RiskCheckPersistenceRequest,
) -> LedgerActivityResult:
    return _ledger_activity_service.persist_risk_check(payload)


@activity.defn(name="persist_execution_intent")
async def persist_execution_intent(
    payload: ActivityPlaceholderInput | ExecutionIntentPersistenceRequest,
) -> ActivityPlaceholderResult | LedgerActivityResult:
    if isinstance(payload, ActivityPlaceholderInput):
        return _ledger_activity_service.persist_workflow_checkpoint(
            activity_name="persist_execution_intent",
            payload=payload,
        )
    return _ledger_activity_service.persist_execution_intents(payload)


@activity.defn(name="persist_order_event")
async def persist_order_event(
    payload: ActivityPlaceholderInput | OrderEventPersistenceRequest,
) -> ActivityPlaceholderResult | LedgerActivityResult:
    if isinstance(payload, ActivityPlaceholderInput):
        return _ledger_activity_service.persist_workflow_checkpoint(
            activity_name="persist_order_event",
            payload=payload,
        )
    return _ledger_activity_service.persist_order_events(payload)


@activity.defn(name="persist_fill_event")
async def persist_fill_event(payload: FillEventPersistenceRequest) -> LedgerActivityResult:
    return _ledger_activity_service.persist_fill_events(payload)


@activity.defn(name="persist_position_snapshot")
async def persist_position_snapshot(
    payload: ActivityPlaceholderInput | PositionSnapshotPersistenceRequest,
) -> ActivityPlaceholderResult | LedgerActivityResult:
    if isinstance(payload, ActivityPlaceholderInput):
        return _ledger_activity_service.persist_workflow_checkpoint(
            activity_name="persist_position_snapshot",
            payload=payload,
        )
    return _ledger_activity_service.persist_position_snapshots(payload)


@activity.defn(name="persist_broker_reconciliation")
async def persist_broker_reconciliation(
    payload: ActivityPlaceholderInput | BrokerReconciliationPersistenceRequest,
) -> ActivityPlaceholderResult | LedgerActivityResult:
    if isinstance(payload, ActivityPlaceholderInput):
        return _ledger_activity_service.persist_workflow_checkpoint(
            activity_name="persist_broker_reconciliation",
            payload=payload,
        )
    return _ledger_activity_service.persist_broker_reconciliations(payload)


@activity.defn(name="persist_system_event")
async def persist_system_event(
    payload: ActivityPlaceholderInput | SystemEventPersistenceRequest,
) -> ActivityPlaceholderResult | LedgerActivityResult:
    if isinstance(payload, ActivityPlaceholderInput):
        return _ledger_activity_service.persist_workflow_checkpoint(
            activity_name="persist_system_event",
            payload=payload,
        )
    return _ledger_activity_service.persist_system_events(payload)


@activity.defn(name="persist_report")
async def persist_report(
    payload: ActivityPlaceholderInput | ReportPersistenceRequest,
) -> ActivityPlaceholderResult | LedgerActivityResult:
    if isinstance(payload, ActivityPlaceholderInput):
        return _ledger_activity_service.persist_workflow_checkpoint(
            activity_name="persist_report",
            payload=payload,
        )
    return _ledger_activity_service.persist_reports(payload)


@activity.defn(name="get_latest_reconciliation_status")
async def get_latest_reconciliation_status(
    payload: LedgerReadRequest,
) -> LedgerActivityResult:
    return _ledger_activity_service.get_latest_reconciliation_status(payload)


@activity.defn(name="get_active_execution_intents")
async def get_active_execution_intents(payload: LedgerReadRequest) -> LedgerActivityResult:
    return _ledger_activity_service.get_active_execution_intents(payload)


@activity.defn(name="get_open_positions")
async def get_open_positions(payload: LedgerReadRequest) -> LedgerActivityResult:
    return _ledger_activity_service.get_open_positions(payload)


@activity.defn(name="get_recent_incidents")
async def get_recent_incidents(payload: LedgerReadRequest) -> LedgerActivityResult:
    return _ledger_activity_service.get_recent_incidents(payload)


LEDGER_ACTIVITY_FUNCTIONS = (
    persist_raw_provider_payload,
    persist_data_refresh_result,
    persist_trade_candidates,
    persist_ai_research_outputs,
    persist_trade_decision,
    persist_risk_check,
    persist_execution_intent,
    persist_order_event,
    persist_fill_event,
    persist_position_snapshot,
    persist_broker_reconciliation,
    persist_system_event,
    persist_report,
    get_latest_reconciliation_status,
    get_active_execution_intents,
    get_open_positions,
    get_recent_incidents,
)


def _result(activity_name: str, record_ids: tuple[str, ...]) -> LedgerActivityResult:
    return LedgerActivityResult(
        activity_name=activity_name,
        status="persisted" if record_ids else "noop",
        records_written=len(record_ids),
        record_ids=record_ids,
        external_calls_performed=False,
        details={"side_effects": "local_ledger_only", "external_calls": "none"},
    )


def _read_result(
    activity_name: str,
    record_ids: tuple[str, ...],
    details: dict[str, str],
) -> LedgerActivityResult:
    return LedgerActivityResult(
        activity_name=activity_name,
        status="read" if record_ids else "noop",
        records_written=0,
        record_ids=record_ids,
        external_calls_performed=False,
        details={**details, "side_effects": "local_ledger_only", "external_calls": "none"},
    )


def _utc_now() -> datetime:
    return datetime.now(UTC)
