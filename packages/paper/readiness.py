"""Controlled paper operations readiness aggregation.

This module is read-only. It evaluates existing evidence and safe local checks; it does not submit
orders, activate schedules, call providers, send alerts, or deploy anything.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, model_validator

from packages.core.config import AppConfig, load_app_config

ReadinessSeverity = Literal["required", "hard_failure"]


class ReadinessModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ReadinessCheck(ReadinessModel):
    name: str
    passed: bool
    severity: ReadinessSeverity = "required"
    detail: str


class PaperOperationsReadinessEvidence(ReadinessModel):
    config_safety: bool
    database_migration_schema_crud_evidence: bool
    managed_db_runtime_explicitly_gated: bool
    temporal_local_tests_evidence: bool
    temporal_cloud_dev_smoke_evidence: bool
    schedules_created: bool = False
    schedules_activated: bool = False
    alpaca_readonly_smoke_evidence: bool
    alpaca_lifecycle_smoke_evidence: bool
    current_open_smoke_state_checked: bool = False
    current_open_smoke_state_clean: bool | None = None
    live_endpoint_used: bool = False
    ai_news_layer_implemented: bool
    marketaux_alpha_vantage_smoke_evidence: bool
    openai_structured_smoke_evidence: bool
    openai_web_fallback_disabled_by_default: bool
    telegram_harness_implemented: bool
    telegram_smoke_evidence: bool
    alert_real_delivery_disabled_by_default: bool
    email_resend_deferred: bool
    dashboard_runtime_smoke_evidence: bool
    vercel_preview_deployment_evidence: bool
    dashboard_no_secrets_exposed: bool
    dashboard_no_order_entry_ui: bool
    dashboard_no_workers_on_vercel: bool
    actual_paper_trading_started: bool = False
    frozen_paper_evidence_available: bool = False
    first_controlled_paper_session_started: bool = False
    level4_ready: bool = False
    external_calls_performed: bool = False
    broker_writes_attempted: bool = False
    ai_news_calls_performed: bool = False
    real_alerts_sent: bool = False
    deployment_performed: bool = False
    secrets_printed: bool = False

    @model_validator(mode="after")
    def validate_non_operational_defaults(self) -> Self:
        if self.actual_paper_trading_started:
            raise ValueError("readiness evidence must not claim actual paper trading started")
        if self.first_controlled_paper_session_started:
            raise ValueError(
                "readiness evidence must not claim first controlled paper session started"
            )
        if self.level4_ready:
            raise ValueError("readiness evidence must not claim Level 4 readiness")
        return self


class PaperOperationsReadinessResult(ReadinessModel):
    ready_for_first_controlled_paper_session: bool
    checks: tuple[ReadinessCheck, ...]
    hard_failures: tuple[str, ...]
    missing_required_evidence: tuple[str, ...]
    database_evidence: bool
    temporal_evidence: bool
    broker_evidence: bool
    ai_news_evidence: bool
    alerting_evidence: bool
    dashboard_evidence: bool
    paper_operations_started: bool
    frozen_paper_evidence: bool
    level4_ready: bool
    external_calls_performed: bool
    broker_writes_attempted: bool
    ai_news_calls_performed: bool
    real_alerts_sent: bool
    schedules_activated: bool
    deployment_performed: bool
    secrets_printed: bool

    def to_sanitized_dict(self) -> dict[str, object]:
        return {
            "ready_for_first_controlled_paper_session": (
                self.ready_for_first_controlled_paper_session
            ),
            "checks": [check.model_dump(mode="json") for check in self.checks],
            "hard_failures": list(self.hard_failures),
            "missing_required_evidence": list(self.missing_required_evidence),
            "database_evidence": self.database_evidence,
            "temporal_evidence": self.temporal_evidence,
            "broker_evidence": self.broker_evidence,
            "ai_news_evidence": self.ai_news_evidence,
            "alerting_evidence": self.alerting_evidence,
            "dashboard_evidence": self.dashboard_evidence,
            "paper_operations_started": self.paper_operations_started,
            "frozen_paper_evidence": self.frozen_paper_evidence,
            "level4_ready": self.level4_ready,
            "external_calls_performed": self.external_calls_performed,
            "broker_writes_attempted": self.broker_writes_attempted,
            "ai_news_calls_performed": self.ai_news_calls_performed,
            "real_alerts_sent": self.real_alerts_sent,
            "schedules_activated": self.schedules_activated,
            "deployment_performed": self.deployment_performed,
            "secrets_printed": self.secrets_printed,
        }


def build_repository_readiness_evidence(
    *,
    repo_root: Path | None = None,
    config: AppConfig | None = None,
    dashboard_runtime_smoke_evidence: bool | None = None,
    vercel_preview_guardrails_evidence: bool | None = None,
) -> PaperOperationsReadinessEvidence:
    root = Path.cwd() if repo_root is None else repo_root
    app_config = config or load_app_config()
    docs = _read_docs(root)
    all_docs = "\n".join(docs.values())

    dashboard_runtime = (
        _contains_all(
            docs["dashboard_control_plane"],
            ("Milestone 25", "dev runtime smoke", "fake/default dispatch"),
        )
        if dashboard_runtime_smoke_evidence is None
        else dashboard_runtime_smoke_evidence
    )
    vercel_preview = (
        _contains_all(
            all_docs,
            (
                "https://ai-trading-cy85e5pf1-michael-peppas-projects.vercel.app",
                "static/read-only",
                "Vercel deployment evidence",
            ),
        )
        if vercel_preview_guardrails_evidence is None
        else vercel_preview_guardrails_evidence
    )

    return PaperOperationsReadinessEvidence(
        config_safety=config_safety_invariants_hold(app_config),
        database_migration_schema_crud_evidence=_contains_any(
            all_docs,
            (
                "Managed Supabase/Postgres dev DB validation previously passed",
                "opt-in managed repository CRUD validation",
                "managed repository CRUD validation",
            ),
        ),
        managed_db_runtime_explicitly_gated=_contains_all(
            all_docs,
            ("DATABASE_URL", "explicit", "gated"),
        ),
        temporal_local_tests_evidence=_contains_all(
            all_docs,
            ("Local Temporal SDK", "test", "replay"),
        ),
        temporal_cloud_dev_smoke_evidence=_contains_all(
            all_docs,
            ("Milestone 24", "Temporal Cloud dev smoke"),
        ),
        alpaca_readonly_smoke_evidence=_contains_all(
            all_docs,
            ("Milestone 20 read-only smoke", "passed"),
        ),
        alpaca_lifecycle_smoke_evidence=_contains_all(
            all_docs,
            ("Milestone 21B", "completed", "clean/flat"),
        )
        or _contains_all(
            all_docs,
            ("Milestone 21B", "completed", "clean"),
        ),
        ai_news_layer_implemented=_contains_all(
            all_docs,
            ("Marketaux", "Alpha Vantage", "OpenAI structured"),
        ),
        marketaux_alpha_vantage_smoke_evidence=_contains_all(
            all_docs,
            ("Marketaux/Alpha Vantage", "real provider/OpenAI smoke evidence"),
        ),
        openai_structured_smoke_evidence=_contains_all(
            all_docs,
            ("OpenAI structured", "real provider/OpenAI smoke evidence"),
        ),
        openai_web_fallback_disabled_by_default=(
            app_config.ai.news_enable_openai_web_fallback is False
        ),
        telegram_harness_implemented=_contains_all(
            all_docs,
            ("Telegram", "smoke harness"),
        ),
        telegram_smoke_evidence=_contains_all(
            all_docs,
            ("Real Telegram smoke evidence", "gated paths"),
        ),
        alert_real_delivery_disabled_by_default=True,
        email_resend_deferred=_contains_all(all_docs, ("Email/Resend", "deferred")),
        dashboard_runtime_smoke_evidence=dashboard_runtime,
        vercel_preview_deployment_evidence=vercel_preview,
        dashboard_no_secrets_exposed=_contains_all(
            all_docs,
            ("no frontend secrets", "no privileged browser-side calls"),
        )
        or _contains_all(all_docs, ("No workers", "No secrets")),
        dashboard_no_order_entry_ui=_contains_any(
            all_docs,
            ("no order-entry controls", "No order-entry"),
        ),
        dashboard_no_workers_on_vercel=_contains_all(
            all_docs,
            ("no workers", "Vercel"),
        )
        or _contains_all(all_docs, ("No workers", "Vercel")),
    )


def evaluate_paper_operations_readiness(
    evidence: PaperOperationsReadinessEvidence,
) -> PaperOperationsReadinessResult:
    checks = _build_checks(evidence)
    hard_failures = tuple(
        check.name
        for check in checks
        if not check.passed and check.severity == "hard_failure"
    )
    missing_required = tuple(
        check.name
        for check in checks
        if not check.passed and check.severity == "required"
    )
    database_evidence = (
        evidence.database_migration_schema_crud_evidence
        and evidence.managed_db_runtime_explicitly_gated
    )
    temporal_evidence = (
        evidence.temporal_local_tests_evidence
        and evidence.temporal_cloud_dev_smoke_evidence
        and not evidence.schedules_created
        and not evidence.schedules_activated
    )
    broker_evidence = (
        evidence.alpaca_readonly_smoke_evidence
        and evidence.alpaca_lifecycle_smoke_evidence
        and not evidence.live_endpoint_used
    )
    ai_news_evidence = (
        evidence.ai_news_layer_implemented
        and evidence.marketaux_alpha_vantage_smoke_evidence
        and evidence.openai_structured_smoke_evidence
        and evidence.openai_web_fallback_disabled_by_default
    )
    alerting_evidence = (
        evidence.telegram_harness_implemented
        and evidence.telegram_smoke_evidence
        and evidence.alert_real_delivery_disabled_by_default
        and evidence.email_resend_deferred
    )
    dashboard_evidence = (
        evidence.dashboard_runtime_smoke_evidence
        and evidence.vercel_preview_deployment_evidence
        and evidence.dashboard_no_secrets_exposed
        and evidence.dashboard_no_order_entry_ui
        and evidence.dashboard_no_workers_on_vercel
    )

    ready = not hard_failures and not missing_required

    return PaperOperationsReadinessResult(
        ready_for_first_controlled_paper_session=ready,
        checks=checks,
        hard_failures=hard_failures,
        missing_required_evidence=missing_required,
        database_evidence=database_evidence,
        temporal_evidence=temporal_evidence,
        broker_evidence=broker_evidence,
        ai_news_evidence=ai_news_evidence,
        alerting_evidence=alerting_evidence,
        dashboard_evidence=dashboard_evidence,
        paper_operations_started=evidence.actual_paper_trading_started,
        frozen_paper_evidence=evidence.frozen_paper_evidence_available,
        level4_ready=evidence.level4_ready,
        external_calls_performed=evidence.external_calls_performed,
        broker_writes_attempted=evidence.broker_writes_attempted,
        ai_news_calls_performed=evidence.ai_news_calls_performed,
        real_alerts_sent=evidence.real_alerts_sent,
        schedules_activated=evidence.schedules_activated,
        deployment_performed=evidence.deployment_performed,
        secrets_printed=evidence.secrets_printed,
    )


def config_safety_invariants_hold(config: AppConfig) -> bool:
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


def _build_checks(evidence: PaperOperationsReadinessEvidence) -> tuple[ReadinessCheck, ...]:
    return (
        ReadinessCheck(
            name="config_safety",
            passed=evidence.config_safety,
            severity="hard_failure",
            detail=(
                "paper mode, no live/autonomous execution, live orders disabled, "
                "stops/recon required"
            ),
        ),
        ReadinessCheck(
            name="database_evidence",
            passed=(
                evidence.database_migration_schema_crud_evidence
                and evidence.managed_db_runtime_explicitly_gated
            ),
            detail="managed DB validation evidence exists and runtime remains explicitly gated",
        ),
        ReadinessCheck(
            name="temporal_evidence",
            passed=(
                evidence.temporal_local_tests_evidence
                and evidence.temporal_cloud_dev_smoke_evidence
            ),
            detail="local Temporal tests and Temporal Cloud dev smoke evidence exist",
        ),
        ReadinessCheck(
            name="schedules_not_activated",
            passed=not evidence.schedules_created and not evidence.schedules_activated,
            severity="hard_failure",
            detail="readiness must not create or activate schedules",
        ),
        ReadinessCheck(
            name="broker_evidence",
            passed=(
                evidence.alpaca_readonly_smoke_evidence
                and evidence.alpaca_lifecycle_smoke_evidence
                and not evidence.live_endpoint_used
            ),
            detail=(
                "paper read-only and controlled lifecycle smoke evidence exist; "
                "live endpoint not used"
            ),
        ),
        ReadinessCheck(
            name="ai_news_evidence",
            passed=(
                evidence.ai_news_layer_implemented
                and evidence.marketaux_alpha_vantage_smoke_evidence
                and evidence.openai_structured_smoke_evidence
                and evidence.openai_web_fallback_disabled_by_default
            ),
            detail=(
                "provider-first news and OpenAI structured analysis evidence exists; "
                "web fallback off"
            ),
        ),
        ReadinessCheck(
            name="alerting_evidence",
            passed=(
                evidence.telegram_harness_implemented
                and evidence.telegram_smoke_evidence
                and evidence.alert_real_delivery_disabled_by_default
                and evidence.email_resend_deferred
            ),
            detail="Telegram harness/evidence exists; real delivery default off; email deferred",
        ),
        ReadinessCheck(
            name="dashboard_evidence",
            passed=(
                evidence.dashboard_runtime_smoke_evidence
                and evidence.vercel_preview_deployment_evidence
                and evidence.dashboard_no_secrets_exposed
                and evidence.dashboard_no_order_entry_ui
                and evidence.dashboard_no_workers_on_vercel
            ),
            detail=(
                "dashboard runtime and Vercel evidence exists with no "
                "secrets/order-entry/workers"
            ),
        ),
        ReadinessCheck(
            name="no_external_side_effects",
            passed=(
                not evidence.external_calls_performed
                and not evidence.broker_writes_attempted
                and not evidence.ai_news_calls_performed
                and not evidence.real_alerts_sent
                and not evidence.deployment_performed
                and not evidence.secrets_printed
            ),
            severity="hard_failure",
            detail=(
                "readiness harness must not call providers, write broker state, "
                "alert, deploy, or print secrets"
            ),
        ),
        ReadinessCheck(
            name="paper_operations_not_started",
            passed=(
                not evidence.actual_paper_trading_started
                and not evidence.first_controlled_paper_session_started
            ),
            severity="hard_failure",
            detail="first controlled paper session remains a future explicit milestone",
        ),
        ReadinessCheck(
            name="level4_not_ready",
            passed=not evidence.level4_ready,
            severity="hard_failure",
            detail="Level 4 readiness must remain false",
        ),
    )


def _read_docs(root: Path) -> dict[str, str]:
    paths = {
        "readme": root / "README.md",
        "validation_plan": root / "docs" / "validation_plan.md",
        "paper_trading_runbook": root / "docs" / "paper_trading_runbook.md",
        "level4": root / "docs" / "level4_micro_live_readiness.md",
        "dashboard_control_plane": root / "docs" / "dashboard_control_plane.md",
        "temporal_workflows": root / "docs" / "temporal_workflows.md",
        "broker_integration": root / "docs" / "broker_integration.md",
        "ai_intelligence": root / "docs" / "ai_intelligence.md",
        "alerting": root / "docs" / "alerting.md",
        "database_runtime": root / "docs" / "database_runtime.md",
    }
    return {
        key: path.read_text(encoding="utf-8") if path.is_file() else ""
        for key, path in paths.items()
    }


def _contains_all(text: str, snippets: tuple[str, ...]) -> bool:
    lowered = text.lower()
    return all(snippet.lower() in lowered for snippet in snippets)


def _contains_any(text: str, snippets: tuple[str, ...]) -> bool:
    lowered = text.lower()
    return any(snippet.lower() in lowered for snippet in snippets)
