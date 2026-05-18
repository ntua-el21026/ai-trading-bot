from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, cast

from packages.broker.alpaca import AlpacaPaperCredentials
from packages.core.config import load_app_config
from packages.paper.durable_runner import (
    M47B_APPROVAL,
    DurableRunnerM47BRequest,
    fake_cloud_heartbeat,
    run_durable_runner_m47b,
    write_durable_runner_m47b_artifact,
)
from packages.paper.validation_runner import M47BrokerReadOnlyClient
from packages.paper.validation_start import (
    LOCAL_SCHEDULE_ID,
    M45ReadOnlyClientFactory,
    _frozen_hashes,
)


def _fixed_start() -> datetime:
    return datetime(2026, 5, 18, 16, 51, 9, 38248, tzinfo=UTC)


def _inside_window() -> datetime:
    return datetime(2026, 5, 19, 10, 30, tzinfo=UTC)


def _outside_window() -> datetime:
    return datetime(2026, 7, 14, 10, 30, tzinfo=UTC)


def _prepare_repo_root(tmp_path: Path, *, artifacts: bool = True) -> Path:
    spec_dir = tmp_path / "docs/app"
    spec_dir.mkdir(parents=True)
    (spec_dir / "Autonomous_AI_Trading_Bot_SPEC_v0.6.md").write_text(
        "# v0.6 test spec\n",
        encoding="utf-8",
    )
    (tmp_path / ".gitignore").write_text(".runtime/\n*.log\n", encoding="utf-8")
    (tmp_path / ".vercelignore").write_text("apps/workers/\n", encoding="utf-8")
    (tmp_path / "vercel.json").write_text('{"framework": null}\n', encoding="utf-8")
    if artifacts:
        for path in (
            "Dockerfile.paper-runner",
            ".dockerignore",
            "docker-compose.paper-runner.yml",
            "deploy/systemd/frozen-paper-runner.service",
            "scripts/run_frozen_paper_validation_runner.py",
            "scripts/check_frozen_paper_runner_health.py",
        ):
            target = tmp_path / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("artifact\n", encoding="utf-8")
    return tmp_path


def _write_m45_packet(
    repo_root: Path,
    *,
    validation_status: str = "active",
    start: datetime | None = None,
    end: datetime | None = None,
    old_test_schedules_active: bool = False,
    hashes: Mapping[str, str] | None = None,
) -> Path:
    start_time = _fixed_start() if start is None else start
    end_time = start_time + timedelta(days=56) if end is None else end
    payload: dict[str, Any] = {
        "packet_id": "m45-test",
        "timestamp": start_time.isoformat().replace("+00:00", "Z"),
        "latest_spec_path": "docs/app/Autonomous_AI_Trading_Bot_SPEC_v0.6.md",
        "latest_spec_version": "v0.6",
        "validation_status": validation_status,
        "validation_start_timestamp_utc": start_time.isoformat().replace("+00:00", "Z"),
        "validation_end_target_timestamp_utc": end_time.isoformat().replace("+00:00", "Z"),
        "frozen_hashes": dict(hashes or _frozen_hashes(repo_root).model_dump()),
        "schedule": {
            "schedule_final_state": "active_local_paper_validation_registry",
            "schedule_id_or_name": LOCAL_SCHEDULE_ID,
            "old_test_schedules_active": old_test_schedules_active,
            "temporal_cloud_schedule_created": False,
        },
    }
    path = repo_root / "m45.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _write_m46_packet(repo_root: Path) -> Path:
    payload = {
        "packet_id": "m46-test",
        "m46_result": "NO_GO",
        "blockers": ["local_registry_has_no_active_runner"],
    }
    path = repo_root / "m46.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _write_m47_packet(
    repo_root: Path,
    *,
    runner_status: str = "active",
) -> Path:
    payload = {
        "packet_id": "m47-test",
        "m47_result": "GO",
        "runner_path_selected": "local_runner",
        "runner_status": runner_status,
        "old_test_schedules_active": False,
    }
    path = repo_root / "m47.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _request(
    m45_path: Path,
    m46_path: Path,
    m47_path: Path,
    **overrides: object,
) -> DurableRunnerM47BRequest:
    payload: dict[str, object] = {
        "mode": "fake",
        "operator_approval": M47B_APPROVAL,
        "confirm_paper_only": True,
        "confirm_validation_already_started": True,
        "confirm_no_live_trading": True,
        "confirm_no_autonomous_live": True,
        "confirm_no_leverage": True,
        "confirm_live_shorting_disabled": True,
        "confirm_ai_no_broker_authority": True,
        "confirm_no_level4": True,
        "confirm_no_forced_trades": True,
        "confirm_no_vercel_execution_worker": True,
        "m45_evidence_path": str(m45_path),
        "m46_evidence_path": str(m46_path),
        "m47_evidence_path": str(m47_path),
    }
    payload.update(overrides)
    return DurableRunnerM47BRequest.model_validate(payload)


def test_m47b_refuses_if_m45_evidence_missing(tmp_path: Path) -> None:
    repo_root = _prepare_repo_root(tmp_path)
    m46_path = _write_m46_packet(repo_root)
    m47_path = _write_m47_packet(repo_root)

    result = run_durable_runner_m47b(
        _request(repo_root / "missing.json", m46_path, m47_path),
        app_config=load_app_config(),
        current_time=_inside_window,
        repo_root=repo_root,
    )

    assert "m45_evidence_missing" in result.blockers
    assert result.packet.off_pc_operation_result == "NO_GO"


def test_m47b_refuses_if_validation_window_inactive(tmp_path: Path) -> None:
    repo_root = _prepare_repo_root(tmp_path)
    m45_path = _write_m45_packet(repo_root)
    m46_path = _write_m46_packet(repo_root)
    m47_path = _write_m47_packet(repo_root)

    result = run_durable_runner_m47b(
        _request(m45_path, m46_path, m47_path),
        app_config=load_app_config(),
        current_time=_outside_window,
        repo_root=repo_root,
    )

    assert result.packet.validation_window_active is False
    assert "validation_window_not_active" in result.blockers


def test_m47b_detects_local_runner_only(tmp_path: Path) -> None:
    repo_root = _prepare_repo_root(tmp_path, artifacts=False)
    m45_path = _write_m45_packet(repo_root)
    m46_path = _write_m46_packet(repo_root)
    m47_path = _write_m47_packet(repo_root)

    result = run_durable_runner_m47b(
        _request(m45_path, m46_path, m47_path),
        app_config=load_app_config(),
        current_time=_inside_window,
        repo_root=repo_root,
    )

    assert result.packet.durable_runner_status == "local_runner_only"
    assert "durable_runner_deployment_artifacts_missing" in result.blockers


def test_m47b_detects_deployment_ready_not_active(tmp_path: Path) -> None:
    repo_root = _prepare_repo_root(tmp_path)
    m45_path = _write_m45_packet(repo_root)
    m46_path = _write_m46_packet(repo_root)
    m47_path = _write_m47_packet(repo_root)

    result = run_durable_runner_m47b(
        _request(m45_path, m46_path, m47_path),
        app_config=load_app_config(),
        current_time=_inside_window,
        repo_root=repo_root,
    )

    assert result.packet.preparation_result == "GO"
    assert result.packet.off_pc_operation_result == "NO_GO"
    assert result.packet.durable_runner_status == "deployment_ready_not_active"
    assert "durable_off_pc_runner_not_active" in result.blockers


def test_m47b_detects_durable_runner_active(tmp_path: Path) -> None:
    repo_root = _prepare_repo_root(tmp_path)
    heartbeat = repo_root / ".runtime/durable_frozen_validation_runner/heartbeat.json"
    fake_cloud_heartbeat(heartbeat, now=_inside_window())
    m45_path = _write_m45_packet(repo_root)
    m46_path = _write_m46_packet(repo_root)
    m47_path = _write_m47_packet(repo_root)

    result = run_durable_runner_m47b(
        _request(m45_path, m46_path, m47_path),
        app_config=load_app_config(),
        current_time=_inside_window,
        repo_root=repo_root,
    )

    assert result.success is True
    assert result.packet.durable_runner_status == "durable_runner_active"
    assert result.packet.off_pc_operation_result == "GO"


def test_m47b_temporal_schedule_active_without_worker_is_no_go(tmp_path: Path) -> None:
    repo_root = _prepare_repo_root(tmp_path)
    m45_path = _write_m45_packet(repo_root)
    m46_path = _write_m46_packet(repo_root)
    m47_path = _write_m47_packet(repo_root)

    result = run_durable_runner_m47b(
        _request(m45_path, m46_path, m47_path, temporal_schedule_active=True),
        app_config=load_app_config(),
        current_time=_inside_window,
        repo_root=repo_root,
    )

    assert result.packet.selected_durable_path == "temporal_cloud_schedule_and_worker"
    assert "temporal_schedule_active_without_worker_confirmed" in result.blockers


def test_m47b_temporal_schedule_plus_worker_confirmed_is_go(tmp_path: Path) -> None:
    repo_root = _prepare_repo_root(tmp_path)
    m45_path = _write_m45_packet(repo_root)
    m46_path = _write_m46_packet(repo_root)
    m47_path = _write_m47_packet(repo_root)

    result = run_durable_runner_m47b(
        _request(
            m45_path,
            m46_path,
            m47_path,
            temporal_schedule_active=True,
            worker_registration_confirmed=True,
        ),
        app_config=load_app_config(),
        current_time=_inside_window,
        repo_root=repo_root,
    )

    assert result.success is True
    assert result.packet.durable_runner_status == "temporal_schedule_active_worker_confirmed"


def test_m47b_verifies_required_deployment_artifacts_exist(tmp_path: Path) -> None:
    repo_root = _prepare_repo_root(tmp_path)
    m45_path = _write_m45_packet(repo_root)
    m46_path = _write_m46_packet(repo_root)
    m47_path = _write_m47_packet(repo_root)

    result = run_durable_runner_m47b(
        _request(m45_path, m46_path, m47_path),
        app_config=load_app_config(),
        current_time=_inside_window,
        repo_root=repo_root,
    )

    assert "Dockerfile.paper-runner" in result.packet.deployment_artifacts
    assert "docker-compose.paper-runner.yml" in result.packet.deployment_artifacts
    assert "durable_runner_deployment_artifacts_missing" not in result.blockers


def test_m47b_verifies_runtime_paths_are_ignored(tmp_path: Path) -> None:
    repo_root = _prepare_repo_root(tmp_path)
    (repo_root / ".gitignore").write_text("*.log\n", encoding="utf-8")
    m45_path = _write_m45_packet(repo_root)
    m46_path = _write_m46_packet(repo_root)
    m47_path = _write_m47_packet(repo_root)

    result = run_durable_runner_m47b(
        _request(m45_path, m46_path, m47_path),
        app_config=load_app_config(),
        current_time=_inside_window,
        repo_root=repo_root,
    )

    assert "runtime_paths_not_ignored" in result.blockers


def test_m47b_verifies_vercel_execution_worker_is_not_used(tmp_path: Path) -> None:
    repo_root = _prepare_repo_root(tmp_path)
    (repo_root / ".vercelignore").write_text("apps/api/\n", encoding="utf-8")
    m45_path = _write_m45_packet(repo_root)
    m46_path = _write_m46_packet(repo_root)
    m47_path = _write_m47_packet(repo_root)

    result = run_durable_runner_m47b(
        _request(m45_path, m46_path, m47_path),
        app_config=load_app_config(),
        current_time=_inside_window,
        repo_root=repo_root,
    )

    assert result.packet.vercel_execution_worker_detected is True
    assert "vercel_execution_worker_detected" in result.blockers


def test_m47b_verifies_broker_read_only_state(tmp_path: Path) -> None:
    repo_root = _prepare_repo_root(tmp_path)
    m45_path = _write_m45_packet(repo_root)
    m46_path = _write_m46_packet(repo_root)
    m47_path = _write_m47_packet(repo_root)

    result = run_durable_runner_m47b(
        _request(m45_path, m46_path, m47_path, mode="real-paper"),
        environ=_paper_env(),
        app_config=load_app_config(),
        client_factory=_client_factory(_OpenOrderBrokerClient()),
        current_time=_inside_window,
        repo_root=repo_root,
    )

    assert result.packet.broker_state.open_orders_count == 1
    assert "broker_reconciliation_not_clean" in result.blockers


def test_m47b_verifies_tiingo_status_with_fake_data(tmp_path: Path) -> None:
    repo_root = _prepare_repo_root(tmp_path)
    m45_path = _write_m45_packet(repo_root)
    m46_path = _write_m46_packet(repo_root)
    m47_path = _write_m47_packet(repo_root)

    result = run_durable_runner_m47b(
        _request(m45_path, m46_path, m47_path),
        app_config=load_app_config(),
        current_time=_inside_window,
        repo_root=repo_root,
    )

    assert result.packet.market_data_status.provider == "tiingo"
    assert result.packet.market_data_status.latest_check_result == "verified"


def test_m47b_detects_frozen_hash_drift(tmp_path: Path) -> None:
    repo_root = _prepare_repo_root(tmp_path)
    hashes = dict(_frozen_hashes(repo_root).model_dump())
    hashes["config_hash"] = "not-the-start-hash"
    m45_path = _write_m45_packet(repo_root, hashes=hashes)
    m46_path = _write_m46_packet(repo_root)
    m47_path = _write_m47_packet(repo_root)

    result = run_durable_runner_m47b(
        _request(m45_path, m46_path, m47_path),
        app_config=load_app_config(),
        current_time=_inside_window,
        repo_root=repo_root,
    )

    assert result.packet.frozen_policy_drift_detected is True
    assert "frozen_policy_hash_drift_detected" in result.blockers


def test_m47b_evidence_contains_required_fields_and_excludes_secrets(tmp_path: Path) -> None:
    repo_root = _prepare_repo_root(tmp_path)
    m45_path = _write_m45_packet(repo_root)
    m46_path = _write_m46_packet(repo_root)
    m47_path = _write_m47_packet(repo_root)

    result = run_durable_runner_m47b(
        _request(m45_path, m46_path, m47_path),
        environ={
            "ALPACA_API_KEY": "secret-key-value",
            "ALPACA_SECRET_KEY": "secret-secret-value",
            "TIINGO_API_KEY": "secret-tiingo-value",
        },
        app_config=load_app_config(),
        current_time=_inside_window,
        repo_root=repo_root,
    )
    output = write_durable_runner_m47b_artifact(result, tmp_path / "m47b.json")
    payload = json.loads(output.read_text(encoding="utf-8"))
    required = {
        "packet_id",
        "timestamp",
        "latest_spec_path",
        "latest_spec_version",
        "m45_evidence_reference",
        "m46_evidence_reference",
        "m47_evidence_reference",
        "validation_status",
        "validation_start_timestamp_utc",
        "validation_target_end_timestamp_utc",
        "current_time_utc",
        "validation_day_index",
        "validation_window_active",
        "selected_durable_path",
        "durable_runner_status",
        "runner_command",
        "deployment_artifacts",
        "health_check_command",
        "heartbeat_status",
        "heartbeat_age_seconds",
        "temporal_schedule_created",
        "worker_registration_confirmed",
        "old_test_schedules_active",
        "vercel_execution_worker_detected",
        "broker_state",
        "market_data_status",
        "broker_writes_performed_in_m47b",
        "cycle_ran_in_m47b",
        "live_trading_enabled",
        "autonomous_live_execution_enabled",
        "leverage_enabled",
        "live_shorting_enabled",
        "ai_broker_authority",
        "level4_ready",
        "off_pc_operation_result",
        "blockers",
    }
    text = output.read_text(encoding="utf-8")

    assert required <= set(payload)
    assert "secret-key-value" not in text
    assert "secret-secret-value" not in text
    assert "secret-tiingo-value" not in text


def test_m47b_does_not_enable_live_autonomy_leverage_live_shorting_or_level4(
    tmp_path: Path,
) -> None:
    repo_root = _prepare_repo_root(tmp_path)
    m45_path = _write_m45_packet(repo_root)
    m46_path = _write_m46_packet(repo_root)
    m47_path = _write_m47_packet(repo_root)

    result = run_durable_runner_m47b(
        _request(m45_path, m46_path, m47_path),
        app_config=load_app_config(),
        current_time=_inside_window,
        repo_root=repo_root,
    )

    assert result.packet.live_trading_enabled is False
    assert result.packet.autonomous_live_execution_enabled is False
    assert result.packet.leverage_enabled is False
    assert result.packet.live_shorting_enabled is False
    assert result.packet.ai_broker_authority is False
    assert result.packet.level4_ready is False


def _paper_env() -> dict[str, str]:
    return {
        "ALPACA_API_KEY": "paper-key",
        "ALPACA_SECRET_KEY": "paper-secret",
        "ALPACA_BASE_URL": "https://paper-api.alpaca.markets",
        "TIINGO_API_KEY": "tiingo-secret",
    }


def _client_factory(client: M47BrokerReadOnlyClient) -> M45ReadOnlyClientFactory:
    def factory(
        _credentials: AlpacaPaperCredentials,
        _timeout_seconds: float,
    ) -> M47BrokerReadOnlyClient:
        return client

    return cast(M45ReadOnlyClientFactory, factory)


class _OpenOrderBrokerClient:
    def get_account(self) -> Mapping[str, Any]:
        return {
            "id": "paper-account",
            "equity": "100000",
            "cash": "100000",
            "buying_power": "100000",
            "shorting_enabled": True,
            "multiplier": "1",
            "currency": "USD",
        }

    def get_clock(self) -> Mapping[str, Any]:
        return {
            "is_open": True,
            "timestamp": "2026-05-19T10:30:00Z",
            "next_open": "2026-05-19T13:30:00Z",
            "next_close": "2026-05-19T20:00:00Z",
        }

    def list_open_orders(self) -> tuple[Mapping[str, Any], ...]:
        return (
            {
                "id": "broker-order-1",
                "client_order_id": "m47b-test-order",
                "symbol": "SPY",
                "side": "buy",
                "asset_class": "us_equity",
                "qty": "1",
                "filled_qty": "0",
                "type": "limit",
                "time_in_force": "day",
                "status": "new",
                "limit_price": "100",
                "submitted_at": "2026-05-19T10:30:00Z",
            },
        )

    def list_positions(self) -> tuple[Mapping[str, Any], ...]:
        return ()
