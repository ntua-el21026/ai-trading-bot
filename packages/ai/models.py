"""Strict AI/news intelligence contracts.

The AI layer is advisory only. These models carry candidate-specific news analysis and never
provide broker authority.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

AI_PROMPT_VERSION = "ai_trade_research_v0_3"
AI_SCHEMA_VERSION = "ai_trade_research_schema_v0_3"
NEUTRAL_AI_SCORE = 50

NewsState = Literal["found", "insufficient_data", "mixed", "provider_error"]
FallbackReason = Literal[
    "none",
    "no_news_found",
    "invalid_json",
    "schema_violation",
    "ai_provider_outage",
    "insufficient_data",
    "provider_error",
    "conflicting_sources",
]
EventType = Literal[
    "earnings_surprise_guidance_revision",
    "offering_dilution_shelf_convert",
    "ma_strategic_deal",
    "lawsuit_sec_fda_halt_accounting_risk",
    "analyst_upgrade_downgrade",
    "product_contract_management_change",
    "dividend_split_calendar_only",
    "generic_macro_mention",
    "other",
]
EventDirection = Literal["positive", "negative", "mixed", "neutral"]
EventRiskLevel = Literal["low", "medium", "high", "blocking"]
SourceQuality = Literal[
    "regulatory_filing",
    "company_pr",
    "premier_financial_publisher",
    "secondary_aggregation",
    "low_substance_rewrite",
]


class AIModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class DeterministicShortlistNewsRequest(AIModel):
    symbols: tuple[str, ...]
    generated_by_strategy: bool = True
    deterministic_shortlist_only: bool = True
    lookback_calendar_days: int = Field(gt=0)
    max_articles_per_symbol: int = Field(gt=0)

    @field_validator("symbols")
    @classmethod
    def validate_symbols(cls, symbols: tuple[str, ...]) -> tuple[str, ...]:
        if not symbols:
            raise ValueError("news request must contain deterministic shortlist symbols")
        if any(symbol != symbol.upper() for symbol in symbols):
            raise ValueError("news request symbols must be uppercase")
        return tuple(dict.fromkeys(symbols))

    @model_validator(mode="after")
    def validate_shortlist_only(self) -> Self:
        if not self.generated_by_strategy:
            raise ValueError("AI news requests must originate from deterministic strategy output")
        if not self.deterministic_shortlist_only:
            raise ValueError("AI news requests must be deterministic-shortlist only")
        return self


class ProviderNewsArticle(AIModel):
    provider: str
    provider_article_id: str | None = None
    symbol: str
    tickers: tuple[str, ...]
    title: str
    source: str
    canonical_url: str | None = None
    published_at: datetime
    summary: str | None = None
    body: str | None = None
    raw_provider_payload: dict[str, Any] | None = None
    raw_payload_hash: str | None = None
    source_quality: SourceQuality = "secondary_aggregation"

    @field_validator("symbol")
    @classmethod
    def validate_symbol(cls, symbol: str) -> str:
        if symbol != symbol.upper():
            raise ValueError("article symbol must be uppercase")
        return symbol

    @field_validator("tickers")
    @classmethod
    def validate_tickers(cls, tickers: tuple[str, ...]) -> tuple[str, ...]:
        if not tickers:
            raise ValueError("article must include ticker associations")
        if any(ticker != ticker.upper() for ticker in tickers):
            raise ValueError("article tickers must be uppercase")
        return tuple(dict.fromkeys(tickers))

    @model_validator(mode="after")
    def validate_article(self) -> Self:
        if self.symbol not in self.tickers:
            raise ValueError("primary symbol must be included in article tickers")
        if self.published_at.tzinfo is None:
            raise ValueError("published_at must be timezone-aware")
        if self.canonical_url is not None and not self.canonical_url.lower().startswith(
            ("http://", "https://")
        ):
            raise ValueError("canonical_url must be http(s)")
        return self


class NormalizedNewsArticle(AIModel):
    provider: str
    provider_article_id: str | None = None
    symbol: str
    tickers: tuple[str, ...]
    title: str
    normalized_title: str
    source: str
    normalized_source: str
    canonical_url: str | None = None
    normalized_canonical_url: str | None = None
    published_at: datetime
    content: str | None = None
    raw_payload_hash: str | None = None
    source_quality: SourceQuality

    @model_validator(mode="after")
    def validate_normalized_article(self) -> Self:
        if self.symbol != self.symbol.upper():
            raise ValueError("article symbol must be uppercase")
        if any(ticker != ticker.upper() for ticker in self.tickers):
            raise ValueError("article tickers must be uppercase")
        if self.symbol not in self.tickers:
            raise ValueError("primary symbol must be included in article tickers")
        if self.published_at.tzinfo is None:
            raise ValueError("published_at must be timezone-aware")
        return self

    @property
    def dedupe_key(self) -> str:
        if self.normalized_canonical_url:
            return f"url:{self.normalized_canonical_url}"
        if self.provider_article_id:
            return f"provider:{self.provider}:{self.provider_article_id}"
        published_day = self.published_at.date().isoformat()
        return f"title:{self.normalized_title}:{self.normalized_source}:{published_day}"


class AICitation(AIModel):
    citation_id: str
    title: str
    source: str
    canonical_url: str
    published_at: datetime
    provider: str
    raw_payload_hash: str | None = None

    @model_validator(mode="after")
    def validate_citation(self) -> Self:
        if self.published_at.tzinfo is None:
            raise ValueError("published_at must be timezone-aware")
        if not self.canonical_url.startswith(("http://", "https://")):
            raise ValueError("citation canonical_url must be http(s)")
        return self


class AIEvent(AIModel):
    event_id: str
    event_type: EventType
    direction: EventDirection
    confidence: float = Field(ge=0, le=1)
    risk_level: EventRiskLevel
    source_quality: SourceQuality
    published_at: datetime
    citation_ids: tuple[str, ...]
    summary: str
    blocking_risk: bool = False

    @model_validator(mode="after")
    def validate_event(self) -> Self:
        if self.published_at.tzinfo is None:
            raise ValueError("published_at must be timezone-aware")
        if not self.citation_ids:
            raise ValueError("events must include citation IDs")
        return self


class AITradeResearchOutput(AIModel):
    symbol: str
    analysis_at: datetime
    schema_version: str
    prompt_version: str
    model_version: str
    news_state: NewsState
    events: tuple[AIEvent, ...] = ()
    citations: tuple[AICitation, ...] = ()
    hard_block: bool
    hard_block_reason: str | None = None
    ai_score: int = Field(ge=10, le=90)
    size_multiplier: float = Field(ge=0, le=1)
    explanation: str
    fallback: bool = False
    fallback_reason: FallbackReason = "none"

    @field_validator("symbol")
    @classmethod
    def validate_symbol(cls, symbol: str) -> str:
        if symbol != symbol.upper():
            raise ValueError("AI research symbol must be uppercase")
        return symbol

    @model_validator(mode="after")
    def validate_research_output(self) -> Self:
        if self.analysis_at.tzinfo is None:
            raise ValueError("analysis_at must be timezone-aware")
        if self.hard_block and not self.hard_block_reason:
            raise ValueError("hard_block=true requires hard_block_reason")
        if not self.hard_block and self.hard_block_reason:
            raise ValueError("hard_block_reason requires hard_block=true")
        if self.fallback and self.fallback_reason == "none":
            raise ValueError("fallback=true requires fallback_reason")
        if not self.fallback and self.fallback_reason != "none":
            raise ValueError("fallback_reason requires fallback=true")
        citation_ids = {citation.citation_id for citation in self.citations}
        if len(citation_ids) != len(self.citations):
            raise ValueError("citation IDs must be unique")
        missing_citations = [
            citation_id
            for event in self.events
            for citation_id in event.citation_ids
            if citation_id not in citation_ids
        ]
        if missing_citations:
            raise ValueError(f"event citation IDs are missing: {missing_citations}")
        if self.news_state == "found" and not self.events:
            raise ValueError("news_state=found requires at least one event")
        return self


class AIProviderFailure(AIModel):
    symbol: str
    occurred_at: datetime
    provider: str
    reason: FallbackReason
    message: str
    incident_severity: Literal["warning"] = "warning"
    trigger_global_kill_switch: bool = False

    @model_validator(mode="after")
    def validate_failure(self) -> Self:
        if self.symbol != self.symbol.upper():
            raise ValueError("failure symbol must be uppercase")
        if self.occurred_at.tzinfo is None:
            raise ValueError("occurred_at must be timezone-aware")
        return self
