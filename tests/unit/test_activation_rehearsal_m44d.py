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
    M44E_APPROVAL,
    SCALE_IN_REHEARSAL_M44E_EVIDENCE_PATH,
    ActivationRehearsalClient,
    ActivationRehearsalClientFactory,
    ActivationRehearsalRequest,
    FakeActivationRehearsalClient,
    build_frozen_readiness_m44d_packet,
    build_frozen_readiness_m44e_packet,
    run_activation_rehearsal_m44d,
    run_scale_in_repair_m44e,
    write_activation_rehearsal_m44d_artifacts,
    write_scale_in_rehearsal_m44e_artifacts,
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


def _m44e_request(mode: str = "fake") -> ActivationRehearsalRequest:
    return ActivationRehearsalRequest(
        mode=mode,  # type: ignore[arg-type]
        rehearsal_mode="scale-in-repair",
        operator_approval=M44E_APPROVAL,
        confirm_paper_endpoint=True,
        confirm_scale_in_rehearsal_only=True,
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
    assert config.validation.scale_in_policy.enabled_at_validation_start is True
    assert config.validation.scale_in_policy.real_additive_stop_proof_completed_by_m44d is False
    assert config.validation.scale_in_policy.real_additive_stop_proof_completed_by_m44e is True
    assert config.validation.scale_in_policy.short_scale_in_enabled_at_validation_start is False
    assert config.shorts.eligible_symbols == ("SPY", "QQQ", "DIA", "IWM")
    assert config.validation_risk.max_scale_ins_per_day_at_start == 1


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


def test_m44e_refuses_without_approval_marker() -> None:
    result = run_scale_in_repair_m44e(
        _m44e_request().model_copy(update={"operator_approval": None}),
        environ={},
    )

    assert result.success is False
    assert "m44e_approval_marker_required" in result.blockers
    assert result.broker_writes_performed is False


def test_m44e_refuses_non_approved_symbols() -> None:
    try:
        ActivationRehearsalRequest(
            mode="fake",
            rehearsal_mode="scale-in-repair",
            operator_approval=M44E_APPROVAL,
            scale_primary_symbol="AAPL",
            scale_fallback_symbol="XLF",
        )
    except ValueError as exc:
        assert "scale-in rehearsal candidates" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("invalid M44E scale-in symbol was accepted")


def test_m44e_refuses_non_flat_broker_baseline() -> None:
    client = FakeActivationRehearsalClient(
        positions=(
            {
                "symbol": "XLK",
                "asset_class": "etf",
                "qty": "1",
                "avg_entry_price": "100",
                "market_value": "100",
                "opened_at": "2026-05-18T14:30:00Z",
            },
        )
    )

    result = run_scale_in_repair_m44e(
        _m44e_request(mode="real-paper"),
        environ=_paper_env(),
        app_config=_m44e_proof_config(),
        client_factory=cast(
            ActivationRehearsalClientFactory,
            lambda _credentials, _timeout_seconds: client,
        ),
    )

    assert result.success is False
    assert "pre_run_positions_not_zero" in result.blockers
    assert client.submitted_order_requests == []


def test_m44e_fake_repair_records_root_cause_and_oto_addon_shape() -> None:
    result = run_scale_in_repair_m44e(
        _m44e_request(),
        environ={},
        app_config=_m44e_proof_config(),
    )

    assert result.success is False
    assert result.packet.m44d_short_proof_accepted is True
    assert result.packet.repair_summary.order_shape_changed is True
    assert result.packet.repair_summary.risk_gate_changed is False
    assert result.packet.scale_in_entry_request_summary is not None
    assert result.packet.scale_in_entry_request_summary.order_class == "oto"
    assert result.packet.scale_in_entry_request_summary.side == "buy"
    assert result.packet.additive_protective_stop_result is not None
    assert result.packet.additive_protective_stop_result.verified is True
    assert result.packet.aggregate_long_protection_check is not None
    assert result.packet.aggregate_long_protection_check.passed is True
    assert result.packet.final_open_orders_count == 0
    assert result.packet.final_positions_count == 0
    assert "real_m44e_scale_in_rehearsal_not_performed" in result.blockers


def test_m44e_real_paper_mode_with_stubbed_client_can_make_readiness_go() -> None:
    client = FakeActivationRehearsalClient()

    def factory(
        _credentials: AlpacaPaperCredentials,
        _timeout_seconds: float,
    ) -> ActivationRehearsalClient:
        return client

    result = run_scale_in_repair_m44e(
        _m44e_request(mode="real-paper"),
        environ=_paper_env(),
        app_config=_m44e_proof_config(),
        client_factory=cast(ActivationRehearsalClientFactory, factory),
    )

    submitted = client.submitted_order_requests
    addon_requests = [request for request in submitted if request.get("order_class") == "oto"]
    assert result.success is True
    assert result.packet.m45_long_short_scalein_readiness is True
    assert result.packet.scale_in_fill_result is not None
    assert result.packet.scale_in_fill_result.filled_quantity == 1.0
    assert len(addon_requests) == 1
    assert addon_requests[0]["side"] == "buy"
    assert addon_requests[0]["stop_loss"]["stop_price"]
    assert result.readiness_packet.m45_readiness is True


def test_m44e_readiness_false_if_scale_in_missing() -> None:
    result = run_scale_in_repair_m44e(
        _m44e_request(mode="real-paper"),
        environ=_paper_env(),
        app_config=_m44e_proof_config(),
        client_factory=cast(
            ActivationRehearsalClientFactory,
            lambda _credentials, _timeout_seconds: FakeActivationRehearsalClient(
                submit_statuses=(("filled", 1.0), ("accepted", 0.0), ("rejected", 0.0))
            ),
        ),
    )

    readiness = build_frozen_readiness_m44e_packet(
        scale_in_packet=result.packet,
        app_config=_m44e_proof_config(),
        tiingo_gate_go=True,
    )

    assert readiness.m45_readiness is False
    assert "m44e_scale_in_rehearsal_not_successful" in readiness.blockers


def test_m44e_evidence_packets_exclude_secrets(tmp_path: Path) -> None:
    client = FakeActivationRehearsalClient()

    def factory(
        _credentials: AlpacaPaperCredentials,
        _timeout_seconds: float,
    ) -> ActivationRehearsalClient:
        return client

    result = run_scale_in_repair_m44e(
        _m44e_request(mode="real-paper"),
        environ=_paper_env(),
        app_config=_m44e_proof_config(),
        client_factory=cast(ActivationRehearsalClientFactory, factory),
    )
    scale_path, readiness_path = write_scale_in_rehearsal_m44e_artifacts(
        result,
        scale_in_path=tmp_path / "scale_in_rehearsal_m44e.json",
        readiness_path=tmp_path / "frozen_readiness_m44e.json",
    )
    payload = json.loads(scale_path.read_text(encoding="utf-8"))
    readiness_payload = json.loads(readiness_path.read_text(encoding="utf-8"))

    assert result.success is True
    assert payload["latest_spec_version"] == "v0.6"
    assert payload["repair_summary"]["suspected_root_cause"].startswith("alpaca_wash")
    assert readiness_payload["scale_in_rehearsal_m44e_packet_reference"] == (
        SCALE_IN_REHEARSAL_M44E_EVIDENCE_PATH
    )
    assert not _contains_sensitive_token(payload)
    assert not _contains_sensitive_token(readiness_payload)


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
    data["scale_in"]["real_additive_stop_proof_completed_by_m44e"] = False
    data["validation"]["scale_in_policy"]["enabled_at_validation_start"] = True
    data["validation"]["scale_in_policy"]["required_clean_scheduled_runs_before_enable"] = 0
    data["validation"]["scale_in_policy"]["real_additive_stop_proof_completed_by_m44d"] = True
    data["validation"]["scale_in_policy"]["real_additive_stop_proof_completed_by_m44e"] = False
    data["validation_risk"]["max_scale_ins_per_day_at_start"] = 1
    return AppConfig.model_validate(data)


def _m44e_proof_config() -> AppConfig:
    data = load_app_config().model_dump()
    data["scale_in"]["real_additive_stop_proof_completed_by_m44d"] = False
    data["scale_in"]["real_additive_stop_proof_completed_by_m44e"] = True
    data["validation"]["scale_in_policy"]["enabled_at_validation_start"] = True
    data["validation"]["scale_in_policy"]["required_clean_scheduled_runs_before_enable"] = 0
    data["validation"]["scale_in_policy"]["real_additive_stop_proof_completed_by_m44d"] = False
    data["validation"]["scale_in_policy"]["real_additive_stop_proof_completed_by_m44e"] = True
    data["validation_risk"]["max_scale_ins_per_day_at_start"] = 1
    return AppConfig.model_validate(data)
