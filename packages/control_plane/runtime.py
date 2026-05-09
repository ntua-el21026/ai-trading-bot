"""Dashboard/control-plane dev runtime smoke harness.

The runtime is server-side only. It builds safe read models, validates control-action contracts, and
uses fake dispatch by default. It never calls brokers, AI/news providers, alert adapters, deployment
APIs, or Temporal schedules.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Self

from apps.api.app.control_plane import CONTROL_ACTION_SIGNAL_MAP, dispatch_control_action
from packages.control_plane.models import ControlActionRequest, DashboardSnapshot
from packages.control_plane.service import (
    FixtureControlActionDispatcher,
    FixtureDashboardReadModelProvider,
    build_unavailable_dashboard_snapshot,
)
from packages.core.config import AppConfig, load_app_config

DASHBOARD_SMOKE_RUN_ENV = "RUN_DASHBOARD_CONTROL_PLANE_SMOKE"
DASHBOARD_SMOKE_CONFIRM_ENV = "DASHBOARD_CONTROL_PLANE_SMOKE_CONFIRM"
DASHBOARD_SMOKE_CONFIRM_VALUE = "READ_ONLY_AND_SAFE_CONTROLS_ONLY"
DASHBOARD_USE_TEMPORAL_DEV_ENV = "DASHBOARD_CONTROL_PLANE_USE_TEMPORAL_DEV"
DASHBOARD_USE_MANAGED_DB_ENV = "DASHBOARD_CONTROL_PLANE_USE_MANAGED_DB"
DASHBOARD_ALLOW_CONTROL_SIGNALS_ENV = "DASHBOARD_CONTROL_PLANE_ALLOW_CONTROL_SIGNALS"

VERCEL_DASHBOARD_PREVIEW_RUN_ENV = "RUN_VERCEL_DASHBOARD_PREVIEW"
VERCEL_DASHBOARD_PREVIEW_CONFIRM_ENV = "VERCEL_DASHBOARD_PREVIEW_CONFIRM"


@dataclass(frozen=True)
class DashboardControlPlaneSmokeSettings:
    gates_loaded: bool
    use_temporal_dev: bool
    use_managed_db: bool
    allow_control_signals: bool
    deployment_requested: bool
    refusal_reasons: tuple[str, ...] = ()

    @classmethod
    def from_env(cls, environ: Mapping[str, str] | None = None) -> Self:
        env = os.environ if environ is None else environ
        run_requested = env.get(DASHBOARD_SMOKE_RUN_ENV) == "1"
        confirm_loaded = env.get(DASHBOARD_SMOKE_CONFIRM_ENV) == DASHBOARD_SMOKE_CONFIRM_VALUE
        use_temporal_dev = _env_bool(env.get(DASHBOARD_USE_TEMPORAL_DEV_ENV), default=False)
        use_managed_db = _env_bool(env.get(DASHBOARD_USE_MANAGED_DB_ENV), default=False)
        allow_control_signals = _env_bool(
            env.get(DASHBOARD_ALLOW_CONTROL_SIGNALS_ENV),
            default=False,
        )
        deployment_requested = env.get(VERCEL_DASHBOARD_PREVIEW_RUN_ENV) == "1"

        reasons: list[str] = []
        if run_requested and not confirm_loaded:
            reasons.append("missing_dashboard_control_plane_confirmation")
        if use_managed_db:
            reasons.append("managed_db_dashboard_runtime_not_enabled")
        if deployment_requested:
            reasons.append("deployment_not_allowed_for_milestone_25")

        return cls(
            gates_loaded=run_requested and confirm_loaded and not reasons,
            use_temporal_dev=use_temporal_dev,
            use_managed_db=use_managed_db,
            allow_control_signals=allow_control_signals,
            deployment_requested=deployment_requested,
            refusal_reasons=tuple(reasons),
        )


@dataclass(frozen=True)
class DashboardControlPlaneSmokeResult:
    gates_loaded: bool = False
    snapshot_built: bool = False
    system_state_present: bool = False
    workflows_present: bool = False
    kill_switch_state_present: bool = False
    execution_intents_present: bool = False
    orders_present: bool = False
    positions_present: bool = False
    incidents_present: bool = False
    reconciliation_present: bool = False
    candidates_present: bool = False
    ai_outputs_present: bool = False
    reports_present: bool = False
    risk_status_present: bool = False
    alerting_status_present: bool = False
    temporal_status_present: bool = False
    safe_controls_validated: bool = False
    temporal_dev_signal_checked: bool = False
    broker_calls_performed: bool = False
    ai_news_calls_performed: bool = False
    alert_calls_performed: bool = False
    schedules_created: bool = False
    schedules_activated: bool = False
    deployment_performed: bool = False
    secrets_printed: bool = False
    actual_paper_trading_started: bool = False
    level4_ready: bool = False
    refused: bool = False
    refusal_reasons: tuple[str, ...] = ()
    failure_codes: tuple[str, ...] = ()

    def to_sanitized_dict(self) -> dict[str, object]:
        return {
            "gates_loaded": self.gates_loaded,
            "snapshot_built": self.snapshot_built,
            "system_state_present": self.system_state_present,
            "workflows_present": self.workflows_present,
            "kill_switch_state_present": self.kill_switch_state_present,
            "execution_intents_present": self.execution_intents_present,
            "orders_present": self.orders_present,
            "positions_present": self.positions_present,
            "incidents_present": self.incidents_present,
            "reconciliation_present": self.reconciliation_present,
            "candidates_present": self.candidates_present,
            "ai_outputs_present": self.ai_outputs_present,
            "reports_present": self.reports_present,
            "risk_status_present": self.risk_status_present,
            "alerting_status_present": self.alerting_status_present,
            "temporal_status_present": self.temporal_status_present,
            "safe_controls_validated": self.safe_controls_validated,
            "temporal_dev_signal_checked": self.temporal_dev_signal_checked,
            "broker_calls_performed": self.broker_calls_performed,
            "ai_news_calls_performed": self.ai_news_calls_performed,
            "alert_calls_performed": self.alert_calls_performed,
            "schedules_created": self.schedules_created,
            "schedules_activated": self.schedules_activated,
            "deployment_performed": self.deployment_performed,
            "secrets_printed": self.secrets_printed,
            "actual_paper_trading_started": self.actual_paper_trading_started,
            "level4_ready": self.level4_ready,
            "refused": self.refused,
            "refusal_reasons": list(self.refusal_reasons),
            "failure_codes": list(self.failure_codes),
        }


def run_dashboard_control_plane_smoke(
    *,
    environ: Mapping[str, str] | None = None,
    config: AppConfig | None = None,
) -> DashboardControlPlaneSmokeResult:
    settings = DashboardControlPlaneSmokeSettings.from_env(environ)
    app_config = config or load_app_config()

    if settings.refusal_reasons:
        return DashboardControlPlaneSmokeResult(
            gates_loaded=False,
            refused=True,
            refusal_reasons=settings.refusal_reasons,
        )

    if not _config_safety_invariants_hold(app_config):
        return DashboardControlPlaneSmokeResult(
            gates_loaded=settings.gates_loaded,
            refused=True,
            failure_codes=("unsafe_runtime_config",),
        )

    snapshot = FixtureDashboardReadModelProvider(
        build_unavailable_dashboard_snapshot(as_of=datetime.now(UTC))
    ).snapshot()
    controls_validated = validate_safe_control_actions()

    temporal_checked = False
    if settings.gates_loaded and settings.use_temporal_dev and settings.allow_control_signals:
        temporal_checked = _run_optional_temporal_signal_smoke()

    return _result_from_snapshot(
        snapshot,
        gates_loaded=settings.gates_loaded,
        safe_controls_validated=controls_validated,
        temporal_dev_signal_checked=temporal_checked,
    )


def validate_safe_control_actions() -> bool:
    dispatcher = FixtureControlActionDispatcher(CONTROL_ACTION_SIGNAL_MAP)
    for action in CONTROL_ACTION_SIGNAL_MAP:
        request = _control_request(action)
        receipt = dispatch_control_action(request, dispatcher)
        if receipt.status != "accepted":
            return False
        if receipt.temporal_signal_name != CONTROL_ACTION_SIGNAL_MAP[action]:
            return False
        if (
            receipt.broker_calls_performed
            or receipt.orders_created
            or receipt.risk_limits_modified
            or receipt.autonomy_level_modified
        ):
            return False
    return True


def _control_request(action: str) -> ControlActionRequest:
    requested_at = datetime(2026, 5, 9, 12, 0, tzinfo=UTC)
    return ControlActionRequest.model_validate(
        {
            "action": action,
            "requested_by": "dashboard-smoke",
            "requested_at": requested_at,
            "reason": "dashboard control-plane smoke validation",
            "incident_id": "incident-smoke" if action == "acknowledge_incident" else None,
            "manual_review_reference": (
                "manual-review-smoke" if action == "manual_resume_after_review" else None
            ),
            "idempotency_key": f"dashboard-smoke-{action}",
        }
    )


def _run_optional_temporal_signal_smoke() -> bool:
    from apps.workers.app.temporal_cloud_smoke import run_temporal_cloud_smoke

    result = run_temporal_cloud_smoke()
    return result.workflow_completed and result.signal_query_checked


def _result_from_snapshot(
    snapshot: DashboardSnapshot,
    *,
    gates_loaded: bool,
    safe_controls_validated: bool,
    temporal_dev_signal_checked: bool,
) -> DashboardControlPlaneSmokeResult:
    return DashboardControlPlaneSmokeResult(
        gates_loaded=gates_loaded,
        snapshot_built=True,
        system_state_present=hasattr(snapshot, "system_state"),
        workflows_present=hasattr(snapshot, "active_workflows"),
        kill_switch_state_present=hasattr(snapshot, "kill_switch"),
        execution_intents_present=hasattr(snapshot, "active_execution_intents"),
        orders_present=hasattr(snapshot, "open_orders"),
        positions_present=hasattr(snapshot, "open_positions"),
        incidents_present=hasattr(snapshot, "recent_incidents"),
        reconciliation_present=hasattr(snapshot, "reconciliation_status"),
        candidates_present=hasattr(snapshot, "candidate_signals"),
        ai_outputs_present=(
            hasattr(snapshot, "ai_outputs") and hasattr(snapshot, "ai_quality_state")
        ),
        reports_present=hasattr(snapshot, "reports"),
        risk_status_present=hasattr(snapshot, "risk_status"),
        alerting_status_present=hasattr(snapshot, "alerting_status"),
        temporal_status_present=hasattr(snapshot, "temporal_runtime_status"),
        safe_controls_validated=safe_controls_validated,
        temporal_dev_signal_checked=temporal_dev_signal_checked,
        actual_paper_trading_started=snapshot.paper_operation_readiness.actual_paper_trading_started,
        level4_ready=snapshot.paper_operation_readiness.level4_ready,
    )


def _config_safety_invariants_hold(config: AppConfig) -> bool:
    return (
        config.system.environment == "paper"
        and config.system.live_trading_enabled is False
        and config.system.autonomous_execution_enabled is False
        and config.execution.allow_live_orders is False
        and config.execution.autonomous_execution_enabled is False
        and config.execution.require_execution_intent is True
        and config.execution.require_passed_risk_check is True
        and config.execution.require_broker_reconciliation_before_order is True
        and config.execution.require_protective_stop is True
    )


def _env_bool(value: str | None, *, default: bool) -> bool:
    if value is None or value == "":
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}
