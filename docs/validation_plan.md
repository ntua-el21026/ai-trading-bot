# Validation Plan

This document describes the current validation scaffold.

The latest source of truth is `docs/app/Autonomous_AI_Trading_Bot_SPEC_v0.3.md`. Milestone 06 adds unit tests for config loading, data models, raw payload hashing, deterministic feature utilities, universe filtering, backtest metrics/engine scaffolding, Temporal contracts, deterministic regime/strategy/exit helpers, risk checks, position sizing, kill-switch state, execution intents, idempotency, passive order lifecycle transitions, broker model validation, Alpaca stream mapping, safe adapter gating, REST fallback snapshots, reconciliation mismatches, and incident recommendations. It does not validate real Alpaca paper credentials, live Temporal replay behavior, AI schema behavior, database persistence, or profitability.

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
- Risk checks are fixture-tested for accepted and rejected new-risk paths, stale data, kill switch, duplicate intent, exposure, and loss-limit failures.
- Position sizing is fixture-tested for configured caps, multipliers, invalid stop distance, and below-one-share rejection.
- Execution intent and idempotency helpers are fixture-tested for approved-risk intent creation, protective-stop validation, expiration checks, deterministic client order IDs, duplicate detection, and passive lifecycle transition rejection.
- Broker model validation is fixture-tested without credentials.
- Alpaca `trade_updates` mapping is fixture-tested without websocket connections.
- REST fallback snapshot construction is fixture-tested with the 30-second spec interval.
- Reconciliation comparison is fixture-tested for clean state, missing/extra positions, missing protective stops, duplicate open entry orders, unexpected short positions, unsupported broker asset classes, unknown open broker orders, missing fills, quantity mismatch, average-price mismatch, account-equity mismatch, stale snapshots, and Temporal workflow inconsistency.
- Incident severity, pause-new-risk recommendations, and flatten-if-safe recommendations are fixture-tested.

## Backtest Policy

Backtests are validation tools. They are not proof of live profitability. They can help validate data plumbing, feature calculations, assumptions, metrics, and later strategy behavior.

If point-in-time universe membership is unavailable, stock-universe backtests must be labeled optimistic. The current research universe scaffolding exposes an `optimistic_backtest_warning` flag for this purpose.

## Future Validation Scope

Later milestones must add real integration, failure, backtest, and paper dry-run checks required by the latest spec. Backtests and paper trading must not be represented as proof of live profitability.

## Current Assumptions

Earnings blackout logic requires a caller-supplied trading calendar and earnings date. If earnings
data or the relevant trading session is unavailable, the status is `unknown` and candidate entries
are blocked conservatively. Exits remain allowed during blackout according to the latest spec.
