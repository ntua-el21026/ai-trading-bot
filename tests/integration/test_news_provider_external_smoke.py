from __future__ import annotations

import os
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import cast

import pytest

from packages.ai.models import DeterministicShortlistNewsRequest
from packages.ai.providers import (
    ALPHA_VANTAGE_PROVIDER,
    MARKETAUX_PROVIDER,
    AlphaVantageNewsClient,
    MarketauxNewsClient,
    NewsProviderClient,
    NewsProviderConfig,
    ProviderFirstNewsService,
)


@pytest.mark.integration
def test_news_provider_shortlist_smoke() -> None:
    missing = _missing_provider_smoke_gates(os.environ)
    if missing:
        pytest.skip(f"news provider smoke gates not satisfied: {missing}")

    config = NewsProviderConfig.from_env()
    symbols = tuple(
        symbol.strip().upper()
        for symbol in os.environ.get("NEWS_PROVIDER_SMOKE_SYMBOLS", "SPY").split(",")
        if symbol.strip()
    )
    request = DeterministicShortlistNewsRequest(
        symbols=symbols[: config.max_symbols_per_run],
        lookback_calendar_days=config.default_lookback_days,
        max_articles_per_symbol=config.max_articles_per_symbol,
    )
    provider_clients: dict[str, NewsProviderClient] = {
        str(MARKETAUX_PROVIDER): cast(
            NewsProviderClient,
            MarketauxNewsClient(api_key=os.environ["MARKETAUX_API_KEY"]),
        ),
        str(ALPHA_VANTAGE_PROVIDER): cast(
            NewsProviderClient,
            AlphaVantageNewsClient(api_key=os.environ["ALPHA_VANTAGE_API_KEY"]),
        ),
    }
    service = ProviderFirstNewsService(
        config=config,
        provider_clients=provider_clients,
    )

    result = service.fetch_shortlist_news(request, as_of=datetime.now(UTC))
    serialized = result.model_dump_json()

    assert result.full_universe_scanned is False
    assert result.external_calls_performed is True
    assert "MARKETAUX_API_KEY" not in serialized
    assert "ALPHA_VANTAGE_API_KEY" not in serialized


def _missing_provider_smoke_gates(environ: Mapping[str, str]) -> list[str]:
    required = {
        "RUN_NEWS_PROVIDER_SMOKE": "1",
        "NEWS_PROVIDER_SMOKE_CONFIRM": "FETCH_SHORTLIST_NEWS_ONLY",
    }
    missing = [name for name, expected in required.items() if environ.get(name) != expected]
    for secret_name in ("MARKETAUX_API_KEY", "ALPHA_VANTAGE_API_KEY"):
        if not environ.get(secret_name):
            missing.append(secret_name)
    return missing
