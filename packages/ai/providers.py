"""Provider-first news retrieval for deterministic shortlist symbols."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime, timedelta
from typing import Any, Literal, Protocol, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from packages.ai.budget import RequestBudgetDecision, RequestBudgetService
from packages.ai.dedupe import dedupe_articles, normalize_articles
from packages.ai.models import (
    DeterministicShortlistNewsRequest,
    NormalizedNewsArticle,
    ProviderNewsArticle,
)
from packages.data.payloads import build_raw_provider_payload, hash_payload
from packages.ledger.repositories import RawProviderPayloadRepository

NewsProviderName = Literal["marketaux", "alpha_vantage"]

DEFAULT_NEWS_PROVIDER_PRIMARY: NewsProviderName = "marketaux"
DEFAULT_NEWS_PROVIDER_FALLBACK: NewsProviderName = "alpha_vantage"
MARKETAUX_PROVIDER: NewsProviderName = "marketaux"
ALPHA_VANTAGE_PROVIDER: NewsProviderName = "alpha_vantage"
MARKETAUX_ENDPOINT = "https://api.marketaux.com/v1/news/all"
ALPHA_VANTAGE_ENDPOINT = "https://www.alphavantage.co/query"


class NewsProviderModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class NewsProviderConfig(NewsProviderModel):
    primary_provider: NewsProviderName = DEFAULT_NEWS_PROVIDER_PRIMARY
    fallback_provider: NewsProviderName = DEFAULT_NEWS_PROVIDER_FALLBACK
    marketaux_daily_request_limit: int = Field(default=90, ge=0)
    alpha_vantage_daily_request_limit: int = Field(default=20, ge=0)
    max_symbols_per_run: int = Field(default=5, gt=0)
    max_articles_per_symbol: int = Field(default=3, gt=0)
    default_lookback_days: int = Field(default=7, gt=0)
    extended_lookback_days: int = Field(default=14, gt=0)
    enable_openai_web_fallback: bool = False
    openai_web_daily_request_limit: int = Field(default=5, ge=0)

    @model_validator(mode="after")
    def validate_provider_order(self) -> Self:
        if self.primary_provider == self.fallback_provider:
            raise ValueError("primary and fallback news providers must differ")
        if self.max_articles_per_symbol < 1:
            raise ValueError("max_articles_per_symbol must be positive")
        if self.extended_lookback_days < self.default_lookback_days:
            raise ValueError("extended lookback must be at least default lookback")
        return self

    @classmethod
    def from_env(cls, environ: Mapping[str, str] | None = None) -> NewsProviderConfig:
        source = os.environ if environ is None else environ
        return cls(
            primary_provider=_news_provider_name(
                _env(source, "NEWS_PROVIDER_PRIMARY", DEFAULT_NEWS_PROVIDER_PRIMARY)
            ),
            fallback_provider=_news_provider_name(
                _env(source, "NEWS_PROVIDER_FALLBACK", DEFAULT_NEWS_PROVIDER_FALLBACK)
            ),
            marketaux_daily_request_limit=_env_int(
                source,
                "NEWS_MARKETAUX_DAILY_REQUEST_LIMIT",
                90,
            ),
            alpha_vantage_daily_request_limit=_env_int(
                source,
                "NEWS_ALPHA_VANTAGE_DAILY_REQUEST_LIMIT",
                20,
            ),
            max_symbols_per_run=_env_int(source, "NEWS_MAX_SYMBOLS_PER_RUN", 5),
            max_articles_per_symbol=_env_int(source, "NEWS_MAX_ARTICLES_PER_SYMBOL", 3),
            default_lookback_days=_env_int(source, "NEWS_DEFAULT_LOOKBACK_DAYS", 7),
            extended_lookback_days=_env_int(source, "NEWS_EXTENDED_LOOKBACK_DAYS", 14),
            enable_openai_web_fallback=_env_bool(
                source,
                "NEWS_ENABLE_OPENAI_WEB_FALLBACK",
                False,
            ),
            openai_web_daily_request_limit=_env_int(
                source,
                "NEWS_OPENAI_WEB_DAILY_REQUEST_LIMIT",
                5,
            ),
        )

    def daily_limit_for(self, provider: str) -> int:
        if provider == MARKETAUX_PROVIDER:
            return self.marketaux_daily_request_limit
        if provider == ALPHA_VANTAGE_PROVIDER:
            return self.alpha_vantage_daily_request_limit
        raise ValueError(f"unsupported news provider: {provider}")


class ProviderFetchFailure(NewsProviderModel):
    provider: str
    symbol: str
    reason: str
    message: str
    fallback_allowed: bool = True


class ProviderFetchResult(NewsProviderModel):
    provider: str
    endpoint: str
    symbol: str
    raw_payload_hash: str | None = None
    articles: tuple[ProviderNewsArticle, ...] = ()
    failure: ProviderFetchFailure | None = None
    budget_decision: RequestBudgetDecision | None = None
    external_call_performed: bool = False


class ShortlistNewsResult(NewsProviderModel):
    requested_symbols: tuple[str, ...]
    articles_by_symbol: dict[str, tuple[NormalizedNewsArticle, ...]]
    provider_failures: tuple[ProviderFetchFailure, ...] = ()
    budget_events: tuple[RequestBudgetDecision, ...] = ()
    raw_payload_hashes: tuple[str, ...] = ()
    external_calls_performed: bool = False
    full_universe_scanned: bool = False

    @property
    def provider_coverage_rate(self) -> float:
        if not self.requested_symbols:
            return 0.0
        covered = sum(1 for symbol in self.requested_symbols if self.articles_by_symbol[symbol])
        return covered / len(self.requested_symbols)


class NewsProviderClient(Protocol):
    provider_name: str
    endpoint: str

    def fetch_symbol_news(
        self,
        *,
        symbol: str,
        lookback_days: int,
        max_articles: int,
        as_of: datetime,
    ) -> ProviderFetchResult:
        """Fetch provider news for one deterministic shortlist symbol."""


class FixtureNewsProviderClient:
    """In-memory provider client for tests and default offline behavior."""

    def __init__(
        self,
        *,
        provider_name: str,
        endpoint: str,
        articles_by_symbol: Mapping[str, Sequence[ProviderNewsArticle]] | None = None,
        failure_symbols: Mapping[str, str] | None = None,
    ) -> None:
        self.provider_name = provider_name
        self.endpoint = endpoint
        self._articles_by_symbol = {
            symbol: tuple(articles) for symbol, articles in (articles_by_symbol or {}).items()
        }
        self._failure_symbols = dict(failure_symbols or {})
        self.requested_symbols: list[str] = []

    def fetch_symbol_news(
        self,
        *,
        symbol: str,
        lookback_days: int,
        max_articles: int,
        as_of: datetime,
    ) -> ProviderFetchResult:
        del lookback_days, as_of
        self.requested_symbols.append(symbol)
        if symbol in self._failure_symbols:
            return ProviderFetchResult(
                provider=self.provider_name,
                endpoint=self.endpoint,
                symbol=symbol,
                failure=ProviderFetchFailure(
                    provider=self.provider_name,
                    symbol=symbol,
                    reason="provider_error",
                    message=self._failure_symbols[symbol],
                ),
            )
        articles = tuple(self._articles_by_symbol.get(symbol, ()))[:max_articles]
        return ProviderFetchResult(
            provider=self.provider_name,
            endpoint=self.endpoint,
            symbol=symbol,
            raw_payload_hash=hash_payload(
                [article.model_dump(mode="json") for article in articles]
            ),
            articles=articles,
        )


class MarketauxNewsClient:
    provider_name = MARKETAUX_PROVIDER
    endpoint = MARKETAUX_ENDPOINT

    def __init__(self, *, api_key: str, timeout_seconds: float = 10.0) -> None:
        self._api_key = api_key
        self._timeout_seconds = timeout_seconds

    def fetch_symbol_news(
        self,
        *,
        symbol: str,
        lookback_days: int,
        max_articles: int,
        as_of: datetime,
    ) -> ProviderFetchResult:
        params = {
            "api_token": self._api_key,
            "symbols": symbol,
            "filter_entities": "true",
            "language": "en",
            "published_after": (as_of - timedelta(days=lookback_days)).date().isoformat(),
            "limit": str(max_articles),
        }
        return _fetch_json_provider_result(
            provider=self.provider_name,
            endpoint=self.endpoint,
            symbol=symbol,
            url=f"{self.endpoint}?{urllib.parse.urlencode(params)}",
            timeout_seconds=self._timeout_seconds,
            parser=_parse_marketaux_payload,
        )


class AlphaVantageNewsClient:
    provider_name = ALPHA_VANTAGE_PROVIDER
    endpoint = ALPHA_VANTAGE_ENDPOINT

    def __init__(self, *, api_key: str, timeout_seconds: float = 10.0) -> None:
        self._api_key = api_key
        self._timeout_seconds = timeout_seconds

    def fetch_symbol_news(
        self,
        *,
        symbol: str,
        lookback_days: int,
        max_articles: int,
        as_of: datetime,
    ) -> ProviderFetchResult:
        time_from = as_of - timedelta(days=lookback_days)
        params = {
            "function": "NEWS_SENTIMENT",
            "tickers": symbol,
            "sort": "LATEST",
            "limit": str(max_articles),
            "time_from": time_from.strftime("%Y%m%dT%H%M"),
            "apikey": self._api_key,
        }
        return _fetch_json_provider_result(
            provider=self.provider_name,
            endpoint=self.endpoint,
            symbol=symbol,
            url=f"{self.endpoint}?{urllib.parse.urlencode(params)}",
            timeout_seconds=self._timeout_seconds,
            parser=_parse_alpha_vantage_payload,
        )


class ProviderFirstNewsService:
    """Fetch and normalize provider-first news for deterministic shortlist symbols."""

    def __init__(
        self,
        *,
        config: NewsProviderConfig,
        budget_service: RequestBudgetService | None = None,
        provider_clients: Mapping[str, NewsProviderClient],
        raw_payload_repository: RawProviderPayloadRepository | None = None,
        cross_check_on_primary_hit: bool = False,
    ) -> None:
        self._config = config
        self._budget_service = budget_service or RequestBudgetService()
        self._provider_clients = dict(provider_clients)
        self._raw_payload_repository = raw_payload_repository
        self._cross_check_on_primary_hit = cross_check_on_primary_hit
        self._run_cache: dict[tuple[str, str, int, int], ProviderFetchResult] = {}

    def fetch_shortlist_news(
        self,
        request: DeterministicShortlistNewsRequest,
        *,
        as_of: datetime,
        extended_lookback: bool = False,
    ) -> ShortlistNewsResult:
        if as_of.tzinfo is None:
            raise ValueError("as_of must be timezone-aware")
        if len(request.symbols) > self._config.max_symbols_per_run:
            raise ValueError("news request exceeds max symbols per run")
        if request.max_articles_per_symbol > self._config.max_articles_per_symbol:
            raise ValueError("news request exceeds max articles per symbol")
        lookback_days = (
            self._config.extended_lookback_days
            if extended_lookback
            else min(request.lookback_calendar_days, self._config.default_lookback_days)
        )
        failures: list[ProviderFetchFailure] = []
        budget_events: list[RequestBudgetDecision] = []
        raw_hashes: list[str] = []
        external_calls: list[bool] = []
        articles_by_symbol: dict[str, tuple[NormalizedNewsArticle, ...]] = {}

        for symbol in request.symbols:
            symbol_articles: list[ProviderNewsArticle] = []
            primary_result = self._fetch_provider_for_symbol(
                provider=self._config.primary_provider,
                symbol=symbol,
                lookback_days=lookback_days,
                max_articles=request.max_articles_per_symbol,
                as_of=as_of,
            )
            _collect_provider_result(primary_result, failures, budget_events, raw_hashes)
            external_calls.append(primary_result.external_call_performed)
            symbol_articles.extend(primary_result.articles)

            should_fetch_fallback = (
                primary_result.failure is not None
                or not primary_result.articles
                or self._cross_check_on_primary_hit
            )
            if should_fetch_fallback:
                fallback_result = self._fetch_provider_for_symbol(
                    provider=self._config.fallback_provider,
                    symbol=symbol,
                    lookback_days=lookback_days,
                    max_articles=request.max_articles_per_symbol,
                    as_of=as_of,
                )
                _collect_provider_result(fallback_result, failures, budget_events, raw_hashes)
                external_calls.append(fallback_result.external_call_performed)
                symbol_articles.extend(fallback_result.articles)

            normalized = dedupe_articles(normalize_articles(symbol_articles))
            articles_by_symbol[symbol] = normalized[: request.max_articles_per_symbol]

        return ShortlistNewsResult(
            requested_symbols=request.symbols,
            articles_by_symbol=articles_by_symbol,
            provider_failures=tuple(failures),
            budget_events=tuple(budget_events),
            raw_payload_hashes=tuple(dict.fromkeys(raw_hashes)),
            external_calls_performed=any(external_calls),
        )

    def _fetch_provider_for_symbol(
        self,
        *,
        provider: str,
        symbol: str,
        lookback_days: int,
        max_articles: int,
        as_of: datetime,
    ) -> ProviderFetchResult:
        cache_key = (provider, symbol, lookback_days, max_articles)
        if cache_key in self._run_cache:
            return self._run_cache[cache_key]

        budget_decision = self._budget_service.check_and_consume(
            provider=provider,
            budget_date=as_of.date(),
            limit=self._config.daily_limit_for(provider),
        )
        if not budget_decision.allowed:
            result = ProviderFetchResult(
                provider=provider,
                endpoint=_endpoint_for(provider),
                symbol=symbol,
                failure=ProviderFetchFailure(
                    provider=provider,
                    symbol=symbol,
                    reason="daily_budget_exceeded",
                    message="provider daily request budget exceeded",
                ),
                budget_decision=budget_decision,
            )
            self._run_cache[cache_key] = result
            return result

        client = self._provider_clients[provider]
        result = client.fetch_symbol_news(
            symbol=symbol,
            lookback_days=lookback_days,
            max_articles=max_articles,
            as_of=as_of,
        )
        result = ProviderFetchResult.model_validate(
            result.model_dump(mode="python") | {"budget_decision": budget_decision}
        )
        self._persist_raw_payload_hashes(result, as_of=as_of)
        self._run_cache[cache_key] = result
        return result

    def _persist_raw_payload_hashes(self, result: ProviderFetchResult, *, as_of: datetime) -> None:
        if self._raw_payload_repository is None:
            return
        for article in result.articles:
            if article.raw_provider_payload is None:
                continue
            payload = build_raw_provider_payload(
                provider=result.provider,
                endpoint=result.endpoint,
                payload=article.raw_provider_payload,
                fetched_at=as_of,
                symbol=result.symbol,
            )
            self._raw_payload_repository.insert_raw_provider_payload(payload)


def _fetch_json_provider_result(
    *,
    provider: str,
    endpoint: str,
    symbol: str,
    url: str,
    timeout_seconds: float,
    parser: Any,
) -> ProviderFetchResult:
    request = urllib.request.Request(url, headers={"Accept": "application/json"}, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            body = response.read().decode("utf-8")
    except (urllib.error.URLError, OSError) as exc:
        return ProviderFetchResult(
            provider=provider,
            endpoint=endpoint,
            symbol=symbol,
            external_call_performed=True,
            failure=ProviderFetchFailure(
                provider=provider,
                symbol=symbol,
                reason="provider_error",
                message=type(exc).__name__,
            ),
        )
    try:
        payload = json.loads(body)
        articles = parser(symbol, payload)
    except (TypeError, ValueError) as exc:
        return ProviderFetchResult(
            provider=provider,
            endpoint=endpoint,
            symbol=symbol,
            raw_payload_hash=hash_payload(body),
            external_call_performed=True,
            failure=ProviderFetchFailure(
                provider=provider,
                symbol=symbol,
                reason="malformed_payload",
                message=type(exc).__name__,
            ),
        )
    return ProviderFetchResult(
        provider=provider,
        endpoint=endpoint,
        symbol=symbol,
        raw_payload_hash=hash_payload(payload),
        articles=articles,
        external_call_performed=True,
    )


def _parse_marketaux_payload(
    symbol: str,
    payload: Mapping[str, Any],
) -> tuple[ProviderNewsArticle, ...]:
    raw_items = payload.get("data", ())
    if not isinstance(raw_items, Sequence) or isinstance(raw_items, str):
        raise ValueError("Marketaux payload data must be a list")
    articles: list[ProviderNewsArticle] = []
    for index, item in enumerate(raw_items):
        if not isinstance(item, Mapping):
            continue
        entities = item.get("entities", ())
        tickers = _tickers_from_marketaux_entities(entities, fallback_symbol=symbol)
        if symbol not in tickers:
            continue
        raw_payload = dict(item)
        articles.append(
            ProviderNewsArticle(
                provider=MARKETAUX_PROVIDER,
                endpoint=MARKETAUX_ENDPOINT,
                provider_article_id=_optional_str(item.get("uuid")) or f"marketaux-{index}",
                symbol=symbol,
                tickers=tickers,
                title=_required_str(item.get("title"), "title"),
                source=_source_name(item),
                canonical_url=_optional_str(item.get("url")),
                published_at=_parse_provider_timestamp(item.get("published_at")),
                summary=_optional_str(item.get("description"))
                or _optional_str(item.get("snippet")),
                language=_optional_str(item.get("language")),
                sentiment=_entity_sentiment_for_symbol(entities, symbol),
                raw_provider_payload=raw_payload,
                raw_payload_hash=hash_payload(raw_payload),
            )
        )
    return tuple(articles)


def _parse_alpha_vantage_payload(
    symbol: str,
    payload: Mapping[str, Any],
) -> tuple[ProviderNewsArticle, ...]:
    raw_items = payload.get("feed", ())
    if not isinstance(raw_items, Sequence) or isinstance(raw_items, str):
        raise ValueError("Alpha Vantage payload feed must be a list")
    articles: list[ProviderNewsArticle] = []
    for index, item in enumerate(raw_items):
        if not isinstance(item, Mapping):
            continue
        ticker_sentiment = item.get("ticker_sentiment", ())
        tickers = _tickers_from_alpha_sentiment(ticker_sentiment, fallback_symbol=symbol)
        if symbol not in tickers:
            continue
        raw_payload = dict(item)
        articles.append(
            ProviderNewsArticle(
                provider=ALPHA_VANTAGE_PROVIDER,
                endpoint=ALPHA_VANTAGE_ENDPOINT,
                provider_article_id=_optional_str(item.get("url")) or f"alpha-vantage-{index}",
                symbol=symbol,
                tickers=tickers,
                title=_required_str(item.get("title"), "title"),
                source=_optional_str(item.get("source")) or "Alpha Vantage",
                canonical_url=_optional_str(item.get("url")),
                published_at=_parse_alpha_time(item.get("time_published")),
                summary=_optional_str(item.get("summary")),
                sentiment=_optional_str(item.get("overall_sentiment_label")),
                raw_provider_payload=raw_payload,
                raw_payload_hash=hash_payload(raw_payload),
            )
        )
    return tuple(articles)


def _collect_provider_result(
    result: ProviderFetchResult,
    failures: list[ProviderFetchFailure],
    budget_events: list[RequestBudgetDecision],
    raw_hashes: list[str],
) -> None:
    if result.failure is not None:
        failures.append(result.failure)
    if result.budget_decision is not None:
        budget_events.append(result.budget_decision)
    if result.raw_payload_hash is not None:
        raw_hashes.append(result.raw_payload_hash)
    for article in result.articles:
        if article.raw_payload_hash is not None:
            raw_hashes.append(article.raw_payload_hash)


def _endpoint_for(provider: str) -> str:
    if provider == MARKETAUX_PROVIDER:
        return MARKETAUX_ENDPOINT
    if provider == ALPHA_VANTAGE_PROVIDER:
        return ALPHA_VANTAGE_ENDPOINT
    raise ValueError(f"unsupported news provider: {provider}")


def _tickers_from_marketaux_entities(
    entities: object,
    *,
    fallback_symbol: str,
) -> tuple[str, ...]:
    tickers: list[str] = []
    if isinstance(entities, Sequence) and not isinstance(entities, str):
        for entity in entities:
            if isinstance(entity, Mapping):
                ticker = _optional_str(entity.get("symbol"))
                if ticker:
                    tickers.append(ticker.upper())
    return tuple(dict.fromkeys(tickers or [fallback_symbol]))


def _tickers_from_alpha_sentiment(
    ticker_sentiment: object,
    *,
    fallback_symbol: str,
) -> tuple[str, ...]:
    tickers: list[str] = []
    if isinstance(ticker_sentiment, Sequence) and not isinstance(ticker_sentiment, str):
        for item in ticker_sentiment:
            if isinstance(item, Mapping):
                ticker = _optional_str(item.get("ticker"))
                if ticker:
                    tickers.append(ticker.upper())
    return tuple(dict.fromkeys(tickers or [fallback_symbol]))


def _entity_sentiment_for_symbol(entities: object, symbol: str) -> str | None:
    if not isinstance(entities, Sequence) or isinstance(entities, str):
        return None
    for entity in entities:
        if not isinstance(entity, Mapping):
            continue
        if _optional_str(entity.get("symbol")) == symbol:
            return _optional_str(entity.get("sentiment_score"))
    return None


def _source_name(item: Mapping[str, Any]) -> str:
    source = item.get("source")
    if isinstance(source, Mapping):
        return _optional_str(source.get("name")) or "Marketaux"
    return _optional_str(source) or "Marketaux"


def _parse_provider_timestamp(value: object) -> datetime:
    text = _required_str(value, "published_at")
    return _parse_iso_datetime(text)


def _parse_alpha_time(value: object) -> datetime:
    text = _required_str(value, "time_published")
    try:
        return datetime.strptime(text, "%Y%m%dT%H%M%S").replace(tzinfo=UTC)
    except ValueError:
        return _parse_iso_datetime(text)


def _parse_iso_datetime(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed


def _optional_str(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _required_str(value: object, field_name: str) -> str:
    text = _optional_str(value)
    if text is None:
        raise ValueError(f"missing required provider field: {field_name}")
    return text


def _news_provider_name(value: str) -> NewsProviderName:
    if value == MARKETAUX_PROVIDER:
        return MARKETAUX_PROVIDER
    if value == ALPHA_VANTAGE_PROVIDER:
        return ALPHA_VANTAGE_PROVIDER
    raise ValueError(f"unsupported news provider: {value}")


def _env(source: Mapping[str, str], name: str, default: str) -> str:
    return source.get(name, default).strip() or default


def _env_int(source: Mapping[str, str], name: str, default: int) -> int:
    raw = source.get(name, "").strip()
    if not raw:
        return default
    return int(raw)


def _env_bool(source: Mapping[str, str], name: str, default: bool) -> bool:
    raw = source.get(name, "").strip().lower()
    if not raw:
        return default
    return raw in {"1", "true", "yes", "on"}
