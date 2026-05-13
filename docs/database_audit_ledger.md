# Database Audit Ledger

Milestone 12 added the database/audit-ledger foundation required by
`docs/app/Autonomous_AI_Trading_Bot_SPEC_v0.5.md`.

Milestone 13 connects safe Temporal activity boundaries to the local/fake ledger repository layer.
Workflow code still does not import repositories or database sessions directly.

Milestone 14 adds fake-tested paper broker boundaries that produce normalized broker payloads for
future ledger persistence. Managed Postgres/Supabase runtime wiring is still deferred.

Milestone 15 adds report generation/persistence helpers and ledger-backed dashboard read-model
queries. It does not add managed Postgres/Supabase runtime wiring or external alert delivery.

Milestone 16 uses the local ledger repository for fake/local paper dry-run evidence persistence.
It persists fixture raw payloads, candidates, AI outputs, decisions, risk checks, execution
intents, fake broker orders/fills/positions, reconciliation results, system events/incidents, and
daily reports without requiring `DATABASE_URL`.

Milestone 17 adds an explicit managed Postgres/Supabase runtime path for migration application and
schema validation. Default tests still use SQLite/fakes and do not require managed database
credentials.

Milestone 18 adds a Postgres-backed repository for explicit managed CRUD validation, strengthens
managed database operation gates, and extends schema checks to include key uniqueness/index
expectations. In this run the managed database gates were absent, so no migration was applied and
managed CRUD validation was skipped.

Milestone 22 uses the existing raw provider payload, AI research output, system event, and report
boundaries for provider-first news, OpenAI structured-analysis audit hashes, provider budget events,
and AI calibration reports. No destructive schema change is required for this milestone.

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
- Explicit Postgres/Supabase runtime helpers:
  - `packages/ledger/runtime.py`
- Explicit Postgres/Supabase repository implementation for opt-in validation:
  - `packages/ledger/postgres_repository.py`
- Typed ledger record models:
  - `packages/ledger/models.py`
- Repository protocols and a local SQLite repository implementation:
  - `packages/ledger/repositories.py`
- Unit tests for schema, round trips, uniqueness constraints, rollback behavior, and safety flags:
  - `tests/unit/test_ledger_schema.py`
  - `tests/unit/test_ledger_repositories.py`
- Unit tests for report persistence and dashboard read models:
  - `tests/unit/test_reporting.py`
  - `tests/unit/test_dashboard_read_models.py`
- Unit tests for fake/local dry-run ledger evidence:
  - `tests/unit/test_paper_dry_run_orchestration.py`
- Unit tests for runtime URL validation, migration dry run, and default-skipped managed DB checks:
  - `tests/unit/test_database_runtime.py`
  - `tests/unit/test_ledger_connection_runtime.py`
  - `tests/unit/test_migration_runtime.py`
- Opt-in managed Postgres repository CRUD validation:
  - `tests/integration/test_managed_ledger_crud.py`
- Operator-invoked database scripts:
  - `scripts/apply_ledger_migrations.py`
  - `scripts/check_ledger_database.py`
- Safe Temporal ledger activity contracts and tests:
  - `apps/workers/app/activities/models.py`
  - `apps/workers/app/activities/ledger.py`
  - `apps/workers/app/activities/fakes.py`
  - `tests/unit/test_ledger_activities.py`
  - `tests/temporal/test_workflow_contracts.py`
- AI/news audit payload helpers:
  - `packages/ai/providers.py`
  - `packages/ai/openai.py`
  - `packages/ai/feedback.py`
  - `tests/unit/test_news_provider_integration.py`
  - `tests/unit/test_openai_structured_analysis.py`
  - `tests/unit/test_ai_feedback_calibration.py`

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

## Runtime Postgres/Supabase Path

Runtime database access is explicit and opt-in:

- `LedgerDatabaseConfig.from_env()` reads `DATABASE_URL` only when called.
- Missing, non-Postgres, and obvious placeholder URLs fail closed.
- Script output uses redacted target metadata and never prints credentials.
- `connect_runtime_postgres()` does not fall back to SQLite.
- `apply_postgres_migration_sql()` executes the checked-in migration against an explicit
  connection.
- `check_postgres_ledger_schema()` verifies that all expected ledger tables exist.
- `check_postgres_ledger_schema()` also verifies expected uniqueness constraints and the
  `positions_one_open_per_symbol` partial index.
- `PostgresLedgerRepository` uses a caller-supplied psycopg connection for managed runtime CRUD
  validation and does not auto-commit, allowing rollback-based validation.

Dry-run migration command:

```bash
DATABASE_URL="postgresql://..." uv run python scripts/apply_ledger_migrations.py
```

Apply command:

```bash
RUN_MANAGED_DB_TESTS=1 \
LEDGER_MIGRATION_CONFIRM=APPLY_TO_DEV_DATABASE \
DATABASE_URL="postgresql://..." \
  uv run python scripts/apply_ledger_migrations.py --apply
```

Schema check command:

```bash
RUN_MANAGED_DB_TESTS=1 DATABASE_URL="postgresql://..." \
  uv run python scripts/check_ledger_database.py --list-tables
```

Managed DB tests are skipped by default and require both `RUN_MANAGED_DB_TESTS=1` and
`DATABASE_URL`.

Managed CRUD validation command:

```bash
RUN_MANAGED_DB_TESTS=1 DATABASE_URL="postgresql://..." \
  uv run --group dev pytest tests/integration/test_managed_ledger_crud.py
```

Milestone 18 did not apply migrations or run managed CRUD validation because `DATABASE_URL`,
`RUN_MANAGED_DB_TESTS=1`, and `LEDGER_MIGRATION_CONFIRM=APPLY_TO_DEV_DATABASE` were not present in
the environment.

## Repository Boundaries

The local SQLite repository supports:

- raw provider payload insert/get by provider, endpoint, and payload hash;
- AI research output insert/get with raw prompt/output hashes and parsed payload;
- system event/report insertion for AI quality warnings and calibration reports;
- execution intent insert/get by ID and `client_order_id_root`;
- order insert/get by `client_order_id`;
- fill insert with broker fill ID uniqueness;
- position upsert/get;
- broker reconciliation snapshot insert/get latest;
- system event insert/list;
- report insert/get.
- active execution intent, open position, recent incident, and latest reconciliation read helpers.
- report, AI output, candidate, decision, risk-check, order, fill, and reconciliation list helpers
  used by reporting and dashboard read-model services.

The opt-in Postgres repository supports the same core managed CRUD validation path for raw payloads,
AI outputs, candidates, decisions, risk checks, execution intents, orders, fills, open positions,
broker reconciliations, system events/incidents, and reports.

Temporal ledger activities support:

- raw provider payload and data-refresh checkpoint persistence;
- trade candidate, AI research output, trade decision, and risk-check persistence;
- execution intent, order, fill, and position audit persistence;
- broker reconciliation, system event/incident, and report persistence;
- read helpers for later dashboard/control-plane integration.

Repositories are side-effect limited to database access against the provided connection. They do not
call broker APIs, AI/news provider APIs, Temporal, alert services, or managed database APIs.
Activity implementations call only these repository boundaries and local/fake SQLite by default.
Reporting helpers persist generated daily/weekly report payloads through the same repository
boundary. Dashboard read models use repository reads only and do not call broker, AI/news, alert, or
Temporal clients.
Paper dry-run orchestration uses the same local repository boundary for end-to-end fake evidence
and still avoids managed Postgres/Supabase runtime access by default.

## Local Test Strategy

Postgres/Supabase Postgres remains the production target. Unit tests use in-memory SQLite to avoid
requiring real credentials or external services.

SQLite compatibility differences:

- UUIDs are stored as `TEXT` in local tests.
- JSON/JSONB payloads are stored as canonical JSON text in local tests.
- The checked-in migration remains Postgres-oriented and uses `JSONB`, `TIMESTAMPTZ`, and
  `gen_random_uuid()`.
- Actual managed Postgres/Supabase migration execution remains operator opt-in and was not run in
  this environment.
- Repository CRUD validation against managed Postgres with fixture data exists as an opt-in
  integration test and was skipped in this environment because managed DB gates were absent.
- Temporal real test-server/replay coverage remains deferred.

## Safety Boundary

Milestones 12-17 do not:

- enable live trading;
- enable autonomous execution;
- add secrets or real database credentials;
- call managed Postgres/Supabase services in default tests;
- call real broker APIs in default tests;
- call AI/news provider APIs;
- submit real paper or live broker orders;
- connect Temporal activities to real managed Postgres/Supabase runtime writes by default;
- deploy a dashboard;
- implement real alert delivery;
- start actual paper trading operations.

Paper trading still requires actually applying and validating migrations in the target managed
database, explicit Alpaca paper smoke-test evidence, provider integration, real alert delivery,
deployed dashboard evidence, Temporal test-server/replay evidence, and controlled paper-operation
evidence.
