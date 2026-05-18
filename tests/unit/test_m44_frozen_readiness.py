from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from packages.broker.fakes import FakeAlpacaClient
from packages.broker.models import (
    BrokerAccountSnapshot,
    BrokerPosition,
    BrokerProtectiveStop,
    BrokerSnapshot,
)
from packages.core.config import ShortsConfig, load_app_config
from packages.execution.side import (
    build_side_order_semantics,
    can_open_position_side,
    classify_position_side,
)
from packages.paper.frozen_readiness import (
    FROZEN_READINESS_M44_EVIDENCE_PATH,
    LATEST_V05_SPEC_PATH,
    M44_FLAT_START_CLEANUP_APPROVAL,
    FlatStartCleanupRequest,
    build_frozen_readiness_m44_packet,
    run_flat_start_cleanup_m44,
    write_flat_start_cleanup_artifact,
    write_frozen_readiness_m44_artifact,
)
from packages.reconciliation.models import (
    InternalAccountSnapshot,
    InternalLedgerSnapshot,
)
from packages.reconciliation.service import compare_broker_and_internal
from packages.risk.shorts import (
    ShortAccountSnapshot,
    ShortAssetSnapshot,
    ShortEntryRiskInput,
    evaluate_short_entry_risk,
)

AS_OF = datetime(2026, 5, 13, 14, 30, tzinfo=UTC)


def _short_policy(**updates: object) -> ShortsConfig:
    config = load_app_config().shorts
    return ShortsConfig.model_validate(config.model_dump() | updates)


def _short_input(**updates: object) -> ShortEntryRiskInput:
    data: dict[str, object] = {
        "symbol": "SPY",
        "quantity": 1.0,
        "entry_price": 500.0,
        "stop_price": 510.0,
        "asset": ShortAssetSnapshot(
            symbol="SPY",
            asset_class="etf",
            tradable=True,
            marginable=True,
            shortable=True,
            easy_to_borrow=True,
        ),
        "account": ShortAccountSnapshot(
            environment="paper",
            equity=100_000.0,
            shorting_enabled=True,
        ),
        "broker_state_ambiguous": False,
        "deterministic_bearish_signal": True,
        "execution_intent_present": True,
        "protective_buy_stop_planned": True,
    }
    data.update(updates)
    return ShortEntryRiskInput.model_validate(data)


def test_v0_6_is_latest_detected_spec() -> None:
    assert Path(LATEST_V05_SPEC_PATH).is_file()
    assert "SPEC_v0.6.md" in Path("AGENTS.md").read_text(encoding="utf-8")
    assert "SPEC_v0.6.md" in Path("README.md").read_text(encoding="utf-8")


def test_v0_6_config_loads_with_long_short_scale_in_defaults() -> None:
    config = load_app_config()

    assert config.validation.active_spec_version == "v0.6"
    assert config.validation.frozen_validation_enabled is False
    assert config.validation.validation_clock_started is False
    assert config.validation.flat_start_required is True
    assert config.validation.carry_in_positions_allowed is False
    assert config.validation.short_policy.enabled_at_validation_start is True
    assert config.validation.scale_in_policy.enabled_at_validation_start is True
    assert config.shorts.enabled is True
    assert config.shorts.eligible_symbols == ("SPY", "QQQ", "DIA", "IWM")
    assert config.validation_ai.negative_only is True
    assert config.live_universe.symbols == (
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


def test_short_side_semantics_are_signed_and_side_aware() -> None:
    long_semantics = build_side_order_semantics(requested_side="long", quantity=1)
    short_semantics = build_side_order_semantics(requested_side="short", quantity=1)

    assert classify_position_side(1) == "long"
    assert classify_position_side(-1) == "short"
    assert classify_position_side(0) == "flat"
    assert long_semantics.entry_side == "buy"
    assert long_semantics.protective_side == "sell"
    assert short_semantics.entry_side == "sell"
    assert short_semantics.protective_side == "buy"
    assert short_semantics.signed_quantity == -1
    assert can_open_position_side(current_side="long", requested_side="short") is False
    assert can_open_position_side(current_side="short", requested_side="long") is False


def test_default_short_policy_can_pass_rehearsed_broad_etf_gates() -> None:
    result = evaluate_short_entry_risk(policy=load_app_config().shorts, short_input=_short_input())

    assert result.allowed is True
    assert result.broker_side == "sell"
    assert result.protective_side == "buy"
    assert result.signed_quantity == -1


def test_shorts_disabled_blocks_all_short_entries() -> None:
    result = evaluate_short_entry_risk(
        policy=_short_policy(enabled=False, enabled_at_validation_start=False),
        short_input=_short_input(),
    )

    assert result.allowed is False
    assert "shorts_disabled" in result.reason_codes


def test_enabled_shorts_still_require_paper_mode() -> None:
    result = evaluate_short_entry_risk(
        policy=_short_policy(enabled=True),
        short_input=_short_input(account=ShortAccountSnapshot(
            environment="live",
            equity=100_000.0,
            shorting_enabled=True,
        )),
    )

    assert result.allowed is False
    assert "paper_environment_required" in result.reason_codes


def test_short_asset_and_account_gates_fail_closed() -> None:
    asset = ShortAssetSnapshot(
        symbol="SPY",
        asset_class="etf",
        tradable=True,
        marginable=False,
        shortable=False,
        easy_to_borrow=False,
    )
    result = evaluate_short_entry_risk(
        policy=_short_policy(enabled=True),
        short_input=_short_input(
            asset=asset,
            account=ShortAccountSnapshot(
                environment="paper",
                equity=1_000.0,
                shorting_enabled=False,
            ),
        ),
    )

    assert "asset_not_marginable" in result.reason_codes
    assert "asset_not_shortable" in result.reason_codes
    assert "asset_not_easy_to_borrow" in result.reason_codes
    assert "account_shorting_not_enabled" in result.reason_codes
    assert "account_equity_below_2000" in result.reason_codes


def test_short_policy_rejects_fractional_individual_stock_and_sector_etf() -> None:
    stock_result = evaluate_short_entry_risk(
        policy=_short_policy(enabled=True),
        short_input=_short_input(
            symbol="AAPL",
            quantity=0.5,
            asset=ShortAssetSnapshot(
                symbol="AAPL",
                asset_class="equity",
                tradable=True,
                marginable=True,
                shortable=True,
                easy_to_borrow=True,
            ),
        ),
    )
    sector_result = evaluate_short_entry_risk(
        policy=_short_policy(enabled=True),
        short_input=_short_input(
            symbol="XLK",
            asset=ShortAssetSnapshot(
                symbol="XLK",
                asset_class="etf",
                tradable=True,
                marginable=True,
                shortable=True,
                easy_to_borrow=True,
            ),
        ),
    )

    assert "fractional_short_quantity_forbidden" in stock_result.reason_codes
    assert "individual_stock_short_forbidden" in stock_result.reason_codes
    assert "sector_etf_short_forbidden" in sector_result.reason_codes


def test_future_enabled_broad_etf_short_can_pass_all_dormant_gates() -> None:
    result = evaluate_short_entry_risk(
        policy=_short_policy(enabled=True),
        short_input=_short_input(),
    )

    assert result.allowed is True
    assert result.reason_codes == ("short_entry_allowed",)


def test_existing_long_blocks_short_in_same_symbol() -> None:
    result = evaluate_short_entry_risk(
        policy=_short_policy(enabled=True),
        short_input=_short_input(existing_position_side="long"),
    )

    assert result.allowed is False
    assert "opposite_side_position_present" in result.reason_codes


def test_short_reconciliation_detects_open_short_without_buy_stop() -> None:
    broker_snapshot = BrokerSnapshot(
        account=BrokerAccountSnapshot(
            account_id="paper",
            environment="paper",
            equity=100_000,
            cash=100_000,
            as_of=AS_OF,
        ),
        positions=(
            BrokerPosition(
                symbol="SPY",
                asset_class="etf",
                quantity=-1.0,
                avg_entry_price=500.0,
                market_value=-500.0,
                opened_at=AS_OF,
            ),
        ),
        as_of=AS_OF,
    )
    internal_snapshot = InternalLedgerSnapshot(
        account=InternalAccountSnapshot(equity=100_000, cash=100_000, as_of=AS_OF),
        positions=(),
        as_of=AS_OF,
    )

    result = compare_broker_and_internal(
        broker_snapshot=broker_snapshot,
        internal_snapshot=internal_snapshot,
        as_of=AS_OF,
        protective_stop_config=load_app_config().protective_stop,
    )

    assert "unexpected_short_position" in {item.mismatch_type for item in result.mismatches}
    assert "short_protective_stop_missing" in {item.mismatch_type for item in result.mismatches}


def test_short_reconciliation_detects_buy_stop_quantity_shortfall() -> None:
    broker_snapshot = BrokerSnapshot(
        account=BrokerAccountSnapshot(
            account_id="paper",
            environment="paper",
            equity=100_000,
            cash=100_000,
            as_of=AS_OF,
        ),
        positions=(
            BrokerPosition(
                symbol="SPY",
                asset_class="etf",
                quantity=-2.0,
                avg_entry_price=500.0,
                market_value=-1000.0,
                opened_at=AS_OF,
            ),
        ),
        protective_stops=(
            BrokerProtectiveStop(
                broker_order_id="buy-stop-1",
                client_order_id="buy-stop-1",
                symbol="SPY",
                side="buy",
                quantity=1.0,
                stop_price=510.0,
                status="accepted",
                confirmed=True,
                submitted_at=AS_OF,
            ),
        ),
        as_of=AS_OF,
    )
    internal_snapshot = InternalLedgerSnapshot(
        account=InternalAccountSnapshot(equity=100_000, cash=100_000, as_of=AS_OF),
        positions=(),
        as_of=AS_OF,
    )

    result = compare_broker_and_internal(
        broker_snapshot=broker_snapshot,
        internal_snapshot=internal_snapshot,
        as_of=AS_OF,
        protective_stop_config=load_app_config().protective_stop,
    )

    assert "short_protective_stop_missing" in {item.mismatch_type for item in result.mismatches}


def test_flat_cleanup_refuses_without_m44_approval_marker() -> None:
    request = FlatStartCleanupRequest(
        mode="fake",
        operator_approval=None,
        confirm_paper_endpoint=True,
        confirm_risk_reducing_only=True,
        confirm_cancel_session_stop_before_sell=True,
        confirm_emergency_reprotect_if_sell_fails=True,
        confirm_no_new_entry=True,
        confirm_no_buy_orders=True,
        confirm_no_short_orders=True,
        confirm_no_live_trading=True,
        confirm_no_autonomous_live=True,
        confirm_no_schedules=True,
        confirm_no_leverage=True,
    )
    result = run_flat_start_cleanup_m44(request, environ={})

    assert result.success is False
    assert "m44_cleanup_approval_marker_required" in result.blockers
    assert result.broker_writes_performed is False


def test_flat_cleanup_fake_flow_cancels_stops_before_sell_and_reaches_flat() -> None:
    request = _approved_cleanup_request()
    result = run_flat_start_cleanup_m44(request, environ={})

    assert result.success is True
    assert result.packet.final_open_orders_count == 0
    assert result.packet.final_positions_count == 0
    assert result.packet.final_reconciliation == "flat_zero_positions_zero_open_orders"
    assert result.packet.short_orders_performed is False
    assert [write.operation for write in result.packet.broker_writes] == [
        "cancel_session_protective_stop",
        "submit_cleanup_sell",
        "cancel_session_protective_stop",
        "submit_cleanup_sell",
        "cancel_session_protective_stop",
        "submit_cleanup_sell",
    ]


def test_flat_cleanup_emergency_reprotects_if_sell_fails_after_stop_cancel() -> None:
    client = FakeAlpacaClient(
        orders=[
            _stop_order("AAPL"),
            _stop_order("MSFT"),
            _stop_order("XLK"),
        ],
        positions=[
            _position("AAPL"),
            _position("MSFT"),
            _position("XLK"),
        ],
        submit_outcomes=(("rejected", 0.0),),
        mutate_positions_on_submit=True,
    )

    def factory(*_args: object, **_kwargs: object) -> FakeAlpacaClient:
        return client

    result = run_flat_start_cleanup_m44(
        _approved_cleanup_request(mode="real-paper"),
        environ={
            "ALPACA_API_KEY": "paper-key",
            "ALPACA_SECRET_KEY": "paper-secret",
            "ALPACA_BASE_URL": "https://paper-api.alpaca.markets",
        },
        client_factory=factory,  # type: ignore[arg-type]
    )

    assert result.success is False
    assert any(
        write.operation == "submit_emergency_protective_stop"
        for write in result.packet.broker_writes
    )
    assert "emergency_reprotection_required_after_cleanup_failure" in result.blockers


def test_frozen_readiness_packet_requires_flat_baseline_and_non_iex_gate(tmp_path: Path) -> None:
    cleanup_result = run_flat_start_cleanup_m44(_approved_cleanup_request(), environ={})
    cleanup_path = write_flat_start_cleanup_artifact(
        cleanup_result,
        tmp_path / "flat_start_cleanup_m44.json",
    )
    packet = build_frozen_readiness_m44_packet(flat_cleanup_packet_path=cleanup_path)
    readiness_path = write_frozen_readiness_m44_artifact(
        packet,
        tmp_path / "frozen_readiness_m44.json",
    )
    payload = json.loads(readiness_path.read_text(encoding="utf-8"))

    assert packet.flat_start_achieved is True
    assert packet.m45_readiness is False
    assert "non_iex_primary_signal_data_not_verified" in packet.blockers
    assert payload["frozen_readiness"]["shorts_enabled"] is True
    assert payload["frozen_readiness"]["frozen_validation_started"] is False
    assert not _contains_sensitive_token(payload)


def test_frozen_readiness_default_output_path_is_m44_packet_path() -> None:
    assert FROZEN_READINESS_M44_EVIDENCE_PATH == "docs/evidence/frozen_readiness_m44.json"


def _approved_cleanup_request(mode: str = "fake") -> FlatStartCleanupRequest:
    return FlatStartCleanupRequest(
        mode=mode,  # type: ignore[arg-type]
        operator_approval=M44_FLAT_START_CLEANUP_APPROVAL,
        confirm_paper_endpoint=True,
        confirm_risk_reducing_only=True,
        confirm_cancel_session_stop_before_sell=True,
        confirm_emergency_reprotect_if_sell_fails=True,
        confirm_no_new_entry=True,
        confirm_no_buy_orders=True,
        confirm_no_short_orders=True,
        confirm_no_live_trading=True,
        confirm_no_autonomous_live=True,
        confirm_no_schedules=True,
        confirm_no_leverage=True,
    )


def _stop_order(symbol: str) -> dict[str, str]:
    return {
        "id": f"stop-{symbol}",
        "client_order_id": f"first-session-{symbol}-stop",
        "symbol": symbol,
        "side": "sell",
        "asset_class": "etf" if symbol == "XLK" else "equity",
        "qty": "1",
        "filled_qty": "0",
        "type": "stop",
        "time_in_force": "gtc",
        "status": "new",
        "stop_price": "95",
        "submitted_at": AS_OF.isoformat().replace("+00:00", "Z"),
        "updated_at": AS_OF.isoformat().replace("+00:00", "Z"),
    }


def _position(symbol: str) -> dict[str, str]:
    return {
        "symbol": symbol,
        "asset_class": "etf" if symbol == "XLK" else "equity",
        "qty": "1",
        "avg_entry_price": "100",
        "market_value": "100",
        "opened_at": AS_OF.isoformat().replace("+00:00", "Z"),
    }


def _contains_sensitive_token(value: object) -> bool:
    text = json.dumps(value, sort_keys=True)
    return any(token in text for token in ("paper-key", "paper-secret", "DATABASE_URL"))
