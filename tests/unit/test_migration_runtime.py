from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from packages.ledger.schema import EXPECTED_LEDGER_TABLES, read_postgres_migration

ROOT = Path(__file__).resolve().parents[2]
APPLY_SCRIPT = ROOT / "scripts" / "apply_ledger_migrations.py"
CHECK_SCRIPT = ROOT / "scripts" / "check_ledger_database.py"
VALID_RUNTIME_URL = (
    "postgresql://trader:s3cr3t@db.supabase.co:5432/postgres?sslmode=require"
)
PLACEHOLDER_RUNTIME_URL = "postgresql://user:password@localhost:5432/postgres"


def test_postgres_migration_sql_contains_expected_tables_and_no_secret_values() -> None:
    migration = read_postgres_migration()

    for table_name in EXPECTED_LEDGER_TABLES:
        assert f"CREATE TABLE IF NOT EXISTS {table_name}" in migration
    assert "DATABASE_URL=" not in migration
    assert "ALPACA_SECRET_KEY=" not in migration
    assert "OPENAI_API_KEY=" not in migration
    assert "-----BEGIN" not in migration


def test_apply_migration_script_dry_run_requires_url_but_does_not_connect() -> None:
    completed = _run_script(APPLY_SCRIPT, {"DATABASE_URL": VALID_RUNTIME_URL})

    assert completed.returncode == 0
    assert "Mode: dry-run" in completed.stdout
    assert "db.supabase.co" in completed.stdout
    assert "s3cr3t" not in completed.stdout
    assert "trader" not in completed.stdout
    assert completed.stderr == ""


def test_apply_migration_script_fails_closed_without_database_url() -> None:
    completed = _run_script(APPLY_SCRIPT, {})

    assert completed.returncode == 2
    assert "DATABASE_URL is required" in completed.stderr


def test_check_database_script_rejects_placeholder_database_url_without_leaking_it() -> None:
    completed = _run_script(CHECK_SCRIPT, {"DATABASE_URL": PLACEHOLDER_RUNTIME_URL})

    assert completed.returncode == 2
    assert "placeholder value" in completed.stderr
    assert "user:password" not in completed.stderr
    assert PLACEHOLDER_RUNTIME_URL not in completed.stderr


def _run_script(
    script: Path,
    env_overrides: dict[str, str],
) -> subprocess.CompletedProcess[str]:
    env = {
        key: value
        for key, value in os.environ.items()
        if key not in {"DATABASE_URL", "RUN_MANAGED_DB_TESTS"}
    }
    env.update(env_overrides)
    return subprocess.run(
        [sys.executable, str(script)],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
