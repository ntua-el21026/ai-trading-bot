# Database Runtime

The latest source of truth is `docs/app/Autonomous_AI_Trading_Bot_SPEC_v0.3.md`.

Milestone 17 prepares a managed Postgres/Supabase-compatible runtime path for the audit ledger. It
does not start actual paper trading, submit broker orders, call external providers, or require real
credentials in default tests.

## Runtime Target

The target runtime database is:

```text
Postgres / Supabase Postgres
```

The checked-in migration remains:

```text
db/migrations/0001_initial_audit_ledger.sql
```

Default tests continue to use in-memory SQLite through `packages.ledger.connect_in_memory_sqlite()`.
They do not require `DATABASE_URL` and do not call managed Postgres/Supabase.

## Runtime Configuration

Runtime database access uses only:

```text
DATABASE_URL
```

Rules:

- Store real values in a local `.env` file or a secret manager.
- Never commit `.env`.
- Never print full `DATABASE_URL`.
- Never expose `DATABASE_URL` to frontend/dashboard code.
- Keep production and paper environments separated.
- Use the runtime helpers only from server-side scripts or future server-side workers.

The runtime helpers reject missing, non-Postgres, and obvious placeholder URLs before connecting.

## Runtime Helpers

`packages/ledger/runtime.py` provides:

- `LedgerDatabaseConfig.from_env()` for explicit `DATABASE_URL` loading.
- `validate_postgres_database_url()` for fail-closed URL validation.
- `redact_database_url()` and `database_target()` for safe target output.
- `connect_runtime_postgres()` for explicit psycopg runtime connections.
- `apply_postgres_migration_sql()` for migration execution.
- `check_postgres_ledger_schema()` for expected table validation.

These helpers do not fall back to SQLite. If `DATABASE_URL` is absent, they fail closed.

## Applying Migrations

Dry-run the migration target first:

```bash
DATABASE_URL="postgresql://..." uv run python scripts/apply_ledger_migrations.py
```

The dry run validates the URL, loads the migration file, prints a redacted target summary, and does
not connect.

Apply the migration only after confirming the target:

```bash
DATABASE_URL="postgresql://..." uv run python scripts/apply_ledger_migrations.py --apply
```

The script does not print credentials. It does not call brokers, AI/news providers, alert services,
Temporal schedules, or dashboard deployment commands.

## Checking Schema

After applying migrations, validate expected tables:

```bash
DATABASE_URL="postgresql://..." uv run python scripts/check_ledger_database.py --list-tables
```

The check connects to the supplied Postgres target, verifies the spec-required ledger tables, and
prints no secrets.

## Opt-In Tests

Default tests skip managed DB checks. To run the managed DB schema check explicitly:

```bash
RUN_MANAGED_DB_TESTS=1 DATABASE_URL="postgresql://..." \
  uv run --group dev pytest tests/unit/test_ledger_connection_runtime.py -m integration
```

Do not run this command with live trading credentials in the environment. The test is read-only
schema validation, but runtime secrets must still be handled through local env files or a secret
manager.

## Safety Boundary

Milestone 17 does not:

- enable live trading;
- enable autonomous execution;
- add secrets;
- commit `.env`;
- call Alpaca;
- call AI/news providers;
- send Telegram/email alerts;
- submit paper or live broker orders;
- activate Temporal schedules;
- deploy a dashboard;
- start actual paper trading operations.

## Remaining Gaps

Still deferred:

- actually applying migrations to a managed Supabase/Postgres instance;
- repository CRUD validation against a managed Postgres runtime with fixture data;
- real Temporal test-server/replay integration;
- real Alpaca paper smoke tests;
- real AI/news provider integration;
- real alert delivery;
- real dashboard deployment;
- actual paper trading operations;
- frozen paper evidence;
- Level 4 micro-live readiness.
