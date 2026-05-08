from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from packages.ai.budget import InMemoryRequestBudgetStore, RequestBudgetService
from packages.ai.models import DeterministicShortlistNewsRequest, ProviderNewsArticle
from packages.ai.providers import (
    ALPHA_VANTAGE_ENDPOINT,
    ALPHA_VANTAGE_PROVIDER,
    MARKETAUX_ENDPOINT,
    MARKETAUX_PROVIDER,
    FixtureNewsProviderClient,
    NewsProviderConfig,
    ProviderFirstNewsService,
    _parse_alpha_vantage_payload,
    _parse_marketaux_payload,
)

AS_OF = datetime(2026, 5, 4, 14, 30, tzinfo=UTC)


def _article(
    *,
    provider: str = MARKETAUX_PROVIDER,
    endpoint: str = MARKETAUX_ENDPOINT,
    article_id: str = "article-1",
    symbol: str = "AAPL",
    title: str = "AAPL signs new contract",
    canonical_url: str = "https://example.com/aapl-contract",
) -> ProviderNewsArticle:
    return ProviderNewsArticle(
        provider=provider,
        endpoint=endpoint,
        provider_article_id=article_id,
        symbol=symbol,
        tickers=(symbol,),
        title=title,
        source="Example News",
        canonical_url=canonical_url,
        published_at=AS_OF,
        summary="Contract summary",
        raw_payload_hash=f"hash-{article_id}",
    )


def _service(
    *,
    config: NewsProviderConfig | None = None,
    primary_articles: tuple[ProviderNewsArticle, ...] = (),
    fallback_articles: tuple[ProviderNewsArticle, ...] = (),
    primary_failures: dict[str, str] | None = None,
    budget_service: RequestBudgetService | None = None,
    cross_check_on_primary_hit: bool = False,
) -> ProviderFirstNewsService:
    return ProviderFirstNewsService(
        config=config or NewsProviderConfig(),
        budget_service=budget_service,
        provider_clients={
            MARKETAUX_PROVIDER: FixtureNewsProviderClient(
                provider_name=MARKETAUX_PROVIDER,
                endpoint=MARKETAUX_ENDPOINT,
                articles_by_symbol={"AAPL": primary_articles},
                failure_symbols=primary_failures,
            ),
            ALPHA_VANTAGE_PROVIDER: FixtureNewsProviderClient(
                provider_name=ALPHA_VANTAGE_PROVIDER,
                endpoint=ALPHA_VANTAGE_ENDPOINT,
                articles_by_symbol={"AAPL": fallback_articles},
            ),
        },
        cross_check_on_primary_hit=cross_check_on_primary_hit,
    )


def _request(
    *,
    symbols: tuple[str, ...] = ("AAPL",),
    max_articles: int = 3,
) -> DeterministicShortlistNewsRequest:
    return DeterministicShortlistNewsRequest(
        symbols=symbols,
        lookback_calendar_days=7,
        max_articles_per_symbol=max_articles,
    )


def test_marketaux_response_normalization_preserves_required_fields() -> None:
    articles = _parse_marketaux_payload(
        "AAPL",
        {
            "data": [
                {
                    "uuid": "m-1",
                    "title": "AAPL announces product contract",
                    "source": {"name": "Marketaux Source"},
                    "url": "https://example.com/aapl",
                    "published_at": AS_OF.isoformat(),
                    "description": "AAPL contract details",
                    "language": "en",
                    "entities": [{"symbol": "AAPL", "sentiment_score": "0.42"}],
                }
            ]
        },
    )

    article = articles[0]
    assert article.provider == MARKETAUX_PROVIDER
    assert article.endpoint == MARKETAUX_ENDPOINT
    assert article.symbol == "AAPL"
    assert article.language == "en"
    assert article.sentiment == "0.42"
    assert article.raw_payload_hash is not None


def test_alpha_vantage_response_normalization_preserves_required_fields() -> None:
    articles = _parse_alpha_vantage_payload(
        "AAPL",
        {
            "feed": [
                {
                    "title": "AAPL earnings guidance",
                    "source": "Alpha Source",
                    "url": "https://example.com/aapl-guidance",
                    "time_published": "20260504T143000",
                    "summary": "Guidance summary",
                    "overall_sentiment_label": "Bullish",
                    "ticker_sentiment": [{"ticker": "AAPL"}],
                }
            ]
        },
    )

    article = articles[0]
    assert article.provider == ALPHA_VANTAGE_PROVIDER
    assert article.endpoint == ALPHA_VANTAGE_ENDPOINT
    assert article.symbol == "AAPL"
    assert article.sentiment == "Bullish"
    assert article.raw_payload_hash is not None


def test_provider_deduplication_and_per_symbol_article_cap() -> None:
    duplicate = _article(
        provider=ALPHA_VANTAGE_PROVIDER,
        endpoint=ALPHA_VANTAGE_ENDPOINT,
        article_id="fallback-1",
    )
    service = _service(
        primary_articles=(_article(),),
        fallback_articles=(duplicate,),
        cross_check_on_primary_hit=True,
    )

    result = service.fetch_shortlist_news(_request(max_articles=1), as_of=AS_OF)

    assert len(result.articles_by_symbol["AAPL"]) == 1
    assert result.articles_by_symbol["AAPL"][0].provider == MARKETAUX_PROVIDER
    assert result.full_universe_scanned is False
    assert result.external_calls_performed is False


def test_no_news_and_provider_outage_use_structured_fallback_path() -> None:
    no_news = _service().fetch_shortlist_news(_request(), as_of=AS_OF)
    assert no_news.articles_by_symbol["AAPL"] == ()
    assert no_news.provider_coverage_rate == 0.0

    outage = _service(
        primary_failures={"AAPL": "timeout"},
        fallback_articles=(
            _article(provider=ALPHA_VANTAGE_PROVIDER, endpoint=ALPHA_VANTAGE_ENDPOINT),
        ),
    ).fetch_shortlist_news(_request(), as_of=AS_OF)
    assert outage.provider_failures[0].reason == "provider_error"
    assert len(outage.articles_by_symbol["AAPL"]) == 1


def test_malformed_provider_payload_is_structured_failure() -> None:
    with pytest.raises(ValueError, match="Marketaux payload data must be a list"):
        _parse_marketaux_payload("AAPL", {"data": "not-a-list"})

    with pytest.raises(ValueError, match="Alpha Vantage payload feed must be a list"):
        _parse_alpha_vantage_payload("AAPL", {"feed": "not-a-list"})


def test_provider_budget_allowed_and_exceeded() -> None:
    config = NewsProviderConfig(
        marketaux_daily_request_limit=1,
        alpha_vantage_daily_request_limit=0,
    )
    service = _service(
        config=config,
        primary_articles=(_article(),),
        budget_service=RequestBudgetService(InMemoryRequestBudgetStore()),
    )

    result = service.fetch_shortlist_news(
        _request(symbols=("AAPL", "MSFT")),
        as_of=AS_OF,
    )

    assert result.budget_events[0].allowed is True
    assert any(event.allowed is False for event in result.budget_events)
    assert any(failure.reason == "daily_budget_exceeded" for failure in result.provider_failures)


def test_provider_caps_and_shortlist_only_are_enforced() -> None:
    service = _service(config=NewsProviderConfig(max_symbols_per_run=1, max_articles_per_symbol=1))

    with pytest.raises(ValueError, match="max symbols"):
        service.fetch_shortlist_news(
            _request(symbols=("AAPL", "MSFT"), max_articles=1),
            as_of=AS_OF,
        )

    with pytest.raises(ValueError, match="max articles"):
        service.fetch_shortlist_news(_request(symbols=("AAPL",), max_articles=2), as_of=AS_OF)

    with pytest.raises(ValidationError, match="deterministic-shortlist only"):
        DeterministicShortlistNewsRequest(
            symbols=("AAPL",),
            deterministic_shortlist_only=False,
            lookback_calendar_days=7,
            max_articles_per_symbol=1,
        )
