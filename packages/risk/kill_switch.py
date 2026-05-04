"""Kill-switch state helpers.

These helpers model control state only. They do not cancel orders, flatten positions, or call a
broker.
"""

from __future__ import annotations

from packages.risk.models import KillSwitchSnapshot


def running_state(reason: str = "manual_rearm_complete") -> KillSwitchSnapshot:
    return KillSwitchSnapshot(
        state="RUNNING",
        reason=reason,
        new_risk_allowed=True,
        risk_reducing_exits_allowed=True,
    )


def pause_new_risk(reason: str) -> KillSwitchSnapshot:
    return KillSwitchSnapshot(
        state="PAUSED_NEW_RISK",
        reason=reason,
        new_risk_allowed=False,
        risk_reducing_exits_allowed=True,
    )


def pause_all_autonomous_actions(reason: str) -> KillSwitchSnapshot:
    return KillSwitchSnapshot(
        state="PAUSED_ALL_AUTONOMOUS_ACTIONS",
        reason=reason,
        new_risk_allowed=False,
        risk_reducing_exits_allowed=False,
    )


def request_force_flat(reason: str) -> KillSwitchSnapshot:
    return KillSwitchSnapshot(
        state="FORCE_FLAT_REQUESTED",
        reason=reason,
        new_risk_allowed=False,
        risk_reducing_exits_allowed=True,
    )


def require_manual_review(reason: str) -> KillSwitchSnapshot:
    return KillSwitchSnapshot(
        state="MANUAL_REVIEW_REQUIRED",
        reason=reason,
        new_risk_allowed=False,
        risk_reducing_exits_allowed=True,
    )


def new_risk_allowed(snapshot: KillSwitchSnapshot) -> bool:
    return snapshot.state == "RUNNING" and snapshot.new_risk_allowed


def risk_reducing_exits_allowed(snapshot: KillSwitchSnapshot) -> bool:
    return snapshot.risk_reducing_exits_allowed

