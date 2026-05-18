"""Typed configuration loading for repository foundation files."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any, Literal, Self

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

CONFIG_FILES: tuple[str, ...] = (
    "system.yaml",
    "temporal.yaml",
    "market_data.yaml",
    "execution.yaml",
    "universe.yaml",
    "strategy.yaml",
    "regime.yaml",
    "risk.yaml",
    "ai.yaml",
)


class ConfigLoadError(RuntimeError):
    """Raised when configuration files cannot be loaded or validated."""


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class SystemConfig(StrictModel):
    environment: Literal["paper", "live"]
    timezone_market: str
    timezone_user: str
    dry_run: bool
    live_trading_enabled: bool
    autonomous_execution_enabled: bool
    autonomy_level: int = Field(ge=0, le=5)
    kill_switch_enabled: bool
    require_broker_reconciliation: bool
    pause_on_reconciliation_error: bool

    @model_validator(mode="after")
    def validate_safe_environment(self) -> Self:
        if self.environment == "paper" and self.live_trading_enabled:
            raise ValueError("paper environment cannot have live_trading_enabled=true")
        if self.live_trading_enabled and self.dry_run:
            raise ValueError("live_trading_enabled=true cannot be combined with dry_run=true")
        return self


class TemporalTaskQueues(StrictModel):
    market_data: str
    strategy: str
    ai_research: str
    execution: str
    reconciliation: str
    reporting: str


class TemporalSchedules(StrictModel):
    daily_data_refresh: str
    eod_signal_generation: str
    ai_shortlist_research: str
    trade_plan_snapshot: str
    sanity_reconciliation: str


class RetryDefaults(StrictModel):
    initial_interval_seconds: int = Field(gt=0)
    backoff_coefficient: float = Field(ge=1.0)
    maximum_interval_seconds: int = Field(gt=0)
    maximum_attempts: int = Field(gt=0)


class TemporalConfig(StrictModel):
    address: str = "localhost:7233"
    namespace: str
    task_queues: TemporalTaskQueues
    schedules: TemporalSchedules
    retry_defaults: RetryDefaults


class TiingoMarketDataConfig(StrictModel):
    enabled: bool
    api_key_env: str
    base_url: str
    eod_endpoint_template: str
    adjusted_prices_required: bool
    completed_daily_bars_only: bool
    min_history_bars: int = Field(ge=260)
    validation_sample_symbols: tuple[str, ...]

    @field_validator("api_key_env")
    @classmethod
    def validate_api_key_env(cls, api_key_env: str) -> str:
        normalized = api_key_env.strip()
        if normalized != "TIINGO_API_KEY":
            raise ValueError("Tiingo token must be loaded from TIINGO_API_KEY")
        return normalized

    @field_validator("validation_sample_symbols")
    @classmethod
    def validate_validation_sample_symbols(cls, symbols: tuple[str, ...]) -> tuple[str, ...]:
        normalized = tuple(symbol.strip().upper() for symbol in symbols if symbol.strip())
        if not normalized:
            raise ValueError("Tiingo validation sample symbols are required")
        if any(symbol != symbol.upper() for symbol in normalized):
            raise ValueError("Tiingo validation sample symbols must be uppercase")
        return normalized


class AlpacaMarketDataFallbackConfig(StrictModel):
    fallback_allowed_for_execution_broker: bool
    fallback_allowed_for_signal_generation: bool
    iex_allowed_for_signal_generation: bool

    @model_validator(mode="after")
    def validate_signal_generation_fallback(self) -> Self:
        if self.fallback_allowed_for_signal_generation:
            raise ValueError("Alpaca fallback is not allowed for frozen signal generation")
        if self.iex_allowed_for_signal_generation:
            raise ValueError("Alpaca IEX is not allowed for frozen signal generation")
        return self


class MarketDataConfig(StrictModel):
    primary_signal_provider: str
    primary_signal_feed: Literal["sip", "iex", "delayed_sip", "eod", "other"]
    primary_signal_mode: Literal[
        "historical_completed_daily_bars",
        "realtime_bars",
        "delayed_historical_bars",
        "other",
    ] = "other"
    require_non_iex_primary_signal_data: bool
    fail_if_primary_signal_feed_is_iex: bool
    allow_iex_only_for_frozen_validation: bool
    allow_delayed_sip_for_signal_generation: bool = False
    non_iex_primary_signal_data_verified: bool = False
    non_iex_primary_signal_data_waiver_enabled: bool = False
    non_iex_primary_signal_data_waiver_reason: str = ""
    tiingo: TiingoMarketDataConfig | None = None
    alpaca: AlpacaMarketDataFallbackConfig | None = None

    @field_validator("primary_signal_provider", mode="before")
    @classmethod
    def normalize_provider(cls, provider: object) -> str:
        normalized = str(provider).strip().lower()
        if not normalized:
            raise ValueError("primary signal provider is required")
        return normalized

    @field_validator("primary_signal_feed", mode="before")
    @classmethod
    def normalize_feed(cls, feed: object) -> str:
        normalized = str(feed).strip().lower().replace("-", "_")
        if normalized == "sip_delayed":
            normalized = "delayed_sip"
        return normalized

    @model_validator(mode="after")
    def validate_market_data_policy(self) -> Self:
        if not self.require_non_iex_primary_signal_data:
            raise ValueError("v0.5 requires non-IEX primary signal data before M45")
        if not self.fail_if_primary_signal_feed_is_iex:
            raise ValueError("IEX-only primary signal data must fail the M45 gate")
        if self.primary_signal_provider == "tiingo":
            if self.primary_signal_feed != "eod":
                raise ValueError("Tiingo primary signal data must use EOD feed")
            if self.primary_signal_mode != "historical_completed_daily_bars":
                raise ValueError("Tiingo frozen signals must use completed daily bars")
            if self.tiingo is None or not self.tiingo.enabled:
                raise ValueError("Tiingo config must be enabled for Tiingo primary signal data")
        if self.allow_iex_only_for_frozen_validation and not (
            self.non_iex_primary_signal_data_waiver_enabled
            and self.non_iex_primary_signal_data_waiver_reason.strip()
        ):
            raise ValueError("IEX-only validation requires an explicit waiver reason")
        if self.primary_signal_feed == "delayed_sip" and not (
            self.allow_delayed_sip_for_signal_generation
            or self.non_iex_primary_signal_data_waiver_enabled
        ):
            # Delayed SIP is classified explicitly by the M44B gate, but config loading should
            # remain conservative instead of silently equating it to real-time SIP.
            return self
        if self.non_iex_primary_signal_data_verified and self.primary_signal_feed == "iex":
            raise ValueError("IEX-only feed cannot be marked non-IEX verified")
        return self


class ExecutionConfig(StrictModel):
    autonomous_execution_enabled: bool
    allow_live_orders: bool
    require_execution_intent: bool
    require_passed_risk_check: bool
    require_broker_reconciliation_before_order: bool
    require_protective_stop: bool
    entry_order_type: Literal["limit"]
    entry_time_in_force: Literal["day"]
    entry_window_start_et: str
    entry_window_end_et: str
    unfilled_entry_cancel_time_et: str
    max_acceptable_slippage_bps: int = Field(ge=0)
    first_session_max_qty: int = Field(gt=0)
    first_session_absolute_max_notional_usd: float = Field(gt=0)
    pause_on_order_submit_failure: bool
    pause_on_stop_failure: bool
    notify_on_every_order: bool

    @model_validator(mode="after")
    def validate_execution_gates(self) -> Self:
        if self.allow_live_orders and not self.require_execution_intent:
            raise ValueError("live orders cannot be allowed without required execution intents")
        if self.allow_live_orders and not self.require_passed_risk_check:
            raise ValueError("live orders cannot be allowed without required risk checks")
        if self.allow_live_orders and not self.require_broker_reconciliation_before_order:
            raise ValueError("live orders cannot be allowed without broker reconciliation")
        if self.allow_live_orders and not self.require_protective_stop:
            raise ValueError("live orders cannot be allowed without protective stops")
        if self.first_session_max_qty != 1:
            raise ValueError("first controlled paper session max quantity must remain 1")
        if self.first_session_absolute_max_notional_usd > 500.0:
            raise ValueError("first controlled paper session notional ceiling exceeds 500 USD")
        return self


class ProtectiveStopConfig(StrictModel):
    warning_after_seconds: int = Field(gt=0)
    critical_after_seconds: int = Field(gt=0)
    flatten_after_seconds: int = Field(gt=0)
    max_retries: int = Field(ge=0)

    @model_validator(mode="after")
    def validate_threshold_order(self) -> Self:
        if not (
            self.warning_after_seconds
            < self.critical_after_seconds
            < self.flatten_after_seconds
        ):
            raise ValueError("protective stop thresholds must increase from warning to flatten")
        return self


class ScaleInConfig(StrictModel):
    enabled_for_paper_validation: bool
    max_entries_per_symbol: int = Field(ge=1)
    max_add_entries_per_symbol: int = Field(ge=0)
    max_new_entry_qty: int = Field(gt=0)
    max_scale_in_qty: int = Field(gt=0)
    max_total_symbol_qty: int = Field(gt=0)
    max_pending_entry_orders_per_symbol: int = Field(ge=0)
    max_unresolved_incidents_per_symbol: int = Field(ge=0)
    require_existing_stop_verified: bool
    require_add_on_signal: bool
    require_no_pending_entry_order: bool
    require_no_unresolved_symbol_incident: bool
    protective_stop_required_before_scale_in: bool
    protective_stop_required_after_scale_in: bool
    stop_policy: Literal["additive_stop_for_added_quantity"]
    allow_stop_replacement: bool
    allow_stop_cancel_before_scale_in: bool
    block_if_protected_quantity_below_position_quantity: bool

    @model_validator(mode="after")
    def validate_scale_in_bounds(self) -> Self:
        if self.max_entries_per_symbol != 2:
            raise ValueError("paper-validation scale-in must allow exactly two entries per symbol")
        if self.max_add_entries_per_symbol > self.max_entries_per_symbol - 1:
            raise ValueError("add-entry cap cannot exceed total entries minus initial entry")
        if self.max_total_symbol_qty < self.max_new_entry_qty:
            raise ValueError("total symbol quantity cap cannot be below initial entry quantity")
        if self.max_total_symbol_qty < self.max_scale_in_qty:
            raise ValueError("total symbol quantity cap cannot be below scale-in quantity")
        if self.allow_stop_replacement:
            raise ValueError("scale-in stop replacement is not allowed")
        if self.allow_stop_cancel_before_scale_in:
            raise ValueError("scale-in cannot cancel stops before add-on entry")
        if not self.protective_stop_required_before_scale_in:
            raise ValueError("scale-in requires verified existing protective stops")
        if not self.protective_stop_required_after_scale_in:
            raise ValueError("scale-in requires protective stop after added fill")
        if not self.block_if_protected_quantity_below_position_quantity:
            raise ValueError("under-protected positions must block scale-in")
        return self


class ValidationUniversePolicy(StrictModel):
    include_full_allowed_universe: bool
    force_trades: bool


class ValidationLongPolicy(StrictModel):
    enabled: bool
    active_breakout_lookback: int = Field(gt=0)
    research_breakout_lookbacks: tuple[int, ...]
    same_day_reentry_forbidden: bool
    early_close_new_entries_allowed: bool

    @model_validator(mode="after")
    def validate_long_policy(self) -> Self:
        if not self.enabled:
            raise ValueError("v0.5 frozen validation starts with long policy enabled")
        if self.active_breakout_lookback != 20:
            raise ValueError("v0.5 frozen validation active breakout must be 20D")
        if 55 not in self.research_breakout_lookbacks:
            raise ValueError("v0.5 must keep 55D breakout research-only")
        if not self.same_day_reentry_forbidden:
            raise ValueError("same-day re-entry must be forbidden at validation start")
        if self.early_close_new_entries_allowed:
            raise ValueError("early-close new entries must be disabled at validation start")
        return self


class ValidationShortPolicy(StrictModel):
    enabled_at_validation_start: bool
    implementation_present: bool
    activation_requires_future_rehearsal: bool

    @model_validator(mode="after")
    def validate_short_policy(self) -> Self:
        if self.enabled_at_validation_start:
            raise ValueError("shorts must remain disabled at validation start")
        if not self.implementation_present:
            raise ValueError("v0.5 requires dormant short-side implementation")
        if not self.activation_requires_future_rehearsal:
            raise ValueError("short activation requires a future rehearsal milestone")
        return self


class ValidationScaleInPolicy(StrictModel):
    implementation_present: bool
    enabled_at_validation_start: bool
    stage_gate_required: bool
    required_clean_scheduled_runs_before_enable: int = Field(ge=0)
    require_real_broker_additive_stop_proof: bool

    @model_validator(mode="after")
    def validate_scale_in_policy(self) -> Self:
        if not self.implementation_present:
            raise ValueError("scale-in implementation must remain present")
        if self.enabled_at_validation_start:
            raise ValueError("scale-ins must be disabled at validation start")
        if not self.stage_gate_required:
            raise ValueError("scale-in enablement requires a stage gate")
        if self.required_clean_scheduled_runs_before_enable < 10:
            raise ValueError("scale-in stage gate requires at least 10 clean scheduled runs")
        if not self.require_real_broker_additive_stop_proof:
            raise ValueError("scale-in stage gate requires real broker additive-stop proof")
        return self


class ValidationAiPolicy(StrictModel):
    enabled: bool
    negative_only: bool
    ai_positive_ranking_enabled: bool
    ai_may_hard_block: bool
    ai_may_reduce_size: bool
    ai_may_increase_size: bool
    ai_may_authorize_trade: bool
    neutral_fallback_on_error: bool
    max_ai_runs_per_day: int = Field(ge=0)
    max_ai_calls_per_day: int = Field(ge=0)
    max_symbols_per_run: int = Field(gt=0)
    max_articles_per_symbol: int = Field(gt=0)

    @model_validator(mode="after")
    def validate_validation_ai(self) -> Self:
        if not self.enabled:
            raise ValueError("validation AI policy must be enabled as a risk overlay")
        if not self.negative_only:
            raise ValueError("validation AI must be negative-only")
        if self.ai_positive_ranking_enabled:
            raise ValueError("AI positive ranking must be disabled in the frozen window")
        if not self.ai_may_hard_block or not self.ai_may_reduce_size:
            raise ValueError("AI must be able to block or reduce risk")
        if self.ai_may_increase_size or self.ai_may_authorize_trade:
            raise ValueError("AI cannot increase size or authorize trades")
        if not self.neutral_fallback_on_error:
            raise ValueError("AI provider failures must fall back to neutral behavior")
        return self


class ValidationExitPolicy(StrictModel):
    protective_stop: bool
    fail_fast_exit: bool
    technical_exit_ema10: bool
    time_stop: bool
    app_level_trailing_stop: bool

    @model_validator(mode="after")
    def validate_exits(self) -> Self:
        if not self.protective_stop:
            raise ValueError("protective stops are mandatory")
        if not self.fail_fast_exit or not self.technical_exit_ema10 or not self.time_stop:
            raise ValueError("fail-fast, EMA10 technical, and time-stop exits must be active")
        if self.app_level_trailing_stop:
            raise ValueError("app-level trailing stop is disabled at validation start")
        return self


class ValidationSchedulePolicy(StrictModel):
    data_refresh_et: str
    bod_reconciliation_et: str
    plan_build_et: str
    entry_window_start_et: str
    entry_window_end_et: str
    unfilled_entry_cancel_et: str
    eod_signal_et: str
    ai_research_et: str
    trade_plan_snapshot_et: str
    eod_reconciliation_et: str
    daily_report_et: str
    weekly_report_day: Literal["MON", "TUE", "WED", "THU", "FRI"]
    weekly_report_et: str
    skip_early_close_new_entries: bool


class ValidationConfig(StrictModel):
    frozen_validation_enabled: bool
    frozen_validation_start_allowed: bool
    flat_start_required: bool
    carry_in_positions_allowed: bool
    validation_clock_started: bool
    validation_window_weeks: int = Field(gt=0)
    active_spec_version: Literal["v0.5"]
    active_mode: Literal["paper"]
    live_trading_enabled: bool
    autonomous_live_execution_enabled: bool
    level4_ready: bool
    universe: ValidationUniversePolicy
    long_policy: ValidationLongPolicy
    short_policy: ValidationShortPolicy
    scale_in_policy: ValidationScaleInPolicy
    ai_policy: ValidationAiPolicy
    exits: ValidationExitPolicy
    schedule: ValidationSchedulePolicy

    @model_validator(mode="after")
    def validate_frozen_start_boundaries(self) -> Self:
        if self.frozen_validation_enabled or self.frozen_validation_start_allowed:
            raise ValueError("M44 must not enable or allow frozen validation start")
        if not self.flat_start_required:
            raise ValueError("v0.5 requires a flat broker baseline before validation")
        if self.carry_in_positions_allowed:
            raise ValueError("carry-in positions are not allowed at validation start")
        if self.validation_clock_started:
            raise ValueError("M44 must not start the validation clock")
        if self.live_trading_enabled or self.autonomous_live_execution_enabled:
            raise ValueError("validation config cannot enable live or autonomous live execution")
        if self.level4_ready:
            raise ValueError("Level 4 readiness cannot be claimed before frozen validation")
        return self


class LiveUniverseConfig(StrictModel):
    symbols: tuple[str, ...]
    min_price: float = Field(gt=0)
    min_adv20_usd: int = Field(gt=0)
    allow_etfs: bool
    allow_common_stocks: bool
    allow_options: bool
    allow_shorting: bool
    allow_leveraged_etfs: bool
    allow_inverse_etfs: bool
    allow_futures: bool
    allow_crypto: bool
    allow_prediction_markets: bool

    @field_validator("symbols")
    @classmethod
    def validate_symbols(cls, symbols: tuple[str, ...]) -> tuple[str, ...]:
        if not symbols:
            raise ValueError("live universe must contain at least one approved symbol")
        if any(symbol != symbol.upper() for symbol in symbols):
            raise ValueError("live universe symbols must be uppercase")
        return symbols

    @model_validator(mode="after")
    def validate_exclusions(self) -> Self:
        forbidden = {
            "allow_options": self.allow_options,
            "allow_shorting": self.allow_shorting,
            "allow_leveraged_etfs": self.allow_leveraged_etfs,
            "allow_inverse_etfs": self.allow_inverse_etfs,
            "allow_futures": self.allow_futures,
            "allow_crypto": self.allow_crypto,
            "allow_prediction_markets": self.allow_prediction_markets,
        }
        enabled = [name for name, value in forbidden.items() if value]
        if enabled:
            raise ValueError(f"v0.1 forbidden live universe flags enabled: {enabled}")
        return self


class ResearchUniverseConfig(StrictModel):
    min_price: float = Field(gt=0)
    min_adv20_usd: int = Field(gt=0)
    include_us_common_stocks: bool
    include_major_etfs: bool
    survivorship_bias_warning_required: bool
    point_in_time_universe_preferred: bool


class UniverseBucketsConfig(StrictModel):
    broad_etfs: tuple[str, ...]
    sector_etfs: tuple[str, ...]
    single_name_mega_caps: tuple[str, ...]
    short_eligible_broad_etfs: tuple[str, ...]

    @model_validator(mode="after")
    def validate_buckets(self) -> Self:
        expected_short = ("SPY", "QQQ", "DIA", "IWM")
        if self.short_eligible_broad_etfs != expected_short:
            raise ValueError("v0.5 short-eligible universe must be SPY/QQQ/DIA/IWM only")
        for symbol in (*self.broad_etfs, *self.sector_etfs, *self.single_name_mega_caps):
            if symbol != symbol.upper():
                raise ValueError("universe bucket symbols must be uppercase")
        return self


class StrategyConfig(StrictModel):
    name: str
    trend_fast_ma: int = Field(gt=0)
    trend_slow_ma: int = Field(gt=0)
    breakout_lookback_primary: int = Field(gt=0)
    breakout_lookback_research_variants: tuple[int, ...]
    volume_lookback_days: int = Field(gt=0)
    volume_ratio_min: float = Field(gt=0)
    relative_strength_lookback_days: int = Field(gt=0)
    relative_strength_min: float
    relative_strength_percentile_floor_research: int = Field(ge=0, le=100)
    atr_period: int = Field(gt=0)
    atr_pct_min: float = Field(gt=0)
    atr_pct_max: float = Field(gt=0)
    initial_stop_atr_multiplier: float = Field(gt=0)
    initial_stop_atr_multiplier_research_variants: tuple[float, ...]
    trailing_stop_atr_multiplier: float = Field(gt=0)
    trailing_stop_atr_multiplier_research_variants: tuple[float, ...]
    technical_exit_ema: int = Field(gt=0)
    technical_exit_confirm_closes: int = Field(gt=0)
    time_stop_days: int = Field(gt=0)
    fail_fast_exit_days: int = Field(gt=0)

    @model_validator(mode="after")
    def validate_strategy_ranges(self) -> Self:
        if self.trend_fast_ma >= self.trend_slow_ma:
            raise ValueError("trend_fast_ma must be less than trend_slow_ma")
        if self.breakout_lookback_primary not in self.breakout_lookback_research_variants:
            raise ValueError("primary breakout lookback must be included in research variants")
        if self.atr_pct_min >= self.atr_pct_max:
            raise ValueError("atr_pct_min must be less than atr_pct_max")
        return self


class ValidationStrategyConfig(StrictModel):
    active_breakout_lookback: int = Field(gt=0)
    research_breakout_lookbacks: tuple[int, ...]
    same_day_reentry_forbidden: bool
    early_close_new_entries_allowed: bool
    force_trades: bool
    active_long_filters: tuple[str, ...]
    rejection_reasons: tuple[str, ...]

    @model_validator(mode="after")
    def validate_validation_strategy(self) -> Self:
        required_rejections = {
            "early_close_session",
            "execution_budget_exhausted",
            "correlation_cluster_cap",
            "same_day_reentry_forbidden",
            "scale_in_stage_gate_not_met",
        }
        if self.active_breakout_lookback != 20:
            raise ValueError("20D breakout must be the active frozen validation breakout")
        if 55 not in self.research_breakout_lookbacks:
            raise ValueError("55D breakout must remain research-only")
        if not self.same_day_reentry_forbidden:
            raise ValueError("same-day re-entry must be forbidden")
        if self.early_close_new_entries_allowed:
            raise ValueError("early-close new entries must be disabled")
        if self.force_trades:
            raise ValueError("frozen validation must not force trades")
        missing = required_rejections.difference(self.rejection_reasons)
        if missing:
            raise ValueError(f"missing validation rejection reasons: {sorted(missing)}")
        return self


class ValidationExitsConfig(ValidationExitPolicy):
    pass


class RegimeConfig(StrictModel):
    model_version: str
    states: tuple[Literal["RISK_ON", "CAUTION", "RISK_OFF"], ...]
    proxy: str
    sma_slow: int = Field(gt=0)
    sma_fast: int = Field(gt=0)
    risk_on_above_sma200_multiplier: float = Field(gt=0)
    risk_off_below_sma200_multiplier: float = Field(gt=0)
    risk_on_confirm_closes: int = Field(gt=0)
    risk_off_confirm_closes: int = Field(gt=0)
    rv20_risk_on_max: float = Field(gt=0)
    rv20_risk_off_min: float = Field(gt=0)
    risk_off_cooldown_days: int = Field(ge=0)


class RiskLevelConfig(StrictModel):
    max_gross_exposure_pct: float = Field(gt=0, le=1)
    max_deployable_capital_pct: float = Field(gt=0, le=1)
    max_position_size_pct: float = Field(gt=0, le=1)
    max_risk_per_trade_pct: float = Field(gt=0, le=1)
    max_open_positions: int = Field(gt=0)
    max_sector_exposure_pct: float = Field(gt=0, le=1)
    min_cash_buffer_pct: float = Field(ge=0, le=1)
    max_daily_loss_pct: float = Field(gt=0, le=1)
    max_weekly_loss_pct: float = Field(gt=0, le=1)
    max_monthly_loss_pct: float = Field(gt=0, le=1)
    allow_margin: bool
    allow_shorting: bool
    allow_options: bool
    allow_leveraged_etfs: bool
    allow_futures: bool
    allow_crypto: bool
    allow_prediction_markets: bool
    require_protective_stop: bool

    @model_validator(mode="after")
    def validate_risk_safety_flags(self) -> Self:
        forbidden = {
            "allow_margin": self.allow_margin,
            "allow_shorting": self.allow_shorting,
            "allow_options": self.allow_options,
            "allow_leveraged_etfs": self.allow_leveraged_etfs,
            "allow_futures": self.allow_futures,
            "allow_crypto": self.allow_crypto,
            "allow_prediction_markets": self.allow_prediction_markets,
        }
        enabled = [name for name, value in forbidden.items() if value]
        if enabled:
            raise ValueError(f"v0.1 forbidden risk flags enabled: {enabled}")
        if not self.require_protective_stop:
            raise ValueError("protective stops are required")
        return self


class ShortsConfig(StrictModel):
    enabled: bool
    paper_only_short_exposure: bool
    allow_live_shorting: bool
    require_explicit_short_activation: bool
    eligible_symbols: tuple[str, ...]
    allow_individual_stock_shorts: bool
    allow_sector_etf_shorts: bool
    allow_leveraged_etf_shorts: bool
    allow_inverse_etf_shorts: bool
    require_shortable: bool
    require_easy_to_borrow: bool
    require_marginable: bool
    require_account_shorting_enabled: bool
    require_whole_shares: bool
    max_open_short_symbols: int = Field(ge=0)
    max_entries_per_symbol: int = Field(ge=0)
    max_add_entries_per_symbol: int = Field(ge=0)
    max_total_symbol_qty: int = Field(ge=0)
    max_symbol_notional_usd: float = Field(gt=0)
    max_portfolio_short_notional_usd: float = Field(gt=0)
    max_portfolio_short_exposure_pct: float = Field(gt=0, le=1)
    max_net_short_exposure_pct: float = Field(gt=0, le=1)
    max_short_risk_per_trade_pct: float = Field(gt=0, le=1)
    max_portfolio_short_risk_at_stop_pct: float = Field(gt=0, le=1)
    allow_stop_replacement: bool
    allow_partial_discretionary_cover: bool
    require_buy_stop_for_filled_short_qty: bool

    @model_validator(mode="after")
    def validate_short_safety(self) -> Self:
        if not self.paper_only_short_exposure:
            raise ValueError("short capability must be paper-only")
        if self.allow_live_shorting:
            raise ValueError("live shorting is not allowed")
        if not self.require_explicit_short_activation:
            raise ValueError("short activation requires explicit future approval")
        if self.eligible_symbols != ("SPY", "QQQ", "DIA", "IWM"):
            raise ValueError("initial short universe must be SPY/QQQ/DIA/IWM only")
        forbidden = {
            "allow_individual_stock_shorts": self.allow_individual_stock_shorts,
            "allow_sector_etf_shorts": self.allow_sector_etf_shorts,
            "allow_leveraged_etf_shorts": self.allow_leveraged_etf_shorts,
            "allow_inverse_etf_shorts": self.allow_inverse_etf_shorts,
            "allow_stop_replacement": self.allow_stop_replacement,
            "allow_partial_discretionary_cover": self.allow_partial_discretionary_cover,
        }
        enabled = [name for name, value in forbidden.items() if value]
        if enabled:
            raise ValueError(f"forbidden short flags enabled: {enabled}")
        required = {
            "require_shortable": self.require_shortable,
            "require_easy_to_borrow": self.require_easy_to_borrow,
            "require_marginable": self.require_marginable,
            "require_account_shorting_enabled": self.require_account_shorting_enabled,
            "require_whole_shares": self.require_whole_shares,
            "require_buy_stop_for_filled_short_qty": self.require_buy_stop_for_filled_short_qty,
        }
        missing = [name for name, value in required.items() if not value]
        if missing:
            raise ValueError(f"required short gates disabled: {missing}")
        if self.max_add_entries_per_symbol != 0:
            raise ValueError("short add-on entries are disabled in v0.5")
        if self.max_total_symbol_qty != 1:
            raise ValueError("short total symbol quantity cap must be one share")
        return self


class ValidationRiskConfig(StrictModel):
    max_gross_exposure_pct: float = Field(gt=0, le=1)
    max_net_exposure_pct: float = Field(gt=0, le=1)
    max_deployable_capital_pct: float = Field(gt=0, le=1)
    max_open_positions: int = Field(gt=0)
    max_position_size_pct_etf: float = Field(gt=0, le=1)
    max_position_size_pct_stock: float = Field(gt=0, le=1)
    max_risk_per_trade_pct: float = Field(gt=0, le=1)
    max_symbol_risk_at_stop_pct_after_scalein: float = Field(gt=0, le=1)
    max_portfolio_risk_at_stop_pct: float = Field(gt=0, le=1)
    max_sector_exposure_pct: float = Field(gt=0, le=1)
    max_tech_complex_exposure_pct: float = Field(gt=0, le=1)
    max_broad_beta_overlap_pct: float = Field(gt=0, le=1)
    max_new_entries_per_day: int = Field(ge=0)
    max_scale_ins_per_day_at_start: int = Field(ge=0)
    max_broker_writes_per_day: int = Field(ge=0)
    max_unresolved_critical_incidents: int = Field(ge=0)
    max_daily_loss_pct: float = Field(gt=0, le=1)
    max_weekly_loss_pct: float = Field(gt=0, le=1)
    max_monthly_loss_pct: float = Field(gt=0, le=1)
    soft_drawdown_review_pct: float = Field(gt=0, le=1)
    hard_drawdown_fail_pct: float = Field(gt=0, le=1)

    @model_validator(mode="after")
    def validate_validation_risk(self) -> Self:
        if self.max_scale_ins_per_day_at_start != 0:
            raise ValueError("scale-ins are disabled at validation start")
        if self.max_unresolved_critical_incidents != 0:
            raise ValueError("validation start requires zero unresolved critical incidents")
        if self.soft_drawdown_review_pct >= self.hard_drawdown_fail_pct:
            raise ValueError("soft drawdown review threshold must be below hard fail threshold")
        return self


class AiConfig(StrictModel):
    enabled: bool
    provider: str
    model: str
    require_json_schema: bool
    allow_ai_to_create_orders: bool
    allow_ai_to_modify_strategy: bool
    allow_ai_to_modify_risk_limits: bool
    analyze_full_universe: bool
    analyze_deterministic_shortlist_only: bool
    default_news_lookback_calendar_days: int = Field(gt=0)
    extended_event_lookback_calendar_days: int = Field(gt=0)
    max_articles_per_symbol: int = Field(gt=0)
    batch_size_symbols: int = Field(gt=0)
    max_batch_size_symbols: int = Field(gt=0)
    missing_news_fallback_score: int = Field(ge=0, le=100)
    invalid_output_fallback_score: int = Field(ge=0, le=100)
    hard_block_confidence_min: float = Field(ge=0, le=1)
    prompt_version: str
    schema_version: str
    news_provider_primary: Literal["marketaux", "alpha_vantage"] = "marketaux"
    news_provider_fallback: Literal["marketaux", "alpha_vantage"] = "alpha_vantage"
    marketaux_daily_request_limit: int = Field(default=90, ge=0)
    alpha_vantage_daily_request_limit: int = Field(default=20, ge=0)
    news_max_symbols_per_run: int = Field(default=5, gt=0)
    news_max_articles_per_symbol: int = Field(default=3, gt=0)
    news_enable_openai_web_fallback: bool = False
    news_openai_web_daily_request_limit: int = Field(default=5, ge=0)
    openai_model: str = "gpt-5.2"
    openai_escalation_model: str = "gpt-5.2-pro"
    openai_fallback_model: str = "gpt-5-mini"
    ai_daily_request_limit: int = Field(default=25, ge=0)
    ai_max_symbols_per_run: int = Field(default=5, gt=0)
    ai_max_articles_per_symbol: int = Field(default=3, gt=0)
    ai_require_structured_output: bool = True
    ai_neutral_fallback_on_error: bool = True
    ai_enable_escalation: bool = False
    ai_feedback_enabled: bool = True
    ai_feedback_min_schema_validity_rate: float = Field(default=0.99, ge=0, le=1)
    ai_feedback_min_provider_coverage_rate: float = Field(default=0.60, ge=0, le=1)
    ai_feedback_max_fallback_rate: float = Field(default=0.35, ge=0, le=1)
    ai_feedback_max_missed_risk_false_negative_proxy_rate: float = Field(
        default=0.15,
        ge=0,
        le=1,
    )

    @model_validator(mode="after")
    def validate_ai_boundaries(self) -> Self:
        if self.allow_ai_to_create_orders:
            raise ValueError("AI cannot create orders")
        if self.allow_ai_to_modify_strategy:
            raise ValueError("AI cannot modify strategy")
        if self.allow_ai_to_modify_risk_limits:
            raise ValueError("AI cannot modify risk limits")
        if self.analyze_full_universe:
            raise ValueError("AI cannot analyze the full universe in v0.1")
        if not self.analyze_deterministic_shortlist_only:
            raise ValueError("AI must be constrained to deterministic shortlist candidates")
        if not self.require_json_schema:
            raise ValueError("AI outputs must require JSON schema validation")
        if self.batch_size_symbols > self.max_batch_size_symbols:
            raise ValueError("batch_size_symbols cannot exceed max_batch_size_symbols")
        if self.news_provider_primary == self.news_provider_fallback:
            raise ValueError("primary and fallback news providers must differ")
        if self.news_max_symbols_per_run > self.max_batch_size_symbols:
            raise ValueError("news_max_symbols_per_run cannot exceed max_batch_size_symbols")
        if self.news_max_articles_per_symbol > self.max_articles_per_symbol:
            raise ValueError("news_max_articles_per_symbol cannot exceed max_articles_per_symbol")
        if self.ai_max_symbols_per_run > self.max_batch_size_symbols:
            raise ValueError("ai_max_symbols_per_run cannot exceed max_batch_size_symbols")
        if self.ai_max_articles_per_symbol > self.max_articles_per_symbol:
            raise ValueError("ai_max_articles_per_symbol cannot exceed max_articles_per_symbol")
        if not self.ai_require_structured_output:
            raise ValueError("OpenAI analysis must require structured output")
        if not self.ai_neutral_fallback_on_error:
            raise ValueError("AI provider failures must fall back to neutral behavior")
        return self


class ValidationAiConfig(ValidationAiPolicy):
    ai_may_authorize_scale_in: bool
    ai_may_authorize_shorts: bool

    @model_validator(mode="after")
    def validate_ai_extensions(self) -> Self:
        if not self.enabled:
            raise ValueError("validation AI policy must be enabled as a risk overlay")
        if not self.negative_only:
            raise ValueError("validation AI must be negative-only")
        if self.ai_positive_ranking_enabled:
            raise ValueError("AI positive ranking must be disabled in the frozen window")
        if not self.ai_may_hard_block or not self.ai_may_reduce_size:
            raise ValueError("AI must be able to block or reduce risk")
        if self.ai_may_increase_size or self.ai_may_authorize_trade:
            raise ValueError("AI cannot increase size or authorize trades")
        if not self.neutral_fallback_on_error:
            raise ValueError("AI provider failures must fall back to neutral behavior")
        if self.ai_may_authorize_scale_in or self.ai_may_authorize_shorts:
            raise ValueError("AI cannot authorize scale-ins or shorts")
        return self


class AppConfig(StrictModel):
    system: SystemConfig
    temporal: TemporalConfig
    market_data: MarketDataConfig
    execution: ExecutionConfig
    protective_stop: ProtectiveStopConfig
    scale_in: ScaleInConfig
    validation: ValidationConfig
    live_universe: LiveUniverseConfig
    research_universe: ResearchUniverseConfig
    universe_buckets: UniverseBucketsConfig
    strategy: StrategyConfig
    validation_strategy: ValidationStrategyConfig
    validation_exits: ValidationExitsConfig
    regime: RegimeConfig
    risk_level_4_micro_live: RiskLevelConfig
    risk_level_4_expanded: RiskLevelConfig
    shorts: ShortsConfig
    validation_risk: ValidationRiskConfig
    ai: AiConfig
    validation_ai: ValidationAiConfig


def load_app_config(config_dir: str | Path = "config") -> AppConfig:
    config_path = Path(config_dir)
    merged: dict[str, Any] = {}

    for file_name in CONFIG_FILES:
        file_path = config_path / file_name
        if not file_path.is_file():
            raise ConfigLoadError(f"missing required config file: {file_path}")
        data = _load_yaml_mapping(file_path)
        duplicate_keys = set(merged).intersection(data)
        if duplicate_keys:
            joined = ", ".join(sorted(duplicate_keys))
            raise ConfigLoadError(f"duplicate top-level config sections in {file_path}: {joined}")
        merged.update(data)

    try:
        return AppConfig.model_validate(merged)
    except ValidationError as exc:
        raise ConfigLoadError(f"invalid application configuration: {exc}") from exc


def _load_yaml_mapping(file_path: Path) -> Mapping[str, Any]:
    try:
        with file_path.open("r", encoding="utf-8") as handle:
            data = yaml.safe_load(handle)
    except yaml.YAMLError as exc:
        raise ConfigLoadError(f"invalid YAML in {file_path}: {exc}") from exc

    if not isinstance(data, Mapping):
        raise ConfigLoadError(f"config file must contain a mapping: {file_path}")
    return data
