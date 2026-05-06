"""Fake/local paper dry-run orchestration contracts."""

from packages.paper.dry_run import PaperDryRunOrchestrator, run_paper_dry_run
from packages.paper.fixtures import default_dry_run_input, scenario_by_id
from packages.paper.models import (
    DryRunConfig,
    DryRunEvidence,
    DryRunFailureMode,
    DryRunInput,
    DryRunResult,
    DryRunSafetyFlags,
    DryRunScenario,
    DryRunStepResult,
    DryRunStepStatus,
)

__all__ = [
    "DryRunConfig",
    "DryRunEvidence",
    "DryRunFailureMode",
    "DryRunInput",
    "DryRunResult",
    "DryRunSafetyFlags",
    "DryRunScenario",
    "DryRunStepResult",
    "DryRunStepStatus",
    "PaperDryRunOrchestrator",
    "default_dry_run_input",
    "run_paper_dry_run",
    "scenario_by_id",
]
