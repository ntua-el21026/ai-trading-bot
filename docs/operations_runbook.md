# Operations Runbook

This document is a foundation placeholder for operations.

The latest source of truth is `docs/app/Autonomous_AI_Trading_Bot_SPEC_v0.3.md`. Milestone 06 does not implement production services, active schedules, real broker clients, alerts, reports, paper trading runs, or live trading. It does define passive broker/reconciliation contracts and incident recommendations.

## Current Foundation Operations

1. Install dependencies with `uv sync --dev`.
2. Validate configuration with `uv run pytest tests/unit/test_config.py`.
3. Keep `.env` files local and uncommitted.
4. Treat `.env.example` as variable names only.

## Current Reconciliation Operations

Broker reconciliation is currently a pure comparison contract:

1. Build a normalized broker snapshot from fixture, stream, or future REST activity output.
2. Build a passive internal ledger snapshot from fixture or future database activity output.
3. Compare snapshots with `compare_broker_and_internal`.
4. Treat critical incidents as pause-new-risk recommendations.
5. Treat missing protective stops according to the configured warning, critical, and flatten
   thresholds.

No current operation submits, cancels, or flattens broker orders. Flattening is represented only as a
`flatten_if_safe` recommendation for later execution workflow handling.

## Future Operations Scope

Later milestones must document real worker startup, Temporal schedules, paper trading procedures,
real broker credential setup, database-backed reconciliation, incident response, kill-switch
behavior, reporting, and Level 4 micro-live readiness gates.
