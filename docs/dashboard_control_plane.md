# Dashboard Control Plane

The latest source of truth is `docs/app/Autonomous_AI_Trading_Bot_SPEC_v0.3.md`.

Milestone 08 implements dashboard/control-plane contracts only. Vercel is dashboard-only; autonomous
execution workers must run outside Vercel.

## Implemented Contracts

- `packages/control_plane/models.py` defines read-only dashboard view models and auditable control
  action requests.
- `packages/control_plane/service.py` defines read-model and control-dispatch protocols plus fixture
  providers for tests.
- `packages/control_plane/security.py` defines frontend secret-reference guardrails.
- `apps/api/app/control_plane.py` is a server-side API contract that maps safe control actions to
  existing Temporal signal names.
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
- reports;
- risk status;
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

## Environment Policy

Dashboard/frontend code may only expose explicitly safe public values. It must not reference broker
credentials, AI/news provider keys, privileged database URLs, or Temporal API keys.

Current implementation does not add Vercel deployment files, frontend dependencies, real Temporal
clients, database-backed read-model providers, or production dashboard deployment.

## Level 4 Readiness Evidence

`docs/level4_micro_live_readiness.md` requires dashboard/control-plane evidence before any Level 4
micro-live decision: safe read models, no frontend secrets, no browser-side broker/AI/news/Temporal
calls, no order-entry controls, server-side control routing, and operator-tested kill-switch,
pause-new-risk, force-reconciliation, force-report, acknowledge-incident, and resume-after-review
paths. Current dashboard/control-plane implementation is contract-only and not deployed.
