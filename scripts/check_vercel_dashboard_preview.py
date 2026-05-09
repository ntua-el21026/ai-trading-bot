#!/usr/bin/env python
"""Validate the dashboard-only Vercel preview harness.

The check is intentionally non-deploying. It validates gates, frontend safety, and Vercel config,
then reports sanitized preview-readiness fields. Deployment remains an explicit operator action.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
DASHBOARD_DIR = REPO_ROOT / "apps" / "dashboard"
VERCEL_CONFIG = REPO_ROOT / "vercel.json"
VERCEL_IGNORE = REPO_ROOT / ".vercelignore"
PACKAGE_JSON = REPO_ROOT / "package.json"

PREVIEW_RUN_ENV = "RUN_VERCEL_DASHBOARD_PREVIEW"
PREVIEW_CONFIRM_ENV = "VERCEL_DASHBOARD_PREVIEW_CONFIRM"
PREVIEW_CONFIRM_VALUE = "DASHBOARD_ONLY_NO_SECRETS_NO_WORKERS"

SAFE_PUBLIC_ENV_NAMES = frozenset({"NEXT_PUBLIC_APP_ENV", "NEXT_PUBLIC_DASHBOARD_ENV"})

FORBIDDEN_FRONTEND_ENV_NAMES = (
    "ALPACA_API_KEY",
    "ALPACA_SECRET_KEY",
    "OPENAI_API_KEY",
    "MARKETAUX_API_KEY",
    "ALPHA_VANTAGE_API_KEY",
    "DATABASE_URL",
    "TEMPORAL_ADDRESS",
    "TEMPORAL_NAMESPACE",
    "TEMPORAL_API_KEY",
    "TELEGRAM_BOT_TOKEN",
    "TELEGRAM_CHAT_ID",
    "RUN_MANAGED_DB_TESTS",
    "LEDGER_MIGRATION_CONFIRM",
)

FORBIDDEN_UI_TEXT = (
    "Submit order",
    "Cancel order",
    "Replace order",
    "Place stop",
    "Enable live trading",
    "Enable autonomous",
    "natural-language trading",
)

FORBIDDEN_BROWSER_TOKENS = (
    "fetch(",
    "XMLHttpRequest",
    "WebSocket",
    "EventSource",
    "navigator.sendBeacon",
    "@temporalio",
)


@dataclass(frozen=True)
class VercelDashboardPreviewResult:
    run: str
    gates_loaded: bool
    vercel_cli_available: bool
    vercel_login_available: bool
    preview_deployment_created: bool
    preview_url: str | None
    production_deployment: bool
    secrets_printed: bool
    custom_domain_used: bool
    frontend_scaffold_present: bool
    public_env_valid: bool
    secret_env_guardrails: bool
    no_workers: bool
    no_backend_secrets: bool
    no_browser_privileged_calls: bool
    no_order_entry_controls: bool
    vercel_config_valid: bool
    deployment_performed: bool
    actual_paper_trading_started: bool
    level4_ready: bool
    refused: bool
    refusal_reasons: tuple[str, ...]
    failure_codes: tuple[str, ...]

    def to_sanitized_dict(self) -> dict[str, Any]:
        return asdict(self)


def check_vercel_dashboard_preview(
    *,
    environ: Mapping[str, str] | None = None,
    check_cli: bool = True,
) -> VercelDashboardPreviewResult:
    env = os.environ if environ is None else environ
    gates_loaded = (
        env.get(PREVIEW_RUN_ENV) == "1"
        and env.get(PREVIEW_CONFIRM_ENV) == PREVIEW_CONFIRM_VALUE
    )
    refusal_reasons: list[str] = []
    if not gates_loaded:
        refusal_reasons.append("missing_vercel_dashboard_preview_gates")

    frontend_scaffold_present = _frontend_scaffold_present()
    public_env_valid = _public_env_valid()
    secret_env_guardrails = _secret_env_guardrails()
    no_workers = _vercel_excludes_workers()
    no_backend_secrets = _no_backend_secrets()
    no_browser_privileged_calls = _no_browser_privileged_calls()
    no_order_entry_controls = _no_order_entry_controls()
    vercel_config_valid = _vercel_config_valid()

    failure_codes = tuple(
        code
        for code, ok in (
            ("frontend_scaffold_missing", frontend_scaffold_present),
            ("unsafe_public_env_contract", public_env_valid),
            ("frontend_secret_reference_detected", secret_env_guardrails),
            ("vercel_worker_scope_detected", no_workers),
            ("backend_secret_reference_detected", no_backend_secrets),
            ("browser_privileged_call_detected", no_browser_privileged_calls),
            ("order_entry_control_detected", no_order_entry_controls),
            ("invalid_vercel_config", vercel_config_valid),
        )
        if not ok
    )

    cli_available = shutil.which("vercel") is not None if check_cli else False
    login_available = (
        _vercel_login_available() if check_cli and cli_available and gates_loaded else False
    )

    return VercelDashboardPreviewResult(
        run="refused" if refusal_reasons else "validated",
        gates_loaded=gates_loaded,
        vercel_cli_available=cli_available,
        vercel_login_available=login_available,
        preview_deployment_created=False,
        preview_url=None,
        production_deployment=False,
        secrets_printed=False,
        custom_domain_used=False,
        frontend_scaffold_present=frontend_scaffold_present,
        public_env_valid=public_env_valid,
        secret_env_guardrails=secret_env_guardrails,
        no_workers=no_workers,
        no_backend_secrets=no_backend_secrets,
        no_browser_privileged_calls=no_browser_privileged_calls,
        no_order_entry_controls=no_order_entry_controls,
        vercel_config_valid=vercel_config_valid,
        deployment_performed=False,
        actual_paper_trading_started=False,
        level4_ready=False,
        refused=bool(refusal_reasons),
        refusal_reasons=tuple(refusal_reasons),
        failure_codes=failure_codes,
    )


def _frontend_scaffold_present() -> bool:
    return (
        (DASHBOARD_DIR / "src" / "index.html").is_file()
        and (DASHBOARD_DIR / "src" / "styles.css").is_file()
        and (DASHBOARD_DIR / "build-preview.mjs").is_file()
        and PACKAGE_JSON.is_file()
    )


def _public_env_valid() -> bool:
    text = (DASHBOARD_DIR / "build-preview.mjs").read_text(encoding="utf-8")
    referenced = {name for name in SAFE_PUBLIC_ENV_NAMES if name in text}
    return referenced == SAFE_PUBLIC_ENV_NAMES and not any(
        name.startswith("NEXT_PUBLIC_") and name not in SAFE_PUBLIC_ENV_NAMES
        for name in _tokens_from_text(text)
    )


def _secret_env_guardrails() -> bool:
    return _forbidden_references_in_path(DASHBOARD_DIR) == ()


def _vercel_excludes_workers() -> bool:
    if not VERCEL_IGNORE.is_file():
        return False
    text = VERCEL_IGNORE.read_text(encoding="utf-8")
    return all(pattern in text for pattern in ("apps/workers/", "apps/api/", "packages/"))


def _no_backend_secrets() -> bool:
    if not VERCEL_IGNORE.is_file():
        return False
    text = VERCEL_IGNORE.read_text(encoding="utf-8")
    return ".env" in text and ".env.*" in text


def _no_browser_privileged_calls() -> bool:
    frontend_scripts = list((DASHBOARD_DIR / "src").rglob("*.js")) + list(
        (DASHBOARD_DIR / "src").rglob("*.mjs")
    )
    frontend_scripts.append(DASHBOARD_DIR / "build-preview.mjs")
    for file_path in frontend_scripts:
        if not file_path.is_file():
            continue
        text = file_path.read_text(encoding="utf-8")
        if any(token in text for token in FORBIDDEN_BROWSER_TOKENS):
            return False
    return True


def _no_order_entry_controls() -> bool:
    text = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (DASHBOARD_DIR / "src").rglob("*")
        if path.is_file()
    )
    return not any(token in text for token in FORBIDDEN_UI_TEXT) and "<button" not in text.lower()


def _vercel_config_valid() -> bool:
    if not VERCEL_CONFIG.is_file():
        return False
    config = json.loads(VERCEL_CONFIG.read_text(encoding="utf-8"))
    return (
        config.get("framework") is None
        and config.get("buildCommand") == "npm run build"
        and config.get("outputDirectory") == "apps/dashboard/dist"
        and "functions" not in config
        and "crons" not in config
    )


def _vercel_login_available() -> bool:
    try:
        result = subprocess.run(
            ["vercel", "whoami"],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return result.returncode == 0


def _tokens_from_text(text: str) -> set[str]:
    normalized = text.replace('"', " ").replace("'", " ").replace("`", " ")
    return {token.strip(" ,;:()[]{}") for token in normalized.split()}


def _forbidden_references_in_path(root: Path) -> tuple[str, ...]:
    violations: list[str] = []
    for path in root.rglob("*"):
        if not path.is_file() or "__pycache__" in path.parts:
            continue
        text = path.read_text(encoding="utf-8")
        for name in FORBIDDEN_FRONTEND_ENV_NAMES:
            if name in text:
                violations.append(f"{path}:{name}")
    return tuple(violations)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--frontend-only",
        action="store_true",
        help="Validate frontend/config guardrails without checking Vercel CLI login.",
    )
    args = parser.parse_args()

    result = check_vercel_dashboard_preview(check_cli=not args.frontend_only)
    print(json.dumps(result.to_sanitized_dict(), indent=2, sort_keys=True))
    if result.failure_codes:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
