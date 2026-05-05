"""Deterministic article normalization and deduplication."""

from __future__ import annotations

import re
from collections.abc import Iterable
from urllib.parse import urlsplit, urlunsplit

from packages.ai.models import NormalizedNewsArticle, ProviderNewsArticle

_WHITESPACE_RE = re.compile(r"\s+")


def normalize_article(article: ProviderNewsArticle) -> NormalizedNewsArticle:
    content = article.summary or article.body
    return NormalizedNewsArticle(
        provider=article.provider,
        provider_article_id=article.provider_article_id,
        symbol=article.symbol,
        tickers=article.tickers,
        title=article.title.strip(),
        normalized_title=normalize_text(article.title),
        source=article.source.strip(),
        normalized_source=normalize_text(article.source),
        canonical_url=article.canonical_url,
        normalized_canonical_url=normalize_url(article.canonical_url),
        published_at=article.published_at,
        content=content.strip() if content else None,
        raw_payload_hash=article.raw_payload_hash,
        source_quality=article.source_quality,
    )


def normalize_articles(
    articles: Iterable[ProviderNewsArticle],
) -> tuple[NormalizedNewsArticle, ...]:
    return tuple(normalize_article(article) for article in articles)


def dedupe_articles(
    articles: Iterable[NormalizedNewsArticle],
) -> tuple[NormalizedNewsArticle, ...]:
    seen: set[str] = set()
    deduped: list[NormalizedNewsArticle] = []
    for article in articles:
        if article.dedupe_key in seen:
            continue
        seen.add(article.dedupe_key)
        deduped.append(article)
    return tuple(deduped)


def normalize_text(value: str) -> str:
    return _WHITESPACE_RE.sub(" ", value.strip().lower())


def normalize_url(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    if not stripped:
        return None
    parts = urlsplit(stripped)
    scheme = parts.scheme.lower()
    netloc = parts.netloc.lower()
    path = parts.path.rstrip("/")
    return urlunsplit((scheme, netloc, path, "", ""))
