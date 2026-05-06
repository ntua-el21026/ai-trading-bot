"""Ledger schema helpers.

The checked-in migration is Postgres-oriented. The SQLite DDL in this module is a local testing
compatibility layer that preserves table names, essential columns, and idempotency constraints.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

POSTGRES_MIGRATION_PATH = (
    Path(__file__).resolve().parents[2] / "db" / "migrations" / "0001_initial_audit_ledger.sql"
)

EXPECTED_LEDGER_TABLES: tuple[str, ...] = (
    "symbols",
    "raw_provider_payloads",
    "ohlcv_daily",
    "features_daily",
    "regimes",
    "trade_candidates",
    "ai_research_outputs",
    "trade_decisions",
    "risk_checks",
    "execution_intents",
    "orders",
    "fills",
    "positions",
    "broker_reconciliations",
    "system_events",
    "reports",
)

SQLITE_COMPATIBILITY_NOTES = (
    "Postgres is the target database. Local tests use SQLite with JSON stored as canonical text, "
    "TEXT UUIDs, and partial unique indexes where SQLite supports them. Managed Postgres/Supabase "
    "integration remains deferred."
)


def read_postgres_migration() -> str:
    return POSTGRES_MIGRATION_PATH.read_text(encoding="utf-8")


def create_sqlite_schema(connection: sqlite3.Connection) -> None:
    connection.executescript(SQLITE_SCHEMA)


def sqlite_table_names(connection: sqlite3.Connection) -> tuple[str, ...]:
    rows = connection.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
    ).fetchall()
    return tuple(sorted(str(row["name"]) for row in rows))


SQLITE_SCHEMA = """
CREATE TABLE IF NOT EXISTS symbols (
    symbol TEXT PRIMARY KEY,
    asset_class TEXT NOT NULL CHECK (asset_class IN ('equity', 'etf')),
    active INTEGER NOT NULL DEFAULT 1,
    approved_live INTEGER NOT NULL DEFAULT 0,
    approved_research INTEGER NOT NULL DEFAULT 0,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS raw_provider_payloads (
    raw_provider_payload_id TEXT PRIMARY KEY,
    provider TEXT NOT NULL,
    endpoint TEXT NOT NULL,
    symbol TEXT,
    payload_hash TEXT NOT NULL,
    raw_payload_json TEXT NOT NULL,
    content_type TEXT NOT NULL DEFAULT 'application/json',
    received_at TEXT NOT NULL,
    UNIQUE (provider, endpoint, payload_hash)
);

CREATE TABLE IF NOT EXISTS ohlcv_daily (
    ohlcv_daily_id TEXT PRIMARY KEY,
    symbol TEXT NOT NULL,
    trading_date TEXT NOT NULL,
    open REAL NOT NULL CHECK (open > 0),
    high REAL NOT NULL CHECK (high > 0),
    low REAL NOT NULL CHECK (low > 0),
    close REAL NOT NULL CHECK (close > 0),
    volume INTEGER NOT NULL CHECK (volume >= 0),
    adjusted INTEGER NOT NULL DEFAULT 1,
    provider TEXT NOT NULL,
    raw_provider_payload_id TEXT REFERENCES raw_provider_payloads(raw_provider_payload_id),
    created_at TEXT NOT NULL,
    UNIQUE (symbol, trading_date, provider)
);

CREATE TABLE IF NOT EXISTS features_daily (
    features_daily_id TEXT PRIMARY KEY,
    symbol TEXT NOT NULL,
    trading_date TEXT NOT NULL,
    feature_version TEXT NOT NULL,
    close REAL,
    feature_payload_json TEXT NOT NULL DEFAULT '{}',
    source_ohlcv_daily_id TEXT REFERENCES ohlcv_daily(ohlcv_daily_id),
    created_at TEXT NOT NULL,
    UNIQUE (symbol, trading_date, feature_version)
);

CREATE TABLE IF NOT EXISTS regimes (
    regime_id TEXT PRIMARY KEY,
    trading_date TEXT NOT NULL,
    regime_state TEXT NOT NULL,
    model_version TEXT NOT NULL,
    proxy_symbol TEXT NOT NULL,
    diagnostic_payload_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    UNIQUE (trading_date, model_version)
);

CREATE TABLE IF NOT EXISTS trade_candidates (
    candidate_id TEXT PRIMARY KEY,
    symbol TEXT NOT NULL,
    trading_date TEXT NOT NULL,
    strategy_version TEXT NOT NULL,
    candidate_status TEXT NOT NULL,
    technical_score REAL,
    relative_strength_score REAL,
    score_payload_json TEXT NOT NULL DEFAULT '{}',
    reason_payload_json TEXT NOT NULL DEFAULT '{}',
    rejection_reasons_json TEXT NOT NULL DEFAULT '[]',
    source_features_daily_id TEXT REFERENCES features_daily(features_daily_id),
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS ai_research_outputs (
    output_id TEXT PRIMARY KEY,
    symbol TEXT NOT NULL,
    prompt_version TEXT NOT NULL,
    schema_version TEXT NOT NULL,
    model_version TEXT NOT NULL,
    raw_prompt TEXT NOT NULL,
    raw_prompt_hash TEXT NOT NULL,
    raw_output TEXT,
    raw_output_hash TEXT,
    parsed_output_json TEXT NOT NULL,
    ai_score INTEGER NOT NULL CHECK (ai_score BETWEEN 10 AND 90),
    hard_block INTEGER NOT NULL,
    fallback_reason TEXT NOT NULL,
    citations_json TEXT NOT NULL DEFAULT '[]',
    canonical_urls_json TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS trade_decisions (
    decision_id TEXT PRIMARY KEY,
    candidate_id TEXT REFERENCES trade_candidates(candidate_id),
    symbol TEXT NOT NULL,
    decision_status TEXT NOT NULL,
    final_score REAL,
    deterministic_decision_payload_json TEXT NOT NULL DEFAULT '{}',
    ai_output_id TEXT REFERENCES ai_research_outputs(output_id),
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS execution_intents (
    execution_intent_id TEXT PRIMARY KEY,
    temporal_workflow_id TEXT,
    decision_id TEXT,
    client_order_id_root TEXT NOT NULL UNIQUE,
    symbol TEXT NOT NULL,
    side TEXT NOT NULL,
    asset_class TEXT NOT NULL,
    quantity INTEGER NOT NULL CHECK (quantity > 0),
    entry_order_type TEXT NOT NULL,
    limit_price REAL NOT NULL CHECK (limit_price > 0),
    stop_loss_price REAL CHECK (stop_loss_price > 0),
    time_in_force TEXT NOT NULL,
    strategy_version TEXT NOT NULL,
    risk_config_version TEXT NOT NULL,
    autonomy_level INTEGER NOT NULL CHECK (autonomy_level BETWEEN 0 AND 5),
    requires_protective_stop INTEGER NOT NULL,
    max_acceptable_slippage_bps INTEGER NOT NULL CHECK (max_acceptable_slippage_bps >= 0),
    status TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS risk_checks (
    risk_check_id TEXT PRIMARY KEY,
    decision_id TEXT REFERENCES trade_decisions(decision_id),
    execution_intent_id TEXT REFERENCES execution_intents(execution_intent_id),
    symbol TEXT NOT NULL,
    passed INTEGER NOT NULL,
    reason_codes_json TEXT NOT NULL DEFAULT '[]',
    risk_config_version TEXT NOT NULL,
    input_snapshot_json TEXT NOT NULL DEFAULT '{}',
    result_payload_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS orders (
    order_id TEXT PRIMARY KEY,
    execution_intent_id TEXT REFERENCES execution_intents(execution_intent_id),
    broker_order_id TEXT UNIQUE,
    client_order_id TEXT NOT NULL UNIQUE,
    symbol TEXT NOT NULL,
    side TEXT NOT NULL,
    order_type TEXT NOT NULL,
    time_in_force TEXT NOT NULL,
    quantity REAL NOT NULL CHECK (quantity > 0),
    limit_price REAL CHECK (limit_price > 0),
    stop_price REAL CHECK (stop_price > 0),
    status TEXT NOT NULL,
    raw_broker_payload_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS fills (
    fill_id TEXT PRIMARY KEY,
    order_id TEXT NOT NULL REFERENCES orders(order_id),
    broker_order_id TEXT,
    broker_fill_id TEXT UNIQUE,
    symbol TEXT NOT NULL,
    quantity REAL NOT NULL CHECK (quantity > 0),
    price REAL NOT NULL CHECK (price > 0),
    filled_at TEXT NOT NULL,
    raw_broker_payload_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS positions (
    position_id TEXT PRIMARY KEY,
    symbol TEXT NOT NULL,
    quantity REAL NOT NULL,
    average_entry_price REAL NOT NULL CHECK (average_entry_price > 0),
    status TEXT NOT NULL,
    protective_stop_order_id TEXT REFERENCES orders(order_id),
    opened_at TEXT,
    closed_at TEXT,
    raw_source_payload_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS positions_one_open_per_symbol
    ON positions(symbol)
    WHERE status = 'open';

CREATE TABLE IF NOT EXISTS broker_reconciliations (
    reconciliation_id TEXT PRIMARY KEY,
    temporal_workflow_id TEXT,
    account_snapshot_json TEXT NOT NULL,
    broker_positions_json TEXT NOT NULL DEFAULT '[]',
    internal_positions_json TEXT NOT NULL DEFAULT '[]',
    broker_orders_json TEXT NOT NULL DEFAULT '[]',
    internal_orders_json TEXT NOT NULL DEFAULT '[]',
    mismatches_json TEXT NOT NULL DEFAULT '[]',
    status TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS system_events (
    event_id TEXT PRIMARY KEY,
    event_type TEXT NOT NULL,
    severity TEXT NOT NULL,
    source_component TEXT NOT NULL,
    related_entity_type TEXT,
    related_entity_id TEXT,
    message TEXT NOT NULL,
    payload_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    acknowledged_at TEXT
);

CREATE TABLE IF NOT EXISTS reports (
    report_id TEXT PRIMARY KEY,
    report_type TEXT NOT NULL,
    report_date TEXT,
    period_start TEXT,
    period_end TEXT,
    status TEXT NOT NULL,
    payload_json TEXT NOT NULL DEFAULT '{}',
    markdown TEXT,
    created_at TEXT NOT NULL
);
"""
