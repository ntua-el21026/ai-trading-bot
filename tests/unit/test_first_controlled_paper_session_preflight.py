from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import pytest

from packages.broker.alpaca import ALPACA_PAPER_BASE_URL
from packages.paper import (
    MILESTONE_30_FAKE_OPERATOR_APPROVAL,
    MILESTONE_31_FAKE_OPERATOR_APPROVAL,
    MILESTONE_31_READ_ONLY_OPERATOR_APPROVAL,
    MILESTONE_32_READ_ONLY_OPERATOR_APPROVAL,
    MILESTONE_33_READ_ONLY_OPERATOR_APPROVAL,
    FirstSessionPreflightRequest,
    FirstSessionPreflightResult,
    ReadOnlyPreflightBrokerClient,
    default_first_session_preflight_request,
    load_preflight_environment,
    run_first_controlled_paper_session_preflight,
    write_launch_packet_artifact,
)
from scripts.check_first_controlled_paper_session import main as m29_script_main
from scripts.check_first_controlled_paper_session_preflight import main as m31_script_main
from scripts.run_first_controlled_paper_session import main as m30_script_main


def _safe_readonly_env() -> dict[str, str]:
    return {
        "ALPACA_API_KEY": "paper-key",
        "ALPACA_SECRET_KEY": "paper-secret",
        "ALPACA_BASE_URL": ALPACA_PAPER_BASE_URL,
        "RUN_ALPACA_PAPER_SMOKE": "1",
        "ALPACA_PAPER_SMOKE_CONFIRM": "READ_ONLY_PAPER_ACCOUNT",
    }


def _run_fake(scenario_id: str = "happy_path") -> FirstSessionPreflightResult:
    request = default_first_session_preflight_request(
        scenario_id,
        mode="fake",
        operator_approval_marker=MILESTONE_31_FAKE_OPERATOR_APPROVAL,
    )
    return run_first_controlled_paper_session_preflight(request)


def _real_readonly_request(confirm: bool = True) -> FirstSessionPreflightRequest:
    return default_first_session_preflight_request(
        "happy_path",
        mode="real-read-only",
        operator_approval_marker=MILESTONE_31_READ_ONLY_OPERATOR_APPROVAL,
        confirm_paper_endpoint=confirm,
        confirm_no_broker_writes=confirm,
        confirm_no_live_trading=confirm,
        confirm_no_autonomous_live=confirm,
        confirm_no_schedules=confirm,
        confirm_no_leverage=confirm,
    )


def _real_readonly_request_m32(confirm: bool = True) -> FirstSessionPreflightRequest:
    return _real_readonly_request(confirm=confirm).model_copy(
        update={"operator_approval_marker": MILESTONE_32_READ_ONLY_OPERATOR_APPROVAL}
    )


def _real_readonly_request_m33(confirm: bool = True) -> FirstSessionPreflightRequest:
    return _real_readonly_request(confirm=confirm).model_copy(
        update={"operator_approval_marker": MILESTONE_33_READ_ONLY_OPERATOR_APPROVAL}
    )


def test_fake_preflight_happy_path_succeeds_with_authorization_packet() -> None:
    result = _run_fake()

    assert result.success is True
    assert result.refused is False
    assert result.go_no_go_decision == "go"
    assert result.actual_paper_trading_started is False
    assert result.real_broker_writes_attempted is False
    assert result.broker_write_methods_called is False
    assert result.read_only_broker_calls_performed is False
    assert result.real_read_only_alpaca_calls_performed is False
    assert result.packet.preflight_mode == "fake"
    assert result.packet.paper_endpoint_proof.paper_endpoint_proven is True
    assert result.packet.live_endpoint_rejection_proof.live_endpoint_rejected is True
    assert result.packet.target_symbol_cleanliness.clean is True
    assert result.packet.go_no_go_decision == "go"


def test_default_path_refuses_without_external_calls_or_broker_writes() -> None:
    result = run_first_controlled_paper_session_preflight()

    assert result.success is False
    assert result.refused is True
    assert "operator_approval_missing" in result.blockers
    assert result.broker_preflight is None
    assert result.read_only_broker_calls_performed is False
    assert result.real_read_only_alpaca_calls_performed is False
    assert result.real_broker_writes_attempted is False


def test_missing_operator_approval_refuses() -> None:
    request = default_first_session_preflight_request(
        "missing_operator_approval",
        mode="fake",
        operator_approval_marker=MILESTONE_31_FAKE_OPERATOR_APPROVAL,
    )
    result = run_first_controlled_paper_session_preflight(request)

    assert result.success is False
    assert result.refused is True
    assert result.blockers == ("operator_approval_missing",)


def test_real_readonly_without_gates_refuses_before_broker_calls() -> None:
    client = _FakeReadOnlyClient()
    result = run_first_controlled_paper_session_preflight(
        _real_readonly_request(confirm=False),
        environ=_safe_readonly_env(),
        client_factory=lambda _credentials: client,
        real_external_calls_performed=False,
    )

    assert result.success is False
    assert "confirm_paper_endpoint_required" in result.blockers
    assert "confirm_no_broker_writes_required" in result.blockers
    assert client.read_calls == ()
    assert client.write_calls == ()


def test_live_endpoint_refuses_before_broker_calls() -> None:
    client = _FakeReadOnlyClient()
    request = default_first_session_preflight_request(
        "live_endpoint_rejected",
        mode="real-read-only",
        operator_approval_marker=MILESTONE_31_READ_ONLY_OPERATOR_APPROVAL,
        confirm_paper_endpoint=True,
        confirm_no_broker_writes=True,
        confirm_no_live_trading=True,
        confirm_no_autonomous_live=True,
        confirm_no_schedules=True,
        confirm_no_leverage=True,
    )
    result = run_first_controlled_paper_session_preflight(
        request,
        environ=_safe_readonly_env(),
        client_factory=lambda _credentials: client,
        real_external_calls_performed=False,
    )

    assert result.success is False
    assert "live_endpoint_detected" in result.blockers
    assert "paper_endpoint_not_proven" in result.blockers
    assert client.read_calls == ()
    assert client.write_calls == ()


def test_paper_endpoint_not_proven_refuses() -> None:
    result = _run_fake("paper_endpoint_not_proven")

    assert result.success is False
    assert "paper_endpoint_not_proven" in result.blockers
    assert result.read_only_broker_calls_performed is False


def test_real_readonly_path_uses_fake_client_reads_and_never_calls_write_methods() -> None:
    client = _FakeReadOnlyClient()
    result = run_first_controlled_paper_session_preflight(
        _real_readonly_request(),
        environ=_safe_readonly_env(),
        client_factory=lambda _credentials: client,
        real_external_calls_performed=False,
    )

    assert result.success is True
    assert result.read_only_broker_calls_performed is True
    assert result.real_read_only_alpaca_calls_performed is False
    assert client.read_calls == ("get_account", "get_clock", "list_open_orders", "list_positions")
    assert client.write_calls == ()
    assert result.packet.open_orders_summary.total_open_orders == 0
    assert result.packet.positions_summary.total_positions == 0


def test_m32_real_readonly_marker_is_accepted_for_stubbed_success() -> None:
    client = _FakeReadOnlyClient()
    result = run_first_controlled_paper_session_preflight(
        _real_readonly_request_m32(),
        environ=_safe_readonly_env(),
        client_factory=lambda _credentials: client,
        real_external_calls_performed=False,
    )

    assert result.success is True
    assert result.packet.operator_approval_marker == MILESTONE_32_READ_ONLY_OPERATOR_APPROVAL
    assert client.write_calls == ()


def test_m33_real_readonly_marker_is_accepted_for_stubbed_success() -> None:
    client = _FakeReadOnlyClient()
    result = run_first_controlled_paper_session_preflight(
        _real_readonly_request_m33(),
        environ=_safe_readonly_env(),
        client_factory=lambda _credentials: client,
        real_external_calls_performed=False,
    )

    assert result.success is True
    assert result.packet.operator_approval_marker == MILESTONE_33_READ_ONLY_OPERATOR_APPROVAL
    assert client.read_calls == ("get_account", "get_clock", "list_open_orders", "list_positions")
    assert client.write_calls == ()


def test_readonly_wrapper_exposes_no_write_methods() -> None:
    wrapper = ReadOnlyPreflightBrokerClient(_FakeReadOnlyClient())

    assert wrapper.get_account()["id"] == "paper-account"
    assert not hasattr(wrapper, "submit_order")
    assert not hasattr(wrapper, "cancel_order")
    assert not hasattr(wrapper, "replace_order")
    assert not hasattr(wrapper, "close_position")


def test_open_orders_and_positions_are_summarized_without_secrets() -> None:
    client = _FakeReadOnlyClient(
        open_orders=(_order_payload("MSFT"),),
        positions=(_position_payload("GOOG"),),
    )
    result = run_first_controlled_paper_session_preflight(
        _real_readonly_request(),
        environ=_safe_readonly_env(),
        client_factory=lambda _credentials: client,
        real_external_calls_performed=False,
    )
    serialized = result.packet.model_dump_json()

    assert result.success is True
    assert result.packet.open_orders_summary.symbols == ("MSFT",)
    assert result.packet.positions_summary.symbols == ("GOOG",)
    assert "paper-key" not in serialized
    assert "paper-secret" not in serialized
    assert "DATABASE_URL=" not in serialized


def test_safe_env_loading_uses_dotenv_without_exposing_secret_values(tmp_path: Path) -> None:
    env_path = tmp_path / ".env"
    env_path.write_text(
        "\n".join(
            [
                "ALPACA_API_KEY=paper-key-from-env-file",
                "ALPACA_SECRET_KEY='paper-secret-from-env-file'",
                f"ALPACA_BASE_URL={ALPACA_PAPER_BASE_URL}",
                "RUN_ALPACA_PAPER_SMOKE=1",
                "ALPACA_PAPER_SMOKE_CONFIRM=READ_ONLY_PAPER_ACCOUNT",
            ]
        ),
        encoding="utf-8",
    )
    loaded = load_preflight_environment(repo_root=tmp_path, base_environ={})
    result = run_first_controlled_paper_session_preflight(
        _real_readonly_request_m32(),
        environ=loaded,
        client_factory=lambda _credentials: _FakeReadOnlyClient(),
        real_external_calls_performed=False,
    )
    serialized = result.packet.model_dump_json()

    assert result.success is True
    assert "paper-key-from-env-file" not in serialized
    assert "paper-secret-from-env-file" not in serialized


def test_safe_env_loading_allows_process_override_to_clear_write_smoke_flag(
    tmp_path: Path,
) -> None:
    env_path = tmp_path / ".env"
    env_path.write_text(
        "\n".join(
            [
                "ALPACA_API_KEY=paper-key-from-env-file",
                "ALPACA_SECRET_KEY=paper-secret-from-env-file",
                f"ALPACA_BASE_URL={ALPACA_PAPER_BASE_URL}",
                "RUN_ALPACA_PAPER_SMOKE=1",
                "ALPACA_PAPER_SMOKE_CONFIRM=READ_ONLY_PAPER_ACCOUNT",
                "RUN_ALPACA_PAPER_ORDER_LIFECYCLE_SMOKE=1",
            ]
        ),
        encoding="utf-8",
    )
    loaded = load_preflight_environment(
        repo_root=tmp_path,
        base_environ={"RUN_ALPACA_PAPER_ORDER_LIFECYCLE_SMOKE": ""},
    )
    result = run_first_controlled_paper_session_preflight(
        _real_readonly_request_m33(),
        environ=loaded,
        client_factory=lambda _credentials: _FakeReadOnlyClient(),
        real_external_calls_performed=False,
    )

    assert result.success is True
    assert "write_smoke_flag_must_be_disabled" not in result.blockers
    assert result.read_only_broker_calls_performed is True
    assert result.real_broker_writes_attempted is False


def test_dirty_target_symbol_open_orders_and_position_are_no_go() -> None:
    result = _run_fake("dirty_target_symbol")

    assert result.success is False
    assert result.go_no_go_decision == "no_go"
    assert "target_symbol_not_clean" in result.blockers
    assert "existing_open_orders_block_first_session" in result.blockers
    assert "existing_position_blocks_first_session" in result.blockers


def test_existing_open_orders_are_no_go_unless_explicitly_allowed() -> None:
    result = _run_fake("open_orders_present")

    assert result.success is False
    assert "existing_open_orders_block_first_session" in result.blockers


def test_existing_position_is_no_go_unless_explicitly_allowed() -> None:
    result = _run_fake("open_position_present")

    assert result.success is False
    assert "existing_position_blocks_first_session" in result.blockers


def test_missing_target_symbol_is_no_go_for_actual_launch() -> None:
    result = _run_fake("missing_target_symbol")

    assert result.success is False
    assert "target_symbol_not_selected" in result.blockers
    assert "target_symbol_not_allowed" in result.blockers


def test_no_leverage_assertion_fails_when_gross_exposure_exceeds_one_x() -> None:
    result = _run_fake("leverage_rejected")

    assert result.success is False
    assert "leverage_or_margin_exposure_detected" in result.blockers
    assert "gross_exposure_exceeds_1x" in result.blockers
    assert result.packet.no_leverage_assertion is False


def test_missing_cleanup_policy_decision_is_no_go() -> None:
    result = _run_fake("missing_cleanup_policy")

    assert result.success is False
    assert "cleanup_policy_decision_required" in result.blockers
    assert result.packet.cleanup_policy_decision.mode == "missing"


def test_missing_evidence_persistence_decision_is_no_go() -> None:
    result = _run_fake("missing_evidence_persistence")

    assert result.success is False
    assert "evidence_persistence_decision_required" in result.blockers
    assert result.packet.evidence_persistence_decision.mode == "missing"


def test_write_smoke_and_execution_flags_refuse_before_broker_calls() -> None:
    client = _FakeReadOnlyClient()
    env = _safe_readonly_env() | {
        "RUN_ALPACA_PAPER_ORDER_LIFECYCLE_SMOKE": "1",
        "RUN_FIRST_CONTROLLED_PAPER_SESSION": "1",
    }
    result = run_first_controlled_paper_session_preflight(
        _real_readonly_request_m32(),
        environ=env,
        client_factory=lambda _credentials: client,
        real_external_calls_performed=False,
    )

    assert result.success is False
    assert "write_smoke_flag_must_be_disabled" in result.blockers
    assert (
        "first_session_execution_flag_must_be_disabled:RUN_FIRST_CONTROLLED_PAPER_SESSION"
        in result.blockers
    )
    assert client.read_calls == ()
    assert client.write_calls == ()


def test_launch_authorization_packet_contains_required_fields() -> None:
    result = _run_fake()
    packet = result.packet

    assert packet.authorization_packet_id
    assert packet.timestamp.tzinfo is not None
    assert packet.operator_approval_marker == MILESTONE_31_FAKE_OPERATOR_APPROVAL
    assert packet.commit_hash
    assert packet.spec_version == "Autonomous_AI_Trading_Bot_SPEC_v0.3.md"
    assert packet.latest_spec_path == "docs/app/Autonomous_AI_Trading_Bot_SPEC_v0.3.md"
    assert "docs/pre_paper_operations_gap_audit.md" in packet.doc_references
    assert packet.preflight_mode == "fake"
    assert packet.broker_endpoint_mode == "paper"
    assert packet.account_status_summary.status_summary == "reachable_paper_account"
    assert packet.clock_session_summary.status_summary == "clock_readable"
    assert packet.kill_switch_expected_state == "RUNNING"
    assert packet.prior_incident_review_marker == "prior_incidents_reviewed_clear"
    assert packet.no_schedule_assertion is True
    assert packet.no_live_assertion is True
    assert packet.no_autonomous_live_assertion is True
    assert packet.no_leverage_assertion is True
    assert packet.max_gross_exposure_assertion == 1.0
    assert packet.target_symbol_allowlist == ("AAPL",)
    assert packet.max_quantity == 1
    assert packet.max_notional_usd == 1000.0
    assert packet.cleanup_policy_decision.cleanup_forbidden_for_new_risk is True
    assert packet.alert_mode_decision.mode == "fake"
    assert packet.evidence_persistence_decision.local_evidence_packet_required is True
    assert packet.dashboard_report_visibility_decision.deployment_required is False
    assert packet.required_first_session_gates_checklist
    assert packet.go_no_go_decision == "go"
    assert packet.blockers == ()
    assert packet.actual_paper_trading_started is False
    assert packet.real_broker_writes_attempted is False
    assert packet.read_only_broker_calls_performed is False
    assert packet.real_read_only_alpaca_calls_performed is False
    assert packet.provider_ai_telegram_vercel_temporal_calls_performed is False


def test_launch_packet_artifact_is_sanitized(tmp_path: Path) -> None:
    result = _run_fake()
    packet_path = write_launch_packet_artifact(
        result,
        tmp_path / "first_controlled_paper_session_launch_packet.json",
    )
    artifact = packet_path.read_text(encoding="utf-8")

    assert '"milestone": "33"' in artifact
    assert '"actual_paper_trading_started": false' in artifact
    assert '"real_broker_writes_attempted": false' in artifact
    assert "DATABASE_URL=" not in artifact
    assert "paper-secret" not in artifact


def test_go_no_go_decision_is_deterministic() -> None:
    request = default_first_session_preflight_request(
        "dirty_target_symbol",
        mode="fake",
        operator_approval_marker=MILESTONE_31_FAKE_OPERATOR_APPROVAL,
    )

    first = run_first_controlled_paper_session_preflight(request)
    second = run_first_controlled_paper_session_preflight(request)

    assert first.packet.authorization_packet_id == second.packet.authorization_packet_id
    assert first.go_no_go_decision == second.go_no_go_decision == "no_go"
    assert first.blockers == second.blockers


def test_milestone_31_script_fake_success_and_refusals(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert (
        m31_script_main(
            [
                "--mode",
                "fake",
                "--scenario",
                "happy_path",
                "--operator-approval",
                MILESTONE_31_FAKE_OPERATOR_APPROVAL,
            ],
        )
        == 0
    )
    assert '"success": true' in capsys.readouterr().out

    assert (
        m31_script_main(
            [
                "--mode",
                "fake",
                "--scenario",
                "live_endpoint_rejected",
                "--operator-approval",
                MILESTONE_31_FAKE_OPERATOR_APPROVAL,
            ],
        )
        == 1
    )
    assert '"go_no_go_decision": "no_go"' in capsys.readouterr().out

    assert (
        m31_script_main(
            [
                "--mode",
                "fake",
                "--scenario",
                "dirty_target_symbol",
                "--operator-approval",
                MILESTONE_31_FAKE_OPERATOR_APPROVAL,
            ],
        )
        == 1
    )
    assert '"target_symbol_clean": false' in capsys.readouterr().out

    assert (
        m31_script_main(
            [
                "--mode",
                "real-read-only",
                "--operator-approval",
                MILESTONE_32_READ_ONLY_OPERATOR_APPROVAL,
            ],
        )
        == 1
    )
    assert '"read_only_broker_calls_performed": false' in capsys.readouterr().out


def test_existing_milestone_29_and_30_scripts_still_work(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert m29_script_main(["--scenario", "happy_path"]) == 0
    assert '"success": true' in capsys.readouterr().out

    assert (
        m30_script_main(
            [
                "--mode",
                "fake",
                "--scenario",
                "happy_path",
                "--operator-approval",
                MILESTONE_30_FAKE_OPERATOR_APPROVAL,
            ],
        )
        == 0
    )
    assert '"success": true' in capsys.readouterr().out


class _FakeReadOnlyClient:
    def __init__(
        self,
        *,
        open_orders: Sequence[Mapping[str, Any]] = (),
        positions: Sequence[Mapping[str, Any]] = (),
    ) -> None:
        self._open_orders = tuple(open_orders)
        self._positions = tuple(positions)
        self._read_calls: list[str] = []
        self._write_calls: list[str] = []

    @property
    def read_calls(self) -> tuple[str, ...]:
        return tuple(self._read_calls)

    @property
    def write_calls(self) -> tuple[str, ...]:
        return tuple(self._write_calls)

    def get_account(self) -> Mapping[str, Any]:
        self._read_calls.append("get_account")
        return _account_payload()

    def get_clock(self) -> Mapping[str, Any]:
        self._read_calls.append("get_clock")
        return _clock_payload()

    def list_open_orders(self) -> Sequence[Mapping[str, Any]]:
        self._read_calls.append("list_open_orders")
        return self._open_orders

    def list_positions(self) -> Sequence[Mapping[str, Any]]:
        self._read_calls.append("list_positions")
        return self._positions

    def submit_order(self, _request: Mapping[str, Any]) -> Mapping[str, Any]:
        self._write_calls.append("submit_order")
        return {}

    def cancel_order(self, _broker_order_id: str) -> Mapping[str, Any]:
        self._write_calls.append("cancel_order")
        return {}


def _account_payload() -> dict[str, Any]:
    return {
        "id": "paper-account",
        "equity": "100000",
        "cash": "90000",
        "buying_power": "100000",
        "currency": "USD",
        "as_of": "2026-05-09T14:00:00Z",
    }


def _clock_payload() -> dict[str, Any]:
    return {
        "is_open": True,
        "timestamp": "2026-05-09T14:00:00Z",
        "next_open": "2026-05-10T13:30:00Z",
        "next_close": "2026-05-09T20:00:00Z",
    }


def _order_payload(symbol: str) -> dict[str, Any]:
    return {
        "id": f"broker-order-{symbol}",
        "client_order_id": f"strategy-{symbol}-buy-20260509-1-abc123",
        "symbol": symbol,
        "side": "buy",
        "asset_class": "us_equity",
        "qty": "1",
        "filled_qty": "0",
        "type": "limit",
        "time_in_force": "day",
        "status": "accepted",
        "limit_price": "180.50",
        "submitted_at": "2026-05-09T14:00:00Z",
    }


def _position_payload(symbol: str) -> dict[str, Any]:
    return {
        "symbol": symbol,
        "asset_class": "us_equity",
        "qty": "1",
        "avg_entry_price": "180.25",
        "market_value": "180.25",
    }
