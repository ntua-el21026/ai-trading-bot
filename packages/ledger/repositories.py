"""Repository boundaries and local SQLite implementation for the audit ledger."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Mapping, Sequence
from datetime import UTC, date, datetime
from typing import Any, Literal, Protocol
from uuid import uuid4

from packages.ai.persistence import AIResearchPersistencePayload
from packages.data.models import RawProviderPayload
from packages.execution.models import ExecutionIntent
from packages.ledger.models import (
    AIResearchOutputRecord,
    BrokerReconciliationRecord,
    ExecutionIntentRecord,
    FillRecord,
    OrderRecord,
    PositionRecord,
    RawProviderPayloadRecord,
    ReportRecord,
    RiskCheckRecord,
    SystemEventRecord,
    TradeCandidateRecord,
    TradeDecisionRecord,
)
from packages.reconciliation.models import ReconciliationResult


class RawProviderPayloadRepository(Protocol):
    def insert_raw_provider_payload(
        self,
        payload: RawProviderPayload,
    ) -> RawProviderPayloadRecord:
        """Persist a raw provider payload."""

    def get_raw_provider_payload_by_hash(
        self,
        *,
        provider: str,
        endpoint: str,
        payload_hash: str,
    ) -> RawProviderPayloadRecord | None:
        """Fetch a raw payload by provider/source/hash scope."""


class AuditLedgerRepository(RawProviderPayloadRepository, Protocol):
    def insert_ai_research_output(
        self,
        payload: AIResearchPersistencePayload,
    ) -> AIResearchOutputRecord:
        """Persist raw and parsed AI research output."""

    def get_ai_research_output(self, output_id: str) -> AIResearchOutputRecord | None:
        """Fetch an AI research output by ID."""

    def insert_execution_intent(
        self,
        intent: ExecutionIntent,
        *,
        execution_intent_id: str | None = None,
        payload: Mapping[str, Any] | None = None,
    ) -> ExecutionIntentRecord:
        """Persist an execution intent and enforce client-order-root uniqueness."""

    def get_execution_intent_by_id(
        self,
        execution_intent_id: str,
    ) -> ExecutionIntentRecord | None:
        """Fetch an execution intent by ledger ID."""

    def get_execution_intent_by_client_order_id_root(
        self,
        client_order_id_root: str,
    ) -> ExecutionIntentRecord | None:
        """Fetch an execution intent by idempotent client-order root."""

    def insert_trade_candidate(
        self,
        *,
        symbol: str,
        trading_date: date,
        strategy_version: str,
        candidate_status: str,
        candidate_id: str | None = None,
        technical_score: float | None = None,
        relative_strength_score: float | None = None,
        score_payload: Mapping[str, Any] | None = None,
        reason_payload: Mapping[str, Any] | None = None,
        rejection_reasons: Sequence[str] = (),
        source_features_daily_id: str | None = None,
        created_at: datetime | None = None,
    ) -> TradeCandidateRecord:
        """Persist a deterministic strategy candidate."""

    def insert_trade_decision(
        self,
        *,
        symbol: str,
        decision_status: str,
        decision_id: str | None = None,
        candidate_id: str | None = None,
        final_score: float | None = None,
        deterministic_decision_payload: Mapping[str, Any] | None = None,
        ai_output_id: str | None = None,
        created_at: datetime | None = None,
    ) -> TradeDecisionRecord:
        """Persist a deterministic trade decision."""

    def insert_risk_check(
        self,
        *,
        symbol: str,
        passed: bool,
        risk_config_version: str,
        risk_check_id: str | None = None,
        decision_id: str | None = None,
        execution_intent_id: str | None = None,
        reason_codes: Sequence[str] = (),
        input_snapshot: Mapping[str, Any] | None = None,
        result_payload: Mapping[str, Any] | None = None,
        created_at: datetime | None = None,
    ) -> RiskCheckRecord:
        """Persist a deterministic risk-check result."""


class SQLiteLedgerRepository:
    """SQLite-backed local repository implementation.

    This class is for in-process tests and local development. It intentionally performs only
    database I/O against the provided connection and does not read environment variables or call
    managed database, broker, AI/news, Temporal, or alerting APIs.
    """

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

    def insert_raw_provider_payload(
        self,
        payload: RawProviderPayload,
    ) -> RawProviderPayloadRecord:
        record_id = _new_id()
        raw_payload = _raw_provider_payload_json(payload)
        with self._connection:
            self._connection.execute(
                """
                INSERT INTO raw_provider_payloads (
                    raw_provider_payload_id,
                    provider,
                    endpoint,
                    symbol,
                    payload_hash,
                    raw_payload_json,
                    content_type,
                    received_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record_id,
                    payload.provider,
                    payload.endpoint,
                    payload.symbol,
                    payload.payload_hash,
                    _json_for_db(raw_payload),
                    payload.content_type,
                    _datetime_for_db(payload.fetched_at),
                ),
            )
        row = self._fetch_one(
            "SELECT * FROM raw_provider_payloads WHERE raw_provider_payload_id = ?",
            (record_id,),
        )
        if row is None:
            raise LedgerRepositoryError("raw provider payload insert did not return a row")
        return _raw_provider_payload_record(row)

    def get_raw_provider_payload_by_hash(
        self,
        *,
        provider: str,
        endpoint: str,
        payload_hash: str,
    ) -> RawProviderPayloadRecord | None:
        row = self._fetch_one(
            """
            SELECT * FROM raw_provider_payloads
            WHERE provider = ? AND endpoint = ? AND payload_hash = ?
            """,
            (provider, endpoint, payload_hash),
        )
        return None if row is None else _raw_provider_payload_record(row)

    def insert_ai_research_output(
        self,
        payload: AIResearchPersistencePayload,
        *,
        output_id: str | None = None,
    ) -> AIResearchOutputRecord:
        record_id = output_id or _new_id()
        with self._connection:
            self._connection.execute(
                """
                INSERT INTO ai_research_outputs (
                    output_id,
                    symbol,
                    prompt_version,
                    schema_version,
                    model_version,
                    raw_prompt,
                    raw_prompt_hash,
                    raw_output,
                    raw_output_hash,
                    parsed_output_json,
                    ai_score,
                    hard_block,
                    fallback_reason,
                    citations_json,
                    canonical_urls_json,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record_id,
                    payload.symbol,
                    payload.prompt_version,
                    payload.schema_version,
                    payload.model_version,
                    payload.raw_prompt,
                    payload.raw_prompt_hash,
                    payload.raw_ai_output,
                    payload.raw_output_hash,
                    _json_for_db(payload.parsed_output.model_dump(mode="json")),
                    payload.parsed_output.ai_score,
                    _bool_for_db(payload.parsed_output.hard_block),
                    payload.fallback_reason,
                    _json_for_db(list(payload.citations)),
                    _json_for_db(list(payload.canonical_urls)),
                    _datetime_for_db(payload.created_at),
                ),
            )
        row = self._fetch_one("SELECT * FROM ai_research_outputs WHERE output_id = ?", (record_id,))
        if row is None:
            raise LedgerRepositoryError("AI research output insert did not return a row")
        return _ai_research_output_record(row)

    def get_ai_research_output(self, output_id: str) -> AIResearchOutputRecord | None:
        row = self._fetch_one("SELECT * FROM ai_research_outputs WHERE output_id = ?", (output_id,))
        return None if row is None else _ai_research_output_record(row)

    def insert_execution_intent(
        self,
        intent: ExecutionIntent,
        *,
        execution_intent_id: str | None = None,
        payload: Mapping[str, Any] | None = None,
    ) -> ExecutionIntentRecord:
        record_id = execution_intent_id or _new_id()
        stored_payload = dict(payload or intent.model_dump(mode="json"))
        with self._connection:
            self._connection.execute(
                """
                INSERT INTO execution_intents (
                    execution_intent_id,
                    temporal_workflow_id,
                    decision_id,
                    client_order_id_root,
                    symbol,
                    side,
                    asset_class,
                    quantity,
                    entry_order_type,
                    limit_price,
                    stop_loss_price,
                    time_in_force,
                    strategy_version,
                    risk_config_version,
                    autonomy_level,
                    requires_protective_stop,
                    max_acceptable_slippage_bps,
                    status,
                    payload_json,
                    expires_at,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record_id,
                    intent.temporal_workflow_id,
                    str(intent.decision_id),
                    intent.client_order_id_root,
                    intent.symbol,
                    intent.side,
                    intent.asset_class,
                    intent.quantity,
                    intent.entry_order_type,
                    intent.limit_price,
                    intent.stop_loss_price,
                    intent.time_in_force,
                    intent.strategy_version,
                    intent.risk_config_version,
                    intent.autonomy_level,
                    _bool_for_db(intent.requires_protective_stop),
                    intent.max_acceptable_slippage_bps,
                    intent.status,
                    _json_for_db(stored_payload),
                    _datetime_for_db(intent.expires_at),
                    _datetime_for_db(_utc_now()),
                ),
            )
        return self._get_required_execution_intent(record_id)

    def get_execution_intent_by_id(
        self,
        execution_intent_id: str,
    ) -> ExecutionIntentRecord | None:
        row = self._fetch_one(
            "SELECT * FROM execution_intents WHERE execution_intent_id = ?",
            (execution_intent_id,),
        )
        return None if row is None else _execution_intent_record(row)

    def get_execution_intent_by_client_order_id_root(
        self,
        client_order_id_root: str,
    ) -> ExecutionIntentRecord | None:
        row = self._fetch_one(
            "SELECT * FROM execution_intents WHERE client_order_id_root = ?",
            (client_order_id_root,),
        )
        return None if row is None else _execution_intent_record(row)

    def list_active_execution_intents(
        self,
        *,
        statuses: Sequence[str] = ("created", "risk_approved", "submitted_to_workflow"),
        limit: int = 100,
    ) -> tuple[ExecutionIntentRecord, ...]:
        allowed_statuses = set(statuses)
        rows = self._connection.execute(
            """
            SELECT * FROM execution_intents
            ORDER BY created_at DESC, execution_intent_id DESC
            """
        ).fetchall()
        records = [
            _execution_intent_record(row) for row in rows if str(row["status"]) in allowed_statuses
        ]
        return tuple(records[:limit])

    def insert_trade_candidate(
        self,
        *,
        symbol: str,
        trading_date: date,
        strategy_version: str,
        candidate_status: str,
        candidate_id: str | None = None,
        technical_score: float | None = None,
        relative_strength_score: float | None = None,
        score_payload: Mapping[str, Any] | None = None,
        reason_payload: Mapping[str, Any] | None = None,
        rejection_reasons: Sequence[str] = (),
        source_features_daily_id: str | None = None,
        created_at: datetime | None = None,
    ) -> TradeCandidateRecord:
        record_id = candidate_id or _new_id()
        with self._connection:
            self._connection.execute(
                """
                INSERT INTO trade_candidates (
                    candidate_id,
                    symbol,
                    trading_date,
                    strategy_version,
                    candidate_status,
                    technical_score,
                    relative_strength_score,
                    score_payload_json,
                    reason_payload_json,
                    rejection_reasons_json,
                    source_features_daily_id,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record_id,
                    symbol,
                    _date_for_db(trading_date),
                    strategy_version,
                    candidate_status,
                    technical_score,
                    relative_strength_score,
                    _json_for_db(dict(score_payload or {})),
                    _json_for_db(dict(reason_payload or {})),
                    _json_for_db(list(rejection_reasons)),
                    source_features_daily_id,
                    _datetime_for_db(created_at or _utc_now()),
                ),
            )
        row = self._fetch_one("SELECT * FROM trade_candidates WHERE candidate_id = ?", (record_id,))
        if row is None:
            raise LedgerRepositoryError("trade candidate insert did not return a row")
        return _trade_candidate_record(row)

    def insert_trade_decision(
        self,
        *,
        symbol: str,
        decision_status: str,
        decision_id: str | None = None,
        candidate_id: str | None = None,
        final_score: float | None = None,
        deterministic_decision_payload: Mapping[str, Any] | None = None,
        ai_output_id: str | None = None,
        created_at: datetime | None = None,
    ) -> TradeDecisionRecord:
        record_id = decision_id or _new_id()
        with self._connection:
            self._connection.execute(
                """
                INSERT INTO trade_decisions (
                    decision_id,
                    candidate_id,
                    symbol,
                    decision_status,
                    final_score,
                    deterministic_decision_payload_json,
                    ai_output_id,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record_id,
                    candidate_id,
                    symbol,
                    decision_status,
                    final_score,
                    _json_for_db(dict(deterministic_decision_payload or {})),
                    ai_output_id,
                    _datetime_for_db(created_at or _utc_now()),
                ),
            )
        row = self._fetch_one("SELECT * FROM trade_decisions WHERE decision_id = ?", (record_id,))
        if row is None:
            raise LedgerRepositoryError("trade decision insert did not return a row")
        return _trade_decision_record(row)

    def insert_risk_check(
        self,
        *,
        symbol: str,
        passed: bool,
        risk_config_version: str,
        risk_check_id: str | None = None,
        decision_id: str | None = None,
        execution_intent_id: str | None = None,
        reason_codes: Sequence[str] = (),
        input_snapshot: Mapping[str, Any] | None = None,
        result_payload: Mapping[str, Any] | None = None,
        created_at: datetime | None = None,
    ) -> RiskCheckRecord:
        record_id = risk_check_id or _new_id()
        with self._connection:
            self._connection.execute(
                """
                INSERT INTO risk_checks (
                    risk_check_id,
                    decision_id,
                    execution_intent_id,
                    symbol,
                    passed,
                    reason_codes_json,
                    risk_config_version,
                    input_snapshot_json,
                    result_payload_json,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record_id,
                    decision_id,
                    execution_intent_id,
                    symbol,
                    _bool_for_db(passed),
                    _json_for_db(list(reason_codes)),
                    risk_config_version,
                    _json_for_db(dict(input_snapshot or {})),
                    _json_for_db(dict(result_payload or {})),
                    _datetime_for_db(created_at or _utc_now()),
                ),
            )
        row = self._fetch_one("SELECT * FROM risk_checks WHERE risk_check_id = ?", (record_id,))
        if row is None:
            raise LedgerRepositoryError("risk check insert did not return a row")
        return _risk_check_record(row)

    def insert_order(
        self,
        *,
        client_order_id: str,
        symbol: str,
        side: Literal["buy", "sell"],
        order_type: str,
        time_in_force: str,
        quantity: float,
        status: str,
        execution_intent_id: str | None = None,
        broker_order_id: str | None = None,
        limit_price: float | None = None,
        stop_price: float | None = None,
        raw_broker_payload: Mapping[str, Any] | None = None,
        order_id: str | None = None,
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
    ) -> OrderRecord:
        record_id = order_id or _new_id()
        created = created_at or _utc_now()
        updated = updated_at or created
        with self._connection:
            self._connection.execute(
                """
                INSERT INTO orders (
                    order_id,
                    execution_intent_id,
                    broker_order_id,
                    client_order_id,
                    symbol,
                    side,
                    order_type,
                    time_in_force,
                    quantity,
                    limit_price,
                    stop_price,
                    status,
                    raw_broker_payload_json,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record_id,
                    execution_intent_id,
                    broker_order_id,
                    client_order_id,
                    symbol,
                    side,
                    order_type,
                    time_in_force,
                    quantity,
                    limit_price,
                    stop_price,
                    status,
                    _json_for_db(dict(raw_broker_payload or {})),
                    _datetime_for_db(created),
                    _datetime_for_db(updated),
                ),
            )
        row = self._fetch_one("SELECT * FROM orders WHERE order_id = ?", (record_id,))
        if row is None:
            raise LedgerRepositoryError("order insert did not return a row")
        return _order_record(row)

    def get_order_by_client_order_id(self, client_order_id: str) -> OrderRecord | None:
        row = self._fetch_one(
            "SELECT * FROM orders WHERE client_order_id = ?",
            (client_order_id,),
        )
        return None if row is None else _order_record(row)

    def insert_fill(
        self,
        *,
        order_id: str,
        symbol: str,
        quantity: float,
        price: float,
        filled_at: datetime,
        broker_order_id: str | None = None,
        broker_fill_id: str | None = None,
        raw_broker_payload: Mapping[str, Any] | None = None,
        fill_id: str | None = None,
        created_at: datetime | None = None,
    ) -> FillRecord:
        record_id = fill_id or _new_id()
        with self._connection:
            self._connection.execute(
                """
                INSERT INTO fills (
                    fill_id,
                    order_id,
                    broker_order_id,
                    broker_fill_id,
                    symbol,
                    quantity,
                    price,
                    filled_at,
                    raw_broker_payload_json,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record_id,
                    order_id,
                    broker_order_id,
                    broker_fill_id,
                    symbol,
                    quantity,
                    price,
                    _datetime_for_db(filled_at),
                    _json_for_db(dict(raw_broker_payload or {})),
                    _datetime_for_db(created_at or _utc_now()),
                ),
            )
        row = self._fetch_one("SELECT * FROM fills WHERE fill_id = ?", (record_id,))
        if row is None:
            raise LedgerRepositoryError("fill insert did not return a row")
        return _fill_record(row)

    def upsert_position(
        self,
        *,
        symbol: str,
        quantity: float,
        average_entry_price: float,
        status: str = "open",
        protective_stop_order_id: str | None = None,
        opened_at: datetime | None = None,
        closed_at: datetime | None = None,
        raw_source_payload: Mapping[str, Any] | None = None,
    ) -> PositionRecord:
        existing = self.get_open_position(symbol) if status == "open" else None
        now = _utc_now()
        if existing is None:
            record_id = _new_id()
            with self._connection:
                self._connection.execute(
                    """
                    INSERT INTO positions (
                        position_id,
                        symbol,
                        quantity,
                        average_entry_price,
                        status,
                        protective_stop_order_id,
                        opened_at,
                        closed_at,
                        raw_source_payload_json,
                        created_at,
                        updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        record_id,
                        symbol,
                        quantity,
                        average_entry_price,
                        status,
                        protective_stop_order_id,
                        _optional_datetime_for_db(opened_at),
                        _optional_datetime_for_db(closed_at),
                        _json_for_db(dict(raw_source_payload or {})),
                        _datetime_for_db(now),
                        _datetime_for_db(now),
                    ),
                )
            return self._get_required_position(record_id)

        with self._connection:
            self._connection.execute(
                """
                UPDATE positions
                SET quantity = ?,
                    average_entry_price = ?,
                    protective_stop_order_id = ?,
                    opened_at = ?,
                    closed_at = ?,
                    raw_source_payload_json = ?,
                    updated_at = ?
                WHERE position_id = ?
                """,
                (
                    quantity,
                    average_entry_price,
                    protective_stop_order_id,
                    _optional_datetime_for_db(opened_at),
                    _optional_datetime_for_db(closed_at),
                    _json_for_db(dict(raw_source_payload or {})),
                    _datetime_for_db(now),
                    existing.position_id,
                ),
            )
        return self._get_required_position(existing.position_id)

    def get_position(self, position_id: str) -> PositionRecord | None:
        row = self._fetch_one("SELECT * FROM positions WHERE position_id = ?", (position_id,))
        return None if row is None else _position_record(row)

    def get_open_position(self, symbol: str) -> PositionRecord | None:
        row = self._fetch_one(
            "SELECT * FROM positions WHERE symbol = ? AND status = 'open'",
            (symbol,),
        )
        return None if row is None else _position_record(row)

    def list_open_positions(self, *, limit: int = 100) -> tuple[PositionRecord, ...]:
        rows = self._connection.execute(
            """
            SELECT * FROM positions
            WHERE status = 'open'
            ORDER BY updated_at DESC, position_id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return tuple(_position_record(row) for row in rows)

    def insert_broker_reconciliation_snapshot(
        self,
        *,
        account_snapshot: Mapping[str, Any],
        broker_positions: Sequence[Any] = (),
        internal_positions: Sequence[Any] = (),
        broker_orders: Sequence[Any] = (),
        internal_orders: Sequence[Any] = (),
        mismatches: Sequence[Any] = (),
        status: str,
        temporal_workflow_id: str | None = None,
        reconciliation_id: str | None = None,
        created_at: datetime | None = None,
    ) -> BrokerReconciliationRecord:
        record_id = reconciliation_id or _new_id()
        with self._connection:
            self._connection.execute(
                """
                INSERT INTO broker_reconciliations (
                    reconciliation_id,
                    temporal_workflow_id,
                    account_snapshot_json,
                    broker_positions_json,
                    internal_positions_json,
                    broker_orders_json,
                    internal_orders_json,
                    mismatches_json,
                    status,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record_id,
                    temporal_workflow_id,
                    _json_for_db(dict(account_snapshot)),
                    _json_for_db(list(broker_positions)),
                    _json_for_db(list(internal_positions)),
                    _json_for_db(list(broker_orders)),
                    _json_for_db(list(internal_orders)),
                    _json_for_db(list(mismatches)),
                    status,
                    _datetime_for_db(created_at or _utc_now()),
                ),
            )
        row = self._fetch_one(
            "SELECT * FROM broker_reconciliations WHERE reconciliation_id = ?",
            (record_id,),
        )
        if row is None:
            raise LedgerRepositoryError("broker reconciliation insert did not return a row")
        return _broker_reconciliation_record(row)

    def insert_broker_reconciliation_result(
        self,
        result: ReconciliationResult,
        *,
        temporal_workflow_id: str | None = None,
        reconciliation_id: str | None = None,
        created_at: datetime | None = None,
    ) -> BrokerReconciliationRecord:
        return self.insert_broker_reconciliation_snapshot(
            reconciliation_id=reconciliation_id,
            temporal_workflow_id=temporal_workflow_id,
            account_snapshot=result.broker_snapshot.account.model_dump(mode="json"),
            broker_positions=[
                position.model_dump(mode="json") for position in result.broker_snapshot.positions
            ],
            internal_positions=[
                position.model_dump(mode="json") for position in result.internal_snapshot.positions
            ],
            broker_orders=[
                order.model_dump(mode="json") for order in result.broker_snapshot.open_orders
            ],
            internal_orders=[
                order.model_dump(mode="json") for order in result.internal_snapshot.orders
            ],
            mismatches=[mismatch.model_dump(mode="json") for mismatch in result.mismatches],
            status="clean" if result.clean else "mismatched",
            created_at=created_at,
        )

    def get_latest_broker_reconciliation(self) -> BrokerReconciliationRecord | None:
        row = self._fetch_one(
            """
            SELECT * FROM broker_reconciliations
            ORDER BY created_at DESC, reconciliation_id DESC
            LIMIT 1
            """,
            (),
        )
        return None if row is None else _broker_reconciliation_record(row)

    def insert_system_event(
        self,
        *,
        event_type: str,
        severity: Literal["info", "warning", "critical"],
        source_component: str,
        message: str,
        related_entity_type: str | None = None,
        related_entity_id: str | None = None,
        payload: Mapping[str, Any] | None = None,
        event_id: str | None = None,
        created_at: datetime | None = None,
        acknowledged_at: datetime | None = None,
    ) -> SystemEventRecord:
        record_id = event_id or _new_id()
        with self._connection:
            self._connection.execute(
                """
                INSERT INTO system_events (
                    event_id,
                    event_type,
                    severity,
                    source_component,
                    related_entity_type,
                    related_entity_id,
                    message,
                    payload_json,
                    created_at,
                    acknowledged_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record_id,
                    event_type,
                    severity,
                    source_component,
                    related_entity_type,
                    related_entity_id,
                    message,
                    _json_for_db(dict(payload or {})),
                    _datetime_for_db(created_at or _utc_now()),
                    _optional_datetime_for_db(acknowledged_at),
                ),
            )
        row = self._fetch_one("SELECT * FROM system_events WHERE event_id = ?", (record_id,))
        if row is None:
            raise LedgerRepositoryError("system event insert did not return a row")
        return _system_event_record(row)

    def list_system_events(self, *, limit: int = 100) -> tuple[SystemEventRecord, ...]:
        rows = self._connection.execute(
            "SELECT * FROM system_events ORDER BY created_at DESC, event_id DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return tuple(_system_event_record(row) for row in rows)

    def list_recent_incidents(self, *, limit: int = 100) -> tuple[SystemEventRecord, ...]:
        rows = self._connection.execute(
            """
            SELECT * FROM system_events
            WHERE event_type LIKE '%incident%' OR severity IN ('warning', 'critical')
            ORDER BY created_at DESC, event_id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return tuple(_system_event_record(row) for row in rows)

    def insert_report(
        self,
        *,
        report_type: str,
        status: str,
        payload: Mapping[str, Any] | None = None,
        markdown: str | None = None,
        report_date: date | None = None,
        period_start: date | None = None,
        period_end: date | None = None,
        report_id: str | None = None,
        created_at: datetime | None = None,
    ) -> ReportRecord:
        record_id = report_id or _new_id()
        with self._connection:
            self._connection.execute(
                """
                INSERT INTO reports (
                    report_id,
                    report_type,
                    report_date,
                    period_start,
                    period_end,
                    status,
                    payload_json,
                    markdown,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record_id,
                    report_type,
                    _optional_date_for_db(report_date),
                    _optional_date_for_db(period_start),
                    _optional_date_for_db(period_end),
                    status,
                    _json_for_db(dict(payload or {})),
                    markdown,
                    _datetime_for_db(created_at or _utc_now()),
                ),
            )
        row = self._fetch_one("SELECT * FROM reports WHERE report_id = ?", (record_id,))
        if row is None:
            raise LedgerRepositoryError("report insert did not return a row")
        return _report_record(row)

    def get_report(self, report_id: str) -> ReportRecord | None:
        row = self._fetch_one("SELECT * FROM reports WHERE report_id = ?", (report_id,))
        return None if row is None else _report_record(row)

    def _get_required_execution_intent(self, execution_intent_id: str) -> ExecutionIntentRecord:
        record = self.get_execution_intent_by_id(execution_intent_id)
        if record is None:
            raise LedgerRepositoryError("execution intent was not found after write")
        return record

    def _get_required_position(self, position_id: str) -> PositionRecord:
        record = self.get_position(position_id)
        if record is None:
            raise LedgerRepositoryError("position was not found after write")
        return record

    def _fetch_one(self, query: str, params: tuple[Any, ...]) -> sqlite3.Row | None:
        row = self._connection.execute(query, params).fetchone()
        if row is None:
            return None
        if not isinstance(row, sqlite3.Row):
            raise LedgerRepositoryError("connection must use sqlite3.Row row_factory")
        return row


class LedgerRepositoryError(RuntimeError):
    """Raised when repository writes cannot be read back consistently."""


def _raw_provider_payload_record(row: sqlite3.Row) -> RawProviderPayloadRecord:
    return RawProviderPayloadRecord(
        raw_provider_payload_id=str(row["raw_provider_payload_id"]),
        provider=str(row["provider"]),
        endpoint=str(row["endpoint"]),
        symbol=_optional_str(row["symbol"]),
        payload_hash=str(row["payload_hash"]),
        raw_payload=_json_from_db(row["raw_payload_json"]),
        content_type=str(row["content_type"]),
        received_at=_datetime_from_db(row["received_at"]),
    )


def _ai_research_output_record(row: sqlite3.Row) -> AIResearchOutputRecord:
    return AIResearchOutputRecord(
        output_id=str(row["output_id"]),
        symbol=str(row["symbol"]),
        prompt_version=str(row["prompt_version"]),
        schema_version=str(row["schema_version"]),
        model_version=str(row["model_version"]),
        raw_prompt=str(row["raw_prompt"]),
        raw_prompt_hash=str(row["raw_prompt_hash"]),
        raw_output=_optional_str(row["raw_output"]),
        raw_output_hash=_optional_str(row["raw_output_hash"]),
        parsed_output=dict(_json_from_db(row["parsed_output_json"])),
        ai_score=int(row["ai_score"]),
        hard_block=bool(row["hard_block"]),
        fallback_reason=str(row["fallback_reason"]),
        citations=tuple(str(item) for item in _json_from_db(row["citations_json"])),
        canonical_urls=tuple(str(item) for item in _json_from_db(row["canonical_urls_json"])),
        created_at=_datetime_from_db(row["created_at"]),
    )


def _execution_intent_record(row: sqlite3.Row) -> ExecutionIntentRecord:
    return ExecutionIntentRecord(
        execution_intent_id=str(row["execution_intent_id"]),
        temporal_workflow_id=_optional_str(row["temporal_workflow_id"]),
        decision_id=str(row["decision_id"]),
        client_order_id_root=str(row["client_order_id_root"]),
        symbol=str(row["symbol"]),
        side=row["side"],
        asset_class=row["asset_class"],
        quantity=int(row["quantity"]),
        entry_order_type=row["entry_order_type"],
        limit_price=float(row["limit_price"]),
        stop_loss_price=_optional_float(row["stop_loss_price"]),
        time_in_force=row["time_in_force"],
        strategy_version=str(row["strategy_version"]),
        risk_config_version=str(row["risk_config_version"]),
        autonomy_level=int(row["autonomy_level"]),
        requires_protective_stop=bool(row["requires_protective_stop"]),
        max_acceptable_slippage_bps=int(row["max_acceptable_slippage_bps"]),
        status=str(row["status"]),
        payload=dict(_json_from_db(row["payload_json"])),
        expires_at=_datetime_from_db(row["expires_at"]),
        created_at=_datetime_from_db(row["created_at"]),
    )


def _trade_candidate_record(row: sqlite3.Row) -> TradeCandidateRecord:
    return TradeCandidateRecord(
        candidate_id=str(row["candidate_id"]),
        symbol=str(row["symbol"]),
        trading_date=_date_from_db(row["trading_date"]),
        strategy_version=str(row["strategy_version"]),
        candidate_status=str(row["candidate_status"]),
        technical_score=_optional_float(row["technical_score"]),
        relative_strength_score=_optional_float(row["relative_strength_score"]),
        score_payload=dict(_json_from_db(row["score_payload_json"])),
        reason_payload=dict(_json_from_db(row["reason_payload_json"])),
        rejection_reasons=tuple(str(item) for item in _json_from_db(row["rejection_reasons_json"])),
        source_features_daily_id=_optional_str(row["source_features_daily_id"]),
        created_at=_datetime_from_db(row["created_at"]),
    )


def _trade_decision_record(row: sqlite3.Row) -> TradeDecisionRecord:
    return TradeDecisionRecord(
        decision_id=str(row["decision_id"]),
        candidate_id=_optional_str(row["candidate_id"]),
        symbol=str(row["symbol"]),
        decision_status=str(row["decision_status"]),
        final_score=_optional_float(row["final_score"]),
        deterministic_decision_payload=dict(
            _json_from_db(row["deterministic_decision_payload_json"])
        ),
        ai_output_id=_optional_str(row["ai_output_id"]),
        created_at=_datetime_from_db(row["created_at"]),
    )


def _risk_check_record(row: sqlite3.Row) -> RiskCheckRecord:
    return RiskCheckRecord(
        risk_check_id=str(row["risk_check_id"]),
        decision_id=_optional_str(row["decision_id"]),
        execution_intent_id=_optional_str(row["execution_intent_id"]),
        symbol=str(row["symbol"]),
        passed=bool(row["passed"]),
        reason_codes=tuple(str(item) for item in _json_from_db(row["reason_codes_json"])),
        risk_config_version=str(row["risk_config_version"]),
        input_snapshot=dict(_json_from_db(row["input_snapshot_json"])),
        result_payload=dict(_json_from_db(row["result_payload_json"])),
        created_at=_datetime_from_db(row["created_at"]),
    )


def _order_record(row: sqlite3.Row) -> OrderRecord:
    return OrderRecord(
        order_id=str(row["order_id"]),
        execution_intent_id=_optional_str(row["execution_intent_id"]),
        broker_order_id=_optional_str(row["broker_order_id"]),
        client_order_id=str(row["client_order_id"]),
        symbol=str(row["symbol"]),
        side=row["side"],
        order_type=str(row["order_type"]),
        time_in_force=str(row["time_in_force"]),
        quantity=float(row["quantity"]),
        limit_price=_optional_float(row["limit_price"]),
        stop_price=_optional_float(row["stop_price"]),
        status=str(row["status"]),
        raw_broker_payload=dict(_json_from_db(row["raw_broker_payload_json"])),
        created_at=_datetime_from_db(row["created_at"]),
        updated_at=_datetime_from_db(row["updated_at"]),
    )


def _fill_record(row: sqlite3.Row) -> FillRecord:
    return FillRecord(
        fill_id=str(row["fill_id"]),
        order_id=str(row["order_id"]),
        broker_order_id=_optional_str(row["broker_order_id"]),
        broker_fill_id=_optional_str(row["broker_fill_id"]),
        symbol=str(row["symbol"]),
        quantity=float(row["quantity"]),
        price=float(row["price"]),
        filled_at=_datetime_from_db(row["filled_at"]),
        raw_broker_payload=dict(_json_from_db(row["raw_broker_payload_json"])),
        created_at=_datetime_from_db(row["created_at"]),
    )


def _position_record(row: sqlite3.Row) -> PositionRecord:
    return PositionRecord(
        position_id=str(row["position_id"]),
        symbol=str(row["symbol"]),
        quantity=float(row["quantity"]),
        average_entry_price=float(row["average_entry_price"]),
        status=str(row["status"]),
        protective_stop_order_id=_optional_str(row["protective_stop_order_id"]),
        opened_at=_optional_datetime_from_db(row["opened_at"]),
        closed_at=_optional_datetime_from_db(row["closed_at"]),
        raw_source_payload=dict(_json_from_db(row["raw_source_payload_json"])),
        created_at=_datetime_from_db(row["created_at"]),
        updated_at=_datetime_from_db(row["updated_at"]),
    )


def _broker_reconciliation_record(row: sqlite3.Row) -> BrokerReconciliationRecord:
    return BrokerReconciliationRecord(
        reconciliation_id=str(row["reconciliation_id"]),
        temporal_workflow_id=_optional_str(row["temporal_workflow_id"]),
        account_snapshot=dict(_json_from_db(row["account_snapshot_json"])),
        broker_positions=list(_json_from_db(row["broker_positions_json"])),
        internal_positions=list(_json_from_db(row["internal_positions_json"])),
        broker_orders=list(_json_from_db(row["broker_orders_json"])),
        internal_orders=list(_json_from_db(row["internal_orders_json"])),
        mismatches=list(_json_from_db(row["mismatches_json"])),
        status=str(row["status"]),
        created_at=_datetime_from_db(row["created_at"]),
    )


def _system_event_record(row: sqlite3.Row) -> SystemEventRecord:
    return SystemEventRecord(
        event_id=str(row["event_id"]),
        event_type=str(row["event_type"]),
        severity=row["severity"],
        source_component=str(row["source_component"]),
        related_entity_type=_optional_str(row["related_entity_type"]),
        related_entity_id=_optional_str(row["related_entity_id"]),
        message=str(row["message"]),
        payload=dict(_json_from_db(row["payload_json"])),
        created_at=_datetime_from_db(row["created_at"]),
        acknowledged_at=_optional_datetime_from_db(row["acknowledged_at"]),
    )


def _report_record(row: sqlite3.Row) -> ReportRecord:
    return ReportRecord(
        report_id=str(row["report_id"]),
        report_type=str(row["report_type"]),
        report_date=_optional_date_from_db(row["report_date"]),
        period_start=_optional_date_from_db(row["period_start"]),
        period_end=_optional_date_from_db(row["period_end"]),
        status=str(row["status"]),
        payload=dict(_json_from_db(row["payload_json"])),
        markdown=_optional_str(row["markdown"]),
        created_at=_datetime_from_db(row["created_at"]),
    )


def _raw_provider_payload_json(payload: RawProviderPayload) -> Any:
    try:
        return json.loads(payload.raw_payload)
    except json.JSONDecodeError:
        return {"raw_payload": payload.raw_payload}


def _json_for_db(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _json_from_db(value: Any) -> Any:
    if not isinstance(value, str):
        raise LedgerRepositoryError(f"expected JSON text from database, got {type(value).__name__}")
    return json.loads(value)


def _datetime_for_db(value: datetime) -> str:
    if value.tzinfo is None:
        raise ValueError("database timestamps must be timezone-aware")
    return value.isoformat()


def _optional_datetime_for_db(value: datetime | None) -> str | None:
    return None if value is None else _datetime_for_db(value)


def _datetime_from_db(value: Any) -> datetime:
    if not isinstance(value, str):
        raise LedgerRepositoryError("database timestamp must be stored as text")
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        raise LedgerRepositoryError("database timestamp must be timezone-aware")
    return parsed


def _optional_datetime_from_db(value: Any) -> datetime | None:
    if value is None:
        return None
    return _datetime_from_db(value)


def _optional_date_for_db(value: date | None) -> str | None:
    return None if value is None else value.isoformat()


def _date_for_db(value: date) -> str:
    return value.isoformat()


def _date_from_db(value: Any) -> date:
    if not isinstance(value, str):
        raise LedgerRepositoryError("database date must be stored as text")
    return date.fromisoformat(value)


def _optional_date_from_db(value: Any) -> date | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise LedgerRepositoryError("database date must be stored as text")
    return date.fromisoformat(value)


def _optional_str(value: Any) -> str | None:
    return None if value is None else str(value)


def _optional_float(value: Any) -> float | None:
    return None if value is None else float(value)


def _bool_for_db(value: bool) -> int:
    return 1 if value else 0


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _new_id() -> str:
    return str(uuid4())
