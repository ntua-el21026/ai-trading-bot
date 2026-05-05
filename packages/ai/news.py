"""News provider boundaries for deterministic shortlist candidates only."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Protocol

from packages.ai.models import DeterministicShortlistNewsRequest, ProviderNewsArticle


class NewsProviderUnavailable(RuntimeError):
    """Raised by provider implementations when fixture/live data is unavailable."""


class CandidateNewsProvider(Protocol):
    """Ticker-tagged news boundary for deterministic shortlist symbols.

    Implementations must not scan the full universe. Live provider clients are intentionally
    deferred; tests use fixture providers only.
    """

    provider_name: str

    def fetch_candidate_news(
        self,
        request: DeterministicShortlistNewsRequest,
    ) -> Mapping[str, Sequence[ProviderNewsArticle]]:
        """Return ticker-tagged articles keyed by deterministic shortlist symbol."""


class FixtureCandidateNewsProvider:
    """In-memory provider for tests and local contracts."""

    provider_name = "fixture"

    def __init__(
        self,
        articles_by_symbol: Mapping[str, Sequence[ProviderNewsArticle]],
    ) -> None:
        self._articles_by_symbol = {
            symbol: tuple(articles) for symbol, articles in articles_by_symbol.items()
        }

    def fetch_candidate_news(
        self,
        request: DeterministicShortlistNewsRequest,
    ) -> Mapping[str, Sequence[ProviderNewsArticle]]:
        return {
            symbol: tuple(self._articles_by_symbol.get(symbol, ()))[
                : request.max_articles_per_symbol
            ]
            for symbol in request.symbols
        }
