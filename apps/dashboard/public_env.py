"""Safe public dashboard environment contract."""

from __future__ import annotations

from collections.abc import Mapping

SAFE_PUBLIC_ENV_NAMES: tuple[str, ...] = (
    "NEXT_PUBLIC_DASHBOARD_API_BASE_URL",
    "NEXT_PUBLIC_APP_ENV",
    "NEXT_PUBLIC_DASHBOARD_ENV",
)


def select_public_dashboard_env(raw_env: Mapping[str, str]) -> dict[str, str]:
    """Return only explicitly safe public dashboard environment values."""

    return {name: raw_env[name] for name in SAFE_PUBLIC_ENV_NAMES if name in raw_env}
