"""Neutral AI fallback contracts."""

from __future__ import annotations

from datetime import datetime

from packages.ai.models import (
    NEUTRAL_AI_SCORE,
    AIProviderFailure,
    AITradeResearchOutput,
    FallbackReason,
    NewsState,
)


def neutral_research_output(
    *,
    symbol: str,
    analysis_at: datetime,
    prompt_version: str,
    schema_version: str,
    model_version: str,
    fallback_reason: FallbackReason,
    news_state: NewsState = "insufficient_data",
    explanation: str | None = None,
    size_multiplier: float = 1.0,
) -> AITradeResearchOutput:
    return AITradeResearchOutput(
        symbol=symbol,
        analysis_at=analysis_at,
        schema_version=schema_version,
        prompt_version=prompt_version,
        model_version=model_version,
        news_state=news_state,
        events=(),
        citations=(),
        hard_block=False,
        hard_block_reason=None,
        ai_score=NEUTRAL_AI_SCORE,
        size_multiplier=min(size_multiplier, 1.0),
        explanation=explanation or f"Neutral AI fallback: {fallback_reason}",
        fallback=True,
        fallback_reason=fallback_reason,
    )


def no_news_fallback(
    *,
    symbol: str,
    analysis_at: datetime,
    prompt_version: str,
    schema_version: str,
    model_version: str,
) -> AITradeResearchOutput:
    return neutral_research_output(
        symbol=symbol,
        analysis_at=analysis_at,
        prompt_version=prompt_version,
        schema_version=schema_version,
        model_version=model_version,
        fallback_reason="no_news_found",
        news_state="insufficient_data",
        explanation="No candidate-specific news found; using neutral AI score.",
    )


def provider_outage_fallback(
    *,
    symbol: str,
    analysis_at: datetime,
    prompt_version: str,
    schema_version: str,
    model_version: str,
    provider: str,
    message: str,
) -> tuple[AITradeResearchOutput, AIProviderFailure]:
    output = neutral_research_output(
        symbol=symbol,
        analysis_at=analysis_at,
        prompt_version=prompt_version,
        schema_version=schema_version,
        model_version=model_version,
        fallback_reason="ai_provider_outage",
        news_state="provider_error",
        explanation="AI provider outage; using neutral fallback without global kill switch.",
    )
    failure = AIProviderFailure(
        symbol=symbol,
        occurred_at=analysis_at,
        provider=provider,
        reason="ai_provider_outage",
        message=message,
    )
    return output, failure


def conflicting_sources_fallback(
    *,
    symbol: str,
    analysis_at: datetime,
    prompt_version: str,
    schema_version: str,
    model_version: str,
) -> AITradeResearchOutput:
    return neutral_research_output(
        symbol=symbol,
        analysis_at=analysis_at,
        prompt_version=prompt_version,
        schema_version=schema_version,
        model_version=model_version,
        fallback_reason="conflicting_sources",
        news_state="mixed",
        explanation="Conflicting candidate-specific sources; using mixed neutral fallback.",
        size_multiplier=0.75,
    )
