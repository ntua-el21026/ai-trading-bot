# Architecture

This document describes the current foundation and data/backtest architecture.

The latest source of truth is `docs/app/Autonomous_AI_Trading_Bot_SPEC_v0.3.md`. Current repository implementation is limited to Milestone 02 data/backtest scaffolding: project metadata, safe configuration defaults, typed config loading, structured logging helpers, offline data contracts, deterministic feature utilities, universe filters, and explicit-signal backtest utilities.

## Target Shape

- Temporal orchestrates execution-critical workflows.
- Postgres or Supabase Postgres is the durable business and audit ledger.
- Deterministic strategy, risk, execution, and reconciliation code owns trading authority.
- AI is bounded to shortlist news/catalyst/risk intelligence and has no broker write path.
- Vercel is dashboard/control-plane only.

## Current Milestone Status

- Data models exist for adjusted daily OHLCV bars, quotes, asset metadata, raw provider payload metadata, feature rows, and universe membership.
- Raw provider payload hashing helpers and repository protocol contracts exist.
- Provider interfaces exist as protocols only and make no live network calls.
- Feature utilities calculate daily returns, SMA, EMA, ATR14, ATR percent, volume averages, volume ratios, highs, dollar volume, and RS63 inputs.
- Universe filters support live and research universe scaffolding with point-in-time optimism warnings.
- Backtesting utilities support explicit fixture signals, basic mark-to-market equity, and validation metrics.
- No API service is implemented.
- No worker process is implemented.
- No dashboard is implemented.
- No trading logic is implemented.
- No broker adapter is implemented.
- No database schema or migration is implemented.
- No AI/news integration is implemented.

Future milestones must keep implementation aligned with the latest spec before adding behavior.
