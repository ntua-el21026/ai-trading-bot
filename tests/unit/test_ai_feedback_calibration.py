from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from packages.ai.feedback import (
    AICalibrationReport,
    AIFeedbackCalibrationService,
    AIFeedbackObservation,
    build_ai_quality_event_payloads,
    compute_calibration_metrics,
)
from packages.ai.models import AI_PROMPT_VERSION, AI_SCHEMA_VERSION

AS_OF = datetime(2026, 5, 4, 14, 30, tzinfo=UTC)


def _observation(
    *,
    symbol: str = "AAPL",
    schema_valid: bool = True,
    provider_articles_found: int = 1,
    fallback_used: bool = False,
    web_fallback_used: bool = False,
    hard_block: bool = False,
    risk_flagged: bool = False,
    confidence: float = 0.75,
    ai_score: int = 55,
    later_adverse_outcome: bool = False,
    later_return_pct: float | None = 1.0,
    later_max_drawdown_pct: float | None = -1.0,
) -> AIFeedbackObservation:
    return AIFeedbackObservation(
        symbol=symbol,
        observed_at=AS_OF,
        model_version="fixture-model",
        prompt_version=AI_PROMPT_VERSION,
        schema_version=AI_SCHEMA_VERSION,
        provider_primary="marketaux",
        provider_fallback="alpha_vantage",
        schema_valid=schema_valid,
        provider_articles_found=provider_articles_found,
        fallback_used=fallback_used,
        web_fallback_used=web_fallback_used,
        hard_block=hard_block,
        risk_flagged=risk_flagged,
        confidence=confidence,
        ai_score=ai_score,
        later_return_pct=later_return_pct,
        later_max_drawdown_pct=later_max_drawdown_pct,
        later_adverse_outcome=later_adverse_outcome,
    )


def test_calibration_metrics_cover_validity_fallback_coverage_and_buckets() -> None:
    observations = (
        _observation(confidence=0.85, ai_score=68),
        _observation(
            schema_valid=False,
            provider_articles_found=0,
            fallback_used=True,
            web_fallback_used=True,
            confidence=0.30,
            ai_score=50,
            later_adverse_outcome=True,
        ),
        _observation(hard_block=True, risk_flagged=True, confidence=0.92, ai_score=30),
    )

    metrics = compute_calibration_metrics(observations)

    assert metrics.observation_count == 3
    assert metrics.schema_validity_rate == pytest.approx(2 / 3)
    assert metrics.provider_coverage_rate == pytest.approx(2 / 3)
    assert metrics.no_news_rate == pytest.approx(1 / 3)
    assert metrics.fallback_rate == pytest.approx(1 / 3)
    assert metrics.web_fallback_rate == pytest.approx(1 / 3)
    assert metrics.hard_block_count == 1
    assert metrics.hard_block_false_positive_proxy_rate == 1.0
    assert metrics.missed_risk_false_negative_proxy_rate == pytest.approx(1 / 3)
    assert {bucket.bucket for bucket in metrics.confidence_buckets} == {
        "0.00-0.40",
        "0.40-0.70",
        "0.70-1.00",
    }
    assert metrics.version_breakdowns[0].model_version == "fixture-model"


def test_calibration_report_generates_warning_and_safety_downgrade() -> None:
    service = AIFeedbackCalibrationService()
    report = service.generate_report(
        (
            _observation(schema_valid=False, provider_articles_found=0, fallback_used=True),
            _observation(later_adverse_outcome=True, risk_flagged=False, hard_block=False),
        ),
        generated_at=AS_OF,
        evaluation_window_days=30,
    )

    assert report.recommended_safety_state == "AI_ESCALATION_REQUIRED"
    assert "require_escalation_for_high_risk_low_confidence_cases" in report.recommendations
    assert report.quality_event_payloads
    assert report.strategy_mutation_attempted is False
    assert report.risk_mutation_attempted is False
    assert report.execution_mutation_attempted is False
    assert report.broker_call_attempted is False


def test_safety_state_cannot_increase_ai_influence() -> None:
    service = AIFeedbackCalibrationService()
    report = service.generate_report(
        (_observation(), _observation(symbol="MSFT")),
        generated_at=AS_OF,
        evaluation_window_days=30,
        current_safety_state="AI_NEUTRAL_ONLY",
    )

    assert report.recommended_safety_state == "AI_NEUTRAL_ONLY"


def test_feedback_report_rejects_execution_impacting_mutation_flags() -> None:
    service = AIFeedbackCalibrationService()
    report = service.generate_report(
        (_observation(),),
        generated_at=AS_OF,
        evaluation_window_days=30,
    )

    payload = report.model_dump(mode="python")
    payload["broker_call_attempted"] = True

    with pytest.raises(ValidationError, match="cannot mutate execution-impacting"):
        AICalibrationReport.model_validate(payload)


def test_quality_event_payloads_are_empty_for_normal_state() -> None:
    assert build_ai_quality_event_payloads({"recommended_safety_state": "AI_NORMAL"}) == ()
