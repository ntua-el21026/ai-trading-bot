# 06 - Broker Reconciliation

You are Codex working inside this repository.

## Context

This repository is governed by `AGENTS.md` and the latest versioned autonomous trading bot specification. Codex must read both before editing. Broker state must be reconciled before new-risk execution, and execution must be idempotent, auditable, and broker-reconciled.

## Mandatory First Steps

1. Read `AGENTS.md`.
2. Identify and read the latest versioned spec.
3. Inspect the relevant files before editing.
4. Check whether the requested work is compliant with the latest spec.
5. If not compliant, stop and ask for approval.

## Goal

Implement broker adapter boundaries and reconciliation logic for Alpaca paper mode, including stream/REST fallback abstractions and mismatch incident handling, without enabling live trading.

## Scope

- Broker adapter interface.
- Alpaca paper-mode adapter implementation or safe adapter skeleton.
- `trade_updates` stream handling abstraction or event model.
- REST fallback abstraction for orders, fills, positions, and account snapshots.
- Broker/internal reconciliation models and services.
- Mismatch incident creation and pause-new-risk behavior.
- Tests using mocks/fixtures, not live credentials.

## Out of Scope

- No live trading enablement.
- No live credential configuration.
- No uncontrolled broker API calls.
- No execution path outside Temporal activities/workflows.
- No bypass of `ExecutionIntent`, risk checks, protective stop requirements, or kill-switch behavior.
- No crypto, options, futures, shorting, margin, or unsupported asset classes.

## Required Inspection

- `AGENTS.md`
- Latest versioned spec sections on broker, execution engine, broker reconciliation, kill switch, database specification, Temporal workflows, config, environment variables, and testing
- Existing `packages/execution`, `packages/risk`, `apps/workers/activities`, `config/execution.yaml`, `config/system.yaml`, and tests
- Existing order, fill, position, execution intent, and incident models
- Existing Temporal workflow/activity contracts

## Implementation Tasks

1. Define or refine broker adapter protocols for account, orders, fills, positions, stream events, submit/cancel, and stop order operations.
2. Implement Alpaca paper-mode adapter behavior only where safe and configured; otherwise provide testable skeletons behind explicit environment checks.
3. Add stream event models for `trade_updates` and map them to internal order/fill lifecycle events.
4. Add REST fallback paths for reconciliation snapshots.
5. Implement reconciliation comparison between broker account/orders/fills/positions and internal ledger state.
6. Detect critical mismatches such as broker position without internal position, internal position without broker position, missing protective stop, duplicate active entry, unknown open order, and stale state.
7. Create structured incidents and trigger pause-new-risk or kill-switch state transitions according to severity.
8. Add tests with fixture payloads for normal reconciliation, stream update mapping, REST fallback, mismatches, and incident behavior.

## Spec Alignment Checks

- Broker state must be treated as operational truth while Postgres remains the business/audit ledger.
- New-risk execution must require pre-submit broker reconciliation.
- Missing or unconfirmed protective stops must trigger the latest-spec stop-failure policy.
- Ambiguous order submission must not be blindly retried without idempotency lookup.
- Live trading must remain disabled unless explicitly requested and separately approved.

## Tests / Validation

- Run unit tests for broker adapter mapping and reconciliation comparison.
- Run integration tests only with mocked payloads or Alpaca paper credentials if explicitly available and safe.
- Run Temporal activity tests if reconciliation activities are added.
- Document any live/paper external tests not run and exact commands for later.

## Documentation Updates

- Update execution and reconciliation documentation with adapter boundaries, stream/REST fallback behavior, mismatch handling, and incident policy.
- Update `.env.example` only with variable names if needed.
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
