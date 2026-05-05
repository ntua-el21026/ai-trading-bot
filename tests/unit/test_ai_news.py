from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

import packages.ai as ai_package
from packages.ai.dedupe import dedupe_articles, normalize_article
from packages.ai.models import DeterministicShortlistNewsRequest, ProviderNewsArticle
from packages.ai.news import FixtureCandidateNewsProvider

AS_OF = datetime(2026, 5, 4, 14, 30, tzinfo=UTC)


def _article(
    *,
    article_id: str | None = "article-1",
    title: str = "  AAPL launches new contract  ",
    canonical_url: str | None = "HTTPS://Example.com/news/AAPL?utm_source=x",
) -> ProviderNewsArticle:
    return ProviderNewsArticle(
        provider="fixture",
        provider_article_id=article_id,
        symbol="AAPL",
        tickers=("AAPL",),
        title=title,
        source=" Example News ",
        canonical_url=canonical_url,
        published_at=AS_OF,
        summary="New contract summary",
        raw_payload_hash="abc123",
        source_quality="premier_financial_publisher",
    )


def test_article_model_requires_uppercase_ticker_and_aware_timestamp() -> None:
    with pytest.raises(ValidationError, match="uppercase"):
        ProviderNewsArticle(
            provider="fixture",
            symbol="aapl",
            tickers=("AAPL",),
            title="AAPL news",
            source="Fixture",
            published_at=AS_OF,
        )

    with pytest.raises(ValidationError, match="timezone-aware"):
        ProviderNewsArticle(
            provider="fixture",
            symbol="AAPL",
            tickers=("AAPL",),
            title="AAPL news",
            source="Fixture",
            published_at=datetime(2026, 5, 4, 14, 30),
        )


def test_article_normalization_and_deduplication() -> None:
    first = normalize_article(_article())
    duplicate_url = normalize_article(
        _article(article_id="article-2", title="AAPL launches new contract")
    )
    duplicate_title = normalize_article(
        _article(article_id=None, canonical_url=None, title="AAPL   launches NEW contract")
    )
    duplicate_title_without_id = normalize_article(
        _article(article_id=None, canonical_url=None, title="aapl launches new contract")
    )
    unique = normalize_article(
        _article(
            article_id="article-3",
            title="Different catalyst",
            canonical_url="https://example.com/news/different-catalyst",
        )
    )

    deduped = dedupe_articles(
        (first, duplicate_url, duplicate_title, duplicate_title_without_id, unique)
    )

    assert first.normalized_title == "aapl launches new contract"
    assert first.normalized_canonical_url == "https://example.com/news/AAPL"
    assert len(deduped) == 3
    assert deduped[0] == first
    assert unique in deduped


def test_news_request_and_fixture_provider_are_shortlist_only() -> None:
    with pytest.raises(ValidationError, match="deterministic-shortlist only"):
        DeterministicShortlistNewsRequest(
            symbols=("AAPL",),
            deterministic_shortlist_only=False,
            lookback_calendar_days=7,
            max_articles_per_symbol=12,
        )

    request = DeterministicShortlistNewsRequest(
        symbols=("AAPL", "AAPL", "MSFT"),
        lookback_calendar_days=7,
        max_articles_per_symbol=1,
    )
    provider = FixtureCandidateNewsProvider(
        {"AAPL": (_article(), _article(article_id="article-2"))}
    )

    result = provider.fetch_candidate_news(request)

    assert request.symbols == ("AAPL", "MSFT")
    assert len(result["AAPL"]) == 1
    assert result["MSFT"] == ()


def test_ai_package_does_not_import_broker_boundaries() -> None:
    ai_root = Path(ai_package.__file__).parent
    source = "\n".join(path.read_text(encoding="utf-8") for path in ai_root.glob("*.py"))

    assert "packages.broker" not in source
