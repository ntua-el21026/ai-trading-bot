"""Autonomous AI feedback and calibration contracts.

The feedback loop is intentionally one-way: it may reduce or neutralize AI influence and
recommend escalation, but it never mutates strategy, risk, execution, broker, or universe rules.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping, Sequence
from datetime import datetime
from typing import Any, Literal

from pydantic import Field, model_validator

from packages.ai.models import AI_PROMPT_VERSION, AI_SCHEMA_VERSION, AIModel

AISafetyState = Literal[
    "AI_NORMAL",
    "AI_REDUCED_INFLUENCE",
    "AI_NEUTRAL_ONLY",
    "AI_ESCALATION_REQUIRED",
]

_SAFETY_STATE_RANK: dict[AISafetyState, int] = {
    "AI_NORMAL": 0,
    "AI_REDUCED_INFLUENCE": 1,
    "AI_NEUTRAL_ONLY": 2,
    "AI_ESCALATION_REQUIRED": 3,
}


class AIFeedbackObservation(AIModel):
    symbol: str
    observed_at: datetime
    model_version: str
    prompt_version: str = AI_PROMPT_VERSION
    schema_version: str = AI_SCHEMA_VERSION
    provider_primary: str
    provider_fallback: str | None = None
    schema_valid: bool
    provider_articles_found: int = Field(ge=0)
    fallback_used: bool
    web_fallback_used: bool = False
    hard_block: bool
    risk_flagged: bool = False
    confidence: float = Field(ge=0, le=1)
    ai_score: int = Field(ge=10, le=90)
    later_return_pct: float | None = None
    later_max_drawdown_pct: float | None = None
    later_adverse_outcome: bool = False

    @model_validator(mode="after")
    def validate_observation(self) -> AIFeedbackObservation:
        if self.symbol != self.symbol.upper():
            raise ValueError("feedback observation symbol must be uppercase")
        if self.observed_at.tzinfo is None:
            raise ValueError("observed_at must be timezone-aware")
        return self


class AIBucketSummary(AIModel):
    bucket: str
    count: int = Field(ge=0)
    adverse_outcome_rate: float = Field(ge=0, le=1)
    average_later_return_pct: float | None = None
    average_later_max_drawdown_pct: float | None = None


class AIVersionBreakdown(AIModel):
    model_version: str
    prompt_version: str
    schema_version: str
    count: int = Field(ge=0)
    schema_validity_rate: float = Field(ge=0, le=1)
    fallback_rate: float = Field(ge=0, le=1)
    provider_coverage_rate: float = Field(ge=0, le=1)


class AICalibrationMetrics(AIModel):
    observation_count: int = Field(ge=0)
    schema_validity_rate: float = Field(ge=0, le=1)
    provider_coverage_rate: float = Field(ge=0, le=1)
    no_news_rate: float = Field(ge=0, le=1)
    fallback_rate: float = Field(ge=0, le=1)
    web_fallback_rate: float = Field(ge=0, le=1)
    hard_block_count: int = Field(ge=0)
    hard_block_false_positive_proxy_rate: float = Field(ge=0, le=1)
    missed_risk_false_negative_proxy_rate: float = Field(ge=0, le=1)
    confidence_buckets: tuple[AIBucketSummary, ...]
    score_buckets: tuple[AIBucketSummary, ...]
    version_breakdowns: tuple[AIVersionBreakdown, ...]


class AICalibrationReport(AIModel):
    generated_at: datetime
    evaluation_window_days: int = Field(gt=0)
    metrics: AICalibrationMetrics
    current_safety_state: AISafetyState
    recommended_safety_state: AISafetyState
    recommendations: tuple[str, ...]
    report_payload: dict[str, Any]
    quality_event_payloads: tuple[dict[str, Any], ...]
    strategy_mutation_attempted: bool = False
    risk_mutation_attempted: bool = False
    execution_mutation_attempted: bool = False
    broker_call_attempted: bool = False

    @model_validator(mode="after")
    def validate_report(self) -> AICalibrationReport:
        if self.generated_at.tzinfo is None:
            raise ValueError("generated_at must be timezone-aware")
        if _SAFETY_STATE_RANK[self.recommended_safety_state] < _SAFETY_STATE_RANK[
            self.current_safety_state
        ]:
            raise ValueError("AI feedback may not increase AI influence")
        if (
            self.strategy_mutation_attempted
            or self.risk_mutation_attempted
            or self.execution_mutation_attempted
            or self.broker_call_attempted
        ):
            raise ValueError("AI feedback cannot mutate execution-impacting systems")
        return self


class AIFeedbackCalibrationService:
    """Evaluate historical AI behavior and recommend safety downgrades only."""

    def __init__(
        self,
        *,
        min_schema_validity_rate: float = 0.99,
        min_provider_coverage_rate: float = 0.60,
        max_fallback_rate: float = 0.35,
        max_missed_risk_false_negative_proxy_rate: float = 0.15,
        max_hard_block_false_positive_proxy_rate: float = 0.40,
    ) -> None:
        self._min_schema_validity_rate = min_schema_validity_rate
        self._min_provider_coverage_rate = min_provider_coverage_rate
        self._max_fallback_rate = max_fallback_rate
        self._max_missed_risk_false_negative_proxy_rate = (
            max_missed_risk_false_negative_proxy_rate
        )
        self._max_hard_block_false_positive_proxy_rate = (
            max_hard_block_false_positive_proxy_rate
        )

    def generate_report(
        self,
        observations: Sequence[AIFeedbackObservation],
        *,
        generated_at: datetime,
        evaluation_window_days: int,
        current_safety_state: AISafetyState = "AI_NORMAL",
    ) -> AICalibrationReport:
        if generated_at.tzinfo is None:
            raise ValueError("generated_at must be timezone-aware")
        metrics = compute_calibration_metrics(observations)
        recommended_state = self.recommend_safety_state(
            metrics,
            current_safety_state=current_safety_state,
        )
        recommendations = _recommendations_for(metrics, recommended_state)
        report_payload = build_ai_calibration_report_payload(
            generated_at=generated_at,
            evaluation_window_days=evaluation_window_days,
            metrics=metrics,
            current_safety_state=current_safety_state,
            recommended_safety_state=recommended_state,
            recommendations=recommendations,
        )
        quality_events = build_ai_quality_event_payloads(report_payload)
        return AICalibrationReport(
            generated_at=generated_at,
            evaluation_window_days=evaluation_window_days,
            metrics=metrics,
            current_safety_state=current_safety_state,
            recommended_safety_state=recommended_state,
            recommendations=recommendations,
            report_payload=report_payload,
            quality_event_payloads=quality_events,
        )

    def recommend_safety_state(
        self,
        metrics: AICalibrationMetrics,
        *,
        current_safety_state: AISafetyState = "AI_NORMAL",
    ) -> AISafetyState:
        candidate: AISafetyState = "AI_NORMAL"
        if metrics.observation_count == 0:
            candidate = "AI_REDUCED_INFLUENCE"
        if (
            metrics.schema_validity_rate < self._min_schema_validity_rate
            or metrics.fallback_rate > self._max_fallback_rate
            or metrics.provider_coverage_rate < self._min_provider_coverage_rate
            or metrics.hard_block_false_positive_proxy_rate
            > self._max_hard_block_false_positive_proxy_rate
        ):
            candidate = _max_safety_state(candidate, "AI_REDUCED_INFLUENCE")
        if (
            metrics.schema_validity_rate < 0.95
            or metrics.missed_risk_false_negative_proxy_rate
            > self._max_missed_risk_false_negative_proxy_rate
        ):
            candidate = _max_safety_state(candidate, "AI_NEUTRAL_ONLY")
        if (
            metrics.schema_validity_rate < 0.90
            or metrics.missed_risk_false_negative_proxy_rate
            > max(0.25, self._max_missed_risk_false_negative_proxy_rate)
        ):
            candidate = _max_safety_state(candidate, "AI_ESCALATION_REQUIRED")
        return _max_safety_state(current_safety_state, candidate)


def compute_calibration_metrics(
    observations: Sequence[AIFeedbackObservation],
) -> AICalibrationMetrics:
    total = len(observations)
    hard_blocks = [observation for observation in observations if observation.hard_block]
    hard_block_false_positives = [
        observation
        for observation in hard_blocks
        if not observation.later_adverse_outcome and not _material_drawdown(observation)
    ]
    missed_risks = [
        observation
        for observation in observations
        if observation.later_adverse_outcome
        and not observation.hard_block
        and not observation.risk_flagged
    ]
    return AICalibrationMetrics(
        observation_count=total,
        schema_validity_rate=_rate(observations, lambda item: item.schema_valid),
        provider_coverage_rate=_rate(observations, lambda item: item.provider_articles_found > 0),
        no_news_rate=_rate(observations, lambda item: item.provider_articles_found == 0),
        fallback_rate=_rate(observations, lambda item: item.fallback_used),
        web_fallback_rate=_rate(observations, lambda item: item.web_fallback_used),
        hard_block_count=len(hard_blocks),
        hard_block_false_positive_proxy_rate=_ratio(
            len(hard_block_false_positives),
            len(hard_blocks),
        ),
        missed_risk_false_negative_proxy_rate=_ratio(len(missed_risks), total),
        confidence_buckets=_bucket_summaries(
            observations,
            bucket_selector=_confidence_bucket,
            ordered_buckets=("0.00-0.40", "0.40-0.70", "0.70-1.00"),
        ),
        score_buckets=_bucket_summaries(
            observations,
            bucket_selector=_score_bucket,
            ordered_buckets=("10-44", "45-64", "65-90"),
        ),
        version_breakdowns=_version_breakdowns(observations),
    )


def build_ai_calibration_report_payload(
    *,
    generated_at: datetime,
    evaluation_window_days: int,
    metrics: AICalibrationMetrics,
    current_safety_state: AISafetyState,
    recommended_safety_state: AISafetyState,
    recommendations: Sequence[str],
) -> dict[str, Any]:
    return {
        "report_type": "ai_calibration",
        "generated_at": generated_at.isoformat(),
        "evaluation_window_days": evaluation_window_days,
        "current_safety_state": current_safety_state,
        "recommended_safety_state": recommended_safety_state,
        "recommendations": list(recommendations),
        "metrics": metrics.model_dump(mode="json"),
        "strategy_mutation_attempted": False,
        "risk_mutation_attempted": False,
        "execution_mutation_attempted": False,
        "broker_call_attempted": False,
    }


def build_ai_quality_event_payloads(
    report_payload: Mapping[str, Any],
) -> tuple[dict[str, Any], ...]:
    state = report_payload.get("recommended_safety_state")
    if state == "AI_NORMAL":
        return ()
    severity = "critical" if state in {"AI_NEUTRAL_ONLY", "AI_ESCALATION_REQUIRED"} else "warning"
    return (
        {
            "event_type": "ai_quality_warning",
            "severity": severity,
            "source_component": "ai_feedback_calibration",
            "message": f"AI feedback recommends {state}",
            "payload": dict(report_payload),
        },
    )


def _recommendations_for(
    metrics: AICalibrationMetrics,
    recommended_state: AISafetyState,
) -> tuple[str, ...]:
    recommendations: list[str] = []
    if recommended_state != "AI_NORMAL":
        recommendations.append(f"set_ai_safety_state:{recommended_state}")
    if metrics.schema_validity_rate < 0.99:
        recommendations.append("investigate_ai_schema_validity")
    if metrics.provider_coverage_rate < 0.60:
        recommendations.append("review_news_provider_coverage")
    if metrics.fallback_rate > 0.35:
        recommendations.append("reduce_ai_influence_until_fallbacks_improve")
    if metrics.missed_risk_false_negative_proxy_rate > 0.15:
        recommendations.append("require_escalation_for_high_risk_low_confidence_cases")
    return tuple(dict.fromkeys(recommendations))


def _version_breakdowns(
    observations: Sequence[AIFeedbackObservation],
) -> tuple[AIVersionBreakdown, ...]:
    groups: dict[tuple[str, str, str], list[AIFeedbackObservation]] = {}
    for observation in observations:
        key = (
            observation.model_version,
            observation.prompt_version,
            observation.schema_version,
        )
        groups.setdefault(key, []).append(observation)
    return tuple(
        AIVersionBreakdown(
            model_version=model_version,
            prompt_version=prompt_version,
            schema_version=schema_version,
            count=len(items),
            schema_validity_rate=_rate(items, lambda item: item.schema_valid),
            fallback_rate=_rate(items, lambda item: item.fallback_used),
            provider_coverage_rate=_rate(items, lambda item: item.provider_articles_found > 0),
        )
        for (model_version, prompt_version, schema_version), items in sorted(groups.items())
    )


def _bucket_summaries(
    observations: Sequence[AIFeedbackObservation],
    *,
    bucket_selector: Callable[[AIFeedbackObservation], str],
    ordered_buckets: Sequence[str],
) -> tuple[AIBucketSummary, ...]:
    grouped: dict[str, list[AIFeedbackObservation]] = {bucket: [] for bucket in ordered_buckets}
    for observation in observations:
        grouped.setdefault(bucket_selector(observation), []).append(observation)
    return tuple(
        AIBucketSummary(
            bucket=bucket,
            count=len(items),
            adverse_outcome_rate=_rate(items, lambda item: item.later_adverse_outcome),
            average_later_return_pct=_average(
                item.later_return_pct for item in items if item.later_return_pct is not None
            ),
            average_later_max_drawdown_pct=_average(
                item.later_max_drawdown_pct
                for item in items
                if item.later_max_drawdown_pct is not None
            ),
        )
        for bucket, items in grouped.items()
    )


def _confidence_bucket(observation: AIFeedbackObservation) -> str:
    if observation.confidence < 0.40:
        return "0.00-0.40"
    if observation.confidence < 0.70:
        return "0.40-0.70"
    return "0.70-1.00"


def _score_bucket(observation: AIFeedbackObservation) -> str:
    if observation.ai_score < 45:
        return "10-44"
    if observation.ai_score < 65:
        return "45-64"
    return "65-90"


def _material_drawdown(observation: AIFeedbackObservation) -> bool:
    if observation.later_max_drawdown_pct is None:
        return False
    return observation.later_max_drawdown_pct <= -5.0


def _rate(
    observations: Sequence[AIFeedbackObservation],
    predicate: Callable[[AIFeedbackObservation], bool],
) -> float:
    if not observations:
        return 0.0
    return sum(1 for observation in observations if predicate(observation)) / len(observations)


def _ratio(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return numerator / denominator


def _average(values: Iterable[float]) -> float | None:
    materialized = tuple(values)
    if not materialized:
        return None
    return sum(materialized) / len(materialized)


def _max_safety_state(left: AISafetyState, right: AISafetyState) -> AISafetyState:
    return left if _SAFETY_STATE_RANK[left] >= _SAFETY_STATE_RANK[right] else right
