"""Side-aware execution semantics for v0.5 signed positions."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from packages.execution.models import ExecutionOrderRole, ExecutionSide, PositionSide


class SideSemanticsModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class SideOrderSemantics(SideSemanticsModel):
    position_side: PositionSide
    signed_quantity: float
    entry_side: ExecutionSide | None
    protective_side: ExecutionSide | None
    exit_side: ExecutionSide | None
    entry_role: ExecutionOrderRole | None
    protective_role: ExecutionOrderRole | None
    exit_role: ExecutionOrderRole | None


def classify_position_side(signed_qty: float) -> PositionSide:
    if signed_qty > 0:
        return "long"
    if signed_qty < 0:
        return "short"
    return "flat"


def can_open_position_side(
    *,
    current_side: PositionSide,
    requested_side: PositionSide,
) -> bool:
    """Return whether v0.5 can open requested side without a same-symbol reversal."""

    if requested_side == "flat":
        return True
    if current_side == "flat":
        return True
    return current_side == requested_side


def build_side_order_semantics(
    *,
    requested_side: PositionSide,
    quantity: float,
) -> SideOrderSemantics:
    if requested_side == "long":
        return SideOrderSemantics(
            position_side="long",
            signed_quantity=quantity,
            entry_side="buy",
            protective_side="sell",
            exit_side="sell",
            entry_role="initial_entry",
            protective_role="initial_protective_stop",
            exit_role="strategy_exit",
        )
    if requested_side == "short":
        return SideOrderSemantics(
            position_side="short",
            signed_quantity=-quantity,
            entry_side="sell",
            protective_side="buy",
            exit_side="buy",
            entry_role="short_entry",
            protective_role="short_protective_stop",
            exit_role="short_cover",
        )
    return SideOrderSemantics(
        position_side="flat",
        signed_quantity=0.0,
        entry_side=None,
        protective_side=None,
        exit_side=None,
        entry_role=None,
        protective_role=None,
        exit_role=None,
    )
