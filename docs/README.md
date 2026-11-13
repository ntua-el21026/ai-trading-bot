# Technical documentation index

The [v0.6 specification](app/Autonomous_AI_Trading_Bot_SPEC_v0.6.md) is the current policy reference. Versioned earlier specifications, milestone narratives, AI research notes and recorded evidence preserve their historical role.

## Implementation and contracts

- [Architecture](architecture.md): package boundaries and milestone-specific implementation notes.
- [Temporal workflows](temporal_workflows.md): deterministic workflow/activity contracts and test-server scope.
- [Risk](risk_policy.md), [execution](execution_policy.md) and [broker integration](broker_integration.md): deterministic authority, order/reconciliation and paper-adapter boundaries.
- [AI intelligence](ai_intelligence.md): shortlist news analysis, schemas, request budgets and fallbacks.
- [Database/audit ledger](database_audit_ledger.md) and [database runtime](database_runtime.md): local repositories and explicitly gated managed operations.
- [Dashboard/control plane](dashboard_control_plane.md), [reporting](reporting.md) and [alerting](alerting.md): read models, safe controls and delivery boundaries.

## Validation and operational evidence

- [Validation plan](validation_plan.md) separates unit, integration, failure-path and replay checks.
- [Paper dry-run orchestration](paper_dry_run_orchestration.md) describes the fake/local demonstration.
- [Paper-trading runbook](paper_trading_runbook.md) and [operations runbook](operations_runbook.md) describe operator-controlled procedures.
- [Frozen validation start](frozen_paper_validation_m45.md), [Day-1 audit](frozen_validation_day1_audit_m46.md), [runner](frozen_validation_runner_m47.md) and [durable-runner record](durable_runner_m47b.md) describe recorded milestones and their limits.
- [evidence/](evidence/) retains machine-readable observations. A `GO` for a preparation step does not imply active deployment, completed acceptance or live-trading readiness.
- [Level 4 readiness](level4_micro_live_readiness.md) records future operational gates; it does not enable live trading.

Source review and fake/local tests need no provider credentials. Keep private configuration outside Git and retain failed-gate evidence.
