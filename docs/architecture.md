# Architecture

This document describes the current foundation, data/backtest, database/audit-ledger, Temporal
skeleton/activity, deterministic strategy, risk/execution-core, broker-reconciliation, AI/news
intelligence, reporting/alerting, dashboard/control-plane, validation/testing, paper-operations,
and Level 4 readiness documentation boundary architecture.

The latest source of truth is `docs/app/Autonomous_AI_Trading_Bot_SPEC_v0.4.md`. Current
repository implementation is limited to Milestones 00-19 scaffolding and local/fake integration
foundation: project metadata, safe configuration defaults, typed config loading, structured logging
helpers, offline data contracts, deterministic feature utilities, universe filters, explicit-signal
backtest utilities, Postgres-oriented audit-ledger DDL, local SQLite ledger repositories for tests,
Temporal workflow/worker skeletons, safe ledger-backed activity boundaries using fake/local
repositories, paper-only Alpaca broker boundaries using fake clients by default, deterministic
strategy/regime/signal helpers, passive risk/execution-core contracts, normalized broker models,
pure reconciliation comparison, bounded AI/news intelligence contracts, pure report generation,
fake-safe alert contracts, ledger-backed dashboard read models, dashboard/control-plane read/action
contracts, validation/testing contracts, fake/local paper dry-run orchestration, explicit
Postgres/Supabase runtime migration/check helpers, opt-in managed repository CRUD validation, paper
trading runbook documentation, local Temporal SDK test-server/replay validation, and Level 4
micro-live readiness documentation.

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
- `db/migrations/0001_initial_audit_ledger.sql` defines the initial Postgres/Supabase audit-ledger
  schema for all core spec section 19 tables.
- `packages/ledger/` defines local schema helpers, typed ledger records, repository protocols, and a
  SQLite repository implementation for deterministic tests without managed database credentials.
- `packages/ledger/runtime.py` defines explicit Postgres/Supabase `DATABASE_URL` validation,
  redacted target metadata, managed operation gates, psycopg connection helpers, migration
  execution helpers, and expected table/uniqueness/index schema checks for operator-invoked runtime
  use.
- `packages/ledger/postgres_repository.py` defines a transaction-scoped Postgres repository for
  opt-in managed CRUD validation and future server-side runtime wiring. It does not auto-commit and
  does not open connections itself.
- Temporal SDK dependency, typed client bootstrap, task queue mapping, workflow skeletons, safe
  ledger activity contracts, provider placeholders, signal names, query names, and retry-policy
  contracts exist.
- `apps/workers/app/activities/models.py` defines typed ledger activity request/response contracts.
- `apps/workers/app/activities/ledger.py` defines repository-backed activities for raw payloads,
  data refresh checkpoints, candidates, AI outputs, decisions, risk checks, execution intents,
  orders, fills, positions, reconciliations, system events/incidents, reports, and read helpers.
- Workflow skeletons call ledger activity boundaries by stable name while workflow code remains
  deterministic and imports no database, broker, AI/news, provider, network, clock, or random
  clients.
- `tests/temporal/test_temporal_sdk_environment.py` starts Temporal's local SDK test environment,
  registers workers on the configured task queues, executes every workflow skeleton with fake/local
  activities, validates selected signal/query contracts, and replays a generated kill-switch
  workflow history. It does not connect to Temporal Cloud or activate schedules.
- Regime classification implements deterministic `RISK_ON`, `CAUTION`, and `RISK_OFF` states from SPY SMA/realized-volatility rules.
- Strategy candidate evaluation implements long-only trend, breakout, volume, RS63, ATR percent, universe, price, ADV, earnings, held-symbol, and duplicate-intent gates.
- Exit helpers calculate stop levels and exit trigger reason codes only; they do not submit or modify orders.
- Risk checks evaluate new-risk eligibility from config and caller-supplied system, session, reconciliation, Temporal, exposure, loss, cash, duplicate-intent, and kill-switch state.
- Position sizing implements the configured risk-per-trade and max-position-size formula with non-increasing multipliers.
- Execution-core contracts define `ExecutionIntent`, deterministic client order ID roots, duplicate-intent helpers, passive order lifecycle transitions, and structured rejection models.
- Broker contracts define account, order, fill, position, protective-stop, REST fallback, and stream event models.
- The Alpaca paper adapter is dependency-free and protocol-backed. It refuses live-mode/live-order
  configuration, requires explicit paper credentials in runtime mode, and defaults to fake clients
  in tests.
- Fake Alpaca clients cover account/order/fill/position snapshots, idempotency lookup, paper entry
  submit, cancel, protective-stop submit/verify, stream-event mapping, and REST fallback status
  contracts without credentials or network calls.
- Broker Temporal activity contracts are registered with fake-adapter defaults. They are boundaries
  for later order lifecycle integration, not active paper orchestration.
- Reconciliation contracts compare broker snapshots against passive internal ledger snapshots and classify mismatches into structured incidents with pause-new-risk or flatten-if-safe recommendations.
- AI/news contracts define deterministic-shortlist-only news requests, provider protocols, article normalization/deduplication, strict AI output schemas, neutral fallbacks, deterministic AI event scoring, hard-block classification, and persistence payload contracts.
- The AI prompt template is versioned under `packages/ai/prompts/` and explicitly forbids broker actions, order creation/modification, stop changes, strategy mutation, risk-limit changes, and full-universe scanning.
- AI/news provider activity boundaries are placeholders only and perform no external provider, AI,
  broker, or network calls.
- `packages/reporting/` defines daily/weekly report models, pure report generators, deterministic
  Markdown rendering, and ledger persistence helpers. These generators read supplied snapshots only
  and do not call broker, AI/news, market-data, alert, or network providers.
- `packages/alerting/` defines alert message models, severity/category routing, a fake adapter, and
  fail-closed Telegram/email adapter skeletons. Default routing captures messages locally and
  performs no external delivery.
- `apps/workers/app/activities/reporting.py` registers activity boundaries for daily/weekly report
  generation, alert dispatch, incident/report alert dispatch, and dashboard snapshot construction.
  They use local ledger repositories and fake alert adapters by default.
- Control-plane contracts define read-only dashboard views and auditable safe control requests.
- `packages/control_plane/service.py` includes a ledger-backed read-model provider that constructs
  dashboard snapshots from repository records without broker, AI/news, alert, frontend, or Temporal
  calls.
- `apps/api/app/control_plane.py` maps safe backend control requests to existing Temporal signal
  names and exposes a helper for ledger-backed dashboard snapshots. It does not call broker
  adapters, AI/news providers, alert services, or browser-side Temporal paths.
- `packages/paper/` coordinates a fake/local end-to-end paper dry run with fixture data, neutral or
  fake AI output, deterministic risk checks, ledger persistence, `FakeAlpacaClient` entry/fill/stop
  behavior, reconciliation, fake alerts, daily report generation, and dashboard/read-model
  snapshots.
- `scripts/run_paper_dry_run.py` runs the fake/local dry run and prints the explicit warning that
  no broker orders are submitted.
- `apps/dashboard/` is a minimal dashboard scaffold with safe public environment selection only. No
  frontend framework or deployment files are added.
- Validation contracts under `packages/validation/` define the spec-required backtest split, benchmark,
  fee/slippage, ablation, Monte Carlo placeholder, failure-simulation, and paper dry-run check
  assumptions. They are deterministic contracts only and do not run live or paper broker orders.
- `docs/paper_trading_runbook.md` and related checklist/report templates define paper operations,
  monitoring, incident response, frozen paper acceptance criteria, and paper-to-Level-4 handoff
  gates. They are documentation only and do not activate paper or live trading.
- `docs/level4_micro_live_readiness.md` and related checklists/templates define Level 4 evidence
  gates, credential separation, control re-arm checks, and go/no-go records. They are documentation
  only and do not enable live trading.
- No production API service is implemented.
- No production worker deployment is implemented.
- No production dashboard UI is implemented.
- No real alert delivery is implemented.
- No actual paper trading operations with real broker/provider side effects are implemented.
- No Alpaca SDK-backed runtime wiring or real paper smoke-test evidence is implemented.
- No real managed Postgres/Supabase activity wiring is implemented.
- No real AI/news provider integration is implemented.
- No production Temporal query/signal backend integration is implemented.
- No production Temporal worker deployment evidence is implemented.
- Temporal schedules are not activated.
- Level 4 micro-live readiness is not satisfied because required evidence is absent.
- Earnings blackout evaluation requires caller-supplied earnings dates and trading calendars. Missing earnings data is treated as unknown and blocks entries conservatively.

Future milestones must keep implementation aligned with the latest spec before adding behavior.
