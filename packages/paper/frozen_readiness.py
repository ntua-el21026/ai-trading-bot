"""Milestone 44 frozen-readiness, flat-start cleanup, and baseline helpers.

The real cleanup path is intentionally narrow: it may only close existing long AAPL/MSFT/XLK
paper holds after their protective stops are verified and cancelled. This module never submits
short orders and never starts frozen validation.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import time
from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Literal, Protocol
from uuid import NAMESPACE_URL, uuid5

from pydantic import BaseModel, ConfigDict, Field, field_validator

from packages.broker.alpaca import (
    ALPACA_PAPER_BASE_URL,
    AlpacaClientError,
    AlpacaPaperAdapter,
    AlpacaPaperCredentials,
    map_alpaca_clock,
    map_alpaca_order,
)
from packages.broker.fakes import FakeAlpacaClient
from packages.broker.models import BrokerClockSnapshot, BrokerOrder, BrokerPosition
from packages.broker.order_lifecycle_smoke import (
    AlpacaPaperOrderLifecycleClient,
    AlpacaPaperOrderLifecycleHttpClient,
)
from packages.core.config import AppConfig, load_app_config
from packages.execution.models import ExecutionIntent
from packages.paper.preflight import load_preflight_environment

M44_FLAT_START_CLEANUP_APPROVAL = "MILESTONE_44_FLAT_START_CLEANUP_AND_BASELINE"
FLAT_START_CLEANUP_M44_EVIDENCE_PATH = "docs/evidence/flat_start_cleanup_m44.json"
FROZEN_READINESS_M44_EVIDENCE_PATH = "docs/evidence/frozen_readiness_m44.json"
M43_SCALE_IN_POLICY_EVIDENCE_PATH = "docs/evidence/scale_in_policy_m43.json"
M42_SUPERVISED_SCHEDULED_RUN_EVIDENCE_PATH = (
    "docs/evidence/supervised_scheduled_paper_run_m42.json"
)
LATEST_V05_SPEC_PATH = "docs/app/Autonomous_AI_Trading_Bot_SPEC_v0.5.md"
EXPECTED_CLEANUP_SYMBOLS = ("AAPL", "MSFT", "XLK")
SENSITIVE_TOKEN_NAMES = (
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

Sleeper = Callable[[float], None]
Clock = Callable[[], float]


class M44ClientFactory(Protocol):
    def __call__(
        self,
        credentials: AlpacaPaperCredentials,
        timeout_seconds: float,
    ) -> AlpacaPaperOrderLifecycleClient:
        """Build a write-capable paper client after explicit M44 gates pass."""


class FrozenReadinessModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class FlatStartCleanupRequest(FrozenReadinessModel):
    mode: Literal["fake", "real-paper"] = "fake"
    operator_approval: str | None = None
    symbols: tuple[str, ...] = EXPECTED_CLEANUP_SYMBOLS
    confirm_paper_endpoint: bool = False
    confirm_risk_reducing_only: bool = False
    confirm_cancel_session_stop_before_sell: bool = False
    confirm_emergency_reprotect_if_sell_fails: bool = False
    confirm_no_new_entry: bool = False
    confirm_no_buy_orders: bool = False
    confirm_no_short_orders: bool = False
    confirm_no_live_trading: bool = False
    confirm_no_autonomous_live: bool = False
    confirm_no_schedules: bool = False
    confirm_no_leverage: bool = False
    cleanup_timeout_seconds: float = Field(default=30.0, ge=0, le=180.0)

    @field_validator("symbols")
    @classmethod
    def validate_symbols(cls, symbols: tuple[str, ...]) -> tuple[str, ...]:
        normalized = tuple(symbol.upper() for symbol in symbols)
        if normalized != EXPECTED_CLEANUP_SYMBOLS:
            raise ValueError("M44 cleanup is limited to AAPL, MSFT, and XLK in that order")
        return normalized


class SymbolCleanupState(FrozenReadinessModel):
    symbol: str
    position_status: Literal["open_long", "flat", "short_or_ambiguous"]
    position_quantity: float
    protective_stop_verified: bool
    protective_stop_quantity: float | None = None
    protective_stop_client_order_id_present: bool = False
    protective_stop_broker_order_id_present: bool = False
    protective_stop_client_order_id: str | None = Field(default=None, exclude=True)
    protective_stop_broker_order_id: str | None = Field(default=None, exclude=True)
    protective_stop_status: str | None = None


class BrokerBaselineState(FrozenReadinessModel):
    account_reachable: bool
    clock_reachable: bool
    clock_is_open: bool | None
    paper_endpoint_proven: bool
    open_orders_count: int = Field(ge=0)
    positions_count: int = Field(ge=0)
    expected_stop_order_count: int = Field(ge=0)
    unexpected_open_order_symbols: tuple[str, ...]
    unexpected_position_symbols: tuple[str, ...]
    symbol_states: tuple[SymbolCleanupState, ...]
    baseline_paper_equity: float | None = None


class CleanupWriteRecord(FrozenReadinessModel):
    operation: Literal[
        "cancel_session_protective_stop",
        "submit_cleanup_sell",
        "submit_emergency_protective_stop",
        "cancel_stale_orphan_stop",
    ]
    symbol: str
    attempted: bool
    side: Literal["buy", "sell"] | None
    quantity: float | None
    order_type: str | None
    status: str
    broker_order_id_present: bool
    client_order_id_present: bool
    fake_only: bool


class SymbolCleanupAction(FrozenReadinessModel):
    symbol: str
    pre_state: SymbolCleanupState
    strategy: str
    stop_cancellation_result: str | None = None
    sell_result: str | None = None
    emergency_reprotection_result: str | None = None
    final_state: SymbolCleanupState | None = None
    blockers: tuple[str, ...] = ()


class FlatStartCleanupPacket(FrozenReadinessModel):
    packet_id: str
    timestamp: datetime
    spec_version: Literal["v0.5"] = "v0.5"
    latest_spec_path: str = LATEST_V05_SPEC_PATH
    operator_approval_marker: str | None
    pre_cleanup_broker_state: BrokerBaselineState
    per_symbol_cleanup_actions: tuple[SymbolCleanupAction, ...]
    stop_cancellation_results: tuple[str, ...]
    sell_results: tuple[str, ...]
    emergency_reprotection_results: tuple[str, ...]
    final_broker_state: BrokerBaselineState
    final_open_orders_count: int
    final_positions_count: int
    final_reconciliation: str
    baseline_paper_equity: float | None
    broker_writes_performed: bool
    broker_writes: tuple[CleanupWriteRecord, ...]
    live_trading_enabled: bool = False
    autonomous_live_execution_enabled: bool = False
    leverage_enabled: bool = False
    short_orders_performed: bool = False
    schedules_activated: bool = False
    frozen_validation_started: bool = False
    m45_flat_start_ready: bool
    blockers: tuple[str, ...]


class FlatStartCleanupResult(FrozenReadinessModel):
    success: bool
    go_no_go: Literal["go", "no_go"]
    packet: FlatStartCleanupPacket
    blockers: tuple[str, ...]
    broker_writes_performed: bool
    real_broker_writes_performed: bool
    real_read_only_calls_performed: bool


class M44ReadinessPacket(FrozenReadinessModel):
    packet_id: str
    timestamp: datetime
    latest_spec_path: str = LATEST_V05_SPEC_PATH
    latest_spec_version: Literal["v0.5"] = "v0.5"
    git_commit_hash: str
    config_hash: str
    universe_hash: str
    strategy_policy_hash: str
    risk_policy_hash: str
    execution_policy_hash: str
    reconciliation_policy_hash: str
    ai_news_policy_hash: str
    schedule_hash: str
    reporting_schema_version_hash: str
    dashboard_validation_view_status: str
    data_provider_status: str
    non_iex_data_gate_status: str
    broker_baseline_packet_reference: str
    flat_start_required: bool = True
    flat_start_achieved: bool
    open_orders_count: int = Field(ge=0)
    positions_count: int = Field(ge=0)
    reconciliation_summary: str
    shorts_implementation_present: bool
    shorts_enabled: bool
    short_universe: tuple[str, ...]
    scale_in_implementation_present: bool
    scale_in_enabled_at_validation_start: bool
    scale_in_stage_gate: dict[str, str | int | bool]
    active_exits: tuple[str, ...]
    ai_negative_only_policy: dict[str, bool | int]
    operator_intervention_policy: tuple[str, ...]
    incident_rules: tuple[str, ...]
    m45_readiness: bool
    blockers: tuple[str, ...]
    live_trading_enabled: bool = False
    autonomous_live_execution_enabled: bool = False
    leverage_enabled: bool = False
    frozen_validation_started: bool = False
    level4_ready: bool = False
    schedules_activated: bool = False


def build_alpaca_paper_order_lifecycle_client(
    credentials: AlpacaPaperCredentials,
    timeout_seconds: float,
) -> AlpacaPaperOrderLifecycleClient:
    return AlpacaPaperOrderLifecycleHttpClient(
        credentials=credentials,
        timeout_seconds=max(timeout_seconds, 1.0),
    )


def run_flat_start_cleanup_m44(
    request: FlatStartCleanupRequest,
    *,
    environ: Mapping[str, str] | None = None,
    app_config: AppConfig | None = None,
    client_factory: M44ClientFactory = build_alpaca_paper_order_lifecycle_client,
    now: datetime | None = None,
    sleeper: Sleeper = time.sleep,
    clock: Clock = time.monotonic,
) -> FlatStartCleanupResult:
    active_config = load_app_config() if app_config is None else app_config
    active_environ = (
        load_preflight_environment(repo_root=Path.cwd(), base_environ=environ)
        if environ is not None
        else load_preflight_environment(repo_root=Path.cwd())
    )
    timestamp = now or datetime.now(UTC)
    gate_blockers = _cleanup_gate_blockers(request, active_config, active_environ)
    client, adapter, client_blockers, fake_only = _client_and_adapter(
        request=request,
        app_config=active_config,
        environ=active_environ,
        client_factory=client_factory,
        gate_blockers=gate_blockers,
        timestamp=timestamp,
    )
    blockers = list(_unique((*gate_blockers, *client_blockers)))

    if adapter is None or client is None:
        pre_state = _empty_baseline_state()
        packet = _cleanup_packet(
            request=request,
            timestamp=timestamp,
            pre_state=pre_state,
            actions=(),
            final_state=pre_state,
            writes=(),
            blockers=tuple(blockers),
        )
        return FlatStartCleanupResult(
            success=False,
            go_no_go="no_go",
            packet=packet,
            blockers=packet.blockers,
            broker_writes_performed=False,
            real_broker_writes_performed=False,
            real_read_only_calls_performed=False,
        )

    pre_state = summarize_cleanup_broker_state(adapter=adapter, client=client)
    action_blockers = list(_broker_state_blockers(pre_state))
    if pre_state.clock_is_open is not True:
        action_blockers.append("market_clock_not_open_for_m44_cleanup")
    if blockers:
        action_blockers.append("cleanup_gates_failed")

    writes: list[CleanupWriteRecord] = []
    actions: list[SymbolCleanupAction] = []
    current_state = pre_state
    if not action_blockers:
        for symbol_state in pre_state.symbol_states:
            action, current_state, symbol_writes = _cleanup_one_symbol(
                request=request,
                adapter=adapter,
                client=client,
                state=symbol_state,
                fake_only=fake_only,
                now=timestamp,
                sleeper=sleeper,
                clock=clock,
            )
            actions.append(action)
            writes.extend(symbol_writes)
            if action.blockers:
                action_blockers.extend(action.blockers)
                break
    else:
        actions = [
            SymbolCleanupAction(
                symbol=state.symbol,
                pre_state=state,
                strategy="refused_before_cleanup",
                blockers=tuple(action_blockers),
            )
            for state in pre_state.symbol_states
        ]

    final_state = summarize_cleanup_broker_state(adapter=adapter, client=client)
    all_blockers = _unique(
        (
            *blockers,
            *tuple(action_blockers),
            *_final_baseline_blockers(final_state),
        )
    )
    packet = _cleanup_packet(
        request=request,
        timestamp=timestamp,
        pre_state=pre_state,
        actions=tuple(actions),
        final_state=final_state,
        writes=tuple(writes),
        blockers=all_blockers,
    )
    success = packet.m45_flat_start_ready and not packet.blockers
    return FlatStartCleanupResult(
        success=success,
        go_no_go="go" if success else "no_go",
        packet=packet,
        blockers=packet.blockers,
        broker_writes_performed=bool(packet.broker_writes),
        real_broker_writes_performed=any(not write.fake_only for write in packet.broker_writes),
        real_read_only_calls_performed=not fake_only,
    )


def summarize_cleanup_broker_state(
    *,
    adapter: AlpacaPaperAdapter,
    client: AlpacaPaperOrderLifecycleClient | FakeAlpacaClient,
) -> BrokerBaselineState:
    account = adapter.account_snapshot()
    clock_snapshot = _clock_snapshot(client)
    open_orders = adapter.open_orders()
    positions = adapter.positions()
    symbol_states = tuple(
        _symbol_cleanup_state(symbol=symbol, open_orders=open_orders, positions=positions)
        for symbol in EXPECTED_CLEANUP_SYMBOLS
    )
    unexpected_orders = tuple(
        sorted(
            {
                order.symbol
                for order in open_orders
                if order.symbol not in EXPECTED_CLEANUP_SYMBOLS
                or not _is_expected_long_stop_order(order)
            }
        )
    )
    unexpected_positions = tuple(
        sorted(
            {
                position.symbol
                for position in positions
                if position.symbol not in EXPECTED_CLEANUP_SYMBOLS
                or position.quantity < -1e-9
            }
        )
    )
    return BrokerBaselineState(
        account_reachable=True,
        clock_reachable=True,
        clock_is_open=clock_snapshot.is_open,
        paper_endpoint_proven=account.environment == "paper",
        open_orders_count=len(open_orders),
        positions_count=len(positions),
        expected_stop_order_count=sum(
            1 for order in open_orders if _is_expected_long_stop_order(order)
        ),
        unexpected_open_order_symbols=unexpected_orders,
        unexpected_position_symbols=unexpected_positions,
        symbol_states=symbol_states,
        baseline_paper_equity=account.equity,
    )


def write_flat_start_cleanup_artifact(
    result: FlatStartCleanupResult,
    output_path: str | Path = FLAT_START_CLEANUP_M44_EVIDENCE_PATH,
) -> Path:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "milestone": "44",
        "result": {
            "success": result.success,
            "go_no_go": result.go_no_go,
            "blockers": result.blockers,
            "broker_writes_performed": result.broker_writes_performed,
            "real_broker_writes_performed": result.real_broker_writes_performed,
            "real_read_only_calls_performed": result.real_read_only_calls_performed,
            "short_orders_performed": result.packet.short_orders_performed,
            "frozen_validation_started": result.packet.frozen_validation_started,
            "schedules_activated": result.packet.schedules_activated,
        },
        "flat_start_cleanup": result.packet.model_dump(mode="json"),
    }
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return path


def build_frozen_readiness_m44_packet(
    *,
    flat_cleanup_packet_path: str | Path = FLAT_START_CLEANUP_M44_EVIDENCE_PATH,
    app_config: AppConfig | None = None,
    now: datetime | None = None,
) -> M44ReadinessPacket:
    active_config = load_app_config() if app_config is None else app_config
    timestamp = now or datetime.now(UTC)
    cleanup_payload = _load_json_mapping(Path(flat_cleanup_packet_path))
    cleanup_packet = cleanup_payload.get("flat_start_cleanup")
    flat_achieved = False
    open_orders_count = 0
    positions_count = 0
    reconciliation_summary = "flat_cleanup_packet_missing_or_invalid"
    baseline_blockers: tuple[str, ...] = ("flat_cleanup_packet_missing_or_invalid",)
    if isinstance(cleanup_packet, Mapping):
        open_orders_count = int(cleanup_packet.get("final_open_orders_count") or 0)
        positions_count = int(cleanup_packet.get("final_positions_count") or 0)
        reconciliation_summary = str(cleanup_packet.get("final_reconciliation") or "unknown")
        baseline_blockers = tuple(str(item) for item in cleanup_packet.get("blockers", ()))
        flat_achieved = (
            bool(cleanup_packet.get("m45_flat_start_ready"))
            and open_orders_count == 0
            and positions_count == 0
            and reconciliation_summary == "flat_zero_positions_zero_open_orders"
            and not baseline_blockers
        )

    non_iex_status = "not_verified"
    blockers = list(baseline_blockers)
    if not flat_achieved:
        blockers.append("flat_broker_baseline_not_achieved")
    blockers.append("non_iex_primary_signal_data_not_verified")
    if not _spec_v05_exists():
        blockers.append("spec_v0_5_missing")
    if active_config.validation.validation_clock_started:
        blockers.append("validation_clock_already_started")
    if active_config.shorts.enabled:
        blockers.append("shorts_enabled_in_default_config")
    if active_config.validation.scale_in_policy.enabled_at_validation_start:
        blockers.append("scale_in_enabled_at_validation_start")

    packet = M44ReadinessPacket(
        packet_id=str(uuid5(NAMESPACE_URL, f"m44-readiness:{timestamp.isoformat()}")),
        timestamp=timestamp,
        git_commit_hash=_git_commit_or_unavailable(),
        config_hash=_hash_paths(_config_paths()),
        universe_hash=_hash_paths((Path("config/universe.yaml"),)),
        strategy_policy_hash=_hash_paths((Path("config/strategy.yaml"),)),
        risk_policy_hash=_hash_paths((Path("config/risk.yaml"),)),
        execution_policy_hash=_hash_paths((Path("config/execution.yaml"),)),
        reconciliation_policy_hash=_hash_paths(
            (Path("packages/reconciliation/models.py"), Path("packages/reconciliation/service.py"))
        ),
        ai_news_policy_hash=_hash_paths((Path("config/ai.yaml"), Path("docs/ai_intelligence.md"))),
        schedule_hash=_hash_text(json.dumps(active_config.validation.schedule.model_dump())),
        reporting_schema_version_hash=_hash_paths(
            (Path("docs/reporting.md"), Path("packages/reporting/models.py"))
        ),
        dashboard_validation_view_status="documented_not_frozen_started",
        data_provider_status="non_iex_primary_signal_data_not_verified",
        non_iex_data_gate_status=non_iex_status,
        broker_baseline_packet_reference=str(flat_cleanup_packet_path),
        flat_start_achieved=flat_achieved,
        open_orders_count=open_orders_count,
        positions_count=positions_count,
        reconciliation_summary=reconciliation_summary,
        shorts_implementation_present=True,
        shorts_enabled=active_config.shorts.enabled,
        short_universe=active_config.shorts.eligible_symbols,
        scale_in_implementation_present=active_config.validation.scale_in_policy.implementation_present,
        scale_in_enabled_at_validation_start=(
            active_config.validation.scale_in_policy.enabled_at_validation_start
        ),
        scale_in_stage_gate={
            "stage_gate_required": active_config.validation.scale_in_policy.stage_gate_required,
            "required_clean_scheduled_runs_before_enable": (
                active_config.validation.scale_in_policy.required_clean_scheduled_runs_before_enable
            ),
            "require_real_broker_additive_stop_proof": (
                active_config.validation.scale_in_policy.require_real_broker_additive_stop_proof
            ),
        },
        active_exits=tuple(
            name
            for name, enabled in active_config.validation.exits.model_dump().items()
            if bool(enabled)
        ),
        ai_negative_only_policy=active_config.validation.ai_policy.model_dump(),
        operator_intervention_policy=(
            "Operator approval required to start M45 frozen validation.",
            "Risk-reducing cleanup remains separate from new-risk execution.",
            "Manual broker review required for ambiguous broker state or missing stops.",
        ),
        incident_rules=(
            "No blind retry after ambiguous submit; reconcile by client_order_id first.",
            "Missing protective stop pauses new risk and requires incident handling.",
            "Same-day re-entry is forbidden after stop, exit, or cleanup.",
            "Unexpected short position is a critical incident while shorts are disabled.",
        ),
        m45_readiness=False,
        blockers=_unique(tuple(blockers)),
    )
    return packet


def write_frozen_readiness_m44_artifact(
    packet: M44ReadinessPacket,
    output_path: str | Path = FROZEN_READINESS_M44_EVIDENCE_PATH,
) -> Path:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "milestone": "44",
        "result": {
            "m45_readiness": packet.m45_readiness,
            "blockers": packet.blockers,
            "flat_start_achieved": packet.flat_start_achieved,
            "shorts_enabled": packet.shorts_enabled,
            "frozen_validation_started": packet.frozen_validation_started,
            "schedules_activated": packet.schedules_activated,
        },
        "frozen_readiness": packet.model_dump(mode="json"),
    }
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return path


def _cleanup_one_symbol(
    *,
    request: FlatStartCleanupRequest,
    adapter: AlpacaPaperAdapter,
    client: AlpacaPaperOrderLifecycleClient | FakeAlpacaClient,
    state: SymbolCleanupState,
    fake_only: bool,
    now: datetime,
    sleeper: Sleeper,
    clock: Clock,
) -> tuple[SymbolCleanupAction, BrokerBaselineState, tuple[CleanupWriteRecord, ...]]:
    writes: list[CleanupWriteRecord] = []
    blockers: list[str] = []
    if state.position_status == "short_or_ambiguous":
        return (
            SymbolCleanupAction(
                symbol=state.symbol,
                pre_state=state,
                strategy="manual_review_for_ambiguous_state",
                blockers=("symbol_state_ambiguous_or_short",),
            ),
            summarize_cleanup_broker_state(adapter=adapter, client=client),
            (),
        )
    if state.position_status == "flat":
        strategy = "flat_no_sell_needed"
        if state.protective_stop_client_order_id is not None:
            write = _cancel_stop(
                adapter=adapter,
                stop_client_order_id=state.protective_stop_client_order_id,
                symbol=state.symbol,
                operation="cancel_stale_orphan_stop",
                fake_only=fake_only,
            )
            writes.append(write)
            strategy = "flat_cancel_stale_orphan_stop_only"
        final_state = summarize_cleanup_broker_state(adapter=adapter, client=client)
        return (
            SymbolCleanupAction(
                symbol=state.symbol,
                pre_state=state,
                strategy=strategy,
                stop_cancellation_result=_last_status(writes),
                final_state=_state_for(final_state, state.symbol),
            ),
            final_state,
            tuple(writes),
        )

    if not state.protective_stop_verified or state.protective_stop_client_order_id is None:
        blockers.append("verified_protective_stop_required_before_cleanup")
        final_state = summarize_cleanup_broker_state(adapter=adapter, client=client)
        return (
            SymbolCleanupAction(
                symbol=state.symbol,
                pre_state=state,
                strategy="manual_review_missing_stop",
                blockers=tuple(blockers),
                final_state=_state_for(final_state, state.symbol),
            ),
            final_state,
            tuple(writes),
        )

    cancel_write = _cancel_stop(
        adapter=adapter,
        stop_client_order_id=state.protective_stop_client_order_id,
        symbol=state.symbol,
        operation="cancel_session_protective_stop",
        fake_only=fake_only,
    )
    writes.append(cancel_write)
    after_cancel = summarize_cleanup_broker_state(adapter=adapter, client=client)
    after_cancel_state = _state_for(after_cancel, state.symbol)
    if after_cancel_state.protective_stop_verified:
        blockers.append("stop_cancellation_not_verified")
        return (
            SymbolCleanupAction(
                symbol=state.symbol,
                pre_state=state,
                strategy="cancel_verified_stop_then_sell_current_long_quantity",
                stop_cancellation_result=cancel_write.status,
                blockers=tuple(blockers),
                final_state=after_cancel_state,
            ),
            after_cancel,
            tuple(writes),
        )

    sell_order, sell_write = _submit_cleanup_sell(
        client=client,
        adapter=adapter,
        symbol=state.symbol,
        quantity=state.position_quantity,
        fake_only=fake_only,
        now=now,
        timeout_seconds=request.cleanup_timeout_seconds,
        sleeper=sleeper,
        clock=clock,
    )
    writes.append(sell_write)
    if sell_order is None or sell_write.status not in {"filled", "succeeded:filled"}:
        blockers.append("cleanup_sell_not_filled_or_not_verified")
    after_sell = summarize_cleanup_broker_state(adapter=adapter, client=client)
    after_sell_state = _state_for(after_sell, state.symbol)
    emergency_status = None
    if (
        after_sell_state.position_status == "open_long"
        and not after_sell_state.protective_stop_verified
    ):
        reprotect = _submit_emergency_reprotect(
            adapter=adapter,
            symbol=state.symbol,
            quantity=after_sell_state.position_quantity,
            stop_price=state.protective_stop_quantity and _stop_price_from_state(state, adapter),
            fake_only=fake_only,
            now=now,
        )
        if reprotect is not None:
            writes.append(reprotect)
            emergency_status = reprotect.status
        blockers.append("emergency_reprotection_required_after_cleanup_failure")
        after_sell = summarize_cleanup_broker_state(adapter=adapter, client=client)
        after_sell_state = _state_for(after_sell, state.symbol)

    return (
        SymbolCleanupAction(
            symbol=state.symbol,
            pre_state=state,
            strategy="cancel_verified_stop_then_sell_current_long_quantity",
            stop_cancellation_result=cancel_write.status,
            sell_result=sell_write.status,
            emergency_reprotection_result=emergency_status,
            final_state=after_sell_state,
            blockers=tuple(blockers),
        ),
        after_sell,
        tuple(writes),
    )


def _client_and_adapter(
    *,
    request: FlatStartCleanupRequest,
    app_config: AppConfig,
    environ: Mapping[str, str],
    client_factory: M44ClientFactory,
    gate_blockers: tuple[str, ...],
    timestamp: datetime,
) -> tuple[
    AlpacaPaperOrderLifecycleClient | FakeAlpacaClient | None,
    AlpacaPaperAdapter | None,
    tuple[str, ...],
    bool,
]:
    if gate_blockers:
        return None, None, (), True
    if request.mode == "fake":
        client = _fake_m44_client(timestamp)
        adapter = AlpacaPaperAdapter(
            system_config=app_config.system,
            execution_config=app_config.execution,
            client=client,
            credentials=None,
            run_mode="test",
        )
        return client, adapter, (), True
    try:
        credentials = _credentials_from_env(environ)
        real_client = client_factory(credentials, request.cleanup_timeout_seconds)
        adapter = AlpacaPaperAdapter(
            system_config=app_config.system,
            execution_config=app_config.execution,
            client=real_client,
            credentials=credentials,
            run_mode="runtime",
        )
    except Exception:
        return None, None, ("alpaca_m44_cleanup_credentials_or_client_unavailable",), False
    return real_client, adapter, (), False


def _credentials_from_env(environ: Mapping[str, str]) -> AlpacaPaperCredentials:
    return AlpacaPaperCredentials(
        api_key=environ.get("ALPACA_API_KEY", "").strip(),
        secret_key=environ.get("ALPACA_SECRET_KEY", "").strip(),
        base_url=environ.get("ALPACA_BASE_URL", "").strip(),
    )


def _cleanup_gate_blockers(
    request: FlatStartCleanupRequest,
    app_config: AppConfig,
    environ: Mapping[str, str],
) -> tuple[str, ...]:
    blockers: list[str] = []
    if request.operator_approval != M44_FLAT_START_CLEANUP_APPROVAL:
        blockers.append("m44_cleanup_approval_marker_required")
    confirmations = (
        ("confirm_paper_endpoint", "confirm_paper_endpoint_required"),
        ("confirm_risk_reducing_only", "confirm_risk_reducing_only_required"),
        ("confirm_cancel_session_stop_before_sell", "confirm_cancel_stop_before_sell_required"),
        (
            "confirm_emergency_reprotect_if_sell_fails",
            "confirm_emergency_reprotect_required",
        ),
        ("confirm_no_new_entry", "confirm_no_new_entry_required"),
        ("confirm_no_buy_orders", "confirm_no_buy_orders_required"),
        ("confirm_no_short_orders", "confirm_no_short_orders_required"),
        ("confirm_no_live_trading", "confirm_no_live_trading_required"),
        ("confirm_no_autonomous_live", "confirm_no_autonomous_live_required"),
        ("confirm_no_schedules", "confirm_no_schedules_required"),
        ("confirm_no_leverage", "confirm_no_leverage_required"),
    )
    for field_name, reason in confirmations:
        if not bool(getattr(request, field_name)):
            blockers.append(reason)
    if request.mode == "real-paper":
        if environ.get("ALPACA_BASE_URL", "").strip() != ALPACA_PAPER_BASE_URL:
            blockers.append("alpaca_base_url_must_be_exact_paper_endpoint")
        if not environ.get("ALPACA_API_KEY", "").strip():
            blockers.append("alpaca_api_key_required")
        if not environ.get("ALPACA_SECRET_KEY", "").strip():
            blockers.append("alpaca_secret_key_required")
    if app_config.system.live_trading_enabled or app_config.execution.allow_live_orders:
        blockers.append("live_trading_enabled")
    if (
        app_config.system.autonomous_execution_enabled
        or app_config.execution.autonomous_execution_enabled
    ):
        blockers.append("autonomous_live_execution_enabled")
    if app_config.risk_level_4_micro_live.allow_margin:
        blockers.append("leverage_enabled")
    if app_config.shorts.enabled:
        blockers.append("shorts_enabled_in_default_config")
    if app_config.validation.validation_clock_started:
        blockers.append("validation_clock_already_started")
    return _unique(tuple(blockers))


def _broker_state_blockers(state: BrokerBaselineState) -> tuple[str, ...]:
    blockers: list[str] = []
    if not state.account_reachable or not state.clock_reachable or not state.paper_endpoint_proven:
        blockers.append("broker_state_not_reached_or_not_paper")
    if state.unexpected_open_order_symbols:
        blockers.append("unexpected_open_orders_present")
    if state.unexpected_position_symbols:
        blockers.append("unexpected_positions_present")
    for symbol_state in state.symbol_states:
        if symbol_state.position_status == "short_or_ambiguous":
            blockers.append(f"{symbol_state.symbol.lower()}_position_state_ambiguous_or_short")
        if (
            symbol_state.position_status == "open_long"
            and not symbol_state.protective_stop_verified
        ):
            blockers.append(f"{symbol_state.symbol.lower()}_protective_stop_unverified")
    return _unique(tuple(blockers))


def _final_baseline_blockers(state: BrokerBaselineState) -> tuple[str, ...]:
    blockers: list[str] = []
    if state.open_orders_count != 0:
        blockers.append("final_open_orders_not_zero")
    if state.positions_count != 0:
        blockers.append("final_positions_not_zero")
    if state.unexpected_open_order_symbols:
        blockers.append("final_unexpected_open_orders_present")
    if state.unexpected_position_symbols:
        blockers.append("final_unexpected_positions_present")
    return _unique(tuple(blockers))


def _symbol_cleanup_state(
    *,
    symbol: str,
    open_orders: tuple[BrokerOrder, ...],
    positions: tuple[BrokerPosition, ...],
) -> SymbolCleanupState:
    position = next((item for item in positions if item.symbol == symbol), None)
    quantity = 0.0 if position is None else position.quantity
    if quantity > 1e-9:
        position_status: Literal["open_long", "flat", "short_or_ambiguous"] = "open_long"
    elif abs(quantity) <= 1e-9:
        position_status = "flat"
    else:
        position_status = "short_or_ambiguous"
    matching_stops = tuple(
        order
        for order in open_orders
        if order.symbol == symbol and _is_expected_long_stop_order(order)
    )
    verified = len(matching_stops) == 1 and matching_stops[0].quantity >= max(quantity, 0.0)
    stop = matching_stops[0] if len(matching_stops) == 1 else None
    return SymbolCleanupState(
        symbol=symbol,
        position_status=position_status,
        position_quantity=quantity,
        protective_stop_verified=verified,
        protective_stop_quantity=None if stop is None else stop.quantity,
        protective_stop_client_order_id_present=stop is not None,
        protective_stop_broker_order_id_present=stop is not None,
        protective_stop_client_order_id=None if stop is None else stop.client_order_id,
        protective_stop_broker_order_id=None if stop is None else stop.broker_order_id,
        protective_stop_status=None if stop is None else stop.status,
    )


def _is_expected_long_stop_order(order: BrokerOrder) -> bool:
    return (
        order.is_open
        and order.side == "sell"
        and order.order_type in {"stop", "stop_limit"}
        and order.purpose == "protective_stop"
    )


def _cancel_stop(
    *,
    adapter: AlpacaPaperAdapter,
    stop_client_order_id: str,
    symbol: str,
    operation: Literal["cancel_session_protective_stop", "cancel_stale_orphan_stop"],
    fake_only: bool,
) -> CleanupWriteRecord:
    result = adapter.cancel_order(stop_client_order_id)
    if result.status == "succeeded" and result.order is not None:
        order = result.order
        return CleanupWriteRecord(
            operation=operation,
            symbol=symbol,
            attempted=True,
            side=order.side,
            quantity=order.quantity,
            order_type=order.order_type,
            status=order.status,
            broker_order_id_present=bool(order.broker_order_id),
            client_order_id_present=bool(order.client_order_id),
            fake_only=fake_only,
        )
    status = "failed" if result.error is None else f"failed:{result.error.code}"
    return CleanupWriteRecord(
        operation=operation,
        symbol=symbol,
        attempted=True,
        side="sell",
        quantity=None,
        order_type="stop",
        status=status,
        broker_order_id_present=False,
        client_order_id_present=bool(stop_client_order_id),
        fake_only=fake_only,
    )


def _submit_cleanup_sell(
    *,
    client: AlpacaPaperOrderLifecycleClient | FakeAlpacaClient,
    adapter: AlpacaPaperAdapter,
    symbol: str,
    quantity: float,
    fake_only: bool,
    now: datetime,
    timeout_seconds: float,
    sleeper: Sleeper,
    clock: Clock,
) -> tuple[BrokerOrder | None, CleanupWriteRecord]:
    client_order_id = _cleanup_client_order_id(symbol, now)
    request = {
        "symbol": symbol,
        "side": "sell",
        "type": "market",
        "time_in_force": "day",
        "qty": _format_quantity(quantity),
        "client_order_id": client_order_id,
        "extended_hours": False,
    }
    try:
        initial_order = map_alpaca_order(client.submit_order(request))
        order = _poll_order_by_client_order_id(
            adapter,
            client_order_id=client_order_id,
            initial_order=initial_order,
            timeout_seconds=timeout_seconds,
            sleeper=sleeper,
            clock=clock,
        )
        status = order.status
        if order.status == "filled" or order.filled_quantity >= quantity:
            status = "filled"
        return order, CleanupWriteRecord(
            operation="submit_cleanup_sell",
            symbol=symbol,
            attempted=True,
            side=order.side,
            quantity=order.quantity,
            order_type=order.order_type,
            status=status,
            broker_order_id_present=bool(order.broker_order_id),
            client_order_id_present=bool(order.client_order_id),
            fake_only=fake_only,
        )
    except AlpacaClientError as exc:
        return None, CleanupWriteRecord(
            operation="submit_cleanup_sell",
            symbol=symbol,
            attempted=True,
            side="sell",
            quantity=quantity,
            order_type="market",
            status=f"failed:{exc.code}",
            broker_order_id_present=False,
            client_order_id_present=True,
            fake_only=fake_only,
        )


def _submit_emergency_reprotect(
    *,
    adapter: AlpacaPaperAdapter,
    symbol: str,
    quantity: float,
    stop_price: float | None,
    fake_only: bool,
    now: datetime,
) -> CleanupWriteRecord | None:
    if quantity <= 1e-9 or stop_price is None:
        return None
    client_order_root = f"m44-emergency-stop-{symbol}-{now.strftime('%Y%m%d%H%M%S')}"
    intent = ExecutionIntent(
        decision_id=uuid5(NAMESPACE_URL, f"m44-emergency-reprotect:{client_order_root}"),
        symbol=symbol,
        side="buy",
        asset_class="etf" if symbol == "XLK" else "equity",
        quantity=int(round(quantity)),
        entry_order_type="limit",
        limit_price=max(stop_price * 2.0, stop_price + 1.0),
        stop_loss_price=stop_price,
        time_in_force="day",
        strategy_version="m44-flat-start-cleanup",
        risk_config_version="m44-flat-start-cleanup",
        autonomy_level=0,
        requires_protective_stop=True,
        max_acceptable_slippage_bps=0,
        expires_at=now + timedelta(minutes=15),
        client_order_id_root=client_order_root,
        status="risk_approved",
    )
    result = adapter.submit_protective_stop(intent, filled_quantity=quantity)
    if result.status == "succeeded" and result.order is not None:
        verification = adapter.verify_protective_stop(
            symbol=symbol,
            required_quantity=quantity,
            client_order_id=result.order.client_order_id,
        )
        return CleanupWriteRecord(
            operation="submit_emergency_protective_stop",
            symbol=symbol,
            attempted=True,
            side=result.order.side,
            quantity=result.order.quantity,
            order_type=result.order.order_type,
            status=result.order.status if verification.protected else "failed:not_verified",
            broker_order_id_present=bool(result.order.broker_order_id),
            client_order_id_present=bool(result.order.client_order_id),
            fake_only=fake_only,
        )
    status = "failed" if result.error is None else f"failed:{result.error.code}"
    return CleanupWriteRecord(
        operation="submit_emergency_protective_stop",
        symbol=symbol,
        attempted=True,
        side="sell",
        quantity=quantity,
        order_type="stop",
        status=status,
        broker_order_id_present=False,
        client_order_id_present=True,
        fake_only=fake_only,
    )


def _poll_order_by_client_order_id(
    adapter: AlpacaPaperAdapter,
    *,
    client_order_id: str,
    initial_order: BrokerOrder,
    timeout_seconds: float,
    sleeper: Sleeper,
    clock: Clock,
) -> BrokerOrder:
    latest = initial_order
    deadline = clock() + timeout_seconds
    while clock() <= deadline:
        lookup = adapter.order_by_client_order_id(client_order_id)
        if lookup is not None:
            latest = lookup
            if latest.status in {"filled", "cancelled", "expired", "rejected"}:
                return latest
        sleeper(0.25)
    lookup = adapter.order_by_client_order_id(client_order_id)
    return latest if lookup is None else lookup


def _cleanup_packet(
    *,
    request: FlatStartCleanupRequest,
    timestamp: datetime,
    pre_state: BrokerBaselineState,
    actions: tuple[SymbolCleanupAction, ...],
    final_state: BrokerBaselineState,
    writes: tuple[CleanupWriteRecord, ...],
    blockers: tuple[str, ...],
) -> FlatStartCleanupPacket:
    final_reconciliation = (
        "flat_zero_positions_zero_open_orders"
        if final_state.open_orders_count == 0 and final_state.positions_count == 0
        else "not_flat_or_open_orders_remain"
    )
    flat_ready = final_reconciliation == "flat_zero_positions_zero_open_orders" and not blockers
    return FlatStartCleanupPacket(
        packet_id=str(uuid5(NAMESPACE_URL, f"m44-flat-cleanup:{timestamp.isoformat()}")),
        timestamp=timestamp,
        operator_approval_marker=request.operator_approval,
        pre_cleanup_broker_state=pre_state,
        per_symbol_cleanup_actions=actions,
        stop_cancellation_results=tuple(
            action.stop_cancellation_result
            for action in actions
            if action.stop_cancellation_result is not None
        ),
        sell_results=tuple(
            action.sell_result for action in actions if action.sell_result is not None
        ),
        emergency_reprotection_results=tuple(
            action.emergency_reprotection_result
            for action in actions
            if action.emergency_reprotection_result is not None
        ),
        final_broker_state=final_state,
        final_open_orders_count=final_state.open_orders_count,
        final_positions_count=final_state.positions_count,
        final_reconciliation=final_reconciliation,
        baseline_paper_equity=final_state.baseline_paper_equity,
        broker_writes_performed=bool(writes),
        broker_writes=writes,
        m45_flat_start_ready=flat_ready,
        blockers=blockers,
    )


def _empty_baseline_state() -> BrokerBaselineState:
    return BrokerBaselineState(
        account_reachable=False,
        clock_reachable=False,
        clock_is_open=None,
        paper_endpoint_proven=False,
        open_orders_count=0,
        positions_count=0,
        expected_stop_order_count=0,
        unexpected_open_order_symbols=(),
        unexpected_position_symbols=(),
        symbol_states=(),
        baseline_paper_equity=None,
    )


def _fake_m44_client(timestamp: datetime) -> FakeAlpacaClient:
    submitted_at = timestamp.isoformat().replace("+00:00", "Z")
    orders = [
        _fake_stop_order(symbol=symbol, submitted_at=submitted_at)
        for symbol in EXPECTED_CLEANUP_SYMBOLS
    ]
    positions = [
        {
            "symbol": symbol,
            "asset_class": "etf" if symbol == "XLK" else "equity",
            "qty": "1",
            "avg_entry_price": "100",
            "market_value": "100",
            "opened_at": submitted_at,
        }
        for symbol in EXPECTED_CLEANUP_SYMBOLS
    ]
    client = FakeAlpacaClient(
        orders=orders,
        positions=positions,
        submit_outcomes=(("filled", 1.0), ("filled", 1.0), ("filled", 1.0)),
        mutate_positions_on_submit=True,
    )
    return client


def _fake_stop_order(*, symbol: str, submitted_at: str) -> dict[str, str]:
    return {
        "id": f"m44-existing-stop-{symbol}",
        "client_order_id": f"first-session-{symbol}-existing-stop",
        "symbol": symbol,
        "side": "sell",
        "asset_class": "etf" if symbol == "XLK" else "equity",
        "qty": "1",
        "filled_qty": "0",
        "type": "stop",
        "time_in_force": "gtc",
        "status": "new",
        "stop_price": "95",
        "submitted_at": submitted_at,
        "updated_at": submitted_at,
    }


def _clock_snapshot(
    client: AlpacaPaperOrderLifecycleClient | FakeAlpacaClient,
) -> BrokerClockSnapshot:
    return map_alpaca_clock(client.get_clock())


def _state_for(state: BrokerBaselineState, symbol: str) -> SymbolCleanupState:
    return next(item for item in state.symbol_states if item.symbol == symbol)


def _last_status(writes: Sequence[CleanupWriteRecord]) -> str | None:
    if not writes:
        return None
    return writes[-1].status


def _stop_price_from_state(state: SymbolCleanupState, adapter: AlpacaPaperAdapter) -> float | None:
    if state.protective_stop_client_order_id is None:
        return None
    order = adapter.order_by_client_order_id(state.protective_stop_client_order_id)
    return None if order is None else order.stop_price


def _cleanup_client_order_id(symbol: str, now: datetime) -> str:
    digest = uuid5(NAMESPACE_URL, f"m44-cleanup:{symbol}:{now.isoformat()}").hex[:8]
    return f"m44-cleanup-{symbol}-{now.strftime('%Y%m%d%H%M%S')}-{digest}"


def _format_quantity(quantity: float) -> str:
    if abs(quantity - round(quantity)) <= 1e-9:
        return str(int(round(quantity)))
    return f"{quantity:.8f}".rstrip("0").rstrip(".")


def _load_json_mapping(path: Path) -> Mapping[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, Mapping) else {}


def _hash_paths(paths: Sequence[Path]) -> str:
    digest = hashlib.sha256()
    for path in paths:
        digest.update(str(path).encode("utf-8"))
        try:
            digest.update(path.read_bytes())
        except OSError:
            digest.update(b"missing")
    return digest.hexdigest()


def _hash_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _config_paths() -> tuple[Path, ...]:
    return tuple(sorted(Path("config").glob("*.yaml")))


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


def _spec_v05_exists() -> bool:
    return Path(LATEST_V05_SPEC_PATH).is_file()


def _unique(values: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(item for item in values if item))
