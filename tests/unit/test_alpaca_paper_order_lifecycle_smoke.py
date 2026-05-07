from __future__ import annotations

import json
from collections.abc import Callable

from packages.broker.alpaca import ALPACA_PAPER_BASE_URL, AlpacaClientError, AlpacaPaperCredentials
from packages.broker.fakes import FakeAlpacaClient
from packages.broker.order_lifecycle_smoke import (
    ORDER_LIFECYCLE_CONFIRM_ENV_VAR,
    ORDER_LIFECYCLE_CONFIRM_VALUE,
    ORDER_LIFECYCLE_MAX_NOTIONAL_ENV_VAR,
    ORDER_LIFECYCLE_MAX_QTY_ENV_VAR,
    ORDER_LIFECYCLE_SYMBOL_ENV_VAR,
    ORDER_LIFECYCLE_TIMEOUT_ENV_VAR,
    RUN_ORDER_LIFECYCLE_SMOKE_ENV_VAR,
    AlpacaPaperOrderLifecycleClient,
    AlpacaPaperOrderLifecycleSmokeSettings,
    failed_alpaca_paper_order_lifecycle_smoke_gates,
    run_alpaca_paper_order_lifecycle_smoke,
)
from packages.core.config import AppConfig, load_app_config


def _safe_env(**updates: str) -> dict[str, str]:
    env = {
        "ALPACA_API_KEY": "paper-key",
        "ALPACA_SECRET_KEY": "paper-secret",
        "ALPACA_BASE_URL": ALPACA_PAPER_BASE_URL,
        RUN_ORDER_LIFECYCLE_SMOKE_ENV_VAR: "1",
        ORDER_LIFECYCLE_CONFIRM_ENV_VAR: ORDER_LIFECYCLE_CONFIRM_VALUE,
        ORDER_LIFECYCLE_SYMBOL_ENV_VAR: "AAPL",
        ORDER_LIFECYCLE_MAX_QTY_ENV_VAR: "1",
        ORDER_LIFECYCLE_MAX_NOTIONAL_ENV_VAR: "200",
        ORDER_LIFECYCLE_TIMEOUT_ENV_VAR: "0",
    }
    env.update(updates)
    return env


def _config(
    *,
    system_updates: dict[str, object] | None = None,
    execution_updates: dict[str, object] | None = None,
) -> AppConfig:
    app_config = load_app_config()
    return app_config.model_copy(
        update={
            "system": app_config.system.model_copy(update=system_updates or {}),
            "execution": app_config.execution.model_copy(update=execution_updates or {}),
        }
    )


def _client_factory(
    client: FakeAlpacaClient,
) -> Callable[
    [AlpacaPaperCredentials, AlpacaPaperOrderLifecycleSmokeSettings],
    AlpacaPaperOrderLifecycleClient,
]:
    def factory(
        _credentials: AlpacaPaperCredentials,
        _settings: AlpacaPaperOrderLifecycleSmokeSettings,
    ) -> AlpacaPaperOrderLifecycleClient:
        return client

    return factory


def _order_payload(**updates: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "id": "existing-order-1",
        "client_order_id": "manual-AAPL-order",
        "symbol": "AAPL",
        "side": "buy",
        "asset_class": "equity",
        "qty": "1",
        "filled_qty": "0",
        "type": "limit",
        "time_in_force": "day",
        "status": "accepted",
        "limit_price": "180.50",
        "submitted_at": "2026-05-04T14:00:00Z",
        "updated_at": "2026-05-04T14:00:00Z",
    }
    payload.update(updates)
    return payload


def _position_payload() -> dict[str, object]:
    return {
        "symbol": "AAPL",
        "asset_class": "equity",
        "qty": "1",
        "avg_entry_price": "180.25",
        "market_value": "180.25",
    }


def test_order_lifecycle_smoke_refuses_by_default_without_gates() -> None:
    summary = run_alpaca_paper_order_lifecycle_smoke(environ={}, app_config=load_app_config())

    assert summary.refused is True
    assert summary.gates_loaded is False
    assert summary.write_operations_attempted is False
    assert summary.entry_order_submitted is False
    assert summary.protective_stop_submitted is False
    assert summary.cleanup_exit_submitted is False
    assert RUN_ORDER_LIFECYCLE_SMOKE_ENV_VAR + "=1" in summary.refusal_reasons


def test_order_lifecycle_smoke_refuses_missing_confirmation_gate() -> None:
    env = _safe_env(**{ORDER_LIFECYCLE_CONFIRM_ENV_VAR: ""})

    failed = failed_alpaca_paper_order_lifecycle_smoke_gates(
        environ=env,
        app_config=load_app_config(),
    )

    assert f"{ORDER_LIFECYCLE_CONFIRM_ENV_VAR}={ORDER_LIFECYCLE_CONFIRM_VALUE}" in failed


def test_order_lifecycle_smoke_refuses_live_alpaca_base_url() -> None:
    summary = run_alpaca_paper_order_lifecycle_smoke(
        environ=_safe_env(ALPACA_BASE_URL="https://api.alpaca.markets"),
        app_config=load_app_config(),
    )

    assert summary.refused is True
    assert "ALPACA_BASE_URL exact paper endpoint" in summary.refusal_reasons
    assert summary.live_endpoint_used is False
    assert summary.write_operations_attempted is False


def test_order_lifecycle_smoke_refuses_live_and_autonomous_config_flags() -> None:
    live_summary = run_alpaca_paper_order_lifecycle_smoke(
        environ=_safe_env(),
        app_config=_config(system_updates={"live_trading_enabled": True}),
    )
    autonomous_summary = run_alpaca_paper_order_lifecycle_smoke(
        environ=_safe_env(),
        app_config=_config(system_updates={"autonomous_execution_enabled": True}),
    )

    assert "config/system.yaml live_trading_enabled=false" in live_summary.refusal_reasons
    assert (
        "config/system.yaml autonomous_execution_enabled=false"
        in autonomous_summary.refusal_reasons
    )


def test_order_lifecycle_smoke_refuses_allow_live_orders_config_flag() -> None:
    summary = run_alpaca_paper_order_lifecycle_smoke(
        environ=_safe_env(),
        app_config=_config(execution_updates={"allow_live_orders": True}),
    )

    assert "config/execution.yaml allow_live_orders=false" in summary.refusal_reasons
    assert summary.write_operations_attempted is False


def test_order_lifecycle_smoke_refuses_unsupported_symbol() -> None:
    summary = run_alpaca_paper_order_lifecycle_smoke(
        environ=_safe_env(**{ORDER_LIFECYCLE_SYMBOL_ENV_VAR: "TSLA"}),
        app_config=load_app_config(),
    )

    assert summary.refused is True
    assert (
        f"{ORDER_LIFECYCLE_SYMBOL_ENV_VAR} approved live-universe symbol"
        in summary.refusal_reasons
    )


def test_order_lifecycle_smoke_refuses_quantity_above_cap() -> None:
    summary = run_alpaca_paper_order_lifecycle_smoke(
        environ=_safe_env(**{ORDER_LIFECYCLE_MAX_QTY_ENV_VAR: "2"}),
        app_config=load_app_config(),
    )

    assert f"{ORDER_LIFECYCLE_MAX_QTY_ENV_VAR}<=1" in summary.refusal_reasons
    assert summary.write_operations_attempted is False


def test_order_lifecycle_smoke_refuses_notional_above_cap() -> None:
    summary = run_alpaca_paper_order_lifecycle_smoke(
        environ=_safe_env(**{ORDER_LIFECYCLE_MAX_NOTIONAL_ENV_VAR: "1000.01"}),
        app_config=load_app_config(),
    )

    assert f"{ORDER_LIFECYCLE_MAX_NOTIONAL_ENV_VAR}<=1000" in summary.refusal_reasons
    assert summary.write_operations_attempted is False


def test_order_lifecycle_smoke_refuses_existing_position_for_symbol() -> None:
    client = FakeAlpacaClient(positions=(_position_payload(),))

    summary = run_alpaca_paper_order_lifecycle_smoke(
        environ=_safe_env(),
        app_config=load_app_config(),
        client_factory=_client_factory(client),
    )

    assert summary.gates_loaded is True
    assert summary.refused is True
    assert "no_existing_position_for_symbol" in summary.refusal_reasons
    assert summary.write_operations_attempted is False


def test_order_lifecycle_smoke_refuses_existing_open_order_for_symbol() -> None:
    client = FakeAlpacaClient(orders=(_order_payload(),))

    summary = run_alpaca_paper_order_lifecycle_smoke(
        environ=_safe_env(),
        app_config=load_app_config(),
        client_factory=_client_factory(client),
    )

    assert summary.gates_loaded is True
    assert summary.refused is True
    assert "no_existing_open_order_for_symbol" in summary.refusal_reasons
    assert summary.write_operations_attempted is False


def test_fake_client_happy_path_submits_stop_cleans_up_and_sanitizes_summary() -> None:
    client = FakeAlpacaClient(
        submit_outcomes=(("filled", 1.0), ("accepted", 0.0), ("filled", 1.0)),
        mutate_positions_on_submit=True,
    )

    summary = run_alpaca_paper_order_lifecycle_smoke(
        environ=_safe_env(),
        app_config=load_app_config(),
        client_factory=_client_factory(client),
    )

    assert summary.refused is False
    assert summary.write_operations_attempted is True
    assert summary.entry_order_submitted is True
    assert summary.entry_order_acknowledged is True
    assert summary.entry_order_filled is True
    assert summary.protective_stop_submitted is True
    assert summary.protective_stop_verified is True
    assert summary.cleanup_exit_submitted is True
    assert summary.cleanup_exit_filled_or_confirmed is True
    assert summary.smoke_orders_cancelled == 1
    assert summary.final_position_flat_for_symbol is True
    assert summary.broker_reconciliation_clean is True
    assert summary.actual_paper_trading_started is False
    assert summary.level4_ready is False
    assert client.submitted_order_requests[0]["client_order_id"].startswith("smoke-AAPL-")
    assert client.submitted_order_requests[0]["type"] == "limit"
    assert client.submitted_order_requests[0]["time_in_force"] == "day"
    assert client.submitted_order_requests[0]["extended_hours"] is False
    serialized = json.dumps(summary.model_dump(mode="json"))
    assert "paper-key" not in serialized
    assert "paper-secret" not in serialized
    assert "raw_broker_payload" not in serialized


def test_fake_client_unfilled_path_cancels_entry_without_stop_or_cleanup() -> None:
    client = FakeAlpacaClient(submit_outcomes=(("accepted", 0.0),))

    summary = run_alpaca_paper_order_lifecycle_smoke(
        environ=_safe_env(),
        app_config=load_app_config(),
        client_factory=_client_factory(client),
    )

    assert summary.entry_order_submitted is True
    assert summary.entry_order_filled is False
    assert summary.entry_order_cancelled is True
    assert summary.protective_stop_submitted is False
    assert summary.cleanup_exit_submitted is False
    assert summary.smoke_orders_cancelled == 1
    assert summary.broker_reconciliation_clean is True


def test_fake_client_partial_fill_stops_filled_quantity_and_cleans_up() -> None:
    client = FakeAlpacaClient(
        submit_outcomes=(("partially_filled", 0.4), ("accepted", 0.0), ("filled", 0.4)),
        mutate_positions_on_submit=True,
    )

    summary = run_alpaca_paper_order_lifecycle_smoke(
        environ=_safe_env(),
        app_config=load_app_config(),
        client_factory=_client_factory(client),
    )

    assert summary.partial_fill_observed is True
    assert summary.filled_quantity == 0.4
    assert summary.protective_stop_submitted is True
    assert summary.protective_stop_verified is True
    assert summary.entry_order_cancelled is True
    assert summary.cleanup_exit_filled_or_confirmed is True
    assert summary.final_position_flat_for_symbol is True
    assert client.submitted_order_requests[1]["type"] == "stop"
    assert client.submitted_order_requests[1]["qty"] == "0.4"


def test_fake_client_ambiguity_path_pauses_without_blind_retry() -> None:
    client = FakeAlpacaClient(
        submit_error=AlpacaClientError(
            "broker_timeout",
            "paper broker submit timed out after request write",
            retryable=True,
            ambiguous=True,
            pause_new_risk=True,
        )
    )

    summary = run_alpaca_paper_order_lifecycle_smoke(
        environ=_safe_env(),
        app_config=load_app_config(),
        client_factory=_client_factory(client),
    )

    assert summary.refused is True
    assert summary.write_operations_attempted is True
    assert summary.broker_ambiguity_detected is True
    assert summary.pause_new_risk_recommended is True
    assert summary.entry_order_submitted is False
    assert client.submitted_order_requests == []
