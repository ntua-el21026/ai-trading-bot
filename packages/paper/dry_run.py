"""End-to-end fake/local paper dry-run orchestration.

This module is explicit dry-run validation code. It uses only local SQLite repositories, fake broker
clients, neutral/fake AI output, fake alert adapters, and pure report/dashboard read models.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import datetime, timedelta
from typing import Any
from uuid import NAMESPACE_URL, UUID, uuid5

from packages.ai.fallback import neutral_research_output
from packages.ai.models import AI_PROMPT_VERSION, AI_SCHEMA_VERSION, FallbackReason
from packages.ai.persistence import build_ai_research_persistence_payload
from packages.alerting.adapters import FakeAlertAdapter
from packages.alerting.models import AlertCategory, AlertMessage, AlertSeverity
from packages.alerting.routing import AlertRouter
from packages.broker.alpaca import AlpacaClientError
from packages.broker.fakes import FakeAlpacaClient, build_fake_alpaca_paper_adapter
from packages.broker.models import (
    BrokerAccountSnapshot,
    BrokerFill,
    BrokerOrder,
    BrokerPosition,
    BrokerProtectiveStop,
    BrokerSnapshot,
)
from packages.control_plane.models import DashboardSnapshot
from packages.control_plane.service import LedgerDashboardReadModelProvider
from packages.core.config import AppConfig, ExecutionConfig, SystemConfig, load_app_config
from packages.data.payloads import build_raw_provider_payload
from packages.execution.execution_intent import create_execution_intent
from packages.execution.models import ExecutionIntent
from packages.ledger.connection import connect_in_memory_sqlite
from packages.ledger.models import OrderRecord
from packages.ledger.repositories import SQLiteLedgerRepository
from packages.paper.fixtures import default_dry_run_input
from packages.paper.models import (
    DryRunEvidence,
    DryRunFailureMode,
    DryRunInput,
    DryRunResult,
    DryRunSafetyFlags,
    DryRunStepResult,
    DryRunStepStatus,
)
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
from packages.reporting.generators import generate_daily_report
from packages.reporting.ledger import (
    build_report_input_snapshot,
    persist_report_generation_result,
)
from packages.risk.checks import evaluate_new_risk_order
from packages.risk.kill_switch import pause_new_risk, running_state
from packages.risk.models import KillSwitchSnapshot, NewRiskOrderInput, RiskAssessment


def run_paper_dry_run(
    dry_run_input: DryRunInput | None = None,
    *,
    repository: SQLiteLedgerRepository | None = None,
    app_config: AppConfig | None = None,
) -> DryRunResult:
    """Run one fake/local paper dry-run scenario."""

    orchestrator = PaperDryRunOrchestrator(
        repository=repository,
        app_config=app_config,
    )
    return orchestrator.run(dry_run_input or default_dry_run_input())


class PaperDryRunOrchestrator:
    """Coordinates a fake/local dry-run through existing package boundaries."""

    def __init__(
        self,
        *,
        repository: SQLiteLedgerRepository | None = None,
        app_config: AppConfig | None = None,
        alert_adapter: FakeAlertAdapter | None = None,
    ) -> None:
        self.repository = repository or SQLiteLedgerRepository(connect_in_memory_sqlite())
        self.app_config = app_config or load_app_config()
        self.alert_adapter = alert_adapter or FakeAlertAdapter()
        self.alert_router = AlertRouter(adapters=(self.alert_adapter,))

    def run(self, dry_run_input: DryRunInput) -> DryRunResult:
        state = _DryRunState(
            dry_run_input,
            self.repository,
            self.app_config,
            self.alert_router,
            self.alert_adapter,
        )
        state.add_step("initialize_local_ledger", "passed", "local_sqlite_ledger_ready")
        state.add_step("load_safe_runtime_config", "passed", "safe_runtime_config_loaded")

        safety_flags = _safety_flags(self.app_config)
        if dry_run_input.config.require_safe_runtime_flags and not safety_flags.safe:
            state.add_step("verify_safety_flags", "failed", "unsafe_runtime_flags")
            return state.result(safety_flags=safety_flags, passed=False)
        state.add_step("verify_safety_flags", "passed", "runtime_flags_safe")

        _persist_fixture_data(state)
        _persist_candidate_and_ai(state)
        _persist_decision(state)
        _maybe_insert_duplicate_intent_fixture(state)

        risk_assessment = _run_risk_gate(state)
        if not risk_assessment.approved:
            _persist_risk_check(state, risk_assessment, execution_intent_id=None)
            _record_failure_event_and_alert(
                state,
                event_type="paper_dry_run_risk_rejection_incident",
                category=_category_for_failure(state.failure_mode),
                severity="warning",
                reason_codes=risk_assessment.rejection_reasons,
                message="Dry-run risk gate rejected the fake/local candidate.",
            )
            _generate_report_and_dashboard(state)
            return state.result(safety_flags=safety_flags, passed=False)

        intent = _create_and_persist_intent(state, risk_assessment)
        _persist_risk_check(state, risk_assessment, execution_intent_id=state.intent_record_id)

        broker_client = _fake_broker_client(state.failure_mode, state)
        adapter = build_fake_alpaca_paper_adapter(client=broker_client)
        entry_result = adapter.submit_entry_order(intent)
        state.evidence.fake_broker_order_request_count = len(broker_client.submitted_order_requests)

        if entry_result.status == "ambiguous":
            state.add_step("submit_fake_entry_order", "failed", "broker_ambiguity_detected")
            _record_failure_event_and_alert(
                state,
                event_type="paper_dry_run_broker_ambiguity_incident",
                category="broker_ambiguity",
                severity="critical",
                reason_codes=("broker_ambiguity",),
                message="Fake broker submit returned an ambiguous result.",
            )
            _generate_report_and_dashboard(state)
            return state.result(safety_flags=safety_flags, passed=False)
        if entry_result.status != "succeeded" or entry_result.order is None:
            state.add_step("submit_fake_entry_order", "failed", "fake_entry_submit_failed")
            _record_failure_event_and_alert(
                state,
                event_type="paper_dry_run_order_submit_incident",
                category="broker_ambiguity",
                severity="critical",
                reason_codes=("fake_entry_submit_failed",),
                message="Fake broker submit failed before order acknowledgement.",
            )
            _generate_report_and_dashboard(state)
            return state.result(safety_flags=safety_flags, passed=False)

        state.add_step("submit_fake_entry_order", "passed", "fake_entry_order_acknowledged")
        entry_order_record = _persist_order(state, entry_result.order)
        state.evidence.fake_broker_order_id = entry_result.order.broker_order_id
        state.evidence.client_order_id = entry_result.order.client_order_id
        state.evidence.fake_broker_order_status = entry_result.order.status

        filled_quantity = entry_result.order.filled_quantity
        broker_fill = _persist_fill_and_position_if_needed(
            state,
            intent=intent,
            entry_order=entry_result.order,
            entry_order_id=entry_order_record.order_id,
            filled_quantity=filled_quantity,
        )

        stop_order: BrokerOrder | None = None
        stop: BrokerProtectiveStop | None = None
        if filled_quantity > 0 and state.failure_mode != "missing_protective_stop":
            broker_client.next_submit_status = "accepted"
            broker_client.next_submit_filled_qty = 0.0
            stop_result = adapter.submit_protective_stop(intent, filled_quantity=filled_quantity)
            if stop_result.status == "succeeded" and stop_result.order is not None:
                stop_order = stop_result.order
                stop_order_record = _persist_order(state, stop_result.order)
                state.stop_order_record_id = stop_order_record.order_id
                verify_result = adapter.verify_protective_stop(
                    symbol=state.scenario.symbol,
                    required_quantity=filled_quantity,
                    client_order_id=stop_result.order.client_order_id,
                )
                stop = verify_result.stop
                state.evidence.protective_stop_client_order_id = stop_result.order.client_order_id
                state.evidence.protective_stop_verified = verify_result.protected
                state.add_step(
                    "submit_and_verify_fake_protective_stop",
                    "passed" if verify_result.protected else "failed",
                    "fake_protective_stop_verified"
                    if verify_result.protected
                    else "fake_protective_stop_missing",
                    {"required_quantity": f"{filled_quantity:.6f}"},
                )
                if state.position_opened and state.position_record_id is not None:
                    state.repository.upsert_position(
                        symbol=state.scenario.symbol,
                        quantity=filled_quantity,
                        average_entry_price=state.scenario.limit_price,
                        protective_stop_order_id=state.stop_order_record_id,
                        opened_at=_position_opened_at(state),
                        raw_source_payload={"source": "fake_paper_dry_run"},
                    )
            else:
                state.add_step(
                    "submit_and_verify_fake_protective_stop",
                    "failed",
                    "fake_protective_stop_submit_failed",
                )
        elif filled_quantity > 0:
            verify_result = adapter.verify_protective_stop(
                symbol=state.scenario.symbol,
                required_quantity=filled_quantity,
            )
            state.evidence.protective_stop_verified = verify_result.protected
            state.add_step(
                "submit_and_verify_fake_protective_stop",
                "failed",
                "fake_protective_stop_intentionally_missing",
            )
        else:
            state.add_step(
                "submit_and_verify_fake_protective_stop",
                "skipped",
                "no_fake_fill_to_protect",
            )
        state.evidence.fake_broker_order_request_count = len(broker_client.submitted_order_requests)

        reconciliation = _reconcile_and_persist(
            state,
            account=adapter.account_snapshot(),
            entry_order=entry_result.order,
            stop_order=stop_order,
            broker_fill=broker_fill,
            stop=stop,
            filled_quantity=filled_quantity,
        )
        _persist_reconciliation_incidents(state, reconciliation)
        _dispatch_success_alerts(state, entry_result.order, broker_fill)
        _generate_report_and_dashboard(state)

        passed = (
            state.failure_mode in {"none", "invalid_ai_output_neutral", "partial_fill"}
            and reconciliation.clean
            and (filled_quantity == 0 or state.evidence.protective_stop_verified)
        )
        if not passed and not state.failure_reasons:
            state.failure_reasons.extend(state.evidence.reconciliation_mismatch_types)
        return state.result(safety_flags=safety_flags, passed=passed)


class _DryRunState:
    def __init__(
        self,
        dry_run_input: DryRunInput,
        repository: SQLiteLedgerRepository,
        app_config: AppConfig,
        alert_router: AlertRouter,
        alert_adapter: FakeAlertAdapter,
    ) -> None:
        self.input = dry_run_input
        self.scenario = dry_run_input.scenario
        self.failure_mode = dry_run_input.scenario.failure_mode
        self.repository = repository
        self.app_config = app_config
        self.alert_router = alert_router
        self.alert_adapter = alert_adapter
        self.steps: list[DryRunStepResult] = []
        self.failure_reasons: list[str] = []
        self.persisted_entity_ids: dict[str, list[str]] = {}
        self.evidence = DryRunEvidence()
        self.candidate_id: str | None = None
        self.ai_output_id: str | None = None
        self.decision_id: UUID | None = None
        self.intent_record_id: str | None = None
        self.entry_order_record_id: str | None = None
        self.stop_order_record_id: str | None = None
        self.position_record_id: str | None = None
        self.position_opened = False
        self.dashboard_snapshot: DashboardSnapshot | None = None

    def add_step(
        self,
        name: str,
        status: DryRunStepStatus,
        reason_code: str,
        details: Mapping[str, str] | None = None,
    ) -> None:
        self.steps.append(
            DryRunStepResult(
                name=name,
                status=status,
                reason_code=reason_code,
                details=dict(details or {}),
            )
        )
        if status == "failed":
            self.failure_reasons.append(reason_code)

    def add_entity_id(self, entity_type: str, entity_id: str) -> None:
        self.persisted_entity_ids.setdefault(entity_type, []).append(entity_id)

    def result(self, *, safety_flags: DryRunSafetyFlags, passed: bool) -> DryRunResult:
        self.evidence.persisted_entity_ids = {
            key: tuple(value) for key, value in sorted(self.persisted_entity_ids.items())
        }
        self.evidence.alert_count = len(self.alert_adapter.messages)
        self.evidence.alert_titles = tuple(
            message.title for message in self.alert_adapter.messages
        )
        return DryRunResult(
            scenario_id=self.scenario.scenario_id,
            scenario_name=self.scenario.name,
            failure_mode=self.failure_mode,
            started_at=self.input.started_at,
            completed_at=self.input.completed_at,
            steps=tuple(self.steps),
            evidence=self.evidence,
            safety_flags=safety_flags,
            passed=passed and safety_flags.safe,
            failure_reasons=tuple(dict.fromkeys(self.failure_reasons)),
            dashboard_snapshot=self.dashboard_snapshot,
        )


def _persist_fixture_data(state: _DryRunState) -> None:
    payload = {
        "symbol": state.scenario.symbol,
        "trade_date": state.scenario.trade_date.isoformat(),
        "close": state.scenario.limit_price,
        "feature_snapshot": {
            "sma_50": 170.0,
            "sma_200": 150.0,
            "volume_ratio_20": 1.35,
            "rs_63": 0.08,
            "atr_14": 3.15,
        },
        "source": "fake_paper_dry_run_fixture",
    }
    record = state.repository.insert_raw_provider_payload(
        build_raw_provider_payload(
            provider="fixture",
            endpoint="paper-dry-run/daily-feature-snapshot",
            symbol=state.scenario.symbol,
            payload=payload,
            fetched_at=state.input.started_at,
        )
    )
    state.add_entity_id("raw_provider_payloads", record.raw_provider_payload_id)
    state.add_step("persist_fixture_data", "passed", "fixture_payload_persisted")


def _persist_candidate_and_ai(state: _DryRunState) -> None:
    candidate = state.repository.insert_trade_candidate(
        candidate_id=f"candidate-{state.scenario.scenario_id}",
        symbol=state.scenario.symbol,
        trading_date=state.scenario.trade_date,
        strategy_version=state.app_config.strategy.name,
        candidate_status="accepted",
        technical_score=state.scenario.technical_score,
        relative_strength_score=state.scenario.relative_strength_score,
        score_payload={
            "source": "fake_paper_dry_run",
            "technical_score": state.scenario.technical_score,
            "relative_strength_score": state.scenario.relative_strength_score,
        },
        reason_payload={"reason_codes": ("fixture_candidate_passed",)},
        created_at=state.input.started_at,
    )
    state.candidate_id = candidate.candidate_id
    state.add_entity_id("trade_candidates", candidate.candidate_id)
    state.add_step("persist_strategy_candidate", "passed", "fixture_candidate_persisted")

    fallback_reason: FallbackReason = (
        "schema_violation"
        if state.failure_mode == "invalid_ai_output_neutral"
        else "no_news_found"
    )
    ai_output = neutral_research_output(
        symbol=state.scenario.symbol,
        analysis_at=state.input.started_at,
        prompt_version=AI_PROMPT_VERSION,
        schema_version=AI_SCHEMA_VERSION,
        model_version="fake-neutral-model",
        fallback_reason=fallback_reason,
        explanation="Fake/local dry-run AI output; no provider call was made.",
    )
    raw_prompt = f"Fake dry-run prompt for {state.scenario.symbol}."
    raw_output = json.dumps(ai_output.model_dump(mode="json"), sort_keys=True)
    ai_payload = build_ai_research_persistence_payload(
        symbol=state.scenario.symbol,
        created_at=state.input.started_at,
        raw_prompt=raw_prompt,
        raw_ai_output=raw_output,
        parsed_output=ai_output,
    )
    ai_record = state.repository.insert_ai_research_output(
        ai_payload,
        output_id=f"ai-output-{state.scenario.scenario_id}",
    )
    state.ai_output_id = ai_record.output_id
    state.add_entity_id("ai_research_outputs", ai_record.output_id)
    state.add_step(
        "persist_fake_ai_research",
        "passed",
        "neutral_ai_fallback_persisted",
        {"fallback_reason": fallback_reason},
    )


def _persist_decision(state: _DryRunState) -> None:
    state.decision_id = _scenario_uuid(state, "decision")
    final_score = (
        0.60 * state.scenario.technical_score
        + 0.20 * state.scenario.relative_strength_score
        + 0.10 * 50
        + 0.10 * 80
    )
    decision = state.repository.insert_trade_decision(
        decision_id=str(state.decision_id),
        candidate_id=state.candidate_id,
        symbol=state.scenario.symbol,
        decision_status="approved",
        final_score=round(final_score, 4),
        deterministic_decision_payload={
            "source": "fake_paper_dry_run",
            "regime": "RISK_ON",
            "ai_score": 50,
            "portfolio_fit_score": 80,
        },
        ai_output_id=state.ai_output_id,
        created_at=state.input.started_at,
    )
    state.add_entity_id("trade_decisions", decision.decision_id)
    state.add_step("persist_trade_decision", "passed", "fixture_decision_approved")


def _maybe_insert_duplicate_intent_fixture(state: _DryRunState) -> None:
    if state.failure_mode != "duplicate_active_intent":
        return
    duplicate_intent = ExecutionIntent(
        decision_id=_scenario_uuid(state, "duplicate-decision"),
        symbol=state.scenario.symbol,
        side="buy",
        asset_class=state.scenario.asset_class,
        quantity=state.scenario.quantity,
        entry_order_type="limit",
        limit_price=state.scenario.limit_price,
        stop_loss_price=state.scenario.stop_loss_price,
        time_in_force="day",
        strategy_version=state.app_config.strategy.name,
        risk_config_version="risk_v0_3",
        autonomy_level=state.app_config.system.autonomy_level,
        requires_protective_stop=True,
        max_acceptable_slippage_bps=state.app_config.execution.max_acceptable_slippage_bps,
        expires_at=state.input.started_at + timedelta(hours=1),
        client_order_id_root=f"duplicate-{state.scenario.symbol}-buy-20260506-1",
        status="risk_approved",
        temporal_workflow_id="dry-run-duplicate-workflow",
    )
    record = state.repository.insert_execution_intent(
        duplicate_intent,
        execution_intent_id=f"existing-intent-{state.scenario.scenario_id}",
    )
    state.add_entity_id("execution_intents", record.execution_intent_id)
    state.add_step("seed_duplicate_active_intent", "passed", "duplicate_fixture_persisted")


def _run_risk_gate(state: _DryRunState) -> RiskAssessment:
    risk_input = _risk_input(state)
    risk_assessment = evaluate_new_risk_order(
        risk_input,
        system_config=_risk_system_config(state),
        execution_config=_risk_execution_config(state),
        risk_config=state.app_config.risk_level_4_micro_live,
        live_universe_config=state.app_config.live_universe,
    )
    state.add_step(
        "run_deterministic_risk_gate",
        "passed" if risk_assessment.approved else "failed",
        "risk_gate_passed" if risk_assessment.approved else "risk_gate_rejected",
        {"reason_codes": ",".join(risk_assessment.rejection_reasons)},
    )
    return risk_assessment


def _risk_input(state: _DryRunState) -> NewRiskOrderInput:
    return NewRiskOrderInput(
        symbol=state.scenario.symbol,
        asset_class=state.scenario.asset_class,
        quantity=state.scenario.quantity,
        entry_price=state.scenario.limit_price,
        stop_loss_price=state.scenario.stop_loss_price,
        account_equity=state.scenario.account_equity,
        cash=state.scenario.cash,
        current_gross_exposure=0.0,
        current_deployable_capital=0.0,
        current_open_positions=0,
        current_sector_exposure_pct=0.0,
        daily_loss_pct=(
            state.app_config.risk_level_4_micro_live.max_daily_loss_pct
            if state.failure_mode == "risk_rejection"
            else 0.0
        ),
        weekly_loss_pct=0.0,
        monthly_loss_pct=0.0,
        data_is_fresh=state.failure_mode != "stale_data",
        market_session_valid=True,
        broker_reconciliation_clean=True,
        broker_account_environment="paper",
        kill_switch=_kill_switch_for_scenario(state.failure_mode),
        active_duplicate_intent=state.failure_mode == "duplicate_active_intent",
        temporal_workflow_consistent=True,
        system_health_ok=True,
    )


def _create_and_persist_intent(
    state: _DryRunState,
    risk_assessment: RiskAssessment,
) -> ExecutionIntent:
    if state.decision_id is None:
        raise RuntimeError("decision_id is required before creating execution intent")
    intent = create_execution_intent(
        decision_id=state.decision_id,
        symbol=state.scenario.symbol,
        side="buy",
        asset_class=state.scenario.asset_class,
        quantity=state.scenario.quantity,
        limit_price=state.scenario.limit_price,
        stop_loss_price=state.scenario.stop_loss_price,
        strategy_version=state.app_config.strategy.name,
        risk_config_version="risk_v0_3",
        expires_at=state.input.started_at + timedelta(hours=1),
        trade_date=state.scenario.trade_date,
        intent_sequence=1,
        risk_assessment=risk_assessment,
        system_config=_risk_system_config(state),
        execution_config=_risk_execution_config(state),
        temporal_workflow_id=f"dry-run-{state.scenario.scenario_id}-workflow",
    )
    record = state.repository.insert_execution_intent(
        intent,
        execution_intent_id=f"intent-{state.scenario.scenario_id}",
        payload=intent.model_dump(mode="json")
        | {"dry_run": True, "broker_mode": "fake", "real_orders_submitted": False},
    )
    state.intent_record_id = record.execution_intent_id
    state.evidence.execution_intent_id = record.execution_intent_id
    state.evidence.client_order_id = record.client_order_id_root
    state.add_entity_id("execution_intents", record.execution_intent_id)
    state.add_step("create_execution_intent", "passed", "execution_intent_persisted")
    return intent


def _persist_risk_check(
    state: _DryRunState,
    risk_assessment: RiskAssessment,
    *,
    execution_intent_id: str | None,
) -> None:
    record = state.repository.insert_risk_check(
        risk_check_id=f"risk-check-{state.scenario.scenario_id}",
        decision_id=None if state.decision_id is None else str(state.decision_id),
        execution_intent_id=execution_intent_id,
        symbol=state.scenario.symbol,
        passed=risk_assessment.approved,
        reason_codes=risk_assessment.rejection_reasons,
        risk_config_version="risk_v0_3",
        input_snapshot=_risk_input(state).model_dump(mode="json"),
        result_payload=risk_assessment.model_dump(mode="json"),
        created_at=state.input.started_at,
    )
    state.add_entity_id("risk_checks", record.risk_check_id)
    state.add_step("persist_risk_check", "passed", "risk_check_persisted")


def _fake_broker_client(
    failure_mode: DryRunFailureMode,
    state: _DryRunState,
) -> FakeAlpacaClient:
    if failure_mode == "broker_ambiguity":
        return FakeAlpacaClient(
            submit_error=AlpacaClientError(
                "broker_timeout",
                "fake broker submit timed out after request write",
                retryable=True,
                ambiguous=True,
                pause_new_risk=True,
            )
        )
    if failure_mode == "partial_fill":
        return FakeAlpacaClient(
            next_submit_status="partially_filled",
            next_submit_filled_qty=float(state.scenario.filled_quantity),
        )
    return FakeAlpacaClient(
        next_submit_status="filled",
        next_submit_filled_qty=float(state.scenario.quantity),
    )


def _persist_order(state: _DryRunState, order: BrokerOrder) -> OrderRecord:
    record = state.repository.insert_order(
        order_id=f"order-{order.client_order_id}",
        execution_intent_id=state.intent_record_id,
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
        raw_broker_payload=order.model_dump(mode="json")
        | {"broker_mode": "fake", "real_order_submitted": False},
        created_at=order.submitted_at or state.input.started_at,
        updated_at=order.updated_at or state.input.started_at,
    )
    state.add_entity_id("orders", record.order_id)
    if order.purpose == "entry":
        state.entry_order_record_id = record.order_id
    return record


def _persist_fill_and_position_if_needed(
    state: _DryRunState,
    *,
    intent: ExecutionIntent,
    entry_order: BrokerOrder,
    entry_order_id: str,
    filled_quantity: float,
) -> BrokerFill | None:
    if filled_quantity <= 0:
        state.add_step("persist_fake_fill", "skipped", "entry_order_not_filled")
        return None
    fill = BrokerFill(
        broker_order_id=entry_order.broker_order_id,
        client_order_id=entry_order.client_order_id,
        symbol=entry_order.symbol,
        side=entry_order.side,
        quantity=filled_quantity,
        price=state.scenario.limit_price,
        filled_at=state.input.started_at + timedelta(minutes=1),
        broker_fill_id=f"fake-fill-{state.scenario.scenario_id}",
    )
    fill_record = state.repository.insert_fill(
        fill_id=f"fill-{state.scenario.scenario_id}",
        order_id=entry_order_id,
        broker_order_id=fill.broker_order_id,
        broker_fill_id=fill.broker_fill_id,
        symbol=fill.symbol,
        quantity=fill.quantity,
        price=fill.price,
        filled_at=fill.filled_at,
        raw_broker_payload=fill.model_dump(mode="json")
        | {"broker_mode": "fake", "real_order_submitted": False},
        created_at=fill.filled_at,
    )
    position = state.repository.upsert_position(
        symbol=intent.symbol,
        quantity=filled_quantity,
        average_entry_price=fill.price,
        protective_stop_order_id=None,
        opened_at=_position_opened_at(state),
        raw_source_payload={"source": "fake_paper_dry_run", "fill_id": fill_record.fill_id},
    )
    state.position_record_id = position.position_id
    state.position_opened = True
    state.evidence.fake_fill_status = "filled" if filled_quantity == intent.quantity else "partial"
    state.evidence.filled_quantity = filled_quantity
    state.add_entity_id("fills", fill_record.fill_id)
    state.add_entity_id("positions", position.position_id)
    state.add_step(
        "persist_fake_fill_and_position",
        "passed",
        "fake_fill_and_position_persisted",
        {"filled_quantity": f"{filled_quantity:.6f}"},
    )
    return fill


def _reconcile_and_persist(
    state: _DryRunState,
    *,
    account: BrokerAccountSnapshot,
    entry_order: BrokerOrder,
    stop_order: BrokerOrder | None,
    broker_fill: BrokerFill | None,
    stop: BrokerProtectiveStop | None,
    filled_quantity: float,
) -> ReconciliationResult:
    broker_snapshot = _broker_snapshot(
        state,
        account=account,
        entry_order=entry_order,
        stop_order=stop_order,
        broker_fill=broker_fill,
        stop=stop,
        filled_quantity=filled_quantity,
    )
    internal_snapshot = _internal_snapshot(
        state,
        entry_order=entry_order,
        stop_order=stop_order,
        broker_fill=broker_fill,
        filled_quantity=filled_quantity,
    )
    result = compare_broker_and_internal(
        broker_snapshot=broker_snapshot,
        internal_snapshot=internal_snapshot,
        as_of=state.input.completed_at,
        protective_stop_config=state.app_config.protective_stop,
    )
    record = state.repository.insert_broker_reconciliation_result(
        result,
        temporal_workflow_id=f"dry-run-{state.scenario.scenario_id}-reconciliation",
        reconciliation_id=f"reconciliation-{state.scenario.scenario_id}",
        created_at=state.input.completed_at,
    )
    state.evidence.reconciliation_status = record.status
    state.evidence.reconciliation_mismatch_types = tuple(
        mismatch.mismatch_type for mismatch in result.mismatches
    )
    state.add_entity_id("broker_reconciliations", record.reconciliation_id)
    state.add_step(
        "run_reconciliation",
        "passed" if result.clean else "failed",
        "reconciliation_clean" if result.clean else "reconciliation_mismatch_detected",
        {"mismatch_types": ",".join(state.evidence.reconciliation_mismatch_types)},
    )
    return result


def _broker_snapshot(
    state: _DryRunState,
    *,
    account: BrokerAccountSnapshot,
    entry_order: BrokerOrder,
    stop_order: BrokerOrder | None,
    broker_fill: BrokerFill | None,
    stop: BrokerProtectiveStop | None,
    filled_quantity: float,
) -> BrokerSnapshot:
    open_orders: tuple[BrokerOrder, ...]
    if entry_order.status == "partially_filled" and stop_order is not None:
        open_orders = (entry_order, stop_order)
    elif stop_order is not None:
        open_orders = (stop_order,)
    else:
        open_orders = ()

    position = (
        BrokerPosition(
            symbol=state.scenario.symbol,
            asset_class=state.scenario.asset_class,
            quantity=filled_quantity,
            avg_entry_price=state.scenario.limit_price,
            opened_at=_position_opened_at(state),
        )
        if filled_quantity > 0
        else None
    )
    positions = () if position is None else (position,)
    if state.failure_mode == "reconciliation_mismatch":
        positions = ()
    return BrokerSnapshot(
        account=account,
        open_orders=open_orders,
        recent_fills=() if broker_fill is None else (broker_fill,),
        positions=positions,
        protective_stops=() if stop is None else (stop,),
        as_of=state.input.completed_at,
        source="fixture",
    )


def _internal_snapshot(
    state: _DryRunState,
    *,
    entry_order: BrokerOrder,
    stop_order: BrokerOrder | None,
    broker_fill: BrokerFill | None,
    filled_quantity: float,
) -> InternalLedgerSnapshot:
    orders: list[InternalOrder] = [
        InternalOrder(
            order_id=state.entry_order_record_id or f"order-{entry_order.client_order_id}",
            client_order_id=entry_order.client_order_id,
            symbol=entry_order.symbol,
            side=entry_order.side,
            quantity=entry_order.quantity,
            filled_quantity=filled_quantity,
            status=_internal_order_status(entry_order),
            broker_order_id=entry_order.broker_order_id,
            temporal_workflow_id=f"dry-run-{state.scenario.scenario_id}-order",
            is_entry_order=True,
        )
    ]
    if stop_order is not None:
        orders.append(
            InternalOrder(
                order_id=state.stop_order_record_id or f"order-{stop_order.client_order_id}",
                client_order_id=stop_order.client_order_id,
                symbol=stop_order.symbol,
                side=stop_order.side,
                quantity=stop_order.quantity,
                status="open",
                broker_order_id=stop_order.broker_order_id,
                temporal_workflow_id=f"dry-run-{state.scenario.scenario_id}-stop",
                is_entry_order=False,
            )
        )
    fills = (
        ()
        if broker_fill is None
        else (
            InternalFill(
                broker_order_id=broker_fill.broker_order_id,
                client_order_id=broker_fill.client_order_id,
                symbol=broker_fill.symbol,
                quantity=broker_fill.quantity,
                price=broker_fill.price,
                filled_at=broker_fill.filled_at,
            ),
        )
    )
    positions = (
        ()
        if filled_quantity <= 0
        else (
            InternalPosition(
                symbol=state.scenario.symbol,
                quantity=filled_quantity,
                avg_entry_price=state.scenario.limit_price,
                opened_at=_position_opened_at(state),
                protective_stop_client_order_id=(
                    None if stop_order is None else stop_order.client_order_id
                ),
                temporal_workflow_id=f"dry-run-{state.scenario.scenario_id}-position",
            ),
        )
    )
    return InternalLedgerSnapshot(
        account=InternalAccountSnapshot(
            equity=state.scenario.account_equity,
            cash=state.scenario.cash,
            as_of=state.input.completed_at,
        ),
        orders=tuple(orders),
        fills=fills,
        positions=positions,
        as_of=state.input.completed_at,
    )


def _persist_reconciliation_incidents(
    state: _DryRunState,
    reconciliation: ReconciliationResult,
) -> None:
    if reconciliation.clean:
        event = state.repository.insert_system_event(
            event_id=f"event-{state.scenario.scenario_id}-reconciliation-clean",
            event_type="paper_dry_run_reconciliation_completed",
            severity="info",
            source_component="paper_dry_run",
            related_entity_type="broker_reconciliation",
            related_entity_id=f"reconciliation-{state.scenario.scenario_id}",
            message="Fake/local dry-run reconciliation completed cleanly.",
            payload={"dry_run": True, "broker_mode": "fake"},
            created_at=state.input.completed_at,
        )
        state.add_entity_id("system_events", event.event_id)
        return

    for index, incident in enumerate(reconciliation.incidents, start=1):
        event = state.repository.insert_system_event(
            event_id=f"event-{state.scenario.scenario_id}-reconciliation-{index}",
            event_type="paper_dry_run_reconciliation_incident",
            severity=incident.severity,
            source_component="paper_dry_run",
            related_entity_type="broker_reconciliation",
            related_entity_id=f"reconciliation-{state.scenario.scenario_id}",
            message=incident.message,
            payload=incident.model_dump(mode="json"),
            created_at=state.input.completed_at,
        )
        state.add_entity_id("system_events", event.event_id)
        _dispatch_alert(
            state,
            category=(
                "missing_protective_stop"
                if incident.reason_code == "missing_protective_stop"
                else "reconciliation_mismatch"
            ),
            severity=incident.severity,
            title=f"Dry-run incident: {incident.reason_code}",
            body=incident.message,
            related_entity_id=event.event_id,
            payload=incident.model_dump(mode="json"),
        )


def _record_failure_event_and_alert(
    state: _DryRunState,
    *,
    event_type: str,
    category: AlertCategory,
    severity: AlertSeverity,
    reason_codes: tuple[str, ...],
    message: str,
) -> None:
    state.failure_reasons.extend(reason_codes)
    event = state.repository.insert_system_event(
        event_id=f"event-{state.scenario.scenario_id}-{event_type}",
        event_type=event_type,
        severity=severity,
        source_component="paper_dry_run",
        related_entity_type="dry_run_scenario",
        related_entity_id=state.scenario.scenario_id,
        message=message,
        payload={"reason_codes": list(reason_codes), "dry_run": True},
        created_at=state.input.completed_at,
    )
    state.add_entity_id("system_events", event.event_id)
    _dispatch_alert(
        state,
        category=category,
        severity=severity,
        title=f"Dry-run safety event: {state.scenario.name}",
        body=message,
        related_entity_id=event.event_id,
        payload={"reason_codes": list(reason_codes), "dry_run": True},
    )


def _dispatch_success_alerts(
    state: _DryRunState,
    entry_order: BrokerOrder,
    broker_fill: BrokerFill | None,
) -> None:
    _dispatch_alert(
        state,
        category="order_notification",
        severity="info",
        title="Dry-run fake entry order acknowledged",
        body="Fake broker adapter acknowledged the dry-run entry order.",
        related_entity_id=entry_order.client_order_id,
        payload=entry_order.model_dump(mode="json"),
    )
    if broker_fill is not None:
        _dispatch_alert(
            state,
            category="fill_notification",
            severity="info",
            title="Dry-run fake fill recorded",
            body="Fake broker fill was persisted to the local ledger.",
            related_entity_id=broker_fill.broker_fill_id,
            payload=broker_fill.model_dump(mode="json"),
        )


def _generate_report_and_dashboard(state: _DryRunState) -> None:
    snapshot = build_report_input_snapshot(
        state.repository,
        generated_at=state.input.completed_at,
        environment=state.app_config.system.environment,
        dry_run=state.app_config.system.dry_run,
        live_trading_enabled=state.app_config.system.live_trading_enabled,
        autonomous_execution_enabled=state.app_config.system.autonomous_execution_enabled,
    )
    report_result = generate_daily_report(
        report_date=state.scenario.trade_date,
        snapshot=snapshot,
    )
    persisted_report = persist_report_generation_result(state.repository, report_result)
    if persisted_report.persisted_report_id is not None:
        state.evidence.report_id = persisted_report.persisted_report_id
        state.add_entity_id("reports", persisted_report.persisted_report_id)
    _dispatch_alert(
        state,
        category="report_generated",
        severity="info",
        title="Dry-run report generated",
        body="Fake/local dry-run report was generated and persisted.",
        related_entity_id=persisted_report.persisted_report_id,
        payload={"report_type": "daily", "dry_run": True},
    )
    dashboard = LedgerDashboardReadModelProvider(
        state.repository,
        config=state.app_config,
        as_of=state.input.completed_at,
    ).snapshot()
    state.dashboard_snapshot = dashboard
    state.evidence.dashboard_snapshot_status = dashboard.system_state.data_source
    state.add_step("generate_report_and_dashboard", "passed", "report_and_dashboard_ready")


def _dispatch_alert(
    state: _DryRunState,
    *,
    category: AlertCategory,
    severity: AlertSeverity,
    title: str,
    body: str,
    related_entity_id: str | None,
    payload: Mapping[str, Any],
) -> None:
    state.alert_router.dispatch(
        AlertMessage(
            category=category,
            severity=severity,
            title=title,
            body=body,
            source_component="paper_dry_run",
            created_at=state.input.completed_at,
            related_entity_type="paper_dry_run",
            related_entity_id=related_entity_id,
            payload=dict(payload),
        )
    )


def _safety_flags(app_config: AppConfig) -> DryRunSafetyFlags:
    return DryRunSafetyFlags(
        live_trading_enabled=app_config.system.live_trading_enabled,
        autonomous_execution_enabled=(
            app_config.system.autonomous_execution_enabled
            or app_config.execution.autonomous_execution_enabled
        ),
        allow_live_orders=app_config.execution.allow_live_orders,
    )


def _risk_system_config(state: _DryRunState) -> SystemConfig:
    if not state.input.config.simulate_autonomous_permission_for_risk_gate:
        return state.app_config.system
    return _simulated_paper_system_config(state.app_config.system)


def _risk_execution_config(state: _DryRunState) -> ExecutionConfig:
    if not state.input.config.simulate_autonomous_permission_for_risk_gate:
        return state.app_config.execution
    return _simulated_paper_execution_config(state.app_config.execution)


def _simulated_paper_system_config(config: SystemConfig) -> SystemConfig:
    return SystemConfig.model_validate(
        config.model_dump() | {"autonomous_execution_enabled": True}
    )


def _simulated_paper_execution_config(config: ExecutionConfig) -> ExecutionConfig:
    return ExecutionConfig.model_validate(
        config.model_dump() | {"autonomous_execution_enabled": True}
    )


def _kill_switch_for_scenario(failure_mode: DryRunFailureMode) -> KillSwitchSnapshot:
    if failure_mode == "kill_switch_pause_new_risk":
        return pause_new_risk("fake_dry_run_pause")
    return running_state()


def _category_for_failure(failure_mode: DryRunFailureMode) -> AlertCategory:
    if failure_mode == "duplicate_active_intent":
        return "duplicate_order_or_intent"
    if failure_mode == "stale_data":
        return "stale_data"
    if failure_mode == "kill_switch_pause_new_risk":
        return "kill_switch_activation"
    return "manual_control_action"


def _internal_order_status(order: BrokerOrder) -> InternalOrderStatus:
    if order.status == "filled":
        return "filled"
    if order.status == "cancelled":
        return "cancelled"
    if order.status == "expired":
        return "expired"
    if order.status == "rejected":
        return "rejected"
    return "open"


def _position_opened_at(state: _DryRunState) -> datetime:
    if state.failure_mode == "missing_protective_stop":
        return state.input.completed_at - timedelta(seconds=61)
    return state.input.started_at + timedelta(minutes=1)


def _scenario_uuid(state: _DryRunState, label: str) -> UUID:
    return uuid5(NAMESPACE_URL, f"{state.scenario.scenario_id}:{label}")
