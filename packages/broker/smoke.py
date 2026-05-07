"""Opt-in read-only Alpaca paper smoke validation.

The smoke path performs account/order/position/clock reads only. It never submits, cancels,
replaces, or modifies broker orders.
"""

from __future__ import annotations

import os
from collections.abc import Callable, Mapping, Sequence
from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict

from packages.broker.adapters import BrokerAdapterNotConfigured
from packages.broker.alpaca import (
    ALPACA_PAPER_BASE_URL,
    AlpacaPaperAdapter,
    AlpacaPaperCredentials,
    AlpacaPaperReadOnlyHttpClient,
    map_alpaca_account,
    map_alpaca_clock,
    map_alpaca_order,
    map_alpaca_position,
)
from packages.core.config import AppConfig, ExecutionConfig, SystemConfig, load_app_config

ALPACA_PAPER_SMOKE_CONFIRM_VALUE = "READ_ONLY_PAPER_ACCOUNT"


class AlpacaPaperReadOnlySmokeGateError(RuntimeError):
    def __init__(self, failed_gates: Sequence[str]) -> None:
        self.failed_gates = tuple(failed_gates)
        joined = ", ".join(self.failed_gates)
        super().__init__(f"Alpaca paper read-only smoke gates are not satisfied: {joined}")


class AlpacaPaperReadOnlyClient(Protocol):
    def get_account(self) -> Mapping[str, Any]:
        """Return an Alpaca account payload."""

    def list_open_orders(self) -> Sequence[Mapping[str, Any]]:
        """Return Alpaca open-order payloads."""

    def list_positions(self) -> Sequence[Mapping[str, Any]]:
        """Return Alpaca position payloads."""

    def get_clock(self) -> Mapping[str, Any]:
        """Return Alpaca clock payload."""


class AlpacaPaperReadOnlySmokeSummary(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    base_url: str
    credentials_loaded: bool
    system_live_trading_enabled: bool
    execution_allow_live_orders: bool
    adapter_live_mode_refused: bool
    account_snapshot_reachable: bool
    account_snapshot_mapped: bool
    open_orders_reachable: bool
    open_orders_mapped: bool
    open_orders_count: int
    positions_reachable: bool
    positions_mapped: bool
    positions_count: int
    clock_reachable: bool
    clock_mapped: bool
    clock_is_open: bool
    live_endpoint_used: bool = False
    write_operations_attempted: bool = False
    order_write_endpoints_called: bool = False
    orders_submitted: bool = False
    orders_cancelled: bool = False
    orders_replaced: bool = False
    stops_submitted: bool = False
    external_calls_performed: bool = True


ReadOnlyClientFactory = Callable[[AlpacaPaperCredentials], AlpacaPaperReadOnlyClient]


def build_alpaca_paper_readonly_http_client(
    credentials: AlpacaPaperCredentials,
) -> AlpacaPaperReadOnlyClient:
    return AlpacaPaperReadOnlyHttpClient(credentials=credentials)


def failed_alpaca_paper_readonly_smoke_gates(
    *,
    environ: Mapping[str, str],
    app_config: AppConfig,
) -> tuple[str, ...]:
    failed: list[str] = []
    api_key = environ.get("ALPACA_API_KEY", "").strip()
    secret_key = environ.get("ALPACA_SECRET_KEY", "").strip()
    base_url = environ.get("ALPACA_BASE_URL", "").strip()
    run_smoke = environ.get("RUN_ALPACA_PAPER_SMOKE", "").strip()
    confirm = environ.get("ALPACA_PAPER_SMOKE_CONFIRM", "").strip()
    if not api_key:
        failed.append("ALPACA_API_KEY present")
    if not secret_key:
        failed.append("ALPACA_SECRET_KEY present")
    if base_url != ALPACA_PAPER_BASE_URL:
        failed.append("ALPACA_BASE_URL exact paper endpoint")
    if run_smoke != "1":
        failed.append("RUN_ALPACA_PAPER_SMOKE=1")
    if confirm != ALPACA_PAPER_SMOKE_CONFIRM_VALUE:
        failed.append(f"ALPACA_PAPER_SMOKE_CONFIRM={ALPACA_PAPER_SMOKE_CONFIRM_VALUE}")
    if app_config.system.live_trading_enabled:
        failed.append("config/system.yaml live_trading_enabled=false")
    if app_config.system.autonomous_execution_enabled:
        failed.append("config/system.yaml autonomous_execution_enabled=false")
    if app_config.execution.allow_live_orders:
        failed.append("config/execution.yaml allow_live_orders=false")
    if app_config.execution.autonomous_execution_enabled:
        failed.append("config/execution.yaml autonomous_execution_enabled=false")
    if not _adapter_refuses_live_mode(app_config.system, app_config.execution):
        failed.append("AlpacaPaperAdapter refuses live mode")
    return tuple(failed)


def validate_alpaca_paper_readonly_smoke_gates(
    *,
    environ: Mapping[str, str],
    app_config: AppConfig,
) -> AlpacaPaperCredentials:
    failed = failed_alpaca_paper_readonly_smoke_gates(
        environ=environ,
        app_config=app_config,
    )
    if failed:
        raise AlpacaPaperReadOnlySmokeGateError(failed)
    return AlpacaPaperCredentials(
        api_key=environ["ALPACA_API_KEY"].strip(),
        secret_key=environ["ALPACA_SECRET_KEY"].strip(),
        base_url=environ["ALPACA_BASE_URL"].strip(),
    )


def run_alpaca_paper_readonly_smoke(
    *,
    environ: Mapping[str, str] | None = None,
    app_config: AppConfig | None = None,
    client_factory: ReadOnlyClientFactory = build_alpaca_paper_readonly_http_client,
) -> AlpacaPaperReadOnlySmokeSummary:
    active_environ = os.environ if environ is None else environ
    active_config = load_app_config() if app_config is None else app_config
    credentials = validate_alpaca_paper_readonly_smoke_gates(
        environ=active_environ,
        app_config=active_config,
    )
    client = client_factory(credentials)

    account = map_alpaca_account(client.get_account(), environment="paper")
    open_orders = tuple(map_alpaca_order(payload) for payload in client.list_open_orders())
    positions = tuple(map_alpaca_position(payload) for payload in client.list_positions())
    clock = map_alpaca_clock(client.get_clock())

    return AlpacaPaperReadOnlySmokeSummary(
        base_url=ALPACA_PAPER_BASE_URL,
        credentials_loaded=True,
        system_live_trading_enabled=active_config.system.live_trading_enabled,
        execution_allow_live_orders=active_config.execution.allow_live_orders,
        adapter_live_mode_refused=True,
        account_snapshot_reachable=True,
        account_snapshot_mapped=account.environment == "paper",
        open_orders_reachable=True,
        open_orders_mapped=all(order.broker_order_id for order in open_orders),
        open_orders_count=len(open_orders),
        positions_reachable=True,
        positions_mapped=all(position.symbol for position in positions),
        positions_count=len(positions),
        clock_reachable=True,
        clock_mapped=clock.timestamp.tzinfo is not None,
        clock_is_open=clock.is_open,
    )


def _adapter_refuses_live_mode(
    system_config: SystemConfig,
    execution_config: ExecutionConfig,
) -> bool:
    live_system = SystemConfig.model_validate(
        system_config.model_dump() | {"environment": "live", "live_trading_enabled": False}
    )
    try:
        AlpacaPaperAdapter(
            system_config=live_system,
            execution_config=execution_config,
            client=_NoopAlpacaClient(),
            run_mode="test",
        )
    except BrokerAdapterNotConfigured:
        return True
    return False


class _NoopAlpacaClient:
    def get_account(self) -> Mapping[str, Any]:
        raise AssertionError("gate-only client must not be called")

    def list_open_orders(self) -> Sequence[Mapping[str, Any]]:
        raise AssertionError("gate-only client must not be called")

    def get_order_by_id(self, broker_order_id: str) -> Mapping[str, Any] | None:
        raise AssertionError("gate-only client must not be called")

    def get_order_by_client_order_id(self, client_order_id: str) -> Mapping[str, Any] | None:
        raise AssertionError("gate-only client must not be called")

    def submit_order(self, request: Mapping[str, Any]) -> Mapping[str, Any]:
        raise AssertionError("gate-only client must not be called")

    def cancel_order(self, broker_order_id: str) -> Mapping[str, Any]:
        raise AssertionError("gate-only client must not be called")

    def list_fills(self) -> Sequence[Mapping[str, Any]]:
        raise AssertionError("gate-only client must not be called")

    def list_positions(self) -> Sequence[Mapping[str, Any]]:
        raise AssertionError("gate-only client must not be called")

    def get_position(self, symbol: str) -> Mapping[str, Any] | None:
        raise AssertionError("gate-only client must not be called")

    def consume_trade_updates(self) -> Sequence[Mapping[str, Any]]:
        raise AssertionError("gate-only client must not be called")
