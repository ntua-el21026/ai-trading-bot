from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Literal, cast

from packages.alerting.adapters import (
    TelegramAlertAdapter,
    TelegramDeliveryConfig,
    TelegramDeliveryError,
    TelegramSendResult,
    render_telegram_message,
)
from packages.alerting.models import AlertDispatchRequest, AlertMessage
from packages.alerting.routing import AlertRouter
from packages.alerting.smoke import run_telegram_alert_smoke
from packages.alerting.templates import (
    TradeOutcomeSummary,
    build_ai_news_warning_alert,
    build_daily_report_alert,
    build_fill_alert,
    build_generic_incident_alert,
    build_kill_switch_alert,
    build_order_submitted_alert,
    build_protective_stop_confirmed_alert,
    build_protective_stop_missing_alert,
    build_reconciliation_mismatch_alert,
    build_test_alert,
    build_trade_outcome_alert,
    build_weekly_report_alert,
)
from packages.reporting.generators import (
    default_week_bounds,
    generate_daily_report,
    generate_weekly_report,
)
from packages.reporting.models import DailyReport, ReportInputSnapshot, WeeklyReport

NOW = datetime(2026, 5, 8, 12, 0, tzinfo=UTC)


class FakeTelegramClient:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.messages: list[str] = []

    def send_message(
        self,
        *,
        bot_token: str,
        chat_id: str,
        text: str,
        timeout_seconds: int,
    ) -> TelegramSendResult:
        assert bot_token
        assert chat_id
        assert timeout_seconds > 0
        if self.fail:
            raise TelegramDeliveryError(
                code="telegram_api_rejected",
                sanitized_message="Telegram API rejected the message.",
            )
        self.messages.append(text)
        return TelegramSendResult(provider_message_id="telegram-message-1")


def _message(severity: Literal["info", "warning", "critical"] = "info") -> AlertMessage:
    return AlertMessage(
        category="routine_status",
        severity=severity,
        title="Status",
        body="Routine status update.",
        source_component="unit_test",
        created_at=NOW,
    )


def _gated_env(**overrides: str) -> dict[str, str]:
    env = {
        "ALERT_PROVIDER_PRIMARY": "telegram",
        "ALERT_ENABLE_REAL_DELIVERY": "true",
        "ALERT_DAILY_MESSAGE_LIMIT": "50",
        "ALERT_CRITICAL_BYPASS_DAILY_LIMIT": "true",
        "TELEGRAM_BOT_TOKEN": "123456:unit-test-token",
        "TELEGRAM_CHAT_ID": "987654321",
        "RUN_TELEGRAM_ALERT_SMOKE": "1",
        "TELEGRAM_ALERT_SMOKE_CONFIRM": "SEND_TEST_ALERT_TO_OPERATOR",
        "TELEGRAM_ALERT_SMOKE_MAX_MESSAGES": "3",
    }
    env.update(overrides)
    return env


def test_telegram_adapter_refuses_without_explicit_gates() -> None:
    adapter = TelegramAlertAdapter(
        config=TelegramDeliveryConfig.from_mapping({}),
        client=FakeTelegramClient(),
    )

    result = adapter.dispatch(AlertDispatchRequest(message=_message(), channels=("telegram",)))

    assert result.status == "failed_closed"
    assert result.failure_code == "telegram_gates_missing"
    assert result.external_calls_performed is False


def test_telegram_adapter_refuses_when_real_delivery_disabled() -> None:
    env = _gated_env(ALERT_ENABLE_REAL_DELIVERY="false")
    adapter = TelegramAlertAdapter(
        config=TelegramDeliveryConfig.from_mapping(env),
        client=FakeTelegramClient(),
    )

    result = adapter.dispatch(AlertDispatchRequest(message=_message(), channels=("telegram",)))

    assert result.status == "failed_closed"
    assert result.external_calls_performed is False


def test_telegram_adapter_refuses_without_token_or_chat_id_or_confirm() -> None:
    for override in (
        {"TELEGRAM_BOT_TOKEN": ""},
        {"TELEGRAM_CHAT_ID": ""},
        {"TELEGRAM_ALERT_SMOKE_CONFIRM": ""},
    ):
        adapter = TelegramAlertAdapter(
            config=TelegramDeliveryConfig.from_mapping(_gated_env(**override)),
            client=FakeTelegramClient(),
        )

        result = adapter.dispatch(AlertDispatchRequest(message=_message(), channels=("telegram",)))

        assert result.status == "failed_closed"
        assert result.external_calls_performed is False


def test_telegram_adapter_sends_with_fake_client_when_all_gates_loaded() -> None:
    client = FakeTelegramClient()
    adapter = TelegramAlertAdapter(
        config=TelegramDeliveryConfig.from_mapping(_gated_env()),
        client=client,
    )

    result = adapter.dispatch(AlertDispatchRequest(message=_message(), channels=("telegram",)))

    assert result.status == "sent"
    assert result.external_calls_performed is True
    assert result.provider_message_id == "telegram-message-1"
    assert len(client.messages) == 1


def test_telegram_adapter_respects_smoke_and_daily_message_limits() -> None:
    client = FakeTelegramClient()
    adapter = TelegramAlertAdapter(
        config=TelegramDeliveryConfig.from_mapping(
            _gated_env(TELEGRAM_ALERT_SMOKE_MAX_MESSAGES="1")
        ),
        client=client,
    )

    first = adapter.dispatch(AlertDispatchRequest(message=_message(), channels=("telegram",)))
    second = adapter.dispatch(AlertDispatchRequest(message=_message(), channels=("telegram",)))

    assert first.status == "sent"
    assert second.status == "failed_closed"
    assert second.failure_code == "telegram_smoke_limit_exceeded"

    daily_limited = TelegramAlertAdapter(
        config=TelegramDeliveryConfig.from_mapping(
            _gated_env(ALERT_DAILY_MESSAGE_LIMIT="0")
        ),
        client=FakeTelegramClient(),
    )
    normal = daily_limited.dispatch(
        AlertDispatchRequest(message=_message("warning"), channels=("telegram",))
    )
    critical = daily_limited.dispatch(
        AlertDispatchRequest(message=_message("critical"), channels=("telegram",))
    )

    assert normal.failure_code == "telegram_daily_limit_exceeded"
    assert critical.status == "sent"


def test_telegram_adapter_sanitizes_message_text_and_handles_api_errors() -> None:
    secret_message = AlertMessage(
        category="routine_status",
        severity="info",
        title="Token token=123456:abcdefghijklmnopqrstuvwxyz",
        body="Do not leak DATABASE_URL=postgresql://user:secret@example.invalid/db",
        source_component="unit_test",
        created_at=NOW,
    )

    rendered = render_telegram_message(secret_message)

    assert "abcdefghijklmnopqrstuvwxyz" not in rendered
    assert "user:secret" not in rendered

    result = TelegramAlertAdapter(
        config=TelegramDeliveryConfig.from_mapping(_gated_env()),
        client=FakeTelegramClient(fail=True),
    ).dispatch(AlertDispatchRequest(message=secret_message, channels=("telegram",)))

    assert result.status == "failed_closed"
    assert result.external_calls_performed is True
    assert result.failure_code == "telegram_api_rejected"
    assert "secret" not in (result.error_message or "").lower()


def test_alert_router_covers_required_routing_categories() -> None:
    router = AlertRouter()

    assert router.route(_message()).channels == ("fake",)
    ai_route = router.route(
        build_ai_news_warning_alert(symbol="SPY", reason="fallback", created_at=NOW)
    )
    stop_route = router.route(build_protective_stop_missing_alert(symbol="SPY", created_at=NOW))
    loss_route = router.route(build_trade_outcome_alert(_loss_outcome(), created_at=NOW))

    assert ai_route.message.severity == "warning"
    assert stop_route.message.severity == "critical"
    assert loss_route.message.severity == "warning"


def test_alert_templates_cover_order_fill_stop_trade_reports_and_incidents() -> None:
    snapshot = _snapshot()
    daily = cast(
        DailyReport,
        generate_daily_report(report_date=date(2026, 5, 8), snapshot=snapshot).report,
    )
    start, end = default_week_bounds(date(2026, 5, 8))
    weekly = cast(
        WeeklyReport,
        generate_weekly_report(period_start=start, period_end=end, snapshot=snapshot).report,
    )
    messages = (
        build_test_alert(created_at=NOW),
        build_order_submitted_alert(symbol="SPY", quantity=1, order_type="limit", created_at=NOW),
        build_fill_alert(
            symbol="SPY",
            filled_quantity=1,
            average_price=500.00,
            partial=False,
            created_at=NOW,
        ),
        build_fill_alert(
            symbol="SPY",
            filled_quantity=0.5,
            average_price=500.00,
            partial=True,
            created_at=NOW,
        ),
        build_protective_stop_confirmed_alert(
            symbol="SPY",
            quantity=1,
            stop_price=490.00,
            created_at=NOW,
        ),
        build_protective_stop_missing_alert(symbol="SPY", created_at=NOW),
        build_trade_outcome_alert(_win_outcome(), created_at=NOW),
        build_trade_outcome_alert(_loss_outcome(), created_at=NOW),
        build_daily_report_alert(daily, created_at=NOW),
        build_weekly_report_alert(weekly, created_at=NOW),
        build_ai_news_warning_alert(
            symbol="SPY",
            reason="provider budget exceeded",
            created_at=NOW,
        ),
        build_reconciliation_mismatch_alert(
            summary="Broker/internal mismatch.",
            critical=True,
            created_at=NOW,
        ),
        build_kill_switch_alert(reason="manual", created_at=NOW),
        build_generic_incident_alert(
            title="Incident",
            body="Review required.",
            severity="warning",
            created_at=NOW,
        ),
    )

    bodies = "\n".join(message.body for message in messages)

    assert "Trade Closed: SPY" in bodies
    assert "Daily Report - Dry Run" in bodies
    assert "Weekly Report - Dry Run" in bodies
    assert all(message.created_at == NOW for message in messages)


def test_telegram_smoke_refuses_by_default_and_sends_with_fake_client_when_gated() -> None:
    refused = run_telegram_alert_smoke(env={}, client=FakeTelegramClient(), now=NOW)

    assert refused.refused is True
    assert refused.gates_loaded is False
    assert refused.messages_attempted == 0
    assert refused.messages_sent == 0

    client = FakeTelegramClient()
    sent = run_telegram_alert_smoke(
        env=_gated_env(
            TELEGRAM_ALERT_SMOKE_INCLUDE_REPORT_SAMPLE="true",
            TELEGRAM_ALERT_SMOKE_INCLUDE_TRADE_SAMPLE="true",
            TELEGRAM_ALERT_SMOKE_INCLUDE_CRITICAL_SAMPLE="true",
        ),
        client=client,
        now=NOW,
    )

    assert sent.gates_loaded is True
    assert sent.messages_attempted == 3
    assert sent.messages_sent == 3
    assert sent.message_limit_respected is True
    assert sent.raw_response_printed is False
    assert sent.secrets_printed is False
    assert len(client.messages) == 3


def _snapshot() -> ReportInputSnapshot:
    return ReportInputSnapshot(
        generated_at=NOW,
        environment="paper",
        dry_run=True,
        live_trading_enabled=False,
        autonomous_execution_enabled=False,
        candidates=({"symbol": "SPY", "candidate_status": "accepted"},),
        decisions=({"symbol": "SPY", "decision_status": "approved"},),
        positions=(),
        reconciliations=({"status": "clean", "mismatches": []},),
        incidents=(),
    )


def _win_outcome() -> TradeOutcomeSummary:
    return TradeOutcomeSummary(
        symbol="SPY",
        result="WIN",
        entry_price=500.00,
        exit_price=510.00,
        pnl_pct=2.0,
        r_multiple=1.2,
        exit_reason="technical exit",
    )


def _loss_outcome() -> TradeOutcomeSummary:
    return TradeOutcomeSummary(
        symbol="SPY",
        result="LOSS",
        entry_price=500.00,
        exit_price=490.00,
        pnl_pct=-2.0,
        r_multiple=-1.0,
        exit_reason="protective stop hit",
    )
