"""Validation harness contracts.

These models describe validation assumptions and dry-run checks only. They do not run live or paper
broker orders and must not be treated as proof of profitability.
"""

from __future__ import annotations

from datetime import date
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

ValidationSplitName = Literal[
    "design_parameter_selection",
    "rolling_oos_development",
    "final_untouched_lockbox",
]
BenchmarkName = Literal[
    "SPY total return",
    "exposure-adjusted SPY",
    "equal-weight approved universe",
]
AblationName = Literal[
    "regime_on_off",
    "relative_strength_on_off",
    "volume_filter_on_off",
    "ai_forced_neutral_vs_enabled",
    "fail_fast_exit_on_off",
    "time_stop_on_off",
    "breakout_20d_vs_55d",
    "atr_stop_2_0_vs_2_5",
    "atr_trailing_2_5_vs_3_0",
]

REQUIRED_SPLIT_NAMES: tuple[ValidationSplitName, ...] = (
    "design_parameter_selection",
    "rolling_oos_development",
    "final_untouched_lockbox",
)
REQUIRED_BENCHMARKS: tuple[BenchmarkName, ...] = (
    "SPY total return",
    "exposure-adjusted SPY",
    "equal-weight approved universe",
)
REQUIRED_ABLATIONS: tuple[AblationName, ...] = (
    "regime_on_off",
    "relative_strength_on_off",
    "volume_filter_on_off",
    "ai_forced_neutral_vs_enabled",
    "fail_fast_exit_on_off",
    "time_stop_on_off",
    "breakout_20d_vs_55d",
    "atr_stop_2_0_vs_2_5",
    "atr_trailing_2_5_vs_3_0",
)


class ValidationModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class HistoricalSplit(ValidationModel):
    name: ValidationSplitName
    start: date
    end: date | None
    label: str

    @model_validator(mode="after")
    def validate_dates(self) -> Self:
        if self.end is not None and self.end < self.start:
            raise ValueError("split end cannot be before split start")
        return self


class ValidationCostAssumptions(ValidationModel):
    commission: float = Field(ge=0)
    fee_proxy_bps_per_side: float = Field(ge=0)
    baseline_entry_slippage_bps: float = Field(ge=0)
    baseline_routine_exit_slippage_bps: float = Field(ge=0)
    baseline_stop_exit_slippage_bps: float = Field(ge=0)
    stress_entry_slippage_bps: float = Field(ge=0)
    stress_stop_exit_slippage_bps: float = Field(ge=0)

    @model_validator(mode="after")
    def validate_stress_is_not_lower_than_baseline(self) -> Self:
        if self.stress_entry_slippage_bps < self.baseline_entry_slippage_bps:
            raise ValueError("stress entry slippage cannot be below baseline")
        if self.stress_stop_exit_slippage_bps < self.baseline_stop_exit_slippage_bps:
            raise ValueError("stress stop slippage cannot be below baseline")
        return self


class BenchmarkDefinition(ValidationModel):
    name: BenchmarkName
    required: bool = True


class AblationDefinition(ValidationModel):
    name: AblationName
    enabled: bool = True


class MonteCarloPlan(ValidationModel):
    trade_sequence_bootstraps: int = Field(gt=0)
    monthly_block_bootstrap_returns: bool
    missed_fill_rate: float = Field(ge=0, le=1)
    slippage_multiplier_min: float = Field(gt=0)
    slippage_multiplier_max: float = Field(gt=0)

    @model_validator(mode="after")
    def validate_slippage_multiplier_range(self) -> Self:
        if self.slippage_multiplier_min > self.slippage_multiplier_max:
            raise ValueError("slippage multiplier min cannot exceed max")
        return self


class ValidationHarnessConfig(ValidationModel):
    historical_period_start: date
    historical_period_end: Literal["latest_available"]
    splits: tuple[HistoricalSplit, ...]
    benchmarks: tuple[BenchmarkDefinition, ...]
    costs: ValidationCostAssumptions
    ablations: tuple[AblationDefinition, ...]
    monte_carlo: MonteCarloPlan
    point_in_time_universe_available: bool
    optimistic_universe_warning: bool
    validation_note: str = "Backtests are validation tools, not proof of profitability."
    paper_trading_note: str = (
        "Paper trading is operational rehearsal, not proof of live profitability."
    )

    @model_validator(mode="after")
    def validate_config(self) -> Self:
        split_names = {split.name for split in self.splits}
        if split_names != set(REQUIRED_SPLIT_NAMES):
            raise ValueError("validation config must include all required split names")
        benchmark_names = {benchmark.name for benchmark in self.benchmarks}
        if benchmark_names != set(REQUIRED_BENCHMARKS):
            raise ValueError("validation config must include all required benchmarks")
        ablation_names = {ablation.name for ablation in self.ablations}
        if ablation_names != set(REQUIRED_ABLATIONS):
            raise ValueError("validation config must include all required ablations")
        if not self.point_in_time_universe_available and not self.optimistic_universe_warning:
            raise ValueError("missing point-in-time universe data requires optimism warning")
        if "not proof of profitability" not in self.validation_note:
            raise ValueError("validation note must reject profitability proof claims")
        if "not proof of live profitability" not in self.paper_trading_note:
            raise ValueError("paper trading note must reject live profitability proof claims")
        return self


def build_default_validation_harness_config(
    *,
    point_in_time_universe_available: bool,
) -> ValidationHarnessConfig:
    return ValidationHarnessConfig(
        historical_period_start=date(2012, 1, 1),
        historical_period_end="latest_available",
        splits=(
            HistoricalSplit(
                name="design_parameter_selection",
                start=date(2012, 1, 1),
                end=date(2018, 12, 31),
                label="2012-2018",
            ),
            HistoricalSplit(
                name="rolling_oos_development",
                start=date(2019, 1, 1),
                end=date(2023, 12, 31),
                label="2019-2023",
            ),
            HistoricalSplit(
                name="final_untouched_lockbox",
                start=date(2024, 1, 1),
                end=None,
                label="2024-latest",
            ),
        ),
        benchmarks=tuple(BenchmarkDefinition(name=name) for name in REQUIRED_BENCHMARKS),
        costs=ValidationCostAssumptions(
            commission=0.0,
            fee_proxy_bps_per_side=1.0,
            baseline_entry_slippage_bps=10.0,
            baseline_routine_exit_slippage_bps=10.0,
            baseline_stop_exit_slippage_bps=20.0,
            stress_entry_slippage_bps=25.0,
            stress_stop_exit_slippage_bps=40.0,
        ),
        ablations=tuple(AblationDefinition(name=name) for name in REQUIRED_ABLATIONS),
        monte_carlo=MonteCarloPlan(
            trade_sequence_bootstraps=10_000,
            monthly_block_bootstrap_returns=True,
            missed_fill_rate=0.05,
            slippage_multiplier_min=0.5,
            slippage_multiplier_max=1.5,
        ),
        point_in_time_universe_available=point_in_time_universe_available,
        optimistic_universe_warning=not point_in_time_universe_available,
    )
