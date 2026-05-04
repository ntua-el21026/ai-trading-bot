"""Temporal signal contract names required by the latest spec."""

from __future__ import annotations

from dataclasses import dataclass

MANUAL_KILL_SWITCH = "manual_kill_switch"
MANUAL_PAUSE_NEW_RISK = "manual_pause_new_risk"
MANUAL_RESUME_AFTER_REVIEW = "manual_resume_after_review"
FORCE_RECONCILIATION = "force_reconciliation"
FORCE_REPORT = "force_report"
APPROVE_LEVEL_CHANGE = "approve_level_change"
ACKNOWLEDGE_INCIDENT = "acknowledge_incident"

SIGNAL_NAMES: tuple[str, ...] = (
    MANUAL_KILL_SWITCH,
    MANUAL_PAUSE_NEW_RISK,
    MANUAL_RESUME_AFTER_REVIEW,
    FORCE_RECONCILIATION,
    FORCE_REPORT,
    APPROVE_LEVEL_CHANGE,
    ACKNOWLEDGE_INCIDENT,
)


@dataclass(frozen=True)
class SignalContract:
    name: str
    purpose: str


SIGNAL_CONTRACTS: dict[str, SignalContract] = {
    MANUAL_KILL_SWITCH: SignalContract(
        name=MANUAL_KILL_SWITCH,
        purpose="Transition the system into kill-switch state and block new risk.",
    ),
    MANUAL_PAUSE_NEW_RISK: SignalContract(
        name=MANUAL_PAUSE_NEW_RISK,
        purpose="Pause new-risk entries while preserving risk-reducing exits.",
    ),
    MANUAL_RESUME_AFTER_REVIEW: SignalContract(
        name=MANUAL_RESUME_AFTER_REVIEW,
        purpose="Resume after documented manual review and re-arm approval.",
    ),
    FORCE_RECONCILIATION: SignalContract(
        name=FORCE_RECONCILIATION,
        purpose="Request immediate broker/internal state reconciliation.",
    ),
    FORCE_REPORT: SignalContract(
        name=FORCE_REPORT,
        purpose="Request immediate report generation.",
    ),
    APPROVE_LEVEL_CHANGE: SignalContract(
        name=APPROVE_LEVEL_CHANGE,
        purpose="Record manual approval for a future autonomy or risk-level change.",
    ),
    ACKNOWLEDGE_INCIDENT: SignalContract(
        name=ACKNOWLEDGE_INCIDENT,
        purpose="Record manual acknowledgement of an incident.",
    ),
}
