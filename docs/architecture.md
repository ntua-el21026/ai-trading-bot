# Architecture

This document is a foundation placeholder for the autonomous AI trading bot architecture.

The latest source of truth is `docs/app/Autonomous_AI_Trading_Bot_SPEC_v0.3.md`. Current repository implementation is limited to Milestone 01 foundation scaffolding: project metadata, safe configuration defaults, typed config loading, structured logging helpers, and documentation placeholders.

## Target Shape

- Temporal orchestrates execution-critical workflows.
- Postgres or Supabase Postgres is the durable business and audit ledger.
- Deterministic strategy, risk, execution, and reconciliation code owns trading authority.
- AI is bounded to shortlist news/catalyst/risk intelligence and has no broker write path.
- Vercel is dashboard/control-plane only.

## Current Milestone Status

- No API service is implemented.
- No worker process is implemented.
- No dashboard is implemented.
- No trading logic is implemented.
- No broker adapter is implemented.
- No database schema or migration is implemented.

Future milestones must keep implementation aligned with the latest spec before adding behavior.
