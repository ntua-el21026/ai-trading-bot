# AI Trading Bot

Spec-governed autonomous AI-assisted trading bot repository.

The latest identified source-of-truth spec is:

```text
docs/app/Autonomous_AI_Trading_Bot_SPEC_v0.3.md
```

## Current Status

This repository is at Milestone 03 Temporal workflow foundation scaffolding.

Implemented pieces:

- `uv`-compatible `pyproject.toml`
- safe YAML defaults under `config/`
- typed config loading in `packages/core/config.py`
- structured logging setup in `packages/core/logging.py`
- `.env.example` with variable names only
- typed data models and raw payload hashing under `packages/data/`
- offline provider protocols with no live network calls
- deterministic daily feature functions
- live/research universe filter scaffolding
- deterministic backtest models, metrics, and explicit-signal engine skeleton
- Temporal SDK dependency and typed Temporal client bootstrap
- Temporal task queue mapping for the spec-defined queues
- workflow skeletons and placeholder activity contracts under `apps/workers/`
- signal, query, and retry-policy contracts
- unit tests for config, data models, features, universe filters, backtest metrics, and Temporal contracts

Not implemented yet:

- trading strategy logic
- broker adapters or order submission
- AI/news integration
- database migrations
- dashboard/control plane
- live trading

## Setup

Use Python `>=3.12` with `uv`.

```bash
uv sync --dev
```

## Validation

Run unit tests:

```bash
uv run --group dev pytest tests/unit
```

Run Temporal contract tests:

```bash
uv run --group dev pytest tests/temporal
```

Optional local checks once dependencies are installed:

```bash
uv run --group dev ruff check .
uv run --group dev mypy packages apps tests
```

## Temporal Skeletons

The worker bootstrap is available after a local Temporal service is running:

```bash
uv run python scripts/start_worker.py --task-queue execution-task-queue
```

`scripts/seed_temporal_schedules.py` is dry-run only in this milestone and does not create or
activate production schedules.

## Safety Defaults

The foundation config defaults to paper/dry-run behavior with live trading and autonomous execution disabled. It does not contain secrets and does not implement broker access.

Backtests in this repository are validation tools only. They are not proof of live profitability. Stock-universe backtests without point-in-time universe data must be treated as optimistic.
