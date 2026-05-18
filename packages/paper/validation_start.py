"""Milestone 45 frozen paper validation start gates.

This module starts only the paper-validation clock and local schedule registry evidence.
It performs no broker writes and does not connect to Temporal Cloud.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Literal, Protocol
from uuid import NAMESPACE_URL, uuid5

from pydantic import BaseModel, ConfigDict, Field

from packages.broker.alpaca import (
    AlpacaClientError,
    AlpacaPaperCredentials,
    AlpacaPaperReadOnlyHttpClient,
    map_alpaca_account,
    map_alpaca_clock,
    map_alpaca_order,
    map_alpaca_position,
)
from packages.core.config import CONFIG_FILES, AppConfig, load_app_config
from packages.paper.preflight import load_preflight_environment

M45_APPROVAL = "MILESTONE_45_START_8_WEEK_LONG_SHORT_SCALEIN_FROZEN_PAPER_VALIDATION"
FROZEN_PAPER_VALIDATION_START_M45_EVIDENCE_PATH = (
    "docs/evidence/frozen_paper_validation_start_m45.json"
)
LATEST_V06_SPEC_PATH = "docs/app/Autonomous_AI_Trading_Bot_SPEC_v0.6.md"
FLAT_START_CLEANUP_M44_EVIDENCE_PATH = "docs/evidence/flat_start_cleanup_m44.json"
FROZEN_READINESS_M44_EVIDENCE_PATH = "docs/evidence/frozen_readiness_m44.json"
PRIMARY_SIGNAL_DATA_GATE_M44C_EVIDENCE_PATH = (
    "docs/evidence/primary_signal_data_gate_m44c.json"
)
ACTIVATION_REHEARSAL_M44D_EVIDENCE_PATH = "docs/evidence/activation_rehearsal_m44d.json"
SCALE_IN_REHEARSAL_M44E_EVIDENCE_PATH = "docs/evidence/scale_in_rehearsal_m44e.json"
FROZEN_READINESS_M44E_EVIDENCE_PATH = "docs/evidence/frozen_readiness_m44e.json"

LOCAL_SCHEDULE_ID = "frozen-paper-validation-v0.6-long-short-scalein"
EXPECTED_LONG_UNIVERSE = (
    "SPY",
    "QQQ",
    "DIA",
    "IWM",
    "XLK",
    "XLF",
    "XLE",
    "XLV",
    "AAPL",
    "MSFT",
    "NVDA",
    "AMZN",
    "META",
    "GOOGL",
)
EXPECTED_SHORT_UNIVERSE = ("SPY", "QQQ", "DIA", "IWM")
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


class M45ReadOnlyClient(Protocol):
    def get_account(self) -> Mapping[str, Any]:
        """Return a paper account payload."""

    def get_clock(self) -> Mapping[str, Any]:
        """Return a market clock payload."""

    def list_open_orders(self) -> Sequence[Mapping[str, Any]]:
        """Return open order payloads."""

    def list_positions(self) -> Sequence[Mapping[str, Any]]:
        """Return position payloads."""


class M45ReadOnlyClientFactory(Protocol):
    def __call__(
        self,
        credentials: AlpacaPaperCredentials,
        timeout_seconds: float,
    ) -> M45ReadOnlyClient:
        """Build a read-only paper client."""


class M45Model(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class FrozenPaperValidationStartRequest(M45Model):
    mode: Literal["fake", "real-paper"] = "real-paper"
    operator_approval: str | None = None
    confirm_paper_only: bool = False
    confirm_flat_baseline: bool = False
    confirm_tiingo_eod_primary_signal_data: bool = False
    confirm_paper_shorts_enabled: bool = False
    confirm_live_shorting_disabled: bool = False
    confirm_long_scale_ins_enabled: bool = False
    confirm_short_scale_ins_disabled: bool = False
    confirm_no_live_trading: bool = False
    confirm_no_autonomous_live: bool = False
    confirm_no_leverage: bool = False
    confirm_ai_negative_only: bool = False
    confirm_no_forced_trades: bool = False
    confirm_level4_not_ready: bool = False
    timeout_seconds: float = Field(default=15.0, ge=1.0, le=60.0)


class BrokerBaselineSummary(M45Model):
    account_reachable: bool
    clock_reachable: bool
    clock_is_open: bool | None
    paper_endpoint_proven: bool
    open_orders_count: int = Field(ge=0)
    positions_count: int = Field(ge=0)
    reconciliation_summary: str
    symbols_with_open_orders: tuple[str, ...]
    symbols_with_positions: tuple[str, ...]


class MarketDataGateSummary(M45Model):
    provider: str
    feed: str
    mode: str
    verified: bool


class ShortReadinessSummary(M45Model):
    enabled_at_validation_start: bool
    proof_reference: str
    eligible_symbols: tuple[str, ...]
    live_shorting_enabled: bool = False
    short_scale_in_enabled: bool = False


class ScaleInReadinessSummary(M45Model):
    enabled_at_validation_start: bool
    proof_reference: str
    max_entries_per_symbol: int
    max_add_entries_per_symbol: int
    additive_stop_required: bool = True


class FrozenHashes(M45Model):
    config_hash: str
    universe_hash: str
    strategy_policy_hash: str
    risk_policy_hash: str
    execution_policy_hash: str
    reconciliation_policy_hash: str
    ai_policy_hash: str
    market_data_policy_hash: str
    schedule_hash: str
    reporting_schema_hash: str


class FrozenPolicySummary(M45Model):
    live_trading_enabled: bool = False
    autonomous_live_execution_enabled: bool = False
    leverage_enabled: bool = False
    paper_shorts_enabled: bool
    live_shorting_enabled: bool = False
    long_scale_in_enabled: bool
    short_scale_in_enabled: bool = False
    ai_negative_only: bool
    full_long_universe_enabled: bool
    forced_trades: bool = False


class ScheduleStartSummary(M45Model):
    schedule_created_or_activated: bool
    schedule_id_or_name: str | None
    schedule_final_state: str
    old_test_schedules_active: bool = False
    activation_type: Literal["local_registry", "none"]
    temporal_cloud_schedule_created: bool = False


class M45EvidenceReferences(M45Model):
    flat_start_cleanup_m44: str
    primary_signal_data_gate_m44c: str
    activation_rehearsal_m44d: str
    scale_in_rehearsal_m44e: str
    frozen_readiness_m44e: str


class FrozenPaperValidationStartPacket(M45Model):
    packet_id: str
    timestamp: datetime
    operator_approval_marker: str | None
    latest_spec_path: str
    latest_spec_version: str
    validation_start_result: Literal["GO", "NO-GO"]
    validation_status: Literal["active", "not_started"]
    validation_start_timestamp_utc: datetime | None
    validation_end_target_timestamp_utc: datetime | None
    validation_window_days: int
    references: M45EvidenceReferences
    current_broker_baseline: BrokerBaselineSummary
    current_market_data_gate: MarketDataGateSummary
    short_readiness: ShortReadinessSummary
    scale_in_readiness: ScaleInReadinessSummary
    frozen_hashes: FrozenHashes
    frozen_policy: FrozenPolicySummary
    schedule: ScheduleStartSummary
    operator_intervention_policy: tuple[str, ...]
    incident_rules: tuple[str, ...]
    reporting_requirements: tuple[str, ...]
    blockers: tuple[str, ...]
    level4_ready: bool = False
    broker_writes_performed: bool = False


class FrozenPaperValidationStartResult(M45Model):
    success: bool
    go_no_go: Literal["go", "no_go"]
    packet: FrozenPaperValidationStartPacket
    blockers: tuple[str, ...]
    broker_writes_performed: bool = False
    schedule_activated: bool


def build_m45_read_only_client(
    credentials: AlpacaPaperCredentials,
    timeout_seconds: float,
) -> M45ReadOnlyClient:
    return AlpacaPaperReadOnlyHttpClient(
        credentials=credentials,
        timeout_seconds=timeout_seconds,
    )


def run_frozen_paper_validation_start_m45(
    request: FrozenPaperValidationStartRequest,
    *,
    environ: Mapping[str, str] | None = None,
    app_config: AppConfig | None = None,
    client_factory: M45ReadOnlyClientFactory = build_m45_read_only_client,
    current_time: Callable[[], datetime] | None = None,
    repo_root: Path | None = None,
) -> FrozenPaperValidationStartResult:
    root = repo_root or Path.cwd()
    active_config = load_app_config(root / "config") if app_config is None else app_config
    active_environ = (
        load_preflight_environment(repo_root=root, base_environ=environ)
        if environ is not None
        else load_preflight_environment(repo_root=root)
    )
    timestamp = _now(current_time)
    latest_spec_path, latest_spec_version = _latest_spec(root)
    blockers = list(_request_blockers(request))
    blockers.extend(_config_blockers(active_config, latest_spec_path, latest_spec_version))

    flat_cleanup = _load_packet(
        root / FLAT_START_CLEANUP_M44_EVIDENCE_PATH,
        wrapper_key="flat_start_cleanup",
    )
    m44c_gate = _load_packet(
        root / PRIMARY_SIGNAL_DATA_GATE_M44C_EVIDENCE_PATH,
        wrapper_key="primary_signal_data_gate_m44c",
    )
    m44d_activation = _load_packet(root / ACTIVATION_REHEARSAL_M44D_EVIDENCE_PATH)
    m44e_scale = _load_packet(root / SCALE_IN_REHEARSAL_M44E_EVIDENCE_PATH)
    m44e_readiness = _load_packet(root / FROZEN_READINESS_M44E_EVIDENCE_PATH)
    blockers.extend(
        _evidence_blockers(
            flat_cleanup=flat_cleanup,
            m44c_gate=m44c_gate,
            m44d_activation=m44d_activation,
            m44e_scale=m44e_scale,
            m44e_readiness=m44e_readiness,
        )
    )

    baseline, baseline_blockers = _read_current_broker_baseline(
        request=request,
        environ=active_environ,
        client_factory=client_factory,
        gate_blockers=tuple(blockers),
    )
    blockers.extend(baseline_blockers)
    hashes = _frozen_hashes(root)
    unique_blockers = tuple(dict.fromkeys(blockers))
    success = (
        not unique_blockers
        and baseline.open_orders_count == 0
        and baseline.positions_count == 0
        and baseline.reconciliation_summary == "flat_zero_positions_zero_open_orders"
    )
    validation_start = timestamp if success else None
    validation_end = timestamp + timedelta(days=56) if success else None
    schedule = ScheduleStartSummary(
        schedule_created_or_activated=success,
        schedule_id_or_name=LOCAL_SCHEDULE_ID if success else None,
        schedule_final_state="active_local_paper_validation_registry" if success else "not_started",
        activation_type="local_registry" if success else "none",
    )
    packet = FrozenPaperValidationStartPacket(
        packet_id=_packet_id("frozen-paper-validation-start-m45", timestamp),
        timestamp=timestamp,
        operator_approval_marker=request.operator_approval,
        latest_spec_path=latest_spec_path,
        latest_spec_version=latest_spec_version,
        validation_start_result="GO" if success else "NO-GO",
        validation_status="active" if success else "not_started",
        validation_start_timestamp_utc=validation_start,
        validation_end_target_timestamp_utc=validation_end,
        validation_window_days=56,
        references=M45EvidenceReferences(
            flat_start_cleanup_m44=FLAT_START_CLEANUP_M44_EVIDENCE_PATH,
            primary_signal_data_gate_m44c=PRIMARY_SIGNAL_DATA_GATE_M44C_EVIDENCE_PATH,
            activation_rehearsal_m44d=ACTIVATION_REHEARSAL_M44D_EVIDENCE_PATH,
            scale_in_rehearsal_m44e=SCALE_IN_REHEARSAL_M44E_EVIDENCE_PATH,
            frozen_readiness_m44e=FROZEN_READINESS_M44E_EVIDENCE_PATH,
        ),
        current_broker_baseline=baseline,
        current_market_data_gate=_market_data_gate_summary(active_config, m44c_gate),
        short_readiness=ShortReadinessSummary(
            enabled_at_validation_start=(
                active_config.validation.short_policy.enabled_at_validation_start
            ),
            proof_reference=ACTIVATION_REHEARSAL_M44D_EVIDENCE_PATH,
            eligible_symbols=active_config.shorts.eligible_symbols,
            live_shorting_enabled=active_config.validation.short_policy.live_shorting_enabled,
            short_scale_in_enabled=(
                active_config.validation.scale_in_policy.short_scale_in_enabled_at_validation_start
            ),
        ),
        scale_in_readiness=ScaleInReadinessSummary(
            enabled_at_validation_start=(
                active_config.validation.scale_in_policy.enabled_at_validation_start
            ),
            proof_reference=SCALE_IN_REHEARSAL_M44E_EVIDENCE_PATH,
            max_entries_per_symbol=active_config.scale_in.max_entries_per_symbol,
            max_add_entries_per_symbol=active_config.scale_in.max_add_entries_per_symbol,
            additive_stop_required=(
                active_config.scale_in.stop_policy == "additive_stop_for_added_quantity"
                and active_config.scale_in.protective_stop_required_after_scale_in
            ),
        ),
        frozen_hashes=hashes,
        frozen_policy=FrozenPolicySummary(
            paper_shorts_enabled=active_config.validation.short_policy.enabled_at_validation_start,
            long_scale_in_enabled=(
                active_config.validation.scale_in_policy.enabled_at_validation_start
            ),
            ai_negative_only=active_config.validation.ai_policy.negative_only,
            full_long_universe_enabled=active_config.validation.universe.include_full_allowed_universe,
            forced_trades=active_config.validation.universe.force_trades,
        ),
        schedule=schedule,
        operator_intervention_policy=_operator_intervention_policy(),
        incident_rules=_incident_rules(),
        reporting_requirements=_reporting_requirements(),
        blockers=unique_blockers,
    )
    return FrozenPaperValidationStartResult(
        success=success,
        go_no_go="go" if success else "no_go",
        packet=packet,
        blockers=unique_blockers,
        schedule_activated=schedule.schedule_created_or_activated,
    )


def write_frozen_paper_validation_start_m45_artifact(
    result: FrozenPaperValidationStartResult,
    path: str | Path = FROZEN_PAPER_VALIDATION_START_M45_EVIDENCE_PATH,
) -> Path:
    return _write_json(result.packet.model_dump(mode="json"), Path(path))


def _request_blockers(request: FrozenPaperValidationStartRequest) -> tuple[str, ...]:
    blockers: list[str] = []
    if request.operator_approval != M45_APPROVAL:
        blockers.append("m45_operator_approval_marker_required")
    confirmations = {
        "confirm_paper_only": request.confirm_paper_only,
        "confirm_flat_baseline": request.confirm_flat_baseline,
        "confirm_tiingo_eod_primary_signal_data": (
            request.confirm_tiingo_eod_primary_signal_data
        ),
        "confirm_paper_shorts_enabled": request.confirm_paper_shorts_enabled,
        "confirm_live_shorting_disabled": request.confirm_live_shorting_disabled,
        "confirm_long_scale_ins_enabled": request.confirm_long_scale_ins_enabled,
        "confirm_short_scale_ins_disabled": request.confirm_short_scale_ins_disabled,
        "confirm_no_live_trading": request.confirm_no_live_trading,
        "confirm_no_autonomous_live": request.confirm_no_autonomous_live,
        "confirm_no_leverage": request.confirm_no_leverage,
        "confirm_ai_negative_only": request.confirm_ai_negative_only,
        "confirm_no_forced_trades": request.confirm_no_forced_trades,
        "confirm_level4_not_ready": request.confirm_level4_not_ready,
    }
    blockers.extend(
        f"{name}_required" for name, confirmed in confirmations.items() if not confirmed
    )
    return tuple(blockers)


def _config_blockers(config: AppConfig, latest_path: str, latest_version: str) -> tuple[str, ...]:
    blockers: list[str] = []
    if latest_version != "v0.6" or latest_path != LATEST_V06_SPEC_PATH:
        blockers.append("latest_spec_not_v0_6")
    if config.validation.active_spec_version != "v0.6":
        blockers.append("active_spec_not_v0_6")
    if config.system.environment != "paper" or config.validation.active_mode != "paper":
        blockers.append("paper_mode_not_configured")
    if config.system.live_trading_enabled or config.validation.live_trading_enabled:
        blockers.append("live_trading_enabled")
    if config.execution.allow_live_orders:
        blockers.append("live_orders_enabled")
    if (
        config.system.autonomous_execution_enabled
        or config.validation.autonomous_live_execution_enabled
    ):
        blockers.append("autonomous_live_execution_enabled")
    if config.validation.level4_ready:
        blockers.append("level4_ready_true")
    if config.risk_level_4_micro_live.allow_margin:
        blockers.append("leverage_or_margin_enabled")
    if not config.validation.flat_start_required or config.validation.carry_in_positions_allowed:
        blockers.append("flat_start_policy_not_enforced")
    if not config.validation.universe.include_full_allowed_universe:
        blockers.append("full_long_universe_not_enabled")
    if config.validation.universe.force_trades or config.validation_strategy.force_trades:
        blockers.append("forced_trades_enabled")
    if config.live_universe.symbols != EXPECTED_LONG_UNIVERSE:
        blockers.append("long_universe_not_frozen_to_expected_symbols")
    if config.shorts.eligible_symbols != EXPECTED_SHORT_UNIVERSE:
        blockers.append("short_universe_not_frozen_to_broad_etfs")
    if not config.validation.short_policy.enabled_at_validation_start:
        blockers.append("paper_shorts_not_enabled_at_validation_start")
    if not config.validation.short_policy.paper_only or not config.shorts.paper_only_short_exposure:
        blockers.append("shorts_not_paper_only")
    if config.validation.short_policy.live_shorting_enabled or config.shorts.allow_live_shorting:
        blockers.append("live_shorting_enabled")
    if (
        config.validation.scale_in_policy.short_scale_in_enabled_at_validation_start
        or config.shorts.short_scale_in_enabled_at_validation_start
    ):
        blockers.append("short_scale_ins_enabled_at_validation_start")
    if not config.validation.short_policy.real_short_lifecycle_proof_completed_by_m44d:
        blockers.append("short_lifecycle_proof_not_recorded_in_config")
    if not config.validation.scale_in_policy.enabled_at_validation_start:
        blockers.append("long_scale_ins_not_enabled_at_validation_start")
    if not config.scale_in.enabled_for_paper_validation:
        blockers.append("scale_in_not_enabled_for_paper_validation")
    if not (
        config.validation.scale_in_policy.real_additive_stop_proof_completed_by_m44d
        or config.validation.scale_in_policy.real_additive_stop_proof_completed_by_m44e
        or config.scale_in.real_additive_stop_proof_completed_by_m44d
        or config.scale_in.real_additive_stop_proof_completed_by_m44e
    ):
        blockers.append("scale_in_additive_stop_proof_not_recorded_in_config")
    if not config.scale_in.protective_stop_required_after_scale_in:
        blockers.append("additive_stop_policy_not_required")
    if config.market_data.primary_signal_provider != "tiingo":
        blockers.append("primary_signal_provider_not_tiingo")
    if config.market_data.primary_signal_feed != "eod":
        blockers.append("primary_signal_feed_not_eod")
    if config.market_data.allow_iex_only_for_frozen_validation:
        blockers.append("iex_only_signal_generation_allowed")
    if not config.market_data.require_non_iex_primary_signal_data:
        blockers.append("non_iex_signal_data_not_required")
    if not config.validation.ai_policy.negative_only or not config.validation_ai.negative_only:
        blockers.append("ai_not_negative_only")
    if config.validation.ai_policy.ai_may_authorize_trade:
        blockers.append("ai_trade_authority_enabled")
    if (
        config.validation_ai.ai_may_authorize_scale_in
        or config.validation_ai.ai_may_authorize_shorts
    ):
        blockers.append("ai_scale_in_or_short_authority_enabled")
    return tuple(blockers)


def _evidence_blockers(
    *,
    flat_cleanup: Mapping[str, Any] | None,
    m44c_gate: Mapping[str, Any] | None,
    m44d_activation: Mapping[str, Any] | None,
    m44e_scale: Mapping[str, Any] | None,
    m44e_readiness: Mapping[str, Any] | None,
) -> tuple[str, ...]:
    blockers: list[str] = []
    if not _flat_cleanup_ok(flat_cleanup):
        blockers.append("flat_start_cleanup_m44_missing_or_not_flat")
    if not _m44c_tiingo_gate_ok(m44c_gate):
        blockers.append("m44c_tiingo_gate_missing_or_not_go")
    if not _m44d_short_proof_ok(m44d_activation):
        blockers.append("m44d_short_proof_missing_or_not_go")
    if not _m44e_scale_in_proof_ok(m44e_scale):
        blockers.append("m44e_scale_in_proof_missing_or_not_go")
    if not _m44e_readiness_ok(m44e_readiness):
        blockers.append("frozen_readiness_m44e_missing_or_not_go")
    return tuple(blockers)


def _read_current_broker_baseline(
    *,
    request: FrozenPaperValidationStartRequest,
    environ: Mapping[str, str],
    client_factory: M45ReadOnlyClientFactory,
    gate_blockers: tuple[str, ...],
) -> tuple[BrokerBaselineSummary, tuple[str, ...]]:
    if gate_blockers:
        return _empty_baseline(), ()
    try:
        if request.mode == "fake":
            client: M45ReadOnlyClient = FakeM45ReadOnlyClient()
        else:
            credentials = AlpacaPaperCredentials(
                api_key=environ.get("ALPACA_API_KEY", "").strip(),
                secret_key=environ.get("ALPACA_SECRET_KEY", "").strip(),
                base_url=environ.get("ALPACA_BASE_URL", "").strip(),
            )
            client = client_factory(credentials, request.timeout_seconds)
        map_alpaca_account(client.get_account(), environment="paper")
        clock = map_alpaca_clock(client.get_clock())
        orders = tuple(map(map_alpaca_order, client.list_open_orders()))
        positions = tuple(map(map_alpaca_position, client.list_positions()))
    except (AlpacaClientError, ValueError) as exc:
        return _empty_baseline(), (_sanitized_exception("broker_read_only_baseline_failed", exc),)
    active_positions = tuple(position for position in positions if abs(position.quantity) > 1e-9)
    baseline = BrokerBaselineSummary(
        account_reachable=True,
        clock_reachable=True,
        clock_is_open=clock.is_open,
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
    blockers: list[str] = []
    if baseline.open_orders_count != 0:
        blockers.append("current_broker_open_orders_not_zero")
    if baseline.positions_count != 0:
        blockers.append("current_broker_positions_not_zero")
    if baseline.reconciliation_summary != "flat_zero_positions_zero_open_orders":
        blockers.append("current_broker_reconciliation_not_flat")
    return baseline, tuple(blockers)


def _flat_cleanup_ok(payload: Mapping[str, Any] | None) -> bool:
    return (
        payload is not None
        and payload.get("m45_flat_start_ready") is True
        and payload.get("final_open_orders_count") == 0
        and payload.get("final_positions_count") == 0
        and payload.get("final_reconciliation") == "flat_zero_positions_zero_open_orders"
        and payload.get("frozen_validation_started") is False
    )


def _m44c_tiingo_gate_ok(payload: Mapping[str, Any] | None) -> bool:
    return (
        payload is not None
        and payload.get("configured_primary_signal_provider") == "tiingo"
        and payload.get("configured_primary_signal_feed") == "eod"
        and payload.get("configured_primary_signal_mode") == "historical_completed_daily_bars"
        and payload.get("non_iex_primary_signal_data_verified") is True
        and payload.get("data_check_result") == "verified"
        and payload.get("m45_readiness_impact") == "go"
        and not payload.get("blockers")
        and payload.get("broker_writes_performed") is False
        and payload.get("schedules_activated") is False
        and payload.get("frozen_validation_started") is False
    )


def _m44d_short_proof_ok(payload: Mapping[str, Any] | None) -> bool:
    if payload is None:
        return False
    short = payload.get("short_rehearsal")
    final_state = payload.get("final_broker_baseline")
    if not isinstance(short, Mapping) or not isinstance(final_state, Mapping):
        return False
    return (
        payload.get("real_short_broker_write_performed") is True
        and short.get("succeeded") is True
        and short.get("selected_symbol") in EXPECTED_SHORT_UNIVERSE
        and _filled_side(short.get("short_entry_result"), side="sell")
        and _filled_side(short.get("fill_result"), side="sell")
        and _verified_stop(short.get("protective_buy_stop_verification"), side="buy")
        and _filled_side(short.get("buy_to_cover_result"), side="buy")
        and not short.get("blockers")
        and short.get("final_open_orders_count") == 0
        and short.get("final_positions_count") == 0
        and short.get("final_reconciliation") == "flat_zero_positions_zero_open_orders"
        and final_state.get("open_orders_count") == 0
        and final_state.get("positions_count") == 0
        and payload.get("frozen_validation_started") is False
        and payload.get("schedules_activated") is False
    )


def _m44e_scale_in_proof_ok(payload: Mapping[str, Any] | None) -> bool:
    if payload is None:
        return False
    aggregate = payload.get("aggregate_long_protection_check")
    return (
        payload.get("m44d_short_proof_accepted") is True
        and payload.get("m45_long_short_scalein_readiness") is True
        and payload.get("real_scale_in_broker_write_performed") is True
        and _filled_side(payload.get("initial_entry_result"), side="buy")
        and _filled_side(payload.get("initial_fill_result"), side="buy")
        and _verified_stop(payload.get("initial_protective_stop_result"), side="sell")
        and _filled_side(payload.get("scale_in_fill_result"), side="buy")
        and _verified_stop(payload.get("additive_protective_stop_result"), side="sell")
        and isinstance(aggregate, Mapping)
        and aggregate.get("passed") is True
        and float(aggregate.get("protected_quantity_sum") or 0.0) >= 2.0
        and payload.get("final_open_orders_count") == 0
        and payload.get("final_positions_count") == 0
        and payload.get("final_reconciliation") == "flat_zero_positions_zero_open_orders"
        and not payload.get("blockers")
        and payload.get("frozen_validation_started") is False
        and payload.get("schedules_activated") is False
    )


def _m44e_readiness_ok(payload: Mapping[str, Any] | None) -> bool:
    return (
        payload is not None
        and payload.get("m45_readiness") is True
        and payload.get("m44d_short_proof_accepted") is True
        and payload.get("m44e_scale_in_rehearsal_succeeded") is True
        and payload.get("tiingo_gate_status") == "go"
        and payload.get("shorts_enabled_at_validation_start") is True
        and payload.get("scale_in_enabled_at_validation_start") is True
        and payload.get("short_scale_in_enabled_at_validation_start") is False
        and not payload.get("blockers")
        and payload.get("frozen_validation_started") is False
        and payload.get("schedules_activated") is False
    )


def _filled_side(value: object, *, side: str) -> bool:
    return (
        isinstance(value, Mapping)
        and value.get("side") == side
        and float(value.get("filled_quantity") or 0.0) > 0.0
        and value.get("status") == "filled"
    )


def _verified_stop(value: object, *, side: str) -> bool:
    return (
        isinstance(value, Mapping)
        and value.get("verified") is True
        and value.get("side") == side
        and float(value.get("verified_quantity") or 0.0) > 0.0
    )


def _market_data_gate_summary(
    config: AppConfig,
    gate_payload: Mapping[str, Any] | None,
) -> MarketDataGateSummary:
    return MarketDataGateSummary(
        provider=config.market_data.primary_signal_provider,
        feed=config.market_data.primary_signal_feed,
        mode=config.market_data.primary_signal_mode,
        verified=_m44c_tiingo_gate_ok(gate_payload),
    )


def _frozen_hashes(repo_root: Path) -> FrozenHashes:
    return FrozenHashes(
        config_hash=_hash_paths([repo_root / "config" / name for name in CONFIG_FILES]),
        universe_hash=_hash_paths([repo_root / "config/universe.yaml"]),
        strategy_policy_hash=_hash_paths(
            [repo_root / "config/strategy.yaml", repo_root / "docs/validation_plan.md"]
        ),
        risk_policy_hash=_hash_paths(
            [repo_root / "config/risk.yaml", repo_root / "docs/risk_policy.md"]
        ),
        execution_policy_hash=_hash_paths(
            [repo_root / "config/execution.yaml", repo_root / "docs/execution_policy.md"]
        ),
        reconciliation_policy_hash=_hash_paths([repo_root / "packages/reconciliation"]),
        ai_policy_hash=_hash_paths(
            [repo_root / "config/ai.yaml", repo_root / "docs/ai_intelligence.md"]
        ),
        market_data_policy_hash=_hash_paths([repo_root / "config/market_data.yaml"]),
        schedule_hash=_hash_paths(
            [repo_root / "config/temporal.yaml", repo_root / "docs/temporal_workflows.md"]
        ),
        reporting_schema_hash=_hash_paths(
            [repo_root / "docs/reporting.md", repo_root / "packages/reporting"]
        ),
    )


def _hash_paths(paths: Sequence[Path]) -> str:
    digest = hashlib.sha256()
    for path in sorted(paths, key=lambda item: str(item)):
        if path.is_dir():
            nested = sorted(
                child
                for child in path.rglob("*")
                if child.is_file() and "__pycache__" not in child.parts
            )
            for child in nested:
                _hash_file(digest, child)
        elif path.is_file():
            _hash_file(digest, path)
        else:
            digest.update(f"missing:{path.as_posix()}\n".encode())
    return digest.hexdigest()


def _hash_file(digest: Any, path: Path) -> None:
    digest.update(path.as_posix().encode("utf-8"))
    digest.update(b"\0")
    digest.update(path.read_bytes())
    digest.update(b"\0")


def _latest_spec(repo_root: Path) -> tuple[str, str]:
    spec_dir = repo_root / "docs/app"
    candidates: list[tuple[tuple[int, ...], Path, str]] = []
    for path in spec_dir.glob("Autonomous_AI_Trading_Bot_SPEC_v*.md"):
        match = re.search(r"_SPEC_v(\d+(?:\.\d+)*)\.md$", path.name)
        if match is None:
            continue
        version_tuple = tuple(int(part) for part in match.group(1).split("."))
        candidates.append((version_tuple, path, f"v{match.group(1)}"))
    if not candidates:
        return "", ""
    _version, path, label = max(candidates, key=lambda item: item[0])
    return path.relative_to(repo_root).as_posix(), label


def _load_packet(path: Path, wrapper_key: str | None = None) -> Mapping[str, Any] | None:
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, Mapping):
        return None
    if wrapper_key is not None:
        wrapped = payload.get(wrapper_key, payload)
        return wrapped if isinstance(wrapped, Mapping) else None
    return payload


def _empty_baseline() -> BrokerBaselineSummary:
    return BrokerBaselineSummary(
        account_reachable=False,
        clock_reachable=False,
        clock_is_open=None,
        paper_endpoint_proven=False,
        open_orders_count=0,
        positions_count=0,
        reconciliation_summary="unavailable",
        symbols_with_open_orders=(),
        symbols_with_positions=(),
    )


def _operator_intervention_policy() -> tuple[str, ...]:
    return (
        "pause_or_kill_switch",
        "manual_review",
        "stop_repair",
        "risk_reducing_cleanup",
        "disable_schedule_after_incident",
        "restart_only_after_documented_incident_review",
        "credential_rotation_if_compromised",
        "non_strategy_operational_bugfix_with_evidence",
    )


def _incident_rules() -> tuple[str, ...]:
    return (
        "missing_or_unverified_protective_stop_blocks_new_risk",
        "broker_state_mismatch_blocks_new_risk",
        "unexpected_position_or_open_order_blocks_new_risk",
        "short_without_verified_buy_stop_is_critical_incident",
        "scale_in_without_additive_stop_is_critical_incident",
        "operator_strategy_override_contaminates_validation",
    )


def _reporting_requirements() -> tuple[str, ...]:
    return (
        "daily_reconciliation_report",
        "daily_trade_plan_snapshot",
        "daily_evidence_packet_for_scheduled_run",
        "weekly_validation_summary",
        "incident_report_for_any_no_go_or_repair",
    )


def _packet_id(prefix: str, now: datetime) -> str:
    return f"{prefix}-{now.strftime('%Y%m%dT%H%M%SZ')}"


def _now(current_time: Callable[[], datetime] | None) -> datetime:
    now = (current_time or (lambda: datetime.now(UTC)))()
    if now.tzinfo is None:
        return now.replace(tzinfo=UTC)
    return now.astimezone(UTC)


def _write_json(payload: Mapping[str, Any], path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _sanitized_exception(prefix: str, exc: BaseException) -> str:
    code = getattr(exc, "code", type(exc).__name__)
    return f"{prefix}:{code}"


class FakeM45ReadOnlyClient:
    """Read-only in-memory broker baseline used by M45 unit tests."""

    def __init__(
        self,
        *,
        orders: Sequence[Mapping[str, Any]] = (),
        positions: Sequence[Mapping[str, Any]] = (),
    ) -> None:
        self.orders = tuple(dict(order) for order in orders)
        self.positions = tuple(dict(position) for position in positions)

    def get_account(self) -> Mapping[str, Any]:
        return {
            "id": str(uuid5(NAMESPACE_URL, "m45-paper-account")),
            "equity": "100000",
            "cash": "100000",
            "buying_power": "100000",
            "shorting_enabled": True,
            "multiplier": "1",
            "currency": "USD",
        }

    def get_clock(self) -> Mapping[str, Any]:
        now = datetime.now(UTC).isoformat()
        return {
            "is_open": True,
            "timestamp": now,
            "next_open": now,
            "next_close": now,
        }

    def list_open_orders(self) -> Sequence[Mapping[str, Any]]:
        return self.orders

    def list_positions(self) -> Sequence[Mapping[str, Any]]:
        return self.positions
