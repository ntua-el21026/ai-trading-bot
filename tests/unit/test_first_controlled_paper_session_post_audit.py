from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from packages.broker.alpaca import ALPACA_PAPER_BASE_URL, AlpacaPaperAdapter
from packages.broker.fakes import DEFAULT_AS_OF, FakeAlpacaClient
from packages.core.config import load_app_config
from packages.paper import (
    M34_RESULT_EVIDENCE_PATH,
    M35D_POST_SESSION_AUDIT_EVIDENCE_PATH,
    PostSessionAuditRequest,
    audit_m35c_result_packet,
    audit_m35d_post_session_audit_packet,
    default_first_paper_session_execution_request,
    run_first_controlled_paper_session_hold_decision,
    run_first_controlled_paper_session_post_session_audit,
    write_hold_decision_artifact,
    write_post_session_audit_artifact,
)
from packages.paper.execution import (
    MILESTONE_34_FAKE_OPERATOR_APPROVAL,
    _run_adapter_execution,
)


def test_m35c_result_packet_auditor_detects_safe_incident_status() -> None:
    audit, packet = audit_m35c_result_packet(M34_RESULT_EVIDENCE_PATH)

    assert packet is not None
    assert audit.parseable is True
    assert audit.milestone == "35C"
    assert audit.status == "incident"
    assert audit.actual_paper_trading_started is True
    assert audit.real_broker_orders_submitted is True
    assert audit.target_symbol == "AAPL"
    assert audit.entry_order_status == "filled"
    assert audit.fill_status == "filled"
    assert audit.filled_quantity == 1.0
    assert audit.fill_client_order_id_missing_incident_detected is True
    assert audit.recovery_stop_verified is True
    assert audit.post_session_no_go is True
    assert audit.blockers == ()


def test_fake_post_session_audit_recommends_hold_and_blocks_repetition() -> None:
    result = run_first_controlled_paper_session_post_session_audit(
        PostSessionAuditRequest(mode="fake", scenario_id="protected_position")
    )

    assert result.audit_completed is True
    assert result.go_no_go == "no_go"
    assert result.packet.cleanup_hold_decision_recommendation == (
        "HOLD_PROTECTED_POSITION_UNTIL_NEXT_REVIEW"
    )
    assert result.packet.current_broker_state.target_position_quantity == 1.0
    assert result.packet.current_broker_state.protective_stop_verified is True
    assert result.packet.current_broker_state.reconciliation_summary == (
        "protected_position_reconciled_for_hold"
    )
    assert result.broker_writes_performed_in_this_milestone is False
    assert result.packet.repeated_session_go_no_go == "no_go"


def test_m35d_post_session_audit_packet_parser_validates_hold_recommendation() -> None:
    audit = audit_m35d_post_session_audit_packet(M35D_POST_SESSION_AUDIT_EVIDENCE_PATH)

    assert audit.parseable is True
    assert audit.milestone == "35D"
    assert audit.audit_completed is True
    assert audit.recommendation == "HOLD_PROTECTED_POSITION_UNTIL_NEXT_REVIEW"
    assert audit.repeated_session_go_no_go == "no_go"
    assert audit.broker_writes_performed_in_m35d is False
    assert audit.protected_position_verified is True
    assert audit.blockers == ()


def test_hold_decision_packet_records_operator_decision_and_blocks_repetition() -> None:
    result = run_first_controlled_paper_session_hold_decision(
        PostSessionAuditRequest(mode="fake", scenario_id="protected_position")
    )

    assert result.hold_confirmed is True
    assert result.go_no_go == "no_go"
    assert result.operator_decision == "HOLD_PROTECTED_POSITION_UNTIL_NEXT_REVIEW"
    assert result.packet.operator_decision == "HOLD_PROTECTED_POSITION_UNTIL_NEXT_REVIEW"
    assert result.packet.cleanup_hold_recommendation == "CONTINUE_HOLD_UNTIL_NEXT_REVIEW"
    assert result.packet.repeated_session_go_no_go == "no_go"
    assert result.packet.frozen_validation_started is False
    assert result.packet.cleanup_performed is False
    assert result.packet.flatten_performed is False
    assert result.packet.cancel_performed is False
    assert result.packet.broker_writes_performed_in_this_milestone is False
    assert "repeated_sessions_blocked_until_later_audit_decision" in result.blockers


def test_hold_decision_missing_stop_is_no_go_and_requests_stop_repair() -> None:
    result = run_first_controlled_paper_session_hold_decision(
        PostSessionAuditRequest(mode="fake", scenario_id="missing_stop")
    )

    assert result.hold_confirmed is False
    assert result.go_no_go == "no_go"
    assert result.packet.cleanup_hold_recommendation == "REQUEST_OPERATOR_APPROVED_STOP_REPAIR"
    assert "aapl_protective_stop_not_verified" in result.blockers
    assert result.packet.broker_writes_performed_in_this_milestone is False


def test_hold_decision_unexpected_position_is_no_go() -> None:
    result = run_first_controlled_paper_session_hold_decision(
        PostSessionAuditRequest(mode="fake", scenario_id="unexpected_position")
    )

    assert result.hold_confirmed is False
    assert result.packet.cleanup_hold_recommendation == "MANUAL_BROKER_REVIEW_REQUIRED"
    assert "unexpected_positions_present" in result.blockers
    assert result.packet.broker_writes_performed_in_this_milestone is False


def test_hold_decision_unexpected_order_is_no_go() -> None:
    result = run_first_controlled_paper_session_hold_decision(
        PostSessionAuditRequest(mode="fake", scenario_id="unexpected_order")
    )

    assert result.hold_confirmed is False
    assert result.packet.cleanup_hold_recommendation == "MANUAL_BROKER_REVIEW_REQUIRED"
    assert "unexpected_open_orders_present" in result.blockers
    assert result.packet.broker_writes_performed_in_this_milestone is False


def test_hold_decision_packet_excludes_secret_values(tmp_path: Path) -> None:
    result = run_first_controlled_paper_session_hold_decision(
        PostSessionAuditRequest(mode="fake", scenario_id="protected_position")
    )
    path = write_hold_decision_artifact(result, tmp_path / "hold.json")
    payload = path.read_text(encoding="utf-8")

    assert "paper-secret" not in payload
    assert "paper-key" not in payload
    assert "postgres://" not in payload
    assert "sk-" not in payload
    hold_payload = json.loads(payload)["hold_decision"]
    assert hold_payload["operator_decision"] == "HOLD_PROTECTED_POSITION_UNTIL_NEXT_REVIEW"
    assert hold_payload["broker_writes_performed_in_this_milestone"] is False


def test_fake_post_session_audit_missing_stop_requests_stop_repair() -> None:
    result = run_first_controlled_paper_session_post_session_audit(
        PostSessionAuditRequest(mode="fake", scenario_id="missing_stop")
    )

    assert result.audit_completed is True
    assert result.packet.cleanup_hold_decision_recommendation == (
        "REQUEST_OPERATOR_APPROVED_STOP_REPAIR"
    )
    assert result.packet.current_broker_state.target_position_open is True
    assert result.packet.current_broker_state.protective_stop_verified is False
    assert "protective_stop_missing_or_unverified" in result.blockers


def test_post_session_audit_packet_excludes_secret_values(tmp_path: Path) -> None:
    result = run_first_controlled_paper_session_post_session_audit(
        PostSessionAuditRequest(mode="fake", scenario_id="protected_position")
    )
    path = write_post_session_audit_artifact(result, tmp_path / "audit.json")
    payload = path.read_text(encoding="utf-8")

    assert "paper-secret" not in payload
    assert "paper-key" not in payload
    assert "postgres://" not in payload
    assert "sk-" not in payload
    audit_payload = json.loads(payload)["post_session_audit"]
    assert audit_payload["broker_writes_performed_in_this_milestone"] is False


def test_real_read_only_post_audit_stub_never_calls_write_methods() -> None:
    client = _ReadOnlyGuardClient()

    def factory(*_args: Any, **_kwargs: Any) -> _ReadOnlyGuardClient:
        return client

    result = run_first_controlled_paper_session_post_session_audit(
        PostSessionAuditRequest(
            mode="real-read-only",
            scenario_id="protected_position",
            confirm_paper_endpoint=True,
            confirm_no_broker_writes=True,
            confirm_no_live_trading=True,
            confirm_no_autonomous_live=True,
            confirm_no_schedules=True,
            confirm_no_leverage=True,
        ),
        environ={
            "ALPACA_API_KEY": "placeholder-key",
            "ALPACA_SECRET_KEY": "placeholder-secret",
            "ALPACA_BASE_URL": ALPACA_PAPER_BASE_URL,
            "RUN_ALPACA_PAPER_SMOKE": "1",
            "ALPACA_PAPER_SMOKE_CONFIRM": "READ_ONLY_PAPER_ACCOUNT",
        },
        client_factory=factory,
    )

    assert result.audit_completed is True
    assert result.real_read_only_calls_performed is True
    assert result.broker_writes_performed_in_this_milestone is False
    assert client.submit_order_calls == 0
    assert client.cancel_order_calls == 0
    assert result.packet.current_broker_state.protective_stop_verified is True


def test_real_read_only_hold_decision_stub_never_calls_write_methods() -> None:
    client = _ReadOnlyGuardClient()

    def factory(*_args: Any, **_kwargs: Any) -> _ReadOnlyGuardClient:
        return client

    result = run_first_controlled_paper_session_hold_decision(
        PostSessionAuditRequest(
            mode="real-read-only",
            scenario_id="protected_position",
            confirm_paper_endpoint=True,
            confirm_no_broker_writes=True,
            confirm_no_live_trading=True,
            confirm_no_autonomous_live=True,
            confirm_no_schedules=True,
            confirm_no_leverage=True,
        ),
        environ={
            "ALPACA_API_KEY": "placeholder-key",
            "ALPACA_SECRET_KEY": "placeholder-secret",
            "ALPACA_BASE_URL": ALPACA_PAPER_BASE_URL,
            "RUN_ALPACA_PAPER_SMOKE": "1",
            "ALPACA_PAPER_SMOKE_CONFIRM": "READ_ONLY_PAPER_ACCOUNT",
        },
        client_factory=factory,
    )

    assert result.hold_confirmed is True
    assert result.go_no_go == "no_go"
    assert result.real_read_only_calls_performed is True
    assert result.broker_writes_performed_in_this_milestone is False
    assert client.submit_order_calls == 0
    assert client.cancel_order_calls == 0
    assert result.packet.cleanup_hold_recommendation == "CONTINUE_HOLD_UNTIL_NEXT_REVIEW"
    assert result.packet.current_broker_state.protective_stop_verified is True
    assert result.packet.frozen_validation_started is False


def test_execution_path_continues_to_stop_when_fill_metadata_is_malformed() -> None:
    app_config = load_app_config()
    request = default_first_paper_session_execution_request(
        "happy_path",
        mode="fake-real-paper",
        operator_approval_marker=MILESTONE_34_FAKE_OPERATOR_APPROVAL,
        target_symbol="AAPL",
        max_quantity=1,
        max_notional_usd=350.0,
        limit_price=330.0,
    )
    client = _MalformedFillClient(
        submit_outcomes=(("filled", 1.0), ("accepted", 0.0)),
        mutate_positions_on_submit=True,
    )
    adapter = AlpacaPaperAdapter(
        system_config=app_config.system,
        execution_config=app_config.execution,
        client=client,
        credentials=None,
        run_mode="test",
    )

    result = _run_adapter_execution(
        request=request,
        app_config=app_config,
        adapter=adapter,
        client=client,
        real_broker=False,
        real_external_calls_performed=False,
        sleeper=lambda _seconds: None,
        clock=lambda: 0.0,
    )

    assert result.status == "incident"
    assert "fill_metadata_unavailable_recent_fills_unparseable" in result.result_packet.incidents
    assert result.result_packet.protective_stop_verification_result == "verified"
    assert result.real_broker_writes_attempted is False
    assert [order["type"] for order in client.submitted_order_requests] == ["limit", "stop"]


class _MalformedFillClient(FakeAlpacaClient):
    def list_fills(self) -> Sequence[Mapping[str, Any]]:
        return (
            {
                "order_id": "paper-order-1",
                "symbol": "AAPL",
                "side": "buy",
                "qty": "1",
                "transaction_time": DEFAULT_AS_OF.isoformat().replace("+00:00", "Z"),
            },
        )


class _ReadOnlyGuardClient:
    def __init__(self) -> None:
        self.submit_order_calls = 0
        self.cancel_order_calls = 0
        self._orders = {
            "00000000-0000-4000-8000-900000000006": _order_payload(
                broker_order_id="00000000-0000-4000-8000-900000000006",
                client_order_id="first-session-AAPL-20000101T000000Z-00000001",
                order_type="limit",
                status="filled",
                side="buy",
                filled_qty="1",
            ),
            "00000000-0000-4000-8000-900000000008": _order_payload(
                broker_order_id="00000000-0000-4000-8000-900000000008",
                client_order_id="first-session-AAPL-safety-stop-20000101T000000Z-00000003-stop",
                order_type="stop",
                status="new",
                side="sell",
                stop_price="165",
            ),
        }

    def get_account(self) -> Mapping[str, Any]:
        return {
            "id": "redacted-test-account",
            "equity": "100000",
            "cash": "90000",
            "buying_power": "180000",
            "currency": "USD",
            "as_of": DEFAULT_AS_OF.isoformat().replace("+00:00", "Z"),
        }

    def list_open_orders(self) -> Sequence[Mapping[str, Any]]:
        return (self._orders["00000000-0000-4000-8000-900000000008"],)

    def get_order_by_id(self, broker_order_id: str) -> Mapping[str, Any] | None:
        return self._orders.get(broker_order_id)

    def get_order_by_client_order_id(self, client_order_id: str) -> Mapping[str, Any] | None:
        for order in self._orders.values():
            if order["client_order_id"] == client_order_id:
                return order
        return None

    def submit_order(self, _request: Mapping[str, Any]) -> Mapping[str, Any]:
        self.submit_order_calls += 1
        raise AssertionError("post-session audit must not submit orders")

    def cancel_order(self, _broker_order_id: str) -> Mapping[str, Any]:
        self.cancel_order_calls += 1
        raise AssertionError("post-session audit must not cancel orders")

    def list_fills(self) -> Sequence[Mapping[str, Any]]:
        return ()

    def list_positions(self) -> Sequence[Mapping[str, Any]]:
        return (
            {
                "symbol": "AAPL",
                "asset_class": "equity",
                "qty": "1",
                "avg_entry_price": "290.94",
                "market_value": "290.94",
                "opened_at": DEFAULT_AS_OF.isoformat().replace("+00:00", "Z"),
            },
        )

    def get_position(self, _symbol: str) -> Mapping[str, Any] | None:
        return self.list_positions()[0]

    def consume_trade_updates(self) -> Sequence[Mapping[str, Any]]:
        return ()

    def get_clock(self) -> Mapping[str, Any]:
        return {
            "is_open": True,
            "timestamp": DEFAULT_AS_OF.isoformat().replace("+00:00", "Z"),
            "next_open": DEFAULT_AS_OF.isoformat().replace("+00:00", "Z"),
            "next_close": DEFAULT_AS_OF.replace(hour=21, minute=0)
            .isoformat()
            .replace("+00:00", "Z"),
        }


def _order_payload(
    *,
    broker_order_id: str,
    client_order_id: str,
    order_type: str,
    status: str,
    side: str,
    filled_qty: str = "0",
    stop_price: str | None = None,
) -> dict[str, Any]:
    payload = {
        "id": broker_order_id,
        "client_order_id": client_order_id,
        "symbol": "AAPL",
        "side": side,
        "asset_class": "equity",
        "qty": "1",
        "filled_qty": filled_qty,
        "type": order_type,
        "time_in_force": "gtc" if order_type == "stop" else "day",
        "status": status,
        "submitted_at": DEFAULT_AS_OF.isoformat().replace("+00:00", "Z"),
    }
    if order_type == "limit":
        payload["limit_price"] = "330"
    if stop_price is not None:
        payload["stop_price"] = stop_price
    return payload
