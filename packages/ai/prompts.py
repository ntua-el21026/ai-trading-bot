"""Versioned AI prompt template loading."""

from __future__ import annotations

from pathlib import Path

from packages.ai.models import AI_PROMPT_VERSION

PROMPT_TEMPLATE_DIR = Path(__file__).resolve().parent / "prompts"


class PromptTemplateNotFound(RuntimeError):
    """Raised when a configured prompt template version is missing."""


def prompt_template_path(prompt_version: str = AI_PROMPT_VERSION) -> Path:
    return PROMPT_TEMPLATE_DIR / f"{prompt_version}.md"


def load_prompt_template(prompt_version: str = AI_PROMPT_VERSION) -> str:
    path = prompt_template_path(prompt_version)
    if not path.is_file():
        raise PromptTemplateNotFound(f"missing AI prompt template: {path}")
    return path.read_text(encoding="utf-8")
