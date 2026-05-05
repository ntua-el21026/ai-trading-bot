import json
from datetime import UTC, datetime, timedelta

from apps.api.app.control_plane import CONTROL_ACTION_SIGNAL_MAP
from apps.workers.app.signals import MANUAL_KILL_SWITCH
from packages.ai.models import AI_PROMPT_VERSION, AI_SCHEMA_VERSION, NEUTRAL_AI_SCORE
from packages.ai.parser import parse_ai_trade_research_or_fallback
from packages.broker.models import (
    BrokerAccountSnapshot,
    BrokerOrder,
    BrokerPosition,
    BrokerSnapshot,
)
from packages.core.config import load_app_config
from packages.execution.models import OrderLifecycleState
from packages.execution.order_lifecycle import transition_order_lifecycle
from packages.reconciliation.models import InternalAccountSnapshot, InternalLedgerSnapshot
from packages.reconciliation.service import compare_broker_and_internal
from packages.validation.failures import (
    REQUIRED_FAILURE_SCENARIOS,
    default_failure_simulation_scenarios,
)

AS_OF = datetime(2026, 5, 5, 12, 0, tzinfo=UTC)


def test_failure_simulation_catalog_covers_required_spec_scenarios_without_external_calls() -> None:
    scenarios = default_failure_simulation_scenarios()

    assert tuple(scenario.scenario_type for scenario in scenarios) == REQUIRED_FAILURE_SCENARIOS
    assert all(scenario.external_calls_required is False for scenario in scenarios)
    assert {
        scenario.scenario_type
        for scenario in scenarios
        if scenario.pause_new_risk_expected
    } >= {
        "missing_protective_stop",
        "broker_position_without_internal_position",
        "internal_position_without_broker_position",
        "unexpected_short_position",
        "database_outage_placeholder",
        "temporal_worker_unavailable_placeholder",
        "kill_switch_activation",
        "order_submitted_not_recorded_placeholder",
    }


def test_invalid_ai_json_and_schema_violation_failure_simulations_fall_back_neutral() -> None:
    invalid_json = parse_ai_trade_research_or_fallback(
        "{not-json",
        symbol="AAPL",
        analysis_at=AS_OF,
        prompt_version=AI_PROMPT_VERSION,
        schema_version=AI_SCHEMA_VERSION,
        model_version="fixture-model",
    )
    invalid_schema = parse_ai_trade_research_or_fallback(
        json.dumps(
            {
                "symbol": "AAPL",
                "analysis_at": AS_OF.isoformat(),
                "schema_version": AI_SCHEMA_VERSION,
                "prompt_version": AI_PROMPT_VERSION,
                "model_version": "fixture-model",
                "news_state": "found",
                "events": [],
                "citations": [],
                "hard_block": False,
                "ai_score": 101,
                "size_multiplier": 1.0,
                "explanation": "invalid",
                "fallback": False,
                "fallback_reason": "none",
            }
        ),
        symbol="AAPL",
        analysis_at=AS_OF,
        prompt_version=AI_PROMPT_VERSION,
        schema_version=AI_SCHEMA_VERSION,
        model_version="fixture-model",
    )

    assert invalid_json.ai_score == NEUTRAL_AI_SCORE
    assert invalid_json.hard_block is False
    assert invalid_json.fallback_reason == "invalid_json"
    assert invalid_schema.ai_score == NEUTRAL_AI_SCORE
    assert invalid_schema.hard_block is False
    assert invalid_schema.fallback_reason == "schema_violation"


def test_partial_fill_failure_simulation_is_modeled_in_lifecycle_contract() -> None:
    state = OrderLifecycleState(client_order_id="client-order-1", status="acknowledged")

    result = transition_order_lifecycle(state, "partially_filled")

    assert result.accepted is True
    assert result.state.status == "partially_filled"


def test_unknown_open_broker_order_and_position_mismatch_pause_new_risk() -> None:
    account = BrokerAccountSnapshot(
        account_id="paper-account",
        environment="paper",
        equity=100_000.0,
        cash=90_000.0,
        as_of=AS_OF,
    )
    unknown_order = BrokerOrder(
        broker_order_id="broker-order-1",
        client_order_id="unknown-client-order",
        symbol="AAPL",
        side="buy",
        asset_class="equity",
        quantity=10.0,
        filled_quantity=0.0,
        order_type="limit",
        time_in_force="day",
        status="accepted",
        limit_price=100.0,
        purpose="entry",
    )
    broker_snapshot = BrokerSnapshot(
        account=account,
        open_orders=(unknown_order,),
        positions=(
            BrokerPosition(
                symbol="AAPL",
                asset_class="equity",
                quantity=10.0,
                avg_entry_price=100.0,
                opened_at=AS_OF - timedelta(seconds=40),
            ),
        ),
        protective_stops=(),
        as_of=AS_OF,
    )
    internal_snapshot = InternalLedgerSnapshot(
        account=InternalAccountSnapshot(equity=100_000.0, cash=90_000.0, as_of=AS_OF),
        as_of=AS_OF,
    )

    result = compare_broker_and_internal(
        broker_snapshot=broker_snapshot,
        internal_snapshot=internal_snapshot,
        as_of=AS_OF,
        protective_stop_config=load_app_config().protective_stop,
    )
    mismatch_types = {mismatch.mismatch_type for mismatch in result.mismatches}

    assert "unknown_open_broker_order" in mismatch_types
    assert "broker_position_without_internal_position" in mismatch_types
    assert result.pause_new_risk_recommended is True


def test_kill_switch_control_failure_simulation_maps_to_existing_signal() -> None:
    assert CONTROL_ACTION_SIGNAL_MAP["manual_kill_switch"] == MANUAL_KILL_SWITCH
