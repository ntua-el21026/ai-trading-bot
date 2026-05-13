from pathlib import Path

import pytest

from packages.core.config import ConfigLoadError, load_app_config


def test_load_app_config_uses_safe_defaults() -> None:
    config = load_app_config()

    assert config.system.environment == "paper"
    assert config.system.dry_run is True
    assert config.system.live_trading_enabled is False
    assert config.system.autonomous_execution_enabled is False
    assert config.execution.allow_live_orders is False
    assert config.execution.require_execution_intent is True
    assert config.execution.require_passed_risk_check is True
    assert config.execution.require_broker_reconciliation_before_order is True
    assert config.execution.require_protective_stop is True
    assert config.execution.first_session_max_qty == 1
    assert config.execution.first_session_absolute_max_notional_usd == 500.0
    assert config.scale_in.enabled_for_paper_validation is True
    assert config.scale_in.max_entries_per_symbol == 2
    assert config.scale_in.max_add_entries_per_symbol == 1
    assert config.scale_in.max_new_entry_qty == 1
    assert config.scale_in.max_scale_in_qty == 1
    assert config.scale_in.max_total_symbol_qty == 2
    assert config.scale_in.max_pending_entry_orders_per_symbol == 0
    assert config.scale_in.max_unresolved_incidents_per_symbol == 0
    assert config.scale_in.require_existing_stop_verified is True
    assert config.scale_in.require_add_on_signal is True
    assert config.scale_in.require_no_pending_entry_order is True
    assert config.scale_in.require_no_unresolved_symbol_incident is True
    assert config.scale_in.protective_stop_required_before_scale_in is True
    assert config.scale_in.protective_stop_required_after_scale_in is True
    assert config.scale_in.stop_policy == "additive_stop_for_added_quantity"
    assert config.scale_in.allow_stop_replacement is False
    assert config.scale_in.allow_stop_cancel_before_scale_in is False
    assert config.scale_in.block_if_protected_quantity_below_position_quantity is True
    assert config.risk_level_4_micro_live.allow_margin is False
    assert config.risk_level_4_micro_live.allow_shorting is False
    assert config.risk_level_4_micro_live.allow_options is False
    assert config.risk_level_4_micro_live.allow_futures is False
    assert config.risk_level_4_micro_live.allow_crypto is False
    assert config.risk_level_4_micro_live.allow_prediction_markets is False
    assert config.risk_level_4_micro_live.require_protective_stop is True
    assert config.ai.allow_ai_to_create_orders is False
    assert config.ai.allow_ai_to_modify_strategy is False
    assert config.ai.allow_ai_to_modify_risk_limits is False
    assert config.ai.analyze_full_universe is False
    assert config.ai.analyze_deterministic_shortlist_only is True
    assert config.ai.news_provider_primary == "marketaux"
    assert config.ai.news_provider_fallback == "alpha_vantage"
    assert config.ai.news_enable_openai_web_fallback is False
    assert config.ai.ai_require_structured_output is True
    assert config.ai.ai_neutral_fallback_on_error is True
    assert config.ai.ai_enable_escalation is False
    assert config.ai.ai_feedback_enabled is True


def test_load_app_config_rejects_missing_files(tmp_path: Path) -> None:
    with pytest.raises(ConfigLoadError, match="missing required config file"):
        load_app_config(tmp_path)


def test_logging_can_be_configured() -> None:
    pytest.importorskip("structlog")
    from packages.core.logging import configure_logging, get_logger

    configure_logging("INFO", json_logs=True)
    logger = get_logger("foundation-test")

    assert logger is not None
