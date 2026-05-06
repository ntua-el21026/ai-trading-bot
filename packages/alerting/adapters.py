"""Alert adapter protocols and fake/fail-closed implementations."""

from __future__ import annotations

from typing import Protocol

from packages.alerting.models import (
    AlertChannel,
    AlertDispatchRequest,
    AlertDispatchResult,
    AlertMessage,
)


class AlertAdapter(Protocol):
    channel: AlertChannel

    def dispatch(self, request: AlertDispatchRequest) -> AlertDispatchResult:
        """Dispatch an alert message through a channel boundary."""


class FakeAlertAdapter:
    channel: AlertChannel = "fake"

    def __init__(self) -> None:
        self.messages: list[AlertMessage] = []

    def dispatch(self, request: AlertDispatchRequest) -> AlertDispatchResult:
        self.messages.append(request.message)
        return AlertDispatchResult(
            status="captured",
            channel=self.channel,
            message=request.message,
            external_calls_performed=False,
        )


class TelegramAlertAdapter:
    channel: AlertChannel = "telegram"

    def __init__(self, *, bot_token: str | None = None, chat_id: str | None = None) -> None:
        self._configured = bool(bot_token and chat_id)

    def dispatch(self, request: AlertDispatchRequest) -> AlertDispatchResult:
        if not self._configured:
            return _failed_closed(
                channel=self.channel,
                message=request.message,
                error_message="Telegram alert adapter is not configured with required secrets.",
            )
        return _failed_closed(
            channel=self.channel,
            message=request.message,
            error_message="Telegram network delivery is disabled in this milestone.",
        )


class EmailAlertAdapter:
    channel: AlertChannel = "email"

    def __init__(self, *, smtp_url: str | None = None, from_address: str | None = None) -> None:
        self._configured = bool(smtp_url and from_address)

    def dispatch(self, request: AlertDispatchRequest) -> AlertDispatchResult:
        if not self._configured:
            return _failed_closed(
                channel=self.channel,
                message=request.message,
                error_message="Email alert adapter is not configured with required secrets.",
            )
        return _failed_closed(
            channel=self.channel,
            message=request.message,
            error_message="Email network delivery is disabled in this milestone.",
        )


def _failed_closed(
    *,
    channel: AlertChannel,
    message: AlertMessage,
    error_message: str,
) -> AlertDispatchResult:
    return AlertDispatchResult(
        status="failed_closed",
        channel=channel,
        message=message,
        external_calls_performed=False,
        error_message=error_message,
    )
