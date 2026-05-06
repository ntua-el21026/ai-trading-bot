"""Deterministic fake/local paper dry-run fixtures."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

from packages.paper.models import DryRunFailureMode, DryRunInput, DryRunScenario

DRY_RUN_STARTED_AT = datetime(2026, 5, 6, 14, 0, tzinfo=UTC)
DRY_RUN_COMPLETED_AT = DRY_RUN_STARTED_AT + timedelta(minutes=10)


def base_dry_run_scenario(
    *,
    scenario_id: str = "happy_path",
    name: str = "Happy path fake/local paper dry run",
    failure_mode: DryRunFailureMode = "none",
    quantity: int = 10,
    filled_quantity: int = 10,
) -> DryRunScenario:
    return DryRunScenario(
        scenario_id=scenario_id,
        name=name,
        failure_mode=failure_mode,
        symbol="AAPL",
        asset_class="equity",
        trade_date=date(2026, 5, 6),
        quantity=quantity,
        filled_quantity=filled_quantity,
        limit_price=180.50,
        stop_loss_price=174.20,
        account_equity=100_000.0,
        cash=98_000.0,
        technical_score=82.0,
        relative_strength_score=78.0,
    )


def scenario_by_id(scenario_id: str) -> DryRunScenario:
    scenarios = {
        "happy_path": base_dry_run_scenario(),
        "risk_rejection": base_dry_run_scenario(
            scenario_id="risk_rejection",
            name="Risk rejection fake/local paper dry run",
            failure_mode="risk_rejection",
        ),
        "invalid_ai_output_neutral": base_dry_run_scenario(
            scenario_id="invalid_ai_output_neutral",
            name="Invalid AI output neutral fallback dry run",
            failure_mode="invalid_ai_output_neutral",
        ),
        "duplicate_active_intent": base_dry_run_scenario(
            scenario_id="duplicate_active_intent",
            name="Duplicate active intent dry run",
            failure_mode="duplicate_active_intent",
        ),
        "broker_ambiguity": base_dry_run_scenario(
            scenario_id="broker_ambiguity",
            name="Broker ambiguous fake submit dry run",
            failure_mode="broker_ambiguity",
        ),
        "partial_fill": base_dry_run_scenario(
            scenario_id="partial_fill",
            name="Partial fill matched protective stop dry run",
            failure_mode="partial_fill",
            filled_quantity=4,
        ),
        "missing_protective_stop": base_dry_run_scenario(
            scenario_id="missing_protective_stop",
            name="Missing protective stop incident dry run",
            failure_mode="missing_protective_stop",
        ),
        "reconciliation_mismatch": base_dry_run_scenario(
            scenario_id="reconciliation_mismatch",
            name="Reconciliation mismatch dry run",
            failure_mode="reconciliation_mismatch",
        ),
        "kill_switch_pause_new_risk": base_dry_run_scenario(
            scenario_id="kill_switch_pause_new_risk",
            name="Kill-switch pause-new-risk dry run",
            failure_mode="kill_switch_pause_new_risk",
        ),
        "stale_data": base_dry_run_scenario(
            scenario_id="stale_data",
            name="Stale data rejection dry run",
            failure_mode="stale_data",
        ),
    }
    try:
        return scenarios[scenario_id]
    except KeyError as exc:
        raise ValueError(f"unknown dry-run scenario_id: {scenario_id}") from exc


def default_dry_run_input(scenario_id: str = "happy_path") -> DryRunInput:
    return DryRunInput(
        scenario=scenario_by_id(scenario_id),
        started_at=DRY_RUN_STARTED_AT,
        completed_at=DRY_RUN_COMPLETED_AT,
    )
