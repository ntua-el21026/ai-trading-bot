# 02 - Data And Backtest Core

You are Codex working inside this repository.

## Context

This repository is governed by `AGENTS.md` and the latest versioned autonomous trading bot specification. Codex must read both before editing. Data and backtesting are validation tools and must not be presented as proof of profitability.

## Mandatory First Steps

1. Read `AGENTS.md`.
2. Identify and read the latest versioned spec.
3. Inspect the relevant files before editing.
4. Check whether the requested work is compliant with the latest spec.
5. If not compliant, stop and ask for approval.

## Goal

Build the deterministic data and backtest core needed for later strategy validation, including market data abstractions, raw payload persistence contracts, OHLCV models, feature scaffolding, backtest skeleton, and metrics skeleton.

## Scope

- Market data provider interfaces or protocols.
- Raw provider payload persistence model or repository boundary.
- Adjusted daily OHLCV domain models.
- Feature calculation scaffolding for daily/swing timeframe data.
- Universe builder scaffolding for approved live and broader research universes.
- Backtest engine skeleton with deterministic inputs/outputs.
- Metrics/report skeleton for validation outputs.
- Unit tests for pure model and feature scaffolding where implemented.

## Out of Scope

- No broker execution or order submission.
- No Temporal execution workflows except passive interfaces if already established.
- No AI/news analysis.
- No live trading configuration.
- No real provider credentials or network calls unless explicitly isolated behind dry-run/test adapters.
- No claims of profitability.

## Required Inspection

- `AGENTS.md`
- Latest versioned spec sections for data, database, validation, configuration, and roadmap
- Existing `packages/data`, `packages/backtesting`, `packages/core`, `config/`, `tests/`, and `docs/` if present
- Existing database or persistence abstractions if present
- Existing project configuration and test setup

## Implementation Tasks

1. Implement or refine market data abstractions for adjusted daily bars, quotes/reference data if specified, and provider raw payloads.
2. Define typed OHLCV and provider-payload models consistent with latest-spec database concepts.
3. Add raw payload hashing/persistence boundaries without requiring a live database if database infrastructure is not yet present.
4. Implement feature calculation scaffolding for returns, volume, ATR, SMA/EMA, highs, relative strength inputs, and freshness metadata as applicable to this milestone.
5. Add a deterministic backtest engine skeleton that can later consume signals and risk/execution assumptions.
6. Add metrics skeletons for returns, drawdown, exposure, trade counts, slippage assumptions, and benchmark comparison hooks.
7. Add tests around pure functions and model validation.
8. Document optimistic labeling requirements for non-point-in-time universe backtests.

## Spec Alignment Checks

- Backtests must be labeled as validation, not proof of live profitability.
- If point-in-time universe data is unavailable, stock-universe backtests must be labeled optimistic.
- Data models must support raw provider payload preservation and audit hashes.
- The live universe must remain US equities/ETFs only with excluded instruments blocked by config or model constraints.
- Production signals must not rely solely on Alpaca free IEX feed if the spec prohibits it.

## Tests / Validation

- Run unit tests for data models, feature scaffolding, and backtest skeleton.
- Run type checks or lint if configured.
- If external data is needed, use fixtures or mocked providers by default.
- Document any provider/network tests not run and the exact command needed to run them later.

## Documentation Updates

- Update data/backtest documentation with implemented interfaces and limitations.
- Update validation docs with backtest assumptions and optimism warnings.
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
