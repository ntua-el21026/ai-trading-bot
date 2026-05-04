from datetime import UTC, date, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from packages.core.config import ExecutionConfig, SystemConfig, load_app_config
from packages.execution.execution_intent import create_execution_intent, intent_is_expired
from packages.execution.models import ExecutionIntent, OrderLifecycleState
from packages.execution.order_lifecycle import transition_order_lifecycle
from packages.risk.models import RiskAssessment, RiskCheckResult


def _live_system_config() -> SystemConfig:
    config = load_app_config().system
    return SystemConfig.model_validate(
        config.model_dump()
        | {
            "environment": "live",
            "dry_run": False,
            "live_trading_enabled": True,
            "autonomous_execution_enabled": True,
            "autonomy_level": 4,
        }
    )


def _live_execution_config() -> ExecutionConfig:
    config = load_app_config().execution
    return ExecutionConfig.model_validate(
        config.model_dump()
        | {
            "autonomous_execution_enabled": True,
            "allow_live_orders": True,
        }
    )


def _approved_risk(symbol: str = "AAPL") -> RiskAssessment:
    return RiskAssessment(
        symbol=symbol,
        approved=True,
        checks=(
            RiskCheckResult(
                name="test",
                passed=True,
                severity="info",
                reason_code="test_passed",
            ),
        ),
    )


def test_create_execution_intent_requires_approved_risk_and_builds_idempotency_root() -> None:
    intent = create_execution_intent(
        decision_id=uuid4(),
        symbol="AAPL",
        side="buy",
        asset_class="equity",
        quantity=10,
        limit_price=100.0,
        stop_loss_price=98.0,
        strategy_version="regime_filtered_breakout_v0_3",
        risk_config_version="risk_v0_3",
        expires_at=datetime(2026, 5, 4, 15, 0, tzinfo=UTC),
        trade_date=date(2026, 5, 4),
        intent_sequence=1,
        risk_assessment=_approved_risk(),
        system_config=_live_system_config(),
        execution_config=_live_execution_config(),
        temporal_workflow_id="workflow-1",
    )

    assert intent.status == "risk_approved"
    assert intent.entry_order_type == "limit"
    assert intent.time_in_force == "day"
    assert intent.requires_protective_stop is True
    assert intent.client_order_id_root.startswith("regime_filtered_breakout_v0_3-AAPL-buy-")
    assert intent.temporal_workflow_id == "workflow-1"


def test_create_execution_intent_rejects_failed_risk_assessment() -> None:
    config = load_app_config()
    failed_risk = RiskAssessment(
        symbol="AAPL",
        approved=False,
        checks=(RiskCheckResult(name="risk", passed=False, reason_code="risk_failed"),),
    )

    with pytest.raises(ValueError, match="approved risk assessment"):
        create_execution_intent(
            decision_id=uuid4(),
            symbol="AAPL",
            side="buy",
            asset_class="equity",
            quantity=10,
            limit_price=100.0,
            stop_loss_price=98.0,
            strategy_version=config.strategy.name,
            risk_config_version="risk_v0_3",
            expires_at=datetime(2026, 5, 4, 15, 0, tzinfo=UTC),
            trade_date=date(2026, 5, 4),
            intent_sequence=1,
            risk_assessment=failed_risk,
            system_config=_live_system_config(),
            execution_config=_live_execution_config(),
        )


def test_execution_intent_rejects_missing_protective_stop() -> None:
    with pytest.raises(ValidationError, match="protective stop is required"):
        ExecutionIntent(
            decision_id=uuid4(),
            symbol="AAPL",
            side="buy",
            asset_class="equity",
            quantity=10,
            entry_order_type="limit",
            limit_price=100.0,
            stop_loss_price=None,
            time_in_force="day",
            strategy_version="regime_filtered_breakout_v0_3",
            risk_config_version="risk_v0_3",
            autonomy_level=4,
            requires_protective_stop=True,
            max_acceptable_slippage_bps=25,
            expires_at=datetime(2026, 5, 4, 15, 0, tzinfo=UTC),
            client_order_id_root="root",
        )


def test_intent_expiration_is_checked_with_explicit_time() -> None:
    intent = ExecutionIntent(
        decision_id=uuid4(),
        symbol="AAPL",
        side="buy",
        asset_class="equity",
        quantity=10,
        entry_order_type="limit",
        limit_price=100.0,
        stop_loss_price=98.0,
        time_in_force="day",
        strategy_version="regime_filtered_breakout_v0_3",
        risk_config_version="risk_v0_3",
        autonomy_level=4,
        requires_protective_stop=True,
        max_acceptable_slippage_bps=25,
        expires_at=datetime(2026, 5, 4, 15, 0, tzinfo=UTC),
        client_order_id_root="root",
    )

    assert intent_is_expired(intent, as_of=datetime(2026, 5, 4, 15, 0, tzinfo=UTC)) is True


def test_order_lifecycle_transition_validation_is_passive() -> None:
    state = OrderLifecycleState(client_order_id="order-1")
    transition = transition_order_lifecycle(state, "risk_checked")

    assert transition.accepted is True
    assert transition.state.status == "risk_checked"

    invalid = transition_order_lifecycle(transition.state, "protected")

    assert invalid.accepted is False
    assert invalid.rejection is not None
    assert invalid.rejection.reason_code == "invalid_order_lifecycle_transition"

