"""Pure broker/internal reconciliation comparison service."""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime

from packages.broker.models import (
    SUPPORTED_BROKER_ASSET_CLASSES,
    BrokerFill,
    BrokerOrder,
    BrokerPosition,
    BrokerProtectiveStop,
    BrokerSnapshot,
)
from packages.core.config import ProtectiveStopConfig
from packages.reconciliation.models import (
    IncidentActionRecommendation,
    IncidentSeverity,
    InternalLedgerSnapshot,
    InternalOrder,
    InternalPosition,
    ReconciliationIncident,
    ReconciliationMismatch,
    ReconciliationMismatchType,
    ReconciliationResult,
)

DEFAULT_ACCOUNT_EQUITY_TOLERANCE_PCT = 0.001
DEFAULT_AVG_ENTRY_PRICE_TOLERANCE_PCT = 0.001
DEFAULT_QUANTITY_TOLERANCE = 1e-6
DEFAULT_STALE_AFTER_SECONDS = 60
TERMINAL_WORKFLOW_STATES = {"completed", "failed", "terminated", "cancelled", "closed"}


def compare_broker_and_internal(
    *,
    broker_snapshot: BrokerSnapshot,
    internal_snapshot: InternalLedgerSnapshot,
    as_of: datetime,
    protective_stop_config: ProtectiveStopConfig,
    account_equity_tolerance_pct: float = DEFAULT_ACCOUNT_EQUITY_TOLERANCE_PCT,
    avg_entry_price_tolerance_pct: float = DEFAULT_AVG_ENTRY_PRICE_TOLERANCE_PCT,
    quantity_tolerance: float = DEFAULT_QUANTITY_TOLERANCE,
    stale_after_seconds: int = DEFAULT_STALE_AFTER_SECONDS,
) -> ReconciliationResult:
    """Compare broker executable state with passive internal ledger state."""

    if as_of.tzinfo is None:
        raise ValueError("as_of must be timezone-aware")
    mismatches: list[ReconciliationMismatch] = []

    _append_staleness_mismatches(
        mismatches,
        broker_snapshot=broker_snapshot,
        internal_snapshot=internal_snapshot,
        as_of=as_of,
        stale_after_seconds=stale_after_seconds,
    )
    _append_account_mismatches(
        mismatches,
        broker_snapshot=broker_snapshot,
        internal_snapshot=internal_snapshot,
        account_equity_tolerance_pct=account_equity_tolerance_pct,
    )
    _append_order_mismatches(mismatches, broker_snapshot.open_orders, internal_snapshot.orders)
    _append_fill_mismatches(mismatches, broker_snapshot.recent_fills, internal_snapshot.fills)
    _append_position_mismatches(
        mismatches,
        broker_positions=broker_snapshot.positions,
        internal_positions=internal_snapshot.positions,
        protective_stops=broker_snapshot.protective_stops,
        as_of=as_of,
        protective_stop_config=protective_stop_config,
        avg_entry_price_tolerance_pct=avg_entry_price_tolerance_pct,
        quantity_tolerance=quantity_tolerance,
    )
    _append_temporal_mismatches(mismatches, internal_snapshot)

    incidents = tuple(_incident_from_mismatch(mismatch) for mismatch in mismatches)
    return ReconciliationResult(
        broker_snapshot=broker_snapshot,
        internal_snapshot=internal_snapshot,
        mismatches=tuple(mismatches),
        incidents=incidents,
    )


def _append_staleness_mismatches(
    mismatches: list[ReconciliationMismatch],
    *,
    broker_snapshot: BrokerSnapshot,
    internal_snapshot: InternalLedgerSnapshot,
    as_of: datetime,
    stale_after_seconds: int,
) -> None:
    broker_age = (as_of - broker_snapshot.as_of).total_seconds()
    internal_age = (as_of - internal_snapshot.as_of).total_seconds()
    if broker_age > stale_after_seconds:
        mismatches.append(
            _mismatch(
                "stale_broker_snapshot",
                "critical",
                "broker snapshot is stale",
                details={"age_seconds": f"{broker_age:.0f}"},
            )
        )
    if internal_age > stale_after_seconds:
        mismatches.append(
            _mismatch(
                "stale_internal_snapshot",
                "critical",
                "internal ledger snapshot is stale",
                details={"age_seconds": f"{internal_age:.0f}"},
            )
        )


def _append_account_mismatches(
    mismatches: list[ReconciliationMismatch],
    *,
    broker_snapshot: BrokerSnapshot,
    internal_snapshot: InternalLedgerSnapshot,
    account_equity_tolerance_pct: float,
) -> None:
    internal_equity = internal_snapshot.account.equity
    diff = abs(broker_snapshot.account.equity - internal_equity)
    diff_pct = diff / internal_equity
    if diff_pct > account_equity_tolerance_pct:
        mismatches.append(
            _mismatch(
                "account_equity_mismatch",
                "critical",
                "broker and internal account equity differ above tolerance",
                details={
                    "broker_equity": f"{broker_snapshot.account.equity:.6f}",
                    "internal_equity": f"{internal_equity:.6f}",
                    "diff_pct": f"{diff_pct:.6f}",
                },
            )
        )


def _append_order_mismatches(
    mismatches: list[ReconciliationMismatch],
    broker_orders: tuple[BrokerOrder, ...],
    internal_orders: tuple[InternalOrder, ...],
) -> None:
    internal_by_client_order_id = {order.client_order_id: order for order in internal_orders}
    open_entry_symbols: list[str] = []
    for order in broker_orders:
        if order.asset_class not in SUPPORTED_BROKER_ASSET_CLASSES:
            mismatches.append(
                _mismatch(
                    "unsupported_broker_asset_class",
                    "critical",
                    "broker order uses unsupported asset class",
                    symbol=order.symbol,
                    client_order_id=order.client_order_id,
                    broker_order_id=order.broker_order_id,
                    details={"asset_class": order.asset_class},
                )
            )
        if order.is_open and order.purpose == "entry" and order.side == "buy":
            open_entry_symbols.append(order.symbol)
        if order.is_open and order.client_order_id not in internal_by_client_order_id:
            mismatches.append(
                _mismatch(
                    "unknown_open_broker_order",
                    "critical",
                    "open broker order is not present in internal ledger",
                    symbol=order.symbol,
                    client_order_id=order.client_order_id,
                    broker_order_id=order.broker_order_id,
                )
            )

    for symbol, count in Counter(open_entry_symbols).items():
        if count > 1:
            mismatches.append(
                _mismatch(
                    "duplicate_open_entry_orders",
                    "critical",
                    "multiple open broker entry orders exist for symbol",
                    symbol=symbol,
                    details={"open_entry_order_count": str(count)},
                )
            )


def _append_fill_mismatches(
    mismatches: list[ReconciliationMismatch],
    broker_fills: tuple[BrokerFill, ...],
    internal_fills: tuple,
) -> None:
    internal_keys = {
        (fill.broker_order_id, fill.client_order_id, fill.symbol, fill.quantity, fill.price)
        for fill in internal_fills
    }
    for fill in broker_fills:
        key = (fill.broker_order_id, fill.client_order_id, fill.symbol, fill.quantity, fill.price)
        if key not in internal_keys:
            mismatches.append(
                _mismatch(
                    "fill_not_recorded_internal",
                    "critical",
                    "broker fill is not recorded in internal ledger",
                    symbol=fill.symbol,
                    client_order_id=fill.client_order_id,
                    broker_order_id=fill.broker_order_id,
                )
            )


def _append_position_mismatches(
    mismatches: list[ReconciliationMismatch],
    *,
    broker_positions: tuple[BrokerPosition, ...],
    internal_positions: tuple[InternalPosition, ...],
    protective_stops: tuple[BrokerProtectiveStop, ...],
    as_of: datetime,
    protective_stop_config: ProtectiveStopConfig,
    avg_entry_price_tolerance_pct: float,
    quantity_tolerance: float,
) -> None:
    broker_by_symbol = {position.symbol: position for position in broker_positions}
    internal_by_symbol = {position.symbol: position for position in internal_positions}
    stops_by_symbol: dict[str, list[BrokerProtectiveStop]] = defaultdict(list)
    for stop in protective_stops:
        stops_by_symbol[stop.symbol].append(stop)

    for stop in protective_stops:
        if stop.is_open and stop.symbol not in broker_by_symbol:
            mismatches.append(
                _mismatch(
                    "orphan_protective_stop_without_position",
                    "critical",
                    "open protective stop exists without a broker position",
                    symbol=stop.symbol,
                    client_order_id=stop.client_order_id,
                    broker_order_id=stop.broker_order_id,
                    details={"stop_quantity": f"{stop.quantity:.6f}", "stop_side": stop.side},
                )
            )

    for symbol, broker_position in broker_by_symbol.items():
        if broker_position.asset_class not in SUPPORTED_BROKER_ASSET_CLASSES:
            mismatches.append(
                _mismatch(
                    "unsupported_broker_asset_class",
                    "critical",
                    "broker position uses unsupported asset class",
                    symbol=symbol,
                    details={"asset_class": broker_position.asset_class},
                )
            )
        if broker_position.quantity < 0:
            mismatches.append(
                _mismatch(
                    "unexpected_short_position",
                    "critical",
                    "broker reports an unexpected short position",
                    symbol=symbol,
                    details={"broker_quantity": f"{broker_position.quantity:.6f}"},
                )
            )
            _append_short_protective_stop_mismatch(
                mismatches,
                broker_position=broker_position,
                protective_stops=tuple(stops_by_symbol.get(symbol, ())),
                quantity_tolerance=quantity_tolerance,
            )
        internal_position = internal_by_symbol.get(symbol)
        if internal_position is None and broker_position.quantity != 0:
            mismatches.append(
                _mismatch(
                    "broker_position_without_internal_position",
                    "critical",
                    "broker position exists without internal position",
                    symbol=symbol,
                )
            )
            continue
        if internal_position is None:
            continue
        _append_position_value_mismatches(
            mismatches,
            broker_position=broker_position,
            internal_position=internal_position,
            avg_entry_price_tolerance_pct=avg_entry_price_tolerance_pct,
            quantity_tolerance=quantity_tolerance,
        )
        _append_protective_stop_mismatch(
            mismatches,
            broker_position=broker_position,
            internal_position=internal_position,
            protective_stops=tuple(stops_by_symbol.get(symbol, ())),
            as_of=as_of,
            protective_stop_config=protective_stop_config,
        )

    for symbol in set(internal_by_symbol).difference(broker_by_symbol):
        mismatches.append(
            _mismatch(
                "internal_position_without_broker_position",
                "critical",
                "internal position exists without broker position",
                symbol=symbol,
            )
        )


def _append_position_value_mismatches(
    mismatches: list[ReconciliationMismatch],
    *,
    broker_position: BrokerPosition,
    internal_position: InternalPosition,
    avg_entry_price_tolerance_pct: float,
    quantity_tolerance: float,
) -> None:
    quantity_diff = abs(broker_position.quantity - internal_position.quantity)
    if quantity_diff > quantity_tolerance:
        mismatches.append(
            _mismatch(
                "quantity_mismatch",
                "critical",
                "broker and internal position quantities differ",
                symbol=broker_position.symbol,
                details={
                    "broker_quantity": f"{broker_position.quantity:.6f}",
                    "internal_quantity": f"{internal_position.quantity:.6f}",
                },
            )
        )
    avg_price_diff_pct = (
        abs(broker_position.avg_entry_price - internal_position.avg_entry_price)
        / internal_position.avg_entry_price
    )
    if avg_price_diff_pct > avg_entry_price_tolerance_pct:
        mismatches.append(
            _mismatch(
                "avg_entry_price_mismatch",
                "critical",
                "broker and internal average entry prices differ above tolerance",
                symbol=broker_position.symbol,
                details={
                    "broker_avg_entry_price": f"{broker_position.avg_entry_price:.6f}",
                    "internal_avg_entry_price": f"{internal_position.avg_entry_price:.6f}",
                    "diff_pct": f"{avg_price_diff_pct:.6f}",
                },
            )
        )


def _append_protective_stop_mismatch(
    mismatches: list[ReconciliationMismatch],
    *,
    broker_position: BrokerPosition,
    internal_position: InternalPosition,
    protective_stops: tuple[BrokerProtectiveStop, ...],
    as_of: datetime,
    protective_stop_config: ProtectiveStopConfig,
) -> None:
    confirmed_stops = [
        stop
        for stop in protective_stops
        if stop.confirmed and stop.is_open and stop.side == "sell"
    ]
    protected_quantity_sum = sum(stop.quantity for stop in confirmed_stops)
    if broker_position.quantity > 0 and protected_quantity_sum > broker_position.quantity + 1e-6:
        mismatches.append(
            _mismatch(
                "oversubscribed_protective_stop_quantity",
                "critical",
                "open protective stop quantity exceeds the open long position quantity",
                symbol=broker_position.symbol,
                details={
                    "broker_position_quantity": f"{broker_position.quantity:.6f}",
                    "protected_quantity_sum": f"{protected_quantity_sum:.6f}",
                },
            )
        )
    if protected_quantity_sum >= broker_position.quantity:
        return
    opened_at = internal_position.opened_at or broker_position.opened_at
    age_seconds = None if opened_at is None else (as_of - opened_at).total_seconds()
    severity, message = _stop_failure_severity(age_seconds, protective_stop_config)
    details = {
        "broker_position_quantity": f"{broker_position.quantity:.6f}",
        "protected_quantity_sum": f"{protected_quantity_sum:.6f}",
        "warning_after_seconds": str(protective_stop_config.warning_after_seconds),
        "critical_after_seconds": str(protective_stop_config.critical_after_seconds),
        "flatten_after_seconds": str(protective_stop_config.flatten_after_seconds),
    }
    if age_seconds is not None:
        details["age_seconds"] = f"{age_seconds:.0f}"
    mismatches.append(
        _mismatch(
            "missing_protective_stop",
            severity,
            message,
            symbol=broker_position.symbol,
            details=details,
        )
    )


def _append_short_protective_stop_mismatch(
    mismatches: list[ReconciliationMismatch],
    *,
    broker_position: BrokerPosition,
    protective_stops: tuple[BrokerProtectiveStop, ...],
    quantity_tolerance: float,
) -> None:
    confirmed_buy_stops = [
        stop
        for stop in protective_stops
        if stop.confirmed and stop.is_open and stop.side == "buy"
    ]
    protected_quantity_sum = sum(stop.quantity for stop in confirmed_buy_stops)
    required_quantity = abs(broker_position.quantity)
    if protected_quantity_sum + quantity_tolerance >= required_quantity:
        return
    mismatches.append(
        _mismatch(
            "short_protective_stop_missing",
            "critical",
            "open short position lacks sufficient verified protective buy-stop quantity",
            symbol=broker_position.symbol,
            details={
                "open_short_quantity": f"{required_quantity:.6f}",
                "protected_buy_stop_quantity_sum": f"{protected_quantity_sum:.6f}",
            },
        )
    )


def _stop_failure_severity(
    age_seconds: float | None,
    config: ProtectiveStopConfig,
) -> tuple[IncidentSeverity, str]:
    if age_seconds is None:
        return "critical", "position exists without protective stop confirmation"
    if age_seconds >= config.flatten_after_seconds:
        return "critical", "protective stop missing beyond flatten threshold"
    if age_seconds >= config.critical_after_seconds:
        return "critical", "protective stop missing beyond critical threshold"
    if age_seconds >= config.warning_after_seconds:
        return "warning", "protective stop missing beyond warning threshold"
    return "warning", "protective stop confirmation is pending"


def _append_temporal_mismatches(
    mismatches: list[ReconciliationMismatch],
    internal_snapshot: InternalLedgerSnapshot,
) -> None:
    for order in internal_snapshot.orders:
        workflow_status = internal_snapshot.order_workflow_status_by_client_order_id.get(
            order.client_order_id
        )
        if order.status == "open" and workflow_status in TERMINAL_WORKFLOW_STATES:
            mismatches.append(
                _mismatch(
                    "temporal_workflow_state_inconsistent",
                    "critical",
                    "open internal order has terminal Temporal workflow state",
                    symbol=order.symbol,
                    client_order_id=order.client_order_id,
                    broker_order_id=order.broker_order_id,
                    details={"workflow_status": workflow_status},
                )
            )
    for position in internal_snapshot.positions:
        workflow_status = internal_snapshot.position_workflow_status_by_symbol.get(position.symbol)
        if workflow_status in TERMINAL_WORKFLOW_STATES:
            mismatches.append(
                _mismatch(
                    "temporal_workflow_state_inconsistent",
                    "critical",
                    "open internal position has terminal Temporal workflow state",
                    symbol=position.symbol,
                    details={"workflow_status": workflow_status},
                )
            )


def _mismatch(
    mismatch_type: ReconciliationMismatchType,
    severity: IncidentSeverity,
    message: str,
    *,
    symbol: str | None = None,
    client_order_id: str | None = None,
    broker_order_id: str | None = None,
    details: dict[str, str] | None = None,
) -> ReconciliationMismatch:
    return ReconciliationMismatch(
        mismatch_type=mismatch_type,
        severity=severity,
        symbol=symbol,
        client_order_id=client_order_id,
        broker_order_id=broker_order_id,
        message=message,
        details=details or {},
    )


def _incident_from_mismatch(mismatch: ReconciliationMismatch) -> ReconciliationIncident:
    action = _recommended_action(mismatch)
    return ReconciliationIncident(
        incident_key=_incident_key(mismatch),
        severity=mismatch.severity,
        recommended_action=action,
        pause_new_risk=action in {"pause_new_risk", "manual_review_required", "flatten_if_safe"},
        reason_code=mismatch.mismatch_type,
        message=mismatch.message,
        details=mismatch.details,
    )


def _recommended_action(mismatch: ReconciliationMismatch) -> IncidentActionRecommendation:
    if mismatch.mismatch_type in {"missing_protective_stop", "short_protective_stop_missing"}:
        age_seconds = mismatch.details.get("age_seconds")
        if age_seconds is not None:
            flatten_after_seconds = float(mismatch.details.get("flatten_after_seconds", "60"))
            if float(age_seconds) >= flatten_after_seconds:
                return "flatten_if_safe"
        if mismatch.severity == "critical":
            return "pause_new_risk"
        return "investigate"
    if mismatch.severity == "critical":
        return "pause_new_risk"
    if mismatch.severity == "warning":
        return "investigate"
    return "none"


def _incident_key(mismatch: ReconciliationMismatch) -> str:
    parts = [
        mismatch.mismatch_type,
        mismatch.symbol or "",
        mismatch.client_order_id or "",
        mismatch.broker_order_id or "",
    ]
    return ":".join(parts).rstrip(":")
