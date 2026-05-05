"""Persistence payload contracts for future AI research storage."""

from __future__ import annotations

from datetime import datetime
from typing import Self

from pydantic import Field, model_validator

from packages.ai.models import AIModel, AITradeResearchOutput, FallbackReason
from packages.data.payloads import hash_payload


class AIResearchPersistencePayload(AIModel):
    symbol: str
    created_at: datetime
    prompt_version: str
    schema_version: str
    model_version: str
    raw_prompt: str
    raw_ai_output: str | None
    parsed_output: AITradeResearchOutput
    citations: tuple[str, ...]
    canonical_urls: tuple[str, ...]
    raw_prompt_hash: str = Field(min_length=64, max_length=64)
    raw_output_hash: str | None = Field(default=None, min_length=64, max_length=64)
    fallback_reason: FallbackReason

    @model_validator(mode="after")
    def validate_payload(self) -> Self:
        if self.symbol != self.symbol.upper():
            raise ValueError("payload symbol must be uppercase")
        if self.created_at.tzinfo is None:
            raise ValueError("created_at must be timezone-aware")
        if self.raw_prompt_hash != hash_payload(self.raw_prompt):
            raise ValueError("raw_prompt_hash does not match raw_prompt")
        expected_output_hash = (
            None if self.raw_ai_output is None else hash_payload(self.raw_ai_output)
        )
        if self.raw_output_hash != expected_output_hash:
            raise ValueError("raw_output_hash does not match raw_ai_output")
        return self


def build_ai_research_persistence_payload(
    *,
    symbol: str,
    created_at: datetime,
    raw_prompt: str,
    raw_ai_output: str | None,
    parsed_output: AITradeResearchOutput,
) -> AIResearchPersistencePayload:
    return AIResearchPersistencePayload(
        symbol=symbol,
        created_at=created_at,
        prompt_version=parsed_output.prompt_version,
        schema_version=parsed_output.schema_version,
        model_version=parsed_output.model_version,
        raw_prompt=raw_prompt,
        raw_ai_output=raw_ai_output,
        parsed_output=parsed_output,
        citations=tuple(citation.citation_id for citation in parsed_output.citations),
        canonical_urls=tuple(citation.canonical_url for citation in parsed_output.citations),
        raw_prompt_hash=hash_payload(raw_prompt),
        raw_output_hash=None if raw_ai_output is None else hash_payload(raw_ai_output),
        fallback_reason=parsed_output.fallback_reason,
    )
