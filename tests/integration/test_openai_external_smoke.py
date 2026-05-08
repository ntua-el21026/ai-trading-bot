from __future__ import annotations

import os
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta

import pytest

from packages.ai.budget import InMemoryRequestBudgetStore, RequestBudgetService
from packages.ai.models import NormalizedNewsArticle
from packages.ai.openai import (
    OpenAIHttpClient,
    OpenAIModelConfig,
    WebFallbackPolicy,
    analyze_symbol_news_with_openai,
    decide_web_fallback,
    run_openai_web_fallback,
    validate_openai_model_availability,
)


@pytest.mark.integration
def test_openai_model_list_smoke() -> None:
    missing = _missing_exact_gates(
        os.environ,
        {
            "RUN_OPENAI_MODEL_LIST_SMOKE": "1",
            "OPENAI_MODEL_LIST_CONFIRM": "LIST_AVAILABLE_MODELS_ONLY",
        },
        required_secret_names=("OPENAI_API_KEY",),
    )
    if missing:
        pytest.skip(f"OpenAI model-list smoke gates not satisfied: {missing}")

    config = OpenAIModelConfig.from_env()
    client = OpenAIHttpClient(api_key=os.environ["OPENAI_API_KEY"])
    result = validate_openai_model_availability(client=client, model=config.model)

    assert result.checked is True
    assert result.sanitized_error in {None, "configured_model_unavailable"}
    assert "OPENAI_API_KEY" not in result.model_dump_json()
    if not result.available:
        pytest.fail(f"configured OpenAI model unavailable: {result.sanitized_error}", pytrace=False)


@pytest.mark.integration
def test_openai_structured_analysis_smoke() -> None:
    missing = _missing_exact_gates(
        os.environ,
        {
            "RUN_OPENAI_AI_SMOKE": "1",
            "OPENAI_AI_SMOKE_CONFIRM": "STRUCTURED_OUTPUT_SHORTLIST_NEWS_ONLY",
        },
        required_secret_names=("OPENAI_API_KEY",),
    )
    if missing:
        pytest.skip(f"OpenAI structured-analysis smoke gates not satisfied: {missing}")

    analysis_at = datetime.now(UTC)
    result = analyze_symbol_news_with_openai(
        symbol="SPY",
        articles=(_article(analysis_at),),
        client=OpenAIHttpClient(api_key=os.environ["OPENAI_API_KEY"]),
        config=OpenAIModelConfig.from_env(),
        analysis_at=analysis_at,
        budget_service=RequestBudgetService(InMemoryRequestBudgetStore()),
    )
    serialized = result.model_dump_json()

    assert result.external_calls_performed is True
    assert result.provider_failure_code is None
    assert result.output.symbol == "SPY"
    assert result.output.fallback is False
    assert result.output.size_multiplier <= 1.0
    assert "OPENAI_API_KEY" not in serialized


@pytest.mark.integration
def test_openai_web_fallback_smoke() -> None:
    missing = _missing_exact_gates(
        os.environ,
        {
            "RUN_OPENAI_WEB_FALLBACK_SMOKE": "1",
            "OPENAI_WEB_FALLBACK_CONFIRM": "AUDITED_EXCEPTION_ONLY_WEB_SEARCH",
            "NEWS_ENABLE_OPENAI_WEB_FALLBACK": "true",
        },
        required_secret_names=("OPENAI_API_KEY",),
    )
    if missing:
        pytest.skip(f"OpenAI web-fallback smoke gates not satisfied: {missing}")

    config = OpenAIModelConfig.from_env()
    result = run_openai_web_fallback(
        client=OpenAIHttpClient(api_key=os.environ["OPENAI_API_KEY"]),
        model=config.model,
        policy=WebFallbackPolicy(
            enabled=True,
            runtime_policy_allowed=True,
            daily_request_limit=int(os.environ.get("NEWS_OPENAI_WEB_DAILY_REQUEST_LIMIT", "5")),
        ),
        budget_service=RequestBudgetService(InMemoryRequestBudgetStore()),
        as_of=datetime.now(UTC),
        prompt="Find audited exception-only recent news context for SPY. Return a concise summary.",
        decision=decide_web_fallback(provider_articles=()),
    )
    serialized = result.model_dump_json()

    assert result.external_calls_performed is True
    assert result.sanitized_error is None
    assert result.raw_output_hash is not None
    assert "OPENAI_API_KEY" not in serialized


def _article(analysis_at: datetime) -> NormalizedNewsArticle:
    return NormalizedNewsArticle(
        provider="marketaux",
        endpoint="https://api.marketaux.com/v1/news/all",
        provider_article_id="smoke-article-1",
        symbol="SPY",
        tickers=("SPY",),
        title="SPY market context",
        normalized_title="spy market context",
        source="Smoke Fixture",
        normalized_source="smoke fixture",
        canonical_url="https://example.com/spy-context",
        normalized_canonical_url="https://example.com/spy-context",
        published_at=analysis_at - timedelta(hours=1),
        content="SPY has routine market context in this smoke fixture.",
        raw_payload_hash="smoke-provider-hash",
        source_quality="secondary_aggregation",
    )


def _missing_exact_gates(
    environ: Mapping[str, str],
    required: Mapping[str, str],
    *,
    required_secret_names: tuple[str, ...],
) -> list[str]:
    missing = [name for name, expected in required.items() if environ.get(name) != expected]
    for secret_name in required_secret_names:
        if not environ.get(secret_name):
            missing.append(secret_name)
    return missing
