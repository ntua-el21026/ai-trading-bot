"""Control-plane service contracts and fixture read models."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Protocol

from packages.control_plane.models import (
    ControlActionReceipt,
    ControlActionRequest,
    DashboardSnapshot,
    KillSwitchStateView,
    ReconciliationStatusView,
    RiskStatusView,
    SystemStateView,
)


class DashboardReadModelProvider(Protocol):
    """Read-only dashboard data boundary."""

    def snapshot(self) -> DashboardSnapshot:
        """Return a read-only dashboard snapshot."""


class ControlActionDispatcher(Protocol):
    """Server-side control action dispatch boundary."""

    def dispatch(self, request: ControlActionRequest) -> ControlActionReceipt:
        """Dispatch a safe control action through a backend boundary."""


class FixtureDashboardReadModelProvider:
    """Non-production read-model provider for tests and local contracts."""

    def __init__(self, snapshot: DashboardSnapshot | None = None) -> None:
        self._snapshot = snapshot or build_unavailable_dashboard_snapshot()

    def snapshot(self) -> DashboardSnapshot:
        return self._snapshot


class FixtureControlActionDispatcher:
    """Non-production dispatcher that records signal intent without side effects."""

    def __init__(self, signal_map: Mapping[str, str]) -> None:
        self._signal_map = dict(signal_map)

    def dispatch(self, request: ControlActionRequest) -> ControlActionReceipt:
        signal_name = self._signal_map[request.action]
        return ControlActionReceipt(
            request=request,
            status="accepted",
            temporal_signal_name=signal_name,
            dispatched_at=None,
            message="Control action accepted by fixture dispatcher; no Temporal call performed.",
        )


def build_unavailable_dashboard_snapshot(
    *,
    as_of: datetime | None = None,
) -> DashboardSnapshot:
    timestamp = as_of or datetime.now(UTC)
    return DashboardSnapshot(
        system_state=SystemStateView(
            environment="paper",
            dry_run=True,
            live_trading_enabled=False,
            autonomous_execution_enabled=False,
            autonomy_level=2,
            kill_switch_enabled=True,
            as_of=timestamp,
            data_source="unavailable",
        ),
        kill_switch=KillSwitchStateView(
            state="PAUSED_NEW_RISK",
            new_risk_allowed=False,
            risk_reducing_exits_allowed=True,
            reason="dashboard_read_model_unavailable",
            data_source="unavailable",
        ),
        risk_status=RiskStatusView(
            new_risk_allowed=False,
            broker_reconciliation_clean=False,
            risk_checks_passing=False,
            current_gross_exposure_pct=0.0,
            current_deployable_capital_pct=0.0,
            daily_loss_pct=0.0,
            weekly_loss_pct=0.0,
            monthly_loss_pct=0.0,
            data_source="unavailable",
        ),
        reconciliation_status=ReconciliationStatusView(
            clean=False,
            last_checked_at=None,
            severity="warning",
            mismatch_count=0,
            pause_new_risk_recommended=True,
            data_source="unavailable",
        ),
    )
