"""Local database connection helpers for ledger tests and development."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from packages.ledger.schema import create_sqlite_schema


def connect_in_memory_sqlite(*, initialize: bool = True) -> sqlite3.Connection:
    """Create an in-memory SQLite ledger connection.

    This helper is for local tests and deterministic development only. It does not read
    `DATABASE_URL` and never opens a managed Postgres/Supabase connection.
    """

    return connect_sqlite(":memory:", initialize=initialize)


def connect_sqlite(path: str | Path, *, initialize: bool = True) -> sqlite3.Connection:
    connection = sqlite3.connect(str(path))
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    if initialize:
        create_sqlite_schema(connection)
    return connection
