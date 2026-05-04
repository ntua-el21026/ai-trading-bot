import pytest
from pydantic import ValidationError

from packages.risk.kill_switch import (
    new_risk_allowed,
    pause_all_autonomous_actions,
    pause_new_risk,
    request_force_flat,
    require_manual_review,
    risk_reducing_exits_allowed,
    running_state,
)
from packages.risk.models import KillSwitchSnapshot


def test_running_state_allows_new_risk_and_exits() -> None:
    snapshot = running_state()

    assert new_risk_allowed(snapshot) is True
    assert risk_reducing_exits_allowed(snapshot) is True


def test_pause_new_risk_blocks_entries_but_preserves_risk_reducing_exits() -> None:
    snapshot = pause_new_risk("operator_pause")

    assert snapshot.state == "PAUSED_NEW_RISK"
    assert new_risk_allowed(snapshot) is False
    assert risk_reducing_exits_allowed(snapshot) is True


def test_force_flat_and_manual_review_block_new_risk() -> None:
    assert new_risk_allowed(request_force_flat("stop_failure")) is False
    assert risk_reducing_exits_allowed(request_force_flat("stop_failure")) is True
    assert new_risk_allowed(require_manual_review("mismatch")) is False


def test_pause_all_autonomous_actions_blocks_risk_reducing_exits_too() -> None:
    snapshot = pause_all_autonomous_actions("control_failure")

    assert new_risk_allowed(snapshot) is False
    assert risk_reducing_exits_allowed(snapshot) is False


def test_non_running_state_cannot_allow_new_risk() -> None:
    with pytest.raises(ValidationError, match="cannot allow new risk"):
        KillSwitchSnapshot(
            state="PAUSED_NEW_RISK",
            reason="invalid",
            new_risk_allowed=True,
            risk_reducing_exits_allowed=True,
        )

