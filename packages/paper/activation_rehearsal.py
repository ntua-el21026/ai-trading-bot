"""Milestone 44D paper-only short and scale-in activation rehearsal helpers.

This module is deliberately narrow orchestration tooling. It may submit real Alpaca paper orders
only after the explicit M44D approval marker and safety confirmations are present. It never starts
M45, never activates schedules, and never targets live trading endpoints.
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Literal, Protocol, Self, cast
from uuid import NAMESPACE_URL, uuid5

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from packages.broker.alpaca import (
    ALPACA_PAPER_BASE_URL,
    AlpacaClientError,
    AlpacaPaperCredentials,
    build_alpaca_auth_headers,
    map_alpaca_account,
    map_alpaca_clock,
    map_alpaca_order,
    map_alpaca_position,
)
from packages.broker.models import BrokerAccountSnapshot, BrokerClockSnapshot, BrokerOrder
from packages.broker.order_lifecycle_smoke import AlpacaPaperOrderLifecycleHttpClient
from packages.core.config import AppConfig, load_app_config
from packages.execution.idempotency import short_hash
from packages.execution.models import ExecutionIntent
from packages.paper.preflight import load_preflight_environment
from packages.risk.shorts import (
    ShortAccountSnapshot,
    ShortAssetSnapshot,
    ShortEntryRiskInput,
    evaluate_short_entry_risk,
)

M44D_APPROVAL = "MILESTONE_44D_SHORT_AND_SCALE_IN_REHEARSAL_AND_LONG_SHORT_SCALEIN_READINESS"
ACTIVATION_REHEARSAL_M44D_EVIDENCE_PATH = "docs/evidence/activation_rehearsal_m44d.json"
FROZEN_READINESS_M44D_EVIDENCE_PATH = "docs/evidence/frozen_readiness_m44d.json"
LATEST_V06_SPEC_PATH = "docs/app/Autonomous_AI_Trading_Bot_SPEC_v0.6.md"
FLAT_START_CLEANUP_M44_EVIDENCE_PATH = "docs/evidence/flat_start_cleanup_m44.json"
PRIMARY_SIGNAL_DATA_GATE_M44C_EVIDENCE_PATH = (
    "docs/evidence/primary_signal_data_gate_m44c.json"
)
FROZEN_READINESS_M44C_EVIDENCE_PATH = "docs/evidence/frozen_readiness_m44c.json"

ALPACA_MARKET_DATA_BASE_URL = "https://data.alpaca.markets"
SHORT_CANDIDATES = ("IWM", "SPY")
SCALE_IN_CANDIDATES = ("XLK", "XLF")
SHORT_MAX_NOTIONAL_USD = 1000.0
SCALE_TOTAL_NOTIONAL_CAPS_USD = {"XLK": 600.0, "XLF": 300.0}
SENSITIVE_TOKEN_NAMES = (
    "DATABASE_URL",
    "TEMPORAL_NAMESPACE",
    "TEMPORAL_ADDRESS",
    "TEMPORAL_API_KEY",
    "ALPACA_API_KEY",
    "ALPACA_SECRET_KEY",
    "ALPACA_BASE_URL",
    "TIINGO_API_KEY",
    "MARKETAUX_API_KEY",
    "ALPHA_VANTAGE_API_KEY",
    "OPENAI_API_KEY",
    "TELEGRAM_BOT_TOKEN",
    "TELEGRAM_CHAT_ID",
)

Sleeper = Callable[[float], None]
Clock = Callable[[], float]


class ActivationRehearsalClient(Protocol):
    def get_account(self) -> Mapping[str, Any]:
        """Return an Alpaca-like paper account payload."""

    def get_clock(self) -> Mapping[str, Any]:
        """Return an Alpaca-like clock payload."""

    def list_open_orders(self) -> Sequence[Mapping[str, Any]]:
        """Return open orders."""

    def list_positions(self) -> Sequence[Mapping[str, Any]]:
        """Return current positions."""

    def get_position(self, symbol: str) -> Mapping[str, Any] | None:
        """Return one current position, if any."""

    def get_order_by_id(self, broker_order_id: str) -> Mapping[str, Any] | None:
        """Return an order by broker ID."""

    def get_order_by_client_order_id(self, client_order_id: str) -> Mapping[str, Any] | None:
        """Return an order by client order ID."""

    def submit_order(self, request: Mapping[str, Any]) -> Mapping[str, Any]:
        """Submit a paper order."""

    def cancel_order(self, broker_order_id: str) -> Mapping[str, Any]:
        """Cancel a paper order."""

    def get_asset(self, symbol: str) -> Mapping[str, Any] | None:
        """Return an Alpaca-like asset payload."""

    def get_latest_trade_price(self, symbol: str) -> float | None:
        """Return a latest paper-safe execution reference price."""


class ActivationRehearsalClientFactory(Protocol):
    def __call__(
        self,
        credentials: AlpacaPaperCredentials,
        timeout_seconds: float,
    ) -> ActivationRehearsalClient:
        """Build a client only after M44D gates pass."""


class ActivationRehearsalModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ActivationRehearsalRequest(ActivationRehearsalModel):
    mode: Literal["fake", "real-paper"] = "fake"
    rehearsal_mode: Literal["short", "scale-in", "full"] = "full"
    operator_approval: str | None = None
    short_primary_symbol: str = "IWM"
    short_fallback_symbol: str = "SPY"
    scale_primary_symbol: str = "XLK"
    scale_fallback_symbol: str = "XLF"
    short_max_qty: int = Field(default=1, gt=0, le=1)
    scale_initial_max_qty: int = Field(default=1, gt=0, le=1)
    scale_addon_max_qty: int = Field(default=1, gt=0, le=1)
    confirm_paper_endpoint: bool = False
    confirm_short_rehearsal_only: bool = False
    confirm_scale_in_rehearsal_only: bool = False
    confirm_protective_buy_stop_required: bool = False
    confirm_additive_sell_stop_required: bool = False
    confirm_cleanup_to_flat: bool = False
    confirm_no_live_trading: bool = False
    confirm_no_autonomous_live: bool = False
    confirm_no_schedules: bool = False
    confirm_no_leverage: bool = False
    confirm_no_frozen_validation_start: bool = False
    confirm_level4_not_ready: bool = False
    timeout_seconds: float = Field(default=45.0, ge=0, le=180.0)

    @field_validator(
        "short_primary_symbol",
        "short_fallback_symbol",
        "scale_primary_symbol",
        "scale_fallback_symbol",
        mode="before",
    )
    @classmethod
    def normalize_symbol(cls, value: object) -> str:
        return str(value).strip().upper()

    @model_validator(mode="after")
    def validate_approved_candidates(self) -> Self:
        if (self.short_primary_symbol, self.short_fallback_symbol) != SHORT_CANDIDATES:
            raise ValueError("M44D short rehearsal candidates must be IWM then SPY")
        if (self.scale_primary_symbol, self.scale_fallback_symbol) != SCALE_IN_CANDIDATES:
            raise ValueError("M44D scale-in rehearsal candidates must be XLK then XLF")
        return self


class BrokerStateSummary(ActivationRehearsalModel):
    account_reachable: bool
    clock_reachable: bool
    clock_is_open: bool | None
    paper_endpoint_proven: bool
    open_orders_count: int = Field(ge=0)
    positions_count: int = Field(ge=0)
    reconciliation_summary: str
    symbols_with_open_orders: tuple[str, ...]
    symbols_with_positions: tuple[str, ...]


class AssetShortabilitySnapshot(ActivationRehearsalModel):
    symbol: str
    asset_class: str
    tradable: bool | None
    marginable: bool | None
    shortable: bool | None
    easy_to_borrow: bool | None


class AccountShortingSnapshot(ActivationRehearsalModel):
    environment: Literal["paper"] = "paper"
    shorting_enabled: bool | None
    equity_available: bool
    equity_above_2000: bool | None


class OrderRequestSummary(ActivationRehearsalModel):
    symbol: str
    side: Literal["buy", "sell"]
    quantity: float = Field(gt=0)
    order_type: Literal["market", "limit", "stop"]
    time_in_force: str
    role: str
    limit_price: float | None = None
    stop_price: float | None = None
    client_order_id_present: bool


class OrderResultSummary(ActivationRehearsalModel):
    submitted: bool
    status: str
    side: Literal["buy", "sell"] | None = None
    filled_quantity: float = Field(default=0.0, ge=0)
    broker_order_id_present: bool = False
    client_order_id_present: bool = False
    reason: str | None = None


class StopVerificationSummary(ActivationRehearsalModel):
    verified: bool
    side: Literal["buy", "sell"] | None
    required_quantity: float = Field(ge=0)
    verified_quantity: float = Field(ge=0)
    broker_order_id_present: bool = False
    client_order_id_present: bool = False
    status: str | None = None
    reason: str | None = None


class AggregateProtectionSummary(ActivationRehearsalModel):
    passed: bool
    position_quantity: float
    protected_quantity_sum: float = Field(ge=0)
    reason_code: str


class ShortRehearsalSummary(ActivationRehearsalModel):
    selected_symbol: str | None = None
    fallback_used: bool = False
    asset_shortability_snapshot: AssetShortabilitySnapshot | None = None
    account_shorting_snapshot: AccountShortingSnapshot | None = None
    short_order_request_summary: OrderRequestSummary | None = None
    short_entry_result: OrderResultSummary | None = None
    fill_result: OrderResultSummary | None = None
    signed_position_result: dict[str, float | str | bool] = Field(default_factory=dict)
    protective_buy_stop_request_summary: OrderRequestSummary | None = None
    protective_buy_stop_verification: StopVerificationSummary | None = None
    aggregate_short_protection_check: AggregateProtectionSummary | None = None
    cleanup_stop_cancel_result: str | None = None
    buy_to_cover_result: OrderResultSummary | None = None
    emergency_reprotect_result: StopVerificationSummary | None = None
    final_open_orders_count: int = Field(default=0, ge=0)
    final_positions_count: int = Field(default=0, ge=0)
    final_reconciliation: str = "not_run"
    succeeded: bool = False
    broker_writes_performed: bool = False
    blockers: tuple[str, ...] = ()


class ScaleInRehearsalSummary(ActivationRehearsalModel):
    selected_symbol: str | None = None
    fallback_used: bool = False
    initial_entry_request_summary: OrderRequestSummary | None = None
    initial_entry_result: OrderResultSummary | None = None
    initial_fill_result: OrderResultSummary | None = None
    initial_protective_stop_result: StopVerificationSummary | None = None
    scale_in_entry_request_summary: OrderRequestSummary | None = None
    scale_in_fill_result: OrderResultSummary | None = None
    additive_protective_stop_result: StopVerificationSummary | None = None
    aggregate_long_protection_check: AggregateProtectionSummary | None = None
    cleanup_stop_cancel_result: str | None = None
    cleanup_sell_result: OrderResultSummary | None = None
    emergency_reprotect_result: StopVerificationSummary | None = None
    final_open_orders_count: int = Field(default=0, ge=0)
    final_positions_count: int = Field(default=0, ge=0)
    final_reconciliation: str = "not_run"
    succeeded: bool = False
    broker_writes_performed: bool = False
    blockers: tuple[str, ...] = ()


class ActivationRehearsalPacket(ActivationRehearsalModel):
    packet_id: str
    timestamp: datetime
    latest_spec_path: str = LATEST_V06_SPEC_PATH
    latest_spec_version: Literal["v0.6"] = "v0.6"
    operator_approval_marker: str | None
    pre_run_broker_state: BrokerStateSummary
    short_rehearsal: ShortRehearsalSummary
    scale_in_rehearsal: ScaleInRehearsalSummary
    broker_writes_performed: bool
    real_short_broker_write_performed: bool
    real_scale_in_broker_write_performed: bool
    schedules_activated: bool = False
    frozen_validation_started: bool = False
    live_trading_enabled: bool = False
    autonomous_live_execution_enabled: bool = False
    leverage_enabled: bool = False
    level4_ready: bool = False
    final_broker_baseline: BrokerStateSummary
    m45_long_short_scalein_readiness: bool
    blockers: tuple[str, ...]


class FrozenReadinessM44DPacket(ActivationRehearsalModel):
    packet_id: str
    timestamp: datetime
    latest_spec_path: str = LATEST_V06_SPEC_PATH
    latest_spec_version: Literal["v0.6"] = "v0.6"
    flat_start_cleanup_m44_packet_reference: str = FLAT_START_CLEANUP_M44_EVIDENCE_PATH
    primary_signal_data_gate_m44c_packet_reference: str = (
        PRIMARY_SIGNAL_DATA_GATE_M44C_EVIDENCE_PATH
    )
    frozen_readiness_m44c_packet_reference: str = FROZEN_READINESS_M44C_EVIDENCE_PATH
    activation_rehearsal_m44d_packet_reference: str = ACTIVATION_REHEARSAL_M44D_EVIDENCE_PATH
    tiingo_gate_status: str
    final_broker_baseline: BrokerStateSummary
    short_rehearsal_succeeded: bool
    scale_in_rehearsal_succeeded: bool
    shorts_enabled_at_validation_start: bool
    scale_in_enabled_at_validation_start: bool
    short_universe: tuple[str, ...]
    live_shorting_enabled: bool = False
    short_scale_in_enabled_at_validation_start: bool = False
    m45_readiness: bool
    operator_approval_required_for_m45: bool = True
    blockers: tuple[str, ...]
    schedules_activated: bool = False
    frozen_validation_started: bool = False
    live_trading_enabled: bool = False
    autonomous_live_execution_enabled: bool = False
    leverage_enabled: bool = False
    level4_ready: bool = False


class ActivationRehearsalResult(ActivationRehearsalModel):
    success: bool
    go_no_go: Literal["go", "no_go"]
    packet: ActivationRehearsalPacket
    readiness_packet: FrozenReadinessM44DPacket
    blockers: tuple[str, ...]
    broker_writes_performed: bool
    real_broker_writes_performed: bool


class AlpacaActivationRehearsalHttpClient(AlpacaPaperOrderLifecycleHttpClient):
    """Write-capable paper client plus read-only asset and trade-price checks."""

    def __init__(
        self,
        *,
        credentials: AlpacaPaperCredentials,
        timeout_seconds: float,
        opener: Any | None = None,
    ) -> None:
        super().__init__(
            credentials=credentials,
            timeout_seconds=timeout_seconds,
            opener=opener,
        )
        self._credentials = credentials
        self._timeout_seconds = timeout_seconds
        self._opener = opener or urllib.request.urlopen

    def get_asset(self, symbol: str) -> Mapping[str, Any] | None:
        value = self._request_optional_json(
            "GET",
            f"/v2/assets/{urllib.parse.quote(symbol.upper())}",
        )
        return None if value is None else cast(Mapping[str, Any], value)

    def get_latest_trade_price(self, symbol: str) -> float | None:
        params = {"symbols": symbol.upper(), "feed": "iex"}
        request = urllib.request.Request(
            build_alpaca_market_data_url(
                ALPACA_MARKET_DATA_BASE_URL,
                "/v2/stocks/trades/latest",
                params=params,
            ),
            headers=build_alpaca_auth_headers(self._credentials),
            method="GET",
        )
        try:
            with self._opener(request, timeout=self._timeout_seconds) as response:
                body = response.read()
        except urllib.error.HTTPError as exc:
            if exc.code in {401, 403}:
                raise AlpacaClientError(
                    "credential_rejected",
                    f"Alpaca market data request was rejected with HTTP {exc.code}",
                    pause_new_risk=True,
                ) from exc
            raise AlpacaClientError(
                "rest_fallback_unavailable",
                f"Alpaca market data request failed with HTTP {exc.code}",
                retryable=500 <= exc.code < 600,
            ) from exc
        except (urllib.error.URLError, OSError) as exc:
            raise AlpacaClientError(
                "rest_fallback_unavailable",
                "Alpaca market data request failed before a response was received",
                retryable=True,
                details={"error_type": type(exc).__name__},
            ) from exc
        try:
            payload = json.loads(body.decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise AlpacaClientError(
                "rest_fallback_unavailable",
                "Alpaca market data response was not valid JSON",
            ) from exc
        trades = payload.get("trades") if isinstance(payload, Mapping) else None
        trade = trades.get(symbol.upper()) if isinstance(trades, Mapping) else None
        price = trade.get("p") if isinstance(trade, Mapping) else None
        if price is None:
            return None
        return float(price)


def build_alpaca_market_data_url(
    base_url: str,
    path: str,
    *,
    params: Mapping[str, str] | None = None,
) -> str:
    normalized_base = base_url.rstrip("/")
    normalized_path = path if path.startswith("/") else f"/{path}"
    query = "" if not params else f"?{urllib.parse.urlencode(params)}"
    return f"{normalized_base}{normalized_path}{query}"


def build_activation_rehearsal_client(
    credentials: AlpacaPaperCredentials,
    timeout_seconds: float,
) -> ActivationRehearsalClient:
    return AlpacaActivationRehearsalHttpClient(
        credentials=credentials,
        timeout_seconds=max(timeout_seconds, 1.0),
    )


def run_activation_rehearsal_m44d(
    request: ActivationRehearsalRequest,
    *,
    environ: Mapping[str, str] | None = None,
    app_config: AppConfig | None = None,
    client_factory: ActivationRehearsalClientFactory = build_activation_rehearsal_client,
    sleeper: Sleeper = time.sleep,
    clock: Clock = time.monotonic,
    current_time: Callable[[], datetime] | None = None,
) -> ActivationRehearsalResult:
    active_environ = os.environ if environ is None else environ
    active_config = load_app_config() if app_config is None else app_config
    now = _now(current_time)
    blockers = list(_request_gate_blockers(request, active_config, active_environ))

    client: ActivationRehearsalClient | None = None
    pre_state = _empty_state()
    final_state = _empty_state()
    short_summary = ShortRehearsalSummary(blockers=("short_rehearsal_not_run",))
    scale_summary = ScaleInRehearsalSummary(blockers=("scale_in_rehearsal_not_run",))

    if not blockers:
        try:
            if request.mode == "fake":
                client = FakeActivationRehearsalClient()
            else:
                credentials = AlpacaPaperCredentials(
                    api_key=active_environ.get("ALPACA_API_KEY", "").strip(),
                    secret_key=active_environ.get("ALPACA_SECRET_KEY", "").strip(),
                    base_url=active_environ.get("ALPACA_BASE_URL", "").strip(),
                )
                client = client_factory(credentials, request.timeout_seconds)
        except (AlpacaClientError, ValueError) as exc:
            blockers.append(_sanitized_exception("client_setup_failed", exc))

    if client is not None:
        try:
            account = map_alpaca_account(client.get_account(), environment="paper")
            clock_snapshot = map_alpaca_clock(client.get_clock())
            pre_state = _broker_state(client, clock_snapshot=clock_snapshot)
        except (AlpacaClientError, ValueError) as exc:
            blockers.append(_sanitized_exception("broker_preflight_failed", exc))
            account = None
            clock_snapshot = None

        if account is not None and clock_snapshot is not None:
            pre_blockers = _pre_run_state_blockers(pre_state, clock_snapshot)
            blockers.extend(pre_blockers)
            if not pre_blockers:
                if request.rehearsal_mode in {"short", "full"}:
                    short_summary = _run_short_rehearsal(
                        request=request,
                        config=active_config,
                        client=client,
                        account=account,
                        clock_snapshot=clock_snapshot,
                        sleeper=sleeper,
                        clock=clock,
                        current_time=current_time,
                    )
                    blockers.extend(short_summary.blockers)
                    final_state = _safe_broker_state(client, clock_snapshot)
                    if request.rehearsal_mode == "full" and not short_summary.succeeded:
                        blockers.append("short_rehearsal_required_before_scale_in")
                    if final_state.open_orders_count != 0 or final_state.positions_count != 0:
                        blockers.append("broker_not_flat_after_short_rehearsal")
                else:
                    short_summary = ShortRehearsalSummary(blockers=())

                if (
                    request.rehearsal_mode in {"scale-in", "full"}
                    and "broker_not_flat_after_short_rehearsal" not in blockers
                    and "short_rehearsal_required_before_scale_in" not in blockers
                ):
                    scale_summary = _run_scale_in_rehearsal(
                        request=request,
                        config=active_config,
                        client=client,
                        clock_snapshot=clock_snapshot,
                        sleeper=sleeper,
                        clock=clock,
                        current_time=current_time,
                    )
                    blockers.extend(scale_summary.blockers)
                elif request.rehearsal_mode == "short":
                    scale_summary = ScaleInRehearsalSummary(blockers=())

                final_state = _safe_broker_state(client, clock_snapshot)
                if final_state.open_orders_count != 0 or final_state.positions_count != 0:
                    blockers.append("final_broker_baseline_not_flat")

    if client is None:
        final_state = pre_state
    if final_state.reconciliation_summary == "unavailable":
        final_state = pre_state

    mode_requirements_met = (
        (request.rehearsal_mode != "short" or short_summary.succeeded)
        and (request.rehearsal_mode != "scale-in" or scale_summary.succeeded)
        and (
            request.rehearsal_mode != "full"
            or (short_summary.succeeded and scale_summary.succeeded)
        )
    )
    config_ready = (
        active_config.validation.active_spec_version == "v0.6"
        and active_config.validation.short_policy.enabled_at_validation_start
        and active_config.validation.short_policy.real_short_lifecycle_proof_completed_by_m44d
        and active_config.validation.scale_in_policy.enabled_at_validation_start
        and active_config.validation.scale_in_policy.real_additive_stop_proof_completed_by_m44d
        and active_config.shorts.enabled_at_validation_start
        and active_config.shorts.real_short_lifecycle_proof_completed_by_m44d
        and active_config.scale_in.real_additive_stop_proof_completed_by_m44d
    )
    tiingo_gate_go = _tiingo_gate_go()
    if not tiingo_gate_go:
        blockers.append("tiingo_primary_signal_data_gate_not_go")
    if not config_ready:
        blockers.append("v0_6_long_short_scalein_config_not_ready")
    if request.mode != "real-paper":
        blockers.append("real_m44d_rehearsals_not_performed")

    unique_blockers = tuple(dict.fromkeys(blockers))
    broker_writes = short_summary.broker_writes_performed or scale_summary.broker_writes_performed
    real_short_write = request.mode == "real-paper" and short_summary.broker_writes_performed
    real_scale_write = request.mode == "real-paper" and scale_summary.broker_writes_performed
    m45_ready = (
        not unique_blockers
        and mode_requirements_met
        and final_state.open_orders_count == 0
        and final_state.positions_count == 0
        and final_state.reconciliation_summary == "flat_zero_positions_zero_open_orders"
        and config_ready
        and tiingo_gate_go
        and request.mode == "real-paper"
        and request.rehearsal_mode == "full"
    )
    packet = ActivationRehearsalPacket(
        packet_id=_packet_id("activation-rehearsal-m44d", now),
        timestamp=now,
        operator_approval_marker=request.operator_approval,
        pre_run_broker_state=pre_state,
        short_rehearsal=short_summary,
        scale_in_rehearsal=scale_summary,
        broker_writes_performed=broker_writes,
        real_short_broker_write_performed=real_short_write,
        real_scale_in_broker_write_performed=real_scale_write,
        final_broker_baseline=final_state,
        m45_long_short_scalein_readiness=m45_ready,
        blockers=unique_blockers,
    )
    readiness_packet = build_frozen_readiness_m44d_packet(
        activation_packet=packet,
        app_config=active_config,
        now=now,
        tiingo_gate_go=tiingo_gate_go,
    )
    return ActivationRehearsalResult(
        success=m45_ready,
        go_no_go="go" if m45_ready else "no_go",
        packet=packet,
        readiness_packet=readiness_packet,
        blockers=unique_blockers,
        broker_writes_performed=broker_writes,
        real_broker_writes_performed=real_short_write or real_scale_write,
    )


def build_frozen_readiness_m44d_packet(
    *,
    activation_packet: ActivationRehearsalPacket,
    app_config: AppConfig | None = None,
    now: datetime | None = None,
    tiingo_gate_go: bool | None = None,
) -> FrozenReadinessM44DPacket:
    active_config = load_app_config() if app_config is None else app_config
    gate_go = _tiingo_gate_go() if tiingo_gate_go is None else tiingo_gate_go
    blockers = list(activation_packet.blockers)
    if not activation_packet.short_rehearsal.succeeded:
        blockers.append("short_rehearsal_not_successful")
    if not activation_packet.scale_in_rehearsal.succeeded:
        blockers.append("scale_in_rehearsal_not_successful")
    if activation_packet.final_broker_baseline.open_orders_count != 0:
        blockers.append("final_open_orders_not_zero")
    if activation_packet.final_broker_baseline.positions_count != 0:
        blockers.append("final_positions_not_zero")
    if not gate_go:
        blockers.append("tiingo_primary_signal_data_gate_not_go")
    if active_config.validation.active_spec_version != "v0.6":
        blockers.append("latest_spec_not_v0_6")
    if not active_config.validation.short_policy.enabled_at_validation_start:
        blockers.append("shorts_not_enabled_at_validation_start")
    if not active_config.validation.scale_in_policy.enabled_at_validation_start:
        blockers.append("scale_ins_not_enabled_at_validation_start")
    if active_config.validation.short_policy.live_shorting_enabled:
        blockers.append("live_shorting_enabled")
    if active_config.validation.scale_in_policy.short_scale_in_enabled_at_validation_start:
        blockers.append("short_scale_ins_enabled_at_validation_start")
    unique_blockers = tuple(dict.fromkeys(blockers))
    m45_readiness = not unique_blockers
    timestamp = now or datetime.now(UTC)
    return FrozenReadinessM44DPacket(
        packet_id=_packet_id("frozen-readiness-m44d", timestamp),
        timestamp=timestamp,
        tiingo_gate_status="go" if gate_go else "no_go",
        final_broker_baseline=activation_packet.final_broker_baseline,
        short_rehearsal_succeeded=activation_packet.short_rehearsal.succeeded,
        scale_in_rehearsal_succeeded=activation_packet.scale_in_rehearsal.succeeded,
        shorts_enabled_at_validation_start=(
            active_config.validation.short_policy.enabled_at_validation_start
        ),
        scale_in_enabled_at_validation_start=(
            active_config.validation.scale_in_policy.enabled_at_validation_start
        ),
        short_universe=active_config.shorts.eligible_symbols,
        m45_readiness=m45_readiness,
        blockers=unique_blockers,
    )


def write_activation_rehearsal_m44d_artifacts(
    result: ActivationRehearsalResult,
    *,
    activation_path: str | Path = ACTIVATION_REHEARSAL_M44D_EVIDENCE_PATH,
    readiness_path: str | Path = FROZEN_READINESS_M44D_EVIDENCE_PATH,
) -> tuple[Path, Path]:
    activation_output = _write_json(result.packet.model_dump(mode="json"), Path(activation_path))
    readiness_output = _write_json(
        result.readiness_packet.model_dump(mode="json"),
        Path(readiness_path),
    )
    return activation_output, readiness_output


def _request_gate_blockers(
    request: ActivationRehearsalRequest,
    config: AppConfig,
    environ: Mapping[str, str],
) -> tuple[str, ...]:
    blockers: list[str] = []
    if request.operator_approval != M44D_APPROVAL:
        blockers.append("m44d_approval_marker_required")
    confirmations = {
        "confirm_paper_endpoint": request.confirm_paper_endpoint,
        "confirm_short_rehearsal_only": request.confirm_short_rehearsal_only,
        "confirm_scale_in_rehearsal_only": request.confirm_scale_in_rehearsal_only,
        "confirm_protective_buy_stop_required": request.confirm_protective_buy_stop_required,
        "confirm_additive_sell_stop_required": request.confirm_additive_sell_stop_required,
        "confirm_cleanup_to_flat": request.confirm_cleanup_to_flat,
        "confirm_no_live_trading": request.confirm_no_live_trading,
        "confirm_no_autonomous_live": request.confirm_no_autonomous_live,
        "confirm_no_schedules": request.confirm_no_schedules,
        "confirm_no_leverage": request.confirm_no_leverage,
        "confirm_no_frozen_validation_start": request.confirm_no_frozen_validation_start,
        "confirm_level4_not_ready": request.confirm_level4_not_ready,
    }
    blockers.extend(name for name, value in confirmations.items() if not value)
    if request.mode == "real-paper":
        if environ.get("ALPACA_API_KEY", "").strip() == "":
            blockers.append("ALPACA_API_KEY_required")
        if environ.get("ALPACA_SECRET_KEY", "").strip() == "":
            blockers.append("ALPACA_SECRET_KEY_required")
        if environ.get("ALPACA_BASE_URL", "").strip() != ALPACA_PAPER_BASE_URL:
            blockers.append("ALPACA_BASE_URL_exact_paper_endpoint_required")
    if config.system.environment != "paper":
        blockers.append("system_environment_not_paper")
    if not config.system.dry_run:
        blockers.append("system_dry_run_not_true")
    if config.system.live_trading_enabled or config.execution.allow_live_orders:
        blockers.append("live_trading_enabled")
    if config.system.autonomous_execution_enabled or config.execution.autonomous_execution_enabled:
        blockers.append("autonomous_live_execution_enabled")
    if config.validation.frozen_validation_enabled or config.validation.validation_clock_started:
        blockers.append("frozen_validation_started_or_enabled")
    if config.validation.frozen_validation_start_allowed:
        blockers.append("frozen_validation_start_allowed_in_m44d")
    if config.risk_level_4_micro_live.allow_margin:
        blockers.append("leverage_or_margin_enabled")
    if config.validation.level4_ready:
        blockers.append("level4_ready_enabled")
    if config.ai.allow_ai_to_create_orders:
        blockers.append("ai_broker_write_authority_enabled")
    if config.validation.active_spec_version != "v0.6":
        blockers.append("active_spec_version_not_v0_6")
    if config.validation.short_policy.live_shorting_enabled:
        blockers.append("live_shorting_enabled_in_validation_policy")
    return tuple(dict.fromkeys(blockers))


def _pre_run_state_blockers(
    state: BrokerStateSummary,
    clock_snapshot: BrokerClockSnapshot,
) -> tuple[str, ...]:
    blockers: list[str] = []
    if not state.account_reachable:
        blockers.append("account_not_reachable")
    if not state.clock_reachable:
        blockers.append("clock_not_reachable")
    if not clock_snapshot.is_open:
        blockers.append("market_session_not_open")
    if state.open_orders_count != 0:
        blockers.append("pre_run_open_orders_not_zero")
    if state.positions_count != 0:
        blockers.append("pre_run_positions_not_zero")
    if state.reconciliation_summary != "flat_zero_positions_zero_open_orders":
        blockers.append("pre_run_reconciliation_not_flat")
    return tuple(blockers)


def _run_short_rehearsal(
    *,
    request: ActivationRehearsalRequest,
    config: AppConfig,
    client: ActivationRehearsalClient,
    account: BrokerAccountSnapshot,
    clock_snapshot: BrokerClockSnapshot,
    sleeper: Sleeper,
    clock: Clock,
    current_time: Callable[[], datetime] | None,
) -> ShortRehearsalSummary:
    del clock_snapshot
    blockers: list[str] = []
    selected_symbol: str | None = None
    fallback_used = False
    asset_snapshot: AssetShortabilitySnapshot | None = None
    account_snapshot = AccountShortingSnapshot(
        shorting_enabled=account.shorting_enabled,
        equity_available=account.equity > 0,
        equity_above_2000=account.equity >= 2_000,
    )
    entry_order: BrokerOrder | None = None
    stop_order: BrokerOrder | None = None
    entry_request: OrderRequestSummary | None = None
    stop_request: OrderRequestSummary | None = None
    buy_to_cover_result: OrderResultSummary | None = None
    emergency_result: StopVerificationSummary | None = None
    cleanup_result = None
    broker_writes = False

    for index, symbol in enumerate(SHORT_CANDIDATES):
        try:
            candidate_asset = _asset_snapshot(client, symbol)
            price = _latest_trade_price(client, symbol)
        except AlpacaClientError as exc:
            blockers.append(_sanitized_exception(f"{symbol}_asset_or_price_check_failed", exc))
            continue
        asset_snapshot = candidate_asset
        fallback_used = index > 0
        selected_symbol = symbol
        entry_price = _short_limit_price(price)
        stop_price = _short_stop_price(entry_price)
        risk_result = evaluate_short_entry_risk(
            policy=config.shorts,
            short_input=ShortEntryRiskInput(
                symbol=symbol,
                quantity=request.short_max_qty,
                entry_price=entry_price,
                stop_price=stop_price,
                asset=ShortAssetSnapshot(
                    symbol=symbol,
                    asset_class=cast(Literal["equity", "etf"], candidate_asset.asset_class),
                    tradable=candidate_asset.tradable,
                    marginable=candidate_asset.marginable,
                    shortable=candidate_asset.shortable,
                    easy_to_borrow=candidate_asset.easy_to_borrow,
                ),
                account=ShortAccountSnapshot(
                    environment="paper",
                    equity=account.equity,
                    shorting_enabled=account.shorting_enabled,
                ),
                broker_state_ambiguous=False,
                deterministic_bearish_signal=True,
                execution_intent_present=True,
                protective_buy_stop_planned=True,
            ),
        )
        if not risk_result.allowed:
            blockers.extend(f"{symbol}:{reason}" for reason in risk_result.reason_codes)
            selected_symbol = None
            continue
        if entry_price * request.short_max_qty > SHORT_MAX_NOTIONAL_USD:
            blockers.append(f"{symbol}:short_notional_cap_exceeded")
            selected_symbol = None
            continue
        break

    if selected_symbol is None or asset_snapshot is None:
        return ShortRehearsalSummary(
            selected_symbol=None,
            fallback_used=False,
            asset_shortability_snapshot=asset_snapshot,
            account_shorting_snapshot=account_snapshot,
            final_reconciliation="not_run",
            blockers=tuple(dict.fromkeys(blockers or ["no_short_candidate_passed_gates"])),
        )

    now = _now(current_time)
    entry_price = _short_limit_price(_latest_trade_price(client, selected_symbol))
    stop_price = _short_stop_price(entry_price)
    intent = _execution_intent(
        symbol=selected_symbol,
        side="sell",
        position_side="short",
        quantity=request.short_max_qty,
        limit_price=entry_price,
        stop_loss_price=stop_price,
        order_role="short_entry",
        client_order_id_root=_client_order_id("m44d-short", selected_symbol, now),
        config=config,
        now=now,
    )
    entry_payload = {
        "symbol": selected_symbol,
        "side": "sell",
        "type": "limit",
        "time_in_force": "day",
        "qty": str(request.short_max_qty),
        "limit_price": str(intent.limit_price),
        "client_order_id": intent.client_order_id_root,
        "extended_hours": False,
    }
    entry_request = _request_summary(entry_payload, role="short_entry")
    try:
        entry_order = map_alpaca_order(client.submit_order(entry_payload))
        broker_writes = True
        entry_order = _poll_order(
            client,
            client_order_id=intent.client_order_id_root,
            initial_order=entry_order,
            timeout_seconds=request.timeout_seconds,
            sleeper=sleeper,
            clock=clock,
        )
    except AlpacaClientError as exc:
        blockers.append(_sanitized_exception("short_entry_submit_failed", exc))
        return _short_summary_with_final_state(
            client=client,
            selected_symbol=selected_symbol,
            fallback_used=fallback_used,
            asset_snapshot=asset_snapshot,
            account_snapshot=account_snapshot,
            entry_request=entry_request,
            entry_order=entry_order,
            stop_request=None,
            stop_order=None,
            buy_to_cover_result=None,
            emergency_result=None,
            cleanup_result=None,
            blockers=blockers,
            broker_writes=broker_writes,
        )
    filled_quantity = entry_order.filled_quantity
    if filled_quantity <= 0:
        blockers.append("short_entry_not_filled")
        _cancel_if_open(client, entry_order)
        return _short_summary_with_final_state(
            client=client,
            selected_symbol=selected_symbol,
            fallback_used=fallback_used,
            asset_snapshot=asset_snapshot,
            account_snapshot=account_snapshot,
            entry_request=entry_request,
            entry_order=entry_order,
            stop_request=None,
            stop_order=None,
            buy_to_cover_result=None,
            emergency_result=None,
            cleanup_result="cancelled_unfilled_short_entry",
            blockers=blockers,
            broker_writes=broker_writes,
        )
    signed_position = _position_quantity(client, selected_symbol)
    if signed_position >= 0 or abs(signed_position) - filled_quantity > 1e-6:
        blockers.append("short_signed_position_verification_failed")

    stop_payload = {
        "symbol": selected_symbol,
        "side": "buy",
        "type": "stop",
        "time_in_force": "gtc",
        "qty": _format_quantity(filled_quantity),
        "stop_price": str(stop_price),
        "client_order_id": f"{intent.client_order_id_root}-buy-stop",
        "extended_hours": False,
    }
    stop_request = _request_summary(stop_payload, role="short_protective_stop")
    try:
        stop_order = map_alpaca_order(client.submit_order(stop_payload))
        broker_writes = True
    except AlpacaClientError as exc:
        blockers.append(_sanitized_exception("short_protective_buy_stop_failed", exc))
    protection = _aggregate_stop_protection(
        client,
        symbol=selected_symbol,
        side="buy",
        required_position_quantity=abs(_position_quantity(client, selected_symbol)),
    )
    if not protection.passed:
        blockers.append("short_protective_buy_stop_not_verified")

    try:
        if stop_order is not None and stop_order.is_open:
            client.cancel_order(stop_order.broker_order_id)
            cleanup_result = "short_protective_stop_cancelled"
        cover_qty = abs(_position_quantity(client, selected_symbol))
        if cover_qty > 0:
            cover_payload = {
                "symbol": selected_symbol,
                "side": "buy",
                "type": "market",
                "time_in_force": "day",
                "qty": _format_quantity(cover_qty),
                "client_order_id": f"{intent.client_order_id_root}-cover",
                "extended_hours": False,
            }
            cover_order = map_alpaca_order(client.submit_order(cover_payload))
            broker_writes = True
            cover_order = _poll_order(
                client,
                client_order_id=str(cover_payload["client_order_id"]),
                initial_order=cover_order,
                timeout_seconds=request.timeout_seconds,
                sleeper=sleeper,
                clock=clock,
            )
            buy_to_cover_result = _order_result(cover_order, submitted=True)
            if _position_quantity(client, selected_symbol) < 0:
                blockers.append("short_cleanup_cover_failed")
                emergency_result = _emergency_stop(
                    client,
                    symbol=selected_symbol,
                    side="buy",
                    quantity=abs(_position_quantity(client, selected_symbol)),
                    stop_price=stop_price,
                    client_order_id=f"{intent.client_order_id_root}-emergency-buy-stop",
                )
                blockers.append("emergency_short_reprotection_required")
    except AlpacaClientError as exc:
        blockers.append(_sanitized_exception("short_cleanup_failed", exc))
        if _position_quantity(client, selected_symbol) < 0:
            emergency_result = _emergency_stop(
                client,
                symbol=selected_symbol,
                side="buy",
                quantity=abs(_position_quantity(client, selected_symbol)),
                stop_price=stop_price,
                client_order_id=f"{intent.client_order_id_root}-emergency-buy-stop",
            )
            blockers.append("emergency_short_reprotection_required")

    return _short_summary_with_final_state(
        client=client,
        selected_symbol=selected_symbol,
        fallback_used=fallback_used,
        asset_snapshot=asset_snapshot,
        account_snapshot=account_snapshot,
        entry_request=entry_request,
        entry_order=entry_order,
        stop_request=stop_request,
        stop_order=stop_order,
        buy_to_cover_result=buy_to_cover_result,
        emergency_result=emergency_result,
        cleanup_result=cleanup_result,
        blockers=blockers,
        broker_writes=broker_writes,
    )


def _run_scale_in_rehearsal(
    *,
    request: ActivationRehearsalRequest,
    config: AppConfig,
    client: ActivationRehearsalClient,
    clock_snapshot: BrokerClockSnapshot,
    sleeper: Sleeper,
    clock: Clock,
    current_time: Callable[[], datetime] | None,
) -> ScaleInRehearsalSummary:
    del clock_snapshot
    blockers: list[str] = []
    selected_symbol = None
    fallback_used = False
    broker_writes = False
    initial_order: BrokerOrder | None = None
    addon_order: BrokerOrder | None = None
    emergency_result: StopVerificationSummary | None = None
    cleanup_sell_result: OrderResultSummary | None = None
    cleanup_result = None

    for index, symbol in enumerate(SCALE_IN_CANDIDATES):
        try:
            price = _latest_trade_price(client, symbol)
            asset = client.get_asset(symbol)
        except AlpacaClientError as exc:
            blockers.append(
                _sanitized_exception(f"{symbol}_scale_asset_or_price_check_failed", exc)
            )
            continue
        if asset is None or not _bool(asset.get("tradable")):
            blockers.append(f"{symbol}:asset_not_tradable")
            continue
        if symbol not in config.live_universe.symbols:
            blockers.append(f"{symbol}:symbol_not_long_eligible")
            continue
        if _position_quantity(client, symbol) != 0:
            blockers.append(f"{symbol}:existing_position_present")
            continue
        if _symbol_open_orders(client, symbol):
            blockers.append(f"{symbol}:existing_open_order_present")
            continue
        cap = SCALE_TOTAL_NOTIONAL_CAPS_USD[symbol]
        if price * (request.scale_initial_max_qty + request.scale_addon_max_qty) > cap:
            blockers.append(f"{symbol}:scale_in_notional_cap_exceeded")
            continue
        selected_symbol = symbol
        fallback_used = index > 0
        break

    if selected_symbol is None:
        return ScaleInRehearsalSummary(
            fallback_used=False,
            final_reconciliation="not_run",
            blockers=tuple(dict.fromkeys(blockers or ["no_scale_in_candidate_passed_gates"])),
        )

    now = _now(current_time)
    price = _latest_trade_price(client, selected_symbol)
    entry_price = _long_limit_price(price)
    stop_price = _long_stop_price(entry_price)
    client_root = _client_order_id("m44d-scale", selected_symbol, now)
    initial_payload = {
        "symbol": selected_symbol,
        "side": "buy",
        "type": "limit",
        "time_in_force": "day",
        "qty": str(request.scale_initial_max_qty),
        "limit_price": str(entry_price),
        "client_order_id": client_root,
        "extended_hours": False,
    }
    initial_request = _request_summary(initial_payload, role="initial_entry")
    initial_stop_result: StopVerificationSummary | None = None
    addon_stop_result: StopVerificationSummary | None = None
    addon_request: OrderRequestSummary | None = None

    try:
        initial_order = map_alpaca_order(client.submit_order(initial_payload))
        broker_writes = True
        initial_order = _poll_order(
            client,
            client_order_id=client_root,
            initial_order=initial_order,
            timeout_seconds=request.timeout_seconds,
            sleeper=sleeper,
            clock=clock,
        )
    except AlpacaClientError as exc:
        blockers.append(_sanitized_exception("initial_long_entry_submit_failed", exc))
        return _scale_summary_with_final_state(
            client=client,
            selected_symbol=selected_symbol,
            fallback_used=fallback_used,
            initial_request=initial_request,
            initial_order=initial_order,
            initial_stop_result=None,
            addon_request=None,
            addon_order=None,
            addon_stop_result=None,
            cleanup_sell_result=None,
            emergency_result=None,
            cleanup_result=None,
            blockers=blockers,
            broker_writes=broker_writes,
        )
    if initial_order.filled_quantity <= 0:
        blockers.append("initial_long_entry_not_filled")
        _cancel_if_open(client, initial_order)
        return _scale_summary_with_final_state(
            client=client,
            selected_symbol=selected_symbol,
            fallback_used=fallback_used,
            initial_request=initial_request,
            initial_order=initial_order,
            initial_stop_result=None,
            addon_request=None,
            addon_order=None,
            addon_stop_result=None,
            cleanup_sell_result=None,
            emergency_result=None,
            cleanup_result="cancelled_unfilled_initial_entry",
            blockers=blockers,
            broker_writes=broker_writes,
        )

    initial_stop_payload = {
        "symbol": selected_symbol,
        "side": "sell",
        "type": "stop",
        "time_in_force": "gtc",
        "qty": _format_quantity(initial_order.filled_quantity),
        "stop_price": str(stop_price),
        "client_order_id": f"{client_root}-initial-stop",
        "extended_hours": False,
    }
    try:
        map_alpaca_order(client.submit_order(initial_stop_payload))
        broker_writes = True
    except AlpacaClientError as exc:
        blockers.append(_sanitized_exception("initial_sell_stop_submit_failed", exc))
    initial_stop_result = _stop_verification(
        client,
        symbol=selected_symbol,
        side="sell",
        required_quantity=initial_order.filled_quantity,
        client_order_id=str(initial_stop_payload["client_order_id"]),
    )
    if not initial_stop_result.verified:
        blockers.append("initial_protective_sell_stop_not_verified")
        return _scale_summary_with_final_state(
            client=client,
            selected_symbol=selected_symbol,
            fallback_used=fallback_used,
            initial_request=initial_request,
            initial_order=initial_order,
            initial_stop_result=initial_stop_result,
            addon_request=None,
            addon_order=None,
            addon_stop_result=None,
            cleanup_sell_result=None,
            emergency_result=None,
            cleanup_result=None,
            blockers=blockers,
            broker_writes=broker_writes,
        )

    addon_payload = {
        "symbol": selected_symbol,
        "side": "buy",
        "type": "limit",
        "time_in_force": "day",
        "qty": str(request.scale_addon_max_qty),
        "limit_price": str(entry_price),
        "client_order_id": f"{client_root}-addon",
        "extended_hours": False,
    }
    addon_request = _request_summary(addon_payload, role="scale_in_entry")
    try:
        addon_order = map_alpaca_order(client.submit_order(addon_payload))
        broker_writes = True
        addon_order = _poll_order(
            client,
            client_order_id=str(addon_payload["client_order_id"]),
            initial_order=addon_order,
            timeout_seconds=request.timeout_seconds,
            sleeper=sleeper,
            clock=clock,
        )
    except AlpacaClientError as exc:
        blockers.append(_sanitized_exception("scale_in_entry_submit_failed", exc))
    if addon_order is None or addon_order.filled_quantity <= 0:
        blockers.append("scale_in_entry_not_filled")
    else:
        addon_stop_payload = {
            "symbol": selected_symbol,
            "side": "sell",
            "type": "stop",
            "time_in_force": "gtc",
            "qty": _format_quantity(addon_order.filled_quantity),
            "stop_price": str(stop_price),
            "client_order_id": f"{client_root}-addon-stop",
            "extended_hours": False,
        }
        try:
            map_alpaca_order(client.submit_order(addon_stop_payload))
            broker_writes = True
        except AlpacaClientError as exc:
            blockers.append(_sanitized_exception("additive_sell_stop_submit_failed", exc))
        addon_stop_result = _stop_verification(
            client,
            symbol=selected_symbol,
            side="sell",
            required_quantity=addon_order.filled_quantity,
            client_order_id=str(addon_stop_payload["client_order_id"]),
        )
        if not addon_stop_result.verified:
            blockers.append("additive_protective_sell_stop_not_verified")

    aggregate = _aggregate_stop_protection(
        client,
        symbol=selected_symbol,
        side="sell",
        required_position_quantity=max(_position_quantity(client, selected_symbol), 0.0),
    )
    if not aggregate.passed:
        blockers.append("aggregate_long_protection_not_verified")

    try:
        for order in _symbol_open_orders(client, selected_symbol):
            if order.order_type == "stop" and order.client_order_id.startswith(client_root):
                client.cancel_order(order.broker_order_id)
                broker_writes = True
        cleanup_result = "session_protective_stops_cancelled"
        sell_qty = _position_quantity(client, selected_symbol)
        if sell_qty > 0:
            cleanup_payload = {
                "symbol": selected_symbol,
                "side": "sell",
                "type": "market",
                "time_in_force": "day",
                "qty": _format_quantity(sell_qty),
                "client_order_id": f"{client_root}-cleanup-sell",
                "extended_hours": False,
            }
            cleanup_order = map_alpaca_order(client.submit_order(cleanup_payload))
            broker_writes = True
            cleanup_order = _poll_order(
                client,
                client_order_id=str(cleanup_payload["client_order_id"]),
                initial_order=cleanup_order,
                timeout_seconds=request.timeout_seconds,
                sleeper=sleeper,
                clock=clock,
            )
            cleanup_sell_result = _order_result(cleanup_order, submitted=True)
        if _position_quantity(client, selected_symbol) > 0:
            blockers.append("long_scale_in_cleanup_sell_failed")
            emergency_result = _emergency_stop(
                client,
                symbol=selected_symbol,
                side="sell",
                quantity=_position_quantity(client, selected_symbol),
                stop_price=stop_price,
                client_order_id=f"{client_root}-emergency-sell-stop",
            )
            blockers.append("emergency_long_reprotection_required")
    except AlpacaClientError as exc:
        blockers.append(_sanitized_exception("scale_in_cleanup_failed", exc))
        if _position_quantity(client, selected_symbol) > 0:
            emergency_result = _emergency_stop(
                client,
                symbol=selected_symbol,
                side="sell",
                quantity=_position_quantity(client, selected_symbol),
                stop_price=stop_price,
                client_order_id=f"{client_root}-emergency-sell-stop",
            )
            blockers.append("emergency_long_reprotection_required")

    return _scale_summary_with_final_state(
        client=client,
        selected_symbol=selected_symbol,
        fallback_used=fallback_used,
        initial_request=initial_request,
        initial_order=initial_order,
        initial_stop_result=initial_stop_result,
        addon_request=addon_request,
        addon_order=addon_order,
        addon_stop_result=addon_stop_result,
        cleanup_sell_result=cleanup_sell_result,
        emergency_result=emergency_result,
        cleanup_result=cleanup_result,
        blockers=blockers,
        broker_writes=broker_writes,
    )


def _short_summary_with_final_state(
    *,
    client: ActivationRehearsalClient,
    selected_symbol: str,
    fallback_used: bool,
    asset_snapshot: AssetShortabilitySnapshot,
    account_snapshot: AccountShortingSnapshot,
    entry_request: OrderRequestSummary | None,
    entry_order: BrokerOrder | None,
    stop_request: OrderRequestSummary | None,
    stop_order: BrokerOrder | None,
    buy_to_cover_result: OrderResultSummary | None,
    emergency_result: StopVerificationSummary | None,
    cleanup_result: str | None,
    blockers: Sequence[str],
    broker_writes: bool,
) -> ShortRehearsalSummary:
    final_state = _safe_broker_state(client)
    signed_qty = _position_quantity(client, selected_symbol)
    aggregate = _aggregate_stop_protection(
        client,
        symbol=selected_symbol,
        side="buy",
        required_position_quantity=abs(min(signed_qty, 0.0)),
    )
    unique_blockers = tuple(dict.fromkeys(blockers))
    succeeded = (
        not unique_blockers
        and entry_order is not None
        and entry_order.filled_quantity > 0
        and stop_order is not None
        and final_state.open_orders_count == 0
        and final_state.positions_count == 0
        and final_state.reconciliation_summary == "flat_zero_positions_zero_open_orders"
    )
    return ShortRehearsalSummary(
        selected_symbol=selected_symbol,
        fallback_used=fallback_used,
        asset_shortability_snapshot=asset_snapshot,
        account_shorting_snapshot=account_snapshot,
        short_order_request_summary=entry_request,
        short_entry_result=(
            None if entry_order is None else _order_result(entry_order, submitted=True)
        ),
        fill_result=None if entry_order is None else _order_result(entry_order, submitted=True),
        signed_position_result={
            "symbol": selected_symbol,
            "signed_qty_after_short_fill": signed_qty,
            "short_position_observed": signed_qty < 0,
        },
        protective_buy_stop_request_summary=stop_request,
        protective_buy_stop_verification=_stop_verification_from_order(
            stop_order,
            required_quantity=0.0 if entry_order is None else entry_order.filled_quantity,
        ),
        aggregate_short_protection_check=aggregate,
        cleanup_stop_cancel_result=cleanup_result,
        buy_to_cover_result=buy_to_cover_result,
        emergency_reprotect_result=emergency_result,
        final_open_orders_count=final_state.open_orders_count,
        final_positions_count=final_state.positions_count,
        final_reconciliation=final_state.reconciliation_summary,
        succeeded=succeeded,
        broker_writes_performed=broker_writes,
        blockers=unique_blockers,
    )


def _scale_summary_with_final_state(
    *,
    client: ActivationRehearsalClient,
    selected_symbol: str,
    fallback_used: bool,
    initial_request: OrderRequestSummary | None,
    initial_order: BrokerOrder | None,
    initial_stop_result: StopVerificationSummary | None,
    addon_request: OrderRequestSummary | None,
    addon_order: BrokerOrder | None,
    addon_stop_result: StopVerificationSummary | None,
    cleanup_sell_result: OrderResultSummary | None,
    emergency_result: StopVerificationSummary | None,
    cleanup_result: str | None,
    blockers: Sequence[str],
    broker_writes: bool,
) -> ScaleInRehearsalSummary:
    final_state = _safe_broker_state(client)
    aggregate = _aggregate_stop_protection(
        client,
        symbol=selected_symbol,
        side="sell",
        required_position_quantity=max(_position_quantity(client, selected_symbol), 0.0),
    )
    unique_blockers = tuple(dict.fromkeys(blockers))
    succeeded = (
        not unique_blockers
        and initial_order is not None
        and initial_order.filled_quantity > 0
        and addon_order is not None
        and addon_order.filled_quantity > 0
        and final_state.open_orders_count == 0
        and final_state.positions_count == 0
        and final_state.reconciliation_summary == "flat_zero_positions_zero_open_orders"
    )
    return ScaleInRehearsalSummary(
        selected_symbol=selected_symbol,
        fallback_used=fallback_used,
        initial_entry_request_summary=initial_request,
        initial_entry_result=(
            None if initial_order is None else _order_result(initial_order, submitted=True)
        ),
        initial_fill_result=(
            None if initial_order is None else _order_result(initial_order, submitted=True)
        ),
        initial_protective_stop_result=initial_stop_result,
        scale_in_entry_request_summary=addon_request,
        scale_in_fill_result=(
            None if addon_order is None else _order_result(addon_order, submitted=True)
        ),
        additive_protective_stop_result=addon_stop_result,
        aggregate_long_protection_check=aggregate,
        cleanup_stop_cancel_result=cleanup_result,
        cleanup_sell_result=cleanup_sell_result,
        emergency_reprotect_result=emergency_result,
        final_open_orders_count=final_state.open_orders_count,
        final_positions_count=final_state.positions_count,
        final_reconciliation=final_state.reconciliation_summary,
        succeeded=succeeded,
        broker_writes_performed=broker_writes,
        blockers=unique_blockers,
    )


def _asset_snapshot(client: ActivationRehearsalClient, symbol: str) -> AssetShortabilitySnapshot:
    payload = client.get_asset(symbol)
    if payload is None:
        raise AlpacaClientError(
            "rest_fallback_unavailable",
            "asset snapshot was unavailable",
            pause_new_risk=True,
            details={"symbol": symbol},
        )
    asset_class = _asset_class_for_symbol(symbol)
    return AssetShortabilitySnapshot(
        symbol=symbol,
        asset_class=asset_class,
        tradable=_optional_bool(payload.get("tradable")),
        marginable=_optional_bool(payload.get("marginable")),
        shortable=_optional_bool(payload.get("shortable")),
        easy_to_borrow=_optional_bool(payload.get("easy_to_borrow")),
    )


def _latest_trade_price(client: ActivationRehearsalClient, symbol: str) -> float:
    price = client.get_latest_trade_price(symbol)
    if price is None or price <= 0:
        raise AlpacaClientError(
            "rest_fallback_unavailable",
            "latest trade price was unavailable",
            pause_new_risk=True,
            details={"symbol": symbol},
        )
    return price


def _execution_intent(
    *,
    symbol: str,
    side: Literal["buy", "sell"],
    position_side: Literal["long", "short"],
    quantity: int,
    limit_price: float,
    stop_loss_price: float,
    order_role: str,
    client_order_id_root: str,
    config: AppConfig,
    now: datetime,
) -> ExecutionIntent:
    return ExecutionIntent(
        decision_id=uuid5(NAMESPACE_URL, client_order_id_root),
        symbol=symbol,
        side=side,
        position_side=position_side,
        asset_class=cast(Literal["equity", "etf"], _asset_class_for_symbol(symbol)),
        quantity=quantity,
        signed_quantity=-quantity if position_side == "short" else quantity,
        order_role=cast(Any, order_role),
        opening_effect="open_short" if position_side == "short" else "open_long",
        closing_effect="none",
        protective_side="buy" if position_side == "short" else "sell",
        entry_order_type="limit",
        limit_price=limit_price,
        stop_loss_price=stop_loss_price,
        time_in_force="day",
        strategy_version="m44d_activation_rehearsal_v0_6",
        risk_config_version="m44d_activation_rehearsal_caps_v0_6",
        autonomy_level=config.system.autonomy_level,
        requires_protective_stop=True,
        max_acceptable_slippage_bps=config.execution.max_acceptable_slippage_bps,
        expires_at=now + timedelta(seconds=60),
        client_order_id_root=client_order_id_root,
        status="risk_approved",
        temporal_workflow_id=None,
    )


def _poll_order(
    client: ActivationRehearsalClient,
    *,
    client_order_id: str,
    initial_order: BrokerOrder,
    timeout_seconds: float,
    sleeper: Sleeper,
    clock: Clock,
) -> BrokerOrder:
    order = initial_order
    if _terminal_or_filled(order):
        return order
    deadline = clock() + timeout_seconds
    while clock() < deadline:
        latest_payload = client.get_order_by_client_order_id(client_order_id)
        if latest_payload is not None:
            order = map_alpaca_order(latest_payload)
        if _terminal_or_filled(order):
            return order
        sleeper(min(1.0, max(0.0, deadline - clock())))
    latest_payload = client.get_order_by_client_order_id(client_order_id)
    return order if latest_payload is None else map_alpaca_order(latest_payload)


def _terminal_or_filled(order: BrokerOrder) -> bool:
    return (
        order.status in {"filled", "cancelled", "expired", "rejected"}
        or order.filled_quantity > 0
    )


def _cancel_if_open(client: ActivationRehearsalClient, order: BrokerOrder) -> None:
    if order.is_open:
        client.cancel_order(order.broker_order_id)


def _broker_state(
    client: ActivationRehearsalClient,
    *,
    clock_snapshot: BrokerClockSnapshot | None = None,
) -> BrokerStateSummary:
    orders = tuple(map(map_alpaca_order, client.list_open_orders()))
    positions = tuple(map(map_alpaca_position, client.list_positions()))
    if clock_snapshot is None:
        clock_snapshot = map_alpaca_clock(client.get_clock())
    active_positions = tuple(position for position in positions if abs(position.quantity) > 1e-9)
    return BrokerStateSummary(
        account_reachable=True,
        clock_reachable=True,
        clock_is_open=clock_snapshot.is_open,
        paper_endpoint_proven=True,
        open_orders_count=len(orders),
        positions_count=len(active_positions),
        reconciliation_summary=(
            "flat_zero_positions_zero_open_orders"
            if not orders and not active_positions
            else "non_flat_or_open_orders_present"
        ),
        symbols_with_open_orders=tuple(sorted({order.symbol for order in orders})),
        symbols_with_positions=tuple(sorted({position.symbol for position in active_positions})),
    )


def _safe_broker_state(
    client: ActivationRehearsalClient,
    clock_snapshot: BrokerClockSnapshot | None = None,
) -> BrokerStateSummary:
    try:
        return _broker_state(client, clock_snapshot=clock_snapshot)
    except (AlpacaClientError, ValueError):
        return _empty_state(reconciliation_summary="unavailable")


def _empty_state(reconciliation_summary: str = "unavailable") -> BrokerStateSummary:
    return BrokerStateSummary(
        account_reachable=False,
        clock_reachable=False,
        clock_is_open=None,
        paper_endpoint_proven=False,
        open_orders_count=0,
        positions_count=0,
        reconciliation_summary=reconciliation_summary,
        symbols_with_open_orders=(),
        symbols_with_positions=(),
    )


def _symbol_open_orders(client: ActivationRehearsalClient, symbol: str) -> tuple[BrokerOrder, ...]:
    return tuple(
        order
        for order in tuple(map(map_alpaca_order, client.list_open_orders()))
        if order.symbol == symbol.upper() and order.is_open
    )


def _position_quantity(client: ActivationRehearsalClient, symbol: str) -> float:
    payload = client.get_position(symbol)
    if payload is None:
        return 0.0
    return float(payload.get("qty") or payload.get("quantity") or 0.0)


def _stop_verification(
    client: ActivationRehearsalClient,
    *,
    symbol: str,
    side: Literal["buy", "sell"],
    required_quantity: float,
    client_order_id: str,
) -> StopVerificationSummary:
    for order in _symbol_open_orders(client, symbol):
        if (
            order.order_type == "stop"
            and order.side == side
            and order.client_order_id == client_order_id
            and order.quantity + 1e-9 >= required_quantity
        ):
            return StopVerificationSummary(
                verified=True,
                side=side,
                required_quantity=required_quantity,
                verified_quantity=order.quantity,
                broker_order_id_present=True,
                client_order_id_present=True,
                status=order.status,
            )
    return StopVerificationSummary(
        verified=False,
        side=side,
        required_quantity=required_quantity,
        verified_quantity=0.0,
        reason="matching_open_stop_not_found",
    )


def _stop_verification_from_order(
    order: BrokerOrder | None,
    *,
    required_quantity: float,
) -> StopVerificationSummary | None:
    if order is None:
        return None
    return StopVerificationSummary(
        verified=order.is_open and order.quantity + 1e-9 >= required_quantity,
        side=order.side,
        required_quantity=required_quantity,
        verified_quantity=order.quantity,
        broker_order_id_present=True,
        client_order_id_present=True,
        status=order.status,
    )


def _aggregate_stop_protection(
    client: ActivationRehearsalClient,
    *,
    symbol: str,
    side: Literal["buy", "sell"],
    required_position_quantity: float,
) -> AggregateProtectionSummary:
    protected_qty = 0.0
    for order_payload in client.list_open_orders():
        order = map_alpaca_order(order_payload)
        if order.symbol == symbol.upper() and order.order_type == "stop" and order.side == side:
            protected_qty += order.quantity
    passed = protected_qty + 1e-9 >= required_position_quantity
    return AggregateProtectionSummary(
        passed=passed,
        position_quantity=required_position_quantity,
        protected_quantity_sum=protected_qty,
        reason_code="aggregate_protection_ok" if passed else "aggregate_protection_shortfall",
    )


def _emergency_stop(
    client: ActivationRehearsalClient,
    *,
    symbol: str,
    side: Literal["buy", "sell"],
    quantity: float,
    stop_price: float,
    client_order_id: str,
) -> StopVerificationSummary:
    if quantity <= 0:
        return StopVerificationSummary(
            verified=True,
            side=side,
            required_quantity=0.0,
            verified_quantity=0.0,
            status="noop",
        )
    payload = {
        "symbol": symbol,
        "side": side,
        "type": "stop",
        "time_in_force": "gtc",
        "qty": _format_quantity(quantity),
        "stop_price": str(stop_price),
        "client_order_id": client_order_id,
        "extended_hours": False,
    }
    order = map_alpaca_order(client.submit_order(payload))
    verified_order = _stop_verification_from_order(order, required_quantity=quantity)
    return verified_order or StopVerificationSummary(
        verified=False,
        side=side,
        required_quantity=quantity,
        verified_quantity=0.0,
        reason="emergency_stop_not_verified",
    )


def _request_summary(payload: Mapping[str, Any], *, role: str) -> OrderRequestSummary:
    return OrderRequestSummary(
        symbol=str(payload["symbol"]).upper(),
        side=cast(Literal["buy", "sell"], payload["side"]),
        quantity=float(payload["qty"]),
        order_type=cast(Literal["market", "limit", "stop"], payload["type"]),
        time_in_force=str(payload["time_in_force"]),
        role=role,
        limit_price=_optional_float(payload.get("limit_price")),
        stop_price=_optional_float(payload.get("stop_price")),
        client_order_id_present=bool(payload.get("client_order_id")),
    )


def _order_result(order: BrokerOrder, *, submitted: bool) -> OrderResultSummary:
    return OrderResultSummary(
        submitted=submitted,
        status=order.status,
        side=order.side,
        filled_quantity=order.filled_quantity,
        broker_order_id_present=True,
        client_order_id_present=True,
    )


def _short_limit_price(reference_price: float) -> float:
    return max(0.01, round(reference_price * 0.99, 2))


def _short_stop_price(entry_price: float) -> float:
    return round(entry_price * 1.03, 2)


def _long_limit_price(reference_price: float) -> float:
    return max(0.01, round(reference_price * 1.01, 2))


def _long_stop_price(entry_price: float) -> float:
    return max(0.01, round(entry_price * 0.97, 2))


def _asset_class_for_symbol(symbol: str) -> Literal["equity", "etf"]:
    etf_symbols = {"SPY", "QQQ", "DIA", "IWM", "XLK", "XLF", "XLE", "XLV"}
    return "etf" if symbol.upper() in etf_symbols else "equity"


def _format_quantity(quantity: float) -> str:
    if float(quantity).is_integer():
        return str(int(quantity))
    return f"{quantity:.6f}".rstrip("0").rstrip(".")


def _client_order_id(prefix: str, symbol: str, now: datetime) -> str:
    timestamp = now.strftime("%Y%m%dT%H%M%SZ")
    digest = short_hash(f"{prefix}-{symbol}-{timestamp}", 8)
    return f"{prefix}-{symbol}-{timestamp}-{digest}"


def _packet_id(prefix: str, now: datetime) -> str:
    return f"{prefix}-{now.strftime('%Y%m%dT%H%M%SZ')}"


def _now(current_time: Callable[[], datetime] | None) -> datetime:
    now = (current_time or (lambda: datetime.now(UTC)))()
    if now.tzinfo is None:
        return now.replace(tzinfo=UTC)
    return now


def _tiingo_gate_go() -> bool:
    path = Path(PRIMARY_SIGNAL_DATA_GATE_M44C_EVIDENCE_PATH)
    if not path.is_file():
        return False
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return False
    payload = payload.get("primary_signal_data_gate_m44c", payload)
    return (
        payload.get("configured_primary_signal_provider") == "tiingo"
        and payload.get("configured_primary_signal_feed") == "eod"
        and payload.get("non_iex_primary_signal_data_verified") is True
        and payload.get("m45_readiness_impact") == "go"
        and not payload.get("blockers")
    )


def _write_json(payload: Mapping[str, Any], path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _sanitized_exception(prefix: str, exc: BaseException) -> str:
    code = getattr(exc, "code", type(exc).__name__)
    return f"{prefix}:{code}"


def _optional_bool(value: object) -> bool | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    normalized = str(value).strip().lower()
    if normalized in {"true", "1", "yes"}:
        return True
    if normalized in {"false", "0", "no"}:
        return False
    return None


def _bool(value: object) -> bool:
    parsed = _optional_bool(value)
    return bool(parsed)


def _optional_float(value: object) -> float | None:
    if value in (None, ""):
        return None
    if not isinstance(value, str | int | float):
        raise ValueError(f"expected numeric value, got {type(value).__name__}")
    return float(value)


class FakeActivationRehearsalClient:
    """In-memory broker for default tests and fake M44D scenario."""

    def __init__(
        self,
        *,
        account: Mapping[str, Any] | None = None,
        assets: Mapping[str, Mapping[str, Any]] | None = None,
        prices: Mapping[str, float] | None = None,
        orders: Sequence[Mapping[str, Any]] = (),
        positions: Sequence[Mapping[str, Any]] = (),
        submit_statuses: Sequence[tuple[str, float | None]] = (),
    ) -> None:
        self.account_payload = dict(account or _default_account())
        self.assets = {
            symbol.upper(): dict(payload)
            for symbol, payload in (assets or _default_assets()).items()
        }
        self.prices = {
            symbol.upper(): price
            for symbol, price in (prices or _default_prices()).items()
        }
        self.orders_by_id = {str(order["id"]): dict(order) for order in orders}
        self.orders_by_client_order_id = {
            str(order["client_order_id"]): dict(order) for order in orders
        }
        self.positions_by_symbol = {
            str(position["symbol"]).upper(): dict(position) for position in positions
        }
        self.submit_statuses = list(submit_statuses)
        self.submitted_order_requests: list[dict[str, Any]] = []
        self.cancelled_broker_order_ids: list[str] = []
        self.clock_payload = {
            "is_open": True,
            "timestamp": _fake_timestamp(2026, 5, 18, 14, 30),
            "next_open": _fake_timestamp(2026, 5, 19, 13, 30),
            "next_close": _fake_timestamp(2026, 5, 18, 20, 0),
        }

    def get_account(self) -> Mapping[str, Any]:
        return dict(self.account_payload)

    def get_clock(self) -> Mapping[str, Any]:
        return dict(self.clock_payload)

    def list_open_orders(self) -> Sequence[Mapping[str, Any]]:
        return tuple(
            dict(order)
            for order in self.orders_by_id.values()
            if str(order.get("status")) in {"new", "accepted", "pending_new", "partially_filled"}
        )

    def list_positions(self) -> Sequence[Mapping[str, Any]]:
        return tuple(dict(position) for position in self.positions_by_symbol.values())

    def get_position(self, symbol: str) -> Mapping[str, Any] | None:
        position = self.positions_by_symbol.get(symbol.upper())
        return None if position is None else dict(position)

    def get_order_by_id(self, broker_order_id: str) -> Mapping[str, Any] | None:
        order = self.orders_by_id.get(broker_order_id)
        return None if order is None else dict(order)

    def get_order_by_client_order_id(self, client_order_id: str) -> Mapping[str, Any] | None:
        order = self.orders_by_client_order_id.get(client_order_id)
        return None if order is None else dict(order)

    def submit_order(self, request: Mapping[str, Any]) -> Mapping[str, Any]:
        payload = dict(request)
        self.submitted_order_requests.append(payload)
        requested_qty = float(payload["qty"])
        status = "accepted" if payload["type"] == "stop" else "filled"
        filled_qty = 0.0 if payload["type"] == "stop" else requested_qty
        if self.submit_statuses:
            next_status, next_filled_qty = self.submit_statuses.pop(0)
            status = next_status
            if next_filled_qty is not None:
                filled_qty = next_filled_qty
        broker_order_id = f"m44d-paper-order-{len(self.orders_by_id) + 1}"
        order = {
            "id": broker_order_id,
            "client_order_id": payload["client_order_id"],
            "symbol": payload["symbol"],
            "side": payload["side"],
            "asset_class": _asset_class_for_symbol(str(payload["symbol"])),
            "qty": str(requested_qty),
            "filled_qty": str(filled_qty),
            "type": payload["type"],
            "time_in_force": payload["time_in_force"],
            "status": status,
            "limit_price": payload.get("limit_price"),
            "stop_price": payload.get("stop_price"),
            "submitted_at": self.clock_payload["timestamp"],
            "updated_at": self.clock_payload["timestamp"],
        }
        self.orders_by_id[broker_order_id] = dict(order)
        self.orders_by_client_order_id[str(payload["client_order_id"])] = dict(order)
        if status == "filled" and filled_qty > 0:
            self._apply_fill(order)
        return dict(order)

    def cancel_order(self, broker_order_id: str) -> Mapping[str, Any]:
        order = self.orders_by_id.get(broker_order_id)
        if order is None:
            raise AlpacaClientError("order_not_found", "fake order not found")
        cancelled = dict(order) | {
            "status": "cancelled",
            "updated_at": self.clock_payload["timestamp"],
        }
        self.orders_by_id[broker_order_id] = dict(cancelled)
        self.orders_by_client_order_id[str(cancelled["client_order_id"])] = dict(cancelled)
        self.cancelled_broker_order_ids.append(broker_order_id)
        return cancelled

    def get_asset(self, symbol: str) -> Mapping[str, Any] | None:
        asset = self.assets.get(symbol.upper())
        return None if asset is None else dict(asset)

    def get_latest_trade_price(self, symbol: str) -> float | None:
        return self.prices.get(symbol.upper())

    def _apply_fill(self, order: Mapping[str, Any]) -> None:
        symbol = str(order["symbol"]).upper()
        side = str(order["side"])
        qty = float(order["filled_qty"])
        price = float(order.get("limit_price") or order.get("stop_price") or self.prices[symbol])
        existing = self.positions_by_symbol.get(symbol)
        existing_qty = 0.0 if existing is None else float(existing["qty"])
        if side == "buy":
            new_qty = existing_qty + qty
        else:
            new_qty = existing_qty - qty
        if abs(new_qty) <= 1e-9:
            self.positions_by_symbol.pop(symbol, None)
            return
        self.positions_by_symbol[symbol] = {
            "symbol": symbol,
            "asset_class": _asset_class_for_symbol(symbol),
            "qty": str(new_qty),
            "avg_entry_price": str(price),
            "market_value": str(new_qty * price),
            "opened_at": self.clock_payload["timestamp"],
        }


def _default_account() -> dict[str, Any]:
    return {
        "id": "paper-account",
        "equity": "100000",
        "cash": "100000",
        "buying_power": "200000",
        "shorting_enabled": True,
        "currency": "USD",
        "as_of": datetime(2026, 5, 18, 14, 30, tzinfo=UTC).isoformat().replace("+00:00", "Z"),
    }


def _fake_timestamp(year: int, month: int, day: int, hour: int, minute: int) -> str:
    return datetime(year, month, day, hour, minute, tzinfo=UTC).isoformat().replace(
        "+00:00",
        "Z",
    )


def _default_assets() -> dict[str, dict[str, Any]]:
    return {
        symbol: {
            "symbol": symbol,
            "asset_class": "us_equity_etf",
            "tradable": True,
            "marginable": True,
            "shortable": True,
            "easy_to_borrow": True,
        }
        for symbol in (*SHORT_CANDIDATES, *SCALE_IN_CANDIDATES)
    }


def _default_prices() -> dict[str, float]:
    return {"IWM": 205.0, "SPY": 530.0, "XLK": 210.0, "XLF": 45.0}


def cli_request_from_args(args: Any) -> ActivationRehearsalRequest:
    return ActivationRehearsalRequest(
        mode=getattr(args, "broker_mode", "real-paper"),
        rehearsal_mode=getattr(args, "mode", "full"),
        operator_approval=getattr(args, "operator_approval", None),
        short_primary_symbol=getattr(args, "short_primary_symbol", "IWM"),
        short_fallback_symbol=getattr(args, "short_fallback_symbol", "SPY"),
        scale_primary_symbol=getattr(args, "scale_primary_symbol", "XLK"),
        scale_fallback_symbol=getattr(args, "scale_fallback_symbol", "XLF"),
        short_max_qty=getattr(args, "short_max_qty", 1),
        scale_initial_max_qty=getattr(args, "scale_initial_max_qty", 1),
        scale_addon_max_qty=getattr(args, "scale_addon_max_qty", 1),
        confirm_paper_endpoint=getattr(args, "confirm_paper_endpoint", False),
        confirm_short_rehearsal_only=getattr(args, "confirm_short_rehearsal_only", False),
        confirm_scale_in_rehearsal_only=getattr(args, "confirm_scale_in_rehearsal_only", False),
        confirm_protective_buy_stop_required=getattr(
            args,
            "confirm_protective_buy_stop_required",
            False,
        ),
        confirm_additive_sell_stop_required=getattr(
            args,
            "confirm_additive_sell_stop_required",
            False,
        ),
        confirm_cleanup_to_flat=getattr(args, "confirm_cleanup_to_flat", False),
        confirm_no_live_trading=getattr(args, "confirm_no_live_trading", False),
        confirm_no_autonomous_live=getattr(args, "confirm_no_autonomous_live", False),
        confirm_no_schedules=getattr(args, "confirm_no_schedules", False),
        confirm_no_leverage=getattr(args, "confirm_no_leverage", False),
        confirm_no_frozen_validation_start=getattr(
            args,
            "confirm_no_frozen_validation_start",
            False,
        ),
        confirm_level4_not_ready=getattr(args, "confirm_level4_not_ready", False),
    )


def load_runtime_request_environment() -> Mapping[str, str]:
    return load_preflight_environment()
