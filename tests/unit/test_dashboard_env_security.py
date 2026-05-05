from pathlib import Path

from apps.dashboard.public_env import SAFE_PUBLIC_ENV_NAMES, select_public_dashboard_env
from packages.control_plane.security import (
    FORBIDDEN_FRONTEND_ENV_NAMES,
    forbidden_env_references_in_paths,
)


def test_dashboard_public_env_selector_exposes_only_safe_public_values() -> None:
    selected = select_public_dashboard_env(
        {
            "NEXT_PUBLIC_DASHBOARD_API_BASE_URL": "https://dashboard.example.test",
            "NEXT_PUBLIC_APP_ENV": "test",
            "ALPACA_API_KEY": "should-not-expose",
            "OPENAI_API_KEY": "should-not-expose",
            "DATABASE_URL": "postgres://should-not-expose",
        }
    )

    assert selected == {
        "NEXT_PUBLIC_DASHBOARD_API_BASE_URL": "https://dashboard.example.test",
        "NEXT_PUBLIC_APP_ENV": "test",
    }
    assert set(selected).issubset(SAFE_PUBLIC_ENV_NAMES)


def test_dashboard_code_does_not_reference_forbidden_secret_env_names() -> None:
    violations = forbidden_env_references_in_paths(
        (Path("apps/dashboard"),),
        forbidden_names=FORBIDDEN_FRONTEND_ENV_NAMES,
    )

    assert violations == ()
