from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, cast

from packages.broker.alpaca import AlpacaPaperCredentials
from packages.core.config import load_app_config
from packages.paper.validation_start import (
    EXPECTED_LONG_UNIVERSE,
    EXPECTED_SHORT_UNIVERSE,
    M45_APPROVAL,
    FakeM45ReadOnlyClient,
    FrozenPaperValidationStartRequest,
    M45ReadOnlyClient,
    M45ReadOnlyClientFactory,
    run_frozen_paper_validation_start_m45,
    write_frozen_paper_validation_start_m45_artifact,
)


def _approved_request(mode: str = "fake") -> FrozenPaperValidationStartRequest:
    return FrozenPaperValidationStartRequest(
        mode=mode,  # type: ignore[arg-type]
        operator_approval=M45_APPROVAL,
        confirm_paper_only=True,
        confirm_flat_baseline=True,
        confirm_tiingo_eod_primary_signal_data=True,
        confirm_paper_shorts_enabled=True,
        confirm_live_shorting_disabled=True,
        confirm_long_scale_ins_enabled=True,
        confirm_short_scale_ins_disabled=True,
        confirm_no_live_trading=True,
        confirm_no_autonomous_live=True,
        confirm_no_leverage=True,
        confirm_ai_negative_only=True,
        confirm_no_forced_trades=True,
        confirm_level4_not_ready=True,
    )


def _paper_env() -> dict[str, str]:
    return {
        "ALPACA_API_KEY": "paper-key",
        "ALPACA_SECRET_KEY": "paper-secret",
        "ALPACA_BASE_URL": "https://paper-api.alpaca.markets",
    }


def _fixed_now() -> datetime:
    return datetime(2026, 5, 18, 14, 30, tzinfo=UTC)


def _order(symbol: str = "SPY") -> Mapping[str, Any]:
    return {
        "id": "order-1",
        "client_order_id": "m45-test-order",
        "symbol": symbol,
        "side": "buy",
        "asset_class": "us_equity",
        "qty": "1",
        "filled_qty": "0",
        "type": "limit",
        "time_in_force": "day",
        "status": "new",
        "limit_price": "100",
        "submitted_at": "2026-05-18T14:30:00Z",
        "updated_at": "2026-05-18T14:30:00Z",
    }


def _position(symbol: str = "SPY") -> Mapping[str, Any]:
    return {
        "symbol": symbol,
        "asset_class": "us_equity",
        "qty": "1",
        "avg_entry_price": "100",
        "market_value": "100",
        "opened_at": "2026-05-18T14:30:00Z",
    }


def _client_factory(client: M45ReadOnlyClient) -> M45ReadOnlyClientFactory:
    def factory(
        _credentials: AlpacaPaperCredentials,
        _timeout_seconds: float,
    ) -> M45ReadOnlyClient:
        return client

    return cast(M45ReadOnlyClientFactory, factory)


def test_m45_refuses_without_operator_approval_marker() -> None:
    request = _approved_request().model_copy(update={"operator_approval": None})

    result = run_frozen_paper_validation_start_m45(
        request,
        environ={},
        current_time=_fixed_now,
    )

    assert result.success is False
    assert "m45_operator_approval_marker_required" in result.blockers
    assert result.packet.validation_status == "not_started"
    assert result.broker_writes_performed is False


def test_m45_fake_happy_path_starts_validation_and_local_schedule() -> None:
    result = run_frozen_paper_validation_start_m45(
        _approved_request(),
        environ={},
        current_time=_fixed_now,
    )

    assert result.success is True
    assert result.packet.validation_start_result == "GO"
    assert result.packet.validation_status == "active"
    assert result.packet.validation_start_timestamp_utc == _fixed_now()
    assert result.packet.validation_end_target_timestamp_utc == _fixed_now() + timedelta(days=56)
    assert result.packet.schedule.schedule_created_or_activated is True
    assert result.packet.schedule.activation_type == "local_registry"
    assert result.packet.schedule.temporal_cloud_schedule_created is False
    assert result.packet.broker_writes_performed is False


def test_m45_refuses_if_latest_spec_is_not_v0_6(tmp_path: Path) -> None:
    spec_dir = tmp_path / "docs/app"
    spec_dir.mkdir(parents=True)
    (spec_dir / "Autonomous_AI_Trading_Bot_SPEC_v0.5.md").write_text("v0.5\n", encoding="utf-8")

    result = run_frozen_paper_validation_start_m45(
        _approved_request(),
        environ={},
        app_config=load_app_config(),
        current_time=_fixed_now,
        repo_root=tmp_path,
    )

    assert result.success is False
    assert "latest_spec_not_v0_6" in result.blockers


def test_m45_refuses_if_m44c_tiingo_gate_missing(tmp_path: Path) -> None:
    result = run_frozen_paper_validation_start_m45(
        _approved_request(),
        environ={},
        app_config=load_app_config(),
        current_time=_fixed_now,
        repo_root=tmp_path,
    )

    assert result.success is False
    assert "m44c_tiingo_gate_missing_or_not_go" in result.blockers


def test_m45_refuses_if_m44d_short_proof_missing() -> None:
    result = run_frozen_paper_validation_start_m45(
        _approved_request(),
        environ={},
        current_time=_fixed_now,
        repo_root=Path("/tmp/missing-m44d-evidence"),
        app_config=load_app_config(),
    )

    assert result.success is False
    assert "m44d_short_proof_missing_or_not_go" in result.blockers


def test_m45_refuses_if_m44e_scale_in_proof_missing() -> None:
    result = run_frozen_paper_validation_start_m45(
        _approved_request(),
        environ={},
        current_time=_fixed_now,
        repo_root=Path("/tmp/missing-m44e-evidence"),
        app_config=load_app_config(),
    )

    assert result.success is False
    assert "m44e_scale_in_proof_missing_or_not_go" in result.blockers


def test_m45_refuses_if_broker_baseline_has_open_orders() -> None:
    result = run_frozen_paper_validation_start_m45(
        _approved_request(mode="real-paper"),
        environ=_paper_env(),
        current_time=_fixed_now,
        client_factory=_client_factory(FakeM45ReadOnlyClient(orders=(_order(),))),
    )

    assert result.success is False
    assert "current_broker_open_orders_not_zero" in result.blockers


def test_m45_refuses_if_broker_baseline_has_positions() -> None:
    result = run_frozen_paper_validation_start_m45(
        _approved_request(mode="real-paper"),
        environ=_paper_env(),
        current_time=_fixed_now,
        client_factory=_client_factory(FakeM45ReadOnlyClient(positions=(_position(),))),
    )

    assert result.success is False
    assert "current_broker_positions_not_zero" in result.blockers


def test_m45_refuses_if_paper_shorts_not_enabled() -> None:
    config = load_app_config()
    short_policy = config.validation.short_policy.model_copy(
        update={"enabled_at_validation_start": False}
    )
    validation = config.validation.model_copy(update={"short_policy": short_policy})
    bad_config = config.model_copy(update={"validation": validation})

    result = run_frozen_paper_validation_start_m45(
        _approved_request(),
        environ={},
        app_config=bad_config,
        current_time=_fixed_now,
    )

    assert result.success is False
    assert "paper_shorts_not_enabled_at_validation_start" in result.blockers


def test_m45_refuses_if_live_shorting_enabled() -> None:
    config = load_app_config()
    short_policy = config.validation.short_policy.model_copy(update={"live_shorting_enabled": True})
    validation = config.validation.model_copy(update={"short_policy": short_policy})
    bad_config = config.model_copy(update={"validation": validation})

    result = run_frozen_paper_validation_start_m45(
        _approved_request(),
        environ={},
        app_config=bad_config,
        current_time=_fixed_now,
    )

    assert result.success is False
    assert "live_shorting_enabled" in result.blockers


def test_m45_refuses_if_long_scale_ins_not_enabled() -> None:
    config = load_app_config()
    scale_policy = config.validation.scale_in_policy.model_copy(
        update={"enabled_at_validation_start": False}
    )
    validation = config.validation.model_copy(update={"scale_in_policy": scale_policy})
    bad_config = config.model_copy(update={"validation": validation})

    result = run_frozen_paper_validation_start_m45(
        _approved_request(),
        environ={},
        app_config=bad_config,
        current_time=_fixed_now,
    )

    assert result.success is False
    assert "long_scale_ins_not_enabled_at_validation_start" in result.blockers


def test_m45_refuses_if_short_scale_ins_enabled() -> None:
    config = load_app_config()
    scale_policy = config.validation.scale_in_policy.model_copy(
        update={"short_scale_in_enabled_at_validation_start": True}
    )
    validation = config.validation.model_copy(update={"scale_in_policy": scale_policy})
    bad_config = config.model_copy(update={"validation": validation})

    result = run_frozen_paper_validation_start_m45(
        _approved_request(),
        environ={},
        app_config=bad_config,
        current_time=_fixed_now,
    )

    assert result.success is False
    assert "short_scale_ins_enabled_at_validation_start" in result.blockers


def test_m45_refuses_if_ai_not_negative_only() -> None:
    config = load_app_config()
    ai_policy = config.validation.ai_policy.model_copy(update={"negative_only": False})
    validation = config.validation.model_copy(update={"ai_policy": ai_policy})
    bad_config = config.model_copy(update={"validation": validation})

    result = run_frozen_paper_validation_start_m45(
        _approved_request(),
        environ={},
        app_config=bad_config,
        current_time=_fixed_now,
    )

    assert result.success is False
    assert "ai_not_negative_only" in result.blockers


def test_m45_refuses_if_live_trading_enabled() -> None:
    config = load_app_config()
    system = config.system.model_copy(update={"live_trading_enabled": True})
    bad_config = config.model_copy(update={"system": system})

    result = run_frozen_paper_validation_start_m45(
        _approved_request(),
        environ={},
        app_config=bad_config,
        current_time=_fixed_now,
    )

    assert result.success is False
    assert "live_trading_enabled" in result.blockers


def test_m45_refuses_if_autonomous_live_execution_enabled() -> None:
    config = load_app_config()
    system = config.system.model_copy(update={"autonomous_execution_enabled": True})
    bad_config = config.model_copy(update={"system": system})

    result = run_frozen_paper_validation_start_m45(
        _approved_request(),
        environ={},
        app_config=bad_config,
        current_time=_fixed_now,
    )

    assert result.success is False
    assert "autonomous_live_execution_enabled" in result.blockers


def test_m45_refuses_if_leverage_enabled() -> None:
    config = load_app_config()
    risk = config.risk_level_4_micro_live.model_copy(update={"allow_margin": True})
    bad_config = config.model_copy(update={"risk_level_4_micro_live": risk})

    result = run_frozen_paper_validation_start_m45(
        _approved_request(),
        environ={},
        app_config=bad_config,
        current_time=_fixed_now,
    )

    assert result.success is False
    assert "leverage_or_margin_enabled" in result.blockers


def test_m45_refuses_if_forced_trades_enabled() -> None:
    config = load_app_config()
    universe = config.validation.universe.model_copy(update={"force_trades": True})
    validation = config.validation.model_copy(update={"universe": universe})
    bad_config = config.model_copy(update={"validation": validation})

    result = run_frozen_paper_validation_start_m45(
        _approved_request(),
        environ={},
        app_config=bad_config,
        current_time=_fixed_now,
    )

    assert result.success is False
    assert "forced_trades_enabled" in result.blockers


def test_m45_computes_frozen_hashes_and_universes() -> None:
    result = run_frozen_paper_validation_start_m45(
        _approved_request(),
        environ={},
        current_time=_fixed_now,
    )

    hashes = result.packet.frozen_hashes.model_dump()
    assert all(isinstance(value, str) and len(value) == 64 for value in hashes.values())
    assert result.packet.short_readiness.eligible_symbols == EXPECTED_SHORT_UNIVERSE
    assert load_app_config().live_universe.symbols == EXPECTED_LONG_UNIVERSE


def test_m45_evidence_packet_contains_required_fields_and_excludes_secrets(tmp_path: Path) -> None:
    result = run_frozen_paper_validation_start_m45(
        _approved_request(),
        environ={},
        current_time=_fixed_now,
    )
    output = write_frozen_paper_validation_start_m45_artifact(result, tmp_path / "m45.json")
    payload = json.loads(output.read_text(encoding="utf-8"))
    required = {
        "packet_id",
        "timestamp",
        "operator_approval_marker",
        "latest_spec_path",
        "latest_spec_version",
        "validation_start_result",
        "validation_status",
        "validation_start_timestamp_utc",
        "validation_end_target_timestamp_utc",
        "references",
        "current_broker_baseline",
        "current_market_data_gate",
        "short_readiness",
        "scale_in_readiness",
        "frozen_hashes",
        "frozen_policy",
        "schedule",
        "blockers",
        "level4_ready",
    }

    assert required.issubset(payload)
    serialized = output.read_text(encoding="utf-8")
    assert "paper-secret" not in serialized
    assert "ALPACA_SECRET_KEY" not in serialized
    assert "TIINGO_API_KEY" not in serialized
