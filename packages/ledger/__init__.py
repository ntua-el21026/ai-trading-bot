"""Database/audit-ledger foundation.

The ledger package owns persistence schema and repository boundaries. It does not call brokers,
AI/news providers, Temporal, alert services, or managed database APIs.
"""

from packages.ledger.connection import connect_in_memory_sqlite
from packages.ledger.repositories import SQLiteLedgerRepository
from packages.ledger.runtime import (
    LedgerDatabaseConfig,
    LedgerRuntimeError,
    connect_runtime_postgres,
)
from packages.ledger.schema import EXPECTED_LEDGER_TABLES, create_sqlite_schema

__all__ = [
    "EXPECTED_LEDGER_TABLES",
    "LedgerDatabaseConfig",
    "LedgerRuntimeError",
    "SQLiteLedgerRepository",
    "connect_in_memory_sqlite",
    "connect_runtime_postgres",
    "create_sqlite_schema",
]
