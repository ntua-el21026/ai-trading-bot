"""AI/news activity boundaries.

These activity definitions declare the Milestone 22 side-effect boundaries. Default local and
test execution returns a refusal/fake placeholder; real provider or OpenAI calls must be injected
behind these boundaries only when explicit smoke gates are present.
"""

from __future__ import annotations

from temporalio import activity

from apps.workers.app.types import ActivityPlaceholderInput, ActivityPlaceholderResult


def _ai_placeholder_result(
    activity_name: str,
    payload: ActivityPlaceholderInput,
) -> ActivityPlaceholderResult:
    return ActivityPlaceholderResult(
        activity_name=activity_name,
        details={
            "workflow_name": payload.workflow_name,
            "purpose": payload.purpose,
            "external_calls": "none",
            "broker_writes": "none",
            "default_behavior": "fake_or_refuse_without_explicit_gates",
        },
    )


@activity.defn(name="fetch_shortlist_news")
async def fetch_shortlist_news(payload: ActivityPlaceholderInput) -> ActivityPlaceholderResult:
    return _ai_placeholder_result("fetch_shortlist_news", payload)


@activity.defn(name="fetch_marketaux_news")
async def fetch_marketaux_news(payload: ActivityPlaceholderInput) -> ActivityPlaceholderResult:
    return _ai_placeholder_result("fetch_marketaux_news", payload)


@activity.defn(name="fetch_alpha_vantage_news")
async def fetch_alpha_vantage_news(
    payload: ActivityPlaceholderInput,
) -> ActivityPlaceholderResult:
    return _ai_placeholder_result("fetch_alpha_vantage_news", payload)


@activity.defn(name="run_openai_web_fallback")
async def run_openai_web_fallback(
    payload: ActivityPlaceholderInput,
) -> ActivityPlaceholderResult:
    return _ai_placeholder_result("run_openai_web_fallback", payload)


@activity.defn(name="persist_news_payloads")
async def persist_news_payloads(payload: ActivityPlaceholderInput) -> ActivityPlaceholderResult:
    return _ai_placeholder_result("persist_news_payloads", payload)


@activity.defn(name="persist_ai_research_output")
async def persist_ai_research_output(
    payload: ActivityPlaceholderInput,
) -> ActivityPlaceholderResult:
    return _ai_placeholder_result("persist_ai_research_output", payload)


@activity.defn(name="generate_ai_calibration_report")
async def generate_ai_calibration_report(
    payload: ActivityPlaceholderInput,
) -> ActivityPlaceholderResult:
    return _ai_placeholder_result("generate_ai_calibration_report", payload)


AI_ACTIVITY_FUNCTIONS = (
    fetch_shortlist_news,
    fetch_marketaux_news,
    fetch_alpha_vantage_news,
    run_openai_web_fallback,
    persist_news_payloads,
    persist_ai_research_output,
    generate_ai_calibration_report,
)
