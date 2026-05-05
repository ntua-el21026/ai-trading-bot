from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from packages.ai.models import (
    AI_PROMPT_VERSION,
    AI_SCHEMA_VERSION,
    AICitation,
    AIEvent,
    AITradeResearchOutput,
    EventDirection,
    EventRiskLevel,
    SourceQuality,
)
from packages.ai.scoring import (
    apply_deterministic_ai_policy,
    classify_hard_block,
    mapped_ai_score,
    recency_weight,
    source_quality_weight,
)

AS_OF = datetime(2026, 5, 4, 14, 30, tzinfo=UTC)


def _citation(citation_id: str = "citation-1") -> AICitation:
    return AICitation(
        citation_id=citation_id,
        title="AAPL filing",
        source="Fixture",
        canonical_url=f"https://example.com/{citation_id}",
        published_at=AS_OF - timedelta(hours=1),
        provider="fixture",
    )


def _event(
    event_id: str = "event-1",
    *,
    direction: EventDirection = "positive",
    confidence: float = 0.8,
    risk_level: EventRiskLevel = "low",
    blocking_risk: bool = False,
    source_quality: SourceQuality = "premier_financial_publisher",
    published_at: datetime | None = None,
) -> AIEvent:
    return AIEvent(
        event_id=event_id,
        event_type="product_contract_management_change",
        direction=direction,
        confidence=confidence,
        risk_level=risk_level,
        source_quality=source_quality,
        published_at=published_at or AS_OF,
        citation_ids=("citation-1",),
        summary="Fixture event",
        blocking_risk=blocking_risk,
    )


def _research(events: tuple[AIEvent, ...]) -> AITradeResearchOutput:
    return AITradeResearchOutput(
        symbol="AAPL",
        analysis_at=AS_OF,
        schema_version=AI_SCHEMA_VERSION,
        prompt_version=AI_PROMPT_VERSION,
        model_version="fixture-model",
        news_state="found",
        events=events,
        citations=(_citation(),),
        hard_block=False,
        hard_block_reason=None,
        ai_score=50,
        size_multiplier=1.0,
        explanation="Fixture analysis",
    )


def test_recency_decay_and_source_quality_weights_follow_spec() -> None:
    assert recency_weight(published_at=AS_OF, as_of=AS_OF) == 1.0
    assert recency_weight(published_at=AS_OF - timedelta(hours=72), as_of=AS_OF) == pytest.approx(
        0.367879,
        rel=1e-5,
    )
    assert source_quality_weight("regulatory_filing") == 1.0
    assert source_quality_weight("secondary_aggregation") == 0.7
    assert source_quality_weight("low_substance_rewrite") == 0.4


def test_ai_score_is_clipped_to_spec_bounds() -> None:
    positive_events = tuple(_event(f"event-{index}") for index in range(20))
    negative_events = tuple(
        _event(f"event-{index}", direction="negative") for index in range(20)
    )

    assert mapped_ai_score(positive_events, as_of=AS_OF) == 90
    assert mapped_ai_score(negative_events, as_of=AS_OF) == 10


def test_hard_block_requires_blocking_risk_and_confidence_threshold() -> None:
    below_threshold = _event(risk_level="blocking", blocking_risk=True, confidence=0.69)
    above_threshold = _event(risk_level="blocking", blocking_risk=True, confidence=0.70)

    assert classify_hard_block((below_threshold,), confidence_min=0.70) == (False, None)
    assert classify_hard_block((above_threshold,), confidence_min=0.70) == (
        True,
        "product_contract_management_change:event-1",
    )


def test_deterministic_policy_sets_score_size_and_hard_block() -> None:
    blocking_event = _event(risk_level="blocking", blocking_risk=True, confidence=0.91)
    research = apply_deterministic_ai_policy(
        _research((blocking_event,)),
        as_of=AS_OF,
        hard_block_confidence_min=0.70,
    )

    assert research.hard_block is True
    assert research.hard_block_reason == "product_contract_management_change:event-1"
    assert research.size_multiplier == 0.0


def test_size_multiplier_cannot_increase_above_one() -> None:
    with pytest.raises(ValidationError):
        AITradeResearchOutput(
            symbol="AAPL",
            analysis_at=AS_OF,
            schema_version=AI_SCHEMA_VERSION,
            prompt_version=AI_PROMPT_VERSION,
            model_version="fixture-model",
            news_state="found",
            events=(_event(),),
            citations=(_citation(),),
            hard_block=False,
            ai_score=50,
            size_multiplier=1.01,
            explanation="Invalid size increase",
        )
