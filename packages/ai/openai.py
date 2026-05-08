"""Explicitly gated OpenAI structured analysis and web-fallback boundaries."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from collections.abc import Mapping, Sequence
from datetime import datetime
from typing import Any, Protocol, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from packages.ai.budget import RequestBudgetDecision, RequestBudgetService
from packages.ai.fallback import neutral_research_output, no_news_fallback, provider_outage_fallback
from packages.ai.models import (
    AI_PROMPT_VERSION,
    AI_SCHEMA_VERSION,
    AITradeResearchOutput,
    NormalizedNewsArticle,
)
from packages.ai.parser import parse_ai_trade_research_or_fallback
from packages.ai.persistence import (
    AIResearchPersistencePayload,
    build_ai_research_persistence_payload,
)
from packages.ai.prompts import load_prompt_template
from packages.ai.scoring import apply_deterministic_ai_policy

OPENAI_RESPONSES_ENDPOINT = "https://api.openai.com/v1/responses"
OPENAI_MODELS_ENDPOINT = "https://api.openai.com/v1/models"
OPENAI_WEB_PROVIDER_NAME = "openai_web_search"

DEFAULT_OPENAI_MODEL = "gpt-5.2"
DEFAULT_OPENAI_ESCALATION_MODEL = "gpt-5.2-pro"
DEFAULT_OPENAI_FALLBACK_MODEL = "gpt-5-mini"

AI_DAILY_BUDGET_PROVIDER = "openai_structured_analysis"


class OpenAIModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class OpenAIModelConfig(OpenAIModel):
    provider: str = "openai"
    model: str = DEFAULT_OPENAI_MODEL
    escalation_model: str = DEFAULT_OPENAI_ESCALATION_MODEL
    fallback_model: str = DEFAULT_OPENAI_FALLBACK_MODEL
    daily_request_limit: int = Field(default=25, ge=0)
    max_symbols_per_run: int = Field(default=5, gt=0)
    max_articles_per_symbol: int = Field(default=3, gt=0)
    require_structured_output: bool = True
    neutral_fallback_on_error: bool = True
    enable_escalation: bool = False

    @model_validator(mode="after")
    def validate_safety_defaults(self) -> Self:
        if self.provider != "openai":
            raise ValueError("Milestone 22 OpenAI config requires AI_PROVIDER=openai")
        if not self.require_structured_output:
            raise ValueError("OpenAI analysis must require structured output")
        if not self.neutral_fallback_on_error:
            raise ValueError("OpenAI errors must fall back to neutral behavior")
        return self

    @classmethod
    def from_env(cls, environ: Mapping[str, str] | None = None) -> OpenAIModelConfig:
        source = os.environ if environ is None else environ
        return cls(
            provider=_env(source, "AI_PROVIDER", "openai"),
            model=_env(source, "OPENAI_MODEL", DEFAULT_OPENAI_MODEL),
            escalation_model=_env(
                source,
                "OPENAI_ESCALATION_MODEL",
                DEFAULT_OPENAI_ESCALATION_MODEL,
            ),
            fallback_model=_env(source, "OPENAI_FALLBACK_MODEL", DEFAULT_OPENAI_FALLBACK_MODEL),
            daily_request_limit=_env_int(source, "AI_DAILY_REQUEST_LIMIT", 25),
            max_symbols_per_run=_env_int(source, "AI_MAX_SYMBOLS_PER_RUN", 5),
            max_articles_per_symbol=_env_int(source, "AI_MAX_ARTICLES_PER_SYMBOL", 3),
            require_structured_output=_env_bool(source, "AI_REQUIRE_STRUCTURED_OUTPUT", True),
            neutral_fallback_on_error=_env_bool(source, "AI_NEUTRAL_FALLBACK_ON_ERROR", True),
            enable_escalation=_env_bool(source, "AI_ENABLE_ESCALATION", False),
        )


class OpenAIProviderError(RuntimeError):
    def __init__(self, code: str, message: str, *, retryable: bool = False) -> None:
        self.code = code
        self.retryable = retryable
        super().__init__(message)


class OpenAIClient(Protocol):
    def list_models(self) -> tuple[str, ...]:
        """Return available model IDs."""

    def create_structured_response(
        self,
        *,
        model: str,
        prompt: str,
        schema: Mapping[str, Any],
    ) -> str:
        """Return raw structured model output text."""

    def run_web_search(
        self,
        *,
        model: str,
        prompt: str,
    ) -> tuple[str, tuple[str, ...]]:
        """Return web-search output text and sanitized source URLs."""


class OpenAIHttpClient:
    """Minimal urllib OpenAI client used only by explicit smoke-gated paths."""

    def __init__(self, *, api_key: str, timeout_seconds: float = 30.0) -> None:
        self._api_key = api_key
        self._timeout_seconds = timeout_seconds

    def list_models(self) -> tuple[str, ...]:
        payload = self._request_json("GET", OPENAI_MODELS_ENDPOINT)
        data = payload.get("data", ())
        if not isinstance(data, Sequence) or isinstance(data, str):
            raise OpenAIProviderError("malformed_model_list", "OpenAI model list was malformed")
        model_ids: list[str] = []
        for item in data:
            if isinstance(item, Mapping):
                model_id = item.get("id")
                if isinstance(model_id, str):
                    model_ids.append(model_id)
        return tuple(model_ids)

    def create_structured_response(
        self,
        *,
        model: str,
        prompt: str,
        schema: Mapping[str, Any],
    ) -> str:
        payload = {
            "model": model,
            "input": prompt,
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": "ai_trade_research_output",
                    "strict": True,
                    "schema": schema,
                }
            },
        }
        response = self._request_json("POST", OPENAI_RESPONSES_ENDPOINT, payload=payload)
        return _extract_response_text(response)

    def run_web_search(
        self,
        *,
        model: str,
        prompt: str,
    ) -> tuple[str, tuple[str, ...]]:
        payload = {
            "model": model,
            "input": prompt,
            "tools": [{"type": "web_search"}],
            "tool_choice": "auto",
            "include": ["web_search_call.action.sources"],
        }
        response = self._request_json("POST", OPENAI_RESPONSES_ENDPOINT, payload=payload)
        return _extract_response_text(response), _extract_source_urls(response)

    def _request_json(
        self,
        method: str,
        url: str,
        *,
        payload: Mapping[str, Any] | None = None,
    ) -> Mapping[str, Any]:
        body = None if payload is None else json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            url,
            data=body,
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            method=method,
        )
        try:
            with urllib.request.urlopen(request, timeout=self._timeout_seconds) as response:
                response_body = response.read()
        except urllib.error.HTTPError as exc:
            code = "credential_rejected" if exc.code in {401, 403} else "openai_http_error"
            raise OpenAIProviderError(
                code,
                f"OpenAI request failed with HTTP {exc.code}",
                retryable=500 <= exc.code < 600,
            ) from exc
        except (urllib.error.URLError, OSError) as exc:
            raise OpenAIProviderError(
                "openai_unavailable",
                "OpenAI request failed before response",
                retryable=True,
            ) from exc
        try:
            parsed = json.loads(response_body.decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise OpenAIProviderError("malformed_response", "OpenAI response was not JSON") from exc
        if not isinstance(parsed, Mapping):
            raise OpenAIProviderError("malformed_response", "OpenAI response was not an object")
        return parsed


class FakeOpenAIClient:
    """Deterministic fake OpenAI client for default tests."""

    def __init__(
        self,
        *,
        structured_output: str | None = None,
        model_ids: Sequence[str] = (DEFAULT_OPENAI_MODEL,),
        error: OpenAIProviderError | None = None,
        web_output: str = "{}",
        web_sources: Sequence[str] = (),
    ) -> None:
        self._structured_output = structured_output
        self._model_ids = tuple(model_ids)
        self._error = error
        self._web_output = web_output
        self._web_sources = tuple(web_sources)
        self.structured_requests: list[dict[str, object]] = []
        self.web_requests: list[dict[str, object]] = []

    def list_models(self) -> tuple[str, ...]:
        if self._error is not None:
            raise self._error
        return self._model_ids

    def create_structured_response(
        self,
        *,
        model: str,
        prompt: str,
        schema: Mapping[str, Any],
    ) -> str:
        del schema
        if self._error is not None:
            raise self._error
        self.structured_requests.append({"model": model, "prompt": prompt})
        if self._structured_output is None:
            raise OpenAIProviderError("no_fixture_output", "fake structured output not configured")
        return self._structured_output

    def run_web_search(
        self,
        *,
        model: str,
        prompt: str,
    ) -> tuple[str, tuple[str, ...]]:
        if self._error is not None:
            raise self._error
        self.web_requests.append({"model": model, "prompt": prompt})
        return self._web_output, self._web_sources


class OpenAIModelValidationResult(OpenAIModel):
    model: str
    available: bool
    checked: bool
    sanitized_error: str | None = None


class OpenAIAnalysisResult(OpenAIModel):
    output: AITradeResearchOutput
    persistence_payload: AIResearchPersistencePayload
    raw_prompt_hash: str
    raw_output_hash: str | None
    external_calls_performed: bool
    budget_decision: RequestBudgetDecision | None = None
    provider_failure_code: str | None = None


def validate_openai_model_availability(
    *,
    client: OpenAIClient,
    model: str,
) -> OpenAIModelValidationResult:
    try:
        model_ids = client.list_models()
    except OpenAIProviderError as exc:
        return OpenAIModelValidationResult(
            model=model,
            available=False,
            checked=True,
            sanitized_error=exc.code,
        )
    return OpenAIModelValidationResult(
        model=model,
        available=model in model_ids,
        checked=True,
        sanitized_error=None if model in model_ids else "configured_model_unavailable",
    )


def analyze_symbol_news_with_openai(
    *,
    symbol: str,
    articles: Sequence[NormalizedNewsArticle],
    client: OpenAIClient,
    config: OpenAIModelConfig,
    analysis_at: datetime,
    budget_service: RequestBudgetService | None = None,
    prompt_version: str = AI_PROMPT_VERSION,
    schema_version: str = AI_SCHEMA_VERSION,
    hard_block_confidence_min: float = 0.70,
) -> OpenAIAnalysisResult:
    if analysis_at.tzinfo is None:
        raise ValueError("analysis_at must be timezone-aware")
    if len(articles) > config.max_articles_per_symbol:
        raise ValueError("OpenAI analysis exceeds max articles per symbol")
    raw_prompt = build_openai_research_prompt(
        symbol=symbol,
        articles=articles,
        prompt_version=prompt_version,
    )
    if not articles:
        output = no_news_fallback(
            symbol=symbol,
            analysis_at=analysis_at,
            prompt_version=prompt_version,
            schema_version=schema_version,
            model_version=config.model,
        )
        payload = build_ai_research_persistence_payload(
            symbol=symbol,
            created_at=analysis_at,
            raw_prompt=raw_prompt,
            raw_ai_output=None,
            parsed_output=output,
        )
        return OpenAIAnalysisResult(
            output=output,
            persistence_payload=payload,
            raw_prompt_hash=payload.raw_prompt_hash,
            raw_output_hash=payload.raw_output_hash,
            external_calls_performed=False,
        )

    budget_decision = (budget_service or RequestBudgetService()).check_and_consume(
        provider=AI_DAILY_BUDGET_PROVIDER,
        budget_date=analysis_at.date(),
        limit=config.daily_request_limit,
    )
    if not budget_decision.allowed:
        output = neutral_research_output(
            symbol=symbol,
            analysis_at=analysis_at,
            prompt_version=prompt_version,
            schema_version=schema_version,
            model_version=config.model,
            fallback_reason="ai_provider_outage",
            news_state="provider_error",
            explanation="OpenAI daily request budget exceeded; using neutral fallback.",
        )
        payload = build_ai_research_persistence_payload(
            symbol=symbol,
            created_at=analysis_at,
            raw_prompt=raw_prompt,
            raw_ai_output=None,
            parsed_output=output,
        )
        return OpenAIAnalysisResult(
            output=output,
            persistence_payload=payload,
            raw_prompt_hash=payload.raw_prompt_hash,
            raw_output_hash=payload.raw_output_hash,
            external_calls_performed=False,
            budget_decision=budget_decision,
            provider_failure_code="daily_budget_exceeded",
        )

    try:
        raw_output = client.create_structured_response(
            model=config.model,
            prompt=raw_prompt,
            schema=openai_ai_research_json_schema(),
        )
    except OpenAIProviderError as exc:
        output, _failure = provider_outage_fallback(
            symbol=symbol,
            analysis_at=analysis_at,
            prompt_version=prompt_version,
            schema_version=schema_version,
            model_version=config.model,
            provider="openai",
            message=exc.code,
        )
        payload = build_ai_research_persistence_payload(
            symbol=symbol,
            created_at=analysis_at,
            raw_prompt=raw_prompt,
            raw_ai_output=None,
            parsed_output=output,
        )
        return OpenAIAnalysisResult(
            output=output,
            persistence_payload=payload,
            raw_prompt_hash=payload.raw_prompt_hash,
            raw_output_hash=payload.raw_output_hash,
            external_calls_performed=True,
            budget_decision=budget_decision,
            provider_failure_code=exc.code,
        )

    parsed = parse_ai_trade_research_or_fallback(
        raw_output,
        symbol=symbol,
        analysis_at=analysis_at,
        prompt_version=prompt_version,
        schema_version=schema_version,
        model_version=config.model,
    )
    parsed = apply_deterministic_ai_policy(
        parsed,
        as_of=analysis_at,
        hard_block_confidence_min=hard_block_confidence_min,
    )
    payload = build_ai_research_persistence_payload(
        symbol=symbol,
        created_at=analysis_at,
        raw_prompt=raw_prompt,
        raw_ai_output=raw_output,
        parsed_output=parsed,
    )
    return OpenAIAnalysisResult(
        output=parsed,
        persistence_payload=payload,
        raw_prompt_hash=payload.raw_prompt_hash,
        raw_output_hash=payload.raw_output_hash,
        external_calls_performed=True,
        budget_decision=budget_decision,
    )


def build_openai_research_prompt(
    *,
    symbol: str,
    articles: Sequence[NormalizedNewsArticle],
    prompt_version: str = AI_PROMPT_VERSION,
) -> str:
    template = load_prompt_template(prompt_version)
    article_payload = [
        {
            "citation_id": f"article-{index + 1}",
            "provider": article.provider,
            "title": article.title,
            "source": article.source,
            "url": article.canonical_url,
            "published_at": article.published_at.isoformat(),
            "content": article.content,
            "raw_payload_hash": article.raw_payload_hash,
        }
        for index, article in enumerate(articles)
    ]
    return (
        f"{template}\n\n"
        "Return JSON only for this deterministic shortlist symbol.\n"
        f"Symbol: {symbol}\n"
        f"Prompt version: {prompt_version}\n"
        f"Schema version: {AI_SCHEMA_VERSION}\n"
        f"Articles JSON: {json.dumps(article_payload, sort_keys=True, default=str)}"
    )


def openai_ai_research_json_schema() -> dict[str, Any]:
    """Return a strict Responses-API JSON schema for AI research output."""

    return _strict_openai_json_schema(AITradeResearchOutput.model_json_schema())


class WebFallbackPolicy(OpenAIModel):
    enabled: bool = False
    runtime_policy_allowed: bool = False
    daily_request_limit: int = Field(default=5, ge=0)

    @property
    def usable(self) -> bool:
        return self.enabled and self.runtime_policy_allowed


class WebFallbackDecision(OpenAIModel):
    should_run: bool
    reason: str


class WebFallbackResult(OpenAIModel):
    decision: WebFallbackDecision
    raw_output_hash: str | None = None
    source_urls: tuple[str, ...] = ()
    budget_decision: RequestBudgetDecision | None = None
    external_calls_performed: bool = False
    sanitized_error: str | None = None


def decide_web_fallback(
    *,
    provider_articles: Sequence[NormalizedNewsArticle],
    providers_conflict: bool = False,
    high_risk_context_incomplete: bool = False,
    ai_confidence_low_trade_would_pass: bool = False,
    hard_block_depends_on_missing_context: bool = False,
) -> WebFallbackDecision:
    if not provider_articles:
        return WebFallbackDecision(should_run=True, reason="provider_no_articles")
    if providers_conflict:
        return WebFallbackDecision(should_run=True, reason="provider_conflict")
    if high_risk_context_incomplete:
        return WebFallbackDecision(should_run=True, reason="high_risk_context_incomplete")
    if ai_confidence_low_trade_would_pass:
        return WebFallbackDecision(should_run=True, reason="low_confidence_trade_would_pass")
    if hard_block_depends_on_missing_context:
        return WebFallbackDecision(should_run=True, reason="hard_block_context_missing")
    return WebFallbackDecision(should_run=False, reason="provider_context_sufficient")


def run_openai_web_fallback(
    *,
    client: OpenAIClient,
    model: str,
    policy: WebFallbackPolicy,
    budget_service: RequestBudgetService,
    as_of: datetime,
    prompt: str,
    decision: WebFallbackDecision,
) -> WebFallbackResult:
    if not decision.should_run:
        return WebFallbackResult(decision=decision)
    if not policy.usable:
        return WebFallbackResult(
            decision=WebFallbackDecision(should_run=False, reason="web_fallback_disabled"),
        )
    budget_decision = budget_service.check_and_consume(
        provider=OPENAI_WEB_PROVIDER_NAME,
        budget_date=as_of.date(),
        limit=policy.daily_request_limit,
    )
    if not budget_decision.allowed:
        return WebFallbackResult(
            decision=decision,
            budget_decision=budget_decision,
            sanitized_error="daily_budget_exceeded",
        )
    try:
        raw_output, sources = client.run_web_search(model=model, prompt=prompt)
    except OpenAIProviderError as exc:
        return WebFallbackResult(
            decision=decision,
            budget_decision=budget_decision,
            external_calls_performed=True,
            sanitized_error=exc.code,
        )
    return WebFallbackResult(
        decision=decision,
        raw_output_hash=_hash_text(raw_output),
        source_urls=sources,
        budget_decision=budget_decision,
        external_calls_performed=True,
    )


def _extract_response_text(response: Mapping[str, Any]) -> str:
    output_text = response.get("output_text")
    if isinstance(output_text, str):
        return output_text
    output = response.get("output", ())
    if isinstance(output, Sequence) and not isinstance(output, str):
        for item in output:
            if not isinstance(item, Mapping):
                continue
            content = item.get("content", ())
            if not isinstance(content, Sequence) or isinstance(content, str):
                continue
            for part in content:
                if isinstance(part, Mapping):
                    text = part.get("text")
                    if isinstance(text, str):
                        return text
    raise OpenAIProviderError("missing_output_text", "OpenAI response had no output text")


def _extract_source_urls(response: Mapping[str, Any]) -> tuple[str, ...]:
    urls: list[str] = []
    sources = response.get("sources", ())
    if isinstance(sources, Sequence) and not isinstance(sources, str):
        urls.extend(_url_values(sources))
    output = response.get("output", ())
    if isinstance(output, Sequence) and not isinstance(output, str):
        for item in output:
            if not isinstance(item, Mapping):
                continue
            action = item.get("action")
            if isinstance(action, Mapping):
                action_sources = action.get("sources", ())
                if isinstance(action_sources, Sequence) and not isinstance(action_sources, str):
                    urls.extend(_url_values(action_sources))
            content = item.get("content", ())
            if isinstance(content, Sequence) and not isinstance(content, str):
                for part in content:
                    if not isinstance(part, Mapping):
                        continue
                    annotations = part.get("annotations", ())
                    if isinstance(annotations, Sequence) and not isinstance(annotations, str):
                        urls.extend(_url_values(annotations))
    return tuple(dict.fromkeys(urls))


def _url_values(items: Sequence[object]) -> list[str]:
    urls: list[str] = []
    for item in items:
        if isinstance(item, Mapping):
            url = item.get("url")
            if isinstance(url, str):
                urls.append(url)
    return urls


def _strict_openai_json_schema(schema: Mapping[str, Any]) -> dict[str, Any]:
    normalized: dict[str, Any] = {}
    for key, value in schema.items():
        if key == "default":
            continue
        if isinstance(value, Mapping):
            normalized[key] = _strict_openai_json_schema(value)
        elif isinstance(value, Sequence) and not isinstance(value, str):
            normalized[key] = [
                _strict_openai_json_schema(item) if isinstance(item, Mapping) else item
                for item in value
            ]
        else:
            normalized[key] = value
    properties = normalized.get("properties")
    if isinstance(properties, Mapping):
        normalized["additionalProperties"] = False
        normalized["required"] = list(properties)
    return normalized


def _hash_text(value: str) -> str:
    from packages.data.payloads import hash_payload

    return hash_payload(value)


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
