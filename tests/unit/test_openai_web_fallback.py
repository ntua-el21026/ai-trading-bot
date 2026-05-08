from __future__ import annotations

from datetime import UTC, datetime, timedelta

from packages.ai.budget import InMemoryRequestBudgetStore, RequestBudgetService
from packages.ai.models import NormalizedNewsArticle
from packages.ai.openai import (
    FakeOpenAIClient,
    WebFallbackPolicy,
    decide_web_fallback,
    run_openai_web_fallback,
)

AS_OF = datetime(2026, 5, 4, 14, 30, tzinfo=UTC)


def _article() -> NormalizedNewsArticle:
    return NormalizedNewsArticle(
        provider="marketaux",
        endpoint="https://api.marketaux.com/v1/news/all",
        provider_article_id="article-1",
        symbol="SPY",
        tickers=("SPY",),
        title="SPY news",
        normalized_title="spy news",
        source="Example News",
        normalized_source="example news",
        canonical_url="https://example.com/spy",
        normalized_canonical_url="https://example.com/spy",
        published_at=AS_OF - timedelta(hours=1),
        content="Provider context.",
        raw_payload_hash="hash-1",
        source_quality="secondary_aggregation",
    )


def test_web_fallback_is_disabled_by_default() -> None:
    decision = decide_web_fallback(provider_articles=())
    client = FakeOpenAIClient(web_output="web context", web_sources=("https://example.com/source",))

    result = run_openai_web_fallback(
        client=client,
        model="fixture-model",
        policy=WebFallbackPolicy(),
        budget_service=RequestBudgetService(InMemoryRequestBudgetStore()),
        as_of=AS_OF,
        prompt="Find audited context for SPY.",
        decision=decision,
    )

    assert decision.should_run is True
    assert result.decision.reason == "web_fallback_disabled"
    assert result.external_calls_performed is False
    assert client.web_requests == []


def test_web_fallback_requires_runtime_allow_and_budget() -> None:
    client = FakeOpenAIClient(web_output="sanitized web context")
    decision = decide_web_fallback(provider_articles=(), high_risk_context_incomplete=True)

    result = run_openai_web_fallback(
        client=client,
        model="fixture-model",
        policy=WebFallbackPolicy(enabled=True, runtime_policy_allowed=True, daily_request_limit=1),
        budget_service=RequestBudgetService(InMemoryRequestBudgetStore()),
        as_of=AS_OF,
        prompt="Exception-only web fallback prompt.",
        decision=decision,
    )

    assert result.external_calls_performed is True
    assert result.raw_output_hash is not None
    assert result.budget_decision is not None
    assert result.budget_decision.allowed is True
    assert len(client.web_requests) == 1


def test_web_fallback_budget_exceeded_refuses_before_call() -> None:
    client = FakeOpenAIClient(web_output="unused")
    result = run_openai_web_fallback(
        client=client,
        model="fixture-model",
        policy=WebFallbackPolicy(enabled=True, runtime_policy_allowed=True, daily_request_limit=0),
        budget_service=RequestBudgetService(InMemoryRequestBudgetStore()),
        as_of=AS_OF,
        prompt="Exception-only web fallback prompt.",
        decision=decide_web_fallback(provider_articles=()),
    )

    assert result.external_calls_performed is False
    assert result.sanitized_error == "daily_budget_exceeded"
    assert client.web_requests == []


def test_web_fallback_not_used_for_provider_covered_symbol() -> None:
    decision = decide_web_fallback(provider_articles=(_article(),))
    client = FakeOpenAIClient(web_output="unused")

    result = run_openai_web_fallback(
        client=client,
        model="fixture-model",
        policy=WebFallbackPolicy(enabled=True, runtime_policy_allowed=True, daily_request_limit=1),
        budget_service=RequestBudgetService(InMemoryRequestBudgetStore()),
        as_of=AS_OF,
        prompt="Should not run.",
        decision=decision,
    )

    assert decision.should_run is False
    assert decision.reason == "provider_context_sufficient"
    assert result.external_calls_performed is False
    assert client.web_requests == []
