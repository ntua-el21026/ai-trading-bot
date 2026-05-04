# AI Trading Bot

Spec-governed autonomous AI-assisted trading bot repository.

The latest identified source-of-truth spec is:

```text
docs/app/Autonomous_AI_Trading_Bot_SPEC_v0.3.md
```

## Current Status

This repository is at Milestone 01 foundation scaffolding.

Implemented foundation pieces:

- `uv`-compatible `pyproject.toml`
- safe YAML defaults under `config/`
- typed config loading in `packages/core/config.py`
- structured logging setup in `packages/core/logging.py`
- `.env.example` with variable names only
- foundation documentation placeholders
- narrow unit tests for config loading and safe defaults

Not implemented yet:

- trading strategy logic
- Temporal workflows or workers
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

Run the foundation tests:

```bash
uv run pytest tests/unit/test_config.py
```

Optional local checks once dependencies are installed:

```bash
uv run ruff check .
uv run mypy packages tests
```

## Safety Defaults

The foundation config defaults to paper/dry-run behavior with live trading and autonomous execution disabled. It does not contain secrets and does not implement broker access.
