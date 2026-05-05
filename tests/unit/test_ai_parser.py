import json
from datetime import UTC, datetime, timedelta

from packages.ai.fallback import (
    conflicting_sources_fallback,
    no_news_fallback,
    provider_outage_fallback,
)
from packages.ai.models import AI_PROMPT_VERSION, AI_SCHEMA_VERSION, NEUTRAL_AI_SCORE
from packages.ai.parser import parse_ai_trade_research_json, parse_ai_trade_research_or_fallback
from packages.ai.prompts import load_prompt_template

AS_OF = datetime(2026, 5, 4, 14, 30, tzinfo=UTC)


def _valid_payload() -> dict[str, object]:
    published_at = (AS_OF - timedelta(hours=2)).isoformat()
    return {
        "symbol": "AAPL",
        "analysis_at": AS_OF.isoformat(),
        "schema_version": AI_SCHEMA_VERSION,
        "prompt_version": AI_PROMPT_VERSION,
        "model_version": "fixture-model",
        "news_state": "found",
        "events": [
            {
                "event_id": "event-1",
                "event_type": "product_contract_management_change",
                "direction": "positive",
                "confidence": 0.82,
                "risk_level": "low",
                "source_quality": "premier_financial_publisher",
                "published_at": published_at,
                "citation_ids": ["citation-1"],
                "summary": "AAPL announced a new contract.",
                "blocking_risk": False,
            }
        ],
        "citations": [
            {
                "citation_id": "citation-1",
                "title": "AAPL contract",
                "source": "Fixture News",
                "canonical_url": "https://example.com/aapl-contract",
                "published_at": published_at,
                "provider": "fixture",
                "raw_payload_hash": "hash-1",
            }
        ],
        "hard_block": False,
        "hard_block_reason": None,
        "ai_score": 54,
        "size_multiplier": 1.0,
        "explanation": "Positive contract catalyst.",
        "fallback": False,
        "fallback_reason": "none",
    }


def test_prompt_version_loading_includes_authority_boundaries() -> None:
    template = load_prompt_template(AI_PROMPT_VERSION)

    assert "strict JSON only" in template
    assert "cannot create orders" in template
    assert "deterministic shortlist" in template


def test_valid_ai_output_parses_with_strict_schema() -> None:
    output = parse_ai_trade_research_json(json.dumps(_valid_payload()))

    assert output.symbol == "AAPL"
    assert output.news_state == "found"
    assert output.events[0].citation_ids == ("citation-1",)
    assert output.fallback is False


def test_invalid_json_falls_back_to_neutral_output() -> None:
    output = parse_ai_trade_research_or_fallback(
        "{not-json",
        symbol="AAPL",
        analysis_at=AS_OF,
        prompt_version=AI_PROMPT_VERSION,
        schema_version=AI_SCHEMA_VERSION,
        model_version="fixture-model",
    )

    assert output.fallback is True
    assert output.fallback_reason == "invalid_json"
    assert output.ai_score == NEUTRAL_AI_SCORE
    assert output.hard_block is False


def test_schema_violation_falls_back_to_neutral_output() -> None:
    payload = _valid_payload()
    payload["ai_score"] = 101

    output = parse_ai_trade_research_or_fallback(
        json.dumps(payload),
        symbol="AAPL",
        analysis_at=AS_OF,
        prompt_version=AI_PROMPT_VERSION,
        schema_version=AI_SCHEMA_VERSION,
        model_version="fixture-model",
    )

    assert output.fallback is True
    assert output.fallback_reason == "schema_violation"
    assert output.ai_score == NEUTRAL_AI_SCORE
    assert output.hard_block is False


def test_missing_news_provider_outage_and_conflicting_sources_fallbacks() -> None:
    missing = no_news_fallback(
        symbol="AAPL",
        analysis_at=AS_OF,
        prompt_version=AI_PROMPT_VERSION,
        schema_version=AI_SCHEMA_VERSION,
        model_version="fixture-model",
    )
    outage, failure = provider_outage_fallback(
        symbol="AAPL",
        analysis_at=AS_OF,
        prompt_version=AI_PROMPT_VERSION,
        schema_version=AI_SCHEMA_VERSION,
        model_version="fixture-model",
        provider="fixture-ai",
        message="timeout",
    )
    mixed = conflicting_sources_fallback(
        symbol="AAPL",
        analysis_at=AS_OF,
        prompt_version=AI_PROMPT_VERSION,
        schema_version=AI_SCHEMA_VERSION,
        model_version="fixture-model",
    )

    assert missing.news_state == "insufficient_data"
    assert missing.ai_score == NEUTRAL_AI_SCORE
    assert outage.news_state == "provider_error"
    assert failure.trigger_global_kill_switch is False
    assert mixed.news_state == "mixed"
    assert mixed.size_multiplier <= 0.75
    assert mixed.hard_block is False
