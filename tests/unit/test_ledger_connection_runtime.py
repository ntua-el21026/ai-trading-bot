from __future__ import annotations

import os

import pytest

from packages.ledger.connection import connect_in_memory_sqlite
from packages.ledger.runtime import (
    LedgerDatabaseConfig,
    check_postgres_ledger_schema,
    connect_runtime_postgres,
)
from packages.ledger.schema import EXPECTED_LEDGER_TABLES, sqlite_table_names


def test_default_sqlite_connection_remains_local_and_schema_initialized() -> None:
    connection = connect_in_memory_sqlite()

    assert set(sqlite_table_names(connection)) == set(EXPECTED_LEDGER_TABLES)


@pytest.mark.integration
@pytest.mark.skipif(
    os.environ.get("RUN_MANAGED_DB_TESTS") != "1" or not os.environ.get("DATABASE_URL"),
    reason="managed DB checks require RUN_MANAGED_DB_TESTS=1 and DATABASE_URL",
)
def test_managed_postgres_schema_check_is_explicit_opt_in() -> None:
    config = LedgerDatabaseConfig.from_env()

    with connect_runtime_postgres(config) as connection:
        result = check_postgres_ledger_schema(connection)

    assert result.ok
