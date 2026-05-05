import pytest
from pydantic import ValidationError

from packages.validation.models import (
    REQUIRED_ABLATIONS,
    REQUIRED_BENCHMARKS,
    REQUIRED_SPLIT_NAMES,
    ValidationHarnessConfig,
    build_default_validation_harness_config,
)


def test_default_validation_harness_matches_spec_splits_costs_and_benchmarks() -> None:
    config = build_default_validation_harness_config(point_in_time_universe_available=False)

    assert config.historical_period_start.isoformat() == "2012-01-01"
    assert config.historical_period_end == "latest_available"
    assert tuple(split.name for split in config.splits) == REQUIRED_SPLIT_NAMES
    assert tuple(split.label for split in config.splits) == (
        "2012-2018",
        "2019-2023",
        "2024-latest",
    )
    assert tuple(benchmark.name for benchmark in config.benchmarks) == REQUIRED_BENCHMARKS
    assert config.costs.commission == 0.0
    assert config.costs.fee_proxy_bps_per_side == 1.0
    assert config.costs.baseline_entry_slippage_bps == 10.0
    assert config.costs.baseline_routine_exit_slippage_bps == 10.0
    assert config.costs.baseline_stop_exit_slippage_bps == 20.0
    assert config.costs.stress_entry_slippage_bps == 25.0
    assert config.costs.stress_stop_exit_slippage_bps == 40.0
    assert tuple(ablation.name for ablation in config.ablations) == REQUIRED_ABLATIONS
    assert config.optimistic_universe_warning is True
    assert "not proof of profitability" in config.validation_note
    assert "not proof of live profitability" in config.paper_trading_note


def test_validation_harness_monte_carlo_contract_matches_spec_placeholders() -> None:
    config = build_default_validation_harness_config(point_in_time_universe_available=True)

    assert config.optimistic_universe_warning is False
    assert config.monte_carlo.trade_sequence_bootstraps == 10_000
    assert config.monte_carlo.monthly_block_bootstrap_returns is True
    assert config.monte_carlo.missed_fill_rate == 0.05
    assert config.monte_carlo.slippage_multiplier_min == 0.5
    assert config.monte_carlo.slippage_multiplier_max == 1.5


def test_validation_harness_requires_optimism_warning_without_point_in_time_universe() -> None:
    config = build_default_validation_harness_config(point_in_time_universe_available=False)
    invalid_data = config.model_dump(mode="python") | {"optimistic_universe_warning": False}

    with pytest.raises(ValidationError, match="optimism warning"):
        ValidationHarnessConfig.model_validate(invalid_data)
