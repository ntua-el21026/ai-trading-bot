"""Read-only preflight and launch authorization packet for the first paper session."""

from __future__ import annotations

import os
import subprocess
from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal, Protocol, Self, cast
from uuid import NAMESPACE_URL, uuid5

from pydantic import BaseModel, ConfigDict, Field, model_validator

from packages.broker.alpaca import (
    ALPACA_PAPER_BASE_URL,
    AlpacaClientError,
    AlpacaPaperCredentials,
    map_alpaca_account,
    map_alpaca_clock,
    map_alpaca_order,
    map_alpaca_position,
)
from packages.broker.smoke import (
    build_alpaca_paper_readonly_http_client,
    failed_alpaca_paper_readonly_smoke_gates,
    validate_alpaca_paper_readonly_smoke_gates,
)
from packages.core.config import AppConfig, load_app_config
from packages.paper.first_session import FIRST_SESSION_SPEC_VERSION, SENSITIVE_ENV_NAMES
from packages.paper.real_gate import REAL_SESSION_MAX_NOTIONAL_USD, REAL_SESSION_MAX_QUANTITY

MILESTONE_31_FAKE_OPERATOR_APPROVAL = "MILESTONE_31_FAKE_PREFLIGHT"
MILESTONE_31_READ_ONLY_OPERATOR_APPROVAL = "MILESTONE_31_READ_ONLY_PREFLIGHT"
MILESTONE_32_READ_ONLY_OPERATOR_APPROVAL = "MILESTONE_32_READ_ONLY_PREFLIGHT"
PREFLIGHT_PACKET_STARTED_AT = datetime(2026, 5, 9, 14, 0, tzinfo=UTC)

PreflightMode = Literal["fake", "real-read-only"]
PreflightScenarioId = Literal[
    "happy_path",
    "missing_operator_approval",
    "live_endpoint_rejected",
    "paper_endpoint_not_proven",
    "dirty_target_symbol",
    "open_orders_present",
    "open_position_present",
    "missing_target_symbol",
    "leverage_rejected",
    "missing_cleanup_policy",
    "missing_evidence_persistence",
]
BrokerEndpointMode = Literal["paper", "live", "unknown"]
GoNoGoDecision = Literal["go", "no_go"]

PREFLIGHT_SCENARIO_IDS: tuple[PreflightScenarioId, ...] = (
    "happy_path",
    "missing_operator_approval",
    "live_endpoint_rejected",
    "paper_endpoint_not_proven",
    "dirty_target_symbol",
    "open_orders_present",
    "open_position_present",
    "missing_target_symbol",
    "leverage_rejected",
    "missing_cleanup_policy",
    "missing_evidence_persistence",
)

DOC_REFERENCES: tuple[str, ...] = (
    "docs/pre_paper_operations_gap_audit.md",
    "docs/first_controlled_paper_session_wiring.md",
    "docs/first_controlled_paper_session_real_gate_wiring.md",
    "docs/first_controlled_paper_session_preflight.md",
    "docs/paper_trading_runbook.md",
)

PREFLIGHT_DOTENV_FILES: tuple[str, ...] = (".env", ".env.local")
WRITE_SMOKE_FLAG_ENV_VAR = "RUN_ALPACA_PAPER_ORDER_LIFECYCLE_SMOKE"
FIRST_SESSION_EXECUTION_FLAG_ENV_VARS: tuple[str, ...] = (
    "RUN_FIRST_CONTROLLED_PAPER_SESSION",
    "RUN_FIRST_CONTROLLED_PAPER_SESSION_EXECUTION",
)


class ReadOnlyBrokerClient(Protocol):
    def get_account(self) -> Mapping[str, Any]:
        """Return account payload."""

    def get_clock(self) -> Mapping[str, Any]:
        """Return clock/session payload."""

    def list_open_orders(self) -> Sequence[Mapping[str, Any]]:
        """Return open-order payloads."""

    def list_positions(self) -> Sequence[Mapping[str, Any]]:
        """Return position payloads."""


ReadOnlyClientFactory = Callable[[AlpacaPaperCredentials], ReadOnlyBrokerClient]


class ReadOnlyPreflightBrokerClient:
    """Narrow preflight wrapper that exposes only read-only broker methods."""

    def __init__(self, client: ReadOnlyBrokerClient) -> None:
        self._client = client

    def get_account(self) -> Mapping[str, Any]:
        return self._client.get_account()

    def get_clock(self) -> Mapping[str, Any]:
        return self._client.get_clock()

    def list_open_orders(self) -> Sequence[Mapping[str, Any]]:
        return self._client.list_open_orders()

    def list_positions(self) -> Sequence[Mapping[str, Any]]:
        return self._client.list_positions()


class PreflightModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class EndpointValidationResult(PreflightModel):
    broker_endpoint_mode: BrokerEndpointMode
    represented_base_url: str
    paper_endpoint_proven: bool
    live_endpoint_rejected: bool
    broker_call_performed: bool = False
    reason_code: str


class AccountSnapshotSummary(PreflightModel):
    reachable: bool
    environment: Literal["paper", "unknown"]
    equity: float = Field(ge=0)
    buying_power: float | None = Field(default=None, ge=0)
    currency: str
    status_summary: str


class ClockSessionSummary(PreflightModel):
    reachable: bool
    is_open: bool | None
    timestamp: datetime | None
    next_open: datetime | None
    next_close: datetime | None
    status_summary: str


class OpenOrdersSummary(PreflightModel):
    reachable: bool
    total_open_orders: int = Field(ge=0)
    target_symbol_open_orders: int = Field(ge=0)
    symbols: tuple[str, ...] = ()
    has_blocking_open_orders: bool
    status_summary: str


class PositionsSummary(PreflightModel):
    reachable: bool
    total_positions: int = Field(ge=0)
    target_symbol_quantity: float
    symbols: tuple[str, ...] = ()
    has_blocking_position: bool
    status_summary: str


class TargetSymbolCleanlinessResult(PreflightModel):
    target_symbol: str
    allowed: bool
    clean: bool
    open_order_count: int = Field(ge=0)
    position_quantity: float
    explicitly_allowed_existing_state: bool = False
    reason_code: str


class ExposureSummary(PreflightModel):
    equity: float = Field(ge=0)
    buying_power: float | None = Field(default=None, ge=0)
    current_gross_exposure: float = Field(ge=0)
    max_gross_exposure: float = Field(gt=0, le=1)
    no_leverage_assertion: bool
    gross_exposure_within_limit: bool


class ManagedEvidencePersistenceDecision(PreflightModel):
    mode: Literal[
        "local_packet_only",
        "managed_db_future_plus_local_packet",
        "missing",
    ] = "managed_db_future_plus_local_packet"
    direct_managed_db_persistence_for_first_session: bool = False
    local_evidence_packet_required: bool = True
    post_session_managed_db_audit_required: bool = True


class CleanupFlattenPolicyDecision(PreflightModel):
    policy_id: str | None = "first-session-cleanup-verify-only"
    mode: Literal["verify_only", "manual_risk_reducing_cleanup_if_needed", "missing"] = (
        "verify_only"
    )
    cleanup_allowed_only_for_risk_reduction: bool = True
    cleanup_forbidden_for_new_risk: bool = True
    paper_endpoint_required: bool = True
    cleanup_performed_in_this_milestone: bool = False


class AlertModeDecision(PreflightModel):
    mode: Literal["fake", "future_real_delivery_explicit_gate"] = "fake"
    real_delivery_enabled_this_milestone: bool = False


class DashboardReportVisibilityDecision(PreflightModel):
    mode: Literal["local_packet_and_report_summary"] = "local_packet_and_report_summary"
    dashboard_read_model_expected_after_session: bool = True
    report_generation_expected_after_session: bool = True
    deployment_required: bool = False


class PreflightGateCheck(PreflightModel):
    name: str
    passed: bool
    reason_code: str


class FirstSessionPreflightRequest(PreflightModel):
    mode: PreflightMode = "fake"
    scenario_id: PreflightScenarioId = "happy_path"
    operator_approval_marker: str | None = None
    target_symbol: str = "AAPL"
    target_symbol_allowlist: tuple[str, ...] = ("AAPL",)
    confirm_paper_endpoint: bool = True
    confirm_no_broker_writes: bool = True
    confirm_no_live_trading: bool = True
    confirm_no_autonomous_live: bool = True
    confirm_no_schedules: bool = True
    confirm_no_leverage: bool = True
    broker_endpoint_mode: BrokerEndpointMode = "paper"
    represented_base_url: str = ALPACA_PAPER_BASE_URL
    paper_endpoint_proven: bool = True
    allow_existing_open_orders: bool = False
    allow_existing_position: bool = False
    current_gross_exposure: float = Field(default=0.0, ge=0)
    max_gross_exposure: float = Field(default=1.0, gt=0, le=1)
    max_quantity: int = Field(default=REAL_SESSION_MAX_QUANTITY, gt=0)
    max_notional_usd: float = Field(default=REAL_SESSION_MAX_NOTIONAL_USD, gt=0)
    kill_switch_expected_state: Literal["RUNNING", "PAUSED_NEW_RISK"] = "RUNNING"
    prior_incident_review_marker: str = "prior_incidents_reviewed_clear"
    cleanup_policy: CleanupFlattenPolicyDecision = Field(
        default_factory=CleanupFlattenPolicyDecision
    )
    evidence_persistence: ManagedEvidencePersistenceDecision = Field(
        default_factory=ManagedEvidencePersistenceDecision
    )
    alert_mode: AlertModeDecision = Field(default_factory=AlertModeDecision)
    dashboard_report_visibility: DashboardReportVisibilityDecision = Field(
        default_factory=DashboardReportVisibilityDecision
    )
    started_at: datetime = PREFLIGHT_PACKET_STARTED_AT

    @model_validator(mode="after")
    def validate_request(self) -> Self:
        if self.target_symbol and self.target_symbol != self.target_symbol.upper():
            raise ValueError("target_symbol must be uppercase")
        if any(symbol != symbol.upper() for symbol in self.target_symbol_allowlist):
            raise ValueError("target_symbol_allowlist symbols must be uppercase")
        if self.started_at.tzinfo is None:
            raise ValueError("started_at must be timezone-aware")
        return self


class ReadOnlyBrokerPreflightResult(PreflightModel):
    preflight_id: str
    mode: PreflightMode
    endpoint_validation: EndpointValidationResult
    account: AccountSnapshotSummary
    clock: ClockSessionSummary
    open_orders: OpenOrdersSummary
    positions: PositionsSummary
    target_symbol: TargetSymbolCleanlinessResult
    exposure: ExposureSummary
    read_only_broker_calls_performed: bool = False
    real_read_only_alpaca_calls_performed: bool = False
    broker_write_methods_called: bool = False
    real_broker_writes_attempted: bool = False


class LaunchAuthorizationPacket(PreflightModel):
    authorization_packet_id: str
    timestamp: datetime
    operator_approval_marker: str | None
    commit_hash: str
    spec_version: str
    latest_spec_path: str
    doc_references: tuple[str, ...]
    preflight_mode: PreflightMode
    broker_endpoint_mode: BrokerEndpointMode
    paper_endpoint_proof: EndpointValidationResult
    live_endpoint_rejection_proof: EndpointValidationResult
    account_status_summary: AccountSnapshotSummary
    clock_session_summary: ClockSessionSummary
    open_orders_summary: OpenOrdersSummary
    positions_summary: PositionsSummary
    target_symbol_cleanliness: TargetSymbolCleanlinessResult
    kill_switch_expected_state: str
    prior_incident_review_marker: str
    no_schedule_assertion: bool
    no_live_assertion: bool
    no_autonomous_live_assertion: bool
    no_leverage_assertion: bool
    max_gross_exposure_assertion: float
    target_symbol_allowlist: tuple[str, ...]
    max_quantity: int
    max_notional_usd: float
    cleanup_policy_decision: CleanupFlattenPolicyDecision
    alert_mode_decision: AlertModeDecision
    evidence_persistence_decision: ManagedEvidencePersistenceDecision
    dashboard_report_visibility_decision: DashboardReportVisibilityDecision
    required_first_session_gates_checklist: tuple[PreflightGateCheck, ...]
    go_no_go_decision: GoNoGoDecision
    blockers: tuple[str, ...]
    actual_paper_trading_started: bool = False
    real_broker_writes_attempted: bool = False
    real_broker_orders_submitted: bool = False
    broker_write_methods_called: bool = False
    read_only_broker_calls_performed: bool = False
    real_read_only_alpaca_calls_performed: bool = False
    provider_ai_telegram_vercel_temporal_calls_performed: bool = False
    schedules_activated: bool = False
    live_trading_enabled: bool = False
    autonomous_live_execution_enabled: bool = False
    leverage_enabled: bool = False
    level4_ready: bool = False
    secrets_redacted: dict[str, str] = Field(
        default_factory=lambda: {name: "<redacted-not-inspected>" for name in SENSITIVE_ENV_NAMES}
    )
    statement_actual_paper_trading_not_started: str = (
        "Actual paper trading has not started."
    )
    statement_no_real_broker_writes_attempted: str = (
        "No real broker writes were attempted."
    )


class FirstSessionPreflightResult(PreflightModel):
    mode: PreflightMode
    scenario_id: PreflightScenarioId
    success: bool
    refused: bool
    go_no_go_decision: GoNoGoDecision
    blockers: tuple[str, ...]
    packet: LaunchAuthorizationPacket
    broker_preflight: ReadOnlyBrokerPreflightResult | None
    actual_paper_trading_started: bool = False
    real_broker_orders_submitted: bool = False
    real_broker_writes_attempted: bool = False
    broker_write_methods_called: bool = False
    read_only_broker_calls_performed: bool = False
    real_read_only_alpaca_calls_performed: bool = False
    provider_ai_telegram_vercel_temporal_calls_performed: bool = False
    schedules_activated: bool = False
    live_trading_enabled: bool = False
    autonomous_live_execution_enabled: bool = False
    leverage_enabled: bool = False
    ai_broker_write_authority: bool = False
    level4_ready: bool = False
    note: str = (
        "Milestone 31/32 read-only preflight and launch authorization only. Actual paper trading "
        "has not started and no broker writes were attempted."
    )

    @model_validator(mode="after")
    def validate_no_disallowed_side_effects(self) -> Self:
        forbidden = {
            "actual_paper_trading_started": self.actual_paper_trading_started,
            "real_broker_orders_submitted": self.real_broker_orders_submitted,
            "real_broker_writes_attempted": self.real_broker_writes_attempted,
            "broker_write_methods_called": self.broker_write_methods_called,
            "provider_ai_telegram_vercel_temporal_calls_performed": (
                self.provider_ai_telegram_vercel_temporal_calls_performed
            ),
            "schedules_activated": self.schedules_activated,
            "live_trading_enabled": self.live_trading_enabled,
            "autonomous_live_execution_enabled": self.autonomous_live_execution_enabled,
            "leverage_enabled": self.leverage_enabled,
            "ai_broker_write_authority": self.ai_broker_write_authority,
            "level4_ready": self.level4_ready,
        }
        enabled = [name for name, value in forbidden.items() if value]
        if enabled:
            raise ValueError(f"preflight result enabled forbidden flags: {enabled}")
        return self


def default_first_session_preflight_request(
    scenario_id: str = "happy_path",
    *,
    mode: PreflightMode = "fake",
    operator_approval_marker: str | None = None,
    confirm_paper_endpoint: bool | None = None,
    confirm_no_broker_writes: bool | None = None,
    confirm_no_live_trading: bool | None = None,
    confirm_no_autonomous_live: bool | None = None,
    confirm_no_schedules: bool | None = None,
    confirm_no_leverage: bool | None = None,
) -> FirstSessionPreflightRequest:
    scenario = _validate_scenario_id(scenario_id)
    default_confirm = mode == "fake"
    request = FirstSessionPreflightRequest(
        mode=mode,
        scenario_id=scenario,
        operator_approval_marker=operator_approval_marker,
        confirm_paper_endpoint=(
            default_confirm if confirm_paper_endpoint is None else confirm_paper_endpoint
        ),
        confirm_no_broker_writes=(
            default_confirm if confirm_no_broker_writes is None else confirm_no_broker_writes
        ),
        confirm_no_live_trading=(
            default_confirm if confirm_no_live_trading is None else confirm_no_live_trading
        ),
        confirm_no_autonomous_live=(
            default_confirm
            if confirm_no_autonomous_live is None
            else confirm_no_autonomous_live
        ),
        confirm_no_schedules=(
            default_confirm if confirm_no_schedules is None else confirm_no_schedules
        ),
        confirm_no_leverage=(
            default_confirm if confirm_no_leverage is None else confirm_no_leverage
        ),
    )
    return _scenario_request(request, scenario)


def load_preflight_environment(
    *,
    repo_root: Path | str | None = None,
    base_environ: Mapping[str, str] | None = None,
) -> dict[str, str]:
    """Load process env plus local .env files without logging secret values."""

    root = Path.cwd() if repo_root is None else Path(repo_root)
    merged: dict[str, str] = {}
    for file_name in PREFLIGHT_DOTENV_FILES:
        env_path = root / file_name
        if not env_path.is_file():
            continue
        merged.update(_parse_env_file(env_path))
    merged.update(os.environ if base_environ is None else base_environ)
    return merged


def write_launch_packet_artifact(
    result: FirstSessionPreflightResult,
    output_path: Path | str,
) -> Path:
    """Persist a sanitized launch packet artifact."""

    import json

    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "milestone": "32",
        "result": {
            "success": result.success,
            "refused": result.refused,
            "go_no_go_decision": result.go_no_go_decision,
            "blockers": result.blockers,
            "actual_paper_trading_started": result.actual_paper_trading_started,
            "real_broker_orders_submitted": result.real_broker_orders_submitted,
            "real_broker_writes_attempted": result.real_broker_writes_attempted,
            "broker_write_methods_called": result.broker_write_methods_called,
            "read_only_broker_calls_performed": result.read_only_broker_calls_performed,
            "real_read_only_alpaca_calls_performed": result.real_read_only_alpaca_calls_performed,
            "provider_ai_telegram_vercel_temporal_calls_performed": (
                result.provider_ai_telegram_vercel_temporal_calls_performed
            ),
            "schedules_activated": result.schedules_activated,
            "live_trading_enabled": result.live_trading_enabled,
            "autonomous_live_execution_enabled": result.autonomous_live_execution_enabled,
            "leverage_enabled": result.leverage_enabled,
            "ai_broker_write_authority": result.ai_broker_write_authority,
            "level4_ready": result.level4_ready,
        },
        "launch_packet": result.packet.model_dump(mode="json"),
    }
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return path


def run_first_controlled_paper_session_preflight(
    request: FirstSessionPreflightRequest | None = None,
    *,
    environ: Mapping[str, str] | None = None,
    app_config: AppConfig | None = None,
    client_factory: ReadOnlyClientFactory = build_alpaca_paper_readonly_http_client,
    real_external_calls_performed: bool = True,
) -> FirstSessionPreflightResult:
    active_request = request or default_first_session_preflight_request()
    active_config = app_config or load_app_config()
    active_environ = os.environ if environ is None else environ

    if not _operator_approval_valid(active_request):
        return _build_result(
            request=active_request,
            app_config=active_config,
            broker_preflight=None,
            blockers=("operator_approval_missing",),
        )

    pre_broker_blockers = _pre_broker_blockers(active_request, active_config, active_environ)
    if pre_broker_blockers:
        return _build_result(
            request=active_request,
            app_config=active_config,
            broker_preflight=None,
            blockers=pre_broker_blockers,
        )

    broker_preflight: ReadOnlyBrokerPreflightResult | None
    if active_request.mode == "fake":
        broker_preflight = _fake_broker_preflight(active_request)
    else:
        broker_preflight, read_blockers = _real_read_only_broker_preflight(
            active_request,
            app_config=active_config,
            environ=active_environ,
            client_factory=client_factory,
            real_external_calls_performed=real_external_calls_performed,
        )
        if read_blockers:
            return _build_result(
                request=active_request,
                app_config=active_config,
                broker_preflight=broker_preflight,
                blockers=read_blockers,
            )
        if broker_preflight is None:
            return _build_result(
                request=active_request,
                app_config=active_config,
                broker_preflight=None,
                blockers=("alpaca_read_only_preflight_missing",),
            )

    post_read_blockers = _post_read_blockers(active_request, broker_preflight, active_config)
    return _build_result(
        request=active_request,
        app_config=active_config,
        broker_preflight=broker_preflight,
        blockers=post_read_blockers,
    )


def _validate_scenario_id(scenario_id: str) -> PreflightScenarioId:
    if scenario_id not in PREFLIGHT_SCENARIO_IDS:
        allowed = ", ".join(PREFLIGHT_SCENARIO_IDS)
        raise ValueError(f"unknown preflight scenario_id: {scenario_id}; allowed: {allowed}")
    return cast(PreflightScenarioId, scenario_id)


def _scenario_request(
    request: FirstSessionPreflightRequest,
    scenario: PreflightScenarioId,
) -> FirstSessionPreflightRequest:
    updates: dict[str, object] = {}
    if scenario == "missing_operator_approval":
        updates["operator_approval_marker"] = None
    elif scenario == "live_endpoint_rejected":
        updates["broker_endpoint_mode"] = "live"
        updates["represented_base_url"] = "https://api.alpaca.markets"
        updates["paper_endpoint_proven"] = False
    elif scenario == "paper_endpoint_not_proven":
        updates["paper_endpoint_proven"] = False
    elif scenario in {"dirty_target_symbol", "open_orders_present"}:
        updates["allow_existing_open_orders"] = False
    elif scenario == "open_position_present":
        updates["allow_existing_position"] = False
    elif scenario == "missing_target_symbol":
        updates["target_symbol"] = ""
    elif scenario == "leverage_rejected":
        updates["current_gross_exposure"] = 1.01
    elif scenario == "missing_cleanup_policy":
        updates["cleanup_policy"] = CleanupFlattenPolicyDecision(
            policy_id=None,
            mode="missing",
            cleanup_allowed_only_for_risk_reduction=False,
            cleanup_forbidden_for_new_risk=False,
            paper_endpoint_required=False,
        )
    elif scenario == "missing_evidence_persistence":
        updates["evidence_persistence"] = ManagedEvidencePersistenceDecision(
            mode="missing",
            local_evidence_packet_required=False,
            post_session_managed_db_audit_required=False,
        )
    return request.model_copy(update=updates)


def _operator_approval_valid(request: FirstSessionPreflightRequest) -> bool:
    if request.mode == "fake":
        return request.operator_approval_marker == MILESTONE_31_FAKE_OPERATOR_APPROVAL
    return request.operator_approval_marker in {
        MILESTONE_31_READ_ONLY_OPERATOR_APPROVAL,
        MILESTONE_32_READ_ONLY_OPERATOR_APPROVAL,
    }


def _pre_broker_blockers(
    request: FirstSessionPreflightRequest,
    app_config: AppConfig,
    environ: Mapping[str, str],
) -> tuple[str, ...]:
    blockers: list[str] = []
    if not request.confirm_paper_endpoint:
        blockers.append("confirm_paper_endpoint_required")
    if not request.confirm_no_broker_writes:
        blockers.append("confirm_no_broker_writes_required")
    if not request.confirm_no_live_trading:
        blockers.append("confirm_no_live_trading_required")
    if not request.confirm_no_autonomous_live:
        blockers.append("confirm_no_autonomous_live_required")
    if not request.confirm_no_schedules:
        blockers.append("confirm_no_schedules_required")
    if not request.confirm_no_leverage:
        blockers.append("confirm_no_leverage_required")
    if (
        request.broker_endpoint_mode == "live"
        or request.represented_base_url != ALPACA_PAPER_BASE_URL
    ):
        blockers.append("live_endpoint_detected")
    if not request.paper_endpoint_proven:
        blockers.append("paper_endpoint_not_proven")
    if app_config.system.live_trading_enabled or app_config.execution.allow_live_orders:
        blockers.append("live_trading_enabled")
    if (
        app_config.system.autonomous_execution_enabled
        or app_config.execution.autonomous_execution_enabled
    ):
        blockers.append("autonomous_live_execution_enabled")
    if app_config.risk_level_4_micro_live.allow_margin:
        blockers.append("leverage_enabled")
    if environ.get(WRITE_SMOKE_FLAG_ENV_VAR, "").strip() == "1":
        blockers.append("write_smoke_flag_must_be_disabled")
    for env_name in FIRST_SESSION_EXECUTION_FLAG_ENV_VARS:
        if environ.get(env_name, "").strip() == "1":
            blockers.append(f"first_session_execution_flag_must_be_disabled:{env_name}")
    if request.mode == "real-read-only" and not blockers:
        blockers.extend(
            f"alpaca_readonly_gate:{gate}"
            for gate in failed_alpaca_paper_readonly_smoke_gates(
                environ=environ,
                app_config=app_config,
            )
        )
    return _unique(tuple(blockers))


def _fake_broker_preflight(
    request: FirstSessionPreflightRequest,
) -> ReadOnlyBrokerPreflightResult:
    endpoint = EndpointValidationResult(
        broker_endpoint_mode=request.broker_endpoint_mode,
        represented_base_url=request.represented_base_url,
        paper_endpoint_proven=(
            request.paper_endpoint_proven and request.broker_endpoint_mode == "paper"
        ),
        live_endpoint_rejected=request.broker_endpoint_mode != "live",
        reason_code=(
            "paper_endpoint_verified"
            if request.broker_endpoint_mode == "paper" and request.paper_endpoint_proven
            else "endpoint_not_safe"
        ),
    )
    open_order_symbols = _fake_open_order_symbols(request)
    position_symbols = _fake_position_symbols(request)
    return _broker_preflight_from_values(
        request=request,
        endpoint=endpoint,
        equity=100_000.0,
        buying_power=100_000.0,
        clock_is_open=True,
        clock_timestamp=request.started_at,
        next_open=request.started_at,
        next_close=request.started_at,
        open_order_symbols=open_order_symbols,
        total_open_orders=len(open_order_symbols),
        target_open_order_count=sum(
            symbol == request.target_symbol for symbol in open_order_symbols
        ),
        position_symbols=position_symbols,
        total_positions=len(position_symbols),
        target_position_quantity=(1.0 if request.target_symbol in position_symbols else 0.0),
        read_only_broker_calls_performed=False,
        real_read_only_alpaca_calls_performed=False,
    )


def _real_read_only_broker_preflight(
    request: FirstSessionPreflightRequest,
    *,
    app_config: AppConfig,
    environ: Mapping[str, str],
    client_factory: ReadOnlyClientFactory,
    real_external_calls_performed: bool,
) -> tuple[ReadOnlyBrokerPreflightResult | None, tuple[str, ...]]:
    try:
        credentials = validate_alpaca_paper_readonly_smoke_gates(
            environ=environ,
            app_config=app_config,
        )
        client = ReadOnlyPreflightBrokerClient(client_factory(credentials))
        account = map_alpaca_account(client.get_account(), environment="paper")
        clock = map_alpaca_clock(client.get_clock())
        open_orders = tuple(map_alpaca_order(payload) for payload in client.list_open_orders())
        positions = tuple(map_alpaca_position(payload) for payload in client.list_positions())
    except AlpacaClientError as exc:
        return None, (f"alpaca_read_only_failed:{exc.code}",)
    except Exception as exc:
        return None, (f"alpaca_read_only_failed:{type(exc).__name__}",)

    endpoint = EndpointValidationResult(
        broker_endpoint_mode="paper",
        represented_base_url=ALPACA_PAPER_BASE_URL,
        paper_endpoint_proven=True,
        live_endpoint_rejected=True,
        broker_call_performed=True,
        reason_code="paper_endpoint_verified_before_read",
    )
    open_order_symbols = tuple(sorted({order.symbol for order in open_orders}))
    position_symbols = tuple(sorted({position.symbol for position in positions}))
    return (
        _broker_preflight_from_values(
            request=request,
            endpoint=endpoint,
            equity=account.equity,
            buying_power=account.buying_power,
            clock_is_open=clock.is_open,
            clock_timestamp=clock.timestamp,
            next_open=clock.next_open,
            next_close=clock.next_close,
            open_order_symbols=open_order_symbols,
            total_open_orders=len(open_orders),
            target_open_order_count=sum(
                1 for order in open_orders if order.symbol == request.target_symbol
            ),
            position_symbols=position_symbols,
            total_positions=len(positions),
            target_position_quantity=sum(
                position.quantity
                for position in positions
                if position.symbol == request.target_symbol
            ),
            read_only_broker_calls_performed=True,
            real_read_only_alpaca_calls_performed=real_external_calls_performed,
        ),
        (),
    )


def _broker_preflight_from_values(
    *,
    request: FirstSessionPreflightRequest,
    endpoint: EndpointValidationResult,
    equity: float,
    buying_power: float | None,
    clock_is_open: bool,
    clock_timestamp: datetime,
    next_open: datetime,
    next_close: datetime,
    open_order_symbols: tuple[str, ...],
    total_open_orders: int,
    target_open_order_count: int,
    position_symbols: tuple[str, ...],
    total_positions: int,
    target_position_quantity: float,
    read_only_broker_calls_performed: bool,
    real_read_only_alpaca_calls_performed: bool,
) -> ReadOnlyBrokerPreflightResult:
    target_symbol_allowed = request.target_symbol in request.target_symbol_allowlist
    blocking_open_orders = target_open_order_count > 0 and not request.allow_existing_open_orders
    blocking_position = target_position_quantity != 0 and not request.allow_existing_position
    target_clean = target_symbol_allowed and not blocking_open_orders and not blocking_position
    return ReadOnlyBrokerPreflightResult(
        preflight_id=f"preflight-{request.mode}-{request.scenario_id}",
        mode=request.mode,
        endpoint_validation=endpoint,
        account=AccountSnapshotSummary(
            reachable=True,
            environment="paper",
            equity=equity,
            buying_power=buying_power,
            currency="USD",
            status_summary="reachable_paper_account",
        ),
        clock=ClockSessionSummary(
            reachable=True,
            is_open=clock_is_open,
            timestamp=clock_timestamp,
            next_open=next_open,
            next_close=next_close,
            status_summary="clock_readable",
        ),
        open_orders=OpenOrdersSummary(
            reachable=True,
            total_open_orders=total_open_orders,
            target_symbol_open_orders=target_open_order_count,
            symbols=tuple(sorted(open_order_symbols)),
            has_blocking_open_orders=blocking_open_orders,
            status_summary="blocking_open_orders_present" if blocking_open_orders else "clean",
        ),
        positions=PositionsSummary(
            reachable=True,
            total_positions=total_positions,
            target_symbol_quantity=target_position_quantity,
            symbols=tuple(sorted(position_symbols)),
            has_blocking_position=blocking_position,
            status_summary="blocking_position_present" if blocking_position else "clean",
        ),
        target_symbol=TargetSymbolCleanlinessResult(
            target_symbol=request.target_symbol,
            allowed=target_symbol_allowed,
            clean=target_clean,
            open_order_count=target_open_order_count,
            position_quantity=target_position_quantity,
            explicitly_allowed_existing_state=(
                request.allow_existing_open_orders or request.allow_existing_position
            ),
            reason_code="clean" if target_clean else "target_symbol_not_clean",
        ),
        exposure=ExposureSummary(
            equity=equity,
            buying_power=buying_power,
            current_gross_exposure=request.current_gross_exposure,
            max_gross_exposure=request.max_gross_exposure,
            no_leverage_assertion=request.current_gross_exposure <= 1.0,
            gross_exposure_within_limit=(
                request.current_gross_exposure <= request.max_gross_exposure
                and request.current_gross_exposure <= 1.0
            ),
        ),
        read_only_broker_calls_performed=read_only_broker_calls_performed,
        real_read_only_alpaca_calls_performed=real_read_only_alpaca_calls_performed,
    )


def _post_read_blockers(
    request: FirstSessionPreflightRequest,
    broker_preflight: ReadOnlyBrokerPreflightResult,
    app_config: AppConfig,
) -> tuple[str, ...]:
    blockers: list[str] = []
    if not request.target_symbol:
        blockers.append("target_symbol_not_selected")
    if not broker_preflight.endpoint_validation.paper_endpoint_proven:
        blockers.append("paper_endpoint_not_proven")
    if not broker_preflight.endpoint_validation.live_endpoint_rejected:
        blockers.append("live_endpoint_detected")
    if not broker_preflight.target_symbol.allowed:
        blockers.append("target_symbol_not_allowed")
    if not broker_preflight.target_symbol.clean:
        blockers.append("target_symbol_not_clean")
    if broker_preflight.open_orders.has_blocking_open_orders:
        blockers.append("existing_open_orders_block_first_session")
    if broker_preflight.positions.has_blocking_position:
        blockers.append("existing_position_blocks_first_session")
    if not broker_preflight.exposure.no_leverage_assertion:
        blockers.append("leverage_or_margin_exposure_detected")
    if not broker_preflight.exposure.gross_exposure_within_limit:
        blockers.append("gross_exposure_exceeds_1x")
    if request.cleanup_policy.mode == "missing" or request.cleanup_policy.policy_id is None:
        blockers.append("cleanup_policy_decision_required")
    if request.evidence_persistence.mode == "missing":
        blockers.append("evidence_persistence_decision_required")
    if not request.confirm_no_schedules:
        blockers.append("no_schedule_assertion_required")
    if not request.confirm_no_live_trading or app_config.system.live_trading_enabled:
        blockers.append("no_live_assertion_required")
    if not request.confirm_no_autonomous_live:
        blockers.append("no_autonomous_live_assertion_required")
    if not request.confirm_no_leverage:
        blockers.append("no_leverage_assertion_required")
    return _unique(tuple(blockers))


def _build_result(
    *,
    request: FirstSessionPreflightRequest,
    app_config: AppConfig,
    broker_preflight: ReadOnlyBrokerPreflightResult | None,
    blockers: tuple[str, ...],
) -> FirstSessionPreflightResult:
    clean_blockers = _unique(blockers)
    decision: GoNoGoDecision = "go" if not clean_blockers else "no_go"
    packet = _build_packet(
        request=request,
        app_config=app_config,
        broker_preflight=broker_preflight,
        blockers=clean_blockers,
        decision=decision,
    )
    return FirstSessionPreflightResult(
        mode=request.mode,
        scenario_id=request.scenario_id,
        success=decision == "go",
        refused=decision == "no_go",
        go_no_go_decision=decision,
        blockers=clean_blockers,
        packet=packet,
        broker_preflight=broker_preflight,
        read_only_broker_calls_performed=(
            False if broker_preflight is None else broker_preflight.read_only_broker_calls_performed
        ),
        real_read_only_alpaca_calls_performed=(
            False
            if broker_preflight is None
            else broker_preflight.real_read_only_alpaca_calls_performed
        ),
        live_trading_enabled=False,
        autonomous_live_execution_enabled=False,
        leverage_enabled=False,
    )


def _build_packet(
    *,
    request: FirstSessionPreflightRequest,
    app_config: AppConfig,
    broker_preflight: ReadOnlyBrokerPreflightResult | None,
    blockers: tuple[str, ...],
    decision: GoNoGoDecision,
) -> LaunchAuthorizationPacket:
    fallback = _fallback_broker_preflight(request)
    preflight = fallback if broker_preflight is None else broker_preflight
    checks = _gate_checklist(request, app_config, preflight, blockers)
    return LaunchAuthorizationPacket(
        authorization_packet_id=_packet_id(request),
        timestamp=request.started_at,
        operator_approval_marker=request.operator_approval_marker,
        commit_hash=_git_commit_or_unavailable(),
        spec_version=FIRST_SESSION_SPEC_VERSION,
        latest_spec_path=f"docs/app/{FIRST_SESSION_SPEC_VERSION}",
        doc_references=DOC_REFERENCES,
        preflight_mode=request.mode,
        broker_endpoint_mode=preflight.endpoint_validation.broker_endpoint_mode,
        paper_endpoint_proof=preflight.endpoint_validation,
        live_endpoint_rejection_proof=EndpointValidationResult(
            broker_endpoint_mode=preflight.endpoint_validation.broker_endpoint_mode,
            represented_base_url=preflight.endpoint_validation.represented_base_url,
            paper_endpoint_proven=preflight.endpoint_validation.paper_endpoint_proven,
            live_endpoint_rejected=preflight.endpoint_validation.live_endpoint_rejected,
            broker_call_performed=preflight.endpoint_validation.broker_call_performed,
            reason_code=(
                "live_endpoint_rejected"
                if preflight.endpoint_validation.live_endpoint_rejected
                else "live_endpoint_detected"
            ),
        ),
        account_status_summary=preflight.account,
        clock_session_summary=preflight.clock,
        open_orders_summary=preflight.open_orders,
        positions_summary=preflight.positions,
        target_symbol_cleanliness=preflight.target_symbol,
        kill_switch_expected_state=request.kill_switch_expected_state,
        prior_incident_review_marker=request.prior_incident_review_marker,
        no_schedule_assertion=request.confirm_no_schedules,
        no_live_assertion=(
            request.confirm_no_live_trading
            and not app_config.system.live_trading_enabled
            and not app_config.execution.allow_live_orders
        ),
        no_autonomous_live_assertion=(
            request.confirm_no_autonomous_live
            and not app_config.system.autonomous_execution_enabled
            and not app_config.execution.autonomous_execution_enabled
        ),
        no_leverage_assertion=(
            request.confirm_no_leverage
            and preflight.exposure.no_leverage_assertion
            and not app_config.risk_level_4_micro_live.allow_margin
        ),
        max_gross_exposure_assertion=request.max_gross_exposure,
        target_symbol_allowlist=request.target_symbol_allowlist,
        max_quantity=request.max_quantity,
        max_notional_usd=request.max_notional_usd,
        cleanup_policy_decision=request.cleanup_policy,
        alert_mode_decision=request.alert_mode,
        evidence_persistence_decision=request.evidence_persistence,
        dashboard_report_visibility_decision=request.dashboard_report_visibility,
        required_first_session_gates_checklist=checks,
        go_no_go_decision=decision,
        blockers=blockers,
        read_only_broker_calls_performed=preflight.read_only_broker_calls_performed,
        real_read_only_alpaca_calls_performed=preflight.real_read_only_alpaca_calls_performed,
        provider_ai_telegram_vercel_temporal_calls_performed=False,
        live_trading_enabled=False,
        autonomous_live_execution_enabled=False,
        leverage_enabled=False,
    )


def _fallback_broker_preflight(
    request: FirstSessionPreflightRequest,
) -> ReadOnlyBrokerPreflightResult:
    endpoint = EndpointValidationResult(
        broker_endpoint_mode=request.broker_endpoint_mode,
        represented_base_url=request.represented_base_url,
        paper_endpoint_proven=(
            request.paper_endpoint_proven
            and request.broker_endpoint_mode == "paper"
            and request.represented_base_url == ALPACA_PAPER_BASE_URL
        ),
        live_endpoint_rejected=(
            request.broker_endpoint_mode != "live"
            and request.represented_base_url == ALPACA_PAPER_BASE_URL
        ),
        reason_code="not_reached_pre_broker_refusal",
    )
    return ReadOnlyBrokerPreflightResult(
        preflight_id=f"preflight-not-reached-{request.mode}-{request.scenario_id}",
        mode=request.mode,
        endpoint_validation=endpoint,
        account=AccountSnapshotSummary(
            reachable=False,
            environment="unknown",
            equity=0.0,
            buying_power=None,
            currency="USD",
            status_summary="not_reached",
        ),
        clock=ClockSessionSummary(
            reachable=False,
            is_open=None,
            timestamp=None,
            next_open=None,
            next_close=None,
            status_summary="not_reached",
        ),
        open_orders=OpenOrdersSummary(
            reachable=False,
            total_open_orders=0,
            target_symbol_open_orders=0,
            has_blocking_open_orders=False,
            status_summary="not_reached",
        ),
        positions=PositionsSummary(
            reachable=False,
            total_positions=0,
            target_symbol_quantity=0.0,
            has_blocking_position=False,
            status_summary="not_reached",
        ),
        target_symbol=TargetSymbolCleanlinessResult(
            target_symbol=request.target_symbol,
            allowed=request.target_symbol in request.target_symbol_allowlist,
            clean=False,
            open_order_count=0,
            position_quantity=0.0,
            reason_code="not_reached",
        ),
        exposure=ExposureSummary(
            equity=0.0,
            buying_power=None,
            current_gross_exposure=request.current_gross_exposure,
            max_gross_exposure=request.max_gross_exposure,
            no_leverage_assertion=request.current_gross_exposure <= 1.0,
            gross_exposure_within_limit=(
                request.current_gross_exposure <= request.max_gross_exposure
            ),
        ),
    )


def _gate_checklist(
    request: FirstSessionPreflightRequest,
    app_config: AppConfig,
    preflight: ReadOnlyBrokerPreflightResult,
    blockers: tuple[str, ...],
) -> tuple[PreflightGateCheck, ...]:
    return (
        _check("operator_approval", _operator_approval_valid(request), "operator_approval_missing"),
        _check(
            "paper_endpoint_proof",
            preflight.endpoint_validation.paper_endpoint_proven,
            "paper_endpoint_not_proven",
        ),
        _check(
            "live_endpoint_rejection",
            preflight.endpoint_validation.live_endpoint_rejected,
            "live_endpoint_detected",
        ),
        _check(
            "no_broker_writes",
            request.confirm_no_broker_writes and not preflight.broker_write_methods_called,
            "broker_write_forbidden",
        ),
        _check(
            "no_live_trading",
            request.confirm_no_live_trading
            and not app_config.system.live_trading_enabled
            and not app_config.execution.allow_live_orders,
            "live_trading_enabled",
        ),
        _check(
            "no_autonomous_live",
            request.confirm_no_autonomous_live
            and not app_config.system.autonomous_execution_enabled
            and not app_config.execution.autonomous_execution_enabled,
            "autonomous_live_execution_enabled",
        ),
        _check("no_schedules", request.confirm_no_schedules, "schedules_forbidden"),
        _check(
            "no_leverage",
            request.confirm_no_leverage and preflight.exposure.no_leverage_assertion,
            "leverage_or_margin_exposure_detected",
        ),
        _check("target_symbol_clean", preflight.target_symbol.clean, "target_symbol_not_clean"),
        _check(
            "cleanup_policy",
            request.cleanup_policy.mode != "missing"
            and request.cleanup_policy.policy_id is not None,
            "cleanup_policy_decision_required",
        ),
        _check(
            "evidence_persistence",
            request.evidence_persistence.mode != "missing",
            "evidence_persistence_decision_required",
        ),
        _check("go_no_go", not blockers, "no_go_blockers_present"),
    )


def _check(name: str, passed: bool, reason_code: str) -> PreflightGateCheck:
    return PreflightGateCheck(
        name=name,
        passed=passed,
        reason_code=f"{name}_passed" if passed else reason_code,
    )


def _fake_open_order_symbols(request: FirstSessionPreflightRequest) -> tuple[str, ...]:
    if request.scenario_id in {"dirty_target_symbol", "open_orders_present"}:
        return (request.target_symbol,)
    return ()


def _fake_position_symbols(request: FirstSessionPreflightRequest) -> tuple[str, ...]:
    if request.scenario_id in {"dirty_target_symbol", "open_position_present"}:
        return (request.target_symbol,)
    return ()


def _packet_id(request: FirstSessionPreflightRequest) -> str:
    value = f"m31-preflight:{request.mode}:{request.scenario_id}:{request.started_at.isoformat()}"
    return str(uuid5(NAMESPACE_URL, value))


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


def _unique(values: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(values))


def _parse_env_file(path: Path) -> dict[str, str]:
    parsed: dict[str, str] = {}
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return parsed
    for raw_line in lines:
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        if line.startswith("export "):
            line = line[len("export ") :].strip()
        name, value = line.split("=", 1)
        key = name.strip()
        if not key:
            continue
        parsed[key] = _parse_env_value(value.strip())
    return parsed


def _parse_env_value(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value.split(" #", 1)[0].strip()
