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
    assert config.market_data.primary_signal_provider == "tiingo"
    assert config.market_data.primary_signal_feed == "eod"
    assert config.market_data.primary_signal_mode == "historical_completed_daily_bars"
    assert config.market_data.require_non_iex_primary_signal_data is True
    assert config.market_data.fail_if_primary_signal_feed_is_iex is True
    assert config.market_data.allow_iex_only_for_frozen_validation is False
    assert config.market_data.non_iex_primary_signal_data_verified is False
    assert config.market_data.non_iex_primary_signal_data_waiver_enabled is False
    assert config.market_data.tiingo is not None
    assert config.market_data.tiingo.api_key_env == "TIINGO_API_KEY"
    assert config.market_data.tiingo.min_history_bars == 260
    assert config.market_data.tiingo.validation_sample_symbols == (
        "SPY",
        "QQQ",
        "AAPL",
        "MSFT",
        "XLK",
    )
    assert config.market_data.alpaca is not None
    assert config.market_data.alpaca.fallback_allowed_for_execution_broker is True
    assert config.market_data.alpaca.fallback_allowed_for_signal_generation is False
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
    assert config.validation.active_spec_version == "v0.6"
    assert config.validation.frozen_validation_enabled is False
    assert config.validation.frozen_validation_start_allowed is False
    assert config.validation.flat_start_required is True
    assert config.validation.carry_in_positions_allowed is False
    assert config.validation.validation_clock_started is False
    assert config.validation.short_policy.enabled_at_validation_start is True
    assert config.validation.short_policy.real_short_lifecycle_proof_completed_by_m44d is True
    assert config.validation.short_policy.paper_only is True
    assert config.validation.short_policy.live_shorting_enabled is False
    assert config.validation.scale_in_policy.enabled_at_validation_start is False
    assert config.validation.scale_in_policy.required_clean_scheduled_runs_before_enable == 1
    assert config.validation.scale_in_policy.require_real_broker_additive_stop_proof is True
    assert config.validation.scale_in_policy.real_additive_stop_proof_completed_by_m44d is False
    assert config.validation.scale_in_policy.short_scale_in_enabled_at_validation_start is False
    assert config.validation.exits.app_level_trailing_stop is False
    assert config.validation_risk.max_scale_ins_per_day_at_start == 0
    assert config.validation_risk.max_open_positions == 4
    assert config.shorts.enabled is True
    assert config.shorts.enabled_at_validation_start is True
    assert config.shorts.real_short_lifecycle_proof_completed_by_m44d is True
    assert config.shorts.paper_only_short_exposure is True
    assert config.shorts.allow_live_shorting is False
    assert config.shorts.short_scale_in_enabled_at_validation_start is False
    assert config.shorts.eligible_symbols == ("SPY", "QQQ", "DIA", "IWM")
    assert config.universe_buckets.short_eligible_broad_etfs == ("SPY", "QQQ", "DIA", "IWM")
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
    assert config.validation_ai.negative_only is True
    assert config.validation_ai.ai_positive_ranking_enabled is False
    assert config.validation_ai.ai_may_increase_size is False
    assert config.validation_ai.ai_may_authorize_trade is False
    assert config.validation_ai.ai_may_authorize_scale_in is False
    assert config.validation_ai.ai_may_authorize_shorts is False


def test_load_app_config_rejects_missing_files(tmp_path: Path) -> None:
    with pytest.raises(ConfigLoadError, match="missing required config file"):
        load_app_config(tmp_path)


def test_logging_can_be_configured() -> None:
    pytest.importorskip("structlog")
    from packages.core.logging import configure_logging, get_logger

    configure_logging("INFO", json_logs=True)
    logger = get_logger("foundation-test")

    assert logger is not None
