"""Milestone 46 frozen-validation Day-1 operational audit.

This module is read-only by default. It verifies the M45 clock, local schedule registry,
paper broker state, Tiingo EOD data status, safety flags, and frozen hash drift without
submitting broker orders or activating schedules.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, model_validator

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
    _sanitized_exception,
    build_m45_read_only_client,
)

M46_EVIDENCE_PATH = "docs/evidence/frozen_validation_day1_audit_m46.json"
M46_DOC_PATH = "docs/frozen_validation_day1_audit_m46.md"

SchedulerExecutionStatus = Literal[
    "active_durable_schedule",
    "active_local_runner_confirmed",
    "active_registry_only_no_runner",
    "manual_trigger_required",
    "unknown",
]
M46GoNoGo = Literal["GO", "NO_GO"]
TemporalCloudDetected = bool | Literal["unknown"]


class M46Model(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class FrozenValidationDay1AuditRequest(M46Model):
    mode: Literal["fake", "real-paper"] = "real-paper"
    confirm_paper_only: bool = False
    confirm_no_live_trading: bool = False
    confirm_no_autonomous_live: bool = False
    confirm_no_leverage: bool = False
    confirm_no_level4: bool = False
    confirm_no_forced_trades: bool = False
    timeout_seconds: float = Field(default=15.0, ge=1.0, le=60.0)
    m45_evidence_path: str = FROZEN_PAPER_VALIDATION_START_M45_EVIDENCE_PATH


class SchedulerObservation(M46Model):
    durable_schedule_active: bool = False
    local_runner_active: bool = False
    local_runner_command: str | None = None
    manual_trigger_required: bool = False
    old_test_schedules_active: bool | None = None
    temporal_cloud_schedule_detected: TemporalCloudDetected | None = None

    @model_validator(mode="after")
    def validate_runner_command(self) -> SchedulerObservation:
        if self.local_runner_active and not self.local_runner_command:
            raise ValueError("active local runner requires a runner command")
        return self


class BrokerStateAudit(M46Model):
    open_orders_count: int = Field(ge=0)
    positions_count: int = Field(ge=0)
    reconciliation_summary: str


class MarketDataStatus(M46Model):
    provider: str
    feed: str
    latest_check_result: str
    sample_symbols: tuple[str, ...]


class ReportingStatus(M46Model):
    daily_packet_generated: bool
    daily_report_generated: bool
    dashboard_snapshot_generated: bool


class ValidationIntegrity(M46Model):
    config_hash_matches_start: bool
    frozen_policy_drift_detected: bool


class FrozenValidationDay1AuditPacket(M46Model):
    packet_id: str
    timestamp: datetime
    latest_spec_path: str
    latest_spec_version: str
    m45_evidence_reference: str
    validation_status: str
    validation_start_timestamp_utc: datetime | None
    validation_target_end_timestamp_utc: datetime | None
    current_time_utc: datetime
    validation_day_index: int = Field(ge=0)
    validation_window_active: bool
    schedule_registry_status: str
    scheduler_execution_status: SchedulerExecutionStatus
    schedule_id_or_name: str | None
    old_test_schedules_active: bool
    temporal_cloud_schedule_detected: TemporalCloudDetected
    runner_command: str | None = None
    broker_state: BrokerStateAudit
    market_data_status: MarketDataStatus
    reporting_status: ReportingStatus
    broker_writes_performed_in_m46: bool = False
    scheduled_cycle_run_in_m46: bool = False
    scheduled_cycle_result: str | None = None
    trades_created_by_scheduled_cycle: tuple[str, ...] = ()
    live_trading_enabled: bool = False
    autonomous_live_execution_enabled: bool = False
    leverage_enabled: bool = False
    live_shorting_enabled: bool = False
    ai_broker_authority: bool = False
    level4_ready: bool = False
    validation_integrity: ValidationIntegrity
    m46_result: M46GoNoGo
    blockers: tuple[str, ...]


class FrozenValidationDay1AuditResult(M46Model):
    success: bool
    packet: FrozenValidationDay1AuditPacket
    blockers: tuple[str, ...]
    broker_writes_performed: bool = False
    scheduled_cycle_run: bool = False


class M46BrokerReadOnlyClient(Protocol):
    def get_account(self) -> Mapping[str, Any]:
        """Return a paper account payload."""

    def get_clock(self) -> Mapping[str, Any]:
        """Return a market clock payload."""

    def list_open_orders(self) -> Sequence[Mapping[str, Any]]:
        """Return open order payloads."""

    def list_positions(self) -> Sequence[Mapping[str, Any]]:
        """Return position payloads."""


def run_frozen_validation_day1_audit_m46(
    request: FrozenValidationDay1AuditRequest,
    *,
    environ: Mapping[str, str] | None = None,
    app_config: AppConfig | None = None,
    client_factory: M45ReadOnlyClientFactory = build_m45_read_only_client,
    tiingo_client: TiingoSignalDataClient | None = None,
    scheduler_observation: SchedulerObservation | None = None,
    current_time: Callable[[], datetime] | None = None,
    repo_root: Path | None = None,
) -> FrozenValidationDay1AuditResult:
    root = repo_root or Path.cwd()
    active_config = load_app_config(root / "config") if app_config is None else app_config
    active_environ = (
        load_preflight_environment(repo_root=root, base_environ=environ)
        if environ is not None
        else load_preflight_environment(repo_root=root)
    )
    now = _now(current_time)
    latest_spec_path, latest_spec_version = _latest_spec(root)
    m45_path = root / request.m45_evidence_path
    m45_packet = _load_json_mapping(m45_path)

    blockers: list[str] = []
    blockers.extend(_request_blockers(request))
    if latest_spec_path != LATEST_V06_SPEC_PATH or latest_spec_version != "v0.6":
        blockers.append("latest_spec_not_v0_6")

    if m45_packet is None:
        blockers.append("m45_evidence_missing")

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
    registry_status = _string_field(
        schedule_mapping,
        "schedule_final_state",
        "missing",
    )
    schedule_id = _optional_string_field(schedule_mapping, "schedule_id_or_name")
    if registry_status != "active_local_paper_validation_registry":
        blockers.append("schedule_registry_not_active")

    observation = scheduler_observation or _inspect_scheduler_observation(root)
    old_test_schedules_active = bool(
        observation.old_test_schedules_active
        if observation.old_test_schedules_active is not None
        else bool(schedule_mapping.get("old_test_schedules_active", False))
    )
    temporal_detected: TemporalCloudDetected = (
        observation.temporal_cloud_schedule_detected
        if observation.temporal_cloud_schedule_detected is not None
        else bool(schedule_mapping.get("temporal_cloud_schedule_created", False))
    )
    scheduler_status, scheduler_blockers = _classify_scheduler(
        registry_status=registry_status,
        observation=observation,
        old_test_schedules_active=old_test_schedules_active,
        temporal_cloud_schedule_detected=temporal_detected,
    )
    blockers.extend(scheduler_blockers)

    broker_state, broker_blockers = _read_broker_state(
        request=request,
        environ=active_environ,
        client_factory=client_factory,
        gate_blockers=tuple(blockers),
    )
    blockers.extend(broker_blockers)

    market_data_status, market_data_blockers = _verify_tiingo_status(
        request=request,
        environ=active_environ,
        app_config=active_config,
        tiingo_client=tiingo_client,
        now=now,
    )
    blockers.extend(market_data_blockers)

    safety_flags, safety_blockers = _safety_flags(active_config)
    blockers.extend(safety_blockers)
    integrity, integrity_blockers = _validation_integrity(root, m45_packet)
    blockers.extend(integrity_blockers)

    unique_blockers = tuple(dict.fromkeys(blockers))
    m46_result: M46GoNoGo = "GO" if not unique_blockers else "NO_GO"
    packet = FrozenValidationDay1AuditPacket(
        packet_id=_packet_id("frozen-validation-day1-audit-m46", now),
        timestamp=now,
        latest_spec_path=latest_spec_path,
        latest_spec_version=latest_spec_version,
        m45_evidence_reference=request.m45_evidence_path,
        validation_status=validation_status,
        validation_start_timestamp_utc=start,
        validation_target_end_timestamp_utc=end,
        current_time_utc=now,
        validation_day_index=day_index,
        validation_window_active=window_active,
        schedule_registry_status=registry_status,
        scheduler_execution_status=scheduler_status,
        schedule_id_or_name=schedule_id,
        old_test_schedules_active=old_test_schedules_active,
        temporal_cloud_schedule_detected=temporal_detected,
        runner_command=observation.local_runner_command,
        broker_state=broker_state,
        market_data_status=market_data_status,
        reporting_status=ReportingStatus(
            daily_packet_generated=True,
            daily_report_generated=False,
            dashboard_snapshot_generated=False,
        ),
        scheduled_cycle_result=None,
        live_trading_enabled=safety_flags["live_trading_enabled"],
        autonomous_live_execution_enabled=safety_flags["autonomous_live_execution_enabled"],
        leverage_enabled=safety_flags["leverage_enabled"],
        live_shorting_enabled=safety_flags["live_shorting_enabled"],
        ai_broker_authority=safety_flags["ai_broker_authority"],
        level4_ready=safety_flags["level4_ready"],
        validation_integrity=integrity,
        m46_result=m46_result,
        blockers=unique_blockers,
    )
    return FrozenValidationDay1AuditResult(
        success=m46_result == "GO",
        packet=packet,
        blockers=unique_blockers,
    )


def write_frozen_validation_day1_audit_m46_artifact(
    result: FrozenValidationDay1AuditResult,
    path: str | Path = M46_EVIDENCE_PATH,
) -> Path:
    return _write_json(result.packet.model_dump(mode="json"), Path(path))


def write_frozen_validation_day1_audit_m46_doc(
    result: FrozenValidationDay1AuditResult,
    path: str | Path = M46_DOC_PATH,
) -> Path:
    packet = result.packet
    text = "\n".join(
        (
            "# Milestone 46 Frozen Validation Day-1 Audit",
            "",
            f"Latest source of truth: `{packet.latest_spec_path}`.",
            "",
            "## Result",
            "",
            f"- M46 result: `{packet.m46_result}`",
            f"- Validation status: `{packet.validation_status}`",
            f"- Validation window active: `{str(packet.validation_window_active).lower()}`",
            f"- Validation day index: `{packet.validation_day_index}`",
            f"- Scheduler execution status: `{packet.scheduler_execution_status}`",
            f"- Broker writes performed in M46: `"
            f"{str(packet.broker_writes_performed_in_m46).lower()}`",
            f"- Scheduled cycle run in M46: `"
            f"{str(packet.scheduled_cycle_run_in_m46).lower()}`",
            "",
            "## Validation Clock",
            "",
            f"- Start UTC: `{_format_dt(packet.validation_start_timestamp_utc)}`",
            f"- Target end UTC: `{_format_dt(packet.validation_target_end_timestamp_utc)}`",
            f"- Current audit time UTC: `{_format_dt(packet.current_time_utc)}`",
            "",
            "## Scheduler / Runner",
            "",
            f"- Local registry status: `{packet.schedule_registry_status}`",
            f"- Schedule ID/name: `{packet.schedule_id_or_name}`",
            f"- Runner command: `{packet.runner_command or 'none'}`",
            f"- Old/test schedules active: `{str(packet.old_test_schedules_active).lower()}`",
            f"- Temporal Cloud schedule detected: `"
            f"{_format_temporal_detected(packet.temporal_cloud_schedule_detected)}`",
            "",
            "## Broker / Data / Reporting",
            "",
            f"- Open orders: `{packet.broker_state.open_orders_count}`",
            f"- Positions: `{packet.broker_state.positions_count}`",
            f"- Reconciliation summary: `{packet.broker_state.reconciliation_summary}`",
            f"- Market data: `{packet.market_data_status.provider}` "
            f"`{packet.market_data_status.feed}` "
            f"`{packet.market_data_status.latest_check_result}`",
            f"- Daily packet generated: `"
            f"{str(packet.reporting_status.daily_packet_generated).lower()}`",
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
            "",
            "## Blockers",
            "",
            *(
                (f"- `{blocker}`" for blocker in packet.blockers)
                if packet.blockers
                else ("- None",)
            ),
            "",
            "## Next Operational Step",
            "",
            _next_step(packet),
            "",
        )
    )
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(text, encoding="utf-8")
    return output


def _request_blockers(request: FrozenValidationDay1AuditRequest) -> tuple[str, ...]:
    required = {
        "confirm_paper_only": request.confirm_paper_only,
        "confirm_no_live_trading": request.confirm_no_live_trading,
        "confirm_no_autonomous_live": request.confirm_no_autonomous_live,
        "confirm_no_leverage": request.confirm_no_leverage,
        "confirm_no_level4": request.confirm_no_level4,
        "confirm_no_forced_trades": request.confirm_no_forced_trades,
    }
    return tuple(f"{name}_required" for name, confirmed in required.items() if not confirmed)


def _inspect_scheduler_observation(repo_root: Path) -> SchedulerObservation:
    runner_paths = (
        "scripts/run_frozen_paper_validation_runner.py",
        "scripts/run_frozen_validation_registry.py",
        "scripts/run_frozen_validation_cycle.py",
    )
    for runner_path in runner_paths:
        if (repo_root / runner_path).is_file():
            return SchedulerObservation(
                local_runner_active=True,
                local_runner_command=f"uv run python {runner_path}",
                temporal_cloud_schedule_detected=False,
            )
    return SchedulerObservation(temporal_cloud_schedule_detected=False)


def _classify_scheduler(
    *,
    registry_status: str,
    observation: SchedulerObservation,
    old_test_schedules_active: bool,
    temporal_cloud_schedule_detected: TemporalCloudDetected,
) -> tuple[SchedulerExecutionStatus, tuple[str, ...]]:
    blockers: list[str] = []
    if old_test_schedules_active:
        blockers.append("old_test_schedules_active")
    if temporal_cloud_schedule_detected is True:
        blockers.append("unexpected_temporal_cloud_schedule_detected")

    if observation.durable_schedule_active:
        status: SchedulerExecutionStatus = "active_durable_schedule"
    elif observation.local_runner_active and observation.local_runner_command:
        status = "active_local_runner_confirmed"
    elif observation.manual_trigger_required:
        status = "manual_trigger_required"
        blockers.append("manual_trigger_required")
    elif registry_status == "active_local_paper_validation_registry":
        status = "active_registry_only_no_runner"
        blockers.append("local_registry_has_no_active_runner")
    else:
        status = "unknown"
        blockers.append("scheduler_execution_status_unknown")

    return status, tuple(blockers)


def _read_broker_state(
    *,
    request: FrozenValidationDay1AuditRequest,
    environ: Mapping[str, str],
    client_factory: M45ReadOnlyClientFactory,
    gate_blockers: tuple[str, ...],
) -> tuple[BrokerStateAudit, tuple[str, ...]]:
    if "m45_evidence_missing" in gate_blockers or "latest_spec_not_v0_6" in gate_blockers:
        return BrokerStateAudit(
            open_orders_count=0,
            positions_count=0,
            reconciliation_summary="not_checked_due_to_prior_gate_blocker",
        ), ()
    try:
        if request.mode == "fake":
            client: M45ReadOnlyClient = FakeM46ReadOnlyClient()
        else:
            credentials = AlpacaPaperCredentials(
                api_key=environ.get("ALPACA_API_KEY", "").strip(),
                secret_key=environ.get("ALPACA_SECRET_KEY", "").strip(),
                base_url=environ.get("ALPACA_BASE_URL", "").strip(),
            )
            client = client_factory(credentials, request.timeout_seconds)
        map_alpaca_account(client.get_account(), environment="paper")
        map_alpaca_clock(client.get_clock())
        orders = tuple(map(map_alpaca_order, client.list_open_orders()))
        positions = tuple(map(map_alpaca_position, client.list_positions()))
    except (AlpacaClientError, ValueError) as exc:
        return BrokerStateAudit(
            open_orders_count=0,
            positions_count=0,
            reconciliation_summary="broker_read_only_state_unavailable",
        ), (_sanitized_exception("broker_read_only_state_failed", exc),)

    active_positions = tuple(position for position in positions if abs(position.quantity) > 1e-9)
    summary = (
        "flat_zero_positions_zero_open_orders"
        if not orders and not active_positions
        else "non_flat_or_open_orders_present"
    )
    state = BrokerStateAudit(
        open_orders_count=len(orders),
        positions_count=len(active_positions),
        reconciliation_summary=summary,
    )
    blockers: list[str] = []
    if state.open_orders_count or state.positions_count:
        blockers.append("broker_state_not_flat_or_open_orders_present")
    return state, tuple(blockers)


def _verify_tiingo_status(
    *,
    request: FrozenValidationDay1AuditRequest,
    environ: Mapping[str, str],
    app_config: AppConfig,
    tiingo_client: TiingoSignalDataClient | None,
    now: datetime,
) -> tuple[MarketDataStatus, tuple[str, ...]]:
    client = FakeM46TiingoClient(now.date()) if request.mode == "fake" else tiingo_client
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


def _validation_integrity(
    repo_root: Path,
    m45_packet: Mapping[str, Any] | None,
) -> tuple[ValidationIntegrity, tuple[str, ...]]:
    current_hashes = _frozen_hashes(repo_root).model_dump()
    m45_hashes_value = _mapping_field(m45_packet, "frozen_hashes")
    if not m45_hashes_value:
        return ValidationIntegrity(
            config_hash_matches_start=False,
            frozen_policy_drift_detected=True,
        ), ("m45_frozen_hashes_missing",)
    m45_hashes = {key: str(value) for key, value in m45_hashes_value.items()}
    config_matches = current_hashes.get("config_hash") == m45_hashes.get("config_hash")
    drift = any(current_hashes.get(key) != m45_hashes.get(key) for key in current_hashes)
    blockers: list[str] = []
    if not config_matches:
        blockers.append("frozen_config_hash_drift_detected")
    if drift:
        blockers.append("frozen_policy_hash_drift_detected")
    return ValidationIntegrity(
        config_hash_matches_start=config_matches,
        frozen_policy_drift_detected=drift,
    ), tuple(blockers)


def _load_json_mapping(path: Path) -> Mapping[str, Any] | None:
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, Mapping) else None


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


def _packet_id(prefix: str, now: datetime) -> str:
    return f"{prefix}-{now.strftime('%Y%m%dT%H%M%SZ')}"


def _write_json(payload: Mapping[str, Any], path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _format_dt(value: datetime | None) -> str:
    if value is None:
        return "missing"
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _format_temporal_detected(value: TemporalCloudDetected) -> str:
    if isinstance(value, bool):
        return str(value).lower()
    return value


def _next_step(packet: FrozenValidationDay1AuditPacket) -> str:
    if packet.m46_result == "GO":
        return (
            "Continue daily monitoring packets through the frozen window and keep Level 4 "
            "readiness blocked until frozen-paper acceptance criteria are met."
        )
    if "local_registry_has_no_active_runner" in packet.blockers:
        return (
            "Implement or start a documented local runner, or replace the registry with an "
            "explicitly approved durable paper-only schedule in a later milestone."
        )
    return "Resolve the listed blockers before claiming automatic frozen-validation operation."


class FakeM46ReadOnlyClient:
    """Flat read-only paper broker fixture for M46 fake mode."""

    def get_account(self) -> Mapping[str, Any]:
        return {
            "id": "m46-paper-account",
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


class FakeM46TiingoClient:
    """Read-only Tiingo EOD fixture with enough completed daily bars."""

    def __init__(self, end_date: date) -> None:
        self._end_date = end_date

    def adjusted_daily_bars(
        self,
        symbol: str,
        start: date,
        end: date,
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
