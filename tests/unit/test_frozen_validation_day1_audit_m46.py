from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, cast

from packages.broker.alpaca import AlpacaPaperCredentials
from packages.core.config import load_app_config
from packages.paper.day1_audit import (
    FrozenValidationDay1AuditRequest,
    M46BrokerReadOnlyClient,
    SchedulerObservation,
    run_frozen_validation_day1_audit_m46,
    write_frozen_validation_day1_audit_m46_artifact,
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


def _outside_window() -> datetime:
    return datetime(2026, 7, 14, 17, 30, tzinfo=UTC)


def _request(
    m45_path: str,
    *,
    mode: str = "fake",
) -> FrozenValidationDay1AuditRequest:
    return FrozenValidationDay1AuditRequest(
        mode=mode,  # type: ignore[arg-type]
        m45_evidence_path=m45_path,
        confirm_paper_only=True,
        confirm_no_live_trading=True,
        confirm_no_autonomous_live=True,
        confirm_no_leverage=True,
        confirm_no_level4=True,
        confirm_no_forced_trades=True,
    )


def _active_runner() -> SchedulerObservation:
    return SchedulerObservation(
        local_runner_active=True,
        local_runner_command="uv run python scripts/run_frozen_validation_cycle.py",
        temporal_cloud_schedule_detected=False,
    )


def _registry_only() -> SchedulerObservation:
    return SchedulerObservation(temporal_cloud_schedule_detected=False)


def _write_m45_packet(
    tmp_path: Path,
    *,
    validation_status: str = "active",
    start: datetime | None = None,
    end: datetime | None = None,
    schedule_status: str = "active_local_paper_validation_registry",
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
        "frozen_hashes": dict(hashes or _frozen_hashes(Path.cwd()).model_dump()),
        "schedule": {
            "schedule_final_state": schedule_status,
            "schedule_id_or_name": LOCAL_SCHEDULE_ID,
            "old_test_schedules_active": False,
            "temporal_cloud_schedule_created": False,
        },
    }
    path = tmp_path / "m45.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_m46_refuses_if_m45_evidence_missing(tmp_path: Path) -> None:
    result = run_frozen_validation_day1_audit_m46(
        _request(str(tmp_path / "missing.json")),
        app_config=load_app_config(),
        scheduler_observation=_active_runner(),
        current_time=_inside_window,
    )

    assert result.packet.m46_result == "NO_GO"
    assert "m45_evidence_missing" in result.blockers


def test_m46_refuses_if_m45_validation_status_is_not_active(tmp_path: Path) -> None:
    m45_path = _write_m45_packet(tmp_path, validation_status="not_started")

    result = run_frozen_validation_day1_audit_m46(
        _request(str(m45_path)),
        app_config=load_app_config(),
        scheduler_observation=_active_runner(),
        current_time=_inside_window,
    )

    assert result.packet.validation_status == "not_started"
    assert "m45_validation_not_active" in result.blockers


def test_m46_detects_validation_clock_inside_active_window(tmp_path: Path) -> None:
    m45_path = _write_m45_packet(tmp_path)

    result = run_frozen_validation_day1_audit_m46(
        _request(str(m45_path)),
        app_config=load_app_config(),
        scheduler_observation=_active_runner(),
        current_time=_inside_window,
    )

    assert result.packet.validation_window_active is True
    assert result.packet.validation_day_index == 1
    assert "validation_window_not_active" not in result.blockers


def test_m46_detects_validation_clock_outside_active_window(tmp_path: Path) -> None:
    m45_path = _write_m45_packet(tmp_path)

    result = run_frozen_validation_day1_audit_m46(
        _request(str(m45_path)),
        app_config=load_app_config(),
        scheduler_observation=_active_runner(),
        current_time=_outside_window,
    )

    assert result.packet.validation_window_active is False
    assert result.packet.validation_day_index > 56
    assert "validation_window_not_active" in result.blockers


def test_m46_detects_active_local_registry(tmp_path: Path) -> None:
    m45_path = _write_m45_packet(tmp_path)

    result = run_frozen_validation_day1_audit_m46(
        _request(str(m45_path)),
        app_config=load_app_config(),
        scheduler_observation=_active_runner(),
        current_time=_inside_window,
    )

    assert result.packet.schedule_registry_status == "active_local_paper_validation_registry"
    assert result.packet.schedule_id_or_name == LOCAL_SCHEDULE_ID
    assert "schedule_registry_not_active" not in result.blockers


def test_m46_distinguishes_registry_only_from_active_runner(tmp_path: Path) -> None:
    m45_path = _write_m45_packet(tmp_path)

    registry_only = run_frozen_validation_day1_audit_m46(
        _request(str(m45_path)),
        app_config=load_app_config(),
        scheduler_observation=_registry_only(),
        current_time=_inside_window,
    )
    active_runner = run_frozen_validation_day1_audit_m46(
        _request(str(m45_path)),
        app_config=load_app_config(),
        scheduler_observation=_active_runner(),
        current_time=_inside_window,
    )

    assert registry_only.packet.scheduler_execution_status == "active_registry_only_no_runner"
    assert active_runner.packet.scheduler_execution_status == "active_local_runner_confirmed"


def test_m46_returns_no_go_if_registry_exists_but_no_runner_exists(tmp_path: Path) -> None:
    m45_path = _write_m45_packet(tmp_path)

    result = run_frozen_validation_day1_audit_m46(
        _request(str(m45_path)),
        app_config=load_app_config(),
        scheduler_observation=_registry_only(),
        current_time=_inside_window,
    )

    assert result.packet.m46_result == "NO_GO"
    assert "local_registry_has_no_active_runner" in result.blockers


def test_m46_accepts_active_local_runner_when_configured(tmp_path: Path) -> None:
    m45_path = _write_m45_packet(tmp_path)

    result = run_frozen_validation_day1_audit_m46(
        _request(str(m45_path)),
        app_config=load_app_config(),
        scheduler_observation=_active_runner(),
        current_time=_inside_window,
    )

    assert result.packet.m46_result == "GO"
    assert result.packet.runner_command == "uv run python scripts/run_frozen_validation_cycle.py"


def test_m46_detects_old_test_schedule_active(tmp_path: Path) -> None:
    m45_path = _write_m45_packet(tmp_path)
    observation = SchedulerObservation(
        local_runner_active=True,
        local_runner_command="uv run python scripts/run_frozen_validation_cycle.py",
        old_test_schedules_active=True,
        temporal_cloud_schedule_detected=False,
    )

    result = run_frozen_validation_day1_audit_m46(
        _request(str(m45_path)),
        app_config=load_app_config(),
        scheduler_observation=observation,
        current_time=_inside_window,
    )

    assert result.packet.old_test_schedules_active is True
    assert "old_test_schedules_active" in result.blockers


def test_m46_detects_unexpected_temporal_schedule_if_visible(tmp_path: Path) -> None:
    m45_path = _write_m45_packet(tmp_path)
    observation = SchedulerObservation(
        local_runner_active=True,
        local_runner_command="uv run python scripts/run_frozen_validation_cycle.py",
        temporal_cloud_schedule_detected=True,
    )

    result = run_frozen_validation_day1_audit_m46(
        _request(str(m45_path)),
        app_config=load_app_config(),
        scheduler_observation=observation,
        current_time=_inside_window,
    )

    assert result.packet.temporal_cloud_schedule_detected is True
    assert "unexpected_temporal_cloud_schedule_detected" in result.blockers


def test_m46_verifies_broker_read_only_state_with_stub(tmp_path: Path) -> None:
    m45_path = _write_m45_packet(tmp_path)

    result = run_frozen_validation_day1_audit_m46(
        _request(str(m45_path), mode="real-paper"),
        environ=_paper_env(),
        app_config=load_app_config(),
        client_factory=_client_factory(_OpenOrderBrokerClient()),
        scheduler_observation=_active_runner(),
        current_time=_inside_window,
    )

    assert result.packet.broker_state.open_orders_count == 1
    assert result.packet.broker_state.reconciliation_summary == "non_flat_or_open_orders_present"
    assert "broker_state_not_flat_or_open_orders_present" in result.blockers


def test_m46_verifies_tiingo_read_only_status_using_fake_client(tmp_path: Path) -> None:
    m45_path = _write_m45_packet(tmp_path)

    result = run_frozen_validation_day1_audit_m46(
        _request(str(m45_path)),
        app_config=load_app_config(),
        scheduler_observation=_active_runner(),
        current_time=_inside_window,
    )

    assert result.packet.market_data_status.provider == "tiingo"
    assert result.packet.market_data_status.feed == "eod"
    assert result.packet.market_data_status.latest_check_result == "verified"
    assert result.packet.market_data_status.sample_symbols


def test_m46_evidence_contains_required_fields(tmp_path: Path) -> None:
    m45_path = _write_m45_packet(tmp_path)
    result = run_frozen_validation_day1_audit_m46(
        _request(str(m45_path)),
        app_config=load_app_config(),
        scheduler_observation=_active_runner(),
        current_time=_inside_window,
    )
    output = write_frozen_validation_day1_audit_m46_artifact(result, tmp_path / "m46.json")
    payload = json.loads(output.read_text(encoding="utf-8"))

    required = {
        "packet_id",
        "timestamp",
        "latest_spec_path",
        "latest_spec_version",
        "m45_evidence_reference",
        "validation_status",
        "validation_start_timestamp_utc",
        "validation_target_end_timestamp_utc",
        "current_time_utc",
        "validation_day_index",
        "validation_window_active",
        "schedule_registry_status",
        "scheduler_execution_status",
        "schedule_id_or_name",
        "old_test_schedules_active",
        "temporal_cloud_schedule_detected",
        "broker_state",
        "market_data_status",
        "reporting_status",
        "broker_writes_performed_in_m46",
        "scheduled_cycle_run_in_m46",
        "live_trading_enabled",
        "autonomous_live_execution_enabled",
        "leverage_enabled",
        "live_shorting_enabled",
        "ai_broker_authority",
        "level4_ready",
        "validation_integrity",
        "m46_result",
        "blockers",
    }
    assert required <= set(payload)


def test_m46_evidence_excludes_secret_values(tmp_path: Path) -> None:
    m45_path = _write_m45_packet(tmp_path)
    result = run_frozen_validation_day1_audit_m46(
        _request(str(m45_path)),
        environ={
            "ALPACA_API_KEY": "secret-key-value",
            "ALPACA_SECRET_KEY": "secret-secret-value",
            "TIINGO_API_KEY": "secret-tiingo-value",
        },
        app_config=load_app_config(),
        scheduler_observation=_active_runner(),
        current_time=_inside_window,
    )
    output = write_frozen_validation_day1_audit_m46_artifact(result, tmp_path / "m46.json")
    text = output.read_text(encoding="utf-8")

    assert "secret-key-value" not in text
    assert "secret-secret-value" not in text
    assert "secret-tiingo-value" not in text


def test_m46_detects_frozen_config_hash_drift(tmp_path: Path) -> None:
    hashes = dict(_frozen_hashes(Path.cwd()).model_dump())
    hashes["config_hash"] = "not-the-start-hash"
    m45_path = _write_m45_packet(tmp_path, hashes=hashes)

    result = run_frozen_validation_day1_audit_m46(
        _request(str(m45_path)),
        app_config=load_app_config(),
        scheduler_observation=_active_runner(),
        current_time=_inside_window,
    )

    assert result.packet.validation_integrity.config_hash_matches_start is False
    assert result.packet.validation_integrity.frozen_policy_drift_detected is True
    assert "frozen_config_hash_drift_detected" in result.blockers


def test_m46_default_audit_path_does_not_perform_broker_writes(tmp_path: Path) -> None:
    m45_path = _write_m45_packet(tmp_path)

    result = run_frozen_validation_day1_audit_m46(
        _request(str(m45_path)),
        app_config=load_app_config(),
        scheduler_observation=_active_runner(),
        current_time=_inside_window,
    )

    assert result.packet.broker_writes_performed_in_m46 is False
    assert result.broker_writes_performed is False
    assert result.packet.scheduled_cycle_run_in_m46 is False


def test_m46_does_not_enable_live_autonomy_or_leverage(tmp_path: Path) -> None:
    m45_path = _write_m45_packet(tmp_path)

    result = run_frozen_validation_day1_audit_m46(
        _request(str(m45_path)),
        app_config=load_app_config(),
        scheduler_observation=_active_runner(),
        current_time=_inside_window,
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
    }


def _client_factory(client: M46BrokerReadOnlyClient) -> M45ReadOnlyClientFactory:
    def factory(
        _credentials: AlpacaPaperCredentials,
        _timeout_seconds: float,
    ) -> M46BrokerReadOnlyClient:
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
                "client_order_id": "m46-test-order",
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
