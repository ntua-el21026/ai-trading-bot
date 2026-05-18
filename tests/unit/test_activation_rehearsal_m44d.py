from __future__ import annotations

import json
from pathlib import Path
from typing import cast

from packages.broker.alpaca import AlpacaPaperCredentials
from packages.core.config import AppConfig, load_app_config
from packages.paper.activation_rehearsal import (
    ACTIVATION_REHEARSAL_M44D_EVIDENCE_PATH,
    FROZEN_READINESS_M44D_EVIDENCE_PATH,
    M44D_APPROVAL,
    ActivationRehearsalClient,
    ActivationRehearsalClientFactory,
    ActivationRehearsalRequest,
    FakeActivationRehearsalClient,
    build_frozen_readiness_m44d_packet,
    run_activation_rehearsal_m44d,
    write_activation_rehearsal_m44d_artifacts,
)


def _approved_request(mode: str = "fake") -> ActivationRehearsalRequest:
    return ActivationRehearsalRequest(
        mode=mode,  # type: ignore[arg-type]
        rehearsal_mode="full",
        operator_approval=M44D_APPROVAL,
        confirm_paper_endpoint=True,
        confirm_short_rehearsal_only=True,
        confirm_scale_in_rehearsal_only=True,
        confirm_protective_buy_stop_required=True,
        confirm_additive_sell_stop_required=True,
        confirm_cleanup_to_flat=True,
        confirm_no_live_trading=True,
        confirm_no_autonomous_live=True,
        confirm_no_schedules=True,
        confirm_no_leverage=True,
        confirm_no_frozen_validation_start=True,
        confirm_level4_not_ready=True,
    )


def _paper_env() -> dict[str, str]:
    return {
        "ALPACA_API_KEY": "paper-key",
        "ALPACA_SECRET_KEY": "paper-secret",
        "ALPACA_BASE_URL": "https://paper-api.alpaca.markets",
    }


def test_v0_6_long_short_scale_in_config_loads() -> None:
    config = load_app_config()

    assert config.validation.active_spec_version == "v0.6"
    assert config.validation.short_policy.enabled_at_validation_start is True
    assert config.validation.short_policy.live_shorting_enabled is False
    assert config.validation.scale_in_policy.enabled_at_validation_start is False
    assert config.validation.scale_in_policy.real_additive_stop_proof_completed_by_m44d is False
    assert config.validation.scale_in_policy.short_scale_in_enabled_at_validation_start is False
    assert config.shorts.eligible_symbols == ("SPY", "QQQ", "DIA", "IWM")
    assert config.validation_risk.max_scale_ins_per_day_at_start == 0


def test_m44d_refuses_without_approval_marker() -> None:
    request = _approved_request()
    request = request.model_copy(update={"operator_approval": None})

    result = run_activation_rehearsal_m44d(request, environ={})

    assert result.success is False
    assert "m44d_approval_marker_required" in result.blockers
    assert result.broker_writes_performed is False


def test_m44d_refuses_non_approved_symbols() -> None:
    try:
        ActivationRehearsalRequest(
            mode="fake",
            rehearsal_mode="full",
            operator_approval=M44D_APPROVAL,
            short_primary_symbol="QQQ",
            short_fallback_symbol="SPY",
        )
    except ValueError as exc:
        assert "M44D short rehearsal candidates" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("invalid M44D symbols were accepted")


def test_m44d_fake_full_rehearsal_succeeds_and_restores_flat_baseline() -> None:
    result = run_activation_rehearsal_m44d(_approved_request(), environ={})

    assert result.success is False
    assert result.packet.short_rehearsal.succeeded is True
    assert result.packet.scale_in_rehearsal.succeeded is True
    assert result.packet.short_rehearsal.selected_symbol == "IWM"
    assert result.packet.scale_in_rehearsal.selected_symbol == "XLK"
    assert result.packet.short_rehearsal.short_order_request_summary is not None
    assert result.packet.short_rehearsal.short_order_request_summary.side == "sell"
    assert result.packet.short_rehearsal.protective_buy_stop_request_summary is not None
    assert result.packet.short_rehearsal.protective_buy_stop_request_summary.side == "buy"
    assert result.packet.scale_in_rehearsal.initial_entry_request_summary is not None
    assert result.packet.scale_in_rehearsal.initial_entry_request_summary.side == "buy"
    assert result.packet.scale_in_rehearsal.scale_in_entry_request_summary is not None
    assert result.packet.scale_in_rehearsal.scale_in_entry_request_summary.side == "buy"
    assert result.packet.scale_in_rehearsal.aggregate_long_protection_check is not None
    assert result.packet.final_broker_baseline.open_orders_count == 0
    assert result.packet.final_broker_baseline.positions_count == 0
    assert result.packet.m45_long_short_scalein_readiness is False
    assert "real_m44d_rehearsals_not_performed" in result.blockers
    assert result.real_broker_writes_performed is False


def test_m44d_real_paper_mode_with_stubbed_client_can_make_readiness_go() -> None:
    client = FakeActivationRehearsalClient()

    def factory(
        _credentials: AlpacaPaperCredentials,
        _timeout_seconds: float,
    ) -> ActivationRehearsalClient:
        return client

    result = run_activation_rehearsal_m44d(
        _approved_request(mode="real-paper"),
        environ=_paper_env(),
        app_config=_scale_in_proof_config(),
        client_factory=cast(ActivationRehearsalClientFactory, factory),
    )

    assert result.success is True
    assert result.packet.m45_long_short_scalein_readiness is True
    assert result.real_broker_writes_performed is True


def test_m44d_rejects_non_shortable_asset() -> None:
    client = FakeActivationRehearsalClient(
        assets={
            "IWM": {
                "symbol": "IWM",
                "asset_class": "us_equity_etf",
                "tradable": True,
                "marginable": True,
                "shortable": False,
                "easy_to_borrow": True,
            },
            "SPY": {
                "symbol": "SPY",
                "asset_class": "us_equity_etf",
                "tradable": True,
                "marginable": True,
                "shortable": False,
                "easy_to_borrow": True,
            },
            "XLK": {
                "symbol": "XLK",
                "asset_class": "us_equity_etf",
                "tradable": True,
                "marginable": True,
                "shortable": True,
                "easy_to_borrow": True,
            },
            "XLF": {
                "symbol": "XLF",
                "asset_class": "us_equity_etf",
                "tradable": True,
                "marginable": True,
                "shortable": True,
                "easy_to_borrow": True,
            },
        }
    )

    def factory(
        _credentials: AlpacaPaperCredentials,
        _timeout_seconds: float,
    ) -> ActivationRehearsalClient:
        return client

    result = run_activation_rehearsal_m44d(
        _approved_request(mode="real-paper"),
        environ=_paper_env(),
        app_config=_scale_in_proof_config(),
        client_factory=cast(ActivationRehearsalClientFactory, factory),
    )

    assert result.success is False
    assert any("asset_not_shortable" in blocker for blocker in result.blockers)
    assert result.packet.short_rehearsal.succeeded is False


def test_m44d_emergency_reprotects_if_short_cover_fails() -> None:
    client = FakeActivationRehearsalClient(
        submit_statuses=(
            ("filled", 1.0),
            ("accepted", 0.0),
            ("rejected", 0.0),
            ("accepted", 0.0),
        )
    )

    def factory(
        _credentials: AlpacaPaperCredentials,
        _timeout_seconds: float,
    ) -> ActivationRehearsalClient:
        return client

    result = run_activation_rehearsal_m44d(
        _approved_request(mode="real-paper").model_copy(update={"rehearsal_mode": "short"}),
        environ=_paper_env(),
        app_config=_scale_in_proof_config(),
        client_factory=cast(ActivationRehearsalClientFactory, factory),
    )

    assert result.success is False
    assert "emergency_short_reprotection_required" in result.blockers
    assert result.packet.short_rehearsal.emergency_reprotect_result is not None
    assert result.packet.short_rehearsal.emergency_reprotect_result.verified is True


def test_m44d_readiness_false_if_scale_in_missing() -> None:
    short_only = run_activation_rehearsal_m44d(
        _approved_request().model_copy(update={"rehearsal_mode": "short"}),
        environ={},
    )
    readiness = build_frozen_readiness_m44d_packet(
        activation_packet=short_only.packet,
        app_config=load_app_config(),
        tiingo_gate_go=True,
    )

    assert readiness.m45_readiness is False
    assert "scale_in_rehearsal_not_successful" in readiness.blockers


def test_m44d_evidence_packets_exclude_secrets(tmp_path: Path) -> None:
    client = FakeActivationRehearsalClient()

    def factory(
        _credentials: AlpacaPaperCredentials,
        _timeout_seconds: float,
    ) -> ActivationRehearsalClient:
        return client

    result = run_activation_rehearsal_m44d(
        _approved_request(mode="real-paper"),
        environ=_paper_env(),
        app_config=_scale_in_proof_config(),
        client_factory=cast(ActivationRehearsalClientFactory, factory),
    )
    activation_path, readiness_path = write_activation_rehearsal_m44d_artifacts(
        result,
        activation_path=tmp_path / "activation_rehearsal_m44d.json",
        readiness_path=tmp_path / "frozen_readiness_m44d.json",
    )
    payload = json.loads(activation_path.read_text(encoding="utf-8"))
    readiness_payload = json.loads(readiness_path.read_text(encoding="utf-8"))

    assert result.success is True
    assert payload["latest_spec_version"] == "v0.6"
    assert readiness_payload["activation_rehearsal_m44d_packet_reference"] == (
        ACTIVATION_REHEARSAL_M44D_EVIDENCE_PATH
    )
    assert readiness_payload["m45_readiness"] is True
    assert not _contains_sensitive_token(payload)
    assert not _contains_sensitive_token(readiness_payload)
    assert FROZEN_READINESS_M44D_EVIDENCE_PATH == "docs/evidence/frozen_readiness_m44d.json"


def _contains_sensitive_token(value: object) -> bool:
    text = json.dumps(value, sort_keys=True)
    return any(
        token in text
        for token in (
            "paper-key",
            "paper-secret",
            "DATABASE_URL",
            "ALPACA_API_KEY",
            "TIINGO_API_KEY",
        )
    )


def _scale_in_proof_config() -> AppConfig:
    data = load_app_config().model_dump()
    data["scale_in"]["real_additive_stop_proof_completed_by_m44d"] = True
    data["validation"]["scale_in_policy"]["enabled_at_validation_start"] = True
    data["validation"]["scale_in_policy"]["required_clean_scheduled_runs_before_enable"] = 0
    data["validation"]["scale_in_policy"]["real_additive_stop_proof_completed_by_m44d"] = True
    data["validation_risk"]["max_scale_ins_per_day_at_start"] = 1
    return AppConfig.model_validate(data)
