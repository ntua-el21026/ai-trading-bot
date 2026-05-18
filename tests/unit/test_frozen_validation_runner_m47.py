from __future__ import annotations

import json
import os
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, cast

from packages.broker.alpaca import AlpacaPaperCredentials
from packages.core.config import load_app_config
from packages.paper.validation_runner import (
    M47_APPROVAL,
    PID_FILE,
    FrozenValidationCycleRequest,
    FrozenValidationRunnerRequest,
    M47BrokerReadOnlyClient,
    run_frozen_validation_cycle_once,
    run_frozen_validation_runner_m47,
    write_frozen_validation_runner_m47_artifact,
)
from packages.paper.validation_start import (
    LOCAL_SCHEDULE_ID,
    M45ReadOnlyClientFactory,
    _frozen_hashes,
)


def _fixed_start() -> datetime:
    return datetime(2026, 5, 18, 16, 51, 9, 38248, tzinfo=UTC)


def _inside_window() -> datetime:
    return datetime(2026, 5, 18, 17, 30, tzinfo=UTC)


def _due_window() -> datetime:
    return datetime(2026, 5, 18, 20, 10, 30, tzinfo=UTC)


def _outside_window() -> datetime:
    return datetime(2026, 7, 14, 17, 30, tzinfo=UTC)


def _prepare_repo_root(tmp_path: Path) -> Path:
    spec_dir = tmp_path / "docs/app"
    spec_dir.mkdir(parents=True)
    (spec_dir / "Autonomous_AI_Trading_Bot_SPEC_v0.6.md").write_text(
        "# v0.6 test spec\n",
        encoding="utf-8",
    )
    return tmp_path


def _write_m45_packet(
    repo_root: Path,
    *,
    validation_status: str = "active",
    start: datetime | None = None,
    end: datetime | None = None,
    schedule_status: str = "active_local_paper_validation_registry",
    old_test_schedules_active: bool = False,
    temporal_cloud_schedule_created: bool = False,
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
            "schedule_final_state": schedule_status,
            "schedule_id_or_name": LOCAL_SCHEDULE_ID,
            "old_test_schedules_active": old_test_schedules_active,
            "temporal_cloud_schedule_created": temporal_cloud_schedule_created,
        },
    }
    path = repo_root / "m45.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _write_m46_packet(
    repo_root: Path,
    *,
    blockers: tuple[str, ...] = ("local_registry_has_no_active_runner",),
) -> Path:
    payload: dict[str, Any] = {
        "packet_id": "m46-test",
        "timestamp": _inside_window().isoformat().replace("+00:00", "Z"),
        "m46_result": "NO_GO",
        "scheduler_execution_status": "active_registry_only_no_runner",
        "blockers": list(blockers),
    }
    path = repo_root / "m46.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _request(m45_path: Path, m46_path: Path, **overrides: object) -> FrozenValidationRunnerRequest:
    payload: dict[str, object] = {
        "mode": "fake",
        "operator_approval": M47_APPROVAL,
        "confirm_paper_only": True,
        "confirm_validation_already_started": True,
        "confirm_no_live_trading": True,
        "confirm_no_autonomous_live": True,
        "confirm_no_leverage": True,
        "confirm_live_shorting_disabled": True,
        "confirm_ai_no_broker_authority": True,
        "confirm_no_level4": True,
        "confirm_no_forced_trades": True,
        "m45_evidence_path": str(m45_path),
        "m46_evidence_path": str(m46_path),
    }
    payload.update(overrides)
    return FrozenValidationRunnerRequest.model_validate(payload)


def _cycle_request(m45_path: Path, **overrides: object) -> FrozenValidationCycleRequest:
    payload: dict[str, object] = {
        "mode": "fake",
        "confirm_paper_only": True,
        "confirm_no_live_trading": True,
        "confirm_no_autonomous_live": True,
        "confirm_no_leverage": True,
        "confirm_live_shorting_disabled": True,
        "confirm_ai_no_broker_authority": True,
        "confirm_no_level4": True,
        "confirm_no_forced_trades": True,
        "m45_evidence_path": str(m45_path),
    }
    payload.update(overrides)
    return FrozenValidationCycleRequest.model_validate(payload)


def _launcher(_repo_root: Path, _environ: Mapping[str, str], _poll_seconds: int) -> int | None:
    return 4242


def test_m47_refuses_if_m45_evidence_missing(tmp_path: Path) -> None:
    repo_root = _prepare_repo_root(tmp_path)
    m46_path = _write_m46_packet(repo_root)

    result = run_frozen_validation_runner_m47(
        _request(repo_root / "missing.json", m46_path),
        app_config=load_app_config(),
        current_time=_inside_window,
        repo_root=repo_root,
        process_launcher=_launcher,
    )

    assert result.packet.m47_result == "NO_GO"
    assert "m45_evidence_missing" in result.blockers


def test_m47_refuses_if_m46_evidence_missing(tmp_path: Path) -> None:
    repo_root = _prepare_repo_root(tmp_path)
    m45_path = _write_m45_packet(repo_root)

    result = run_frozen_validation_runner_m47(
        _request(m45_path, repo_root / "missing.json"),
        app_config=load_app_config(),
        current_time=_inside_window,
        repo_root=repo_root,
        process_launcher=_launcher,
    )

    assert "m46_evidence_missing" in result.blockers


def test_m47_refuses_if_validation_window_inactive(tmp_path: Path) -> None:
    repo_root = _prepare_repo_root(tmp_path)
    m45_path = _write_m45_packet(repo_root)
    m46_path = _write_m46_packet(repo_root)

    result = run_frozen_validation_runner_m47(
        _request(m45_path, m46_path),
        app_config=load_app_config(),
        current_time=_outside_window,
        repo_root=repo_root,
        process_launcher=_launcher,
    )

    assert result.packet.validation_window_active is False
    assert "validation_window_not_active" in result.blockers


def test_m47_refuses_without_operator_approval_marker(tmp_path: Path) -> None:
    repo_root = _prepare_repo_root(tmp_path)
    m45_path = _write_m45_packet(repo_root)
    m46_path = _write_m46_packet(repo_root)

    result = run_frozen_validation_runner_m47(
        _request(m45_path, m46_path, operator_approval="wrong"),
        app_config=load_app_config(),
        current_time=_inside_window,
        repo_root=repo_root,
        process_launcher=_launcher,
    )

    assert "m47_operator_approval_marker_required" in result.blockers
    assert result.packet.runner_status == "configured_not_started"


def test_m47_detects_registry_only_no_runner_state(tmp_path: Path) -> None:
    repo_root = _prepare_repo_root(tmp_path)
    m45_path = _write_m45_packet(repo_root)
    m46_path = _write_m46_packet(repo_root)

    result = run_frozen_validation_runner_m47(
        _request(m45_path, m46_path, activate_runner=False),
        app_config=load_app_config(),
        current_time=_inside_window,
        repo_root=repo_root,
        process_launcher=_launcher,
    )

    assert result.packet.runner_path_selected == "local_runner"
    assert result.packet.runner_status == "configured_not_started"
    assert "local_runner_not_active" in result.blockers


def test_m47_selects_local_runner_when_activation_succeeds(tmp_path: Path) -> None:
    repo_root = _prepare_repo_root(tmp_path)
    m45_path = _write_m45_packet(repo_root)
    m46_path = _write_m46_packet(repo_root)

    result = run_frozen_validation_runner_m47(
        _request(m45_path, m46_path),
        app_config=load_app_config(),
        current_time=_inside_window,
        repo_root=repo_root,
        process_launcher=_launcher,
    )

    assert result.success is True
    assert result.packet.runner_path_selected == "local_runner"
    assert result.packet.runner_status == "active"
    assert result.packet.temporal_cloud_schedule_created is False


def test_m47_refuses_unexpected_temporal_schedule(tmp_path: Path) -> None:
    repo_root = _prepare_repo_root(tmp_path)
    m45_path = _write_m45_packet(repo_root, temporal_cloud_schedule_created=True)
    m46_path = _write_m46_packet(repo_root)

    result = run_frozen_validation_runner_m47(
        _request(m45_path, m46_path),
        app_config=load_app_config(),
        current_time=_inside_window,
        repo_root=repo_root,
        process_launcher=_launcher,
    )

    assert result.packet.temporal_cloud_schedule_created is True
    assert "unexpected_temporal_cloud_schedule_detected" in result.blockers


def test_m47_refuses_duplicate_active_runner(tmp_path: Path) -> None:
    repo_root = _prepare_repo_root(tmp_path)
    runtime_pid = repo_root / PID_FILE
    runtime_pid.parent.mkdir(parents=True)
    runtime_pid.write_text(str(os.getpid()), encoding="utf-8")
    m45_path = _write_m45_packet(repo_root)
    m46_path = _write_m46_packet(repo_root)

    result = run_frozen_validation_runner_m47(
        _request(m45_path, m46_path),
        app_config=load_app_config(),
        current_time=_inside_window,
        repo_root=repo_root,
        process_launcher=_launcher,
    )

    assert result.packet.runner_status == "unavailable"
    assert "duplicate_active_runner_detected" in result.blockers


def test_m47_detects_old_test_schedule_active(tmp_path: Path) -> None:
    repo_root = _prepare_repo_root(tmp_path)
    m45_path = _write_m45_packet(repo_root, old_test_schedules_active=True)
    m46_path = _write_m46_packet(repo_root)

    result = run_frozen_validation_runner_m47(
        _request(m45_path, m46_path),
        app_config=load_app_config(),
        current_time=_inside_window,
        repo_root=repo_root,
        process_launcher=_launcher,
    )

    assert result.packet.old_test_schedules_active is True
    assert "old_test_schedules_active" in result.blockers


def test_m47_verifies_broker_read_only_baseline_before_activation(tmp_path: Path) -> None:
    repo_root = _prepare_repo_root(tmp_path)
    m45_path = _write_m45_packet(repo_root)
    m46_path = _write_m46_packet(repo_root)

    result = run_frozen_validation_runner_m47(
        _request(m45_path, m46_path, mode="real-paper"),
        environ=_paper_env(),
        app_config=load_app_config(),
        client_factory=_client_factory(_OpenOrderBrokerClient()),
        current_time=_inside_window,
        repo_root=repo_root,
        process_launcher=_launcher,
    )

    assert result.packet.pre_activation_broker_state.open_orders_count == 1
    assert "broker_reconciliation_not_clean" in result.blockers


def test_m47_verifies_tiingo_status_with_fake_client(tmp_path: Path) -> None:
    repo_root = _prepare_repo_root(tmp_path)
    m45_path = _write_m45_packet(repo_root)
    m46_path = _write_m46_packet(repo_root)

    result = run_frozen_validation_runner_m47(
        _request(m45_path, m46_path),
        app_config=load_app_config(),
        current_time=_inside_window,
        repo_root=repo_root,
        process_launcher=_launcher,
    )

    assert result.packet.market_data_status.provider == "tiingo"
    assert result.packet.market_data_status.latest_check_result == "verified"


def test_m47_detects_frozen_config_hash_drift(tmp_path: Path) -> None:
    repo_root = _prepare_repo_root(tmp_path)
    hashes = dict(_frozen_hashes(repo_root).model_dump())
    hashes["config_hash"] = "not-the-start-hash"
    m45_path = _write_m45_packet(repo_root, hashes=hashes)
    m46_path = _write_m46_packet(repo_root)

    result = run_frozen_validation_runner_m47(
        _request(m45_path, m46_path),
        app_config=load_app_config(),
        current_time=_inside_window,
        repo_root=repo_root,
        process_launcher=_launcher,
    )

    assert result.packet.frozen_policy_drift_detected is True
    assert "frozen_policy_hash_drift_detected" in result.blockers


def test_m47_cycle_refuses_outside_validation_window(tmp_path: Path) -> None:
    repo_root = _prepare_repo_root(tmp_path)
    m45_path = _write_m45_packet(repo_root)

    result = run_frozen_validation_cycle_once(
        _cycle_request(m45_path),
        app_config=load_app_config(),
        current_time=_outside_window,
        repo_root=repo_root,
        write_evidence=False,
    )

    assert result.packet.cycle_result == "refused"
    assert "validation_window_not_active" in result.packet.blockers


def test_m47_cycle_refuses_when_tiingo_gate_fails(tmp_path: Path) -> None:
    repo_root = _prepare_repo_root(tmp_path)
    m45_path = _write_m45_packet(repo_root)

    result = run_frozen_validation_cycle_once(
        _cycle_request(m45_path, mode="real-paper"),
        environ={"TIINGO_API_KEY": ""},
        app_config=load_app_config(),
        current_time=_due_window,
        repo_root=repo_root,
        write_evidence=False,
    )

    assert result.packet.cycle_result == "refused"
    assert "tiingo_data_check_not_verified" in result.packet.blockers


def test_m47_cycle_refuses_when_broker_reconciliation_fails(tmp_path: Path) -> None:
    repo_root = _prepare_repo_root(tmp_path)
    m45_path = _write_m45_packet(repo_root)

    result = run_frozen_validation_cycle_once(
        _cycle_request(m45_path, mode="real-paper"),
        environ=_paper_env(),
        app_config=load_app_config(),
        client_factory=_client_factory(_OpenOrderBrokerClient()),
        current_time=_due_window,
        repo_root=repo_root,
        write_evidence=False,
    )

    assert result.packet.cycle_result == "refused"
    assert "broker_reconciliation_not_clean" in result.packet.blockers


def test_m47_due_cycle_produces_no_trade_evidence_without_forcing_trade(tmp_path: Path) -> None:
    repo_root = _prepare_repo_root(tmp_path)
    m45_path = _write_m45_packet(repo_root)
    m46_path = _write_m46_packet(repo_root)

    result = run_frozen_validation_runner_m47(
        _request(m45_path, m46_path),
        app_config=load_app_config(),
        current_time=_due_window,
        repo_root=repo_root,
        process_launcher=_launcher,
    )

    assert result.packet.due_cycle_detected is True
    assert result.packet.cycle_ran_in_m47 is True
    assert result.packet.cycle_result == "no_trade"
    assert result.packet.broker_writes_performed_in_m47 is False
    assert result.packet.reporting_status.cycle_packet_generated is True


def test_m47_evidence_contains_required_fields_and_excludes_secrets(tmp_path: Path) -> None:
    repo_root = _prepare_repo_root(tmp_path)
    m45_path = _write_m45_packet(repo_root)
    m46_path = _write_m46_packet(repo_root)

    result = run_frozen_validation_runner_m47(
        _request(m45_path, m46_path),
        environ={
            "ALPACA_API_KEY": "secret-key-value",
            "ALPACA_SECRET_KEY": "secret-secret-value",
            "TIINGO_API_KEY": "secret-tiingo-value",
        },
        app_config=load_app_config(),
        current_time=_inside_window,
        repo_root=repo_root,
        process_launcher=_launcher,
    )
    output = write_frozen_validation_runner_m47_artifact(result, tmp_path / "m47.json")
    payload = json.loads(output.read_text(encoding="utf-8"))
    required = {
        "packet_id",
        "timestamp",
        "latest_spec_path",
        "latest_spec_version",
        "m45_evidence_reference",
        "m46_evidence_reference",
        "validation_status",
        "validation_start_timestamp_utc",
        "validation_target_end_timestamp_utc",
        "current_time_utc",
        "validation_day_index",
        "validation_window_active",
        "pre_activation_broker_state",
        "market_data_status",
        "runner_path_selected",
        "runner_status",
        "schedule_or_runner_id",
        "runner_command",
        "old_test_schedules_active",
        "temporal_cloud_schedule_created",
        "due_cycle_detected",
        "cycle_ran_in_m47",
        "broker_writes_performed_in_m47",
        "broker_writes_reason",
        "post_activation_broker_state",
        "reporting_status",
        "live_trading_enabled",
        "autonomous_live_execution_enabled",
        "leverage_enabled",
        "live_shorting_enabled",
        "ai_broker_authority",
        "level4_ready",
        "frozen_policy_drift_detected",
        "m47_result",
        "blockers",
    }

    text = output.read_text(encoding="utf-8")
    assert required <= set(payload)
    assert "secret-key-value" not in text
    assert "secret-secret-value" not in text
    assert "secret-tiingo-value" not in text


def test_m47_does_not_enable_live_autonomy_leverage_or_level4(tmp_path: Path) -> None:
    repo_root = _prepare_repo_root(tmp_path)
    m45_path = _write_m45_packet(repo_root)
    m46_path = _write_m46_packet(repo_root)

    result = run_frozen_validation_runner_m47(
        _request(m45_path, m46_path),
        app_config=load_app_config(),
        current_time=_inside_window,
        repo_root=repo_root,
        process_launcher=_launcher,
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
            "timestamp": "2026-05-18T17:30:00Z",
            "next_open": "2026-05-19T13:30:00Z",
            "next_close": "2026-05-18T20:00:00Z",
        }

    def list_open_orders(self) -> tuple[Mapping[str, Any], ...]:
        return (
            {
                "id": "broker-order-1",
                "client_order_id": "m47-test-order",
                "symbol": "SPY",
                "side": "buy",
                "asset_class": "us_equity",
                "qty": "1",
                "filled_qty": "0",
                "type": "limit",
                "time_in_force": "day",
                "status": "new",
                "limit_price": "100",
                "submitted_at": "2026-05-18T17:30:00Z",
            },
        )

    def list_positions(self) -> tuple[Mapping[str, Any], ...]:
        return ()
