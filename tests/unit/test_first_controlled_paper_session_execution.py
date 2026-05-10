from __future__ import annotations

from pathlib import Path

import pytest

from packages.core.config import load_app_config
from packages.paper import (
    MILESTONE_34_FAKE_OPERATOR_APPROVAL,
    MILESTONE_34_REAL_OPERATOR_APPROVAL,
    FirstPaperSessionExecutionRequest,
    FirstPaperSessionExecutionResult,
    default_first_paper_session_execution_request,
    run_first_controlled_paper_session_execution,
    write_first_controlled_paper_session_result_artifact,
)
from scripts.check_first_controlled_paper_session import main as m29_script_main
from scripts.check_first_controlled_paper_session_preflight import main as preflight_script_main
from scripts.run_first_controlled_paper_session import main as run_session_script_main


def _fake_request(scenario_id: str = "happy_path") -> FirstPaperSessionExecutionRequest:
    return default_first_paper_session_execution_request(
        scenario_id,
        mode="fake-real-paper",
        operator_approval_marker=MILESTONE_34_FAKE_OPERATOR_APPROVAL,
    )


def _real_request(
    scenario_id: str = "happy_path",
    *,
    target_symbol: str | None = "AAPL",
    max_quantity: int | None = 1,
    max_notional_usd: float | None = 25.0,
    operator_approval_marker: str | None = MILESTONE_34_REAL_OPERATOR_APPROVAL,
    confirm_real_paper_writes: bool = True,
) -> FirstPaperSessionExecutionRequest:
    return default_first_paper_session_execution_request(
        scenario_id,
        mode="real-paper",
        operator_approval_marker=operator_approval_marker,
        target_symbol=target_symbol,
        max_quantity=max_quantity,
        max_notional_usd=max_notional_usd,
        confirm_paper_endpoint=True,
        confirm_real_paper_writes=confirm_real_paper_writes,
        confirm_no_live_trading=True,
        confirm_no_autonomous_live=True,
        confirm_no_schedules=True,
        confirm_no_leverage=True,
        confirm_first_session_only=True,
        confirm_protective_stop_required=True,
        confirm_cleanup_policy=True,
    )


def _run_fake(scenario_id: str = "happy_path") -> FirstPaperSessionExecutionResult:
    return run_first_controlled_paper_session_execution(_fake_request(scenario_id))


def test_default_real_session_script_refuses_before_external_calls(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert run_session_script_main([]) == 1
    output = capsys.readouterr().out
    assert '"refused": true' in output
    assert '"real_broker_writes_attempted": false' in output


def test_real_paper_without_operator_approval_refuses_before_broker_calls() -> None:
    result = run_first_controlled_paper_session_execution(
        _real_request(operator_approval_marker=None),
        environ={},
    )

    assert result.refused is True
    assert "operator_approval_missing" in result.blockers
    assert result.real_read_only_alpaca_calls_performed is False
    assert result.real_broker_writes_attempted is False


def test_real_paper_without_confirm_real_paper_writes_refuses() -> None:
    result = run_first_controlled_paper_session_execution(
        _real_request(confirm_real_paper_writes=False),
        environ={},
    )

    assert result.refused is True
    assert "confirm_real_paper_writes_required" in result.blockers
    assert result.real_broker_writes_attempted is False


def test_real_paper_without_target_symbol_or_envelope_refuses() -> None:
    result = run_first_controlled_paper_session_execution(
        _real_request(target_symbol=None, max_quantity=None, max_notional_usd=None),
        environ={},
    )

    assert result.refused is True
    assert "target_symbol_required" in result.blockers
    assert "max_qty_required" in result.blockers
    assert "max_notional_required" in result.blockers
    assert result.real_broker_writes_attempted is False


def test_real_paper_with_missing_launch_packet_refuses(tmp_path: Path) -> None:
    request = _real_request().model_copy(
        update={"launch_packet_path": str(tmp_path / "missing.json")}
    )
    result = run_first_controlled_paper_session_execution(request, environ={})

    assert result.refused is True
    assert "launch_packet_missing" in result.blockers
    assert result.real_broker_writes_attempted is False


def test_live_endpoint_and_paper_endpoint_gates_refuse() -> None:
    result = run_first_controlled_paper_session_execution(
        _real_request("live_endpoint_rejected"),
        environ={},
    )

    assert result.refused is True
    assert "live_endpoint_detected" in result.blockers
    assert "confirm_paper_endpoint_required" in result.blockers
    assert result.real_broker_writes_attempted is False


def test_schedule_live_autonomous_and_leverage_gates_refuse() -> None:
    request = _real_request().model_copy(
        update={
            "confirm_no_schedules": False,
            "confirm_no_live_trading": False,
            "confirm_no_autonomous_live": False,
            "confirm_no_leverage": False,
        }
    )
    result = run_first_controlled_paper_session_execution(request, environ={})

    assert "confirm_no_schedules_required" in result.blockers
    assert "confirm_no_live_trading_required" in result.blockers
    assert "confirm_no_autonomous_live_required" in result.blockers
    assert "confirm_no_leverage_required" in result.blockers
    assert result.real_broker_writes_attempted is False


def test_config_live_autonomous_and_leverage_refuse() -> None:
    app_config = load_app_config()
    unsafe_config = app_config.model_copy(
        update={
            "system": app_config.system.model_copy(
                update={"live_trading_enabled": True, "dry_run": False}
            ),
            "execution": app_config.execution.model_copy(
                update={"autonomous_execution_enabled": True}
            ),
            "risk_level_4_micro_live": app_config.risk_level_4_micro_live.model_copy(
                update={"allow_margin": True}
            ),
        }
    )
    result = run_first_controlled_paper_session_execution(
        _real_request(),
        environ={},
        app_config=unsafe_config,
    )

    assert "live_trading_enabled" in result.blockers
    assert "autonomous_live_execution_enabled" in result.blockers
    assert "leverage_enabled" in result.blockers
    assert result.real_broker_writes_attempted is False


def test_short_and_unsupported_asset_refuse_before_broker() -> None:
    short_result = run_first_controlled_paper_session_execution(
        _real_request("short_rejected"),
        environ={},
    )
    unsupported_result = run_first_controlled_paper_session_execution(
        _real_request("unsupported_asset_rejected"),
        environ={},
    )

    assert "short_side_forbidden" in short_result.blockers
    assert "unsupported_asset_class" in unsupported_result.blockers
    assert short_result.real_broker_writes_attempted is False
    assert unsupported_result.real_broker_writes_attempted is False


def test_dirty_reconciliation_existing_order_and_position_refuse() -> None:
    dirty = _run_fake("dirty_reconciliation_blocks")
    open_order = _run_fake("existing_open_orders")
    position = _run_fake("existing_position")

    assert "pre_run_reconciliation_not_clean" in dirty.blockers
    assert "existing_target_symbol_open_order" in open_order.blockers
    assert "existing_target_symbol_position" in position.blockers


def test_missing_execution_intent_idempotency_and_stop_plan_refuse() -> None:
    missing_intent = run_first_controlled_paper_session_execution(
        _real_request("missing_execution_intent"),
        environ={},
    )
    missing_key = run_first_controlled_paper_session_execution(
        _real_request("missing_idempotency_key"),
        environ={},
    )
    missing_stop = run_first_controlled_paper_session_execution(
        _real_request("missing_protective_stop_plan"),
        environ={},
    )

    assert "execution_intent_required" in missing_intent.blockers
    assert "idempotency_key_required" in missing_key.blockers
    assert "protective_stop_plan_required" in missing_stop.blockers


def test_fake_real_paper_success_submits_fake_entry_stop_and_verifies_stop() -> None:
    result = _run_fake()

    assert result.success is True
    assert result.status == "executed"
    assert result.actual_paper_trading_started is False
    assert result.real_broker_writes_attempted is False
    assert result.result_packet.entry_order_status == "filled"
    assert result.result_packet.fill_status == "filled"
    assert result.result_packet.filled_quantity == 1.0
    assert result.result_packet.protective_stop_order_id is not None
    assert result.result_packet.protective_stop_verification_result == "verified"
    assert result.result_packet.post_session_recommendation == (
        "post_session_audit_required_before_repetition"
    )


def test_fake_partial_fill_places_stop_for_filled_quantity_and_cancels_remainder() -> None:
    result = _run_fake("partial_fill")

    assert result.success is True
    assert result.result_packet.fill_status == "partial_fill"
    assert result.result_packet.filled_quantity == 0.5
    assert result.result_packet.protective_stop_verification_result == "verified"
    assert "cancel_unfilled_remainder" in result.result_packet.cleanup_actions


def test_fake_no_fill_cancels_without_stop() -> None:
    result = _run_fake("no_fill")

    assert result.success is True
    assert result.result_packet.fill_status == "not_filled"
    assert result.result_packet.protective_stop_order_id is None
    assert result.result_packet.protective_stop_verification_result == "not_required_no_fill"
    assert "cancel_unfilled_entry" in result.result_packet.cleanup_actions


def test_fake_missing_stop_verification_creates_critical_incident() -> None:
    result = _run_fake("missing_stop_verification")

    assert result.success is False
    assert result.unsafe is True
    assert result.status == "incident"
    assert "critical_missing_protective_stop_verification" in result.result_packet.incidents
    assert result.result_packet.protective_stop_verification_result == "not_verified"


def test_result_packet_contains_required_fields_and_excludes_secrets(tmp_path: Path) -> None:
    result = _run_fake()
    packet = result.result_packet

    assert packet.result_packet_id
    assert packet.operator_approval_marker == MILESTONE_34_FAKE_OPERATOR_APPROVAL
    assert packet.latest_spec_path == "docs/app/Autonomous_AI_Trading_Bot_SPEC_v0.3.md"
    assert packet.candidate_id == "candidate-AAPL-m34"
    assert packet.ai_news_neutral_fallback_marker == "neutral_fake_ai_news_no_broker_authority"
    assert packet.decision_id
    assert packet.risk_check_id
    assert packet.execution_intent_id
    assert packet.client_order_id
    assert packet.broker_order_id
    assert packet.fake_alert_summary == "fake_alert_summary_only"
    output = write_first_controlled_paper_session_result_artifact(
        result,
        tmp_path / "first_controlled_paper_session_result.json",
    )
    serialized = output.read_text(encoding="utf-8")
    assert '"milestone": "34"' in serialized
    assert "paper-secret" not in serialized
    assert "DATABASE_URL=" not in serialized


def test_ai_news_neutral_fallback_has_no_broker_authority() -> None:
    result = _run_fake()

    assert result.result_packet.ai_news_neutral_fallback_marker
    assert result.ai_broker_write_authority is False
    assert result.real_broker_writes_attempted is False


def test_existing_m29_m30_and_preflight_scripts_still_work(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert m29_script_main(["--scenario", "happy_path"]) == 0
    assert '"success": true' in capsys.readouterr().out

    assert (
        run_session_script_main(
            [
                "--mode",
                "fake",
                "--scenario",
                "happy_path",
                "--operator-approval",
                "MILESTONE_30_FAKE_ONLY",
            ]
        )
        == 0
    )
    assert '"success": true' in capsys.readouterr().out

    assert (
        preflight_script_main(
            [
                "--mode",
                "fake",
                "--scenario",
                "happy_path",
                "--operator-approval",
                "MILESTONE_31_FAKE_PREFLIGHT",
            ]
        )
        == 0
    )
    assert '"success": true' in capsys.readouterr().out


def test_m34_script_real_paper_missing_target_writes_result_packet(
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    output_path = tmp_path / "first_controlled_paper_session_result.json"
    assert (
        run_session_script_main(
            [
                "--mode",
                "real-paper",
                "--operator-approval",
                MILESTONE_34_REAL_OPERATOR_APPROVAL,
                "--confirm-paper-endpoint",
                "--confirm-real-paper-writes",
                "--confirm-no-live-trading",
                "--confirm-no-autonomous-live",
                "--confirm-no-schedules",
                "--confirm-no-leverage",
                "--confirm-first-session-only",
                "--confirm-protective-stop-required",
                "--confirm-cleanup-policy",
                "--result-output",
                str(output_path),
            ]
        )
        == 1
    )
    output = capsys.readouterr().out
    assert '"target_symbol_required"' in output
    assert str(output_path) in output


def test_m34_script_fake_real_paper_happy_path(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert (
        run_session_script_main(
            [
                "--mode",
                "fake-real-paper",
                "--scenario",
                "happy_path",
                "--operator-approval",
                MILESTONE_34_FAKE_OPERATOR_APPROVAL,
            ]
        )
        == 0
    )
    output = capsys.readouterr().out
    assert '"status": "executed"' in output
    assert '"real_broker_writes_attempted": false' in output
