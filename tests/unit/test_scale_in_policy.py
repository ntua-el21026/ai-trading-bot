from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from typing import Literal
from uuid import uuid4

import pytest

from packages.broker.fakes import DEFAULT_AS_OF, FakeAlpacaClient, build_fake_alpaca_paper_adapter
from packages.broker.models import (
    BrokerAccountSnapshot,
    BrokerOrder,
    BrokerPosition,
    BrokerProtectiveStop,
    BrokerSnapshot,
)
from packages.core.config import ScaleInConfig, load_app_config
from packages.execution.execution_intent import create_execution_intent
from packages.execution.scale_in import (
    ScaleInCandidate,
    ScaleInEligibilityResult,
    ScaleInEvidence,
    SymbolExposureState,
    build_add_on_stop_action,
    check_aggregate_protection,
    classify_open_order_role,
    create_scale_in_execution_intent,
    evaluate_add_on_stop_outcome,
    evaluate_scale_in_eligibility,
)
from packages.reconciliation.models import (
    InternalAccountSnapshot,
    InternalLedgerSnapshot,
    InternalPosition,
)
from packages.reconciliation.service import compare_broker_and_internal
from packages.risk.models import RiskAssessment, RiskCheckResult

AS_OF = datetime(2026, 5, 13, 14, 30, tzinfo=UTC)
EXPECTED_FULL_UNIVERSE = (
    "SPY",
    "QQQ",
    "DIA",
    "IWM",
    "XLK",
    "XLF",
    "XLE",
    "XLV",
    "AAPL",
    "MSFT",
    "NVDA",
    "AMZN",
    "META",
    "GOOGL",
)


def _policy(**updates: object) -> ScaleInConfig:
    config = load_app_config().scale_in
    return ScaleInConfig.model_validate(config.model_dump() | updates)


def _candidate(**updates: object) -> ScaleInCandidate:
    data: dict[str, object] = {
        "symbol": "AAPL",
        "asset_class": "equity",
        "signal_id": "breakout-continuation-20260513",
        "add_quantity": 1,
        "entry_price": 100.0,
        "stop_loss_price": 98.0,
        "deterministic_add_on_signal": True,
    }
    data.update(updates)
    return ScaleInCandidate.model_validate(data)


def _exposure(**updates: object) -> SymbolExposureState:
    data: dict[str, object] = {
        "symbol": "AAPL",
        "position_quantity": 1.0,
        "protected_quantity": 1.0,
        "existing_entry_count": 1,
        "existing_add_entry_count": 0,
        "unresolved_incident_count": 0,
        "broker_reconciliation_clean": True,
        "current_symbol_notional": 100.0,
        "current_portfolio_exposure": 300.0,
        "current_symbol_risk_at_stop": 2.0,
        "current_portfolio_risk_at_stop": 6.0,
        "account_equity": 100_000.0,
    }
    data.update(updates)
    return SymbolExposureState.model_validate(data)


def _order(
    *,
    symbol: str = "AAPL",
    side: Literal["buy", "sell"] = "sell",
    order_type: Literal["market", "limit", "stop", "stop_limit"] = "stop",
    purpose: Literal["entry", "protective_stop", "risk_reducing_exit", "unknown"] = (
        "protective_stop"
    ),
    client_order_id: str = "stop-AAPL-1",
    broker_order_id: str = "broker-stop-AAPL-1",
) -> BrokerOrder:
    return BrokerOrder(
        broker_order_id=broker_order_id,
        client_order_id=client_order_id,
        symbol=symbol,
        side=side,
        asset_class="equity",
        quantity=1.0,
        filled_quantity=0.0,
        order_type=order_type,
        time_in_force="gtc" if order_type in {"stop", "stop_limit"} else "day",
        status="accepted",
        limit_price=100.0 if order_type == "limit" else None,
        stop_price=95.0 if order_type in {"stop", "stop_limit"} else None,
        purpose=purpose,
        submitted_at=AS_OF - timedelta(minutes=5),
    )


def _stop(symbol: str = "AAPL", quantity: float = 1.0) -> BrokerProtectiveStop:
    return BrokerProtectiveStop(
        broker_order_id=f"broker-stop-{symbol}-{quantity}",
        client_order_id=f"stop-{symbol}-{quantity}",
        symbol=symbol,
        quantity=quantity,
        stop_price=95.0,
        status="accepted",
        confirmed=True,
        submitted_at=AS_OF - timedelta(minutes=5),
    )


def _approved_risk(symbol: str = "AAPL") -> RiskAssessment:
    return RiskAssessment(
        symbol=symbol,
        approved=True,
        checks=(
            RiskCheckResult(
                name="scale_in_test",
                passed=True,
                severity="info",
                reason_code="scale_in_test_passed",
            ),
        ),
    )


def _eligibility(
    *,
    exposure: SymbolExposureState | None = None,
    candidate: ScaleInCandidate | None = None,
    policy: ScaleInConfig | None = None,
    open_orders: tuple[BrokerOrder, ...] = (),
) -> ScaleInEligibilityResult:
    config = load_app_config()
    return evaluate_scale_in_eligibility(
        candidate=candidate or _candidate(),
        exposure=exposure or _exposure(),
        policy=policy or config.scale_in,
        risk_config=config.risk_level_4_micro_live,
        open_orders=open_orders,
    )


def test_scale_in_config_loads_with_expected_defaults() -> None:
    config = load_app_config()

    assert config.scale_in.enabled_for_paper_validation is True
    assert config.scale_in.max_entries_per_symbol == 2
    assert config.scale_in.max_add_entries_per_symbol == 1
    assert config.scale_in.max_new_entry_qty == 1
    assert config.scale_in.max_scale_in_qty == 1
    assert config.scale_in.max_total_symbol_qty == 2
    assert config.scale_in.max_pending_entry_orders_per_symbol == 0
    assert config.scale_in.max_unresolved_incidents_per_symbol == 0
    assert config.scale_in.stop_policy == "additive_stop_for_added_quantity"
    assert config.scale_in.allow_stop_replacement is False
    assert config.scale_in.allow_stop_cancel_before_scale_in is False


def test_scale_in_disabled_blocks_scale_in() -> None:
    result = _eligibility(policy=_policy(enabled_for_paper_validation=False))

    assert result.allowed is False
    assert "scale_in_disabled" in result.reason_codes


def test_existing_long_position_with_verified_stop_can_be_scale_in_eligible() -> None:
    result = _eligibility()

    assert result.allowed is True
    assert result.reason_codes == ()
    assert result.total_symbol_quantity_after == 2.0


def test_existing_long_position_without_verified_stop_blocks_scale_in() -> None:
    result = _eligibility(exposure=_exposure(protected_quantity=0.0))

    assert result.allowed is False
    assert "existing_position_not_fully_protected" in result.reason_codes


def test_pending_entry_order_blocks_scale_in() -> None:
    pending_entry = _order(
        side="buy",
        order_type="limit",
        purpose="entry",
        client_order_id="entry-AAPL-pending",
        broker_order_id="broker-entry-AAPL-pending",
    )

    result = _eligibility(open_orders=(pending_entry,))

    assert result.allowed is False
    assert "pending_entry_order_present" in result.reason_codes


def test_verified_protective_stop_order_does_not_block_scale_in() -> None:
    protective_stop = _order()

    result = _eligibility(open_orders=(protective_stop,))

    assert result.allowed is True
    assert result.open_order_roles[0].role == "protective_stop"


def test_unknown_ambiguous_order_blocks_scale_in() -> None:
    unknown = _order(
        side="buy",
        order_type="market",
        purpose="unknown",
        client_order_id="manual-AAPL-market",
        broker_order_id="broker-manual-AAPL-market",
    )

    result = _eligibility(open_orders=(unknown,))

    assert result.allowed is False
    assert "ambiguous_open_order_present" in result.reason_codes


def test_unresolved_symbol_incident_blocks_scale_in() -> None:
    result = _eligibility(exposure=_exposure(unresolved_incident_count=1))

    assert result.allowed is False
    assert "unresolved_symbol_incident_present" in result.reason_codes


def test_scale_in_refuses_when_max_entries_reached() -> None:
    result = _eligibility(exposure=_exposure(existing_entry_count=2))

    assert result.allowed is False
    assert "max_entries_per_symbol_reached" in result.reason_codes


def test_scale_in_refuses_when_max_total_symbol_qty_would_be_exceeded() -> None:
    result = _eligibility(
        exposure=_exposure(position_quantity=1.5, protected_quantity=1.5)
    )

    assert result.allowed is False
    assert "max_total_symbol_qty_exceeded" in result.reason_codes


def test_scale_in_refuses_when_max_add_entries_reached() -> None:
    result = _eligibility(exposure=_exposure(existing_add_entry_count=1))

    assert result.allowed is False
    assert "max_add_entries_per_symbol_reached" in result.reason_codes


def test_scale_in_refuses_when_symbol_notional_cap_would_be_exceeded() -> None:
    result = _eligibility(exposure=_exposure(current_symbol_notional=3_950.0))

    assert result.allowed is False
    assert "aggregate_symbol_notional_cap_exceeded" in result.reason_codes


def test_scale_in_refuses_when_portfolio_exposure_cap_would_be_exceeded() -> None:
    result = _eligibility(exposure=_exposure(current_portfolio_exposure=19_950.0))

    assert result.allowed is False
    assert "portfolio_exposure_cap_exceeded" in result.reason_codes


def test_scale_in_refuses_when_aggregate_risk_at_stop_cap_would_be_exceeded() -> None:
    result = _eligibility(exposure=_exposure(current_symbol_risk_at_stop=349.0))

    assert result.allowed is False
    assert "aggregate_risk_at_stop_cap_exceeded" in result.reason_codes


def test_scale_in_refuses_without_deterministic_add_on_signal() -> None:
    result = _eligibility(candidate=_candidate(deterministic_add_on_signal=False))

    assert result.allowed is False
    assert "deterministic_add_on_signal_required" in result.reason_codes


def test_scale_in_creates_valid_execution_intent_when_eligible() -> None:
    config = load_app_config()
    result = _eligibility()
    intent = create_scale_in_execution_intent(
        decision_id=uuid4(),
        candidate=_candidate(),
        eligibility=result,
        strategy_version=config.strategy.name,
        risk_config_version="risk_v0_4",
        expires_at=datetime(2026, 5, 13, 15, 0, tzinfo=UTC),
        trade_date=date(2026, 5, 13),
        intent_sequence=2,
        risk_assessment=_approved_risk(),
        system_config=config.system,
        execution_config=config.execution,
    )

    assert intent.symbol == "AAPL"
    assert intent.quantity == 1
    assert intent.stop_loss_price == 98.0
    assert intent.status == "risk_approved"
    assert "scale_in" in intent.strategy_version
    assert "scale_in" in intent.client_order_id_root


def test_scale_in_uses_distinct_intent_metadata_from_initial_entries() -> None:
    config = load_app_config()
    initial = create_execution_intent(
        decision_id=uuid4(),
        symbol="AAPL",
        side="buy",
        asset_class="equity",
        quantity=1,
        limit_price=100.0,
        stop_loss_price=98.0,
        strategy_version=config.strategy.name,
        risk_config_version="risk_v0_4",
        expires_at=datetime(2026, 5, 13, 15, 0, tzinfo=UTC),
        trade_date=date(2026, 5, 13),
        intent_sequence=1,
        risk_assessment=_approved_risk(),
        system_config=config.system,
        execution_config=config.execution,
    )
    scale_in = create_scale_in_execution_intent(
        decision_id=uuid4(),
        candidate=_candidate(),
        eligibility=_eligibility(),
        strategy_version=config.strategy.name,
        risk_config_version="risk_v0_4",
        expires_at=datetime(2026, 5, 13, 15, 0, tzinfo=UTC),
        trade_date=date(2026, 5, 13),
        intent_sequence=2,
        risk_assessment=_approved_risk(),
        system_config=config.system,
        execution_config=config.execution,
    )

    assert initial.client_order_id_root != scale_in.client_order_id_root
    assert "scale_in" not in initial.client_order_id_root
    assert "scale_in" in scale_in.client_order_id_root


def test_add_on_fill_requires_additive_stop_and_does_not_cancel_existing_stop() -> None:
    config = load_app_config()
    intent = create_scale_in_execution_intent(
        decision_id=uuid4(),
        candidate=_candidate(),
        eligibility=_eligibility(),
        strategy_version=config.strategy.name,
        risk_config_version="risk_v0_4",
        expires_at=datetime(2026, 5, 13, 15, 0, tzinfo=UTC),
        trade_date=date(2026, 5, 13),
        intent_sequence=2,
        risk_assessment=_approved_risk(),
        system_config=config.system,
        execution_config=config.execution,
    )
    action = build_add_on_stop_action(
        intent=intent,
        filled_quantity=1.0,
        policy=config.scale_in,
    )
    client = FakeAlpacaClient(
        orders=(_fake_stop_order_payload("AAPL", "existing-stop", "existing-stop-client"),),
        positions=(_fake_position_payload("AAPL", 2.0),),
    )
    adapter = build_fake_alpaca_paper_adapter(client=client)

    stop_result = adapter.submit_protective_stop(intent, filled_quantity=1.0)
    verify = adapter.verify_protective_stop(
        symbol="AAPL",
        required_quantity=1.0,
        client_order_id=action.add_on_stop_client_order_id,
    )

    assert action.add_on_stop_required is True
    assert action.cancel_existing_stops is False
    assert action.replace_existing_stops is False
    assert stop_result.status == "succeeded"
    assert verify.protected is True
    assert client.cancelled_broker_order_ids == []


def test_aggregate_protection_check_passes_when_sum_covers_position_quantity() -> None:
    result = check_aggregate_protection(
        symbol="AAPL",
        position_quantity=2.0,
        protective_stops=(_stop(quantity=1.0), _stop(quantity=1.0)),
    )

    assert result.passed is True
    assert result.protected_quantity_sum == 2.0


def test_aggregate_protection_check_fails_when_sum_is_below_position_quantity() -> None:
    result = check_aggregate_protection(
        symbol="AAPL",
        position_quantity=2.0,
        protective_stops=(_stop(quantity=1.0),),
    )

    assert result.passed is False
    assert result.reason_code == "aggregate_protection_shortfall"


def test_reconciliation_accepts_additive_protective_stop_quantity_sum() -> None:
    broker_snapshot = BrokerSnapshot(
        account=_broker_account(),
        positions=(_broker_position("AAPL", 2.0),),
        protective_stops=(_stop(quantity=1.0), _stop(quantity=1.0)),
        as_of=AS_OF,
    )
    internal_snapshot = InternalLedgerSnapshot(
        account=_internal_account(),
        positions=(_internal_position("AAPL", 2.0),),
        as_of=AS_OF,
    )

    result = compare_broker_and_internal(
        broker_snapshot=broker_snapshot,
        internal_snapshot=internal_snapshot,
        as_of=AS_OF,
        protective_stop_config=load_app_config().protective_stop,
    )

    assert result.clean is True


def test_failed_add_on_stop_submission_produces_structured_incident() -> None:
    outcome = evaluate_add_on_stop_outcome(
        symbol="AAPL",
        filled_quantity=1.0,
        stop_submitted=False,
        stop_verified=False,
        reason="submit_failed",
    )

    assert outcome.incident is not None
    assert outcome.incident.severity == "critical"
    assert outcome.incident.reason_code == "scale_in_add_on_stop_unverified"
    assert outcome.incident.pause_new_risk is True


def test_duplicate_active_scale_in_intent_is_blocked() -> None:
    result = _eligibility(
        exposure=_exposure(active_scale_in_signal_ids=("breakout-continuation-20260513",))
    )

    assert result.allowed is False
    assert "active_scale_in_signal_intent_present" in result.reason_codes


def test_reporting_evidence_distinguishes_initial_entry_from_scale_in_entry() -> None:
    initial = ScaleInEvidence(
        symbol="AAPL",
        action_role="initial_entry",
        success=True,
        total_symbol_quantity_after=1.0,
        protected_quantity_after=1.0,
    )
    scale_in = ScaleInEvidence(
        symbol="AAPL",
        action_role="scale_in_entry",
        success=True,
        total_symbol_quantity_after=2.0,
        protected_quantity_after=2.0,
    )

    assert initial.action_role == "initial_entry"
    assert scale_in.action_role == "scale_in_entry"
    assert scale_in.real_broker_writes_performed is False


def test_full_universe_remains_eligible_for_evaluation_without_forced_trades() -> None:
    config = load_app_config()

    assert config.live_universe.symbols == EXPECTED_FULL_UNIVERSE
    assert all(symbol in config.live_universe.symbols for symbol in EXPECTED_FULL_UNIVERSE)


@pytest.mark.parametrize("symbol", ("AAPL", "MSFT", "XLK"))
def test_existing_m39_m40_m42_protected_holds_are_potential_scale_in_candidates(
    symbol: str,
) -> None:
    asset_class = "etf" if symbol == "XLK" else "equity"
    result = _eligibility(
        exposure=_exposure(symbol=symbol),
        candidate=_candidate(symbol=symbol, asset_class=asset_class),
    )

    assert result.allowed is True
    assert result.action_role == "scale_in_entry"


def test_protected_position_without_add_on_signal_is_evaluated_but_not_allowed() -> None:
    result = _eligibility(candidate=_candidate(deterministic_add_on_signal=False))

    assert result.aggregate_protection.passed is True
    assert "deterministic_add_on_signal_required" in result.reason_codes


def test_open_order_role_classification_is_deterministic() -> None:
    assert classify_open_order_role(_order()).role == "protective_stop"
    assert (
        classify_open_order_role(
            _order(
                side="buy",
                order_type="limit",
                purpose="entry",
                client_order_id="entry",
                broker_order_id="broker-entry",
            )
        ).role
        == "pending_entry"
    )
    assert (
        classify_open_order_role(
            _order(
                side="sell",
                order_type="limit",
                purpose="risk_reducing_exit",
                client_order_id="exit",
                broker_order_id="broker-exit",
            )
        ).role
        == "pending_exit"
    )
    assert (
        classify_open_order_role(
            _order(
                side="buy",
                order_type="market",
                purpose="unknown",
                client_order_id="unknown",
                broker_order_id="broker-unknown",
            )
        ).role
        == "unknown_or_ambiguous"
    )
    stale = _order(client_order_id="stale", broker_order_id="broker-stale")
    assert classify_open_order_role(stale, stale_session_client_order_ids=("stale",)).role == (
        "stale_session_order"
    )


def _fake_position_payload(symbol: str, quantity: float) -> dict[str, str]:
    return {
        "symbol": symbol,
        "asset_class": "etf" if symbol == "XLK" else "equity",
        "qty": str(quantity),
        "avg_entry_price": "100",
        "market_value": str(quantity * 100.0),
        "opened_at": DEFAULT_AS_OF.isoformat().replace("+00:00", "Z"),
    }


def _fake_stop_order_payload(
    symbol: str,
    broker_order_id: str,
    client_order_id: str,
) -> dict[str, str]:
    return {
        "id": broker_order_id,
        "client_order_id": client_order_id,
        "symbol": symbol,
        "side": "sell",
        "asset_class": "etf" if symbol == "XLK" else "equity",
        "qty": "1",
        "filled_qty": "0",
        "type": "stop",
        "time_in_force": "gtc",
        "status": "accepted",
        "stop_price": "95",
        "submitted_at": DEFAULT_AS_OF.isoformat().replace("+00:00", "Z"),
    }


def _broker_account() -> BrokerAccountSnapshot:
    return BrokerAccountSnapshot(
        account_id="paper-account",
        environment="paper",
        equity=100_000.0,
        cash=90_000.0,
        as_of=AS_OF,
    )


def _internal_account() -> InternalAccountSnapshot:
    return InternalAccountSnapshot(equity=100_000.0, cash=90_000.0, as_of=AS_OF)


def _broker_position(symbol: str, quantity: float) -> BrokerPosition:
    return BrokerPosition(
        symbol=symbol,
        asset_class="etf" if symbol == "XLK" else "equity",
        quantity=quantity,
        avg_entry_price=100.0,
        opened_at=AS_OF - timedelta(minutes=10),
    )


def _internal_position(symbol: str, quantity: float) -> InternalPosition:
    return InternalPosition(
        symbol=symbol,
        quantity=quantity,
        avg_entry_price=100.0,
        opened_at=AS_OF - timedelta(minutes=10),
    )
