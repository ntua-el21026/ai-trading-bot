from packages.core.config import ExecutionConfig, SystemConfig, load_app_config
from packages.risk.checks import evaluate_new_risk_order
from packages.risk.kill_switch import pause_new_risk, running_state
from packages.risk.models import NewRiskOrderInput


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


def _order_input(**updates: object) -> NewRiskOrderInput:
    data = {
        "symbol": "AAPL",
        "asset_class": "equity",
        "quantity": 10,
        "entry_price": 100.0,
        "stop_loss_price": 98.0,
        "account_equity": 100_000.0,
        "cash": 98_000.0,
        "current_gross_exposure": 10_000.0,
        "current_deployable_capital": 10_000.0,
        "current_open_positions": 4,
        "current_sector_exposure_pct": 0.02,
        "daily_loss_pct": 0.0,
        "weekly_loss_pct": 0.0,
        "monthly_loss_pct": 0.0,
        "data_is_fresh": True,
        "market_session_valid": True,
        "broker_reconciliation_clean": True,
        "broker_account_environment": "live",
        "kill_switch": running_state(),
        "active_duplicate_intent": False,
        "temporal_workflow_consistent": True,
        "system_health_ok": True,
    }
    data.update(updates)
    return NewRiskOrderInput.model_validate(data)


def test_new_risk_order_passes_when_all_required_gates_are_clean() -> None:
    config = load_app_config()

    assessment = evaluate_new_risk_order(
        _order_input(),
        system_config=_live_system_config(),
        execution_config=_live_execution_config(),
        risk_config=config.risk_level_4_micro_live,
        live_universe_config=config.live_universe,
    )

    assert assessment.approved is True
    assert assessment.rejection_reasons == ()


def test_default_safe_config_rejects_autonomous_new_risk() -> None:
    config = load_app_config()

    assessment = evaluate_new_risk_order(
        _order_input(broker_account_environment="paper"),
        system_config=config.system,
        execution_config=config.execution,
        risk_config=config.risk_level_4_micro_live,
        live_universe_config=config.live_universe,
    )

    assert assessment.approved is False
    assert "system_autonomous_execution_disabled" in assessment.rejection_reasons


def test_new_risk_order_rejects_stale_data_kill_switch_and_duplicate_intent() -> None:
    config = load_app_config()

    assessment = evaluate_new_risk_order(
        _order_input(
            data_is_fresh=False,
            kill_switch=pause_new_risk("operator_pause"),
            active_duplicate_intent=True,
        ),
        system_config=_live_system_config(),
        execution_config=_live_execution_config(),
        risk_config=config.risk_level_4_micro_live,
        live_universe_config=config.live_universe,
    )

    assert assessment.approved is False
    assert "stale_market_data" in assessment.rejection_reasons
    assert "kill_switch_paused_new_risk" in assessment.rejection_reasons
    assert "active_duplicate_intent" in assessment.rejection_reasons


def test_new_risk_order_rejects_exposure_and_loss_limit_breaches() -> None:
    config = load_app_config()

    assessment = evaluate_new_risk_order(
        _order_input(
            quantity=5_000,
            daily_loss_pct=config.risk_level_4_micro_live.max_daily_loss_pct,
        ),
        system_config=_live_system_config(),
        execution_config=_live_execution_config(),
        risk_config=config.risk_level_4_micro_live,
        live_universe_config=config.live_universe,
    )

    assert assessment.approved is False
    assert "daily_loss_limit_breached" in assessment.rejection_reasons
    assert "max_position_size_exceeded" in assessment.rejection_reasons
    assert "max_gross_exposure_exceeded" in assessment.rejection_reasons

