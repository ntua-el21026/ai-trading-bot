"""Milestone 35D post-session audit for the first controlled paper session."""

from __future__ import annotations

import json
import subprocess
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal, Protocol
from uuid import NAMESPACE_URL, uuid5

from pydantic import BaseModel, ConfigDict, Field

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
    M34_RESULT_EVIDENCE_PATH,
    FirstPaperSessionResultPacket,
)
from packages.paper.first_session import FIRST_SESSION_SPEC_VERSION, SENSITIVE_ENV_NAMES

M35D_POST_SESSION_AUDIT_EVIDENCE_PATH = (
    "docs/evidence/first_controlled_paper_session_post_session_audit.json"
)
M35E_HOLD_DECISION_EVIDENCE_PATH = (
    "docs/evidence/first_controlled_paper_session_hold_decision.json"
)

PostSessionAuditMode = Literal["fake", "real-read-only"]
PostSessionAuditScenarioId = Literal[
    "protected_position",
    "missing_stop",
    "unexpected_order",
    "unexpected_position",
    "flat",
]
CleanupHoldRecommendation = Literal[
    "HOLD_PROTECTED_POSITION_UNTIL_NEXT_REVIEW",
    "REQUEST_OPERATOR_APPROVED_RISK_REDUCING_FLATTEN",
    "REQUEST_OPERATOR_APPROVED_STOP_REPAIR",
    "MANUAL_BROKER_REVIEW_REQUIRED",
    "NO_CLEANUP_REQUIRED",
]
OperatorHoldDecision = Literal["HOLD_PROTECTED_POSITION_UNTIL_NEXT_REVIEW"]
HoldDecisionRecommendation = Literal[
    "CONTINUE_HOLD_UNTIL_NEXT_REVIEW",
    "REQUEST_OPERATOR_APPROVED_STOP_REPAIR",
    "REQUEST_OPERATOR_APPROVED_RISK_REDUCING_FLATTEN",
    "MANUAL_BROKER_REVIEW_REQUIRED",
]


class PostSessionAuditClientFactory(Protocol):
    def __call__(
        self,
        credentials: AlpacaPaperCredentials,
        settings: AlpacaPaperOrderLifecycleSmokeSettings,
    ) -> AlpacaPaperOrderLifecycleClient:
        """Build a broker client. The audit uses only read-only methods."""


class M35DAuditModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class M35CResultPacketAudit(M35DAuditModel):
    packet_path: str
    parseable: bool
    milestone: str | None
    status: str | None
    actual_paper_trading_started: bool
    real_broker_orders_submitted: bool
    real_broker_writes_attempted: bool
    target_symbol: str | None
    entry_order_status: str | None
    fill_status: str | None
    filled_quantity: float
    fill_client_order_id_missing_incident_detected: bool
    recovery_stop_verified: bool
    no_cancel_replace_flatten_recorded: bool
    post_session_no_go: bool
    blockers: tuple[str, ...]


class M35DPostSessionAuditPacketAudit(M35DAuditModel):
    packet_path: str
    parseable: bool
    milestone: str | None
    audit_completed: bool
    recommendation: str | None
    repeated_session_go_no_go: str | None
    broker_writes_performed_in_m35d: bool
    protected_position_verified: bool
    blockers: tuple[str, ...]


class PostSessionBrokerStateSummary(M35DAuditModel):
    account_reachable: bool
    clock_reachable: bool
    clock_is_open: bool | None
    paper_endpoint_proven: bool
    live_endpoint_used: bool = False
    target_symbol: str
    target_position_quantity: float
    target_position_open: bool
    expected_filled_quantity: float
    entry_order_status: str | None
    protective_stop_order_status: str | None
    protective_stop_open: bool
    protective_stop_verified: bool
    protective_stop_quantity: float | None
    protective_stop_matches_position_quantity: bool
    open_orders_total: int = Field(ge=0)
    expected_protective_stop_open_orders: int = Field(ge=0)
    unexpected_open_orders_count: int = Field(ge=0)
    unexpected_open_order_symbols: tuple[str, ...]
    positions_total: int = Field(ge=0)
    unexpected_positions_count: int = Field(ge=0)
    unexpected_position_symbols: tuple[str, ...]
    reconciliation_summary: str
    read_only_calls_performed: bool
    broker_writes_attempted: bool = False


class PostSessionAuditPacket(M35DAuditModel):
    audit_packet_id: str
    timestamp: datetime
    latest_spec_path: str
    spec_version: str
    commit_hash: str
    m35c_result_packet_reference: str
    root_cause_summary: str
    incident_classification: str
    m35c_result_audit: M35CResultPacketAudit
    current_broker_state: PostSessionBrokerStateSummary
    code_hardening_summary: str
    tests_added_or_updated: tuple[str, ...]
    cleanup_hold_decision_recommendation: CleanupHoldRecommendation
    repeated_session_go_no_go: Literal["no_go"]
    frozen_validation_started: bool = False
    level4_ready: bool = False
    live_trading_enabled: bool = False
    autonomous_live_execution_enabled: bool = False
    leverage_enabled: bool = False
    schedules_activated: bool = False
    broker_writes_performed_in_this_milestone: bool = False
    real_read_only_calls_performed: bool
    provider_ai_telegram_vercel_temporal_calls: bool = False
    blockers: tuple[str, ...]
    secrets_redacted: dict[str, str] = Field(
        default_factory=lambda: {name: "<redacted-not-inspected>" for name in SENSITIVE_ENV_NAMES}
    )


class PostSessionAuditResult(M35DAuditModel):
    mode: PostSessionAuditMode
    scenario_id: PostSessionAuditScenarioId
    audit_completed: bool
    go_no_go: Literal["no_go"]
    blockers: tuple[str, ...]
    packet: PostSessionAuditPacket
    packet_path: str | None = None
    broker_writes_performed_in_this_milestone: bool = False
    real_read_only_calls_performed: bool
    schedules_activated: bool = False
    live_trading_enabled: bool = False
    autonomous_live_execution_enabled: bool = False
    leverage_enabled: bool = False
    ai_broker_write_authority: bool = False


class HoldDecisionPacket(M35DAuditModel):
    packet_id: str
    timestamp: datetime
    latest_spec_path: str
    spec_version: str
    commit_hash: str
    m35c_result_packet_reference: str
    m35d_post_session_audit_packet_reference: str
    operator_decision: OperatorHoldDecision
    m35c_result_audit: M35CResultPacketAudit
    m35d_post_session_audit: M35DPostSessionAuditPacketAudit
    current_broker_state: PostSessionBrokerStateSummary
    aapl_position_status: str
    aapl_protective_stop_status: str
    open_orders_summary: str
    positions_summary: str
    reconciliation_summary: str
    repeated_session_go_no_go: Literal["no_go"]
    cleanup_performed: bool = False
    flatten_performed: bool = False
    cancel_performed: bool = False
    broker_writes_performed_in_this_milestone: bool = False
    real_read_only_calls_performed: bool
    frozen_validation_started: bool = False
    level4_ready: bool = False
    live_trading_enabled: bool = False
    autonomous_live_execution_enabled: bool = False
    leverage_enabled: bool = False
    schedules_activated: bool = False
    provider_ai_telegram_vercel_temporal_calls: bool = False
    hold_confirmed: bool
    cleanup_hold_recommendation: HoldDecisionRecommendation
    blockers: tuple[str, ...]
    secrets_redacted: dict[str, str] = Field(
        default_factory=lambda: {name: "<redacted-not-inspected>" for name in SENSITIVE_ENV_NAMES}
    )


class HoldDecisionResult(M35DAuditModel):
    mode: PostSessionAuditMode
    scenario_id: PostSessionAuditScenarioId
    operator_decision: OperatorHoldDecision
    hold_confirmed: bool
    go_no_go: Literal["no_go"]
    blockers: tuple[str, ...]
    packet: HoldDecisionPacket
    packet_path: str | None = None
    broker_writes_performed_in_this_milestone: bool = False
    real_read_only_calls_performed: bool
    schedules_activated: bool = False
    live_trading_enabled: bool = False
    autonomous_live_execution_enabled: bool = False
    leverage_enabled: bool = False
    ai_broker_write_authority: bool = False


class PostSessionAuditRequest(M35DAuditModel):
    mode: PostSessionAuditMode = "fake"
    scenario_id: PostSessionAuditScenarioId = "protected_position"
    result_packet_path: str = M34_RESULT_EVIDENCE_PATH
    target_symbol: str = "AAPL"
    confirm_paper_endpoint: bool = False
    confirm_no_broker_writes: bool = False
    confirm_no_live_trading: bool = False
    confirm_no_autonomous_live: bool = False
    confirm_no_schedules: bool = False
    confirm_no_leverage: bool = False


def run_first_controlled_paper_session_hold_decision(
    request: PostSessionAuditRequest | None = None,
    *,
    operator_decision: OperatorHoldDecision = "HOLD_PROTECTED_POSITION_UNTIL_NEXT_REVIEW",
    post_session_audit_packet_path: str = M35D_POST_SESSION_AUDIT_EVIDENCE_PATH,
    environ: Mapping[str, str] | None = None,
    app_config: AppConfig | None = None,
    client_factory: PostSessionAuditClientFactory = (
        build_alpaca_paper_order_lifecycle_http_client
    ),
    now: datetime | None = None,
) -> HoldDecisionResult:
    active_request = request or PostSessionAuditRequest()
    decision_time = now or datetime.now(UTC)
    audit_result = run_first_controlled_paper_session_post_session_audit(
        active_request,
        environ=environ,
        app_config=app_config,
        client_factory=client_factory,
        now=decision_time,
    )
    m35d_audit = audit_m35d_post_session_audit_packet(post_session_audit_packet_path)
    broker_state = audit_result.packet.current_broker_state
    hold_confirmed = _hold_confirmed(broker_state, m35d_audit)
    recommendation = _hold_decision_recommendation(broker_state)
    blockers = _unique(
        (
            *audit_result.blockers,
            *audit_result.packet.m35c_result_audit.blockers,
            *m35d_audit.blockers,
            *_hold_state_blockers(broker_state),
            "repeated_sessions_blocked_until_later_audit_decision",
        )
    )
    packet = HoldDecisionPacket(
        packet_id=str(
            uuid5(
                NAMESPACE_URL,
                f"m35e-hold-decision:{active_request.mode}:"
                f"{active_request.scenario_id}:{decision_time.isoformat()}",
            )
        ),
        timestamp=decision_time,
        latest_spec_path=f"docs/app/{FIRST_SESSION_SPEC_VERSION}",
        spec_version=FIRST_SESSION_SPEC_VERSION,
        commit_hash=_git_commit_or_unavailable(),
        m35c_result_packet_reference=active_request.result_packet_path,
        m35d_post_session_audit_packet_reference=post_session_audit_packet_path,
        operator_decision=operator_decision,
        m35c_result_audit=audit_result.packet.m35c_result_audit,
        m35d_post_session_audit=m35d_audit,
        current_broker_state=broker_state,
        aapl_position_status=_position_status(broker_state),
        aapl_protective_stop_status=_protective_stop_status(broker_state),
        open_orders_summary=_open_orders_summary(broker_state),
        positions_summary=_positions_summary(broker_state),
        reconciliation_summary=broker_state.reconciliation_summary,
        repeated_session_go_no_go="no_go",
        real_read_only_calls_performed=audit_result.real_read_only_calls_performed,
        hold_confirmed=hold_confirmed,
        cleanup_hold_recommendation=recommendation,
        blockers=blockers,
    )
    return HoldDecisionResult(
        mode=active_request.mode,
        scenario_id=active_request.scenario_id,
        operator_decision=operator_decision,
        hold_confirmed=hold_confirmed,
        go_no_go="no_go",
        blockers=blockers,
        packet=packet,
        real_read_only_calls_performed=audit_result.real_read_only_calls_performed,
    )


def run_first_controlled_paper_session_post_session_audit(
    request: PostSessionAuditRequest | None = None,
    *,
    environ: Mapping[str, str] | None = None,
    app_config: AppConfig | None = None,
    client_factory: PostSessionAuditClientFactory = (
        build_alpaca_paper_order_lifecycle_http_client
    ),
    now: datetime | None = None,
) -> PostSessionAuditResult:
    active_request = request or PostSessionAuditRequest()
    active_config = app_config or load_app_config()
    audit_time = now or datetime.now(UTC)
    result_audit, result_packet = audit_m35c_result_packet(active_request.result_packet_path)
    gate_blockers = _request_gate_blockers(active_request)
    broker_summary, broker_blockers, read_only_calls = _broker_summary_for_request(
        active_request,
        result_packet=result_packet,
        app_config=active_config,
        environ={} if environ is None else environ,
        client_factory=client_factory,
        gate_blockers=gate_blockers,
    )
    recommendation = _cleanup_recommendation(broker_summary)
    blockers = _unique(
        (
            *result_audit.blockers,
            *gate_blockers,
            *broker_blockers,
            "repeated_sessions_blocked_pending_post_session_audit_acceptance",
        )
    )
    packet = PostSessionAuditPacket(
        audit_packet_id=str(
            uuid5(
                NAMESPACE_URL,
                f"m35d-post-session-audit:{active_request.mode}:"
                f"{active_request.scenario_id}:{audit_time.isoformat()}",
            )
        ),
        timestamp=audit_time,
        latest_spec_path=f"docs/app/{FIRST_SESSION_SPEC_VERSION}",
        spec_version=FIRST_SESSION_SPEC_VERSION,
        commit_hash=_git_commit_or_unavailable(),
        m35c_result_packet_reference=active_request.result_packet_path,
        root_cause_summary=(
            "Alpaca account activity fill payload omitted client_order_id; the first-session "
            "fill lookup assumed that field before normal protective-stop submission."
        ),
        incident_classification="safe_incident_recovered_with_verified_protective_stop",
        m35c_result_audit=result_audit,
        current_broker_state=broker_summary,
        code_hardening_summary=(
            "Fill mapping falls back to order_id when client_order_id is absent, and fill-id "
            "lookup now records malformed fill metadata as a structured incident while "
            "continuing to the protective-stop path from the known entry order context."
        ),
        tests_added_or_updated=(
            "tests/unit/test_alpaca_mapping.py",
            "tests/unit/test_first_controlled_paper_session_execution.py",
            "tests/unit/test_first_controlled_paper_session_post_audit.py",
        ),
        cleanup_hold_decision_recommendation=recommendation,
        repeated_session_go_no_go="no_go",
        real_read_only_calls_performed=read_only_calls,
        blockers=blockers,
    )
    return PostSessionAuditResult(
        mode=active_request.mode,
        scenario_id=active_request.scenario_id,
        audit_completed=not gate_blockers and broker_summary.account_reachable,
        go_no_go="no_go",
        blockers=blockers,
        packet=packet,
        real_read_only_calls_performed=read_only_calls,
    )


def audit_m35c_result_packet(
    result_packet_path: str | Path,
) -> tuple[M35CResultPacketAudit, FirstPaperSessionResultPacket | None]:
    path = Path(result_packet_path)
    blockers: list[str] = []
    if not path.is_file():
        return (
            M35CResultPacketAudit(
                packet_path=str(path),
                parseable=False,
                milestone=None,
                status=None,
                actual_paper_trading_started=False,
                real_broker_orders_submitted=False,
                real_broker_writes_attempted=False,
                target_symbol=None,
                entry_order_status=None,
                fill_status=None,
                filled_quantity=0.0,
                fill_client_order_id_missing_incident_detected=False,
                recovery_stop_verified=False,
                no_cancel_replace_flatten_recorded=False,
                post_session_no_go=False,
                blockers=("m35c_result_packet_missing",),
            ),
            None,
        )
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        packet = FirstPaperSessionResultPacket.model_validate(payload["session_result"])
    except (OSError, KeyError, TypeError, ValueError):
        return (
            M35CResultPacketAudit(
                packet_path=str(path),
                parseable=False,
                milestone=None,
                status=None,
                actual_paper_trading_started=False,
                real_broker_orders_submitted=False,
                real_broker_writes_attempted=False,
                target_symbol=None,
                entry_order_status=None,
                fill_status=None,
                filled_quantity=0.0,
                fill_client_order_id_missing_incident_detected=False,
                recovery_stop_verified=False,
                no_cancel_replace_flatten_recorded=False,
                post_session_no_go=False,
                blockers=("m35c_result_packet_unparseable",),
            ),
            None,
        )
    result = payload.get("result", {})
    incidents = set(packet.incidents)
    broker_write_operations = {write.operation for write in packet.broker_writes}
    no_cancel_replace_flatten = not (
        {"cancel_unfilled_entry", "cancel_unfilled_remainder", "replace_order", "flatten_position"}
        & broker_write_operations
    )
    fill_missing_incident = (
        "execution_crashed_before_protective_stop_submission_fill_payload_missing_client_order_id"
        in incidents
    )
    recovery_stop_verified = (
        "safety_stop_submitted_and_verified_after_incident" in incidents
        and packet.protective_stop_verification_result == "verified"
    )
    checks = {
        "m35c_result_milestone_is_35c": payload.get("milestone") == "35C",
        "m35c_result_status_is_incident": result.get("status") == "incident",
        "m35c_actual_paper_trading_started": result.get("actual_paper_trading_started") is True,
        "m35c_real_broker_orders_submitted": result.get("real_broker_orders_submitted") is True,
        "m35c_real_broker_writes_attempted": result.get("real_broker_writes_attempted") is True,
        "m35c_target_symbol_aapl": packet.target_symbol == "AAPL",
        "m35c_entry_filled": packet.entry_order_status == "filled",
        "m35c_fill_status_filled": packet.fill_status == "filled",
        "m35c_filled_quantity_one": abs(packet.filled_quantity - 1.0) <= 1e-9,
        "m35c_fill_missing_client_order_id_incident_present": fill_missing_incident,
        "m35c_recovery_stop_verified": recovery_stop_verified,
        "m35c_no_cancel_replace_flatten_recorded": no_cancel_replace_flatten,
        "m35c_post_session_no_go": result.get("post_session_go_no_go") == "no_go",
    }
    blockers.extend(name for name, passed in checks.items() if not passed)
    return (
        M35CResultPacketAudit(
            packet_path=str(path),
            parseable=True,
            milestone=str(payload.get("milestone")),
            status=None if result.get("status") is None else str(result.get("status")),
            actual_paper_trading_started=bool(result.get("actual_paper_trading_started")),
            real_broker_orders_submitted=bool(result.get("real_broker_orders_submitted")),
            real_broker_writes_attempted=bool(result.get("real_broker_writes_attempted")),
            target_symbol=packet.target_symbol,
            entry_order_status=packet.entry_order_status,
            fill_status=packet.fill_status,
            filled_quantity=packet.filled_quantity,
            fill_client_order_id_missing_incident_detected=fill_missing_incident,
            recovery_stop_verified=recovery_stop_verified,
            no_cancel_replace_flatten_recorded=no_cancel_replace_flatten,
            post_session_no_go=result.get("post_session_go_no_go") == "no_go",
            blockers=tuple(blockers),
        ),
        packet,
    )


def audit_m35d_post_session_audit_packet(
    audit_packet_path: str | Path,
) -> M35DPostSessionAuditPacketAudit:
    path = Path(audit_packet_path)
    if not path.is_file():
        return M35DPostSessionAuditPacketAudit(
            packet_path=str(path),
            parseable=False,
            milestone=None,
            audit_completed=False,
            recommendation=None,
            repeated_session_go_no_go=None,
            broker_writes_performed_in_m35d=False,
            protected_position_verified=False,
            blockers=("m35d_post_session_audit_packet_missing",),
        )
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        packet = PostSessionAuditPacket.model_validate(payload["post_session_audit"])
    except (OSError, KeyError, TypeError, ValueError):
        return M35DPostSessionAuditPacketAudit(
            packet_path=str(path),
            parseable=False,
            milestone=None,
            audit_completed=False,
            recommendation=None,
            repeated_session_go_no_go=None,
            broker_writes_performed_in_m35d=False,
            protected_position_verified=False,
            blockers=("m35d_post_session_audit_packet_unparseable",),
        )
    result = payload.get("result", {})
    broker_state = packet.current_broker_state
    protected_verified = (
        broker_state.target_symbol == "AAPL"
        and broker_state.target_position_open
        and broker_state.protective_stop_verified
        and broker_state.protective_stop_matches_position_quantity
        and broker_state.unexpected_open_orders_count == 0
        and broker_state.unexpected_positions_count == 0
    )
    checks = {
        "m35d_audit_milestone_is_35d": payload.get("milestone") == "35D",
        "m35d_audit_completed": result.get("audit_completed") is True,
        "m35d_recommendation_is_hold": (
            packet.cleanup_hold_decision_recommendation
            == "HOLD_PROTECTED_POSITION_UNTIL_NEXT_REVIEW"
        ),
        "m35d_repeated_sessions_no_go": packet.repeated_session_go_no_go == "no_go",
        "m35d_broker_writes_false": (
            result.get("broker_writes_performed_in_this_milestone") is False
        ),
        "m35d_protected_position_verified": protected_verified,
    }
    blockers = tuple(name for name, passed in checks.items() if not passed)
    return M35DPostSessionAuditPacketAudit(
        packet_path=str(path),
        parseable=True,
        milestone=str(payload.get("milestone")),
        audit_completed=bool(result.get("audit_completed")),
        recommendation=packet.cleanup_hold_decision_recommendation,
        repeated_session_go_no_go=packet.repeated_session_go_no_go,
        broker_writes_performed_in_m35d=bool(
            result.get("broker_writes_performed_in_this_milestone")
        ),
        protected_position_verified=protected_verified,
        blockers=blockers,
    )


def write_post_session_audit_artifact(
    result: PostSessionAuditResult,
    output_path: str | Path,
) -> Path:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "milestone": "35D",
        "result": {
            "audit_completed": result.audit_completed,
            "go_no_go": result.go_no_go,
            "blockers": result.blockers,
            "broker_writes_performed_in_this_milestone": (
                result.broker_writes_performed_in_this_milestone
            ),
            "real_read_only_calls_performed": result.real_read_only_calls_performed,
            "schedules_activated": result.schedules_activated,
            "live_trading_enabled": result.live_trading_enabled,
            "autonomous_live_execution_enabled": result.autonomous_live_execution_enabled,
            "leverage_enabled": result.leverage_enabled,
            "ai_broker_write_authority": result.ai_broker_write_authority,
        },
        "post_session_audit": result.packet.model_dump(mode="json"),
    }
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return path


def write_hold_decision_artifact(
    result: HoldDecisionResult,
    output_path: str | Path,
) -> Path:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "milestone": "35E",
        "result": {
            "operator_decision": result.operator_decision,
            "hold_confirmed": result.hold_confirmed,
            "go_no_go": result.go_no_go,
            "blockers": result.blockers,
            "cleanup_performed": result.packet.cleanup_performed,
            "flatten_performed": result.packet.flatten_performed,
            "cancel_performed": result.packet.cancel_performed,
            "broker_writes_performed_in_this_milestone": (
                result.broker_writes_performed_in_this_milestone
            ),
            "real_read_only_calls_performed": result.real_read_only_calls_performed,
            "schedules_activated": result.schedules_activated,
            "live_trading_enabled": result.live_trading_enabled,
            "autonomous_live_execution_enabled": result.autonomous_live_execution_enabled,
            "leverage_enabled": result.leverage_enabled,
            "ai_broker_write_authority": result.ai_broker_write_authority,
        },
        "hold_decision": result.packet.model_dump(mode="json"),
    }
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return path


def _request_gate_blockers(request: PostSessionAuditRequest) -> tuple[str, ...]:
    if request.mode == "fake":
        return ()
    blockers: list[str] = []
    for field_name, reason in (
        ("confirm_paper_endpoint", "confirm_paper_endpoint_required"),
        ("confirm_no_broker_writes", "confirm_no_broker_writes_required"),
        ("confirm_no_live_trading", "confirm_no_live_trading_required"),
        ("confirm_no_autonomous_live", "confirm_no_autonomous_live_required"),
        ("confirm_no_schedules", "confirm_no_schedules_required"),
        ("confirm_no_leverage", "confirm_no_leverage_required"),
    ):
        if not bool(getattr(request, field_name)):
            blockers.append(reason)
    return tuple(blockers)


def _broker_summary_for_request(
    request: PostSessionAuditRequest,
    *,
    result_packet: FirstPaperSessionResultPacket | None,
    app_config: AppConfig,
    environ: Mapping[str, str],
    client_factory: PostSessionAuditClientFactory,
    gate_blockers: tuple[str, ...],
) -> tuple[PostSessionBrokerStateSummary, tuple[str, ...], bool]:
    if gate_blockers:
        return _unreached_broker_summary(request.target_symbol), (), False
    if request.mode == "fake":
        client = _fake_client_for_post_audit(request, result_packet)
        adapter = AlpacaPaperAdapter(
            system_config=app_config.system,
            execution_config=app_config.execution,
            client=client,
            credentials=None,
            run_mode="test",
        )
        return _broker_state_summary(
            request=request,
            result_packet=result_packet,
            adapter=adapter,
            client=client,
            read_only_calls_performed=False,
        )
    try:
        credentials = validate_alpaca_paper_readonly_smoke_gates(
            environ=environ,
            app_config=app_config,
        )
        settings = AlpacaPaperOrderLifecycleSmokeSettings(
            symbol=request.target_symbol,
            quantity=1,
            max_notional_usd=350.0,
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
        return (
            _unreached_broker_summary(request.target_symbol),
            ("alpaca_read_only_audit_gates_or_credentials_unavailable",),
            False,
        )
    return _broker_state_summary(
        request=request,
        result_packet=result_packet,
        adapter=adapter,
        client=real_client,
        read_only_calls_performed=True,
    )


def _broker_state_summary(
    *,
    request: PostSessionAuditRequest,
    result_packet: FirstPaperSessionResultPacket | None,
    adapter: AlpacaPaperAdapter,
    client: AlpacaPaperOrderLifecycleClient | FakeAlpacaClient,
    read_only_calls_performed: bool,
) -> tuple[PostSessionBrokerStateSummary, tuple[str, ...], bool]:
    target = request.target_symbol
    expected_qty = 0.0 if result_packet is None else result_packet.filled_quantity
    expected_stop_order_id = (
        None if result_packet is None else result_packet.protective_stop_order_id
    )
    expected_entry_order_id = None if result_packet is None else result_packet.broker_order_id
    expected_stop_client_order_id = _expected_stop_client_order_id(result_packet)
    try:
        adapter.account_snapshot()
        clock = map_alpaca_clock(client.get_clock())
        open_orders = adapter.open_orders()
        positions = adapter.positions()
        entry_order = (
            None
            if expected_entry_order_id is None
            else adapter.order_by_broker_order_id(expected_entry_order_id)
        )
        stop_order = (
            None
            if expected_stop_order_id is None
            else adapter.order_by_broker_order_id(expected_stop_order_id)
        )
        verification = adapter.verify_protective_stop(
            symbol=target,
            required_quantity=max(expected_qty, 0.0),
            client_order_id=expected_stop_client_order_id,
        )
    except AlpacaClientError as exc:
        return (
            _unreached_broker_summary(target),
            (f"alpaca_read_only_post_audit_failed:{exc.code}",),
            read_only_calls_performed,
        )
    except Exception as exc:
        return (
            _unreached_broker_summary(target),
            (f"alpaca_read_only_post_audit_failed:{type(exc).__name__}",),
            read_only_calls_performed,
        )
    target_positions = tuple(position for position in positions if position.symbol == target)
    target_quantity = sum(position.quantity for position in target_positions)
    expected_stop_orders = tuple(
        order
        for order in open_orders
        if order.broker_order_id == expected_stop_order_id
        and order.symbol == target
        and order.order_type in {"stop", "stop_limit"}
    )
    unexpected_open_orders = _unexpected_open_orders(
        open_orders=open_orders,
        target=target,
        expected_stop_order_id=expected_stop_order_id,
    )
    unexpected_positions = _unexpected_positions(
        positions=positions,
        target=target,
        expected_quantity=expected_qty,
    )
    verified_stop = verification.stop
    protective_stop_quantity = None if verified_stop is None else verified_stop.quantity
    stop_matches_quantity = (
        verified_stop is not None
        and abs(verified_stop.quantity - max(target_quantity, 0.0)) <= 1e-9
    )
    stop_order_status = None
    if verified_stop is not None:
        stop_order_status = verified_stop.status
    elif stop_order is not None:
        stop_order_status = stop_order.status
    blockers: list[str] = []
    if target_quantity > 1e-9 and not verification.protected:
        blockers.append("protective_stop_missing_or_unverified")
    if target_quantity > 1e-9 and verification.protected and not stop_matches_quantity:
        blockers.append("protective_stop_quantity_mismatch")
    if unexpected_open_orders:
        blockers.append("unexpected_open_orders_present")
    if unexpected_positions:
        blockers.append("unexpected_positions_present")
    reconciliation = _reconciliation_summary(
        target_quantity=target_quantity,
        expected_quantity=expected_qty,
        protective_stop_verified=verification.protected,
        unexpected_open_orders=unexpected_open_orders,
        unexpected_positions=unexpected_positions,
    )
    return (
        PostSessionBrokerStateSummary(
            account_reachable=True,
            clock_reachable=True,
            clock_is_open=clock.is_open,
            paper_endpoint_proven=True,
            target_symbol=target,
            target_position_quantity=target_quantity,
            target_position_open=abs(target_quantity) > 1e-9,
            expected_filled_quantity=expected_qty,
            entry_order_status=None if entry_order is None else entry_order.status,
            protective_stop_order_status=stop_order_status,
            protective_stop_open=verification.protected,
            protective_stop_verified=verification.protected,
            protective_stop_quantity=protective_stop_quantity,
            protective_stop_matches_position_quantity=stop_matches_quantity,
            open_orders_total=len(open_orders),
            expected_protective_stop_open_orders=len(expected_stop_orders),
            unexpected_open_orders_count=len(unexpected_open_orders),
            unexpected_open_order_symbols=tuple(
                sorted({order.symbol for order in unexpected_open_orders})
            ),
            positions_total=len(positions),
            unexpected_positions_count=len(unexpected_positions),
            unexpected_position_symbols=tuple(
                sorted({position.symbol for position in unexpected_positions})
            ),
            reconciliation_summary=reconciliation,
            read_only_calls_performed=read_only_calls_performed,
        ),
        tuple(blockers),
        read_only_calls_performed,
    )


def _unreached_broker_summary(target: str) -> PostSessionBrokerStateSummary:
    return PostSessionBrokerStateSummary(
        account_reachable=False,
        clock_reachable=False,
        clock_is_open=None,
        paper_endpoint_proven=False,
        target_symbol=target,
        target_position_quantity=0.0,
        target_position_open=False,
        expected_filled_quantity=0.0,
        entry_order_status=None,
        protective_stop_order_status=None,
        protective_stop_open=False,
        protective_stop_verified=False,
        protective_stop_quantity=None,
        protective_stop_matches_position_quantity=False,
        open_orders_total=0,
        expected_protective_stop_open_orders=0,
        unexpected_open_orders_count=0,
        unexpected_open_order_symbols=(),
        positions_total=0,
        unexpected_positions_count=0,
        unexpected_position_symbols=(),
        reconciliation_summary="broker_state_not_reached",
        read_only_calls_performed=False,
    )


def _fake_client_for_post_audit(
    request: PostSessionAuditRequest,
    result_packet: FirstPaperSessionResultPacket | None,
) -> FakeAlpacaClient:
    target = request.target_symbol
    qty = 1.0 if result_packet is None else result_packet.filled_quantity
    entry_id = "fake-entry-order" if result_packet is None else result_packet.broker_order_id
    entry_client_order_id = (
        "fake-entry-client-order"
        if result_packet is None
        else result_packet.client_order_id
    )
    stop_id = (
        "fake-stop-order"
        if result_packet is None or result_packet.protective_stop_order_id is None
        else result_packet.protective_stop_order_id
    )
    stop_client_order_id = _expected_stop_client_order_id(result_packet) or "fake-stop-client-order"
    orders: list[dict[str, Any]] = []
    positions: list[dict[str, Any]] = []
    if request.scenario_id != "flat":
        positions.append(_fake_position_payload(target, qty))
    if entry_id and entry_client_order_id:
        orders.append(_fake_entry_order_payload(target, entry_id, entry_client_order_id, qty))
    if request.scenario_id not in {"missing_stop", "flat"}:
        orders.append(_fake_stop_order_payload(target, stop_id, stop_client_order_id, qty))
    if request.scenario_id == "unexpected_order":
        orders.append(
            _fake_stop_order_payload(
                "MSFT",
                "unexpected-stop",
                "unexpected-stop-client",
                1.0,
            )
        )
    if request.scenario_id == "unexpected_position":
        positions.append(_fake_position_payload("MSFT", 1.0))
    return FakeAlpacaClient(orders=tuple(orders), positions=tuple(positions))


def _fake_entry_order_payload(
    symbol: str,
    broker_order_id: str,
    client_order_id: str,
    quantity: float,
) -> dict[str, Any]:
    return {
        "id": broker_order_id,
        "client_order_id": client_order_id,
        "symbol": symbol,
        "side": "buy",
        "asset_class": "equity",
        "qty": str(quantity),
        "filled_qty": str(quantity),
        "type": "limit",
        "time_in_force": "day",
        "status": "filled",
        "limit_price": "330",
        "submitted_at": DEFAULT_AS_OF.isoformat().replace("+00:00", "Z"),
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
        "asset_class": "equity",
        "qty": str(quantity),
        "filled_qty": "0",
        "type": "stop",
        "time_in_force": "gtc",
        "status": "new",
        "stop_price": "165",
        "submitted_at": DEFAULT_AS_OF.isoformat().replace("+00:00", "Z"),
    }


def _fake_position_payload(symbol: str, quantity: float) -> dict[str, Any]:
    return {
        "symbol": symbol,
        "asset_class": "equity",
        "qty": str(quantity),
        "avg_entry_price": "290.94",
        "market_value": str(quantity * 290.94),
        "opened_at": DEFAULT_AS_OF.isoformat().replace("+00:00", "Z"),
    }


def _expected_stop_client_order_id(
    result_packet: FirstPaperSessionResultPacket | None,
) -> str | None:
    if result_packet is None:
        return None
    for write in result_packet.broker_writes:
        if write.operation == "submit_protective_stop":
            return write.client_order_id
    return None


def _unexpected_open_orders(
    *,
    open_orders: tuple[BrokerOrder, ...],
    target: str,
    expected_stop_order_id: str | None,
) -> tuple[BrokerOrder, ...]:
    return tuple(
        order
        for order in open_orders
        if not (
            order.symbol == target
            and order.broker_order_id == expected_stop_order_id
            and order.order_type in {"stop", "stop_limit"}
        )
    )


def _unexpected_positions(
    *,
    positions: tuple[BrokerPosition, ...],
    target: str,
    expected_quantity: float,
) -> tuple[BrokerPosition, ...]:
    unexpected: list[BrokerPosition] = []
    for position in positions:
        if abs(position.quantity) <= 1e-9:
            continue
        if position.symbol != target:
            unexpected.append(position)
        elif expected_quantity > 0 and abs(position.quantity - expected_quantity) > 1e-9:
            unexpected.append(position)
    return tuple(unexpected)


def _reconciliation_summary(
    *,
    target_quantity: float,
    expected_quantity: float,
    protective_stop_verified: bool,
    unexpected_open_orders: tuple[BrokerOrder, ...],
    unexpected_positions: tuple[BrokerPosition, ...],
) -> str:
    if unexpected_open_orders or unexpected_positions:
        return "unexpected_broker_state_requires_manual_review"
    if target_quantity > 1e-9 and protective_stop_verified:
        if abs(target_quantity - expected_quantity) <= 1e-9:
            return "protected_position_reconciled_for_hold"
        return "protected_position_quantity_differs_from_evidence"
    if target_quantity > 1e-9:
        return "position_open_without_verified_stop"
    return "flat_no_open_position"


def _cleanup_recommendation(
    broker_summary: PostSessionBrokerStateSummary,
) -> CleanupHoldRecommendation:
    if broker_summary.unexpected_open_orders_count or broker_summary.unexpected_positions_count:
        return "MANUAL_BROKER_REVIEW_REQUIRED"
    if broker_summary.target_position_open and broker_summary.protective_stop_verified:
        return "HOLD_PROTECTED_POSITION_UNTIL_NEXT_REVIEW"
    if broker_summary.target_position_open:
        return "REQUEST_OPERATOR_APPROVED_STOP_REPAIR"
    return "NO_CLEANUP_REQUIRED"


def _hold_confirmed(
    broker_summary: PostSessionBrokerStateSummary,
    m35d_audit: M35DPostSessionAuditPacketAudit,
) -> bool:
    return (
        m35d_audit.parseable
        and m35d_audit.audit_completed
        and m35d_audit.recommendation == "HOLD_PROTECTED_POSITION_UNTIL_NEXT_REVIEW"
        and m35d_audit.repeated_session_go_no_go == "no_go"
        and not m35d_audit.broker_writes_performed_in_m35d
        and broker_summary.target_symbol == "AAPL"
        and broker_summary.target_position_open
        and broker_summary.protective_stop_verified
        and broker_summary.protective_stop_matches_position_quantity
        and broker_summary.unexpected_open_orders_count == 0
        and broker_summary.unexpected_positions_count == 0
    )


def _hold_state_blockers(
    broker_summary: PostSessionBrokerStateSummary,
) -> tuple[str, ...]:
    blockers: list[str] = []
    if not broker_summary.target_position_open:
        blockers.append("aapl_position_not_open")
    if not broker_summary.protective_stop_verified:
        blockers.append("aapl_protective_stop_not_verified")
    if (
        broker_summary.target_position_open
        and not broker_summary.protective_stop_matches_position_quantity
    ):
        blockers.append("aapl_protective_stop_quantity_mismatch")
    if broker_summary.unexpected_open_orders_count:
        blockers.append("unexpected_open_orders_present")
    if broker_summary.unexpected_positions_count:
        blockers.append("unexpected_positions_present")
    return tuple(blockers)


def _hold_decision_recommendation(
    broker_summary: PostSessionBrokerStateSummary,
) -> HoldDecisionRecommendation:
    if broker_summary.unexpected_open_orders_count or broker_summary.unexpected_positions_count:
        return "MANUAL_BROKER_REVIEW_REQUIRED"
    if broker_summary.target_position_open and broker_summary.protective_stop_verified:
        if broker_summary.protective_stop_matches_position_quantity:
            return "CONTINUE_HOLD_UNTIL_NEXT_REVIEW"
        return "REQUEST_OPERATOR_APPROVED_STOP_REPAIR"
    if broker_summary.target_position_open:
        return "REQUEST_OPERATOR_APPROVED_STOP_REPAIR"
    return "MANUAL_BROKER_REVIEW_REQUIRED"


def _position_status(broker_summary: PostSessionBrokerStateSummary) -> str:
    if broker_summary.target_position_open:
        return "open"
    return "not_open"


def _protective_stop_status(broker_summary: PostSessionBrokerStateSummary) -> str:
    if broker_summary.protective_stop_verified:
        return "open_verified"
    return "missing_or_unverified"


def _open_orders_summary(broker_summary: PostSessionBrokerStateSummary) -> str:
    if broker_summary.unexpected_open_orders_count:
        return "unexpected_open_orders_present"
    if broker_summary.protective_stop_verified:
        return "expected_protective_stop_only"
    return "no_verified_protective_stop"


def _positions_summary(broker_summary: PostSessionBrokerStateSummary) -> str:
    if broker_summary.unexpected_positions_count:
        return "unexpected_positions_present"
    if broker_summary.target_position_open:
        return "expected_aapl_position_only"
    return "no_target_position"


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
    return completed.stdout.strip() or "unavailable"


def _unique(values: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(values))
