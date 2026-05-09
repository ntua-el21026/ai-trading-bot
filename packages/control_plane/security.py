"""Dashboard/frontend environment guardrails."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from pathlib import Path

FORBIDDEN_FRONTEND_ENV_NAMES: tuple[str, ...] = (
    "ALPACA_API_KEY",
    "ALPACA_SECRET_KEY",
    "OPENAI_API_KEY",
    "MARKETAUX_API_KEY",
    "ALPHA_VANTAGE_API_KEY",
    "ANTHROPIC_API_KEY",
    "POLYGON_API_KEY",
    "FINNHUB_API_KEY",
    "FMP_API_KEY",
    "TIINGO_API_KEY",
    "TAVILY_API_KEY",
    "BRAVE_SEARCH_API_KEY",
    "DATABASE_URL",
    "TEMPORAL_ADDRESS",
    "TEMPORAL_NAMESPACE",
    "TEMPORAL_API_KEY",
    "TELEGRAM_BOT_TOKEN",
    "TELEGRAM_CHAT_ID",
)


def forbidden_env_references_in_paths(
    paths: Iterable[Path],
    *,
    forbidden_names: Sequence[str] = FORBIDDEN_FRONTEND_ENV_NAMES,
) -> tuple[str, ...]:
    violations: list[str] = []
    for root in paths:
        files = [root] if root.is_file() else [path for path in root.rglob("*") if path.is_file()]
        for file_path in files:
            if "__pycache__" in file_path.parts:
                continue
            text = file_path.read_text(encoding="utf-8")
            for name in forbidden_names:
                if name in text:
                    violations.append(f"{file_path}:{name}")
    return tuple(violations)
