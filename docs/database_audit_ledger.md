# Database Audit Ledger

Milestone 12 added the database/audit-ledger foundation required by
`docs/app/Autonomous_AI_Trading_Bot_SPEC_v0.3.md`.

Milestone 13 connects safe Temporal activity boundaries to the local/fake ledger repository layer.
Workflow code still does not import repositories or database sessions directly.

Milestone 14 adds fake-tested paper broker boundaries that produce normalized broker payloads for
future ledger persistence. Managed Postgres/Supabase runtime wiring is still deferred.

The package name is `packages/ledger` because the latest spec describes Postgres as the durable
business and audit ledger. Domain logic remains in the existing domain packages; ledger code owns
schema and persistence boundaries only.

## Scope

Implemented:

- Postgres-oriented initial DDL migration:
  - `db/migrations/0001_initial_audit_ledger.sql`
- Local SQLite schema compatibility helper for deterministic tests:
  - `packages/ledger/schema.py`
- Local in-memory SQLite connection helper:
  - `packages/ledger/connection.py`
- Typed ledger record models:
  - `packages/ledger/models.py`
- Repository protocols and a local SQLite repository implementation:
  - `packages/ledger/repositories.py`
- Unit tests for schema, round trips, uniqueness constraints, rollback behavior, and safety flags:
  - `tests/unit/test_ledger_schema.py`
  - `tests/unit/test_ledger_repositories.py`
- Safe Temporal ledger activity contracts and tests:
  - `apps/workers/app/activities/models.py`
  - `apps/workers/app/activities/ledger.py`
  - `apps/workers/app/activities/fakes.py`
  - `tests/unit/test_ledger_activities.py`
  - `tests/temporal/test_workflow_contracts.py`

No real managed database connection is required by default tests.

## Core Tables

The initial migration defines all core tables required by spec section 19:

- `symbols`
- `raw_provider_payloads`
- `ohlcv_daily`
- `features_daily`
- `regimes`
- `trade_candidates`
- `ai_research_outputs`
- `trade_decisions`
- `risk_checks`
- `execution_intents`
- `orders`
- `fills`
- `positions`
- `broker_reconciliations`
- `system_events`
- `reports`

The schema is intentionally complete but minimal. Some operational columns and indexes may be
expanded in later milestones as Temporal activities, broker paper integration, reporting, and
dashboard read models are connected.

## Idempotency And Uniqueness

The migration and local schema include constraints for:

- `raw_provider_payloads`: unique `(provider, endpoint, payload_hash)`
- `ohlcv_daily`: unique `(symbol, trading_date, provider)`
- `features_daily`: unique `(symbol, trading_date, feature_version)`
- `regimes`: unique `(trading_date, model_version)`
- `execution_intents.client_order_id_root`: unique
- `orders.client_order_id`: unique
- `orders.broker_order_id`: unique when present
- `fills.broker_fill_id`: unique when present
- `positions`: one open position per symbol

These constraints support later duplicate-intent prevention and idempotent broker order handling.

## Repository Boundaries

The local repository supports:

- raw provider payload insert/get by provider, endpoint, and payload hash;
- AI research output insert/get with raw prompt/output hashes and parsed payload;
- execution intent insert/get by ID and `client_order_id_root`;
- order insert/get by `client_order_id`;
- fill insert with broker fill ID uniqueness;
- position upsert/get;
- broker reconciliation snapshot insert/get latest;
- system event insert/list;
- report insert/get.
- active execution intent, open position, recent incident, and latest reconciliation read helpers.

Temporal ledger activities support:

- raw provider payload and data-refresh checkpoint persistence;
- trade candidate, AI research output, trade decision, and risk-check persistence;
- execution intent, order, fill, and position audit persistence;
- broker reconciliation, system event/incident, and report persistence;
- read helpers for later dashboard/control-plane integration.

Repositories are side-effect limited to database access against the provided connection. They do not
call broker APIs, AI/news provider APIs, Temporal, alert services, or managed database APIs.
Activity implementations call only these repository boundaries and local/fake SQLite by default.

## Local Test Strategy

Postgres/Supabase Postgres remains the production target. Unit tests use in-memory SQLite to avoid
requiring real credentials or external services.

SQLite compatibility differences:

- UUIDs are stored as `TEXT` in local tests.
- JSON/JSONB payloads are stored as canonical JSON text in local tests.
- The checked-in migration remains Postgres-oriented and uses `JSONB`, `TIMESTAMPTZ`, and
  `gen_random_uuid()`.
- Real managed Postgres/Supabase migration execution is deferred to a later integration milestone.
- Temporal real test-server/replay coverage remains deferred.

## Safety Boundary

Milestones 12-14 do not:

- enable live trading;
- enable autonomous execution;
- add secrets or real database credentials;
- call managed Postgres/Supabase services;
- call real broker APIs in default tests;
- call AI/news provider APIs;
- submit real paper or live broker orders;
- connect Temporal activities to real managed Postgres/Supabase runtime writes;
- deploy a dashboard;
- implement alert delivery.

Paper trading still requires real managed database integration, explicit Alpaca paper smoke-test
evidence, provider integration, alerting, report generation, dashboard read models, Temporal
test-server/replay evidence, and operational dry-run evidence.
