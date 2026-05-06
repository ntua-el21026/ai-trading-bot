"""Validate an explicit Postgres/Supabase audit-ledger database."""

from __future__ import annotations

import argparse
import sys

from packages.ledger.runtime import (
    LedgerDatabaseConfig,
    LedgerRuntimeError,
    check_postgres_ledger_schema,
    connect_runtime_postgres,
    require_managed_db_tests_enabled,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Check expected audit-ledger tables in an explicit Postgres database."
    )
    parser.add_argument(
        "--list-tables",
        action="store_true",
        help="Print present expected table names. Credentials are never printed.",
    )
    args = parser.parse_args(argv)

    try:
        config = LedgerDatabaseConfig.from_env()
        require_managed_db_tests_enabled()
    except LedgerRuntimeError as exc:
        print(f"Refusing database check: {exc}", file=sys.stderr)
        return 2

    print(f"Target: {config.target.display}")
    print("Secrets: credentials redacted; DATABASE_URL is not printed.")

    try:
        with connect_runtime_postgres(config) as connection:
            result = check_postgres_ledger_schema(connection)
    except Exception as exc:  # pragma: no cover - exercised by opt-in runtime use.
        print(f"Database check failed for target {config.target.display}: {exc}", file=sys.stderr)
        return 1

    if args.list_tables:
        for table_name in result.present_tables:
            print(f"table={table_name}")

    if not result.ok:
        if result.missing_tables:
            print(f"Missing expected tables: {', '.join(result.missing_tables)}", file=sys.stderr)
        if result.missing_unique_constraints:
            print(
                "Missing expected unique constraints: "
                f"{', '.join(result.missing_unique_constraints)}",
                file=sys.stderr,
            )
        if result.missing_indexes:
            print(f"Missing expected indexes: {', '.join(result.missing_indexes)}", file=sys.stderr)
        return 1

    print("Ledger schema check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
