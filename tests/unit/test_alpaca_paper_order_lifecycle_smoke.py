from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable, Mapping
from email.message import Message
from io import BytesIO
from typing import Any

import pytest
from pydantic import ValidationError

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
    AlpacaPaperOrderLifecycleHttpClient,
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


def test_order_lifecycle_credentials_normalize_paper_url_and_refuse_live_endpoint() -> None:
    credentials = AlpacaPaperCredentials(
        api_key="paper-key",
        secret_key="paper-secret",
        base_url=f"{ALPACA_PAPER_BASE_URL}/",
    )

    assert credentials.base_url == ALPACA_PAPER_BASE_URL

    with pytest.raises(ValidationError):
        AlpacaPaperCredentials(
            api_key="paper-key",
            secret_key="paper-secret",
            base_url="https://api.alpaca.markets",
        )


def test_order_lifecycle_http_client_uses_apca_headers_and_single_v2_path() -> None:
    calls: list[urllib.request.Request] = []

    def opener(request: urllib.request.Request, timeout: float) -> _Response:
        calls.append(request)
        path = urllib.parse.urlparse(request.full_url).path
        if path == "/v2/account":
            return _Response(_account_payload())
        if path == "/v2/orders":
            if request.get_method() == "POST":
                return _Response(_order_payload(client_order_id="smoke-AAPL-test"))
            return _Response([])
        if path == "/v2/orders:by_client_order_id":
            raise urllib.error.HTTPError(
                request.full_url,
                404,
                "Not Found",
                Message(),
                BytesIO(b"{}"),
            )
        raise AssertionError(f"unexpected lifecycle path: {path}")

    client = AlpacaPaperOrderLifecycleHttpClient(
        credentials=AlpacaPaperCredentials(
            api_key="paper-key",
            secret_key="paper-secret",
            base_url=f"{ALPACA_PAPER_BASE_URL}/",
        ),
        timeout_seconds=1,
        opener=opener,
    )

    assert client.get_account()["id"] == "paper-account"
    assert client.list_open_orders() == ()
    assert client.get_order_by_client_order_id("smoke-AAPL-test") is None
    client.submit_order(
        {
            "symbol": "AAPL",
            "side": "buy",
            "type": "limit",
            "time_in_force": "day",
            "qty": "1",
            "limit_price": "200",
            "client_order_id": "smoke-AAPL-test",
            "extended_hours": False,
        }
    )

    assert calls
    for request in calls:
        headers = {key.lower(): value for key, value in request.header_items()}
        assert headers["apca-api-key-id"] == "paper-key"
        assert headers["apca-api-secret-key"] == "paper-secret"
        assert request.full_url.startswith(ALPACA_PAPER_BASE_URL)
        assert "/v2/v2/" not in request.full_url


def test_order_lifecycle_http_client_maps_only_401_to_credential_rejected() -> None:
    def opener(request: urllib.request.Request, timeout: float) -> _Response:
        raise urllib.error.HTTPError(
            request.full_url,
            403,
            "Forbidden",
            Message(),
            BytesIO(b"{}"),
        )

    client = AlpacaPaperOrderLifecycleHttpClient(
        credentials=AlpacaPaperCredentials(
            api_key="paper-key",
            secret_key="paper-secret",
            base_url=ALPACA_PAPER_BASE_URL,
        ),
        timeout_seconds=1,
        opener=opener,
    )

    with pytest.raises(AlpacaClientError) as exc_info:
        client.submit_order({"client_order_id": "smoke-AAPL-test"})

    assert exc_info.value.code == "invalid_order_request"


def test_order_lifecycle_http_client_maps_401_to_credential_rejected() -> None:
    def opener(request: urllib.request.Request, timeout: float) -> _Response:
        raise urllib.error.HTTPError(
            request.full_url,
            401,
            "Unauthorized",
            Message(),
            BytesIO(b"{}"),
        )

    client = AlpacaPaperOrderLifecycleHttpClient(
        credentials=AlpacaPaperCredentials(
            api_key="paper-key",
            secret_key="paper-secret",
            base_url=ALPACA_PAPER_BASE_URL,
        ),
        timeout_seconds=1,
        opener=opener,
    )

    with pytest.raises(AlpacaClientError) as exc_info:
        client.get_account()

    assert exc_info.value.code == "credential_rejected"


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


def test_order_lifecycle_smoke_refuses_before_writes_on_account_preflight_auth_failure() -> None:
    client = FakeAlpacaClient(
        rest_error=AlpacaClientError(
            "credential_rejected",
            "paper account preflight was rejected",
            pause_new_risk=True,
        )
    )

    summary = run_alpaca_paper_order_lifecycle_smoke(
        environ=_safe_env(),
        app_config=load_app_config(),
        client_factory=_client_factory(client),
    )

    assert summary.refused is True
    assert "broker_preflight_error:credential_rejected" in summary.refusal_reasons
    assert summary.account_snapshot_reachable is False
    assert summary.write_operations_attempted is False
    assert client.submitted_order_requests == []


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
    assert summary.protective_stop_cancelled_after_cleanup is True
    assert summary.cleanup_exit_submitted is True
    assert summary.cleanup_exit_filled_or_confirmed is True
    assert summary.smoke_orders_cancelled == 1
    assert summary.final_open_smoke_orders == 0
    assert summary.final_position_flat_for_symbol is True
    assert summary.broker_reconciliation_clean is True
    assert summary.actual_paper_trading_started is False
    assert summary.level4_ready is False
    assert client.submitted_order_requests[0]["client_order_id"].startswith("smoke-AAPL-")
    assert client.submitted_order_requests[0]["type"] == "limit"
    assert client.submitted_order_requests[0]["time_in_force"] == "day"
    assert client.submitted_order_requests[0]["extended_hours"] is False
    cleanup_request = client.submitted_order_requests[2]
    assert cleanup_request["side"] == "sell"
    assert cleanup_request["type"] == "market"
    assert cleanup_request["time_in_force"] == "day"
    assert cleanup_request["qty"] == "1"
    assert cleanup_request["client_order_id"].endswith("-cleanup-exit")
    assert cleanup_request["extended_hours"] is False
    assert "limit_price" not in cleanup_request
    assert "stop_price" not in cleanup_request
    assert "notional" not in cleanup_request
    assert "position_intent" not in cleanup_request
    serialized = json.dumps(summary.model_dump(mode="json"))
    assert "paper-key" not in serialized
    assert "paper-secret" not in serialized
    assert "raw_broker_payload" not in serialized


def test_cleanup_retry_cancels_smoke_stop_then_closes_position_cleanly() -> None:
    client = _CleanupRejectingFakeAlpacaClient(
        cleanup_rejections=1,
        submit_outcomes=(("filled", 1.0), ("accepted", 0.0), ("filled", 1.0)),
        mutate_positions_on_submit=True,
    )

    summary = run_alpaca_paper_order_lifecycle_smoke(
        environ=_safe_env(),
        app_config=load_app_config(),
        client_factory=_client_factory(client),
    )

    assert summary.refused is False
    assert summary.protective_stop_submitted is True
    assert summary.protective_stop_verified is True
    assert summary.protective_stop_cancelled_after_cleanup is True
    assert summary.cleanup_exit_submitted is True
    assert summary.cleanup_exit_filled_or_confirmed is True
    assert summary.cleanup_needed is False
    assert summary.final_open_smoke_orders == 0
    assert summary.final_position_flat_for_symbol is True
    assert summary.broker_reconciliation_clean is True
    cleanup_requests = [
        request
        for request in client.submitted_order_requests
        if str(request["client_order_id"]).endswith("-cleanup-exit")
    ]
    assert len(cleanup_requests) == 2


def test_cleanup_failure_returns_sanitized_cleanup_needed_summary() -> None:
    client = _CleanupRejectingFakeAlpacaClient(
        cleanup_rejections=2,
        submit_outcomes=(("filled", 1.0), ("accepted", 0.0)),
        mutate_positions_on_submit=True,
    )

    summary = run_alpaca_paper_order_lifecycle_smoke(
        environ=_safe_env(),
        app_config=load_app_config(),
        client_factory=_client_factory(client),
    )

    assert summary.refused is True
    assert summary.protective_stop_submitted is True
    assert summary.protective_stop_verified is True
    assert summary.protective_stop_cancelled_after_cleanup is True
    assert summary.cleanup_exit_submitted is False
    assert summary.cleanup_exit_filled_or_confirmed is False
    assert summary.cleanup_needed is True
    assert summary.final_position_flat_for_symbol is False
    assert summary.broker_reconciliation_clean is False
    assert summary.broker_error_code == "invalid_order_request"
    assert summary.sanitized_http_status == "422"
    assert summary.sanitized_reason == "cleanup_exit_failed"
    assert summary.broker_error_retryable is False
    assert summary.broker_error_ambiguous is False
    serialized = json.dumps(summary.model_dump(mode="json"))
    assert "paper-key" not in serialized
    assert "paper-secret" not in serialized
    assert "raw_broker_payload" not in serialized


def test_cleanup_cancels_only_smoke_created_orders() -> None:
    non_smoke_order = _order_payload(
        id="manual-order-1",
        client_order_id="manual-QQQ-stop",
        symbol="QQQ",
        side="sell",
        type="stop",
        time_in_force="gtc",
        stop_price="300",
    )
    client = FakeAlpacaClient(
        orders=(non_smoke_order,),
        submit_outcomes=(("filled", 1.0), ("accepted", 0.0), ("filled", 1.0)),
        mutate_positions_on_submit=True,
    )

    summary = run_alpaca_paper_order_lifecycle_smoke(
        environ=_safe_env(),
        app_config=load_app_config(),
        client_factory=_client_factory(client),
    )

    assert summary.refused is False
    assert "manual-order-1" not in client.cancelled_broker_order_ids
    assert summary.final_open_smoke_orders == 0
    assert summary.final_position_flat_for_symbol is True


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


class _Response:
    def __init__(self, payload: object) -> None:
        self._payload = payload

    def __enter__(self) -> _Response:
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        return None

    def read(self) -> bytes:
        return json.dumps(self._payload).encode("utf-8")


def _account_payload() -> dict[str, Any]:
    return {
        "id": "paper-account",
        "equity": "100000",
        "cash": "90000",
        "buying_power": "180000",
        "currency": "USD",
        "as_of": "2026-05-04T14:30:00Z",
    }


class _CleanupRejectingFakeAlpacaClient(FakeAlpacaClient):
    def __init__(self, *, cleanup_rejections: int, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.cleanup_rejections = cleanup_rejections

    def submit_order(self, request: Mapping[str, Any]) -> Mapping[str, Any]:
        if str(request["client_order_id"]).endswith("-cleanup-exit"):
            if self.cleanup_rejections > 0:
                self.submitted_order_requests.append(dict(request))
                self.cleanup_rejections -= 1
                raise AlpacaClientError(
                    "invalid_order_request",
                    "fake cleanup order was rejected",
                    pause_new_risk=True,
                    details={"http_status": "422"},
                )
        return super().submit_order(request)
