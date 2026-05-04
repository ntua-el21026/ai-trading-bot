# 03 - Temporal Workflows

You are Codex working inside this repository.

## Context

This repository is governed by `AGENTS.md` and the latest versioned autonomous trading bot specification. Codex must read both before editing. Temporal is part of the v0.1 architecture and must be used for execution-critical orchestration.

## Mandatory First Steps

1. Read `AGENTS.md`.
2. Identify and read the latest versioned spec.
3. Inspect the relevant files before editing.
4. Check whether the requested work is compliant with the latest spec.
5. If not compliant, stop and ask for approval.

## Goal

Create Temporal worker setup, task queues, deterministic workflow skeletons, activity boundaries, and initial Temporal tests without performing real broker orders or side-effecting production calls.

## Scope

- Temporal client/worker bootstrap.
- Task queue configuration aligned with the latest spec.
- Workflow skeletons for daily data refresh, EOD signals, AI shortlist research, decision, execution intent, order lifecycle, position lifecycle, reconciliation, kill switch, and reporting as appropriate for the current codebase.
- Activity interfaces for side effects.
- Signals and queries defined as contracts or placeholders.
- Temporal determinism documentation.
- Replay or unit tests for skeleton workflows where feasible.

## Out of Scope

- No real broker order submission.
- No direct external API calls from workflow code.
- No production schedule activation unless explicitly requested and safe.
- No live trading enablement.
- No strategy/risk/broker implementation beyond placeholders needed to compile workflow skeletons.

## Required Inspection

- `AGENTS.md`
- Latest versioned spec sections on Temporal, execution authority, reconciliation, kill switch, reporting, and config
- Existing `apps/workers`, `packages/*`, `config/temporal.yaml`, `tests/temporal`, and scripts if present
- Existing foundation/config/logging code
- Existing data/backtest contracts from previous milestones

## Implementation Tasks

1. Add Temporal configuration loading for namespace, address, task queues, schedules, and retry policy definitions.
2. Implement worker bootstrap for configured task queues.
3. Create deterministic workflow skeletons that only orchestrate state, timers, signals, queries, and activity calls.
4. Define activity interfaces for broker, database, AI, news, alerting, data refresh, and reporting side effects.
5. Add required signals such as manual kill switch, pause new risk, resume after review, force reconciliation, force report, approve level change, and acknowledge incident.
6. Add required dashboard queries as workflow query contracts where appropriate.
7. Add tests that verify skeleton workflows start, call mocked activities, and remain deterministic where the SDK/test framework supports it.
8. Document workflow/activity boundaries and prohibited calls inside workflow code.

## Spec Alignment Checks

- Workflow code must not call broker APIs, AI APIs, news APIs, databases, random generation, or wall-clock time directly.
- Execution-critical workflows must use dedicated execution and reconciliation task queues.
- Broker order submission retry behavior must not blindly retry without idempotency lookup.
- Kill-switch workflow must block new risk while preserving or allowing risk-reducing exits according to the spec.
- Temporal must complement, not replace, the Postgres business/audit ledger.

## Tests / Validation

- Run Temporal unit/replay tests if configured.
- Run general unit tests for workflow contracts and config loading.
- Run type checks if configured.
- If a Temporal test server or SDK feature is unavailable, document the blocker and the exact command to run after setup.

## Documentation Updates

- Update `docs/temporal_workflows.md` or equivalent with implemented workflow names, task queues, activity boundaries, signals, queries, and determinism rules.
- Do not claim broker execution works until later milestones implement and test it.
- Update the latest spec only if an approved deviation requires it.

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
