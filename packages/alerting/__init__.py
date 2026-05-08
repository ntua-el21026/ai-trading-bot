"""Fake-safe alerting contracts."""

from packages.alerting.adapters import (
    AlertAdapter,
    EmailAlertAdapter,
    FakeAlertAdapter,
    TelegramAlertAdapter,
    TelegramDeliveryConfig,
    render_telegram_message,
    sanitize_alert_text,
)
from packages.alerting.models import (
    AlertDispatchRequest,
    AlertDispatchResult,
    AlertMessage,
)
from packages.alerting.routing import AlertRouter
from packages.alerting.templates import TradeOutcomeSummary

__all__ = [
    "AlertAdapter",
    "AlertDispatchRequest",
    "AlertDispatchResult",
    "AlertMessage",
    "AlertRouter",
    "EmailAlertAdapter",
    "FakeAlertAdapter",
    "TelegramDeliveryConfig",
    "TelegramAlertAdapter",
    "TradeOutcomeSummary",
    "render_telegram_message",
    "sanitize_alert_text",
]
