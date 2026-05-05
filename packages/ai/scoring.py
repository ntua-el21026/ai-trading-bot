"""Deterministic AI event scoring helpers."""

from __future__ import annotations

import math
from datetime import datetime

from packages.ai.models import AIEvent, AITradeResearchOutput, EventType, SourceQuality

SOURCE_QUALITY_WEIGHTS: dict[SourceQuality, float] = {
    "regulatory_filing": 1.0,
    "company_pr": 1.0,
    "premier_financial_publisher": 1.0,
    "secondary_aggregation": 0.7,
    "low_substance_rewrite": 0.4,
}

EVENT_WEIGHTS: dict[EventType, float] = {
    "earnings_surprise_guidance_revision": 1.0,
    "offering_dilution_shelf_convert": 1.0,
    "ma_strategic_deal": 0.8,
    "lawsuit_sec_fda_halt_accounting_risk": 1.0,
    "analyst_upgrade_downgrade": 0.6,
    "product_contract_management_change": 0.6,
    "dividend_split_calendar_only": 0.25,
    "generic_macro_mention": 0.25,
    "other": 0.4,
}


def recency_weight(*, published_at: datetime, as_of: datetime) -> float:
    if published_at.tzinfo is None or as_of.tzinfo is None:
        raise ValueError("published_at and as_of must be timezone-aware")
    hours_since_publication = max((as_of - published_at).total_seconds() / 3600.0, 0.0)
    return math.exp(-hours_since_publication / 72.0)


def source_quality_weight(source_quality: SourceQuality) -> float:
    return SOURCE_QUALITY_WEIGHTS[source_quality]


def direction_sign(event: AIEvent) -> int:
    if event.direction == "positive":
        return 1
    if event.direction == "negative":
        return -1
    return 0


def event_score_component(event: AIEvent, *, as_of: datetime) -> float:
    return (
        direction_sign(event)
        * EVENT_WEIGHTS[event.event_type]
        * recency_weight(published_at=event.published_at, as_of=as_of)
        * source_quality_weight(event.source_quality)
    )


def raw_catalyst_score(events: tuple[AIEvent, ...], *, as_of: datetime) -> float:
    return _clip(sum(event_score_component(event, as_of=as_of) for event in events), -5.0, 5.0)


def mapped_ai_score(events: tuple[AIEvent, ...], *, as_of: datetime) -> int:
    raw_score = raw_catalyst_score(events, as_of=as_of)
    return int(round(_clip(50.0 + (8.0 * raw_score), 10.0, 90.0)))


def classify_hard_block(
    events: tuple[AIEvent, ...],
    *,
    confidence_min: float,
) -> tuple[bool, str | None]:
    for event in events:
        if (
            event.blocking_risk
            and event.risk_level in {"high", "blocking"}
            and event.confidence >= confidence_min
        ):
            return True, f"{event.event_type}:{event.event_id}"
    return False, None


def deterministic_size_multiplier(
    research: AITradeResearchOutput,
    *,
    hard_block_confidence_min: float,
) -> float:
    if research.hard_block:
        return 0.0
    if any(event.risk_level == "blocking" for event in research.events):
        return 0.5
    if any(
        event.risk_level == "high" and event.direction == "negative"
        for event in research.events
    ):
        return 0.5
    uncertain = any(
        event.direction in {"negative", "mixed"}
        and 0.55 <= event.confidence < hard_block_confidence_min
        for event in research.events
    )
    if research.news_state == "mixed" or uncertain:
        return min(research.size_multiplier, 0.75)
    return min(research.size_multiplier, 1.0)


def apply_deterministic_ai_policy(
    research: AITradeResearchOutput,
    *,
    as_of: datetime,
    hard_block_confidence_min: float,
) -> AITradeResearchOutput:
    if research.fallback:
        return research
    hard_block, hard_block_reason = classify_hard_block(
        research.events,
        confidence_min=hard_block_confidence_min,
    )
    updated = research.model_dump(mode="python")
    updated["ai_score"] = mapped_ai_score(research.events, as_of=as_of)
    updated["hard_block"] = hard_block
    updated["hard_block_reason"] = hard_block_reason
    provisional = AITradeResearchOutput.model_validate(updated)
    updated["size_multiplier"] = deterministic_size_multiplier(
        provisional,
        hard_block_confidence_min=hard_block_confidence_min,
    )
    return AITradeResearchOutput.model_validate(updated)


def _clip(value: float, lower: float, upper: float) -> float:
    return max(lower, min(upper, value))
