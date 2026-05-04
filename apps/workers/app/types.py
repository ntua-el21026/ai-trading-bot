"""Serializable contracts shared by Temporal workflow skeletons and activities."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class WorkflowRunInput:
    """Minimal deterministic input used by skeleton workflows."""

    reason: str = "scheduled"
    request_id: str | None = None


@dataclass(frozen=True)
class WorkflowStatus:
    """Small workflow status snapshot suitable for Temporal queries."""

    workflow_name: str
    status: str
    details: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class ActivityPlaceholderInput:
    """Placeholder activity input that carries no executable trading instruction."""

    workflow_name: str
    purpose: str


@dataclass(frozen=True)
class ActivityPlaceholderResult:
    """Placeholder activity result proving no external side effect was performed."""

    activity_name: str
    status: str = "placeholder"
    external_calls_performed: bool = False
    details: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class KillSwitchState:
    """Kill-switch state contract for workflow queries."""

    state: str = "RUNNING"
    new_risk_allowed: bool = True
    risk_reducing_exits_allowed: bool = True
    reason: str = "initialized"
