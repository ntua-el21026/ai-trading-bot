from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "run_paper_dry_run.py"


def test_paper_dry_run_cli_defaults_to_fake_local_mode() -> None:
    completed = subprocess.run(
        [sys.executable, str(SCRIPT)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0
    lines = completed.stdout.splitlines()
    assert lines[0] == "This is a fake/local dry run. No broker orders are submitted."
    payload: dict[str, Any] = json.loads("\n".join(lines[1:]))
    assert payload["passed"] is True
    assert payload["safety_flags"]["external_calls_performed"] is False
    assert payload["safety_flags"]["real_orders_submitted"] is False


def test_paper_dry_run_cli_refuses_non_fake_mode() -> None:
    completed = subprocess.run(
        [sys.executable, str(SCRIPT), "--mode", "live"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 2
    assert "Refusing non-fake paper dry-run mode." in completed.stderr
