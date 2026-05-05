from datetime import UTC, datetime
from typing import get_args

import pytest
from pydantic import ValidationError

from packages.control_plane.models import (
    ORDER_ENTRY_CONTROL_ACTIONS,
    ControlActionReceipt,
    ControlActionRequest,
    ControlActionType,
    KillSwitchStateView,
    OrderView,
)
from packages.control_plane.service import build_unavailable_dashboard_snapshot

AS_OF = datetime(2026, 5, 5, 12, 0, tzinfo=UTC)


def _request(
    action: ControlActionType = "manual_pause_new_risk",
    **updates: object,
) -> ControlActionRequest:
    data: dict[str, object] = {
        "action": action,
        "requested_by": "operator@example.com",
        "requested_at": AS_OF,
        "reason": "operator requested",
        "idempotency_key": f"{action}-20260505",
    }
    data.update(updates)
    return ControlActionRequest.model_validate(data)


def test_dashboard_snapshot_defaults_to_safe_unavailable_state() -> None:
    snapshot = build_unavailable_dashboard_snapshot(as_of=AS_OF)

    assert snapshot.system_state.environment == "paper"
    assert snapshot.system_state.live_trading_enabled is False
    assert snapshot.system_state.autonomous_execution_enabled is False
    assert snapshot.kill_switch.state == "PAUSED_NEW_RISK"
    assert snapshot.kill_switch.new_risk_allowed is False
    assert snapshot.risk_status.new_risk_allowed is False
    assert snapshot.reconciliation_status.pause_new_risk_recommended is True


def test_dashboard_read_models_validate_safety_invariants() -> None:
    with pytest.raises(ValidationError, match="non-running"):
        KillSwitchStateView(
            state="PAUSED_NEW_RISK",
            new_risk_allowed=True,
            risk_reducing_exits_allowed=True,
        )

    with pytest.raises(ValidationError, match="filled_quantity"):
        OrderView(
            client_order_id="client-1",
            symbol="AAPL",
            side="buy",
            order_type="limit",
            status="accepted",
            quantity=10,
            filled_quantity=11,
        )


def test_control_action_request_shapes_are_auditable_and_safe() -> None:
    kill_switch = _request("manual_kill_switch")
    pause = _request("manual_pause_new_risk")
    force_reconciliation = _request("force_reconciliation")
    force_report = _request("force_report")
    acknowledge = _request("acknowledge_incident", incident_id="incident-1")
    resume = _request(
        "manual_resume_after_review",
        manual_review_reference="review-20260505",
    )

    assert kill_switch.idempotency_key
    assert pause.reason == "operator requested"
    assert force_reconciliation.action == "force_reconciliation"
    assert force_report.action == "force_report"
    assert acknowledge.incident_id == "incident-1"
    assert resume.manual_review_reference == "review-20260505"


def test_control_actions_reject_missing_required_review_or_incident_fields() -> None:
    with pytest.raises(ValidationError, match="manual_review_reference"):
        _request("manual_resume_after_review")

    with pytest.raises(ValidationError, match="incident_id"):
        _request("acknowledge_incident")


def test_no_order_entry_control_action_exists() -> None:
    action_names = set(get_args(ControlActionType))

    assert action_names.isdisjoint(ORDER_ENTRY_CONTROL_ACTIONS)
    assert "submit_order" not in action_names
    assert "natural_language_order" not in action_names


def test_control_action_receipt_cannot_report_broker_or_order_side_effects() -> None:
    request = _request()

    with pytest.raises(ValidationError, match="broker calls"):
        ControlActionReceipt(
            request=request,
            status="accepted",
            temporal_signal_name="manual_pause_new_risk",
            message="invalid",
            broker_calls_performed=True,
        )

    with pytest.raises(ValidationError, match="create orders"):
        ControlActionReceipt(
            request=request,
            status="accepted",
            temporal_signal_name="manual_pause_new_risk",
            message="invalid",
            orders_created=True,
        )
