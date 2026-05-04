# Operations Runbook

This document is a foundation placeholder for operations.

The latest source of truth is `docs/app/Autonomous_AI_Trading_Bot_SPEC_v0.3.md`. Milestone 01 does not implement services, workers, schedules, broker access, alerts, reports, paper trading, or live trading.

## Current Foundation Operations

1. Install dependencies with `uv sync --dev`.
2. Validate configuration with `uv run pytest tests/unit/test_config.py`.
3. Keep `.env` files local and uncommitted.
4. Treat `.env.example` as variable names only.

## Future Operations Scope

Later milestones must document worker startup, Temporal schedules, paper trading procedures, reconciliation, incident response, kill-switch behavior, reporting, and Level 4 micro-live readiness gates.
