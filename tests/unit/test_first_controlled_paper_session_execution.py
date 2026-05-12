from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

import pytest

from packages.broker.alpaca import ALPACA_PAPER_BASE_URL
from packages.broker.fakes import DEFAULT_AS_OF, FakeAlpacaClient
from packages.core.config import load_app_config
from packages.paper import (
    M39_CLEAN_CONTROLLED_SESSION_EVIDENCE_PATH,
    M40_READ_ONLY_PREFLIGHT_EVIDENCE_PATH,
    M40_REPEATED_CONTROLLED_BATCH_EVIDENCE_PATH,
    MILESTONE_34_FAKE_OPERATOR_APPROVAL,
    MILESTONE_34_REAL_OPERATOR_APPROVAL,
    MILESTONE_35_REAL_OPERATOR_APPROVAL,
    MILESTONE_35B_REAL_OPERATOR_APPROVAL,
    MILESTONE_35C_REAL_OPERATOR_APPROVAL,
    MILESTONE_39_REAL_OPERATOR_APPROVAL,
    MILESTONE_40_REAL_OPERATOR_APPROVAL,
    FirstPaperSessionExecutionRequest,
    FirstPaperSessionExecutionResult,
    audit_first_session_symbol_universe,
    audit_m38_corrected_cleanup_packet,
    audit_m39_clean_controlled_session_packet,
    build_clean_controlled_session_m39_result,
    build_repeated_controlled_batch_m40_result,
    default_first_paper_session_execution_request,
    run_first_controlled_paper_session_execution,
    write_clean_controlled_session_m39_artifact,
    write_first_controlled_paper_session_result_artifact,
    write_repeated_controlled_batch_m40_artifact,
)
from scripts.check_first_controlled_paper_session import main as m29_script_main
from scripts.check_first_controlled_paper_session_preflight import main as preflight_script_main
from scripts.run_first_controlled_paper_session import main as run_session_script_main


def _fake_request(scenario_id: str = "happy_path") -> FirstPaperSessionExecutionRequest:
    return default_first_paper_session_execution_request(
        scenario_id,
        mode="fake-real-paper",
        operator_approval_marker=MILESTONE_34_FAKE_OPERATOR_APPROVAL,
    )


def _write_go_launch_packet(path: Path) -> Path:
    path.write_text(
        json.dumps(
            {
                "milestone": "33",
                "result": {
                    "go_no_go_decision": "go",
                    "blockers": [],
                    "read_only_broker_calls_performed": True,
                    "real_broker_writes_attempted": False,
                    "actual_paper_trading_started": False,
                    "schedules_activated": False,
                    "leverage_enabled": False,
                    "level4_ready": False,
                },
                "launch_packet": {
                    "broker_endpoint_mode": "paper",
                    "open_orders_summary": {"total_open_orders": 0},
                    "positions_summary": {"total_positions": 0},
                },
            }
        ),
        encoding="utf-8",
    )
    return path


def _write_m38_corrected_cleanup_packet(
    path: Path,
    *,
    incident_closed: bool = True,
    target_position_quantity: float = 0.0,
    open_orders_total: int = 0,
    positions_total: int = 0,
    final_reconciliation_summary: str = "flat_no_open_position",
    repeated_session_go_no_go: str = "eligible_for_m39_consideration",
    next_recommendation: str = (
        "M39_COMPACT_CONTROLLED_SESSION_AND_AUDIT_MAY_BE_CONSIDERED"
    ),
    blockers: tuple[str, ...] = (),
) -> Path:
    path.write_text(
        json.dumps(
            {
                "milestone": "38",
                "result": {
                    "incident_closed": incident_closed,
                    "go_no_go": repeated_session_go_no_go,
                    "blockers": list(blockers),
                    "real_broker_writes_attempted": True,
                    "schedules_activated": False,
                    "live_trading_enabled": False,
                    "autonomous_live_execution_enabled": False,
                    "leverage_enabled": False,
                    "level4_ready": False,
                },
                "corrected_cleanup": {
                    "incident_closed": incident_closed,
                    "aapl_position_status": (
                        "flat" if abs(target_position_quantity) <= 1e-9 else "open"
                    ),
                    "aapl_protective_stop_status": (
                        "none" if open_orders_total == 0 else "stale_session_stop_open"
                    ),
                    "final_broker_state": {
                        "target_symbol": "AAPL",
                        "target_position_quantity": target_position_quantity,
                        "open_orders_total": open_orders_total,
                        "positions_total": positions_total,
                        "reconciliation_summary": final_reconciliation_summary,
                    },
                    "final_reconciliation_summary": final_reconciliation_summary,
                    "repeated_session_go_no_go": repeated_session_go_no_go,
                    "next_compact_milestone_recommendation": next_recommendation,
                    "frozen_validation_started": False,
                    "level4_ready": False,
                    "blockers": list(blockers),
                },
            }
        ),
        encoding="utf-8",
    )
    return path


def _m39_safe_broker_env() -> dict[str, str]:
    return {
        "ALPACA_API_KEY": "paper-key-placeholder",
        "ALPACA_SECRET_KEY": "paper-secret-placeholder",
        "ALPACA_BASE_URL": ALPACA_PAPER_BASE_URL,
        "RUN_ALPACA_PAPER_SMOKE": "1",
        "ALPACA_PAPER_SMOKE_CONFIRM": "READ_ONLY_PAPER_ACCOUNT",
        "RUN_ALPACA_PAPER_ORDER_LIFECYCLE_SMOKE": "",
        "ALERT_ENABLE_REAL_DELIVERY": "false",
        "AI_ENABLE_ESCALATION": "false",
        "NEWS_ENABLE_OPENAI_WEB_FALLBACK": "false",
        "DASHBOARD_CONTROL_PLANE_ALLOW_CONTROL_SIGNALS": "false",
        "RUN_FIRST_CONTROLLED_PAPER_SESSION": "",
        "RUN_FIRST_CONTROLLED_PAPER_SESSION_EXECUTION": "",
        "RUN_TEMPORAL_CLOUD_SMOKE": "",
        "RUN_DASHBOARD_CONTROL_PLANE_SMOKE": "",
        "RUN_VERCEL_DASHBOARD_PREVIEW": "",
        "RUN_TELEGRAM_ALERT_SMOKE": "",
    }


def _m39_request(
    tmp_path: Path,
    scenario_id: str = "happy_path",
    *,
    operator_approval_marker: str | None = MILESTONE_39_REAL_OPERATOR_APPROVAL,
    target_symbol: str | None = "AAPL",
    m38_packet: Path | None = None,
) -> FirstPaperSessionExecutionRequest:
    return _real_request(
        scenario_id,
        target_symbol=target_symbol,
        max_quantity=1,
        max_notional_usd=350.0,
        limit_price=330.0,
        operator_approval_marker=operator_approval_marker,
    ).model_copy(
        update={
            "launch_packet_path": str(_write_go_launch_packet(tmp_path / "m33-go.json")),
            "m38_corrected_cleanup_packet_path": str(
                m38_packet
                or _write_m38_corrected_cleanup_packet(tmp_path / "m38-clean.json")
            ),
        }
    )


def _write_m40_launch_packet(path: Path, *, target_symbol: str = "MSFT") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "milestone": "33",
                "result": {
                    "go_no_go_decision": "go",
                    "blockers": [],
                    "read_only_broker_calls_performed": True,
                    "real_broker_writes_attempted": False,
                    "actual_paper_trading_started": False,
                    "schedules_activated": False,
                    "leverage_enabled": False,
                    "level4_ready": False,
                },
                "launch_packet": {
                    "broker_endpoint_mode": "paper",
                    "open_orders_summary": {
                        "symbols": ["AAPL"],
                        "target_symbol_open_orders": 0,
                        "total_open_orders": 1,
                    },
                    "positions_summary": {
                        "symbols": ["AAPL"],
                        "target_symbol_quantity": 0.0,
                        "total_positions": 1,
                    },
                    "target_symbol_cleanliness": {
                        "target_symbol": target_symbol,
                        "allowed": True,
                        "clean": True,
                        "open_order_count": 0,
                        "position_quantity": 0.0,
                        "reason_code": "clean",
                    },
                },
            }
        ),
        encoding="utf-8",
    )
    return path


def _m40_request(
    tmp_path: Path,
    scenario_id: str = "happy_path",
    *,
    operator_approval_marker: str | None = MILESTONE_40_REAL_OPERATOR_APPROVAL,
    target_symbol: str | None = "MSFT",
    max_quantity: int | None = 1,
    max_notional_usd: float | None = 500.0,
    limit_price: float | None = 500.0,
    m39_packet: Path | None = None,
) -> FirstPaperSessionExecutionRequest:
    return _real_request(
        scenario_id,
        target_symbol=target_symbol,
        max_quantity=max_quantity,
        max_notional_usd=max_notional_usd,
        limit_price=limit_price,
        operator_approval_marker=operator_approval_marker,
    ).model_copy(
        update={
            "launch_packet_path": str(
                _write_m40_launch_packet(
                    tmp_path / M40_READ_ONLY_PREFLIGHT_EVIDENCE_PATH,
                    target_symbol=target_symbol or "",
                )
            ),
            "m39_clean_controlled_session_packet_path": str(
                m39_packet or _write_m39_clean_session_packet(tmp_path / "m39-clean.json")
            ),
        }
    )


def _write_m39_clean_session_packet(
    path: Path,
    *,
    success: bool = True,
    final_reconciliation: str = "clean_protected_hold",
    normal_stop_path_succeeded: bool = True,
    recovery_stop_path_used: bool = False,
    repeated_batch_recommendation: str = (
        "M40_REPEATED_CONTROLLED_PAPER_BATCH_MAY_BE_CONSIDERED"
    ),
    blockers: tuple[str, ...] = (),
) -> Path:
    path.write_text(
        json.dumps(
            {
                "milestone": "39",
                "result": {
                    "success": success,
                    "go_no_go": "go" if success else "no_go",
                    "blockers": list(blockers),
                    "repeated_batch_readiness_recommendation": (
                        repeated_batch_recommendation
                    ),
                    "schedules_activated": False,
                    "live_trading_enabled": False,
                    "autonomous_live_execution_enabled": False,
                    "leverage_enabled": False,
                    "level4_ready": False,
                },
                "clean_controlled_session": {
                    "m38_corrected_cleanup_audit": {"blockers": []},
                    "target_symbol": "AAPL",
                    "fill_status": "filled",
                    "filled_quantity": 1.0,
                    "normal_stop_path_succeeded": normal_stop_path_succeeded,
                    "recovery_stop_path_used": recovery_stop_path_used,
                    "final_reconciliation": final_reconciliation,
                    "incidents": [],
                    "post_run_broker_state": {
                        "target_symbol_position_quantity": 1.0,
                        "protective_stop_verified": True,
                        "protective_stop_quantity": 1.0,
                    },
                    "repeated_batch_readiness_recommendation": (
                        repeated_batch_recommendation
                    ),
                    "frozen_validation_started": False,
                    "level4_ready": False,
                    "blockers": list(blockers),
                },
            }
        ),
        encoding="utf-8",
    )
    return path


def _protected_aapl_order() -> dict[str, str]:
    submitted_at = DEFAULT_AS_OF.isoformat().replace("+00:00", "Z")
    return {
        "id": "paper-aapl-stop",
        "client_order_id": "first-session-AAPL-20000101T000000Z-00000002-stop",
        "symbol": "AAPL",
        "side": "sell",
        "asset_class": "equity",
        "qty": "1",
        "filled_qty": "0",
        "type": "stop",
        "time_in_force": "gtc",
        "status": "accepted",
        "stop_price": "165",
        "submitted_at": submitted_at,
        "updated_at": submitted_at,
    }


def _protected_aapl_position() -> dict[str, str]:
    return {
        "symbol": "AAPL",
        "asset_class": "equity",
        "qty": "1",
        "avg_entry_price": "330",
        "market_value": "330",
        "opened_at": DEFAULT_AS_OF.isoformat().replace("+00:00", "Z"),
    }


def _m40_protected_aapl_client(
    *,
    submit_outcomes: tuple[tuple[str, float], ...] = (("filled", 1.0), ("accepted", 0.0)),
) -> FakeAlpacaClient:
    return FakeAlpacaClient(
        orders=(_protected_aapl_order(),),
        positions=(_protected_aapl_position(),),
        submit_outcomes=submit_outcomes,
        mutate_positions_on_submit=True,
    )


def _m39_client_factory(
    client: FakeAlpacaClient,
) -> Callable[..., FakeAlpacaClient]:
    def factory(*_args: object, **_kwargs: object) -> FakeAlpacaClient:
        return client

    return factory


def _fast_clock() -> Callable[[], float]:
    state = {"now": 0.0}

    def clock() -> float:
        state["now"] += 20.0
        return state["now"]

    return clock


def _real_request(
    scenario_id: str = "happy_path",
    *,
    target_symbol: str | None = "AAPL",
    max_quantity: int | None = 1,
    max_notional_usd: float | None = 350.0,
    limit_price: float | None = 330.0,
    operator_approval_marker: str | None = MILESTONE_34_REAL_OPERATOR_APPROVAL,
    confirm_real_paper_writes: bool = True,
) -> FirstPaperSessionExecutionRequest:
    return default_first_paper_session_execution_request(
        scenario_id,
        mode="real-paper",
        operator_approval_marker=operator_approval_marker,
        target_symbol=target_symbol,
        max_quantity=max_quantity,
        max_notional_usd=max_notional_usd,
        limit_price=limit_price,
        confirm_paper_endpoint=True,
        confirm_real_paper_writes=confirm_real_paper_writes,
        confirm_no_live_trading=True,
        confirm_no_autonomous_live=True,
        confirm_no_schedules=True,
        confirm_no_leverage=True,
        confirm_first_session_only=True,
        confirm_protective_stop_required=True,
        confirm_cleanup_policy=True,
    )


def _run_fake(scenario_id: str = "happy_path") -> FirstPaperSessionExecutionResult:
    return run_first_controlled_paper_session_execution(_fake_request(scenario_id))


def _fake_request_for_symbol(
    symbol: str,
    *,
    max_quantity: int = 1,
    max_notional_usd: float = 500.0,
    limit_price: float = 490.0,
) -> FirstPaperSessionExecutionRequest:
    return default_first_paper_session_execution_request(
        "happy_path",
        mode="fake-real-paper",
        operator_approval_marker=MILESTONE_34_FAKE_OPERATOR_APPROVAL,
        target_symbol=symbol,
        max_quantity=max_quantity,
        max_notional_usd=max_notional_usd,
        limit_price=limit_price,
    )


def test_default_real_session_script_refuses_before_external_calls(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert run_session_script_main([]) == 1
    output = capsys.readouterr().out
    assert '"refused": true' in output
    assert '"real_broker_writes_attempted": false' in output


def test_real_paper_without_operator_approval_refuses_before_broker_calls() -> None:
    result = run_first_controlled_paper_session_execution(
        _real_request(operator_approval_marker=None),
        environ={},
    )

    assert result.refused is True
    assert "operator_approval_missing" in result.blockers
    assert result.real_read_only_alpaca_calls_performed is False
    assert result.real_broker_writes_attempted is False


def test_real_paper_without_confirm_real_paper_writes_refuses() -> None:
    result = run_first_controlled_paper_session_execution(
        _real_request(confirm_real_paper_writes=False),
        environ={},
    )

    assert result.refused is True
    assert "confirm_real_paper_writes_required" in result.blockers
    assert result.real_broker_writes_attempted is False


def test_real_paper_without_target_symbol_or_envelope_refuses() -> None:
    result = run_first_controlled_paper_session_execution(
        _real_request(
            target_symbol=None,
            max_quantity=None,
            max_notional_usd=None,
            limit_price=None,
        ),
        environ={},
    )

    assert result.refused is True
    assert "target_symbol_required" in result.blockers
    assert "max_qty_required" in result.blockers
    assert "max_notional_required" in result.blockers
    assert "limit_price_required" in result.blockers
    assert result.real_broker_writes_attempted is False


def test_old_twenty_five_dollar_cap_is_not_universal() -> None:
    result = run_first_controlled_paper_session_execution(
        _fake_request_for_symbol("AAPL", max_notional_usd=350.0, limit_price=330.0)
    )

    assert result.success is True
    assert result.result_packet.order_envelope.max_quantity == 1
    assert result.result_packet.order_envelope.max_notional_usd == 350.0
    assert result.result_packet.order_envelope.limit_price == 330.0
    assert result.result_packet.estimated_entry_notional_usd == 330.0
    assert result.result_packet.first_session_absolute_max_notional_usd == 500.0
    assert result.result_packet.order_envelope_validation_result == "passed"


def test_first_session_absolute_notional_ceiling_is_enforced() -> None:
    result = run_first_controlled_paper_session_execution(
        _fake_request_for_symbol("AAPL", max_notional_usd=1000.0, limit_price=330.0)
    )

    assert result.refused is True
    assert "max_notional_exceeds_first_session_ceiling" in result.blockers
    assert result.real_broker_writes_attempted is False


def test_first_session_max_quantity_is_enforced() -> None:
    result = run_first_controlled_paper_session_execution(
        _fake_request_for_symbol(
            "AAPL",
            max_quantity=2,
            max_notional_usd=500.0,
            limit_price=200.0,
        )
    )

    assert result.refused is True
    assert "max_qty_exceeds_first_session_max" in result.blockers
    assert result.real_broker_writes_attempted is False


def test_limit_price_is_required_for_real_paper_mode() -> None:
    result = run_first_controlled_paper_session_execution(
        _real_request(limit_price=None),
        environ={},
    )

    assert result.refused is True
    assert "limit_price_required" in result.blockers
    assert result.real_broker_writes_attempted is False


def test_positive_finite_limit_price_is_required() -> None:
    with pytest.raises(ValueError):
        _real_request(limit_price=float("nan"))
    with pytest.raises(ValueError, match="limit_price must be finite"):
        _real_request(limit_price=float("inf"))


def test_estimated_notional_cannot_exceed_max_notional() -> None:
    result = run_first_controlled_paper_session_execution(
        _fake_request_for_symbol("AAPL", max_notional_usd=100.0, limit_price=330.0)
    )

    assert result.refused is True
    assert "estimated_notional_exceeds_max_notional" in result.blockers
    assert result.result_packet.estimated_entry_notional_usd == 330.0


@pytest.mark.parametrize(
    ("symbol", "max_notional", "limit_price"),
    (
        ("AAPL", 350.0, 330.0),
        ("SPY", 500.0, 490.0),
        ("QQQ", 500.0, 490.0),
        ("XLK", 300.0, 290.0),
    ),
)
def test_allowed_symbols_pass_local_envelope_validation(
    symbol: str,
    max_notional: float,
    limit_price: float,
) -> None:
    result = run_first_controlled_paper_session_execution(
        _fake_request_for_symbol(
            symbol,
            max_notional_usd=max_notional,
            limit_price=limit_price,
        )
    )

    assert result.success is True
    assert result.result_packet.target_symbol == symbol
    assert result.result_packet.symbol_allowlist_decision == "approved"
    assert result.result_packet.estimated_entry_notional_usd == limit_price
    assert result.result_packet.real_broker_writes_attempted is False


def test_unallowed_and_leveraged_or_inverse_symbols_reject_before_broker() -> None:
    unallowed = run_first_controlled_paper_session_execution(
        _fake_request_for_symbol("TSLA", max_notional_usd=300.0, limit_price=250.0)
    )
    leveraged = run_first_controlled_paper_session_execution(
        _fake_request_for_symbol("TQQQ", max_notional_usd=100.0, limit_price=90.0)
    )

    assert "target_symbol_not_approved" in unallowed.blockers
    assert "target_symbol_not_approved" in leveraged.blockers
    assert "leveraged_or_inverse_etf_forbidden" in leveraged.blockers
    assert unallowed.real_broker_writes_attempted is False
    assert leveraged.real_broker_writes_attempted is False


def test_symbol_universe_audit_accepts_configured_symbols_offline() -> None:
    audit = audit_first_session_symbol_universe()

    assert audit.success is True
    assert {"AAPL", "SPY", "QQQ"}.issubset(set(audit.allowed_symbols))
    assert all(record.accepted_by_first_session_envelope_logic for record in audit.records)
    assert audit.external_calls_attempted is False
    assert audit.real_broker_writes_attempted is False


def test_real_paper_valid_local_envelope_reaches_credential_gate_without_writes(
    tmp_path: Path,
) -> None:
    request = _real_request(max_notional_usd=350.0, limit_price=330.0).model_copy(
        update={"launch_packet_path": str(_write_go_launch_packet(tmp_path / "go.json"))}
    )
    result = run_first_controlled_paper_session_execution(
        request,
        environ={},
    )

    assert result.refused is True
    assert result.result_packet.order_envelope_validation_result == "passed"
    assert result.real_broker_writes_attempted is False
    assert any(reason.startswith("alpaca_readonly_gate:") for reason in result.blockers)


def test_m35_operator_marker_is_accepted_by_local_gate_model() -> None:
    result = run_first_controlled_paper_session_execution(
        _real_request(operator_approval_marker=MILESTONE_35_REAL_OPERATOR_APPROVAL),
        environ={},
    )

    assert "operator_approval_missing" not in result.blockers
    assert result.real_broker_writes_attempted is False


def test_m35b_operator_marker_is_accepted_by_local_gate_model() -> None:
    result = run_first_controlled_paper_session_execution(
        _real_request(operator_approval_marker=MILESTONE_35B_REAL_OPERATOR_APPROVAL),
        environ={},
    )

    assert "operator_approval_missing" not in result.blockers
    assert result.real_broker_writes_attempted is False


def test_m35c_operator_marker_is_accepted_by_local_gate_model() -> None:
    result = run_first_controlled_paper_session_execution(
        _real_request(operator_approval_marker=MILESTONE_35C_REAL_OPERATOR_APPROVAL),
        environ={},
    )

    assert "operator_approval_missing" not in result.blockers
    assert result.real_broker_writes_attempted is False


def test_real_paper_with_missing_launch_packet_refuses(tmp_path: Path) -> None:
    request = _real_request().model_copy(
        update={"launch_packet_path": str(tmp_path / "missing.json")}
    )
    result = run_first_controlled_paper_session_execution(request, environ={})

    assert result.refused is True
    assert "launch_packet_missing" in result.blockers
    assert result.real_broker_writes_attempted is False


def test_live_endpoint_and_paper_endpoint_gates_refuse() -> None:
    result = run_first_controlled_paper_session_execution(
        _real_request("live_endpoint_rejected"),
        environ={},
    )

    assert result.refused is True
    assert "live_endpoint_detected" in result.blockers
    assert "confirm_paper_endpoint_required" in result.blockers
    assert result.real_broker_writes_attempted is False


def test_schedule_live_autonomous_and_leverage_gates_refuse() -> None:
    request = _real_request().model_copy(
        update={
            "confirm_no_schedules": False,
            "confirm_no_live_trading": False,
            "confirm_no_autonomous_live": False,
            "confirm_no_leverage": False,
        }
    )
    result = run_first_controlled_paper_session_execution(request, environ={})

    assert "confirm_no_schedules_required" in result.blockers
    assert "confirm_no_live_trading_required" in result.blockers
    assert "confirm_no_autonomous_live_required" in result.blockers
    assert "confirm_no_leverage_required" in result.blockers
    assert result.real_broker_writes_attempted is False


def test_config_live_autonomous_and_leverage_refuse() -> None:
    app_config = load_app_config()
    unsafe_config = app_config.model_copy(
        update={
            "system": app_config.system.model_copy(
                update={"live_trading_enabled": True, "dry_run": False}
            ),
            "execution": app_config.execution.model_copy(
                update={"autonomous_execution_enabled": True}
            ),
            "risk_level_4_micro_live": app_config.risk_level_4_micro_live.model_copy(
                update={"allow_margin": True}
            ),
        }
    )
    result = run_first_controlled_paper_session_execution(
        _real_request(),
        environ={},
        app_config=unsafe_config,
    )

    assert "live_trading_enabled" in result.blockers
    assert "autonomous_live_execution_enabled" in result.blockers
    assert "leverage_enabled" in result.blockers
    assert result.real_broker_writes_attempted is False


def test_short_and_unsupported_asset_refuse_before_broker() -> None:
    short_result = run_first_controlled_paper_session_execution(
        _real_request("short_rejected"),
        environ={},
    )
    unsupported_result = run_first_controlled_paper_session_execution(
        _real_request("unsupported_asset_rejected"),
        environ={},
    )

    assert "short_side_forbidden" in short_result.blockers
    assert "unsupported_asset_class" in unsupported_result.blockers
    assert short_result.real_broker_writes_attempted is False
    assert unsupported_result.real_broker_writes_attempted is False


def test_dirty_reconciliation_existing_order_and_position_refuse() -> None:
    dirty = _run_fake("dirty_reconciliation_blocks")
    open_order = _run_fake("existing_open_orders")
    position = _run_fake("existing_position")

    assert "pre_run_reconciliation_not_clean" in dirty.blockers
    assert "existing_target_symbol_open_order" in open_order.blockers
    assert "existing_target_symbol_position" in position.blockers


def test_missing_execution_intent_idempotency_and_stop_plan_refuse() -> None:
    missing_intent = run_first_controlled_paper_session_execution(
        _real_request("missing_execution_intent"),
        environ={},
    )
    missing_key = run_first_controlled_paper_session_execution(
        _real_request("missing_idempotency_key"),
        environ={},
    )
    missing_stop = run_first_controlled_paper_session_execution(
        _real_request("missing_protective_stop_plan"),
        environ={},
    )

    assert "execution_intent_required" in missing_intent.blockers
    assert "idempotency_key_required" in missing_key.blockers
    assert "protective_stop_plan_required" in missing_stop.blockers


def test_fake_real_paper_success_submits_fake_entry_stop_and_verifies_stop() -> None:
    result = _run_fake()

    assert result.success is True
    assert result.status == "executed"
    assert result.actual_paper_trading_started is False
    assert result.real_broker_writes_attempted is False
    assert result.result_packet.entry_order_status == "filled"
    assert result.result_packet.fill_status == "filled"
    assert result.result_packet.filled_quantity == 1.0
    assert result.result_packet.protective_stop_order_id is not None
    assert result.result_packet.protective_stop_verification_result == "verified"
    assert result.result_packet.post_session_recommendation == (
        "post_session_audit_required_before_repetition"
    )


def test_fake_partial_fill_places_stop_for_filled_quantity_and_cancels_remainder() -> None:
    result = _run_fake("partial_fill")

    assert result.success is True
    assert result.result_packet.fill_status == "partial_fill"
    assert result.result_packet.filled_quantity == 0.5
    assert result.result_packet.protective_stop_verification_result == "verified"
    assert "cancel_unfilled_remainder" in result.result_packet.cleanup_actions


def test_fake_no_fill_cancels_without_stop() -> None:
    result = _run_fake("no_fill")

    assert result.success is True
    assert result.result_packet.fill_status == "not_filled"
    assert result.result_packet.protective_stop_order_id is None
    assert result.result_packet.protective_stop_verification_result == "not_required_no_fill"
    assert "cancel_unfilled_entry" in result.result_packet.cleanup_actions


def test_fake_missing_stop_verification_creates_critical_incident() -> None:
    result = _run_fake("missing_stop_verification")

    assert result.success is False
    assert result.unsafe is True
    assert result.status == "incident"
    assert "critical_missing_protective_stop_verification" in result.result_packet.incidents
    assert result.result_packet.protective_stop_verification_result == "not_verified"


def test_result_packet_contains_required_fields_and_excludes_secrets(tmp_path: Path) -> None:
    result = _run_fake()
    packet = result.result_packet

    assert packet.result_packet_id
    assert packet.operator_approval_marker == MILESTONE_34_FAKE_OPERATOR_APPROVAL
    assert packet.latest_spec_path == "docs/app/Autonomous_AI_Trading_Bot_SPEC_v0.3.md"
    assert packet.candidate_id == "candidate-AAPL-m34"
    assert packet.ai_news_neutral_fallback_marker == "neutral_fake_ai_news_no_broker_authority"
    assert packet.decision_id
    assert packet.risk_check_id
    assert packet.execution_intent_id
    assert packet.client_order_id
    assert packet.broker_order_id
    assert packet.fake_alert_summary == "fake_alert_summary_only"
    assert packet.estimated_entry_notional_usd == 25.0
    assert packet.first_session_max_quantity == 1
    assert packet.first_session_absolute_max_notional_usd == 500.0
    assert packet.symbol_allowlist_decision == "approved"
    assert packet.order_envelope_validation_result == "passed"
    output = write_first_controlled_paper_session_result_artifact(
        result,
        tmp_path / "first_controlled_paper_session_result.json",
    )
    serialized = output.read_text(encoding="utf-8")
    assert '"milestone": "34"' in serialized
    assert "paper-secret" not in serialized
    assert "DATABASE_URL=" not in serialized


def test_ai_news_neutral_fallback_has_no_broker_authority() -> None:
    result = _run_fake()

    assert result.result_packet.ai_news_neutral_fallback_marker
    assert result.ai_broker_write_authority is False
    assert result.real_broker_writes_attempted is False


def test_existing_m29_m30_and_preflight_scripts_still_work(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert m29_script_main(["--scenario", "happy_path"]) == 0
    assert '"success": true' in capsys.readouterr().out

    assert (
        run_session_script_main(
            [
                "--mode",
                "fake",
                "--scenario",
                "happy_path",
                "--operator-approval",
                "MILESTONE_30_FAKE_ONLY",
            ]
        )
        == 0
    )
    assert '"success": true' in capsys.readouterr().out

    assert (
        preflight_script_main(
            [
                "--mode",
                "fake",
                "--scenario",
                "happy_path",
                "--operator-approval",
                "MILESTONE_31_FAKE_PREFLIGHT",
            ]
        )
        == 0
    )
    assert '"success": true' in capsys.readouterr().out


def test_m34_script_real_paper_missing_target_writes_result_packet(
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    output_path = tmp_path / "first_controlled_paper_session_result.json"
    assert (
        run_session_script_main(
            [
                "--mode",
                "real-paper",
                "--operator-approval",
                MILESTONE_34_REAL_OPERATOR_APPROVAL,
                "--confirm-paper-endpoint",
                "--confirm-real-paper-writes",
                "--confirm-no-live-trading",
                "--confirm-no-autonomous-live",
                "--confirm-no-schedules",
                "--confirm-no-leverage",
                "--confirm-first-session-only",
                "--confirm-protective-stop-required",
                "--confirm-cleanup-policy",
                "--result-output",
                str(output_path),
            ]
        )
        == 1
    )
    output = capsys.readouterr().out
    assert '"target_symbol_required"' in output
    assert '"limit_price_required"' in output
    assert str(output_path) in output


def test_symbol_universe_audit_script_is_local_only(capsys: pytest.CaptureFixture[str]) -> None:
    assert run_session_script_main(["--mode", "audit-symbol-universe"]) == 0
    output = capsys.readouterr().out
    assert '"success": true' in output
    assert '"external_calls_attempted": false' in output
    assert '"real_broker_writes_attempted": false' in output
    assert "AAPL" in output
    assert "SPY" in output
    assert "QQQ" in output


def test_m34_script_fake_real_paper_happy_path(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert (
        run_session_script_main(
            [
                "--mode",
                "fake-real-paper",
                "--scenario",
                "happy_path",
                "--operator-approval",
                MILESTONE_34_FAKE_OPERATOR_APPROVAL,
                "--target-symbol",
                "AAPL",
                "--max-qty",
                "1",
                "--max-notional",
                "350",
                "--limit-price",
                "330",
            ]
        )
        == 0
    )
    output = capsys.readouterr().out
    assert '"status": "executed"' in output
    assert '"estimated_entry_notional_usd": 330.0' in output
    assert '"real_broker_writes_attempted": false' in output


def test_m39_audits_clean_m38_corrected_cleanup_packet(tmp_path: Path) -> None:
    packet = _write_m38_corrected_cleanup_packet(tmp_path / "m38-clean.json")

    audit = audit_m38_corrected_cleanup_packet(packet)

    assert audit.parseable is True
    assert audit.milestone == "38"
    assert audit.incident_closed is True
    assert audit.aapl_position_flat is True
    assert audit.open_orders_clean is True
    assert audit.positions_clean is True
    assert audit.final_reconciliation_clean is True
    assert audit.repeated_session_m39_eligible is True
    assert audit.blockers == ()


def test_m39_refuses_if_m38_corrected_cleanup_packet_is_missing(tmp_path: Path) -> None:
    request = _m39_request(tmp_path).model_copy(
        update={"m38_corrected_cleanup_packet_path": str(tmp_path / "missing-m38.json")}
    )

    result = run_first_controlled_paper_session_execution(
        request,
        environ=_m39_safe_broker_env(),
    )

    assert result.refused is True
    assert "m38_corrected_cleanup_packet_missing" in result.blockers
    assert result.real_broker_writes_attempted is False


def test_m39_refuses_if_m38_incident_closure_is_not_clean_flat(tmp_path: Path) -> None:
    packet = _write_m38_corrected_cleanup_packet(
        tmp_path / "m38-dirty.json",
        incident_closed=False,
        target_position_quantity=1.0,
        positions_total=1,
        final_reconciliation_summary="protected_position_open",
        repeated_session_go_no_go="no_go",
        next_recommendation="M39_BLOCKED_MANUAL_REVIEW_REQUIRED",
        blockers=("m38_manual_review_required",),
    )
    result = run_first_controlled_paper_session_execution(
        _m39_request(tmp_path, m38_packet=packet),
        environ=_m39_safe_broker_env(),
    )

    assert result.refused is True
    assert "m38_incident_closed" in result.blockers
    assert "m38_aapl_position_flat" in result.blockers
    assert "m38_positions_clean" in result.blockers
    assert "m38_final_reconciliation_clean" in result.blockers
    assert "m38_repeated_session_m39_eligible" in result.blockers
    assert "m38_manual_review_required" in result.blockers
    assert result.real_broker_writes_attempted is False


def test_m39_refuses_if_stale_aapl_stop_remains_after_m38(tmp_path: Path) -> None:
    packet = _write_m38_corrected_cleanup_packet(
        tmp_path / "m38-stale-stop.json",
        open_orders_total=1,
    )

    result = run_first_controlled_paper_session_execution(
        _m39_request(tmp_path, m38_packet=packet),
        environ=_m39_safe_broker_env(),
    )

    assert result.refused is True
    assert "m38_open_orders_clean" in result.blockers
    assert result.real_broker_writes_attempted is False


def test_m39_requires_operator_marker(tmp_path: Path) -> None:
    result = run_first_controlled_paper_session_execution(
        _m39_request(tmp_path, operator_approval_marker=None),
        environ=_m39_safe_broker_env(),
    )

    assert result.refused is True
    assert "operator_approval_missing" in result.blockers
    assert result.real_broker_writes_attempted is False


def test_m39_result_packet_refuses_non_aapl_target(tmp_path: Path) -> None:
    result = run_first_controlled_paper_session_execution(
        _m39_request(tmp_path, target_symbol="SPY"),
        environ=_m39_safe_broker_env(),
    )
    m39 = build_clean_controlled_session_m39_result(
        result,
        m38_corrected_cleanup_packet_path=result.result_packet.launch_packet_reference.replace(
            "m33-go.json",
            "m38-clean.json",
        ),
    )

    assert m39.success is False
    assert "m39_target_symbol_must_be_aapl" in m39.blockers
    assert result.real_broker_writes_attempted is False


def test_m39_refuses_if_unexpected_open_order_exists_before_entry(
    tmp_path: Path,
) -> None:
    existing_order = {
        "id": "paper-existing-order",
        "client_order_id": "existing-aapl-stop",
        "symbol": "AAPL",
        "side": "sell",
        "asset_class": "equity",
        "qty": "1",
        "filled_qty": "0",
        "type": "stop",
        "time_in_force": "gtc",
        "status": "accepted",
        "stop_price": "300",
        "submitted_at": DEFAULT_AS_OF.isoformat().replace("+00:00", "Z"),
        "updated_at": DEFAULT_AS_OF.isoformat().replace("+00:00", "Z"),
    }
    client = FakeAlpacaClient(orders=(existing_order,))

    result = run_first_controlled_paper_session_execution(
        _m39_request(tmp_path),
        environ=_m39_safe_broker_env(),
        client_factory=_m39_client_factory(client),
    )

    assert result.refused is True
    assert "existing_target_symbol_open_order" in result.blockers
    assert result.real_broker_writes_attempted is False


def test_m39_refuses_if_unexpected_position_exists_before_entry(
    tmp_path: Path,
) -> None:
    client = FakeAlpacaClient(
        positions=(
            {
                "symbol": "AAPL",
                "asset_class": "equity",
                "qty": "1",
                "avg_entry_price": "330",
                "market_value": "330",
                "opened_at": DEFAULT_AS_OF.isoformat().replace("+00:00", "Z"),
            },
        )
    )

    result = run_first_controlled_paper_session_execution(
        _m39_request(tmp_path),
        environ=_m39_safe_broker_env(),
        client_factory=_m39_client_factory(client),
    )

    assert result.refused is True
    assert "existing_target_symbol_position" in result.blockers
    assert "pre_run_reconciliation_not_clean" in result.blockers
    assert result.real_broker_writes_attempted is False


def test_m39_fake_stub_success_verifies_normal_stop_without_recovery(
    tmp_path: Path,
) -> None:
    client = FakeAlpacaClient(
        submit_outcomes=(("filled", 1.0), ("accepted", 0.0)),
        mutate_positions_on_submit=True,
    )

    result = run_first_controlled_paper_session_execution(
        _m39_request(tmp_path),
        environ=_m39_safe_broker_env(),
        client_factory=_m39_client_factory(client),
        sleeper=lambda _seconds: None,
        clock=_fast_clock(),
    )
    m39 = build_clean_controlled_session_m39_result(
        result,
        m38_corrected_cleanup_packet_path=result.result_packet.launch_packet_reference.replace(
            "m33-go.json",
            "m38-clean.json",
        ),
    )

    assert result.success is True
    assert result.actual_paper_trading_started is True
    assert result.real_broker_writes_attempted is True
    assert result.result_packet.operator_approval_marker == MILESTONE_39_REAL_OPERATOR_APPROVAL
    assert result.result_packet.normal_stop_path_succeeded is True
    assert result.result_packet.recovery_stop_path_used is False
    assert result.result_packet.protective_stop_verification_result == "verified"
    assert result.result_packet.post_run_broker_state is not None
    assert result.result_packet.post_run_broker_state.reconciliation_result == (
        "clean_protected_hold"
    )
    assert m39.success is True
    assert m39.repeated_batch_readiness_recommendation == (
        "M40_REPEATED_CONTROLLED_PAPER_BATCH_MAY_BE_CONSIDERED"
    )


def test_m39_fake_stub_no_fill_path_is_audited(tmp_path: Path) -> None:
    client = FakeAlpacaClient(submit_outcomes=(("accepted", 0.0),))

    result = run_first_controlled_paper_session_execution(
        _m39_request(tmp_path, "no_fill"),
        environ=_m39_safe_broker_env(),
        client_factory=_m39_client_factory(client),
        sleeper=lambda _seconds: None,
        clock=_fast_clock(),
    )
    m39 = build_clean_controlled_session_m39_result(
        result,
        m38_corrected_cleanup_packet_path=result.result_packet.launch_packet_reference.replace(
            "m33-go.json",
            "m38-clean.json",
        ),
    )

    assert result.success is True
    assert result.result_packet.fill_status == "not_filled"
    assert result.result_packet.protective_stop_order_id is None
    assert result.result_packet.protective_stop_verification_result == "not_required_no_fill"
    assert result.result_packet.normal_stop_path_succeeded is False
    assert result.result_packet.post_run_broker_state is not None
    assert result.result_packet.post_run_broker_state.reconciliation_result == (
        "flat_no_open_position"
    )
    assert "cancel_unfilled_entry" in result.result_packet.cleanup_actions
    assert m39.success is True


def test_m39_clean_session_artifact_contains_required_fields_and_excludes_secrets(
    tmp_path: Path,
) -> None:
    client = FakeAlpacaClient(
        submit_outcomes=(("filled", 1.0), ("accepted", 0.0)),
        mutate_positions_on_submit=True,
    )
    result = run_first_controlled_paper_session_execution(
        _m39_request(tmp_path),
        environ=_m39_safe_broker_env(),
        client_factory=_m39_client_factory(client),
        sleeper=lambda _seconds: None,
        clock=_fast_clock(),
    )
    output = write_clean_controlled_session_m39_artifact(
        result,
        tmp_path / M39_CLEAN_CONTROLLED_SESSION_EVIDENCE_PATH,
        m38_corrected_cleanup_packet_path=result.result_packet.launch_packet_reference.replace(
            "m33-go.json",
            "m38-clean.json",
        ),
    )
    serialized = output.read_text(encoding="utf-8")
    payload = json.loads(serialized)

    assert payload["milestone"] == "39"
    assert payload["result"]["success"] is True
    packet = payload["clean_controlled_session"]
    assert packet["target_symbol"] == "AAPL"
    assert packet["estimated_notional"] == 330.0
    assert packet["normal_stop_path_succeeded"] is True
    assert packet["recovery_stop_path_used"] is False
    assert packet["repeated_batch_readiness_recommendation"] == (
        "M40_REPEATED_CONTROLLED_PAPER_BATCH_MAY_BE_CONSIDERED"
    )
    assert "paper-secret-placeholder" not in serialized
    assert "paper-key-placeholder" not in serialized
    assert "DATABASE_URL=" not in serialized
    assert "postgres://" not in serialized


def test_m40_audits_clean_m39_packet(tmp_path: Path) -> None:
    packet = _write_m39_clean_session_packet(tmp_path / "m39-clean.json")

    audit = audit_m39_clean_controlled_session_packet(packet)

    assert audit.parseable is True
    assert audit.milestone == "39"
    assert audit.clean_success_or_resolved is True
    assert audit.normal_stop_path_succeeded_without_recovery is True
    assert audit.final_reconciliation_clean is True
    assert audit.no_unresolved_incident is True
    assert audit.repeated_batch_m40_eligible is True
    assert audit.existing_aapl_position_quantity == 1.0
    assert audit.existing_aapl_protective_stop_verified is True
    assert audit.existing_aapl_protective_stop_quantity == 1.0
    assert audit.blockers == ()


def test_m40_refuses_if_m39_packet_is_missing(tmp_path: Path) -> None:
    result = run_first_controlled_paper_session_execution(
        _m40_request(tmp_path).model_copy(
            update={
                "m39_clean_controlled_session_packet_path": str(
                    tmp_path / "missing-m39.json"
                )
            }
        ),
        environ=_m39_safe_broker_env(),
    )

    assert result.refused is True
    assert "m39_clean_controlled_session_packet_missing" in result.blockers
    assert result.real_broker_writes_attempted is False


def test_m40_refuses_if_m39_result_is_not_clean(tmp_path: Path) -> None:
    packet = _write_m39_clean_session_packet(
        tmp_path / "m39-dirty.json",
        success=False,
        final_reconciliation="post_run_state_requires_incident_review",
        normal_stop_path_succeeded=False,
        recovery_stop_path_used=True,
        repeated_batch_recommendation="M40_REPEATED_CONTROLLED_PAPER_BATCH_BLOCKED",
        blockers=("m39_incident_recorded",),
    )

    result = run_first_controlled_paper_session_execution(
        _m40_request(tmp_path, m39_packet=packet),
        environ=_m39_safe_broker_env(),
    )

    assert result.refused is True
    assert "m39_clean_success_or_resolved" in result.blockers
    assert "m39_normal_stop_path_succeeded_without_recovery" in result.blockers
    assert "m39_final_reconciliation_clean" in result.blockers
    assert "m39_repeated_batch_m40_eligible" in result.blockers
    assert "m39_incident_recorded" in result.blockers
    assert result.real_broker_writes_attempted is False


def test_m40_requires_operator_marker(tmp_path: Path) -> None:
    result = run_first_controlled_paper_session_execution(
        _m40_request(tmp_path, operator_approval_marker=None),
        environ=_m39_safe_broker_env(),
    )

    assert result.refused is True
    assert "operator_approval_missing" in result.blockers
    assert result.real_broker_writes_attempted is False


def test_m40_blocks_duplicate_aapl_entry(tmp_path: Path) -> None:
    result = run_first_controlled_paper_session_execution(
        _m40_request(
            tmp_path,
            target_symbol="AAPL",
            max_notional_usd=350.0,
            limit_price=330.0,
        ),
        environ=_m39_safe_broker_env(),
    )

    assert result.refused is True
    assert "m40_target_symbol_must_be_msft_or_xlk" in result.blockers
    assert "m40_duplicate_aapl_entry_forbidden" in result.blockers
    assert result.real_broker_writes_attempted is False


def test_m40_validates_msft_envelope(tmp_path: Path) -> None:
    request = _m40_request(tmp_path, target_symbol="MSFT")

    result = run_first_controlled_paper_session_execution(
        request,
        environ=_m39_safe_broker_env(),
        client_factory=_m39_client_factory(_m40_protected_aapl_client()),
        sleeper=lambda _seconds: None,
        clock=_fast_clock(),
    )

    assert result.success is True
    assert result.result_packet.target_symbol == "MSFT"
    assert result.result_packet.estimated_entry_notional_usd == 500.0
    assert result.result_packet.pre_run_broker_state.aapl_hold_status == (
        "clean_protected_hold"
    )
    assert result.result_packet.normal_stop_path_succeeded is True
    assert result.result_packet.recovery_stop_path_used is False


def test_m40_validates_xlk_fallback_envelope(tmp_path: Path) -> None:
    request = _m40_request(
        tmp_path,
        target_symbol="XLK",
        max_notional_usd=300.0,
        limit_price=300.0,
    )

    result = run_first_controlled_paper_session_execution(
        request,
        environ=_m39_safe_broker_env(),
        client_factory=_m39_client_factory(_m40_protected_aapl_client()),
        sleeper=lambda _seconds: None,
        clock=_fast_clock(),
    )

    assert result.success is True
    assert result.result_packet.target_symbol == "XLK"
    assert result.result_packet.estimated_entry_notional_usd == 300.0
    assert result.result_packet.normal_stop_path_succeeded is True


def test_m40_refuses_symbols_outside_operator_candidates(tmp_path: Path) -> None:
    result = run_first_controlled_paper_session_execution(
        _m40_request(
            tmp_path,
            target_symbol="QQQ",
            max_notional_usd=500.0,
            limit_price=490.0,
        ),
        environ=_m39_safe_broker_env(),
    )

    assert result.refused is True
    assert "m40_target_symbol_must_be_msft_or_xlk" in result.blockers
    assert result.real_broker_writes_attempted is False


def test_m40_refuses_unexpected_open_order(tmp_path: Path) -> None:
    client = FakeAlpacaClient(
        orders=(
            _protected_aapl_order(),
            {
                **_protected_aapl_order(),
                "id": "paper-unexpected-order",
                "client_order_id": "unexpected-qqq-stop",
                "symbol": "QQQ",
            },
        ),
        positions=(_protected_aapl_position(),),
    )

    result = run_first_controlled_paper_session_execution(
        _m40_request(tmp_path),
        environ=_m39_safe_broker_env(),
        client_factory=_m39_client_factory(client),
    )

    assert result.refused is True
    assert "m40_unexpected_open_order" in result.blockers
    assert result.real_broker_writes_attempted is False


def test_m40_refuses_unexpected_position(tmp_path: Path) -> None:
    client = FakeAlpacaClient(
        orders=(_protected_aapl_order(),),
        positions=(
            _protected_aapl_position(),
            {
                **_protected_aapl_position(),
                "symbol": "QQQ",
                "avg_entry_price": "490",
                "market_value": "490",
            },
        ),
    )

    result = run_first_controlled_paper_session_execution(
        _m40_request(tmp_path),
        environ=_m39_safe_broker_env(),
        client_factory=_m39_client_factory(client),
    )

    assert result.refused is True
    assert "m40_unexpected_position" in result.blockers
    assert result.real_broker_writes_attempted is False


def test_m40_fake_stub_success_verifies_normal_stop_without_recovery(
    tmp_path: Path,
) -> None:
    request = _m40_request(tmp_path)
    result = run_first_controlled_paper_session_execution(
        request,
        environ=_m39_safe_broker_env(),
        client_factory=_m39_client_factory(_m40_protected_aapl_client()),
        sleeper=lambda _seconds: None,
        clock=_fast_clock(),
    )
    m40 = build_repeated_controlled_batch_m40_result(
        result,
        m39_clean_controlled_session_packet_path=request.m39_clean_controlled_session_packet_path,
    )

    assert result.success is True
    assert result.actual_paper_trading_started is True
    assert result.result_packet.normal_stop_path_succeeded is True
    assert result.result_packet.recovery_stop_path_used is False
    assert result.result_packet.post_run_broker_state is not None
    assert result.result_packet.post_run_broker_state.open_order_count == 2
    assert result.result_packet.post_run_broker_state.position_count == 2
    assert result.result_packet.post_run_broker_state.aapl_hold_status == (
        "clean_protected_hold"
    )
    assert m40.success is True
    assert m40.supervised_schedule_readiness_recommendation == (
        "M41_SUPERVISED_SCHEDULED_PAPER_READINESS_MAY_BE_CONSIDERED"
    )


def test_m40_fake_stub_no_fill_path_is_audited(tmp_path: Path) -> None:
    request = _m40_request(tmp_path, "no_fill")
    result = run_first_controlled_paper_session_execution(
        request,
        environ=_m39_safe_broker_env(),
        client_factory=_m39_client_factory(
            _m40_protected_aapl_client(submit_outcomes=(("accepted", 0.0),))
        ),
        sleeper=lambda _seconds: None,
        clock=_fast_clock(),
    )
    m40 = build_repeated_controlled_batch_m40_result(
        result,
        m39_clean_controlled_session_packet_path=request.m39_clean_controlled_session_packet_path,
    )

    assert result.success is True
    assert result.result_packet.fill_status == "not_filled"
    assert result.result_packet.protective_stop_order_id is None
    assert result.result_packet.normal_stop_path_succeeded is False
    assert result.result_packet.post_run_broker_state is not None
    assert result.result_packet.post_run_broker_state.aapl_hold_status == (
        "clean_protected_hold"
    )
    assert "cancel_unfilled_entry" in result.result_packet.cleanup_actions
    assert m40.success is True


def test_m40_repeated_batch_artifact_contains_required_fields_and_excludes_secrets(
    tmp_path: Path,
) -> None:
    request = _m40_request(tmp_path)
    result = run_first_controlled_paper_session_execution(
        request,
        environ=_m39_safe_broker_env(),
        client_factory=_m39_client_factory(_m40_protected_aapl_client()),
        sleeper=lambda _seconds: None,
        clock=_fast_clock(),
    )
    output = write_repeated_controlled_batch_m40_artifact(
        result,
        tmp_path / M40_REPEATED_CONTROLLED_BATCH_EVIDENCE_PATH,
        m39_clean_controlled_session_packet_path=request.m39_clean_controlled_session_packet_path,
    )
    serialized = output.read_text(encoding="utf-8")
    payload = json.loads(serialized)

    assert payload["milestone"] == "40"
    assert payload["result"]["success"] is True
    packet = payload["repeated_controlled_batch"]
    assert packet["selected_target_symbol"] == "MSFT"
    assert packet["estimated_notional"] == 500.0
    assert packet["existing_aapl_protected_hold_status"] == "clean_protected_hold"
    assert packet["normal_stop_path_succeeded"] is True
    assert packet["recovery_stop_path_used"] is False
    assert packet["supervised_schedule_readiness_recommendation"] == (
        "M41_SUPERVISED_SCHEDULED_PAPER_READINESS_MAY_BE_CONSIDERED"
    )
    assert "paper-secret-placeholder" not in serialized
    assert "paper-key-placeholder" not in serialized
    assert "DATABASE_URL=" not in serialized
    assert "postgres://" not in serialized
