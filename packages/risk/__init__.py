"""Deterministic risk checks, sizing, and kill-switch contracts."""

from packages.risk.checks import evaluate_new_risk_order
from packages.risk.kill_switch import (
    new_risk_allowed,
    pause_all_autonomous_actions,
    pause_new_risk,
    request_force_flat,
    require_manual_review,
    risk_reducing_exits_allowed,
    running_state,
)
from packages.risk.models import (
    KillSwitchSnapshot,
    NewRiskOrderInput,
    PositionSizingInput,
    PositionSizingResult,
    RiskAssessment,
    RiskCheckResult,
)
from packages.risk.shorts import (
    ShortAccountSnapshot,
    ShortAssetSnapshot,
    ShortEntryRiskInput,
    ShortEntryRiskResult,
    evaluate_short_entry_risk,
)
from packages.risk.sizing import calculate_position_size

__all__ = [
    "KillSwitchSnapshot",
    "NewRiskOrderInput",
    "PositionSizingInput",
    "PositionSizingResult",
    "RiskAssessment",
    "RiskCheckResult",
    "ShortAccountSnapshot",
    "ShortAssetSnapshot",
    "ShortEntryRiskInput",
    "ShortEntryRiskResult",
    "calculate_position_size",
    "evaluate_new_risk_order",
    "evaluate_short_entry_risk",
    "new_risk_allowed",
    "pause_all_autonomous_actions",
    "pause_new_risk",
    "request_force_flat",
    "require_manual_review",
    "risk_reducing_exits_allowed",
    "running_state",
]
