from __future__ import annotations

import inspect
import json
from datetime import UTC, datetime, timedelta

from packages.ai import openai as openai_module
from packages.ai.budget import InMemoryRequestBudgetStore, RequestBudgetService
from packages.ai.models import AI_PROMPT_VERSION, AI_SCHEMA_VERSION, NormalizedNewsArticle
from packages.ai.openai import (
    DEFAULT_OPENAI_MODEL,
    FakeOpenAIClient,
    OpenAIModelConfig,
    OpenAIProviderError,
    analyze_symbol_news_with_openai,
    openai_ai_research_json_schema,
    validate_openai_model_availability,
)

AS_OF = datetime(2026, 5, 4, 14, 30, tzinfo=UTC)


def _article() -> NormalizedNewsArticle:
    return NormalizedNewsArticle(
        provider="marketaux",
        endpoint="https://api.marketaux.com/v1/news/all",
        provider_article_id="article-1",
        symbol="AAPL",
        tickers=("AAPL",),
        title="AAPL announces contract",
        normalized_title="aapl announces contract",
        source="Example News",
        normalized_source="example news",
        canonical_url="https://example.com/aapl-contract",
        normalized_canonical_url="https://example.com/aapl-contract",
        published_at=AS_OF - timedelta(hours=2),
        content="Contract news summary",
        language="en",
        sentiment="positive",
        raw_payload_hash="hash-1",
        source_quality="premier_financial_publisher",
    )


def _valid_output(*, event_type: str = "product_contract_management_change") -> str:
    published_at = (AS_OF - timedelta(hours=2)).isoformat()
    payload = {
        "symbol": "AAPL",
        "analysis_at": AS_OF.isoformat(),
        "schema_version": AI_SCHEMA_VERSION,
        "prompt_version": AI_PROMPT_VERSION,
        "model_version": DEFAULT_OPENAI_MODEL,
        "news_state": "found",
        "events": [
            {
                "event_id": "event-1",
                "event_type": event_type,
                "direction": "negative"
                if event_type == "lawsuit_sec_fda_halt_accounting_risk"
                else "positive",
                "confidence": 0.82,
                "risk_level": "blocking"
                if event_type == "lawsuit_sec_fda_halt_accounting_risk"
                else "low",
                "source_quality": "premier_financial_publisher",
                "published_at": published_at,
                "citation_ids": ["citation-1"],
                "summary": "Structured event summary.",
                "blocking_risk": event_type == "lawsuit_sec_fda_halt_accounting_risk",
            }
        ],
        "citations": [
            {
                "citation_id": "citation-1",
                "title": "AAPL announces contract",
                "source": "Example News",
                "canonical_url": "https://example.com/aapl-contract",
                "published_at": published_at,
                "provider": "marketaux",
                "raw_payload_hash": "hash-1",
            }
        ],
        "hard_block": False,
        "hard_block_reason": None,
        "ai_score": 54,
        "size_multiplier": 1.0,
        "explanation": "Structured analysis.",
        "fallback": False,
        "fallback_reason": "none",
    }
    return json.dumps(payload)


def test_openai_model_config_parsing_and_availability_validation() -> None:
    config = OpenAIModelConfig.from_env(
        {
            "AI_PROVIDER": "openai",
            "OPENAI_MODEL": "fixture-model",
            "OPENAI_ESCALATION_MODEL": "fixture-escalation",
            "OPENAI_FALLBACK_MODEL": "fixture-fallback",
            "AI_DAILY_REQUEST_LIMIT": "3",
            "AI_REQUIRE_STRUCTURED_OUTPUT": "true",
            "AI_NEUTRAL_FALLBACK_ON_ERROR": "true",
        }
    )
    available = validate_openai_model_availability(
        client=FakeOpenAIClient(model_ids=("fixture-model",)),
        model=config.model,
    )
    unavailable = validate_openai_model_availability(
        client=FakeOpenAIClient(model_ids=("other-model",)),
        model=config.model,
    )

    assert config.model == "fixture-model"
    assert available.available is True
    assert unavailable.available is False
    assert unavailable.sanitized_error == "configured_model_unavailable"


def test_structured_output_success_records_versions_and_hashes() -> None:
    client = FakeOpenAIClient(structured_output=_valid_output())
    result = analyze_symbol_news_with_openai(
        symbol="AAPL",
        articles=(_article(),),
        client=client,
        config=OpenAIModelConfig(),
        analysis_at=AS_OF,
    )

    assert result.output.fallback is False
    assert result.output.prompt_version == AI_PROMPT_VERSION
    assert result.output.schema_version == AI_SCHEMA_VERSION
    assert result.output.model_version == DEFAULT_OPENAI_MODEL
    assert result.raw_prompt_hash == result.persistence_payload.raw_prompt_hash
    assert result.raw_output_hash == result.persistence_payload.raw_output_hash
    assert result.external_calls_performed is True
    assert result.output.size_multiplier <= 1.0
    assert len(client.structured_requests) == 1


def test_openai_structured_schema_requires_all_top_level_fields() -> None:
    schema = openai_ai_research_json_schema()
    properties = schema["properties"]

    assert schema["additionalProperties"] is False
    assert set(schema["required"]) == set(properties)
    assert "default" not in json.dumps(schema)


def test_invalid_json_and_schema_violation_fall_back_to_neutral() -> None:
    invalid = analyze_symbol_news_with_openai(
        symbol="AAPL",
        articles=(_article(),),
        client=FakeOpenAIClient(structured_output="{not-json"),
        config=OpenAIModelConfig(),
        analysis_at=AS_OF,
    )
    schema_payload = json.loads(_valid_output())
    schema_payload["size_multiplier"] = 1.5
    schema_violation = analyze_symbol_news_with_openai(
        symbol="AAPL",
        articles=(_article(),),
        client=FakeOpenAIClient(structured_output=json.dumps(schema_payload)),
        config=OpenAIModelConfig(),
        analysis_at=AS_OF,
    )

    assert invalid.output.fallback is True
    assert invalid.output.fallback_reason == "invalid_json"
    assert schema_violation.output.fallback is True
    assert schema_violation.output.fallback_reason == "schema_violation"
    assert schema_violation.output.size_multiplier <= 1.0


def test_no_news_provider_outage_and_budget_exceeded_are_neutral_fallbacks() -> None:
    no_news = analyze_symbol_news_with_openai(
        symbol="AAPL",
        articles=(),
        client=FakeOpenAIClient(structured_output=_valid_output()),
        config=OpenAIModelConfig(),
        analysis_at=AS_OF,
    )
    outage = analyze_symbol_news_with_openai(
        symbol="AAPL",
        articles=(_article(),),
        client=FakeOpenAIClient(error=OpenAIProviderError("timeout", "sanitized")),
        config=OpenAIModelConfig(),
        analysis_at=AS_OF,
    )
    budget_exceeded = analyze_symbol_news_with_openai(
        symbol="AAPL",
        articles=(_article(),),
        client=FakeOpenAIClient(structured_output=_valid_output()),
        config=OpenAIModelConfig(daily_request_limit=0),
        analysis_at=AS_OF,
        budget_service=RequestBudgetService(InMemoryRequestBudgetStore()),
    )

    assert no_news.output.fallback_reason == "no_news_found"
    assert no_news.external_calls_performed is False
    assert outage.output.fallback_reason == "ai_provider_outage"
    assert outage.external_calls_performed is True
    assert outage.provider_failure_code == "timeout"
    assert budget_exceeded.output.fallback_reason == "ai_provider_outage"
    assert budget_exceeded.external_calls_performed is False
    assert budget_exceeded.provider_failure_code == "daily_budget_exceeded"


def test_hard_block_threshold_is_applied_deterministically() -> None:
    result = analyze_symbol_news_with_openai(
        symbol="AAPL",
        articles=(_article(),),
        client=FakeOpenAIClient(
            structured_output=_valid_output(event_type="lawsuit_sec_fda_halt_accounting_risk")
        ),
        config=OpenAIModelConfig(),
        analysis_at=AS_OF,
    )

    assert result.output.hard_block is True
    assert result.output.size_multiplier == 0.0


def test_openai_ai_module_has_no_broker_or_execution_authority() -> None:
    source = inspect.getsource(openai_module)

    assert "ExecutionIntent" not in source
    assert "submit_order" not in source
    assert "cancel_order" not in source
    assert "packages.broker" not in source
