"""Apply or dry-run ledger migrations against an explicit Postgres/Supabase database."""

from __future__ import annotations

import argparse
import sys

from packages.ledger.runtime import (
    LedgerDatabaseConfig,
    LedgerRuntimeError,
    apply_postgres_migration_sql,
    connect_runtime_postgres,
)
from packages.ledger.schema import POSTGRES_MIGRATION_PATH, read_postgres_migration


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Apply the audit-ledger migration to an explicit Postgres database."
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Actually execute the migration. Omit for dry-run validation only.",
    )
    args = parser.parse_args(argv)

    try:
        config = LedgerDatabaseConfig.from_env()
    except LedgerRuntimeError as exc:
        print(f"Refusing migration: {exc}", file=sys.stderr)
        return 2

    migration_sql = read_postgres_migration()
    print(f"Target: {config.target.display}")
    print(f"Migration: {POSTGRES_MIGRATION_PATH}")
    print("Secrets: credentials redacted; DATABASE_URL is not printed.")

    if not args.apply:
        print("Mode: dry-run. Migration SQL was loaded but not executed.")
        print("Re-run with --apply to execute against the target database.")
        return 0

    try:
        with connect_runtime_postgres(config) as connection:
            apply_postgres_migration_sql(connection, migration_sql=migration_sql)
    except Exception as exc:  # pragma: no cover - exercised by opt-in runtime use.
        print(f"Migration failed for target {config.target.display}: {exc}", file=sys.stderr)
        return 1

    print("Migration applied successfully.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
