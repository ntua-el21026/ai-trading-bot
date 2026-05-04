"""ExecutionIntent construction helpers."""

from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from packages.core.config import ExecutionConfig, SystemConfig
from packages.data.models import AssetClass
from packages.execution.idempotency import build_client_order_id_root
from packages.execution.models import ExecutionIntent, ExecutionSide
from packages.risk.models import RiskAssessment


def create_execution_intent(
    *,
    decision_id: UUID,
    symbol: str,
    side: ExecutionSide,
    asset_class: AssetClass,
    quantity: int,
    limit_price: float,
    stop_loss_price: float | None,
    strategy_version: str,
    risk_config_version: str,
    expires_at: datetime,
    trade_date: date,
    intent_sequence: int,
    risk_assessment: RiskAssessment,
    system_config: SystemConfig,
    execution_config: ExecutionConfig,
    temporal_workflow_id: str | None = None,
) -> ExecutionIntent:
    if not risk_assessment.approved:
        raise ValueError("cannot create ExecutionIntent without approved risk assessment")
    if risk_assessment.symbol != symbol:
        raise ValueError("risk assessment symbol must match execution intent symbol")
    client_order_id_root = build_client_order_id_root(
        strategy_version=strategy_version,
        symbol=symbol,
        side=side,
        trade_date=trade_date,
        intent_sequence=intent_sequence,
        decision_id=str(decision_id),
    )
    return ExecutionIntent(
        decision_id=decision_id,
        symbol=symbol,
        side=side,
        asset_class=asset_class,
        quantity=quantity,
        entry_order_type=execution_config.entry_order_type,
        limit_price=limit_price,
        stop_loss_price=stop_loss_price,
        time_in_force=execution_config.entry_time_in_force,
        strategy_version=strategy_version,
        risk_config_version=risk_config_version,
        autonomy_level=system_config.autonomy_level,
        requires_protective_stop=execution_config.require_protective_stop,
        max_acceptable_slippage_bps=execution_config.max_acceptable_slippage_bps,
        expires_at=expires_at,
        client_order_id_root=client_order_id_root,
        status="risk_approved",
        temporal_workflow_id=temporal_workflow_id,
    )


def intent_is_expired(intent: ExecutionIntent, *, as_of: datetime) -> bool:
    if as_of.tzinfo is None:
        raise ValueError("as_of must be timezone-aware")
    return as_of >= intent.expires_at
