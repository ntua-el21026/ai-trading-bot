from __future__ import annotations

import json
from fnmatch import fnmatch
from pathlib import Path

from scripts.check_vercel_dashboard_preview import (
    PREVIEW_CONFIRM_VALUE,
    check_vercel_dashboard_preview,
)


def test_preview_smoke_refuses_without_gates_but_validates_guardrails() -> None:
    result = check_vercel_dashboard_preview(environ={}, check_cli=False)

    assert result.refused is True
    assert "missing_vercel_dashboard_preview_gates" in result.refusal_reasons
    assert result.failure_codes == ()
    assert result.preview_deployment_created is False
    assert result.deployment_performed is False


def test_preview_smoke_validates_gates_when_present() -> None:
    result = check_vercel_dashboard_preview(
        environ={
            "RUN_VERCEL_DASHBOARD_PREVIEW": "1",
            "VERCEL_DASHBOARD_PREVIEW_CONFIRM": PREVIEW_CONFIRM_VALUE,
            "NEXT_PUBLIC_APP_ENV": "dev",
            "NEXT_PUBLIC_DASHBOARD_ENV": "preview",
        },
        check_cli=False,
    )

    assert result.refused is False
    assert result.gates_loaded is True
    assert result.frontend_scaffold_present is True
    assert result.dashboard_files_included is True
    assert result.public_env_valid is True
    assert result.secret_env_guardrails is True
    assert result.no_workers is True
    assert result.no_backend_secrets is True
    assert result.no_browser_privileged_calls is True
    assert result.no_order_entry_controls is True
    assert result.vercel_config_valid is True
    assert result.production_deployment is False


def test_vercel_config_is_dashboard_only_static_preview() -> None:
    config = json.loads(Path("vercel.json").read_text(encoding="utf-8"))

    assert config["framework"] is None
    assert config["buildCommand"] == "npm run build"
    assert config["outputDirectory"] == "apps/dashboard/dist"
    assert "functions" not in config
    assert "crons" not in config


def test_vercel_ignore_includes_dashboard_build_inputs() -> None:
    required_files = (
        "package.json",
        "package-lock.json",
        "vercel.json",
        "apps/dashboard/build-preview.mjs",
        "apps/dashboard/src/index.html",
        "apps/dashboard/src/styles.css",
        "apps/dashboard/public_env.py",
    )

    assert all(not _vercelignored(path) for path in required_files)


def test_vercel_ignore_excludes_workers_backend_and_local_env() -> None:
    text = Path(".vercelignore").read_text(encoding="utf-8")

    assert ".env" in text
    assert ".env.*" in text
    assert "apps/workers/" in text
    assert "apps/api/" in text
    assert "packages/" in text
    assert "scripts/" in text
    assert "tests/" in text
    assert _vercelignored(".env")
    assert _vercelignored("apps/workers/app/worker.py")
    assert _vercelignored("apps/api/app/control_plane.py")
    assert _vercelignored("packages/broker/alpaca.py")


def test_dashboard_build_uses_only_approved_public_env_names() -> None:
    text = Path("apps/dashboard/build-preview.mjs").read_text(encoding="utf-8")

    assert "NEXT_PUBLIC_APP_ENV" in text
    assert "NEXT_PUBLIC_DASHBOARD_ENV" in text
    assert "NEXT_PUBLIC_DASHBOARD_API_BASE_URL" not in text


def test_dashboard_preview_has_no_order_entry_ui_or_privileged_browser_calls() -> None:
    source = "\n".join(
        path.read_text(encoding="utf-8")
        for path in Path("apps/dashboard/src").rglob("*")
        if path.is_file()
    )
    script = Path("apps/dashboard/build-preview.mjs").read_text(encoding="utf-8")

    assert "<button" not in source.lower()
    assert "Submit order" not in source
    assert "Cancel order" not in source
    assert "Replace order" not in source
    assert "Place stop" not in source
    assert "fetch(" not in script
    assert "WebSocket" not in script
    assert "@temporalio" not in script


def _vercelignored(path: str) -> bool:
    ignored = False
    for raw_line in Path(".vercelignore").read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        negated = line.startswith("!")
        pattern = line[1:] if negated else line
        if _matches(path, pattern):
            ignored = not negated
    return ignored


def _matches(path: str, pattern: str) -> bool:
    normalized = pattern.strip("/")
    if not normalized:
        return False
    if pattern.endswith("/"):
        return path == normalized or path.startswith(f"{normalized}/")
    return fnmatch(path, normalized) or fnmatch(Path(path).name, normalized)
