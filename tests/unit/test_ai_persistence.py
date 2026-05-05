from datetime import UTC, datetime, timedelta

from packages.ai.models import (
    AI_PROMPT_VERSION,
    AI_SCHEMA_VERSION,
    AICitation,
    AIEvent,
    AITradeResearchOutput,
)
from packages.ai.persistence import build_ai_research_persistence_payload
from packages.data.payloads import hash_payload

AS_OF = datetime(2026, 5, 4, 14, 30, tzinfo=UTC)


def _research_output() -> AITradeResearchOutput:
    citation = AICitation(
        citation_id="citation-1",
        title="AAPL contract",
        source="Fixture News",
        canonical_url="https://example.com/aapl-contract",
        published_at=AS_OF - timedelta(hours=1),
        provider="fixture",
    )
    event = AIEvent(
        event_id="event-1",
        event_type="product_contract_management_change",
        direction="positive",
        confidence=0.80,
        risk_level="low",
        source_quality="premier_financial_publisher",
        published_at=AS_OF - timedelta(hours=1),
        citation_ids=("citation-1",),
        summary="AAPL announced a contract.",
    )
    return AITradeResearchOutput(
        symbol="AAPL",
        analysis_at=AS_OF,
        schema_version=AI_SCHEMA_VERSION,
        prompt_version=AI_PROMPT_VERSION,
        model_version="fixture-model",
        news_state="found",
        events=(event,),
        citations=(citation,),
        hard_block=False,
        hard_block_reason=None,
        ai_score=54,
        size_multiplier=1.0,
        explanation="Positive contract catalyst.",
    )


def test_ai_research_persistence_payload_hashes_are_stable() -> None:
    raw_prompt = "Prompt for AAPL"
    raw_output = '{"symbol":"AAPL"}'
    parsed = _research_output()

    first = build_ai_research_persistence_payload(
        symbol="AAPL",
        created_at=AS_OF,
        raw_prompt=raw_prompt,
        raw_ai_output=raw_output,
        parsed_output=parsed,
    )
    second = build_ai_research_persistence_payload(
        symbol="AAPL",
        created_at=AS_OF,
        raw_prompt=raw_prompt,
        raw_ai_output=raw_output,
        parsed_output=parsed,
    )

    assert first.raw_prompt_hash == hash_payload(raw_prompt)
    assert first.raw_output_hash == hash_payload(raw_output)
    assert first.raw_prompt_hash == second.raw_prompt_hash
    assert first.raw_output_hash == second.raw_output_hash
    assert first.canonical_urls == ("https://example.com/aapl-contract",)
    assert first.fallback_reason == "none"
