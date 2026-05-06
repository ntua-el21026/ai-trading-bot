# AI Trading Bot

Spec-governed autonomous AI-assisted trading bot repository.

The latest identified source-of-truth spec is:

```text
docs/app/Autonomous_AI_Trading_Bot_SPEC_v0.3.md
```

## Current Status

This repository is at Milestone 16 fake/local end-to-end paper dry-run orchestration with
fake/local defaults.

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
- workflow skeletons and safe Temporal activity contracts under `apps/workers/`
- signal, query, and retry-policy contracts
- deterministic `RISK_ON` / `CAUTION` / `RISK_OFF` regime classification
- long-only deterministic candidate evaluation for configured trend, breakout, volume, RS63, ATR, universe, price, ADV, earnings, held-symbol, and duplicate-intent gates
- stop-level and exit-trigger calculation helpers that do not submit orders
- deterministic risk checks for new-risk eligibility
- position sizing from configured risk and position caps
- kill-switch state models
- passive `ExecutionIntent`, idempotency, order lifecycle, and rejection contracts
- dependency-free broker adapter protocols and a paper-only Alpaca adapter behind explicit gates
- normalized broker account/order/fill/position/protective-stop/stream models
- fixture-only Alpaca `trade_updates` mapping to internal broker lifecycle events
- fake Alpaca client support for account/order/fill/position snapshots, order lookup, paper entry
  submit, cancel, protective-stop submit/verify, stream-event mapping, and REST fallback contracts
- broker Temporal activity contracts that default to fake Alpaca paper adapters and perform no real
  Alpaca calls in default tests
- pure daily and weekly report generation from supplied ledger/read-model snapshots under
  `packages/reporting/`
- deterministic Markdown report rendering and report persistence through the ledger repository
- alerting contracts, severity/category routing, fake alert adapter, and fail-closed Telegram/email
  adapter skeletons under `packages/alerting/`
- reporting/alerting/dashboard Temporal activity contracts that use local ledger repositories and
  fake alert adapters by default
- fake/local paper dry-run orchestration under `packages/paper/` that exercises fixture data,
  candidate persistence, neutral/fake AI output, deterministic risk checks, execution-intent
  creation, fake broker submit/fill/protective-stop verification, reconciliation, fake alerts,
  daily report generation, and dashboard/read-model snapshots
- safe CLI entry point `scripts/run_paper_dry_run.py` that defaults to fake/local mode and submits
  no broker orders
- REST fallback snapshot contracts using the spec's 30-second fallback interval
- passive broker/internal reconciliation snapshots, mismatch classification, incident contracts,
  and pause-new-risk or flatten-if-safe recommendations
- bounded AI/news provider protocols for deterministic shortlist candidates only
- ticker-tagged news article normalization and deduplication helpers
- versioned AI trade-research prompt template
- strict schema-validated AI trade-research output models and neutral fallback behavior
- deterministic AI event scoring, hard-block classification, and non-increasing size-multiplier
  helpers
- raw prompt/output persistence payload contracts with audit hashes
- Postgres-oriented audit-ledger migration under `db/migrations/`
- local `packages/ledger/` schema, typed records, and SQLite repository implementation for
  deterministic tests without managed database credentials
- ledger tables for symbols, raw payloads, OHLCV, features, regimes, candidates, AI outputs,
  decisions, risk checks, execution intents, orders, fills, positions, reconciliations, system
  events, and reports
- typed ledger activity request/response models under `apps/workers/app/activities/models.py`
- safe ledger-backed Temporal activity functions under `apps/workers/app/activities/ledger.py`
  using local/fake SQLite repositories by default
- workflow skeletons aligned to ledger persistence activity boundaries without direct database,
  broker, AI/news, provider, network, clock, or random calls in workflow code
- Temporal AI/news activity boundaries that perform no external calls
- dashboard/control-plane read models for system state, workflows, intents, orders, positions,
  incidents, reconciliation, kill switch, candidates/signals, AI outputs, reports, and risk status
- server-side control-plane contracts mapping safe manual controls to existing Temporal signal names
- minimal `apps/api/` and `apps/dashboard/` scaffolds with frontend environment guardrails and no
  frontend framework dependencies
- validation harness contracts for spec-defined backtest splits, benchmarks, costs, ablations,
  Monte Carlo placeholders, failure simulations, and paper dry-run checks
- paper trading runbook, daily/weekly checklist templates, report templates, incident response flow,
  frozen paper acceptance criteria, and paper-to-Level-4 handoff gates
- Level 4 micro-live readiness documentation, credential separation checklist, kill-switch re-arm
  checklist, readiness checklist, and go/no-go template
- unit tests for config, data models, features, universe filters, backtest metrics, Temporal contracts, strategy/regime/exit helpers, risk checks, sizing, kill switch, execution intent, and idempotency
- unit tests for broker models, Alpaca stream mapping, paper-only adapter gates, fake-client
  submit/cancel/stop/verify boundaries, REST fallback snapshots, reconciliation clean state,
  mismatch detection, and incident recommendations
- unit tests for AI/news article validation, deduplication, prompt loading, strict parsing,
  fallbacks, scoring, hard-block policy, and persistence hashes
- unit tests for dashboard read models, safe control actions, Temporal signal mapping, no order-entry
  controls, and frontend secret guardrails
- unit tests for validation harness assumptions, failure-simulation contracts, paper dry-run safety,
  and workflow side-effect boundary checks
- unit tests for ledger activity persistence and read helpers

Not implemented yet:

- actual end-to-end paper trading operations with real provider and broker side effects
- real Alpaca SDK-backed runtime wiring
- real Alpaca paper smoke-test evidence
- real news provider integration
- real AI provider integration
- managed Postgres/Supabase runtime connection or migration execution
- real Temporal test-server/replay execution
- production dashboard UI/deployment
- real Telegram/email alert delivery
- real Temporal query/signal backend integration
- actual paper trading operations
- Level 4 micro-live readiness evidence
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

Run the Milestone 09 validation-focused tests:

```bash
uv run --group dev pytest tests/unit/test_validation_harness.py tests/unit/test_failure_simulations.py tests/unit/test_paper_dry_run.py tests/temporal/test_workflow_contracts.py
```

Run Milestone 12 ledger tests:

```bash
uv run --group dev pytest tests/unit/test_ledger*.py
```

Run Milestone 13 ledger activity tests:

```bash
uv run --group dev pytest tests/unit/test_ledger_activities.py tests/temporal/test_workflow_contracts.py
```

Run Milestone 14 paper broker boundary tests:

```bash
uv run --group dev pytest tests/unit/test_alpaca*.py tests/unit/test_broker*.py tests/unit/test_broker_activities.py
```

Run Milestone 15 reporting, alerting, and dashboard read-model tests:

```bash
uv run --group dev pytest tests/unit/test_reporting*.py tests/unit/test_alerting*.py tests/unit/test_dashboard*.py tests/unit/test_control_plane*.py tests/temporal/test_workflow_contracts.py
```

Run Milestone 16 fake/local paper dry-run orchestration tests:

```bash
uv run --group dev pytest tests/unit/test_paper_dry_run*.py tests/unit/test_dry_run*.py
```

Run the safe fake/local dry-run script:

```bash
uv run python scripts/run_paper_dry_run.py
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

## Paper Trading Runbook

Milestone 10 adds paper trading operating documentation only:

- `docs/paper_trading_runbook.md`
- `docs/checklists/paper_daily_checklist.md`
- `docs/checklists/paper_weekly_review.md`
- `docs/templates/paper_daily_report_template.md`
- `docs/templates/paper_incident_report_template.md`

The runbook is target-state operational readiness documentation. It does not mean real provider
integrations, managed database runtime integration, paper broker execution, alerting, dashboard
deployment, or live trading are complete.

## Broker Integration

Milestone 14 adds `packages/broker/alpaca.py`, `packages/broker/fakes.py`, and
`apps/workers/app/activities/broker.py`. The adapter is paper-only, refuses live-mode or live-order
flags, and requires explicit paper credentials in runtime mode. Default tests and default activity
wiring use fakes and do not call Alpaca or submit real paper orders. Optional real Alpaca paper smoke
tests remain deferred and must require explicit credentials and an explicit opt-in marker.

## Reporting And Alerting

Milestone 15 adds `packages/reporting/`, `packages/alerting/`, and
`apps/workers/app/activities/reporting.py`. Reports are generated from supplied ledger/read-model
snapshots, rendered deterministically, and persisted through the ledger repository. Alert delivery
uses fake adapters by default; Telegram/email skeletons fail closed and do not send network
messages in this milestone. Dashboard read models can be built from ledger repositories, but a real
dashboard deployment and real Temporal query/signal backend are still deferred.

## Paper Dry-Run Orchestration

Milestone 16 adds `packages/paper/` and `scripts/run_paper_dry_run.py`. The path is fake/local
only: in-memory SQLite, fixture data, neutral/fake AI output, `FakeAlpacaClient`, fake alerts,
report generation, and ledger-backed dashboard read models. It does not call Alpaca, AI/news,
market-data, Telegram/email, managed Postgres/Supabase, or Temporal services, and it submits no
real paper or live broker orders.

## Level 4 Micro-Live Readiness

Milestone 11 adds readiness documentation only:

- `docs/level4_micro_live_readiness.md`
- `docs/checklists/level4_micro_live_readiness_checklist.md`
- `docs/checklists/credential_separation_checklist.md`
- `docs/checklists/kill_switch_rearm_checklist.md`
- `docs/templates/level4_micro_live_go_no_go_template.md`

Current conclusion: Level 4 micro-live is not ready. The repo still lacks frozen paper evidence,
real provider integrations, managed database runtime integration, real Temporal query/signal backend
integration, real dashboard deployment, alerting, and live go/no-go approval.

## Safety Defaults

The foundation config defaults to paper/dry-run behavior with live trading and autonomous execution disabled. It does not contain secrets and does not execute AI/news provider calls. Ledger, reporting, alerting, and activity tests use local in-memory SQLite or fake adapters and do not require `DATABASE_URL`, managed Postgres/Supabase credentials, or alert credentials. Broker tests use fake Alpaca clients by default and do not call Alpaca or submit real orders. Real provider wiring must be added explicitly through server-side Temporal activities or API services.

Backtests in this repository are validation tools only. They are not proof of live profitability. Stock-universe backtests without point-in-time universe data must be treated as optimistic.
