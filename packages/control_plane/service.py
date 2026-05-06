"""Control-plane service contracts and fixture read models."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Literal, Protocol

from packages.control_plane.models import (
    AIResearchOutputView,
    CandidateSignalView,
    ControlActionReceipt,
    ControlActionRequest,
    DashboardSeverity,
    DashboardSnapshot,
    ExecutionIntentView,
    IncidentView,
    KillSwitchStateView,
    OrderView,
    PositionView,
    ReconciliationStatusView,
    ReportSummaryView,
    RiskStatusView,
    SystemStateView,
)
from packages.core.config import AppConfig, load_app_config
from packages.ledger.repositories import SQLiteLedgerRepository


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


class LedgerDashboardReadModelProvider:
    """Read dashboard models from the local ledger repository.

    This provider performs repository reads only. It does not call Temporal, broker adapters,
    AI/news providers, alert adapters, frontend code, or environment secret sources.
    """

    def __init__(
        self,
        repository: SQLiteLedgerRepository,
        *,
        config: AppConfig | None = None,
        as_of: datetime | None = None,
    ) -> None:
        self._repository = repository
        self._config = config or load_app_config()
        self._as_of = as_of

    def snapshot(self) -> DashboardSnapshot:
        as_of = self._as_of or datetime.now(UTC)
        latest_reconciliation = self._repository.get_latest_broker_reconciliation()
        incidents = self._repository.list_recent_incidents(limit=25)
        active_intents = self._repository.list_active_execution_intents(limit=100)
        open_orders = self._repository.list_open_orders(limit=100)
        open_positions = self._repository.list_open_positions(limit=100)
        candidates = self._repository.list_trade_candidates(limit=50)
        ai_outputs = self._repository.list_ai_research_outputs(limit=50)
        reports = self._repository.list_reports(limit=20)
        recent_risk_checks = self._repository.list_recent_risk_checks(limit=50)

        reconciliation_clean = (
            latest_reconciliation is not None and latest_reconciliation.status == "clean"
        )
        risk_checks_passing = bool(recent_risk_checks) and all(
            check.passed for check in recent_risk_checks
        )
        critical_incidents = [event for event in incidents if event.severity == "critical"]

        return DashboardSnapshot(
            system_state=SystemStateView(
                environment=self._config.system.environment,
                dry_run=self._config.system.dry_run,
                live_trading_enabled=self._config.system.live_trading_enabled,
                autonomous_execution_enabled=self._config.system.autonomous_execution_enabled,
                autonomy_level=self._config.system.autonomy_level,
                kill_switch_enabled=self._config.system.kill_switch_enabled,
                as_of=as_of,
                data_source="database_read_model",
            ),
            kill_switch=KillSwitchStateView(
                state="PAUSED_NEW_RISK" if critical_incidents else "RUNNING",
                new_risk_allowed=not critical_incidents and reconciliation_clean,
                risk_reducing_exits_allowed=True,
                reason="critical_incident" if critical_incidents else None,
                data_source="database_read_model",
            ),
            risk_status=RiskStatusView(
                new_risk_allowed=False,
                broker_reconciliation_clean=reconciliation_clean,
                risk_checks_passing=risk_checks_passing,
                current_gross_exposure_pct=0.0,
                current_deployable_capital_pct=0.0,
                daily_loss_pct=0.0,
                weekly_loss_pct=0.0,
                monthly_loss_pct=0.0,
                data_source="database_read_model",
            ),
            reconciliation_status=ReconciliationStatusView(
                clean=reconciliation_clean,
                last_checked_at=(
                    None if latest_reconciliation is None else latest_reconciliation.created_at
                ),
                severity=_reconciliation_severity(
                    latest_reconciliation is not None,
                    reconciliation_clean,
                ),
                mismatch_count=(
                    0 if latest_reconciliation is None else len(latest_reconciliation.mismatches)
                ),
                pause_new_risk_recommended=not reconciliation_clean,
                data_source="database_read_model",
            ),
            active_execution_intents=tuple(
                ExecutionIntentView(
                    intent_id=intent.execution_intent_id,
                    symbol=intent.symbol,
                    side=intent.side,
                    quantity=float(intent.quantity),
                    status=intent.status,
                    expires_at=intent.expires_at,
                    data_source="database_read_model",
                )
                for intent in active_intents
            ),
            open_orders=tuple(
                OrderView(
                    client_order_id=order.client_order_id,
                    broker_order_id=order.broker_order_id,
                    symbol=order.symbol,
                    side=order.side,
                    order_type=order.order_type,
                    status=order.status,
                    quantity=order.quantity,
                    filled_quantity=float(order.raw_broker_payload.get("filled_quantity", 0.0)),
                    submitted_at=order.created_at,
                    data_source="database_read_model",
                )
                for order in open_orders
            ),
            open_positions=tuple(
                PositionView(
                    symbol=position.symbol,
                    quantity=position.quantity,
                    avg_entry_price=position.average_entry_price,
                    protective_stop_confirmed=position.protective_stop_order_id is not None,
                    opened_at=position.opened_at,
                    data_source="database_read_model",
                )
                for position in open_positions
            ),
            recent_incidents=tuple(
                IncidentView(
                    incident_id=event.event_id,
                    severity=event.severity,
                    status="acknowledged" if event.acknowledged_at else "open",
                    message=event.message,
                    created_at=event.created_at,
                    acknowledged_at=event.acknowledged_at,
                    data_source="database_read_model",
                )
                for event in incidents
            ),
            candidate_signals=tuple(
                CandidateSignalView(
                    symbol=candidate.symbol,
                    accepted=candidate.candidate_status in {"accepted", "open"},
                    technical_score=candidate.technical_score or 0.0,
                    relative_strength_score=candidate.relative_strength_score or 0.0,
                    rejection_reasons=candidate.rejection_reasons,
                    data_source="database_read_model",
                )
                for candidate in candidates
            ),
            ai_outputs=tuple(
                AIResearchOutputView(
                    symbol=output.symbol,
                    news_state=str(output.parsed_output.get("news_state", "unknown")),
                    ai_score=output.ai_score,
                    hard_block=output.hard_block,
                    fallback=bool(output.fallback_reason and output.fallback_reason != "none"),
                    explanation=str(output.parsed_output.get("explanation", "")),
                    data_source="database_read_model",
                )
                for output in ai_outputs
            ),
            reports=tuple(
                ReportSummaryView(
                    report_id=report.report_id,
                    report_type=_report_type(report.report_type),
                    generated_at=report.created_at,
                    status=report.status,
                    data_source="database_read_model",
                )
                for report in reports
            ),
        )


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


def _reconciliation_severity(
    has_reconciliation: bool,
    clean: bool,
) -> DashboardSeverity:
    if not has_reconciliation:
        return "warning"
    return "info" if clean else "critical"


def _report_type(value: str) -> Literal["daily", "weekly", "manual"]:
    if value == "daily":
        return "daily"
    if value == "weekly":
        return "weekly"
    return "manual"
