# 05 - Risk And Execution Core

You are Codex working inside this repository.

## Context

This repository is governed by `AGENTS.md` and the latest versioned autonomous trading bot specification. Codex must read both before editing. Risk logic is deterministic and non-bypassable. Execution authority belongs to the deterministic execution pipeline, and every live order requires a valid `ExecutionIntent`.

## Mandatory First Steps

1. Read `AGENTS.md`.
2. Identify and read the latest versioned spec.
3. Inspect the relevant files before editing.
4. Check whether the requested work is compliant with the latest spec.
5. If not compliant, stop and ask for approval.

## Goal

Implement the deterministic risk and execution core: risk checks, position sizing, `ExecutionIntent`, idempotency design, and order lifecycle abstractions without enabling live trading.

## Scope

- Risk input/output models.
- Config-driven risk checks.
- Position sizing calculations.
- `ExecutionIntent` schema/model with required fields.
- Client order ID root/idempotency design.
- Order request and lifecycle abstractions.
- Rejection logging/event contracts.
- Unit tests for risk checks, sizing, and execution intent construction.

## Out of Scope

- No live broker credentials.
- No live trading enablement.
- No actual broker order submission unless implemented only as a mocked/paper-safe boundary and approved by the current milestone.
- No changes to risk limits, stop policy, autonomy level, or execution policy without explicit approval and spec update.
- No AI authority over risk or execution.

## Required Inspection

- `AGENTS.md`
- Latest versioned spec sections on autonomous execution authority, risk engine, execution engine, kill switch, database specification, config, environment variables, and testing
- Existing `packages/risk`, `packages/execution`, `packages/core`, `apps/workers`, `config/risk.yaml`, `config/execution.yaml`, and tests
- Existing strategy candidate/decision models
- Existing Temporal workflow skeletons

## Implementation Tasks

1. Implement deterministic risk-check models and result types.
2. Implement pre-new-risk checks for environment validity, paper/live mode, autonomy flags, approved symbols, asset class, data freshness, reconciliation status, kill switch state, exposures, cash buffer, loss limits, protective stop availability, duplicate intent prevention, and Temporal consistency where data is available.
3. Implement position sizing from configured max position size, max risk per trade, stop distance, and exposure constraints.
4. Implement `ExecutionIntent` with required latest-spec fields, expiration, status, `temporal_workflow_id`, and client order ID root support.
5. Implement idempotent client order ID construction and duplicate-intent rejection logic.
6. Add order lifecycle abstractions without concrete live broker behavior.
7. Ensure every rejection is structured for audit logging and notification in later milestones.
8. Add tests for accepted/rejected risk paths, sizing edge cases, stale data, kill switch, duplicate intent, and invalid execution intent.

## Spec Alignment Checks

- Every new-risk order path must require passed risk checks, valid reconciliation, kill switch off, and valid `ExecutionIntent`.
- Risk limits must match latest-spec config and must not be silently changed.
- AI must not override risk limits, increase position size, disable stops, disable kill switches, or mutate live strategy rules.
- Protective stop availability must be required before any new-risk order.
- Live defaults must remain disabled.

## Tests / Validation

- Run unit tests for risk checks, position sizing, execution intent validation, idempotency, and rejection behavior.
- Run type checks or lint if configured.
- Run Temporal contract tests if this milestone touches workflow interfaces.
- Document any integration tests deferred to broker reconciliation or paper milestones.

## Documentation Updates

- Update risk and execution policy docs with implemented checks and lifecycle contracts.
- Update config documentation if config files are created or changed.
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
