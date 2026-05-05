"""Validation and testing harness contracts."""

from packages.validation.failures import (
    REQUIRED_FAILURE_SCENARIOS,
    FailureSimulationScenario,
    default_failure_simulation_scenarios,
)
from packages.validation.models import (
    REQUIRED_ABLATIONS,
    REQUIRED_BENCHMARKS,
    REQUIRED_SPLIT_NAMES,
    AblationDefinition,
    BenchmarkDefinition,
    HistoricalSplit,
    MonteCarloPlan,
    ValidationCostAssumptions,
    ValidationHarnessConfig,
    build_default_validation_harness_config,
)
from packages.validation.paper import (
    PaperDryRunCheck,
    PaperDryRunInputs,
    PaperDryRunResult,
    evaluate_paper_dry_run,
)

__all__ = [
    "REQUIRED_ABLATIONS",
    "REQUIRED_BENCHMARKS",
    "REQUIRED_FAILURE_SCENARIOS",
    "REQUIRED_SPLIT_NAMES",
    "AblationDefinition",
    "BenchmarkDefinition",
    "FailureSimulationScenario",
    "HistoricalSplit",
    "MonteCarloPlan",
    "PaperDryRunCheck",
    "PaperDryRunInputs",
    "PaperDryRunResult",
    "ValidationCostAssumptions",
    "ValidationHarnessConfig",
    "build_default_validation_harness_config",
    "default_failure_simulation_scenarios",
    "evaluate_paper_dry_run",
]
