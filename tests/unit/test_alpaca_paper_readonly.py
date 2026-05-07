from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Mapping, Sequence
from email.message import Message
from io import BytesIO
from typing import Any

import pytest

from packages.broker.alpaca import (
    ALPACA_PAPER_BASE_URL,
    AlpacaClientError,
    AlpacaPaperCredentials,
    AlpacaPaperReadOnlyHttpClient,
    map_alpaca_clock,
    map_alpaca_order,
    map_alpaca_position,
)
from packages.broker.smoke import (
    AlpacaPaperReadOnlySmokeGateError,
    failed_alpaca_paper_readonly_smoke_gates,
    run_alpaca_paper_readonly_smoke,
)
from packages.core.config import load_app_config


def _safe_env() -> dict[str, str]:
    return {
        "ALPACA_API_KEY": "paper-key",
        "ALPACA_SECRET_KEY": "paper-secret",
        "ALPACA_BASE_URL": ALPACA_PAPER_BASE_URL,
        "RUN_ALPACA_PAPER_SMOKE": "1",
        "ALPACA_PAPER_SMOKE_CONFIRM": "READ_ONLY_PAPER_ACCOUNT",
    }


def test_readonly_smoke_gates_fail_closed_without_explicit_env() -> None:
    app_config = load_app_config()

    failed_gates = failed_alpaca_paper_readonly_smoke_gates(
        environ={},
        app_config=app_config,
    )

    assert "ALPACA_API_KEY present" in failed_gates
    assert "ALPACA_SECRET_KEY present" in failed_gates
    assert "ALPACA_BASE_URL exact paper endpoint" in failed_gates
    assert "RUN_ALPACA_PAPER_SMOKE=1" in failed_gates
    assert "ALPACA_PAPER_SMOKE_CONFIRM=READ_ONLY_PAPER_ACCOUNT" in failed_gates


def test_readonly_smoke_gates_reject_live_endpoint() -> None:
    app_config = load_app_config()
    unsafe_env = _safe_env() | {"ALPACA_BASE_URL": "https://api.alpaca.markets"}

    with pytest.raises(AlpacaPaperReadOnlySmokeGateError) as exc_info:
        run_alpaca_paper_readonly_smoke(
            environ=unsafe_env,
            app_config=app_config,
            client_factory=lambda _credentials: _FakeReadOnlyClient(),
        )

    assert "ALPACA_BASE_URL exact paper endpoint" in exc_info.value.failed_gates


def test_readonly_http_client_uses_get_requests_and_maps_payloads() -> None:
    calls: list[tuple[str, str]] = []

    def opener(request: urllib.request.Request, timeout: float) -> _Response:
        calls.append((request.get_method(), request.full_url))
        path = urllib.parse.urlparse(request.full_url).path
        if path == "/v2/account":
            return _Response(_account_payload())
        if path == "/v2/orders":
            return _Response([_order_payload()])
        if path == "/v2/positions":
            return _Response([_position_payload()])
        if path == "/v2/clock":
            return _Response(_clock_payload())
        raise AssertionError(f"unexpected read-only path: {path}")

    client = AlpacaPaperReadOnlyHttpClient(
        credentials=AlpacaPaperCredentials(
            api_key="paper-key",
            secret_key="paper-secret",
            base_url=ALPACA_PAPER_BASE_URL,
        ),
        opener=opener,
    )

    assert client.get_account()["id"] == "paper-account"
    assert map_alpaca_order(client.list_open_orders()[0]).asset_class == "equity"
    assert map_alpaca_position(client.list_positions()[0]).asset_class == "equity"
    assert map_alpaca_clock(client.get_clock()).is_open is False
    assert calls
    assert all(method == "GET" for method, _url in calls)


def test_readonly_http_client_refuses_write_operations_without_request() -> None:
    calls: list[str] = []

    def opener(request: urllib.request.Request, timeout: float) -> _Response:
        calls.append(request.full_url)
        return _Response({})

    client = AlpacaPaperReadOnlyHttpClient(
        credentials=AlpacaPaperCredentials(
            api_key="paper-key",
            secret_key="paper-secret",
            base_url=ALPACA_PAPER_BASE_URL,
        ),
        opener=opener,
    )

    with pytest.raises(AlpacaClientError, match="refuses write operation"):
        client.submit_order({"symbol": "AAPL"})
    with pytest.raises(AlpacaClientError, match="refuses write operation"):
        client.cancel_order("broker-order-1")

    assert calls == []


def test_readonly_http_client_reports_rejected_credentials_distinctly() -> None:
    def opener(request: urllib.request.Request, timeout: float) -> _Response:
        raise urllib.error.HTTPError(
            request.full_url,
            401,
            "Unauthorized",
            Message(),
            BytesIO(b"{}"),
        )

    client = AlpacaPaperReadOnlyHttpClient(
        credentials=AlpacaPaperCredentials(
            api_key="paper-key",
            secret_key="paper-secret",
            base_url=ALPACA_PAPER_BASE_URL,
        ),
        opener=opener,
    )

    with pytest.raises(AlpacaClientError) as exc_info:
        client.get_account()

    assert exc_info.value.code == "credential_rejected"


def test_readonly_smoke_gates_trim_env_values() -> None:
    summary = run_alpaca_paper_readonly_smoke(
        environ={
            "ALPACA_API_KEY": " paper-key ",
            "ALPACA_SECRET_KEY": " paper-secret ",
            "ALPACA_BASE_URL": f" {ALPACA_PAPER_BASE_URL} ",
            "RUN_ALPACA_PAPER_SMOKE": " 1 ",
            "ALPACA_PAPER_SMOKE_CONFIRM": " READ_ONLY_PAPER_ACCOUNT ",
        },
        app_config=load_app_config(),
        client_factory=lambda _credentials: _FakeReadOnlyClient(),
    )

    assert summary.credentials_loaded is True


def test_readonly_smoke_summary_uses_sanitized_status_fields() -> None:
    summary = run_alpaca_paper_readonly_smoke(
        environ=_safe_env(),
        app_config=load_app_config(),
        client_factory=lambda _credentials: _FakeReadOnlyClient(),
    )

    assert summary.credentials_loaded is True
    assert summary.base_url == ALPACA_PAPER_BASE_URL
    assert summary.account_snapshot_mapped is True
    assert summary.open_orders_count == 1
    assert summary.positions_count == 1
    assert summary.clock_mapped is True
    assert summary.write_operations_attempted is False
    assert summary.order_write_endpoints_called is False
    assert summary.orders_submitted is False
    assert summary.orders_cancelled is False
    assert summary.stops_submitted is False


class _Response:
    def __init__(self, payload: object) -> None:
        self._payload = payload

    def __enter__(self) -> _Response:
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        return None

    def read(self) -> bytes:
        return json.dumps(self._payload).encode("utf-8")


class _FakeReadOnlyClient:
    def get_account(self) -> Mapping[str, Any]:
        return _account_payload()

    def list_open_orders(self) -> Sequence[Mapping[str, Any]]:
        return (_order_payload(),)

    def list_positions(self) -> Sequence[Mapping[str, Any]]:
        return (_position_payload(),)

    def get_clock(self) -> Mapping[str, Any]:
        return _clock_payload()


def _account_payload() -> dict[str, Any]:
    return {
        "id": "paper-account",
        "equity": "100000",
        "cash": "90000",
        "buying_power": "180000",
        "currency": "USD",
        "as_of": "2026-05-04T14:30:00Z",
    }


def _order_payload() -> dict[str, Any]:
    return {
        "id": "broker-order-1",
        "client_order_id": "strategy-AAPL-buy-20260504-1-abc123",
        "symbol": "AAPL",
        "side": "buy",
        "asset_class": "us_equity",
        "qty": "10",
        "filled_qty": "0",
        "type": "limit",
        "time_in_force": "day",
        "status": "accepted",
        "limit_price": "180.50",
        "submitted_at": "2026-05-04T14:00:00Z",
    }


def _position_payload() -> dict[str, Any]:
    return {
        "symbol": "AAPL",
        "asset_class": "us_equity",
        "qty": "10",
        "avg_entry_price": "180.25",
        "market_value": "1802.50",
    }


def _clock_payload() -> dict[str, Any]:
    return {
        "is_open": False,
        "timestamp": "2026-05-04T20:30:00Z",
        "next_open": "2026-05-05T13:30:00Z",
        "next_close": "2026-05-05T20:00:00Z",
    }
