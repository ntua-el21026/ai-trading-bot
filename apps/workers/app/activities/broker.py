"""Paper broker Temporal activity contracts.

Default activity wiring uses the in-memory fake Alpaca client. Real Alpaca paper clients must be
injected explicitly by a later runtime integration and are not used by default tests.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator
from temporalio import activity

from packages.broker.adapters import BrokerAdapter, BrokerAdapterNotConfigured
from packages.broker.alpaca import AlpacaClientError, map_alpaca_trade_update
from packages.broker.fakes import build_fake_alpaca_paper_adapter
from packages.broker.models import BrokerOperationError, BrokerOrder
from packages.execution.models import ExecutionIntent

BrokerActivityStatus = Literal["succeeded", "failed", "ambiguous", "not_found", "noop"]


class BrokerActivityModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class BrokerActivityContext(BrokerActivityModel):
    workflow_name: str
    purpose: str
    request_id: str | None = None


class BrokerActivityResult(BrokerActivityModel):
    activity_name: str
    status: BrokerActivityStatus
    external_calls_performed: bool = False
    payload: dict[str, Any] = Field(default_factory=dict)
    error: BrokerOperationError | None = None
    details: dict[str, str] = Field(default_factory=dict)


class BrokerActivityRequest(BrokerActivityModel):
    context: BrokerActivityContext


class BrokerLookupByClientOrderIdRequest(BrokerActivityRequest):
    client_order_id: str


class BrokerLookupByBrokerOrderIdRequest(BrokerActivityRequest):
    broker_order_id: str


class SubmitPaperEntryOrderRequest(BrokerActivityRequest):
    intent: ExecutionIntent


class CancelPaperOrderRequest(BrokerActivityRequest):
    client_order_id: str


class SubmitPaperProtectiveStopRequest(BrokerActivityRequest):
    intent: ExecutionIntent
    filled_quantity: float = Field(gt=0)


class VerifyPaperProtectiveStopRequest(BrokerActivityRequest):
    symbol: str
    required_quantity: float = Field(gt=0)
    client_order_id: str | None = None

    @field_validator("symbol")
    @classmethod
    def validate_symbol(cls, symbol: str) -> str:
        if symbol != symbol.upper():
            raise ValueError("symbol must be uppercase")
        return symbol


class MapTradeUpdateEventRequest(BrokerActivityRequest):
    payload: dict[str, Any]


class BrokerActivityService:
    """Adapter-backed broker activity service with fake-safe defaults."""

    def __init__(
        self,
        adapter: BrokerAdapter,
        *,
        external_calls_performed: bool = False,
    ) -> None:
        self._adapter = adapter
        self._external_calls_performed = external_calls_performed

    def get_account_snapshot(self, request: BrokerActivityRequest) -> BrokerActivityResult:
        return self._call_snapshot(
            "get_broker_account_snapshot",
            request,
            lambda: {"account": self._adapter.account_snapshot().model_dump(mode="json")},
        )

    def get_orders_snapshot(self, request: BrokerActivityRequest) -> BrokerActivityResult:
        return self._call_snapshot(
            "get_broker_orders_snapshot",
            request,
            lambda: {
                "orders": [
                    order.model_dump(mode="json") for order in self._adapter.open_orders()
                ]
            },
        )

    def get_positions_snapshot(self, request: BrokerActivityRequest) -> BrokerActivityResult:
        return self._call_snapshot(
            "get_broker_positions_snapshot",
            request,
            lambda: {
                "positions": [
                    position.model_dump(mode="json") for position in self._adapter.positions()
                ]
            },
        )

    def get_fills_snapshot(self, request: BrokerActivityRequest) -> BrokerActivityResult:
        return self._call_snapshot(
            "get_broker_fills_snapshot",
            request,
            lambda: {
                "fills": [fill.model_dump(mode="json") for fill in self._adapter.recent_fills()]
            },
        )

    def lookup_order_by_client_order_id(
        self,
        request: BrokerLookupByClientOrderIdRequest,
    ) -> BrokerActivityResult:
        return self._lookup(
            "lookup_broker_order_by_client_order_id",
            request.context,
            lambda: self._adapter.order_by_client_order_id(request.client_order_id),
            {"client_order_id": request.client_order_id},
        )

    def lookup_order_by_broker_order_id(
        self,
        request: BrokerLookupByBrokerOrderIdRequest,
    ) -> BrokerActivityResult:
        return self._lookup(
            "lookup_broker_order_by_broker_order_id",
            request.context,
            lambda: self._adapter.order_by_broker_order_id(request.broker_order_id),
            {"broker_order_id": request.broker_order_id},
        )

    def submit_entry_order(self, request: SubmitPaperEntryOrderRequest) -> BrokerActivityResult:
        result = self._adapter.submit_entry_order(request.intent)
        return _broker_result(
            "submit_paper_entry_order",
            request.context,
            status=result.status,
            payload={"result": result.model_dump(mode="json")},
            error=result.error,
            external_calls_performed=self._external_calls_performed,
        )

    def cancel_order(self, request: CancelPaperOrderRequest) -> BrokerActivityResult:
        result = self._adapter.cancel_order(request.client_order_id)
        return _broker_result(
            "cancel_paper_order",
            request.context,
            status=result.status,
            payload={"result": result.model_dump(mode="json")},
            error=result.error,
            external_calls_performed=self._external_calls_performed,
        )

    def submit_protective_stop(
        self,
        request: SubmitPaperProtectiveStopRequest,
    ) -> BrokerActivityResult:
        result = self._adapter.submit_protective_stop(
            request.intent,
            filled_quantity=request.filled_quantity,
        )
        return _broker_result(
            "submit_paper_protective_stop",
            request.context,
            status=result.status,
            payload={"result": result.model_dump(mode="json")},
            error=result.error,
            external_calls_performed=self._external_calls_performed,
        )

    def verify_protective_stop(
        self,
        request: VerifyPaperProtectiveStopRequest,
    ) -> BrokerActivityResult:
        result = self._adapter.verify_protective_stop(
            symbol=request.symbol,
            required_quantity=request.required_quantity,
            client_order_id=request.client_order_id,
        )
        return _broker_result(
            "verify_paper_protective_stop",
            request.context,
            status=result.status,
            payload={"result": result.model_dump(mode="json")},
            error=result.error,
            external_calls_performed=self._external_calls_performed,
        )

    def map_trade_update_event(self, request: MapTradeUpdateEventRequest) -> BrokerActivityResult:
        event = map_alpaca_trade_update(request.payload)
        return _broker_result(
            "map_trade_update_event",
            request.context,
            status="succeeded",
            payload={"event": event.model_dump(mode="json")},
            external_calls_performed=False,
        )

    def _call_snapshot(
        self,
        activity_name: str,
        request: BrokerActivityRequest,
        payload_factory: Callable[[], dict[str, Any]],
    ) -> BrokerActivityResult:
        try:
            return _broker_result(
                activity_name,
                request.context,
                status="succeeded",
                payload=payload_factory(),
                external_calls_performed=self._external_calls_performed,
            )
        except (AlpacaClientError, BrokerAdapterNotConfigured) as exc:
            return _broker_result(
                activity_name,
                request.context,
                status="failed",
                error=_activity_error(exc),
                external_calls_performed=self._external_calls_performed,
            )

    def _lookup(
        self,
        activity_name: str,
        context: BrokerActivityContext,
        lookup: Callable[[], BrokerOrder | None],
        details: dict[str, str],
    ) -> BrokerActivityResult:
        try:
            order = lookup()
        except (AlpacaClientError, BrokerAdapterNotConfigured) as exc:
            return _broker_result(
                activity_name,
                context,
                status="failed",
                error=_activity_error(exc),
                external_calls_performed=self._external_calls_performed,
            )
        if order is None:
            return _broker_result(
                activity_name,
                context,
                status="not_found",
                error=BrokerOperationError(
                    code="order_not_found",
                    message="broker order was not found",
                    details=details,
                ),
                external_calls_performed=self._external_calls_performed,
            )
        return _broker_result(
            activity_name,
            context,
            status="succeeded",
            payload={"order": order.model_dump(mode="json")},
            external_calls_performed=self._external_calls_performed,
        )


def build_fake_broker_activity_service() -> BrokerActivityService:
    return BrokerActivityService(build_fake_alpaca_paper_adapter(), external_calls_performed=False)


_broker_activity_service = build_fake_broker_activity_service()


def configure_broker_activity_service_for_tests(service: BrokerActivityService) -> None:
    global _broker_activity_service
    _broker_activity_service = service


def reset_broker_activity_service_for_tests() -> None:
    configure_broker_activity_service_for_tests(build_fake_broker_activity_service())


@activity.defn(name="get_broker_account_snapshot")
async def get_broker_account_snapshot(payload: BrokerActivityRequest) -> BrokerActivityResult:
    return _broker_activity_service.get_account_snapshot(payload)


@activity.defn(name="get_broker_orders_snapshot")
async def get_broker_orders_snapshot(payload: BrokerActivityRequest) -> BrokerActivityResult:
    return _broker_activity_service.get_orders_snapshot(payload)


@activity.defn(name="get_broker_positions_snapshot")
async def get_broker_positions_snapshot(payload: BrokerActivityRequest) -> BrokerActivityResult:
    return _broker_activity_service.get_positions_snapshot(payload)


@activity.defn(name="get_broker_fills_snapshot")
async def get_broker_fills_snapshot(payload: BrokerActivityRequest) -> BrokerActivityResult:
    return _broker_activity_service.get_fills_snapshot(payload)


@activity.defn(name="lookup_broker_order_by_client_order_id")
async def lookup_broker_order_by_client_order_id(
    payload: BrokerLookupByClientOrderIdRequest,
) -> BrokerActivityResult:
    return _broker_activity_service.lookup_order_by_client_order_id(payload)


@activity.defn(name="lookup_broker_order_by_broker_order_id")
async def lookup_broker_order_by_broker_order_id(
    payload: BrokerLookupByBrokerOrderIdRequest,
) -> BrokerActivityResult:
    return _broker_activity_service.lookup_order_by_broker_order_id(payload)


@activity.defn(name="submit_paper_entry_order")
async def submit_paper_entry_order(
    payload: SubmitPaperEntryOrderRequest,
) -> BrokerActivityResult:
    return _broker_activity_service.submit_entry_order(payload)


@activity.defn(name="cancel_paper_order")
async def cancel_paper_order(payload: CancelPaperOrderRequest) -> BrokerActivityResult:
    return _broker_activity_service.cancel_order(payload)


@activity.defn(name="submit_paper_protective_stop")
async def submit_paper_protective_stop(
    payload: SubmitPaperProtectiveStopRequest,
) -> BrokerActivityResult:
    return _broker_activity_service.submit_protective_stop(payload)


@activity.defn(name="verify_paper_protective_stop")
async def verify_paper_protective_stop(
    payload: VerifyPaperProtectiveStopRequest,
) -> BrokerActivityResult:
    return _broker_activity_service.verify_protective_stop(payload)


@activity.defn(name="map_trade_update_event")
async def map_trade_update_event(payload: MapTradeUpdateEventRequest) -> BrokerActivityResult:
    return _broker_activity_service.map_trade_update_event(payload)


BROKER_ACTIVITY_FUNCTIONS = (
    get_broker_account_snapshot,
    get_broker_orders_snapshot,
    get_broker_positions_snapshot,
    get_broker_fills_snapshot,
    lookup_broker_order_by_client_order_id,
    lookup_broker_order_by_broker_order_id,
    submit_paper_entry_order,
    cancel_paper_order,
    submit_paper_protective_stop,
    verify_paper_protective_stop,
    map_trade_update_event,
)


def _broker_result(
    activity_name: str,
    context: BrokerActivityContext,
    *,
    status: BrokerActivityStatus,
    payload: dict[str, Any] | None = None,
    error: BrokerOperationError | None = None,
    external_calls_performed: bool,
) -> BrokerActivityResult:
    return BrokerActivityResult(
        activity_name=activity_name,
        status=status,
        external_calls_performed=external_calls_performed,
        payload=payload or {},
        error=error,
        details={
            "workflow_name": context.workflow_name,
            "purpose": context.purpose,
            "external_calls": "yes" if external_calls_performed else "none",
        },
    )


def _activity_error(exc: AlpacaClientError | BrokerAdapterNotConfigured) -> BrokerOperationError:
    if isinstance(exc, AlpacaClientError):
        return BrokerOperationError(
            code=exc.code,
            message=str(exc),
            retryable=exc.retryable,
            ambiguous=exc.ambiguous,
            pause_new_risk=exc.pause_new_risk or exc.ambiguous,
            details=exc.details,
        )
    return BrokerOperationError(
        code="client_not_configured",
        message=str(exc),
        pause_new_risk=True,
    )
