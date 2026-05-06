"""Postgres-backed audit-ledger repository for explicit runtime validation.

The local SQLite repository remains the default for unit tests and fake/local dry runs. This
repository is for operator-invoked managed Postgres/Supabase validation and future server-side
runtime wiring. It never reads environment variables, opens network connections, or calls broker,
AI/news, alert, Temporal, or trading services. Transaction commit/rollback is owned by the caller.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from datetime import UTC, date, datetime
from typing import Any, Literal
from uuid import UUID, uuid4

from psycopg import Connection
from psycopg.types.json import Jsonb

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
from packages.ledger.repositories import LedgerRepositoryError
from packages.reconciliation.models import ReconciliationResult

Row = Mapping[str, Any]


class PostgresLedgerRepository:
    """Postgres/Supabase repository implementation using an explicit psycopg connection."""

    def __init__(self, connection: Connection[dict[str, Any]]) -> None:
        self._connection = connection

    def insert_raw_provider_payload(
        self,
        payload: RawProviderPayload,
    ) -> RawProviderPayloadRecord:
        row = self._fetch_one(
            """
            INSERT INTO raw_provider_payloads (
                provider,
                endpoint,
                symbol,
                payload_hash,
                raw_payload,
                content_type,
                received_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING *
            """,
            (
                payload.provider,
                payload.endpoint,
                payload.symbol,
                payload.payload_hash,
                Jsonb(_raw_provider_payload_json(payload)),
                payload.content_type,
                payload.fetched_at,
            ),
        )
        return _raw_provider_payload_record(_required_row(row, "raw provider payload insert"))

    def get_raw_provider_payload_by_hash(
        self,
        *,
        provider: str,
        endpoint: str,
        payload_hash: str,
    ) -> RawProviderPayloadRecord | None:
        row = self._fetch_one(
            """
            SELECT *
            FROM raw_provider_payloads
            WHERE provider = %s AND endpoint = %s AND payload_hash = %s
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
        row = self._fetch_one(
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
                parsed_output,
                ai_score,
                hard_block,
                fallback_reason,
                citations,
                canonical_urls,
                created_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING *
            """,
            (
                _uuid_or_new(output_id),
                payload.symbol,
                payload.prompt_version,
                payload.schema_version,
                payload.model_version,
                payload.raw_prompt,
                payload.raw_prompt_hash,
                payload.raw_ai_output,
                payload.raw_output_hash,
                Jsonb(payload.parsed_output.model_dump(mode="json")),
                payload.parsed_output.ai_score,
                payload.parsed_output.hard_block,
                payload.fallback_reason,
                Jsonb(list(payload.citations)),
                Jsonb(list(payload.canonical_urls)),
                payload.created_at,
            ),
        )
        return _ai_research_output_record(_required_row(row, "AI research output insert"))

    def get_ai_research_output(self, output_id: str) -> AIResearchOutputRecord | None:
        row = self._fetch_one(
            "SELECT * FROM ai_research_outputs WHERE output_id = %s",
            (_uuid(output_id),),
        )
        return None if row is None else _ai_research_output_record(row)

    def insert_execution_intent(
        self,
        intent: ExecutionIntent,
        *,
        execution_intent_id: str | None = None,
        payload: Mapping[str, Any] | None = None,
    ) -> ExecutionIntentRecord:
        stored_payload = dict(payload or intent.model_dump(mode="json"))
        row = self._fetch_one(
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
                payload,
                expires_at,
                created_at
            )
            VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
            )
            RETURNING *
            """,
            (
                _uuid_or_new(execution_intent_id),
                intent.temporal_workflow_id,
                intent.decision_id,
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
                intent.requires_protective_stop,
                intent.max_acceptable_slippage_bps,
                intent.status,
                Jsonb(stored_payload),
                intent.expires_at,
                _utc_now(),
            ),
        )
        return _execution_intent_record(_required_row(row, "execution intent insert"))

    def get_execution_intent_by_id(
        self,
        execution_intent_id: str,
    ) -> ExecutionIntentRecord | None:
        row = self._fetch_one(
            "SELECT * FROM execution_intents WHERE execution_intent_id = %s",
            (_uuid(execution_intent_id),),
        )
        return None if row is None else _execution_intent_record(row)

    def get_execution_intent_by_client_order_id_root(
        self,
        client_order_id_root: str,
    ) -> ExecutionIntentRecord | None:
        row = self._fetch_one(
            "SELECT * FROM execution_intents WHERE client_order_id_root = %s",
            (client_order_id_root,),
        )
        return None if row is None else _execution_intent_record(row)

    def list_active_execution_intents(
        self,
        *,
        statuses: Sequence[str] = ("created", "risk_approved", "submitted_to_workflow"),
        limit: int = 100,
    ) -> tuple[ExecutionIntentRecord, ...]:
        rows = self._fetch_all(
            """
            SELECT *
            FROM execution_intents
            WHERE status = ANY(%s)
            ORDER BY created_at DESC, execution_intent_id DESC
            LIMIT %s
            """,
            (list(statuses), limit),
        )
        return tuple(_execution_intent_record(row) for row in rows)

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
        row = self._fetch_one(
            """
            INSERT INTO trade_candidates (
                candidate_id,
                symbol,
                trading_date,
                strategy_version,
                candidate_status,
                technical_score,
                relative_strength_score,
                score_payload,
                reason_payload,
                rejection_reasons,
                source_features_daily_id,
                created_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING *
            """,
            (
                _uuid_or_new(candidate_id),
                symbol,
                trading_date,
                strategy_version,
                candidate_status,
                technical_score,
                relative_strength_score,
                Jsonb(dict(score_payload or {})),
                Jsonb(dict(reason_payload or {})),
                Jsonb(list(rejection_reasons)),
                _optional_uuid(source_features_daily_id),
                created_at or _utc_now(),
            ),
        )
        return _trade_candidate_record(_required_row(row, "trade candidate insert"))

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
        row = self._fetch_one(
            """
            INSERT INTO trade_decisions (
                decision_id,
                candidate_id,
                symbol,
                decision_status,
                final_score,
                deterministic_decision_payload,
                ai_output_id,
                created_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING *
            """,
            (
                _uuid_or_new(decision_id),
                _optional_uuid(candidate_id),
                symbol,
                decision_status,
                final_score,
                Jsonb(dict(deterministic_decision_payload or {})),
                _optional_uuid(ai_output_id),
                created_at or _utc_now(),
            ),
        )
        return _trade_decision_record(_required_row(row, "trade decision insert"))

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
        row = self._fetch_one(
            """
            INSERT INTO risk_checks (
                risk_check_id,
                decision_id,
                execution_intent_id,
                symbol,
                passed,
                reason_codes,
                risk_config_version,
                input_snapshot,
                result_payload,
                created_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING *
            """,
            (
                _uuid_or_new(risk_check_id),
                _optional_uuid(decision_id),
                _optional_uuid(execution_intent_id),
                symbol,
                passed,
                Jsonb(list(reason_codes)),
                risk_config_version,
                Jsonb(dict(input_snapshot or {})),
                Jsonb(dict(result_payload or {})),
                created_at or _utc_now(),
            ),
        )
        return _risk_check_record(_required_row(row, "risk check insert"))

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
        created = created_at or _utc_now()
        updated = updated_at or created
        row = self._fetch_one(
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
                raw_broker_payload,
                created_at,
                updated_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING *
            """,
            (
                _uuid_or_new(order_id),
                _optional_uuid(execution_intent_id),
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
                Jsonb(dict(raw_broker_payload or {})),
                created,
                updated,
            ),
        )
        return _order_record(_required_row(row, "order insert"))

    def get_order_by_client_order_id(self, client_order_id: str) -> OrderRecord | None:
        row = self._fetch_one(
            "SELECT * FROM orders WHERE client_order_id = %s",
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
        row = self._fetch_one(
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
                raw_broker_payload,
                created_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING *
            """,
            (
                _uuid_or_new(fill_id),
                _uuid(order_id),
                broker_order_id,
                broker_fill_id,
                symbol,
                quantity,
                price,
                filled_at,
                Jsonb(dict(raw_broker_payload or {})),
                created_at or _utc_now(),
            ),
        )
        return _fill_record(_required_row(row, "fill insert"))

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
        now = _utc_now()
        if status == "open":
            row = self._fetch_one(
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
                    raw_source_payload,
                    created_at,
                    updated_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (symbol) WHERE status = 'open'
                DO UPDATE SET
                    quantity = EXCLUDED.quantity,
                    average_entry_price = EXCLUDED.average_entry_price,
                    protective_stop_order_id = EXCLUDED.protective_stop_order_id,
                    opened_at = EXCLUDED.opened_at,
                    closed_at = EXCLUDED.closed_at,
                    raw_source_payload = EXCLUDED.raw_source_payload,
                    updated_at = EXCLUDED.updated_at
                RETURNING *
                """,
                (
                    uuid4(),
                    symbol,
                    quantity,
                    average_entry_price,
                    status,
                    _optional_uuid(protective_stop_order_id),
                    opened_at,
                    closed_at,
                    Jsonb(dict(raw_source_payload or {})),
                    now,
                    now,
                ),
            )
        else:
            row = self._fetch_one(
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
                    raw_source_payload,
                    created_at,
                    updated_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING *
                """,
                (
                    uuid4(),
                    symbol,
                    quantity,
                    average_entry_price,
                    status,
                    _optional_uuid(protective_stop_order_id),
                    opened_at,
                    closed_at,
                    Jsonb(dict(raw_source_payload or {})),
                    now,
                    now,
                ),
            )
        return _position_record(_required_row(row, "position upsert"))

    def get_position(self, position_id: str) -> PositionRecord | None:
        row = self._fetch_one(
            "SELECT * FROM positions WHERE position_id = %s",
            (_uuid(position_id),),
        )
        return None if row is None else _position_record(row)

    def get_open_position(self, symbol: str) -> PositionRecord | None:
        row = self._fetch_one(
            "SELECT * FROM positions WHERE symbol = %s AND status = 'open'",
            (symbol,),
        )
        return None if row is None else _position_record(row)

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
        row = self._fetch_one(
            """
            INSERT INTO broker_reconciliations (
                reconciliation_id,
                temporal_workflow_id,
                account_snapshot,
                broker_positions,
                internal_positions,
                broker_orders,
                internal_orders,
                mismatches,
                status,
                created_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING *
            """,
            (
                _uuid_or_new(reconciliation_id),
                temporal_workflow_id,
                Jsonb(dict(account_snapshot)),
                Jsonb(list(broker_positions)),
                Jsonb(list(internal_positions)),
                Jsonb(list(broker_orders)),
                Jsonb(list(internal_orders)),
                Jsonb(list(mismatches)),
                status,
                created_at or _utc_now(),
            ),
        )
        return _broker_reconciliation_record(_required_row(row, "broker reconciliation insert"))

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
            SELECT *
            FROM broker_reconciliations
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
        row = self._fetch_one(
            """
            INSERT INTO system_events (
                event_id,
                event_type,
                severity,
                source_component,
                related_entity_type,
                related_entity_id,
                message,
                payload,
                created_at,
                acknowledged_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING *
            """,
            (
                _uuid_or_new(event_id),
                event_type,
                severity,
                source_component,
                related_entity_type,
                related_entity_id,
                message,
                Jsonb(dict(payload or {})),
                created_at or _utc_now(),
                acknowledged_at,
            ),
        )
        return _system_event_record(_required_row(row, "system event insert"))

    def list_system_events(self, *, limit: int = 100) -> tuple[SystemEventRecord, ...]:
        rows = self._fetch_all(
            "SELECT * FROM system_events ORDER BY created_at DESC, event_id DESC LIMIT %s",
            (limit,),
        )
        return tuple(_system_event_record(row) for row in rows)

    def list_recent_incidents(self, *, limit: int = 100) -> tuple[SystemEventRecord, ...]:
        rows = self._fetch_all(
            """
            SELECT *
            FROM system_events
            WHERE event_type LIKE '%%incident%%' OR severity IN ('warning', 'critical')
            ORDER BY created_at DESC, event_id DESC
            LIMIT %s
            """,
            (limit,),
        )
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
        row = self._fetch_one(
            """
            INSERT INTO reports (
                report_id,
                report_type,
                report_date,
                period_start,
                period_end,
                status,
                payload,
                markdown,
                created_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING *
            """,
            (
                _uuid_or_new(report_id),
                report_type,
                report_date,
                period_start,
                period_end,
                status,
                Jsonb(dict(payload or {})),
                markdown,
                created_at or _utc_now(),
            ),
        )
        return _report_record(_required_row(row, "report insert"))

    def get_report(self, report_id: str) -> ReportRecord | None:
        row = self._fetch_one(
            "SELECT * FROM reports WHERE report_id = %s",
            (_uuid(report_id),),
        )
        return None if row is None else _report_record(row)

    def _fetch_one(self, query: str, params: tuple[Any, ...]) -> Row | None:
        with self._connection.cursor() as cursor:
            cursor.execute(query, params)
            return cursor.fetchone()

    def _fetch_all(self, query: str, params: tuple[Any, ...]) -> tuple[Row, ...]:
        with self._connection.cursor() as cursor:
            cursor.execute(query, params)
            return tuple(cursor.fetchall())


def _raw_provider_payload_record(row: Row) -> RawProviderPayloadRecord:
    return RawProviderPayloadRecord(
        raw_provider_payload_id=str(row["raw_provider_payload_id"]),
        provider=str(row["provider"]),
        endpoint=str(row["endpoint"]),
        symbol=_optional_str(row["symbol"]),
        payload_hash=str(row["payload_hash"]),
        raw_payload=_json_value(row["raw_payload"]),
        content_type=str(row["content_type"]),
        received_at=_datetime_value(row["received_at"]),
    )


def _ai_research_output_record(row: Row) -> AIResearchOutputRecord:
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
        parsed_output=_dict_value(row["parsed_output"]),
        ai_score=int(row["ai_score"]),
        hard_block=bool(row["hard_block"]),
        fallback_reason=str(row["fallback_reason"]),
        citations=tuple(str(item) for item in _list_value(row["citations"])),
        canonical_urls=tuple(str(item) for item in _list_value(row["canonical_urls"])),
        created_at=_datetime_value(row["created_at"]),
    )


def _execution_intent_record(row: Row) -> ExecutionIntentRecord:
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
        payload=_dict_value(row["payload"]),
        expires_at=_datetime_value(row["expires_at"]),
        created_at=_datetime_value(row["created_at"]),
    )


def _trade_candidate_record(row: Row) -> TradeCandidateRecord:
    return TradeCandidateRecord(
        candidate_id=str(row["candidate_id"]),
        symbol=str(row["symbol"]),
        trading_date=_date_value(row["trading_date"]),
        strategy_version=str(row["strategy_version"]),
        candidate_status=str(row["candidate_status"]),
        technical_score=_optional_float(row["technical_score"]),
        relative_strength_score=_optional_float(row["relative_strength_score"]),
        score_payload=_dict_value(row["score_payload"]),
        reason_payload=_dict_value(row["reason_payload"]),
        rejection_reasons=tuple(str(item) for item in _list_value(row["rejection_reasons"])),
        source_features_daily_id=_optional_str(row["source_features_daily_id"]),
        created_at=_datetime_value(row["created_at"]),
    )


def _trade_decision_record(row: Row) -> TradeDecisionRecord:
    return TradeDecisionRecord(
        decision_id=str(row["decision_id"]),
        candidate_id=_optional_str(row["candidate_id"]),
        symbol=str(row["symbol"]),
        decision_status=str(row["decision_status"]),
        final_score=_optional_float(row["final_score"]),
        deterministic_decision_payload=_dict_value(row["deterministic_decision_payload"]),
        ai_output_id=_optional_str(row["ai_output_id"]),
        created_at=_datetime_value(row["created_at"]),
    )


def _risk_check_record(row: Row) -> RiskCheckRecord:
    return RiskCheckRecord(
        risk_check_id=str(row["risk_check_id"]),
        decision_id=_optional_str(row["decision_id"]),
        execution_intent_id=_optional_str(row["execution_intent_id"]),
        symbol=str(row["symbol"]),
        passed=bool(row["passed"]),
        reason_codes=tuple(str(item) for item in _list_value(row["reason_codes"])),
        risk_config_version=str(row["risk_config_version"]),
        input_snapshot=_dict_value(row["input_snapshot"]),
        result_payload=_dict_value(row["result_payload"]),
        created_at=_datetime_value(row["created_at"]),
    )


def _order_record(row: Row) -> OrderRecord:
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
        raw_broker_payload=_dict_value(row["raw_broker_payload"]),
        created_at=_datetime_value(row["created_at"]),
        updated_at=_datetime_value(row["updated_at"]),
    )


def _fill_record(row: Row) -> FillRecord:
    return FillRecord(
        fill_id=str(row["fill_id"]),
        order_id=str(row["order_id"]),
        broker_order_id=_optional_str(row["broker_order_id"]),
        broker_fill_id=_optional_str(row["broker_fill_id"]),
        symbol=str(row["symbol"]),
        quantity=float(row["quantity"]),
        price=float(row["price"]),
        filled_at=_datetime_value(row["filled_at"]),
        raw_broker_payload=_dict_value(row["raw_broker_payload"]),
        created_at=_datetime_value(row["created_at"]),
    )


def _position_record(row: Row) -> PositionRecord:
    return PositionRecord(
        position_id=str(row["position_id"]),
        symbol=str(row["symbol"]),
        quantity=float(row["quantity"]),
        average_entry_price=float(row["average_entry_price"]),
        status=str(row["status"]),
        protective_stop_order_id=_optional_str(row["protective_stop_order_id"]),
        opened_at=_optional_datetime_value(row["opened_at"]),
        closed_at=_optional_datetime_value(row["closed_at"]),
        raw_source_payload=_dict_value(row["raw_source_payload"]),
        created_at=_datetime_value(row["created_at"]),
        updated_at=_datetime_value(row["updated_at"]),
    )


def _broker_reconciliation_record(row: Row) -> BrokerReconciliationRecord:
    return BrokerReconciliationRecord(
        reconciliation_id=str(row["reconciliation_id"]),
        temporal_workflow_id=_optional_str(row["temporal_workflow_id"]),
        account_snapshot=_dict_value(row["account_snapshot"]),
        broker_positions=_list_value(row["broker_positions"]),
        internal_positions=_list_value(row["internal_positions"]),
        broker_orders=_list_value(row["broker_orders"]),
        internal_orders=_list_value(row["internal_orders"]),
        mismatches=_list_value(row["mismatches"]),
        status=str(row["status"]),
        created_at=_datetime_value(row["created_at"]),
    )


def _system_event_record(row: Row) -> SystemEventRecord:
    return SystemEventRecord(
        event_id=str(row["event_id"]),
        event_type=str(row["event_type"]),
        severity=row["severity"],
        source_component=str(row["source_component"]),
        related_entity_type=_optional_str(row["related_entity_type"]),
        related_entity_id=_optional_str(row["related_entity_id"]),
        message=str(row["message"]),
        payload=_dict_value(row["payload"]),
        created_at=_datetime_value(row["created_at"]),
        acknowledged_at=_optional_datetime_value(row["acknowledged_at"]),
    )


def _report_record(row: Row) -> ReportRecord:
    return ReportRecord(
        report_id=str(row["report_id"]),
        report_type=str(row["report_type"]),
        report_date=_optional_date_value(row["report_date"]),
        period_start=_optional_date_value(row["period_start"]),
        period_end=_optional_date_value(row["period_end"]),
        status=str(row["status"]),
        payload=_dict_value(row["payload"]),
        markdown=_optional_str(row["markdown"]),
        created_at=_datetime_value(row["created_at"]),
    )


def _raw_provider_payload_json(payload: RawProviderPayload) -> Any:
    try:
        return json.loads(payload.raw_payload)
    except json.JSONDecodeError:
        return {"raw_payload": payload.raw_payload}


def _required_row(row: Row | None, context: str) -> Row:
    if row is None:
        raise LedgerRepositoryError(f"{context} did not return a row")
    return row


def _json_value(value: Any) -> Any:
    if isinstance(value, str):
        return json.loads(value)
    return value


def _dict_value(value: Any) -> dict[str, Any]:
    loaded = _json_value(value)
    if not isinstance(loaded, dict):
        raise LedgerRepositoryError(f"expected JSON object, got {type(loaded).__name__}")
    return loaded


def _list_value(value: Any) -> list[Any]:
    loaded = _json_value(value)
    if not isinstance(loaded, list):
        raise LedgerRepositoryError(f"expected JSON array, got {type(loaded).__name__}")
    return loaded


def _datetime_value(value: Any) -> datetime:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            raise LedgerRepositoryError("database timestamp must be timezone-aware")
        return value
    if isinstance(value, str):
        parsed = datetime.fromisoformat(value)
        if parsed.tzinfo is None:
            raise LedgerRepositoryError("database timestamp must be timezone-aware")
        return parsed
    raise LedgerRepositoryError(f"expected datetime value, got {type(value).__name__}")


def _optional_datetime_value(value: Any) -> datetime | None:
    if value is None:
        return None
    return _datetime_value(value)


def _date_value(value: Any) -> date:
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, str):
        return date.fromisoformat(value)
    raise LedgerRepositoryError(f"expected date value, got {type(value).__name__}")


def _optional_date_value(value: Any) -> date | None:
    if value is None:
        return None
    return _date_value(value)


def _uuid(value: str) -> UUID:
    return UUID(value)


def _uuid_or_new(value: str | None) -> UUID:
    return uuid4() if value is None else _uuid(value)


def _optional_uuid(value: str | None) -> UUID | None:
    return None if value is None else _uuid(value)


def _optional_str(value: Any) -> str | None:
    return None if value is None else str(value)


def _optional_float(value: Any) -> float | None:
    return None if value is None else float(value)


def _utc_now() -> datetime:
    return datetime.now(UTC)
