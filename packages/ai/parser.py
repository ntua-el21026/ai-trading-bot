"""Strict JSON parsing and schema fallback for AI research output."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from pydantic import ValidationError

from packages.ai.fallback import neutral_research_output
from packages.ai.models import AITradeResearchOutput


def parse_ai_trade_research_json(raw_output: str) -> AITradeResearchOutput:
    parsed: Any = json.loads(raw_output)
    return AITradeResearchOutput.model_validate(parsed)


def parse_ai_trade_research_or_fallback(
    raw_output: str,
    *,
    symbol: str,
    analysis_at: datetime,
    prompt_version: str,
    schema_version: str,
    model_version: str,
) -> AITradeResearchOutput:
    try:
        return parse_ai_trade_research_json(raw_output)
    except json.JSONDecodeError:
        return neutral_research_output(
            symbol=symbol,
            analysis_at=analysis_at,
            prompt_version=prompt_version,
            schema_version=schema_version,
            model_version=model_version,
            fallback_reason="invalid_json",
            explanation="AI output was not valid JSON; using neutral fallback.",
        )
    except ValidationError:
        return neutral_research_output(
            symbol=symbol,
            analysis_at=analysis_at,
            prompt_version=prompt_version,
            schema_version=schema_version,
            model_version=model_version,
            fallback_reason="schema_violation",
            explanation="AI output failed strict schema validation; using neutral fallback.",
        )
