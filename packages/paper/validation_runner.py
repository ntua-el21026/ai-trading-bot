"""Milestone 47 frozen paper validation runner activation and cycle checks.

The local runner is intentionally conservative. It can wake on frozen schedule times, verify
read-only gates, and produce no-trade cycle evidence. It does not force signals or submit broker
orders.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, datetime, timedelta
from datetime import time as dt_time
from pathlib import Path
from typing import Any, Literal, Protocol
from uuid import NAMESPACE_URL, uuid5
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, Field

from packages.broker.alpaca import (
    AlpacaClientError,
    AlpacaPaperCredentials,
    map_alpaca_account,
    map_alpaca_clock,
    map_alpaca_order,
    map_alpaca_position,
)
from packages.core.config import AppConfig, load_app_config
from packages.data.models import AdjustedDailyBar
from packages.data.primary_signal_gate import (
    PrimarySignalDataGateRequest,
    TiingoSignalDataClient,
    run_primary_signal_data_gate,
)
from packages.paper.preflight import load_preflight_environment
from packages.paper.validation_start import (
    FROZEN_PAPER_VALIDATION_START_M45_EVIDENCE_PATH,
    LATEST_V06_SPEC_PATH,
    M45ReadOnlyClient,
    M45ReadOnlyClientFactory,
    _frozen_hashes,
    _latest_spec,
    build_m45_read_only_client,
)

M47_APPROVAL = "MILESTONE_47_ACTIVATE_FROZEN_VALIDATION_RUNNER"
M47_EVIDENCE_PATH = "docs/evidence/frozen_validation_runner_m47.json"
M47_DOC_PATH = "docs/frozen_validation_runner_m47.md"
M46_EVIDENCE_PATH = "docs/evidence/frozen_validation_day1_audit_m46.json"
RUNNER_SCRIPT = "scripts/run_frozen_paper_validation_runner.py"
CHECK_SCRIPT = "scripts/check_frozen_validation_runner_m47.py"
RUNNER_ID = "frozen-validation-runner-v0.6-local"
RUNTIME_DIR = ".runtime/frozen_validation_runner"
PID_FILE = f"{RUNTIME_DIR}/runner.pid"
HEARTBEAT_FILE = f"{RUNTIME_DIR}/heartbeat.json"
LOG_FILE = f"{RUNTIME_DIR}/runner.log"
CYCLE_EVIDENCE_DIR = "docs/evidence/frozen_validation_cycles"

RunnerPathSelected = Literal[
    "temporal_cloud_schedule",
    "local_runner",
    "os_scheduler_documented",
    "manual_trigger",
    "none",
]
RunnerStatus = Literal["active", "inactive", "configured_not_started", "unavailable", "unknown"]
CycleResult = Literal["no_trade", "trade_executed", "refused", "skipped_not_due", "error"]
M47GoNoGo = Literal["GO", "NO_GO"]
BrokerWritesReason = Literal["none", "natural_due_cycle", "unexpected"]


class M47BrokerReadOnlyClient(Protocol):
    def get_account(self) -> Mapping[str, Any]:
        """Return a paper account payload."""

    def get_clock(self) -> Mapping[str, Any]:
        """Return a market clock payload."""

    def list_open_orders(self) -> Sequence[Mapping[str, Any]]:
        """Return open order payloads."""

    def list_positions(self) -> Sequence[Mapping[str, Any]]:
        """Return position payloads."""


class M47Model(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class FrozenValidationRunnerRequest(M47Model):
    mode: Literal["fake", "real-paper"] = "real-paper"
    operator_approval: str | None = None
    confirm_paper_only: bool = False
    confirm_validation_already_started: bool = False
    confirm_no_live_trading: bool = False
    confirm_no_autonomous_live: bool = False
    confirm_no_leverage: bool = False
    confirm_live_shorting_disabled: bool = False
    confirm_ai_no_broker_authority: bool = False
    confirm_no_level4: bool = False
    confirm_no_forced_trades: bool = False
    activate_runner: bool = True
    run_due_cycle_check: bool = True
    poll_seconds: int = Field(default=300, ge=60, le=3600)
    timeout_seconds: float = Field(default=15.0, ge=1.0, le=60.0)
    m45_evidence_path: str = FROZEN_PAPER_VALIDATION_START_M45_EVIDENCE_PATH
    m46_evidence_path: str = M46_EVIDENCE_PATH


class FrozenValidationCycleRequest(M47Model):
    mode: Literal["fake", "real-paper"] = "real-paper"
    confirm_paper_only: bool = False
    confirm_no_live_trading: bool = False
    confirm_no_autonomous_live: bool = False
    confirm_no_leverage: bool = False
    confirm_live_shorting_disabled: bool = False
    confirm_ai_no_broker_authority: bool = False
    confirm_no_level4: bool = False
    confirm_no_forced_trades: bool = False
    timeout_seconds: float = Field(default=15.0, ge=1.0, le=60.0)
    m45_evidence_path: str = FROZEN_PAPER_VALIDATION_START_M45_EVIDENCE_PATH


class BrokerStateSummary(M47Model):
    open_orders_count: int = Field(ge=0)
    positions_count: int = Field(ge=0)
    reconciliation_summary: str


class MarketDataStatus(M47Model):
    provider: str
    feed: str
    latest_check_result: str
    sample_symbols: tuple[str, ...]


class ReportingStatus(M47Model):
    cycle_packet_generated: bool
    daily_report_generated: bool
    dashboard_snapshot_generated: bool


class CycleResultSummary(M47Model):
    cycle_result: CycleResult
    cycle_label: str | None = None
    cycle_due_at_et: str | None = None
    evidence_path: str | None = None
    candidate_generation_status: str
    broker_writes_performed: bool = False
    broker_writes_reason: BrokerWritesReason = "none"
    blockers: tuple[str, ...] = ()


class RunnerActivationSummary(M47Model):
    runner_path_selected: RunnerPathSelected
    runner_status: RunnerStatus
    schedule_or_runner_id: str | None
    runner_command: str | None
    pid: int | None = None
    old_test_schedules_active: bool = False
    temporal_cloud_schedule_created: bool = False
    temporal_cloud_schedule_id: str | None = None


class FrozenValidationRunnerM47Packet(M47Model):
    packet_id: str
    timestamp: datetime
    latest_spec_path: str
    latest_spec_version: str
    m45_evidence_reference: str
    m46_evidence_reference: str
    validation_status: str
    validation_start_timestamp_utc: datetime | None
    validation_target_end_timestamp_utc: datetime | None
    current_time_utc: datetime
    validation_day_index: int = Field(ge=0)
    validation_window_active: bool
    pre_activation_broker_state: BrokerStateSummary
    market_data_status: MarketDataStatus
    runner_path_selected: RunnerPathSelected
    runner_status: RunnerStatus
    schedule_or_runner_id: str | None
    runner_command: str | None
    old_test_schedules_active: bool
    temporal_cloud_schedule_created: bool
    temporal_cloud_schedule_id: str | None
    due_cycle_detected: bool
    cycle_ran_in_m47: bool
    cycle_result: CycleResult | None
    broker_writes_performed_in_m47: bool
    broker_writes_reason: BrokerWritesReason
    post_activation_broker_state: BrokerStateSummary
    reporting_status: ReportingStatus
    live_trading_enabled: bool = False
    autonomous_live_execution_enabled: bool = False
    leverage_enabled: bool = False
    live_shorting_enabled: bool = False
    ai_broker_authority: bool = False
    level4_ready: bool = False
    frozen_policy_drift_detected: bool
    m47_result: M47GoNoGo
    blockers: tuple[str, ...]


class FrozenValidationRunnerM47Result(M47Model):
    success: bool
    packet: FrozenValidationRunnerM47Packet
    blockers: tuple[str, ...]
    broker_writes_performed: bool
    runner_activated: bool
    cycle_result: CycleResult | None


class FrozenValidationCyclePacket(M47Model):
    packet_id: str
    timestamp: datetime
    m45_evidence_reference: str
    validation_status: str
    validation_window_active: bool
    due_cycle_detected: bool
    cycle_label: str | None
    cycle_result: CycleResult
    broker_state: BrokerStateSummary
    market_data_status: MarketDataStatus
    frozen_policy_drift_detected: bool
    candidate_generation_status: str
    broker_writes_performed: bool = False
    broker_writes_reason: BrokerWritesReason = "none"
    forced_trades: bool = False
    blockers: tuple[str, ...]


class FrozenValidationCycleResult(M47Model):
    packet: FrozenValidationCyclePacket
    evidence_path: Path | None
    broker_writes_performed: bool


def run_frozen_validation_runner_m47(
    request: FrozenValidationRunnerRequest,
    *,
    environ: Mapping[str, str] | None = None,
    app_config: AppConfig | None = None,
    client_factory: M45ReadOnlyClientFactory = build_m45_read_only_client,
    tiingo_client: TiingoSignalDataClient | None = None,
    current_time: Callable[[], datetime] | None = None,
    repo_root: Path | None = None,
    process_launcher: Callable[[Path, Mapping[str, str], int], int | None] | None = None,
) -> FrozenValidationRunnerM47Result:
    root = repo_root or Path.cwd()
    active_config = load_app_config(root / "config") if app_config is None else app_config
    active_environ = (
        load_preflight_environment(repo_root=root, base_environ=environ)
        if environ is not None
        else load_preflight_environment(repo_root=root)
    )
    now = _now(current_time)
    latest_spec_path, latest_spec_version = _latest_spec(root)
    m45_packet = _load_json_mapping(root / request.m45_evidence_path)
    m46_packet = _load_json_mapping(root / request.m46_evidence_path)
    blockers: list[str] = []
    blockers.extend(_m47_request_blockers(request))
    if latest_spec_path != LATEST_V06_SPEC_PATH or latest_spec_version != "v0.6":
        blockers.append("latest_spec_not_v0_6")
    if m45_packet is None:
        blockers.append("m45_evidence_missing")
    if m46_packet is None:
        blockers.append("m46_evidence_missing")
    if m46_packet is not None and "local_registry_has_no_active_runner" not in tuple(
        str(item) for item in m46_packet.get("blockers", ())
    ):
        blockers.append("m46_runner_blocker_not_confirmed")

    validation_status = _string_field(m45_packet, "validation_status", "missing")
    start = _datetime_field(m45_packet, "validation_start_timestamp_utc")
    end = _datetime_field(m45_packet, "validation_end_target_timestamp_utc")
    if m45_packet is not None and validation_status != "active":
        blockers.append("m45_validation_not_active")
    window_active = _validation_window_active(now=now, start=start, end=end)
    if not window_active:
        blockers.append("validation_window_not_active")
    day_index = _validation_day_index(now=now, start=start)
    schedule_mapping = _mapping_field(m45_packet, "schedule")
    schedule_registry_status = _string_field(
        schedule_mapping,
        "schedule_final_state",
        "missing",
    )
    if (
        m45_packet is not None
        and schedule_registry_status != "active_local_paper_validation_registry"
    ):
        blockers.append("schedule_registry_not_active")
    old_test_schedules_active = bool(schedule_mapping.get("old_test_schedules_active", False))
    temporal_cloud_schedule_created = bool(
        schedule_mapping.get("temporal_cloud_schedule_created", False)
    )
    if temporal_cloud_schedule_created:
        blockers.append("unexpected_temporal_cloud_schedule_detected")

    safety_flags, safety_blockers = _safety_flags(active_config)
    blockers.extend(safety_blockers)
    drift_detected, drift_blockers = _frozen_policy_drift(root, m45_packet)
    blockers.extend(drift_blockers)
    old_test_schedules_active = old_test_schedules_active or _old_or_duplicate_schedule_active(root)
    if old_test_schedules_active:
        blockers.append("old_test_schedules_active")

    pre_state, broker_blockers = _read_broker_state(
        mode=request.mode,
        environ=active_environ,
        client_factory=client_factory,
        timeout_seconds=request.timeout_seconds,
        skip_read="m45_evidence_missing" in blockers,
    )
    blockers.extend(broker_blockers)
    market_status, market_blockers = _verify_tiingo_status(
        mode=request.mode,
        environ=active_environ,
        app_config=active_config,
        tiingo_client=tiingo_client,
        now=now,
    )
    blockers.extend(market_blockers)

    due_cycle = _due_cycle(now, active_config)
    activation = _activate_or_observe_runner(
        request=request,
        repo_root=root,
        environ=active_environ,
        existing_blockers=tuple(blockers),
        process_launcher=process_launcher,
    )
    blockers.extend(_runner_blockers(activation))

    cycle_summary = CycleResultSummary(
        cycle_result="skipped_not_due",
        candidate_generation_status="not_due",
    )
    if request.run_due_cycle_check and due_cycle is not None and not blockers:
        cycle_request = FrozenValidationCycleRequest(
            mode=request.mode,
            confirm_paper_only=request.confirm_paper_only,
            confirm_no_live_trading=request.confirm_no_live_trading,
            confirm_no_autonomous_live=request.confirm_no_autonomous_live,
            confirm_no_leverage=request.confirm_no_leverage,
            confirm_live_shorting_disabled=request.confirm_live_shorting_disabled,
            confirm_ai_no_broker_authority=request.confirm_ai_no_broker_authority,
            confirm_no_level4=request.confirm_no_level4,
            confirm_no_forced_trades=request.confirm_no_forced_trades,
            timeout_seconds=request.timeout_seconds,
            m45_evidence_path=request.m45_evidence_path,
        )
        cycle = run_frozen_validation_cycle_once(
            cycle_request,
            environ=active_environ,
            app_config=active_config,
            client_factory=client_factory,
            tiingo_client=tiingo_client,
            current_time=lambda: now,
            repo_root=root,
            write_evidence=True,
            due_cycle_override=due_cycle,
        )
        cycle_summary = CycleResultSummary(
            cycle_result=cycle.packet.cycle_result,
            cycle_label=cycle.packet.cycle_label,
            cycle_due_at_et=None if due_cycle is None else due_cycle["due_at_et"],
            evidence_path=None if cycle.evidence_path is None else str(cycle.evidence_path),
            candidate_generation_status=cycle.packet.candidate_generation_status,
            broker_writes_performed=cycle.broker_writes_performed,
            broker_writes_reason=cycle.packet.broker_writes_reason,
            blockers=cycle.packet.blockers,
        )
        blockers.extend(cycle.packet.blockers)

    post_state, post_broker_blockers = _read_broker_state(
        mode=request.mode,
        environ=active_environ,
        client_factory=client_factory,
        timeout_seconds=request.timeout_seconds,
        skip_read="m45_evidence_missing" in blockers,
    )
    blockers.extend(post_broker_blockers)
    broker_writes = cycle_summary.broker_writes_performed
    if broker_writes and cycle_summary.broker_writes_reason != "natural_due_cycle":
        blockers.append("unexpected_broker_writes_in_m47")

    unique_blockers = tuple(dict.fromkeys(blockers))
    success = not unique_blockers and activation.runner_status == "active"
    packet = FrozenValidationRunnerM47Packet(
        packet_id=_packet_id("frozen-validation-runner-m47", now),
        timestamp=now,
        latest_spec_path=latest_spec_path,
        latest_spec_version=latest_spec_version,
        m45_evidence_reference=request.m45_evidence_path,
        m46_evidence_reference=request.m46_evidence_path,
        validation_status=validation_status,
        validation_start_timestamp_utc=start,
        validation_target_end_timestamp_utc=end,
        current_time_utc=now,
        validation_day_index=day_index,
        validation_window_active=window_active,
        pre_activation_broker_state=pre_state,
        market_data_status=market_status,
        runner_path_selected=activation.runner_path_selected,
        runner_status=activation.runner_status,
        schedule_or_runner_id=activation.schedule_or_runner_id,
        runner_command=activation.runner_command,
        old_test_schedules_active=old_test_schedules_active or activation.old_test_schedules_active,
        temporal_cloud_schedule_created=(
            temporal_cloud_schedule_created or activation.temporal_cloud_schedule_created
        ),
        temporal_cloud_schedule_id=activation.temporal_cloud_schedule_id,
        due_cycle_detected=due_cycle is not None,
        cycle_ran_in_m47=(
            cycle_summary.cycle_result in {"no_trade", "trade_executed", "refused", "error"}
            and due_cycle is not None
        ),
        cycle_result=cycle_summary.cycle_result,
        broker_writes_performed_in_m47=broker_writes,
        broker_writes_reason=cycle_summary.broker_writes_reason,
        post_activation_broker_state=post_state,
        reporting_status=ReportingStatus(
            cycle_packet_generated=cycle_summary.evidence_path is not None,
            daily_report_generated=False,
            dashboard_snapshot_generated=False,
        ),
        live_trading_enabled=safety_flags["live_trading_enabled"],
        autonomous_live_execution_enabled=safety_flags["autonomous_live_execution_enabled"],
        leverage_enabled=safety_flags["leverage_enabled"],
        live_shorting_enabled=safety_flags["live_shorting_enabled"],
        ai_broker_authority=safety_flags["ai_broker_authority"],
        level4_ready=safety_flags["level4_ready"],
        frozen_policy_drift_detected=drift_detected,
        m47_result="GO" if success else "NO_GO",
        blockers=unique_blockers,
    )
    return FrozenValidationRunnerM47Result(
        success=success,
        packet=packet,
        blockers=unique_blockers,
        broker_writes_performed=broker_writes,
        runner_activated=activation.runner_status == "active",
        cycle_result=packet.cycle_result,
    )


def run_frozen_validation_cycle_once(
    request: FrozenValidationCycleRequest,
    *,
    environ: Mapping[str, str] | None = None,
    app_config: AppConfig | None = None,
    client_factory: M45ReadOnlyClientFactory = build_m45_read_only_client,
    tiingo_client: TiingoSignalDataClient | None = None,
    current_time: Callable[[], datetime] | None = None,
    repo_root: Path | None = None,
    write_evidence: bool = True,
    due_cycle_override: Mapping[str, str] | None = None,
) -> FrozenValidationCycleResult:
    root = repo_root or Path.cwd()
    active_config = load_app_config(root / "config") if app_config is None else app_config
    active_environ = (
        load_preflight_environment(repo_root=root, base_environ=environ)
        if environ is not None
        else load_preflight_environment(repo_root=root)
    )
    now = _now(current_time)
    m45_packet = _load_json_mapping(root / request.m45_evidence_path)
    blockers = list(_cycle_request_blockers(request))
    if m45_packet is None:
        blockers.append("m45_evidence_missing")
    validation_status = _string_field(m45_packet, "validation_status", "missing")
    start = _datetime_field(m45_packet, "validation_start_timestamp_utc")
    end = _datetime_field(m45_packet, "validation_end_target_timestamp_utc")
    window_active = _validation_window_active(now=now, start=start, end=end)
    if validation_status != "active":
        blockers.append("m45_validation_not_active")
    if not window_active:
        blockers.append("validation_window_not_active")
    safety_flags, safety_blockers = _safety_flags(active_config)
    del safety_flags
    blockers.extend(safety_blockers)
    drift_detected, drift_blockers = _frozen_policy_drift(root, m45_packet)
    blockers.extend(drift_blockers)
    due_cycle = due_cycle_override or _due_cycle(now, active_config)
    if due_cycle is None:
        blockers.append("cycle_not_due")
    broker_state, broker_blockers = _read_broker_state(
        mode=request.mode,
        environ=active_environ,
        client_factory=client_factory,
        timeout_seconds=request.timeout_seconds,
        skip_read=False,
    )
    blockers.extend(broker_blockers)
    market_status, market_blockers = _verify_tiingo_status(
        mode=request.mode,
        environ=active_environ,
        app_config=active_config,
        tiingo_client=tiingo_client,
        now=now,
    )
    blockers.extend(market_blockers)
    if broker_state.reconciliation_summary != "flat_zero_positions_zero_open_orders":
        blockers.append("broker_reconciliation_not_clean")

    unique_blockers = tuple(dict.fromkeys(blockers))
    cycle_result: CycleResult
    if unique_blockers and unique_blockers != ("cycle_not_due",):
        cycle_result = "refused"
    elif "cycle_not_due" in unique_blockers:
        cycle_result = "skipped_not_due"
    else:
        cycle_result = "no_trade"
    packet = FrozenValidationCyclePacket(
        packet_id=_packet_id("frozen-validation-cycle", now),
        timestamp=now,
        m45_evidence_reference=request.m45_evidence_path,
        validation_status=validation_status,
        validation_window_active=window_active,
        due_cycle_detected=due_cycle is not None,
        cycle_label=None if due_cycle is None else due_cycle["label"],
        cycle_result=cycle_result,
        broker_state=broker_state,
        market_data_status=market_status,
        frozen_policy_drift_detected=drift_detected,
        candidate_generation_status=(
            "not_due"
            if due_cycle is None
            else "no_trade_activation_cycle_no_forced_candidates"
        ),
        blockers=unique_blockers,
    )
    output = (
        _write_cycle_artifact(root, packet)
        if write_evidence and cycle_result in {"no_trade", "refused"}
        else None
    )
    return FrozenValidationCycleResult(
        packet=packet,
        evidence_path=output,
        broker_writes_performed=False,
    )


def write_frozen_validation_runner_m47_artifact(
    result: FrozenValidationRunnerM47Result,
    path: str | Path = M47_EVIDENCE_PATH,
) -> Path:
    return _write_json(result.packet.model_dump(mode="json"), Path(path))


def write_frozen_validation_runner_m47_doc(
    result: FrozenValidationRunnerM47Result,
    path: str | Path = M47_DOC_PATH,
) -> Path:
    packet = result.packet
    text = "\n".join(
        (
            "# Milestone 47 Frozen Validation Runner Activation",
            "",
            f"Latest source of truth: `{packet.latest_spec_path}`.",
            "",
            "## Result",
            "",
            f"- M47 result: `{packet.m47_result}`",
            f"- Runner path selected: `{packet.runner_path_selected}`",
            f"- Runner status: `{packet.runner_status}`",
            f"- Runner command: `{packet.runner_command or 'none'}`",
            f"- Schedule/runner ID: `{packet.schedule_or_runner_id}`",
            f"- Cycle due: `{str(packet.due_cycle_detected).lower()}`",
            f"- Cycle ran in M47: `{str(packet.cycle_ran_in_m47).lower()}`",
            f"- Cycle result: `{packet.cycle_result}`",
            f"- Broker writes in M47: `{str(packet.broker_writes_performed_in_m47).lower()}`",
            f"- Broker writes reason: `{packet.broker_writes_reason}`",
            "",
            "## Validation Clock",
            "",
            f"- Status: `{packet.validation_status}`",
            f"- Start UTC: `{_format_dt(packet.validation_start_timestamp_utc)}`",
            f"- Target end UTC: `{_format_dt(packet.validation_target_end_timestamp_utc)}`",
            f"- Current UTC: `{_format_dt(packet.current_time_utc)}`",
            f"- Day index: `{packet.validation_day_index}`",
            f"- Window active: `{str(packet.validation_window_active).lower()}`",
            "",
            "## Broker / Data / Reporting",
            "",
            f"- Pre open orders: `{packet.pre_activation_broker_state.open_orders_count}`",
            f"- Pre positions: `{packet.pre_activation_broker_state.positions_count}`",
            f"- Post open orders: `{packet.post_activation_broker_state.open_orders_count}`",
            f"- Post positions: `{packet.post_activation_broker_state.positions_count}`",
            f"- Reconciliation: `{packet.post_activation_broker_state.reconciliation_summary}`",
            f"- Market data: `{packet.market_data_status.provider}` "
            f"`{packet.market_data_status.feed}` "
            f"`{packet.market_data_status.latest_check_result}`",
            f"- Cycle packet generated: `"
            f"{str(packet.reporting_status.cycle_packet_generated).lower()}`",
            f"- Daily report generated: `"
            f"{str(packet.reporting_status.daily_report_generated).lower()}`",
            f"- Dashboard snapshot generated: `"
            f"{str(packet.reporting_status.dashboard_snapshot_generated).lower()}`",
            "",
            "## Safety",
            "",
            f"- Live trading enabled: `{str(packet.live_trading_enabled).lower()}`",
            f"- Autonomous live execution enabled: `"
            f"{str(packet.autonomous_live_execution_enabled).lower()}`",
            f"- Leverage enabled: `{str(packet.leverage_enabled).lower()}`",
            f"- Live shorting enabled: `{str(packet.live_shorting_enabled).lower()}`",
            f"- AI broker authority: `{str(packet.ai_broker_authority).lower()}`",
            f"- Level 4 ready: `{str(packet.level4_ready).lower()}`",
            f"- Frozen policy drift detected: `"
            f"{str(packet.frozen_policy_drift_detected).lower()}`",
            "",
            "## Blockers",
            "",
            *(
                (f"- `{blocker}`" for blocker in packet.blockers)
                if packet.blockers
                else ("- None",)
            ),
            "",
            "## Monitoring",
            "",
            (
                "Monitor the runner heartbeat, generated cycle evidence, broker reconciliation, "
                "Tiingo status, protective stop coverage, daily reports, and incidents each "
                "trading day. Do not change frozen strategy, risk, universe, data provider, or "
                "AI authority during the validation window."
            ),
            "",
        )
    )
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(text, encoding="utf-8")
    return output


def run_runner_daemon(
    request: FrozenValidationCycleRequest,
    *,
    poll_seconds: int,
    repo_root: Path | None = None,
) -> None:
    root = repo_root or Path.cwd()
    runtime_dir = root / RUNTIME_DIR
    runtime_dir.mkdir(parents=True, exist_ok=True)
    while True:
        now = datetime.now(UTC)
        heartbeat = {
            "runner_id": RUNNER_ID,
            "timestamp": now.isoformat().replace("+00:00", "Z"),
            "status": "active",
        }
        (root / HEARTBEAT_FILE).write_text(
            json.dumps(heartbeat, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        try:
            if _due_cycle(now, load_app_config(root / "config")) is not None:
                run_frozen_validation_cycle_once(
                    request,
                    current_time=_constant_time(now),
                    repo_root=root,
                    write_evidence=True,
                )
        except Exception as exc:  # pragma: no cover - daemon resilience
            error = {
                "runner_id": RUNNER_ID,
                "timestamp": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
                "status": "error",
                "error_type": type(exc).__name__,
            }
            (root / HEARTBEAT_FILE).write_text(
                json.dumps(error, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
        time.sleep(poll_seconds)


def _m47_request_blockers(request: FrozenValidationRunnerRequest) -> tuple[str, ...]:
    blockers: list[str] = []
    if request.operator_approval != M47_APPROVAL:
        blockers.append("m47_operator_approval_marker_required")
    required = {
        "confirm_paper_only": request.confirm_paper_only,
        "confirm_validation_already_started": request.confirm_validation_already_started,
        "confirm_no_live_trading": request.confirm_no_live_trading,
        "confirm_no_autonomous_live": request.confirm_no_autonomous_live,
        "confirm_no_leverage": request.confirm_no_leverage,
        "confirm_live_shorting_disabled": request.confirm_live_shorting_disabled,
        "confirm_ai_no_broker_authority": request.confirm_ai_no_broker_authority,
        "confirm_no_level4": request.confirm_no_level4,
        "confirm_no_forced_trades": request.confirm_no_forced_trades,
    }
    blockers.extend(f"{name}_required" for name, confirmed in required.items() if not confirmed)
    return tuple(blockers)


def _cycle_request_blockers(request: FrozenValidationCycleRequest) -> tuple[str, ...]:
    required = {
        "confirm_paper_only": request.confirm_paper_only,
        "confirm_no_live_trading": request.confirm_no_live_trading,
        "confirm_no_autonomous_live": request.confirm_no_autonomous_live,
        "confirm_no_leverage": request.confirm_no_leverage,
        "confirm_live_shorting_disabled": request.confirm_live_shorting_disabled,
        "confirm_ai_no_broker_authority": request.confirm_ai_no_broker_authority,
        "confirm_no_level4": request.confirm_no_level4,
        "confirm_no_forced_trades": request.confirm_no_forced_trades,
    }
    return tuple(f"{name}_required" for name, confirmed in required.items() if not confirmed)


def _activate_or_observe_runner(
    *,
    request: FrozenValidationRunnerRequest,
    repo_root: Path,
    environ: Mapping[str, str],
    existing_blockers: tuple[str, ...],
    process_launcher: Callable[[Path, Mapping[str, str], int], int | None] | None,
) -> RunnerActivationSummary:
    runner_command = _runner_command(request.poll_seconds)
    pid_path = repo_root / PID_FILE
    existing_pid = _read_pid(pid_path)
    if existing_pid is not None and _pid_alive(existing_pid):
        return RunnerActivationSummary(
            runner_path_selected="local_runner",
            runner_status="unavailable",
            schedule_or_runner_id=RUNNER_ID,
            runner_command=runner_command,
            pid=existing_pid,
        )
    if existing_blockers:
        return RunnerActivationSummary(
            runner_path_selected="local_runner",
            runner_status="configured_not_started",
            schedule_or_runner_id=RUNNER_ID,
            runner_command=runner_command,
        )
    if not request.activate_runner:
        return RunnerActivationSummary(
            runner_path_selected="local_runner",
            runner_status="configured_not_started",
            schedule_or_runner_id=RUNNER_ID,
            runner_command=runner_command,
        )
    launcher = process_launcher or _launch_local_runner_process
    pid = launcher(repo_root, environ, request.poll_seconds)
    status: RunnerStatus = "active" if pid is not None else "unavailable"
    return RunnerActivationSummary(
        runner_path_selected="local_runner",
        runner_status=status,
        schedule_or_runner_id=RUNNER_ID,
        runner_command=runner_command,
        pid=pid,
    )


def _runner_blockers(activation: RunnerActivationSummary) -> tuple[str, ...]:
    if activation.runner_status == "active":
        return ()
    if activation.runner_status == "unavailable" and activation.pid is not None:
        return ("duplicate_active_runner_detected",)
    return ("local_runner_not_active",)


def _launch_local_runner_process(
    repo_root: Path,
    environ: Mapping[str, str],
    poll_seconds: int,
) -> int | None:
    runtime_dir = repo_root / RUNTIME_DIR
    runtime_dir.mkdir(parents=True, exist_ok=True)
    log_handle = (repo_root / LOG_FILE).open("ab")
    child_env = dict(os.environ)
    child_env.update(environ)
    child_env.update(_safety_overrides())
    cmd = [
        sys.executable,
        RUNNER_SCRIPT,
        "--daemon",
        "--poll-seconds",
        str(poll_seconds),
        "--confirm-paper-only",
        "--confirm-no-live-trading",
        "--confirm-no-autonomous-live",
        "--confirm-no-leverage",
        "--confirm-live-shorting-disabled",
        "--confirm-ai-no-broker-authority",
        "--confirm-no-level4",
        "--confirm-no-forced-trades",
    ]
    try:
        process = subprocess.Popen(  # noqa: S603
            cmd,
            cwd=repo_root,
            env=child_env,
            stdout=log_handle,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            start_new_session=True,
        )
    except OSError:
        return None
    time.sleep(0.2)
    if process.poll() is not None:
        return None
    (repo_root / PID_FILE).write_text(str(process.pid) + "\n", encoding="utf-8")
    (repo_root / HEARTBEAT_FILE).write_text(
        json.dumps(
            {
                "runner_id": RUNNER_ID,
                "pid": process.pid,
                "status": "active",
                "timestamp": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return process.pid


def _runner_command(poll_seconds: int) -> str:
    return (
        "uv run python scripts/run_frozen_paper_validation_runner.py --daemon "
        f"--poll-seconds {poll_seconds} --confirm-paper-only --confirm-no-live-trading "
        "--confirm-no-autonomous-live --confirm-no-leverage --confirm-live-shorting-disabled "
        "--confirm-ai-no-broker-authority --confirm-no-level4 --confirm-no-forced-trades"
    )


def _safety_overrides() -> dict[str, str]:
    return {
        "RUN_ALPACA_PAPER_ORDER_LIFECYCLE_SMOKE": "",
        "ALERT_ENABLE_REAL_DELIVERY": "false",
        "AI_ENABLE_ESCALATION": "false",
        "NEWS_ENABLE_OPENAI_WEB_FALLBACK": "false",
        "DASHBOARD_CONTROL_PLANE_ALLOW_CONTROL_SIGNALS": "false",
        "RUN_FIRST_CONTROLLED_PAPER_SESSION": "",
        "RUN_FIRST_CONTROLLED_PAPER_SESSION_EXECUTION": "",
        "RUN_VERCEL_DASHBOARD_PREVIEW": "",
        "RUN_TELEGRAM_ALERT_SMOKE": "",
    }


def _old_or_duplicate_schedule_active(repo_root: Path) -> bool:
    del repo_root
    return False


def _read_broker_state(
    *,
    mode: Literal["fake", "real-paper"],
    environ: Mapping[str, str],
    client_factory: M45ReadOnlyClientFactory,
    timeout_seconds: float,
    skip_read: bool,
) -> tuple[BrokerStateSummary, tuple[str, ...]]:
    if skip_read:
        return BrokerStateSummary(
            open_orders_count=0,
            positions_count=0,
            reconciliation_summary="not_checked_due_to_prior_gate_blocker",
        ), ()
    try:
        if mode == "fake":
            client: M45ReadOnlyClient = FakeM47ReadOnlyClient()
        else:
            credentials = AlpacaPaperCredentials(
                api_key=environ.get("ALPACA_API_KEY", "").strip(),
                secret_key=environ.get("ALPACA_SECRET_KEY", "").strip(),
                base_url=environ.get("ALPACA_BASE_URL", "").strip(),
            )
            client = client_factory(credentials, timeout_seconds)
        map_alpaca_account(client.get_account(), environment="paper")
        map_alpaca_clock(client.get_clock())
        orders = tuple(map(map_alpaca_order, client.list_open_orders()))
        positions = tuple(map(map_alpaca_position, client.list_positions()))
    except (AlpacaClientError, ValueError) as exc:
        return BrokerStateSummary(
            open_orders_count=0,
            positions_count=0,
            reconciliation_summary="broker_read_only_state_unavailable",
        ), (_sanitized_exception("broker_read_only_state_failed", exc),)
    active_positions = tuple(position for position in positions if abs(position.quantity) > 1e-9)
    state = BrokerStateSummary(
        open_orders_count=len(orders),
        positions_count=len(active_positions),
        reconciliation_summary=(
            "flat_zero_positions_zero_open_orders"
            if not orders and not active_positions
            else "non_flat_or_open_orders_present"
        ),
    )
    if state.open_orders_count or state.positions_count:
        return state, ("broker_reconciliation_not_clean",)
    return state, ()


def _verify_tiingo_status(
    *,
    mode: Literal["fake", "real-paper"],
    environ: Mapping[str, str],
    app_config: AppConfig,
    tiingo_client: TiingoSignalDataClient | None,
    now: datetime,
) -> tuple[MarketDataStatus, tuple[str, ...]]:
    client = FakeM47TiingoClient(now.date()) if mode == "fake" else tiingo_client
    gate = run_primary_signal_data_gate(
        PrimarySignalDataGateRequest(
            mode="verify",
            provider="tiingo",
            feed="eod",
            confirm_read_only=True,
            confirm_no_broker_writes=True,
            confirm_no_schedules=True,
            confirm_no_frozen_validation_start=True,
        ),
        environ=environ,
        app_config=app_config,
        tiingo_client=client,
        now=now,
    )
    status = MarketDataStatus(
        provider=gate.packet.configured_primary_signal_provider,
        feed=gate.packet.configured_primary_signal_feed,
        latest_check_result=gate.packet.data_check_result,
        sample_symbols=gate.packet.data_check_symbols,
    )
    if gate.go_no_go != "go":
        return status, ("tiingo_data_check_not_verified",)
    return status, ()


def _safety_flags(config: AppConfig) -> tuple[dict[str, bool], tuple[str, ...]]:
    flags = {
        "live_trading_enabled": bool(
            config.system.live_trading_enabled or config.validation.live_trading_enabled
        ),
        "autonomous_live_execution_enabled": bool(
            config.system.autonomous_execution_enabled
            or config.execution.autonomous_execution_enabled
            or config.validation.autonomous_live_execution_enabled
        ),
        "leverage_enabled": bool(
            config.risk_level_4_micro_live.allow_margin
            or config.risk_level_4_expanded.allow_margin
        ),
        "live_shorting_enabled": bool(
            config.live_universe.allow_shorting
            or config.risk_level_4_micro_live.allow_shorting
            or config.risk_level_4_expanded.allow_shorting
            or config.shorts.allow_live_shorting
            or config.validation.short_policy.live_shorting_enabled
        ),
        "ai_broker_authority": bool(
            config.ai.allow_ai_to_create_orders
            or config.validation.ai_policy.ai_may_authorize_trade
            or config.validation_ai.ai_may_authorize_trade
            or config.validation_ai.ai_may_authorize_scale_in
            or config.validation_ai.ai_may_authorize_shorts
        ),
        "level4_ready": bool(config.validation.level4_ready),
    }
    blockers = tuple(f"{name}_true" for name, enabled in flags.items() if enabled)
    return flags, blockers


def _frozen_policy_drift(
    repo_root: Path,
    m45_packet: Mapping[str, Any] | None,
) -> tuple[bool, tuple[str, ...]]:
    m45_hashes = _mapping_field(m45_packet, "frozen_hashes")
    if not m45_hashes:
        return True, ("m45_frozen_hashes_missing",)
    current_hashes = _frozen_hashes(repo_root).model_dump()
    drift = any(str(current_hashes[key]) != str(m45_hashes.get(key)) for key in current_hashes)
    return drift, ("frozen_policy_hash_drift_detected",) if drift else ()


def _due_cycle(now: datetime, config: AppConfig) -> Mapping[str, str] | None:
    local_now = now.astimezone(ZoneInfo("America/New_York"))
    if local_now.weekday() >= 5:
        return None
    schedule = config.validation.schedule
    schedule_points = {
        "data_refresh": schedule.data_refresh_et,
        "bod_reconciliation": schedule.bod_reconciliation_et,
        "plan_build": schedule.plan_build_et,
        "entry_window_start": schedule.entry_window_start_et,
        "entry_window_end": schedule.entry_window_end_et,
        "unfilled_entry_cancel": schedule.unfilled_entry_cancel_et,
        "eod_signal": schedule.eod_signal_et,
        "ai_research": schedule.ai_research_et,
        "trade_plan_snapshot": schedule.trade_plan_snapshot_et,
        "eod_reconciliation": schedule.eod_reconciliation_et,
        "daily_report": schedule.daily_report_et,
    }
    for label, hhmm in schedule_points.items():
        due_time = _parse_hhmm(hhmm)
        due_at = local_now.replace(
            hour=due_time.hour,
            minute=due_time.minute,
            second=0,
            microsecond=0,
        )
        delta = (local_now - due_at).total_seconds()
        if 0 <= delta < 300:
            return {"label": label, "due_at_et": hhmm}
    return None


def _parse_hhmm(value: str) -> dt_time:
    hour_text, minute_text = value.split(":", maxsplit=1)
    return dt_time(hour=int(hour_text), minute=int(minute_text))


def _load_json_mapping(path: Path) -> Mapping[str, Any] | None:
    if not path.is_file():
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    return value if isinstance(value, Mapping) else None


def _mapping_field(
    payload: Mapping[str, Any] | None,
    field_name: str,
) -> Mapping[str, Any]:
    if payload is None:
        return {}
    value = payload.get(field_name)
    return value if isinstance(value, Mapping) else {}


def _string_field(
    payload: Mapping[str, Any] | None,
    field_name: str,
    default: str,
) -> str:
    if payload is None:
        return default
    value = payload.get(field_name)
    return value if isinstance(value, str) else default


def _optional_string_field(
    payload: Mapping[str, Any] | None,
    field_name: str,
) -> str | None:
    value = _string_field(payload, field_name, "")
    return value or None


def _datetime_field(
    payload: Mapping[str, Any] | None,
    field_name: str,
) -> datetime | None:
    value = _optional_string_field(payload, field_name)
    if value is None:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _validation_window_active(
    *,
    now: datetime,
    start: datetime | None,
    end: datetime | None,
) -> bool:
    if start is None or end is None:
        return False
    return start <= now <= end


def _validation_day_index(*, now: datetime, start: datetime | None) -> int:
    if start is None or now < start:
        return 0
    return int((now - start).total_seconds() // 86_400) + 1


def _now(current_time: Callable[[], datetime] | None) -> datetime:
    value = (current_time or (lambda: datetime.now(UTC)))()
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _constant_time(value: datetime) -> Callable[[], datetime]:
    def current_time() -> datetime:
        return value

    return current_time


def _packet_id(prefix: str, now: datetime) -> str:
    return f"{prefix}-{now.strftime('%Y%m%dT%H%M%SZ')}"


def _write_json(payload: Mapping[str, Any], path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _write_cycle_artifact(repo_root: Path, packet: FrozenValidationCyclePacket) -> Path:
    output = repo_root / CYCLE_EVIDENCE_DIR / f"{packet.packet_id}.json"
    return _write_json(packet.model_dump(mode="json"), output)


def _format_dt(value: datetime | None) -> str:
    if value is None:
        return "missing"
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _read_pid(path: Path) -> int | None:
    if not path.is_file():
        return None
    try:
        return int(path.read_text(encoding="utf-8").strip())
    except ValueError:
        return None


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def _sanitized_exception(prefix: str, exc: BaseException) -> str:
    code = getattr(exc, "code", type(exc).__name__)
    return f"{prefix}:{code}"


class FakeM47ReadOnlyClient:
    """Flat read-only paper broker fixture."""

    def get_account(self) -> Mapping[str, Any]:
        return {
            "id": str(uuid5(NAMESPACE_URL, "m47-paper-account")),
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
        return ()

    def list_positions(self) -> Sequence[Mapping[str, Any]]:
        return ()


class FakeM47TiingoClient:
    """Read-only Tiingo EOD fixture with enough completed daily bars."""

    def __init__(self, end_date: datetime | Any) -> None:
        self._end_date = end_date if not isinstance(end_date, datetime) else end_date.date()

    def adjusted_daily_bars(
        self,
        symbol: str,
        start: Any,
        end: Any,
    ) -> Sequence[AdjustedDailyBar]:
        del start, end
        return tuple(
            AdjustedDailyBar(
                symbol=symbol,
                date=self._end_date - timedelta(days=300 - index),
                open=100.0 + index * 0.01,
                high=101.0 + index * 0.01,
                low=99.0 + index * 0.01,
                close=100.5 + index * 0.01,
                volume=1_000_000 + index,
                provider="tiingo",
            )
            for index in range(296)
        )
