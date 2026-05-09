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

Milestone 26 adds a dashboard-only Vercel preview harness. The preview is static/read-only, uses
only safe public environment values, excludes workers and backend packages from the Vercel upload,
and can be checked with `scripts/check_vercel_dashboard_preview.py`. The generated Vercel preview
URL is sufficient; no custom domain is required. This is not actual paper trading, frozen paper
evidence, production deployment, or Level 4 readiness.

Milestone 26B records deployment evidence. Preview deployment
`https://ai-trading-cy85e5pf1-michael-peppas-projects.vercel.app` exists. A production deployment
was accidentally created at `https://ai-trading-qxid0g5t8-michael-peppas-projects.vercel.app` with
alias `https://ai-trading-bot-silk.vercel.app`. The production alias was verified as the expected
static/read-only dashboard artifact. The deployment-specific preview and production URLs were
Vercel-ready but returned anonymous HTTP 401 during audit, so their content is protected from
unauthenticated HTTP. This production deployment is non-operational: no workers run on Vercel, no
frontend secrets are exposed, no order-entry controls exist, and browser code performs no broker,
AI/news, Temporal, database, or Telegram privileged calls. Future production deployments require
explicit approval/gates.

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
- `apps/dashboard/` is a minimal static preview scaffold with safe public environment selection and
  no frontend framework dependency.
- `vercel.json` builds only the static dashboard preview output and does not define workers,
  functions, or schedules.
- `.vercelignore` excludes local env files, worker/backend packages, scripts, tests, docs, config,
  and generated runtime state from preview uploads.

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

Current implementation adds dashboard-only Vercel preview files but no frontend dependencies, real
Temporal clients, browser-side Temporal calls, frontend secrets, Telegram bot access, workers, or
production dashboard deployment.

Telegram alert delivery added in Milestone 23 is server-side and operator-facing only. Dashboard and
frontend code must not expose Telegram tokens/chat IDs, broker credentials, AI/news provider keys,
database URLs, or Temporal keys, and must not use Telegram as a command/control trading interface.

Temporal Cloud dev runtime wiring added in Milestone 24 remains server-side only. The
default-refusing smoke harness connects only when explicit dev gates are present, runs a harmless
workflow with fake/local activity behavior, and creates no schedules. Dashboard/browser code still
must not hold Temporal API keys or connect directly to Temporal Cloud.

Milestone 26 keeps Vercel dashboard-only. Preview deployment is allowed only with
`RUN_VERCEL_DASHBOARD_PREVIEW=1` and
`VERCEL_DASHBOARD_PREVIEW_CONFIRM=DASHBOARD_ONLY_NO_SECRETS_NO_WORKERS`. The preview must use only
`NEXT_PUBLIC_APP_ENV` and `NEXT_PUBLIC_DASHBOARD_ENV`; no broker, AI/news, database, Temporal, or
Telegram secrets may be exposed to frontend code. The preview does not include order-entry controls
and cannot enable live trading or autonomous execution.

Running `vercel --prod` is not part of preview-only milestones. If a production deployment is
needed later, it must be explicitly requested, gated, and revalidated as dashboard-only.

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
paths. Current dashboard/control-plane implementation has local ledger read models, contract tests,
a dev runtime smoke harness, and a dashboard-only static preview harness. The preview is not
production dashboard evidence and does not satisfy Level 4 readiness by itself.
