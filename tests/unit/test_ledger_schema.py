from __future__ import annotations

from packages.ledger.connection import connect_in_memory_sqlite
from packages.ledger.schema import (
    EXPECTED_LEDGER_TABLES,
    SQLITE_COMPATIBILITY_NOTES,
    read_postgres_migration,
    sqlite_table_names,
)


def test_sqlite_schema_contains_all_spec_core_tables() -> None:
    connection = connect_in_memory_sqlite()

    assert set(sqlite_table_names(connection)) == set(EXPECTED_LEDGER_TABLES)


def test_postgres_migration_is_audit_ledger_oriented_and_contains_no_secrets() -> None:
    migration = read_postgres_migration()

    for table_name in EXPECTED_LEDGER_TABLES:
        assert f"CREATE TABLE IF NOT EXISTS {table_name}" in migration
    assert "JSONB" in migration
    assert "asset_class TEXT NOT NULL CHECK (asset_class IN ('equity', 'etf'))" in migration
    assert "execution_intents" in migration
    assert "client_order_id_root TEXT NOT NULL UNIQUE" in migration
    assert "client_order_id TEXT NOT NULL UNIQUE" in migration
    assert "broker_fill_id TEXT UNIQUE" in migration

    forbidden_secret_markers = (
        "ALPACA_SECRET_KEY=",
        "ALPACA_API_KEY=",
        "OPENAI_API_KEY=",
        "ANTHROPIC_API_KEY=",
        "DATABASE_URL=",
        "-----BEGIN",
    )
    assert not any(marker in migration for marker in forbidden_secret_markers)


def test_sqlite_compatibility_notes_document_postgres_target() -> None:
    assert "Postgres is the target database" in SQLITE_COMPATIBILITY_NOTES
    assert "SQLite" in SQLITE_COMPATIBILITY_NOTES
    assert "runtime migration and schema checks are opt-in" in SQLITE_COMPATIBILITY_NOTES
