"""Alert severity/category routing."""

from __future__ import annotations

from packages.alerting.adapters import AlertAdapter, FakeAlertAdapter
from packages.alerting.models import (
    AlertCategory,
    AlertChannel,
    AlertDispatchRequest,
    AlertDispatchResult,
    AlertMessage,
    AlertSeverity,
)

DEFAULT_CHANNELS_BY_SEVERITY: dict[AlertSeverity, tuple[AlertChannel, ...]] = {
    "info": ("fake",),
    "warning": ("fake",),
    "critical": ("fake",),
}

CRITICAL_CATEGORIES: frozenset[AlertCategory] = frozenset(
    {
        "protective_stop_critical",
        "missing_protective_stop",
        "reconciliation_mismatch",
        "duplicate_order_or_intent",
        "kill_switch_activation",
        "worker_unavailable",
        "execution_worker_unavailable",
        "broker_ambiguity",
        "ai_quality_degraded",
    }
)

WARNING_CATEGORIES: frozenset[AlertCategory] = frozenset(
    {
        "protective_stop_warning",
        "noncritical_reconciliation_issue",
        "stale_data",
        "provider_budget_exceeded",
        "ai_news_warning",
        "invalid_ai_payload",
        "repeated_invalid_ai_payloads",
        "trade_closed_loss",
    }
)


class AlertRouter:
    def __init__(
        self,
        adapters: tuple[AlertAdapter, ...] | None = None,
        *,
        channels_by_severity: dict[AlertSeverity, tuple[AlertChannel, ...]] | None = None,
    ) -> None:
        configured_adapters = adapters or (FakeAlertAdapter(),)
        self._adapters = {adapter.channel: adapter for adapter in configured_adapters}
        self._channels_by_severity = dict(channels_by_severity or DEFAULT_CHANNELS_BY_SEVERITY)

    def route(self, message: AlertMessage) -> AlertDispatchRequest:
        severity = _effective_severity(message)
        return AlertDispatchRequest(
            message=message.model_copy(update={"severity": severity}),
            channels=self._channels_by_severity[severity],
        )

    def dispatch(self, message: AlertMessage) -> tuple[AlertDispatchResult, ...]:
        request = self.route(message)
        results: list[AlertDispatchResult] = []
        for channel in request.channels:
            adapter = self._adapters.get(channel)
            if adapter is None:
                results.append(
                    AlertDispatchResult(
                        status="failed_closed",
                        channel=channel,
                        message=request.message,
                        external_calls_performed=False,
                        error_message=f"No adapter configured for alert channel {channel}.",
                    )
                )
                continue
            results.append(adapter.dispatch(request))
        return tuple(results)


def _effective_severity(message: AlertMessage) -> AlertSeverity:
    if message.category in CRITICAL_CATEGORIES:
        return "critical"
    if message.category in WARNING_CATEGORIES and message.severity == "info":
        return "warning"
    return message.severity
