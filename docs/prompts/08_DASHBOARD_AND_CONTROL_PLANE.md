# 08 - Dashboard And Control Plane

You are Codex working inside this repository.

## Context

This repository is governed by `AGENTS.md` and the latest versioned autonomous trading bot specification. Codex must read both before editing. Vercel is dashboard/control-plane only. Autonomous execution workers run outside Vercel, and broker credentials must not be exposed to frontend code.

## Mandatory First Steps

1. Read `AGENTS.md`.
2. Identify and read the latest versioned spec.
3. Inspect the relevant files before editing.
4. Check whether the requested work is compliant with the latest spec.
5. If not compliant, stop and ask for approval.

## Goal

Implement the dashboard and control-plane structure for read-only monitoring plus safe kill-switch/control actions, without placing broker orders from the frontend.

## Scope

- Dashboard app structure consistent with the latest spec and existing repo.
- Read-only portfolio, positions, orders, fills, signals, candidates, risk, reconciliation, incidents, AI outputs, and reports views.
- Backend/API read models or stubs needed to support dashboard views.
- Kill-switch, pause-new-risk, force reconciliation, force report, acknowledge incident, and resume-after-review control flow through backend/Temporal signals.
- Frontend environment hygiene that excludes broker secrets.
- UI tests or API tests where feasible.

## Out of Scope

- No broker order submission from frontend or Vercel.
- No broker credentials in frontend environment variables.
- No autonomous execution workers on Vercel.
- No natural-language order placement.
- No live trading enablement.
- No changes to risk limits, autonomy level, or kill-switch semantics without approval and spec update.

## Required Inspection

- `AGENTS.md`
- Latest versioned spec sections on dashboard/control plane, Vercel policy, Temporal queries/signals, kill switch, reporting, environment variables, and infrastructure
- Existing `apps/dashboard`, `apps/api`, `packages/reporting`, `packages/execution`, `config/system.yaml`, `.env.example`, and tests
- Existing workflow query/signal contracts and data models

## Implementation Tasks

1. Create or refine dashboard project structure using the existing frontend stack or the latest-spec recommendation.
2. Add read-only views for current system state, active workflows, execution intents, open orders, open positions, recent incidents, last reconciliation, kill switch state, signals/candidates, AI outputs, and reports.
3. Add backend/control-plane endpoints or service contracts that read from the audit ledger and signal Temporal workflows for controls.
4. Implement kill-switch and pause/resume controls as explicit, auditable actions with confirmation and no direct broker API access from frontend.
5. Ensure frontend environment configuration includes only non-secret public values.
6. Add tests for dashboard rendering, API contracts, auth/control guardrails if present, and secret-exposure checks where feasible.
7. Document deployment assumptions, especially that Vercel is dashboard-only.

## Spec Alignment Checks

- Vercel must remain dashboard-only.
- No autonomous order execution can run on Vercel.
- No broker credentials can be exposed to Vercel frontend.
- Control actions must route through deterministic backend/Temporal signal paths.
- Kill switch must block new risk and preserve/risk-reduce existing positions according to the latest spec.

## Tests / Validation

- Run frontend unit/component tests if configured.
- Run API tests for read/control contracts if implemented.
- Run build/type/lint checks if configured.
- Inspect frontend env usage to confirm broker secrets are not referenced.
- If no frontend stack exists, document what was scaffolded and what checks were possible.

## Documentation Updates

- Update dashboard/control-plane documentation with views, control actions, security constraints, and Vercel policy.
- Update `.env.example` only with safe variable names.
- Do not update the latest spec unless an approved deviation requires it.

## Approval Gate

If any requested implementation would deviate from the latest spec, do not implement it.
Explain the deviation, propose options, and wait for user approval.
If the user approves a deviation, update the latest spec as part of the same milestone or create a new versioned spec file, depending on the size of the change.

## Expected Final Response

Summary:

- ...

Files changed:

- ...

Spec impact:

- ...

Tests:

- ...

Risks / follow-ups:

- ...
