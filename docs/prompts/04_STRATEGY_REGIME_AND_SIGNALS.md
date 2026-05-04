# 04 - Strategy, Regime, And Signals

You are Codex working inside this repository.

## Context

This repository is governed by `AGENTS.md` and the latest versioned autonomous trading bot specification. Codex must read both before editing. Strategy, regime, and signal logic must be deterministic; AI is not allowed to mutate live strategy rules or directly generate broker orders.

## Mandatory First Steps

1. Read `AGENTS.md`.
2. Identify and read the latest versioned spec.
3. Inspect the relevant files before editing.
4. Check whether the requested work is compliant with the latest spec.
5. If not compliant, stop and ask for approval.

## Goal

Implement deterministic regime, strategy signal, and candidate-selection logic for long-only US equities/ETF swing trading without live execution.

## Scope

- Rule-based market regime engine.
- Deterministic breakout signal rules.
- 20D and 55D breakout variants where specified.
- RS63 and relative-strength percentile hooks.
- ATR/volatility filters and ATR-based stop input calculations.
- Volume, price, ADV, and approved-universe filters.
- Earnings blackout placeholder or deterministic implementation if data is available.
- Candidate and signal models needed by later AI/risk/execution milestones.
- Unit tests for pure strategy/regime/signal functions.

## Out of Scope

- No broker order submission.
- No execution-intent creation unless already required as a passive downstream interface.
- No AI-generated trade ideas.
- No live strategy mutation.
- No unsupported instruments, shorting, leverage, options, futures, crypto, or prediction-market logic.
- No parameter optimization that changes production defaults without approval.

## Required Inspection

- `AGENTS.md`
- Latest versioned spec sections on module specification, decision arbiter, strategy config, regime config, validation, and testing
- Existing `packages/strategy`, `packages/data`, `packages/backtesting`, `packages/core`, `config/strategy.yaml`, `config/regime.yaml`, `config/universe.yaml`, and tests
- Existing feature model outputs from the data/backtest milestone

## Implementation Tasks

1. Implement regime classification from configured SPY SMA/volatility rules.
2. Implement strategy candidate generation from deterministic daily features.
3. Implement primary 20D breakout behavior and 55D research variant handling according to the latest spec.
4. Implement RS63 and relative-strength gating/scoring hooks.
5. Implement ATR14 percent filters and ATR stop input calculations without placing stops.
6. Implement volume ratio, price, ADV, approved universe, and excluded instrument checks.
7. Add an earnings blackout placeholder that defaults conservatively if earnings data is missing, unless the spec says otherwise.
8. Produce deterministic candidate records suitable for AI shortlist analysis and later risk checks.
9. Add focused tests covering regime states, candidate acceptance/rejection, edge cases, and config-driven thresholds.

## Spec Alignment Checks

- Regime must remain a gate and risk multiplier, not an AI opinion.
- AI must not scan the full universe or generate direct trade ideas.
- Strategy must remain long-only for US equities/ETFs.
- 20D/55D, RS63, ATR, volume, price, ADV, and earnings rules must match latest-spec config unless approved otherwise.
- Backtest or signal outputs must not be claimed as profitability proof.

## Tests / Validation

- Run unit tests for feature inputs, regime classification, signal generation, candidate filtering, and edge cases.
- Run backtest smoke tests if a backtest skeleton exists and can run without external services.
- Run type checks or lint if configured.
- Document any data-fixture gaps.

## Documentation Updates

- Update strategy/regime documentation with implemented deterministic rules and known placeholders.
- Update validation docs only with implemented behavior and assumptions.
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
