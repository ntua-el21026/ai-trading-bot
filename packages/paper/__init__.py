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
from packages.paper.readiness import (
    PaperOperationsReadinessEvidence,
    PaperOperationsReadinessResult,
    ReadinessCheck,
    build_repository_readiness_evidence,
    evaluate_paper_operations_readiness,
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
    "PaperOperationsReadinessEvidence",
    "PaperOperationsReadinessResult",
    "ReadinessCheck",
    "build_repository_readiness_evidence",
    "default_dry_run_input",
    "evaluate_paper_operations_readiness",
    "run_paper_dry_run",
    "scenario_by_id",
]
