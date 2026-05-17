from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from packages.core.config import MarketDataConfig, load_app_config
from packages.data.primary_signal_gate import (
    M44B_NON_IEX_DATA_GATE_WAIVER_APPROVAL,
    PrimarySignalDataGateRequest,
    build_frozen_readiness_m44b_packet,
    classify_primary_signal_feed,
    market_data_config_with_env_overrides,
    normalize_primary_signal_feed,
    run_primary_signal_data_gate,
    write_frozen_readiness_m44b_artifact,
    write_primary_signal_data_gate_artifact,
)

AS_OF = datetime(2026, 5, 17, 12, 0, tzinfo=UTC)


class _VerifiedDataClient:
    def latest_bars(self, *, symbols: Sequence[str], feed: str) -> Mapping[str, Any]:
        assert feed == "sip"
        return {"bars": {symbol: {"c": 100.0, "t": "2026-05-15T20:00:00Z"} for symbol in symbols}}


class _EmptyDataClient:
    def latest_bars(self, *, symbols: Sequence[str], feed: str) -> Mapping[str, Any]:
        return {"bars": {}}


def _verify_request(**updates: object) -> PrimarySignalDataGateRequest:
    data = {
        "mode": "verify",
        "provider": "alpaca",
        "feed": "sip",
        "symbols": ("SPY",),
        "confirm_read_only": True,
        "confirm_no_broker_writes": True,
        "confirm_no_schedules": True,
        "confirm_no_frozen_validation_start": True,
    }
    data.update(updates)
    return PrimarySignalDataGateRequest.model_validate(data)


def _waive_request(**updates: object) -> PrimarySignalDataGateRequest:
    data = {
        "mode": "waive",
        "operator_approval": M44B_NON_IEX_DATA_GATE_WAIVER_APPROVAL,
        "waiver_reason": "Operator accepts market-data limitations for operational validation.",
        "confirm_no_broker_writes": True,
        "confirm_no_schedules": True,
        "confirm_no_frozen_validation_start": True,
    }
    data.update(updates)
    return PrimarySignalDataGateRequest.model_validate(data)


def _flat_cleanup_packet(tmp_path: Path) -> Path:
    path = tmp_path / "flat_start_cleanup_m44.json"
    path.write_text(
        json.dumps(
            {
                "flat_start_cleanup": {
                    "final_open_orders_count": 0,
                    "final_positions_count": 0,
                    "final_reconciliation": "flat_zero_positions_zero_open_orders",
                    "m45_flat_start_ready": True,
                    "blockers": [],
                }
            }
        ),
        encoding="utf-8",
    )
    return path


def _m44_readiness_packet(tmp_path: Path) -> Path:
    path = tmp_path / "frozen_readiness_m44.json"
    path.write_text(json.dumps({"frozen_readiness": {"m45_readiness": False}}), encoding="utf-8")
    return path


def test_config_loader_supports_market_data_block() -> None:
    config = load_app_config()

    assert config.market_data.primary_signal_provider == "alpaca"
    assert config.market_data.primary_signal_feed == "sip"
    assert config.market_data.require_non_iex_primary_signal_data is True
    assert config.market_data.fail_if_primary_signal_feed_is_iex is True
    assert config.market_data.allow_iex_only_for_frozen_validation is False
    assert config.market_data.non_iex_primary_signal_data_waiver_enabled is False


def test_feed_normalization_and_classification_are_explicit() -> None:
    assert normalize_primary_signal_feed("SIP") == "sip"
    assert normalize_primary_signal_feed("sip-delayed") == "delayed_sip"
    assert classify_primary_signal_feed("sip") == "non_iex"
    assert classify_primary_signal_feed("iex") == "iex_only"
    assert classify_primary_signal_feed("delayed_sip") == "delayed_non_iex"
    assert classify_primary_signal_feed("delayed_sip", delayed_sip_allowed=True) == "non_iex"


def test_market_data_env_overrides_are_non_secret_and_typed() -> None:
    config = load_app_config().market_data
    overridden = market_data_config_with_env_overrides(
        config,
        {
            "MARKET_DATA_PRIMARY_PROVIDER": "alpaca",
            "MARKET_DATA_PRIMARY_FEED": "sip",
            "MARKET_DATA_REQUIRE_NON_IEX": "true",
            "MARKET_DATA_ALLOW_IEX_ONLY_FOR_FROZEN_VALIDATION": "false",
        },
    )

    assert overridden.primary_signal_provider == "alpaca"
    assert overridden.primary_signal_feed == "sip"
    assert overridden.require_non_iex_primary_signal_data is True


def test_verify_mode_marks_go_only_with_verified_sip_data_check() -> None:
    result = run_primary_signal_data_gate(
        _verify_request(),
        data_client=_VerifiedDataClient(),
        environ={},
        now=AS_OF,
    )

    assert result.go_no_go == "go"
    assert result.packet.non_iex_primary_signal_data_verified is True
    assert result.packet.data_check_performed is True
    assert result.packet.data_check_result == "verified"
    assert result.packet.broker_writes_performed is False


def test_verify_mode_remains_no_go_when_feed_is_iex() -> None:
    result = run_primary_signal_data_gate(
        _verify_request(feed="iex"),
        environ={"MARKET_DATA_PRIMARY_FEED": "iex"},
        now=AS_OF,
    )

    assert result.go_no_go == "no_go"
    assert result.packet.non_iex_primary_signal_data_verified is False
    assert "primary_signal_feed_is_iex" in result.blockers


def test_verify_mode_remains_no_go_when_sip_access_is_inconclusive() -> None:
    result = run_primary_signal_data_gate(
        _verify_request(),
        data_client=_EmptyDataClient(),
        environ={},
        now=AS_OF,
    )

    assert result.go_no_go == "no_go"
    assert result.packet.data_check_result == "inconclusive"
    assert "non_iex_primary_signal_data_not_verified" in result.blockers


def test_delayed_sip_does_not_silently_equal_realtime_sip() -> None:
    result = run_primary_signal_data_gate(
        _verify_request(feed="delayed_sip"),
        environ={"MARKET_DATA_PRIMARY_FEED": "delayed_sip"},
        now=AS_OF,
    )

    assert result.go_no_go == "no_go"
    assert "delayed_sip_not_allowed_for_frozen_validation" in result.blockers


def test_waiver_mode_refuses_without_marker() -> None:
    result = run_primary_signal_data_gate(
        _waive_request(operator_approval=None),
        environ={},
        now=AS_OF,
    )

    assert result.go_no_go == "no_go"
    assert result.packet.non_iex_primary_signal_data_waived is False
    assert "waiver_approval_missing" in result.blockers


def test_waiver_mode_records_limitation_and_can_make_operational_readiness_go() -> None:
    result = run_primary_signal_data_gate(_waive_request(), environ={}, now=AS_OF)

    assert result.go_no_go == "go"
    assert result.packet.non_iex_primary_signal_data_verified is False
    assert result.packet.non_iex_primary_signal_data_waived is True
    assert result.packet.validation_limitation is not None
    assert result.packet.m45_readiness_impact == "go"


def test_evidence_packets_contain_required_fields_and_exclude_secrets(tmp_path: Path) -> None:
    gate = run_primary_signal_data_gate(
        _verify_request(),
        data_client=_VerifiedDataClient(),
        environ={},
        now=AS_OF,
    )
    gate_path = write_primary_signal_data_gate_artifact(gate, tmp_path / "gate.json")
    readiness = build_frozen_readiness_m44b_packet(
        gate.packet,
        flat_cleanup_packet_path=str(_flat_cleanup_packet(tmp_path)),
        m44_readiness_packet_path=str(_m44_readiness_packet(tmp_path)),
        gate_packet_path=str(gate_path),
        now=AS_OF,
    )
    readiness_path = write_frozen_readiness_m44b_artifact(
        readiness,
        tmp_path / "readiness.json",
    )

    gate_payload = json.loads(gate_path.read_text())
    readiness_payload = json.loads(readiness_path.read_text())
    assert gate_payload["primary_signal_data_gate"]["latest_spec_version"] == "v0.5"
    assert gate_payload["primary_signal_data_gate"]["broker_writes_performed"] is False
    assert readiness_payload["frozen_readiness_m44b"]["m45_readiness"] is True
    assert readiness_payload["frozen_readiness_m44b"][
        "m44b_primary_signal_data_gate_packet_reference"
    ] == str(gate_path)
    combined = gate_path.read_text() + readiness_path.read_text()
    assert "ALPACA_API_KEY" not in combined
    assert "ALPACA_SECRET_KEY" not in combined
    assert "DATABASE_URL" not in combined


def test_refreshed_readiness_remains_false_if_gate_not_satisfied(tmp_path: Path) -> None:
    gate = run_primary_signal_data_gate(
        _verify_request(),
        data_client=_EmptyDataClient(),
        environ={},
        now=AS_OF,
    )
    readiness = build_frozen_readiness_m44b_packet(
        gate.packet,
        flat_cleanup_packet_path=str(_flat_cleanup_packet(tmp_path)),
        m44_readiness_packet_path=str(_m44_readiness_packet(tmp_path)),
        gate_packet_path="docs/evidence/primary_signal_data_gate_m44b.json",
        now=AS_OF,
    )

    assert readiness.go_no_go == "no_go"
    assert readiness.packet.m45_readiness is False
    assert "primary_signal_data_gate_not_satisfied" in readiness.blockers


def test_config_rejects_iex_marked_verified() -> None:
    config = load_app_config().market_data.model_dump() | {
        "primary_signal_feed": "iex",
        "non_iex_primary_signal_data_verified": True,
    }

    with pytest.raises(ValueError, match="IEX-only feed cannot be marked"):
        MarketDataConfig.model_validate(config)
