"""Bounded AI/news intelligence layer contracts."""

from packages.ai.dedupe import dedupe_articles, normalize_article, normalize_articles
from packages.ai.fallback import (
    conflicting_sources_fallback,
    neutral_research_output,
    no_news_fallback,
    provider_outage_fallback,
)
from packages.ai.models import (
    AI_PROMPT_VERSION,
    AI_SCHEMA_VERSION,
    NEUTRAL_AI_SCORE,
    AICitation,
    AIEvent,
    AIProviderFailure,
    AITradeResearchOutput,
    DeterministicShortlistNewsRequest,
    NormalizedNewsArticle,
    ProviderNewsArticle,
)
from packages.ai.parser import parse_ai_trade_research_json, parse_ai_trade_research_or_fallback
from packages.ai.persistence import (
    AIResearchPersistencePayload,
    build_ai_research_persistence_payload,
)
from packages.ai.prompts import load_prompt_template, prompt_template_path
from packages.ai.scoring import (
    apply_deterministic_ai_policy,
    classify_hard_block,
    mapped_ai_score,
    raw_catalyst_score,
)

__all__ = [
    "AI_PROMPT_VERSION",
    "AI_SCHEMA_VERSION",
    "NEUTRAL_AI_SCORE",
    "AICitation",
    "AIEvent",
    "AIProviderFailure",
    "AIResearchPersistencePayload",
    "AITradeResearchOutput",
    "DeterministicShortlistNewsRequest",
    "NormalizedNewsArticle",
    "ProviderNewsArticle",
    "apply_deterministic_ai_policy",
    "build_ai_research_persistence_payload",
    "classify_hard_block",
    "conflicting_sources_fallback",
    "dedupe_articles",
    "load_prompt_template",
    "mapped_ai_score",
    "neutral_research_output",
    "no_news_fallback",
    "normalize_article",
    "normalize_articles",
    "parse_ai_trade_research_json",
    "parse_ai_trade_research_or_fallback",
    "prompt_template_path",
    "provider_outage_fallback",
    "raw_catalyst_score",
]
