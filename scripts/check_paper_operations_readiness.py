#!/usr/bin/env python
"""Run the controlled paper operations readiness harness.

This script is read-only. It does not submit/cancel/replace broker orders, activate schedules, call
AI/news providers, send real alerts, deploy anything, or print secrets.
"""

# ruff: noqa: E402

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from packages.control_plane.runtime import run_dashboard_control_plane_smoke
from packages.paper.readiness import (
    build_repository_readiness_evidence,
    evaluate_paper_operations_readiness,
)
from scripts.check_vercel_dashboard_preview import check_vercel_dashboard_preview


def run_paper_operations_readiness_check() -> dict[str, object]:
    dashboard_result = run_dashboard_control_plane_smoke(environ={})
    vercel_result = check_vercel_dashboard_preview(environ={}, check_cli=False)
    evidence = build_repository_readiness_evidence(
        repo_root=Path.cwd(),
        dashboard_runtime_smoke_evidence=(
            dashboard_result.snapshot_built
            and dashboard_result.safe_controls_validated
            and not dashboard_result.broker_calls_performed
            and not dashboard_result.ai_news_calls_performed
            and not dashboard_result.alert_calls_performed
            and not dashboard_result.schedules_created
            and not dashboard_result.schedules_activated
            and not dashboard_result.deployment_performed
        ),
        vercel_preview_guardrails_evidence=(
            vercel_result.failure_codes == ()
            and vercel_result.dashboard_files_included
            and vercel_result.no_workers
            and vercel_result.no_backend_secrets
            and vercel_result.no_browser_privileged_calls
            and vercel_result.no_order_entry_controls
            and vercel_result.secret_env_guardrails
            and vercel_result.public_env_valid
        ),
    )
    return evaluate_paper_operations_readiness(evidence).to_sanitized_dict()


def main() -> int:
    summary = run_paper_operations_readiness_check()
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 1 if summary["hard_failures"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
