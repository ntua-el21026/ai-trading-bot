"""Milestone 47B durable/off-PC frozen paper runner preparation audit.

This module does not deploy infrastructure or submit broker orders. It verifies that the active
M45 validation can be moved to a server-side runner package and records whether an off-PC runner is
actually active or only deployment-ready.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal
from uuid import NAMESPACE_URL, uuid5

from pydantic import BaseModel, ConfigDict, Field

from packages.core.config import AppConfig, load_app_config
from packages.data.primary_signal_gate import TiingoSignalDataClient
from packages.paper.preflight import load_preflight_environment
from packages.paper.validation_runner import (
    M46_EVIDENCE_PATH,
    M47_EVIDENCE_PATH,
    BrokerStateSummary,
    FakeM47TiingoClient,
    MarketDataStatus,
    _datetime_field,
    _frozen_policy_drift,
    _latest_spec,
    _load_json_mapping,
    _now,
    _read_broker_state,
    _safety_flags,
    _string_field,
    _validation_day_index,
    _validation_window_active,
    _verify_tiingo_status,
)
from packages.paper.validation_start import (
    FROZEN_PAPER_VALIDATION_START_M45_EVIDENCE_PATH,
    LATEST_V06_SPEC_PATH,
    M45ReadOnlyClientFactory,
    build_m45_read_only_client,
)

M47B_APPROVAL = "MILESTONE_47B_DURABLE_OFF_PC_RUNNER"
M47B_EVIDENCE_PATH = "docs/evidence/durable_runner_m47b.json"
M47B_DOC_PATH = "docs/durable_runner_m47b.md"
DURABLE_HEARTBEAT_PATH = ".runtime/durable_frozen_validation_runner/heartbeat.json"
DURABLE_RUNNER_COMMAND = (
    "docker compose -f docker-compose.paper-runner.yml up -d --build frozen-paper-runner"
)
DURABLE_HEALTH_COMMAND = (
    "docker compose -f docker-compose.paper-runner.yml exec -T frozen-paper-runner "
    "uv run python scripts/check_frozen_paper_runner_health.py "
    "--heartbeat .runtime/frozen_validation_runner/heartbeat.json --max-age-seconds 900"
)

SelectedDurablePath = Literal[
    "temporal_cloud_schedule_and_worker",
    "cloud_vps_docker_runner",
    "systemd_runner",
    "docker_compose_runner",
    "deployment_ready_only",
    "local_runner_only",
]
DurableRunnerStatus = Literal[
    "durable_runner_active",
    "temporal_schedule_active_worker_confirmed",
    "deployment_ready_not_active",
    "local_runner_only",
    "no_runner",
]
HeartbeatStatus = Literal["fresh", "stale", "missing", "not_applicable"]
WorkerRegistrationStatus = bool | Literal["unknown"]
M47BGoNoGo = Literal["GO", "NO_GO"]
CycleResult = Literal["no_trade", "trade_executed", "refused", "skipped_not_due", "error"]


class M47BModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class DurableRunnerM47BRequest(M47BModel):
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
    confirm_no_vercel_execution_worker: bool = False
    timeout_seconds: float = Field(default=15.0, ge=1.0, le=60.0)
    m45_evidence_path: str = FROZEN_PAPER_VALIDATION_START_M45_EVIDENCE_PATH
    m46_evidence_path: str = M46_EVIDENCE_PATH
    m47_evidence_path: str = M47_EVIDENCE_PATH
    heartbeat_path: str = DURABLE_HEARTBEAT_PATH
    max_heartbeat_age_seconds: int = Field(default=900, ge=60, le=86_400)
    temporal_schedule_active: bool = False
    worker_registration_confirmed: WorkerRegistrationStatus = "unknown"


class DurableRunnerM47BPacket(M47BModel):
    packet_id: str
    timestamp: datetime
    latest_spec_path: str
    latest_spec_version: str
    m45_evidence_reference: str
    m46_evidence_reference: str
    m47_evidence_reference: str
    validation_status: str
    validation_start_timestamp_utc: datetime | None
    validation_target_end_timestamp_utc: datetime | None
    current_time_utc: datetime
    validation_day_index: int = Field(ge=0)
    validation_window_active: bool
    selected_durable_path: SelectedDurablePath
    durable_runner_status: DurableRunnerStatus
    runner_command: str
    deployment_artifacts: tuple[str, ...]
    health_check_command: str
    heartbeat_status: HeartbeatStatus
    heartbeat_age_seconds: float | None
    temporal_schedule_created: bool
    temporal_schedule_id: str | None
    worker_registration_confirmed: WorkerRegistrationStatus
    old_test_schedules_active: bool
    vercel_execution_worker_detected: bool
    broker_state: BrokerStateSummary
    market_data_status: MarketDataStatus
    broker_writes_performed_in_m47b: bool = False
    cycle_ran_in_m47b: bool = False
    cycle_result: CycleResult | None = None
    live_trading_enabled: bool = False
    autonomous_live_execution_enabled: bool = False
    leverage_enabled: bool = False
    live_shorting_enabled: bool = False
    ai_broker_authority: bool = False
    level4_ready: bool = False
    frozen_policy_drift_detected: bool
    off_pc_operation_result: M47BGoNoGo
    preparation_result: M47BGoNoGo
    blockers: tuple[str, ...]


class DurableRunnerM47BResult(M47BModel):
    success: bool
    packet: DurableRunnerM47BPacket
    blockers: tuple[str, ...]
    broker_writes_performed: bool = False


def run_durable_runner_m47b(
    request: DurableRunnerM47BRequest,
    *,
    environ: Mapping[str, str] | None = None,
    app_config: AppConfig | None = None,
    client_factory: M45ReadOnlyClientFactory = build_m45_read_only_client,
    tiingo_client: TiingoSignalDataClient | None = None,
    current_time: Callable[[], datetime] | None = None,
    repo_root: Path | None = None,
) -> DurableRunnerM47BResult:
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
    m47_packet = _load_json_mapping(root / request.m47_evidence_path)

    blockers: list[str] = []
    blockers.extend(_request_blockers(request))
    if latest_spec_path != LATEST_V06_SPEC_PATH or latest_spec_version != "v0.6":
        blockers.append("latest_spec_not_v0_6")
    if m45_packet is None:
        blockers.append("m45_evidence_missing")
    if m46_packet is None:
        blockers.append("m46_evidence_missing")
    if m47_packet is None:
        blockers.append("m47_evidence_missing")

    validation_status = _string_field(m45_packet, "validation_status", "missing")
    start = _datetime_field(m45_packet, "validation_start_timestamp_utc")
    end = _datetime_field(m45_packet, "validation_end_target_timestamp_utc")
    if m45_packet is not None and validation_status != "active":
        blockers.append("m45_validation_not_active")
    window_active = _validation_window_active(now=now, start=start, end=end)
    if not window_active:
        blockers.append("validation_window_not_active")
    day_index = _validation_day_index(now=now, start=start)

    artifacts = _deployment_artifacts(root)
    missing_artifacts = tuple(path for path, exists in artifacts.items() if not exists)
    if missing_artifacts:
        blockers.append("durable_runner_deployment_artifacts_missing")
    if not _runtime_paths_ignored(root):
        blockers.append("runtime_paths_not_ignored")

    vercel_worker_detected = _vercel_execution_worker_detected(root)
    if vercel_worker_detected:
        blockers.append("vercel_execution_worker_detected")

    old_test_schedules_active = _old_test_schedules_active(m45_packet, m47_packet)
    if old_test_schedules_active:
        blockers.append("old_test_schedules_active")

    safety_flags, safety_blockers = _safety_flags(active_config)
    blockers.extend(safety_blockers)
    drift_detected, drift_blockers = _frozen_policy_drift(root, m45_packet)
    blockers.extend(drift_blockers)

    broker_state, broker_blockers = _read_broker_state(
        mode=request.mode,
        environ=active_environ,
        client_factory=client_factory,
        timeout_seconds=request.timeout_seconds,
        skip_read=m45_packet is None,
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

    heartbeat_status, heartbeat_age = _heartbeat_status(
        root / request.heartbeat_path,
        now=now,
        max_age_seconds=request.max_heartbeat_age_seconds,
    )
    local_runner_active = _m47_local_runner_active(m47_packet)
    selected_path, durable_status = _classify_durable_status(
        deployment_ready=not missing_artifacts,
        heartbeat_status=heartbeat_status,
        temporal_schedule_active=request.temporal_schedule_active,
        worker_registration_confirmed=request.worker_registration_confirmed,
        local_runner_active=local_runner_active,
    )
    temporal_schedule_id = (
        "frozen-paper-validation-v0.6-temporal-cloud"
        if request.temporal_schedule_active
        else None
    )
    if (
        request.temporal_schedule_active
        and request.worker_registration_confirmed is not True
    ):
        blockers.append("temporal_schedule_active_without_worker_confirmed")
    if durable_status not in {
        "durable_runner_active",
        "temporal_schedule_active_worker_confirmed",
    }:
        blockers.append("durable_off_pc_runner_not_active")

    unique_blockers = tuple(dict.fromkeys(blockers))
    off_pc_success = not unique_blockers and durable_status in {
        "durable_runner_active",
        "temporal_schedule_active_worker_confirmed",
    }
    prep_blockers = tuple(
        blocker
        for blocker in unique_blockers
        if blocker not in {"durable_off_pc_runner_not_active"}
    )
    packet = DurableRunnerM47BPacket(
        packet_id=_packet_id("durable-runner-m47b", now),
        timestamp=now,
        latest_spec_path=latest_spec_path,
        latest_spec_version=latest_spec_version,
        m45_evidence_reference=request.m45_evidence_path,
        m46_evidence_reference=request.m46_evidence_path,
        m47_evidence_reference=request.m47_evidence_path,
        validation_status=validation_status,
        validation_start_timestamp_utc=start,
        validation_target_end_timestamp_utc=end,
        current_time_utc=now,
        validation_day_index=day_index,
        validation_window_active=window_active,
        selected_durable_path=selected_path,
        durable_runner_status=durable_status,
        runner_command=DURABLE_RUNNER_COMMAND,
        deployment_artifacts=tuple(artifacts),
        health_check_command=DURABLE_HEALTH_COMMAND,
        heartbeat_status=heartbeat_status,
        heartbeat_age_seconds=heartbeat_age,
        temporal_schedule_created=request.temporal_schedule_active,
        temporal_schedule_id=temporal_schedule_id,
        worker_registration_confirmed=request.worker_registration_confirmed,
        old_test_schedules_active=old_test_schedules_active,
        vercel_execution_worker_detected=vercel_worker_detected,
        broker_state=broker_state,
        market_data_status=market_status,
        live_trading_enabled=safety_flags["live_trading_enabled"],
        autonomous_live_execution_enabled=safety_flags["autonomous_live_execution_enabled"],
        leverage_enabled=safety_flags["leverage_enabled"],
        live_shorting_enabled=safety_flags["live_shorting_enabled"],
        ai_broker_authority=safety_flags["ai_broker_authority"],
        level4_ready=safety_flags["level4_ready"],
        frozen_policy_drift_detected=drift_detected,
        off_pc_operation_result="GO" if off_pc_success else "NO_GO",
        preparation_result="GO" if not prep_blockers else "NO_GO",
        blockers=unique_blockers,
    )
    return DurableRunnerM47BResult(
        success=off_pc_success,
        packet=packet,
        blockers=unique_blockers,
    )


def write_durable_runner_m47b_artifact(
    result: DurableRunnerM47BResult,
    path: str | Path = M47B_EVIDENCE_PATH,
) -> Path:
    return _write_json(result.packet.model_dump(mode="json"), Path(path))


def write_durable_runner_m47b_doc(
    result: DurableRunnerM47BResult,
    path: str | Path = M47B_DOC_PATH,
) -> Path:
    packet = result.packet
    blockers = "\n".join(f"- `{blocker}`" for blocker in packet.blockers) or "- None"
    text = "\n".join(
        (
            "# Milestone 47B Durable Off-PC Frozen Runner",
            "",
            f"Latest source of truth: `{packet.latest_spec_path}`.",
            "",
            "## Result",
            "",
            f"- Off-PC operation result: `{packet.off_pc_operation_result}`",
            f"- Preparation result: `{packet.preparation_result}`",
            f"- Selected durable path: `{packet.selected_durable_path}`",
            f"- Durable runner status: `{packet.durable_runner_status}`",
            f"- Runner command: `{packet.runner_command}`",
            f"- Health check command: `{packet.health_check_command}`",
            f"- Heartbeat status: `{packet.heartbeat_status}`",
            f"- Heartbeat age seconds: `{packet.heartbeat_age_seconds}`",
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
            "## Deployment Package",
            "",
            "Deployment artifacts:",
            *[f"- `{artifact}`" for artifact in packet.deployment_artifacts],
            "",
            "The package is intended for a small VPS or cloud VM using Docker Compose or systemd.",
            "It is not a Vercel execution worker and exposes no frontend secrets.",
            "",
            "## Broker / Data / Safety",
            "",
            f"- Broker open orders: `{packet.broker_state.open_orders_count}`",
            f"- Broker positions: `{packet.broker_state.positions_count}`",
            f"- Reconciliation: `{packet.broker_state.reconciliation_summary}`",
            f"- Market data: `{packet.market_data_status.provider}` "
            f"`{packet.market_data_status.feed}` "
            f"`{packet.market_data_status.latest_check_result}`",
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
            blockers,
            "",
            "## Setup Commands",
            "",
            "Build and start on the off-PC host:",
            "",
            "```bash",
            packet.runner_command,
            "```",
            "",
            "Health check:",
            "",
            "```bash",
            packet.health_check_command,
            "```",
            "",
            "Stop:",
            "",
            "```bash",
            "docker compose -f docker-compose.paper-runner.yml down",
            "```",
            "",
            "Monitor heartbeat, broker reconciliation, Tiingo status, frozen hash drift, "
            "cycle evidence, incidents, and daily reports each trading day.",
            "",
        )
    )
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(text, encoding="utf-8")
    return output


def _request_blockers(request: DurableRunnerM47BRequest) -> tuple[str, ...]:
    blockers: list[str] = []
    if request.operator_approval != M47B_APPROVAL:
        blockers.append("m47b_operator_approval_marker_required")
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
        "confirm_no_vercel_execution_worker": request.confirm_no_vercel_execution_worker,
    }
    blockers.extend(f"{name}_required" for name, confirmed in required.items() if not confirmed)
    return tuple(blockers)


def _deployment_artifacts(repo_root: Path) -> dict[str, bool]:
    paths = (
        "Dockerfile.paper-runner",
        ".dockerignore",
        "docker-compose.paper-runner.yml",
        "deploy/systemd/frozen-paper-runner.service",
        "scripts/run_frozen_paper_validation_runner.py",
        "scripts/check_frozen_paper_runner_health.py",
    )
    return {path: (repo_root / path).is_file() for path in paths}


def _runtime_paths_ignored(repo_root: Path) -> bool:
    gitignore = repo_root / ".gitignore"
    if not gitignore.is_file():
        return False
    text = gitignore.read_text(encoding="utf-8")
    return ".runtime/" in text and "*.log" in text


def _vercel_execution_worker_detected(repo_root: Path) -> bool:
    vercelignore = repo_root / ".vercelignore"
    vercel_config = repo_root / "vercel.json"
    ignored = vercelignore.is_file() and "apps/workers/" in vercelignore.read_text(
        encoding="utf-8"
    )
    config_text = vercel_config.read_text(encoding="utf-8") if vercel_config.is_file() else ""
    configured_functions = '"functions"' in config_text or '"crons"' in config_text
    return not ignored or configured_functions


def _old_test_schedules_active(
    m45_packet: Mapping[str, Any] | None,
    m47_packet: Mapping[str, Any] | None,
) -> bool:
    m45_schedule = _mapping_field(m45_packet, "schedule")
    return bool(
        m45_schedule.get("old_test_schedules_active", False)
        or (m47_packet or {}).get("old_test_schedules_active", False)
    )


def _mapping_field(payload: Mapping[str, Any] | None, name: str) -> Mapping[str, Any]:
    if payload is None:
        return {}
    value = payload.get(name)
    return value if isinstance(value, Mapping) else {}


def _heartbeat_status(
    path: Path,
    *,
    now: datetime,
    max_age_seconds: int,
) -> tuple[HeartbeatStatus, float | None]:
    if not path.is_file():
        return "missing", None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        raw_timestamp = payload.get("timestamp")
        if not isinstance(raw_timestamp, str):
            return "stale", None
        parsed = datetime.fromisoformat(raw_timestamp.replace("Z", "+00:00")).astimezone(UTC)
    except (json.JSONDecodeError, ValueError):
        return "stale", None
    age = max(0.0, (now - parsed).total_seconds())
    return ("fresh" if age <= max_age_seconds else "stale"), age


def _m47_local_runner_active(m47_packet: Mapping[str, Any] | None) -> bool:
    return (
        _string_field(m47_packet, "runner_path_selected", "") == "local_runner"
        and _string_field(m47_packet, "runner_status", "") == "active"
    )


def _classify_durable_status(
    *,
    deployment_ready: bool,
    heartbeat_status: HeartbeatStatus,
    temporal_schedule_active: bool,
    worker_registration_confirmed: WorkerRegistrationStatus,
    local_runner_active: bool,
) -> tuple[SelectedDurablePath, DurableRunnerStatus]:
    if temporal_schedule_active:
        return (
            "temporal_cloud_schedule_and_worker",
            "temporal_schedule_active_worker_confirmed"
            if worker_registration_confirmed is True
            else "deployment_ready_not_active",
        )
    if heartbeat_status == "fresh":
        return "cloud_vps_docker_runner", "durable_runner_active"
    if deployment_ready:
        return "cloud_vps_docker_runner", "deployment_ready_not_active"
    if local_runner_active:
        return "local_runner_only", "local_runner_only"
    return "local_runner_only", "no_runner"


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


class FakeM47BDurableTiingoClient(FakeM47TiingoClient):
    def __init__(self, now: datetime) -> None:
        super().__init__(now.date())


def fake_cloud_heartbeat(path: Path, *, now: datetime) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "runner_id": str(uuid5(NAMESPACE_URL, "m47b-durable-runner")),
                "status": "active",
                "timestamp": now.astimezone(UTC).isoformat().replace("+00:00", "Z"),
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
