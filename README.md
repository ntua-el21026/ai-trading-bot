# AI Trading Bot

Spec-governed autonomous AI-assisted trading bot repository.

The latest identified source-of-truth spec is:

```text
docs/app/Autonomous_AI_Trading_Bot_SPEC_v0.3.md
```

## Current Status

This repository is at Milestone 06 broker-reconciliation boundary scaffolding.

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
- deterministic `RISK_ON` / `CAUTION` / `RISK_OFF` regime classification
- long-only deterministic candidate evaluation for configured trend, breakout, volume, RS63, ATR, universe, price, ADV, earnings, held-symbol, and duplicate-intent gates
- stop-level and exit-trigger calculation helpers that do not submit orders
- deterministic risk checks for new-risk eligibility
- position sizing from configured risk and position caps
- kill-switch state models
- passive `ExecutionIntent`, idempotency, order lifecycle, and rejection contracts
- dependency-free broker adapter protocols and a safe Alpaca paper adapter skeleton
- normalized broker account/order/fill/position/protective-stop/stream models
- fixture-only Alpaca `trade_updates` mapping to internal broker lifecycle events
- REST fallback snapshot contracts using the spec's 30-second fallback interval
- passive broker/internal reconciliation snapshots, mismatch classification, incident contracts,
  and pause-new-risk or flatten-if-safe recommendations
- unit tests for config, data models, features, universe filters, backtest metrics, Temporal contracts, strategy/regime/exit helpers, risk checks, sizing, kill switch, execution intent, and idempotency
- unit tests for broker models, Alpaca stream mapping, safe adapter gating, REST fallback snapshots,
  reconciliation clean state, mismatch detection, and incident recommendations

Not implemented yet:

- executable broker order submission
- real Alpaca SDK/client integration
- database migrations or durable ledger persistence
- AI/news integration
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

The foundation config defaults to paper/dry-run behavior with live trading and autonomous execution disabled. It does not contain secrets and does not execute broker calls. Broker adapter methods are protocol/skeleton boundaries until a later milestone wires an explicitly configured paper client through Temporal activities.

Backtests in this repository are validation tools only. They are not proof of live profitability. Stock-universe backtests without point-in-time universe data must be treated as optimistic.
