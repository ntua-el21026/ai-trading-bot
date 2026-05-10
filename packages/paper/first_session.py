"""Fake/local first controlled paper-session wiring harness.

This module models the first controlled paper-session runtime shape without performing broker,
provider, alert, Temporal Cloud, managed database, schedule, or deployment side effects.
"""

from __future__ import annotations

import json
import subprocess
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from typing import Any, Literal, Self, cast
from uuid import NAMESPACE_URL, UUID, uuid5

from pydantic import BaseModel, ConfigDict, Field, model_validator

from packages.ai.fallback import neutral_research_output
from packages.ai.models import AI_PROMPT_VERSION, AI_SCHEMA_VERSION
from packages.ai.persistence import build_ai_research_persistence_payload
from packages.alerting.adapters import FakeAlertAdapter
from packages.alerting.models import AlertCategory, AlertMessage, AlertSeverity
from packages.alerting.routing import AlertRouter
from packages.broker.models import (
    BrokerAccountSnapshot,
    BrokerOrder,
    BrokerSnapshot,
)
from packages.control_plane.models import DashboardSnapshot
from packages.control_plane.service import LedgerDashboardReadModelProvider
from packages.core.config import AppConfig, load_app_config
from packages.ledger.connection import connect_in_memory_sqlite
from packages.ledger.models import BrokerReconciliationRecord, SystemEventRecord
from packages.ledger.repositories import SQLiteLedgerRepository
from packages.paper.dry_run import run_paper_dry_run
from packages.paper.fixtures import default_dry_run_input
from packages.paper.models import DryRunResult
from packages.reconciliation.models import (
    InternalAccountSnapshot,
    InternalLedgerSnapshot,
    ReconciliationResult,
)
from packages.reconciliation.service import compare_broker_and_internal
from packages.reporting.generators import generate_daily_report
from packages.reporting.ledger import (
    build_report_input_snapshot,
    persist_report_generation_result,
)

FIRST_SESSION_STARTED_AT = datetime(2026, 5, 7, 14, 0, tzinfo=UTC)
FIRST_SESSION_COMPLETED_AT = FIRST_SESSION_STARTED_AT + timedelta(minutes=10)
FIRST_SESSION_SPEC_VERSION = "Autonomous_AI_Trading_Bot_SPEC_v0.3.md"
FIRST_SESSION_SAFE_MODE: Literal["fake-local"] = "fake-local"
FIRST_SESSION_APPROVAL_MARKER = "FAKE_LOCAL_OPERATOR_APPROVED"
FIRST_SESSION_RISK_CONFIG_VERSION = "risk_v0_3"
FIRST_SESSION_STRATEGY_SOURCE = "first_controlled_paper_session_fake_local"

SENSITIVE_ENV_NAMES: tuple[str, ...] = (
    "DATABASE_URL",
    "TEMPORAL_NAMESPACE",
    "TEMPORAL_ADDRESS",
    "TEMPORAL_API_KEY",
    "ALPACA_API_KEY",
    "ALPACA_SECRET_KEY",
    "ALPACA_BASE_URL",
    "MARKETAUX_API_KEY",
    "ALPHA_VANTAGE_API_KEY",
    "OPENAI_API_KEY",
    "TELEGRAM_BOT_TOKEN",
    "TELEGRAM_CHAT_ID",
)

FirstSessionScenarioId = Literal[
    "happy_path",
    "kill_switch_blocks",
    "dirty_reconciliation_blocks",
    "missing_stop_incident",
    "duplicate_intent_blocks",
    "leverage_rejected",
    "short_rejected",
    "missing_operator_approval",
    "live_endpoint_rejected",
    "missing_execution_intent",
    "unsupported_asset_rejected",
    "partial_fill",
]
FirstSessionStepStatus = Literal["passed", "failed", "skipped"]
FirstSessionSeverity = Literal["info", "warning", "critical"]

FIRST_SESSION_SCENARIO_IDS: tuple[FirstSessionScenarioId, ...] = (
    "happy_path",
    "kill_switch_blocks",
    "dirty_reconciliation_blocks",
    "missing_stop_incident",
    "duplicate_intent_blocks",
    "leverage_rejected",
    "short_rejected",
    "missing_operator_approval",
    "live_endpoint_rejected",
    "missing_execution_intent",
    "unsupported_asset_rejected",
    "partial_fill",
)


class FirstSessionModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class FirstSessionConfig(FirstSessionModel):
    mode: Literal["fake-local"] = FIRST_SESSION_SAFE_MODE
    alert_mode: Literal["fake"] = "fake"
    ledger_mode: Literal["local_sqlite"] = "local_sqlite"
    broker_mode: Literal["fake"] = "fake"
    ai_news_mode: Literal["neutral_fallback"] = "neutral_fallback"
    cleanup_policy: Literal["verify_only"] = "verify_only"
    require_operator_approval: bool = True
    require_pre_run_reconciliation: bool = True
    require_execution_intent: bool = True
    require_protective_stop_verification: bool = True


class FirstSessionInput(FirstSessionModel):
    scenario_id: FirstSessionScenarioId = "happy_path"
    operator_approval_marker: str | None = FIRST_SESSION_APPROVAL_MARKER
    config: FirstSessionConfig = Field(default_factory=FirstSessionConfig)
    started_at: datetime = FIRST_SESSION_STARTED_AT
    completed_at: datetime = FIRST_SESSION_COMPLETED_AT

    @model_validator(mode="after")
    def validate_timestamps(self) -> Self:
        _require_aware(self.started_at, "started_at")
        _require_aware(self.completed_at, "completed_at")
        if self.completed_at < self.started_at:
            raise ValueError("completed_at cannot be before started_at")
        return self


class FirstSessionStepResult(FirstSessionModel):
    name: str
    status: FirstSessionStepStatus
    reason_code: str
    details: dict[str, str] = Field(default_factory=dict)


class EndpointAssertion(FirstSessionModel):
    endpoint_kind: Literal["paper", "live"]
    accepted: bool
    represented_base_url: str
    external_call_performed: bool = False
    reason: str


class FirstSessionSafetyFlags(FirstSessionModel):
    fake_local_mode: bool = True
    local_ledger_used: bool = True
    fake_broker_used: bool = True
    fake_alert_adapter_used: bool = True
    neutral_ai_news_used: bool = True
    live_trading_enabled: bool
    autonomous_live_execution_enabled: bool
    allow_live_orders: bool
    paper_operations_started: bool = False
    actual_paper_trading_started: bool = False
    real_broker_writes_attempted: bool = False
    external_calls_attempted: bool = False
    schedules_activated: bool = False
    temporal_cloud_connected: bool = False
    managed_database_used: bool = False
    real_alerts_sent: bool = False
    secrets_printed: bool = False
    leverage_enabled: bool = False
    ai_broker_write_authority: bool = False
    level4_ready: bool = False

    @property
    def safe(self) -> bool:
        return (
            self.fake_local_mode
            and self.local_ledger_used
            and self.fake_broker_used
            and self.fake_alert_adapter_used
            and self.neutral_ai_news_used
            and not self.live_trading_enabled
            and not self.autonomous_live_execution_enabled
            and not self.allow_live_orders
            and not self.paper_operations_started
            and not self.actual_paper_trading_started
            and not self.real_broker_writes_attempted
            and not self.external_calls_attempted
            and not self.schedules_activated
            and not self.temporal_cloud_connected
            and not self.managed_database_used
            and not self.real_alerts_sent
            and not self.secrets_printed
            and not self.leverage_enabled
            and not self.ai_broker_write_authority
            and not self.level4_ready
        )


class FirstSessionIncident(FirstSessionModel):
    incident_id: str
    severity: FirstSessionSeverity
    reason_code: str
    message: str


class AlertDeliverySummary(FirstSessionModel):
    mode: Literal["fake"] = "fake"
    fake_delivery_count: int = Field(ge=0)
    real_delivery_count: int = Field(default=0, ge=0)
    external_calls_performed: bool = False
    titles: tuple[str, ...] = ()


class FirstSessionEvidencePackage(FirstSessionModel):
    evidence_package_id: str
    session_id: str
    timestamp: datetime
    operator_approval_marker: str | None
    commit_hash: str
    spec_version: str
    config_safety_snapshot: dict[str, Any]
    paper_endpoint_proof: EndpointAssertion
    live_endpoint_rejection_proof: EndpointAssertion
    no_schedule_assertion: bool
    no_leverage_assertion: bool
    orchestration_mode: Literal["temporal_compatible_local_service"]
    temporal_cloud_connected: bool = False
    managed_database_used: bool = False
    market_session_status: str
    cleanup_policy: Literal["verify_only"]
    pre_run_reconciliation_id: str | None = None
    pre_run_reconciliation_result: str | None = None
    candidate_id: str | None = None
    ai_news_output_id: str | None = None
    ai_news_fallback_marker: str | None = None
    decision_id: str | None = None
    risk_check_id: str | None = None
    execution_intent_id: str | None = None
    order_id: str | None = None
    broker_order_id: str | None = None
    client_order_id: str | None = None
    fill_id: str | None = None
    broker_fill_id: str | None = None
    protective_stop_order_id: str | None = None
    protective_stop_client_order_id: str | None = None
    stop_verification_result: str | None = None
    post_run_reconciliation_id: str | None = None
    post_run_reconciliation_result: str | None = None
    final_open_orders_status: str | None = None
    final_positions_status: str | None = None
    report_id: str | None = None
    report_path: str | None = None
    dashboard_snapshot_status: str | None = None
    alert_delivery_summary: AlertDeliverySummary
    incident_ids: tuple[str, ...] = ()
    persisted_entity_ids: dict[str, tuple[str, ...]] = Field(default_factory=dict)


class FirstSessionResult(FirstSessionModel):
    scenario_id: FirstSessionScenarioId
    success: bool
    refused: bool
    unsafe: bool
    started_at: datetime
    completed_at: datetime
    steps: tuple[FirstSessionStepResult, ...]
    safety_flags: FirstSessionSafetyFlags
    evidence_package: FirstSessionEvidencePackage
    incidents: tuple[FirstSessionIncident, ...] = ()
    refusal_reasons: tuple[str, ...] = ()
    paper_operations_started: bool = False
    actual_paper_trading_started: bool = False
    real_broker_writes_attempted: bool = False
    external_calls_attempted: bool = False
    schedules_activated: bool = False
    live_trading_enabled: bool = False
    autonomous_live_execution_enabled: bool = False
    level4_ready: bool = False
    dashboard_snapshot: DashboardSnapshot | None = None
    note: str = (
        "Fake/local first controlled paper-session wiring only. Actual paper trading has not "
        "started and no real broker/provider/alert/Temporal/database calls were made."
    )

    @model_validator(mode="after")
    def validate_safety_invariants(self) -> Self:
        _require_aware(self.started_at, "started_at")
        _require_aware(self.completed_at, "completed_at")
        if self.success and (self.refused or self.unsafe):
            raise ValueError("successful result cannot also be refused or unsafe")
        if not self.safety_flags.safe:
            raise ValueError("first-session fake/local result contains unsafe safety flags")
        forbidden = {
            "paper_operations_started": self.paper_operations_started,
            "actual_paper_trading_started": self.actual_paper_trading_started,
            "real_broker_writes_attempted": self.real_broker_writes_attempted,
            "external_calls_attempted": self.external_calls_attempted,
            "schedules_activated": self.schedules_activated,
            "live_trading_enabled": self.live_trading_enabled,
            "autonomous_live_execution_enabled": self.autonomous_live_execution_enabled,
            "level4_ready": self.level4_ready,
        }
        enabled = [name for name, value in forbidden.items() if value]
        if enabled:
            raise ValueError(f"fake/local first-session result enabled forbidden flags: {enabled}")
        return self


class FirstControlledPaperSessionHarness:
    """Local-only first-session orchestration boundary.

    The class is intentionally a service boundary that can later be called from a Temporal workflow.
    It does not connect to a Temporal server and does not expose any real broker write mode.
    """

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

    def run(self, first_session_input: FirstSessionInput | None = None) -> FirstSessionResult:
        run_input = first_session_input or default_first_session_input()
        state = _FirstSessionState(
            run_input=run_input,
            repository=self.repository,
            app_config=self.app_config,
            alert_adapter=self.alert_adapter,
            alert_router=self.alert_router,
        )
        state.add_step("initialize_local_first_session_harness", "passed", "local_harness_ready")
        state.add_step("load_safe_runtime_config", "passed", "config_loaded_without_secrets")

        safety_flags = _safety_flags(self.app_config)
        if not safety_flags.safe:
            return state.refuse(
                "unsafe_runtime_config",
                "Runtime config is not safe for fake/local first-session wiring.",
                safety_flags=safety_flags,
                severity="critical",
            )
        state.add_step("verify_safety_flags", "passed", "fake_local_runtime_flags_safe")

        if run_input.config.require_operator_approval and not run_input.operator_approval_marker:
            return state.refuse(
                "operator_approval_missing",
                "Operator approval marker is required before first-session wiring can proceed.",
                safety_flags=safety_flags,
                severity="warning",
            )
        state.add_step("verify_operator_approval", "passed", "operator_approval_marker_present")

        if run_input.scenario_id == "missing_operator_approval":
            return state.refuse(
                "operator_approval_missing",
                "Scenario intentionally removes the operator approval marker.",
                safety_flags=safety_flags,
                severity="warning",
            )

        if run_input.scenario_id == "live_endpoint_rejected":
            return state.refuse(
                "live_endpoint_forbidden",
                "Live endpoint configuration is refused in Milestone 29 fake/local wiring.",
                safety_flags=safety_flags,
                severity="critical",
            )
        state.add_step("reject_live_endpoint", "passed", "live_endpoint_forbidden")

        pre_run_reconciliation = _persist_pre_run_reconciliation(
            state,
            clean=run_input.scenario_id != "dirty_reconciliation_blocks",
        )
        state.pre_run_reconciliation_id = pre_run_reconciliation.reconciliation_id
        state.pre_run_reconciliation_result = pre_run_reconciliation.status
        state.add_entity_id("broker_reconciliations", pre_run_reconciliation.reconciliation_id)
        if pre_run_reconciliation.status != "clean":
            return state.refuse(
                "pre_run_reconciliation_not_clean",
                "Pre-run broker/internal reconciliation is not clean.",
                safety_flags=safety_flags,
                severity="critical",
            )
        state.add_step("verify_pre_run_reconciliation", "passed", "pre_run_reconciliation_clean")

        preflight_refusal = _preflight_refusal_for_scenario(run_input.scenario_id)
        if preflight_refusal is not None:
            reason_code, message, risk_reason = preflight_refusal
            _persist_minimal_decision_chain(
                state,
                risk_passed=False,
                risk_reason_codes=(risk_reason,),
            )
            return state.refuse(
                reason_code,
                message,
                safety_flags=safety_flags,
                severity="critical",
            )

        if run_input.scenario_id == "missing_execution_intent":
            _persist_minimal_decision_chain(
                state,
                risk_passed=True,
                risk_reason_codes=(),
            )
            return state.refuse(
                "execution_intent_required",
                "ExecutionIntent is required before any paper order simulation.",
                safety_flags=safety_flags,
                severity="critical",
            )

        dry_run_result = run_paper_dry_run(
            default_dry_run_input(_dry_run_scenario_id(run_input.scenario_id)),
            repository=state.repository,
            app_config=state.app_config,
        )
        state.add_step(
            "run_temporal_compatible_fake_execution_shape",
            "passed" if dry_run_result.evidence.fake_broker_order_request_count > 0 else "failed",
            "fake_execution_shape_completed"
            if dry_run_result.evidence.fake_broker_order_request_count > 0
            else "fake_execution_shape_refused_before_order",
        )
        _merge_dry_run_evidence(state, dry_run_result)

        if run_input.scenario_id in {"kill_switch_blocks", "duplicate_intent_blocks"}:
            reason = (
                "kill_switch_paused_new_risk"
                if run_input.scenario_id == "kill_switch_blocks"
                else "active_duplicate_intent"
            )
            return state.final_result(
                safety_flags=safety_flags,
                success=False,
                refused=True,
                unsafe=False,
                refusal_reasons=(reason,),
            )

        if run_input.scenario_id == "missing_stop_incident":
            return state.final_result(
                safety_flags=safety_flags,
                success=False,
                refused=False,
                unsafe=True,
                refusal_reasons=(),
            )

        return state.final_result(
            safety_flags=safety_flags,
            success=dry_run_result.passed,
            refused=False,
            unsafe=not dry_run_result.passed,
            refusal_reasons=dry_run_result.failure_reasons,
        )


class _FirstSessionState:
    def __init__(
        self,
        *,
        run_input: FirstSessionInput,
        repository: SQLiteLedgerRepository,
        app_config: AppConfig,
        alert_adapter: FakeAlertAdapter,
        alert_router: AlertRouter,
    ) -> None:
        self.input = run_input
        self.repository = repository
        self.app_config = app_config
        self.alert_adapter = alert_adapter
        self.alert_router = alert_router
        self.steps: list[FirstSessionStepResult] = []
        self.persisted_entity_ids: dict[str, list[str]] = {}
        self.incident_records: list[SystemEventRecord] = []
        self.pre_run_reconciliation_id: str | None = None
        self.pre_run_reconciliation_result: str | None = None
        self.candidate_id: str | None = None
        self.ai_news_output_id: str | None = None
        self.decision_id: str | None = None
        self.risk_check_id: str | None = None
        self.execution_intent_id: str | None = None
        self.order_id: str | None = None
        self.broker_order_id: str | None = None
        self.client_order_id: str | None = None
        self.fill_id: str | None = None
        self.broker_fill_id: str | None = None
        self.protective_stop_order_id: str | None = None
        self.protective_stop_client_order_id: str | None = None
        self.stop_verification_result: str | None = None
        self.post_run_reconciliation_id: str | None = None
        self.post_run_reconciliation_result: str | None = None
        self.final_open_orders_status: str | None = None
        self.final_positions_status: str | None = None
        self.report_id: str | None = None
        self.report_path: str | None = None
        self.dashboard_snapshot_status: str | None = None
        self.dashboard_snapshot: DashboardSnapshot | None = None
        self.ai_news_fallback_marker = "neutral_fallback_no_provider_call"

    @property
    def session_id(self) -> str:
        return f"first-controlled-paper-session-{self.input.scenario_id}"

    def add_step(
        self,
        name: str,
        status: FirstSessionStepStatus,
        reason_code: str,
        details: Mapping[str, str] | None = None,
    ) -> None:
        self.steps.append(
            FirstSessionStepResult(
                name=name,
                status=status,
                reason_code=reason_code,
                details=dict(details or {}),
            )
        )

    def add_entity_id(self, entity_type: str, entity_id: str) -> None:
        self.persisted_entity_ids.setdefault(entity_type, []).append(entity_id)

    def refuse(
        self,
        reason_code: str,
        message: str,
        *,
        safety_flags: FirstSessionSafetyFlags,
        severity: FirstSessionSeverity,
    ) -> FirstSessionResult:
        self.add_step(f"refuse_{reason_code}", "failed", reason_code)
        incident = _persist_incident(
            self,
            reason_code=reason_code,
            message=message,
            severity=severity,
        )
        self.incident_records.append(incident)
        self.add_entity_id("system_events", incident.event_id)
        _dispatch_alert(
            self,
            category=_alert_category_for_reason(reason_code),
            severity=severity,
            title=f"First-session wiring refused: {reason_code}",
            body=message,
            related_entity_id=incident.event_id,
            payload={"reason_code": reason_code, "fake_local": True},
        )
        _generate_report_and_dashboard(self, status="refused")
        return self.final_result(
            safety_flags=safety_flags,
            success=False,
            refused=True,
            unsafe=False,
            refusal_reasons=(reason_code,),
        )

    def final_result(
        self,
        *,
        safety_flags: FirstSessionSafetyFlags,
        success: bool,
        refused: bool,
        unsafe: bool,
        refusal_reasons: tuple[str, ...],
    ) -> FirstSessionResult:
        if self.report_id is None or self.dashboard_snapshot_status is None:
            _generate_report_and_dashboard(self, status="passed" if success else "failed")
        incidents = tuple(_incident_from_record(record) for record in self.incident_records)
        evidence = self.evidence_package()
        return FirstSessionResult(
            scenario_id=self.input.scenario_id,
            success=success,
            refused=refused,
            unsafe=unsafe,
            started_at=self.input.started_at,
            completed_at=self.input.completed_at,
            steps=tuple(self.steps),
            safety_flags=safety_flags,
            evidence_package=evidence,
            incidents=incidents,
            refusal_reasons=_unique(refusal_reasons),
            dashboard_snapshot=self.dashboard_snapshot,
        )

    def evidence_package(self) -> FirstSessionEvidencePackage:
        alert_titles = tuple(message.title for message in self.alert_adapter.messages)
        persisted = {
            key: tuple(value) for key, value in sorted(self.persisted_entity_ids.items())
        }
        return FirstSessionEvidencePackage(
            evidence_package_id=f"evidence-{self.session_id}",
            session_id=self.session_id,
            timestamp=self.input.started_at,
            operator_approval_marker=self.input.operator_approval_marker,
            commit_hash=_git_commit_or_unavailable(),
            spec_version=FIRST_SESSION_SPEC_VERSION,
            config_safety_snapshot=_config_safety_snapshot(self.app_config),
            paper_endpoint_proof=EndpointAssertion(
                endpoint_kind="paper",
                accepted=True,
                represented_base_url="https://paper-api.alpaca.markets",
                reason="paper endpoint represented as fake/local evidence only",
            ),
            live_endpoint_rejection_proof=EndpointAssertion(
                endpoint_kind="live",
                accepted=False,
                represented_base_url="https://api.alpaca.markets",
                reason="live endpoint is refused before execution boundaries",
            ),
            no_schedule_assertion=True,
            no_leverage_assertion=True,
            orchestration_mode="temporal_compatible_local_service",
            market_session_status="fake_market_session_open",
            cleanup_policy=self.input.config.cleanup_policy,
            pre_run_reconciliation_id=self.pre_run_reconciliation_id,
            pre_run_reconciliation_result=self.pre_run_reconciliation_result,
            candidate_id=self.candidate_id,
            ai_news_output_id=self.ai_news_output_id,
            ai_news_fallback_marker=self.ai_news_fallback_marker,
            decision_id=self.decision_id,
            risk_check_id=self.risk_check_id,
            execution_intent_id=self.execution_intent_id,
            order_id=self.order_id,
            broker_order_id=self.broker_order_id,
            client_order_id=self.client_order_id,
            fill_id=self.fill_id,
            broker_fill_id=self.broker_fill_id,
            protective_stop_order_id=self.protective_stop_order_id,
            protective_stop_client_order_id=self.protective_stop_client_order_id,
            stop_verification_result=self.stop_verification_result,
            post_run_reconciliation_id=self.post_run_reconciliation_id,
            post_run_reconciliation_result=self.post_run_reconciliation_result,
            final_open_orders_status=self.final_open_orders_status,
            final_positions_status=self.final_positions_status,
            report_id=self.report_id,
            report_path=self.report_path,
            dashboard_snapshot_status=self.dashboard_snapshot_status,
            alert_delivery_summary=AlertDeliverySummary(
                fake_delivery_count=len(self.alert_adapter.messages),
                titles=alert_titles,
            ),
            incident_ids=tuple(record.event_id for record in self.incident_records),
            persisted_entity_ids=persisted,
        )


def default_first_session_input(
    scenario_id: str = "happy_path",
    *,
    operator_approval_marker: str | None = FIRST_SESSION_APPROVAL_MARKER,
) -> FirstSessionInput:
    scenario = _validate_scenario_id(scenario_id)
    if scenario == "missing_operator_approval":
        operator_approval_marker = None
    return FirstSessionInput(
        scenario_id=scenario,
        operator_approval_marker=operator_approval_marker,
    )


def run_first_controlled_paper_session_check(
    first_session_input: FirstSessionInput | None = None,
    *,
    repository: SQLiteLedgerRepository | None = None,
    app_config: AppConfig | None = None,
) -> FirstSessionResult:
    """Run the fake/local first-session wiring harness."""

    return FirstControlledPaperSessionHarness(
        repository=repository,
        app_config=app_config,
    ).run(first_session_input)


def _validate_scenario_id(scenario_id: str) -> FirstSessionScenarioId:
    if scenario_id not in FIRST_SESSION_SCENARIO_IDS:
        allowed = ", ".join(FIRST_SESSION_SCENARIO_IDS)
        raise ValueError(f"unknown first-session scenario_id: {scenario_id}; allowed: {allowed}")
    return cast(FirstSessionScenarioId, scenario_id)


def _safety_flags(app_config: AppConfig) -> FirstSessionSafetyFlags:
    return FirstSessionSafetyFlags(
        live_trading_enabled=app_config.system.live_trading_enabled,
        autonomous_live_execution_enabled=(
            app_config.system.live_trading_enabled
            and (
                app_config.system.autonomous_execution_enabled
                or app_config.execution.autonomous_execution_enabled
            )
        ),
        allow_live_orders=app_config.execution.allow_live_orders,
        leverage_enabled=(
            app_config.risk_level_4_micro_live.allow_margin
            or app_config.risk_level_4_expanded.allow_margin
        ),
        ai_broker_write_authority=app_config.ai.allow_ai_to_create_orders,
    )


def _persist_pre_run_reconciliation(
    state: _FirstSessionState,
    *,
    clean: bool,
) -> BrokerReconciliationRecord:
    result = _pre_run_reconciliation(state, clean=clean)
    record = state.repository.insert_broker_reconciliation_result(
        result,
        temporal_workflow_id=f"{state.session_id}-pre-run-reconciliation-boundary",
        reconciliation_id=f"{state.session_id}-pre-run-reconciliation",
        created_at=state.input.started_at,
    )
    if result.clean:
        return record

    for index, incident in enumerate(result.incidents, start=1):
        event = state.repository.insert_system_event(
            event_id=f"event-{state.session_id}-pre-run-reconciliation-{index}",
            event_type="first_session_pre_run_reconciliation_incident",
            severity=incident.severity,
            source_component="first_controlled_paper_session_harness",
            related_entity_type="broker_reconciliation",
            related_entity_id=record.reconciliation_id,
            message=incident.message,
            payload=incident.model_dump(mode="json"),
            created_at=state.input.started_at,
        )
        state.incident_records.append(event)
        state.add_entity_id("system_events", event.event_id)
    return record


def _pre_run_reconciliation(
    state: _FirstSessionState,
    *,
    clean: bool,
) -> ReconciliationResult:
    account = BrokerAccountSnapshot(
        account_id="fake-paper-account",
        environment="paper",
        equity=100_000.0,
        cash=98_000.0,
        buying_power=100_000.0,
        currency="USD",
        as_of=state.input.started_at,
    )
    broker_orders: tuple[BrokerOrder, ...] = ()
    if not clean:
        broker_orders = (
            BrokerOrder(
                broker_order_id=f"{state.session_id}-unknown-open-order",
                client_order_id=f"{state.session_id}-unknown-open-order",
                symbol="AAPL",
                side="buy",
                asset_class="equity",
                quantity=1.0,
                filled_quantity=0.0,
                order_type="limit",
                time_in_force="day",
                status="accepted",
                submitted_at=state.input.started_at,
                updated_at=state.input.started_at,
                limit_price=180.50,
                purpose="entry",
            ),
        )
    broker_snapshot = BrokerSnapshot(
        account=account,
        open_orders=broker_orders,
        positions=(),
        protective_stops=(),
        recent_fills=(),
        as_of=state.input.started_at,
        source="fixture",
    )
    internal_snapshot = InternalLedgerSnapshot(
        account=InternalAccountSnapshot(
            equity=100_000.0,
            cash=98_000.0,
            as_of=state.input.started_at,
        ),
        orders=(),
        fills=(),
        positions=(),
        as_of=state.input.started_at,
    )
    return compare_broker_and_internal(
        broker_snapshot=broker_snapshot,
        internal_snapshot=internal_snapshot,
        as_of=state.input.started_at,
        protective_stop_config=state.app_config.protective_stop,
    )


def _preflight_refusal_for_scenario(
    scenario_id: FirstSessionScenarioId,
) -> tuple[str, str, str] | None:
    if scenario_id == "short_rejected":
        return (
            "short_side_forbidden",
            "Short-side paper execution is forbidden for v0.1.",
            "short_side_forbidden",
        )
    if scenario_id == "unsupported_asset_rejected":
        return (
            "unsupported_asset_class",
            "Unsupported asset class is refused before execution intent creation.",
            "unsupported_asset_class:crypto",
        )
    if scenario_id == "leverage_rejected":
        return (
            "leverage_not_allowed",
            "Gross exposure above 1.00x equity is refused.",
            "gross_exposure_exceeds_1x",
        )
    return None


def _persist_minimal_decision_chain(
    state: _FirstSessionState,
    *,
    risk_passed: bool,
    risk_reason_codes: tuple[str, ...],
) -> None:
    scenario = state.input.scenario_id
    trade_date = state.input.started_at.date()
    candidate = state.repository.insert_trade_candidate(
        candidate_id=f"first-session-candidate-{scenario}",
        symbol="AAPL",
        trading_date=trade_date,
        strategy_version=state.app_config.strategy.name,
        candidate_status="accepted",
        technical_score=82.0,
        relative_strength_score=78.0,
        score_payload={"source": FIRST_SESSION_STRATEGY_SOURCE},
        reason_payload={"reason_codes": ("fixture_candidate_persisted",)},
        created_at=state.input.started_at,
    )
    state.candidate_id = candidate.candidate_id
    state.add_entity_id("trade_candidates", candidate.candidate_id)
    state.add_step("persist_strategy_candidate", "passed", "fixture_candidate_persisted")

    ai_output = neutral_research_output(
        symbol="AAPL",
        analysis_at=state.input.started_at,
        prompt_version=AI_PROMPT_VERSION,
        schema_version=AI_SCHEMA_VERSION,
        model_version="fake-neutral-model",
        fallback_reason="no_news_found",
        explanation="Fake/local first-session neutral AI/news fallback; no provider call was made.",
    )
    raw_output = json.dumps(ai_output.model_dump(mode="json"), sort_keys=True)
    ai_record = state.repository.insert_ai_research_output(
        build_ai_research_persistence_payload(
            symbol="AAPL",
            created_at=state.input.started_at,
            raw_prompt="Fake/local first-session prompt.",
            raw_ai_output=raw_output,
            parsed_output=ai_output,
        ),
        output_id=f"first-session-ai-output-{scenario}",
    )
    state.ai_news_output_id = ai_record.output_id
    state.add_entity_id("ai_research_outputs", ai_record.output_id)
    state.add_step("persist_neutral_ai_news_fallback", "passed", "neutral_ai_fallback_persisted")

    decision_id = _scenario_uuid(state.input.scenario_id, "decision")
    decision = state.repository.insert_trade_decision(
        decision_id=str(decision_id),
        candidate_id=candidate.candidate_id,
        symbol="AAPL",
        decision_status="approved" if risk_passed else "rejected",
        final_score=78.2,
        deterministic_decision_payload={
            "source": FIRST_SESSION_STRATEGY_SOURCE,
            "risk_passed": risk_passed,
        },
        ai_output_id=ai_record.output_id,
        created_at=state.input.started_at,
    )
    state.decision_id = decision.decision_id
    state.add_entity_id("trade_decisions", decision.decision_id)
    state.add_step("persist_trade_decision", "passed", "deterministic_decision_persisted")

    risk_check = state.repository.insert_risk_check(
        risk_check_id=f"first-session-risk-check-{scenario}",
        decision_id=decision.decision_id,
        execution_intent_id=None,
        symbol="AAPL",
        passed=risk_passed,
        reason_codes=risk_reason_codes,
        risk_config_version=FIRST_SESSION_RISK_CONFIG_VERSION,
        input_snapshot={
            "source": FIRST_SESSION_STRATEGY_SOURCE,
            "scenario_id": scenario,
            "no_real_broker_writes": True,
        },
        result_payload={
            "approved": risk_passed,
            "reason_codes": list(risk_reason_codes),
        },
        created_at=state.input.started_at,
    )
    state.risk_check_id = risk_check.risk_check_id
    state.add_entity_id("risk_checks", risk_check.risk_check_id)
    state.add_step("persist_risk_check", "passed", "risk_check_persisted")


def _dry_run_scenario_id(scenario_id: FirstSessionScenarioId) -> str:
    mapping: dict[FirstSessionScenarioId, str] = {
        "happy_path": "happy_path",
        "kill_switch_blocks": "kill_switch_pause_new_risk",
        "dirty_reconciliation_blocks": "reconciliation_mismatch",
        "missing_stop_incident": "missing_protective_stop",
        "duplicate_intent_blocks": "duplicate_active_intent",
        "leverage_rejected": "risk_rejection",
        "short_rejected": "risk_rejection",
        "missing_operator_approval": "risk_rejection",
        "live_endpoint_rejected": "risk_rejection",
        "missing_execution_intent": "risk_rejection",
        "unsupported_asset_rejected": "risk_rejection",
        "partial_fill": "partial_fill",
    }
    return mapping[scenario_id]


def _merge_dry_run_evidence(
    state: _FirstSessionState,
    dry_run_result: DryRunResult,
) -> None:
    dry_scenario = dry_run_result.scenario_id
    state.candidate_id = f"candidate-{dry_scenario}"
    state.ai_news_output_id = f"ai-output-{dry_scenario}"
    state.decision_id = _latest_trade_decision_id(state)
    state.risk_check_id = f"risk-check-{dry_scenario}"
    state.execution_intent_id = dry_run_result.evidence.execution_intent_id
    state.broker_order_id = dry_run_result.evidence.fake_broker_order_id
    state.client_order_id = dry_run_result.evidence.client_order_id
    state.stop_verification_result = (
        "verified" if dry_run_result.evidence.protective_stop_verified else "not_verified"
    )
    state.post_run_reconciliation_id = f"reconciliation-{dry_scenario}"
    state.post_run_reconciliation_result = dry_run_result.evidence.reconciliation_status
    state.dashboard_snapshot = dry_run_result.dashboard_snapshot
    for key, values in dry_run_result.evidence.persisted_entity_ids.items():
        state.persisted_entity_ids.setdefault(key, []).extend(values)
    orders = state.repository.list_orders(limit=50)
    entry_orders = [order for order in orders if not order.client_order_id.endswith("-stop")]
    stop_orders = [order for order in orders if order.client_order_id.endswith("-stop")]
    if entry_orders:
        entry_order = entry_orders[-1]
        state.order_id = entry_order.order_id
    if stop_orders:
        stop_order = stop_orders[-1]
        state.protective_stop_order_id = stop_order.order_id
        state.protective_stop_client_order_id = stop_order.client_order_id
    fills = state.repository.list_fills(limit=50)
    if fills:
        fill = fills[-1]
        state.fill_id = fill.fill_id
        state.broker_fill_id = fill.broker_fill_id
    open_orders = state.repository.list_open_orders(limit=50)
    open_positions = state.repository.list_open_positions(limit=50)
    state.final_open_orders_status = "none" if not open_orders else f"{len(open_orders)} open"
    state.final_positions_status = (
        "none" if not open_positions else f"{len(open_positions)} open"
    )
    for record in state.repository.list_recent_incidents(limit=50):
        if record not in state.incident_records:
            state.incident_records.append(record)


def _latest_trade_decision_id(state: _FirstSessionState) -> str | None:
    decisions = state.repository.list_trade_decisions(limit=10)
    if not decisions:
        return None
    return decisions[0].decision_id


def _persist_incident(
    state: _FirstSessionState,
    *,
    reason_code: str,
    message: str,
    severity: FirstSessionSeverity,
) -> SystemEventRecord:
    return state.repository.insert_system_event(
        event_id=f"event-{state.session_id}-{reason_code}",
        event_type="first_session_wiring_incident",
        severity=severity,
        source_component="first_controlled_paper_session_harness",
        related_entity_type="first_session",
        related_entity_id=state.session_id,
        message=message,
        payload={"reason_code": reason_code, "fake_local": True},
        created_at=state.input.completed_at,
    )


def _generate_report_and_dashboard(state: _FirstSessionState, *, status: str) -> None:
    snapshot = build_report_input_snapshot(
        state.repository,
        generated_at=state.input.completed_at,
        environment=state.app_config.system.environment,
        dry_run=True,
        live_trading_enabled=False,
        autonomous_execution_enabled=False,
    )
    report_result = generate_daily_report(
        report_date=state.input.started_at.date(),
        snapshot=snapshot,
    )
    persisted_report = persist_report_generation_result(state.repository, report_result)
    state.report_id = persisted_report.persisted_report_id
    state.report_path = (
        None if persisted_report.persisted_report_id is None else f"ledger://reports/{state.report_id}"
    )
    if persisted_report.persisted_report_id is not None:
        state.add_entity_id("reports", persisted_report.persisted_report_id)
    dashboard = LedgerDashboardReadModelProvider(
        state.repository,
        config=state.app_config,
        as_of=state.input.completed_at,
    ).snapshot()
    state.dashboard_snapshot = dashboard
    state.dashboard_snapshot_status = dashboard.system_state.data_source
    open_orders = state.repository.list_open_orders(limit=50)
    open_positions = state.repository.list_open_positions(limit=50)
    state.final_open_orders_status = "none" if not open_orders else f"{len(open_orders)} open"
    state.final_positions_status = (
        "none" if not open_positions else f"{len(open_positions)} open"
    )
    state.add_step("generate_report_and_dashboard", "passed", "report_and_dashboard_ready")
    _dispatch_alert(
        state,
        category="report_generated",
        severity="info",
        title="First-session fake/local evidence package generated",
        body=f"First-session fake/local wiring report generated with status {status}.",
        related_entity_id=state.report_id,
        payload={"status": status, "fake_local": True},
    )


def _dispatch_alert(
    state: _FirstSessionState,
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
            source_component="first_controlled_paper_session_harness",
            created_at=state.input.completed_at,
            related_entity_type="first_session",
            related_entity_id=related_entity_id,
            payload=dict(payload),
        )
    )


def _alert_category_for_reason(reason_code: str) -> AlertCategory:
    if "reconciliation" in reason_code:
        return "reconciliation_mismatch"
    if "kill_switch" in reason_code:
        return "kill_switch_activation"
    if "duplicate" in reason_code:
        return "duplicate_order_or_intent"
    if "protective_stop" in reason_code:
        return "missing_protective_stop"
    return "manual_control_action"


def _incident_from_record(record: SystemEventRecord) -> FirstSessionIncident:
    reason_code = str(record.payload.get("reason_code") or record.event_type)
    return FirstSessionIncident(
        incident_id=record.event_id,
        severity=record.severity,
        reason_code=reason_code,
        message=record.message,
    )


def _config_safety_snapshot(app_config: AppConfig) -> dict[str, Any]:
    return {
        "environment": app_config.system.environment,
        "dry_run": app_config.system.dry_run,
        "live_trading_enabled": app_config.system.live_trading_enabled,
        "system_autonomous_execution_enabled": app_config.system.autonomous_execution_enabled,
        "execution_autonomous_execution_enabled": (
            app_config.execution.autonomous_execution_enabled
        ),
        "allow_live_orders": app_config.execution.allow_live_orders,
        "require_execution_intent": app_config.execution.require_execution_intent,
        "require_broker_reconciliation_before_order": (
            app_config.execution.require_broker_reconciliation_before_order
        ),
        "require_protective_stop": app_config.execution.require_protective_stop,
        "risk_max_gross_exposure_pct": (
            app_config.risk_level_4_micro_live.max_gross_exposure_pct
        ),
        "risk_allow_margin": app_config.risk_level_4_micro_live.allow_margin,
        "risk_allow_shorting": app_config.risk_level_4_micro_live.allow_shorting,
        "risk_allow_options": app_config.risk_level_4_micro_live.allow_options,
        "risk_allow_leveraged_etfs": app_config.risk_level_4_micro_live.allow_leveraged_etfs,
        "risk_allow_futures": app_config.risk_level_4_micro_live.allow_futures,
        "risk_allow_crypto": app_config.risk_level_4_micro_live.allow_crypto,
        "risk_allow_prediction_markets": (
            app_config.risk_level_4_micro_live.allow_prediction_markets
        ),
        "ai_allow_ai_to_create_orders": app_config.ai.allow_ai_to_create_orders,
        "secrets": {name: "<redacted-not-inspected>" for name in SENSITIVE_ENV_NAMES},
    }


def _git_commit_or_unavailable() -> str:
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return "unavailable"
    value = completed.stdout.strip()
    return value or "unavailable"


def _scenario_uuid(scenario_id: str, label: str) -> UUID:
    return uuid5(NAMESPACE_URL, f"first-session:{scenario_id}:{label}")


def _unique(values: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(values))


def _require_aware(value: datetime, field_name: str) -> None:
    if value.tzinfo is None:
        raise ValueError(f"{field_name} must be timezone-aware")
