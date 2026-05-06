"""Explicit Postgres/Supabase runtime helpers for the ledger.

Default tests use SQLite helpers from :mod:`packages.ledger.connection`. This module is only for
operator-invoked runtime checks and migration application against a Postgres-compatible database.
It never reads credentials unless called explicitly and it never calls broker, AI/news, alert,
Temporal, or trading services.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any
from urllib.parse import parse_qsl, urlsplit, urlunsplit

import psycopg
from psycopg import Connection
from psycopg.rows import dict_row

from packages.ledger.schema import EXPECTED_LEDGER_TABLES, read_postgres_migration

DATABASE_URL_ENV_VAR = "DATABASE_URL"
SUPPORTED_POSTGRES_SCHEMES = frozenset({"postgres", "postgresql"})
PLACEHOLDER_DATABASE_URL_MARKERS = (
    "<",
    ">",
    "example",
    "placeholder",
    "changeme",
    "change-me",
    "replace-me",
    "your-",
    "your_",
    "user:password",
    "username:password",
    "password@",
    "DATABASE_URL",
)


class LedgerRuntimeError(RuntimeError):
    """Raised when explicit runtime database configuration is missing or unsafe."""


@dataclass(frozen=True)
class LedgerDatabaseTarget:
    """Redacted database target metadata safe to print in logs and scripts."""

    scheme: str
    host: str
    port: int | None
    database: str
    sslmode: str | None

    @property
    def display(self) -> str:
        port = "" if self.port is None else f":{self.port}"
        sslmode = "" if self.sslmode is None else f" sslmode={self.sslmode}"
        return f"{self.scheme}://{self.host}{port}/{self.database}{sslmode}"


@dataclass(frozen=True)
class LedgerDatabaseConfig:
    """Validated explicit runtime database configuration."""

    database_url: str
    connect_timeout_seconds: int = 10

    @classmethod
    def from_env(
        cls,
        env: Mapping[str, str] | None = None,
        *,
        env_var: str = DATABASE_URL_ENV_VAR,
    ) -> LedgerDatabaseConfig:
        source = os.environ if env is None else env
        database_url = source.get(env_var, "")
        if not database_url.strip():
            raise LedgerRuntimeError(
                f"{env_var} is required for managed Postgres/Supabase runtime operations."
            )
        return cls(database_url=validate_postgres_database_url(database_url))

    @property
    def redacted_url(self) -> str:
        return redact_database_url(self.database_url)

    @property
    def target(self) -> LedgerDatabaseTarget:
        return database_target(self.database_url)


@dataclass(frozen=True)
class LedgerSchemaCheckResult:
    expected_tables: tuple[str, ...]
    present_tables: tuple[str, ...]
    missing_tables: tuple[str, ...]

    @property
    def ok(self) -> bool:
        return not self.missing_tables


def validate_postgres_database_url(database_url: str) -> str:
    """Validate a runtime Postgres URL without opening a connection."""

    normalized = _normalize_database_url(database_url)
    parsed = urlsplit(normalized)
    if parsed.scheme not in SUPPORTED_POSTGRES_SCHEMES:
        raise LedgerRuntimeError("DATABASE_URL must use a postgres/postgresql scheme.")
    if not parsed.hostname:
        raise LedgerRuntimeError("DATABASE_URL must include a hostname.")
    database = parsed.path.lstrip("/")
    if not database:
        raise LedgerRuntimeError("DATABASE_URL must include a database name.")
    _reject_placeholder_url(normalized)
    return normalized


def redact_database_url(database_url: str) -> str:
    """Return a safe-to-print database URL that hides user, password, and query values."""

    parsed = urlsplit(_normalize_database_url(database_url))
    host = parsed.hostname or ""
    port = "" if parsed.port is None else f":{parsed.port}"
    userinfo = "***:***@" if parsed.username or parsed.password else ""
    query_keys = tuple(key for key, _value in parse_qsl(parsed.query, keep_blank_values=True))
    query = "&".join(f"{key}=***" for key in query_keys)
    return urlunsplit((parsed.scheme, f"{userinfo}{host}{port}", parsed.path, query, ""))


def database_target(database_url: str) -> LedgerDatabaseTarget:
    """Return redacted target metadata suitable for script output."""

    parsed = urlsplit(validate_postgres_database_url(database_url))
    query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    return LedgerDatabaseTarget(
        scheme="postgresql",
        host=parsed.hostname or "",
        port=parsed.port,
        database=parsed.path.lstrip("/"),
        sslmode=query.get("sslmode"),
    )


def connect_runtime_postgres(config: LedgerDatabaseConfig) -> Connection[dict[str, Any]]:
    """Open an explicit psycopg runtime connection.

    This function does not fall back to SQLite and should only be called from operator-invoked
    scripts, opt-in integration tests, or future server-side runtime wiring.
    """

    return psycopg.connect(
        config.database_url,
        connect_timeout=config.connect_timeout_seconds,
        row_factory=dict_row,
    )


def apply_postgres_migration_sql(
    connection: Connection[dict[str, Any]],
    *,
    migration_sql: str | None = None,
) -> None:
    """Apply the checked-in ledger migration SQL to an explicit Postgres connection."""

    sql = migration_sql or read_postgres_migration()
    with connection.cursor() as cursor:
        cursor.execute(sql)
    connection.commit()


def fetch_postgres_table_names(connection: Connection[dict[str, Any]]) -> tuple[str, ...]:
    """Fetch public base-table names from a Postgres-compatible database."""

    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
            ORDER BY table_name
            """
        )
        rows = cursor.fetchall()
    return tuple(str(row["table_name"]) for row in rows)


def check_postgres_ledger_schema(
    connection: Connection[dict[str, Any]],
) -> LedgerSchemaCheckResult:
    """Check whether all expected audit-ledger tables exist in Postgres."""

    present = fetch_postgres_table_names(connection)
    present_set = set(present)
    missing = tuple(table for table in EXPECTED_LEDGER_TABLES if table not in present_set)
    return LedgerSchemaCheckResult(
        expected_tables=EXPECTED_LEDGER_TABLES,
        present_tables=present,
        missing_tables=missing,
    )


def _normalize_database_url(database_url: str) -> str:
    normalized = database_url.strip()
    if normalized.startswith("postgres://"):
        return "postgresql://" + normalized.removeprefix("postgres://")
    return normalized


def _reject_placeholder_url(database_url: str) -> None:
    lowered = database_url.lower()
    for marker in PLACEHOLDER_DATABASE_URL_MARKERS:
        if marker.lower() in lowered:
            raise LedgerRuntimeError("DATABASE_URL appears to contain a placeholder value.")
