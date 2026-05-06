"""Fake/local activity service helpers for tests."""

from __future__ import annotations

import sqlite3

from apps.workers.app.activities.ledger import LedgerActivityService
from packages.ledger.connection import connect_in_memory_sqlite
from packages.ledger.repositories import SQLiteLedgerRepository


def build_fake_ledger_activity_service(
    connection: sqlite3.Connection | None = None,
) -> LedgerActivityService:
    """Build a fake-safe ledger service backed by local SQLite only."""

    return LedgerActivityService(SQLiteLedgerRepository(connection or connect_in_memory_sqlite()))
