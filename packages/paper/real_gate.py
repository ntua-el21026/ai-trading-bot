"""Real-gated first controlled paper-session wiring.

This module prepares the first controlled paper-session real gate path without executing a real
broker-write session. Default and real-gated modes refuse before external calls. Fake mode can
exercise the Milestone 29 local harness after all real-session gates are represented as satisfied.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal, Self, cast

from pydantic import BaseModel, ConfigDict, Field, model_validator

from packages.core.config import AppConfig, load_app_config
from packages.ledger.connection import connect_in_memory_sqlite
from packages.ledger.repositories import SQLiteLedgerRepository
from packages.paper.first_session import (
    FIRST_SESSION_SPEC_VERSION,
    FirstSessionEvidencePackage,
    FirstSessionIncident,
    default_first_session_input,
    run_first_controlled_paper_session_check,
)

MILESTONE_30_FAKE_OPERATOR_APPROVAL = "MILESTONE_30_FAKE_ONLY"
MILESTONE_30_REAL_OPERATOR_APPROVAL = "FIRST_CONTROLLED_PAPER_SESSION_OPERATOR_APPROVED"
REAL_SESSION_STARTED_AT = datetime(2026, 5, 8, 14, 0, tzinfo=UTC)
REAL_SESSION_MAX_QUANTITY = 1
REAL_SESSION_MAX_NOTIONAL_USD = 1_000.0

RealSessionMode = Literal["real-gated", "fake"]
RealSessionScenarioId = Literal[
    "happy_path",
    "missing_operator_approval",
    "missing_real_write_gate",
    "live_endpoint_rejected",
    "paper_endpoint_not_proven",
    "live_trading_enabled",
    "autonomous_live_execution_enabled",
    "schedules_active",
    "leverage_rejected",
    "gross_exposure_rejected",
    "short_rejected",
    "unsupported_asset_rejected",
    "unsupported_order_type_rejected",
    "dirty_reconciliation_blocks",
    "kill_switch_blocks",
    "blocking_incident_blocks",
    "duplicate_intent_blocks",
    "missing_execution_intent",
    "missing_idempotency_key",
    "missing_protective_stop_plan",
    "missing_cleanup_policy",
    "missing_evidence_persistence",
    "ambiguous_broker_state",
    "missing_stop_incident",
    "ai_broker_write_request_rejected",
]
BrokerEndpointMode = Literal["paper", "live", "unknown"]
BrokerAdapterMode = Literal["fake", "real_alpaca_paper_deferred"]
CleanupPolicy = Literal["verify_only", "manual_cleanup_policy_recorded"]
LedgerPersistenceMode = Literal["local_sqlite", "missing"]
AlertMode = Literal["fake"]

REAL_SESSION_SCENARIO_IDS: tuple[RealSessionScenarioId, ...] = (
    "happy_path",
    "missing_operator_approval",
    "missing_real_write_gate",
    "live_endpoint_rejected",
    "paper_endpoint_not_proven",
    "live_trading_enabled",
    "autonomous_live_execution_enabled",
    "schedules_active",
    "leverage_rejected",
    "gross_exposure_rejected",
    "short_rejected",
    "unsupported_asset_rejected",
    "unsupported_order_type_rejected",
    "dirty_reconciliation_blocks",
    "kill_switch_blocks",
    "blocking_incident_blocks",
    "duplicate_intent_blocks",
    "missing_execution_intent",
    "missing_idempotency_key",
    "missing_protective_stop_plan",
    "missing_cleanup_policy",
    "missing_evidence_persistence",
    "ambiguous_broker_state",
    "missing_stop_incident",
    "ai_broker_write_request_rejected",
)


class RealSessionModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class RealSessionGateConfig(RealSessionModel):
    mode: RealSessionMode = "real-gated"
    session_id: str
    operator_approval_marker: str | None = None
    expected_spec_version: str = FIRST_SESSION_SPEC_VERSION
    expected_commit_hash_or_marker: str = "recorded-by-future-operator"
    allow_real_alpaca_paper_writes: bool = False
    confirm_paper_endpoint: bool = True
    confirm_live_endpoint_forbidden: bool = True
    confirm_no_schedules: bool = True
    confirm_no_live_trading: bool = True
    confirm_no_autonomous_live_execution: bool = True
    confirm_no_leverage: bool = True
    max_gross_exposure: float = Field(default=1.0, gt=0, le=1)
    target_symbol_allowlist: tuple[str, ...] = ("AAPL",)
    target_symbol: str = "AAPL"
    side: Literal["buy", "sell"] = "buy"
    asset_class: str = "equity"
    order_type: str = "limit"
    quantity: int = Field(default=1, gt=0)
    max_quantity: int = Field(default=REAL_SESSION_MAX_QUANTITY, gt=0)
    estimated_notional_usd: float = Field(default=180.50, gt=0)
    max_notional_usd: float = Field(default=REAL_SESSION_MAX_NOTIONAL_USD, gt=0)
    cleanup_policy: CleanupPolicy | None = "verify_only"
    alert_mode: AlertMode = "fake"
    ledger_persistence_mode: LedgerPersistenceMode = "local_sqlite"
    broker_adapter_mode: BrokerAdapterMode = "real_alpaca_paper_deferred"
    broker_endpoint_mode: BrokerEndpointMode = "paper"
    paper_endpoint_proven: bool = True
    live_endpoint_rejected: bool = True
    schedules_active_or_expected: bool = False
    simulated_live_trading_enabled: bool = False
    simulated_autonomous_live_execution_enabled: bool = False
    leverage_allowed: bool = False
    current_gross_exposure: float = Field(default=0.0, ge=0)
    broker_reconciliation_clean: bool = True
    kill_switch_state: Literal["RUNNING", "PAUSED_NEW_RISK"] = "RUNNING"
    unresolved_blocking_incidents: int = Field(default=0, ge=0)
    duplicate_active_intent: bool = False
    valid_execution_intent_present: bool = True
    idempotency_key_present: bool = True
    protective_stop_plan_present: bool = True
    protective_stop_plan_id: str | None = "first-session-stop-plan"
    broker_state_ambiguous: bool = False
    ai_requested_broker_write: bool = False
    started_at: datetime = REAL_SESSION_STARTED_AT

    @model_validator(mode="after")
    def validate_gate_config(self) -> Self:
        if self.target_symbol != self.target_symbol.upper():
            raise ValueError("target_symbol must be uppercase")
        if any(symbol != symbol.upper() for symbol in self.target_symbol_allowlist):
            raise ValueError("target_symbol_allowlist symbols must be uppercase")
        if self.started_at.tzinfo is None:
            raise ValueError("started_at must be timezone-aware")
        return self


class RealSessionPreflightResult(RealSessionModel):
    preflight_evidence_id: str
    account_read_status: str
    clock_session_status: str
    paper_endpoint_proven: bool
    live_endpoint_rejected: bool
    broker_endpoint_mode: BrokerEndpointMode
    open_orders_summary: str
    positions_summary: str
    target_symbol_allowed: bool
    target_symbol_clean: bool
    equity: float = Field(gt=0)
    buying_power: float = Field(ge=0)
    current_gross_exposure: float = Field(ge=0)
    max_gross_exposure: float = Field(gt=0, le=1)
    no_leverage_assertion: bool
    no_schedule_assertion: bool
    kill_switch_state: Literal["RUNNING", "PAUSED_NEW_RISK"]
    prior_incident_review_status: str
    blocking_incident_count: int = Field(ge=0)
    broker_reconciliation_clean: bool
    broker_state_ambiguous: bool = False
    external_calls_attempted: bool = False


class RealSessionGateEvaluation(RealSessionModel):
    gate_name: str
    passed: bool
    reason_code: str
    details: dict[str, str] = Field(default_factory=dict)


class RealSessionGateEvidence(RealSessionModel):
    real_write_gates_evaluated: bool
    real_write_gates_passed: bool
    broker_adapter_mode: BrokerAdapterMode
    broker_endpoint_mode: BrokerEndpointMode
    preflight_evidence_id: str | None
    reconciliation_evidence_id: str | None
    protective_stop_plan_id: str | None
    cleanup_policy_id: str | None
    refusal_reason_ids: tuple[str, ...]
    gate_evaluations: tuple[RealSessionGateEvaluation, ...]
    alert_mode: AlertMode
    ledger_persistence_mode: LedgerPersistenceMode
    external_calls_attempted: bool = False
    real_broker_writes_attempted: bool = False
    real_broker_orders_submitted: bool = False
    ai_broker_write_authority: bool = False


class RealSessionResult(RealSessionModel):
    scenario_id: RealSessionScenarioId
    mode: RealSessionMode
    success: bool
    refused: bool
    unsafe: bool
    ready_for_future_real_execution: bool
    actual_paper_trading_started: bool = False
    real_broker_orders_submitted: bool = False
    real_broker_writes_attempted: bool = False
    external_calls_attempted: bool = False
    schedules_activated: bool = False
    live_trading_enabled: bool = False
    autonomous_live_execution_enabled: bool = False
    level4_ready: bool = False
    leverage_enabled: bool = False
    ai_broker_write_authority: bool = False
    preflight: RealSessionPreflightResult | None
    real_gate_evidence: RealSessionGateEvidence
    first_session_evidence: FirstSessionEvidencePackage | None = None
    incidents: tuple[FirstSessionIncident, ...] = ()
    refusal_reasons: tuple[str, ...] = ()
    note: str = (
        "Milestone 30 real-gate wiring only. Actual paper trading has not started and no real "
        "broker orders were submitted."
    )

    @model_validator(mode="after")
    def validate_no_real_execution(self) -> Self:
        if self.success and (self.refused or self.unsafe):
            raise ValueError("successful result cannot also be refused or unsafe")
        forbidden = {
            "actual_paper_trading_started": self.actual_paper_trading_started,
            "real_broker_orders_submitted": self.real_broker_orders_submitted,
            "real_broker_writes_attempted": self.real_broker_writes_attempted,
            "external_calls_attempted": self.external_calls_attempted,
            "schedules_activated": self.schedules_activated,
            "live_trading_enabled": self.live_trading_enabled,
            "autonomous_live_execution_enabled": self.autonomous_live_execution_enabled,
            "level4_ready": self.level4_ready,
            "leverage_enabled": self.leverage_enabled,
            "ai_broker_write_authority": self.ai_broker_write_authority,
        }
        enabled = [name for name, value in forbidden.items() if value]
        if enabled:
            raise ValueError(f"real-gate result enabled forbidden flags: {enabled}")
        return self


def default_real_session_gate_config(
    scenario_id: str = "happy_path",
    *,
    mode: RealSessionMode = "real-gated",
    operator_approval_marker: str | None = None,
) -> RealSessionGateConfig:
    scenario = _validate_scenario_id(scenario_id)
    marker = operator_approval_marker
    config = RealSessionGateConfig(
        mode=mode,
        session_id=f"first-controlled-paper-session-real-gate-{scenario}",
        operator_approval_marker=marker,
        broker_adapter_mode=(
            "fake" if mode == "fake" else "real_alpaca_paper_deferred"
        ),
        allow_real_alpaca_paper_writes=False if mode == "fake" else False,
    )
    return _scenario_config(config, scenario)


def run_real_first_controlled_paper_session_gate(
    gate_config: RealSessionGateConfig | None = None,
    *,
    repository: SQLiteLedgerRepository | None = None,
    app_config: AppConfig | None = None,
) -> RealSessionResult:
    active_config = app_config or load_app_config()
    active_repository = repository or SQLiteLedgerRepository(connect_in_memory_sqlite())
    config = gate_config or default_real_session_gate_config()

    if not _operator_approval_valid(config):
        gate = _gate("operator_approval", False, "operator_approval_missing")
        evidence = _real_gate_evidence(
            config,
            preflight=None,
            gate_evaluations=(gate,),
        )
        return _result(
            config,
            success=False,
            refused=True,
            unsafe=False,
            ready=False,
            preflight=None,
            evidence=evidence,
            refusal_reasons=("operator_approval_missing",),
        )

    preflight = _build_fake_preflight(config)
    gate_evaluations = _evaluate_real_session_gates(
        config,
        app_config=active_config,
        preflight=preflight,
    )
    failed_reasons = tuple(gate.reason_code for gate in gate_evaluations if not gate.passed)
    evidence = _real_gate_evidence(
        config,
        preflight=preflight,
        gate_evaluations=gate_evaluations,
    )
    if failed_reasons:
        return _result(
            config,
            success=False,
            refused=True,
            unsafe=False,
            ready=False,
            preflight=preflight,
            evidence=evidence,
            refusal_reasons=failed_reasons,
        )

    if config.mode != "fake":
        deferred_reason = "real_session_execution_deferred_milestone_30"
        return _result(
            config,
            success=False,
            refused=True,
            unsafe=False,
            ready=True,
            preflight=preflight,
            evidence=_real_gate_evidence(
                config,
                preflight=preflight,
                gate_evaluations=gate_evaluations
                + (_gate("milestone_execution_boundary", False, deferred_reason),),
            ),
            refusal_reasons=(deferred_reason,),
        )

    fake_result = run_first_controlled_paper_session_check(
        default_first_session_input(_fake_first_session_scenario(config)),
        repository=active_repository,
        app_config=active_config,
    )
    return _result(
        config,
        success=fake_result.success,
        refused=fake_result.refused,
        unsafe=fake_result.unsafe,
        ready=fake_result.success,
        preflight=preflight,
        evidence=evidence,
        first_session_evidence=fake_result.evidence_package,
        incidents=fake_result.incidents,
        refusal_reasons=fake_result.refusal_reasons,
    )


def _validate_scenario_id(scenario_id: str) -> RealSessionScenarioId:
    if scenario_id not in REAL_SESSION_SCENARIO_IDS:
        allowed = ", ".join(REAL_SESSION_SCENARIO_IDS)
        raise ValueError(f"unknown real-session scenario_id: {scenario_id}; allowed: {allowed}")
    return cast(RealSessionScenarioId, scenario_id)


def _scenario_config(
    config: RealSessionGateConfig,
    scenario: RealSessionScenarioId,
) -> RealSessionGateConfig:
    updates: dict[str, object] = {}
    if scenario == "missing_operator_approval":
        updates["operator_approval_marker"] = None
    elif scenario == "missing_real_write_gate":
        updates["mode"] = "real-gated"
        updates["allow_real_alpaca_paper_writes"] = False
    elif scenario == "live_endpoint_rejected":
        updates["broker_endpoint_mode"] = "live"
        updates["paper_endpoint_proven"] = False
    elif scenario == "paper_endpoint_not_proven":
        updates["paper_endpoint_proven"] = False
    elif scenario == "live_trading_enabled":
        updates["simulated_live_trading_enabled"] = True
    elif scenario == "autonomous_live_execution_enabled":
        updates["simulated_autonomous_live_execution_enabled"] = True
    elif scenario == "schedules_active":
        updates["schedules_active_or_expected"] = True
    elif scenario == "leverage_rejected":
        updates["leverage_allowed"] = True
    elif scenario == "gross_exposure_rejected":
        updates["current_gross_exposure"] = 1.01
    elif scenario == "short_rejected":
        updates["side"] = "sell"
    elif scenario == "unsupported_asset_rejected":
        updates["asset_class"] = "crypto"
    elif scenario == "unsupported_order_type_rejected":
        updates["order_type"] = "market"
    elif scenario == "dirty_reconciliation_blocks":
        updates["broker_reconciliation_clean"] = False
    elif scenario == "kill_switch_blocks":
        updates["kill_switch_state"] = "PAUSED_NEW_RISK"
    elif scenario == "blocking_incident_blocks":
        updates["unresolved_blocking_incidents"] = 1
    elif scenario == "duplicate_intent_blocks":
        updates["duplicate_active_intent"] = True
    elif scenario == "missing_execution_intent":
        updates["valid_execution_intent_present"] = False
    elif scenario == "missing_idempotency_key":
        updates["idempotency_key_present"] = False
    elif scenario == "missing_protective_stop_plan":
        updates["protective_stop_plan_present"] = False
        updates["protective_stop_plan_id"] = None
    elif scenario == "missing_cleanup_policy":
        updates["cleanup_policy"] = None
    elif scenario == "missing_evidence_persistence":
        updates["ledger_persistence_mode"] = "missing"
    elif scenario == "ambiguous_broker_state":
        updates["broker_state_ambiguous"] = True
    elif scenario == "ai_broker_write_request_rejected":
        updates["ai_requested_broker_write"] = True
    return config.model_copy(update=updates)


def _operator_approval_valid(config: RealSessionGateConfig) -> bool:
    if config.mode == "fake":
        return config.operator_approval_marker == MILESTONE_30_FAKE_OPERATOR_APPROVAL
    return config.operator_approval_marker == MILESTONE_30_REAL_OPERATOR_APPROVAL


def _build_fake_preflight(config: RealSessionGateConfig) -> RealSessionPreflightResult:
    return RealSessionPreflightResult(
        preflight_evidence_id=f"preflight-{config.session_id}",
        account_read_status="stubbed_account_ready",
        clock_session_status="stubbed_market_open",
        paper_endpoint_proven=config.paper_endpoint_proven,
        live_endpoint_rejected=config.live_endpoint_rejected
        and config.broker_endpoint_mode != "live",
        broker_endpoint_mode=config.broker_endpoint_mode,
        open_orders_summary="ambiguous" if config.broker_state_ambiguous else "clean",
        positions_summary="clean",
        target_symbol_allowed=config.target_symbol in config.target_symbol_allowlist,
        target_symbol_clean=not config.broker_state_ambiguous,
        equity=100_000.0,
        buying_power=100_000.0,
        current_gross_exposure=config.current_gross_exposure,
        max_gross_exposure=config.max_gross_exposure,
        no_leverage_assertion=not config.leverage_allowed
        and config.current_gross_exposure <= config.max_gross_exposure,
        no_schedule_assertion=not config.schedules_active_or_expected,
        kill_switch_state=config.kill_switch_state,
        prior_incident_review_status=(
            "blocking_incidents_present"
            if config.unresolved_blocking_incidents
            else "reviewed_clear"
        ),
        blocking_incident_count=config.unresolved_blocking_incidents,
        broker_reconciliation_clean=config.broker_reconciliation_clean,
        broker_state_ambiguous=config.broker_state_ambiguous,
    )


def _evaluate_real_session_gates(
    config: RealSessionGateConfig,
    *,
    app_config: AppConfig,
    preflight: RealSessionPreflightResult,
) -> tuple[RealSessionGateEvaluation, ...]:
    return (
        _gate("operator_approval", True, "operator_approval_present"),
        _gate(
            "real_write_permission",
            config.mode == "fake" or config.allow_real_alpaca_paper_writes,
            "fake_mode_no_real_write"
            if config.mode == "fake"
            else "real_broker_writes_not_explicitly_allowed",
        ),
        _gate(
            "paper_endpoint_proof",
            config.confirm_paper_endpoint
            and preflight.paper_endpoint_proven
            and preflight.broker_endpoint_mode == "paper",
            "paper_endpoint_not_proven",
        ),
        _gate(
            "live_endpoint_forbidden",
            config.confirm_live_endpoint_forbidden
            and preflight.live_endpoint_rejected
            and preflight.broker_endpoint_mode != "live",
            "live_endpoint_detected",
        ),
        _gate(
            "live_trading_disabled",
            config.confirm_no_live_trading
            and not config.simulated_live_trading_enabled
            and not app_config.system.live_trading_enabled,
            "live_trading_enabled",
        ),
        _gate(
            "autonomous_live_execution_disabled",
            config.confirm_no_autonomous_live_execution
            and not config.simulated_autonomous_live_execution_enabled
            and not app_config.system.autonomous_execution_enabled
            and not app_config.execution.autonomous_execution_enabled,
            "autonomous_live_execution_enabled",
        ),
        _gate(
            "schedules_inactive",
            config.confirm_no_schedules and preflight.no_schedule_assertion,
            "schedules_active_or_expected",
        ),
        _gate(
            "no_leverage",
            config.confirm_no_leverage
            and preflight.no_leverage_assertion
            and not app_config.risk_level_4_micro_live.allow_margin,
            "leverage_not_allowed",
        ),
        _gate(
            "gross_exposure_le_1x",
            preflight.current_gross_exposure <= 1.0
            and preflight.current_gross_exposure <= preflight.max_gross_exposure,
            "gross_exposure_exceeds_1x",
        ),
        _gate("long_only_side", config.side == "buy", "short_side_forbidden"),
        _gate(
            "supported_asset_class",
            config.asset_class in {"equity", "etf"},
            f"unsupported_asset_class:{config.asset_class}",
        ),
        _gate("supported_order_type", config.order_type == "limit", "unsupported_order_type"),
        _gate(
            "target_symbol_allowed",
            preflight.target_symbol_allowed,
            "target_symbol_not_allowed",
        ),
        _gate(
            "target_symbol_clean",
            preflight.target_symbol_clean,
            "target_symbol_not_clean",
        ),
        _gate(
            "quantity_cap",
            config.quantity <= config.max_quantity,
            "quantity_cap_exceeded",
        ),
        _gate(
            "notional_cap",
            config.estimated_notional_usd <= config.max_notional_usd,
            "notional_cap_exceeded",
        ),
        _gate(
            "pre_run_reconciliation_clean",
            preflight.broker_reconciliation_clean,
            "pre_run_reconciliation_not_clean",
        ),
        _gate(
            "kill_switch_allows_new_risk",
            preflight.kill_switch_state == "RUNNING",
            "kill_switch_blocks_new_risk",
        ),
        _gate(
            "blocking_incidents_clear",
            preflight.blocking_incident_count == 0,
            "unresolved_blocking_incident",
        ),
        _gate(
            "duplicate_active_intent_absent",
            not config.duplicate_active_intent,
            "active_duplicate_intent",
        ),
        _gate(
            "execution_intent_present",
            config.valid_execution_intent_present,
            "execution_intent_required",
        ),
        _gate(
            "idempotency_key_present",
            config.idempotency_key_present,
            "idempotency_key_required",
        ),
        _gate(
            "protective_stop_plan_present",
            config.protective_stop_plan_present
            and config.protective_stop_plan_id is not None,
            "protective_stop_plan_required",
        ),
        _gate(
            "cleanup_policy_recorded",
            config.cleanup_policy is not None,
            "cleanup_policy_required",
        ),
        _gate(
            "evidence_persistence_target_present",
            config.ledger_persistence_mode != "missing",
            "evidence_persistence_target_required",
        ),
        _gate(
            "broker_state_unambiguous",
            not preflight.broker_state_ambiguous,
            "ambiguous_broker_state",
        ),
        _gate(
            "ai_has_no_broker_authority",
            not config.ai_requested_broker_write and not app_config.ai.allow_ai_to_create_orders,
            "ai_broker_write_forbidden",
        ),
    )


def _gate(
    gate_name: str,
    passed: bool,
    reason_code: str,
) -> RealSessionGateEvaluation:
    return RealSessionGateEvaluation(
        gate_name=gate_name,
        passed=passed,
        reason_code=reason_code if not passed else f"{gate_name}_passed",
    )


def _real_gate_evidence(
    config: RealSessionGateConfig,
    *,
    preflight: RealSessionPreflightResult | None,
    gate_evaluations: tuple[RealSessionGateEvaluation, ...],
) -> RealSessionGateEvidence:
    failed = tuple(gate.reason_code for gate in gate_evaluations if not gate.passed)
    gates_passed = not failed
    return RealSessionGateEvidence(
        real_write_gates_evaluated=True,
        real_write_gates_passed=gates_passed,
        broker_adapter_mode=config.broker_adapter_mode,
        broker_endpoint_mode=config.broker_endpoint_mode,
        preflight_evidence_id=None if preflight is None else preflight.preflight_evidence_id,
        reconciliation_evidence_id=(
            None if preflight is None else f"reconciliation-{preflight.preflight_evidence_id}"
        ),
        protective_stop_plan_id=config.protective_stop_plan_id,
        cleanup_policy_id=None if config.cleanup_policy is None else f"cleanup-{config.session_id}",
        refusal_reason_ids=failed,
        gate_evaluations=gate_evaluations,
        alert_mode=config.alert_mode,
        ledger_persistence_mode=config.ledger_persistence_mode,
    )


def _fake_first_session_scenario(config: RealSessionGateConfig) -> str:
    if config.broker_state_ambiguous:
        return "dirty_reconciliation_blocks"
    if config.kill_switch_state != "RUNNING":
        return "kill_switch_blocks"
    if config.duplicate_active_intent:
        return "duplicate_intent_blocks"
    if config.protective_stop_plan_present and config.protective_stop_plan_id is None:
        return "missing_stop_incident"
    if config.session_id.endswith("missing_stop_incident"):
        return "missing_stop_incident"
    return "happy_path"


def _result(
    config: RealSessionGateConfig,
    *,
    success: bool,
    refused: bool,
    unsafe: bool,
    ready: bool,
    preflight: RealSessionPreflightResult | None,
    evidence: RealSessionGateEvidence,
    first_session_evidence: FirstSessionEvidencePackage | None = None,
    incidents: tuple[FirstSessionIncident, ...] = (),
    refusal_reasons: tuple[str, ...] = (),
) -> RealSessionResult:
    return RealSessionResult(
        scenario_id=_scenario_from_session_id(config.session_id),
        mode=config.mode,
        success=success,
        refused=refused,
        unsafe=unsafe,
        ready_for_future_real_execution=ready and config.mode != "fake",
        preflight=preflight,
        real_gate_evidence=evidence,
        first_session_evidence=first_session_evidence,
        incidents=incidents,
        refusal_reasons=_unique(refusal_reasons),
    )


def _scenario_from_session_id(session_id: str) -> RealSessionScenarioId:
    prefix = "first-controlled-paper-session-real-gate-"
    if not session_id.startswith(prefix):
        return "happy_path"
    return _validate_scenario_id(session_id.removeprefix(prefix))


def _unique(values: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(values))
