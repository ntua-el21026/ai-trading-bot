"""Provider interfaces for offline-safe market data access."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import date
from typing import Protocol

from packages.data.models import AdjustedDailyBar, AssetMetadata, QuoteSnapshot


class MarketDataProvider(Protocol):
    """Market data provider boundary.

    Milestone 02 defines the contract only. Implementations must not make live
    network calls unless a later milestone explicitly adds a configured adapter.
    """

    def adjusted_daily_bars(
        self,
        symbol: str,
        start: date,
        end: date,
    ) -> Sequence[AdjustedDailyBar]:
        """Return adjusted daily bars for a symbol and inclusive date range."""

    def latest_quotes(self, symbols: Sequence[str]) -> Sequence[QuoteSnapshot]:
        """Return latest quote snapshots for symbols."""

    def asset_metadata(self, symbols: Sequence[str]) -> Sequence[AssetMetadata]:
        """Return asset reference metadata for symbols."""


class HistoricalDataProvider(Protocol):
    def adjusted_daily_bars_bulk(
        self,
        symbols: Sequence[str],
        start: date,
        end: date,
    ) -> Mapping[str, Sequence[AdjustedDailyBar]]:
        """Return adjusted daily bars keyed by symbol."""
