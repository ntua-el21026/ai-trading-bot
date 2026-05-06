"""Fake-safe alerting contracts."""

from packages.alerting.adapters import (
    AlertAdapter,
    EmailAlertAdapter,
    FakeAlertAdapter,
    TelegramAlertAdapter,
)
from packages.alerting.models import (
    AlertDispatchRequest,
    AlertDispatchResult,
    AlertMessage,
)
from packages.alerting.routing import AlertRouter

__all__ = [
    "AlertAdapter",
    "AlertDispatchRequest",
    "AlertDispatchResult",
    "AlertMessage",
    "AlertRouter",
    "EmailAlertAdapter",
    "FakeAlertAdapter",
    "TelegramAlertAdapter",
]
