# Dashboard Control Plane

The latest source of truth is `docs/app/Autonomous_AI_Trading_Bot_SPEC_v0.3.md`.

Milestone 15 implements dashboard/control-plane contracts plus a ledger-backed backend read-model
provider. Vercel is dashboard-only; autonomous execution workers must run outside Vercel.

Milestone 16 builds a dashboard/read-model snapshot from local dry-run ledger records after the
fake/local paper dry run completes. This is not a deployed dashboard.

Milestone 25 adds safe dashboard/control-plane dev runtime wiring and
`scripts/check_dashboard_control_plane_runtime.py`. The smoke builds a fake/local read-only
snapshot, validates safe control-action schemas, dispatches through a fake server-side dispatcher by
default, and reports sanitized evidence only. It does not deploy, activate schedules, send real
Temporal control signals by default, call broker APIs, call AI/news providers, send Telegram
alerts, or start paper trading operations.

## Implemented Contracts

- `packages/control_plane/models.py` defines read-only dashboard view models and auditable control
  action requests.
- `packages/control_plane/service.py` defines read-model and control-dispatch protocols, fixture
  providers for tests, and `LedgerDashboardReadModelProvider` for repository-backed snapshots.
- `packages/control_plane/runtime.py` defines the dev runtime smoke harness, dashboard smoke gates,
  fake/default control validation, and no-side-effect result summaries.
- `packages/control_plane/security.py` defines frontend secret-reference guardrails.
- `apps/api/app/control_plane.py` is a server-side API contract that maps safe control actions to
  existing Temporal signal names and can read snapshots from the ledger provider.
- `apps/dashboard/` is a minimal scaffold with safe public environment selection and no frontend
  framework dependency.

## Dashboard Views

Read-model contracts cover:

- current system state;
- active workflows;
- active execution intents;
- open orders;
- open positions;
- recent incidents;
- last reconciliation status;
- kill-switch state;
- strategy candidates/signals;
- AI outputs;
- AI quality state;
- provider budget status;
- reports;
- risk status;
- alerting status;
- Temporal runtime status;
- paper-operation readiness status;
- broker/reconciliation status.

## Safe Controls

The only exposed control actions are:

- `manual_kill_switch`;
- `manual_pause_new_risk`;
- `manual_resume_after_review`;
- `force_reconciliation`;
- `force_report`;
- `acknowledge_incident`.

These map to existing Temporal signal names through a server-side contract. They do not call broker
APIs, create orders, modify orders, change stops, modify strategy rules, modify risk limits, change
autonomy level, or enable live/autonomous trading.

Resume-after-review requires a manual review reference and is modeled as a controlled request, not
an automatic live-trading re-enable.

Default dev runtime behavior validates these controls and records the intended signal mapping
through `FixtureControlActionDispatcher`; it does not send real Temporal signals. A future
Temporal-dev signal check must be explicitly gated and harmless.

## Environment Policy

Dashboard/frontend code may only expose explicitly safe public values. It must not reference broker
credentials, AI/news provider keys, privileged database URLs, or Temporal API keys.

Current implementation does not add Vercel deployment files, frontend dependencies, real Temporal
clients, browser-side Temporal calls, frontend secrets, Telegram bot access, or production dashboard
deployment.

Telegram alert delivery added in Milestone 23 is server-side and operator-facing only. Dashboard and
frontend code must not expose Telegram tokens/chat IDs, broker credentials, AI/news provider keys,
database URLs, or Temporal keys, and must not use Telegram as a command/control trading interface.

Temporal Cloud dev runtime wiring added in Milestone 24 remains server-side only. The
default-refusing smoke harness connects only when explicit dev gates are present, runs a harmless
workflow with fake/local activity behavior, and creates no schedules. Dashboard/browser code still
must not hold Temporal API keys or connect directly to Temporal Cloud.

Milestone 25 keeps Vercel dashboard-only and does not deploy. The optional future preview gates
`RUN_VERCEL_DASHBOARD_PREVIEW` and `VERCEL_DASHBOARD_PREVIEW_CONFIRM` are placeholders only; this
milestone refuses deployment mode.

## Ledger Read Models

`LedgerDashboardReadModelProvider` builds dashboard snapshots from repository records for:

- latest system state from safe config;
- active execution intents;
- open orders;
- open positions;
- recent incidents;
- latest reconciliation status;
- kill-switch and risk status;
- candidates/signals;
- AI outputs;
- reports.

The provider performs repository reads only. It does not call broker APIs, AI/news providers,
Temporal, alert adapters, frontend code, or secret sources. Missing data returns explicit empty or
unavailable-safe statuses rather than production claims.

`packages/paper/dry_run.py` uses this provider after the fake/local dry run to verify that report,
incident, reconciliation, order, position, AI, candidate, and execution-intent records can be read
through backend read-model contracts without frontend secrets or external provider calls.

## Level 4 Readiness Evidence

`docs/level4_micro_live_readiness.md` requires dashboard/control-plane evidence before any Level 4
micro-live decision: safe read models, no frontend secrets, no browser-side broker/AI/news/Temporal
calls, no order-entry controls, server-side control routing, and operator-tested kill-switch,
pause-new-risk, force-reconciliation, force-report, acknowledge-incident, and resume-after-review
paths. Current dashboard/control-plane implementation has local ledger read models and contract
tests plus a dev runtime smoke harness, but it is not deployed and does not provide production
dashboard evidence.
