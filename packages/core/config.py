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
    namespace: str
    task_queues: TemporalTaskQueues
    schedules: TemporalSchedules
    retry_defaults: RetryDefaults


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
        return self


class AppConfig(StrictModel):
    system: SystemConfig
    temporal: TemporalConfig
    execution: ExecutionConfig
    protective_stop: ProtectiveStopConfig
    live_universe: LiveUniverseConfig
    research_universe: ResearchUniverseConfig
    strategy: StrategyConfig
    regime: RegimeConfig
    risk_level_4_micro_live: RiskLevelConfig
    risk_level_4_expanded: RiskLevelConfig
    ai: AiConfig


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
