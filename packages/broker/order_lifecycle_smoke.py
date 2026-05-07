"""Explicitly gated Alpaca paper order-lifecycle smoke harness.

This module is operator-invoked validation tooling. It is not autonomous paper trading, does not
activate Temporal schedules, and refuses before write-capable broker calls unless every write-smoke
gate is satisfied.
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable, Iterable, Mapping, Sequence
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol, Self, cast
from uuid import NAMESPACE_URL, uuid5

from pydantic import BaseModel, ConfigDict, Field, model_validator

from packages.broker.adapters import BrokerAdapterNotConfigured
from packages.broker.alpaca import (
    ALPACA_PAPER_BASE_URL,
    AlpacaClientError,
    AlpacaPaperAdapter,
    AlpacaPaperCredentials,
    map_alpaca_clock,
    map_alpaca_order,
)
from packages.broker.models import (
    BrokerAccountSnapshot,
    BrokerOrder,
    BrokerPosition,
    BrokerProtectiveStop,
    BrokerSnapshot,
)
from packages.core.config import AppConfig, load_app_config
from packages.data.models import AssetClass
from packages.execution.idempotency import short_hash
from packages.execution.models import ExecutionIntent
from packages.reconciliation.models import InternalAccountSnapshot, InternalLedgerSnapshot
from packages.reconciliation.service import compare_broker_and_internal

RUN_ORDER_LIFECYCLE_SMOKE_ENV_VAR = "RUN_ALPACA_PAPER_ORDER_LIFECYCLE_SMOKE"
ORDER_LIFECYCLE_CONFIRM_ENV_VAR = "ALPACA_PAPER_ORDER_LIFECYCLE_CONFIRM"
ORDER_LIFECYCLE_CONFIRM_VALUE = "SUBMIT_AND_CLEAN_UP_TINY_PAPER_ORDER"
ORDER_LIFECYCLE_SYMBOL_ENV_VAR = "ALPACA_PAPER_ORDER_SMOKE_SYMBOL"
ORDER_LIFECYCLE_MAX_QTY_ENV_VAR = "ALPACA_PAPER_ORDER_SMOKE_MAX_QTY"
ORDER_LIFECYCLE_MAX_NOTIONAL_ENV_VAR = "ALPACA_PAPER_ORDER_SMOKE_MAX_NOTIONAL_USD"
ORDER_LIFECYCLE_TIMEOUT_ENV_VAR = "ALPACA_PAPER_ORDER_SMOKE_TIMEOUT_SECONDS"

MAX_SMOKE_QTY = 1
MAX_SMOKE_NOTIONAL_USD = 1000.0
MAX_SMOKE_TIMEOUT_SECONDS = 180.0
SMOKE_STRATEGY_VERSION = "paper_order_lifecycle_smoke_v0_3"
SMOKE_RISK_CONFIG_VERSION = "paper_order_lifecycle_smoke_cap_v0_3"
SMOKE_CLIENT_PREFIX = "smoke"
ETF_SYMBOLS = frozenset({"SPY", "QQQ", "DIA", "IWM", "XLK", "XLF", "XLE", "XLV"})


class AlpacaPaperOrderLifecycleSmokeGateError(RuntimeError):
    def __init__(self, failed_gates: Sequence[str]) -> None:
        self.failed_gates = tuple(failed_gates)
        joined = ", ".join(self.failed_gates)
        super().__init__(f"Alpaca paper order-lifecycle smoke gates failed: {joined}")


class AlpacaPaperOrderLifecycleClient(Protocol):
    def get_account(self) -> Mapping[str, Any]:
        """Return an Alpaca account payload."""

    def list_open_orders(self) -> Sequence[Mapping[str, Any]]:
        """Return open Alpaca orders."""

    def get_order_by_id(self, broker_order_id: str) -> Mapping[str, Any] | None:
        """Lookup an Alpaca order by broker order ID."""

    def get_order_by_client_order_id(self, client_order_id: str) -> Mapping[str, Any] | None:
        """Lookup an Alpaca order by client order ID."""

    def submit_order(self, request: Mapping[str, Any]) -> Mapping[str, Any]:
        """Submit an Alpaca paper order."""

    def cancel_order(self, broker_order_id: str) -> Mapping[str, Any]:
        """Cancel an Alpaca paper order by broker order ID."""

    def list_fills(self) -> Sequence[Mapping[str, Any]]:
        """Return recent fill payloads."""

    def list_positions(self) -> Sequence[Mapping[str, Any]]:
        """Return current positions."""

    def get_position(self, symbol: str) -> Mapping[str, Any] | None:
        """Return one current position by symbol."""

    def consume_trade_updates(self) -> Iterable[Mapping[str, Any]]:
        """Yield trade updates when a stream is configured."""

    def get_clock(self) -> Mapping[str, Any]:
        """Return Alpaca clock/session payload."""


class AlpacaPaperOrderLifecycleHttpClient:
    """Minimal Alpaca paper REST client for the explicitly gated write smoke."""

    def __init__(
        self,
        *,
        credentials: AlpacaPaperCredentials,
        timeout_seconds: float,
        opener: Any | None = None,
    ) -> None:
        if credentials.base_url != ALPACA_PAPER_BASE_URL:
            raise AlpacaClientError(
                "attempted_live_mode",
                "order-lifecycle smoke client requires the exact Alpaca paper endpoint",
                pause_new_risk=True,
            )
        self._credentials = credentials
        self._timeout_seconds = timeout_seconds
        self._opener = opener or urllib.request.urlopen

    def get_account(self) -> Mapping[str, Any]:
        return _json_mapping(self._request_json("GET", "/v2/account"))

    def list_open_orders(self) -> Sequence[Mapping[str, Any]]:
        value = self._request_json(
            "GET",
            "/v2/orders",
            params={"status": "open", "limit": "500", "direction": "desc"},
        )
        return _json_mapping_sequence(value)

    def get_order_by_id(self, broker_order_id: str) -> Mapping[str, Any] | None:
        value = self._request_optional_json(
            "GET",
            f"/v2/orders/{urllib.parse.quote(broker_order_id)}",
        )
        return None if value is None else _json_mapping(value)

    def get_order_by_client_order_id(self, client_order_id: str) -> Mapping[str, Any] | None:
        value = self._request_optional_json(
            "GET",
            "/v2/orders:by_client_order_id",
            params={"client_order_id": client_order_id},
        )
        return None if value is None else _json_mapping(value)

    def submit_order(self, request: Mapping[str, Any]) -> Mapping[str, Any]:
        return _json_mapping(self._request_json("POST", "/v2/orders", body=dict(request)))

    def cancel_order(self, broker_order_id: str) -> Mapping[str, Any]:
        existing = self.get_order_by_id(broker_order_id)
        self._request_json("DELETE", f"/v2/orders/{urllib.parse.quote(broker_order_id)}")
        after_cancel = self.get_order_by_id(broker_order_id)
        if after_cancel is not None:
            return after_cancel
        if existing is not None:
            return dict(existing) | {"status": "cancelled"}
        raise AlpacaClientError(
            "order_not_found",
            "paper order was not found after cancellation request",
        )

    def list_fills(self) -> Sequence[Mapping[str, Any]]:
        value = self._request_json(
            "GET",
            "/v2/account/activities/FILL",
            params={"direction": "desc", "page_size": "100"},
        )
        return _json_mapping_sequence(value)

    def list_positions(self) -> Sequence[Mapping[str, Any]]:
        value = self._request_json("GET", "/v2/positions")
        return _json_mapping_sequence(value)

    def get_position(self, symbol: str) -> Mapping[str, Any] | None:
        value = self._request_optional_json(
            "GET",
            f"/v2/positions/{urllib.parse.quote(symbol.upper())}",
        )
        return None if value is None else _json_mapping(value)

    def consume_trade_updates(self) -> Iterable[Mapping[str, Any]]:
        return ()

    def get_clock(self) -> Mapping[str, Any]:
        return _json_mapping(self._request_json("GET", "/v2/clock"))

    def _request_optional_json(
        self,
        method: str,
        path: str,
        *,
        params: Mapping[str, str] | None = None,
    ) -> object | None:
        try:
            return self._request_json(method, path, params=params)
        except AlpacaClientError as exc:
            if exc.code == "order_not_found":
                return None
            raise

    def _request_json(
        self,
        method: str,
        path: str,
        *,
        params: Mapping[str, str] | None = None,
        body: Mapping[str, Any] | None = None,
    ) -> object:
        encoded_body = None if body is None else json.dumps(body).encode("utf-8")
        request = urllib.request.Request(
            _build_url(self._credentials.base_url, path, params=params),
            data=encoded_body,
            headers={
                "APCA-API-KEY-ID": self._credentials.api_key,
                "APCA-API-SECRET-KEY": self._credentials.secret_key,
                "Accept": "application/json",
                "Content-Type": "application/json",
            },
            method=method,
        )
        try:
            with self._opener(request, timeout=self._timeout_seconds) as response:
                response_body = response.read()
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                raise AlpacaClientError(
                    "order_not_found",
                    "Alpaca paper resource was not found",
                ) from exc
            if exc.code in {401, 403}:
                raise AlpacaClientError(
                    "credential_rejected",
                    f"Alpaca paper write-smoke request was rejected with HTTP {exc.code}",
                    pause_new_risk=True,
                ) from exc
            raise AlpacaClientError(
                "rest_fallback_unavailable",
                f"Alpaca paper write-smoke request failed with HTTP {exc.code}",
                retryable=500 <= exc.code < 600,
            ) from exc
        except (urllib.error.URLError, OSError) as exc:
            raise AlpacaClientError(
                "rest_fallback_unavailable",
                "Alpaca paper write-smoke request failed before a response was received",
                retryable=True,
                details={"error_type": type(exc).__name__},
            ) from exc
        if not response_body:
            return {}
        try:
            return json.loads(response_body.decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise AlpacaClientError(
                "rest_fallback_unavailable",
                "Alpaca paper write-smoke response was not valid JSON",
            ) from exc


class AlpacaPaperOrderLifecycleSmokeSettings(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    symbol: str
    quantity: int = Field(gt=0, le=MAX_SMOKE_QTY)
    max_notional_usd: float = Field(gt=0, le=MAX_SMOKE_NOTIONAL_USD)
    timeout_seconds: float = Field(ge=0, le=MAX_SMOKE_TIMEOUT_SECONDS)

    @model_validator(mode="after")
    def validate_symbol(self) -> Self:
        if self.symbol != self.symbol.upper():
            raise ValueError("smoke symbol must be uppercase")
        return self

    @property
    def limit_price(self) -> float:
        return round(self.max_notional_usd / float(self.quantity), 2)

    @property
    def stop_loss_price(self) -> float:
        return max(0.01, round(self.limit_price * 0.5, 2))

    @property
    def estimated_notional_usd(self) -> float:
        return float(self.quantity) * self.limit_price


class AlpacaPaperOrderLifecycleSmokeSummary(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    gates_loaded: bool = False
    refused: bool = False
    refusal_reasons: tuple[str, ...] = ()
    target_symbol: str | None = None
    base_url: str | None = None
    credentials_loaded: bool = False
    paper_endpoint_used: bool = False
    live_endpoint_used: bool = False
    clock_reachable: bool = False
    clock_is_open: bool = False
    account_snapshot_reachable: bool = False
    preflight_reconciliation_clean: bool = False
    write_operations_attempted: bool = False
    order_write_endpoints_called: bool = False
    entry_order_submitted: bool = False
    entry_order_acknowledged: bool = False
    entry_order_filled: bool = False
    partial_fill_observed: bool = False
    protective_stop_submitted: bool = False
    protective_stop_verified: bool = False
    entry_order_cancelled: bool = False
    cleanup_exit_submitted: bool = False
    cleanup_exit_filled_or_confirmed: bool = False
    smoke_orders_cancelled: int = Field(default=0, ge=0)
    final_position_flat_for_symbol: bool = False
    broker_reconciliation_clean: bool = False
    raw_payloads_printed: bool = False
    secrets_printed: bool = False
    actual_paper_trading_started: bool = False
    live_trading_enabled: bool = False
    autonomous_execution_enabled: bool = False
    level4_ready: bool = False
    external_calls_performed: bool = False
    broker_ambiguity_detected: bool = False
    pause_new_risk_recommended: bool = False
    client_order_id_root: str | None = None
    entry_order_status: str | None = None
    filled_quantity: float = Field(default=0.0, ge=0)
    estimated_notional_usd: float | None = Field(default=None, ge=0)


OrderLifecycleClientFactory = Callable[
    [AlpacaPaperCredentials, AlpacaPaperOrderLifecycleSmokeSettings],
    AlpacaPaperOrderLifecycleClient,
]
Sleeper = Callable[[float], None]
Clock = Callable[[], float]


def build_alpaca_paper_order_lifecycle_http_client(
    credentials: AlpacaPaperCredentials,
    settings: AlpacaPaperOrderLifecycleSmokeSettings,
) -> AlpacaPaperOrderLifecycleClient:
    return AlpacaPaperOrderLifecycleHttpClient(
        credentials=credentials,
        timeout_seconds=max(settings.timeout_seconds, 1.0),
    )


def failed_alpaca_paper_order_lifecycle_smoke_gates(
    *,
    environ: Mapping[str, str],
    app_config: AppConfig,
) -> tuple[str, ...]:
    failed: list[str] = []
    if _env(environ, "ALPACA_API_KEY") == "":
        failed.append("ALPACA_API_KEY present")
    if _env(environ, "ALPACA_SECRET_KEY") == "":
        failed.append("ALPACA_SECRET_KEY present")
    if _env(environ, "ALPACA_BASE_URL") != ALPACA_PAPER_BASE_URL:
        failed.append("ALPACA_BASE_URL exact paper endpoint")
    if _env(environ, RUN_ORDER_LIFECYCLE_SMOKE_ENV_VAR) != "1":
        failed.append(f"{RUN_ORDER_LIFECYCLE_SMOKE_ENV_VAR}=1")
    if _env(environ, ORDER_LIFECYCLE_CONFIRM_ENV_VAR) != ORDER_LIFECYCLE_CONFIRM_VALUE:
        failed.append(f"{ORDER_LIFECYCLE_CONFIRM_ENV_VAR}={ORDER_LIFECYCLE_CONFIRM_VALUE}")

    symbol = _env(environ, ORDER_LIFECYCLE_SYMBOL_ENV_VAR).upper()
    if not symbol:
        failed.append(f"{ORDER_LIFECYCLE_SYMBOL_ENV_VAR} present")
    elif symbol not in app_config.live_universe.symbols:
        failed.append(f"{ORDER_LIFECYCLE_SYMBOL_ENV_VAR} approved live-universe symbol")

    quantity = _parse_int(_env(environ, ORDER_LIFECYCLE_MAX_QTY_ENV_VAR))
    if quantity is None:
        failed.append(f"{ORDER_LIFECYCLE_MAX_QTY_ENV_VAR} present integer")
    elif quantity <= 0 or quantity > MAX_SMOKE_QTY:
        failed.append(f"{ORDER_LIFECYCLE_MAX_QTY_ENV_VAR}<={MAX_SMOKE_QTY}")

    max_notional = _parse_float(_env(environ, ORDER_LIFECYCLE_MAX_NOTIONAL_ENV_VAR))
    if max_notional is None:
        failed.append(f"{ORDER_LIFECYCLE_MAX_NOTIONAL_ENV_VAR} present number")
    elif max_notional <= 0 or max_notional > MAX_SMOKE_NOTIONAL_USD:
        failed.append(f"{ORDER_LIFECYCLE_MAX_NOTIONAL_ENV_VAR}<={MAX_SMOKE_NOTIONAL_USD:.0f}")

    timeout_seconds = _parse_float(_env(environ, ORDER_LIFECYCLE_TIMEOUT_ENV_VAR))
    if timeout_seconds is None:
        failed.append(f"{ORDER_LIFECYCLE_TIMEOUT_ENV_VAR} present number")
    elif timeout_seconds < 0 or timeout_seconds > MAX_SMOKE_TIMEOUT_SECONDS:
        failed.append(f"{ORDER_LIFECYCLE_TIMEOUT_ENV_VAR}<={MAX_SMOKE_TIMEOUT_SECONDS:.0f}")

    if app_config.system.environment != "paper":
        failed.append('config/system.yaml environment="paper"')
    if not app_config.system.dry_run:
        failed.append("config/system.yaml dry_run=true")
    if app_config.system.live_trading_enabled:
        failed.append("config/system.yaml live_trading_enabled=false")
    if app_config.system.autonomous_execution_enabled:
        failed.append("config/system.yaml autonomous_execution_enabled=false")
    if app_config.execution.allow_live_orders:
        failed.append("config/execution.yaml allow_live_orders=false")
    if app_config.execution.autonomous_execution_enabled:
        failed.append("config/execution.yaml autonomous_execution_enabled=false")
    if not app_config.execution.require_execution_intent:
        failed.append("config/execution.yaml require_execution_intent=true")
    if not app_config.execution.require_passed_risk_check:
        failed.append("config/execution.yaml require_passed_risk_check=true")
    if not app_config.execution.require_broker_reconciliation_before_order:
        failed.append("config/execution.yaml require_broker_reconciliation_before_order=true")
    if not app_config.execution.require_protective_stop:
        failed.append("config/execution.yaml require_protective_stop=true")
    if app_config.ai.allow_ai_to_create_orders:
        failed.append("config/ai.yaml allow_ai_to_create_orders=false")
    if app_config.ai.allow_ai_to_modify_strategy:
        failed.append("config/ai.yaml allow_ai_to_modify_strategy=false")
    if app_config.ai.allow_ai_to_modify_risk_limits:
        failed.append("config/ai.yaml allow_ai_to_modify_risk_limits=false")
    if app_config.live_universe.allow_options or app_config.live_universe.allow_shorting:
        failed.append("config/universe.yaml no options or shorting")
    if (
        app_config.live_universe.allow_futures
        or app_config.live_universe.allow_crypto
        or app_config.live_universe.allow_prediction_markets
    ):
        failed.append("config/universe.yaml no futures, crypto, or prediction markets")
    if not _adapter_refuses_live_mode(app_config):
        failed.append("AlpacaPaperAdapter refuses live mode")
    return tuple(failed)


def order_lifecycle_smoke_settings_from_env(
    environ: Mapping[str, str],
) -> AlpacaPaperOrderLifecycleSmokeSettings:
    return AlpacaPaperOrderLifecycleSmokeSettings(
        symbol=_env(environ, ORDER_LIFECYCLE_SYMBOL_ENV_VAR).upper(),
        quantity=int(_env(environ, ORDER_LIFECYCLE_MAX_QTY_ENV_VAR)),
        max_notional_usd=float(_env(environ, ORDER_LIFECYCLE_MAX_NOTIONAL_ENV_VAR)),
        timeout_seconds=float(_env(environ, ORDER_LIFECYCLE_TIMEOUT_ENV_VAR)),
    )


def run_alpaca_paper_order_lifecycle_smoke(
    *,
    environ: Mapping[str, str] | None = None,
    app_config: AppConfig | None = None,
    client_factory: OrderLifecycleClientFactory = build_alpaca_paper_order_lifecycle_http_client,
    sleeper: Sleeper = time.sleep,
    clock: Clock = time.monotonic,
    current_time: Callable[[], datetime] | None = None,
) -> AlpacaPaperOrderLifecycleSmokeSummary:
    active_environ = os.environ if environ is None else environ
    active_config = load_app_config() if app_config is None else app_config
    base_url = _env(active_environ, "ALPACA_BASE_URL") or None
    symbol = _env(active_environ, ORDER_LIFECYCLE_SYMBOL_ENV_VAR).upper() or None
    failed_gates = failed_alpaca_paper_order_lifecycle_smoke_gates(
        environ=active_environ,
        app_config=active_config,
    )
    if failed_gates:
        return _summary(
            app_config=active_config,
            refused=True,
            refusal_reasons=failed_gates,
            target_symbol=symbol,
            base_url=base_url,
        )

    settings = order_lifecycle_smoke_settings_from_env(active_environ)
    credentials = AlpacaPaperCredentials(
        api_key=active_environ["ALPACA_API_KEY"].strip(),
        secret_key=active_environ["ALPACA_SECRET_KEY"].strip(),
        base_url=active_environ["ALPACA_BASE_URL"].strip(),
    )
    client = client_factory(credentials, settings)
    adapter = AlpacaPaperAdapter(
        system_config=active_config.system,
        execution_config=active_config.execution,
        client=client,
        credentials=credentials,
        run_mode="runtime",
    )

    account = adapter.account_snapshot()
    clock_snapshot = map_alpaca_clock(client.get_clock())
    open_orders = tuple(adapter.open_orders())
    positions = tuple(adapter.positions())
    preflight_refusals = _preflight_refusals(
        settings=settings,
        app_config=active_config,
        clock_is_open=clock_snapshot.is_open,
        open_orders=open_orders,
        positions=positions,
    )
    preflight_clean = _reconcile_symbol_state(
        app_config=active_config,
        account=account,
        open_orders=(),
        positions=(),
        protective_stops=(),
        as_of=clock_snapshot.timestamp,
    )
    if preflight_refusals:
        return _summary(
            app_config=active_config,
            gates_loaded=True,
            refused=True,
            refusal_reasons=preflight_refusals,
            target_symbol=settings.symbol,
            base_url=ALPACA_PAPER_BASE_URL,
            credentials_loaded=True,
            paper_endpoint_used=True,
            clock_reachable=True,
            clock_is_open=clock_snapshot.is_open,
            account_snapshot_reachable=True,
            preflight_reconciliation_clean=preflight_clean,
            external_calls_performed=True,
            estimated_notional_usd=settings.estimated_notional_usd,
        )

    now = (current_time or (lambda: datetime.now(UTC)))()
    intent = _build_smoke_intent(settings, active_config, now=now)
    summary_updates: dict[str, Any] = {
        "gates_loaded": True,
        "target_symbol": settings.symbol,
        "base_url": ALPACA_PAPER_BASE_URL,
        "credentials_loaded": True,
        "paper_endpoint_used": True,
        "clock_reachable": True,
        "clock_is_open": clock_snapshot.is_open,
        "account_snapshot_reachable": True,
        "preflight_reconciliation_clean": preflight_clean,
        "external_calls_performed": True,
        "client_order_id_root": intent.client_order_id_root,
        "estimated_notional_usd": settings.estimated_notional_usd,
    }

    try:
        entry_result = adapter.submit_entry_order(intent)
    except AlpacaClientError as exc:
        return _summary(
            app_config=active_config,
            **summary_updates,
            write_operations_attempted=True,
            order_write_endpoints_called=True,
            broker_ambiguity_detected=exc.ambiguous,
            pause_new_risk_recommended=exc.pause_new_risk or exc.ambiguous,
            refused=True,
            refusal_reasons=(f"broker_error:{exc.code}",),
        )

    if entry_result.status == "ambiguous":
        return _summary(
            app_config=active_config,
            **summary_updates,
            write_operations_attempted=True,
            order_write_endpoints_called=True,
            broker_ambiguity_detected=True,
            pause_new_risk_recommended=True,
            refused=True,
            refusal_reasons=("broker_ambiguity_detected",),
        )
    if entry_result.status != "succeeded" or entry_result.order is None:
        code = "unknown"
        if entry_result.error is not None:
            code = entry_result.error.code
        return _summary(
            app_config=active_config,
            **summary_updates,
            write_operations_attempted=True,
            order_write_endpoints_called=True,
            refused=True,
            refusal_reasons=(f"entry_submit_failed:{code}",),
        )

    entry_order = _poll_order_until_terminal(
        adapter,
        client_order_id=intent.client_order_id_root,
        initial_order=entry_result.order,
        timeout_seconds=settings.timeout_seconds,
        sleeper=sleeper,
        clock=clock,
    )
    filled_quantity = entry_order.filled_quantity
    entry_acknowledged = entry_order.status in {
        "new",
        "accepted",
        "pending_new",
        "partially_filled",
        "filled",
    }
    entry_filled = entry_order.status == "filled" or filled_quantity >= entry_order.quantity
    partial_fill = filled_quantity > 0 and not entry_filled
    lifecycle_updates: dict[str, Any] = {
        **summary_updates,
        "write_operations_attempted": True,
        "order_write_endpoints_called": True,
        "entry_order_submitted": True,
        "entry_order_acknowledged": entry_acknowledged,
        "entry_order_filled": entry_filled,
        "partial_fill_observed": partial_fill,
        "entry_order_status": entry_order.status,
        "filled_quantity": filled_quantity,
    }

    smoke_cancel_count = 0
    entry_cancelled = False
    stop_submitted = False
    stop_verified = False
    cleanup_submitted = False
    cleanup_filled = False

    if filled_quantity <= 0:
        if entry_order.is_open:
            cancel_result = adapter.cancel_order(intent.client_order_id_root)
            entry_cancelled = cancel_result.status == "succeeded"
            smoke_cancel_count += 1 if entry_cancelled else 0
        return _final_summary(
            adapter=adapter,
            app_config=active_config,
            account=account,
            symbol=settings.symbol,
            summary_updates=lifecycle_updates,
            entry_cancelled=entry_cancelled,
            smoke_cancel_count=smoke_cancel_count,
            as_of=(current_time or (lambda: datetime.now(UTC)))(),
        )

    stop_result = adapter.submit_protective_stop(intent, filled_quantity=filled_quantity)
    stop_submitted = stop_result.status == "succeeded" and stop_result.order is not None
    if stop_submitted and stop_result.order is not None:
        verify = adapter.verify_protective_stop(
            symbol=settings.symbol,
            required_quantity=filled_quantity,
            client_order_id=stop_result.order.client_order_id,
        )
        stop_verified = verify.protected

    if partial_fill and entry_order.is_open:
        cancel_result = adapter.cancel_order(intent.client_order_id_root)
        entry_cancelled = cancel_result.status == "succeeded"
        smoke_cancel_count += 1 if entry_cancelled else 0

    cleanup_order = _submit_cleanup_exit(
        client=client,
        symbol=settings.symbol,
        filled_quantity=filled_quantity,
        reference_limit_price=entry_order.limit_price or settings.limit_price,
        client_order_id=f"{intent.client_order_id_root}-cleanup-exit",
    )
    cleanup_submitted = cleanup_order is not None
    cleanup_filled = (
        cleanup_order is not None
        and (cleanup_order.status == "filled" or cleanup_order.filled_quantity >= filled_quantity)
    )
    smoke_cancel_count += _cancel_open_smoke_orders(
        adapter=adapter,
        symbol=settings.symbol,
        client_order_id_root=intent.client_order_id_root,
    )

    return _final_summary(
        adapter=adapter,
        app_config=active_config,
        account=account,
        symbol=settings.symbol,
        summary_updates=lifecycle_updates,
        protective_stop_submitted=stop_submitted,
        protective_stop_verified=stop_verified,
        entry_cancelled=entry_cancelled,
        cleanup_exit_submitted=cleanup_submitted,
        cleanup_exit_filled_or_confirmed=cleanup_filled,
        smoke_cancel_count=smoke_cancel_count,
        as_of=(current_time or (lambda: datetime.now(UTC)))(),
    )


def _preflight_refusals(
    *,
    settings: AlpacaPaperOrderLifecycleSmokeSettings,
    app_config: AppConfig,
    clock_is_open: bool,
    open_orders: tuple[BrokerOrder, ...],
    positions: tuple[BrokerPosition, ...],
) -> tuple[str, ...]:
    refusals: list[str] = []
    if not clock_is_open:
        refusals.append("alpaca_clock_open=true")
    if settings.symbol not in app_config.live_universe.symbols:
        refusals.append("target_symbol_approved_live_universe")
    if _asset_class_for_symbol(settings.symbol) not in {"equity", "etf"}:
        refusals.append("target_symbol_equity_or_etf")
    if settings.estimated_notional_usd > settings.max_notional_usd:
        refusals.append("estimated_notional_within_cap")
    if any(order.symbol == settings.symbol and order.is_open for order in open_orders):
        refusals.append("no_existing_open_order_for_symbol")
    if any(
        position.symbol == settings.symbol and abs(position.quantity) > 1e-9
        for position in positions
    ):
        refusals.append("no_existing_position_for_symbol")
    return tuple(refusals)


def _build_smoke_intent(
    settings: AlpacaPaperOrderLifecycleSmokeSettings,
    app_config: AppConfig,
    *,
    now: datetime,
) -> ExecutionIntent:
    if now.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    timestamp = now.strftime("%Y%m%dT%H%M%SZ")
    digest = short_hash(f"{settings.symbol}-{timestamp}-{settings.estimated_notional_usd}", 8)
    client_order_id_root = f"{SMOKE_CLIENT_PREFIX}-{settings.symbol}-{timestamp}-{digest}"
    decision_id = uuid5(NAMESPACE_URL, client_order_id_root)
    return ExecutionIntent(
        decision_id=decision_id,
        symbol=settings.symbol,
        side="buy",
        asset_class=_asset_class_for_symbol(settings.symbol),
        quantity=settings.quantity,
        entry_order_type="limit",
        limit_price=settings.limit_price,
        stop_loss_price=settings.stop_loss_price,
        time_in_force="day",
        strategy_version=SMOKE_STRATEGY_VERSION,
        risk_config_version=SMOKE_RISK_CONFIG_VERSION,
        autonomy_level=app_config.system.autonomy_level,
        requires_protective_stop=True,
        max_acceptable_slippage_bps=app_config.execution.max_acceptable_slippage_bps,
        expires_at=now + timedelta(seconds=max(settings.timeout_seconds, 1.0)),
        client_order_id_root=client_order_id_root,
        status="risk_approved",
        temporal_workflow_id=None,
    )


def _poll_order_until_terminal(
    adapter: AlpacaPaperAdapter,
    *,
    client_order_id: str,
    initial_order: BrokerOrder,
    timeout_seconds: float,
    sleeper: Sleeper,
    clock: Clock,
) -> BrokerOrder:
    order = initial_order
    if _terminal_or_filled(order):
        return order
    deadline = clock() + timeout_seconds
    while clock() < deadline:
        latest = adapter.order_by_client_order_id(client_order_id)
        if latest is not None:
            order = latest
        if _terminal_or_filled(order):
            return order
        sleeper(min(1.0, max(0.0, deadline - clock())))
    latest = adapter.order_by_client_order_id(client_order_id)
    return order if latest is None else latest


def _terminal_or_filled(order: BrokerOrder) -> bool:
    return (
        order.status in {"filled", "cancelled", "expired", "rejected"}
        or order.filled_quantity > 0
    )


def _submit_cleanup_exit(
    *,
    client: AlpacaPaperOrderLifecycleClient,
    symbol: str,
    filled_quantity: float,
    reference_limit_price: float,
    client_order_id: str,
) -> BrokerOrder | None:
    limit_price = max(0.01, round(reference_limit_price * 0.5, 2))
    request = {
        "symbol": symbol,
        "side": "sell",
        "type": "limit",
        "time_in_force": "day",
        "qty": str(filled_quantity),
        "limit_price": str(limit_price),
        "client_order_id": client_order_id,
        "extended_hours": False,
    }
    return map_alpaca_order(client.submit_order(request))


def _cancel_open_smoke_orders(
    *,
    adapter: AlpacaPaperAdapter,
    symbol: str,
    client_order_id_root: str,
) -> int:
    cancelled = 0
    for order in adapter.open_orders():
        if order.symbol != symbol:
            continue
        if not order.client_order_id.startswith(client_order_id_root):
            continue
        result = adapter.cancel_order(order.client_order_id)
        if result.status == "succeeded":
            cancelled += 1
    return cancelled


def _final_summary(
    *,
    adapter: AlpacaPaperAdapter,
    app_config: AppConfig,
    account: BrokerAccountSnapshot,
    symbol: str,
    summary_updates: Mapping[str, Any],
    as_of: datetime,
    protective_stop_submitted: bool = False,
    protective_stop_verified: bool = False,
    entry_cancelled: bool = False,
    cleanup_exit_submitted: bool = False,
    cleanup_exit_filled_or_confirmed: bool = False,
    smoke_cancel_count: int = 0,
) -> AlpacaPaperOrderLifecycleSmokeSummary:
    open_orders = tuple(order for order in adapter.open_orders() if order.symbol == symbol)
    positions = tuple(
        position
        for position in adapter.positions()
        if position.symbol == symbol and abs(position.quantity) > 1e-9
    )
    protective_stops = tuple(adapter.protective_stops(symbol))
    final_flat = not positions
    reconciliation_clean = _reconcile_symbol_state(
        app_config=app_config,
        account=account,
        open_orders=open_orders,
        positions=positions,
        protective_stops=protective_stops,
        as_of=as_of,
    )
    return _summary(
        app_config=app_config,
        **summary_updates,
        protective_stop_submitted=protective_stop_submitted,
        protective_stop_verified=protective_stop_verified,
        entry_order_cancelled=entry_cancelled,
        cleanup_exit_submitted=cleanup_exit_submitted,
        cleanup_exit_filled_or_confirmed=cleanup_exit_filled_or_confirmed,
        smoke_orders_cancelled=smoke_cancel_count,
        final_position_flat_for_symbol=final_flat,
        broker_reconciliation_clean=reconciliation_clean,
    )


def _reconcile_symbol_state(
    *,
    app_config: AppConfig,
    account: BrokerAccountSnapshot,
    open_orders: tuple[BrokerOrder, ...],
    positions: tuple[BrokerPosition, ...],
    protective_stops: tuple[BrokerProtectiveStop, ...],
    as_of: datetime,
) -> bool:
    broker_snapshot = BrokerSnapshot(
        account=account,
        open_orders=open_orders,
        positions=positions,
        protective_stops=protective_stops,
        as_of=as_of,
        source="rest_fallback",
    )
    internal_snapshot = InternalLedgerSnapshot(
        account=InternalAccountSnapshot(equity=account.equity, cash=account.cash, as_of=as_of),
        as_of=as_of,
    )
    result = compare_broker_and_internal(
        broker_snapshot=broker_snapshot,
        internal_snapshot=internal_snapshot,
        as_of=as_of,
        protective_stop_config=app_config.protective_stop,
    )
    return result.clean


def _summary(
    *,
    app_config: AppConfig,
    **updates: Any,
) -> AlpacaPaperOrderLifecycleSmokeSummary:
    return AlpacaPaperOrderLifecycleSmokeSummary(
        live_trading_enabled=app_config.system.live_trading_enabled,
        autonomous_execution_enabled=(
            app_config.system.autonomous_execution_enabled
            or app_config.execution.autonomous_execution_enabled
        ),
        **updates,
    )


def _asset_class_for_symbol(symbol: str) -> AssetClass:
    return "etf" if symbol in ETF_SYMBOLS else "equity"


def _adapter_refuses_live_mode(app_config: AppConfig) -> bool:
    live_system = app_config.system.model_copy(update={"environment": "live"})
    try:
        AlpacaPaperAdapter(
            system_config=live_system,
            execution_config=app_config.execution,
            client=_NoopOrderLifecycleClient(),
            run_mode="test",
        )
    except BrokerAdapterNotConfigured:
        return True
    return False


def _env(environ: Mapping[str, str], name: str) -> str:
    return environ.get(name, "").strip()


def _parse_int(value: str) -> int | None:
    try:
        return int(value)
    except ValueError:
        return None


def _parse_float(value: str) -> float | None:
    try:
        return float(value)
    except ValueError:
        return None


def _build_url(
    base_url: str,
    path: str,
    *,
    params: Mapping[str, str] | None = None,
) -> str:
    normalized_base = base_url.rstrip("/")
    normalized_path = path if path.startswith("/") else f"/{path}"
    query = "" if not params else f"?{urllib.parse.urlencode(params)}"
    return f"{normalized_base}{normalized_path}{query}"


def _json_mapping(value: object) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise AlpacaClientError(
            "rest_fallback_unavailable",
            f"expected JSON object from Alpaca, got {type(value).__name__}",
        )
    return cast(Mapping[str, Any], value)


def _json_mapping_sequence(value: object) -> tuple[Mapping[str, Any], ...]:
    if not isinstance(value, list):
        raise AlpacaClientError(
            "rest_fallback_unavailable",
            f"expected JSON list from Alpaca, got {type(value).__name__}",
        )
    return tuple(_json_mapping(item) for item in value)


class _NoopOrderLifecycleClient:
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

    def consume_trade_updates(self) -> Iterable[Mapping[str, Any]]:
        raise AssertionError("gate-only client must not be called")

    def get_clock(self) -> Mapping[str, Any]:
        raise AssertionError("gate-only client must not be called")
