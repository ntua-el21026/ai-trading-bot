"""Server-side control-plane contracts.

This module intentionally defines backend boundaries only. It does not expose browser-side Temporal
access, broker adapters, AI/news providers, or order-entry actions.
"""

from __future__ import annotations

from apps.workers.app.signals import (
    ACKNOWLEDGE_INCIDENT,
    FORCE_RECONCILIATION,
    FORCE_REPORT,
    MANUAL_KILL_SWITCH,
    MANUAL_PAUSE_NEW_RISK,
    MANUAL_RESUME_AFTER_REVIEW,
)
from packages.control_plane.models import (
    ControlActionReceipt,
    ControlActionRequest,
    DashboardSnapshot,
)
from packages.control_plane.service import (
    ControlActionDispatcher,
    DashboardReadModelProvider,
    LedgerDashboardReadModelProvider,
)
from packages.ledger.repositories import SQLiteLedgerRepository

CONTROL_ACTION_SIGNAL_MAP: dict[str, str] = {
    "manual_kill_switch": MANUAL_KILL_SWITCH,
    "manual_pause_new_risk": MANUAL_PAUSE_NEW_RISK,
    "manual_resume_after_review": MANUAL_RESUME_AFTER_REVIEW,
    "force_reconciliation": FORCE_RECONCILIATION,
    "force_report": FORCE_REPORT,
    "acknowledge_incident": ACKNOWLEDGE_INCIDENT,
}


def read_dashboard_snapshot(provider: DashboardReadModelProvider) -> DashboardSnapshot:
    """Read a dashboard snapshot from a backend read-model provider."""

    return provider.snapshot()


def read_ledger_dashboard_snapshot(repository: SQLiteLedgerRepository) -> DashboardSnapshot:
    """Read a dashboard snapshot from the ledger repository boundary."""

    return LedgerDashboardReadModelProvider(repository).snapshot()


def dispatch_control_action(
    request: ControlActionRequest,
    dispatcher: ControlActionDispatcher,
) -> ControlActionReceipt:
    """Dispatch a safe control-plane action through a server-side boundary."""

    return dispatcher.dispatch(request)


def temporal_signal_for_control_action(request: ControlActionRequest) -> str:
    """Map an auditable control request to an existing Temporal signal contract name."""

    return CONTROL_ACTION_SIGNAL_MAP[request.action]
