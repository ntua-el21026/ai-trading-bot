from __future__ import annotations

import pytest

from packages.ledger.runtime import (
    LEDGER_MIGRATION_CONFIRM_VALUE,
    LedgerDatabaseConfig,
    LedgerRuntimeError,
    database_target,
    managed_db_tests_enabled,
    redact_database_url,
    require_managed_db_tests_enabled,
    require_migration_apply_confirmation,
    validate_postgres_database_url,
)

VALID_RUNTIME_URL = (
    "postgres://trader:s3cr3t@db.supabase.co:5432/postgres"
    "?sslmode=require&application_name=ledger-check"
)


def test_runtime_database_config_requires_explicit_database_url() -> None:
    with pytest.raises(LedgerRuntimeError, match="DATABASE_URL is required"):
        LedgerDatabaseConfig.from_env({})


def test_runtime_database_url_validation_rejects_unsafe_values() -> None:
    invalid_urls = (
        "",
        "sqlite:///:memory:",
        "postgresql://user:password@localhost:5432/postgres",
        "postgresql://trader:secret@example.invalid:5432/postgres",
        "postgresql://trader:secret@db.supabase.co:5432/",
    )

    for database_url in invalid_urls:
        with pytest.raises(LedgerRuntimeError):
            validate_postgres_database_url(database_url)


def test_runtime_database_url_validation_normalizes_postgres_scheme() -> None:
    normalized = validate_postgres_database_url(VALID_RUNTIME_URL)

    assert normalized.startswith("postgresql://")
    assert "db.supabase.co" in normalized


def test_runtime_database_url_redaction_hides_credentials_and_query_values() -> None:
    redacted = redact_database_url(VALID_RUNTIME_URL)

    assert "trader" not in redacted
    assert "s3cr3t" not in redacted
    assert "ledger-check" not in redacted
    assert redacted == (
        "postgresql://***:***@db.supabase.co:5432/postgres"
        "?sslmode=***&application_name=***"
    )


def test_runtime_database_target_is_safe_to_print() -> None:
    target = database_target(VALID_RUNTIME_URL)

    assert target.display == "postgresql://db.supabase.co:5432/postgres sslmode=require"
    assert "trader" not in target.display
    assert "s3cr3t" not in target.display


def test_managed_database_operations_require_second_opt_in_gate() -> None:
    assert managed_db_tests_enabled({}) is False
    assert managed_db_tests_enabled({"RUN_MANAGED_DB_TESTS": "0"}) is False
    assert managed_db_tests_enabled({"RUN_MANAGED_DB_TESTS": "1"}) is True

    with pytest.raises(LedgerRuntimeError, match="RUN_MANAGED_DB_TESTS=1 is required"):
        require_managed_db_tests_enabled({})


def test_migration_apply_requires_confirmation_gate() -> None:
    with pytest.raises(LedgerRuntimeError, match="RUN_MANAGED_DB_TESTS=1 is required"):
        require_migration_apply_confirmation({})

    with pytest.raises(LedgerRuntimeError, match="LEDGER_MIGRATION_CONFIRM"):
        require_migration_apply_confirmation({"RUN_MANAGED_DB_TESTS": "1"})

    require_migration_apply_confirmation(
        {
            "RUN_MANAGED_DB_TESTS": "1",
            "LEDGER_MIGRATION_CONFIRM": LEDGER_MIGRATION_CONFIRM_VALUE,
        }
    )
