# Validation Plan

This document describes the current validation scaffold.

The latest source of truth is `docs/app/Autonomous_AI_Trading_Bot_SPEC_v0.3.md`. Milestone 04 adds unit tests for config loading, data models, raw payload hashing, deterministic feature utilities, universe filtering, backtest metrics/engine scaffolding, Temporal contracts, and deterministic regime/strategy/exit helpers. It does not validate execution, broker integration, live Temporal replay behavior, AI schema behavior, database persistence, or profitability.

## Foundation Checks

- Config files load from `config/`.
- Safe defaults remain disabled for live trading and autonomous execution.
- Forbidden v0.1 instruments and authorities remain disabled in config.
- Structured logging can be initialized.
- Raw provider payload hashes are stable for canonical JSON payloads.
- Adjusted daily OHLCV model validation rejects invalid price ranges.
- Daily feature utilities are deterministic and fixture-based.
- Live universe filters preserve the approved US equities/ETF scope.
- Research universe output marks optimistic warnings when point-in-time membership is unavailable.
- Backtest metrics and explicit-signal engine behavior are fixture-tested without broker calls.
- Regime classification is fixture-tested for `RISK_ON`, `CAUTION`, and `RISK_OFF`.
- Strategy candidate evaluation is fixture-tested for long-only accepted/rejected candidates, 20D and 55D breakout variants, RS63, ATR percent, earnings blackout, held-symbol, and duplicate-intent gates.
- Exit helpers are fixture-tested for initial stops, trailing stops, technical exits, time stops, and fail-fast exits without submitting orders.

## Backtest Policy

Backtests are validation tools. They are not proof of live profitability. They can help validate data plumbing, feature calculations, assumptions, metrics, and later strategy behavior.

If point-in-time universe membership is unavailable, stock-universe backtests must be labeled optimistic. The current research universe scaffolding exposes an `optimistic_backtest_warning` flag for this purpose.

## Future Validation Scope

Later milestones must add unit, Temporal, integration, failure, backtest, and paper dry-run checks required by the latest spec. Backtests and paper trading must not be represented as proof of live profitability.

## Current Assumptions

Earnings blackout logic requires a caller-supplied trading calendar and earnings date. If earnings
data or the relevant trading session is unavailable, the status is `unknown` and candidate entries
are blocked conservatively. Exits remain allowed during blackout according to the latest spec.
