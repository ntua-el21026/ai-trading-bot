"""Paper dry-run validation contracts."""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from packages.validation.models import ValidationModel

PaperDryRunCheckName = Literal[
    "execution_intent_lifecycle_validated",
    "broker_snapshot_fixture_used",
    "reconciliation_contract_clean",
    "missing_stop_policy_validated",
    "duplicate_order_rejected",
    "invalid_ai_output_neutral",
    "control_plane_kill_switch_signal_mapped",
    "no_broker_orders_submitted",
    "no_external_calls_performed",
    "safe_runtime_flags",
]


class PaperDryRunInputs(ValidationModel):
    execution_intent_lifecycle_validated: bool
    broker_snapshot_fixture_used: bool
    reconciliation_contract_clean: bool
    missing_stop_policy_validated: bool
    duplicate_order_rejected: bool
    invalid_ai_output_neutral: bool
    control_plane_kill_switch_signal_mapped: bool
    live_trading_enabled: bool
    autonomous_execution_enabled: bool
    broker_orders_submitted: bool
    external_calls_performed: bool


class PaperDryRunCheck(ValidationModel):
    name: PaperDryRunCheckName
    passed: bool
    reason_code: str
    details: dict[str, str] = Field(default_factory=dict)


class PaperDryRunResult(ValidationModel):
    checks: tuple[PaperDryRunCheck, ...]
    validation_note: str = (
        "Paper dry-run checks are operational contract validation, not proof of profitability."
    )

    @property
    def passed(self) -> bool:
        return all(check.passed for check in self.checks)


def evaluate_paper_dry_run(inputs: PaperDryRunInputs) -> PaperDryRunResult:
    return PaperDryRunResult(
        checks=(
            _bool_check(
                "execution_intent_lifecycle_validated",
                inputs.execution_intent_lifecycle_validated,
            ),
            _bool_check("broker_snapshot_fixture_used", inputs.broker_snapshot_fixture_used),
            _bool_check("reconciliation_contract_clean", inputs.reconciliation_contract_clean),
            _bool_check("missing_stop_policy_validated", inputs.missing_stop_policy_validated),
            _bool_check("duplicate_order_rejected", inputs.duplicate_order_rejected),
            _bool_check("invalid_ai_output_neutral", inputs.invalid_ai_output_neutral),
            _bool_check(
                "control_plane_kill_switch_signal_mapped",
                inputs.control_plane_kill_switch_signal_mapped,
            ),
            PaperDryRunCheck(
                name="no_broker_orders_submitted",
                passed=not inputs.broker_orders_submitted,
                reason_code=(
                    "no_broker_orders_submitted"
                    if not inputs.broker_orders_submitted
                    else "broker_orders_submitted"
                ),
            ),
            PaperDryRunCheck(
                name="no_external_calls_performed",
                passed=not inputs.external_calls_performed,
                reason_code=(
                    "no_external_calls_performed"
                    if not inputs.external_calls_performed
                    else "external_calls_performed"
                ),
            ),
            PaperDryRunCheck(
                name="safe_runtime_flags",
                passed=not inputs.live_trading_enabled and not inputs.autonomous_execution_enabled,
                reason_code=(
                    "runtime_flags_safe"
                    if not inputs.live_trading_enabled and not inputs.autonomous_execution_enabled
                    else "runtime_flags_unsafe"
                ),
                details={
                    "live_trading_enabled": str(inputs.live_trading_enabled),
                    "autonomous_execution_enabled": str(inputs.autonomous_execution_enabled),
                },
            ),
        )
    )


def _bool_check(name: PaperDryRunCheckName, value: bool) -> PaperDryRunCheck:
    return PaperDryRunCheck(
        name=name,
        passed=value,
        reason_code=f"{name}_ok" if value else f"{name}_failed",
    )
