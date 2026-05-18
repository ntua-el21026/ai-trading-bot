# AI Trading Bot

Spec-governed autonomous AI-assisted trading bot repository.

The latest identified source-of-truth spec is:

```text
docs/app/Autonomous_AI_Trading_Bot_SPEC_v0.6.md
```

## Current Status

This repository is at Milestone 44D v0.6 readiness preparation. Milestones 39-44C proved controlled
paper entry/stop paths, supervised scheduled one-shot behavior, flat broker cleanup, and Tiingo EOD
primary signal-data verification. Milestone 44D creates the v0.6 frozen-validation spec and prepares
M45 for long+paper-short+long-scale-in validation only if the real paper short and scale-in
rehearsals succeed and the broker baseline is restored flat. It does not start frozen validation,
activate unattended schedules, enable live trading, enable autonomous live execution, enable live
shorting, enable leverage, or claim Level 4 readiness.

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
- Temporal Cloud dev client settings, API-key/TLS connection helper, and default-refusing smoke
  harness for a harmless `KillSwitchWorkflow` run with fake/local activities only
- Temporal task queue mapping for the spec-defined queues
- workflow skeletons and safe Temporal activity contracts under `apps/workers/`
- signal, query, and retry-policy contracts
- deterministic `RISK_ON` / `CAUTION` / `RISK_OFF` regime classification
- deterministic candidate evaluation for configured long signals and gated paper-only broad-ETF
  shorts, with no AI broker authority
- stop-level and exit-trigger calculation helpers that do not submit orders
- deterministic risk checks for new-risk eligibility
- deterministic scale-in policy helpers for one initial entry plus at most one add-on entry per
  symbol under paper-validation caps, with fake/stub tests only
- position sizing from configured risk and position caps
- kill-switch state models
- passive `ExecutionIntent`, idempotency, order lifecycle, and rejection contracts
- dependency-free broker adapter protocols and a paper-only Alpaca adapter behind explicit gates
- normalized broker account/order/fill/position/protective-stop/stream models
- fixture-only Alpaca `trade_updates` mapping to internal broker lifecycle events
- fake Alpaca client support for account/order/fill/position snapshots, order lookup, paper entry
  submit, cancel, protective-stop submit/verify, stream-event mapping, and REST fallback contracts
- opt-in read-only Alpaca paper HTTP smoke client and smoke runner for account, open orders,
  positions, and clock/status snapshots
- successful opt-in Alpaca paper read-only smoke evidence for account, open-orders, positions, and
  clock/status reads against the paper endpoint, with no write operations attempted
- explicitly gated Alpaca paper order-lifecycle smoke harness for one tiny operator-invoked paper
  order lifecycle, with default refusal, smoke-only client order IDs, sanitized summaries, fake
  submit/fill/stop/cancel/cleanup coverage, and no default broker writes
- normalized broker clock snapshot mapping for read-only Alpaca paper smoke validation
- broker Temporal activity contracts that default to fake Alpaca paper adapters and perform no real
  Alpaca calls in default tests
- pure daily and weekly report generation from supplied ledger/read-model snapshots under
  `packages/reporting/`
- deterministic Markdown report rendering and report persistence through the ledger repository
- alerting contracts, severity/category routing, fake alert adapter, Telegram message templates,
  gated server-side Telegram adapter, and explicit Telegram delivery smoke harness under
  `packages/alerting/`
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
- provider-first shortlist news retrieval with Marketaux primary support, Alpha Vantage
  fallback/cross-check support, request-budget enforcement, per-run symbol/article caps,
  provider-independent normalization, deduplication, raw payload hashing, and ledger persistence
  boundaries
- ticker-tagged news article normalization and deduplication helpers
- OpenAI structured-output analysis over normalized shortlist articles, explicit model config
  parsing, optional model-list validation behind smoke gates, strict schema normalization,
  neutral fallback behavior, prompt/model/schema version recording, and raw prompt/output hashes
- disabled-by-default OpenAI web-search fallback with exception-only rules, runtime policy
  requirement, separate request budget, and sanitized audit result hashes
- autonomous AI feedback/calibration service that evaluates historical AI outputs, computes
  calibration/coverage/fallback/missed-risk proxy metrics, emits report/event payloads, and can
  only reduce, neutralize, or escalate AI influence
- Telegram-safe daily report, weekly report, trade win/loss, order/fill/stop, critical incident,
  and AI/news warning alert summaries
- versioned AI trade-research prompt template
- strict schema-validated AI trade-research output models and neutral fallback behavior
- deterministic AI event scoring, hard-block classification, and non-increasing size-multiplier
  helpers
- raw prompt/output persistence payload contracts with audit hashes
- Postgres-oriented audit-ledger migration under `db/migrations/`
- local `packages/ledger/` schema, typed records, and SQLite repository implementation for
  deterministic tests without managed database credentials
- explicit Postgres/Supabase runtime helpers in `packages/ledger/runtime.py` for validated
  `DATABASE_URL` loading, redacted target output, psycopg runtime connections, migration execution,
  expected-table schema checks, and expected uniqueness/index checks
- transaction-scoped Postgres ledger repository support for explicit managed database CRUD
  validation without owning commits
- opt-in database scripts `scripts/apply_ledger_migrations.py` and
  `scripts/check_ledger_database.py` that require explicit `DATABASE_URL`, second opt-in gates, and
  never print secrets
- ledger tables for symbols, raw payloads, OHLCV, features, regimes, candidates, AI outputs,
  decisions, risk checks, execution intents, orders, fills, positions, reconciliations, system
  events, and reports
- typed ledger activity request/response models under `apps/workers/app/activities/models.py`
- safe ledger-backed Temporal activity functions under `apps/workers/app/activities/ledger.py`
  using local/fake SQLite repositories by default
- workflow skeletons aligned to ledger persistence activity boundaries without direct database,
  broker, AI/news, provider, network, clock, or random calls in workflow code
- real Temporal SDK local test-environment coverage for all registered workflow skeletons using
  fake/local activities only
- Temporal signal/query tests for kill switch, reconciliation, and reporting workflows under the
  local SDK test server
- Temporal replay coverage for a generated kill-switch workflow history
- worker registration tests for configured task queues and workflow mappings
- Temporal AI/news activity boundaries that perform no external calls
- dashboard/control-plane read models for system state, workflows, intents, orders, positions,
  incidents, reconciliation, kill switch, candidates/signals, AI outputs, AI quality state,
  provider budget status, reports, risk status, alerting status, Temporal status, and paper
  readiness status
- server-side control-plane contracts mapping safe manual controls to existing Temporal signal names
- dashboard/control-plane dev runtime smoke harness that builds a fake/local snapshot, validates
  safe controls through a fake dispatcher by default, refuses managed DB/deployment modes, and
  performs no broker, AI/news, alert, schedule, or deployment side effects
- minimal `apps/api/` and static `apps/dashboard/` scaffolds with frontend environment guardrails,
  no frontend framework dependencies, and a dashboard-only Vercel preview configuration that
  excludes workers, backend packages, scripts, tests, local env files, and privileged secrets
- controlled paper operations readiness models and `scripts/check_paper_operations_readiness.py`,
  which aggregate existing database, Temporal, broker, AI/news, alerting, dashboard, and paper
  status evidence without starting paper trading, activating schedules, submitting orders, calling
  providers, sending alerts, or deploying anything
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
- unit tests for runtime database URL validation, migration dry-run behavior, schema checks, and
  default-skipped managed DB integration tests

Not implemented yet:

- actual end-to-end paper trading operations with real provider and broker side effects
- first controlled paper trading session
- real Alpaca SDK-backed runtime wiring
- production dashboard deployment
- Email/Resend delivery, intentionally deferred as a possible future secondary channel
- production Temporal query/signal backend integration
- production worker/schedule activation
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

Run Milestone 23 Telegram alerting tests and the default-skipped/explicitly gated smoke:

```bash
uv run --group dev pytest tests/unit/test_alerting.py tests/unit/test_telegram_alerting.py
uv run --group dev pytest tests/integration/test_telegram_alert_delivery_smoke.py
uv run python scripts/check_telegram_alert_delivery.py
```

Run Milestone 24 Temporal Cloud runtime tests and the default-refusing smoke:

```bash
uv run --group dev pytest tests/unit/test_temporal_config.py tests/unit/test_temporal_cloud_runtime.py tests/temporal
uv run python scripts/check_temporal_cloud_runtime.py
```

Run Milestone 25 dashboard/control-plane runtime tests and the fake/local smoke:

```bash
uv run --group dev pytest tests/unit/test_control_plane_models.py tests/unit/test_control_plane_api.py tests/unit/test_dashboard_read_models.py tests/unit/test_dashboard_env_security.py tests/unit/test_dashboard_control_plane_runtime.py
uv run python scripts/check_dashboard_control_plane_runtime.py
```

Run Milestone 26 dashboard preview guardrails and static build:

```bash
uv run --group dev pytest tests/unit/test_vercel_dashboard_preview.py tests/unit/test_dashboard_env_security.py
npm run lint
npm run build
uv run python scripts/check_vercel_dashboard_preview.py
```

Run Milestone 27 controlled paper operations readiness aggregation:

```bash
uv run --group dev pytest tests/unit/test_paper_operations_readiness.py
uv run python scripts/check_paper_operations_readiness.py
```

This aggregates readiness evidence only. It does not start paper trading, activate schedules,
submit broker orders, call AI/news providers, send real alerts, or deploy anything.

Run Milestone 16 fake/local paper dry-run orchestration tests:

```bash
uv run --group dev pytest tests/unit/test_paper_dry_run*.py tests/unit/test_dry_run*.py
```

Run Milestone 17 database runtime tests:

```bash
uv run --group dev pytest tests/unit/test_database_runtime*.py tests/unit/test_ledger_connection*.py tests/unit/test_migration*.py
```

Run Milestone 18 managed database validation tests locally/offline plus the default-skipped
integration test:

```bash
uv run --group dev pytest tests/unit/test_database_runtime.py tests/unit/test_migration_runtime.py tests/integration/test_managed_ledger_crud.py
```

Run the managed CRUD validation only after applying the migration to an explicit development
Postgres/Supabase target:

```bash
RUN_MANAGED_DB_TESTS=1 DATABASE_URL="postgresql://..." \
  uv run --group dev pytest tests/integration/test_managed_ledger_crud.py
```

Run Milestone 19 Temporal SDK test-environment and replay tests:

```bash
uv run --group dev pytest tests/temporal -vv
```

Run Milestone 20 Alpaca paper read-only smoke tooling tests offline:

```bash
uv run --group dev pytest tests/unit/test_alpaca_paper_readonly.py
```

Run the real read-only paper smoke only after loading local secrets and explicit gates:

```bash
RUN_ALPACA_PAPER_SMOKE=1 \
ALPACA_PAPER_SMOKE_CONFIRM=READ_ONLY_PAPER_ACCOUNT \
ALPACA_BASE_URL=https://paper-api.alpaca.markets \
  uv run python scripts/check_alpaca_paper_readonly.py
```

Run Milestone 21A Alpaca paper order-lifecycle smoke harness tests offline:

```bash
uv run --group dev pytest tests/unit/test_alpaca_paper_order_lifecycle_smoke.py
```

Run the gated order-lifecycle smoke harness. With no write-smoke gates, refusal is expected and no
broker write is attempted:

```bash
uv run python scripts/check_alpaca_paper_order_lifecycle.py
```

The real paper write smoke must only be run after loading all explicit write-smoke gates:

```bash
RUN_ALPACA_PAPER_ORDER_LIFECYCLE_SMOKE=1 \
ALPACA_PAPER_ORDER_LIFECYCLE_CONFIRM=SUBMIT_AND_CLEAN_UP_TINY_PAPER_ORDER \
ALPACA_BASE_URL=https://paper-api.alpaca.markets \
ALPACA_PAPER_ORDER_SMOKE_SYMBOL=AAPL \
ALPACA_PAPER_ORDER_SMOKE_MAX_QTY=1 \
ALPACA_PAPER_ORDER_SMOKE_MAX_NOTIONAL_USD=200 \
ALPACA_PAPER_ORDER_SMOKE_TIMEOUT_SECONDS=60 \
  uv run python scripts/check_alpaca_paper_order_lifecycle.py
```

Run Milestone 22 AI/news tests offline:

```bash
uv run --group dev pytest tests/unit/test_news_provider_integration.py \
  tests/unit/test_openai_structured_analysis.py \
  tests/unit/test_openai_web_fallback.py \
  tests/unit/test_ai_feedback_calibration.py
```

Provider/OpenAI integration tests are skipped by default unless their explicit smoke gates and
local secret variables are present:

```bash
uv run --group dev pytest tests/integration/test_news_provider_external_smoke.py \
  tests/integration/test_openai_external_smoke.py
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

Milestone 19 adds local Temporal SDK test-environment and replay coverage under `tests/temporal/`.
These tests start the SDK's local test server, register workers against configured task queues, use
fake/local activities only, do not connect to Temporal Cloud, and do not activate schedules.

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
wiring use fakes and do not call Alpaca or submit real paper orders. Milestone 20 adds an opt-in
read-only paper smoke path for account, open orders, positions, and clock/status snapshots. It
requires explicit environment gates, refuses live endpoints, prints sanitized summaries only, and
does not submit, cancel, replace, or modify orders. Milestone 21A adds a separate order-lifecycle
smoke harness that refuses by default and requires explicit write-smoke gates before any paper
submit/cancel/stop/cleanup call. This harness is smoke validation only, not actual paper trading or
frozen paper evidence.

## Reporting And Alerting

Milestone 15 adds `packages/reporting/`, `packages/alerting/`, and
`apps/workers/app/activities/reporting.py`. Reports are generated from supplied ledger/read-model
snapshots, rendered deterministically, and persisted through the ledger repository. Alert delivery
uses fake adapters by default. Milestone 23 makes Telegram the only real alert channel for now,
behind explicit real-delivery gates and a smoke harness. Telegram is operator-facing only: it does
not submit orders, modify stops, change risk, mutate strategy, or act as a command interface.
Email/Resend is intentionally deferred as a possible future secondary channel. Dashboard read models
can be built from ledger repositories, and Milestone 25 adds a dev runtime smoke for read-only
snapshots plus safe fake-dispatched controls. Milestone 26 adds a static dashboard-only Vercel
preview harness. The preview uses only safe public environment values, has no order-entry controls,
does not deploy workers or execution services, and does not call broker, Temporal, AI/news,
database, or alert providers from browser code. The generated Vercel preview URL is sufficient;
no custom domain is required. Production dashboard deployment remains deferred.

Milestone 26B deployment audit evidence:

- Preview deployment URL: `https://ai-trading-cy85e5pf1-michael-peppas-projects.vercel.app`.
- Accidental production deployment URL:
  `https://ai-trading-qxid0g5t8-michael-peppas-projects.vercel.app`.
- Accidental production alias: `https://ai-trading-bot-silk.vercel.app`.
- The production alias served the expected static/read-only dashboard artifact during audit.
- Deployment-specific preview/production URLs were Vercel-ready but anonymously protected with HTTP
  401, so their page content was not publicly inspectable by unauthenticated HTTP.
- No workers, backend runtime, broker/API/provider/Temporal/database/Telegram browser calls,
  secrets, or order-entry controls are part of the dashboard artifact.
- Future production deployments require explicit approval/gates; do not run `vercel --prod` as
  part of preview-only milestones.

## Database Runtime

Milestones 17-18 add `packages/ledger/runtime.py`, `packages/ledger/postgres_repository.py`,
`scripts/apply_ledger_migrations.py`, and `scripts/check_ledger_database.py`. These are explicit
Postgres/Supabase runtime helpers. Default tests still use SQLite/fakes and do not require
`DATABASE_URL`. Migration application, schema validation, and managed repository CRUD validation are
opt-in, server-side only, and must use secrets from local environment files or a secret manager. See
`docs/database_runtime.md`.

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
actual controlled paper operations, production operational dashboard integration, production
schedule activation, and live go/no-go approval. The Milestone 21B/22/23/24/25/26/27 evidence does
not change that status. Milestone 27 readiness aggregation may report readiness for a future first controlled paper
session, but the session itself remains a separate future milestone and frozen paper evidence is
still absent.

## Safety Defaults

The foundation config defaults to paper/dry-run behavior with live trading and autonomous execution
disabled. It does not contain secrets and does not execute AI/news provider calls by default.
Ledger, reporting, alerting, and activity tests use local in-memory SQLite or fake adapters and do
not require `DATABASE_URL`, managed Postgres/Supabase credentials, or alert credentials. Broker
tests use fake Alpaca clients by default and do not call Alpaca or submit real orders. Provider and
OpenAI smoke paths require explicit environment gates and remain server-side only.

Backtests in this repository are validation tools only. They are not proof of live profitability. Stock-universe backtests without point-in-time universe data must be treated as optimistic.
