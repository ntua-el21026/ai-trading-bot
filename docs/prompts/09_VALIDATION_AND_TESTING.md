# 09 - Validation And Testing

You are Codex working inside this repository.

## Context

This repository is governed by `AGENTS.md` and the latest versioned autonomous trading bot specification. Codex must read both before editing. Validation must focus on correctness, safety, determinism, auditability, orchestration, and operational behavior. Backtests and paper trading must not be treated as proof of live profitability.

## Mandatory First Steps

1. Read `AGENTS.md`.
2. Identify and read the latest versioned spec.
3. Inspect the relevant files before editing.
4. Check whether the requested work is compliant with the latest spec.
5. If not compliant, stop and ask for approval.

## Goal

Build out the project validation and testing harness across unit, integration, Temporal, backtest, paper dry-run, and failure simulation categories required by the latest spec.

## Scope

- Unit tests for data, feature, regime, strategy, risk, sizing, AI schema, execution intent, order request, kill switch, and config logic.
- Temporal workflow replay/determinism tests.
- Integration tests for database boundaries, Temporal worker startup, broker paper adapter boundaries, reconciliation, AI parsing, and scheduled dry runs where feasible.
- Backtest validation harness with split design, slippage/fee assumptions, benchmarks, ablations, and optimism warnings.
- Failure simulations for stale data, invalid AI, broker timeout, duplicate order, partial fill, missing stop, reconciliation mismatch, database outage, worker crash, and kill-switch activation.

## Out of Scope

- No live trading enablement.
- No claim that passing tests proves profitability.
- No production credential use.
- No skipped safety checks to make tests pass.
- No risk/strategy parameter changes without approval and spec update.

## Required Inspection

- `AGENTS.md`
- Latest versioned spec sections on validation plan, testing requirements, paper trading policy, acceptance criteria, risk, execution, reconciliation, AI, and Temporal
- Existing `tests/`, `packages/`, `apps/`, `scripts/`, `docs/validation_plan.md`, and CI config if present
- Existing fixtures, sample payloads, and test commands

## Implementation Tasks

1. Inventory existing test coverage against the latest spec's required unit, Temporal, integration, and failure tests.
2. Add missing tests in the narrowest maintainable way.
3. Add fixtures for market data, AI outputs, broker stream updates, REST snapshots, execution intents, and reconciliation mismatches.
4. Add backtest validation harness support for date splits, benchmark hooks, slippage/fee assumptions, ablations, and Monte Carlo placeholders if not yet implemented.
5. Add paper execution dry-run checks that verify orchestration and lifecycle without live trading.
6. Add CI or local validation command documentation if absent.
7. Ensure tests do not require real secrets by default.

## Spec Alignment Checks

- Required Level 4 micro-live acceptance criteria must be represented in validation docs or checks where practical.
- Backtests must include fees/slippage assumptions and no-profitability-proof language.
- Paper trading must be framed as operational rehearsal.
- Failure tests must cover missing stops, duplicate orders, reconciliation incidents, invalid AI output, and kill-switch transitions.
- Tests must not weaken risk, execution, or AI safety invariants.

## Tests / Validation

- Run the full relevant test suite if feasible.
- Run narrower suites first when debugging.
- Run type checks, lint, and build checks if configured.
- Report every command actually run and its result.
- If any required check cannot run, explain why and provide the exact command to run manually after prerequisites are installed.

## Documentation Updates

- Update `docs/validation_plan.md` or equivalent with implemented validation commands, gaps, assumptions, and acceptance gates.
- Update README test instructions if useful.
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
