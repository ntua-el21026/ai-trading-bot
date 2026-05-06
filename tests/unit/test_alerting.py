from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from packages.alerting.adapters import EmailAlertAdapter, FakeAlertAdapter, TelegramAlertAdapter
from packages.alerting.models import AlertDispatchRequest, AlertMessage
from packages.alerting.routing import AlertRouter

CREATED_AT = datetime(2026, 5, 6, 12, 0, tzinfo=UTC)


def _message(category: str = "report_generated", severity: str = "info") -> AlertMessage:
    return AlertMessage.model_validate(
        {
            "category": category,
            "severity": severity,
            "title": "Daily report generated",
            "body": "A dry-run report was generated from local ledger data.",
            "source_component": "reporting_activity",
            "created_at": CREATED_AT,
            "payload": {"report_id": "report-1"},
        }
    )


def test_alert_models_validate_required_fields_and_timezone() -> None:
    with pytest.raises(ValidationError, match="timezone-aware"):
        AlertMessage.model_validate(
            {
                "category": "report_generated",
                "severity": "info",
                "title": "Report",
                "body": "Generated.",
                "source_component": "test",
                "created_at": datetime(2026, 5, 6, 12, 0),
            }
        )

    with pytest.raises(ValidationError, match="at least one alert channel"):
        AlertDispatchRequest(message=_message(), channels=())


def test_alert_router_routes_critical_categories_to_fake_adapter() -> None:
    adapter = FakeAlertAdapter()
    router = AlertRouter(adapters=(adapter,))

    results = router.dispatch(_message(category="missing_protective_stop", severity="warning"))

    assert len(results) == 1
    assert results[0].status == "captured"
    assert results[0].channel == "fake"
    assert results[0].external_calls_performed is False
    assert adapter.messages[0].severity == "critical"


def test_fake_alert_adapter_captures_messages_without_network_calls() -> None:
    adapter = FakeAlertAdapter()
    request = AlertDispatchRequest(message=_message(), channels=("fake",))

    result = adapter.dispatch(request)

    assert result.status == "captured"
    assert result.external_calls_performed is False
    assert adapter.messages == [_message()]


def test_real_alert_adapter_skeletons_fail_closed_without_or_with_config() -> None:
    request = AlertDispatchRequest(message=_message(), channels=("telegram", "email"))

    telegram_missing = TelegramAlertAdapter().dispatch(request)
    email_missing = EmailAlertAdapter().dispatch(request)
    telegram_configured = TelegramAlertAdapter(bot_token="token", chat_id="chat").dispatch(request)
    email_configured = EmailAlertAdapter(
        smtp_url="smtp://localhost",
        from_address="ops@example.com",
    ).dispatch(request)

    assert telegram_missing.status == "failed_closed"
    assert email_missing.status == "failed_closed"
    assert telegram_configured.status == "failed_closed"
    assert email_configured.status == "failed_closed"
    assert all(
        result.external_calls_performed is False
        for result in (telegram_missing, email_missing, telegram_configured, email_configured)
    )
