"""Milestone 42 supervised one-shot paper schedule boundary."""

from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal, Protocol
from uuid import NAMESPACE_URL, uuid5

from pydantic import BaseModel, ConfigDict, Field, model_validator

from packages.broker.alpaca import (
    AlpacaClientError,
    AlpacaPaperAdapter,
    AlpacaPaperCredentials,
    map_alpaca_clock,
)
from packages.broker.fakes import DEFAULT_AS_OF, FakeAlpacaClient
from packages.broker.models import BrokerOrder, BrokerPosition
from packages.broker.order_lifecycle_smoke import (
    AlpacaPaperOrderLifecycleClient,
    AlpacaPaperOrderLifecycleSmokeSettings,
    build_alpaca_paper_order_lifecycle_http_client,
)
from packages.broker.smoke import validate_alpaca_paper_readonly_smoke_gates
from packages.core.config import AppConfig, load_app_config
from packages.paper.execution import (
    ETF_SYMBOLS,
    M41_SUPERVISED_SCHEDULE_READINESS_EVIDENCE_PATH,
    MILESTONE_42_REAL_OPERATOR_APPROVAL,
    _run_adapter_execution,
    default_first_paper_session_execution_request,
    run_first_controlled_paper_session_execution,
)
from packages.paper.first_session import FIRST_SESSION_SPEC_VERSION, SENSITIVE_ENV_NAMES
from packages.paper.post_session_audit import (
    ProtectedHoldingVerification,
    SupervisedScheduleReadinessPacket,
)

M42_SUPERVISED_SCHEDULED_PAPER_RUN_EVIDENCE_PATH = (
    "docs/evidence/supervised_scheduled_paper_run_m42.json"
)

M42Mode = Literal["fake", "real-paper"]
M42Status = Literal["executed", "refused", "incident"]
M42FreezeReadinessRecommendation = Literal[
    "M43_FREEZE_READINESS_MAY_BE_CONSIDERED",
    "M43_FREEZE_READINESS_BLOCKED_PENDING_ACCEPTED_SUPERVISED_SCHEDULED_RUN",
]


class M42ClientFactory(Protocol):
    def __call__(
        self,
        credentials: AlpacaPaperCredentials,
        settings: AlpacaPaperOrderLifecycleSmokeSettings,
    ) -> AlpacaPaperOrderLifecycleClient:
        """Build a paper broker client."""


class M42Model(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class M41ReadinessPacketAudit(M42Model):
    packet_path: str
    parseable: bool
    milestone: str | None
    readiness_go: bool
    aapl_protected_hold_verified: bool
    msft_protected_hold_verified: bool
    no_unexpected_open_orders: bool
    no_unexpected_positions: bool
    reconciliation_clean: bool
    supervised_run_m42_may_be_considered: bool
    schedules_not_activated: bool
    frozen_validation_started: bool
    level4_ready: bool
    blockers: tuple[str, ...]


class M42CandidateEnvelope(M42Model):
    target_symbol: str
    max_quantity: int = Field(gt=0)
    max_notional_usd: float = Field(gt=0)
    limit_price: float = Field(gt=0)
    estimated_notional_usd: float

    @model_validator(mode="after")
    def validate_estimated_notional(self) -> M42CandidateEnvelope:
        expected = round(self.max_quantity * self.limit_price, 6)
        if abs(self.estimated_notional_usd - expected) > 1e-9:
            raise ValueError("estimated_notional_usd must equal quantity * limit_price")
        return self


class M42CandidateEvaluation(M42Model):
    target_symbol: str
    envelope: M42CandidateEnvelope
    allowed: bool
    clean: bool
    open_order_count: int = Field(ge=0)
    position_quantity: float
    envelope_valid: bool
    selected: bool
    blockers: tuple[str, ...]


class M42BrokerStateSummary(M42Model):
    account_reachable: bool
    clock_reachable: bool
    clock_is_open: bool | None
    paper_endpoint_proven: bool
    live_endpoint_used: bool = False
    protected_holds: tuple[ProtectedHoldingVerification, ...]
    open_orders_total: int = Field(ge=0)
    expected_protective_stop_open_orders: int = Field(ge=0)
    unexpected_open_orders_count: int = Field(ge=0)
    unexpected_open_order_symbols: tuple[str, ...]
    positions_total: int = Field(ge=0)
    unexpected_positions_count: int = Field(ge=0)
    unexpected_position_symbols: tuple[str, ...]
    candidate_target_states: tuple[M42CandidateEvaluation, ...] = ()
    reconciliation_summary: str
    read_only_calls_performed: bool
    broker_writes_attempted: bool = False


class M42ScheduleActionRecord(M42Model):
    action: str
    status: str
    detail: str


class SupervisedScheduledPaperRunRequest(M42Model):
    mode: M42Mode = "real-paper"
    operator_approval_marker: str | None = None
    primary_target_symbol: str = "XLK"
    primary_max_quantity: int = Field(default=1, gt=0)
    primary_max_notional_usd: float = Field(default=300.0, gt=0)
    primary_limit_price: float = Field(default=300.0, gt=0)
    fallback_target_symbol: str = "XLF"
    fallback_max_quantity: int = Field(default=1, gt=0)
    fallback_max_notional_usd: float = Field(default=100.0, gt=0)
    fallback_limit_price: float = Field(default=100.0, gt=0)
    execution_scenario_id: str = "happy_path"
    m41_readiness_packet_path: str = M41_SUPERVISED_SCHEDULE_READINESS_EVIDENCE_PATH
    confirm_paper_endpoint: bool = False
    confirm_temporary_supervised_schedule_only: bool = False
    confirm_disable_after_one_run: bool = False
    confirm_no_live_trading: bool = False
    confirm_no_autonomous_live: bool = False
    confirm_no_unattended_operation: bool = False
    confirm_no_leverage: bool = False
    confirm_protective_stop_required: bool = False
    confirm_cleanup_policy: bool = False
    started_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @model_validator(mode="after")
    def validate_symbols(self) -> SupervisedScheduledPaperRunRequest:
        if self.primary_target_symbol != self.primary_target_symbol.upper():
            raise ValueError("primary_target_symbol must be uppercase")
        if self.fallback_target_symbol != self.fallback_target_symbol.upper():
            raise ValueError("fallback_target_symbol must be uppercase")
        if self.started_at.tzinfo is None:
            raise ValueError("started_at must be timezone-aware")
        return self


class SupervisedScheduledPaperRunPacket(M42Model):
    packet_id: str
    timestamp: datetime
    latest_spec_path: str
    spec_version: str
    commit_hash: str
    m41_readiness_packet_reference: str
    m41_readiness_audit: M41ReadinessPacketAudit
    current_broker_state_summary_before_schedule_run: M42BrokerStateSummary
    aapl_position_stop_status: ProtectedHoldingVerification | None
    msft_position_stop_status: ProtectedHoldingVerification | None
    schedule_workflow_creation_status: str
    schedule_workflow_activation_status: str
    schedule_workflow_run_status: str
    schedule_workflow_deactivation_status: str
    no_recurring_unattended_schedule_remains_active: bool
    selected_target_symbol: str | None
    no_go_reason: str | None
    candidate_evaluations: tuple[M42CandidateEvaluation, ...]
    order_envelope: M42CandidateEnvelope | None
    candidate_decision_risk_evidence: str
    execution_intent_id: str | None
    entry_order_status: str | None
    fill_status: str
    protective_stop_verification_result: str
    normal_stop_path_succeeded: bool
    recovery_stop_path_used: bool
    cleanup_flatten_result: str
    post_run_broker_state: M42BrokerStateSummary | None
    final_reconciliation: str
    incidents: tuple[str, ...]
    actual_paper_trading_started: bool
    broker_writes: tuple[dict[str, Any], ...]
    temporal_schedule_actions: tuple[M42ScheduleActionRecord, ...]
    provider_ai_telegram_vercel_calls: bool = False
    schedules_activated_final_state: bool = False
    live_trading_enabled: bool = False
    autonomous_live_execution_enabled: bool = False
    leverage_enabled: bool = False
    frozen_validation_started: bool = False
    level4_ready: bool = False
    ai_broker_write_authority: bool = False
    freeze_readiness_recommendation: M42FreezeReadinessRecommendation
    blockers: tuple[str, ...]
    secrets_redacted: dict[str, str] = Field(
        default_factory=lambda: {name: "<redacted-not-inspected>" for name in SENSITIVE_ENV_NAMES}
    )


class SupervisedScheduledPaperRunResult(M42Model):
    mode: M42Mode
    status: M42Status
    success: bool
    refused: bool
    unsafe: bool
    blockers: tuple[str, ...]
    packet: SupervisedScheduledPaperRunPacket
    packet_path: str | None = None
    broker_writes_performed: bool
    real_read_only_calls_performed: bool
    schedule_workflow_created_or_activated: bool
    schedule_workflow_remains_active: bool = False
    live_trading_enabled: bool = False
    autonomous_live_execution_enabled: bool = False
    unattended_operation_enabled: bool = False
    leverage_enabled: bool = False
    ai_broker_write_authority: bool = False
    frozen_validation_started: bool = False
    level4_ready: bool = False


def run_supervised_scheduled_paper_once(
    request: SupervisedScheduledPaperRunRequest | None = None,
    *,
    environ: Mapping[str, str] | None = None,
    app_config: AppConfig | None = None,
    client_factory: M42ClientFactory = build_alpaca_paper_order_lifecycle_http_client,
    now: datetime | None = None,
) -> SupervisedScheduledPaperRunResult:
    active_request = request or SupervisedScheduledPaperRunRequest()
    active_config = app_config or load_app_config()
    timestamp = now or active_request.started_at
    m41_audit = audit_m41_supervised_schedule_readiness_packet(
        active_request.m41_readiness_packet_path
    )
    gate_blockers = _request_gate_blockers(active_request, active_config)
    adapter_bundle, adapter_blockers, read_only_calls = _adapter_bundle_for_request(
        active_request,
        active_config,
        environ={} if environ is None else environ,
        client_factory=client_factory,
        gate_blockers=(*m41_audit.blockers, *gate_blockers),
    )
    if adapter_bundle is None:
        pre_state = _unreached_broker_state_summary()
        candidate_evaluations: tuple[M42CandidateEvaluation, ...] = ()
    else:
        pre_state = _broker_state_summary(
            adapter=adapter_bundle.adapter,
            client=adapter_bundle.client,
            expected_protected_symbols=("AAPL", "MSFT"),
            candidate_envelopes=_candidate_envelopes(active_request),
            app_config=active_config,
            read_only_calls_performed=read_only_calls,
        )
        candidate_evaluations = pre_state.candidate_target_states
    state_blockers = _pre_schedule_state_blockers(pre_state)
    selected_candidate = _select_candidate(candidate_evaluations)
    target_blockers = (
        ("no_safe_m42_candidate_target",) if selected_candidate is None else ()
    )
    pre_schedule_blockers = _unique(
        (
            *m41_audit.blockers,
            *gate_blockers,
            *adapter_blockers,
            *state_blockers,
            *target_blockers,
        )
    )

    if pre_schedule_blockers:
        return _result_without_execution(
            request=active_request,
            timestamp=timestamp,
            m41_audit=m41_audit,
            pre_state=pre_state,
            candidate_evaluations=candidate_evaluations,
            blockers=pre_schedule_blockers,
            read_only_calls=read_only_calls,
            no_go_reason=_first_or_none(pre_schedule_blockers),
        )

    assert selected_candidate is not None
    schedule_actions = _schedule_actions_for_run("completed_once")
    execution_result = _execute_selected_candidate(
        request=active_request,
        app_config=active_config,
        selected_candidate=selected_candidate,
        environ={} if environ is None else environ,
        client_factory=client_factory,
        adapter_bundle=adapter_bundle,
    )
    post_state, post_blockers = _post_run_state_for_result(
        request=active_request,
        app_config=active_config,
        selected_candidate=selected_candidate,
        execution_result=execution_result,
        adapter_bundle=adapter_bundle,
        environ={} if environ is None else environ,
        client_factory=client_factory,
        read_only_calls=read_only_calls,
    )
    execution_packet = execution_result.result_packet
    blockers = _unique(
        (
            *execution_result.blockers,
            *execution_packet.incidents,
            *post_blockers,
        )
    )
    success = execution_result.success and not blockers
    status: M42Status = "incident" if execution_result.unsafe else (
        "executed" if execution_result.status == "executed" else "refused"
    )
    freeze_recommendation: M42FreezeReadinessRecommendation = (
        "M43_FREEZE_READINESS_MAY_BE_CONSIDERED"
        if success
        else "M43_FREEZE_READINESS_BLOCKED_PENDING_ACCEPTED_SUPERVISED_SCHEDULED_RUN"
    )
    packet = _packet(
        request=active_request,
        timestamp=timestamp,
        m41_audit=m41_audit,
        pre_state=pre_state,
        selected_candidate=selected_candidate,
        candidate_evaluations=candidate_evaluations,
        schedule_actions=schedule_actions,
        execution_result=execution_result,
        post_state=post_state,
        blockers=blockers,
        no_go_reason=None if success else _first_or_none(blockers),
        freeze_recommendation=freeze_recommendation,
    )
    return SupervisedScheduledPaperRunResult(
        mode=active_request.mode,
        status=status,
        success=success,
        refused=status == "refused",
        unsafe=status == "incident",
        blockers=blockers,
        packet=packet,
        broker_writes_performed=execution_result.real_broker_writes_attempted,
        real_read_only_calls_performed=read_only_calls
        or execution_result.real_read_only_alpaca_calls_performed,
        schedule_workflow_created_or_activated=True,
    )


def audit_m41_supervised_schedule_readiness_packet(
    readiness_packet_path: str | Path,
) -> M41ReadinessPacketAudit:
    path = Path(readiness_packet_path)
    if not path.is_file():
        return M41ReadinessPacketAudit(
            packet_path=str(path),
            parseable=False,
            milestone=None,
            readiness_go=False,
            aapl_protected_hold_verified=False,
            msft_protected_hold_verified=False,
            no_unexpected_open_orders=False,
            no_unexpected_positions=False,
            reconciliation_clean=False,
            supervised_run_m42_may_be_considered=False,
            schedules_not_activated=False,
            frozen_validation_started=False,
            level4_ready=False,
            blockers=("m41_supervised_schedule_readiness_packet_missing",),
        )
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        packet = SupervisedScheduleReadinessPacket.model_validate(
            payload["supervised_schedule_readiness"]
        )
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError):
        return M41ReadinessPacketAudit(
            packet_path=str(path),
            parseable=False,
            milestone=None,
            readiness_go=False,
            aapl_protected_hold_verified=False,
            msft_protected_hold_verified=False,
            no_unexpected_open_orders=False,
            no_unexpected_positions=False,
            reconciliation_clean=False,
            supervised_run_m42_may_be_considered=False,
            schedules_not_activated=False,
            frozen_validation_started=False,
            level4_ready=False,
            blockers=("m41_supervised_schedule_readiness_packet_unparseable",),
        )
    result = payload.get("result", {})
    broker = packet.current_broker_state_summary
    readiness_go = (
        payload.get("milestone") == "41"
        and result.get("readiness_approved") is True
        and result.get("go_no_go") == "go"
        and not result.get("blockers")
        and not packet.blockers
        and not packet.missing_gates
    )
    aapl_verified = _holding_open_and_verified(packet.aapl_position_stop_status)
    msft_verified = _holding_open_and_verified(packet.msft_position_stop_status)
    no_unexpected_orders = broker.unexpected_open_orders_count == 0
    no_unexpected_positions = broker.unexpected_positions_count == 0
    reconciliation_clean = packet.reconciliation_summary == "clean_protected_holds"
    m42_considered = (
        packet.supervised_scheduled_paper_run_readiness_recommendation
        == "M42_SUPERVISED_SCHEDULED_PAPER_RUN_MAY_BE_CONSIDERED"
    )
    schedules_not_activated = (
        packet.schedules_activated is False
        and packet.temporal_schedules_created is False
        and packet.temporal_schedules_activated is False
        and result.get("schedules_created") is False
        and result.get("schedules_activated") is False
    )
    checks = {
        "m41_readiness_milestone_is_41": payload.get("milestone") == "41",
        "m41_readiness_go": readiness_go,
        "m41_aapl_protected_hold_verified": aapl_verified,
        "m41_msft_protected_hold_verified": msft_verified,
        "m41_no_unexpected_open_orders": no_unexpected_orders,
        "m41_no_unexpected_positions": no_unexpected_positions,
        "m41_reconciliation_clean_protected_holds": reconciliation_clean,
        "m41_recommends_m42_supervised_run": m42_considered,
        "m41_schedules_not_activated": schedules_not_activated,
        "m41_frozen_validation_not_started": not packet.frozen_validation_started,
        "m41_level4_not_ready": not packet.level4_ready,
        "m41_live_trading_disabled": not packet.live_trading_enabled,
        "m41_autonomous_live_disabled": not packet.autonomous_live_execution_enabled,
        "m41_leverage_disabled": not packet.leverage_enabled,
    }
    blockers = tuple(name for name, passed in checks.items() if not passed)
    return M41ReadinessPacketAudit(
        packet_path=str(path),
        parseable=True,
        milestone=str(payload.get("milestone")),
        readiness_go=readiness_go,
        aapl_protected_hold_verified=aapl_verified,
        msft_protected_hold_verified=msft_verified,
        no_unexpected_open_orders=no_unexpected_orders,
        no_unexpected_positions=no_unexpected_positions,
        reconciliation_clean=reconciliation_clean,
        supervised_run_m42_may_be_considered=m42_considered,
        schedules_not_activated=schedules_not_activated,
        frozen_validation_started=packet.frozen_validation_started,
        level4_ready=packet.level4_ready,
        blockers=blockers,
    )


def write_supervised_scheduled_paper_run_artifact(
    result: SupervisedScheduledPaperRunResult,
    output_path: str | Path,
) -> Path:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "milestone": "42",
        "result": {
            "success": result.success,
            "status": result.status,
            "refused": result.refused,
            "unsafe": result.unsafe,
            "blockers": result.blockers,
            "broker_writes_performed": result.broker_writes_performed,
            "real_read_only_calls_performed": result.real_read_only_calls_performed,
            "schedule_workflow_created_or_activated": (
                result.schedule_workflow_created_or_activated
            ),
            "schedule_workflow_remains_active": result.schedule_workflow_remains_active,
            "live_trading_enabled": result.live_trading_enabled,
            "autonomous_live_execution_enabled": result.autonomous_live_execution_enabled,
            "unattended_operation_enabled": result.unattended_operation_enabled,
            "leverage_enabled": result.leverage_enabled,
            "ai_broker_write_authority": result.ai_broker_write_authority,
            "frozen_validation_started": result.frozen_validation_started,
            "level4_ready": result.level4_ready,
            "freeze_readiness_recommendation": (
                result.packet.freeze_readiness_recommendation
            ),
        },
        "supervised_scheduled_paper_run": result.packet.model_dump(mode="json"),
    }
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return path


class _AdapterBundle(M42Model):
    adapter: Any
    client: Any
    credentials: AlpacaPaperCredentials | None


def _request_gate_blockers(
    request: SupervisedScheduledPaperRunRequest,
    app_config: AppConfig,
) -> tuple[str, ...]:
    blockers: list[str] = []
    if request.operator_approval_marker != MILESTONE_42_REAL_OPERATOR_APPROVAL:
        blockers.append("m42_operator_approval_marker_required")
    for field_name, reason in (
        ("confirm_paper_endpoint", "confirm_paper_endpoint_required"),
        (
            "confirm_temporary_supervised_schedule_only",
            "confirm_temporary_supervised_schedule_only_required",
        ),
        ("confirm_disable_after_one_run", "confirm_disable_after_one_run_required"),
        ("confirm_no_live_trading", "confirm_no_live_trading_required"),
        ("confirm_no_autonomous_live", "confirm_no_autonomous_live_required"),
        ("confirm_no_unattended_operation", "confirm_no_unattended_operation_required"),
        ("confirm_no_leverage", "confirm_no_leverage_required"),
        ("confirm_protective_stop_required", "confirm_protective_stop_required"),
        ("confirm_cleanup_policy", "confirm_cleanup_policy_required"),
    ):
        if not bool(getattr(request, field_name)):
            blockers.append(reason)
    if request.primary_target_symbol != "XLK":
        blockers.append("m42_primary_target_must_be_xlk")
    if request.fallback_target_symbol != "XLF":
        blockers.append("m42_fallback_target_must_be_xlf")
    if app_config.system.live_trading_enabled or app_config.execution.allow_live_orders:
        blockers.append("live_trading_enabled")
    if (
        app_config.system.autonomous_execution_enabled
        or app_config.execution.autonomous_execution_enabled
    ):
        blockers.append("autonomous_live_execution_enabled")
    if app_config.risk_level_4_micro_live.allow_margin:
        blockers.append("leverage_enabled")
    return _unique(tuple(blockers))


def _candidate_envelopes(
    request: SupervisedScheduledPaperRunRequest,
) -> tuple[M42CandidateEnvelope, M42CandidateEnvelope]:
    primary = M42CandidateEnvelope(
        target_symbol=request.primary_target_symbol,
        max_quantity=request.primary_max_quantity,
        max_notional_usd=request.primary_max_notional_usd,
        limit_price=request.primary_limit_price,
        estimated_notional_usd=round(
            request.primary_max_quantity * request.primary_limit_price,
            6,
        ),
    )
    fallback = M42CandidateEnvelope(
        target_symbol=request.fallback_target_symbol,
        max_quantity=request.fallback_max_quantity,
        max_notional_usd=request.fallback_max_notional_usd,
        limit_price=request.fallback_limit_price,
        estimated_notional_usd=round(
            request.fallback_max_quantity * request.fallback_limit_price,
            6,
        ),
    )
    return primary, fallback


def _candidate_envelope_static_blockers(
    envelope: M42CandidateEnvelope,
    app_config: AppConfig,
) -> tuple[str, ...]:
    blockers: list[str] = []
    symbol = envelope.target_symbol
    if symbol not in {"XLK", "XLF"}:
        blockers.append(f"{symbol.lower()}_not_operator_approved_for_m42")
    if symbol in {"AAPL", "MSFT"}:
        blockers.append(f"{symbol.lower()}_duplicate_existing_hold_forbidden")
    if symbol not in app_config.live_universe.symbols:
        blockers.append(f"{symbol.lower()}_target_symbol_not_approved")
    if symbol in ETF_SYMBOLS and not app_config.live_universe.allow_etfs:
        blockers.append(f"{symbol.lower()}_etfs_disabled")
    if envelope.max_quantity > app_config.execution.first_session_max_qty:
        blockers.append(f"{symbol.lower()}_max_qty_exceeds_configured_cap")
    if (
        envelope.max_notional_usd
        > app_config.execution.first_session_absolute_max_notional_usd
    ):
        blockers.append(f"{symbol.lower()}_max_notional_exceeds_configured_cap")
    if envelope.estimated_notional_usd > envelope.max_notional_usd:
        blockers.append(f"{symbol.lower()}_estimated_notional_exceeds_max_notional")
    return tuple(blockers)


def _adapter_bundle_for_request(
    request: SupervisedScheduledPaperRunRequest,
    app_config: AppConfig,
    *,
    environ: Mapping[str, str],
    client_factory: M42ClientFactory,
    gate_blockers: tuple[str, ...],
) -> tuple[_AdapterBundle | None, tuple[str, ...], bool]:
    if gate_blockers:
        return None, (), False
    if request.mode == "fake":
        fake_client = _fake_m42_client(request)
        adapter = AlpacaPaperAdapter(
            system_config=app_config.system,
            execution_config=app_config.execution,
            client=fake_client,
            credentials=None,
            run_mode="test",
        )
        return _AdapterBundle(adapter=adapter, client=fake_client, credentials=None), (), False
    try:
        credentials = validate_alpaca_paper_readonly_smoke_gates(
            environ=environ,
            app_config=app_config,
        )
        settings = AlpacaPaperOrderLifecycleSmokeSettings(
            symbol=request.primary_target_symbol,
            quantity=request.primary_max_quantity,
            max_notional_usd=request.primary_max_notional_usd,
            timeout_seconds=0.0,
        )
        real_client = client_factory(credentials, settings)
        adapter = AlpacaPaperAdapter(
            system_config=app_config.system,
            execution_config=app_config.execution,
            client=real_client,
            credentials=credentials,
            run_mode="runtime",
        )
    except Exception:
        return None, ("alpaca_m42_read_only_gates_or_credentials_unavailable",), False
    return _AdapterBundle(adapter=adapter, client=real_client, credentials=credentials), (), True


def _broker_state_summary(
    *,
    adapter: AlpacaPaperAdapter,
    client: AlpacaPaperOrderLifecycleClient | FakeAlpacaClient,
    expected_protected_symbols: tuple[str, ...],
    candidate_envelopes: tuple[M42CandidateEnvelope, ...],
    app_config: AppConfig,
    read_only_calls_performed: bool,
) -> M42BrokerStateSummary:
    try:
        adapter.account_snapshot()
        clock = map_alpaca_clock(client.get_clock())
        open_orders = adapter.open_orders()
        positions = adapter.positions()
    except AlpacaClientError:
        return _unreached_broker_state_summary(read_only_calls_performed=read_only_calls_performed)

    expected_stop_order_ids: set[str] = set()
    holdings = tuple(
        _protected_holding_verification(
            adapter=adapter,
            positions=positions,
            symbol=symbol,
            expected_stop_order_ids=expected_stop_order_ids,
        )
        for symbol in expected_protected_symbols
    )
    unexpected_open_orders = tuple(
        order for order in open_orders if order.broker_order_id not in expected_stop_order_ids
    )
    unexpected_positions = tuple(
        position
        for position in positions
        if abs(position.quantity) > 1e-9 and position.symbol not in expected_protected_symbols
    )
    candidate_states = tuple(
        _candidate_evaluation(
            envelope=envelope,
            open_orders=open_orders,
            positions=positions,
            app_config=app_config,
        )
        for envelope in candidate_envelopes
    )
    return M42BrokerStateSummary(
        account_reachable=True,
        clock_reachable=True,
        clock_is_open=clock.is_open,
        paper_endpoint_proven=True,
        protected_holds=holdings,
        open_orders_total=len(open_orders),
        expected_protective_stop_open_orders=len(expected_stop_order_ids),
        unexpected_open_orders_count=len(unexpected_open_orders),
        unexpected_open_order_symbols=tuple(
            sorted({order.symbol for order in unexpected_open_orders})
        ),
        positions_total=len(positions),
        unexpected_positions_count=len(unexpected_positions),
        unexpected_position_symbols=tuple(
            sorted({position.symbol for position in unexpected_positions})
        ),
        candidate_target_states=candidate_states,
        reconciliation_summary=_m42_reconciliation_summary(
            holdings=holdings,
            unexpected_open_orders=unexpected_open_orders,
            unexpected_positions=unexpected_positions,
        ),
        read_only_calls_performed=read_only_calls_performed,
    )


def _candidate_evaluation(
    *,
    envelope: M42CandidateEnvelope,
    open_orders: tuple[BrokerOrder, ...],
    positions: tuple[BrokerPosition, ...],
    app_config: AppConfig,
) -> M42CandidateEvaluation:
    symbol = envelope.target_symbol
    open_order_count = sum(1 for order in open_orders if order.symbol == symbol and order.is_open)
    quantity = sum(position.quantity for position in positions if position.symbol == symbol)
    static_blockers = _candidate_envelope_static_blockers(envelope, app_config)
    blockers = [
        *static_blockers,
        *(("target_symbol_open_order_present",) if open_order_count else ()),
        *(("target_symbol_position_present",) if abs(quantity) > 1e-9 else ()),
    ]
    clean = open_order_count == 0 and abs(quantity) <= 1e-9
    return M42CandidateEvaluation(
        target_symbol=symbol,
        envelope=envelope,
        allowed=symbol in app_config.live_universe.symbols,
        clean=clean,
        open_order_count=open_order_count,
        position_quantity=quantity,
        envelope_valid=not static_blockers,
        selected=False,
        blockers=_unique(tuple(blockers)),
    )


def _select_candidate(
    evaluations: tuple[M42CandidateEvaluation, ...],
) -> M42CandidateEvaluation | None:
    for evaluation in evaluations:
        if evaluation.envelope_valid and evaluation.clean and not evaluation.blockers:
            return evaluation.model_copy(update={"selected": True})
    return None


def _pre_schedule_state_blockers(summary: M42BrokerStateSummary) -> tuple[str, ...]:
    blockers: list[str] = []
    if not summary.account_reachable:
        blockers.append("broker_state_not_reached")
        return tuple(blockers)
    if summary.unexpected_open_orders_count:
        blockers.append("unexpected_open_orders_present")
    if summary.unexpected_positions_count:
        blockers.append("unexpected_positions_present")
    for holding in summary.protected_holds:
        blockers.extend(_holding_blockers(holding, expected_quantity=1.0))
    return _unique(tuple(blockers))


def _post_run_state_for_result(
    *,
    request: SupervisedScheduledPaperRunRequest,
    app_config: AppConfig,
    selected_candidate: M42CandidateEvaluation,
    execution_result: Any,
    adapter_bundle: _AdapterBundle | None,
    environ: Mapping[str, str],
    client_factory: M42ClientFactory,
    read_only_calls: bool,
) -> tuple[M42BrokerStateSummary | None, tuple[str, ...]]:
    filled = execution_result.result_packet.filled_quantity
    expected = ("AAPL", "MSFT", selected_candidate.target_symbol) if filled > 0 else (
        "AAPL",
        "MSFT",
    )
    if request.mode == "fake":
        assert adapter_bundle is not None
        summary = _broker_state_summary(
            adapter=adapter_bundle.adapter,
            client=adapter_bundle.client,
            expected_protected_symbols=expected,
            candidate_envelopes=(selected_candidate.envelope,),
            app_config=app_config,
            read_only_calls_performed=read_only_calls,
        )
    else:
        real_bundle, bundle_blockers, final_read_only = _adapter_bundle_for_request(
            request,
            app_config,
            environ=environ,
            client_factory=client_factory,
            gate_blockers=(),
        )
        if real_bundle is None:
            return None, bundle_blockers
        summary = _broker_state_summary(
            adapter=real_bundle.adapter,
            client=real_bundle.client,
            expected_protected_symbols=expected,
            candidate_envelopes=(selected_candidate.envelope,),
            app_config=app_config,
            read_only_calls_performed=final_read_only,
        )
    blockers = _post_run_state_blockers(summary, selected_candidate, filled_quantity=filled)
    return summary, blockers


def _post_run_state_blockers(
    summary: M42BrokerStateSummary,
    selected_candidate: M42CandidateEvaluation,
    *,
    filled_quantity: float,
) -> tuple[str, ...]:
    blockers: list[str] = []
    if not summary.account_reachable:
        blockers.append("post_run_broker_state_not_reached")
        return tuple(blockers)
    if summary.unexpected_open_orders_count:
        blockers.append("post_run_unexpected_open_orders_present")
    if summary.unexpected_positions_count:
        blockers.append("post_run_unexpected_positions_present")
    for holding in summary.protected_holds:
        expected = filled_quantity if holding.symbol == selected_candidate.target_symbol else 1.0
        blockers.extend(_holding_blockers(holding, expected_quantity=expected))
    if filled_quantity <= 1e-9 and summary.reconciliation_summary != "clean_protected_holds":
        blockers.append("post_run_reconciliation_not_clean_after_no_fill")
    if filled_quantity > 0 and summary.reconciliation_summary != "clean_protected_holds":
        blockers.append("post_run_reconciliation_not_clean_protected_holds")
    return _unique(tuple(blockers))


def _execute_selected_candidate(
    *,
    request: SupervisedScheduledPaperRunRequest,
    app_config: AppConfig,
    selected_candidate: M42CandidateEvaluation,
    environ: Mapping[str, str],
    client_factory: M42ClientFactory,
    adapter_bundle: _AdapterBundle | None,
) -> Any:
    execution_request = default_first_paper_session_execution_request(
        request.execution_scenario_id,
        mode="real-paper" if request.mode == "real-paper" else "fake-real-paper",
        operator_approval_marker=MILESTONE_42_REAL_OPERATOR_APPROVAL,
        target_symbol=selected_candidate.target_symbol,
        max_quantity=selected_candidate.envelope.max_quantity,
        max_notional_usd=selected_candidate.envelope.max_notional_usd,
        limit_price=selected_candidate.envelope.limit_price,
        confirm_paper_endpoint=True,
        confirm_real_paper_writes=True,
        confirm_no_live_trading=True,
        confirm_no_autonomous_live=True,
        confirm_no_schedules=True,
        confirm_no_leverage=True,
        confirm_first_session_only=True,
        confirm_protective_stop_required=True,
        confirm_cleanup_policy=True,
        m41_supervised_schedule_readiness_packet_path=request.m41_readiness_packet_path,
    ).model_copy(update={"started_at": request.started_at})
    if request.mode == "fake":
        assert adapter_bundle is not None
        fake_request = execution_request.model_copy(update={"mode": "real-paper"})
        return _run_adapter_execution(
            request=fake_request,
            app_config=app_config,
            adapter=adapter_bundle.adapter,
            client=adapter_bundle.client,
            real_broker=False,
            real_external_calls_performed=False,
            sleeper=lambda _seconds: None,
            clock=lambda: 0.0,
        )
    return run_first_controlled_paper_session_execution(
        execution_request,
        environ=environ,
        app_config=app_config,
        client_factory=client_factory,
    )


def _packet(
    *,
    request: SupervisedScheduledPaperRunRequest,
    timestamp: datetime,
    m41_audit: M41ReadinessPacketAudit,
    pre_state: M42BrokerStateSummary,
    selected_candidate: M42CandidateEvaluation | None,
    candidate_evaluations: tuple[M42CandidateEvaluation, ...],
    schedule_actions: tuple[M42ScheduleActionRecord, ...],
    execution_result: Any | None,
    post_state: M42BrokerStateSummary | None,
    blockers: tuple[str, ...],
    no_go_reason: str | None,
    freeze_recommendation: M42FreezeReadinessRecommendation,
) -> SupervisedScheduledPaperRunPacket:
    execution_packet = None if execution_result is None else execution_result.result_packet
    selected = None if selected_candidate is None else selected_candidate.target_symbol
    envelope = None if selected_candidate is None else selected_candidate.envelope
    return SupervisedScheduledPaperRunPacket(
        packet_id=str(
            uuid5(
                NAMESPACE_URL,
                f"m42-supervised-schedule:{request.mode}:{timestamp.isoformat()}:"
                f"{selected}:{no_go_reason}",
            )
        ),
        timestamp=timestamp,
        latest_spec_path=f"docs/app/{FIRST_SESSION_SPEC_VERSION}",
        spec_version=FIRST_SESSION_SPEC_VERSION,
        commit_hash=_git_commit_or_unavailable(),
        m41_readiness_packet_reference=request.m41_readiness_packet_path,
        m41_readiness_audit=m41_audit,
        current_broker_state_summary_before_schedule_run=pre_state,
        aapl_position_stop_status=_holding_by_symbol(pre_state, "AAPL"),
        msft_position_stop_status=_holding_by_symbol(pre_state, "MSFT"),
        schedule_workflow_creation_status=_action_status(schedule_actions, "create"),
        schedule_workflow_activation_status=_action_status(schedule_actions, "activate"),
        schedule_workflow_run_status=_action_status(schedule_actions, "run_once"),
        schedule_workflow_deactivation_status=_action_status(schedule_actions, "deactivate"),
        no_recurring_unattended_schedule_remains_active=True,
        selected_target_symbol=selected,
        no_go_reason=no_go_reason,
        candidate_evaluations=tuple(
            evaluation.model_copy(
                update={"selected": selected is not None and evaluation.target_symbol == selected}
            )
            for evaluation in candidate_evaluations
        ),
        order_envelope=envelope,
        candidate_decision_risk_evidence="deterministic_m42_candidate_envelope_and_risk_gates",
        execution_intent_id=(
            None if execution_packet is None else execution_packet.execution_intent_id
        ),
        entry_order_status=(
            None if execution_packet is None else execution_packet.entry_order_status
        ),
        fill_status="not_submitted" if execution_packet is None else execution_packet.fill_status,
        protective_stop_verification_result=(
            "not_reached"
            if execution_packet is None
            else execution_packet.protective_stop_verification_result
        ),
        normal_stop_path_succeeded=(
            False if execution_packet is None else execution_packet.normal_stop_path_succeeded
        ),
        recovery_stop_path_used=(
            False if execution_packet is None else execution_packet.recovery_stop_path_used
        ),
        cleanup_flatten_result=(
            "not_applicable_verify_only"
            if execution_packet is None or not execution_packet.cleanup_actions
            else ",".join(execution_packet.cleanup_actions)
        ),
        post_run_broker_state=post_state,
        final_reconciliation=(
            "not_reached" if post_state is None else post_state.reconciliation_summary
        ),
        incidents=() if execution_packet is None else execution_packet.incidents,
        actual_paper_trading_started=(
            False if execution_result is None else execution_result.actual_paper_trading_started
        ),
        broker_writes=(
            ()
            if execution_packet is None
            else tuple(
                record.model_dump(mode="json") for record in execution_packet.broker_writes
            )
        ),
        temporal_schedule_actions=schedule_actions,
        freeze_readiness_recommendation=freeze_recommendation,
        blockers=blockers,
    )


def _result_without_execution(
    *,
    request: SupervisedScheduledPaperRunRequest,
    timestamp: datetime,
    m41_audit: M41ReadinessPacketAudit,
    pre_state: M42BrokerStateSummary,
    candidate_evaluations: tuple[M42CandidateEvaluation, ...],
    blockers: tuple[str, ...],
    read_only_calls: bool,
    no_go_reason: str | None,
) -> SupervisedScheduledPaperRunResult:
    schedule_actions = _schedule_actions_for_refusal(no_go_reason)
    packet = _packet(
        request=request,
        timestamp=timestamp,
        m41_audit=m41_audit,
        pre_state=pre_state,
        selected_candidate=None,
        candidate_evaluations=candidate_evaluations,
        schedule_actions=schedule_actions,
        execution_result=None,
        post_state=pre_state if pre_state.account_reachable else None,
        blockers=blockers,
        no_go_reason=no_go_reason,
        freeze_recommendation=(
            "M43_FREEZE_READINESS_BLOCKED_PENDING_ACCEPTED_SUPERVISED_SCHEDULED_RUN"
        ),
    )
    return SupervisedScheduledPaperRunResult(
        mode=request.mode,
        status="refused",
        success=False,
        refused=True,
        unsafe=False,
        blockers=blockers,
        packet=packet,
        broker_writes_performed=False,
        real_read_only_calls_performed=read_only_calls,
        schedule_workflow_created_or_activated=False,
    )


def _schedule_actions_for_run(run_status: str) -> tuple[M42ScheduleActionRecord, ...]:
    return (
        M42ScheduleActionRecord(
            action="create",
            status="local_one_shot_workflow_prepared",
            detail=(
                "No Temporal Cloud schedule was created; local supervised one-shot "
                "equivalent only."
            ),
        ),
        M42ScheduleActionRecord(
            action="activate",
            status="activated_for_single_supervised_run",
            detail="Activation was bounded to one immediate supervised local run.",
        ),
        M42ScheduleActionRecord(
            action="run_once",
            status=run_status,
            detail="The supervised paper run was invoked exactly once.",
        ),
        M42ScheduleActionRecord(
            action="deactivate",
            status="deactivated_after_single_run",
            detail="No recurring unattended schedule remains active.",
        ),
    )


def _schedule_actions_for_refusal(no_go_reason: str | None) -> tuple[M42ScheduleActionRecord, ...]:
    reason = "no_go" if no_go_reason is None else no_go_reason
    return (
        M42ScheduleActionRecord(
            action="create",
            status="not_created_pre_schedule_gate_refused",
            detail=reason,
        ),
        M42ScheduleActionRecord(
            action="activate",
            status="not_activated_pre_schedule_gate_refused",
            detail=reason,
        ),
        M42ScheduleActionRecord(
            action="run_once",
            status="not_run_pre_schedule_gate_refused",
            detail=reason,
        ),
        M42ScheduleActionRecord(
            action="deactivate",
            status="not_needed_no_schedule_created",
            detail="No recurring unattended schedule exists.",
        ),
    )


def _fake_m42_client(request: SupervisedScheduledPaperRunRequest) -> FakeAlpacaClient:
    outcomes: tuple[tuple[str, float], ...] = (("filled", 1.0), ("accepted", 0.0))
    if request.execution_scenario_id == "no_fill":
        outcomes = (("accepted", 0.0),)
    orders = (
        _fake_stop_order_payload("AAPL", "m39-aapl-stop", "m39-aapl-stop-client", 1.0),
        _fake_stop_order_payload("MSFT", "m40-msft-stop", "m40-msft-stop-client", 1.0),
    )
    positions = (
        _fake_position_payload("AAPL", 1.0),
        _fake_position_payload("MSFT", 1.0),
    )
    return FakeAlpacaClient(
        orders=orders,
        positions=positions,
        submit_outcomes=outcomes,
        mutate_positions_on_submit=True,
    )


def _fake_position_payload(symbol: str, quantity: float) -> dict[str, Any]:
    price = 100.0
    return {
        "symbol": symbol,
        "asset_class": "etf" if symbol in ETF_SYMBOLS else "equity",
        "qty": str(quantity),
        "avg_entry_price": str(price),
        "market_value": str(quantity * price),
        "opened_at": DEFAULT_AS_OF.isoformat().replace("+00:00", "Z"),
    }


def _fake_stop_order_payload(
    symbol: str,
    broker_order_id: str,
    client_order_id: str,
    quantity: float,
) -> dict[str, Any]:
    return {
        "id": broker_order_id,
        "client_order_id": client_order_id,
        "symbol": symbol,
        "side": "sell",
        "asset_class": "etf" if symbol in ETF_SYMBOLS else "equity",
        "qty": str(quantity),
        "filled_qty": "0",
        "type": "stop",
        "time_in_force": "gtc",
        "status": "new",
        "stop_price": "1",
        "submitted_at": DEFAULT_AS_OF.isoformat().replace("+00:00", "Z"),
        "updated_at": DEFAULT_AS_OF.isoformat().replace("+00:00", "Z"),
    }


def _protected_holding_verification(
    *,
    adapter: AlpacaPaperAdapter,
    positions: tuple[BrokerPosition, ...],
    symbol: str,
    expected_stop_order_ids: set[str],
) -> ProtectedHoldingVerification:
    quantity = sum(position.quantity for position in positions if position.symbol == symbol)
    verification = adapter.verify_protective_stop(
        symbol=symbol,
        required_quantity=max(quantity, 0.0),
    )
    stop = verification.stop
    if verification.protected and stop is not None:
        expected_stop_order_ids.add(stop.broker_order_id)
    stop_quantity = None if stop is None else stop.quantity
    stop_matches = (
        stop is not None
        and quantity > 1e-9
        and abs(stop.quantity - max(quantity, 0.0)) <= 1e-9
    )
    return ProtectedHoldingVerification(
        symbol=symbol,
        position_status="open" if abs(quantity) > 1e-9 else "flat",
        position_quantity=quantity,
        protective_stop_status=(
            "open_verified" if verification.protected else "missing_or_unverified"
        ),
        protective_stop_quantity=stop_quantity,
        protective_stop_order_status=None if stop is None else stop.status,
        protective_stop_verified=verification.protected,
        protective_stop_matches_position_quantity=stop_matches,
    )


def _holding_blockers(
    holding: ProtectedHoldingVerification,
    *,
    expected_quantity: float,
) -> tuple[str, ...]:
    symbol = holding.symbol.lower()
    blockers: list[str] = []
    if holding.position_status != "open":
        blockers.append(f"{symbol}_position_not_open")
    if abs(holding.position_quantity - expected_quantity) > 1e-9:
        blockers.append(f"{symbol}_position_quantity_not_expected")
    if not holding.protective_stop_verified:
        blockers.append(f"{symbol}_protective_stop_missing_or_unverified")
    if holding.protective_stop_verified and not holding.protective_stop_matches_position_quantity:
        blockers.append(f"{symbol}_protective_stop_quantity_mismatch")
    return tuple(blockers)


def _m42_reconciliation_summary(
    *,
    holdings: tuple[ProtectedHoldingVerification, ...],
    unexpected_open_orders: tuple[BrokerOrder, ...],
    unexpected_positions: tuple[BrokerPosition, ...],
) -> str:
    if unexpected_open_orders or unexpected_positions:
        return "unexpected_broker_state_requires_manual_review"
    if all(_holding_open_and_verified(holding) for holding in holdings):
        return "clean_protected_holds"
    return "protected_hold_missing_or_unverified"


def _holding_open_and_verified(holding: ProtectedHoldingVerification) -> bool:
    return (
        holding.position_status == "open"
        and holding.position_quantity > 0
        and holding.protective_stop_verified
        and holding.protective_stop_matches_position_quantity
        and holding.protective_stop_quantity is not None
        and abs(holding.protective_stop_quantity - holding.position_quantity) <= 1e-9
    )


def _unreached_broker_state_summary(
    *,
    read_only_calls_performed: bool = False,
) -> M42BrokerStateSummary:
    return M42BrokerStateSummary(
        account_reachable=False,
        clock_reachable=False,
        clock_is_open=None,
        paper_endpoint_proven=False,
        protected_holds=(),
        open_orders_total=0,
        expected_protective_stop_open_orders=0,
        unexpected_open_orders_count=0,
        unexpected_open_order_symbols=(),
        positions_total=0,
        unexpected_positions_count=0,
        unexpected_position_symbols=(),
        candidate_target_states=(),
        reconciliation_summary="broker_state_not_reached",
        read_only_calls_performed=read_only_calls_performed,
    )


def _holding_by_symbol(
    summary: M42BrokerStateSummary,
    symbol: str,
) -> ProtectedHoldingVerification | None:
    for holding in summary.protected_holds:
        if holding.symbol == symbol:
            return holding
    return None


def _action_status(
    actions: tuple[M42ScheduleActionRecord, ...],
    action_name: str,
) -> str:
    for action in actions:
        if action.action == action_name:
            return action.status
    return "not_recorded"


def _first_or_none(values: tuple[str, ...]) -> str | None:
    return None if not values else values[0]


def _unique(values: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(values))


def _git_commit_or_unavailable() -> str:
    try:
        import subprocess

        completed = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError:
        return "unavailable"
    value = completed.stdout.strip()
    return value or "unavailable"
