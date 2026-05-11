"""Milestone 34 controlled Alpaca paper session execution boundary."""

from __future__ import annotations

import json
import math
import re
import time
from collections.abc import Callable, Mapping
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Literal, Protocol, Self, cast
from uuid import NAMESPACE_URL, uuid5

from pydantic import BaseModel, ConfigDict, Field, model_validator

from packages.broker.alpaca import (
    AlpacaClientError,
    AlpacaPaperAdapter,
    AlpacaPaperCredentials,
    map_alpaca_clock,
)
from packages.broker.fakes import FakeAlpacaClient
from packages.broker.models import BrokerOrder
from packages.broker.order_lifecycle_smoke import (
    AlpacaPaperOrderLifecycleClient,
    AlpacaPaperOrderLifecycleSmokeSettings,
    build_alpaca_paper_order_lifecycle_http_client,
)
from packages.broker.smoke import validate_alpaca_paper_readonly_smoke_gates
from packages.core.config import AppConfig, load_app_config
from packages.execution.idempotency import short_hash
from packages.execution.models import ExecutionIntent
from packages.paper.first_session import FIRST_SESSION_SPEC_VERSION, SENSITIVE_ENV_NAMES
from packages.paper.preflight import load_preflight_environment

MILESTONE_34_REAL_OPERATOR_APPROVAL = "MILESTONE_34_FIRST_CONTROLLED_PAPER_SESSION"
MILESTONE_35_REAL_OPERATOR_APPROVAL = (
    "MILESTONE_35_OPERATOR_SELECTED_FIRST_CONTROLLED_PAPER_SESSION"
)
MILESTONE_34_FAKE_OPERATOR_APPROVAL = "MILESTONE_34_FAKE_REAL_PAPER"
M34_RESULT_EVIDENCE_PATH = "docs/evidence/first_controlled_paper_session_result.json"
M34_LAUNCH_PACKET_PATH = "docs/evidence/first_controlled_paper_session_launch_packet.json"
M34_STARTED_AT = datetime(2026, 5, 10, 14, 0, tzinfo=UTC)
M34_STRATEGY_VERSION = "first_controlled_paper_session_v0_3"
M34_RISK_CONFIG_VERSION = "first_controlled_paper_session_cap_v0_3"
M34_CLIENT_ORDER_PREFIX = "first-session"
ETF_SYMBOLS = frozenset({"SPY", "QQQ", "DIA", "IWM", "XLK", "XLF", "XLE", "XLV"})
LEVERAGED_OR_INVERSE_ETF_SYMBOLS = frozenset(
    {"TQQQ", "SQQQ", "UPRO", "SPXU", "SOXL", "SOXS", "UVXY", "SVXY"}
)
SYMBOL_FORMAT = re.compile(r"^[A-Z][A-Z0-9.]{0,9}$")

FirstPaperSessionMode = Literal["real-paper", "fake-real-paper"]
FirstPaperSessionCliMode = Literal[
    "real-gated",
    "fake",
    "real-paper",
    "fake-real-paper",
    "audit-symbol-universe",
]
FirstPaperSessionScenarioId = Literal[
    "happy_path",
    "partial_fill",
    "no_fill",
    "missing_stop_verification",
    "live_endpoint_rejected",
    "dirty_reconciliation_blocks",
    "existing_open_orders",
    "existing_position",
    "leverage_rejected",
    "short_rejected",
    "unsupported_asset_rejected",
    "missing_execution_intent",
    "missing_idempotency_key",
    "missing_protective_stop_plan",
]
FirstPaperSessionStatus = Literal["executed", "refused", "incident"]
PostSessionAuditRecommendation = Literal[
    "post_session_audit_required_before_repetition",
    "do_not_repeat_until_blockers_cleared",
]

FIRST_PAPER_SESSION_SCENARIO_IDS: tuple[FirstPaperSessionScenarioId, ...] = (
    "happy_path",
    "partial_fill",
    "no_fill",
    "missing_stop_verification",
    "live_endpoint_rejected",
    "dirty_reconciliation_blocks",
    "existing_open_orders",
    "existing_position",
    "leverage_rejected",
    "short_rejected",
    "unsupported_asset_rejected",
    "missing_execution_intent",
    "missing_idempotency_key",
    "missing_protective_stop_plan",
)
REAL_PAPER_OPERATOR_APPROVAL_MARKERS = (
    MILESTONE_34_REAL_OPERATOR_APPROVAL,
    MILESTONE_35_REAL_OPERATOR_APPROVAL,
)
_ORDER_ENVELOPE_BLOCKER_CODES = frozenset(
    {
        "max_qty_required",
        "max_qty_exceeds_first_session_max",
        "max_notional_required",
        "max_notional_exceeds_first_session_ceiling",
        "limit_price_required",
        "entry_order_type_must_be_limit",
        "time_in_force_must_be_day",
        "estimated_notional_exceeds_max_notional",
    }
)


class FirstPaperSessionClientFactory(Protocol):
    def __call__(
        self,
        credentials: AlpacaPaperCredentials,
        settings: AlpacaPaperOrderLifecycleSmokeSettings,
    ) -> AlpacaPaperOrderLifecycleClient:
        """Build a paper broker client."""


class M34Model(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class OrderEnvelope(M34Model):
    max_quantity: int | None = Field(default=None, gt=0)
    max_notional_usd: float | None = Field(default=None, gt=0)
    entry_order_type: Literal["limit"] = "limit"
    time_in_force: Literal["day"] = "day"
    limit_price: float | None = Field(default=None, gt=0)
    stop_loss_percent: float = Field(default=0.5, gt=0, lt=1)
    stop_loss_price: float | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    def validate_finite_prices(self) -> Self:
        for field_name in (
            "max_notional_usd",
            "limit_price",
            "stop_loss_percent",
            "stop_loss_price",
        ):
            value = getattr(self, field_name)
            if value is not None and not math.isfinite(float(value)):
                raise ValueError(f"{field_name} must be finite")
        return self


class BrokerStateSummary(M34Model):
    account_reachable: bool
    clock_reachable: bool
    clock_is_open: bool | None
    open_orders_status: str
    open_order_count: int = Field(ge=0)
    target_symbol_open_order_count: int = Field(ge=0)
    positions_status: str
    position_count: int = Field(ge=0)
    target_symbol_position_quantity: float
    reconciliation_clean: bool


class ProtectiveStopPlan(M34Model):
    plan_id: str | None
    required: bool
    stop_loss_price: float | None
    stop_loss_percent: float
    status: str


class BrokerWriteRecord(M34Model):
    operation: str
    attempted: bool
    broker_order_id: str | None = None
    client_order_id: str | None = None
    status: str | None = None
    fake_only: bool = False


class FirstSessionSymbolAuditRecord(M34Model):
    symbol: str
    symbol_format_valid: bool
    in_allowed_universe: bool
    asset_class: Literal["equity", "etf"]
    supported_asset_class: bool
    leveraged_or_inverse_marker: bool
    accepted_by_first_session_envelope_logic: bool
    reason_codes: tuple[str, ...]


class FirstSessionSymbolUniverseAuditResult(M34Model):
    allowed_symbols: tuple[str, ...]
    first_session_max_quantity: int
    first_session_absolute_max_notional_usd: float
    records: tuple[FirstSessionSymbolAuditRecord, ...]
    success: bool
    actual_paper_trading_started: bool = False
    real_broker_writes_attempted: bool = False
    external_calls_attempted: bool = False
    schedules_activated: bool = False
    live_trading_enabled: bool = False
    autonomous_live_execution_enabled: bool = False
    leverage_enabled: bool = False
    level4_ready: bool = False


class FirstPaperSessionResultPacket(M34Model):
    result_packet_id: str
    timestamp: datetime
    operator_approval_marker: str | None
    commit_hash: str
    latest_spec_path: str
    spec_version: str
    launch_packet_reference: str
    target_symbol: str | None
    order_envelope: OrderEnvelope
    estimated_entry_notional_usd: float | None
    first_session_max_quantity: int
    first_session_absolute_max_notional_usd: float
    symbol_allowlist_decision: str
    order_envelope_validation_result: str
    order_envelope_rejection_reasons: tuple[str, ...]
    paper_endpoint_proof: str
    live_endpoint_rejection_proof: str
    pre_run_broker_state: BrokerStateSummary
    pre_run_reconciliation_result: str
    candidate_id: str | None
    ai_news_neutral_fallback_marker: str
    decision_id: str | None
    risk_check_id: str | None
    execution_intent_id: str | None
    client_order_id: str | None
    broker_order_id: str | None
    entry_order_status: str | None
    fill_status: str
    filled_quantity: float = Field(ge=0)
    fill_id: str | None
    protective_stop_plan: ProtectiveStopPlan
    protective_stop_order_id: str | None
    protective_stop_verification_result: str
    cleanup_flatten_policy: str
    cleanup_actions: tuple[str, ...]
    post_run_open_orders_summary: str
    post_run_positions_summary: str
    post_run_reconciliation_result: str
    incidents: tuple[str, ...]
    fake_alert_summary: str
    report_summary: str
    dashboard_read_model_summary: str
    actual_paper_trading_started: bool
    real_broker_orders_submitted: bool
    real_broker_writes_attempted: bool
    broker_writes: tuple[BrokerWriteRecord, ...]
    provider_ai_telegram_vercel_temporal_calls: bool = False
    schedules_activated: bool = False
    live_trading_enabled: bool = False
    autonomous_live_execution_enabled: bool = False
    leverage_enabled: bool = False
    level4_ready: bool = False
    post_session_recommendation: PostSessionAuditRecommendation
    secrets_redacted: dict[str, str] = Field(
        default_factory=lambda: {name: "<redacted-not-inspected>" for name in SENSITIVE_ENV_NAMES}
    )


class FirstPaperSessionExecutionRequest(M34Model):
    mode: FirstPaperSessionMode = "real-paper"
    scenario_id: FirstPaperSessionScenarioId = "happy_path"
    operator_approval_marker: str | None = None
    target_symbol: str | None = None
    order_envelope: OrderEnvelope = Field(default_factory=OrderEnvelope)
    confirm_paper_endpoint: bool = False
    confirm_real_paper_writes: bool = False
    confirm_no_live_trading: bool = False
    confirm_no_autonomous_live: bool = False
    confirm_no_schedules: bool = False
    confirm_no_leverage: bool = False
    confirm_first_session_only: bool = False
    confirm_protective_stop_required: bool = False
    confirm_cleanup_policy: bool = False
    launch_packet_path: str = M34_LAUNCH_PACKET_PATH
    cleanup_policy: Literal["verify_only"] = "verify_only"
    current_gross_exposure: float = Field(default=0.0, ge=0)
    valid_execution_intent_present: bool = True
    idempotency_key_present: bool = True
    protective_stop_plan_present: bool = True
    started_at: datetime = M34_STARTED_AT

    @model_validator(mode="after")
    def validate_request(self) -> Self:
        if self.target_symbol is not None and self.target_symbol != self.target_symbol.upper():
            raise ValueError("target_symbol must be uppercase")
        if self.started_at.tzinfo is None:
            raise ValueError("started_at must be timezone-aware")
        return self


class FirstPaperSessionExecutionResult(M34Model):
    mode: FirstPaperSessionMode
    scenario_id: FirstPaperSessionScenarioId
    status: FirstPaperSessionStatus
    success: bool
    refused: bool
    unsafe: bool
    blockers: tuple[str, ...]
    result_packet: FirstPaperSessionResultPacket
    result_packet_path: str | None = None
    actual_paper_trading_started: bool
    real_broker_orders_submitted: bool
    real_broker_writes_attempted: bool
    real_read_only_alpaca_calls_performed: bool
    provider_ai_telegram_vercel_temporal_calls: bool = False
    schedules_activated: bool = False
    live_trading_enabled: bool = False
    autonomous_live_execution_enabled: bool = False
    leverage_enabled: bool = False
    ai_broker_write_authority: bool = False
    level4_ready: bool = False
    post_session_go_no_go: Literal["post_session_audit_only", "no_go"]
    note: str = (
        "Milestone 34 controlled Alpaca paper session boundary. Real broker writes occur only in "
        "real-paper mode after every gate passes."
    )

    @model_validator(mode="after")
    def validate_safety_flags(self) -> Self:
        forbidden = {
            "provider_ai_telegram_vercel_temporal_calls": (
                self.provider_ai_telegram_vercel_temporal_calls
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
            raise ValueError(f"M34 result enabled forbidden flags: {enabled}")
        return self


def default_first_paper_session_execution_request(
    scenario_id: str = "happy_path",
    *,
    mode: FirstPaperSessionMode = "real-paper",
    operator_approval_marker: str | None = None,
    target_symbol: str | None = None,
    max_quantity: int | None = None,
    max_notional_usd: float | None = None,
    limit_price: float | None = None,
    confirm_paper_endpoint: bool | None = None,
    confirm_real_paper_writes: bool | None = None,
    confirm_no_live_trading: bool | None = None,
    confirm_no_autonomous_live: bool | None = None,
    confirm_no_schedules: bool | None = None,
    confirm_no_leverage: bool | None = None,
    confirm_first_session_only: bool | None = None,
    confirm_protective_stop_required: bool | None = None,
    confirm_cleanup_policy: bool | None = None,
) -> FirstPaperSessionExecutionRequest:
    scenario = _validate_scenario_id(scenario_id)
    default_confirm = mode == "fake-real-paper"
    default_target = "AAPL" if mode == "fake-real-paper" else None
    default_quantity = 1 if mode == "fake-real-paper" else None
    default_notional = 25.0 if mode == "fake-real-paper" else None
    default_limit_price = 25.0 if mode == "fake-real-paper" else None
    request = FirstPaperSessionExecutionRequest(
        mode=mode,
        scenario_id=scenario,
        operator_approval_marker=operator_approval_marker,
        target_symbol=target_symbol or default_target,
        order_envelope=OrderEnvelope(
            max_quantity=default_quantity if max_quantity is None else max_quantity,
            max_notional_usd=(
                default_notional if max_notional_usd is None else max_notional_usd
            ),
            limit_price=default_limit_price if limit_price is None else limit_price,
        ),
        confirm_paper_endpoint=(
            default_confirm if confirm_paper_endpoint is None else confirm_paper_endpoint
        ),
        confirm_real_paper_writes=(
            default_confirm if confirm_real_paper_writes is None else confirm_real_paper_writes
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
        confirm_first_session_only=(
            default_confirm if confirm_first_session_only is None else confirm_first_session_only
        ),
        confirm_protective_stop_required=(
            default_confirm
            if confirm_protective_stop_required is None
            else confirm_protective_stop_required
        ),
        confirm_cleanup_policy=(
            default_confirm if confirm_cleanup_policy is None else confirm_cleanup_policy
        ),
    )
    return _scenario_request(request, scenario)


def run_first_controlled_paper_session_execution(
    request: FirstPaperSessionExecutionRequest | None = None,
    *,
    environ: Mapping[str, str] | None = None,
    app_config: AppConfig | None = None,
    client_factory: FirstPaperSessionClientFactory = build_alpaca_paper_order_lifecycle_http_client,
    real_external_calls_performed: bool = True,
    sleeper: Callable[[float], None] = time.sleep,
    clock: Callable[[], float] = time.monotonic,
) -> FirstPaperSessionExecutionResult:
    active_request = request or default_first_paper_session_execution_request()
    active_config = app_config or load_app_config()
    active_environ = (
        load_preflight_environment()
        if environ is None and active_request.mode == "real-paper"
        else ({} if environ is None else environ)
    )
    pre_broker_blockers = _pre_broker_blockers(active_request, active_config)
    if pre_broker_blockers:
        return _result_from_blockers(
            active_request,
            active_config,
            pre_broker_blockers,
            real_read_only_calls=False,
        )

    if active_request.mode == "fake-real-paper":
        return _run_fake_execution(active_request, active_config)

    credentials_or_blockers = _credentials_or_blockers(active_environ, active_config)
    if isinstance(credentials_or_blockers, tuple):
        return _result_from_blockers(
            active_request,
            active_config,
            credentials_or_blockers,
            real_read_only_calls=False,
        )
    settings = _settings_from_request(active_request)
    client = client_factory(credentials_or_blockers, settings)
    adapter = AlpacaPaperAdapter(
        system_config=active_config.system,
        execution_config=active_config.execution,
        client=client,
        credentials=credentials_or_blockers,
        run_mode="runtime",
    )
    return _run_adapter_execution(
        request=active_request,
        app_config=active_config,
        adapter=adapter,
        client=client,
        real_broker=True,
        real_external_calls_performed=real_external_calls_performed,
        sleeper=sleeper,
        clock=clock,
    )


def write_first_controlled_paper_session_result_artifact(
    result: FirstPaperSessionExecutionResult,
    output_path: Path | str,
) -> Path:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "milestone": "34",
        "result": {
            "status": result.status,
            "success": result.success,
            "refused": result.refused,
            "unsafe": result.unsafe,
            "blockers": result.blockers,
            "actual_paper_trading_started": result.actual_paper_trading_started,
            "real_broker_orders_submitted": result.real_broker_orders_submitted,
            "real_broker_writes_attempted": result.real_broker_writes_attempted,
            "real_read_only_alpaca_calls_performed": (
                result.real_read_only_alpaca_calls_performed
            ),
            "schedules_activated": result.schedules_activated,
            "live_trading_enabled": result.live_trading_enabled,
            "autonomous_live_execution_enabled": result.autonomous_live_execution_enabled,
            "leverage_enabled": result.leverage_enabled,
            "ai_broker_write_authority": result.ai_broker_write_authority,
            "level4_ready": result.level4_ready,
            "post_session_go_no_go": result.post_session_go_no_go,
        },
        "session_result": result.result_packet.model_dump(mode="json"),
    }
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return path


def audit_first_session_symbol_universe(
    app_config: AppConfig | None = None,
) -> FirstSessionSymbolUniverseAuditResult:
    active_config = app_config or load_app_config()
    records: list[FirstSessionSymbolAuditRecord] = []
    for symbol in active_config.live_universe.symbols:
        reason_codes: list[str] = []
        asset_class: Literal["equity", "etf"] = "etf" if symbol in ETF_SYMBOLS else "equity"
        symbol_format_valid = SYMBOL_FORMAT.fullmatch(symbol) is not None
        if not symbol_format_valid:
            reason_codes.append("symbol_format_invalid")
        if symbol in LEVERAGED_OR_INVERSE_ETF_SYMBOLS:
            reason_codes.append("leveraged_or_inverse_etf_forbidden")
        if asset_class == "etf" and not active_config.live_universe.allow_etfs:
            reason_codes.append("etfs_disabled")
        if asset_class == "equity" and not active_config.live_universe.allow_common_stocks:
            reason_codes.append("common_stocks_disabled")
        if active_config.execution.first_session_max_qty != 1:
            reason_codes.append("first_session_max_qty_not_one")
        if active_config.execution.first_session_absolute_max_notional_usd > 500.0:
            reason_codes.append("first_session_notional_ceiling_too_high")
        records.append(
            FirstSessionSymbolAuditRecord(
                symbol=symbol,
                symbol_format_valid=symbol_format_valid,
                in_allowed_universe=symbol in active_config.live_universe.symbols,
                asset_class=asset_class,
                supported_asset_class=(
                    (asset_class == "etf" and active_config.live_universe.allow_etfs)
                    or (
                        asset_class == "equity"
                        and active_config.live_universe.allow_common_stocks
                    )
                ),
                leveraged_or_inverse_marker=symbol in LEVERAGED_OR_INVERSE_ETF_SYMBOLS,
                accepted_by_first_session_envelope_logic=not reason_codes,
                reason_codes=tuple(reason_codes),
            )
        )
    return FirstSessionSymbolUniverseAuditResult(
        allowed_symbols=active_config.live_universe.symbols,
        first_session_max_quantity=active_config.execution.first_session_max_qty,
        first_session_absolute_max_notional_usd=(
            active_config.execution.first_session_absolute_max_notional_usd
        ),
        records=tuple(records),
        success=all(record.accepted_by_first_session_envelope_logic for record in records),
    )


def _validate_scenario_id(scenario_id: str) -> FirstPaperSessionScenarioId:
    if scenario_id not in FIRST_PAPER_SESSION_SCENARIO_IDS:
        allowed = ", ".join(FIRST_PAPER_SESSION_SCENARIO_IDS)
        raise ValueError(f"unknown M34 scenario_id: {scenario_id}; allowed: {allowed}")
    return cast(FirstPaperSessionScenarioId, scenario_id)


def _scenario_request(
    request: FirstPaperSessionExecutionRequest,
    scenario: FirstPaperSessionScenarioId,
) -> FirstPaperSessionExecutionRequest:
    updates: dict[str, object] = {}
    if scenario == "live_endpoint_rejected":
        updates["confirm_paper_endpoint"] = False
    elif scenario == "leverage_rejected":
        updates["current_gross_exposure"] = 1.01
    elif scenario == "missing_execution_intent":
        updates["valid_execution_intent_present"] = False
    elif scenario == "missing_idempotency_key":
        updates["idempotency_key_present"] = False
    elif scenario == "missing_protective_stop_plan":
        updates["protective_stop_plan_present"] = False
    return request.model_copy(update=updates)


def _pre_broker_blockers(
    request: FirstPaperSessionExecutionRequest,
    app_config: AppConfig,
) -> tuple[str, ...]:
    blockers: list[str] = []
    if request.mode == "fake-real-paper":
        if request.operator_approval_marker != MILESTONE_34_FAKE_OPERATOR_APPROVAL:
            blockers.append("operator_approval_missing")
    elif request.operator_approval_marker not in REAL_PAPER_OPERATOR_APPROVAL_MARKERS:
        blockers.append("operator_approval_missing")
    if request.mode == "real-paper" and not request.confirm_real_paper_writes:
        blockers.append("confirm_real_paper_writes_required")
    if request.scenario_id == "live_endpoint_rejected":
        blockers.append("live_endpoint_detected")
    for field_name, reason in (
        ("confirm_paper_endpoint", "confirm_paper_endpoint_required"),
        ("confirm_no_live_trading", "confirm_no_live_trading_required"),
        ("confirm_no_autonomous_live", "confirm_no_autonomous_live_required"),
        ("confirm_no_schedules", "confirm_no_schedules_required"),
        ("confirm_no_leverage", "confirm_no_leverage_required"),
        ("confirm_first_session_only", "confirm_first_session_only_required"),
        ("confirm_protective_stop_required", "confirm_protective_stop_required"),
        ("confirm_cleanup_policy", "confirm_cleanup_policy_required"),
    ):
        if not bool(getattr(request, field_name)):
            blockers.append(reason)
    blockers.extend(_launch_packet_blockers(request.launch_packet_path))
    if not request.target_symbol:
        blockers.append("target_symbol_required")
    else:
        if request.target_symbol not in app_config.live_universe.symbols:
            blockers.append("target_symbol_not_approved")
        if request.target_symbol in LEVERAGED_OR_INVERSE_ETF_SYMBOLS:
            blockers.append("leveraged_or_inverse_etf_forbidden")
        if request.target_symbol in ETF_SYMBOLS and not app_config.live_universe.allow_etfs:
            blockers.append("etfs_disabled")
        if (
            request.target_symbol not in ETF_SYMBOLS
            and not app_config.live_universe.allow_common_stocks
        ):
            blockers.append("common_stocks_disabled")
    blockers.extend(_order_envelope_blockers(request, app_config))
    if request.current_gross_exposure > 1.0:
        blockers.append("gross_exposure_exceeds_1x")
    if app_config.system.live_trading_enabled or app_config.execution.allow_live_orders:
        blockers.append("live_trading_enabled")
    if (
        app_config.system.autonomous_execution_enabled
        or app_config.execution.autonomous_execution_enabled
    ):
        blockers.append("autonomous_live_execution_enabled")
    if app_config.risk_level_4_micro_live.allow_margin:
        blockers.append("leverage_enabled")
    if app_config.live_universe.allow_shorting:
        blockers.append("shorting_enabled")
    if (
        app_config.live_universe.allow_options
        or app_config.live_universe.allow_futures
        or app_config.live_universe.allow_crypto
        or app_config.live_universe.allow_prediction_markets
        or app_config.live_universe.allow_leveraged_etfs
        or app_config.live_universe.allow_inverse_etfs
    ):
        blockers.append("unsupported_assets_enabled")
    if not request.valid_execution_intent_present:
        blockers.append("execution_intent_required")
    if not request.idempotency_key_present:
        blockers.append("idempotency_key_required")
    if not request.protective_stop_plan_present:
        blockers.append("protective_stop_plan_required")
    if request.scenario_id == "short_rejected":
        blockers.append("short_side_forbidden")
    if request.scenario_id == "unsupported_asset_rejected":
        blockers.append("unsupported_asset_class")
    return _unique(tuple(blockers))


def _order_envelope_blockers(
    request: FirstPaperSessionExecutionRequest,
    app_config: AppConfig,
) -> tuple[str, ...]:
    blockers: list[str] = []
    envelope = request.order_envelope
    max_quantity = app_config.execution.first_session_max_qty
    max_notional_ceiling = app_config.execution.first_session_absolute_max_notional_usd
    if envelope.max_quantity is None:
        blockers.append("max_qty_required")
    elif envelope.max_quantity > max_quantity:
        blockers.append("max_qty_exceeds_first_session_max")
    if envelope.max_notional_usd is None:
        blockers.append("max_notional_required")
    elif envelope.max_notional_usd > max_notional_ceiling:
        blockers.append("max_notional_exceeds_first_session_ceiling")
    if envelope.limit_price is None:
        blockers.append("limit_price_required")
    if envelope.entry_order_type != "limit":
        blockers.append("entry_order_type_must_be_limit")
    if envelope.time_in_force != "day":
        blockers.append("time_in_force_must_be_day")
    estimated_notional = _estimated_entry_notional(envelope)
    if (
        estimated_notional is not None
        and envelope.max_notional_usd is not None
        and estimated_notional > envelope.max_notional_usd
    ):
        blockers.append("estimated_notional_exceeds_max_notional")
    return tuple(blockers)


def _launch_packet_blockers(path: str) -> tuple[str, ...]:
    packet_path = Path(path)
    if not packet_path.is_file():
        return ("launch_packet_missing",)
    try:
        payload = json.loads(packet_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return ("launch_packet_unparseable",)
    result = payload.get("result", {})
    packet = payload.get("launch_packet", {})
    blockers: list[str] = []
    if payload.get("milestone") != "33":
        blockers.append("launch_packet_not_m33")
    if result.get("go_no_go_decision") != "go":
        blockers.append("launch_packet_not_go")
    if result.get("blockers"):
        blockers.append("launch_packet_has_blockers")
    if not result.get("read_only_broker_calls_performed"):
        blockers.append("launch_packet_read_only_preflight_missing")
    if result.get("real_broker_writes_attempted"):
        blockers.append("launch_packet_prior_broker_write_detected")
    if result.get("actual_paper_trading_started"):
        blockers.append("launch_packet_prior_paper_trading_started")
    if packet.get("broker_endpoint_mode") != "paper":
        blockers.append("launch_packet_not_paper_endpoint")
    if packet.get("open_orders_summary", {}).get("total_open_orders") != 0:
        blockers.append("launch_packet_open_orders_not_clean")
    if packet.get("positions_summary", {}).get("total_positions") != 0:
        blockers.append("launch_packet_positions_not_clean")
    if result.get("schedules_activated"):
        blockers.append("launch_packet_schedules_activated")
    if result.get("leverage_enabled"):
        blockers.append("launch_packet_leverage_enabled")
    if result.get("level4_ready"):
        blockers.append("launch_packet_level4_claim_present")
    return _unique(tuple(blockers))


def _credentials_or_blockers(
    environ: Mapping[str, str],
    app_config: AppConfig,
) -> AlpacaPaperCredentials | tuple[str, ...]:
    try:
        return validate_alpaca_paper_readonly_smoke_gates(
            environ=environ,
            app_config=app_config,
        )
    except Exception as exc:
        failed = getattr(exc, "failed_gates", None)
        if isinstance(failed, tuple):
            return tuple(f"alpaca_readonly_gate:{gate}" for gate in failed)
        return (f"alpaca_credentials_unavailable:{type(exc).__name__}",)


def _run_fake_execution(
    request: FirstPaperSessionExecutionRequest,
    app_config: AppConfig,
) -> FirstPaperSessionExecutionResult:
    client = _fake_client_for_scenario(request)
    adapter = AlpacaPaperAdapter(
        system_config=app_config.system,
        execution_config=app_config.execution,
        client=client,
        credentials=None,
        run_mode="test",
    )
    return _run_adapter_execution(
        request=request,
        app_config=app_config,
        adapter=adapter,
        client=client,
        real_broker=False,
        real_external_calls_performed=False,
        sleeper=lambda _seconds: None,
        clock=lambda: 0.0,
    )


def _run_adapter_execution(
    *,
    request: FirstPaperSessionExecutionRequest,
    app_config: AppConfig,
    adapter: AlpacaPaperAdapter,
    client: AlpacaPaperOrderLifecycleClient | FakeAlpacaClient,
    real_broker: bool,
    real_external_calls_performed: bool,
    sleeper: Callable[[float], None],
    clock: Callable[[], float],
) -> FirstPaperSessionExecutionResult:
    assert request.target_symbol is not None
    assert request.order_envelope.max_quantity is not None
    assert request.order_envelope.max_notional_usd is not None
    pre_state, pre_blockers = _pre_run_state(
        request=request,
        app_config=app_config,
        adapter=adapter,
        client=client,
    )
    if pre_blockers:
        return _result_from_blockers(
            request,
            app_config,
            pre_blockers,
            real_read_only_calls=real_external_calls_performed,
            pre_state=pre_state,
        )
    intent = _build_execution_intent(request, app_config)
    stop_plan = _stop_plan_from_intent(intent)
    writes: list[BrokerWriteRecord] = []
    incidents: list[str] = []
    entry_order: BrokerOrder | None = None
    stop_order: BrokerOrder | None = None
    entry_status: str | None = None
    fill_status = "not_submitted"
    filled_quantity = 0.0
    fill_id: str | None = None
    stop_verification = "not_required_no_fill"
    cleanup_actions: list[str] = []
    real_write_attempted = False

    entry_result = adapter.submit_entry_order(intent)
    real_write_attempted = real_broker
    writes.append(
        BrokerWriteRecord(
            operation="submit_entry_order",
            attempted=True,
            broker_order_id=(
                None if entry_result.order is None else entry_result.order.broker_order_id
            ),
            client_order_id=intent.client_order_id_root,
            status=entry_result.status,
            fake_only=not real_broker,
        )
    )
    if entry_result.order is None or entry_result.status not in {"succeeded", "ambiguous"}:
        return _build_result(
            request=request,
            app_config=app_config,
            pre_state=pre_state,
            status="incident" if entry_result.status == "ambiguous" else "refused",
            blockers=(f"entry_submit_failed:{entry_result.status}",),
            entry_order=None,
            entry_status=entry_result.status,
            fill_status="not_filled",
            filled_quantity=0.0,
            fill_id=None,
            stop_plan=stop_plan,
            stop_order=None,
            stop_verification="not_reached",
            cleanup_actions=tuple(cleanup_actions),
            incidents=("entry_submit_ambiguous",) if entry_result.status == "ambiguous" else (),
            writes=tuple(writes),
            real_broker=real_broker,
            real_read_only_calls=real_external_calls_performed,
            real_write_attempted=real_write_attempted,
        )
    entry_order = _poll_order(
        adapter,
        client_order_id=intent.client_order_id_root,
        initial_order=entry_result.order,
        timeout_seconds=0.0 if not real_broker else 15.0,
        sleeper=sleeper,
        clock=clock,
    )
    entry_status = entry_order.status
    filled_quantity = entry_order.filled_quantity
    fill_status = _fill_status(entry_order)
    fill_id = _fill_id(adapter, entry_order.client_order_id)

    if filled_quantity <= 0:
        if entry_order.is_open:
            cancel = adapter.cancel_order(entry_order.client_order_id)
            writes.append(
                BrokerWriteRecord(
                    operation="cancel_unfilled_entry",
                    attempted=True,
                    broker_order_id=None if cancel.order is None else cancel.order.broker_order_id,
                    client_order_id=entry_order.client_order_id,
                    status=cancel.status,
                    fake_only=not real_broker,
                )
            )
            cleanup_actions.append("cancel_unfilled_entry")
            real_write_attempted = real_write_attempted or real_broker
        return _build_result(
            request=request,
            app_config=app_config,
            pre_state=pre_state,
            status="executed",
            blockers=(),
            entry_order=entry_order,
            entry_status=entry_status,
            fill_status=fill_status,
            filled_quantity=filled_quantity,
            fill_id=fill_id,
            stop_plan=stop_plan,
            stop_order=None,
            stop_verification=stop_verification,
            cleanup_actions=tuple(cleanup_actions),
            incidents=(),
            writes=tuple(writes),
            real_broker=real_broker,
            real_read_only_calls=real_external_calls_performed,
            real_write_attempted=real_write_attempted,
        )

    if request.scenario_id == "missing_stop_verification":
        incidents.append("critical_missing_protective_stop_verification")
        stop_verification = "not_verified"
    else:
        stop_result = adapter.submit_protective_stop(intent, filled_quantity=filled_quantity)
        stop_order = stop_result.order
        writes.append(
            BrokerWriteRecord(
                operation="submit_protective_stop",
                attempted=True,
                broker_order_id=None if stop_order is None else stop_order.broker_order_id,
                client_order_id=None if stop_order is None else stop_order.client_order_id,
                status=stop_result.status,
                fake_only=not real_broker,
            )
        )
        real_write_attempted = real_write_attempted or real_broker
        if stop_order is None or stop_result.status != "succeeded":
            incidents.append("critical_protective_stop_submit_failed")
            stop_verification = "not_verified"
        else:
            verification = adapter.verify_protective_stop(
                symbol=request.target_symbol,
                required_quantity=filled_quantity,
                client_order_id=stop_order.client_order_id,
            )
            stop_verification = "verified" if verification.protected else "not_verified"
            if not verification.protected:
                incidents.append("critical_missing_protective_stop_verification")

    if fill_status == "partial_fill" and entry_order.is_open:
        cancel = adapter.cancel_order(entry_order.client_order_id)
        writes.append(
            BrokerWriteRecord(
                operation="cancel_unfilled_remainder",
                attempted=True,
                broker_order_id=None if cancel.order is None else cancel.order.broker_order_id,
                client_order_id=entry_order.client_order_id,
                status=cancel.status,
                fake_only=not real_broker,
            )
        )
        cleanup_actions.append("cancel_unfilled_remainder")
        real_write_attempted = real_write_attempted or real_broker

    return _build_result(
        request=request,
        app_config=app_config,
        pre_state=pre_state,
        status="incident" if incidents else "executed",
        blockers=(),
        entry_order=entry_order,
        entry_status=entry_status,
        fill_status=fill_status,
        filled_quantity=filled_quantity,
        fill_id=fill_id,
        stop_plan=stop_plan,
        stop_order=stop_order,
        stop_verification=stop_verification,
        cleanup_actions=tuple(cleanup_actions),
        incidents=tuple(incidents),
        writes=tuple(writes),
        real_broker=real_broker,
        real_read_only_calls=real_external_calls_performed,
        real_write_attempted=real_write_attempted,
    )


def _pre_run_state(
    *,
    request: FirstPaperSessionExecutionRequest,
    app_config: AppConfig,
    adapter: AlpacaPaperAdapter,
    client: AlpacaPaperOrderLifecycleClient | FakeAlpacaClient,
) -> tuple[BrokerStateSummary, tuple[str, ...]]:
    target = request.target_symbol or ""
    try:
        account = adapter.account_snapshot()
        clock_snapshot = map_alpaca_clock(client.get_clock())
        open_orders = adapter.open_orders()
        positions = adapter.positions()
    except AlpacaClientError as exc:
        fallback = BrokerStateSummary(
            account_reachable=False,
            clock_reachable=False,
            clock_is_open=None,
            open_orders_status="not_reached",
            open_order_count=0,
            target_symbol_open_order_count=0,
            positions_status="not_reached",
            position_count=0,
            target_symbol_position_quantity=0.0,
            reconciliation_clean=False,
        )
        return fallback, (f"broker_preflight_error:{exc.code}",)
    target_open = tuple(order for order in open_orders if order.symbol == target and order.is_open)
    target_positions = tuple(position for position in positions if position.symbol == target)
    target_quantity = sum(position.quantity for position in target_positions)
    clean = not target_open and abs(target_quantity) <= 1e-9
    state = BrokerStateSummary(
        account_reachable=True,
        clock_reachable=True,
        clock_is_open=clock_snapshot.is_open,
        open_orders_status="clean" if not target_open else "target_open_orders_present",
        open_order_count=len(open_orders),
        target_symbol_open_order_count=len(target_open),
        positions_status="clean" if abs(target_quantity) <= 1e-9 else "target_position_present",
        position_count=len(positions),
        target_symbol_position_quantity=target_quantity,
        reconciliation_clean=clean,
    )
    blockers: list[str] = []
    if not clock_snapshot.is_open:
        blockers.append("market_clock_not_open")
    if request.scenario_id == "dirty_reconciliation_blocks":
        blockers.append("pre_run_reconciliation_not_clean")
    if target_open or request.scenario_id == "existing_open_orders":
        blockers.append("existing_target_symbol_open_order")
    if abs(target_quantity) > 1e-9 or request.scenario_id == "existing_position":
        blockers.append("existing_target_symbol_position")
    if not clean:
        blockers.append("pre_run_reconciliation_not_clean")
    _ = account
    return state, _unique(tuple(blockers))


def _settings_from_request(
    request: FirstPaperSessionExecutionRequest,
) -> AlpacaPaperOrderLifecycleSmokeSettings:
    if request.target_symbol is None:
        raise ValueError("target_symbol is required")
    if request.order_envelope.max_quantity is None:
        raise ValueError("max_quantity is required")
    if request.order_envelope.max_notional_usd is None:
        raise ValueError("max_notional_usd is required")
    return AlpacaPaperOrderLifecycleSmokeSettings(
        symbol=request.target_symbol,
        quantity=request.order_envelope.max_quantity,
        max_notional_usd=request.order_envelope.max_notional_usd,
        timeout_seconds=0,
    )


def _estimated_entry_notional(envelope: OrderEnvelope) -> float | None:
    if envelope.max_quantity is None or envelope.limit_price is None:
        return None
    return round(float(envelope.max_quantity) * envelope.limit_price, 6)


def _build_execution_intent(
    request: FirstPaperSessionExecutionRequest,
    app_config: AppConfig,
) -> ExecutionIntent:
    assert request.target_symbol is not None
    assert request.order_envelope.max_quantity is not None
    assert request.order_envelope.limit_price is not None
    limit_price = request.order_envelope.limit_price
    stop_price = request.order_envelope.stop_loss_price or max(
        0.01,
        round(limit_price * (1.0 - request.order_envelope.stop_loss_percent), 2),
    )
    timestamp = request.started_at.strftime("%Y%m%dT%H%M%SZ")
    digest = short_hash(f"{request.target_symbol}-{timestamp}-{limit_price}", 8)
    client_order_id = f"{M34_CLIENT_ORDER_PREFIX}-{request.target_symbol}-{timestamp}-{digest}"
    decision_id = uuid5(NAMESPACE_URL, f"m34-decision:{client_order_id}")
    return ExecutionIntent(
        decision_id=decision_id,
        symbol=request.target_symbol,
        side="buy",
        asset_class="etf" if request.target_symbol in ETF_SYMBOLS else "equity",
        quantity=request.order_envelope.max_quantity,
        entry_order_type="limit",
        limit_price=limit_price,
        stop_loss_price=stop_price,
        time_in_force="day",
        strategy_version=M34_STRATEGY_VERSION,
        risk_config_version=M34_RISK_CONFIG_VERSION,
        autonomy_level=app_config.system.autonomy_level,
        requires_protective_stop=True,
        max_acceptable_slippage_bps=app_config.execution.max_acceptable_slippage_bps,
        expires_at=request.started_at + timedelta(minutes=15),
        client_order_id_root=client_order_id,
        status="risk_approved",
        temporal_workflow_id=None,
    )


def _stop_plan_from_intent(intent: ExecutionIntent) -> ProtectiveStopPlan:
    return ProtectiveStopPlan(
        plan_id=f"stop-plan-{intent.client_order_id_root}",
        required=True,
        stop_loss_price=intent.stop_loss_price,
        stop_loss_percent=0.5,
        status="planned",
    )


def _poll_order(
    adapter: AlpacaPaperAdapter,
    *,
    client_order_id: str,
    initial_order: BrokerOrder,
    timeout_seconds: float,
    sleeper: Callable[[float], None],
    clock: Callable[[], float],
) -> BrokerOrder:
    order = initial_order
    if order.status in {"filled", "cancelled", "expired", "rejected"} or order.filled_quantity > 0:
        return order
    deadline = clock() + timeout_seconds
    while clock() < deadline:
        latest = adapter.order_by_client_order_id(client_order_id)
        if latest is not None:
            order = latest
        if (
            order.status in {"filled", "cancelled", "expired", "rejected"}
            or order.filled_quantity > 0
        ):
            return order
        sleeper(min(1.0, max(0.0, deadline - clock())))
    latest = adapter.order_by_client_order_id(client_order_id)
    return order if latest is None else latest


def _fill_status(order: BrokerOrder) -> str:
    if order.filled_quantity <= 0:
        return "not_filled"
    if order.filled_quantity < order.quantity:
        return "partial_fill"
    return "filled"


def _fill_id(adapter: AlpacaPaperAdapter, client_order_id: str) -> str | None:
    fills = tuple(
        fill for fill in adapter.recent_fills() if fill.client_order_id == client_order_id
    )
    return None if not fills else fills[-1].broker_fill_id


def _result_from_blockers(
    request: FirstPaperSessionExecutionRequest,
    app_config: AppConfig,
    blockers: tuple[str, ...],
    *,
    real_read_only_calls: bool,
    pre_state: BrokerStateSummary | None = None,
) -> FirstPaperSessionExecutionResult:
    fallback_state = pre_state or BrokerStateSummary(
        account_reachable=False,
        clock_reachable=False,
        clock_is_open=None,
        open_orders_status="not_reached",
        open_order_count=0,
        target_symbol_open_order_count=0,
        positions_status="not_reached",
        position_count=0,
        target_symbol_position_quantity=0.0,
        reconciliation_clean=False,
    )
    packet = _packet(
        request=request,
        app_config=app_config,
        status="refused",
        blockers=blockers,
        pre_state=fallback_state,
        entry_order=None,
        entry_status=None,
        fill_status="not_reached",
        filled_quantity=0.0,
        fill_id=None,
        stop_plan=ProtectiveStopPlan(
            plan_id=None,
            required=True,
            stop_loss_price=None,
            stop_loss_percent=request.order_envelope.stop_loss_percent,
            status="not_reached",
        ),
        stop_order=None,
        stop_verification="not_reached",
        cleanup_actions=(),
        incidents=(),
        writes=(),
        real_broker=request.mode == "real-paper",
        real_read_only_calls=real_read_only_calls,
        real_write_attempted=False,
    )
    return FirstPaperSessionExecutionResult(
        mode=request.mode,
        scenario_id=request.scenario_id,
        status="refused",
        success=False,
        refused=True,
        unsafe=False,
        blockers=_unique(blockers),
        result_packet=packet,
        actual_paper_trading_started=False,
        real_broker_orders_submitted=False,
        real_broker_writes_attempted=False,
        real_read_only_alpaca_calls_performed=real_read_only_calls,
        post_session_go_no_go="no_go",
    )


def _build_result(
    *,
    request: FirstPaperSessionExecutionRequest,
    app_config: AppConfig,
    pre_state: BrokerStateSummary,
    status: FirstPaperSessionStatus,
    blockers: tuple[str, ...],
    entry_order: BrokerOrder | None,
    entry_status: str | None,
    fill_status: str,
    filled_quantity: float,
    fill_id: str | None,
    stop_plan: ProtectiveStopPlan,
    stop_order: BrokerOrder | None,
    stop_verification: str,
    cleanup_actions: tuple[str, ...],
    incidents: tuple[str, ...],
    writes: tuple[BrokerWriteRecord, ...],
    real_broker: bool,
    real_read_only_calls: bool,
    real_write_attempted: bool,
) -> FirstPaperSessionExecutionResult:
    packet = _packet(
        request=request,
        app_config=app_config,
        status=status,
        blockers=blockers,
        pre_state=pre_state,
        entry_order=entry_order,
        entry_status=entry_status,
        fill_status=fill_status,
        filled_quantity=filled_quantity,
        fill_id=fill_id,
        stop_plan=stop_plan,
        stop_order=stop_order,
        stop_verification=stop_verification,
        cleanup_actions=cleanup_actions,
        incidents=incidents,
        writes=writes,
        real_broker=real_broker,
        real_read_only_calls=real_read_only_calls,
        real_write_attempted=real_write_attempted,
    )
    unsafe = status == "incident"
    success = status == "executed" and not incidents
    return FirstPaperSessionExecutionResult(
        mode=request.mode,
        scenario_id=request.scenario_id,
        status=status,
        success=success,
        refused=status == "refused",
        unsafe=unsafe,
        blockers=_unique(blockers),
        result_packet=packet,
        actual_paper_trading_started=real_broker and real_write_attempted,
        real_broker_orders_submitted=real_broker
        and any(write.operation == "submit_entry_order" for write in writes),
        real_broker_writes_attempted=real_broker and real_write_attempted,
        real_read_only_alpaca_calls_performed=real_read_only_calls,
        post_session_go_no_go="post_session_audit_only" if success else "no_go",
    )


def _packet(
    *,
    request: FirstPaperSessionExecutionRequest,
    app_config: AppConfig,
    status: FirstPaperSessionStatus,
    blockers: tuple[str, ...],
    pre_state: BrokerStateSummary,
    entry_order: BrokerOrder | None,
    entry_status: str | None,
    fill_status: str,
    filled_quantity: float,
    fill_id: str | None,
    stop_plan: ProtectiveStopPlan,
    stop_order: BrokerOrder | None,
    stop_verification: str,
    cleanup_actions: tuple[str, ...],
    incidents: tuple[str, ...],
    writes: tuple[BrokerWriteRecord, ...],
    real_broker: bool,
    real_read_only_calls: bool,
    real_write_attempted: bool,
) -> FirstPaperSessionResultPacket:
    _ = real_read_only_calls
    target = request.target_symbol
    decision_id = None if target is None else str(uuid5(NAMESPACE_URL, f"m34-decision:{target}"))
    client_order_id = None if entry_order is None else entry_order.client_order_id
    post_open, post_positions = _post_summaries(
        pre_state=pre_state,
        filled_quantity=filled_quantity,
        stop_verification=stop_verification,
        status=status,
    )
    actual_started = real_broker and real_write_attempted
    packet_key = (
        f"m34-result:{request.mode}:{request.scenario_id}:"
        f"{request.started_at.isoformat()}"
    )
    endpoint_proof = (
        "paper_endpoint_confirmed" if request.confirm_paper_endpoint else "not_confirmed"
    )
    envelope_reasons = tuple(
        blocker for blocker in blockers if blocker in _ORDER_ENVELOPE_BLOCKER_CODES
    )
    estimated_notional = _estimated_entry_notional(request.order_envelope)
    return FirstPaperSessionResultPacket(
        result_packet_id=str(uuid5(NAMESPACE_URL, packet_key)),
        timestamp=request.started_at,
        operator_approval_marker=request.operator_approval_marker,
        commit_hash=_git_commit_or_unavailable(),
        latest_spec_path=f"docs/app/{FIRST_SESSION_SPEC_VERSION}",
        spec_version=FIRST_SESSION_SPEC_VERSION,
        launch_packet_reference=request.launch_packet_path,
        target_symbol=target,
        order_envelope=request.order_envelope,
        estimated_entry_notional_usd=estimated_notional,
        first_session_max_quantity=app_config.execution.first_session_max_qty,
        first_session_absolute_max_notional_usd=(
            app_config.execution.first_session_absolute_max_notional_usd
        ),
        symbol_allowlist_decision=_symbol_allowlist_decision(target, app_config),
        order_envelope_validation_result="failed" if envelope_reasons else "passed",
        order_envelope_rejection_reasons=envelope_reasons,
        paper_endpoint_proof=endpoint_proof,
        live_endpoint_rejection_proof="live_endpoint_not_used",
        pre_run_broker_state=pre_state,
        pre_run_reconciliation_result="clean" if pre_state.reconciliation_clean else "not_clean",
        candidate_id=None if target is None else f"candidate-{target}-m34",
        ai_news_neutral_fallback_marker="neutral_fake_ai_news_no_broker_authority",
        decision_id=decision_id,
        risk_check_id=None if target is None else f"risk-check-{target}-m34",
        execution_intent_id=None if client_order_id is None else f"intent-{client_order_id}",
        client_order_id=client_order_id,
        broker_order_id=None if entry_order is None else entry_order.broker_order_id,
        entry_order_status=entry_status,
        fill_status=fill_status,
        filled_quantity=filled_quantity,
        fill_id=fill_id,
        protective_stop_plan=stop_plan,
        protective_stop_order_id=None if stop_order is None else stop_order.broker_order_id,
        protective_stop_verification_result=stop_verification,
        cleanup_flatten_policy=request.cleanup_policy,
        cleanup_actions=cleanup_actions,
        post_run_open_orders_summary=post_open,
        post_run_positions_summary=post_positions,
        post_run_reconciliation_result=(
            "clean_for_protected_session_position"
            if status == "executed" and not incidents
            else "not_clean_or_not_reached"
        ),
        incidents=incidents,
        fake_alert_summary="fake_alert_summary_only",
        report_summary="local_result_packet_generated",
        dashboard_read_model_summary="local_packet_available",
        actual_paper_trading_started=actual_started,
        real_broker_orders_submitted=real_broker
        and any(write.operation == "submit_entry_order" for write in writes),
        real_broker_writes_attempted=real_broker and real_write_attempted,
        broker_writes=writes,
        live_trading_enabled=False,
        autonomous_live_execution_enabled=False,
        leverage_enabled=False,
        post_session_recommendation=(
            "post_session_audit_required_before_repetition"
            if status == "executed" and not incidents and not blockers
            else "do_not_repeat_until_blockers_cleared"
        ),
    )


def _post_summaries(
    *,
    pre_state: BrokerStateSummary,
    filled_quantity: float,
    stop_verification: str,
    status: FirstPaperSessionStatus,
) -> tuple[str, str]:
    if status == "refused":
        return pre_state.open_orders_status, pre_state.positions_status
    if filled_quantity <= 0:
        return "entry_cancelled_or_unfilled", "clean"
    if stop_verification == "verified":
        return "protective_stop_open", "protected_position_open"
    return "missing_verified_protective_stop", "position_requires_incident_review"


def _symbol_allowlist_decision(target: str | None, app_config: AppConfig) -> str:
    if target is None:
        return "missing_target_symbol"
    if target not in app_config.live_universe.symbols:
        return "target_symbol_not_approved"
    if target in LEVERAGED_OR_INVERSE_ETF_SYMBOLS:
        return "leveraged_or_inverse_etf_forbidden"
    if target in ETF_SYMBOLS and not app_config.live_universe.allow_etfs:
        return "etfs_disabled"
    if target not in ETF_SYMBOLS and not app_config.live_universe.allow_common_stocks:
        return "common_stocks_disabled"
    return "approved"


def _fake_client_for_scenario(request: FirstPaperSessionExecutionRequest) -> FakeAlpacaClient:
    target = request.target_symbol or "AAPL"
    orders: tuple[Mapping[str, Any], ...] = ()
    positions: tuple[Mapping[str, Any], ...] = ()
    if request.scenario_id == "existing_open_orders":
        orders = (_fake_order_payload(target),)
    if request.scenario_id == "existing_position":
        positions = (_fake_position_payload(target),)
    outcomes: tuple[tuple[str, float], ...]
    if request.scenario_id == "no_fill":
        outcomes = (("accepted", 0.0),)
    elif request.scenario_id == "partial_fill":
        outcomes = (("partially_filled", 0.5), ("accepted", 0.0))
    else:
        outcomes = (("filled", 1.0), ("accepted", 0.0))
    return FakeAlpacaClient(
        orders=orders,
        positions=positions,
        submit_outcomes=outcomes,
        mutate_positions_on_submit=True,
    )


def _fake_order_payload(symbol: str) -> dict[str, Any]:
    return {
        "id": "existing-order-1",
        "client_order_id": f"manual-{symbol}-order",
        "symbol": symbol,
        "side": "buy",
        "asset_class": "equity",
        "qty": "1",
        "filled_qty": "0",
        "type": "limit",
        "time_in_force": "day",
        "status": "accepted",
        "limit_price": "1",
        "submitted_at": M34_STARTED_AT.isoformat().replace("+00:00", "Z"),
    }


def _fake_position_payload(symbol: str) -> dict[str, Any]:
    return {
        "symbol": symbol,
        "asset_class": "equity",
        "qty": "1",
        "avg_entry_price": "1",
        "market_value": "1",
    }


def _git_commit_or_unavailable() -> str:
    import subprocess

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
