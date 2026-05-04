# Validation Plan

This document is a foundation placeholder for validation planning.

The latest source of truth is `docs/app/Autonomous_AI_Trading_Bot_SPEC_v0.3.md`. Milestone 01 adds only narrow config-loading tests and does not validate strategy, execution, broker integration, Temporal behavior, AI schema behavior, or profitability.

## Foundation Checks

- Config files load from `config/`.
- Safe defaults remain disabled for live trading and autonomous execution.
- Forbidden v0.1 instruments and authorities remain disabled in config.
- Structured logging can be initialized.

## Future Validation Scope

Later milestones must add unit, Temporal, integration, failure, backtest, and paper dry-run checks required by the latest spec. Backtests and paper trading must not be represented as proof of live profitability.
