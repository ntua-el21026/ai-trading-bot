from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from packages.broker.alpaca import ALPACA_PAPER_BASE_URL
from packages.broker.fakes import DEFAULT_AS_OF, FakeAlpacaClient
from packages.core.config import load_app_config
from packages.paper import (
    M41_SUPERVISED_SCHEDULE_READINESS_EVIDENCE_PATH,
    M42_SUPERVISED_SCHEDULED_PAPER_RUN_EVIDENCE_PATH,
    MILESTONE_42_REAL_OPERATOR_APPROVAL,
    SupervisedScheduledPaperRunRequest,
    audit_m41_supervised_schedule_readiness_packet,
    run_supervised_scheduled_paper_once,
    write_supervised_scheduled_paper_run_artifact,
)


def _base_request(**updates: object) -> SupervisedScheduledPaperRunRequest:
    data: dict[str, object] = {
        "mode": "fake",
        "operator_approval_marker": MILESTONE_42_REAL_OPERATOR_APPROVAL,
        "confirm_paper_endpoint": True,
        "confirm_temporary_supervised_schedule_only": True,
        "confirm_disable_after_one_run": True,
        "confirm_no_live_trading": True,
        "confirm_no_autonomous_live": True,
        "confirm_no_unattended_operation": True,
        "confirm_no_leverage": True,
        "confirm_protective_stop_required": True,
        "confirm_cleanup_policy": True,
    }
    data.update(updates)
    return SupervisedScheduledPaperRunRequest.model_validate(data)


def _safe_env() -> dict[str, str]:
    return {
        "ALPACA_API_KEY": "paper-key-placeholder",
        "ALPACA_SECRET_KEY": "paper-secret-placeholder",
        "ALPACA_BASE_URL": ALPACA_PAPER_BASE_URL,
        "RUN_ALPACA_PAPER_SMOKE": "1",
        "ALPACA_PAPER_SMOKE_CONFIRM": "READ_ONLY_PAPER_ACCOUNT",
        "RUN_ALPACA_PAPER_ORDER_LIFECYCLE_SMOKE": "",
        "ALERT_ENABLE_REAL_DELIVERY": "false",
        "AI_ENABLE_ESCALATION": "false",
        "NEWS_ENABLE_OPENAI_WEB_FALLBACK": "false",
        "DASHBOARD_CONTROL_PLANE_ALLOW_CONTROL_SIGNALS": "false",
        "RUN_FIRST_CONTROLLED_PAPER_SESSION": "",
        "RUN_FIRST_CONTROLLED_PAPER_SESSION_EXECUTION": "",
        "RUN_TEMPORAL_CLOUD_SMOKE": "",
        "RUN_DASHBOARD_CONTROL_PLANE_SMOKE": "",
        "RUN_VERCEL_DASHBOARD_PREVIEW": "",
        "RUN_TELEGRAM_ALERT_SMOKE": "",
    }


def test_m42_refuses_if_m41_readiness_packet_missing(tmp_path: Path) -> None:
    result = run_supervised_scheduled_paper_once(
        _base_request(m41_readiness_packet_path=str(tmp_path / "missing-m41.json"))
    )

    assert result.refused is True
    assert "m41_supervised_schedule_readiness_packet_missing" in result.blockers
    assert result.broker_writes_performed is False
    assert result.schedule_workflow_created_or_activated is False
    assert result.packet.schedule_workflow_creation_status == (
        "not_created_pre_schedule_gate_refused"
    )


def test_m42_refuses_if_m41_readiness_is_not_go(tmp_path: Path) -> None:
    packet_path = tmp_path / "m41-not-go.json"
    payload = json.loads(
        Path(M41_SUPERVISED_SCHEDULE_READINESS_EVIDENCE_PATH).read_text(encoding="utf-8")
    )
    payload["result"]["readiness_approved"] = False
    payload["result"]["go_no_go"] = "no_go"
    payload["result"]["blockers"] = ["manual_review_required"]
    packet_path.write_text(json.dumps(payload), encoding="utf-8")

    audit = audit_m41_supervised_schedule_readiness_packet(packet_path)
    result = run_supervised_scheduled_paper_once(
        _base_request(m41_readiness_packet_path=str(packet_path))
    )

    assert audit.readiness_go is False
    assert "m41_readiness_go" in result.blockers
    assert result.schedule_workflow_created_or_activated is False


def test_m42_requires_approval_marker() -> None:
    result = run_supervised_scheduled_paper_once(
        _base_request(operator_approval_marker=None)
    )

    assert result.refused is True
    assert "m42_operator_approval_marker_required" in result.blockers
    assert result.packet.schedule_workflow_activation_status == (
        "not_activated_pre_schedule_gate_refused"
    )


def test_m42_refuses_symbols_outside_operator_candidates() -> None:
    result = run_supervised_scheduled_paper_once(
        _base_request(primary_target_symbol="QQQ")
    )

    assert result.refused is True
    assert "m42_primary_target_must_be_xlk" in result.blockers
    assert result.broker_writes_performed is False


def test_m42_fallback_selects_xlf_when_xlk_envelope_invalid() -> None:
    result = run_supervised_scheduled_paper_once(
        _base_request(primary_max_quantity=2)
    )

    assert result.success is True
    assert result.packet.selected_target_symbol == "XLF"
    xlk = result.packet.candidate_evaluations[0]
    assert xlk.target_symbol == "XLK"
    assert "xlk_max_qty_exceeds_configured_cap" in xlk.blockers
    assert result.packet.normal_stop_path_succeeded is True


def test_m42_fake_supervised_schedule_runs_once_and_deactivates() -> None:
    result = run_supervised_scheduled_paper_once(_base_request())

    assert result.success is True
    assert result.packet.selected_target_symbol == "XLK"
    assert result.packet.fill_status == "filled"
    assert result.packet.protective_stop_verification_result == "verified"
    assert result.packet.normal_stop_path_succeeded is True
    assert result.packet.recovery_stop_path_used is False
    assert result.schedule_workflow_created_or_activated is True
    assert result.schedule_workflow_remains_active is False
    assert result.packet.schedule_workflow_run_status == "completed_once"
    assert result.packet.schedule_workflow_deactivation_status == (
        "deactivated_after_single_run"
    )
    assert result.packet.no_recurring_unattended_schedule_remains_active is True
    assert result.packet.post_run_broker_state is not None
    assert result.packet.post_run_broker_state.reconciliation_summary == (
        "clean_protected_holds"
    )
    assert result.packet.freeze_readiness_recommendation == (
        "M43_FREEZE_READINESS_MAY_BE_CONSIDERED"
    )


def test_m42_fake_no_fill_path_is_audited_and_clean() -> None:
    result = run_supervised_scheduled_paper_once(
        _base_request(execution_scenario_id="no_fill")
    )

    assert result.success is True
    assert result.packet.fill_status == "not_filled"
    assert result.packet.protective_stop_verification_result == "not_required_no_fill"
    assert result.packet.normal_stop_path_succeeded is False
    assert result.packet.post_run_broker_state is not None
    assert result.packet.post_run_broker_state.positions_total == 2
    assert result.packet.post_run_broker_state.open_orders_total == 2


def test_m42_refuses_if_msft_stop_missing_in_current_broker_state() -> None:
    client = FakeAlpacaClient(
        positions=(
            _position_payload("AAPL"),
            _position_payload("MSFT"),
        ),
        orders=(
            _stop_order_payload("AAPL", "aapl-stop", "aapl-stop-client"),
        ),
    )

    def factory(*_args: Any, **_kwargs: Any) -> Any:
        return client

    result = run_supervised_scheduled_paper_once(
        _base_request(mode="real-paper"),
        environ=_safe_env(),
        client_factory=factory,
    )

    assert result.refused is True
    assert "msft_protective_stop_missing_or_unverified" in result.blockers
    assert client.submitted_order_requests == []
    assert result.broker_writes_performed is False


def test_m42_refuses_if_unexpected_open_order_exists() -> None:
    client = FakeAlpacaClient(
        positions=(_position_payload("AAPL"), _position_payload("MSFT")),
        orders=(
            _stop_order_payload("AAPL", "aapl-stop", "aapl-stop-client"),
            _stop_order_payload("MSFT", "msft-stop", "msft-stop-client"),
            _stop_order_payload("XLK", "xlk-existing-stop", "xlk-existing-stop-client"),
        ),
    )

    def factory(*_args: Any, **_kwargs: Any) -> Any:
        return client

    result = run_supervised_scheduled_paper_once(
        _base_request(mode="real-paper"),
        environ=_safe_env(),
        client_factory=factory,
    )

    assert result.refused is True
    assert "unexpected_open_orders_present" in result.blockers
    assert client.submitted_order_requests == []


def test_m42_refuses_if_unexpected_position_exists() -> None:
    client = FakeAlpacaClient(
        positions=(
            _position_payload("AAPL"),
            _position_payload("MSFT"),
            _position_payload("XLK"),
        ),
        orders=(
            _stop_order_payload("AAPL", "aapl-stop", "aapl-stop-client"),
            _stop_order_payload("MSFT", "msft-stop", "msft-stop-client"),
        ),
    )

    def factory(*_args: Any, **_kwargs: Any) -> Any:
        return client

    result = run_supervised_scheduled_paper_once(
        _base_request(mode="real-paper"),
        environ=_safe_env(),
        client_factory=factory,
    )

    assert result.refused is True
    assert "unexpected_positions_present" in result.blockers
    assert client.submitted_order_requests == []


def test_m42_packet_contains_required_fields_and_excludes_secrets(tmp_path: Path) -> None:
    result = run_supervised_scheduled_paper_once(_base_request())
    path = write_supervised_scheduled_paper_run_artifact(
        result,
        tmp_path / M42_SUPERVISED_SCHEDULED_PAPER_RUN_EVIDENCE_PATH,
    )
    text = path.read_text(encoding="utf-8")
    payload = json.loads(text)
    packet = payload["supervised_scheduled_paper_run"]

    assert payload["milestone"] == "42"
    assert packet["m41_readiness_packet_reference"] == (
        M41_SUPERVISED_SCHEDULE_READINESS_EVIDENCE_PATH
    )
    assert packet["selected_target_symbol"] == "XLK"
    assert packet["schedule_workflow_run_status"] == "completed_once"
    assert packet["schedules_activated_final_state"] is False
    assert packet["frozen_validation_started"] is False
    assert packet["level4_ready"] is False
    assert "paper-secret" not in text
    assert "paper-key" not in text
    assert "postgres://" not in text
    assert "sk-" not in text


def test_m42_candidate_envelopes_match_config_caps() -> None:
    config = load_app_config()
    result = run_supervised_scheduled_paper_once(_base_request())

    assert result.packet.candidate_evaluations[0].target_symbol == "XLK"
    assert result.packet.candidate_evaluations[0].envelope.estimated_notional_usd == 300.0
    assert result.packet.candidate_evaluations[1].target_symbol == "XLF"
    assert result.packet.candidate_evaluations[1].envelope.estimated_notional_usd == 100.0
    assert result.packet.order_envelope is not None
    assert result.packet.order_envelope.max_quantity <= config.execution.first_session_max_qty


def _position_payload(symbol: str) -> Mapping[str, str]:
    return {
        "symbol": symbol,
        "asset_class": "etf" if symbol in {"XLK", "XLF"} else "equity",
        "qty": "1",
        "avg_entry_price": "100",
        "market_value": "100",
        "opened_at": DEFAULT_AS_OF.isoformat().replace("+00:00", "Z"),
    }


def _stop_order_payload(
    symbol: str,
    broker_order_id: str,
    client_order_id: str,
) -> Mapping[str, str]:
    return {
        "id": broker_order_id,
        "client_order_id": client_order_id,
        "symbol": symbol,
        "side": "sell",
        "asset_class": "etf" if symbol in {"XLK", "XLF"} else "equity",
        "qty": "1",
        "filled_qty": "0",
        "type": "stop",
        "time_in_force": "gtc",
        "status": "new",
        "stop_price": "1",
        "submitted_at": DEFAULT_AS_OF.isoformat().replace("+00:00", "Z"),
        "updated_at": DEFAULT_AS_OF.isoformat().replace("+00:00", "Z"),
    }
