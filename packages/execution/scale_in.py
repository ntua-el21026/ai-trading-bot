"""Deterministic paper-validation scale-in policy helpers.

The functions in this module are pure policy/evidence helpers. They do not submit, cancel,
replace, or flatten broker orders.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from packages.broker.models import BrokerOrder, BrokerProtectiveStop
from packages.core.config import ExecutionConfig, RiskLevelConfig, ScaleInConfig, SystemConfig
from packages.data.models import AssetClass
from packages.execution.execution_intent import create_execution_intent
from packages.execution.models import ExecutionIntent
from packages.risk.models import RiskAssessment

OpenOrderRole = Literal[
    "protective_stop",
    "pending_entry",
    "pending_exit",
    "stale_session_order",
    "unknown_or_ambiguous",
]
EntryActionRole = Literal[
    "initial_entry",
    "scale_in_entry",
    "initial_protective_stop",
    "add_on_protective_stop",
    "exit",
    "cleanup",
    "incident_repair",
]
ScaleInIncidentSeverity = Literal["warning", "critical"]

_EPSILON = 1e-9


class ScaleInModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class OpenOrderRoleClassification(ScaleInModel):
    broker_order_id: str
    client_order_id: str
    symbol: str
    role: OpenOrderRole
    reason_code: str


class AggregateProtectionCheck(ScaleInModel):
    symbol: str
    position_quantity: float
    protected_quantity_sum: float = Field(ge=0)
    passed: bool
    reason_code: str


class SymbolExposureState(ScaleInModel):
    symbol: str
    position_quantity: float
    protected_quantity: float = Field(ge=0)
    existing_entry_count: int = Field(ge=0)
    existing_add_entry_count: int = Field(ge=0)
    unresolved_incident_count: int = Field(ge=0)
    broker_reconciliation_clean: bool
    current_symbol_notional: float = Field(ge=0)
    current_portfolio_exposure: float = Field(ge=0)
    current_symbol_risk_at_stop: float = Field(ge=0)
    current_portfolio_risk_at_stop: float = Field(ge=0)
    account_equity: float = Field(gt=0)
    active_scale_in_intent: bool = False
    active_scale_in_signal_ids: tuple[str, ...] = ()
    pending_scale_in_stop_unverified: bool = False

    @field_validator("symbol")
    @classmethod
    def validate_symbol(cls, symbol: str) -> str:
        if symbol != symbol.upper():
            raise ValueError("symbol must be uppercase")
        return symbol


class ScaleInCandidate(ScaleInModel):
    symbol: str
    asset_class: AssetClass
    signal_id: str
    add_quantity: int = Field(gt=0)
    entry_price: float = Field(gt=0)
    stop_loss_price: float | None = Field(default=None, gt=0)
    deterministic_add_on_signal: bool

    @field_validator("symbol")
    @classmethod
    def validate_symbol(cls, symbol: str) -> str:
        if symbol != symbol.upper():
            raise ValueError("symbol must be uppercase")
        return symbol

    @model_validator(mode="after")
    def validate_supported_asset(self) -> Self:
        if self.asset_class not in {"equity", "etf"}:
            raise ValueError("scale-in candidates support equities and ETFs only")
        return self

    @property
    def proposed_notional(self) -> float:
        return float(self.add_quantity) * self.entry_price

    @property
    def proposed_risk_at_stop(self) -> float | None:
        if self.stop_loss_price is None:
            return None
        stop_distance = self.entry_price - self.stop_loss_price
        if stop_distance <= 0:
            return None
        return float(self.add_quantity) * stop_distance


class ScaleInEligibilityResult(ScaleInModel):
    symbol: str
    allowed: bool
    action_role: EntryActionRole = "scale_in_entry"
    reason_codes: tuple[str, ...]
    open_order_roles: tuple[OpenOrderRoleClassification, ...]
    aggregate_protection: AggregateProtectionCheck
    total_symbol_quantity_after: float
    total_symbol_notional_after: float
    total_symbol_risk_at_stop_after: float | None


class ScaleInStopAction(ScaleInModel):
    symbol: str
    action_role: EntryActionRole = "add_on_protective_stop"
    filled_quantity: float = Field(gt=0)
    add_on_stop_required: bool
    add_on_stop_client_order_id: str
    cancel_existing_stops: bool = False
    replace_existing_stops: bool = False


class ScaleInIncident(ScaleInModel):
    symbol: str
    severity: ScaleInIncidentSeverity
    reason_code: str
    message: str
    pause_new_risk: bool = True
    details: dict[str, str] = Field(default_factory=dict)


class ScaleInStopOutcome(ScaleInModel):
    symbol: str
    filled_quantity: float = Field(ge=0)
    stop_submitted: bool
    stop_verified: bool
    incident: ScaleInIncident | None = None


class ScaleInEvidence(ScaleInModel):
    symbol: str
    action_role: EntryActionRole
    success: bool
    total_symbol_quantity_after: float = Field(ge=0)
    protected_quantity_after: float = Field(ge=0)
    reason_codes: tuple[str, ...] = ()
    incident_reason_codes: tuple[str, ...] = ()
    real_broker_writes_performed: bool = False


def classify_open_order_role(
    order: BrokerOrder,
    *,
    stale_session_client_order_ids: tuple[str, ...] = (),
) -> OpenOrderRoleClassification:
    """Classify one broker order into a deterministic scale-in role."""

    if order.client_order_id in stale_session_client_order_ids:
        return _classification(order, "stale_session_order", "stale_session_order")
    if order.purpose == "protective_stop" or (
        order.side == "sell" and order.order_type in {"stop", "stop_limit"}
    ):
        return _classification(order, "protective_stop", "open_protective_stop")
    if order.purpose == "entry" or (order.side == "buy" and order.order_type == "limit"):
        return _classification(order, "pending_entry", "open_entry_order")
    if order.purpose == "risk_reducing_exit" or (
        order.side == "sell" and order.order_type in {"market", "limit"}
    ):
        return _classification(order, "pending_exit", "open_exit_order")
    return _classification(order, "unknown_or_ambiguous", "open_order_role_ambiguous")


def classify_symbol_open_orders(
    orders: tuple[BrokerOrder, ...],
    *,
    symbol: str,
    stale_session_client_order_ids: tuple[str, ...] = (),
) -> tuple[OpenOrderRoleClassification, ...]:
    normalized_symbol = symbol.upper()
    return tuple(
        classify_open_order_role(
            order,
            stale_session_client_order_ids=stale_session_client_order_ids,
        )
        for order in orders
        if order.symbol == normalized_symbol and order.is_open
    )


def check_aggregate_protection(
    *,
    symbol: str,
    position_quantity: float,
    protective_stops: tuple[BrokerProtectiveStop, ...],
) -> AggregateProtectionCheck:
    normalized_symbol = symbol.upper()
    protected_quantity_sum = sum(
        stop.quantity
        for stop in protective_stops
        if stop.symbol == normalized_symbol and stop.confirmed and stop.is_open
    )
    passed = protected_quantity_sum + _EPSILON >= max(position_quantity, 0.0)
    return AggregateProtectionCheck(
        symbol=normalized_symbol,
        position_quantity=position_quantity,
        protected_quantity_sum=protected_quantity_sum,
        passed=passed,
        reason_code="aggregate_protection_ok" if passed else "aggregate_protection_shortfall",
    )


def evaluate_scale_in_eligibility(
    *,
    candidate: ScaleInCandidate,
    exposure: SymbolExposureState,
    policy: ScaleInConfig,
    risk_config: RiskLevelConfig,
    open_orders: tuple[BrokerOrder, ...] = (),
    stale_session_client_order_ids: tuple[str, ...] = (),
) -> ScaleInEligibilityResult:
    if exposure.symbol != candidate.symbol:
        raise ValueError("candidate and exposure symbols must match")

    order_roles = classify_symbol_open_orders(
        open_orders,
        symbol=candidate.symbol,
        stale_session_client_order_ids=stale_session_client_order_ids,
    )
    aggregate_protection = AggregateProtectionCheck(
        symbol=exposure.symbol,
        position_quantity=exposure.position_quantity,
        protected_quantity_sum=exposure.protected_quantity,
        passed=exposure.protected_quantity + _EPSILON >= max(exposure.position_quantity, 0.0),
        reason_code=(
            "aggregate_protection_ok"
            if exposure.protected_quantity + _EPSILON >= max(exposure.position_quantity, 0.0)
            else "aggregate_protection_shortfall"
        ),
    )
    total_quantity_after = exposure.position_quantity + candidate.add_quantity
    total_notional_after = exposure.current_symbol_notional + candidate.proposed_notional
    proposed_risk = candidate.proposed_risk_at_stop
    total_symbol_risk_after = (
        None if proposed_risk is None else exposure.current_symbol_risk_at_stop + proposed_risk
    )

    blockers: list[str] = []
    if not policy.enabled_for_paper_validation:
        blockers.append("scale_in_disabled")
    if exposure.position_quantity < 0:
        blockers.append("existing_position_not_long_only")
    elif exposure.position_quantity <= _EPSILON:
        blockers.append("existing_long_position_required")
    if exposure.position_quantity >= policy.max_total_symbol_qty:
        blockers.append("max_total_symbol_qty_reached")
    if policy.require_existing_stop_verified and not aggregate_protection.passed:
        blockers.append("existing_position_not_fully_protected")
    if exposure.unresolved_incident_count > policy.max_unresolved_incidents_per_symbol:
        blockers.append("unresolved_symbol_incident_present")
    if not exposure.broker_reconciliation_clean:
        blockers.append("broker_reconciliation_not_clean")
    if exposure.existing_entry_count >= policy.max_entries_per_symbol:
        blockers.append("max_entries_per_symbol_reached")
    if exposure.existing_add_entry_count >= policy.max_add_entries_per_symbol:
        blockers.append("max_add_entries_per_symbol_reached")
    if candidate.add_quantity > policy.max_scale_in_qty:
        blockers.append("max_scale_in_qty_exceeded")
    if candidate.add_quantity > policy.max_new_entry_qty:
        blockers.append("max_new_entry_qty_exceeded")
    if total_quantity_after > policy.max_total_symbol_qty:
        blockers.append("max_total_symbol_qty_exceeded")
    if policy.require_add_on_signal and not candidate.deterministic_add_on_signal:
        blockers.append("deterministic_add_on_signal_required")
    if policy.protective_stop_required_after_scale_in and candidate.stop_loss_price is None:
        blockers.append("missing_add_on_protective_stop_price")
    if candidate.proposed_risk_at_stop is None:
        blockers.append("invalid_add_on_stop_distance")
    if exposure.active_scale_in_intent:
        blockers.append("active_scale_in_intent_present")
    if candidate.signal_id in exposure.active_scale_in_signal_ids:
        blockers.append("active_scale_in_signal_intent_present")
    if exposure.pending_scale_in_stop_unverified:
        blockers.append("previous_scale_in_stop_unverified")

    blockers.extend(_order_role_blockers(order_roles, policy))
    blockers.extend(
        _risk_limit_blockers(
            exposure=exposure,
            candidate=candidate,
            risk_config=risk_config,
            total_notional_after=total_notional_after,
            total_symbol_risk_after=total_symbol_risk_after,
        )
    )
    reason_codes = tuple(dict.fromkeys(blockers))
    return ScaleInEligibilityResult(
        symbol=candidate.symbol,
        allowed=not reason_codes,
        reason_codes=reason_codes,
        open_order_roles=order_roles,
        aggregate_protection=aggregate_protection,
        total_symbol_quantity_after=total_quantity_after,
        total_symbol_notional_after=total_notional_after,
        total_symbol_risk_at_stop_after=total_symbol_risk_after,
    )


def create_scale_in_execution_intent(
    *,
    decision_id: UUID,
    candidate: ScaleInCandidate,
    eligibility: ScaleInEligibilityResult,
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
    if not eligibility.allowed:
        raise ValueError("cannot create scale-in ExecutionIntent when eligibility is refused")
    scale_in_strategy_version = f"{strategy_version}_scale_in"
    return create_execution_intent(
        decision_id=decision_id,
        symbol=candidate.symbol,
        side="buy",
        asset_class=candidate.asset_class,
        quantity=candidate.add_quantity,
        limit_price=candidate.entry_price,
        stop_loss_price=candidate.stop_loss_price,
        strategy_version=scale_in_strategy_version,
        risk_config_version=risk_config_version,
        expires_at=expires_at,
        trade_date=trade_date,
        intent_sequence=intent_sequence,
        risk_assessment=risk_assessment,
        system_config=system_config,
        execution_config=execution_config,
        temporal_workflow_id=temporal_workflow_id,
    )


def build_add_on_stop_action(
    *,
    intent: ExecutionIntent,
    filled_quantity: float,
    policy: ScaleInConfig,
) -> ScaleInStopAction:
    if filled_quantity <= 0:
        raise ValueError("filled_quantity must be positive for add-on stop action")
    if policy.allow_stop_replacement or policy.allow_stop_cancel_before_scale_in:
        raise ValueError("scale-in policy must not cancel or replace existing stops")
    return ScaleInStopAction(
        symbol=intent.symbol,
        filled_quantity=filled_quantity,
        add_on_stop_required=policy.protective_stop_required_after_scale_in,
        add_on_stop_client_order_id=f"{intent.client_order_id_root}-stop",
    )


def evaluate_add_on_stop_outcome(
    *,
    symbol: str,
    filled_quantity: float,
    stop_submitted: bool,
    stop_verified: bool,
    reason: str | None = None,
) -> ScaleInStopOutcome:
    incident = None
    if filled_quantity > 0 and (not stop_submitted or not stop_verified):
        incident = ScaleInIncident(
            symbol=symbol.upper(),
            severity="critical",
            reason_code="scale_in_add_on_stop_unverified",
            message="scale-in filled quantity does not have a verified additive protective stop",
            details={
                "filled_quantity": f"{filled_quantity:.6f}",
                "reason": reason or "add_on_stop_not_verified",
            },
        )
    return ScaleInStopOutcome(
        symbol=symbol.upper(),
        filled_quantity=filled_quantity,
        stop_submitted=stop_submitted,
        stop_verified=stop_verified,
        incident=incident,
    )


def scale_in_evidence_from_result(
    *,
    eligibility: ScaleInEligibilityResult,
    protected_quantity_after: float,
    stop_outcome: ScaleInStopOutcome | None = None,
) -> ScaleInEvidence:
    incident_codes = (
        ()
        if stop_outcome is None or stop_outcome.incident is None
        else (stop_outcome.incident.reason_code,)
    )
    return ScaleInEvidence(
        symbol=eligibility.symbol,
        action_role="scale_in_entry",
        success=eligibility.allowed and not incident_codes,
        total_symbol_quantity_after=eligibility.total_symbol_quantity_after,
        protected_quantity_after=protected_quantity_after,
        reason_codes=eligibility.reason_codes,
        incident_reason_codes=incident_codes,
    )


def _classification(
    order: BrokerOrder,
    role: OpenOrderRole,
    reason_code: str,
) -> OpenOrderRoleClassification:
    return OpenOrderRoleClassification(
        broker_order_id=order.broker_order_id,
        client_order_id=order.client_order_id,
        symbol=order.symbol,
        role=role,
        reason_code=reason_code,
    )


def _order_role_blockers(
    order_roles: tuple[OpenOrderRoleClassification, ...],
    policy: ScaleInConfig,
) -> tuple[str, ...]:
    pending_entry_count = sum(1 for item in order_roles if item.role == "pending_entry")
    blockers: list[str] = []
    if (
        policy.require_no_pending_entry_order
        and pending_entry_count > policy.max_pending_entry_orders_per_symbol
    ):
        blockers.append("pending_entry_order_present")
    if any(item.role == "unknown_or_ambiguous" for item in order_roles):
        blockers.append("ambiguous_open_order_present")
    if any(item.role == "stale_session_order" for item in order_roles):
        blockers.append("stale_session_order_present")
    if any(item.role == "pending_exit" for item in order_roles):
        blockers.append("pending_exit_order_present")
    return tuple(blockers)


def _risk_limit_blockers(
    *,
    exposure: SymbolExposureState,
    candidate: ScaleInCandidate,
    risk_config: RiskLevelConfig,
    total_notional_after: float,
    total_symbol_risk_after: float | None,
) -> tuple[str, ...]:
    blockers: list[str] = []
    symbol_notional_limit = exposure.account_equity * risk_config.max_position_size_pct
    if total_notional_after > symbol_notional_limit:
        blockers.append("aggregate_symbol_notional_cap_exceeded")

    portfolio_exposure_after = exposure.current_portfolio_exposure + candidate.proposed_notional
    portfolio_exposure_limit = exposure.account_equity * risk_config.max_gross_exposure_pct
    if portfolio_exposure_after > portfolio_exposure_limit:
        blockers.append("portfolio_exposure_cap_exceeded")

    symbol_risk_limit = exposure.account_equity * risk_config.max_risk_per_trade_pct
    if total_symbol_risk_after is not None and total_symbol_risk_after > symbol_risk_limit:
        blockers.append("aggregate_risk_at_stop_cap_exceeded")

    portfolio_risk_after = (
        None
        if candidate.proposed_risk_at_stop is None
        else exposure.current_portfolio_risk_at_stop + candidate.proposed_risk_at_stop
    )
    portfolio_risk_limit = (
        exposure.account_equity
        * risk_config.max_risk_per_trade_pct
        * risk_config.max_open_positions
    )
    if portfolio_risk_after is not None and portfolio_risk_after > portfolio_risk_limit:
        blockers.append("portfolio_risk_at_stop_cap_exceeded")
    return tuple(blockers)
