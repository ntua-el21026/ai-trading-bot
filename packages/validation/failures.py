"""Failure simulation contracts for validation tests."""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from packages.validation.models import ValidationModel

FailureScenarioType = Literal[
    "stale_market_data",
    "invalid_ai_json",
    "ai_provider_outage",
    "broker_api_timeout_ambiguous_state",
    "duplicate_order_attempt",
    "partial_fill",
    "missing_protective_stop",
    "broker_position_without_internal_position",
    "internal_position_without_broker_position",
    "unexpected_short_position",
    "database_outage_placeholder",
    "temporal_worker_unavailable_placeholder",
    "kill_switch_activation",
    "order_submitted_not_recorded_placeholder",
]
FailureExpectedOutcome = Literal[
    "reject_new_risk",
    "neutral_ai_fallback",
    "pause_new_risk",
    "manual_review_required",
    "lifecycle_partial_fill",
    "placeholder_incident",
]

REQUIRED_FAILURE_SCENARIOS: tuple[FailureScenarioType, ...] = (
    "stale_market_data",
    "invalid_ai_json",
    "ai_provider_outage",
    "broker_api_timeout_ambiguous_state",
    "duplicate_order_attempt",
    "partial_fill",
    "missing_protective_stop",
    "broker_position_without_internal_position",
    "internal_position_without_broker_position",
    "unexpected_short_position",
    "database_outage_placeholder",
    "temporal_worker_unavailable_placeholder",
    "kill_switch_activation",
    "order_submitted_not_recorded_placeholder",
)


class FailureSimulationScenario(ValidationModel):
    scenario_type: FailureScenarioType
    expected_outcome: FailureExpectedOutcome
    expected_reason_code: str
    pause_new_risk_expected: bool = False
    kill_switch_expected: bool = False
    external_calls_required: bool = False
    notes: str = Field(default="")


def default_failure_simulation_scenarios() -> tuple[FailureSimulationScenario, ...]:
    return (
        FailureSimulationScenario(
            scenario_type="stale_market_data",
            expected_outcome="reject_new_risk",
            expected_reason_code="stale_market_data",
        ),
        FailureSimulationScenario(
            scenario_type="invalid_ai_json",
            expected_outcome="neutral_ai_fallback",
            expected_reason_code="invalid_json",
        ),
        FailureSimulationScenario(
            scenario_type="ai_provider_outage",
            expected_outcome="neutral_ai_fallback",
            expected_reason_code="ai_provider_outage",
        ),
        FailureSimulationScenario(
            scenario_type="broker_api_timeout_ambiguous_state",
            expected_outcome="manual_review_required",
            expected_reason_code="broker_ambiguity",
            pause_new_risk_expected=True,
        ),
        FailureSimulationScenario(
            scenario_type="duplicate_order_attempt",
            expected_outcome="reject_new_risk",
            expected_reason_code="duplicate_active_intent",
        ),
        FailureSimulationScenario(
            scenario_type="partial_fill",
            expected_outcome="lifecycle_partial_fill",
            expected_reason_code="partially_filled",
        ),
        FailureSimulationScenario(
            scenario_type="missing_protective_stop",
            expected_outcome="pause_new_risk",
            expected_reason_code="missing_protective_stop",
            pause_new_risk_expected=True,
            kill_switch_expected=True,
        ),
        FailureSimulationScenario(
            scenario_type="broker_position_without_internal_position",
            expected_outcome="pause_new_risk",
            expected_reason_code="broker_position_without_internal_position",
            pause_new_risk_expected=True,
        ),
        FailureSimulationScenario(
            scenario_type="internal_position_without_broker_position",
            expected_outcome="pause_new_risk",
            expected_reason_code="internal_position_without_broker_position",
            pause_new_risk_expected=True,
        ),
        FailureSimulationScenario(
            scenario_type="unexpected_short_position",
            expected_outcome="pause_new_risk",
            expected_reason_code="unexpected_short_position",
            pause_new_risk_expected=True,
        ),
        FailureSimulationScenario(
            scenario_type="database_outage_placeholder",
            expected_outcome="placeholder_incident",
            expected_reason_code="database_outage",
            pause_new_risk_expected=True,
        ),
        FailureSimulationScenario(
            scenario_type="temporal_worker_unavailable_placeholder",
            expected_outcome="placeholder_incident",
            expected_reason_code="temporal_worker_unavailable",
            pause_new_risk_expected=True,
        ),
        FailureSimulationScenario(
            scenario_type="kill_switch_activation",
            expected_outcome="pause_new_risk",
            expected_reason_code="manual_kill_switch",
            pause_new_risk_expected=True,
            kill_switch_expected=True,
        ),
        FailureSimulationScenario(
            scenario_type="order_submitted_not_recorded_placeholder",
            expected_outcome="manual_review_required",
            expected_reason_code="order_submitted_not_recorded",
            pause_new_risk_expected=True,
        ),
    )
