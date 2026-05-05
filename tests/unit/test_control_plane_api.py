from datetime import UTC, datetime
from pathlib import Path

from apps.api.app.control_plane import (
    CONTROL_ACTION_SIGNAL_MAP,
    dispatch_control_action,
    read_dashboard_snapshot,
    temporal_signal_for_control_action,
)
from apps.workers.app.signals import (
    ACKNOWLEDGE_INCIDENT,
    FORCE_RECONCILIATION,
    FORCE_REPORT,
    MANUAL_KILL_SWITCH,
    MANUAL_PAUSE_NEW_RISK,
    MANUAL_RESUME_AFTER_REVIEW,
)
from packages.control_plane.models import ControlActionRequest
from packages.control_plane.service import (
    FixtureControlActionDispatcher,
    FixtureDashboardReadModelProvider,
    build_unavailable_dashboard_snapshot,
)

AS_OF = datetime(2026, 5, 5, 12, 0, tzinfo=UTC)


def _request(action: str = "manual_kill_switch") -> ControlActionRequest:
    return ControlActionRequest.model_validate(
        {
            "action": action,
            "requested_by": "operator@example.com",
            "requested_at": AS_OF,
            "reason": "operator requested",
            "incident_id": "incident-1" if action == "acknowledge_incident" else None,
            "manual_review_reference": (
                "review-20260505" if action == "manual_resume_after_review" else None
            ),
            "idempotency_key": f"{action}-20260505",
        }
    )


def test_control_actions_map_to_existing_temporal_signal_names() -> None:
    assert CONTROL_ACTION_SIGNAL_MAP == {
        "manual_kill_switch": MANUAL_KILL_SWITCH,
        "manual_pause_new_risk": MANUAL_PAUSE_NEW_RISK,
        "manual_resume_after_review": MANUAL_RESUME_AFTER_REVIEW,
        "force_reconciliation": FORCE_RECONCILIATION,
        "force_report": FORCE_REPORT,
        "acknowledge_incident": ACKNOWLEDGE_INCIDENT,
    }

    for action in CONTROL_ACTION_SIGNAL_MAP:
        assert (
            temporal_signal_for_control_action(_request(action))
            == CONTROL_ACTION_SIGNAL_MAP[action]
        )


def test_backend_contract_reads_snapshot_and_dispatches_without_side_effects() -> None:
    snapshot = build_unavailable_dashboard_snapshot(as_of=AS_OF)
    provider = FixtureDashboardReadModelProvider(snapshot)
    dispatcher = FixtureControlActionDispatcher(CONTROL_ACTION_SIGNAL_MAP)
    request = _request("manual_pause_new_risk")

    read_result = read_dashboard_snapshot(provider)
    receipt = dispatch_control_action(request, dispatcher)

    assert read_result == snapshot
    assert receipt.status == "accepted"
    assert receipt.temporal_signal_name == MANUAL_PAUSE_NEW_RISK
    assert receipt.broker_calls_performed is False
    assert receipt.orders_created is False
    assert receipt.risk_limits_modified is False
    assert receipt.autonomy_level_modified is False


def test_backend_control_contract_has_no_broker_adapter_imports() -> None:
    source = Path("apps/api/app/control_plane.py").read_text(encoding="utf-8")

    assert "packages.broker" not in source
    assert "BrokerAdapter" not in source
    assert "submit_order" not in source
