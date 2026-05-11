"""Paper-only Alpaca adapter and normalized payload mapping.

This module intentionally avoids an Alpaca SDK dependency. The adapter depends on an injectable
client protocol so default tests can use fakes and future runtime wiring can pass an SDK-backed
wrapper behind explicit paper-mode gates.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Iterable, Mapping, Sequence
from datetime import UTC, datetime
from typing import Any, Literal, Protocol, Self, cast, get_args

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from packages.broker.adapters import BrokerAdapterNotConfigured
from packages.broker.models import (
    REST_FALLBACK_INTERVAL_SECONDS,
    BrokerAccountSnapshot,
    BrokerClockSnapshot,
    BrokerErrorCode,
    BrokerFill,
    BrokerOperationError,
    BrokerOperationStatus,
    BrokerOrder,
    BrokerOrderOperationResult,
    BrokerOrderStatus,
    BrokerOrderType,
    BrokerPosition,
    BrokerProtectiveStop,
    BrokerProtectiveStopVerificationResult,
    BrokerRestFallbackSnapshot,
    BrokerRestFallbackStatus,
    BrokerSide,
    BrokerStreamConnectionResult,
    BrokerStreamEvent,
    BrokerStreamEventType,
    BrokerTimeInForce,
)
from packages.core.config import ExecutionConfig, SystemConfig
from packages.data.models import AssetClass
from packages.data.payloads import hash_payload
from packages.execution.models import ExecutionIntent

ALPACA_PAPER_BASE_URL = "https://paper-api.alpaca.markets"
AdapterRunMode = Literal["runtime", "test"]

ALPACA_EVENT_TYPE_MAP: dict[str, BrokerStreamEventType] = {
    "new": "order_acknowledged",
    "accepted": "order_acknowledged",
    "pending_new": "order_acknowledged",
    "partial_fill": "partial_fill",
    "fill": "fill",
    "canceled": "cancelled",
    "cancelled": "cancelled",
    "rejected": "rejected",
    "expired": "expired",
    "replaced": "replaced",
}


class AlpacaModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class AlpacaPaperCredentials(AlpacaModel):
    """Runtime-only credentials contract.

    Tests use fake clients and do not instantiate this with real values.
    """

    api_key: str = Field(min_length=1)
    secret_key: str = Field(min_length=1)
    base_url: str = Field(default=ALPACA_PAPER_BASE_URL, min_length=1)

    @field_validator("base_url", mode="before")
    @classmethod
    def normalize_base_url(cls, value: object) -> str:
        return str(value).strip().rstrip("/")

    @model_validator(mode="after")
    def validate_paper_url(self) -> Self:
        if self.base_url != ALPACA_PAPER_BASE_URL:
            raise ValueError("Alpaca credentials must target the exact paper endpoint")
        return self


class AlpacaClientError(RuntimeError):
    """Structured error raised by client implementations and normalized by the adapter."""

    def __init__(
        self,
        code: BrokerErrorCode,
        message: str,
        *,
        retryable: bool = False,
        ambiguous: bool = False,
        pause_new_risk: bool = False,
        details: dict[str, str] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.retryable = retryable
        self.ambiguous = ambiguous
        self.pause_new_risk = pause_new_risk
        self.details = details or {}


class AlpacaClientProtocol(Protocol):
    """Minimal SDK-neutral client protocol used by the paper adapter."""

    def get_account(self) -> Mapping[str, Any]:
        """Return an Alpaca-like account payload."""

    def list_open_orders(self) -> Sequence[Mapping[str, Any]]:
        """Return Alpaca-like open order payloads."""

    def get_order_by_id(self, broker_order_id: str) -> Mapping[str, Any] | None:
        """Lookup an order by broker ID."""

    def get_order_by_client_order_id(self, client_order_id: str) -> Mapping[str, Any] | None:
        """Lookup an order by client order ID."""

    def submit_order(self, request: Mapping[str, Any]) -> Mapping[str, Any]:
        """Submit an order and return the broker payload."""

    def cancel_order(self, broker_order_id: str) -> Mapping[str, Any]:
        """Cancel an order by broker ID and return the broker payload."""

    def list_fills(self) -> Sequence[Mapping[str, Any]]:
        """Return recent fill payloads."""

    def list_positions(self) -> Sequence[Mapping[str, Any]]:
        """Return current position payloads."""

    def get_position(self, symbol: str) -> Mapping[str, Any] | None:
        """Lookup one position by symbol."""

    def consume_trade_updates(self) -> Iterable[Mapping[str, Any]]:
        """Yield Alpaca-like trade update payloads."""


class AlpacaPaperClient:
    """SDK-neutral wrapper around an explicitly supplied Alpaca trading client object."""

    def __init__(
        self,
        *,
        credentials: AlpacaPaperCredentials,
        trading_client: object,
    ) -> None:
        self._credentials = credentials
        self._trading_client = trading_client

    def get_account(self) -> Mapping[str, Any]:
        return _as_mapping(self._call(("get_account", "account")))

    def list_open_orders(self) -> Sequence[Mapping[str, Any]]:
        value = self._call(("list_open_orders", "get_orders"), status="open")
        return _as_mapping_sequence(value)

    def get_order_by_id(self, broker_order_id: str) -> Mapping[str, Any] | None:
        value = self._call_optional(("get_order_by_id", "get_order"), broker_order_id)
        return None if value is None else _as_mapping(value)

    def get_order_by_client_order_id(self, client_order_id: str) -> Mapping[str, Any] | None:
        value = self._call_optional(
            ("get_order_by_client_order_id", "get_order_by_client_id"),
            client_order_id,
        )
        return None if value is None else _as_mapping(value)

    def submit_order(self, request: Mapping[str, Any]) -> Mapping[str, Any]:
        return _as_mapping(self._call(("submit_order",), dict(request)))

    def cancel_order(self, broker_order_id: str) -> Mapping[str, Any]:
        return _as_mapping(self._call(("cancel_order", "cancel_order_by_id"), broker_order_id))

    def list_fills(self) -> Sequence[Mapping[str, Any]]:
        value = self._call(("list_fills", "get_fills"))
        return _as_mapping_sequence(value)

    def list_positions(self) -> Sequence[Mapping[str, Any]]:
        value = self._call(("list_positions", "get_all_positions"))
        return _as_mapping_sequence(value)

    def get_position(self, symbol: str) -> Mapping[str, Any] | None:
        value = self._call_optional(("get_position",), symbol)
        return None if value is None else _as_mapping(value)

    def consume_trade_updates(self) -> Iterable[Mapping[str, Any]]:
        value = self._call_optional(("consume_trade_updates", "trade_updates"), None)
        if value is None:
            raise AlpacaClientError(
                "stream_disconnect",
                "trade update stream client is not configured",
                retryable=True,
                ambiguous=True,
                pause_new_risk=True,
            )
        return _as_mapping_sequence(value)

    def _call(self, names: tuple[str, ...], *args: object, **kwargs: object) -> object:
        for name in names:
            method = getattr(self._trading_client, name, None)
            if callable(method):
                return method(*args, **kwargs)
        joined = ", ".join(names)
        raise AlpacaClientError(
            "client_not_configured",
            f"configured Alpaca client does not expose any of: {joined}",
        )

    def _call_optional(self, names: tuple[str, ...], *args: object) -> object | None:
        try:
            return self._call(names, *tuple(arg for arg in args if arg is not None))
        except KeyError:
            return None


class AlpacaPaperReadOnlyHttpClient:
    """Minimal read-only Alpaca paper REST client for opt-in smoke validation."""

    def __init__(
        self,
        *,
        credentials: AlpacaPaperCredentials,
        timeout_seconds: float = 10.0,
        opener: Any | None = None,
    ) -> None:
        if credentials.base_url != ALPACA_PAPER_BASE_URL:
            raise AlpacaClientError(
                "attempted_live_mode",
                "read-only smoke client requires the exact Alpaca paper endpoint",
                pause_new_risk=True,
            )
        self._credentials = credentials
        self._timeout_seconds = timeout_seconds
        self._opener = opener or urllib.request.urlopen

    def get_account(self) -> Mapping[str, Any]:
        return _json_mapping(self._get_json("/v2/account"))

    def list_open_orders(self) -> Sequence[Mapping[str, Any]]:
        value = self._get_json(
            "/v2/orders",
            params={"status": "open", "limit": "500", "direction": "desc"},
        )
        return _json_mapping_sequence(value)

    def get_order_by_id(self, broker_order_id: str) -> Mapping[str, Any] | None:
        value = self._get_optional_json(f"/v2/orders/{urllib.parse.quote(broker_order_id)}")
        return None if value is None else _json_mapping(value)

    def get_order_by_client_order_id(self, client_order_id: str) -> Mapping[str, Any] | None:
        value = self._get_optional_json(
            "/v2/orders:by_client_order_id",
            params={"client_order_id": client_order_id},
        )
        return None if value is None else _json_mapping(value)

    def submit_order(self, request: Mapping[str, Any]) -> Mapping[str, Any]:
        raise _read_only_write_error("submit_order")

    def cancel_order(self, broker_order_id: str) -> Mapping[str, Any]:
        raise _read_only_write_error("cancel_order")

    def list_fills(self) -> Sequence[Mapping[str, Any]]:
        value = self._get_json(
            "/v2/account/activities/FILL",
            params={"direction": "desc", "page_size": "100"},
        )
        return _json_mapping_sequence(value)

    def list_positions(self) -> Sequence[Mapping[str, Any]]:
        value = self._get_json("/v2/positions")
        return _json_mapping_sequence(value)

    def get_position(self, symbol: str) -> Mapping[str, Any] | None:
        value = self._get_optional_json(f"/v2/positions/{urllib.parse.quote(symbol.upper())}")
        return None if value is None else _json_mapping(value)

    def get_clock(self) -> Mapping[str, Any]:
        return _json_mapping(self._get_json("/v2/clock"))

    def consume_trade_updates(self) -> Iterable[Mapping[str, Any]]:
        return ()

    def _get_optional_json(
        self,
        path: str,
        *,
        params: Mapping[str, str] | None = None,
    ) -> object | None:
        try:
            return self._get_json(path, params=params)
        except AlpacaClientError as exc:
            if exc.code == "order_not_found":
                return None
            raise

    def _get_json(
        self,
        path: str,
        *,
        params: Mapping[str, str] | None = None,
    ) -> object:
        request = urllib.request.Request(
            build_alpaca_paper_url(self._credentials.base_url, path, params=params),
            headers=build_alpaca_auth_headers(self._credentials),
            method="GET",
        )
        try:
            with self._opener(request, timeout=self._timeout_seconds) as response:
                body = response.read()
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                raise AlpacaClientError(
                    "order_not_found",
                    "Alpaca paper resource was not found",
                ) from exc
            if exc.code in {401, 403}:
                raise AlpacaClientError(
                    "credential_rejected",
                    f"Alpaca paper read-only request was rejected with HTTP {exc.code}",
                    pause_new_risk=True,
                ) from exc
            raise AlpacaClientError(
                "rest_fallback_unavailable",
                f"Alpaca paper read-only request failed with HTTP {exc.code}",
                retryable=500 <= exc.code < 600,
            ) from exc
        except (urllib.error.URLError, OSError) as exc:
            raise AlpacaClientError(
                "rest_fallback_unavailable",
                "Alpaca paper read-only request failed before a response was received",
                retryable=True,
                details={"error_type": type(exc).__name__},
            ) from exc
        if not body:
            return {}
        try:
            return json.loads(body.decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise AlpacaClientError(
                "rest_fallback_unavailable",
                "Alpaca paper read-only response was not valid JSON",
            ) from exc


class AlpacaPaperAdapter:
    """Paper-mode broker adapter with explicit safety gates and injectable client behavior."""

    def __init__(
        self,
        *,
        system_config: SystemConfig,
        execution_config: ExecutionConfig,
        client: AlpacaClientProtocol | None = None,
        credentials: AlpacaPaperCredentials | None = None,
        run_mode: AdapterRunMode = "runtime",
    ) -> None:
        _validate_paper_gates(system_config=system_config, execution_config=execution_config)
        if run_mode == "runtime" and credentials is None:
            raise BrokerAdapterNotConfigured(
                "explicit Alpaca paper credentials are required in runtime mode"
            )
        if client is None:
            raise BrokerAdapterNotConfigured("Alpaca paper client is not configured")
        self._client = client
        self._credentials = credentials
        self._run_mode = run_mode

    def account_snapshot(self) -> BrokerAccountSnapshot:
        return map_alpaca_account(self._client.get_account(), environment="paper")

    def open_orders(self) -> tuple[BrokerOrder, ...]:
        return tuple(map_alpaca_order(payload) for payload in self._client.list_open_orders())

    def order_by_broker_order_id(self, broker_order_id: str) -> BrokerOrder | None:
        payload = self._client.get_order_by_id(broker_order_id)
        return None if payload is None else map_alpaca_order(payload)

    def order_by_client_order_id(self, client_order_id: str) -> BrokerOrder | None:
        payload = self._client.get_order_by_client_order_id(client_order_id)
        return None if payload is None else map_alpaca_order(payload)

    def recent_fills(self) -> tuple[BrokerFill, ...]:
        return tuple(map_alpaca_fill(payload) for payload in self._client.list_fills())

    def positions(self) -> tuple[BrokerPosition, ...]:
        return tuple(map_alpaca_position(payload) for payload in self._client.list_positions())

    def protective_stops(self, symbol: str | None = None) -> tuple[BrokerProtectiveStop, ...]:
        stops = tuple(
            map_alpaca_protective_stop(order)
            for order in self._client.list_open_orders()
            if _order_type(order.get("order_type") or order.get("type")) in {"stop", "stop_limit"}
        )
        if symbol is None:
            return stops
        return tuple(stop for stop in stops if stop.symbol == symbol.upper())

    def rest_fallback_snapshot(self) -> BrokerRestFallbackSnapshot:
        as_of = datetime.now(UTC)
        return BrokerRestFallbackSnapshot(
            account=self.account_snapshot(),
            open_orders=self.open_orders(),
            recent_fills=self.recent_fills(),
            positions=self.positions(),
            protective_stops=self.protective_stops(),
            as_of=as_of,
            poll_interval_seconds=REST_FALLBACK_INTERVAL_SECONDS,
        )

    def rest_fallback_status(self) -> BrokerRestFallbackStatus:
        try:
            self.rest_fallback_snapshot()
        except AlpacaClientError as exc:
            return BrokerRestFallbackStatus(
                available=False,
                error=_operation_error(exc, fallback_code="rest_fallback_unavailable"),
            )
        return BrokerRestFallbackStatus(available=True)

    def submit_entry_order(self, intent: ExecutionIntent) -> BrokerOrderOperationResult:
        validation_error = _validate_entry_intent(intent)
        if validation_error is not None:
            return _order_failure(
                "submit_paper_entry_order",
                status="failed",
                error=validation_error,
            )

        try:
            existing_order = self.order_by_client_order_id(intent.client_order_id_root)
        except AlpacaClientError as exc:
            return _order_failure(
                "submit_paper_entry_order",
                status=_status_from_error(exc),
                error=_operation_error(exc),
            )
        if existing_order is not None:
            return _result_from_existing_order(existing_order, operation="submit_paper_entry_order")

        request = build_paper_entry_order_request(intent)
        try:
            order = map_alpaca_order(self._client.submit_order(request))
        except AlpacaClientError as exc:
            return _order_failure(
                "submit_paper_entry_order",
                status=_status_from_error(exc),
                error=_operation_error(exc),
            )
        if order.status == "rejected":
            return _order_failure(
                "submit_paper_entry_order",
                status="failed",
                error=BrokerOperationError(
                    code="rejected_order",
                    message="Alpaca rejected the paper entry order",
                    pause_new_risk=True,
                    details={"client_order_id": order.client_order_id},
                ),
                order=order,
            )
        return _order_success("submit_paper_entry_order", order)

    def submit_order(self, intent: ExecutionIntent) -> BrokerOrderOperationResult:
        return self.submit_entry_order(intent)

    def cancel_order(self, client_order_id: str) -> BrokerOrderOperationResult:
        try:
            order = self.order_by_client_order_id(client_order_id)
        except AlpacaClientError as exc:
            return _order_failure(
                "cancel_paper_order",
                status=_status_from_error(exc),
                error=_operation_error(exc),
            )
        if order is None:
            return _order_failure(
                "cancel_paper_order",
                status="not_found",
                error=BrokerOperationError(
                    code="order_not_found",
                    message="paper order was not found by client_order_id",
                    details={"client_order_id": client_order_id},
                ),
            )
        try:
            cancelled = map_alpaca_order(self._client.cancel_order(order.broker_order_id))
        except AlpacaClientError as exc:
            return _order_failure(
                "cancel_paper_order",
                status=_status_from_error(exc),
                error=_operation_error(exc),
            )
        return _order_success("cancel_paper_order", cancelled)

    def submit_protective_stop(
        self,
        intent: ExecutionIntent,
        filled_quantity: float,
    ) -> BrokerOrderOperationResult:
        if filled_quantity <= 0:
            return _order_failure(
                "submit_paper_protective_stop",
                status="failed",
                error=BrokerOperationError(
                    code="invalid_order_request",
                    message="protective stop filled_quantity must be positive",
                ),
            )
        if filled_quantity > intent.quantity:
            return _order_failure(
                "submit_paper_protective_stop",
                status="failed",
                error=BrokerOperationError(
                    code="invalid_order_request",
                    message="protective stop quantity cannot exceed intent quantity",
                ),
            )
        if intent.stop_loss_price is None:
            return _order_failure(
                "submit_paper_protective_stop",
                status="failed",
                error=BrokerOperationError(
                    code="missing_protective_stop",
                    message="execution intent does not include a stop loss price",
                    pause_new_risk=True,
                ),
            )
        request = build_paper_protective_stop_request(intent, filled_quantity=filled_quantity)
        try:
            order = map_alpaca_order(self._client.submit_order(request))
        except AlpacaClientError as exc:
            return _order_failure(
                "submit_paper_protective_stop",
                status=_status_from_error(exc),
                error=_operation_error(exc),
            )
        return _order_success("submit_paper_protective_stop", order)

    def verify_protective_stop(
        self,
        *,
        symbol: str,
        required_quantity: float,
        client_order_id: str | None = None,
    ) -> BrokerProtectiveStopVerificationResult:
        normalized_symbol = symbol.upper()
        stops = self.protective_stops(normalized_symbol)
        for stop in stops:
            client_match = client_order_id is None or stop.client_order_id == client_order_id
            covers_quantity = stop.quantity >= required_quantity
            if client_match and stop.confirmed and stop.is_open and covers_quantity:
                return BrokerProtectiveStopVerificationResult(
                    symbol=normalized_symbol,
                    required_quantity=required_quantity,
                    protected=True,
                    stop=stop,
                    status="succeeded",
                )
        return BrokerProtectiveStopVerificationResult(
            symbol=normalized_symbol,
            required_quantity=required_quantity,
            protected=False,
            status="failed",
            error=BrokerOperationError(
                code="missing_protective_stop",
                message="no confirmed open protective stop covers the required quantity",
                pause_new_risk=True,
                details={"required_quantity": f"{required_quantity:.6f}"},
            ),
        )

    def stream_events(self) -> Iterable[BrokerStreamEvent]:
        for payload in self._client.consume_trade_updates():
            yield map_alpaca_trade_update(payload)

    def stream_connection_result(self) -> BrokerStreamConnectionResult:
        try:
            return BrokerStreamConnectionResult(connected=True, events=tuple(self.stream_events()))
        except AlpacaClientError as exc:
            return BrokerStreamConnectionResult(
                connected=False,
                error=_operation_error(exc, fallback_code="stream_disconnect"),
            )


def build_paper_entry_order_request(intent: ExecutionIntent) -> dict[str, Any]:
    return {
        "symbol": intent.symbol,
        "side": intent.side,
        "type": "limit",
        "time_in_force": "day",
        "qty": str(intent.quantity),
        "limit_price": str(intent.limit_price),
        "client_order_id": intent.client_order_id_root,
        "extended_hours": False,
    }


def build_paper_protective_stop_request(
    intent: ExecutionIntent,
    *,
    filled_quantity: float,
) -> dict[str, Any]:
    if intent.stop_loss_price is None:
        raise ValueError("protective stop requires stop_loss_price")
    return {
        "symbol": intent.symbol,
        "side": "sell" if intent.side == "buy" else "buy",
        "type": "stop",
        "time_in_force": "gtc",
        "qty": str(filled_quantity),
        "stop_price": str(intent.stop_loss_price),
        "client_order_id": f"{intent.client_order_id_root}-stop",
        "extended_hours": False,
    }


def map_alpaca_account(
    payload: Mapping[str, Any],
    *,
    environment: Literal["paper", "live"] = "paper",
    as_of: datetime | None = None,
) -> BrokerAccountSnapshot:
    timestamp = (
        _optional_datetime(payload.get("as_of"))
        or _optional_datetime(payload.get("updated_at"))
        or as_of
        or datetime.now(UTC)
    )
    return BrokerAccountSnapshot(
        account_id=str(payload.get("id") or payload.get("account_id")),
        environment=environment,
        equity=float(payload["equity"]),
        cash=float(payload["cash"]),
        buying_power=_optional_float(payload.get("buying_power")),
        currency=str(payload.get("currency", "USD")).upper(),
        as_of=timestamp,
        raw_payload_hash=hash_payload(payload),
    )


def map_alpaca_order(
    order_payload: Mapping[str, Any],
    *,
    raw_payload_hash: str | None = None,
) -> BrokerOrder:
    order_type = _order_type(order_payload.get("order_type") or order_payload.get("type"))
    status = _order_status(order_payload.get("status"))
    return BrokerOrder(
        broker_order_id=str(order_payload["id"]),
        client_order_id=str(order_payload["client_order_id"]),
        symbol=str(order_payload["symbol"]).upper(),
        side=_side(order_payload.get("side")),
        asset_class=_asset_class(order_payload.get("asset_class")),
        quantity=float(order_payload["qty"]),
        filled_quantity=float(order_payload.get("filled_qty") or 0.0),
        order_type=order_type,
        time_in_force=_time_in_force(order_payload.get("time_in_force")),
        status=status,
        submitted_at=_optional_datetime(order_payload.get("submitted_at")),
        updated_at=_optional_datetime(order_payload.get("updated_at")),
        limit_price=_optional_float(order_payload.get("limit_price")),
        stop_price=_optional_float(order_payload.get("stop_price")),
        purpose="protective_stop" if order_type in {"stop", "stop_limit"} else "entry",
        raw_payload_hash=raw_payload_hash or hash_payload(order_payload),
    )


def map_alpaca_fill(
    payload: Mapping[str, Any],
    *,
    raw_payload_hash: str | None = None,
) -> BrokerFill:
    filled_at = _datetime(payload.get("filled_at") or payload.get("transaction_time"))
    client_order_id = payload.get("client_order_id") or payload.get("order_id")
    return BrokerFill(
        broker_order_id=str(payload["order_id"]),
        client_order_id=str(client_order_id),
        symbol=str(payload["symbol"]).upper(),
        side=_side(payload.get("side")),
        quantity=_required_float(payload.get("qty") or payload.get("quantity"), "quantity"),
        price=float(payload["price"]),
        filled_at=filled_at,
        broker_fill_id=None if payload.get("id") is None else str(payload["id"]),
        raw_payload_hash=raw_payload_hash or hash_payload(payload),
    )


def map_alpaca_position(payload: Mapping[str, Any]) -> BrokerPosition:
    return BrokerPosition(
        symbol=str(payload["symbol"]).upper(),
        asset_class=_asset_class(payload.get("asset_class")),
        quantity=_required_float(payload.get("qty") or payload.get("quantity"), "quantity"),
        avg_entry_price=float(payload["avg_entry_price"]),
        market_value=_optional_float(payload.get("market_value")),
        opened_at=_optional_datetime(payload.get("opened_at")),
        raw_payload_hash=hash_payload(payload),
    )


def map_alpaca_clock(payload: Mapping[str, Any]) -> BrokerClockSnapshot:
    return BrokerClockSnapshot(
        is_open=bool(payload["is_open"]),
        timestamp=_datetime(payload["timestamp"]),
        next_open=_datetime(payload["next_open"]),
        next_close=_datetime(payload["next_close"]),
        raw_payload_hash=hash_payload(payload),
    )


def map_alpaca_protective_stop(payload: Mapping[str, Any]) -> BrokerProtectiveStop:
    order = map_alpaca_order(payload)
    if order.stop_price is None:
        raise ValueError("protective stop order must include stop_price")
    return BrokerProtectiveStop(
        broker_order_id=order.broker_order_id,
        client_order_id=order.client_order_id,
        symbol=order.symbol,
        quantity=order.quantity,
        stop_price=order.stop_price,
        status=order.status,
        confirmed=order.is_open,
        submitted_at=order.submitted_at,
        updated_at=order.updated_at,
        raw_payload_hash=order.raw_payload_hash,
    )


def map_alpaca_trade_update(payload: Mapping[str, Any]) -> BrokerStreamEvent:
    """Map one Alpaca trade_updates payload into normalized broker stream contracts."""

    order_payload = _mapping(payload.get("order"))
    event_name = str(payload.get("event", "unknown"))
    event_type = ALPACA_EVENT_TYPE_MAP.get(event_name, "unknown")
    event_at = _datetime(payload.get("timestamp") or payload.get("at"))
    raw_hash = hash_payload(payload)
    broker_order = map_alpaca_order(order_payload, raw_payload_hash=raw_hash)
    fill = (
        _map_stream_fill(payload, broker_order, event_at, raw_hash)
        if event_type in {"fill", "partial_fill"}
        else None
    )
    return BrokerStreamEvent(
        event_type=event_type,
        broker_order=broker_order,
        fill=fill,
        event_at=event_at,
        raw_payload_hash=raw_hash,
    )


def _map_stream_fill(
    payload: Mapping[str, Any],
    broker_order: BrokerOrder,
    event_at: datetime,
    raw_payload_hash: str,
) -> BrokerFill:
    fill_price = _optional_float(payload.get("price")) or broker_order.limit_price
    if fill_price is None:
        fill_price = _optional_float(_mapping(payload.get("order")).get("filled_avg_price"))
    if fill_price is None:
        raise ValueError("fill trade_update payload must include price or filled_avg_price")
    return BrokerFill(
        broker_order_id=broker_order.broker_order_id,
        client_order_id=broker_order.client_order_id,
        symbol=broker_order.symbol,
        side=broker_order.side,
        quantity=float(payload.get("qty") or broker_order.filled_quantity),
        price=fill_price,
        filled_at=event_at,
        broker_fill_id=None if payload.get("id") is None else str(payload["id"]),
        raw_payload_hash=raw_payload_hash,
    )


def _validate_paper_gates(
    *,
    system_config: SystemConfig,
    execution_config: ExecutionConfig,
) -> None:
    if system_config.environment != "paper":
        raise BrokerAdapterNotConfigured("AlpacaPaperAdapter only supports paper mode")
    if system_config.live_trading_enabled:
        raise BrokerAdapterNotConfigured("live_trading_enabled must remain false")
    if system_config.autonomous_execution_enabled or execution_config.autonomous_execution_enabled:
        raise BrokerAdapterNotConfigured("autonomous execution must remain disabled")
    if execution_config.allow_live_orders:
        raise BrokerAdapterNotConfigured("allow_live_orders must remain false")


def _validate_entry_intent(intent: ExecutionIntent) -> BrokerOperationError | None:
    if getattr(intent, "entry_order_type", None) != "limit":
        return BrokerOperationError(
            code="unsupported_order_type",
            message="new-risk paper entries must use DAY limit orders",
            pause_new_risk=True,
        )
    if getattr(intent, "time_in_force", None) != "day":
        return BrokerOperationError(
            code="invalid_order_request",
            message="new-risk paper entries must use DAY time in force",
            pause_new_risk=True,
        )
    if getattr(intent, "requires_protective_stop", False) and intent.stop_loss_price is None:
        return BrokerOperationError(
            code="missing_protective_stop",
            message="paper entry intent requires a protective stop price",
            pause_new_risk=True,
        )
    return None


def _result_from_existing_order(
    order: BrokerOrder,
    *,
    operation: str,
) -> BrokerOrderOperationResult:
    if order.status == "rejected":
        return _order_failure(
            operation,
            status="failed",
            error=BrokerOperationError(
                code="rejected_order",
                message="idempotency lookup found a rejected broker order",
                pause_new_risk=True,
                details={"client_order_id": order.client_order_id},
            ),
            order=order,
            idempotency_reused=True,
        )
    return _order_success(operation, order, idempotency_reused=True)


def _order_success(
    operation: str,
    order: BrokerOrder,
    *,
    idempotency_reused: bool = False,
) -> BrokerOrderOperationResult:
    return BrokerOrderOperationResult(
        operation=operation,
        status="succeeded",
        order=order,
        idempotency_reused=idempotency_reused,
        protective_stop_required_quantity=(
            order.filled_quantity if order.filled_quantity > 0 else None
        ),
    )


def _order_failure(
    operation: str,
    *,
    status: BrokerOperationStatus,
    error: BrokerOperationError,
    order: BrokerOrder | None = None,
    idempotency_reused: bool = False,
) -> BrokerOrderOperationResult:
    return BrokerOrderOperationResult(
        operation=operation,
        status=status,
        order=order,
        error=error,
        idempotency_reused=idempotency_reused,
    )


def _status_from_error(exc: AlpacaClientError) -> BrokerOperationStatus:
    if exc.ambiguous:
        return "ambiguous"
    if exc.code == "order_not_found":
        return "not_found"
    return "failed"


def _operation_error(
    exc: AlpacaClientError,
    *,
    fallback_code: BrokerErrorCode | None = None,
) -> BrokerOperationError:
    return BrokerOperationError(
        code=fallback_code or exc.code,
        message=str(exc),
        retryable=exc.retryable,
        ambiguous=exc.ambiguous,
        pause_new_risk=exc.pause_new_risk or exc.ambiguous,
        details=exc.details,
    )


def _mapping(value: object) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError("Alpaca trade update payload must contain an order mapping")
    return cast(Mapping[str, Any], value)


def _as_mapping(value: object) -> Mapping[str, Any]:
    if isinstance(value, Mapping):
        return cast(Mapping[str, Any], value)
    if isinstance(value, BaseModel):
        return value.model_dump()
    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        mapped = model_dump()
        if isinstance(mapped, Mapping):
            return cast(Mapping[str, Any], mapped)
    if hasattr(value, "__dict__"):
        return {
            key: item
            for key, item in vars(value).items()
            if not key.startswith("_") and not callable(item)
        }
    raise AlpacaClientError(
        "invalid_order_request",
        f"expected mapping-like Alpaca payload, got {type(value).__name__}",
    )


def _as_mapping_sequence(value: object) -> tuple[Mapping[str, Any], ...]:
    if isinstance(value, str | bytes) or not isinstance(value, Sequence):
        raise AlpacaClientError(
            "invalid_order_request",
            f"expected sequence of Alpaca payloads, got {type(value).__name__}",
        )
    return tuple(_as_mapping(item) for item in value)


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


def build_alpaca_paper_url(
    base_url: str,
    path: str,
    *,
    params: Mapping[str, str] | None = None,
) -> str:
    normalized_base = base_url.rstrip("/")
    normalized_path = path if path.startswith("/") else f"/{path}"
    query = "" if not params else f"?{urllib.parse.urlencode(params)}"
    return f"{normalized_base}{normalized_path}{query}"


def build_alpaca_auth_headers(
    credentials: AlpacaPaperCredentials,
    *,
    include_content_type: bool = False,
) -> dict[str, str]:
    headers = {
        "APCA-API-KEY-ID": credentials.api_key,
        "APCA-API-SECRET-KEY": credentials.secret_key,
        "Accept": "application/json",
    }
    if include_content_type:
        headers["Content-Type"] = "application/json"
    return headers


def _read_only_write_error(operation: str) -> AlpacaClientError:
    return AlpacaClientError(
        "client_not_configured",
        f"read-only Alpaca paper smoke client refuses write operation: {operation}",
        pause_new_risk=True,
    )


def _datetime(value: object) -> datetime:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            raise ValueError("datetime values must be timezone-aware")
        return value
    if not isinstance(value, str):
        raise ValueError("timestamp value is required")
    normalized = value.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed


def _optional_datetime(value: object) -> datetime | None:
    if value in (None, ""):
        return None
    return _datetime(value)


def _optional_float(value: object) -> float | None:
    if value in (None, ""):
        return None
    if not isinstance(value, str | int | float):
        raise ValueError(f"expected numeric value, got {type(value).__name__}")
    return float(value)


def _required_float(value: object, field_name: str) -> float:
    parsed = _optional_float(value)
    if parsed is None:
        raise ValueError(f"{field_name} is required")
    return parsed


def _side(value: object) -> BrokerSide:
    if value not in {"buy", "sell"}:
        raise ValueError(f"unsupported Alpaca side: {value}")
    return cast(BrokerSide, value)


def _order_type(value: object) -> BrokerOrderType:
    if value not in {"market", "limit", "stop", "stop_limit"}:
        raise ValueError(f"unsupported Alpaca order type: {value}")
    return cast(BrokerOrderType, value)


def _time_in_force(value: object) -> BrokerTimeInForce:
    if value not in {"day", "gtc", "ioc", "fok"}:
        raise ValueError(f"unsupported Alpaca time in force: {value}")
    return cast(BrokerTimeInForce, value)


def _order_status(value: object) -> BrokerOrderStatus:
    normalized = "cancelled" if value == "canceled" else str(value or "unknown")
    if normalized not in get_args(BrokerOrderStatus):
        return "unknown"
    return cast(BrokerOrderStatus, normalized)


def _asset_class(value: object) -> AssetClass:
    normalized = str(value or "equity")
    if normalized in {"us_equity", "us_equity_common"}:
        normalized = "equity"
    elif normalized == "us_equity_etf":
        normalized = "etf"
    if normalized not in get_args(AssetClass):
        return "other"
    return cast(AssetClass, normalized)
